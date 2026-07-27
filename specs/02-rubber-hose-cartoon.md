# Spec 02 — Rubber-hose cartoon shorts (supersedes spec 01)

Status: **active**. Supersedes [spec 01](01-pastoral-film.md), which is parked, not deleted.

## Why spec 01 died

Spec 01 chased a photoreal 10-minute nature film on a single 3090. The 56-second POC was
rejected on 2026-07-26: disconnected vignettes, a moon racing across the sky and dissolving,
water poured like syrup, a waterfall on a snowcap. Two failures, one structural and one
capability:

- **Structural:** every shot began from a fresh text-to-image keyframe, so consecutive shots
  shared nothing. A slideshow by construction.
- **Capability:** Wan 2.2 **5B** cannot hold photoreal fluid physics or plausible celestial
  motion. Photoreal is the one genre where every model error reads as an error.

Graham's verdict on the concept itself: *"Is that really a movie? Water running down a mountain?
It sounds like paint drying."*

## The governing principle

**Turn our disadvantages into advantages.** We have one 3090 with 24 GB of VRAM and a small
video model. Rather than fight that, pick a form where the model's failure modes *are the
aesthetic*:

| Our limitation | In photoreal it reads as | In 1930s rubber-hose it reads as |
|---|---|---|
| wobbly, unstable geometry | broken | rubber-hose animation |
| syrupy, wrong fluid physics | uncanny | squash-and-stretch |
| color drift between frames | artifact | (removed — we shoot black and white) |
| low resolution, heavy grain | cheap | authentic 1930s film stock |
| low effective frame rate | stutter | animating "on twos," exactly as they did |

Everything below follows from that table.

## The film

A **two-to-three-minute** black-and-white rubber-hose cartoon short in the lineage of Fleischer's
Betty Boop, Felix the Cat, Disney's *Silly Symphonies*, and Cuphead. **Five minutes is the hard
ceiling.**

- **Music-first.** The score is composed before a single frame is generated, and the animation is
  cut to it. This is not a workaround — it is literally how *Silly Symphonies* were made. Carl
  Stalling's premise was "animation as choreography"; the goal was never to fit music to action
  but to make *the music be the action*.
- **Protagonist:** a rubber-hose character playing a stringed instrument, with the world bending,
  bouncing, and dancing to what they play. Music-first by construction, and Graham's own world.
- **No human faces, no dialogue, no text on screen, ever.**
- **Arc:** the era's own three-beat shape — the character starts playing; the world wakes up and
  dances along; it runs away from them and collapses on the last chord. Rising action, climax,
  fall. Formula is a feature: develop a winning one, churn out shorts on it, change it only when
  it goes stale.

## The three defects we are fixing

Restated as the acceptance gate. A candidate short must pass **all three**, judged by Graham on
the finished thing:

1. **Not a slideshow** — shots visibly continue from one another; one world, not a reel of
   unrelated cards.
2. **Coherent** — it tells a story, in order, that a viewer can follow.
3. **Not AI slop** — no invented or impossible motion; the character does not morph into
   something else.

## Pipeline

### 1. Continuity: one unbroken chain

The single most important change. **Shot N+1 starts from shot N's last frame.** No mid-film
text-to-image restarts. Cuts still happen — a cut inside a chain is an edit decision, not a
regeneration — but the pixels always descend from the previous shot.

Corollary: **the text prompt does not change every shot.** Swapping prompts mid-chain is what
makes a scene morph and melt. One prompt governs a continuous run; a new prompt only at a
deliberate hard cut.

(Full film grammar — establishing shots, deliberate scene changes, cutaways — is the *later*
goal. v2 proves the chain first. A film made of nothing but continuous chain is not the end
state, it is the thing we have never once achieved.)

### 2. Speed: the whole short renders in under an hour

Non-negotiable, and it drives every technical choice. Graham's reasoning: *"we need very rapid
development cycles"* — a 17-hour render means one look at the result per day, which is how spec
01 burned a night on a rejected film.

Levers, in order of payoff:

- **Animate on twos.** Real 1930s cartoons used ~12 drawings per second. Generate at **12 fps**,
  so one 121-frame generation covers ~10 seconds instead of ~5. That is a free 2× and it is
  *more* period-correct, not less.
- **Shoot 4:3 at low resolution.** Period-correct aspect, far fewer pixels than 1280×704.
  YouTube pillarboxes 4:3 automatically with no crop and no re-encode penalty, so we optimise for
  our hardware and let YouTube handle presentation — never the reverse.
- **Black and white.** Removes the color-drift failure mode entirely and suits the era.
- **Fewer sampler steps**, tuned empirically against the wobble budget.

### 3. Music: hand-composed ragtime, fixed tempo

Composed as MIDI and rendered through the existing sampler chain (fluidsynth + Sonatina + sox) —
**not** MusicGen. Two reasons: ragtime and stride piano are the period idiom, and a deterministic,
known tempo is what makes beat-syncing possible at all. Claude writes the music; this is the part
of the pipeline where our resources are strongest, so it carries more of the load.

### 4. Sync: bar sheets, the 1930s way

The animation and the music must look like a dance. The model cannot hear a beat, so sync is
achieved **editorially**, exactly as the studios did it with bar sheets — beats marked on the
exposure sheet frame by frame, and the animation timed to them:

- Compose first at a fixed tempo (e.g. 120 bpm).
- Make every shot an exact whole number of bars.
- Cut on the downbeat.
- Nudging playback speed to land a hit is *permitted here* — in a cartoon it is Mickey-Mousing,
  not cheating. (This is a deliberate departure from spec 01, where any time-stretching was
  banned; in photoreal it is a lie, in animation it is the craft.)

### 5. Character: a variable until one earns the job

We do not lock a mascot on the first try — Betty Boop and Felix weren't first drafts either.

- Generate a **batch of character design sheets as stills** before any animation. Seconds per
  image instead of an hour, and it front-loads the decision that matters most.
- Graham picks by eye.
- **Identity must not drift** within a film: same silhouette start to finish. A shape-shifting
  lead is precisely what reads as AI slop. A simple rubber-hose design is the easiest thing to
  hold stable — another advantage of the form.
- (Idea parked for later: a story *about* metamorphosis — a moth becoming a butterfly — would turn
  drift into the plot. Deliberately not now: we must first prove we can prevent drift when we
  want to.)

### 6. Evolution: a keepers file

Nothing good gets thrown away. Each round produces **three or four candidate shorts**, not one —
selection needs a population. Graham then locks what he likes at the *component* level: character,
background, musical theme, motion style.

Graham's framing: *"evolution doesn't work where birds grow sharper beaks but lose the ability to
fly. If a feature provides an advantage, that feature stays even as other features change."*

Locking is **pure voice** — he says "keep the character, redo the background" and Cadence records
it in the keepers file. No UI to build; it matches how he actually works.

## Resource rules

- Local only. Claude (a cloud subscription) writes the code and the music; **the finished artifact
  is produced entirely by local resources on this machine.**
- The 3090 is shared with the voice sidecar and vision observer. Under-an-hour renders mean this
  no longer requires going deaf and blind overnight.
- Ops hazard carried over from spec 01, still live: **start ComfyUI standalone before a render.**
  `voice-ui/start.sh` kills a ComfyUI it launched, and POSTs `/free` to one it didn't. Avoid
  voice-ui teardowns mid-render.

## Model selection must match the medium

Added 2026-07-26 after the Betty test, which Graham described as "a hybrid of realistic and
cartoon... characters melting in weird ways... like a literal horror show." His note: *"if we're
generating a cartoon, we need a model trained on and generating cartoons. I kind of thought that
goes without saying, but apparently it doesn't."* It should have been written down. It is now:

**Rule: before any render, state which model produces each artifact and what it was trained on.
If the training distribution doesn't match the target medium, the render will not work and must
not be started.**

What went wrong specifically, at two layers:

1. **The still.** `DreamShaperXL_Turbo` is a general-purpose photoreal-leaning SDXL checkpoint. It
   was chosen for *speed*, and it produced a half-realistic figure rather than a 1930s cel.
2. **The motion — and this is the harder one.** Wan 2.2 TI2V-5B is trained on *real video*. Given
   a stylised input it pulls the picture back toward photorealism frame by frame, which is exactly
   the melting Graham saw. No choice of still model fixes this, because the video model is the one
   destroying the style.

**Therefore the video stage itself is now in question.** Two candidate directions, to be decided
before the next render:

- **A cartoon-native generative path** — animate inside an image model that *is* the cartoon
  (e.g. AnimateDiff over a cartoon-trained SDXL checkpoint), so the style lives in the base model
  rather than being fought for downstream.
- **A rigged vector puppet driven by code** — rubber-hose characters are simple shapes with
  squash-and-stretch. Keyframing a puppet programmatically gives perfect style fidelity, exact
  frame-accurate sync to the bar grid, zero melting, zero drift, and renders in seconds instead of
  half an hour. It is also the option that plays to what we are strongest at: deterministic code
  and hand-written music.

The second is the more radical departure from "generate everything with a diffusion model" — and
on current evidence it is the one most likely to actually produce something watchable.

## RESULT: the approach that worked (2026-07-26)

Four attempts at motion in one evening. Only the last one passed.

| # | Approach | Outcome |
|---|---|---|
| 1 | Wan 2.2 5B, frame-chained, 640x480 @12fps | Rejected. Distorted further with every clip until "the violin stopped looking like a violin and the skeleton stopped looking like a skeleton." |
| 2 | Same, native 1280x704 @24fps, repaired handoffs | Rejected. "A hybrid of realistic and cartoon... like a literal horror show." Wan is trained on real video and drags any style back toward photorealism. |
| 3 | AnimateDiff over ToonYou (cartoon-native base) | Genuinely a cartoon at last — but "very disjointed... melting in and out of itself." AnimateDiff stitches 16-frame windows; the seams are the melting. |
| 4 | **Code-rigged puppet + ControlNet paint** | **Accepted.** "That's actually kind of good, honestly." |

**The winning architecture: the rig owns motion, the model owns art.**

`ff_puppet.py` draws the character as geometry — circles, quadratic-bezier "hoses", a
crank-driven leg cycle. Every frame is a pure function of time, so the character *cannot* morph:
it is the same shapes, moved. Pedal cadence is one revolution per beat, which makes the
Mickey-Mousing a mathematical fact rather than an edit.

`ff_puppet_render.py` then feeds each drawn frame to ToonYou through **ControlNet lineart** at
strength 0.95 with one fixed seed. The model cannot invent geometry — it can only render the pose
it is handed — so it contributes exactly what it is good at (line quality, shading, period
texture) and nothing it is bad at (object permanence).

Costs, measured: drawing 120 frames takes **1.5 seconds**; painting them takes **~6 s/frame**, so
a 10-second short is about 12 minutes end to end — comfortably inside the one-hour budget, and the
drawn pass alone is instant enough to iterate motion in real time before spending any GPU at all.

**Consequence for the spec:** generative video models are demoted to a research track. The default
pipeline is now puppet-plus-ControlNet. New motion is authored as code (a walk cycle, a dance, a
chase) and is reusable forever — which is exactly how the 1930s studios worked, with a library of
cycles.

## What one night actually established (2026-07-26)

Seven approaches, one accepted. Recorded so none of it is re-learned.

| # | Approach | Verdict |
|---|---|---|
| 1 | Wan 2.2, chained, off-native resolution | distorted further every clip |
| 2 | Wan 2.2, native res, repaired handoffs | "a hybrid of realistic and cartoon... a literal horror show" |
| 3 | AnimateDiff over a cartoon checkpoint | finally a cartoon, but "melting in and out of itself" at the window seams |
| 4 | Code puppet + ControlNet paint | good motion, but every frame independently re-imagined |
| 5 | Paint one keyframe, transport by rig | no flicker at all, but the art underneath was crude |
| 6 | Generated pose cards, cut and rigged | beautiful art, but cutouts leave holes and inpainting invents extra limbs |
| 7 | **Abstract visual music, stepped on the beat** | **accepted — "this one's locked"** |

### The two findings that matter

**1. Character performance was the wrong premise.** It is the most labour-intensive
thing in animation; studios hired rooms of people for it. Every failure above traces
back to trying to get it for free. Fischinger and McLaren built respected films from
moving shapes cut to music, and that form is made of exactly what this project is
strongest at: deterministic geometry, fixed tempo, and a score we wrote and can read
note by note.

**2. Perceived sync is discrete change, not motion.** The first visual-music film had
audio and MIDI aligned to **4 ms** and still read as unsynced, because everything on
screen moved continuously and the eye had no event to match against the ear. Making
the picture *hold perfectly still and then snap* at each beat — no interpolation
anywhere — fixed it immediately. This is also why 1930s cartoons pose-hold on the
beat rather than easing through it.

Measure before diagnosing: "it's out of sync" was false, and the real fault was two
layers away from where it appeared.

## Out of scope

- Photoreal anything.
- Human faces or human characters.
- Dialogue, narration, subtitles, title cards, on-screen text of any kind.
- Sound effects (slide whistles, clangs) — music only for now, so we are not debugging audio sync
  and animation quality at the same time.
- Any cloud or API video generation.
- Films longer than five minutes, or any render longer than one hour.
- A separate proof-of-concept step — the short *is* the proof of concept now.
- Changing the existing `nature` / `horror` genres, or building further on spec 01's pastoral
  journey.
