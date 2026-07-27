#!/usr/bin/env python3
"""Bind the cut layers to the proven rig: real drawing, real mechanics.

Everything needed for this already exists and was earned separately tonight:

  * ff_meshrig  -- prop-first solve with contacts that pass an acceptance gate
  * ff_layers   -- the master illustration cut into layers with hidden overlap
  * ff_toon_music -- the score the bowing is read from

This module is only the join. Each layer names the bone it rides and a pivot in
master-image space; every frame, the rig is solved as usual and each layer is placed
by its bone's transform. No pixel is ever regenerated, so the art is exactly the
drawing the model made, and the motion is exactly the mechanism the gate approved.

Known simplification, stated rather than hidden: the arm is ONE layer covering upper
arm and forearm together, so it is rotated to aim at the solved hand rather than
bending at the solved elbow. At cartoon scale that reads; splitting the arm into two
layers is the obvious next refinement.
"""
import json, math, os, subprocess

from PIL import Image

import ff_meshrig as R

W, H = R.W, R.H
FPS = R.FPS
LAYERS_DIR = "/home/gpaasch/filmforge/assets/layers"

# Where each layer attaches, and its pivot in the 768-space of the master drawing.
BIND = {
    "hair_back": ("head",    (364, 120)),
    "head":      ("head",    (364, 120)),
    "torso":     ("chest",   (376, 290)),
    "skirt":     ("chest",   (380, 400)),
    "legs":      ("chest",   (380, 470)),
    "far_arm":   ("far_arm", (452, 228)),
    "bow_arm":   ("bow_arm", (300, 228)),
    "bow_hand":  ("bow_hand", (350, 356)),
    "violin":    ("violin",  (392, 250)),
    "bow":       ("bow",     (350, 344)),
}

# The master drawing is 768 tall; the rig works in screen pixels. One scale for all
# layers keeps the character in proportion with itself.
ART_SCALE = 0.78


def load_layers():
    man = json.load(open(f"{LAYERS_DIR}/manifest.json"))
    out = []
    for L in sorted(man["layers"], key=lambda x: x["z"]):
        if L["name"] not in BIND:
            continue
        im = Image.open(L["path"]).convert("RGBA")
        bone, pivot = BIND[L["name"]]
        out.append({"name": L["name"], "z": L["z"], "img": im,
                    "bone": bone, "pivot": pivot})
    return out


def place(canvas, layer, pos, angle_deg, scale=ART_SCALE):
    """Put one layer down with its pivot at `pos`, rotated about that pivot."""
    im = layer["img"]
    px, py = layer["pivot"]
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.LANCZOS)
        px, py = px * scale, py * scale
    if abs(angle_deg) > 1e-6:
        im = im.rotate(angle_deg, resample=Image.BICUBIC, center=(px, py))
    canvas.alpha_composite(im, (int(round(pos[0] - px)), int(round(pos[1] - py))))


def bone_transforms(rig, v, b, arms, sway):
    """Where each named bone sits this frame, and how far it has turned from the
    master drawing's rest pose."""
    def ang(a, c):
        return -math.degrees(math.atan2(c[1] - a[1], c[0] - a[0]))

    # rest angles measured off the master illustration
    REST = {"bow_arm": ang((300, 228), (350, 356)),
            "far_arm": ang((452, 228), (540, 266)),
            "violin": ang((352, 288), (634, 250)),
            "bow": ang((306, 404), (642, 56))}

    r_sh, _r_el, r_hand = arms["r"]
    l_sh, _l_el, l_hand = arms["l"]
    vx, vy = v["axis"]
    return {
        "chest":   (v["chest"], sway * 1.5),
        "head":    ((v["chin"][0] + 22, v["chin"][1] - 40), sway * 2.5),
        "violin":  (v["tail"], ang(v["tail"], v["scroll"]) - REST["violin"]),
        "bow":     (b["grip"], ang(b["grip"], b["tip"]) - REST["bow"]),
        "bow_arm": (r_sh, ang(r_sh, r_hand) - REST["bow_arm"]),
        "far_arm": (l_sh, ang(l_sh, l_hand) - REST["far_arm"]),
        "bow_hand": (r_hand, ang(b["grip"], b["tip"]) - REST["bow"]),
    }


def render(seconds=20, seed=29, workdir="/home/gpaasch/filmforge/runs/bound"):
    import ff_toon_music, make_film as MF, ff_progress, ff_puppet_viola as V
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    print(f"music {meta}; {len(notes)} onsets", flush=True)

    layers = load_layers()
    rig = R.ViolinRig()
    total = int(seconds * FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"bound-{seed}", total, "binding art to the rig")

    states = []
    for n in range(total):
        t = n / FPS
        sway = math.sin(t * 0.8)
        phase, _p, _a = V.bow_state(t, notes)
        slide = 0.5 + 0.5 * math.sin(t * 0.35)

        v = rig.violin(t, sway)
        b = rig.bow(v, phase)
        a = rig.arms(v, b, slide)
        bt = bone_transforms(rig, v, b, a, sway)

        states.append({"grip": b["grip"], "r_hand": a["r"][2],
                       "fingerboard": a["fingerboard"], "l_hand": a["l"][2],
                       "clamped": a["clamped"], "branch": (a["r"][1][0] > a["r"][0][0])})

        canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        # stage behind the character, drawn by the rig's own hand
        last = max([ts for (ts, _p, _v) in notes if ts <= t], default=-9)
        pulse = max(0.0, 1.0 - (t - last) / 0.18)
        from PIL import ImageDraw
        d = ImageDraw.Draw(canvas)
        floor = H * 0.90
        for k in range(16):
            x = k * (W / 15.0)
            d.line([(x, -10), (x + 14 * math.sin(t * 0.3 + k * 0.5), floor - 70)],
                   fill=(0, 0, 0, 255), width=2)
        d.line([(0, floor), (W, floor)], fill=(0, 0, 0, 255), width=7)
        for k in range(9):
            x = 44 + k * (W - 88) / 8
            r = 10 + 5 * pulse
            d.ellipse([x - r, floor + 14 - r, x + r, floor + 14 + r],
                      outline=(0, 0, 0, 255), width=4)

        for L in layers:
            pos, angle = bt[L["bone"]]
            place(canvas, L, pos, angle)

        canvas.convert("L").save(f"{workdir}/frames/f{n:04d}.png")
        prog.step()

    rep = R.check(states)
    print(f"acceptance: {'PASS' if rep['pass'] else 'FAIL'}", flush=True)
    for line in rep["fails"][:4]:
        print("  ", line, flush=True)

    prog.finish("encoding")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=5:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/bound-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 20)
