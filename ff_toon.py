#!/usr/bin/env python3
"""Spec 02 rubber-hose cartoon pipeline.

Everything here follows one rule from the spec: turn our limitations into the style.

  * black and white          -> the model's color drift cannot show
  * 4:3 at low resolution    -> period-correct AND far fewer pixels to generate
  * 12 fps ("on twos")       -> exactly how 1930s cartoons were drawn, and a free 2x
  * wobble and squash        -> rubber-hose animation, not an artifact
  * ONE unbroken chain       -> the fix for spec 01's slideshow: every shot starts
                                from the previous shot's last frame, never a new
                                text-to-image keyframe

Stages:
  1. character sheets  -- cheap stills, Graham picks one before any animation
  2. music             -- composed FIRST, at a fixed tempo (see ff_toon_music)
  3. the chain         -- Wan 2.2 5B image-to-video, each clip continuing the last
  4. assembly          -- bar-aligned cuts, B&W grade, grain, pillarbox for upload
"""
import os, math, subprocess

import ff_pastoral as P          # reuse the ComfyUI plumbing that already works

# --- format -----------------------------------------------------------------
W, H = 640, 480           # 4:3, both divisible by 16 for the VAE
FPS = 12                  # animate on twos
CHAR_CKPT = "DreamShaperXL_Turbo_v2_1.safetensors"   # fast + stylised; good for candidates

# --- musical grid -----------------------------------------------------------
# The whole point of bar-aligned editing: pick numbers where bars land on frames.
BPM = 120                 # 4/4 at 120 => one bar = 2.0 s = 24 frames at 12 fps
BEATS_PER_BAR = 4
FRAMES_PER_BAR = int(round(FPS * BEATS_PER_BAR * 60 / BPM))   # 24
CLIP_BARS = 5                                                 # 5 bars = 120 frames
CLIP_FRAMES = CLIP_BARS * FRAMES_PER_BAR                      # 120
GEN_FRAMES = CLIP_FRAMES + 1   # generate one extra; the seam frame gets dropped

WAN_STEPS = 20
WAN_CFG = 5.0
WAN_SHIFT = 8.0

# --- style ------------------------------------------------------------------
TOON_STYLE = (
    ", 1930s rubber hose cartoon, black and white animation cel, thick confident ink "
    "outlines, flat white gloves, pie-cut eyes, bouncy elastic limbs, simple shapes, "
    "vintage Fleischer Betty Boop and Silly Symphonies style, aged film stock, soft "
    "grain, high contrast, no color"
)
TOON_NEG = (
    "color, colour, photorealistic, 3d render, cgi, anime, manga, modern cartoon, "
    "text, watermark, logo, signature, letters, words, gore, realistic human face, "
    "photograph, lowres, jpeg artifacts, extra limbs, deformed hands"
)
# Wan's own Chinese negative rejects static frames; keep it verbatim (see spec 01).
TOON_MOTION_NEG = P.__dict__.get("_WAN_STOCK_NEG", "") or (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
    "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
    "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
    "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
) + "，color, text, watermark, subtitles, photorealistic, 3d render, scene change, jump cut"


# ---------------------------------------------------------------------------
# stage 1: character sheets  (cheap; Graham picks before anything expensive runs)
# ---------------------------------------------------------------------------

CHARACTER_CANDIDATES = [
    ("cricket",   "a cheerful cartoon cricket standing upright playing a tiny fiddle"),
    ("cat",       "a round cartoon alley cat standing upright sawing at a fiddle"),
    ("frog",      "a wide-mouthed cartoon frog standing upright playing a fiddle"),
    ("scarecrow", "a floppy cartoon scarecrow with a straw hat playing a fiddle"),
    ("mouse",     "a small cartoon mouse in short trousers playing a cello taller than itself"),
    ("owl",       "a sleepy cartoon owl perched on a branch playing a fiddle"),
    ("skeleton",  "a dancing cartoon skeleton playing a fiddle, Skeleton Dance style"),
    ("moon",      "a cartoon crescent moon with a face, playing a fiddle among clouds"),
]


def gen_character_sheet(name, prompt, seed, dest):
    """One candidate design: full figure, plain background, ready to judge."""
    if os.path.exists(dest):
        return dest
    full = (prompt + ", full body character model sheet, standing centered on a plain "
            "empty background, full figure visible head to toe" + TOON_STYLE)
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHAR_CKPT}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": full, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": TOON_NEG, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {
            # Turbo checkpoint: few steps, low cfg. Candidates are meant to be cheap.
            "seed": seed, "steps": 8, "cfg": 2.0, "sampler_name": "dpmpp_sde",
            "scheduler": "karras", "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        # Unique prefix per call on purpose: ComfyUI caches by node inputs, and an
        # identical workflow returns "executed in 0.00s" with NO outputs, which reads
        # as a failure. Varying the save node forces it to hand the file back.
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"fftoon_{name}_{seed}", "images": ["8", 0]}},
    }
    outs = P.run_workflow(wf, timeout_s=600)
    refs = (outs.get("9") or {}).get("images") or []
    if not refs:
        raise RuntimeError(f"character sheet '{name}' produced no image (outputs: {list(outs)})")
    P._fetch(refs[0], dest)
    return grayscale(dest, dest)


def character_sheets(outdir, seed, variants=2):
    """Render every candidate design, `variants` seeds each. Returns the file list."""
    os.makedirs(outdir, exist_ok=True)
    made = []
    for name, prompt in CHARACTER_CANDIDATES:
        for v in range(variants):
            dest = f"{outdir}/char-{name}-{v}.png"
            gen_character_sheet(name, prompt, seed * 100 + v, dest)
            print(f"sheet {name} v{v}", flush=True)
            made.append(dest)
    return made


def grayscale(src, dest):
    """Force true black and white. Cheap insurance: the model cannot drift a colour
    it is not allowed to have."""
    # ffmpeg cannot read and write the same path, and in-place is the common case here.
    tmp = dest + ".tmp.png"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vf",
                    "format=gray,eq=contrast=1.12:brightness=0.01", tmp],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------------------
# stage 3: the chain
# ---------------------------------------------------------------------------

def gen_chain_clip(start_png, motion_prompt, seed, mp4_dest, lastframe_dest):
    """One generation continuing from `start_png`, plus its final frame so the NEXT
    clip can continue from it. This is the whole anti-slideshow mechanism."""
    if os.path.exists(mp4_dest) and os.path.exists(lastframe_dest):
        return mp4_dest, lastframe_dest
    handle = P.upload_image(start_png)
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": P.WAN_UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": P.WAN_CLIP, "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": P.WAN_VAE}},
        "4": {"class_type": "LoadImage", "inputs": {"image": handle}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": motion_prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": TOON_MOTION_NEG, "clip": ["2", 0]}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
            "vae": ["3", 0], "width": W, "height": H, "length": GEN_FRAMES,
            "batch_size": 1, "start_image": ["4", 0]}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": WAN_SHIFT}},
        "9": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": WAN_STEPS, "cfg": WAN_CFG, "sampler_name": "uni_pc",
            "scheduler": "simple", "denoise": 1.0,
            "model": ["8", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "CreateVideo", "inputs": {"images": ["10", 0], "fps": float(FPS)}},
        "12": {"class_type": "SaveVideo", "inputs": {
            "video": ["11", 0], "filename_prefix": f"fftoonclip_{seed}", "format": "mp4", "codec": "h264"}},
        "13": {"class_type": "ImageFromBatch", "inputs": {
            "image": ["10", 0], "batch_index": GEN_FRAMES - 1, "length": 1}},
        "14": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"fftoonlast_{seed}", "images": ["13", 0]}},
    }
    outs = P.run_workflow(wf, timeout_s=5400)

    def one(node_id, what):
        refs = (outs.get(node_id) or {}).get("images") or []
        if not refs:
            raise RuntimeError(f"toon generation produced no {what} (node {node_id})")
        return refs[0]

    P._fetch(one("12", "video"), mp4_dest)
    P._fetch(one("14", "chain frame"), lastframe_dest)
    # The chain frame is what the next clip inherits, so it must already be grey —
    # otherwise colour creeps back in one clip at a time.
    grayscale(lastframe_dest, lastframe_dest)
    return mp4_dest, lastframe_dest


def render_chain(beats, character_png, outdir, seed):
    """Walk the beat list as ONE continuous chain. `beats` is a list of motion
    prompts, one per clip; each clip is CLIP_BARS bars long by construction."""
    os.makedirs(f"{outdir}/clips", exist_ok=True)
    start = character_png
    parts = []
    for i, motion in enumerate(beats):
        mp4 = f"{outdir}/clips/clip{i:03d}.mp4"
        last = f"{outdir}/clips/clip{i:03d}_last.png"
        gen_chain_clip(start, motion + TOON_STYLE, seed * 1000 + i, mp4, last)
        print(f"clip {i:03d}/{len(beats)}", flush=True)
        parts.append(mp4)
        start = last            # <- the chain. Never a fresh keyframe.
    return parts


# ---------------------------------------------------------------------------
# stage 4: assembly — bar-aligned cuts, then the 1930s look
# ---------------------------------------------------------------------------

def assemble(parts, dest):
    """Hard cuts on the downbeat. Each clip is trimmed to exactly CLIP_FRAMES, which
    is a whole number of bars, so every cut lands on a beat with no drift.

    Note the deliberate difference from spec 01: NO cross-dissolves. Dissolving is
    what made the pastoral film read as a slideshow of cards. Cartoons cut."""
    ins, fc, labels = [], [], []
    for n, p in enumerate(parts):
        ins += ["-i", p]
        # drop the duplicated seam frame on every clip after the first
        fc.append(f"[{n}:v]trim=start_frame={1 if n else 0}:end_frame={(1 if n else 0) + CLIP_FRAMES},"
                  f"setpts=PTS-STARTPTS[p{n}]")
        labels.append(f"[p{n}]")
    fc.append("".join(labels) + f"concat=n={len(parts)}:v=1:a=0[o]")
    subprocess.run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[o]",
                    "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", dest],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def period_look(src, dest):
    """Black and white, contrast, grain and a gentle vignette — the aged-stock look.
    Applied once at the end so it is consistent across the whole film."""
    vf = ("format=gray,eq=contrast=1.15:brightness=0.01:gamma=0.98,"
          "noise=alls=9:allf=t+u,"          # per-frame grain, the way film moves
          "vignette=PI/5")
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vf", vf, "-c:v", "libx264",
                    "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", dest],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def pillarbox(src, dest, out_w=1280, out_h=720):
    """4:3 centred in a 16:9 frame for upload. We generate what our hardware is best
    at and let the platform present it — never the other way round."""
    vf = (f"scale={int(out_h*4/3)}:{out_h}:flags=lanczos,"
          f"pad={out_w}:{out_h}:(ow-iw)/2:0:black")
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vf", vf, "-c:v", "libx264",
                    "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", dest],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def mux(video, music_wav, dest):
    subprocess.run(["ffmpeg", "-y", "-i", video, "-i", music_wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "256k", "-movflags", "+faststart", "-shortest", dest],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def film_seconds(n_clips):
    return n_clips * CLIP_FRAMES / FPS


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "sheets":
        seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        out = f"{P.__dict__.get('ROOT', '/home/gpaasch/filmforge')}/runs/toon-sheets-{seed}"
        P.preflight()
        for f in character_sheets(out, seed):
            print(f, flush=True)
