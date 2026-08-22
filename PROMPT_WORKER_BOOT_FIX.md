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
6. The GHCR package `ghcr.io/anthonyx33/resmarke-deepclean` is **PUBLIC** —
   verified Aug 22 by anonymous manifest pull (HTTP 200). No registry
   credentials needed. The private-image hypothesis is DEAD.

## Root cause — CONFIRMED via live GraphQL (Aug 22 2026)

Query `myself { endpoints { id name gpuIds gpuCount workersMax workersMin idleTimeout networkVolumeId } }`
returns for `remint-v6` (`2c9528ebg2vzvx`):

- `gpuIds = "AMPERE_24,-NVIDIA L4,-NVIDIA RTX A5000,-NVIDIA RTX PRO 6000
  Blackwell Server Edition MIG 1g.24gb"` — the ENTIRE 24 GB serverless
  tier was excluded except RTX 3090. 3090 serverless capacity is scarce,
  so the scheduler finds no hardware: no container, no logs, jobs stay
  IN_QUEUE, UI reads "Initializing" forever. This is the primary cause.
- `workersMin = 1` — RunPod continuously tries to keep one worker alive,
  which is why the endpoint spins on Initializing even with no jobs.
- `networkVolumeId = null` — the new endpoint has NO network volume.
  The worker REQUIRES `/runpod-volume` (`bootstrap_models.py` seeds ~10 GB
  of model weights + ComfyUI base there; the Dockerfile hardcodes
  `HF_HOME=/runpod-volume/hf`, `COMFYUI_BASE=/runpod-volume/ComfyUI`).
  Even after the GPU fix, the first real job would re-download models to
  ephemeral disk on every worker boot. This is the SECOND blocker.
- The network volume `m0zdf6o3ot` (`healthy_scarlet_squid`, EU-SE-1,
  50 GB) is still attached to the OLD endpoint `al6fd30432kkov`
  (`resmarke-deepclean-prodx`). It holds the model cache. Do NOT delete it.

### Verified false hypotheses

- Private image pull — FALSE: package is public, anonymous pull is 200.
- "Container image validation" toggle — removed from the new RunPod
  console; not a factor.
- `throttled` workers non-zero — FALSE: `/health` reports `throttled: 0`
  (all six worker counters are zero).

### The fix (owner, dashboard)

1. Endpoint `remint-v6` → Edit → GPU selection → re-enable NVIDIA L4,
   NVIDIA RTX A5000, and RTX PRO 6000 Blackwell MIG (keep RTX 3090) → Save.
2. Attach network volume `m0zdf6o3ot` at `/runpod-volume`. If RunPod
   complains it is in use, detach it from the old endpoint first.
3. Keep 24 GB tier, GPU count 1, workersMin 1 (warm worker = no
   cold-start latency; costs the idle rate).
4. Re-submit a smoke job and expect: worker boots → handler runs → job
   FAILS on the bad input (that proves the chain) → then run one real
   end-to-end job.

## What you must do

1. **Apply the two confirmed fixes (owner, dashboard)**: re-enable the
   excluded 24 GB GPUs and attach network volume `m0zdf6o3ot` at
   `/runpod-volume` (see Root cause section). Then verify via GraphQL:
   `myself { endpoints { id name gpuIds workersMin networkVolumeId } }`
   must show no exclusions in `gpuIds` and `networkVolumeId = m0zdf6o3ot`.
2. **Prove boot**: submit a smoke job and poll `/v2/2c9528ebg2vzvx/status/<job-id>`
   every 20s. Success = worker counters in `/health` move (initializing →
   running) and the job leaves IN_QUEUE. The job may end FAILED on bad
   input — that is EXPECTED and proves the handler ran.
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
