# filmforge

Short films generated end to end on one RTX 3090. No cloud APIs, no paid services —
picture, score and edit all come out of this repo and that one GPU.

`specs/` is the source of truth. Each spec records what we were trying to make, what
actually came out, and why it failed — including the failures, which are the useful
part.

## What's here

| Genre | What it makes |
|---|---|
| `nature` / `horror` | Ken Burns slideshows — stills with pan/zoom, orchestral or MusicGen score |
| `pastoral` (spec 01) | Real generated motion via Wan 2.2 5B frame-chaining. **Rejected — see below.** |
| `toon` (spec 02) | 1930s black-and-white rubber-hose cartoons, ragtime score, cut to the bar |

    ./forge nature 7            # slideshow film
    python ff_toon.py sheets 1  # character candidates to pick from
    python ff_toon.py film 1    # a cartoon short

## The interesting failure

Spec 01 aimed at a ten-minute photoreal film: water running from a summit snowfield
down to a valley river, one continuous morning. The pipeline generated 64 shots by
chaining Wan 2.2 image-to-video clips, and it ran for **eighteen hours**.

The result was rejected in one sentence: *"it's a slideshow of AI slop."*

Two separate causes, and only one of them was about model quality:

1. **Structural.** Every shot started from a *fresh* text-to-image keyframe, so
   consecutive shots shared no pixels, no light, no place. Chaining only happened
   *inside* a shot. It was a slideshow by construction, and no amount of prompt
   writing could have fixed it.
2. **Capability.** A 5B video model cannot hold photoreal fluid physics. Water poured
   like syrup; a moon crossed the sky and dissolved into a cloud.

Spec 02 responds by changing the genre rather than fighting the hardware — the
governing idea being that **our limitations should become the style**:

| Limitation | In photoreal it reads as | In 1930s rubber-hose it reads as |
|---|---|---|
| unstable, wobbly geometry | broken | rubber-hose animation |
| bad fluid physics | uncanny | squash and stretch |
| colour drift between frames | artifact | *(gone — it's black and white)* |
| low resolution, heavy grain | cheap | authentic film stock |
| low frame rate | stutter | animating "on twos", as they actually did |

Plus the structural fix: one unbroken chain, where every clip starts from the previous
clip's last frame, with a low-denoise repair pass on each handoff so errors stop
compounding down the chain.

And a hard budget — **a whole film must render in under an hour**. Eighteen-hour runs
mean one look at your work per day, which is how you end up with eighteen hours of
something nobody wants to watch.

## Music first

The score is composed *before* any frame is generated, at a fixed tempo, in a whole
number of bars — so every shot is an exact number of bars and every cut lands on a
downbeat. This is not a trick; it is how the Silly Symphonies were made, with bar
sheets marking the beats frame by frame before anything was drawn. Carl Stalling's
premise was that the music shouldn't fit the action, the music *is* the action.

Scores are written from scratch (MIDI → fluidsynth/sfizz → sox). Nothing quotes an
existing work; these get published and Content ID doesn't care about intent.

## Layout

    forge                  launcher
    make_film.py           entry point, slideshow genres, sampler chains
    ff_pools.py            scene pools and the pastoral journey
    ff_compose.py          shared orchestral composition helpers
    ff_pastoral*.py        spec 01: photoreal chaining + its F major score
    ff_toon*.py            spec 02: rubber-hose cartoons + ragtime score
    ff_farm.py             offloads ffmpeg/archiving to other machines on the LAN
    specs/                 source of truth, including the rejections

## Requirements

ComfyUI with Wan 2.2 TI2V-5B and an SDXL checkpoint, ffmpeg, fluidsynth + sox, and a
GPU with enough VRAM to hold the video model. Built and run against a single 3090.
