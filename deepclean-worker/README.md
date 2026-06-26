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
- Timeout: `180` seconds.
- Container disk: at least `50 GB`; use more if model caches are baked into the image or volume.
- Idle timeout: low during beta to control spend.

## Required Environment

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs
DEEPCLEAN_MODEL=
HF_TOKEN=...
```

The job payload supplies the webhook URL and webhook secret.

## Smoke Test

Use RunPod's test console with a payload matching `test-job.example.json`. For a real test, create a DeepClean job through the app so the signed input URL and output path are valid.
