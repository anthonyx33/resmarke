# C8 4D-AR1 Report

**Status: M1 FACTORIAL COMPLETE — AWAITING MASTER-ENGINEER M2.**

This report covers the offline M1 factorial execution only. M2 metrics, quality gates, panel results, candidate selection, detector results, production admission, and Track B are not evaluated here.

## Execution record

- Frozen B cells processed: **12/12**.
- Frozen A0-A6 delivered outputs completed: **84/84**.
- Environment: `$TMPDIR/verify3` with Python 3.9.6, NumPy 2.0.2, Pillow 11.3.0.
- External/live actions: **none**. No cell, grading, vendor, Supabase, RunPod, commit, or deploy action is present in this harness.

## Artifact record

`round-4d-ar1/artifact-index.json` hashes every produced artifact and this report, excluding only the index itself.

## Builder declaration

I declare that this harness used only the pinned local archive, executed exactly A0-A6, preserved the frozen factors and settings, and performed none of the forbidden external actions.

Signed: **C88 builder (Codex)**  
Commission date: **2026-08-29 (Australia/Sydney)**

---

## Master-engineer addendum (2026-08-29, post-M2)

The M1 factorial above is complete as signed. M2 metrics were computed,
audited twice by the builder, corrected to the frozen source-relative
recipes, and hash-indexed (`round-4d-ar1/m2-results.json`,
`round-4d-ar1/artifact-index.json`). Outcome: all five structural arms fail
the frozen §7.2 floors; A4 passes the floors but is rejected for challenger
selection under §7.3 (measured no-op: 11/12 delivered cells identical to
A0). No panel, candidate freeze, or Hive calls are authorized. See
`C8_4D_AR1_M2_SUMMARY.md` (v3) and `C8_4D_AR1_AMENDMENT_2_METRIC_DOMAIN.md`
(withdrawn).
