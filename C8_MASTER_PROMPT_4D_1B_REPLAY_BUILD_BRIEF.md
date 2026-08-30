# C8 MASTER PROMPT — 4D-1b REPLAY BUILD BRIEF (PURE REPLAY, NO LIVE CELLS)

Role: builder (code access). Deliverable: a replay-only harness + candidate
module + signed report. **No commit, no push, no deploy, no RunPod/Supabase
action, no grading, no live cell, no vendor call.** This brief commissions
STAGE 1–2 of the staged evidence funnel only (mechanism feasibility +
effect-size replay). The live round is a separate commission after this passes.

## 1. Mission

Build the 4D-1b candidate — **OR→O2, H1-only, loss-constrained camera-detail
preservation** — and run it as a pure replay on the 12 archived incumbent B
cells already retrieved (`round-4d-1a/checkpoints/<job_id>/`). Prove on
archived checkpoints, BEFORE anything is deployed:

1. **Mechanism feasibility**: the candidate activates (quantized change at the
   preservation checkpoint AND at replayed O5) on all 12 cells; support,
   caps, determinism, and reporting are truthful.
2. **Effect size**: the replayed candidate clears the full product-effect gates
   below against the archived incumbent B outputs.

If either fails: stop at replay and report. Nothing proceeds to freeze.

## 2. Inputs (all already on disk — no new data)

Per archived B cell, in `round-4d-1a/checkpoints/<job_id>/`:
`O0_source.png`, `O1_postwash.png`, `OR_postresample.png`,
`O2_precamera.png`, `O3_stage1.png`, `O4_preencode.png`, `O5_final.png`.
Per-cell executed settings: `round-4d-1a/cell-settings.json` (supplied by the
master engineer from the DB before the build starts; contains, per job id:
`color_restore_strength`, `jpeg_quality`, `jpeg_subsampling`,
`quality_finish` block, `finish_mode`, `engine_mode`, `seed`, `strength`).

The 12 job ids and the pair/seed map:
`round-4d-1a/expected-manifest.json` (ledger-derived) and
`ROUND_4D_1A_CELLS.md`.

## 3. Candidate spec (frozen constants)

### 3.1 Data boundary (strict)

The preservation synthesis may reference ONLY `OR_postresample` (H1 band) and
the incumbent `O2_precamera` (H1 band). `O0`, any resampled O0, and any source
alignment must NOT enter the candidate. Raw `O1` is not aligned anew — OR
already defines the lattice. (The downstream replay in §4 legitimately
reproduces the incumbent pipeline, which uses O0 for tone-lock — that is
incumbent behavior, not candidate input.)

### 3.2 Band

H1 only: `gauss(0.7) − gauss(1.4)` on luma (0.2126/0.7152/0.0722), frozen
`_gauss` uint8-quantized recipe. H0, H2, chroma: untouched. One band, one
variable.

### 3.3 Camera-residual basis (sign-preserving, restore-only)

```
O2_H1'(x) = O2_H1(x) + d · (OR_H1(x) − O2_H1(x))
```
with `d = 0.25` (frozen scalar dose) applied ONLY where support passes AND
`OR_H1` local energy > `O2_H1` local energy. Invariants (restore-only, not
detector-neutrality claims):
- never attenuate H1 (`O2_H1'` is a convex combination of `O2_H1` and
  `OR_H1`, 0 ≤ d ≤ 0.25 — sign/polarity of the remint coefficient is preserved
  by construction);
- post-change local H1 energy ≤ OR local H1 energy (never past OR);
- the added signal is a dose of the observed OR→O2 residual, never a free
  high-pass transform of OR or O2.

### 3.4 Support gates (per position, ALL must pass; thresholds are model
estimates, frozen as written)

1. signed local OR/O2 H1 correlation ≥ **0.90** (polarity not reversed);
2. structure-tensor axial orientation difference ≤ **10°**;
3. usable local H1 SNR ≥ **4** (noise = `max((1.4826 × MAD)², 1e-6)` over the
   lowest-20%-edge-energy 32×32 tiles of OR luma, MAD about median);
4. flat/near-flat and clipped/saturated neighborhoods excluded;
5. strong-edge exclusion = UNION of edges found independently in OR and O2
   (`np.gradient` magnitude, p92), Euclidean dilation **2 px**;
6. support re-applied AFTER any confidence smoothing (weight cannot leak
   outside support).

### 3.5 Numerics and reporting (frozen)

float64; frozen `_gauss`; no RNG; reflect borders; deterministic serialization
(fixed formatting, stable key order, no timestamps). Report per cell: pre/post
local H1-energy distributions, eligible/affected support counts, cap hits,
exclusions by reason, exact pixel hashes of OR, O2, preservation output, and
replayed O5; fail-closed on any inconsistency.

## 4. Downstream replay (effect size)

To measure O5 survival, replay the INCUMBENT downstream stages on the
preservation output, using the real worker modules (no reimplementation):

1. tone-lock histogram match to the original reference with the cell's
   `color_restore_strength` (`_histogram_match`);
2. `apply_quality_finish` with the cell's `quality_finish` settings;
3. stage-1 encode + final JPEG encode with the cell's codec settings.

**Fidelity proof FIRST**: replaying the downstream stages on the UNCHANGED
incumbent O2 must reproduce the archived O3/O4/O5 pixel hashes on this machine
for all 12 cells (byte-exact; any deviation must be proven deterministic and
bounded, never assumed). Only after fidelity passes may the preservation
output be pushed through the same downstream.

## 5. Pre-cell replay gates (all must pass on all 12 archived cells)

Measured anchors (frozen, from `round-4d-1a/or-band-split.json` and the 4D-1a
analysis): camera-ladder-only H1 retention **0.4568** (loss **0.5432**);
resample-only H1 loss **0.0000**; incumbent B O2→O5 loss means **0.098217**
overall / **0.106025** hard subset; downstream H1 survival **0.748**.

| Gate | Requirement |
|---|---|
| A. Activation | 12/12 cells: quantized pixel change at the preservation checkpoint AND at replayed O5; no fail-closed/empty-support result |
| B. Effective dose | mean recovered H1 ≥ **20%** of the cohort OR→O2 loss (≥0.1086); no pair < **10%** |
| C. Primary composite | `1 − mean(L_C)/mean(L_B) ≥ 0.25` from the COMMON pre-transfer O2 reference to replayed O5 (overall ceiling **0.07366275**; hard subset **0.07951875**) |
| D. Delivered H1 | mean replayed O5 H1/source ratio ≥ **0.445**; median texture-ROI HFTR_H1 gain ≥ **8%** vs B; ≥5/6 image means improve |
| E. Delivered detail | median O5 EATR gain ≥ **0.04** vs B |
| F. Safety | protected EATR ≥ 0.98×B every pair; smooth luma/chroma RMS rise ≤5%; rho rise ≤0.03 |
| G. Edge geometry | matched-edge ESF (common support from B O2/R2): median width-gap worsening ≤ +0.25 px, no pair > +0.50 px; overshoot median ≤ +0.02, pair ≤ +0.03; out-of-transition excess energy median ≤ 2%, pair ≤ 5%; zero candidate-created second peaks in protected ROIs |

MOCK detection, panel, and the vendor leg are NOT part of this commission
(stages 4–5 of the funnel, after candidate freeze).

## 6. Allowlist and forbidden

- New files only, under `deepclean-worker/tools/` (candidate module +
  replay harness + tests). **No modification of any existing file.**
- Frozen files zero-diff: `coherent_camera.py`, `checkpoint_attribution.py`,
  `camera_only_replay.py`, `checkpoint_capture.py`, `quality_finish.py`,
  `transfer_4d_1a.py`, `ds_remint_v8_8.py`, `worker.py`.
- No Supabase/RunPod access, no grading, no cells, no vendor, no deploy.

## 7. Deliverable

`C8_4D_1B_REPLAY_REPORT.md` (workspace root, untracked):
1. fidelity proof results (incumbent downstream replay vs archived O3/O4/O5
   hashes, all 12 cells);
2. per-cell activation, support, caps, dose, and every gate A–G;
3. artifact hashes and the deterministic report blocks;
4. signed declaration: no commit, no deploy, no RunPod/Supabase action, no
   grading, no cell, no vendor call;
5. if ANY gate fails: stop, report exactly which, do not proceed.

The master engineer verifies every line before any next step.
