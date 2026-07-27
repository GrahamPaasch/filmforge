#!/usr/bin/env python3
"""Cut one master illustration into rig layers, by hand, with hidden overlap.

This is the manual authoring stage the research says cannot be skipped and cannot
be generated: asking the image model for isolated limbs produced eight complete
characters (and one frog). Part art has to come from a master illustration, cut by
a human eye and extended under every joint.

The polygons below were read off `assets/poses/play.png` against a coordinate grid.
That is the whole job — someone looks at the drawing and says where the forearm ends.

Two products per layer, per the plan:
  * visible  -- exactly the pixels the master shows
  * support  -- the visible pixels PLUS hidden overlap grown under the neighbouring
                part, so that when the joint bends there is drawing underneath
                instead of a hole

The hidden overlap here is grown from the layer's own edge pixels rather than
invented, which is the honest version: it continues the material that is actually
there. Anything that needs genuinely unseen anatomy is a job for a new asset, not
for a fill.
"""
import json, os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MASTER = "/home/gpaasch/filmforge/assets/poses/play.png"
OUT = "/home/gpaasch/filmforge/assets/layers"
SIZE = 768

# Read by eye off the coordinate grid in films/play-grid.png. Z-order back to front.
LAYERS = [
    # Re-read against a 48px grid. Notes on what each boundary follows:
    #   head    -- hair silhouette down to the collar line at y~205
    #   torso   -- bodice only; the skirt flares below y~380 and is its own shape
    #   legs    -- from under the skirt hem to the shoes on the stage ellipse
    #   far_arm -- her left arm, shoulder at (455,225) out to the fingerboard hand
    #   bow_arm -- her right arm, shoulder (300,225) down to the gripping hand
    ("hair_back",  2, [(236, 60), (300, 20), (420, 22), (474, 74), (474, 170),
                       (430, 196), (270, 196), (236, 150)]),
    ("legs",       6, [(322, 430), (436, 430), (452, 700), (416, 736), (330, 736),
                       (308, 700)]),
    ("far_arm",    4, [(444, 210), (474, 214), (530, 236), (566, 250), (566, 292),
                       (516, 288), (462, 268), (440, 246)]),
    ("skirt",      7, [(252, 372), (300, 356), (452, 356), (506, 376), (494, 446),
                       (392, 462), (268, 444)]),
    ("torso",      8, [(300, 196), (452, 196), (462, 300), (452, 380), (300, 380),
                       (290, 300)]),
    ("violin",    10, [(352, 288), (392, 210), (516, 202), (596, 232), (634, 250),
                       (628, 282), (556, 288), (444, 306), (376, 306)]),
    ("bow_arm",   12, [(276, 214), (322, 226), (352, 300), (368, 342), (352, 372),
                       (306, 356), (268, 292), (262, 240)]),
    ("bow_hand",  14, [(318, 326), (382, 326), (382, 386), (318, 386)]),
    ("bow",       16, [(306, 404), (350, 344), (642, 56), (604, 106)]),
    ("head",      18, [(258, 34), (438, 30), (474, 96), (466, 176), (410, 206),
                       (300, 206), (256, 160)]),
]

# How far each layer is grown under its neighbours. A joint that swings 30 degrees
# needs overlap proportional to the limb's width, not a couple of pixels.
OVERLAP = {"bow_arm": 26, "far_arm": 26, "torso": 30, "skirt": 20, "legs": 22,
           "head": 18, "hair_back": 14, "violin": 8, "bow": 6, "bow_hand": 14}


def alpha_of(im, cut=205):
    """Figure-vs-paper for the master, flood-filled from the border so white areas
    INSIDE the character stay opaque."""
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    ink = a.min(axis=2) < cut
    bg = np.zeros(ink.shape, dtype=bool)
    stack = [(0, x) for x in range(ink.shape[1])] + \
            [(ink.shape[0] - 1, x) for x in range(ink.shape[1])] + \
            [(y, 0) for y in range(ink.shape[0])] + \
            [(y, ink.shape[1] - 1) for y in range(ink.shape[0])]
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
    return Image.fromarray(((~bg).astype(np.uint8) * 255), "L")


def grow(mask, px):
    """Dilate a mask to make the support region."""
    m = mask
    for _ in range(max(0, px // 2)):
        m = m.filter(ImageFilter.MaxFilter(3))
    return m


def extend_material(rgb, visible, support):
    """Fill the hidden band by continuing the layer's own edge material outward.

    Not invention: each new pixel takes the nearest existing pixel's value, so a
    sleeve continues as sleeve and skin continues as skin. Anything needinggenuinely new
    anatomy is out of scope and must be a separate approved asset."""
    a = np.asarray(rgb).astype(np.uint8)
    vis = np.asarray(visible) > 127
    sup = np.asarray(support) > 127
    out = a.copy()
    band = sup & ~vis
    if band.any():
        from scipy import ndimage
        idx = ndimage.distance_transform_edt(~vis, return_distances=False,
                                             return_indices=True)
        for c in range(3):
            ch = out[:, :, c]
            ch[band] = a[:, :, c][idx[0][band], idx[1][band]]
            out[:, :, c] = ch
    return Image.fromarray(out, "RGB")


def build():
    os.makedirs(OUT, exist_ok=True)
    master = Image.open(MASTER).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    fig = alpha_of(master)

    manifest = []
    for name, z, poly in sorted(LAYERS, key=lambda L: L[1]):
        sel = Image.new("L", (SIZE, SIZE), 0)
        ImageDraw.Draw(sel).polygon(poly, fill=255)
        visible = Image.fromarray(
            ((np.asarray(sel) > 127) & (np.asarray(fig) > 127)).astype(np.uint8) * 255, "L")
        support = Image.fromarray(
            ((np.asarray(grow(sel, OVERLAP.get(name, 16))) > 127)
             & (np.asarray(grow(fig, OVERLAP.get(name, 16))) > 127)).astype(np.uint8) * 255, "L")
        rgb = extend_material(master, visible, support)
        rgba = rgb.convert("RGBA")
        rgba.putalpha(support)
        path = f"{OUT}/{name}.png"
        rgba.save(path)
        vis_px = int((np.asarray(visible) > 127).sum())
        sup_px = int((np.asarray(support) > 127).sum())
        manifest.append({"name": name, "z": z, "path": path,
                         "visible_px": vis_px, "support_px": sup_px,
                         "overlap_px": OVERLAP.get(name, 16),
                         "hidden_gain": round(sup_px / max(1, vis_px), 3)})
        print(f"{name:10s} z={z:2d}  visible {vis_px:6d}  support {sup_px:6d}  "
              f"(+{100*(sup_px/max(1,vis_px)-1):.0f}% hidden)", flush=True)

    with open(f"{OUT}/manifest.json", "w") as f:
        json.dump({"master": MASTER, "size": SIZE, "layers": manifest}, f, indent=1)
    return manifest


def contact_sheet(dest="/home/gpaasch/filmforge/films/layers-sheet.png", cell=192):
    man = json.load(open(f"{OUT}/manifest.json"))["layers"]
    cols = 5
    rows = (len(man) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (245, 245, 245))
    for i, L in enumerate(man):
        im = Image.open(L["path"]).convert("RGBA").resize((cell, cell), Image.LANCZOS)
        tile = Image.new("RGB", (cell, cell), (255, 255, 255))
        tile.paste(im, mask=im.getchannel("A"))
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))
    sheet.save(dest)
    return dest


if __name__ == "__main__":
    build()
    print(contact_sheet())
