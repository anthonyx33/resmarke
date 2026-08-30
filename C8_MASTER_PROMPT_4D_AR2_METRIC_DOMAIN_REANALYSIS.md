# 4D Architecture Reset 2 — Metric-Domain Reanalysis + Panel + Hive (4D-AR2)

Author: master engineer (D). Date: 2026-08-29. Owner GO.
Supersedes nothing; AR1 (`C8_MASTER_PROMPT_4D_AR1_MASTER_FREEZE.md`) remains the
frozen record. This commission re-analyzes AR1's §7.2 floor APPLICATION using
the existing 84 delivery-matched outputs — **zero new arm computation** — and,
if the reanalysis produces a shortlist, proceeds through the blinded panel to
a single frozen winner and the 12-call Hive leg.

**No production admission follows from AR2 alone.** A fresh holdout
validation commission (AR3) on new cells is mandatory before any production
change. Track B (Linux replay recovery) remains optional and non-blocking.

## 0. Governance of this reanalysis

This is a post-hoc change to which metrics GATE the selection. It is
authorized by the owner and pre-registered here BEFORE any panel or vendor
call, with the full AR1 measured record disclosed. Its justification is
documented metric-domain invalidity (AR1 §3 diagnostics, archived raw
profiles), NOT a desire for any arm to pass. If no arm passes the AR2 hard
gates, the funnel stops and no panel or Hive call occurs.

## 1. Unchanged from AR1 (frozen)

- Arms A0–A6, inputs, environment, encodings, and all 84 outputs
  (`round-4d-ar1/`, hash-indexed).
- All §6 measured metrics and their frozen recipes (energy/RMS ratios, EATR,
  ESF profiles, source-relative noise, staircase) — recomputed if needed
  with the SAME `round_4d_ar1_metrics.py` (frozen recipe version).
- Amendment 1 integrity rules and the A4 disposition (master-engineer
  no-shortlist judgment; A4 excluded from selection).
- Candidate selection order (AR1 §8) and the Hive leg rules (AR1 §9).

## 2. Justification (measured, from AR1)

1. **ESF profile domain.** The plateau-normalized profile metric degenerates
   on wide low-contrast transitions (10–90 width 16–21 px): worst-pair
   "overshoot" deltas 5.9–8.4 were measured where the arm's raw profile is
   closer to the source than A0's (archived profiles, e.g., IMG-5/ctla1
   edge (981,1185)). Crossing-count "second peaks" also accumulate on noisy
   ramps.
2. **Rho domain.** The rho rise ceiling (0.03) was calibrated as a
   coarse-grain guard for the 4D-1b restoration context. For stage-knockout
   arms it flags the systematic smooth-region grain/tone difference itself
   (rho2 rises +0.056–0.085) at amplitude rises inside the frozen ceilings.
3. **Overshoot context.** The +0.02/+0.03 overshoot ceilings were calibrated
   for restoration-magnitude differences. Camera-off arms apply Quality
   Finish sharpening to already-sharp content, so their ringing tradeoff is
   a candidate-level quality property to be JUDGED by the blinded panel and
   the frozen Hive table — not one a restoration-calibrated ceiling can
   adjudicate without forbidding the entire arm class.

## 3. AR2 hard gates (pre-registered; automatic)

An arm enters the panel shortlist only if ALL hold:

- **H1 integrity:** geometry and upstream pin identity (passes by
  construction; recorded), Amendment 1 rules, protected EATR ≥ 0.98 × A0
  per cell.
- **H2 amplitude:** cohort-max smooth luma rise ≤ 5% AND smooth chroma rise
  ≤ 5% (frozen source-relative recipe; A2 and A5 are expected to fail on
  their measured amplitudes — they remain measured and reported).
- **H3 second peaks (robust definition, replaces crossing-count):** at
  protected eligible edges, a second peak exists only if the raw normalized
  profile contains a local extremum beyond the primary 10–90 transition
  whose deviation from the adjacent plateau (median of the outer samples)
  exceeds **0.05 of the plateau step** AND whose position is ≥ **2 px**
  from the primary transition endpoints. Required: zero per cell. Edges
  with plateau step < 0.08 or 10–90 width outside [2, 12] px in EITHER the
  arm or A0 profile are excluded from H3 (and from the ESF overshoot
  reporting below) and listed in an exclusion table.
- **H4 no-op exclusion:** A4 remains excluded (measured no-op; disposition
  recorded in AR1).

Automatic outcomes: if the shortlist is empty, the commission stops
(fail-closed, no panel, no Hive). A2/A5 cannot enter regardless of any
other metric.

## 4. Reclassified as REPORTED (not gated; panel-judged)

For shortlisted arms only:

- smooth rho1/rho2 rises;
- ESF cohort median and worst-pair overshoot deltas on H3-eligible edges;
- ESF width-gap worsening.

These are computed with the frozen recipes and included in the panel
briefing as measured values. The panel protocol adds two mandatory
artifact-checklist items per image: "visible edge ringing" and "coarse
grain in smooth areas" (vs A0, same viewing scales). §7.3 applies: an arm
with recurring named artifacts is rejected by the panel rule.

## 5. Panel protocol (blinded, pre-registered)

- Arms: shortlist vs A0, randomized AB presentation, all 6 sentinel images,
  two viewing scales (intended mobile display size; full resolution).
- Scores: naturalness 1–5 and forced preference, separately; artifact
  taxonomy including the two mandatory items; integrity item I1
  (Amendment 1) with the source shown as reference for that item only.
- Calibration: instructions fixed in advance; reviewer agreement reported
  (pairwise agreement + count). Any arm with recurring named artifacts or
  no meaningful naturalness improvement is rejected (§7.3). Panel outcomes
  are not predetermined and are recorded as observed results.

## 6. Candidate selection (AR1 §8, unchanged)

Exactly one challenger: integrity pass → artifact-safety pass → highest
blinded naturalness → edge/texture fidelity tie-breaker → lower complexity
+ runtime final tie-breaker. Freeze the winner's exact file hashes (from
the existing AR1 outputs) and complete settings BEFORE any Hive call. No
second candidate after seeing Hive results.

## 7. Hive leg (12 calls, frozen)

- Submissions: six exact incumbent delivered files (re-fetched from
  archived job outputs, byte-hash pinned) + six exact winner files (AR1
  outputs, already hash-pinned in `round-4d-ar1/artifact-index.json`).
- Rules: `VENDOR_FREEZE_4D_1A.md` v3 (fresh-call ledger, C2PA deny-list, no
  flux key = evaluator failure, median of 3rd+4th sorted); thresholds AI
  ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10; frozen paired
  non-amplification; missing/malformed fails closed.
- Decision table (AR1 §9, unchanged): camera-off wins quality + detection ⇒
  remove O2; 4D-1b wins both ⇒ n/a (A4 excluded); codec bypass wins both ⇒
  remove the intermediate JPEG; camera-off fails detection while incumbent
  passes ⇒ decompose O2 to the minimum useful component; both fail ⇒ pivot
  to O1 wash policy and routing; no visually natural candidate ⇒ stop
  before Hive; no route clears detection ⇒ abstain — never ship the
  least-bad failure. A Hive pass proves Hive eligibility on the 12 sentinel
  cells only.

## 8. Holdout requirement (owner-mandated)

AR2's outcome is PROVISIONAL. Before any production admission: a new
commission (AR3) validates the frozen winner on fresh holdout cells (not
the 12 B cells) — live lab run with the exact frozen winner settings,
same gates, hash-indexed — plus a broader detector claim only under a
separately approved second-vendor validation. No production change from
AR2 alone, in whole or in part.

## 9. Deliverables and sequence

1. Builder implements `deepclean-worker/tools/round_4d_ar2_floors.py` +
   contract tests (new files only; frozen files zero-diff; consumes only
   `round-4d-ar1/` + frozen recipes).
2. Master engineer verifies line-by-line; operator runs it; output
   `round-4d-ar2/floors.json` + `C8_4D_AR2_SHORTLIST.md`, hash-indexed.
3. If shortlist non-empty: panel per §5; winner frozen per §6.
4. Owner + operator execute the 12-call Hive leg per §7; results interpreted
   by the frozen table; report `C8_4D_AR2_REPORT.md`.
5. AR3 holdout commission is drafted by the master engineer if the winner
   reaches the vendor-eligible branch.

Stop conditions: empty shortlist; any pin mismatch; non-finite metric;
forbidden external action in M1/M2 stages; panel non-agreement below the
reported threshold; no challenger after §7.3.
