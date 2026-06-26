# ResMarke Launch Runbook

This is the fastest path to launch Privacy-Max now and DeepClean GPU beta next.

## 0. Install Local Tools

This machine currently does not have the Supabase CLI or Docker installed.

Install:

```bash
brew install supabase/tap/supabase
```

Install Docker Desktop or OrbStack if you want to build the GPU image locally. If you do not want Docker locally, use the included GitHub Actions workflow to publish `deepclean-worker/`.

## 1. Launch Privacy-Max First

Privacy-Max can launch without Supabase/RunPod in demo mode:

```bash
npm install
npm run build
npm run dev
```

Local URL:

```text
http://localhost:5173/
```

For production, deploy this repo to Vercel and set:

```bash
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_STRIPE_TRIAL_LINK=
VITE_STRIPE_PRO_LINK=
VITE_STRIPE_PRO_PLUS_LINK=
VITE_ADMIN_EMAILS=your-admin-email@example.com
```

## 2. Supabase Setup

Create a Supabase project.

Create private storage buckets:

- `deepclean-inputs`, private, max file size 25 MB, MIME: `image/jpeg,image/png,image/webp`
- `deepclean-outputs`, private, max file size 25 MB, MIME: `image/jpeg`

Apply the SQL in:

```text
supabase/migrations/0001_resmarke.sql
```

Fastest path: paste it into Supabase SQL Editor and run it.

CLI path:

```bash
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase db push
```

Deploy functions:

```bash
supabase functions deploy spend-privacy-credit
supabase functions deploy create-deepclean-job
supabase functions deploy dispatch-deepclean-job
supabase functions deploy get-deepclean-job
supabase functions deploy cancel-deepclean-job
supabase functions deploy admin-runpod-endpoint
supabase functions deploy deepclean-webhook --no-verify-jwt
```

Set Supabase secrets:

```bash
supabase secrets set RUNPOD_API_KEY=...
supabase secrets set RUNPOD_ENDPOINT_ID=...
supabase secrets set DEEPCLEAN_WEBHOOK_SECRET=use-a-long-random-string
supabase secrets set ADMIN_EMAILS=your-admin-email@example.com
```

Supabase automatically provides `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to Edge Functions.

## 3. Stripe Setup

Create payment links:

- Trial: `$1 / 7 days`, 15 Privacy-Max exports.
- Pro: `$19.99/mo`, 200 Privacy-Max exports.
- Pro+: `$29.99/mo`, 500 Privacy-Max exports.

For launch speed, payment links can redirect users back to the app. Add manual credit grants in Supabase at first, then wire Stripe webhooks after the MVP is live.

Credit grant SQL for a user:

```sql
update public.creator_profiles
set privacy_exports_remaining = privacy_exports_remaining + 200,
    updated_at = now()
where user_id = 'USER_UUID';
```

## 4. Build DeepClean GPU Image

The image now ships **ComfyUI + the Remarkee Max custom nodes** as the
cleaning engine (it no longer uses the `remove-ai-watermarks` SDXL pipeline).
Before building, complete the one-time workflow export in
`deepclean-worker/workflows/EXPORT.md` so `remarkee-max-v2.api.json` exists —
the worker will refuse to run without it.

Local Docker path:

```bash
cd deepclean-worker
docker build -t ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest .
docker push ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest
```

No-local-Docker path:

1. Push repo to GitHub.
2. Open GitHub Actions.
3. Run the `DeepClean Worker Image` workflow.
4. Use `ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest` as the RunPod image.

The image is larger than the old SDXL image (ComfyUI + 8 custom node packs).
Container disk should be `60 GB+`.

## 5. RunPod Serverless Endpoint

Create RunPod Serverless endpoint:

- Image: `ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest`
- GPU: 24 GB VRAM class (RTX 3090/4090, L4, A5000) — matches the Remarkee Max
  Q4_K_M GGUF setup. 40 GB+ (A6000/L40S) lets both Qwen + Z-Image stay resident.
- Concurrency: `1`
- Timeout: `240s` for standard beta; `300s` for strong; `420s` if exposing max
- Container disk: `60 GB+`
- Network volume: mount one at `/runpod-volume`. The first boot downloads the 10
  Remarkee Max model files (~10 GB) into `/runpod-volume/ComfyUI/models/` via
  `bootstrap_models.py`; later boots skip the download.

For lowest cost during beta:

- Active workers: `0`
- Max workers: `1`
- Idle timeout: `60-300s`

For fastest customer experience:

- Active workers: `1`
- Max workers: `1` to start
- `DEEPCLEAN_PRELOAD=1` so the model loads when the worker boots

The fast mode bills continuously while the active worker is running, but it avoids the worst user-facing cold start.

Set worker environment:

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

`DEEPCLEAN_PRELOAD=1` runs a small image through the workflow at boot so Qwen
+ the Canny controlnet land in VRAM; with `Active workers: 1` the first real
job skips the model-load delay. `start.sh` starts ComfyUI as a localhost
service on `127.0.0.1:8188` and then starts the RunPod handler.

Copy the endpoint ID into Supabase:

```bash
supabase secrets set RUNPOD_ENDPOINT_ID=YOUR_ENDPOINT_ID
```

## 6. First End-to-End Test

1. Open the app.
2. Sign in with email and password.
3. Grant your user credits:

```sql
update public.creator_profiles
set privacy_exports_remaining = 50,
    deepclean_credits = 10,
    updated_at = now()
where user_id = 'YOUR_USER_UUID';
```

4. Process one Privacy-Max image locally.
5. Queue one DeepClean beta job.
6. Watch:

```sql
select * from public.deepclean_jobs order by created_at desc limit 5;
select * from public.credit_ledger order by created_at desc limit 10;
```

7. Confirm the final file exists in `deepclean-outputs`.

## 7. Launch Rules

- Launch Privacy-Max publicly first.
- Keep DeepClean behind beta wording until 300-image bakeoff.
- Charge DeepClean only on successful worker completion.
- Do not claim guaranteed hidden-watermark removal forever.
- Say: "advanced hidden watermark reduction" and "charged only when processing succeeds."
