# Resmarke Launch Runbook

This is the fastest path to launch Privacy-Max now and DeepClean GPU beta next.

## 0. Install Local Tools

This machine currently does not have the Supabase CLI or Docker installed.

Install:

```bash
brew install supabase/tap/supabase
```

Install Docker Desktop or OrbStack if you want to build the GPU image locally. If you do not want Docker locally, use GitHub Actions or another cloud builder to publish `deepclean-worker/`.

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
supabase functions deploy deepclean-webhook --no-verify-jwt
```

Set Supabase secrets:

```bash
supabase secrets set RUNPOD_API_KEY=...
supabase secrets set RUNPOD_ENDPOINT_ID=...
supabase secrets set DEEPCLEAN_WEBHOOK_SECRET=use-a-long-random-string
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

Local Docker path:

```bash
cd deepclean-worker
docker build -t ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest .
docker push ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest
```

No-local-Docker path:

1. Push repo to GitHub.
2. Build `deepclean-worker/Dockerfile` with GitHub Actions, Docker Hub, or another cloud builder.
3. Publish to GHCR or Docker Hub.

## 5. RunPod Serverless Endpoint

Create RunPod Serverless endpoint:

- Image: `ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest`
- GPU: A40/A6000/L40S, 48 GB preferred for bakeoff
- Concurrency: `1`
- Timeout: `180s`
- Container disk: `50 GB+`
- Idle timeout: low during beta

Set worker environment:

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs
HF_TOKEN=...
```

Copy the endpoint ID into Supabase:

```bash
supabase secrets set RUNPOD_ENDPOINT_ID=YOUR_ENDPOINT_ID
```

## 6. First End-to-End Test

1. Open the app.
2. Sign in by magic link.
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
- Do not claim guaranteed SynthID removal forever.
- Say: "advanced hidden watermark reduction" and "charged only when processing succeeds."
