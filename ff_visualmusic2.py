#!/usr/bin/env python3
"""Visual music, take two: STEPPED on the beat.

Why the first version read as unsynced even though audio and MIDI measured aligned
to 4 ms: everything on screen moved continuously. Continuous motion never reads as
locked to a pulse — the eye has no event to match against the ear. Sync is perceived
from DISCRETE CHANGE.

So this version holds still, then snaps. The main form changes state only at beat
boundaries and is then perfectly static until the next one. A held frame followed by
an instant change is the entire trick; it is also why 1930s cartoons pose-hold on
the beat rather than easing through it.

Design rules, deliberately austere:
  * one dominant form, quantised to the beat, no interpolation whatsoever
  * the whole field inverts on the downbeat, for one beat, not one frame
  * the bar count is legible on screen as a row of ticks that fills up
  * everything else is subordinate and sparse enough not to compete
"""
import math, os, subprocess

from PIL import Image, ImageDraw

import ff_toon_music

W, H = 854, 640
FPS = 12
CX, CY = W / 2, H / 2


def beat_state(idx, notes_by_beat):
    """Everything about a beat is a pure function of its index -- so the picture is
    constant within a beat and can only change at the boundary."""
    n = notes_by_beat.get(idx, [])
    pitch = max((p for (_t, p, _v) in n), default=60)
    vel = max((v for (_t, _p, v) in n), default=70)
    return {
        "sides": 3 + (idx % 6),                  # triangle .. octagon, cycling
        "radius": 110 + (pitch - 48) * 5.5,
        "rot": (idx % 12) * math.pi / 6,
        "weight": max(4, int(vel / 8)),
        "offset": ((idx * 137) % 5 - 2) * 46,    # steps sideways, never slides
        "count": 1 + (idx % 3),
    }


def poly(d, cx, cy, r, sides, rot, width):
    pts = [(cx + r * math.cos(rot + k * 2 * math.pi / sides),
            cy + r * math.sin(rot + k * 2 * math.pi / sides)) for k in range(sides)]
    d.polygon(pts, outline=0)
    d.line(pts + [pts[0]], fill=0, width=width, joint="curve")


def render(seconds=60, seed=17, workdir="/home/gpaasch/filmforge/runs/vm2"):
    import make_film as MF, ff_progress, ff_puppet_viola as V
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    bpm = meta["bpm"]
    beat = 60.0 / bpm
    beats_per_bar = 4

    by_beat = {}
    for (ts, p, v) in notes:
        by_beat.setdefault(int(ts / beat + 1e-6), []).append((ts, p, v))

    # At 12 fps the frame that carries a change lands on average half a frame AFTER
    # the beat -- up to 83 ms late, which Graham could see ("a little bit behind the
    # music"). Perception is also asymmetric: sound arriving before its picture reads
    # as wrong far sooner than the reverse. So fire the picture slightly early.
    LEAD = 0.5 / FPS + 0.02          # half a frame, plus a small perceptual margin

    total = int(seconds * FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"vm2-{seed}", total, "stepping the beat")

    for n in range(total):
        t = n / FPS
        idx = int((t + LEAD) / beat + 1e-9)
        st = beat_state(idx, by_beat)
        downbeat = (idx % beats_per_bar == 0)
        bar_no = idx // beats_per_bar

        img = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(img)

        # the dominant form: static for the whole beat, then a hard change
        for k in range(st["count"]):
            r = st["radius"] * (1 - 0.22 * k)
            poly(d, CX + st["offset"], CY, r, st["sides"], st["rot"] + k * 0.3,
                 st["weight"])

        # bar counter: four ticks, filled up to the current beat in the bar
        for k in range(beats_per_bar):
            x = CX - 90 + k * 60
            y = H - 60
            filled = (idx % beats_per_bar) >= k
            if filled:
                d.rectangle([x - 18, y - 14, x + 18, y + 14], fill=0)
            else:
                d.rectangle([x - 18, y - 14, x + 18, y + 14], outline=0, width=4)

        # bar number as a row of marks along the top -- the film's own bar sheet
        for k in range(bar_no % 12 + 1):
            d.rectangle([30 + k * 26, 30, 30 + k * 26 + 12, 54], fill=0)

        # the whole field inverts for the WHOLE downbeat, not one frame
        if downbeat:
            img = Image.eval(img, lambda v: 255 - v)

        img.save(f"{workdir}/frames/f{n:04d}.png")
        prog.step()

    prog.finish("encoding")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=6:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/vm2-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 60)
