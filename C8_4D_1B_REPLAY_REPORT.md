# C8 4D-1b Replay Report

**Decision: HARD STOP — DOWNSTREAM FIDELITY NOT PROVEN.**

This is an archived-checkpoint replay only. No live cell, detector grade, vendor call, deployment, Supabase action, or RunPod action was performed.

## Evidence and runtime

- Input/provenance checks: 191/191 passed.
- Python: `3.11.15`; Pillow: `12.3.0`; NumPy: `2.4.6`.
- Hard-stop reason: unchanged O2 did not reproduce all 36 archived O3/O4/O5 decoded-pixel hashes

## Fidelity proof

- Exact cells: **0/12**.
- Exact decoded stage hashes: **12/36** (O3/O4/O5).
- Stage split: O3 **12/12**, O4 **0/12**, O5 **0/12** exact.
- Binary fidelity gate: **FAIL**.
- Any mismatch has a per-stage signed-delta distribution in `round-4d-1b-replay/fidelity-results.json`; no tolerance was substituted.
- O4 mismatch envelope: 1,356 changed channel samples total; max `1` LSB; worst RMS `0.00924211` LSB.
- O5 mismatch envelope: 29,424 changed channel samples total; max `7` LSB; worst RMS `0.05628309` LSB.

## Candidate and Gates A–G

Not evaluated. Fidelity or an earlier prerequisite failed, so no candidate output was produced.

## Artifact record

`round-4d-1b-replay/artifact-index.json` records byte SHA-256 for every produced replay artifact (and decoded-pixel hashes for images), excluding only itself.
The edge-support artifact was not generated: fidelity failed before the candidate boundary, so candidate preparation was prohibited.

## Signed declaration

I declare that this build and report used only the pinned local archive; honored the fidelity-first and fail-closed stop rules; did not alter a frozen input; and performed none of the forbidden external or live actions.

Signed: **C88 replay builder (Codex)**  
Date: **2026-08-27 (Australia/Sydney)**
