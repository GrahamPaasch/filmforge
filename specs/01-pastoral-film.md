# Spec 01 — Pastoral: a real 24fps film (not a slideshow)

Status: agreed via grill-me on 2026-07-25. Pipeline implemented 2026-07-25; blocked on
prerequisites before it can render (see "Prerequisites" below — disk space and the driver
mismatch are both still outstanding).

Implementation: `ff_pastoral.py` (keyframes + Wan chaining + assembly), `ff_pastoral_music.py`
(the F major score), the `pastoral` entry in `ff_pools.GENRES`, and `bin/fetch_wan.sh`.
Run the POC with `./forge pastoral 1 --poc`.

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
4. **Assembly.** 64 shots = 128 generations (60 gave 9.30 min; 64 gives 9.92 min). Concatenate
   with short cross-dissolves, mux the music, fade audio in/out, `+faststart` for upload. Output
   to `films/` and symlink into the share dir like the existing genres.

### Measured cost (one real generation, 2026-07-25)

**533 s per 121-frame clip** on the 3090 at 1280x704 / 30 steps. Steps have since been cut to
20 to match the reference workflow, so expect roughly **~355 s/clip**:
- POC (6 shots, 12 generations): **~1.2 h**
- Full film (64 shots, 128 generations): **~13 h** — still an overnight run.

### The first generated clip was frozen (2026-07-25)

The one clip rendered before the GPU went down had **no motion at all**. Graham caught it; the
earlier claim in this file that the GPU path was "verified" was about the plumbing (right
resolution, frame count, fps, no duplicate frames), **not** about the picture actually moving,
and it should not have been written as reassuringly as it was.

Measured: best-fitting translation is dy=0 dx=0, no zoom fits better than none, and divergence
from frame 0 saturates at 3.3/255 by frame 15 then stays flat for the remaining 4.4 s. That is a
still image with per-frame denoiser jitter.

Diffed against ComfyUI's own `video_wan2_2_5B_ti2v` template. Model, VAE, CLIP, 1280x704, 121
frames, 24 fps, shift 8, cfg 5 and uni_pc/simple all already matched. Three did not:

1. **The positive prompt was only the motion fragment** and never described the scene. The
   reference feeds a whole descriptive sentence with the camera move inside it. Fixed.
2. **The negative prompt was an English paraphrase.** Wan's stock negative is Chinese and
   explicitly rejects 静态 / 静止 / 静止不动的画面. Now used verbatim. Fixed.
3. **Steps 30 vs the reference 20.** Aligned.

Caveat on the evidence: shot 0 was, by bad luck, the only prompt in the journey that contained
the word "still", on the most static subject in the film. So this is one bad sample, not proof
the pipeline can never move. **None of the three fixes is verified** — the next test must be a
water shot, not shot 0.

### Prerequisites (resolved 2026-07-25)

- **Weights: installed.** `bin/fetch_wan.sh` downloaded Wan 2.2 TI2V-5B (10.0 GB), its VAE
  (1.4 GB) and the umt5-xxl fp8 text encoder (6.7 GB) into `~/ComfyUI/models/`.
- **ComfyUI Wan support: native, no custom nodes needed.** ComfyUI 0.24.0 already ships
  `Wan22ImageToVideoLatent`, `CreateVideo`/`SaveVideo` and the `wan` CLIP type.
- **No restart was needed** to pick up the new weights: `folder_paths.cached_filename_list_`
  invalidates on directory mtime, so the running server saw them immediately.
- **Reboot: DEFERRED, not resolved.** One real Wan generation ran end to end on the GPU, so the
  POC does not need a reboot. But the mismatch is worse than "nvidia-smi is cosmetic":

  > A **newly spawned** process cannot use CUDA at all — `torch.cuda.is_available()` is `False`
  > and allocation dies with `Error 804: forward compatibility was attempted on non supported HW`.
  > Only the ComfyUI process started on 2026-07-24 (**before** the driver files changed) still
  > holds a working CUDA context.

  Consequences until Graham reboots:
  - **Do not restart or kill ComfyUI.** It will not get the GPU back. It is the only working
    CUDA path on the box, and the whole pastoral pipeline talks to it over HTTP.
  - The `horror` genre is currently broken here, unrelated to this spec: `render_horror` loads
    MusicGen with `.to("cuda")` inside the *filmforge* process, which is a new process.
  - Reboot before the full ~19-hour render; a crash or OOM restart mid-run would otherwise
    leave ComfyUI alive but GPU-less and the run would fail with no way to resume.

### Ops hazard: voice-ui owns ComfyUI's lifecycle

**This is what killed the first POC render**, ~1 shot in. Not a crash and not an OOM — a
teardown working exactly as designed.

ComfyUI on this box is not started by anything in `~/ComfyUI`. It is started by
`~/claude/voice-ui/start.sh` (its specs/12 image service), which is where the observed command
line `./venv/bin/python main.py --listen 127.0.0.1 --port 8188 --reserve-vram 4` comes from:

```bash
# voice-ui/start.sh
406: elif port_up "$COMFY_PORT"; then echo "  ✓ ComfyUI already running — reusing it"
410:   ( cd "$COMFY_DIR" && exec ./venv/bin/python main.py ... --reserve-vram 4 ) &
412:   COMFY_PID=$!
192: [ -n "${COMFY_PID:-}" ] && { echo "  • stopping ComfyUI (we started it)"; kill_tree "$COMFY_PID" TERM; }
```

Running `voice-ui/start.sh` again cleans up the previous instance, and that teardown kills the
ComfyUI it started. A long render dies with it.

**Mitigation — start ComfyUI standalone before a long render.** Both kill paths (192 and 205)
are guarded on `COMFY_PID`, which is only set when voice-ui launched the daemon itself. If the
port is already up, voice-ui takes the line 406 branch, reuses it, and never claims ownership,
so its teardowns leave the render alone:

```bash
cd ~/ComfyUI && ./venv/bin/python main.py --listen 127.0.0.1 --port 8188 --reserve-vram 4
```

**Residual hazard that the mitigation does NOT cover.** voice-ui's teardown POSTs
`/free {"unload_models":true,"free_memory":true}` to ComfyUI whenever the port is reachable —
including a daemon it does not own (lines 188-191). That is deliberate, so SDXL cannot squat the
card, but it would unload Wan mid-render: at best a costly model reload, at worst it lands
inside a sampling step. **Avoid voice-ui teardowns entirely while a render is running.**

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

### POC VERDICT: REJECTED — still a slideshow (2026-07-26)

Graham watched `films/pastoral-river-poc-1.mp4` (56s, six shots). His words: "it's still a
slideshow. It's just a series of disconnected vignettes... it's AI slop." Specific defects he
named:

- the moon races across the sky and then disintegrates into a cloud (invented, physically absurd
  motion the prompt never asked for);
- one shot is unidentifiable — "kind of looks like the desert or cloud cover," nothing in the
  journey;
- a waterfall appears on a snow-capped mountain face where no waterfall belongs;
- water is *poured like syrup* rather than falling or dripping — the fluid physics read as wrong;
- overall: "it's not a movie, it's a slideshow of moving graphics. It doesn't tell a story."

**Root cause of the slideshow — structural, not a prompt problem.** `render_shot()` in
`ff_pastoral.py` begins **every** shot with a fresh RealVisXL text-to-image keyframe on its own
seed. Chaining exists only *within* a shot (clip a's last frame starts clip b). So consecutive
shots share no pixels, no lighting, no continuity of place — the film is 64 unrelated ten-second
vignettes cross-dissolved together. It is a slideshow **by construction**, and no amount of
prompt-writing fixes it. The journey prose itself is good; the assembly is what fails.

The second defect (slop / broken physics) is separate: Wan 2.2 **5B** at 20 steps generating 121
frames from a still invents large motion and cannot hold fluid dynamics. The stock negative
prompt pushes *against* stillness, which makes over-motion more likely, not less.

**Direction for v2 (not yet designed — grill Graham first):**

1. **Chain across shots, not just within them.** Shot N+1 starts from shot N's last frame.
   Generate a new keyframe only at deliberate section breaks (a handful, not 64), so the film
   becomes one continuous descent through one place.
2. **Trade length for coherence.** 64 shots is 64 chances to look wrong. A coherent 2-3 minutes
   beats an incoherent 10.
3. **Fix the motion quality** — fewer frames per generation, more steps, motion prompts that ask
   for *small* motion, and revisit the 14B model now that the 5B ceiling is measured.
4. Physically-impossible keyframes (waterfall on a snowcap) need grounding in the still prompts.

Do NOT start another long render until v2 is specified and a fresh short POC is approved.

## Out of scope

- Wan 2.2 14B (revisit only after the 5B POC is approved).
- Any cloud/API video generation — local only.
- Narration, subtitles, title cards, end cards, any text on screen.
- A storm/drama section; this film has one calm sunrise arc.
- Multiple locations or a random shuffle from a scene pool — the shot list is an ordered journey,
  not `random.sample`.
- Changing the existing `nature`/`horror` genres.
- Frame interpolation or slow motion as a way to reach shot length.
