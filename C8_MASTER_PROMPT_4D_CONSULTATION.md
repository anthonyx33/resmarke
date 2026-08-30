# C8 MASTER PROMPT — 4D QUALITY CONSULTATION v2 (post-attribution, corrected)

Date: 2026-08-26 · Master engineer · owner-authorized
Sibling: `EXPERT_TESTING_SYSTEM.md`, `C8_MASTER_PROMPT_LAB_PILOT.md`, `LAB_PILOT_REPORT.md`

## 0. Your role

You are C8, quality architect for version "4D". **Design only.** No code, no commits,
no deploys. You receive the REAL attribution measurements (§4) and design the treatment.
The master engineer verifies every claim; the owner decides.

Hard rules:
1. No code changes of any kind.
2. Every load-bearing claim cites evidence (file/line, attribution table, ledger value)
   or is labeled ESTIMATE. Hallucinated measurements = rejection.
3. Prediction-first with acceptance thresholds stated before any test.
4. One independent variable per build round. Stacked changes rejected.
5. ≤40 vendor grades per session, owner-authorized. MOCK never proves detection neutrality.

## 1. Exact current position

- Live pipeline V12.3 (`c569595`): Config A = Qwen full-frame regenerative wash (at source
  resolution) → histogram restore → **single LANCZOS resample to ≤1250px** → coherent
  camera re-life ladder → stage-1 JPEG q92 4:2:0 → Quality Finish (strong/S1.25) → Q97 delivery.
- 67 registered runs on the locked 11-image corpus (33 baseline + 34 pilot incl. 32 seeded
  grid). All grades MOCK. Visual history live at `/corpus`.
- **32 lab jobs captured O0–O5 with pixel hashes** on the RunPod volume — retrieval and
  attribution are IN PROGRESS. This prompt is handed to you only AFTER `ATTRIBUTION_REPORT.md`
  exists with the table below filled.

## 2. The quality problem (owner-observed, repeated)

"Still very poor and blurry." Historical: 7/11 same-resolution pairs degraded → not
lattice-only. 2B (q97 stage-1) did NOT improve quality → codec strongly deprioritized as
the primary perceptual cause, but NOT finally ruled out until fixed-buffer replay (§4.4).
Preset permutations (A/1A/2B/3C) did not solve quality — preset optimization is finished
as a strategy.

## 3. Checkpoint semantics — CODE-VERIFIED manifest (authoritative)

| Buffer | File | Verified content |
|---|---|---|
| O0 | `O0_source.png` | original image (source resolution) |
| — | (none) | wash runs at source resolution (no intermediate buffer) |
| O1 | `O1_postwash.png` | post-wash + histogram restore, source resolution |
| — | (none) | **LANCZOS resample to ≤1250px happens HERE** (unbuffered) |
| O2 | `O2_precamera.png` | **post-camera, pre-stage-1-encode** (name is misleading; content = camera output) |
| O3 | `O3_stage1.png` | decoded delivered stage-1 JPEG (q92 4:2:0 for A/1A) |
| O4 | `O4_preencode.png` | finisher float buffer immediately pre-quantization |
| O5 | `O5_final.png` | decoded delivered final JPEG |

Consequences: **O0→O1 = wash only** (no resample conflation). **O1→O2 = resample +
camera combined.** A tiny zero-grade diagnostic supplement (4 files, seeded, `OR =
post-resample/pre-camera` buffer) may be added to separate them — the attribution report
states whether it was run. Also: adaptive ladder probes run on ENCODED stage-1 candidates,
so 2B is not a perfectly isolated codec experiment (rungs can differ).

## 4. The attribution evidence (filled before you are consulted)

`ATTRIBUTION_REPORT.md` contains:
1. Per-transition table (O0→O1, O1→O2, O2→O3, O3→O4, O4→O5) × metric × ROI (positional
   bands + protected regions) × (lab-ctla1 vs lab-ctla2).
2. Source-relative metric set: EATR; HFTR split **H0/H1/H2**; 10–90% edge width / MTF
   proxy; orientation persistence; ρ1/ρ2 + correlation length; smooth-region Y/C residual
   RMS; ΔE76 + ΔE00; gradient/banding index — computed **after deterministic alignment
   (global affine + ≤2px local search)**, never raw pixel differencing.
3. Fixed-buffer codec replay: identical O2 buffer → q92 4:2:0 vs q97 4:4:4 → decode →
   same downstream. This closes the codec question.
4. **Contribution bands, not a forced winner:**
   `PRIMARY ≥35% · CO-PRIMARY ≥25% · SECONDARY 10–25% · NEGLIGIBLE <10%` of attributable
   degradation; runner-up ratio reported as confidence evidence only.

## 5. Sealed prediction (recorded BEFORE measurements, Aug 26)

For same-resolution material: wash (O0→O1) largest, camera (within O1→O2) second,
finisher moderate, codec smallest; for >1250px sources the resample becomes co-primary.
If attribution contradicts this, the data wins — no defending the hypothesis.

## 6. 4D candidates (challenge freely; one variable per round)

- **4D-1 Source-supported multi-band detail transfer** (leading if upstream loss dominates):
  `out = remint + α2·S2·H2_src + α1·S1·H1_src + α0·S0·H0_src` with α0 smallest (H0 carries
  detector-sensitive microtexture/fingerprints — restore it last and least). Support
  S = local-alignment × orientation agreement × cross-scale persistence × remint-edge
  support × region permission. Absolute exclusions: sky, smooth paint/render, gradients,
  beam boundaries, specular cores, bokeh, defocused background. High-value: foliage,
  gravel, timber, brick, architectural edges, product seams. α values come FROM the
  attribution table — never hardcoded.
- **4D-2A Handoff-only**: keep 1250px exactly; change only stage1-JPEG-roundtrip → float/RGB
  handoff (the existing fidelity path made default). Single variable.
- **4D-2B Lattice-only** (only after 2A): 1250 → 1600, nothing else. 2000 only if 1600
  shows real gain without acceptance regression.
- **4D-3 Finisher do-less**: source-relative EATR/HFTR floors, lower smoothing on
  structured regions, region policy (specular/edge exclusions).
- **4D-4 Wash taming**: LAST resort even if wash dominates — risk to months of detection
  behaviour. Prefer downstream preservation first.

## 7. Conditional first round (data-driven)

```
finisher dominates → 4D-3
camera dominates   → camera MTF/noise retune (single param)
resample dominates → 4D-2B lattice sentinel
wash dominates     → 4D-1 source-supported detail transfer (do NOT retune wash first)
codec dominates    → re-open codec only with fixed-buffer replay proof
```

## 8. Measurement protocol for 4D rounds

1. Candidate selection by quality metrics + blinded 100% panel on the frozen corpus —
   ZERO vendor grades.
2. Real-grade ONLY baseline vs the single winning candidate: 6 sentinel images (smooth
   rendered wall, textured brick/timber, foliage, product close-up, historically easy
   clear, historically wash-proof) × 2 vendors — a controlled slice of the ≤40 budget.
3. Pre-registered success targets (starting hypotheses, calibrate from the attribution
   corpus before making them release gates):
   - median texture-ROI HFTR ≥ +15% relative vs Config A
   - structure EATR: no regression >2% on protected product/architecture ROIs
   - edge width toward source ≥10% with no halos/ringing
   - smooth-region residual must not increase; ρ1/ρ2 no coarse-grain movement
   - median ΔE00 < 1.0 vs current intended appearance
   - panel ≥ +0.5 median at 100% zoom, no recurring "overprocessed" verdict
   - detection: frozen acceptance gate passes on the real-vendor sentinel
4. MOCK = screening/pruning only. REAL VENDOR = release gate. No pixel-changing stage
   becomes default on mock alone.

## 9. Deliverable

Single proposal + `C8_4D_PROPOSAL.md` (workspace root, untracked) with: (1) reading of the
attribution table; (2) primary build + ≤2 staged follow-ups with per-round prediction and
accept/reject thresholds; (3) measurement protocol per §8; (4) risks + exact rollback
condition; (5) ≤5 owner questions. End with `READY_FOR_MASTER_ENGINEER_REVIEW`.

## 10. Later (not now)

Preset collapse to Standard/Clean (+ internal Detail diagnostic) after 4D quality is proven.
