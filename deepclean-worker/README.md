# DeepClean Worker

RunPod Serverless worker for DeepClean GPU jobs.

## Build

```bash
docker build -t ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest .
docker push ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest
```

If Docker is not installed locally, push this repo to GitHub and run the included `DeepClean Worker Image` GitHub Actions workflow.

## RunPod Endpoint

Create a RunPod Serverless endpoint with:

- Container image: your published `resmarke-deepclean` image.
- GPU: 24 GB VRAM class (RTX 3090/4090, L4, A5000) — matches the Synthid-Bypass
  Q4_K_M GGUF setup. 40 GB+ (A6000/L40S) keeps both Qwen + Z-Image resident.
- Concurrency: `1`.
- Timeout: `240` for `standard`, `300` for `strong`, `420` for `max`.
- Container disk: at least `60 GB`.
- Network volume: mount one at `/runpod-volume`. First boot downloads the 10
  Synthid-Bypass model files (~10 GB) into `/runpod-volume/ComfyUI/models/`;
  later boots skip the download.

### Scaling mode

Cost-controlled beta:

- Active workers: `0`
- Max workers: `1`
- Idle timeout: `60-300s`
- Tradeoff: the first job after scale-to-zero pays cold start + model preload.

Fast warm-model service:

- Active workers: `1`
- Max workers: `1` to start
- Idle timeout: any value; active worker stays running
- Tradeoff: continuous GPU billing, but the model is preloaded and user jobs skip most startup delay.

## Required Environment

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs
DEEPCLEAN_PRELOAD=1
DEEPCLEAN_PRELOAD_PROFILE=standard
DEEPCLEAN_SEED=0
HF_TOKEN=...
# Optional overrides (defaults shown):
# COMFYUI_BASE=/runpod-volume/ComfyUI
# COMFYUI_URL=http://127.0.0.1:8188
# DEEPCLEAN_WORKFLOW=/app/workflows/synthid-bypass-v2.api.json
```

The engine is **ComfyUI running the Synthid-Bypass v2 workflow** (Qwen Image
global redraw + Z-Image Turbo face cleanup, Q4_K_M GGUF). `start.sh` launches
ComfyUI as a localhost service on `127.0.0.1:8188`, waits for it, then starts
the RunPod handler; the handler talks to ComfyUI via `comfyui_client.py`.
ComfyUI keeps Qwen + the Canny controlnet resident in VRAM across jobs, so only
the first job pays the model-load cost. `DEEPCLEAN_PRELOAD=1` warms the models
at boot.

Before the worker can process jobs, you must export the API-format workflow
once — see `workflows/EXPORT.md` — so `workflows/synthid-bypass-v2.api.json`
exists (the worker refuses to run without it).

The job payload supplies the webhook URL and webhook secret.

## Smoke Test

Use RunPod's test console with a payload matching `test-job.example.json`. For a real test, create a DeepClean job through the app so the signed input URL and output path are valid.

Warmup-only payload for the RunPod test console:

```json
{
  "input": {
    "action": "warmup",
    "profile": "standard"
  }
}
```

The first warmup can take minutes (downloading the 10 model files on first boot, then loading Qwen into VRAM). Later warmups on the same worker return quickly and report `"warmed": true`.
