# Pedalling rig: the researched plan (2026-07-26)

Graham had a second AI research this after the first bicycle short read wrong. The plan named
our actual bug, so it is recorded here rather than paraphrased away.

## The correction

Pedalling must be a **closed mechanical system**, solved outward from the crank:

    crank angle -> pedal spindle -> ankle target -> analytical two-bone IK -> knee

Our first rig placed the knee at "the midpoint, plus 26 pixels forward". That is why the legs
did not read as pedalling: the foot followed the crank, but the knee was a fudge factor, so the
limb lengths changed every frame and the eye refused to read it as a leg.

Implemented in `ff_puppet.solve_two_bone()` — circle intersection, both legal branches computed,
the forward branch selected and held so the knee cannot flip inside-out at the top and bottom of
the stroke, and the target clamped into a safe annulus so the leg never locks straight (a fully
extended leg is a kinematic singularity and has no silhouette).

Validated: 720 crank phases, zero reach clamps, both link lengths held to within 0.6 px.

## Proportions (normalised to thigh = 1.00)

| Parameter | Value |
|---|---|
| thigh | 1.00 |
| shin | 0.96 |
| crank radius | 0.35 |
| hip forward of crank | -0.15 |
| hip above crank | -1.40 |
| reach margin | 0.06 |

## Order of operations

Solve the mechanics FIRST, then layer style. Rubber-hose curvature, pelvis bob, torso sway and
head lag are applied to a chain that is already mechanically valid — never as a substitute for
one.

## The caching win

At 96-120 bpm a pedal revolution is a whole number of frames, so the cycle is a **loop**. Painted
frames can be cached by a signature of (line-art hash, prompt, seed, model, sampler settings) and
reused wherever the composition is unchanged. A 60-second film does not need 720 diffusion
images; it needs one loop plus whatever genuinely differs. This is the single biggest lever on
the under-an-hour budget.

## Gate before spending GPU

If the plain black-and-white line art does not already read as cycling, do not run ControlNet.
The drawn pass costs about a second; the painted pass costs ten minutes. Judge the cheap one
first.
