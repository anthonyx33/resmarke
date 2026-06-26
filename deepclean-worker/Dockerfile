FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

# Cache model weights on the RunPod serverless network volume (mounted at
# /runpod-volume) so cold starts load from disk instead of re-downloading.
# These are defaults; the endpoint env can still override them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/runpod-volume/hf \
    HF_HUB_CACHE=/runpod-volume/hf/hub \
    HF_ASSETS_CACHE=/runpod-volume/hf/assets \
    TRANSFORMERS_CACHE=/runpod-volume/hf/transformers \
    DIFFUSERS_CACHE=/runpod-volume/hf/diffusers \
    TORCH_HOME=/runpod-volume/torch \
    XDG_CACHE_HOME=/runpod-volume/.cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY worker.py /app/worker.py

CMD ["python", "-u", "/app/worker.py"]
