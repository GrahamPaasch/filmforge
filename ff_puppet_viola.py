#!/usr/bin/env python3
"""A rubber-hose violist, animated straight off the score.

This is the idea spec 02 started from, finally built the way it should be: not a
character who happens to be near music, but a character whose every movement is
*read out of the MIDI*. The bow changes direction on each note onset. The stage
lamp pulses on the beat. Little ink notes leave the f-hole when the score says a
note begins, and their height is the pitch that was actually played.

Nothing here is estimated or eyeballed. If the music changes, the animation changes
with it, because the animation IS the music — which is what Carl Stalling meant when
he said the music shouldn't fit the action, the music should BE the action.

Pipeline: compose -> read the MIDI -> draw -> paint through ControlNet.
"""
import math, os, subprocess

import mido
from PIL import Image, ImageDraw

import ff_puppet
from ff_puppet import bez, hose, circle, INK, PAPER

W, H = ff_puppet.W, ff_puppet.H
FPS = ff_puppet.FPS


# ---------------------------------------------------------------------------
# the score, as animation data
# ---------------------------------------------------------------------------

def read_score(midi_path, bpm):
    """Return note onsets as (seconds, pitch, velocity). The animation reads from
    this and nothing else, so picture and sound cannot drift apart."""
    mid = mido.MidiFile(midi_path)
    spb = 60.0 / bpm
    notes, t_ticks = [], 0
    for msg in mid.tracks[0]:
        t_ticks += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            notes.append((t_ticks / mid.ticks_per_beat * spb, msg.note, msg.velocity))
    return notes


def bow_state(t, notes):
    """Where the bow is, and which way it is travelling, at time t.

    One stroke per note, alternating down-bow and up-bow — which is what a player
    actually does, and why this reads as playing rather than sawing. Position eases
    across the stroke instead of moving linearly, because a real bow arm
    accelerates out of the change and settles into it."""
    idx = -1
    for i, (ts, _, _) in enumerate(notes):
        if ts <= t:
            idx = i
        else:
            break
    if idx < 0:
        return 0.0, 0, 0.0
    start, pitch, vel = notes[idx]
    end = notes[idx + 1][0] if idx + 1 < len(notes) else start + 0.5
    span = max(0.06, end - start)
    f = min(1.0, (t - start) / span)
    eased = 0.5 - 0.5 * math.cos(math.pi * f)          # ease in and out
    direction = 1 if idx % 2 == 0 else -1
    pos = eased if direction > 0 else 1.0 - eased
    return pos, pitch, min(1.0, (t - start) / 0.12)     # third value: attack flash


# ---------------------------------------------------------------------------
# the drawing
# ---------------------------------------------------------------------------

def draw_stage(d, t, pulse):
    """A little proscenium. The lamp glow pulses with the attack of each note, so
    even the lighting is on the score."""
    floor = H * 0.78
    d.line([(0, floor), (W, floor)], fill=INK, width=6)
    # curtains: swagged arcs, drawn heavy like a cel background
    for side in (0, 1):
        x0 = -60 if side == 0 else W - 130
        for k in range(4):
            d.arc([x0 + k * 26, -80, x0 + 190 + k * 26, floor - 40],
                  start=250 if side == 0 else 200, end=340 if side == 0 else 290,
                  fill=INK, width=5)
    # footlights
    for k in range(7):
        x = 60 + k * (W - 120) / 6
        r = 9 + 5 * pulse
        circle(d, (x, floor + 16), r, fill=None, outline=INK, width=4)
    # a moon through the back
    circle(d, (W * 0.80, H * 0.20), 46 + 4 * pulse, fill=None, outline=INK, width=5)
    circle(d, (W * 0.80 - 16, H * 0.20 - 10), 8, fill=INK, outline=INK, width=1)
    circle(d, (W * 0.80 + 12, H * 0.20 + 14), 5, fill=INK, outline=INK, width=1)


def draw_notes_floating(d, t, notes):
    """Ink notes drift up out of the instrument — one per onset, height set by the
    pitch that was actually played, fading over about a second and a half."""
    for (ts, pitch, vel) in notes:
        age = t - ts
        if not (0 <= age <= 1.6):
            continue
        rise = age * 92
        x = W * 0.44 + 40 * math.sin(age * 2.4 + pitch)
        y = H * 0.46 - rise - (pitch - 55) * 2.0
        r = max(2.0, 7 - age * 2.6)
        if r <= 2.1:
            continue
        d.ellipse([x - r * 1.25, y - r, x + r * 1.25, y + r], fill=INK)
        d.line([(x + r * 1.2, y), (x + r * 1.2, y - r * 3.4)], fill=INK, width=3)
        d.arc([x + r * 1.2, y - r * 3.8, x + r * 4.2, y - r * 1.4],
              start=200, end=340, fill=INK, width=3)


def _draw_bow_only(d, on_axis, nx, ny, ux, uy, pos, shoulder):
    """The bow alone, in rig space -- the only part that must move rigidly."""
    bow_at = on_axis(30 + 74 * pos, 0)
    bpx, bpy = nx * 96, ny * 96
    frog = (bow_at[0] - bpx * 0.35 + ux * 6, bow_at[1] - bpy * 0.35 + uy * 6)
    tip = (bow_at[0] + bpx * 0.65, bow_at[1] + bpy * 0.65)
    d.line([frog, tip], fill=INK, width=6)
    d.line([(frog[0] + ux * 4, frog[1] + uy * 4),
            (tip[0] + ux * 4, tip[1] + uy * 4)], fill=INK, width=2)


def _draw_body_extras(d, shoulder, head_c, attack):
    """Head and left arm, drawn when the body plate is rendered on its own."""
    circle(d, head_c, 36, fill=PAPER, outline=INK, width=6)
    for sx in (-1, 1):
        eye = (head_c[0] + sx * 12 - 6, head_c[1] - 6)
        circle(d, eye, 10, fill=PAPER, outline=INK, width=3)
        circle(d, (eye[0] - 2, eye[1] + 2 + 2 * attack), 5, fill=INK, outline=INK, width=1)
    d.arc([head_c[0] - 20, head_c[1] + 6, head_c[0] + 6, head_c[1] + 24],
          start=0, end=180, fill=INK, width=4)
    for dx, dy, r in ((-30, -20, 13), (-6, -34, 15), (22, -22, 12)):
        circle(d, (head_c[0] + dx, head_c[1] + dy), r, fill=INK, outline=INK, width=1)


def bow_axis(sway=0.0):
    """Expose the bow's travel direction so the propagation rig can move the painted
    bow along exactly the line the drawing used."""
    hip = (W * 0.46, H * 0.64 + 2 * sway)
    shoulder = (hip[0] - 2, hip[1] - 86 + sway)
    tail = (shoulder[0] - 54, shoulder[1] + 6)
    scroll_end = (shoulder[0] - 196, shoulder[1] - 34)
    ux, uy = scroll_end[0] - tail[0], scroll_end[1] - tail[1]
    L = math.hypot(ux, uy)
    return ux / L, uy / L


def draw_violist(d, t, pos, attack, sway, only=None):
    """The player, staged for silhouette.

    The first version failed because everything overlapped: the instrument sat on
    her face, the bow crossed her head, and the legs merged into the dress as one
    black mass. Every choice below is about SEPARATION -- forms held apart so each
    one still reads when the picture is 32 pixels wide.
    """
    hip = (W * 0.46, H * 0.64 + 2 * sway)
    shoulder = (hip[0] - 2, hip[1] - 86 + sway)
    head_c = (shoulder[0] + 2, shoulder[1] - 52)

    # --- legs: two clearly separate diagonals, NOT a filled skirt over a blob ---
    for sx, spread in ((-1, 34), (1, 62)):
        knee = (hip[0] - spread, hip[1] + 52)
        foot = (hip[0] - spread - 16, H * 0.80)
        hose(d, hip, knee, foot, width=13)
        d.ellipse([foot[0] - 20, foot[1] - 8, foot[0] + 12, foot[1] + 10], fill=INK)

    # --- torso: an open outline, so it is a shape and not a silhouette-eating slab
    d.line([hip, shoulder], fill=INK, width=26)
    circle(d, ((hip[0] + shoulder[0]) / 2, (hip[1] + shoulder[1]) / 2 + 6), 6,
           fill=PAPER, outline=PAPER, width=1)

    # --- the instrument: held OUT to her left, well below the chin, big enough to
    # be an instrument rather than a smudge. Real viola grammar: figure-eight body
    # with waist corners, long fingerboard, scroll, f-holes, bridge, four strings.
    tail = (shoulder[0] - 54, shoulder[1] + 6)          # body end, out from the body
    scroll_end = (shoulder[0] - 196, shoulder[1] - 34)  # scroll, far out to the left
    ux = (scroll_end[0] - tail[0]) / 1.0
    uy = (scroll_end[1] - tail[1]) / 1.0
    L = math.hypot(ux, uy)
    ux, uy = ux / L, uy / L
    nx, ny = -uy, ux                                    # normal to the instrument axis

    def on_axis(dist, off=0.0):
        return (tail[0] + ux * dist + nx * off, tail[1] + uy * dist + ny * off)

    # The instrument as a SOLID BLACK silhouette. The previous version was an open
    # outline with f-holes and four strings inside it, and the painter read that as
    # a spoked disc and drew a little machine. An unmistakable filled violin
    # silhouette gives it nothing to reinterpret -- shape first, detail never.
    outline = []
    for dist, off in ((0, 0), (8, 26), (22, 32), (34, 15), (44, 13), (56, 27),
                      (70, 30), (82, 14), (88, 4)):
        outline.append(on_axis(dist, off))
    for dist, off in ((88, -4), (82, -14), (70, -30), (56, -27), (44, -13),
                      (34, -15), (22, -32), (8, -26)):
        outline.append(on_axis(dist, off))
    d.polygon(outline, fill=INK)

    # neck and fingerboard: one solid tapering bar, then the scroll curl
    d.line([on_axis(84, 0), on_axis(176, 0)], fill=INK, width=15)
    circle(d, on_axis(186, 4), 13, fill=INK, outline=INK, width=1)
    circle(d, on_axis(186, 4), 5, fill=PAPER, outline=PAPER, width=1)

    # TWO f-holes as thin white slits cut INTO the black body -- negative space is
    # what says "violin"; black marks on white said "wheel".
    for off in (-15, 15):
        a0 = on_axis(34, off)
        a1 = on_axis(52, off)
        d.line([a0, a1], fill=PAPER, width=4)

    # --- the bow: crosses the STRINGS at a right angle, never the face ---
    # `only` lets the propagation pipeline render each rigid part in isolation, so
    # the painted keyframe can be cut into parts by the rig's own masks rather than
    # by a guessed bounding box (which sliced her head in half last time).
    if only == "body":
        _draw_body_extras(d, shoulder, head_c, attack)
        return
    if only == "bow":
        _draw_bow_only(d, on_axis, nx, ny, ux, uy, pos, shoulder)
        return
    bow_at = on_axis(30 + 74 * pos, 0)
    bpx, bpy = nx * 96, ny * 96
    frog = (bow_at[0] - bpx * 0.35 + ux * 6, bow_at[1] - bpy * 0.35 + uy * 6)
    tip = (bow_at[0] + bpx * 0.65, bow_at[1] + bpy * 0.65)
    d.line([frog, tip], fill=INK, width=6)          # stick
    d.line([(frog[0] + ux * 4, frog[1] + uy * 4),
            (tip[0] + ux * 4, tip[1] + uy * 4)], fill=INK, width=2)   # hair

    # bow arm reaches the frog, held clear of the torso so a gap survives
    hand = frog
    elbow = (shoulder[0] - 6, shoulder[1] + 62)
    hose(d, shoulder, elbow, hand, width=11)
    circle(d, hand, 11, fill=PAPER, outline=INK, width=4)

    # left arm goes UNDER the instrument to the fingerboard
    lh = on_axis(132, 0)
    l_elbow = (shoulder[0] - 78, shoulder[1] + 52)
    hose(d, shoulder, l_elbow, lh, width=10)
    circle(d, lh, 10, fill=PAPER, outline=INK, width=4)

    # --- head, tilted toward the instrument but NOT touching it ---
    circle(d, head_c, 36, fill=PAPER, outline=INK, width=6)
    for sx in (-1, 1):
        eye = (head_c[0] + sx * 12 - 6, head_c[1] - 6)
        circle(d, eye, 10, fill=PAPER, outline=INK, width=3)
        circle(d, (eye[0] - 2, eye[1] + 2 + 2 * attack), 5, fill=INK, outline=INK, width=1)
    d.arc([head_c[0] - 20, head_c[1] + 6, head_c[0] + 6, head_c[1] + 24],
          start=0, end=180, fill=INK, width=4)
    # hair as separate lobes above the skull, not merged into it
    for dx, dy, r in ((-30, -20, 13), (-6, -34, 15), (22, -22, 12)):
        circle(d, (head_c[0] + dx, head_c[1] + dy), r, fill=INK, outline=INK, width=1)


def frame(n, notes, background=True, only=None):
    t = n / FPS
    pos, pitch, attack = bow_state(t, notes)
    flash = max(0.0, 1.0 - attack)
    img = Image.new("L", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # The silhouette gate judges the FIGURE alone: a backdrop that spans the frame
    # would trip every border and fragmentation check and hide the real problem.
    if background:
        draw_stage(d, t, flash)
    draw_violist(d, t, pos, flash, 3 * math.sin(t * 2.1), only=only)
    if background:
        draw_notes_floating(d, t, notes)
    return img


# ---------------------------------------------------------------------------

def render(seconds=15, seed=3,
           workdir="/home/gpaasch/filmforge/runs/viola", paint=True):
    import ff_toon_music, make_film as MF, ff_progress
    os.makedirs(f"{workdir}/drawn", exist_ok=True)
    os.makedirs(f"{workdir}/painted", exist_ok=True)

    # MUSIC FIRST -- everything on screen is derived from it.
    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = read_score(midi, meta['bpm'])
    print(f"music {meta}; {len(notes)} note onsets drive the animation", flush=True)

    total = int(seconds * FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"viola-{seed}", total, "drawing to the score")
    for n in range(total):
        frame(n, notes).save(f"{workdir}/drawn/f{n:04d}.png")
    print(f"drew {total} frames", flush=True)

    src = f"{workdir}/drawn"
    if paint:
        import ff_puppet_render as R
        R.PROMPT = ("a 1930s rubber hose cartoon character playing a viola on a small stage, "
                    "black and white vintage cartoon, thick ink outlines, pie-cut eyes, white "
                    "gloves, curtains and footlights, musical notes floating in the air, "
                    "cel animation, aged film stock, high contrast")
        prog.stage = "painting through ControlNet"
        for n in range(total):
            out = f"{workdir}/painted/f{n:04d}.png"
            if not os.path.exists(out):
                R.paint_frame(f"{workdir}/drawn/f{n:04d}.png", seed, out)
            prog.step()
        src = f"{workdir}/painted"
    prog.finish("encoding + music")

    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{src}/f%04d.png",
                    "-vf", "format=gray,noise=alls=6:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/viola-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 15)
