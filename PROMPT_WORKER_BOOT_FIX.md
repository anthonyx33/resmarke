# Agent Worker Brief — Unblock RunPod Worker Boot & Restore End-to-End Processing

## Mission

The production image pipeline is DOWN. Bring it back online, diagnose and fix
the worker-boot stall, and prove the full chain works with a real image.

You have full access to:
- The workspace at `/Users/a/Documents/NOSYNF`
- A RunPod API key provided by the owner (export as `RUNPOD_API_KEY` — the
  owner accepts it living in the environment; never commit or log it)
- The Supabase CLI (linked to project ref `otzjqcnrabfbonjywlye`, name
  `resmarke-prod`, status ACTIVE_HEALTHY)
- The `gh` CLI (GitHub user `anthonyx33`)

## Current state (verified facts, Aug 22 2026)

1. The previous RunPod serverless endpoint ID (`5017f4bb...`) stopped
   resolving: `/run` returned `404 {"detail":"endpoint not found"}`.
   Root cause confirmed as a stale/rotated RunPod API key in Supabase —
   RunPod returns 404 for unknown-key endpoints.
2. The owner created a NEW endpoint:
   - **Endpoint ID:** `2c9528ebg2vzvx`
   - Name: `remint-v6`
   - Docker image: `ghcr.io/anthonyx33/resmarke-deepclean:4c7235cefa5495232d9e924c3b83998760420edd`
   - Digest: `sha256:34d6eb5dc6d630169c7ace31a13985461d995d2ac17eb7c2a39519c78603f459`
   - GPU: `AMPERE_24` (24 GB class)
3. Supabase secrets are now correct:
   - `RUNPOD_ENDPOINT_ID=2c9528ebg2vzvx` (set by the assistant)
   - `RUNPOD_API_KEY` (set by the owner to their current key)
4. With the current key:
   - `/health` → HTTP 200, shows `"inQueue":1` and **ALL worker counters 0**
     (initializing 0, ready 0, running 0, unhealthy 0, idle 0)
   - Fresh smoke job accepted: id `45ab1e9b-88c6-487c-931d-1410d884abed-u2`,
     status `IN_QUEUE`
5. The RunPod dashboard shows the endpoint stuck at "Initializing" for
   15+ minutes, with NO logs and NO workers ever appearing, even though
   jobs are queued. (With Active Workers = 0, workers only boot on demand —
   but a queued job SHOULD trigger a boot. It is not triggering.)
6. The GHCR package `ghcr.io/anthonyx33/resmarke-deepclean` is **PRIVATE**.
   It is UNKNOWN whether the owner entered GitHub registry credentials on
   the endpoint. RunPod's GraphQL introspection is disabled, so config
   fields cannot be enumerated from here.

## Leading hypotheses (ranked)

1. **Private image without registry credentials.** The template cannot pull
   the image and sits in a failed/retry state forever; queued jobs never
   boot a worker. This is the most common cause of "Initializing forever,
   zero workers".
2. **Template stuck from a previous failed validation.** "Container image
   validation" was possibly left ON; the worker's `start.sh` boots ComfyUI
   (up to 120s), which can stall the validator.
3. **No matching GPU capacity / wrong data center** — jobs would show
   throttled or eventually error, not silent zero-workers.
4. **Missing worker environment variables** — does NOT block boot (only the
   first real job), listed here for completeness:
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs`, `DEEPCLEAN_PRELOAD=1`,
   `DEEPCLEAN_PRELOAD_PROFILE=standard`, `DEEPCLEAN_SEED=0`, `HF_TOKEN`
   (optional).

## What you must do

1. **Confirm/deny hypothesis 1** — the highest-value action: have the owner
   either (a) flip the GHCR package to Public (GitHub → Profile → Packages →
   `resmarke-deepclean` → Package settings → Change visibility → Public),
   or (b) attach registry credentials in the endpoint form
   (username `anthonyx33`, password = a GitHub PAT with `read:packages`).
   Then recreate the endpoint (or trigger a new release) with
   "Container image validation" OFF and the same image tag.
2. **Prove boot**: with `RUNPOD_API_KEY` exported, submit a smoke job
   (`input_url` pointing at a real reachable URL or `https://example.invalid/...`
   is fine for boot-only) and poll `/v2/2c9528ebg2vzvx/status/<job-id>`
   every 20s. Success = a worker appears in `/health` counters
   (initializing → running) and the job status moves past IN_QUEUE.
   The job may end FAILED due to the fake input — that is EXPECTED and
   proves the handler ran.
3. **Verify the Supabase side still matches**:
   `supabase secrets list --project-ref otzjqcnrabfbonjywlye` and confirm
   `RUNPOD_ENDPOINT_ID` + `RUNPOD_API_KEY`.
4. **Run ONE real end-to-end job** through the app (`/cmint`, Full Quality
   Remint) and confirm: dispatch reaches RunPod, worker boots, output
   uploads, webhook updates the job to completed, report contains
   `engine_version` and `delivery_check`.
5. **Document the exact fix** in a short postmortem appended to
   `deepclean-worker/README.md` (registry creds or public package, template
   recreation steps) so this cannot recur silently.

## Acceptance criteria

- `/health` shows a worker transitioning to `running` for a submitted job.
- A real image completes end-to-end with a report.
- The fix is documented; no secrets committed; no worker code changes
  unless a boot failure is PROVEN with logs from the dashboard.

## Explicitly out of scope

- Changing pipeline/finisher code.
- Detector/grader work.
- Any product/UI changes.
