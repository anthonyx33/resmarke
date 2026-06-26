FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

# ComfyUI is the cleaning engine. Model weights cache on the RunPod serverless
# network volume (mounted at /runpod-volume) so cold starts load from disk
# instead of re-downloading. COMFYUI_BASE points ComfyUI at that volume.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/runpod-volume/hf \
    HF_HUB_CACHE=/runpod-volume/hf/hub \
    HF_ASSETS_CACHE=/runpod-volume/hf/assets \
    TRANSFORMERS_CACHE=/runpod-volume/hf/transformers \
    DIFFUSERS_CACHE=/runpod-volume/hf/diffusers \
    TORCH_HOME=/runpod-volume/torch \
    XDG_CACHE_HOME=/runpod-volume/.cache \
    COMFYUI_BASE=/runpod-volume/ComfyUI

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# --- ComfyUI core ---
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI \
    && cd /app/ComfyUI \
    && pip install --no-cache-dir -r requirements.txt

# --- Custom node packs required by Synthid-Bypass v2 ---
WORKDIR /app/ComfyUI/custom_nodes
RUN for repo in \
    "https://github.com/city96/ComfyUI-GGUF.git ComfyUI-GGUF" \
    "https://github.com/ltdrdata/ComfyUI-Impact-Pack.git ComfyUI-Impact-Pack" \
    "https://github.com/rgthree/rgthree-comfy.git rgthree-comfy" \
    "https://github.com/Fannovel16/comfyui_controlnet_aux.git comfyui_controlnet_aux" \
    "https://github.com/kijai/ComfyUI-KJNodes.git ComfyUI-KJNodes" \
    "https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git ComfyUI-Inpaint-CropAndStitch" \
    "https://github.com/ClownsharkBatwing/RES4LYF.git RES4LYF" \
    "https://github.com/00quebec/Synthid-Bypass.git Synthid-Bypass" \
    ; do \
        set -- $repo; \
        echo "[docker] cloning $1 -> $2"; \
        git clone --depth 1 "$1" "$2"; \
        if [ -f "$2/requirements.txt" ]; then \
            echo "[docker] installing requirements for $2"; \
            pip install --no-cache-dir -r "$2/requirements.txt" || echo "[docker] WARN: requirements install failed for $2"; \
        fi; \
    done

# --- Handler glue ---
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY bootstrap_models.py /app/bootstrap_models.py
COPY comfyui_client.py /app/comfyui_client.py
COPY worker.py /app/worker.py
COPY workflows /app/workflows
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
