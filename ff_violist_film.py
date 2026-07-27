#!/usr/bin/env python3
"""The violist short, built the way the research says: paint once, transport by rig.

One diffusion call for the whole film. The bow is the only part that moves rigidly,
so it is cut from the painted keyframe by the rig's own mask and slid along exactly
the axis the drawing used. Everything else is the same painted pixels every frame,
which is precisely why the violin can no longer disappear.
"""
import math, os

from PIL import Image

import ff_propagate as PR
import ff_puppet_viola as V
import ff_pastoral as P


def build(seconds=10, seed=9, workdir="/home/gpaasch/filmforge/runs/violist-film"):
    import ff_toon_music, make_film as MF, ff_progress, ff_puppet_render as R
    os.makedirs(workdir, exist_ok=True)
    P.preflight()
    size = (V.W, V.H)
    fps = V.FPS

    # 1. music first; the score drives the bow
    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    print(f"music {meta}; {len(notes)} onsets", flush=True)

    total = int(seconds * fps)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"violist-{seed}", total + 1, "painting the one keyframe")

    # 2. ONE painted keyframe
    key_line = f"{workdir}/key_line.png"
    V.frame(0, notes).save(key_line)
    R.PROMPT = ("a 1930s rubber hose cartoon girl playing a violin on a small stage, "
                "black and white vintage cartoon, thick ink outlines, big eyes, "
                "curtains and footlights, cel animation, aged film stock, high contrast")
    painted_path = f"{workdir}/key_painted.png"
    R.paint_frame(key_line, seed, painted_path)
    painted = Image.open(painted_path).convert("RGB")
    prog.step(); prog.stage = "transporting the paint"
    print("keyframe painted", flush=True)

    # 3. parts. The bow is the only thing that must move; everything else is one
    #    plate, because a plate that never moves can never flicker.
    ux, uy = V.bow_axis()
    TRAVEL = 74.0          # matches the drawing's own bow excursion

    def draw_body(im):
        from PIL import ImageDraw
        V.draw_stage(ImageDraw.Draw(im), 0, 0.5)
        V.draw_violist(ImageDraw.Draw(im), 0, 0.0, 0.0, 0.0, only="body")
        # the plate also owns the un-moving parts of the figure
        V.draw_violist(ImageDraw.Draw(im), 0, 0.0, 0.0, 0.0)

    def draw_bow(im):
        from PIL import ImageDraw
        V.draw_violist(ImageDraw.Draw(im), 0, 0.0, 0.0, 0.0, only="bow")

    def body_xform(t):
        return (0, 0, 0.0, None)

    def bow_xform(t):
        pos, _pitch, _atk = V.bow_state(t, notes)
        d = (pos - 0.0) * TRAVEL
        return (ux * d, uy * d, 0.0, None)

    parts = [PR.Part("body", draw_body, body_xform, z=0),
             PR.Part("bow", draw_bow, bow_xform, z=1)]

    frames_dir = PR.propagate(painted, parts, total, fps, size, f"{workdir}/frames")
    prog.finish("encoding")

    out = f"/home/gpaasch/filmforge/films/violist-{seed}.mp4"
    PR.encode(frames_dir, music, out, fps)
    print("flicker", PR.flicker_score(frames_dir), flush=True)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    build(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 10)
