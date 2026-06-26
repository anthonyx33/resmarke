#!/usr/bin/env bash
# Entrypoint for the DeepClean RunPod serverless worker.
# Order: seed model volume -> start ComfyUI as a localhost service -> wait for
# ready -> hand off to the RunPod serverless handler. ComfyUI keeps Qwen +
# controlnet resident in VRAM across jobs, so only the first job pays model load.
set -euo pipefail

COMFY_BASE="${COMFYUI_BASE:-/runpod-volume/ComfyUI}"
PORT="${COMFYUI_PORT:-8188}"

echo "[deepclean:start] seeding model volume at ${COMFY_BASE}"
python /app/bootstrap_models.py

echo "[deepclean:start] launching ComfyUI on 127.0.0.1:${PORT}"
cd /app/ComfyUI
python main.py \
    --listen 127.0.0.1 \
    --port "${PORT}" \
    --base-path "${COMFY_BASE}" \
    --preview-method none \
    --disable-metadata &

# Wait until ComfyUI's API is answering.
echo "[deepclean:start] waiting for ComfyUI /system_stats"
for i in $(seq 1 120); do
    if python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:${PORT}/system_stats', timeout=2)" >/dev/null 2>&1; then
        echo "[deepclean:start] ComfyUI ready after ${i}s"
        break
    fi
    sleep 1
done

if ! python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/system_stats', timeout=2)" >/dev/null 2>&1; then
    echo "[deepclean:start] FATAL: ComfyUI did not become ready" >&2
    exit 1
fi

echo "[deepclean:start] starting RunPod serverless handler"
exec python -u /app/worker.py
