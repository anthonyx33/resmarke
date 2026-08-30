# C8 MASTER PROMPT — 4D-1b REPLAY BUILD BRIEF v2.1 (AUTHORITATIVE)

Role: builder (code access). Deliverable: replay-only harness + candidate
module + signed report. **No commit, no push, no deploy, no RunPod/Supabase
action, no grading, no live cell, no vendor call.**
Supersedes v1 and v2; this document wins on every conflict. Incorporates the
expert audit's v2.1 redlines: corrected final stage (stripped pass-through),
corrected energy arithmetic, dimensionally honest Gate D, fully frozen
synthesis primitives, literal evidence hashes, Gate B companion metrics, and a
pinned edge-support artifact.

## 1. Mission (unchanged)

Prove on the 12 archived incumbent B cells — BEFORE anything is deployed —
that the OR→O2 H1-only loss-constrained preservation candidate (a) activates,
(b) reproduces incumbent downstream behavior (fidelity), and (c) clears the
product-effect gates. Any gate failure stops at replay.

## 2. Inputs (literal pins — SHA-256 recorded now, not at build time)

| input | SHA-256 |
|---|---|
| `round-4d-1a/expected-manifest.json` (24 cells × 7 pixel hashes incl O3/O4/O5) | `6d1c730c629fda80b04b742bc75423f2f4710802a6cabc330910aaff7739c76a` |
| `round-4d-1a/cell-settings.json` (12/12 `executed` blocks populated from archived DB reports, extracted by master engineer 2026-08-27) | `17691de31256b5a5f6db99bc0b94560606556e10b40a04fbb805340dffa439f6` |
| `round-4d-1a/or-band-split.json` (+ generator `deepclean-worker/tools/round_4d_1a_or_split.py` `8ba884c6d484443ea9c7f9b5c3539162b8cf8c41f5a988bcddce1dc70edd6c2a`) | `483c9d8dab867f2cd40fbec9d0898371c246fd6d024640343be99fe2f6691ccb` |
| `round-4d-cam-1/roi-manifest.json` | `5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329` |
| evaluator `deepclean-worker/tools/round_4d_cam_1_gates.py` | `cf4c81bc0d70cf6364cba8c5e26dfaf3baba59e9b20cdf0cb97e3bb6a6e677a3` |
| evaluator `deepclean-worker/tools/edge_spread_audit.py` | `3175409ef6c815df25ffb9027c7184667d7c1c04cf2d86d99128480f327f3cc4` |
| `deepclean-worker/tools/checkpoint_attribution.py` (frozen) | `335d8967560a60f32c5732fde63258d9919520fd7006d8d74c1ffa46eef53a44` |
| `deepclean-worker/quality_finish.py` | `538c9edb3bdc7c0ebe7e8faf16b37a76d6d0c29b107a1914168bed8e4f587175` |
| `deepclean-worker/ds_remint_v8_8.py` (current deployed) | `9e57e06eacc8257dfc5c5acdcababd5c6ce25caea7b0dcdbb0160936fda8b1e8` |
| `deepclean-worker/worker.py` (current deployed) | `93f46bbe8412d846b1a15cb42eeca843f5184e32c608e870633f9e09cc98a5f3` |

The harness verifies every pin before running and stops on mismatch.
`cell-settings.json` schema per job id: `remint` (engine_mode, wash_model,
strength, deep_degrade_scale, min_ssim, color_restore, color_restore_strength,
jpeg_quality, jpeg_subsampling), `finish` (preset, scale, overrides,
material_clean, finish_mode), and **`executed`** — `finish_preset_selected`,
`finish_qc_passed`, `effective_seed`, `output_mode` (= `"stripped"` for all
/relab cells), `finalize_passthrough` (= true), `qf_encode` (QF's own encode
block). **The 12 `executed` blocks are a mandatory prerequisite and are now
populated** (extracted by the master engineer from the archived DB reports on
2026-08-27, owner-authenticated Supabase session; all 12 verified consistent:
engine `ds_remint_v8_8`, profile `max`, output_mode `stripped`, finish mode
`quality-finish` preset `strong` applied, QC passed, stage-1 q92/4:2:0, QF
own encode q97/4:4:4 single, finalize pass-through both blocks). The harness
stops if any is absent or mismatches the archived report.

## 3. Candidate spec (frozen)

### 3.1 Data boundary (unchanged)
Synthesis references ONLY `OR_postresample` H1 and `O2_precamera` H1. O0, any
resampled O0, source alignment, source coefficients: excluded. (Downstream
replay reproduces incumbent behavior, including O0-based tone-lock.)

### 3.2 Band (unchanged)
H1 = `gauss(0.7) − gauss(1.4)` on luma (0.2126/0.7152/0.0722), frozen
uint8-quantized `_gauss`. H0, H2, chroma untouched.

### 3.3 Per-pixel eligibility (invariants true by construction)
Dose applies ONLY where ALL hold:
1. local window: signed OR/O2 H1 correlation ≥ 0.90 AND axial orientation
   difference ≤ 10° AND usable local H1 SNR ≥ 4;
2. same sign: `sign(OR_H1(x)) == sign(O2_H1(x))`;
3. magnitude order: `|OR_H1(x)| ≥ |O2_H1(x)|`;
4. outside flat (`_edge_mag` of OR luma < p30) and outside saturation
   (any channel ≥ 250 or ≤ 5, evaluated over the same 15×15 window);
5. outside the strong-edge exclusion (union of OR/O2 edges, `np.gradient`
   magnitude, p92, Euclidean dilation 2 px);
6. support is BINARY, derived from the unsmoothed eligibility mask — no
   confidence field, no smoothing, no weight leak.

With 2+3, `candidate_H1 = O2_H1 + d·(OR_H1 − O2_H1)`, `d = 0.25`, satisfies per
eligible coefficient: same polarity, no attenuation, `|O2_H1| ≤ |cand_H1| ≤
|OR_H1|`. True by construction on eligible pixels.

### 3.4 Frozen primitives (complete)

- SNR: `noise_energy = max((1.4826 × MAD)², 1e-6)` where MAD (about the
  median) is taken over the OR-luma H1 band samples of the lowest-20% tiles
  (32×32) by mean squared `_edge_mag`; `SNR = local 15×15 H1 energy /
  noise_energy`.
- NCC: 15×15 window, mean-centered, denominator = product of window standard
  deviations with ε = 1e-9; denominator ≤ ε ⇒ window invalid.
- Structure tensor: on the H1 band, `np.gradient`; windowed sums Jxx, Jyy,
  Jxy over the 15×15 window; axial angle = `0.5·atan2(2·Jxy, Jxx − Jyy) mod
  π`; orientation difference = `min(|d|, π − |d|)`.
- Valid window: all samples finite, in-bounds, NCC denominator > ε; for Gate B
  additionally Σ(E_OR − E_O2) > 0 and the window intersects the eligible
  support mask.
- Cap enforcement: post-synthesis invariant `E_O2 ≤ E_cand ≤ E_OR` per valid
  15×15 grid window, tolerance 1e-9 relative; where `E_cand > E_OR`, one
  deterministic vectorized rescale toward O2; overlapping window correction
  factors bilinearly upsampled and multiplied elementwise, single pass; any
  remaining violation fails the cell closed.
- Cap checks use the H1 field **recomputed from the quantized RGB output**
  (the delivered pixels, not the pre-quantization field).
- Synthesis: `Δ = cand_H1 − O2_H1`; `Δ_safe = clip(Δ, −min(R,G,B),
  1 − max(R,G,B))`; `out_RGB = clip(RGB + Δ_safe, 0, 1)`; single uint8 round;
  capped-pixel fraction reported.
- float64, frozen `_gauss`, no RNG, reflect borders, deterministic
  fixed-format serialization.

## 4. Downstream replay (CORRECTED final stage)

The /relab incumbent path (output_mode `stripped`, naturalization off,
finalize pass-through — verified against `RelabApp.tsx:515` and
`worker.py` finalize_output):

`O2 → tone-lock → stage-1 q92/4:2:0 encode → decode (O3) → selected Quality
Finish on the delivered stage-1 JPEG → O4 → QF's own q97/4:4:4 encode →
finalize pass-through → O5`

The harness implements exactly this using the real worker modules and the
cell's `finish` + `executed` settings.

**Fidelity is strictly binary**: replaying the UNCHANGED incumbent O2 must
reproduce the archived O3/O4/O5 decoded-pixel hashes BYTE-EXACT for all 12
cells. Any non-exact cell stops the commission with a delta distribution
report; the builder may NOT choose or propose a tolerance. Non-exact fidelity
= "replay not proven"; only the master engineer may authorize further work
under an explicitly frozen tolerance.

## 5. Replay gates (reconciled, dimensionally honest)

Measured anchors (frozen): camera-ladder-only H1 retention **0.456815** (loss
**0.543185**); resample retention 1.000000 under the geometry-normalized
comparison (qualified: earlier native-resolution attribution found a real,
secondary resample cost); incumbent B O2→O5 loss means **0.098217** overall /
**0.106025** hard subset; downstream H1 survival **0.748**.

Perfect-correlation dose arithmetic (corrected):
`r' = (0.75·√r + 0.25)²`; `recovery = (r' − r)/(1 − r)`. At r = 0.456815:
recovery ≈ **21.3%** (≈16.7% at correlation 0.90, before masks).

| Gate | Requirement (v2.1) |
|---|---|
| A. Activation | 12/12 cells: quantized pixel change at the preservation checkpoint AND at replayed O5; no fail-closed/empty-support result |
| B. Effective dose | per cell `recovery_i = (Σ_w E_cand − Σ_w E_O2) / (Σ_w E_OR − Σ_w E_O2)` over VALID grid windows only; cohort mean ≥ **15%**; no cell < **8%**. Companions (report-only, required in the report): whole-frame recovered loss (same formula over ALL windows with positive denominator) and eligible lost-energy mass (eligible-window denominator ÷ whole-frame denominator). Each cell's theoretical perfect-correlation ceiling is reported |
| C. Primary composite | `1 − mean(L_C)/mean(L_B) ≥ 0.25` from the COMMON pre-transfer O2 reference to replayed O5; overall ceiling **0.07366275**; hard-subset ceiling **0.07951875** |
| D. Delivered H1 | mean replayed O5 H1/source ratio ≥ **0.420** (labeled model-estimate product gate; no dimensional arithmetic claimed); median texture-ROI HFTR_H1 gain ≥ **8%**; ≥5/6 image means improve (seed-level counts reported) |
| E. Delivered detail | median O5 EATR gain ≥ **0.04** vs B |
| F. Safety | protected EATR ≥ 0.98×B every pair; smooth luma/chroma RMS rise ≤5%; rho rise ≤0.03 |
| G. Edge geometry | matched-edge ESF with a **pinned edge-support artifact** generated deterministically from the INCUMBENT B O2/R2 only (path `round-4d-1b-replay/edge-support-artifact.json`, hash recorded in the artifact index BEFORE any candidate output is inspected); min 100 valid edges/pair + 20 protected (below minimum = gate failure): median width-gap worsening ≤ +0.25 px, no pair > +0.50 px; overshoot median ≤ +0.02, pair ≤ +0.03; out-of-transition excess energy median ≤ 2%, pair ≤ 5%; zero candidate-created second peaks in protected ROIs |

MOCK detection, panel, and the vendor leg are stages 4–5 of the funnel — NOT
this commission.

## 6. Allowlist, artifacts, forbidden (unchanged from v2)

New files under `deepclean-worker/tools/` + untracked artifact directory
`round-4d-1b-replay/` (all outputs hash-recorded) + root report
`C8_4D_1B_REPLAY_REPORT.md`. No modification of existing tracked files;
frozen files zero-diff (list per v2). No Supabase/RunPod access, no grading,
no cells, no vendor, no deploy.

## 7. Deliverable (unchanged from v2, plus §5 companions and §4 fidelity)

`C8_4D_1B_REPLAY_REPORT.md` with fidelity results, per-cell activation/
eligibility/caps/dose, Gate B formulas + companions + ceilings, gates A–G,
artifact index with SHA-256, signed declaration, and hard stop on any failure.

The master engineer verifies every line before any next step.
