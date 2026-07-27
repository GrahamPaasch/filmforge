# Mesh-rig plan for character performance (researched 2026-07-26)

Recorded verbatim in substance so it survives the session. Graham had this researched after
seven approaches to character animation failed in one evening (see spec 02).

## The verdict

The missing bridge is **not another video model**. It is a conventional 2D animation asset
pipeline — the Spine / Live2D / DragonBones lineage:

> segment one approved illustration into semantic layers → paint finite **hidden overlap**
> beneath every moving part → convert each deformable layer into a textured triangle mesh →
> bind vertices to a sparse skeleton → solve hands from the props by two-bone IK → add
> corrective shapes and a coarse lattice where skinning alone breaks the drawing.

**Production rule: once an image is accepted into the rig, diffusion leaves the frame loop.**
Every animation frame is an evaluation of frozen textures, topology, weights and constraints.

## Why each of our failures happened

| Our failure | Missing structure | The fix |
|---|---|---|
| character melts (Wan) | no persistent vertices, UVs, or identity-bearing asset | immutable RGBA textures on persistent vertices |
| flicker (per-frame paint) | each frame independently synthesised | no synthesis during animation at all |
| violin vanishes | the violin was *prompt content*, not an object | immutable rigid layer with a semantic ID and a visibility assertion |
| cutout holes | parts end exactly at the visible source boundary | **hidden support regions** painted under shoulders, elbows, cuffs, hair |
| stiff joints | rigid transforms, no deformation field | weighted mesh + joint-focused topology + pose correctives |
| **extra limbs** (our inpaint) | frame-time inpainting asked to infer occluded anatomy | approved hidden texture, or a replacement asset, or less motion |
| hand leaves the bow | hand keyframed independently of the prop | **solve prop geometry FIRST**, then IK the hand onto it |

That last row is the one we got backwards all night: the bow should determine the hand, not the
other way round.

## Tooling

Blender + `bpy` headless is the recommended engine — armatures, vertex groups, IK constraints,
shape keys, lattices, and command-line rendering all exist already. **Not currently installed on
this box.** A NumPy/ModernGL runtime is a second-generation optimisation, not the MVP.

Supporting: SAM 2 or `rembg` for mask proposals, PyMatting for alpha, OpenCV for contours,
`triangle` or `mapbox-earcut` for constrained triangulation, Shapely for polygon repair, libigl
for smooth weights if we ever leave Blender.

## The 10-second violin MVP

~10 semantic layers (torso/head, two upper arms, two forearms, two hand assets, violin, bow,
front hair/collar), 8-12 bones, **under 1000 triangles**, one corrective elbow shape per arm, one
coarse torso lattice. Hands are asset swaps, not finger rigs. Excluded: head turns, new camera
angles, cloth, hair physics, lip sync.

Frame order per frame: place the violin from chest/chin anchors → choose bow phase from the
musical timing → place the bow so its hair sits in the string corridor → IK the bowing arm to the
bow's grip landmark → IK the fingering arm to the fingerboard → swap in the approved hand asset.

Gates G0-G6, the important ones being **G1** (move every layer to an extreme and see no holes or
invented anatomy) and **G2** (a two-second flat-colour bow cycle with correct contacts, before any
texture exists).

## The honest cost

The research is explicit: for someone new to mesh rigging, **the first rig is a multi-day
authoring task** — mask cleanup, hidden-region painting, weight correction and correctives all
require human judgement. Rendering is trivial afterwards (240 frames, no diffusion, sub-1000
triangles).

So this is not an evening's work, and pretending otherwise is how tonight went wrong seven times.

## Cheapest next step

**Gate G2 needs no artwork at all.** A flat-colour, untextured, two-second bow cycle proves the
prop-first solve order, the IK branch stability and the contact maintenance — the four
relationships the whole shot depends on. It costs nothing and de-risks everything downstream.
Do that before installing Blender or generating a single asset.
