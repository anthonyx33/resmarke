# REMINT MASTER PLAN — post full-matrix (2026-09-03)

Owner-facing roadmap. Ordered. Every phase has a gate; nothing proceeds
past a failed gate.

## Where we are

- Real-only measurement regime is live: Hive g1 grades, SlashBase results
  page, no-caps (GRADE_SESSION_CAP=10000), frozen quality recipes
  (reproduce archived floors bit-exact).
- The 5-preset × 11-image matrix is complete, independently verified, and
  published in analysis. **No preset promotes** (best: Config A, 4/11 v3).
- C88's consultation is accepted: surviving signal is L2–L4; stage-1 Q92
  encoding is a measured signal-destruction stage (+15.1 pts vs Q97);
  camera ladder is the measured fidelity cost. S1-slim is the frozen next
  experiment.
- S1-slim ledger tool is BUILT and MASTER-VERIFIED (37/37 tests,
  194/194 preflight pins, freeze addendum applied for real-payload
  compatibility).

## The roadmap

**M0 — Deploy the matrix SlashBase** (now)
Commit + push the 5-preset SlashBase wiring (55 cards, 110 real rows).
Gate: site live with preset filters populated. Owner action only if push
fails.

**M1 — Run the S1-slim stage ledger** (next, frozen)
Flash executes `FLASH_OPERATOR_PROMPT_4D_S1_SLIM.md`: 15 fresh real calls
grading archived O1/OR/O2 bytes for IMG-5/6/7/8/9/11. Master engineer
runs the interpreter → `stage-deltas.json` + `decision.json` → report.
Gate: exactly one decision-table row emitted. No engineering during the leg.

**M2 — Execute the stage decision** (branches, ordered by S1 output)
- Camera ladder removal / minimum strength — if wash clears and camera is
  not material. (AR2 quality gates govern the challenger.)
- Camera sub-step decomposition — if wash fails but O2 clears and camera
  is material.
- Wash-policy / photo-naturalization / stage-order — if O1 and O2 both fail.
- Resample dead weight or detection-essential — per materiality.
Every branch: new freeze, C88 build, master verification, real-grade
validation, NO production claim.

**M3 — Candidate freeze and promotion battery**
Once a stage change passes S1 + AR2 quality: freeze a new candidate preset
(e.g., `Config D = A − camera, stage-1 Q92`), run the 11-image corpus with
real grading (OG grades reuse), apply v3 thresholds + non-amplification +
quality floors. Promotion only on full pass.

**M4 — SlashBase as the single results surface**
Every new arm lands as a preset row on SlashBase (real-only, fail-closed).
No mock row ever enters.

**M5 — Hygiene (parallel, non-blocking)**
- Reconcile the one stale legacy Python contract (84/85) or re-freeze it.
- 4D-1b runtime reproduction on the archived image (RunPod) — closes the
  fidelity-replay question.
- Pin Hive model/version per leg (currently v1); monitor for drift.

## Budgets and governance (fixed)

- S1-slim: 15 fresh vendor calls, zero remint credits. Hard stop.
- Every future grade: real g1 only, verbatim ledger, C2PA deny-list,
  session in a fresh tab, cap 10000.
- Quality challengers must clear AR2 frozen gates; detection challengers
  must clear v3 thresholds on the full corpus; routing needs a holdout.
- Frozen recipes and archives are append-only; nothing is re-graded with
  mock, ever.

## Decision gate summary

| Gate | Passes only if |
|---|---|
| S1-slim leg | 15 fresh + 3 verbatim rows, no stops |
| Stage edit | decision-table branch + AR2 quality gates |
| Candidate freeze | master verification + frozen settings code |
| Promotion | full-corpus v3 pass + non-amplification + floors |
| SlashBase entry | real g1, verified, fail-closed import |
