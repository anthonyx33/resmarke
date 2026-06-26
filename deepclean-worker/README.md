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
- GPU: A40/A6000/L40S class, 48 GB preferred for the first bakeoff.
- Concurrency: `1`.
- Timeout: `240` seconds for `standard`, `300` seconds if you expose `strong`.
- Container disk: at least `50 GB`; use more if model caches are baked into the image or volume.

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
DEEPCLEAN_ENGINE_MODE=python
DEEPCLEAN_PRELOAD=1
DEEPCLEAN_PRELOAD_PROFILE=standard
DEEPCLEAN_DEVICE=cuda
DEEPCLEAN_MODEL=
DEEPCLEAN_SEED=0
HF_TOKEN=...
```

`DEEPCLEAN_ENGINE_MODE=python` uses the in-process `InvisibleEngine` and reuses it across jobs. Set
`DEEPCLEAN_ENGINE_MODE=cli` only as a temporary fallback/debug mode.

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

The first warmup can take minutes if model files are not cached. Later warmups on the same worker should return quickly and report `"cached": true`.
