#!/usr/bin/env python3
"""A one-minute violinist short: generated poses, code-animated world, cut to the bar.

The architecture that finally works, stated plainly:

  * the still model makes the ART -- it is excellent at this and always was
  * the code makes the MOTION -- camera moves, the world, and the cutting
  * nothing is ever regenerated, so nothing can flicker, morph, or lose the violin

Each shot is ONE generated pose card held for a whole number of bars while the
camera moves across it, with a hand-drawn world animating behind. Cuts land on the
downbeat. This is exactly how a 1930s musical short was assembled -- limited
animation, strong poses, and the score carrying the motion -- and it is also the
only approach out of five tried that survived Graham's eye.

A minute renders in seconds because the expensive part happened once, offline.
"""
import math, os, subprocess

import numpy as np
from PIL import Image, ImageDraw

import ff_puppet_viola as V
import ff_toon_music

W, H = 854, 640          # 4:3-ish at a size the pose art fills nicely
FPS = 12
POSES = ["play", "lift", "spin", "bow", "close"]
ART = "/home/gpaasch/filmforge/assets/poses"


def _card_space(plate):
    """Put a loaded plate back on a 768x768 canvas so the hand-read coordinates
    above still line up after cropping and scaling."""
    canvas = Image.new("RGBA", (768, 768), (0, 0, 0, 0))
    p = plate.resize((int(plate.width * 768 / plate.height), 768), Image.LANCZOS)
    canvas.alpha_composite(p, ((768 - p.width) // 2, 0))
    return canvas


def load_plate(name, height_frac=0.86):
    """One pose card, background knocked out, scaled to sit on the stage floor."""
    im = Image.open(f"{ART}/{name}.png").convert("RGB")
    a = np.asarray(im).astype(np.int16)
    # The generated cards sit on slightly-off-white "paper" with a drawn border, and
    # a loose threshold kept that paper as a visible rectangle behind her. Cut hard,
    # then drop the outer frame the model likes to draw around its own picture.
    inset = int(min(im.size) * 0.055)
    a = a[inset:-inset, inset:-inset]
    im = im.crop((inset, inset, im.width - inset, im.height - inset))
    ink = (a.min(axis=2) < 205)
    # Her dress, skin and gloves are WHITE, so a plain brightness cut made her
    # see-through and the curtain lines showed straight through her body. Flood the
    # background in from the border instead, and treat everything the flood cannot
    # reach as part of the figure -- holes filled, character solid.
    bg = np.zeros(ink.shape, dtype=bool)
    stack = [(0, x) for x in range(ink.shape[1])] + [(ink.shape[0] - 1, x) for x in range(ink.shape[1])]
    stack += [(y, 0) for y in range(ink.shape[0])] + [(y, ink.shape[1] - 1) for y in range(ink.shape[0])]
    stack = [(y, x) for (y, x) in stack if not ink[y, x]]
    for y, x in stack:
        bg[y, x] = True
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < ink.shape[0] and 0 <= nx < ink.shape[1] \
                    and not bg[ny, nx] and not ink[ny, nx]:
                bg[ny, nx] = True
                stack.append((ny, nx))
    alpha = (~bg).astype(np.uint8) * 255
    rgba = Image.fromarray(np.dstack([np.asarray(im), alpha]), "RGBA")
    rgba = rgba.crop(rgba.getbbox())
    h = int(H * height_frac)
    rgba = rgba.resize((max(1, int(rgba.width * h / rgba.height)), h), Image.LANCZOS)
    return rgba


# ---------------------------------------------------------------------------
# cutout rigging of the generated art
# ---------------------------------------------------------------------------

# Read off the 'play' pose card (768x768) by eye, the way a cutout animator cuts a
# puppet: the bow runs as a long diagonal from her hand at the lower left up past
# the scroll, and the bow hand grips the frog. Cutting the bow AND the hand as one
# rigid piece lets it slide along its own axis, which is what bowing actually is.
BOW_AXIS = (0.713, -0.701)          # unit vector along the bow, lower-left -> upper-right
BOW_QUAD = [(300, 415), (352, 330), (660, 60), (612, 118)]   # the stick
BOW_HAND = ((352, 356), 52)         # centre, radius -- travels with the bow
BOW_TRAVEL = 46.0                   # px at card scale, half-excursion


def split_bow(card):
    """Return (body_without_bow, bow_piece) for the play card, in card space."""
    mask = Image.new("L", card.size, 0)
    md = ImageDraw.Draw(mask)
    md.polygon(BOW_QUAD, fill=255)
    (hx, hy), hr = BOW_HAND
    md.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=255)
    bow = card.copy()
    bow.putalpha(Image.composite(card.getchannel("A"), Image.new("L", card.size, 0), mask))
    body = card.copy()
    inv = Image.eval(mask, lambda v: 255 - v)
    body.putalpha(Image.composite(card.getchannel("A"), Image.new("L", card.size, 0), inv))
    return body, bow


def draw_world(d, t, pulse, drift):
    """The stage, animated in code: curtains, footlights that answer every attack,
    a moon, and a floor. The character is a held pose -- so the WORLD carries the
    movement, which is the oldest trick in limited animation."""
    floor = H * 0.86
    d.rectangle([0, 0, W, H], fill=255)
    # back curtain: vertical folds that breathe slowly
    for k in range(14):
        x = k * (W / 13.0)
        w = 3 + 2 * math.sin(t * 0.7 + k)
        d.line([(x, -10), (x + 18 * math.sin(t * 0.25 + k * 0.4), floor - 60)],
               fill=0, width=int(max(2, w)))
    # swags across the top
    for k in range(5):
        x0 = k * (W / 4.2) - 40
        d.arc([x0, -110, x0 + 260, 90], start=20, end=160, fill=0, width=6)
    # moon, pulsing on the note attacks
    r = 46 + 7 * pulse
    cx, cy = W * 0.83, H * 0.18
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=6)
    d.ellipse([cx - 18, cy - 12, cx - 6, cy], fill=0)
    d.ellipse([cx + 8, cy + 10, cx + 17, cy + 19], fill=0)
    # floor and footlights
    d.line([(0, floor), (W, floor)], fill=0, width=7)
    for k in range(9):
        x = 40 + k * (W - 80) / 8
        rr = 11 + 6 * pulse
        d.ellipse([x - rr, floor + 12 - rr, x + rr, floor + 12 + rr], outline=0, width=4)
    # dust motes drifting, so even empty air is moving
    for k in range(18):
        px = (k * 97 + drift * (30 + k % 7)) % W
        py = (k * 53 + math.sin(t * 0.6 + k) * 14) % (floor - 40) + 20
        d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=0)


def draw_notes(d, t, notes):
    """Ink notes leaving the instrument, one per onset, height set by real pitch."""
    for (ts, pitch, vel) in notes:
        age = t - ts
        if not (0 <= age <= 2.0):
            continue
        x = W * 0.30 + 54 * math.sin(age * 2.2 + pitch)
        y = H * 0.52 - age * 96 - (pitch - 55) * 2.2
        r = max(2.0, 8 - age * 3.0)
        if r <= 2.2 or y < 0:
            continue
        d.ellipse([x - r * 1.3, y - r, x + r * 1.3, y + r], fill=0)
        d.line([(x + r * 1.25, y), (x + r * 1.25, y - r * 3.4)], fill=0, width=3)


def shot_plan(total_bars, bars_per_shot=2):
    """One pose per shot, cut on the downbeat, cycling so no pose repeats back to
    back. Camera move alternates push-in and drift so cuts feel deliberate."""
    plan = []
    n = total_bars // bars_per_shot
    for i in range(n):
        plan.append({"pose": POSES[i % len(POSES)],
                     "bars": bars_per_shot,
                     "move": ("push" if i % 3 == 0 else "drift" if i % 3 == 1 else "pull")})
    return plan


def render(seconds=60, seed=11, workdir="/home/gpaasch/filmforge/runs/violist-short"):
    import make_film as MF, ff_progress
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    print(f"music {meta}; {len(notes)} onsets", flush=True)

    plates = {p: load_plate(p) for p in POSES}
    # The play pose is rigged: its bow is a separate piece that slides on the beat,
    # so the hero shots actually play instead of holding still.
    play_card = load_plate("play")
    scale_to_card = play_card.height / 768.0
    body_plate, bow_plate = split_bow(_card_space(play_card))
    rigged = {"body": body_plate, "bow": bow_plate, "scale": scale_to_card}
    plan = shot_plan(n_bars)
    bar_s = ff_toon_music.BAR_SECONDS
    total = int(seconds * FPS)

    ff_progress.install_page()
    prog = ff_progress.Progress(f"violist-short-{seed}", total, "compositing")

    for n in range(total):
        t = n / FPS
        # which shot are we in, and how far through it
        bar = t / bar_s
        acc, shot, shot_t = 0, plan[-1], 0.0
        for s in plan:
            if bar < acc + s["bars"]:
                shot, shot_t = s, (bar - acc) * bar_s
                break
            acc += s["bars"]
        shot_len = shot["bars"] * bar_s
        f = shot_t / shot_len

        # attack flash from the real score
        last = max([ts for (ts, _, _) in notes if ts <= t], default=-9)
        pulse = max(0.0, 1.0 - (t - last) / 0.16)

        img = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(img)
        draw_world(d, t, pulse, t * 6)
        base = img.convert("RGBA")

        plate = plates[shot["pose"]]
        rig_this_shot = shot["pose"] == "play"
        # camera: a slow move across the held pose is what keeps a static drawing alive
        if shot["move"] == "push":
            sc = 1.00 + 0.10 * f
        elif shot["move"] == "pull":
            sc = 1.10 - 0.10 * f
        else:
            sc = 1.04
        dx = int((-30 + 60 * f) if shot["move"] == "drift" else 0)
        if rig_this_shot:
            # bow position comes from the score: one stroke per note, eased, and the
            # hand travels with it so the wrist stretches like a rubber hose
            pos, _pitch, _atk = V.bow_state(t, notes)
            off = (pos - 0.5) * 2 * BOW_TRAVEL
            hb, hw = rigged["body"], rigged["bow"]
            comp = Image.new("RGBA", hb.size, (0, 0, 0, 0))
            comp.alpha_composite(hb)
            comp.alpha_composite(hw, (int(round(BOW_AXIS[0] * off)),
                                      int(round(BOW_AXIS[1] * off))))
            src = comp.crop(comp.getbbox())
            h = int(H * 0.86)
            src = src.resize((max(1, int(src.width * h / src.height)), h), Image.LANCZOS)
        else:
            src = plate
        pw, ph = int(src.width * sc), int(src.height * sc)
        p = src.resize((pw, ph), Image.LANCZOS)
        base.alpha_composite(p, ((W - pw) // 2 + dx, int(H * 0.86) - ph))

        d2 = ImageDraw.Draw(base)
        draw_notes(d2, t, notes)
        base.convert("L").save(f"{workdir}/frames/f{n:04d}.png")
        prog.step()

    prog.finish("encoding")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=6:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/violist-short-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 60)
