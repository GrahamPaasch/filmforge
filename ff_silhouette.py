#!/usr/bin/env python3
"""Silhouette gate: reject unreadable geometry before any GPU is spent.

The failure this exists to catch is the viola short of 2026-07-26. The instrument
was drawn as two small circles sitting on top of the character's face, the bow
crossed her head, and the legs merged into the dress as one black mass. Graham's
verdict: "there's no viola in it. There's not even a violin in it." ControlNet did
not lose the instrument — it was never legible in the line art to begin with.

The principle is the oldest one in animation: a pose reads in silhouette or it does
not read at all. So the pipeline now tests the silhouette mechanically, and the
drawn pass is judged before the painted pass is ever queued.

Checks implemented here (thresholds are heuristics, calibrate against approved poses):
  * frame safety     -- nothing touching the border
  * ink coverage     -- not a speck, not a blob
  * connectedness    -- one dominant mass, no detached hands or floating shoes
  * hole survival    -- wheel interiors and frame triangles must stay open
  * thumbnail test   -- survives being reduced to 32x32 and blown back up
  * pose separation  -- key poses must differ from each other
  * temporal check   -- adjacent frames neither frozen nor popping
"""
import json, os

import numpy as np
from PIL import Image


def mask_of(img, size=(96, 96)):
    """Flat black-on-white silhouette at thumbnail size. Everything is judged here,
    not at full resolution -- if it only reads at 640px it does not read."""
    a = np.asarray(img.convert("L").resize(size, Image.LANCZOS), dtype=np.float32)
    return a < 128


def foreground_fraction(m):
    return float(m.mean())


def touches_border(m):
    return bool(m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any())


def _label(m):
    """Tiny 4-connected component labeller; avoids a scipy dependency."""
    lab = np.zeros(m.shape, dtype=np.int32)
    cur = 0
    for y in range(m.shape[0]):
        for x in range(m.shape[1]):
            if m[y, x] and lab[y, x] == 0:
                cur += 1
                stack = [(y, x)]
                lab[y, x] = cur
                while stack:
                    cy, cx = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] \
                                and m[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            stack.append((ny, nx))
    return lab, cur


def dominant_mass(m):
    lab, n = _label(m)
    if n == 0:
        return 0.0, 0
    sizes = [int((lab == i).sum()) for i in range(1, n + 1)]
    return max(sizes) / max(1, m.sum()), n


def holes(m):
    """Count enclosed white regions — wheel interiors, the frame triangle, the gap
    between arm and torso. Negative space IS the readability."""
    bg = ~m
    lab, n = _label(bg)
    border_ids = set(lab[0]) | set(lab[-1]) | set(lab[:, 0]) | set(lab[:, -1])
    return sum(1 for i in range(1, n + 1) if i not in border_ids and (lab == i).sum() >= 4)


def thumbnail_stability(img):
    """Downsample hard, blow back up, compare. Features too thin to survive this are
    features the audience will not see either."""
    small = mask_of(img, (32, 32))
    big = np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((96, 96),
                                                                           Image.NEAREST)) < 128
    ref = mask_of(img, (96, 96))
    inter = (big & ref).sum()
    union = (big | ref).sum()
    return float(inter / union) if union else 0.0


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def check_frame(img, name="frame", min_fg=0.06, max_fg=0.70,
                min_dominant=0.80, min_holes=1, min_thumb=0.55):
    m = mask_of(img)
    dom, ncomp = dominant_mass(m)
    fg = foreground_fraction(m)
    h = holes(m)
    thumb = thumbnail_stability(img)
    fails = []
    if touches_border(m):
        fails.append("touches frame border")
    if not (min_fg < fg < max_fg):
        fails.append(f"ink coverage {fg:.2f} outside {min_fg}-{max_fg}")
    if dom < min_dominant:
        fails.append(f"fragmented: dominant mass {dom:.2f} over {ncomp} pieces")
    if h < min_holes:
        fails.append(f"no surviving negative space (holes={h}) -- forms are merging")
    if thumb < min_thumb:
        fails.append(f"thumbnail stability {thumb:.2f} -- detail too thin to read")
    return {"name": name, "fg": round(fg, 3), "dominant": round(dom, 3),
            "components": ncomp, "holes": h, "thumb": round(thumb, 3),
            "pass": not fails, "fails": fails}


def check_cycle(frames, key_indices=None, max_key_iou=0.93,
                min_change=0.002, max_change=0.35):
    """Whole-cycle checks: do the key poses actually differ, and does motion flow?"""
    report = {"frames": [], "cycle": []}
    for i, im in enumerate(frames):
        report["frames"].append(check_frame(im, f"f{i:04d}"))

    masks = [mask_of(im) for im in frames]
    keys = key_indices or [0, len(frames) // 4, len(frames) // 2, 3 * len(frames) // 4]
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            v = iou(masks[keys[a]], masks[keys[b]])
            if v > max_key_iou:
                report["cycle"].append(
                    f"key poses {keys[a]} and {keys[b]} are {v:.2f} identical -- "
                    "the cycle moves internally but produces no new silhouette")

    for i in range(1, len(masks)):
        change = float((masks[i] ^ masks[i - 1]).sum() / masks[i].size)
        if change < min_change:
            report["cycle"].append(f"frames {i-1}->{i} barely change ({change:.4f}) -- frozen")
        elif change > max_change:
            report["cycle"].append(f"frames {i-1}->{i} jump ({change:.3f}) -- pop or IK flip")

    report["pass"] = all(f["pass"] for f in report["frames"]) and not report["cycle"]
    return report


def contact_sheet(frames, dest, cols=6, cell=96):
    """The human gate: one sheet of small black silhouettes. If the action is not
    obvious here, revise the geometry -- not the prompt."""
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("L", (cols * cell, rows * cell), 255)
    for i, im in enumerate(frames):
        m = mask_of(im, (cell, cell))
        tile = Image.fromarray(((~m) * 255).astype(np.uint8))
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))
    sheet.save(dest)
    return dest


def gate(frames, sheet_path=None, report_path=None, verbose=True):
    rep = check_cycle(frames)
    if sheet_path:
        contact_sheet(frames, sheet_path)
        rep["contact_sheet"] = sheet_path
    if report_path:
        with open(report_path, "w") as f:
            json.dump(rep, f, indent=1)
    if verbose:
        bad = [f for f in rep["frames"] if not f["pass"]]
        print(f"silhouette gate: {'PASS' if rep['pass'] else 'FAIL'} "
              f"({len(bad)}/{len(rep['frames'])} frames failed)")
        for f in bad[:4]:
            print("  ", f["name"], "->", "; ".join(f["fails"]))
        for c in rep["cycle"][:4]:
            print("  cycle:", c)
    return rep
