# 4D-AR2 Master Verification and Findings (master engineer)

## Verification (line-by-line, independent)

- `round_4d_ar2_floors.py` reviewed in full against
  `C8_MASTER_PROMPT_4D_AR2_METRIC_DOMAIN_REANALYSIS.md`. H1–H4 implemented
  as frozen; profile window and normalization match the frozen ESF recipe
  (`edge_spread_audit.HALF_W = 21`, outer |x| ≥ 8, 5/95 plateau
  percentiles, isotonic, 0.1/0.9 interp); robust peak rule (strict > 0.05
  step, ≥ 2 px endpoint separation) and either-profile eligibility
  implemented as frozen; exclusion tables complete; reported-only metrics
  separated; empty-shortlist fail-closed; atomic writes; overwrite refusal;
  no network, no RNG.
- Tests independently green: 19/19 AR2, 13/13 AR1, 12/12 legacy (44/44).
- Preflight: 728/728 frozen checks pass; AR1 index pin unchanged
  (`01a51382…d9d4c20`); frozen files zero-diff.
- Delivery hashes match the builder's declaration exactly.

## Result (frozen rules, fail-closed)

`status: EMPTY_SHORTLIST_STOP_NO_PANEL_NO_HIVE`. No panel was run; no
candidate was frozen; no Hive call is authorized.

| Arm | H1 | H2 | H3 | H4 | Shortlist |
|---|---|---|---|---|---|
| A1 | PASS | PASS | FAIL (15 peak edges / 74 peaks on 16 eligible edges) | PASS | NO |
| A2 | PASS | FAIL (chroma +8.7%) | FAIL | PASS | NO |
| A3 | PASS | FAIL (chroma +6.7%) | FAIL | PASS | NO |
| A4 | PASS | PASS | FAIL (A0-inherited peaks) | FAIL (no-op exclusion) | NO |
| A5 | PASS | FAIL (luma +10.4%) | FAIL | PASS | NO |
| A6 | PASS | PASS | FAIL (15 / 77 on 16 eligible edges) | PASS | NO |

H3 domain accounting: most protected edges fall outside the stable domain
(227–263 excluded per arm, 13–55 eligible). Reported (not gated) ESF on
eligible edges: A1 median overshoot delta 0.0526 / worst 1.872, median
width-gap −0.0177 px (A1 narrower than A0 vs source); A6 0.0945 / 1.899,
+0.0126 px.

## Findings for any future commission (new freeze required)

1. H3 as frozen counts arm-absolute peaks; A4 ≡ A0 carries 230 such peaks,
   showing many are inherited from A0's own QF ringing, not
   candidate-created. A difference-based peak rule would require a new
   pre-registered freeze.
2. No minimum eligible-edge floor was frozen for H3 (the eligible
   populations are small: 13–55 edges per arm across 12 cells).
3. The energy findings stand unchanged: the camera ladder is the dominant
   quality cost (0.362 → 0.947/1.093 without it).

## Disposition

AR2 stops per its own frozen rules. No panel, candidate, or Hive action.
The 84 AR1 outputs, AR1 record, and AR2 floors artifacts remain
hash-indexed. Production admission was never authorized by AR2 alone in any
case. Track B remains optional and non-blocking.
