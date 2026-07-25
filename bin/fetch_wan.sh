#!/usr/bin/env bash
# Download the Wan 2.2 TI2V-5B weights the pastoral pipeline needs.
# Nothing video-related was on this box: models/diffusion_models was empty and
# extra_model_paths.yaml only pointed at forge-neo's SD checkpoints.
set -euo pipefail

COMFY="${COMFY:-/home/gpaasch/ComfyUI}"
BASE="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files"
NEED_GB=20   # ~10G unet + ~6.7G text encoder + ~1.4G vae, plus headroom to write

avail_gb=$(df -BG --output=avail "$COMFY" | tail -1 | tr -dc '0-9')
if [ "$avail_gb" -lt "$NEED_GB" ]; then
  echo "REFUSING: ${avail_gb}G free under $COMFY, need ~${NEED_GB}G." >&2
  echo "Free space first (largest dirs: ~/llama_cpp_lab_setup, ~/ai, ~/forge-neo)," >&2
  echo "or set COMFY to a path on a roomier volume and add it to extra_model_paths.yaml." >&2
  exit 1
fi

fetch() {  # fetch <url> <dest>
  if [ -s "$2" ]; then echo "have $(basename "$2")"; return; fi
  echo "fetching $(basename "$2")"
  mkdir -p "$(dirname "$2")"
  curl -fL --retry 3 -C - -o "$2.part" "$1"
  mv "$2.part" "$2"
}

fetch "$BASE/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" \
      "$COMFY/models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"
fetch "$BASE/vae/wan2.2_vae.safetensors" \
      "$COMFY/models/vae/wan2.2_vae.safetensors"
fetch "$BASE/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
      "$COMFY/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"

echo
echo "Done. Restart ComfyUI so it rescans the model directories, then:"
echo "  ./forge pastoral 1 --poc"
