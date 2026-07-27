#!/usr/bin/env python3
"""Gate G2 from the mesh-rig plan: a flat-colour violinist rig, contacts first.

The plan's own advice is to prove the mechanism before spending a minute on art:
a flat-colour, untextured bow cycle that shows stable IK, correct contacts and no
branch flips. If that does not read as playing, no amount of texture will save it.

The correction that matters, and the one we had backwards all evening:

    the PROP determines the HAND, not the reverse.

So every frame is solved in this order — violin from the chest and chin anchors,
bow phase from the musical timing, bow placed so its hair sits in the string
corridor, then the bowing arm solved by IK **to the bow's grip landmark**, then the
fingering arm solved to the fingerboard. The arms are consequences. Nothing is
keyframed independently, so a hand cannot drift off the thing it is holding.
"""
import json, math, os, subprocess

from PIL import Image, ImageDraw

W, H = 854, 640
FPS = 12
INK, PAPER = 0, 255


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def two_bone_ik(root, target, l1, l2, bend_sign=+1, margin=3.0):
    """Analytic two-link IK. Returns (joint, reachable_target, clamped).

    bend_sign is chosen ONCE per arm and held for the whole shot -- that is what
    stops the elbow snapping inside-out mid-stroke."""
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = math.hypot(dx, dy)
    lo, hi = abs(l1 - l2) + margin, l1 + l2 - margin
    dd = min(max(d, lo), hi)
    clamped = abs(dd - d) > 1e-9
    if d < 1e-9:
        target, d = (root[0] + dd, root[1]), dd
    elif clamped:
        target = (root[0] + dx / d * dd, root[1] + dy / d * dd)
        d = dd
    ux, uy = (target[0] - root[0]) / d, (target[1] - root[1]) / d
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    mx, my = root[0] + a * ux, root[1] + a * uy
    j = (mx - bend_sign * h * uy, my + bend_sign * h * ux)
    return j, target, clamped


def lerp(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


# ---------------------------------------------------------------------------
# the rig
# ---------------------------------------------------------------------------

class ViolinRig:
    """Bones and props, in the plan's hierarchy: root -> chest -> {neck/head,
    violin_anchor, two arms}. Lengths are the researched proportions."""

    def __init__(self):
        self.chest = (W * 0.50, H * 0.52)
        # Measured against the actual targets rather than guessed: the bow grip sits
        # 121-200 px from the shoulder and the fingerboard 157-197 px, so a 152 px
        # arm could not reach either and the gate correctly refused the shot.
        # Reach is set to comfortably span the far end with margin to spare, which
        # also keeps the elbow off the fully-extended singularity.
        self.upper = 112.0
        self.fore = 106.0
        self.shoulder_dx = 46.0
        self.head_r = 44.0

    # --- props first -------------------------------------------------------
    def violin(self, t, sway):
        """Rigid, constrained between the chest and the chin. It never follows a
        hand; the hands will follow it."""
        chest = (self.chest[0] + sway * 6, self.chest[1])
        chin = (chest[0] + 6, chest[1] - 96)
        tail = (chin[0] - 26, chin[1] + 16)
        scroll = (chin[0] - 214, chin[1] - 34)
        ux, uy = scroll[0] - tail[0], scroll[1] - tail[1]
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        return {"chest": chest, "chin": chin, "tail": tail, "scroll": scroll,
                "axis": (ux, uy), "normal": (-uy, ux), "length": L}

    def bow(self, v, phase):
        """Bowing is the bow travelling along ITS OWN length while the contact point
        stays put on the string.

        The first version slid the contact up and down the string instead, which is
        a glissando of contact point, not a bow stroke -- Graham saw it immediately
        as "going forward and back rather than side to side". The bow crosses the
        strings at roughly a right angle, so its travel is along the violin's NORMAL,
        not its axis.
        """
        ux, uy = v["axis"]
        nx, ny = v["normal"]
        # contact sits at a fixed point between bridge and fingerboard
        contact = (v["tail"][0] + ux * 96, v["tail"][1] + uy * 96)
        # phase 0..1 = frog to tip; the whole stick slides along the normal
        travel = 150.0
        off = (phase - 0.5) * travel
        grip = (contact[0] - nx * (78 + off), contact[1] - ny * (78 + off))
        tip = (contact[0] + nx * (104 - off), contact[1] + ny * (104 - off))
        return {"contact": contact, "grip": grip, "tip": tip}

    # --- arms are consequences --------------------------------------------
    def arms(self, v, b, slide):
        r_sh = (v["chest"][0] + self.shoulder_dx * 0.4, v["chest"][1] - 62)
        l_sh = (v["chest"][0] - self.shoulder_dx * 0.4, v["chest"][1] - 62)
        r_elbow, r_hand, r_cl = two_bone_ik(r_sh, b["grip"], self.upper, self.fore,
                                            bend_sign=+1)
        ux, uy = v["axis"]
        fb = (v["tail"][0] + ux * (150 + 40 * slide),
              v["tail"][1] + uy * (150 + 40 * slide))
        l_elbow, l_hand, l_cl = two_bone_ik(l_sh, fb, self.upper, self.fore,
                                            bend_sign=-1)
        return {"r": (r_sh, r_elbow, r_hand), "l": (l_sh, l_elbow, l_hand),
                "fingerboard": fb, "clamped": r_cl or l_cl}


# ---------------------------------------------------------------------------
# drawing (flat colour on purpose -- this is the G2 gate)
# ---------------------------------------------------------------------------

def limb(d, a, b, c, w):
    d.line([a, b, c], fill=INK, width=w, joint="curve")
    for p, r in ((a, w / 2), (b, w / 2), (c, w / 2)):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=INK)


def draw(rig, v, b, arms, sway):
    img = Image.new("L", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # far arm behind the body, near arm in front: a stable draw order
    limb(d, *arms["l"], 20)

    # torso and head
    hip = (v["chest"][0], v["chest"][1] + 108)
    d.line([hip, (v["chest"][0], v["chest"][1] - 62)], fill=INK, width=54)
    for sx in (-1, 1):
        d.line([hip, (hip[0] + sx * 26, H * 0.94)], fill=INK, width=20)
    head = (v["chin"][0] + 4, v["chin"][1] - 30)
    d.ellipse([head[0] - rig.head_r, head[1] - rig.head_r,
               head[0] + rig.head_r, head[1] + rig.head_r],
              fill=PAPER, outline=INK, width=7)

    # the violin: solid body, neck, scroll -- an unmistakable silhouette
    ux, uy = v["axis"]
    nx, ny = v["normal"]

    def on(dist, off=0.0):
        return (v["tail"][0] + ux * dist + nx * off, v["tail"][1] + uy * dist + ny * off)

    body = [on(0, 0), on(12, 30), on(30, 36), on(46, 17), on(58, 15), on(72, 30),
            on(90, 34), on(104, 15), on(112, 4)]
    body += [on(112, -4), on(104, -15), on(90, -34), on(72, -30), on(58, -15),
             on(46, -17), on(30, -36), on(12, -30)]
    d.polygon(body, fill=INK)
    d.line([on(110, 0), on(206, 0)], fill=INK, width=16)
    d.ellipse([v["scroll"][0] - 15, v["scroll"][1] - 15,
               v["scroll"][0] + 15, v["scroll"][1] + 15], fill=INK)
    for off in (-16, 16):
        d.line([on(44, off), on(64, off)], fill=PAPER, width=5)

    # the bow, then the near arm on top of it
    d.line([b["grip"], b["tip"]], fill=INK, width=7)
    limb(d, *arms["r"], 22)
    for p in (arms["r"][2], arms["l"][2]):
        d.ellipse([p[0] - 13, p[1] - 13, p[0] + 13, p[1] + 13],
                  fill=PAPER, outline=INK, width=5)
    return img


# ---------------------------------------------------------------------------
# acceptance checks from the plan
# ---------------------------------------------------------------------------

def check(frame_states):
    """The four relationships the shot depends on, asserted every frame."""
    report = {"frames": len(frame_states), "fails": []}
    prev_branch = None
    for i, s in enumerate(frame_states):
        gp, hand = s["grip"], s["r_hand"]
        err = math.hypot(gp[0] - hand[0], gp[1] - hand[1])
        if err > 2.0:
            report["fails"].append(f"f{i}: bow hand {err:.1f}px off the grip")
        fb, lh = s["fingerboard"], s["l_hand"]
        ferr = math.hypot(fb[0] - lh[0], fb[1] - lh[1])
        if ferr > 2.0:
            report["fails"].append(f"f{i}: left hand {ferr:.1f}px off the fingerboard")
        if s["clamped"]:
            report["fails"].append(f"f{i}: IK reach clamp -- proportions out of range")
        branch = s["branch"]
        if prev_branch is not None and branch != prev_branch:
            report["fails"].append(f"f{i}: IK bend branch flipped")
        prev_branch = branch
    report["pass"] = not report["fails"]
    return report


# ---------------------------------------------------------------------------

def render(seconds=20, seed=23, workdir="/home/gpaasch/filmforge/runs/meshrig"):
    import ff_toon_music, make_film as MF, ff_progress, ff_puppet_viola as V
    os.makedirs(f"{workdir}/frames", exist_ok=True)

    n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
    midi, meta = ff_toon_music.compose_toon(workdir, seed, n_bars)
    music = ff_toon_music.render_toon_music(workdir, midi, f"{workdir}/music.wav",
                                            MF.FS, MF.SF, MF.SOX, MF.SFLIB)
    notes = V.read_score(midi, meta["bpm"])
    print(f"music {meta}; {len(notes)} onsets", flush=True)

    rig = ViolinRig()
    total = int(seconds * FPS)
    ff_progress.install_page()
    prog = ff_progress.Progress(f"meshrig-{seed}", total, "solving props then arms")

    states = []
    for n in range(total):
        t = n / FPS
        sway = math.sin(t * 0.8)
        phase, _pitch, _atk = V.bow_state(t, notes)   # bow position IS the score
        slide = 0.5 + 0.5 * math.sin(t * 0.35)

        v = rig.violin(t, sway)
        b = rig.bow(v, phase)
        a = rig.arms(v, b, slide)

        states.append({"grip": b["grip"], "r_hand": a["r"][2],
                       "fingerboard": a["fingerboard"], "l_hand": a["l"][2],
                       "clamped": a["clamped"],
                       "branch": (a["r"][1][0] > a["r"][0][0])})
        draw(rig, v, b, a, sway).save(f"{workdir}/frames/f{n:04d}.png")
        prog.step()

    rep = check(states)
    with open(f"{workdir}/acceptance.json", "w") as f:
        json.dump(rep, f, indent=1)
    print(f"acceptance: {'PASS' if rep['pass'] else 'FAIL'}", flush=True)
    for line in rep["fails"][:5]:
        print("  ", line, flush=True)

    prog.finish("encoding")
    silent = f"{workdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{workdir}/frames/f%04d.png",
                    "-vf", "format=gray,noise=alls=5:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = f"/home/gpaasch/filmforge/films/meshrig-{seed}.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 20)
