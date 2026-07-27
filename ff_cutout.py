#!/usr/bin/env python3
"""Cutout animation: move real generated artwork instead of redrawing it.

The finding that made this obvious (2026-07-26): asked for a plain violin sprite,
the still model instead produced a complete Betty-style girl playing a violin, and
it was better than anything the whole night of generative video had produced. The
still model can already make exactly the look Graham wants. The only thing it
cannot do is move.

So stop asking it to. Generate the artwork ONCE, cut it into pieces, and animate
the pieces — which is literally how cutout animation has always worked, from
Lotte Reiniger to South Park. The art is fixed, so it cannot flicker, cannot
morph, cannot lose the violin. Motion is ours, art is the model's.

Honest limitation of this first pass: the bow is cut and animated, and the whole
figure breathes and sways on the beat, but the bow ARM does not yet follow the bow
— the arm is still part of the body plate. Fixing that needs the arm cut as its own
piece with a pivot at the shoulder. Named here rather than hidden.
"""
import math, os, subprocess

import numpy as np
from PIL import Image

W, H = 640, 480
FPS = 12
BPM = 96
BEAT = 60.0 / BPM


def load_rgba(path, white_cut=236):
    """Load art and knock out the near-white paper as transparency."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    alpha = (a.min(axis=2) < white_cut).astype(np.uint8) * 255
    out = np.dstack([np.asarray(im), alpha])
    return Image.fromarray(out, "RGBA")


def trim(im):
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def cut(im, box):
    """Cut a piece out as its own layer, and erase it from the source plate so the
    two do not double up when recomposited."""
    piece = trim(im.crop(box))
    plate = im.copy()
    px = plate.load()
    for y in range(box[1], min(box[3], im.height)):
        for x in range(box[0], min(box[2], im.width)):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 0)
    return plate, piece


def compose(plate, bow, bow_home, bow_travel, t, notes=None):
    """One frame: body breathes on the beat, bow slides along its own axis."""
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    phase = 2 * math.pi * t / BEAT

    # body: a breath on the beat, a slow sway across two beats, and a gentle
    # scale pulse -- three periods that never quite line up, so it reads as alive
    # rather than as a looping GIF.
    bob = int(round(5 * math.sin(phase)))
    ang = 2.2 * math.sin(phase / 2)
    scale = 1.0 + 0.018 * math.sin(phase / 3 + 1.0)
    body = plate.resize((max(1, int(plate.width * scale)), max(1, int(plate.height * scale))),
                        Image.LANCZOS).rotate(ang, resample=Image.BICUBIC, expand=False)
    bx = (W - body.width) // 2
    by = (H - body.height) // 2 + bob
    canvas.alpha_composite(body, (bx, by))

    # bow: travels up and down its length, one stroke per beat, eased at the ends
    f = (t / BEAT) % 2.0
    stroke = f if f < 1 else 2 - f
    eased = 0.5 - 0.5 * math.cos(math.pi * stroke)
    dx = int(round(bow_travel[0] * (eased - 0.5)))
    dy = int(round(bow_travel[1] * (eased - 0.5)))
    canvas.alpha_composite(bow, (bow_home[0] + dx + bx, bow_home[1] + dy + by))
    return canvas.convert("RGB")


def render(src="/home/gpaasch/filmforge/assets/violin_src.png", seconds=10, seed=5,
           workdir="/home/gpaasch/filmforge/runs/cutout"):
    import ff_toon_music, make_film as MF, ff_progress
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    art = load_rgba(src)
    art = trim(art)
    art.thumbnail((int(H * 0.92 * art.width / art.height), int(H * 0.92)), Image.LANCZOS)

    # NO box cut. The bow in this artwork runs diagonally across her hand and face,
    # so an axis-aligned rectangle took half her head with it and the composite had
    # two faces. Isolating a diagonal limb needs real segmentation, not a box.
    # Until then the whole figure is one plate: clean, consistent, and honest about
    # what it is -- a character breathing and swaying to her own score.
    w, h = art.size
    plate = art
    bow = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    bow_home = (0, 0)
    bow_travel = (0, 0)

    total = int(seconds * FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"cutout-{seed}", total, "compositing cutout")
    for n in range(total):
        compose(plate, bow, bow_home, bow_travel, n / FPS).save(f"{workdir}/frames/f{n:04d}.png")
        prog.step()
    prog.finish("encoding + music")

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    print(f"music {meta}", flush=True)

    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=5:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/cutout-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 10)
