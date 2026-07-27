#!/usr/bin/env python3
"""Spec 02, third attempt at motion: no diffusion at all — a rigged puppet in code.

Two generative video paths failed the same way. Wan 2.2 is trained on real footage
and pulled every cartoon back toward photorealism; AnimateDiff stitches 16-frame
windows and the seams read as melting. Neither can hold an object's identity through
an action, and "Betty rides a bicycle" is exactly an action.

So: draw it. Rubber-hose characters are circles, tapered hoses and a few pivots —
the style is simple *by construction*, which is precisely why it suits a program.
What we get in exchange for authoring the motion ourselves:

  * the character cannot morph, because it is the same geometry every frame
  * pedal cadence locks to the beat exactly (Mickey-Mousing, done properly)
  * 10 seconds renders in a couple of seconds instead of half an hour
  * every parameter is a number we can tune, not a prompt we can only beg with

The tradeoff is honest: we author motion instead of sampling it. But a pedal cycle
written once is reusable forever, which is how the studios actually worked.
"""
import math, os, subprocess

from PIL import Image, ImageDraw

W, H = 640, 480
FPS = 12
BPM = 96
BEAT = 60.0 / BPM                 # 0.625 s
INK = 0
PAPER = 255
# Which way she rides. Everything that implies travel -- wheel spin, scrolling
# scenery, road dashes -- reads off this ONE sign, so the direction can never get
# half-flipped again. (It was: the road and the wheels both ran backwards.)
DIR = -1


# ---------------------------------------------------------------------------
# drawing helpers — the whole rubber-hose vocabulary is here
# ---------------------------------------------------------------------------

def bez(p0, p1, p2, steps=18):
    """Quadratic bezier. A rubber-hose limb is just a curve with a bend point, so
    this single helper draws every arm and leg in the film."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def hose(d, p0, p1, p2, width=9):
    """A limb: thick curve with rounded ends so it reads as a hose, not a stick."""
    pts = bez(p0, p1, p2)
    d.line(pts, fill=INK, width=width, joint="curve")
    r = width / 2
    for p in (p0, p2):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=INK)


def circle(d, c, r, fill=None, outline=INK, width=5):
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=fill,
              outline=outline, width=width)


# ---------------------------------------------------------------------------
# the world
# ---------------------------------------------------------------------------

def draw_background(d, scroll):
    """A scrolling road with fence posts and hills. Everything moves right-to-left
    at the same rate the wheels turn, which is what sells the bicycle as moving."""
    horizon = H * 0.62
    # rolling hills, drawn as arcs so they read as 1930s background art
    for i in range(-1, 6):
        x = (i * 260 - (scroll * 0.25) % 260)
        d.arc([x, horizon - 90, x + 300, horizon + 90], start=180, end=360,
              fill=INK, width=4)
    d.line([(0, horizon), (W, horizon)], fill=INK, width=5)
    # fence posts: the periodic element that makes speed legible
    for i in range(-1, 10):
        x = i * 110 - (scroll % 110)
        d.line([(x, horizon), (x, horizon - 46)], fill=INK, width=5)
        d.line([(x - 55, horizon - 30), (x + 55, horizon - 30)], fill=INK, width=3)
    # road texture dashes
    for i in range(-1, 14):
        x = i * 90 - (scroll * 1.6) % 90
        d.line([(x, horizon + 52), (x + 40, horizon + 52)], fill=INK, width=4)


def draw_bicycle(d, cx, cy, wheel_angle):
    """Two wheels, a frame, handlebars. The spokes are what make rotation readable —
    a plain circle spinning looks like a circle standing still."""
    r = 52
    back = (cx - 62, cy)
    front = (cx + 62, cy)
    for hub in (back, front):
        circle(d, hub, r, outline=INK, width=6)
        for k in range(6):
            a = wheel_angle + k * math.pi / 3
            d.line([hub, (hub[0] + r * 0.86 * math.cos(a),
                          hub[1] + r * 0.86 * math.sin(a))], fill=INK, width=3)
        circle(d, hub, 6, fill=INK, outline=INK, width=1)
    crank = (cx, cy)
    seat = (cx - 26, cy - 74)
    bars = (cx + 54, cy - 76)
    for a, b in ((back, crank), (crank, seat), (seat, back), (crank, bars),
                 (seat, bars), (bars, front)):
        d.line([a, b], fill=INK, width=7)
    d.line([(bars[0] - 22, bars[1] - 6), (bars[0] + 20, bars[1] - 12)], fill=INK, width=8)
    d.ellipse([seat[0] - 20, seat[1] - 9, seat[0] + 16, seat[1] + 5], fill=INK)
    return crank, bars


def draw_rider(d, crank, bars, phase, bob):
    """The rubber-hose rider. Legs are driven straight off the crank angle, so the
    pedalling is correct by construction rather than by keyframing."""
    hip = (crank[0] - 20, crank[1] - 96 + bob)
    shoulder = (hip[0] + 6, hip[1] - 46)
    head_c = (shoulder[0] + 4, shoulder[1] - 40)

    # dress: a simple bell, the era's shape
    d.polygon([(shoulder[0] - 20, shoulder[1] + 6), (shoulder[0] + 20, shoulder[1] + 6),
               (hip[0] + 34, hip[1] + 16), (hip[0] - 34, hip[1] + 16)], fill=INK)

    # legs: pedals are 180 degrees apart on the same crank
    pedal_r = 22
    for k, side in enumerate((0, math.pi)):
        a = phase + side
        pedal = (crank[0] + pedal_r * math.cos(a), crank[1] + pedal_r * math.sin(a))
        knee = ((hip[0] + pedal[0]) / 2 + 26, (hip[1] + pedal[1]) / 2 - 6)
        hose(d, hip, knee, pedal, width=11 if k == 0 else 9)
        # shoe
        d.ellipse([pedal[0] - 12, pedal[1] - 6, pedal[0] + 12, pedal[1] + 8], fill=INK)

    # arms reach to the handlebars, with a little counter-bob
    elbow = ((shoulder[0] + bars[0]) / 2 - 4, (shoulder[1] + bars[1]) / 2 + 20 - bob)
    hose(d, shoulder, elbow, bars, width=9)
    circle(d, bars, 9, fill=PAPER, outline=INK, width=4)      # white glove

    # head: big circle, spit curls, pie-cut eyes
    circle(d, head_c, 34, fill=PAPER, outline=INK, width=6)
    for sx in (-1, 1):
        circle(d, (head_c[0] + sx * 26, head_c[1] - 18), 13, fill=INK, outline=INK, width=1)
    circle(d, (head_c[0] + 30, head_c[1] - 4), 11, fill=INK, outline=INK, width=1)
    for sx in (-1, 1):
        eye = (head_c[0] + sx * 12 + 4, head_c[1] - 4)
        circle(d, eye, 10, fill=PAPER, outline=INK, width=3)
        circle(d, (eye[0] + 2, eye[1] + 2), 5, fill=INK, outline=INK, width=1)
    d.arc([head_c[0] - 4, head_c[1] + 10, head_c[0] + 20, head_c[1] + 26],
          start=0, end=180, fill=INK, width=4)
    circle(d, (head_c[0] - 22, head_c[1] + 12), 5, fill=INK, outline=INK, width=1)


def frame(n, total):
    """One frame. Time is the only input; everything else is derived from it, which
    is why nothing can drift."""
    t = n / FPS
    img = Image.new("L", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # ONE pedal revolution per beat. This is the sync -- not an edit, a fact.
    phase = 2 * math.pi * (t / BEAT)
    scroll = DIR * t * 210
    bob = 4 * math.sin(phase * 2)          # body bobs twice per revolution

    draw_background(d, scroll)
    # the whole bike rides a gentle bounce so it never sits dead-centre
    cy = H * 0.62 - 4 + 5 * math.sin(phase)
    crank, bars = draw_bicycle(d, W * 0.42, cy, DIR * phase)
    draw_rider(d, crank, bars, phase, bob)
    return img


def render(seconds=10, outdir="/home/gpaasch/filmforge/runs/puppet", seed=1,
           want_music=True):
    import ff_toon_music, make_film as MF
    os.makedirs(f"{outdir}/frames", exist_ok=True)
    total = int(seconds * FPS)
    for n in range(total):
        frame(n, total).save(f"{outdir}/frames/f{n:04d}.png")
    print(f"drew {total} frames", flush=True)

    silent = f"{outdir}/silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{outdir}/frames/f%04d.png",
                    # the period look: grain and a vignette over clean line art
                    "-vf", "format=gray,noise=alls=7:allf=t+u,vignette=PI/5",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    out = f"/home/gpaasch/filmforge/films/puppet-bike-{seed}.mp4"
    if want_music:
        n_bars = max(1, round(seconds / ff_toon_music.BAR_SECONDS))
        midi, meta = ff_toon_music.compose_toon(outdir, seed, n_bars)
        music = ff_toon_music.render_toon_music(outdir, midi, f"{outdir}/music.wav",
                                                MF.FS, MF.SF, MF.SOX, MF.SFLIB)
        print(f"music {meta}", flush=True)
        subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                        "-movflags", "+faststart", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", silent, "-c", "copy", out], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"DONE {out}", flush=True)
    return out


if __name__ == "__main__":
    import sys
    render(seconds=float(sys.argv[1]) if len(sys.argv) > 1 else 10)
