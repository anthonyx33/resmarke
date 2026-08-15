# DS ReMint V6 — Make-It-Work & Optimization Strategy (v1, 2026-08-15)

## 0. State of truth

- DS ReMint V6 has **never completed a production job**. The blocker was the
  engine (ComfyUI never booted on the torch 2.5.1 image). The candidate image
  fixes that; it awaits green CI + the release-gate ladder.
- V6 anatomy (from `ds_remint_v6.py`):
  1. **GPU pre-regeneration** — ComfyUI purification pass
     (`max_optimised_remint._run_purification`, `regen_level=8`,
     `process_cap=1536`, `timeout=300s`). The ONLY step proven to remove
     SynthID in live tests.
  2. **Fully local classical chain** — color restore (histogram) → adaptive
     rung ladder (shift+downscale, detector-gated, max 5 rungs) →
     reconstruction (never upscale, delivery ≤ min(src, 1440)) → final
     spectral reshape → tone lock → lens character → masked sensor texture →
     **one** JPEG encode (q94, 4:2:2) + iPhone EXIF → final-byte QC.
- Adaptive mode requires a **normalized detector proxy** (`CX_DETECTOR_URL`).
  Without it, adaptive silently degrades to a single template run ("never
  blind"). With it, `_detector_pass` treats any detector error as a FAIL and
  keeps escalating rungs — **fixed** (see §4 C3, applied pre-Phase A).
- **Detector verdicts are recorded but never enforced.** `detector_gate` /
  `detector_ok` exist only inside `ds_remint_v6.py` and `max_cx_remint.py`; no
  worker or Supabase code branches on them. The only thing that can fail a job
  is `quality_check` (PSNR ≥ 18 / blank check). De facto policy today:
  **ship regardless of detector verdict.** Owner decision 1 (§7) is about
  making this explicit, not hypothetical.
- Hard worker gates (`worker.py`): `quality_check` requires PSNR ≥ 18,
  variance ≥ 12, ≥ 256 px. RunPod timeout ceiling: **420 s**.
- Worst-case v6 wall time: regen ≤ 300 s + up to 5 detector probes (45 s
  timeout each) + classical chain. **Can exceed 420 s** — the #1 operational
  risk until measured.
**BLOCKING for Phase A.** Confirm `CX_DETECTOR_URL` normalized proxy is deployed, reachable from RunPod, and env is set on the endpoint — this determines which pipeline Phase A exercises (adaptive detector-gated vs silent single-template)
## 1. Prerequisites (before the first v6 job)

| ID | Item | Owner |
|---|---|---|
| P1 | Engine candidate passes all CI gates; digest captured; deployed by digest | Owners |
| P2 | Confirm `CX_DETECTOR_URL` normalized proxy is deployed, reachable from RunPod, and env is set on the endpoint. Decide the fail-safe policy when the detector is missing/broken: ship template run with a report flag, or fail the job | Owners |
| P3 | Traffic pause + `reconcile-deepclean-jobs` dry-run → release stuck rows | Owners |
| P4 | Build a 10–20 image benchmark corpus (portraits, landscapes, product, text, screenshots) with detector before/after scores and QC metrics | Owners + agent |

## 2. Phase A — First light (correctness ONLY, no tuning)

0. **Detector infra-error fix is already applied** (§4 C3): tri-state
   `_detector_pass` — output-neutral on a healthy detector, prevents wasted
   rung probes from corrupting the first-light baseline.
1. One controlled v6 job. Pass requires: RunPod `COMPLETED`, `output.ok == true`,
   JPEG in storage, webhook sets DB `completed`, URL loads, one credit.
2. Record from the report JSON: `layers`, `attempts` (rungs tried, detector
   results), `final_qc` (psnr, ssim, sharpness_ratio, halo, blockiness),
   `runtime_ms`, and the before/after watermark inventory.
3. If runtime approaches the RunPod cap: add a worker-side **self-timeout**
   that webhooks a failure BEFORE RunPod kills the container (prevents stuck
   `processing` rows). Small worker.py change, owner-approved.
4. **No v6 algorithm changes in this phase.** Baseline is king.

## 3. Phase B — Measurement & lab harness

1. Build `tools/ds_remint_v6_harness.py` mirroring the other lab harnesses:
   - `--pre-regen-none` → classical chain only (`pre_regen=False`);
   - `--regen-input <png>` → feed a pre-regenned PNG (from the worker or a
     RunPod pod) and run the rest locally;
   - `--detector` via `CX_DETECTOR_URL`; prints the full report JSON.
   This makes the entire classical chain iterable on a Mac, no GPU.
2. Corpus eval script: harness over the corpus → table of
   `rung | detector_ok | ssim | psnr | sharpness | halo | blockiness | P(ai)`.
3. KPIs: detector clear rate @ threshold; PSNR ≥ 18 (hard); SSIM; human QC
   rubric (detail, color fidelity, halos, grain, "AI look"); p50/p95 runtime;
   GPU-seconds and credits per job.

## 4. Phase C — Optimization levers (ranked by expected ROI)

**C1 — Latency**
- Detector probe timeout 45 → 15 s.
- Probe only when it matters: rungs escalate destruction, so if rung 0 fails
  the SSIM floor, later rungs cannot pass the floor — break early instead of
  probing all 5.
- Experiment `regen_level` 8 → 6/7 and `process_cap` 1536 → 1280; re-verify
  SynthID removal via the watermark inventory each time.
- Confirm the purification pass reuses the warmup-resident models (same
  workflow path as the boot warmup).

**C2 — Quality (via harness sweeps, not prod)**
- Sweep `spectral_strength` {0.2, 0.3, 0.4}, `spectral_alpha` {1.5, 2.0, 2.5},
  `spectral_noise_floor`, `sharpen_percent` {16, 24, 32},
  `texture_amount` {0.7, 0.9, 1.1}, `dehalo_strength`, `ai_threshold`
  {0.4, 0.5, 0.6}.
- Tune rung 0 (min(fix applied pre-Phase A; remaining items below)**
- APPLIED: `_detector_pass` is now tri-state (`True` / `False` / `None`).
  Detector infra errors and missing `ai_probability` return `None`; the rung
  loop breaks immediately and ships the best candidate with note
  `detector_unavailable_shipped_best_effort`. Output-neutral on a healthy
  detector; prevents wasted probes (up to 5 × 45 s) from burning the RunPod
  budget. (Previous code escalated on infra errors but shipped rung 0 anyway
  via the SSIM tiebreak in `_keep_better` — the fix recovers the latency, not
  the pixels.)
- FOLLOW-UP: `max_cx_remint.py` has the identical
  `_safe_detect`/`_detector_pass` pattern — apply the same tri-state fix after
  the CX baseline is captured. Do NOT touch CX before the engine rollout.
- Verify the detector probe encode (q92, 4:2:0) matches the final bytes the
  grader will see; otherwise the gate measures the wrong file.
- Decide whether `detector_gate.cleared == false` should eventually FAIL the
  job, or stay flag-only (see §7 owner decision 1)dict; on error,
  ship rung 0 with a `detector_unavailable` note, never blind-escalate.
- Verify the detector probe encode (q92, 4:2:0) matches the final bytes the
  grader will see; otherwise the gate measures the wrong file.

**C4 — Cost**
- Confirm exactly one credit captured per success; measure GPU-seconds per job
  at the chosen regen level; re-evaluate pricing only with real data.

## 5. Phase D — Canary rollout + kill switch

1. **Dispatch-level profile gate** (Supabase `dispatch-deepclean-job`): read an
   admin setting `ds_remint_v6_rollout ∈ {off, all, percent-N}`.
   - `off` → v6 requests are remapped to `max-cx-remint` (proven path).
   - This is the kill switch AND the canary; no UI changes needed.
2. Canary 5 % → monitor clear rate, QC fail rate, timeouts, credit burn,
   refunds → 25 % → 100 %.
3. **Detector verdict policy:** today the job ships regardless of detector
   verdict (only `quality_check` can fail it — verified in code). Decide
   whether `cleared == false` should fail the job, stay ship-with-flag, or be
   gated by policy.
2. Detector fail-safe policy when the proxy is down (P2).
3. Human QC rubric sign-off for the corpus (B3).
4
## 6. What we do NOT do

- No v6 algorithm edits before Phase A baseline is captured.
- No RunPod timeout change without the Phase A timing trace.
- No consultant edits v6 code without a harness-run before/after table
  attached to the proposal.

## 7. Owner decisions needed

1. Detector fail-safe policy (P2).
2. Human QC rubric sign-off for the corpus (B3).
3. Canary percentages and acceptance thresholds (D2).
