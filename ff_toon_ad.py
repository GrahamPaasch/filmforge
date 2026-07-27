#!/usr/bin/env python3
"""Spec 02, second attempt at motion: AnimateDiff over a cartoon-trained base.

Why this instead of Wan. Wan 2.2 is trained on real video, so whatever style you
hand it, it pulls the picture back toward photorealism frame by frame — that is
what produced the melting realistic/cartoon hybrid Graham rejected. AnimateDiff
inverts the relationship: the motion module carries ONLY motion, and every pixel of
style comes from the base checkpoint. Point it at ToonYou and it cannot render
anything but a cartoon, because it has never seen anything else.

Trade-off, stated honestly: AnimateDiff generates in 16-frame context windows with
overlap rather than one continuous take, so long shots are stitched by the sampler
rather than truly continuous. For a bouncing 1930s short that is acceptable; for
spec 01's water it would not have been.
"""
import os, subprocess

import ff_pastoral as P
import ff_farm

# ComfyUI caches by node inputs: re-running an identical workflow returns
# "executed in 0.00s" with NO outputs, which reads as a failure. Tagging the save
# node per process makes every run ask for its file back.
RUN_TAG = os.getpid()

CKPT = "toonyou_beta6.safetensors"          # SD1.5, cartoon-native
MOTION = "v3_sd15_mm.ckpt"                  # the mature SD1.5 motion module
W, H = 512, 384                             # 4:3, SD1.5's comfortable range
FPS = 12                                    # on twos, played back as-is here
CONTEXT = 16                                # AnimateDiff's native window
OVERLAP = 4

STYLE = ("1930s rubber hose cartoon, black and white, thick ink outlines, pie-cut eyes, "
         "flat white gloves, bouncy elastic limbs, vintage Fleischer animation, film grain")
NEG = ("color, photorealistic, 3d render, realistic skin, photograph, modern anime, text, "
       "watermark, signature, extra limbs, deformed hands, blurry, lowres")


def animate(prompt, frames, seed, dest_dir, name):
    """One AnimateDiff generation, returned as a list of PNG frames."""
    wf = {
        "4":  {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "20": {"class_type": "ADE_AnimateDiffUniformContextOptions", "inputs": {
            "context_length": CONTEXT, "context_stride": 1, "context_overlap": OVERLAP,
            "context_schedule": "uniform", "closed_loop": False, "fuse_method": "flat"}},
        "21": {"class_type": "ADE_AnimateDiffLoaderGen1", "inputs": {
            "model": ["4", 0], "model_name": MOTION, "beta_schedule": "autoselect",
            "context_options": ["20", 0]}},
        "5":  {"class_type": "EmptyLatentImage", "inputs": {
            "width": W, "height": H, "batch_size": frames}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {
            "text": f"{prompt}, {STYLE}", "clip": ["4", 1]}},
        "7":  {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["4", 1]}},
        "3":  {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 20, "cfg": 8.0, "sampler_name": "euler",
            "scheduler": "normal", "denoise": 1.0,
            "model": ["21", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["5", 0]}},
        "8":  {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9":  {"class_type": "SaveImage", "inputs": {
            "filename_prefix": f"ffad_{RUN_TAG}_{name}_{seed}", "images": ["8", 0]}},
    }
    outs = P.run_workflow(wf, timeout_s=3600)
    refs = (outs.get("9") or {}).get("images") or []
    if not refs:
        raise RuntimeError(f"AnimateDiff produced no frames (outputs: {list(outs)})")
    os.makedirs(dest_dir, exist_ok=True)
    paths = []
    for i, r in enumerate(refs):
        p = f"{dest_dir}/{name}_{i:04d}.png"
        P._fetch(r, p)
        paths.append(p)
    return paths


def frames_to_clip(frame_dir, name, dest):
    """Frames -> a clip, with the period grade applied in the same pass."""
    return ff_farm.ffmpeg_job(
        [f"{frame_dir}/{name}_%04d.png"],
        ["-vf", "format=gray,eq=contrast=1.15:brightness=0.01,noise=alls=8:allf=t+u,vignette=PI/5",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
         "-r", str(FPS)],
        dest, prefer_remote=False, input_args=["-framerate", str(FPS)])


def make(seed=11, shots=None, want_music=True):
    import ff_toon_music, make_film as MF
    ROOT = "/home/gpaasch/filmforge"
    shots = shots or SHOTS
    d = f"{ROOT}/runs/toonad-{seed}"
    os.makedirs(d, exist_ok=True)
    P.preflight()

    # Frames per shot must stay on the musical grid: at 96bpm played back at 12fps,
    # one bar is exactly 30 frames, so one shot is one bar. Derive the score length
    # from the picture rather than guessing -- getting this wrong once already
    # produced a 5s score under a 10s film, which -shortest then truncated.
    FRAMES_PER_SHOT = 30
    total_seconds = len(shots) * FRAMES_PER_SHOT / FPS
    n_bars = max(1, round(total_seconds / ff_toon_music.BAR_SECONDS))

    music = None
    if want_music:
        midi, meta = ff_toon_music.compose_toon(d, seed, n_bars)
        print(f"music {meta}", flush=True)
        music = ff_toon_music.render_toon_music(d, midi, f"{d}/music.wav",
                                                MF.FS, MF.SF, MF.SOX, MF.SFLIB)

    clips = []
    for i, shot in enumerate(shots):
        fdir = f"{d}/frames"
        animate(shot, FRAMES_PER_SHOT, seed * 100 + i, fdir, f"s{i:02d}")
        clips.append(frames_to_clip(fdir, f"s{i:02d}", f"{d}/clip{i:02d}.mp4"))
        print(f"shot {i:02d}/{len(shots)}", flush=True)

    concat = f"{d}/list.txt"
    with open(concat, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    silent = f"{d}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat,
                    "-c", "copy", silent], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out = f"{ROOT}/films/toonad-{seed}.mp4"
    if music:
        subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                        "-movflags", "+faststart", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", silent, "-c", "copy", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


SHOTS = [
    "a cartoon dancing girl with a big round head and huge eyes sways and dances on a small stage",
    "the cartoon girl spins on the spot, her skirt flaring out",
    "the cartoon girl kicks her legs high one after the other, bouncing",
    "the cartoon girl shimmies her shoulders and waves both arms overhead",
]


if __name__ == "__main__":
    import sys
    make(seed=int(sys.argv[1]) if len(sys.argv) > 1 else 11)
