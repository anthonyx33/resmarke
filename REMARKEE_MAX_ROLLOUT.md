# Remarkee Max — Production Setup & Rollout Guide

A step-by-step, expert guide to taking Remarkee Max (the GPU regeneration tier)
from zero to production. This covers **every system, config value, and process
step** you need. Worker build/verify details live in `deepclean-worker/SETUP_AND_TEST.md`;
this doc is the cross-cutting production rollout.

---

## 0. Mental model — the three tiers and who does what

```
Browser (Vercel SPA)  ──►  Supabase (Postgres + Edge Functions + Storage + Auth)
                                   │
                                   ▼  dispatch + signed URLs
                            RunPod Serverless GPU worker
                                   │  (ComfyUI + vendored RemarkeeMax nodes)
                                   ▼  webhook POST back
                              Supabase  ──►  credit capture/release + result URL
```

- **Frontend** (`src/`): React/Vite SPA on Vercel. Renders the Remarkee Max card,
  calls Supabase edge functions, polls job status.
- **Supabase**: source of truth — `deepclean_jobs`, `creator_profiles`,
  `credit_ledger` tables; private storage buckets; 6 edge functions; auth.
- **RunPod worker** (`deepclean-worker/`): Docker container running ComfyUI as a
  localhost service + the RunPod serverless handler. Runs the Remarkee Max
  ComfyUI workflow (Qwen Image + Z-Image Turbo, Q4_K_M GGUF) on a 24 GB GPU.

The credit model: **1 credit reserved at job creation → captured on successful
completion → released (refunded) on failure.** Never charge on dispatch; only on
the webhook confirming success.

---

## 1. Prerequisites & accounts

- **Supabase** project (Postgres + Edge Functions + Storage). Note the project
  URL, the **anon** key (public, used by the frontend), and the **service role**
  key (secret, used by edge functions + the worker).
- **RunPod** account with Serverless + Network Volumes enabled. Generate an
  **API key**.
- **GitHub** repo (this one) — for the worker image GH Actions build, if you
  don't build Docker locally. A **GitHub Container Registry** (GHCR) token with
  `write:packages`.
- **Vercel** project for the frontend.
- **HuggingFace token**: **not required** — all 10 model files are public. Set
  `HF_TOKEN` only if you hit HF rate limits during the first model download.
- Docker Desktop / OrbStack **or** the GH Actions workflow (for the image).
- A GPU available locally or a throwaway RunPod pod for the one-time workflow
  export (Phase 3).

---

## 2. Phase 1 — Supabase (data, auth, storage, functions, secrets)

### 2.1 Apply the database migration

```bash
supabase db push
# or, from the SQL editor:
# paste supabase/migrations/0001_resmarke.sql
```

This creates `creator_profiles`, `credit_ledger`, `deepclean_jobs`, the private
storage buckets (`deepclean-inputs`, `deepclean-outputs`, 25 MB, MIME-restricted),
RLS policies (users read only their own rows), and an **auto-profile trigger** so
every new auth user gets a `creator_profiles` row (3 free privacy exports, 0
DeepClean credits). The `deepclean_credits` column has a `>= 0` check constraint —
credit operations can never go negative.

### 2.2 Configure auth

- Enable **Email/password** auth (the app uses it). Confirm the
  `on_auth_user_created_creator_profile` trigger fires on signup — new users get
  a profile row automatically.
- (Optional) set the email template, disable "confirm email" for beta, or enable
  Google/GitHub OAuth later.

### 2.3 Storage bucket policies

The buckets are created **private** by the migration. Edge functions use the
service role key to mint signed upload/download URLs — users never touch storage
directly. Confirm no public policies exist:

```sql
select id, public from storage.buckets;
-- both rows must show public=false
```

### 2.4 Deploy the 6 edge functions

```bash
supabase functions deploy create-deepclean-job
supabase functions deploy dispatch-deepclean-job
supabase functions deploy get-deepclean-job
supabase functions deploy cancel-deepclean-job
supabase functions deploy admin-runpod-endpoint
supabase functions deploy deepclean-webhook --no-verify-jwt   # ← called by RunPod, not a user JWT
```

`deepclean-webhook` MUST be deployed with `--no-verify-jwt` — RunPod calls it
with a shared secret, not a user session. (It still authenticates via
`DEEPCLEAN_WEBHOOK_SECRET` in the body.) All others verify JWTs normally.

### 2.5 Set Supabase edge-function secrets

```bash
# RunPod access (Supabase → RunPod dispatch):
supabase secrets set RUNPOD_API_KEY=rpa_xxx
supabase secrets set RUNPOD_ENDPOINT_ID=xxxx                  # from Phase 4
supabase secrets set DEEPCLEAN_WEBHOOK_SECRET=$(openssl rand -hex 32)

# The service role key the functions + worker use:
supabase secrets set SUPABASE_URL=https://YOUR_PROJECT.supabase.co
supabase secrets set SUPABASE_SERVICE_ROLE_KEY=eyJ...        # service role key
```

**Copy the `DEEPCLEAN_WEBHOOK_SECRET` value** — the RunPod worker needs the same
value (Phase 4). Keep the service role key out of git (it's a secret, never a
VITE_ var).

### 2.6 Storage lifecycle (production hardening — do before GA)

By default outputs live in `deepclean-outputs` forever. Add a cleanup policy so
you're not storing customer images indefinitely:

- Set a bucket lifecycle / scheduled edge function that deletes `deepclean-inputs`
  objects after ~1 hour (the worker already deletes inputs post-job) and
  `deepclean-outputs` after e.g. 24–72h (signed download URLs are short-lived
  anyway). This is a **compliance + cost** move — customer image retention should
  be minimal and documented in your privacy policy.

---

## 3. Phase 2 — Build & publish the worker image

The worker image ships ComfyUI + 7 public custom-node packs + the vendored
`RemarkeeMax` node pack + the handler glue. It is large; expect a long first build.

```bash
cd deepclean-worker
docker build -t ghcr.io/YOUR_GH_USER/resmarke-deepclean:latest .
docker push ghcr.io/YOUR_GH_USER/resmarke-deepclean:latest
```

No-local-Docker path: push the branch to GitHub and run the **DeepClean Worker
Image** workflow, then use `ghcr.io/YOUR_GH_USER/resmarke-deepclean:latest`.

> **Watch the build log for**: `WARN: requirements install failed for RES4LYF`
> (or `comfyui_controlnet_aux`). RES4LYF is the most fragile install and the face
> path depends on its `res_2s` sampler. If it fails, the face detailer errors at
> runtime — resolve before going further.

---

## 4. Phase 3 — One-time: export the ComfyUI API workflow + seed the model volume

These are the **two manual one-time steps** that block the worker from running.
The worker refuses jobs without the API-format workflow template.

### 4.1 Export `remarkee-max-v2.api.json`

The workflow ships in `deepclean-worker/workflows/remarkee-max-v2.0.json` (editor
format). ComfyUI's `/prompt` API needs the **API format**. On a machine with a
GPU + ComfyUI + all 8 node packs + the 10 models installed:

1. Drop `deepclean-worker/custom_nodes/RemarkeeMax/` into ComfyUI's
   `custom_nodes/`. (Do NOT also install the upstream pack — our vendored pack
   registers the `RemarkeeMax-*` node names the workflow expects.)
2. Clone the other 7 public packs (see the `Dockerfile` clone list) and download
   the 10 models into the dirs `deepclean-worker/bootstrap_models.py` specifies.
3. Drag `remarkee-max-v2.0.json` onto the ComfyUI canvas. Resolve every
   red/missing error until the graph is green.
4. **Gear menu → Save (API Format)** → save as
   `deepclean-worker/workflows/remarkee-max-v2.api.json`.
5. Commit it. The worker reads this at `DEEPCLEAN_WORKFLOW`
   (default `/app/workflows/remarkee-max-v2.api.json`, baked into the image).

Verify it's the flat API format: values look like
`"<id>": {"class_type": "LoadImage", "inputs": {...}}`, **not**
`{"nodes": [...], "links": [...]}`.

### 4.2 Seed the model volume (first cold start)

On the RunPod endpoint's **first** worker boot, `start.sh` runs
`bootstrap_models.py`, downloading the 10 model files (~10 GB) into
`/runpod-volume/ComfyUI/models/`. The network volume persists, so **only the
first worker ever downloads** — later boots skip straight to "all present".

Two ways to handle the first-download cost (it can exceed the default boot
timeout):

- **Raise the endpoint boot timeout to `1200s+`** for the first cold start, then
  lower it after the volume is seeded; **or**
- **Pre-seed manually**: spin up a throwaway RunPod pod that mounts the same
  network volume, run `python /app/bootstrap_models.py` once, shut it down.
  Then the serverless worker boots instantly.

Confirm seeding by checking the worker logs for
`[bootstrap] all 10 model files already present` and
`[deepclean:cache] comfy models populated=True`.

---

## 5. Phase 4 — RunPod Serverless endpoint

Create a **Serverless** endpoint:

| Setting | Value | Why |
|---|---|---|
| Image | `ghcr.io/YOUR_GH_USER/resmarke-deepclean:latest` | the Phase 2 image |
| GPU | 24 GB class: RTX 3090 / 4090 / L4 / A5000 | matches the Q4_K_M GGUF setup; 40 GB+ (A6000/L40S) keeps both Qwen + Z-Image resident |
| Concurrency | `1` | ComfyUI holds one job at a time per worker |
| Timeout | `240s` standard · `300s` strong · `420s` max | per-profile runtimes + model load headroom |
| Container disk | `60 GB+` | ComfyUI + node packs + working files |
| Network volume | mount one at `/runpod-volume` | models + HF cache persist across cold starts |
| Boot timeout | `1200s+` for first cold start, then `300s` | covers the one-time 10 GB download |

### Worker environment (set in the RunPod endpoint env panel)

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...                         # same as Supabase edge secret
DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs
DEEPCLEAN_PRELOAD=1                                       # warm Qwen into VRAM at boot
DEEPCLEAN_PRELOAD_PROFILE=standard
DEEPCLEAN_SEED=0                                          # deterministic output (optional)
# Webhook secret — must equal the Supabase DEEPCLEAN_WEBHOOK_SECRET:
DEEPCLEAN_WEBHOOK_SECRET=<the value from 2.5>
# Optional overrides (defaults shown):
# COMFYUI_BASE=/runpod-volume/ComfyUI
# COMFYUI_URL=http://127.0.0.1:8188
# DEEPCLEAN_WORKFLOW=/app/workflows/remarkee-max-v2.api.json
# HF_TOKEN=...   (only if HF rate-limited)
```

> ⚠️ **Wait — does the worker read `DEEPCLEAN_WEBHOOK_SECRET`?** The webhook
> secret is currently passed **per-job in the dispatch payload** (Supabase sends
> `webhook_secret` in the job input; the worker includes it in the webhook body).
> So the worker does **not** need a `DEEPCLEAN_WEBHOOK_SECRET` env var — the
> secret flows through the job payload. Confirm `dispatch-deepclean-job` reads
> `DEEPCLEAN_WEBHOOK_SECRET` from Supabase secrets and forwards it. Do **not**
> put the secret in the RunPod env unless you also wire the worker to read it.

### Scaling mode (also controllable from the app's Admin panel via `admin-runpod-endpoint`)

- **Cost beta:** `workersMin=0`, `workersMax=1`, idle timeout `60–300s`. First
  job pays cold start. Lowest cost, worst first-user latency.
- **Warm/fast (recommended for launch):** `workersMin=1`, `workersMax=1` (raise
  `workersMax` to 2–3 as volume grows). One worker stays up with models
  preloaded; first real job skips the model-load delay. Continuous GPU billing,
  but the experience is the product.
- The admin function clamps `workersMax` to ≤3 and `workersMin` to 0–1 — for
  higher scale, edit the endpoint directly in RunPod.

---

## 6. Phase 5 — Wire Supabase → RunPod

1. From the RunPod endpoint, copy the **endpoint ID**.
2. `supabase secrets set RUNPOD_ENDPOINT_ID=<endpoint_id>` (if not set in 2.5).
3. Confirm `RUNPOD_API_KEY` and `DEEPCLEAN_WEBHOOK_SECRET` are set (from 2.5).

`dispatch-deepclean-job` calls
`https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run` with the job payload and
stores the returned RunPod job id on the `deepclean_jobs` row.

---

## 7. Phase 6 — Frontend (Vercel)

Set Vercel env vars (these are public `VITE_` values; safe to expose):

```
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...anon...
VITE_STRIPE_TRIAL_LINK=...      # if using Stripe checkout links for credits
VITE_STRIPE_PRO_LINK=...
VITE_STRIPE_PRO_PLUS_LINK=...
```

Build + deploy. The Remarkee Max card shows "Connected" when Supabase env is
present; "Set Supabase env vars to enable Remarkee Max" otherwise.

---

## 8. Phase 7 — End-to-end verification

### 8.1 Warmup smoke test

In the RunPod endpoint **test console**:

```json
{ "input": { "action": "warmup", "profile": "standard" } }
```

Expect `"warmed": true`, `"engine": "remarkee-max-v2"`. If `false`, read
`warmup_error` — usually the API-format workflow is missing or a node pack
didn't load.

### 8.2 Real job through the app

1. Grant yourself credits:
   ```sql
   update public.creator_profiles
   set deepclean_credits = 10
   where user_id = 'YOUR_UUID';
   ```
2. Sign in, upload a known watermarked AI image (e.g. a Gemini / Nano Banana
   output), pick profile `standard`, output mode `stripped` (no seal, easiest to
   inspect), **Queue job**.
3. Poll `get-deepclean-job` (the app polls every 3.5s) until `completed`.
4. Inspect the report:
   ```sql
   select status, runtime_ms, gpu_type,
          report->'engine' as engine,
          report->'quality' as quality,
          report->'identify_before' as before,
          report->'identify_after' as after
   from public.deepclean_jobs order by created_at desc limit 1;
   ```
   - `identify_before` flags a hidden watermark; `identify_after` reads clean.
   - `quality.psnr` ≥ 18 (typically 25–40). Too low = over-denoised; too high =
     under-cleaned.
   - `report.engine.process_resolution` ≤ `output_resolution` (the cap is working).
5. Download the result; eyeball faces/text against the input — this is the real
   quality bar.

### 8.3 Per-profile + efficiency check

Run the **same 4K image** through each profile. A 4K job's runtime should be
**close to a 1536px job's runtime, not 4× slower** (the cap is applied). If 4K
takes 4× as long, the cap isn't applied — check `process_resolution` in the
report.

### 8.4 Failure-path test

Queue a job, then kill the RunPod worker mid-run (or feed an invalid input).
Confirm: the job ends `failed`, the credit is **refunded** (`credit_ledger`
`deepclean_release` row), and `deepclean_credits` is back where it started.

---

## 9. Production hardening checklist

### Security
- [ ] `deepclean-webhook` deployed with `--no-verify-jwt` and authenticates via
      `DEEPCLEAN_WEBHOOK_SECRET` (shared secret in body). Rotate the secret
      before GA and anytime someone leaves.
- [ ] Service role key is **only** in Supabase secrets + the RunPod worker env —
      never in a `VITE_` var, never committed.
- [ ] Storage buckets private; no public RLS policies. Users get only signed URLs.
- [ ] RLS on all three tables confirmed (users read only own rows; service role
      writes via edge functions).
- [ ] RunPod endpoint not exposed publicly (ComfyUI binds to `127.0.0.1` inside
      the container — already the case).

### Credits / money integrity
- [ ] Credit reserved at `create-deepclean-job`; captured only on webhook
      `completed`; released on `failed`. (Already implemented — verify with the
      failure-path test in 8.4.)
- [ ] `deepclean_credits` has a `>= 0` check constraint (can't go negative).
- [ ] `credit_ledger` is an immutable audit trail — every reserve/capture/release
      is a row. Monitor for `deepclean_release` spikes (worker failure rate).
- [ ] Decide the credit→price mapping and wire Stripe (the `VITE_STRIPE_*` links
      + a grant-credits function on checkout) before charging real money.

### Reliability & failure modes
- [ ] **Webhook delivery**: RunPod retries the webhook on non-2xx, but if Supabase
      edge functions are down at completion time, the job completes on the GPU but
      the DB never updates and the credit stays reserved. Add a **reconciliation
      sweep**: a scheduled function that finds `processing` jobs older than
      `timeout + 2min`, calls RunPod's status API, and closes them (capture or
      release). This is the single biggest production gap — implement before GA.
- [ ] **Idempotent webhook**: already handled — duplicate webhooks return
      `{duplicate: true}` without re-capturing.
- [ ] **Input validation**: `create-deepclean-job` caps at 25 MB and image MIME.
      Confirm the worker's `quality_check` rejects blank/over-drifted outputs
      (PSNR < 18) so bad results don't ship.
- [ ] **Timeouts**: RunPod endpoint timeout per profile (240/300/420s). The
      worker's `wait_for_prompt` uses the same — on timeout the job fails and the
      credit refunds.

### Cost control
- [ ] Start `workersMin=1, workersMax=1` (warm). Monitor idle GPU spend vs. job
      volume; switch to `workersMin=0` only if volume is low and you accept
      cold-start latency.
- [ ] The 4K→1536 cap is your main compute saver — verify it's applied (8.3).
- [ ] Network volume: one-time 10 GB model download, then persistent. No per-job
      download cost.

### Monitoring
- [ ] Watch `runtime_ms` and `gpu_type` per job (in the report). Set an alert if
      median runtime drifts up (model swap cost, VRAM pressure).
- [ ] Watch the `credit_ledger` `deepclean_release` rate = worker failure rate.
- [ ] Watch RunPod worker logs for `[deepclean] Startup preload failed` and
      `WARN: requirements install failed` (image rebuild needed).
- [ ] SynthID/watermark removal is never 100% — do not advertise guaranteed
      removal. Frame as "reduces / disrupts hidden AI watermarks."

### Compliance / framing
- [ ] The product is a **professional creator tool** for images you own or
      control. The UI copy already says this; keep it.
- [ ] Privacy policy covers: inputs deleted post-job, outputs TTL'd (2.6),
      credit ledger retained for audit.
- [ ] All `synthid`/`bypass` vocabulary is removed from the codebase (verified).
      Don't reintroduce it in copy.

---

## 10. Go-live sequence

1. **Canary (you only):** Phase 7 verification on your own account. Fix
   everything. Run 20–50 images across all 3 profiles + the failure path.
2. **Closed beta (invited users):** `workersMin=1, workersMax=1`. Grant beta
   users credits manually. Watch the reconciliation gap (9) — if you haven't
   built the sweep yet, manually reconcile stuck `processing` jobs a few times
   a day. Collect quality feedback on faces/text.
3. **Open beta:** wire Stripe credit purchase. Raise `workersMax` to 2–3.
   Build the reconciliation sweep (9). Add storage TTL (2.6).
4. **GA:** scale `workersMax` to demand, lower boot timeout to normal, rotate
   the webhook secret, publish the privacy policy.

---

## 11. Config reference (all env vars, both sides)

### Supabase edge-function secrets (`supabase secrets set ...`)
| Var | Used by | Purpose |
|---|---|---|
| `SUPABASE_URL` | all functions + worker | project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | all functions + worker | service-role writes (secret) |
| `RUNPOD_API_KEY` | `dispatch-deepclean-job`, `admin-runpod-endpoint` | Supabase→RunPod API auth |
| `RUNPOD_ENDPOINT_ID` | `dispatch-deepclean-job`, `admin-runpod-endpoint` | the serverless endpoint |
| `DEEPCLEAN_WEBHOOK_SECRET` | `dispatch-deepclean-job` (forwards to worker) | shared secret for the worker→Supabase webhook |

### RunPod worker env (endpoint env panel)
| Var | Default | Purpose |
|---|---|---|
| `SUPABASE_URL` | — | project URL (same as Supabase) |
| `SUPABASE_SERVICE_ROLE_KEY` | — | upload outputs, delete inputs |
| `DEEPCLEAN_OUTPUT_BUCKET` | `deepclean-outputs` | output bucket name |
| `DEEPCLEAN_PRELOAD` | `1` | warm models at boot |
| `DEEPCLEAN_PRELOAD_PROFILE` | `standard` | which profile to warm |
| `DEEPCLEAN_SEED` | `0` | deterministic output (optional) |
| `COMFYUI_BASE` | `/runpod-volume/ComfyUI` | ComfyUI model/input root |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | the localhost ComfyUI service |
| `DEEPCLEAN_WORKFLOW` | `/app/workflows/remarkee-max-v2.api.json` | API-format template path |
| `HF_TOKEN` | — | optional, public models |

### Vercel frontend env (public `VITE_`)
| Var | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | anon key (public) |
| `VITE_STRIPE_TRIAL_LINK` / `VITE_STRIPE_PRO_LINK` / `VITE_STRIPE_PRO_PLUS_LINK` | Stripe checkout links |

---

## 12. Runbook — common ops

| Situation | Action |
|---|---|
| **Update a model** (e.g. newer Qwen GGUF) | Put the new file in `/runpod-volume/ComfyUI/models/<dir>/` (run `bootstrap_models.py` with the new URL, or manual upload). Bump the filename in the workflow if it changed, re-export the API format, rebuild the image, redeploy. |
| **Update the workflow** | Edit in ComfyUI UI → Save (API Format) → commit `remarkee-max-v2.api.json` → rebuild image → redeploy (or mount the volume and hot-replace, but rebuild is safer). |
| **Scale up** | Raise `workersMax` in RunPod (or via the app Admin panel, clamped to 3). Keep `workersMin=1` for warm launches. |
| **Stuck `processing` jobs** | If you haven't built the reconciliation sweep (9), run: `select id, created_at from deepclean_jobs where status='processing' and created_at < now() - interval '10 minutes';` then check RunPod job status and manually close (capture/release). |
| **Worker won't start** | Check RunPod logs for `FATAL: ComfyUI did not become ready` (a node pack failed to load) or `[bootstrap]` download failures (HF down — retry). |
| **Every job fails with "workflow template missing"** | The API-format export (`remarkee-max-v2.api.json`) isn't in the image. Do Phase 4.1, rebuild. |
| **Jobs succeed but watermark still detected** | Raise the profile (`strong`/`max`) — higher denoise ceiling. The `max` profile processes at 1800 and runs the face path. |
| **Rotate webhook secret** | `supabase secrets set DEEPCLEAN_WEBHOOK_SECRET=<new>` → no redeploy needed (functions read env at call time); the worker gets it via the dispatch payload, so it picks up immediately too. |

---

## TL;DR rollout order

Supabase (migrate → deploy 6 functions → set 5 secrets) → build+push worker
image → one-time workflow API export + seed model volume → RunPod endpoint
(24GB GPU, volume, env, warm scaling) → wire `RUNPOD_ENDPOINT_ID` → Vercel env →
warmup smoke test → real job → failure-path test → closed beta → build the
reconciliation sweep + storage TTL → open beta → GA.
