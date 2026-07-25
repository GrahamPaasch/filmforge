# Spec 01 — Pastoral: a real 24fps film (not a slideshow)

Status: agreed via grill-me on 2026-07-25. Not yet implemented.

## Why

The existing `nature` and `horror` genres are Ken Burns slideshows: one still image per shot,
zoom/pan applied in ffmpeg, cross-faded. Graham wants an **actual film** — real motion, generated
video — with a coherent through-line and a message. "It's not okay to make an orange and say it's
an apple." Nothing in this spec may be satisfied by faking motion on a still.

## The film

- **Length:** ~10 minutes.
- **Frame rate:** 24 fps, real generated motion in every shot.
- **Continuity:** ONE place, ONE morning. The film follows water downhill:
  snowmelt spring at a summit → trickle over rock → forest creek → meadow brook → wide valley
  river. Time of day advances from first light to full morning across the film. Every shot must
  follow from the previous one geographically and temporally. No non-sequiturs; a viewer should
  never wonder where they are.
- **Message (carried visually, never stated):** everything that becomes a river starts as a single
  thawing drop, and it only ever moves one direction — home.
- **No words.** No narration, no title cards, no end cards, no on-screen text. KISS for the first
  few films.

## Music

Original composition. **Must not quote any existing work** — YouTube Content ID risk, and Graham
is publishing these.

- Idiom: Beethoven 6th, first movement, crossed with Grieg's "Morning Mood" from Peer Gynt.
- Concretely: F major, 2/4, small motifs repeated as ostinato over pedal/drone bass, slow harmonic
  rhythm, woodwind-led statements answered by strings.
- Arc: single sunrise bloom — quiet solo woodwind over a drone → instruments enter one at a time →
  one full tutti sunrise climax → settle back to calm. **No storm section** (the existing
  `ff_compose` STORM material is not used here).
- Duration must match the assembled video length; the composer is parameterized by target seconds,
  not a fixed bar count.

## Pipeline

New genre `pastoral` in `ff_pools.GENRES`, alongside `nature`/`horror` — existing genres keep
rendering the old D-major piece and the slideshow path unchanged.

1. **Keyframes.** Reuse the existing ComfyUI RealVisXL still generation for the first frame of each
   shot. This is what keeps the look consistent with the films Graham already likes.
2. **Motion.** Wan 2.2 **TI2V-5B** image-to-video in ComfyUI (native 720p, 24 fps, 121 frames ≈ 5 s
   per generation). 5B, not 14B: the 14B fp8 path is roughly a week of solid GPU on the 3090 and
   this is a proof of concept.
3. **Shot extension by chaining.** Each ~10 s shot = two generations, where the **last frame of
   clip A is the input image for clip B**. This produces genuine continuous motion.
   **Do NOT time-stretch or frame-interpolate a 5 s clip to 10 s** — that is slow motion, which is
   the slideshow problem in disguise, and was explicitly rejected.
4. **Assembly.** ~60 shots ≈ 120 generations. Concatenate with short cross-dissolves, mux the
   music, fade audio in/out, `+faststart` for upload. Output to `films/` and symlink into the
   share dir like the existing genres.

### Prerequisites (nothing is installed yet)

- No video model exists on this box. `~/ComfyUI/models/diffusion_models/` is empty and
  `extra_model_paths.yaml` only points at `forge-neo` SD checkpoints. Wan 2.2 TI2V-5B weights +
  its VAE and text encoder must be downloaded.
- ComfyUI needs Wan 2.2 support (recent native nodes, or `ComfyUI-WanVideoWrapper`).
- **Ops risk:** `nvidia-smi` currently fails with `Driver/library version mismatch` (NVML 580.173).
  ComfyUI still runs, so the loaded kernel module is the older one — a reboot is pending. Resolve
  or at least confirm this before a multi-hour unattended render.

## Resource rules

- Local 3090, so wall-clock is cheap — only electricity. Long overnight runs are fine and there is
  no token budget or content-classifier concern.
- The GPU is shared with the voice sidecar and the vision observer. Cadence being deaf/blind during
  a long render is acceptable **overnight**; avoid hogging it during the day where practical.

## Proof of concept (do this first)

Wire the full pipeline, then render a **60-second slice** — six chained shots from the head of the
water journey — and hand it to Graham to judge **before** committing to the full 10-minute run.
Graham cannot listen to audio at the moment, so the POC is judged on **video only**; music can lag
behind the visual proof.

## Out of scope

- Wan 2.2 14B (revisit only after the 5B POC is approved).
- Any cloud/API video generation — local only.
- Narration, subtitles, title cards, end cards, any text on screen.
- A storm/drama section; this film has one calm sunrise arc.
- Multiple locations or a random shuffle from a scene pool — the shot list is an ordered journey,
  not `random.sample`.
- Changing the existing `nature`/`horror` genres.
- Frame interpolation or slow motion as a way to reach shot length.
