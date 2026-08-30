# C8 MASTER PROMPT — 4D-1A BUILD BRIEF (H1/H2 SOURCE TRANSFER)

Owner shorthand: "5E". Program name: **4D-1a**. Next approved brief after 4D-CAM-1
rejection and the edge-spread audit (`EDGE_SPREAD_AUDIT_REPORT.md` — read first,
three findings below change this brief materially).

Deliverable for THIS prompt: **audit response only.** No code, no commits, no
deploys, no Supabase/RunPod actions, no grading. The build is commissioned
separately after your audit is accepted.

## 0. Mission

Reduce the largest measured quality loss (W1: camera+resample, O1→O2) at the
delivery level by restoring mid-band (H1/H2) detail energy from the ORIGINAL into
the remint — **remint-led, support-gated, phase-preserving**. H0 excluded. Alpha
ceiling 0.10. One sealed variable: transfer ON vs OFF.

## 1. Edge-audit findings that bind this brief

1. Camera PSF (halved) does NOT broaden matched edges at O2 (C ≈ B: mono width
   +0.02 px). The gate-6 widening was born in the **finisher** (O2→O5) and
   amplified by the blur-sensitive `edge_width_10_90` threshold metric.
2. A small real ringing/over-sharpen component exists on worst pairs
   (IMG-8 ctla1 O5 mono +1.4 px; IMG-5 ctla1 overshoot +0.027).
3. Therefore: edge pass/fail gates use **absolute matched-edge ESF metrics**
   (mono width px, overshoot, second-peak), at BOTH O2 and O5.
   `edge_width_10_90` is context-only, never a gate.

## 2. Design

### 2.1 Placement

In `ds_remint_v8_8.py`, after the O2 capture (`O2_precamera.png`) and **before**
the tone-lock block. Consequence: **O2 is identical within every B/C pair** — a
hard provenance check this round gets for free.

### 2.2 Algorithm (phase-preserving energy matching)

Inputs: `final_image` (remint-led O2) and `original` resampled to O2 geometry (R2).

1. **Bands (luma only):** H1 = gauss(0.7) − gauss(1.4), H2 = gauss(1.4) − gauss(4.0)
   — exactly the program's HFTR band definitions. H0 is never touched. Chroma
   untouched.
2. **Alignment:** block pyramid (3 levels, normalized cross-correlation) → local
   displacement field; source bands warped to remint geometry (bilinear).
3. **Support gates, per position (all must pass):**
   a. displacement scale agreement ≤ 0.25 px between adjacent pyramid levels;
   b. residual post-alignment displacement ≤ 0.5 px in the target band;
   c. structure-tensor orientation difference ≤ 15°;
   d. signed local NCC ≥ 0.80, polarity not reversed;
   e. cross-scale persistence: support present in BOTH H1 and H2;
   f. strong-edge exclusion: dilate the strong-edge mask by
      max(2 px, 2 × effective PSF support) (structural exclusion — the ROI
      manifest is NOT shipped to the worker);
   g. energy cap: post-transfer band energy ≤ aligned source band energy; no new
      local maxima or secondary edges.
4. **Transfer:** `B' = B_remint + α · w · (B_src_aligned − B_remint)`, with
   `α ≤ 0.10` ceiling and `w ∈ [0,1]` = confidence margin from the gates.
   Same-sign scaling only — the remint's phase/orientation is never replaced.
   **Never** paste source coefficients or source pixels directly.
5. **Determinism:** no RNG anywhere in the transfer.
6. **Report block** `engine.transfer_4d_1a`: applied, alpha_requested/executed,
   coverage, mean w, per-gate reject counts, band energy ratios before/after.
7. **Auxiliary checkpoint** `O2_transfer.png` (post-transfer, pre-tone-lock) via
   the auxiliary contract — extend the whitelist in
   `deepclean-worker/tools/auxiliary_checkpoints.py` with this ONE name.
   `EXPECTED_CHECKPOINTS` stays byte-for-byte.

### 2.3 Lab-only flag

- `expert_refinement` remint block gains `4d1a: boolean` (strict; default absent).
- Runs ONLY when a validated lab seed is present AND the flag is true. Flag absent
  or false ⇒ the pipeline is byte-identical to the V12.3 incumbent (replay-proven).
- Edge boundary: invalid/absent-without-seed cases fail closed (400 edge / worker
  error), mirroring `optics_psf_scale`.
- Non-lab jobs: no transfer, no auxiliary file, zero behavior change.

## 3. Identity (frozen before first light)

- New preset id `4d-1a`, label `4D-1A — LAB · H1/H2 source transfer α≤0.10`,
  CUSTOM identity, marker `SEQ-4D1A-`, seed-dependent codes exactly like CAM-1.
- Tuple: incumbent camera settings (`optics_psf_scale` absent/1.0) + `4d1a: true`
  + the two locked seeds.
- All frozen predicates (A / 1A / 2B / 3C) and their goldens unchanged; CAM-1
  predicates unchanged. `validateOpticsPsfScale` and the 4D-CAM-1 preset are not
  modified by this round.
- Round experiment config_set: `["A", "SEQ-4D1A-<ctla1>", "SEQ-4D1A-<ctla2>"]`.

## 4. Build-time proof gates (no cell may run until all pass)

1. Transfer OFF ⇒ replay reproduces the live incumbent O2/O5 pixel hashes
   (same discipline as 4D-CAM-1 replay proof).
2. O2 identical within every B/C pair (transfer is strictly post-capture).
3. `O2_transfer.png` exists iff flag on; main O0–O5 manifest never gains a file.
4. Frozen files zero-diff: `coherent_camera.py`, `checkpoint_attribution.py`,
   `camera_only_replay.py`, `checkpoint_capture.py`, `quality_finish.py`.
5. Identity tests: preset round-trip for both seeds; four frozen goldens + CAM-1
   goldens byte-identical; new codes emitted only for the exact 4D-1a tuple.
6. Determinism: two identical runs ⇒ identical transfer hashes.
7. Fixture tests: synthetic edge fixture proves each support gate actually rejects
   (bad alignment / orientation / polarity-flip / H1-only support), reject counts
   truthful in the report block.
8. `tsc`, `vite build`, deno checks/tests, Python tests all green.

## 5. Screening round (MOCK, after proof gates)

- **32 cells**: IMG-5, 6, 9, 11 (hard subset) + IMG-1, 4, 8, 10 (morphology
  diversity) × seeds `lab-ctla1`/`lab-ctla2` × B (transfer OFF) / C (transfer ON).
- All MOCK; budget 32 × 23 = 736 privacy + 32 deepclean; vendor 0.
- Operator: Flash Max, same per-cell checks as the 4D-CAM-1 round.

### 5.1 Pre-registered acceptance gates (frozen NOW, no post-hoc changes)

1. **Provenance:** 16/16 OR pairs equal; **16/16 O2 pairs equal**; all checkpoint
   hashes verified; B codes `SEQ-CFA-*`, C codes the exact `SEQ-4D1A-*` tuple.
2. **Primary retention:** paired mean O2→O5 combined transition-loss reduction
   ≥ 25% (C vs B). *(Note: O1→O2 cannot change — transfer is post-O2. This
   replaces the O1→O2 gate from the audit response.)*
3. **Hard subset:** IMG-5/6/9/11 × both seeds, C mean O2→O5 loss ≤ 0.75 × the
   paired B mean on the same 8 cells.
4. **Delivered detail:** median O5 EATR gain ≥ 0.04 absolute; median texture-ROI
   HFTR_H1 gain ≥ 8% relative; ≥5/6 sentinel image means move in the predicted
   direction (seed-level reported explicitly).
5. **Safety:** protected EATR ≥ 0.98 × B in every pair; smooth luma/chroma RMS
   rise ≤ 5%; rho rise ≤ 0.03.
6. **Edge geometry (ESF, absolute):** median O5 mono-width increase ≤ +0.25 px;
   no pair > +0.5 px; median overshoot rise ≤ +0.02; no second signed profile
   peak > 10% of main response on any sampled edge; O2 ESF deltas within ±0.25 px
   (transfer must not move the camera-stage geometry at all).
7. **MOCK detection margin:** 16/16 C cells within ai ≤ 0.45, flux-family ≤ 0.30,
   deepfake ≤ 0.10 (screening only); no paired detector component worsens by
   more than 0.02.

### 5.2 After screening

Gates 1–7 all pass ⇒ owner decides the real-vendor leg: 6 sentinels × B/C ×
2 vendors = 24 calls (≤ 40-cap, 16 reserve). Vendor 2 freeze (TruthScan or
Sightengine) still owner-pending. A zero-vendor pass authorizes only the vendor
leg, never product adoption.

## 6. Forbidden

- No camera/PSF changes (edge audit closed that thread for this round).
- No finisher changes; no wash changes; no new wash combos; no lattice change.
- No modifications to frozen tools or `EXPECTED_CHECKPOINTS`.
- No ROI-manifest changes (measurement only; never shipped to the worker).
- No commit/deploy/RunPod/Supabase action; no vendor calls.

## 7. Audit questions for you

1. Is the support-gate set sufficient to prevent double-edges and halo on
   protected product edges at α 0.10? Which gate is weakest?
2. Is band-energy matching (no source phase, H0 excluded) the right carrier-safety
   posture, or does the real-vendor leg need an additional pre-screen?
3. Confirm or amend the O2→O5 gate re-specification (§5.1 gates 2–3) and the ESF
   edge gates (§5.1 gate 6) against the edge-audit findings.
4. Any determinism or replay-proof gap in §4?
5. Mark every threshold you cannot verify from existing measurements as a
   model estimate, with your recommended value.
6. Deliver `C8_4D_1A_BRIEF_AUDIT.md` (workspace root, untracked): accept/amend,
   reasoning per section, no code.
