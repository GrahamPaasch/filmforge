#!/usr/bin/env python3
"""Paint the puppet: ControlNet-conditioned rendering of code-drawn frames.

This is the synthesis of everything spec 02 learned the hard way.

  * Wan (spec 02 attempt 1) melted, because it is trained on real video.
  * AnimateDiff (attempt 2) melted at its 16-frame window seams.
  * The code puppet (attempt 3) cannot melt -- but Graham's verdict was fair:
    "the character doesn't look as good... I think we need to use some kind of
    GPU generation."

Both halves were right. So: the puppet supplies the STRUCTURE and the diffusion
model supplies the ART. Each drawn frame is fed to ControlNet as line art, so the
model is not free to invent geometry -- it can only render the pose it is handed.
Identity is guaranteed by the rig; quality comes from ToonYou.

The same seed for every frame keeps the rendering consistent, and because the input
line art is temporally perfect, the output inherits that stability.
"""
import os, subprocess

import ff_pastoral as P
import ff_progress
import ff_puppet

CKPT = "toonyou_beta6.safetensors"
CONTROLNET = "control_v11p_sd15_lineart.safetensors"

# Strength matters more than any other knob here. Too low and the model wanders off
# the rig (which is the failure we are trying to eliminate); too high and it just
# traces the input and adds nothing.
CN_STRENGTH = 0.95
# THE consistency fix. At denoise 1.0 every frame is generated from fresh noise with
# the line art as a hint only, so each frame is independently re-imagined -- Graham:
# "if I asked you to draw a square moving across the screen, you'd give me a square,
# a circle, a triangle, a rhombus." ControlNet conditions space, it does NOT promise
# temporal identity.
#
# Starting from the DRAWING and only lightly repainting it inverts that: the input
# sequence is already perfectly consistent, so at low denoise the output inherits
# that consistency. Low enough to keep the instrument; high enough to add art.
DENOISE = 0.42
STEPS = 20
CFG = 6.5

PROMPT = ("a 1930s rubber hose cartoon girl riding a bicycle down a country road, "
          "black and white vintage cartoon, thick ink outlines, pie-cut eyes, white "
          "gloves, cel animation, aged film stock, high contrast")
NEG = ("color, photorealistic, 3d render, photograph, realistic, modern anime, text, "
       "watermark, signature, blurry, lowres, extra limbs, deformed")

RUN_TAG = os.getpid()


def paint_frame(png, seed, dest):
    """Render one drawn frame through ControlNet. The drawing is the control image;
    the model never sees a latent it is free to reshape."""
    handle = P.upload_image(png)
    wf = {
        "4":  {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "10": {"class_type": "LoadImage", "inputs": {"image": handle}},
        "11": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["4", 1]}},
        "7":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["4", 1]}},
        "12": {"class_type": "ControlNetApplyAdvanced", "inputs": {
            "positive": ["6", 0], "negative": ["7", 0], "control_net": ["11", 0],
            "image": ["10", 0], "strength": CN_STRENGTH,
            "start_percent": 0.0, "end_percent": 1.0}},
        # img2img: the latent IS the drawn frame, not empty noise.
        "5":  {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["4", 2]}},
        "3":  {"class_type": "KSampler", "inputs": {
            # One fixed seed across the whole film: the line art already guarantees
            # temporal consistency, so re-rolling noise per frame would only add
            # shimmer.
            "seed": seed, "steps": STEPS, "cfg": CFG, "sampler_name": "euler",
            "scheduler": "normal", "denoise": DENOISE,
            "model": ["4", 0], "positive": ["12", 0], "negative": ["12", 1],
            "latent_image": ["5", 0]}},
        "8":  {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9":  {"class_type": "SaveImage", "inputs": {
            "filename_prefix": f"ffpaint_{RUN_TAG}_{os.path.basename(png)[:-4]}",
            "images": ["8", 0]}},
    }
    outs = P.run_workflow(wf, timeout_s=1200)
    refs = (outs.get("9") or {}).get("images") or []
    if not refs:
        raise RuntimeError(f"paint produced no image for {png}")
    return P._fetch(refs[0], dest)


def render(seconds=10, seed=1, want_music=True,
           workdir="/home/gpaasch/filmforge/runs/puppet-painted"):
    import ff_toon_music, make_film as MF
    P.preflight()
    draw_dir = f"{workdir}/drawn"
    paint_dir = f"{workdir}/painted"
    os.makedirs(draw_dir, exist_ok=True)
    os.makedirs(paint_dir, exist_ok=True)

    total = int(seconds * ff_puppet.FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"puppet-painted-{seed}", total, "drawing the rig")
    for n in range(total):
        ff_puppet.frame(n, total).save(f"{draw_dir}/f{n:04d}.png")
    print(f"drew {total} frames", flush=True)

    prog.stage = "painting through ControlNet"
    for n in range(total):
        out = f"{paint_dir}/f{n:04d}.png"
        if not os.path.exists(out):
            paint_frame(f"{draw_dir}/f{n:04d}.png", seed, out)
        prog.step()
        if n % 12 == 0:
            print(f"painted {n}/{total}", flush=True)

    prog.finish("encoding + music")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(ff_puppet.FPS),
                    "-i", f"{paint_dir}/f%04d.png",
                    "-vf", "format=gray,noise=alls=6:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(ff_puppet.FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out = f"/home/gpaasch/filmforge/films/puppet-painted-{seed}.mp4"
    if want_music:
        n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
        midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
        music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                                MF.FS, MF.SF, MF.SOX, MF.SFLIB)
        print(f"music {meta}", flush=True)
        subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                        "-shortest", "-movflags", "+faststart", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", silent, "-c", "copy", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 10)
