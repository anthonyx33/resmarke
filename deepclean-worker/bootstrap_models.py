"""Idempotently download the 10 Remarkee Max model files onto the
persistent RunPod network volume so cold starts load from disk.

Run once at container start (see start.sh). Skips any file already present.
Re-running is cheap and safe. Set HF_TOKEN in the environment for any private
gated repos (none of the v2 files are gated, but the var is honored if set).

Files + directories come straight from the Remarkee Max model list.
"""
import os
import sys
import time
from pathlib import Path

import requests

COMFY_BASE = Path(os.environ.get("COMFYUI_BASE", "/runpod-volume/ComfyUI"))
MODELS = COMFY_BASE / "models"

# (filename, subpath under models/, url)
FILES = [
    # Qwen Image global-redraw path
    ("qwen-image-2512-Q4_K_M.gguf", "diffusion_models",
     "https://huggingface.co/unsloth/Qwen-Image-2512-GGUF/resolve/main/qwen-image-2512-Q4_K_M.gguf"),
    ("Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf", "clip",
     "https://huggingface.co/unsloth/Qwen2.5-VL-7B-Instruct-GGUF/resolve/main/Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"),
    ("qwen_image_vae.safetensors", "vae",
     "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors"),
    ("qwen_image_canny_diffsynth_controlnet.safetensors", "model_patches",
     "https://huggingface.co/Comfy-Org/Qwen-Image-DiffSynth-ControlNets/resolve/main/split_files/model_patches/qwen_image_canny_diffsynth_controlnet.safetensors"),
    ("Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors", "loras",
     "https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"),
    # Z-Image Turbo face-cleanup path
    ("z_image_turbo-Q4_K_M.gguf", "diffusion_models",
     "https://huggingface.co/jayn7/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_K_M.gguf"),
    ("Qwen_3_4b-imatrix-IQ4_XS.gguf", "clip",
     "https://huggingface.co/worstplayer/Z-Image_Qwen_3_4b_text_encoder_GGUF/resolve/main/Qwen_3_4b-imatrix-IQ4_XS.gguf"),
    ("ae.safetensors", "vae",
     "https://huggingface.co/Comfy-Org/Z-Image-ComfyUI/resolve/main/split_files/vae/ae.safetensors"),
    # Face detection / segmentation
    ("yolov8n-face.pt", "ultralytics/bbox",
     "https://huggingface.co/Bingsu/adetailer/resolve/main/face_yolov8n.pt"),
    ("sam_vit_b_01ec64.pth", "sams",
     "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"),
]

CHUNK = 1024 * 1024  # 1 MiB


def download(url: str, dest: Path, retries: int = 4) -> None:
    headers = {"User-Agent": "resmarke-deepclean-bootstrap/1.0"}
    token = os.environ.get("HF_TOKEN")
    if token and "huggingface.co" in url:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(dest.suffix + ".part")
                written = 0
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=CHUNK):
                        if chunk:
                            fh.write(chunk)
                            written += len(chunk)
                            if total and written % (50 * CHUNK) == 0:
                                pct = written * 100 // total
                                print(f"  {dest.name}: {pct}% ({written//1048576}MiB)", flush=True)
                tmp.replace(dest)
                print(f"  {dest.name}: done ({written//1048576}MiB)", flush=True)
                return
        except Exception as exc:  # noqa: BLE001
            print(f"  {dest.name}: attempt {attempt}/{retries} failed: {exc}", flush=True)
            if attempt == retries:
                raise
            time.sleep(5 * attempt)


def main() -> int:
    print(f"[bootstrap] ComfyUI base: {COMFY_BASE}", flush=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    missing = [(name, sub, url) for (name, sub, url) in FILES
               if not (MODELS / sub / name).exists()]
    if not missing:
        present = len(FILES) - len(missing)
        print(f"[bootstrap] all {present} model files already present; nothing to do", flush=True)
        return 0

    print(f"[bootstrap] {len(missing)}/{len(FILES)} files missing; downloading", flush=True)
    for name, sub, url in missing:
        dest = MODELS / sub / name
        if dest.exists():
            continue
        print(f"[bootstrap] {name} -> models/{sub}/", flush=True)
        download(url, dest)

    print("[bootstrap] complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
