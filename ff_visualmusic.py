#!/usr/bin/env python3
"""Visual music: the score, drawn.

First-principles reset. Five attempts at a character performing an action all failed
the same way, because character performance is the single most labour-intensive thing
in animation — studios hired rooms of people for it, and no amount of prompt or rig
patching substitutes.

But the premise was optional. Fischinger and McLaren made films from pure moving
shapes cut to music, and that form is built out of exactly what we are strongest at:
deterministic geometry, a fixed tempo, and a score we wrote ourselves and can read
note by note. Nothing here can melt, flicker, lose a prop or grow an extra arm,
because there is no character to lose.

Every mark on screen comes from the MIDI:
  * each note onset spawns a form; its height is the pitch, its size the velocity
  * the bass register drives the deep field, the melody the fine detail
  * the piece changes visual motif at section boundaries, on the downbeat
  * a slow ground rotation gives the eye somewhere to travel between attacks
"""
import math, os, subprocess

import numpy as np
from PIL import Image, ImageDraw

import ff_toon_music

W, H = 854, 640
FPS = 12
CX, CY = W / 2, H / 2

MOTIFS = ["rings", "bars", "rays", "lattice", "orbits"]


def note_layers(notes):
    """Split the score by register. Bass carries weight, melody carries detail —
    the same division an orchestrator would make, applied to shapes."""
    bass = [n for n in notes if n[1] < 55]
    mid = [n for n in notes if 55 <= n[1] < 72]
    top = [n for n in notes if n[1] >= 72]
    return bass, mid, top


def ground(d, t, spin, energy):
    """A persistent field under everything.

    The first pass was three dots on white: technically driven by the score, visually
    empty. A film needs something on screen BETWEEN attacks, so the notes have
    somewhere to land. This is the paper the music is written on."""
    # concentric ground rings, always present, breathing with overall energy
    for k in range(1, 14):
        r = k * 46 + 18 * math.sin(t * 0.5 + k * 0.6) + energy * 22
        d.ellipse([CX - r, CY - r * 0.72, CX + r, CY + r * 0.72], outline=0,
                  width=1 if k % 3 else 2)
    # a slowly turning radial comb
    for k in range(36):
        a = spin * 0.35 + k * math.pi / 18
        r0, r1 = 34, 300 + 60 * math.sin(t * 0.4 + k)
        d.line([(CX + r0 * math.cos(a), CY + r0 * 0.72 * math.sin(a)),
                (CX + r1 * math.cos(a), CY + r1 * 0.72 * math.sin(a))],
               fill=0, width=1)


def env(t, ts, attack=0.05, decay=1.1):
    """A note's visual envelope: instant attack, exponential decay. Shapes should
    behave like sound, not like objects."""
    a = t - ts
    if a < 0 or a > decay:
        return 0.0
    if a < attack:
        return a / attack
    return max(0.0, (1.0 - (a - attack) / (decay - attack))) ** 1.6


def draw_rings(d, t, layers, spin):
    bass, mid, top = layers
    for (ts, pitch, vel) in bass:
        e = env(t, ts, decay=3.4)
        if e <= 0.01:
            continue
        r = 40 + (1 - e) * 420
        d.ellipse([CX - r, CY - r, CX + r, CY + r], outline=0,
                  width=max(1, int(2 + 9 * e)))
    for (ts, pitch, vel) in mid + top:
        e = env(t, ts, decay=2.6)
        if e <= 0.02:
            continue
        ang = spin + pitch * 0.5
        rr = 90 + (pitch - 55) * 7
        x, y = CX + rr * math.cos(ang), CY + rr * math.sin(ang)
        s = 4 + 26 * e * (vel / 110)
        d.ellipse([x - s, y - s, x + s, y + s], fill=0)


def draw_bars(d, t, layers, spin):
    bass, mid, top = layers
    for (ts, pitch, vel) in mid + top:
        e = env(t, ts, decay=2.2)
        if e <= 0.02:
            continue
        x = CX + (pitch - 66) * 26
        h = 30 + 300 * e * (vel / 110)
        w = max(3, int(16 * e))
        d.rectangle([x - w, CY - h / 2, x + w, CY + h / 2], fill=0)
    for (ts, pitch, vel) in bass:
        e = env(t, ts, decay=3.0)
        if e <= 0.02:
            continue
        y = CY + 200 * math.sin(spin * 0.4 + pitch)
        d.rectangle([0, y - 6 * e, W, y + 6 * e], fill=0)


def draw_rays(d, t, layers, spin):
    bass, mid, top = layers
    for (ts, pitch, vel) in mid + top:
        e = env(t, ts, decay=2.4)
        if e <= 0.02:
            continue
        ang = spin * 0.6 + pitch * 0.42
        L = 120 + 340 * e
        d.line([(CX, CY), (CX + L * math.cos(ang), CY + L * math.sin(ang))],
               fill=0, width=max(2, int(3 + 10 * e)))
    for (ts, pitch, vel) in bass:
        e = env(t, ts, decay=3.2)
        if e <= 0.02:
            continue
        r = 30 + 260 * (1 - e)
        d.arc([CX - r, CY - r, CX + r, CY + r], start=0, end=360, fill=0,
              width=max(1, int(8 * e)))


def draw_lattice(d, t, layers, spin):
    bass, mid, top = layers
    step = 78
    amp = sum(env(t, ts, decay=0.9) for (ts, _p, _v) in mid) * 6
    for i in range(-1, int(W / step) + 2):
        x = i * step + 18 * math.sin(spin + i)
        d.line([(x, 0), (x + amp * math.sin(spin * 1.3 + i), H)], fill=0,
               width=max(1, int(2 + amp * 0.12)))
    for (ts, pitch, vel) in bass:
        e = env(t, ts, decay=2.8)
        if e <= 0.02:
            continue
        y = CY + (pitch - 45) * 9
        d.line([(0, y), (W, y)], fill=0, width=max(2, int(3 + 12 * e)))


def draw_orbits(d, t, layers, spin):
    bass, mid, top = layers
    for k, (ts, pitch, vel) in enumerate(mid + top):
        e = env(t, ts, decay=2.9)
        if e <= 0.02:
            continue
        rr = 60 + (pitch % 12) * 26
        ang = spin * (1 + (pitch % 5) * 0.2) + k
        x, y = CX + rr * math.cos(ang), CY + rr * 0.62 * math.sin(ang)
        s = 3 + 20 * e
        d.ellipse([x - s, y - s, x + s, y + s], outline=0, width=max(1, int(2 + 4 * e)))
    for (ts, pitch, vel) in bass:
        e = env(t, ts, decay=3.6)
        if e <= 0.02:
            continue
        r = 26 + 340 * (1 - e)
        d.ellipse([CX - r, CY - r * 0.62, CX + r, CY + r * 0.62], outline=0,
                  width=max(1, int(2 + 7 * e)))


def accents(d, t, bpm, beats_per_bar=4):
    """Hard visual hits on the beat.

    Measured: the audio and the MIDI agree to 4 ms, so the film was never actually
    out of sync -- but long decay envelopes smeared every attack, so the eye had
    nothing sharp to lock onto and it READ as unsynced. Perceived sync needs an
    unmistakable, short event exactly on the beat.

    Returns an invert flag for the downbeat, which is the strongest accent in the
    silent-film vocabulary: one frame of reversed field."""
    beat = 60.0 / bpm
    pos = t / beat
    idx = int(pos)
    frac = pos - idx
    # a snap ring that fires on every beat and is gone in a sixth of a second
    hit = max(0.0, 1.0 - frac * beat / 0.16)
    if hit > 0:
        r = 30 + 300 * (1 - hit)
        d.ellipse([CX - r, CY - r * 0.72, CX + r, CY + r * 0.72], outline=0,
                  width=max(2, int(14 * hit)))
        # corner ticks: they read even when the centre is busy
        m = int(26 * hit)
        for (x, y, sx, sy) in ((0, 0, 1, 1), (W, 0, -1, 1), (0, H, 1, -1), (W, H, -1, -1)):
            d.line([(x, y), (x + sx * m * 3, y)], fill=0, width=8)
            d.line([(x, y), (x, y + sy * m * 3)], fill=0, width=8)
    # the downbeat inverts the whole frame for one frame
    return (idx % beats_per_bar == 0) and frac < (1.0 / FPS) / beat


DRAW = {"rings": draw_rings, "bars": draw_bars, "rays": draw_rays,
        "lattice": draw_lattice, "orbits": draw_orbits}


def render(seconds=60, seed=13, workdir="/home/gpaasch/filmforge/runs/visualmusic"):
    import make_film as MF, ff_progress, ff_puppet_viola as V
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    layers = note_layers(notes)
    print(f"music {meta}; {len(notes)} onsets "
          f"({len(layers[0])} bass / {len(layers[1])} mid / {len(layers[2])} top)", flush=True)

    bar_s = ff_toon_music.BAR_SECONDS
    bars_per_section = 4
    total = int(seconds * FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"visualmusic-{seed}", total, "drawing the score")

    for n in range(total):
        t = n / FPS
        section = int((t / bar_s) // bars_per_section)
        motif = MOTIFS[section % len(MOTIFS)]
        # the ground turns slowly and never resets, so successive sections never
        # land in the same place twice
        spin = t * 0.55

        # how loud the music is right now, used to breathe the whole field
        energy = sum(env(t, ts, decay=1.2) for (ts, _p, _v) in notes if abs(t - ts) < 1.4)
        energy = min(3.0, energy)

        img = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(img)
        ground(d, t, spin, energy)
        DRAW[motif](d, t, layers, spin)
        flip = accents(d, t, meta["bpm"])
        if flip:
            img = Image.eval(img, lambda v: 255 - v)
            d = ImageDraw.Draw(img)
        # a held frame at the section change would read as a cut; a shrinking iris
        # over the first half-bar reads as an edit
        into = (t / bar_s) % bars_per_section
        if into < 0.5:
            r = int(900 * into / 0.5)
            if r < 900:
                m = Image.new("L", (W, H), 255)
                ImageDraw.Draw(m).ellipse([CX - r, CY - r, CX + r, CY + r], fill=0)
                img = Image.composite(img, Image.new("L", (W, H), 255), m)
        img.save(f"{workdir}/frames/f{n:04d}.png")
        prog.step()

    prog.finish("encoding")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=7:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/visualmusic-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 60)
