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
- GPU: 24 GB VRAM class (RTX 3090/4090, L4, A5000) — matches the Remarkee Max
  Q4_K_M GGUF setup. 40 GB+ (A6000/L40S) keeps both Qwen + Z-Image resident.
- Concurrency: `1`.
- Timeout: `240` for `standard`, `300` for `strong`, `420` for `max`.
- Container disk: at least `60 GB`.
- Network volume: mount one at `/runpod-volume`. First boot downloads the 10
  Remarkee Max model files (~10 GB) into `/runpod-volume/ComfyUI/models/`;
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
# DEEPCLEAN_WORKFLOW=/app/workflows/remarkee-max-v2.api.json
```

The engine is **ComfyUI running the Remarkee Max workflow** (Qwen Image
global redraw + Z-Image Turbo face cleanup, Q4_K_M GGUF). `start.sh` launches
ComfyUI as a localhost service on `127.0.0.1:8188`, waits for it, then starts
the RunPod handler; the handler talks to ComfyUI via `comfyui_client.py`.
ComfyUI keeps Qwen + the Canny controlnet resident in VRAM across jobs, so only
the first job pays the model-load cost. `DEEPCLEAN_PRELOAD=1` warms the models
at boot.

Before the worker can process jobs, you must export the API-format workflow
once — see `workflows/EXPORT.md` — so `workflows/remarkee-max-v2.api.json`
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

## Postmortem — Aug 22 2026: endpoint stuck "Initializing", zero workers, zero logs

**Symptom.** New endpoint `remint-v6` (`2c9528ebg2vzvx`) sat at "Initializing"
for 15+ minutes. `/health` reported every worker counter at 0 while jobs piled
up in the queue. **No container logs were ever produced.**

**Root cause: the GPU selection was narrowed until nothing could be scheduled.**
The endpoint's release #2 set:

```
AMPERE_24,-NVIDIA L4,-NVIDIA RTX A5000,-NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 1g.24gb
```

Those three exclusions leave **RTX 3090 as the only permitted GPU**. Because a
network volume is attached (required — see above), the endpoint is also pinned
to that volume's single data center. Allowed GPUs ∩ that data center's
serverless 3090 capacity was empty, so RunPod never allocated a machine. No
machine means no container, and no container means **no logs at all** — that
total absence of logs is the diagnostic signature. A failed image pull looks
different: it produces logs and an `unhealthy` worker.

**Fix.** Re-enable the full 24 GB tier (L4, A5000, Blackwell MIG). RunPod
serverless bills per **VRAM tier**, not per GPU model — every card in the 24 GB
tier bills at the same flex rate, so excluding models saves nothing and only
destroys schedulable capacity. Keep the 24 GB tier itself: the Q4_K_M GGUF
weights are chosen to fit it (observed peak load 12.7 GB of 22.6 GB usable).

### Things ruled out — do not re-investigate these

- **GHCR package private / registry credentials.** Not the cause. The package
  pulls anonymously; verified by fetching a `ghcr.io/token` scope token and
  resolving the manifest (HTTP 200). Leave registry credentials **blank**.
- **Wrong image / wrong architecture.** Tag
  `4c7235cefa5495232d9e924c3b83998760420edd` resolves to digest
  `sha256:34d6eb5d…`, matching what the endpoint pinned; config blob reports
  `architecture=amd64`, `os=linux`, `Cmd=["/app/start.sh"]`.
- **"Container image validation" toggle.** This option no longer exists in the
  current RunPod console. Its absence is normal, not a misconfiguration.

### Gotchas confirmed while fixing this

- **Never deploy `:latest`.** It resolves to a *different* digest
  (`sha256:cf8a357f…`) than the newest git-SHA tag. Always pin the full
  commit SHA tag, as the Dockerfile header already warns.
- **Leave "Container Start Command" empty.** The image supplies
  `CMD ["/app/start.sh"]`; anything typed there overrides it and breaks boot.
- **Container disk:** the image is 8.19 GB compressed across 44 layers and
  unpacks to roughly 20 GB. RunPod's 5 GB default cannot hold it.
- **Model payload is ~30.2 GB, not the ~10 GB stated earlier in this file.**
  Measured via HTTP HEAD against each URL in `bootstrap_models.py`
  (qwen-image-2512 Q4_K_M alone is 13.24 GB, z_image_turbo 4.98 GB,
  Qwen2.5-VL-7B 4.68 GB). Size the network volume accordingly.
- **Benign error in worker logs — ignore it:**
  `Can't find mmproj file for 'Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf' …
  Qwen-Image-Edit will be broken!` plus a long `clip missing: ['visual.*']`
  warning. `remarkee-max-v2.api.json` contains **no** Qwen-Image-Edit or vision
  nodes; node 608 feeds node 564 (Power Lora Loader) into plain `CLIPTextEncode`
  nodes 9/10, so only the *text* tower is used. The vision tensors are never
  requested. Confirmed by a clean run: `Prompt executed in 137.33 seconds`.

### Confirmed by worker logs (Aug 22, worker `5pi3xl6hg5zxw6`)

The scheduling diagnosis above was verified empirically — once the excluded
cards were re-enabled, the worker landed on one of them:

```
[INFO] Device: cuda:0 NVIDIA RTX A5000 : cudaMallocAsync
[INFO] Total VRAM 24112 MB
```

`NVIDIA RTX A5000` was one of the three GPUs the endpoint had been excluding.
Full boot then succeeded: models already cached on the volume
(`[bootstrap] all 11 model files already present`), ComfyUI ready in 12 s,
`runtime self-check passed`, and the handler registered:
`--- Starting Serverless Worker | Version 1.7.13 ---`.

### `DEEPCLEAN_PRELOAD=0` is the right setting for scale-to-zero

With Active Workers = 0 a worker only boots *because* a job arrived, so the
boot-time warmup is pure waste: it delays that job by ~137 s (measured) and
bills a throwaway 512x512 generation. The model-load cost is paid once either
way — preload only adds a redundant sampling pass and pushes back handler
registration. Set `DEEPCLEAN_PRELOAD=0` unless running with Active Workers >= 1.

### Expected failure: `KeyError: 'job_id'`

A queued smoke/test job whose `input` lacks `job_id` crashes at
[worker.py:116](worker.py) with `KeyError: 'job_id'`. This is **not** a bug —
`handler()` requires `job_id`, `webhook_url`, and `webhook_secret`, and
`dispatch-deepclean-job` supplies all three. Seeing this traceback means the
handler is alive and executing. Purge stale test jobs from the queue, or they
keep waking workers and failing. A warmup-only payload
(`{"input": {"action": "warmup"}}`) short-circuits before the `job_id` lookup
and is always safe.
