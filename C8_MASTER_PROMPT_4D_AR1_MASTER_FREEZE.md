# 4D Architecture Reset 1 — Master Experimental Freeze (4D-AR1)

Author: master engineer (D). Supersedes and closes: `C8_MASTER_PROMPT_4D_1B_REPLAY_BUILD_BRIEF_V21.md` (v2.1).
This document is the single frozen commission. It implements the converged
three-party plan (owner, C88, Consultant D) and the owner's M0–M4 operating
system. No arm, threshold, metric name, or decision rule changes after first
light without a new freeze.

## 0. Disposition of prior commissions

1. **v2.1 replay commission: CLOSED, hard-stopped, unmodified.** Owner chose
   governance option 2: the 4D-1b candidate replay does not continue under
   the v2.1 rules. Its fidelity failure stands as recorded
   (`C8_4D_1B_REPLAY_REPORT.md`). It is not "failed science" and not reopened.
2. **Historical replay recovery (Track B) runs in PARALLEL** under its own
   frozen rules (§11). It changes nothing in v2.1 and blocks nothing here.
3. **The 4D-1b H1-preservation hypothesis is HELD, not rejected.** In this
   commission it appears as arm A4 only. It becomes production architecture
   only through the full funnel (M1→M2→M3), never by presumption.

## 1. Frozen factual baseline (permanent, units-corrected)

Computed by the master engineer from the archived 4D-1a cells
(`checkpoint_attribution` recipes, frozen):

- H1 band = luma ⊗ (gauss σ0.7 − gauss σ1.4); `h1_energy_ratio = E_out / E_ref` where `E = mean(band²)`.
- Cohort mean O5 H1 energy ratio vs source = **0.362** (energy basis, 12 B cells).
- Spot check (computed 2026-08-29): IMG-5/ctla1 global energy 0.398668 (RMS 0.631402); IMG-11/ctla1 global energy 0.416745 (RMS 0.645558). The corresponding RMS-ratio view is the square root — mixing the two produced every disputed figure.
- Frozen Gate D floor **0.420** is an **energy-ratio floor**. **No dimensional defect exists.**
- Camera-ladder H1 loss = **0.543185**; resample contribution ≈ 0 (geometry-normalized). Downstream O2→O5 survival = **0.748** (all energy basis, measured).
- `0.454` (perfect correlation/full support) and `0.434` (correlation 0.90) are **planning estimates, retired**. `≈0.46` is **retired** as an overstatement.
- Energy-basis dose (frozen candidate definition): `d = 0.25` of the positive OR→O2 H1 residual. Dose in energy units = 0.25 × 0.543185 = **0.135796**; perfect-correlation recovery fraction = ((0.75√0.456815 + 0.25)² − 0.456815) / 0.543185 = **21.37%**. These are arithmetic identities, not measurements. The disputed `0.1359`-style squared figures are retired.
- **Eligible lost-energy mass remains UNKNOWN** (candidate never ran). It is measured only by arm A4 (§6).
- O2 is the largest measured quality cost. O2's isolated real-detector benefit is **unmeasured** — this commission measures it.
- Raw O1-vs-O5 vendor grading is withdrawn as confounded.
- `0.362`/`0.420`/`0.543185`/`0.748`/`0.07366275`/`0.07951875` are measured frozen facts; everything else above is labeling.

## 2. Unified objective (no metric may compensate another)

Success requires ALL four: (1) content integrity; (2) naturally photographic
visual quality at delivery size and full zoom; (3) detector eligibility of the
exact delivered bytes; (4) deterministic, affordable, auditable operation with
abstention capability.

## 3. Scope and roles

- Offline only until the M3 vendor leg. **No commit, no deploy, no live cell,
  no grading, no vendor call** in M1–M2. Builder never commits/deploys.
- Owner: business requirements, budgets, final acceptance, RunPod ops (Track B).
- Master engineer (D): this freeze, evidence integrity, arbitration, all
  threshold authority.
- Builder (C88): implements exactly the frozen arms; no threshold decisions.
- Independent auditor (Consultant D + any second): verifies code, arithmetic,
  manifests separately.
- Panel lead: blinded presentation and reviewer calibration.
- Operator: executes frozen runs without design discretion.

## 4. Inputs and environment (frozen)

- Cells: the 12 archived 4D-1a B cells (`round-4d-1a/checkpoints/<job>/O0/O1/OR/O2/O5`)
  and `round-4d-1a/cell-settings.json` (pin `17691de31256b5a5f6db99bc0b94560606556e10b40a04fbb805340dffa439f6`),
  `round-4d-1a/expected-manifest.json`, `round-4d-cam-1/roi-manifest.json`.
- Upstream cache: O0/O1/OR bytes are shared by construction across arms; the
  expensive wash is never repeated.
- Environment (same machine, same interpreter for ALL arms and reruns):
  `$TMPDIR/verify3` — Python 3.9.6, numpy 2.0.2, Pillow 11.3.0. A `pip freeze`
  listing is written to `round-4d-ar1/environment-freeze.txt` on first run and
  is part of the artifact manifest. All arms use the same seed strings as the
  archived cells (`lab:lab-ctla1`, `lab:lab-ctla2`).
- Determinism: no new RNG. Existing frozen seeded paths only.

## 5. Arms (frozen factor definitions)

Factors: **camera** (on = archived O2 / off = OR_postresample used as the O2
position), **intermediate JPEG** (on = stage-1 q92 4:2:0 encode+decode / off =
pre-encode buffer handoff, mirroring the worker's fidelity handoff),
**QF** (on = `apply_quality_finish` preset `strong`, overrides
`{dither 1, sharpen 1, smoothness 1.25}`, scale 1, reference = source / off =
finisher removed).

| Arm | camera | inter-JPEG | QF | Composition |
|---|---|---|---|---|
| A0 incumbent replay | on | on | on | O2 → tone-lock → q92 → QF → q97 |
| A1 camera-off | off | on | on | OR → tone-lock → q92 → QF → q97 |
| A2 codec bypass | on | off | on | O2 → tone-lock → QF(buffer) → q97 |
| A3 camera-off + bypass | off | off | on | OR → tone-lock → QF(buffer) → q97 |
| A4 4D-1b preservation | on | on | on | `transfer_4d_1b.build_candidate(OR, O2)` → tone-lock → q92 → QF → q97 |
| A5 QF-off | on | on | off | O2 → tone-lock → q92 → q97 |
| A6 QF-off + camera-off | off | on | off | OR → tone-lock → q92 → q97 |
| A7 minimal camera kernel | — | — | — | NOT COMMISSIONED this round; requires a new freeze |

Delivery match for every arm: same per-cell delivery size (1250/800/1080),
tone-lock = `_histogram_match` strength 0.8 vs source, final encode JPEG
quality **97** subsampling **4:4:4** optimize True single encode, uniform
metadata policy (no EXIF in arm outputs), output_mode semantics `stripped`.
Frozen modules only: `max_cx_remint._histogram_match`,
`quality_finish.apply_quality_finish`, `transfer_4d_1b.build_candidate`,
`checkpoint_attribution` recipes. New file: `deepclean-worker/tools/round_4d_ar1_factorial.py`
(+ contract tests). Frozen files: zero-diff, always.

## 6. Metric names and units (frozen; never collapsed to "H1")

- `h1_energy_ratio = E_out / E_ref` (global and per-ROI; H0/H2 defined identically per band)
- `h1_rms_ratio = sqrt(h1_energy_ratio)`
- `texture_hftr_rms_gain` — median relative gain of per-texture-ROI RMS ratio (attribution HFTR_H1 definition)
- `eligible_recovered_energy`, `eligible_lost_energy_mass`, `whole_frame_recovered_energy` — A4 recovery-report definitions
- `eatr_p95` — positional-band p95 edge-magnitude ratio (frozen recipe)
- ESF: `edge_width_10_90`, overshoot, ringing, candidate-created second peaks (frozen edge recipes)
- Noise: smooth/texture-region residual RMS (luma + chroma), lag-1 `rho1`, per-band noise spectrum
- `banding_index`, `staircase_index_jpeg` (QF frozen diagnostics)
- Tone: mean |Δluma|, mean |Δchroma| vs source
- Integrity: geometry equality; privacy-redaction ROI byte-identity; protected-ROI pixel delta envelope; second-peak count
- `delivery_resolution` + sampling factors

The band-energy-map numbers (0.362, 0.484, 0.543185) are `h1_energy_ratio`-family values. Any report mixing bases is rejected.

## 7. Quality funnel (M2) — order and thresholds

Per arm, in order; any failure terminates that arm:

1. **Integrity.** Geometry matches; privacy-redaction ROIs byte-identical to
   shared upstream; no candidate-created second peaks in protected ROIs;
   protected EATR ≥ 0.98 × A0 per cell.
2. **Objective quality floors (all arms vs A0, frozen v2.1 F-gate constants
   reused as universal floors).** Smooth-region luma RMS rise ≤ 5%; chroma
   RMS rise ≤ 5%; rho rise ≤ 0.03; worst protected EATR ratio ≥ 0.98; energy
   gain must not be noise-driven (smooth-region residual RMS must not rise
   more than the luma floor); ESF cohort median overshoot delta ≤ +0.02, no
   pair > +0.03. All other metrics are measured and reported, not gated.
3. **Blinded panel (shortlisted arms only).** Randomized AB vs A0, all 6
   images, two viewing scales (intended mobile display size and full
   resolution), naturalness 1–5 and forced preference scored separately,
   artifact taxonomy, calibrated instructions, reviewer agreement reported.
   An arm with recurring named artifacts or no meaningful naturalness
   improvement is rejected.

## 8. Candidate selection (deterministic, before any detector result)

Exactly one challenger. Order: (1) integrity pass; (2) artifact-safety pass;
(3) highest blinded naturalness; (4) edge/texture fidelity as tie-breaker;
(5) lower complexity + runtime as final tie-breaker. Freeze the winner's exact
file hashes + complete settings **before** any Hive call. No second candidate
after seeing Hive results; a failed winner requires a new frozen round.

## 9. M3 — Twelve-call Hive leg (frozen)

- Submissions: six exact incumbent delivered files (re-fetched from archived
  job outputs, byte-hash pinned) + six exact challenger files (frozen winner
  arm outputs, byte-hash pinned).
- Vendor: single vendor Hive (existing `VENDOR_FREEZE_4D_1A.md` v3 rules:
  fresh-call ledger, C2PA deny-list, no flux key = evaluator failure, median
  of 3rd+4th sorted).
- Thresholds: AI ≤ **0.45**; flux-family ≤ **0.30**; deepfake ≤ **0.10**;
  frozen paired non-amplification rule; missing/malformed response fails closed.
- Decision table: camera-off wins quality + detection ⇒ remove O2; 4D-1b wins
  both ⇒ retain provisionally while simplifying O2; codec bypass wins both ⇒
  remove the intermediate JPEG from the composite path; camera-off fails
  detection while incumbent passes ⇒ decompose O2 to the minimum useful
  component; both fail ⇒ pivot to O1 wash policy and routing; no visually
  natural candidate ⇒ stop before Hive; no route clears detection ⇒ abstain —
  never ship the least-bad failure.
- A Hive pass proves Hive eligibility only. Broader claims require a
  separately approved second-vendor validation.

## 10. M4 — Production admission (gates, not yet authorized)

Only after M3: one validated default route; scene-class routing only where
evidence exists per class; validated fallback; shipment disabled when no route
qualifies; exactly one final encode; exact settings/hashes/detector versions
retained; latency/failure/abstention/cost monitored; frozen regression corpus
rerun after any dependency or detector change. Naturalization remains OFF and
isolated; it may enter a future experiment only as a separately frozen arm.

## 11. Track B — historical replay recovery (parallel, no new code)

Owner creates a RunPod pod from the deployed worker image digest
`sha256:25dfbf6716d13381e7ecd2de8f744712b299e1e2449a14adeefadfc18efe9511`
(or uses the retrieval pod if it matches), copies `round-4d-1a/` + the frozen
v2.1 harness, and runs `round_4d_1b_replay.py` — pure compute, no Supabase/
cells/grading/vendor. Outcomes: byte-exact O3/O4/O5 ⇒ the archived environment
is proven and the frozen v2.1 Gates A–G run there as originally commissioned;
non-exact ⇒ v2.1 remains closed unless the master engineer authorizes a new
tolerance in a new freeze. Track B never blocks Track A.

## 12. Stop conditions, errors, and artifacts

Hard stop: any pin mismatch; non-finite metric; missing file; panel
non-agreement below reported threshold (documented in the panel protocol);
any arm output not delivery-matched; any forbidden external action.
Artifact directory `round-4d-ar1/` (hash-indexed, `artifact-index.json`
excluding itself) + report `C8_4D_AR1_REPORT.md` + `environment-freeze.txt`.
Builder signs; master engineer verifies every line before any next step;
operator executes without discretion.

## 13. Immediate sequence

1. Builder implements the §5 factorial harness + contract tests (new files only).
2. Master engineer verifies line-by-line, then the operator runs A0–A6 on the
   pinned environment.
3. Master engineer computes §6 metrics and §7 floors; panel lead runs the
   blinded panel on the shortlist.
4. Candidate frozen (§8). Owner executes the 12-call Hive leg (§9) with the
   operator; results interpreted by the frozen decision table.
5. Track B (§11) proceeds in parallel under owner ops.
