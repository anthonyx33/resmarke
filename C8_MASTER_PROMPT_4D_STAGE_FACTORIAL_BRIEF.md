# C8 MASTER PROMPT — 4D STAGE-KNOCKOUT FACTORIAL BUILD BRIEF (v1)

**Status:** DRAFT for owner freeze. This brief does NOT modify or continue the frozen v2.1 commission — see §0.
**Author:** non-C88 audit copy (Consultant D), 2026-08-28, implementing the unanimously converged plan.
**Builder:** to be issued to C88 after owner freeze. **Verifier:** Consultant D (line-by-line).
**Sandbox for build:** local harness only. No live cells, no vendor calls, no deploy, no Supabase/RunPod action. Vendor leg runs only after §6–§7 conditions and owner GO.

---

## 0. Governance (read first)

1. The frozen v2.1 replay commission (`C8_MASTER_PROMPT_4D_1B_REPLAY_BUILD_BRIEF_V21.md`) remains **hard-stopped** by its own fidelity requirement (O4 0/12, O5 0/12 byte-exact on macOS [MF]). Its artifacts and evidence pins stay frozen and untouched.
2. Owner decision (choose one, before this build starts):
   - **Option 1:** reproduce the archived Linux runtime (deployed digest pod) and finish v2.1 unchanged; or
   - **Option 2 (recommended, C88 agrees):** close v2.1 as failed and commission this new same-machine factorial.
3. Under Option 2, the 4D-1b H1-preservation arm in this factorial is a **new arm**, not a continuation of v2.1. Its Gate D arithmetic is corrected (§5): floor 0.420 is an **energy-ratio** gate [CF]; 0.454/0.434 are planning estimates only [ME].
4. The factual record for the master engineer (agreed by all parties): 0.362 is an H1 **energy** ratio; 0.420 is an energy-ratio floor; the replay metric matches it; there is **no dimensional defect**; 0.1359 was a squaring error; ≈0.46 is retired; eligible lost-energy mass is unmeasured.

## 1. Mission

Produce, in **one pinned local environment**, delivery-matched final files for every stage-knockout arm across the 12 archived sentinel B cells, measure a frozen quality/metric battery on each arm, run a calibrated blinded panel, freeze the best visually natural survivor, and leave the 12-call Hive leg (§7) as the only vendor spend — fired only at the frozen winner.

## 2. Inputs (literal pins, unchanged)

Reuse the v2.1 pins exactly (`round-4d-1a/expected-manifest.json` `6d1c730c…`, `cell-settings.json` `17691de3…`, `or-band-split.json` `483c9d8d…`, `round-4d-cam-1/roi-manifest.json` `5b0d7377…`, evaluators `cf4c81bc…` / `3175409e…` / `335d8967…`, `quality_finish.py` `538c9edb…`, `ds_remint_v8_8.py` `9e57e06e…`, `worker.py` `93f46bbe…`). New pins added at freeze time: the harness file(s) and the edge-support artifact hash.

## 3. Environment & determinism contract

- One machine, one pinned venv (record Python / numpy / Pillow versions in the artifact index).
- Every arm is run **twice**; any two runs of the same arm on the same machine must produce identical delivered-file SHA-256. Non-determinism = arm fails closed.
- The archived bytes are **reference, not control**. The control is the locally replayed incumbent (arm B).
- No GPU, no wash, no live cells: all arms derive from archived `OR_postresample.png` / `O2_precamera.png` / `O0_source.png`.

## 4. Arms (delivery-matched)

All arms share: delivery lattice (per-cell archived size), tone-lock policy (`_histogram_match` to O0, strength 0.8 from the cell's executed block), final encode q97 4:4:4 single, stripped finalize pass-through, metadata policy identical (no EXIF difference), seed/lab context from the cell. [CF] parameterization verified against the existing harness:

| Arm | Input to downstream | Tone-lock | Stage-1 q92 4:2:0 | Quality Finish | Final q97 4:4:4 | Harness basis |
|---|---|---|---|---|---|---|
| **B** local incumbent control | O2_precamera | yes | yes | yes (strong, S1.25) | yes | `replay_downstream(O2)` — exists (fidelity path) |
| **C0** camera-off | OR_postresample | yes | yes | yes | yes | `replay_downstream(OR)` — zero new code |
| **C1** JPEG-bypass (RGB handoff) | O2_precamera | yes | **no** | yes, on RGB via `apply_quality_finish(image=ndarray, reference=O0)` | yes | new variant function |
| **C2** camera-off + JPEG-bypass | OR_postresample | yes | **no** | yes, on RGB | yes | new variant function |
| **T** 4D-1b H1 preservation | `build_candidate(OR, O2)` output | yes | yes | yes | yes | `build_candidate` (exists) → `replay_downstream` |
| **Q−** QF-off companion (diagnostic) | O2_precamera | yes | yes | **no** (decode O3 → direct q97 re-encode) | yes | new variant function |

Companion rule: Q− and any future companion are measured for attribution; they are vendor-leg eligible only if they win the panel (§6) and meet the shared final-byte policy.

## 5. Frozen metrics (unit labels mandatory)

Per arm per cell, all computed before any panel or vendor score:

- **Band energy ratios** vs `_resampled_source`: H0 / H1 / H2 = `mean(b²)/mean(r²)` — **labeled ENERGY**. H1 RMS ratio = `√(E_out)/√(E_ref)` — **labeled RMS, reported separately**. (The 0.420 gate applies to the H1 **energy** ratio only.)
- **EATR** (p95 edge-mag ratio, `_eatr_h1` convention) and per-ROI **HFTR** (RMS, labeled).
- **ESF edge geometry** via pinned `edge_spread_audit.py` on the pinned edge-support artifact (incumbent B only, pre-candidate): raw 10–90, monotonic (PAVA) width, overshoot, second-peak crossings, protected-ROI subsets.
- **Noise/regional grain**: per-ROI luma/chroma RMS, residual rho1/rho2 (existing `_roi_metrics`), MAD noise floor.
- **Identity/semantic**: reference MS-SSIM (2-scale) + TDR (`quality_finish` `_reference_metrics`), PSNR vs source; protected-ROI EATR ratio ≥ 0.98 per cell (Gate F convention).
- **Panel** (M2): calibrate raters on 2–3 pinned anchor pairs first; accept panel scores only if inter-rater agreement meets the frozen floor (e.g., ≥0.70 pairwise agreement or Krippendorff's α ≥ 0.6 — exact floor frozen at this brief's acceptance); arms anonymized, order counterbalanced, scale −2…+2, scored at intended display size and at zoom.

## 6. Freeze-before-inspection

1. All arm outputs, metrics, and the artifact index are hash-pinned **before** the panel sees images and **before** any vendor call.
2. The panel selects the **winner** (best visually natural among arms that meet the structural floors: no terminal identity/privacy regression, no QF fail-close).
3. The winner's delivered bytes (SHA-256) + settings code are frozen. **No pixel changes after freezing.**
4. If no arm looks naturally photographic (§8 last row) → **no vendor calls**.

## 7. Vendor leg (only after §6)

Reuse `VENDOR_FREEZE_4D_1A.md` v3 constants unchanged: eligibility ai ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10; paired non-amplification (median ≤ 0.00, no individual > +0.02); median adverse movement ≤ +0.05; fresh-call provenance contract; model/version validation; 12 logical grades = 6 sentinels × {incumbent delivered, winner delivered}; reserve 28; stop on first confirmed absolute failure or component amplification.

## 8. Decision matrix (frozen)

- Camera-off wins quality **and** remains eligible → **remove O2** from the tuple.
- 4D-1b (T) wins quality and remains eligible → keep provisionally while still simplifying O2.
- Camera-off fails detection but incumbent passes → **decompose O2** to the minimum detector-useful component (component ablation follows as a second freeze).
- Both fail → **pivot to O1 wash policy, candidate diversity, routing**.
- No arm looks natural in the panel → no vendor spend; re-baseline quality first.
- No arm clears detection → **abstain**; never ship least-bad.

## 9. Stop conditions, budget, performance

- Stop: any arm non-deterministic (§3); any input pin mismatch; panel uncalibrated; winner ineligible on any component; arm count or metric definition drifted from this brief.
- Budget: 0 live cells, 0 vendor calls until §6–§7; credits 0. CPU-only run: ~12 cells × 6 arms × (tone-lock + 1–2 encodes + QF ≈ 0.3–0.7 s at ≤1250 px) → minutes per cell, well under one hour total on one machine [ME].

## 10. Deliverables

1. Harness: new file(s) under `deepclean-worker/tools/` (variant functions only; **zero modification of frozen files**).
2. Artifacts under `round-4d-factorial/` (hash-indexed): per-arm per-cell delivered files + metrics JSON, panel protocol record, winner freeze record.
3. Report `C8_4D_FACTORIAL_REPORT.md` with per-arm metric tables (energy and RMS separately labeled), panel results, decision-matrix disposition, signed declaration.
4. Verifier (Consultant D) line-by-line: arm parameterization vs this brief, determinism double-run, pin checks, metric unit labels, freeze ordering.

**Signed:** Consultant D (non-C88 copy) · 2026-08-28 · **Owner freeze required before issue to builder.**
