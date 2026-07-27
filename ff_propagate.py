#!/usr/bin/env python3
"""Paint once, transport by the rig's own correspondence.

The research verdict (2026-07-26): for a temporally perfect line-art sequence, paint
ONE keyframe and propagate it — independent per-frame diffusion just renegotiates
the character's identity every frame, which is why the violin kept vanishing.

EbSynth solves propagation by searching for patch correspondences between frames.
We do not need to search. **The rig already knows the answer.** Every part's position
is a closed-form function of time, so the exact transform from keyframe to frame N is
something we can simply write down. That turns propagation from a fragile
post-process into arithmetic.

  1. the rig draws frame 0 as line art, and also a MASK per part
  2. the diffusion model paints frame 0 once, at full quality
  3. for every later frame, each painted part is cut by its keyframe mask and moved
     by that part's rig transform

Consequences: the art cannot flicker (there is only one painting), the violin cannot
vanish (it is the same pixels every frame), and a film costs one diffusion call plus
some compositing — seconds, not half an hour.

Honest limit: rigid transport per part. A limb that bends inside its own mask will
show its keyframe bend, so parts must be small enough to move rigidly, or be split
further. That is a well-understood cutout-animation constraint, not a mystery.
"""
import math, os, subprocess

import numpy as np
from PIL import Image


class Part:
    """One rigidly-moving piece: a mask in keyframe space plus a transform per frame.

    `xform(t)` returns (dx, dy, degrees, pivot) — everything needed to place the
    painted pixels for this part at time t.
    """

    def __init__(self, name, draw, xform, z=0):
        self.name, self.draw, self.xform, self.z = name, draw, xform, z


def part_mask(size, draw_fn, feather=1):
    """Render one part alone, in black on white, and turn it into an alpha mask."""
    im = Image.new("L", size, 255)
    draw_fn(im)
    a = np.asarray(im)
    m = (a < 128).astype(np.uint8) * 255
    mask = Image.fromarray(m, "L")
    if feather:
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(feather))
    return mask


def cut_painted(painted, mask):
    """Take the painted keyframe's pixels wherever this part covered them."""
    out = painted.convert("RGBA")
    out.putalpha(mask)
    return out


def place(canvas, layer, dx, dy, deg, pivot):
    """Rotate a painted part about its own pivot, then translate it."""
    if abs(deg) > 1e-6:
        layer = layer.rotate(deg, resample=Image.BICUBIC, center=pivot)
    canvas.alpha_composite(layer, (int(round(dx)), int(round(dy))))
    return canvas


def propagate(painted_keyframe, parts, total_frames, fps, size, out_dir,
              background=(255, 255, 255, 255)):
    """Build every frame by moving the ONE painted keyframe's parts."""
    os.makedirs(out_dir, exist_ok=True)
    layers = [(p, cut_painted(painted_keyframe, part_mask(size, p.draw)))
              for p in sorted(parts, key=lambda q: q.z)]
    for n in range(total_frames):
        t = n / fps
        canvas = Image.new("RGBA", size, background)
        for p, layer in layers:
            dx, dy, deg, pivot = p.xform(t)
            place(canvas, layer, dx, dy, deg, pivot)
        canvas.convert("RGB").save(f"{out_dir}/f{n:04d}.png")
    return out_dir


def encode(frame_dir, music_wav, dest, fps, period_look=True):
    vf = ("format=gray,noise=alls=5:allf=t+u,vignette=PI/5" if period_look
          else "format=yuv420p")
    silent = os.path.join(os.path.dirname(dest), "_silent.mp4")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(fps), "-i", f"{frame_dir}/f%04d.png",
                    "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-r", str(fps), silent],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", music_wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                    "-movflags", "+faststart", dest], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def flicker_score(frame_dir, n=None):
    """Objective check the research asked for. With rigid transport this should be
    driven purely by motion, so we report it as a baseline rather than a pass/fail:
    if it ever spikes, a part is being torn."""
    files = sorted(f for f in os.listdir(frame_dir) if f.endswith(".png"))
    if n:
        files = files[:n]
    prev, diffs = None, []
    for f in files:
        a = np.asarray(Image.open(os.path.join(frame_dir, f)).convert("L"), dtype=np.float32)
        if prev is not None:
            diffs.append(float(np.abs(a - prev).mean()))
        prev = a
    if not diffs:
        return {}
    return {"mean": round(float(np.mean(diffs)), 3),
            "p95": round(float(np.percentile(diffs, 95)), 3),
            "max": round(float(np.max(diffs)), 3)}
