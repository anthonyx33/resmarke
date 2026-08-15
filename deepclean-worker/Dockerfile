FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime@sha256:2b59b1b91885677814f78be1f8df48a25d5dc952eb6580eaecfefca510f9afd3

# Deploy this image by the digest resolved from its immutable git-SHA tag.
# Never deploy or promote an unverified :latest tag.

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

# Guard every pip install against moving the torch stack supplied by the base
# image. This is intentionally a critical constraint set, not a full lockfile.
COPY constraints.txt /app/constraints.txt

# --- ComfyUI core (run-#39 source snapshot) ---
RUN set -eux; \
    git init /app/ComfyUI; \
    git -C /app/ComfyUI remote add origin https://github.com/Comfy-Org/ComfyUI.git; \
    git -C /app/ComfyUI fetch --depth 1 origin 7fe8a6138504f90ff7be82f3babf416da32876b1; \
    git -C /app/ComfyUI checkout --detach FETCH_HEAD; \
    python -m pip install --no-cache-dir -c /app/constraints.txt -r /app/ComfyUI/requirements.txt

# --- Custom node packs required by Remarkee Max ---
# The Remarkee Max adaptive-denoise + face-detailer nodes are vendored in this
# repo (custom_nodes/RemarkeeMax). The public node packs use the exact source
# snapshot resolved during GitHub Actions run #39:
#   ComfyUI-GGUF                 6ea2651e7df66d7585f6ffee804b20e92fb38b8a
#   ComfyUI-Impact-Pack          429d0159ad429e64d2b3916e6e7be9c22d025c3c
#   ComfyUI-Impact-Subpack       50c7b71a6a224734cc9b21963c6d1926816a97f1
#   rgthree-comfy                6b76ee6f2c5a007710b5a16f97c94330d6ecc871
#   comfyui_controlnet_aux       e8b689a513c3e6b63edc44066560ca5919c0576e
#   ComfyUI-KJNodes              203eb357743402b437db8ae973a062a9b15387d2
#   Inpaint-CropAndStitch        2dfaf6c9689f16315a428ce3df06983b22a163c0
#   masquerade-nodes-comfyui     432cb4d146a391b387a0cd25ace824328b5b61cf
#   RES4LYF                      26036f647ca15d3048a193daf99a40cecfc3820d
WORKDIR /app/ComfyUI/custom_nodes
RUN set -eux; \
    fetch_repo() { \
        repo_url="$1"; \
        repo_dir="$2"; \
        repo_sha="$3"; \
        git init "$repo_dir"; \
        git -C "$repo_dir" remote add origin "$repo_url"; \
        git -C "$repo_dir" fetch --depth 1 origin "$repo_sha"; \
        git -C "$repo_dir" checkout --detach FETCH_HEAD; \
    }; \
    fetch_repo https://github.com/city96/ComfyUI-GGUF.git ComfyUI-GGUF 6ea2651e7df66d7585f6ffee804b20e92fb38b8a; \
    fetch_repo https://github.com/ltdrdata/ComfyUI-Impact-Pack.git ComfyUI-Impact-Pack 429d0159ad429e64d2b3916e6e7be9c22d025c3c; \
    fetch_repo https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git ComfyUI-Impact-Subpack 50c7b71a6a224734cc9b21963c6d1926816a97f1; \
    fetch_repo https://github.com/rgthree/rgthree-comfy.git rgthree-comfy 6b76ee6f2c5a007710b5a16f97c94330d6ecc871; \
    fetch_repo https://github.com/Fannovel16/comfyui_controlnet_aux.git comfyui_controlnet_aux e8b689a513c3e6b63edc44066560ca5919c0576e; \
    fetch_repo https://github.com/kijai/ComfyUI-KJNodes.git ComfyUI-KJNodes 203eb357743402b437db8ae973a062a9b15387d2; \
    fetch_repo https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git ComfyUI-Inpaint-CropAndStitch 2dfaf6c9689f16315a428ce3df06983b22a163c0; \
    fetch_repo https://github.com/BadCafeCode/masquerade-nodes-comfyui.git masquerade-nodes-comfyui 432cb4d146a391b387a0cd25ace824328b5b61cf; \
    fetch_repo https://github.com/ClownsharkBatwing/RES4LYF.git RES4LYF 26036f647ca15d3048a193daf99a40cecfc3820d

# Impact-Pack otherwise installs SAM2 from a moving default branch.
RUN set -eux; \
    sed -i \
        's|git+https://github.com/facebookresearch/sam2.git|git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4|' \
        /app/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/requirements.txt; \
    grep -Fx \
        'git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4' \
        /app/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/requirements.txt; \
    for node_dir in \
        ComfyUI-GGUF \
        ComfyUI-Impact-Pack \
        ComfyUI-Impact-Subpack \
        rgthree-comfy \
        comfyui_controlnet_aux \
        ComfyUI-KJNodes \
        ComfyUI-Inpaint-CropAndStitch \
        masquerade-nodes-comfyui \
        RES4LYF; \
    do \
        if [ -f "/app/ComfyUI/custom_nodes/${node_dir}/requirements.txt" ]; then \
            echo "[docker] installing requirements for ${node_dir}"; \
            python -m pip install --no-cache-dir -c /app/constraints.txt \
                -r "/app/ComfyUI/custom_nodes/${node_dir}/requirements.txt"; \
        fi; \
    done

# --- Handler glue ---
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -c /app/constraints.txt -r /app/requirements.txt

COPY bootstrap_models.py /app/bootstrap_models.py
COPY comfyui_client.py /app/comfyui_client.py
COPY content_repair.py /app/content_repair.py
COPY deepclean_detector.py /app/deepclean_detector.py
COPY ds_remint_v6.py /app/ds_remint_v6.py
COPY iphone_exif.py /app/iphone_exif.py
COPY max_cx_remint.py /app/max_cx_remint.py
COPY max_optimised_remint.py /app/max_optimised_remint.py
COPY max_remint.py /app/max_remint.py
COPY neural_texture.py /app/neural_texture.py
COPY photo_naturalization.py /app/photo_naturalization.py
COPY worker.py /app/worker.py
COPY workflows /app/workflows
COPY tools /app/tools
COPY custom_nodes/RemarkeeMax /app/ComfyUI/custom_nodes/RemarkeeMax
COPY smoke_test.py /app/smoke_test.py
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# --- Fatal build-time gates ---
RUN cd /app && PYTHONPATH=/app/ComfyUI python -c 'import importlib.metadata as metadata, json, torch, comfy_kitchen, comfy.utils, ds_remint_v6; assert torch.__version__.startswith("2.7.1"), torch.__version__; assert torch.version.cuda == "12.6", torch.version.cuda; backends = comfy_kitchen.list_backends(); print("torch:", torch.__version__); print("torch CUDA runtime:", torch.version.cuda); print("comfy-kitchen:", metadata.version("comfy-kitchen")); print("comfy-kitchen backends:", json.dumps(backends, sort_keys=True)); assert backends.get("eager", {}).get("available") is True, backends; print("OK: imports, versions, and eager backend")'
RUN python /app/workflows/validate_api_workflow.py
RUN cd /app/ComfyUI && python main.py --cpu --quick-test-for-ci
RUN python /app/smoke_test.py
RUN python -m pip check

CMD ["/app/start.sh"]
