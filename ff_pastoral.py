#!/usr/bin/env python3
"""Spec 01 pastoral pipeline: RealVisXL keyframes -> Wan 2.2 TI2V-5B image-to-video
-> chained shot extension -> cross-dissolved assembly.

Real generated motion only. Two rules from the spec this module must never break:
  * a shot reaches its ~10s length by CHAINING (last frame of clip A is the input
    image of clip B), never by time-stretching or interpolating a 5s clip;
  * the shot list is an ordered journey, never a random sample.
"""
import os, io, json, time, uuid, subprocess, urllib.request, urllib.parse

COMFY = "http://127.0.0.1:8188"
CKPT = "RealVisXL_V5.0_fp16.safetensors"

# Wan 2.2 TI2V-5B, native 720p / 24fps. 5B not 14B: the 14B fp8 path is ~a week of
# solid 3090 time at this length, and this is a proof of concept.
WAN_UNET = "wan2.2_ti2v_5B_fp16.safetensors"
WAN_VAE = "wan2.2_vae.safetensors"
WAN_CLIP = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"

W, H = 1280, 704          # Wan 2.2 5B native resolution; keyframes are made to match
FPS = 24
CLIP_FRAMES = 121         # 121 frames @ 24fps = 5.04s, the model's native generation length
CLIPS_PER_SHOT = 2        # -> ~10.0s per shot once the duplicated seam frame is dropped
WAN_STEPS = 20            # matches ComfyUI's video_wan2_2_5B_ti2v reference (was 30)
WAN_CFG = 5.0
WAN_SHIFT = 8.0           # ModelSamplingSD3 shift, per the Wan 2.2 5B reference workflow
XFADE = 0.75              # cross-dissolve between shots

SHOT_FRAMES = CLIPS_PER_SHOT * CLIP_FRAMES - (CLIPS_PER_SHOT - 1)
SHOT_DUR = SHOT_FRAMES / FPS


# ---------------------------------------------------------------------------
# ComfyUI plumbing
# ---------------------------------------------------------------------------

def _post(path, data):
    r = urllib.request.Request(COMFY + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def _get(path, timeout=60):
    return json.loads(urllib.request.urlopen(COMFY + path, timeout=timeout).read())


def _fetch(ref, dest):
    """Download one output file (image or video) named by a ComfyUI history entry."""
    q = (f"/view?filename={urllib.parse.quote(ref['filename'])}"
         f"&subfolder={urllib.parse.quote(ref.get('subfolder', ''))}"
         f"&type={ref.get('type', 'output')}")
    with open(dest, "wb") as f:
        f.write(urllib.request.urlopen(COMFY + q, timeout=900).read())
    return dest


def upload_image(path):
    """POST an image into ComfyUI's input dir so LoadImage can pick it up."""
    name = f"ff_{uuid.uuid4().hex}{os.path.splitext(path)[1] or '.png'}"
    boundary = "----ff" + uuid.uuid4().hex
    with open(path, "rb") as f:
        blob = f.read()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'.encode(),
        b"Content-Type: image/png\r\n\r\n", blob, b"\r\n",
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(COMFY + "/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return r["name"] if not r.get("subfolder") else f"{r['subfolder']}/{r['name']}"


def run_workflow(wf, timeout_s=3600):
    """Queue a prompt and block until it finishes. Returns the history outputs dict."""
    pid = _post("/prompt", {"prompt": wf})["prompt_id"]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(2.0)
        try:
            h = _get(f"/history/{pid}")
        except Exception:
            continue
        if pid in h:
            entry = h[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI job {pid} failed: {json.dumps(status)[:800]}")
            return entry["outputs"]
    raise TimeoutError(f"ComfyUI job {pid} exceeded {timeout_s}s")


def preflight():
    """Fail loudly and usefully if the Wan weights or ComfyUI aren't there yet."""
    try:
        info = _get("/object_info/UNETLoader", timeout=30)
    except Exception as e:
        raise SystemExit(f"ComfyUI is not reachable at {COMFY}: {e}")
    unets = info["UNETLoader"]["input"]["required"]["unet_name"][0]
    vaes = _get("/object_info/VAELoader")["VAELoader"]["input"]["required"]["vae_name"][0]
    clips = _get("/object_info/CLIPLoader")["CLIPLoader"]["input"]["required"]["clip_name"][0]
    ckpts = _get("/object_info/CheckpointLoaderSimple")["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    missing = []
    if WAN_UNET not in unets:
        missing.append(f"models/diffusion_models/{WAN_UNET}")
    if WAN_VAE not in vaes:
        missing.append(f"models/vae/{WAN_VAE}")
    if WAN_CLIP not in clips:
        missing.append(f"models/text_encoders/{WAN_CLIP}")
    if CKPT not in ckpts:
        missing.append(f"(checkpoint) {CKPT}")
    if missing:
        raise SystemExit(
            "Missing models for the pastoral pipeline:\n  " + "\n  ".join(missing) +
            "\n\nRun  bin/fetch_wan.sh  to download the Wan 2.2 TI2V-5B weights, then\n"
            "restart ComfyUI so it rescans the model directories.")


# ---------------------------------------------------------------------------
# stage 1: keyframes (RealVisXL — the look Graham already likes)
# ---------------------------------------------------------------------------

def gen_keyframe(cfg, prompt, seed, dest):
    if os.path.exists(dest):
        return dest
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt + cfg['style'], "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": cfg['neg'], "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": 28, "cfg": cfg['cfg'], "sampler_name": "dpmpp_2m",
            "scheduler": "karras", "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ffkey", "images": ["8", 0]}},
    }
    outs = run_workflow(wf, timeout_s=900)
    refs = (outs.get("9") or {}).get("images") or []
    if not refs:
        raise RuntimeError(f"keyframe generation produced no image (outputs: {list(outs)})")
    return _fetch(refs[0], dest)


# ---------------------------------------------------------------------------
# stage 2: motion (Wan 2.2 TI2V-5B image-to-video)
# ---------------------------------------------------------------------------

def gen_clip(cfg, start_png, motion_prompt, seed, mp4_dest, lastframe_dest):
    """One 121-frame generation from a start image. Also saves the clip's final
    frame, which is what the next clip in the chain starts from."""
    if os.path.exists(mp4_dest) and os.path.exists(lastframe_dest):
        return mp4_dest, lastframe_dest
    handle = upload_image(start_png)
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": WAN_UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": WAN_CLIP, "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": WAN_VAE}},
        "4": {"class_type": "LoadImage", "inputs": {"image": handle}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": motion_prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": cfg['motion_neg'], "clip": ["2", 0]}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
            "vae": ["3", 0], "width": W, "height": H, "length": CLIP_FRAMES,
            "batch_size": 1, "start_image": ["4", 0]}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": WAN_SHIFT}},
        "9": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": WAN_STEPS, "cfg": WAN_CFG, "sampler_name": "uni_pc",
            "scheduler": "simple", "denoise": 1.0,
            "model": ["8", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "CreateVideo", "inputs": {"images": ["10", 0], "fps": float(FPS)}},
        "12": {"class_type": "SaveVideo", "inputs": {
            "video": ["11", 0], "filename_prefix": "ffclip", "format": "mp4", "codec": "h264"}},
        # The chain link: pull the last decoded frame out losslessly as a PNG.
        "13": {"class_type": "ImageFromBatch", "inputs": {
            "image": ["10", 0], "batch_index": CLIP_FRAMES - 1, "length": 1}},
        "14": {"class_type": "SaveImage", "inputs": {"filename_prefix": "fflast", "images": ["13", 0]}},
    }
    outs = run_workflow(wf, timeout_s=5400)
    # SaveVideo reports its mp4 under the "images" key too (PreviewVideo.as_dict),
    # so pick the outputs apart by node id, not by key name.
    def one(node_id, what):
        refs = (outs.get(node_id) or {}).get("images") or []
        if not refs:
            raise RuntimeError(f"Wan generation produced no {what} "
                               f"(node {node_id}; outputs: {list(outs)})")
        return refs[0]
    _fetch(one("12", "video"), mp4_dest)
    _fetch(one("14", "chain frame"), lastframe_dest)
    return mp4_dest, lastframe_dest


def render_shot(cfg, i, total, d, seed):
    """One ~10s shot: a RealVisXL keyframe, then CLIPS_PER_SHOT chained generations."""
    shot_mp4 = f"{d}/shots/shot{i:03d}.mp4"
    if os.path.exists(shot_mp4):
        print(f"shot {i:03d} cached", flush=True)
        return shot_mp4
    still, motion = cfg['shot'](i, total)
    key = f"{d}/keys/key{i:03d}.png"
    gen_keyframe(cfg, still, seed * 1000 + i, key)
    print(f"shot {i:03d} keyframe", flush=True)

    parts, start = [], key
    for c in range(CLIPS_PER_SHOT):
        mp4 = f"{d}/clips/shot{i:03d}{chr(97 + c)}.mp4"
        last = f"{d}/clips/shot{i:03d}{chr(97 + c)}_last.png"
        gen_clip(cfg, start, motion, seed * 1000 + i * 10 + c, mp4, last)
        print(f"shot {i:03d} clip {chr(97 + c)}", flush=True)
        parts.append(mp4)
        start = last          # <- the chain: next clip continues from this frame

    # Join the chain. Clip N's first frame IS clip N-1's last frame, so drop it,
    # otherwise every seam holds one frame for 2/24s and reads as a stutter.
    ins, fc, labels = [], [], []
    for n, p in enumerate(parts):
        ins += ["-i", p]
        fc.append(f"[{n}:v]trim=start_frame={1 if n else 0},setpts=PTS-STARTPTS[p{n}]")
        labels.append(f"[p{n}]")
    fc.append("".join(labels) + f"concat=n={len(parts)}:v=1:a=0[o]")
    sh(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[o]",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", shot_mp4])
    return shot_mp4


# ---------------------------------------------------------------------------
# stage 3: assembly
# ---------------------------------------------------------------------------

def sh(cmd, env=None):
    e = dict(os.environ, **(env or {}))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=e)


def probe_duration(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def concat_shots(shots, dest, xfade_kind="fade"):
    """Cross-dissolve the shots together. Long xfade chains get unwieldy past a few
    dozen inputs, so build it in batches and dissolve the batches together too."""
    if len(shots) == 1:
        sh(["ffmpeg", "-y", "-i", shots[0], "-c", "copy", dest])
        return dest

    def xfade_group(group, out):
        if len(group) == 1:          # nothing to dissolve with (a folded trailing batch)
            sh(["ffmpeg", "-y", "-i", group[0], "-c", "copy", out])
            return out
        ins = []
        for s in group:
            ins += ["-i", s]
        fc, prev, off = [], "0:v", 0.0
        for n in range(1, len(group)):
            off += probe_duration(group[n - 1]) - XFADE
            lbl = f"v{n}"
            fc.append(f"[{prev}][{n}:v]xfade=transition={xfade_kind}:"
                      f"duration={XFADE}:offset={off:.3f}[{lbl}]")
            prev = lbl
        sh(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", f"[{prev}]",
            "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-pix_fmt", "yuv420p", out])
        return out

    BATCH = 12
    if len(shots) <= BATCH:
        return xfade_group(shots, dest)
    tmpdir = os.path.dirname(dest)
    groups = [shots[i:i + BATCH] for i in range(0, len(shots), BATCH)]
    # A trailing group of one has nothing to dissolve with; fold it into the previous.
    if len(groups) > 1 and len(groups[-1]) == 1:
        orphan = groups.pop()
        groups[-1] = groups[-1] + orphan
    parts = [xfade_group(g, f"{tmpdir}/_grp{n:02d}.mp4") for n, g in enumerate(groups)]
    return xfade_group(parts, dest)


def mux(video, music_wav, dest):
    vdur = probe_duration(video)
    fout = max(0.0, vdur - 6.0)
    sh(["ffmpeg", "-y", "-i", video, "-i", music_wav, "-filter_complex",
        f"[1:a]afade=t=in:st=0:d=3,afade=t=out:st={fout:.2f}:d=6[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", "-shortest", dest])


def finalize_silent(video, dest):
    """POC delivery: video only, still +faststart so it streams from the share dir."""
    sh(["ffmpeg", "-y", "-i", video, "-c:v", "copy", "-movflags", "+faststart", dest])


def render(cfg, d, seed, n_shots):
    """Walk the journey in order and return the assembled, music-free video path."""
    preflight()
    for sub in ("keys", "clips", "shots"):
        os.makedirs(f"{d}/{sub}", exist_ok=True)
    total = len(cfg['journey'])
    n_shots = min(n_shots, total)
    print(f"pastoral: {n_shots} shots x {CLIPS_PER_SHOT} generations "
          f"= {n_shots * CLIPS_PER_SHOT} clips, ~{n_shots * SHOT_DUR / 60:.1f} min", flush=True)
    shots = [render_shot(cfg, i, total, d, seed) for i in range(n_shots)]
    silent = f"{d}/video.mp4"
    concat_shots(shots, silent, cfg['xfade_kind'])
    print(f"assembled {probe_duration(silent):.1f}s", flush=True)
    return silent
