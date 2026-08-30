# C8 MASTER PROMPT — 4D-1b REPLAY BUILD BRIEF v2 (CORRECTED, PURE REPLAY)

Role: builder (code access). Deliverable: replay-only harness + candidate
module + signed report. **No commit, no push, no deploy, no RunPod/Supabase
action, no grading, no live cell, no vendor call.**
Supersedes v1 (`C8_MASTER_PROMPT_4D_1B_REPLAY_BUILD_BRIEF.md`); this document
wins on every conflict. v2 incorporates the expert audit's eight redlines:
corrected stage order, executed-settings input, fully specified synthesis,
per-pixel eligibility (honest invariants), reconciled Gate B/D arithmetic,
pinned evidence, strictly binary fidelity, and a hash-verifiable artifact
directory.

## 1. Mission (unchanged)

Prove on the 12 archived incumbent B cells — BEFORE anything is deployed —
that the OR→O2 H1-only loss-constrained preservation candidate (a) activates,
(b) reproduces incumbent downstream behavior (fidelity), and (c) clears the
product-effect gates. Any gate failure stops at replay. Nothing proceeds to
freeze.

## 2. Inputs (pinned, hash-verifiable)

| input | path | pin |
|---|---|---|
| 12 archived B cell dirs | `round-4d-1a/checkpoints/<job_id>/` (O0..O5 + OR) | OR/O2 pixel hashes in `round-4d-1a/expected-manifest.json` (24-cell table, ledger-verified) |
| per-cell settings | `round-4d-1a/cell-settings.json` | schema below; **executed block is a required input** |
| ROI manifest | `round-4d-cam-1/roi-manifest.json` | SHA-256 `5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329` |
| band split evidence | `round-4d-1a/or-band-split.json` | generator `deepclean-worker/tools/round_4d_1a_or_split.py` (frozen recipe) |
| metric evaluators | `round_4d_cam_1_gates.transition_loss` (combined, frozen recipe) · `edge_spread_audit` ESF functions | pinned by file SHA-256 at build start, recorded in the report |
| R2 recipe | PIL LANCZOS, RGB uint8 → float64/255, O0 → target dims | same as 4D-1a FINAL brief |

`cell-settings.json` schema per job id:
`remint` (engine_mode, wash_model, strength, deep_degrade_scale, min_ssim,
color_restore, color_restore_strength, jpeg_quality, jpeg_subsampling),
`finish` (preset, scale, overrides, material_clean, finish_mode),
**`executed`** — `finish_preset_selected`, `finish_qc_passed`,
`effective_seed`, `final_jpeg_quality`, `final_jpeg_subsampling`,
`naturalization_profile`. The `executed` block is extracted by the master
engineer from the archived DB reports and MUST be present before the harness
runs; the harness verifies it against the archived reports' executed values
and stops on mismatch. (The master engineer will deliver this block before
the build starts — it is not derivable from the frozen preset because the
incumbent finish is adaptive.)

## 3. Candidate spec (frozen)

### 3.1 Data boundary (unchanged, strict)

Synthesis references ONLY `OR_postresample` H1 and `O2_precamera` H1. O0, any
resampled O0, source alignment, and source coefficients do NOT enter the
candidate. (Downstream replay legitimately reproduces incumbent behavior,
including O0-based tone-lock — that is incumbent code, not candidate input.)

### 3.2 Band (unchanged)

H1 only: `gauss(0.7) − gauss(1.4)` on luma (0.2126/0.7152/0.0722), frozen
uint8-quantized `_gauss`. H0, H2, chroma untouched.

### 3.3 Per-pixel eligibility (honest invariants — v2 replaces v1 §3.3)

For each pixel x, the dose applies ONLY where ALL of:

1. local window passes: signed OR/O2 H1 correlation ≥ 0.90 AND axial
   structure-tensor orientation difference ≤ 10° AND usable local H1 SNR ≥ 4;
2. **same sign**: `sign(OR_H1(x)) == sign(O2_H1(x))`;
3. **magnitude order**: `|OR_H1(x)| ≥ |O2_H1(x)|` (OR farther from zero);
4. outside flat/near-flat (`_edge_mag` of OR luma < p30) and outside
   saturated neighborhoods (any channel ≥ 250 or ≤ 5);
5. outside the strong-edge exclusion = UNION of independently detected OR and
   O2 edges (`np.gradient` magnitude, p92), Euclidean dilation 2 px;
6. support is BINARY and re-derived from the original (unsmoothed) eligibility
   mask — no continuous confidence field, no smoothing, so weight cannot leak
   outside support by construction.

Under 2+3, `candidate_H1(x) = O2_H1(x) + d·(OR_H1(x) − O2_H1(x))` with
`d = 0.25` satisfies, per eligible coefficient: same polarity, no attenuation,
and `|O2_H1(x)| ≤ |candidate_H1(x)| ≤ |OR_H1(x)|`. These are now TRUE by
construction on eligible pixels (the v1 blanket claims are withdrawn).

### 3.4 Synthesis, windows, caps, quantization (fully specified)

- Candidate H1 field: `O2_H1 + d·(OR_H1 − O2_H1)` on the eligible mask, `O2_H1`
  elsewhere.
- Luma delta `Δ = candidate_H1 − O2_H1`; `Δ_safe = clip(Δ, −min(R,G,B),
  1 − max(R,G,B))`; `out_RGB = clip(RGB + Δ_safe, 0, 1)`; single uint8 round.
  Channel differences are preserved exactly by `Δ_safe`; the capped-pixel
  fraction is reported.
- Windows: energy windows 15×15, stride 3, bilinear-upsampled; NCC and
  structure tensor use the same 15×15 window; structure tensor computed on
  the H1 band.
- Post-synthesis invariant (fail-closed): for EVERY valid 15×15 grid window,
  `E_O2 ≤ E_cand ≤ E_OR` within 1e-9 relative (float64). Single deterministic
  vectorized rescale toward O2 where `E_cand > E_OR`; if any violation remains
  after the rescale, the cell fails closed (candidate = O2 for that cell).
- Determinism: float64 throughout, frozen `_gauss`, no RNG, reflect borders,
  fixed-format serialization, no timestamps. Same-machine reruns byte-identical.

## 4. Downstream replay (CORRECTED ORDER — v2 replaces v1 §4)

The incumbent path is:

`O2 → tone-lock → stage-1 q92/4:2:0 encode → decode (O3) → Quality Finish on
the delivered stage-1 JPEG → O4 → finalize (photo naturalization + final
q97/4:4:4 encode) → O5`

The harness implements exactly this order using the real worker modules
(`_histogram_match`, `apply_quality_finish`, `iphone_exif`/encode helpers,
`photo_naturalization`), the cell's `finish` settings, and the `executed`
choices (selected finish preset, final codec, naturalization profile).

**Fidelity is strictly binary**: replaying the UNCHANGED incumbent O2 must
reproduce the archived O3/O4/O5 decoded-pixel hashes BYTE-EXACT for all 12
cells. Any non-exact cell stops the commission with a delta distribution
report — the builder may NOT choose or propose a tolerance. Non-exact fidelity
is classified as "replay not proven"; the master engineer alone decides
whether to authorize further work under an explicitly frozen tolerance.
(4D-CAM-1 precedent: O2 PNG hashes were byte-exact on 10/17 cells and ≤4 LSB
elsewhere; the decision applies to THIS harness only.)

## 5. Replay gates (reconciled arithmetic)

Measured anchors (frozen): camera-ladder-only H1 retention **0.456815**
(loss **0.543185**); resample retention 1.000000 under the geometry-normalized
comparison (qualified: earlier native-resolution attribution found a real,
secondary resample cost); incumbent B O2→O5 loss means **0.098217** overall /
**0.106025** hard subset; downstream H1 survival **0.748**.

Dose-vs-energy reconciliation (frozen): at d = 0.25 with perfect correlation,
the theoretical full-support energy recovery ceiling is
`(0.75·√r + 0.25)²·(1/r) − 1` over the lost fraction = **≈21.3%** at r =
0.456815, and ≈16.7% at correlation 0.90, before ANY mask. A 25% recovery
gate is therefore unreachable. Gates B and D are re-specified accordingly
(this is pre-light pre-registration, not post-hoc loosening — the v1 values
were arithmetically impossible).

| Gate | Requirement (v2) |
|---|---|
| A. Activation | 12/12 cells: quantized pixel change at the preservation checkpoint AND at replayed O5; no fail-closed/empty-support result |
| B. Effective dose (exact formula) | per cell `recovery_i = (Σ_w E_cand − Σ_w E_O2) / (Σ_w E_OR − Σ_w E_O2)` summed over VALID grid windows (eligible support) only; cohort mean over 12 cells ≥ **15%**; no cell < **8%**. The harness also reports each cell's theoretical full-support ceiling (perfect-correlation bound) for the record |
| C. Primary composite | `1 − mean(L_C)/mean(L_B) ≥ 0.25` from the COMMON pre-transfer O2 reference to replayed O5; overall ceiling **0.07366275**; hard-subset ceiling **0.07951875** |
| D. Delivered H1 | mean replayed O5 H1/source ratio ≥ **0.420** (0.362 baseline + 15% recovery × 0.543185 × 0.748 survival); median texture-ROI HFTR_H1 gain ≥ **8%**; ≥5/6 image means improve (seed-level counts reported) |
| E. Delivered detail | median O5 EATR gain ≥ **0.04** vs B |
| F. Safety | protected EATR ≥ 0.98×B every pair; smooth luma/chroma RMS rise ≤5%; rho rise ≤0.03 |
| G. Edge geometry | matched-edge ESF, common support frozen from B O2/R2, min 100 valid edges/pair + 20 protected (below minimum = gate failure): median width-gap worsening ≤ +0.25 px, no pair > +0.50 px; overshoot median ≤ +0.02, pair ≤ +0.03; out-of-transition excess energy median ≤ 2%, pair ≤ 5%; zero candidate-created second peaks in protected ROIs |

MOCK detection, panel, and vendor leg are stages 4–5 of the funnel — NOT this
commission.

## 6. Allowlist, artifacts, forbidden (v2)

- New files under `deepclean-worker/tools/` (candidate module + harness +
  tests) AND a new untracked artifact directory **`round-4d-1b-replay/`** at
  the workspace root for candidate images, per-cell manifests, deterministic
  report blocks, and gate outputs (all hash-recorded). Root report
  `C8_4D_1B_REPLAY_REPORT.md` (untracked).
- No modification of any existing tracked file. Frozen files zero-diff:
  `coherent_camera.py`, `checkpoint_attribution.py`, `camera_only_replay.py`,
  `checkpoint_capture.py`, `quality_finish.py`, `transfer_4d_1a.py`,
  `ds_remint_v8_8.py`, `worker.py`.
- No Supabase/RunPod access, no grading, no cells, no vendor, no deploy.

## 7. Deliverable

`C8_4D_1B_REPLAY_REPORT.md`:
1. fidelity results (byte-exact or failure, per cell, with delta distribution
   on failure);
2. per-cell activation, eligibility counts by gate, caps, dose, Gate B
   numerators/denominators, theoretical ceilings, and gates A–G;
3. artifact directory index with SHA-256 of every candidate image, manifest,
   and report block;
4. signed declaration: no commit, no deploy, no RunPod/Supabase action, no
   grading, no cell, no vendor call;
5. if any gate fails: stop, report exactly which and why, do not proceed.

The master engineer verifies every line before any next step.
