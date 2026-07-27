# Model inventory — the Swiss Army knife

The rule from spec 02: **state which model makes each artifact and what it was trained on,
before starting a render.** This file is where that gets checked. Keep it current.

Hardware: one RTX 3090, 24 GB VRAM, 265 GB free on the ComfyUI disk (2026-07-26).

## What is actually on this machine

### Video (motion)

| Model | Size | Trained on | Good for | Verdict here |
|---|---|---|---|---|
| Wan 2.2 TI2V-5B | 9.4 GB | **real video** | photoreal motion, image-to-video | **Wrong tool for cartoons.** It drags stylised input back toward photorealism frame by frame — the "melting" and the realistic/cartoon hybrid Graham rejected on 2026-07-26. |

**Installed 2026-07-26 to close that gap** — a toolkit, not one hammer, because a single film may
need different models for different jobs (characters vs. backgrounds vs. motion):

| Model | Size | Trained on | Use it for |
|---|---|---|---|
| **ToonCrafter** (`tooncrafter_512_interp-pruned-fp16`) | 3.2 GB | **cartoons** | generative inbetweening between two cartoon key drawings — 512x320, 16 frames/pass |
| ToonCrafter sketch encoder | 0.7 GB | cartoons/line art | guiding interpolation with sketch input |
| **AnimateDiff SDXL** (`mm_sdxl_v10_beta`) | 0.95 GB | motion only | animating *inside* an SDXL checkpoint's own style |
| **AnimateDiff SD1.5 v3** (`v3_sd15_mm`) | 1.7 GB | motion only | the mature ecosystem: motion LoRAs, camera control |
| **ToonYou beta6** (SD1.5) | 2.3 GB | **cartoon/toon** | the SD1.5 base to pair with AnimateDiff v3 |
| **LTX-Video 2B v0.9.5** | 6.3 GB | real video | fast realistic motion; speed benchmarks |
| **Real-ESRGAN x4** | 0.07 GB | upscaling | mandatory — ToonCrafter outputs 512x320 |

ComfyUI custom nodes installed and verified loading: `ComfyUI-DynamiCrafterWrapper`
(ToonCrafterInterpolation, ToonCrafterDecode, DynamiCrafterI2V, DynamiCrafterBatchInterpolation),
`ComfyUI-AnimateDiff-Evolved`, `ComfyUI-VideoHelperSuite`. LTX nodes ship natively.

**Pick per artifact, not per film.** A cartoon character dancing in a forest may want ToonYou or
Pony for the character, RealVisXL or albedobase for the background plate, ToonCrafter for the
character motion, and Real-ESRGAN to bring it up to delivery resolution.

### Stills (SDXL checkpoints)

| Checkpoint | Leaning | Notes |
|---|---|---|
| RealVisXL V5.0 | photoreal | spec 01's keyframer |
| DreamShaperXL Turbo | general, photoreal-leaning | fast (8 steps); produced the half-realistic Betty figure |
| Juggernaut XL v9 | photoreal | |
| albedobase XL v2.1 | general | most "illustration-friendly" of the general set |
| Illustrious XL v1.0 | **anime/illustration** | true stylised base, modern anime not 1930s |
| Animagine XL 4.0 | **anime** | already used for game art elsewhere |
| Pony Diffusion V6 XL | stylised/cartoon | strong at non-photoreal characters |
| FLUX.1-dev fp8 | general, best prompt adherence | slow; best at following an unusual style brief |
| Ideogram 4 nf4 | general | |

So we *do* have cartoon-capable still models. We used the wrong one. But fixing the still alone
does not fix the film, because the video model is what destroys the style.

## Options to close the gap

Ranked by how likely each is to produce something watchable on this hardware.

### 1. Rig a vector puppet and animate it in code — no diffusion at all
Rubber-hose characters are simple shapes: circles, tapered limbs, a few pivots. Keyframing a
puppet programmatically gives **exact** style fidelity, frame-accurate sync to the bar grid, zero
drift, zero melting, and renders in *seconds* rather than half an hour. It also plays to what this
project is strongest at — deterministic code and hand-written music — and it satisfies the
under-an-hour budget by a factor of hundreds. The 1930s look is achievable because the 1930s look
is *simple by construction*.

Cost: we author motion instead of sampling it. That is real work, but it is work that compounds —
a walk cycle written once is reusable forever, which is exactly how the studios operated.

### 2. AnimateDiff over a cartoon-trained SDXL checkpoint
The motion module animates *inside* the base model's style space, so the style comes from
Illustrious / Animagine / Pony rather than being fought for downstream. Runs on 8 GB, well within
budget, and has a large library of motion LoRAs for art direction. This is the obvious
generative path and the one to try first if we stay with diffusion.
Needs: ComfyUI-AnimateDiff-Evolved custom node (not currently installed — `custom_nodes/` is
empty) plus a motion module.

### 2b. ToonCrafter — the one model actually trained on cartoons
`Doubiiu/ToonCrafter` on Hugging Face (SIGGRAPH Asia 2024), with community ComfyUI nodes
(ComfyUI-ToonCrafter / ComfyUI-DynamiCrafterWrapper) and an fp16 build. ~12 GB VRAM, 16 frames at
512x320 per pass.

It does **generative cartoon interpolation**: give it two cartoon drawings and it in-betweens
them. That is not a workaround, it is exactly the 1930s process — key drawings first, then inbetweens
— and it is the only option here whose training distribution *is* the medium.

Caveats, honestly: 512x320 and 16 frames per pass is small, so a two-minute film needs many passes
and an upscale, and interpolation means we must author the keyframes (in a cartoon SDXL checkpoint
we already have). That authoring requirement is shared with option 1, which is a hint about where
this is really heading.

### 3. LTX-Video (LTX-2.x)
Fast, ComfyUI-native, runs comfortably in 24 GB, and notable for single-pass audio+video. Still a
*realistic* video model, so it likely inherits the same style-collapse problem as Wan. Worth
benchmarking for speed, not for cartoons.

### 4. HunyuanVideo / bigger Wan (14B)
Better quality, materially more VRAM and time. Off the table while the under-an-hour budget
stands.

## Standing rule

Before the next render, write down here:
1. which model makes the still,
2. which makes the motion,
3. what each was trained on,
4. and why that matches the medium.

If step 4 cannot be answered honestly, do not start the render.
