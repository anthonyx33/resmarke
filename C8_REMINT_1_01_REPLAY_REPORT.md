# C8 ReMint 1.01 Replay Report

**Status: HARD STOP — 1.01 REMAINS NON-PRODUCTION.**

## Contract

ReMint 1.01 is Config A with `output_target=1800`; wash process cap remains 1536. This report is offline-only and makes no production or detector claim.

## Preset build

- `/remint` and `/relab` expose the exact ReMint 1.01 tuple; Config A remains the default/incumbent.
- Unseeded marker: `SEQ-1.01-sywgbtfbjwhg`.
- `lab-ctla1`: `SEQ-1.01-yg63qja3got4`; `lab-ctla2`: `SEQ-1.01-vzz7jbtvmvly`.
- Existing goldens remain `SEQ-CFA-dtbnbygm5iao`, `SEQ-1A-3lzgvffda5xf`, `SEQ-2B-zzz2dudlbywp`, and `SEQ-3C-brgbola74zqg`.
- The request client emits `output_target` only when non-null in V8.8, V8.9, and V8.9-HD remint blocks; it does not expose or emit `regen_process_cap`.
- The build contract's tracked-file prohibition conflicts with its required preset surfaces. The preset requirement controls; no AR1-pinned frozen file changed.

## Frozen input verification

- Frozen archive checks: **291/291 passed**.
- External calls, grading, deploys, commits, and live cells: **none**.

## A0-1250 calibration

- Cells: **12/12**.
- Cohort `h1_energy_ratio`: **0.361715423**.
- Required: `0.362 ± 0.001`.
- Verdict: **PASS**.

| Image | Seed | Job | H0 energy | H1 energy | H2 energy | EATR p95 |
|---|---|---|---:|---:|---:|---:|
| IMG-5 | lab-ctla1 | `e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5` | 0.071298 | 0.398670 | 0.826087 | 0.568833 |
| IMG-6 | lab-ctla1 | `cfca4ae3-5400-4a2c-a025-53271e40aaa7` | 0.158630 | 0.450413 | 0.629826 | 0.661841 |
| IMG-7 | lab-ctla1 | `f8b00791-fad5-4d51-a0ba-56a4b6bf98a7` | 0.081225 | 0.266015 | 0.813031 | 0.502815 |
| IMG-8 | lab-ctla1 | `24ba6a88-6889-4704-b48c-3fe31c352b42` | 0.103105 | 0.276841 | 0.659643 | 0.578409 |
| IMG-9 | lab-ctla1 | `3d92e342-ff7f-4ae8-9af6-9d778f42270f` | 0.096487 | 0.333277 | 0.830287 | 0.592245 |
| IMG-11 | lab-ctla1 | `0e8faaa6-647b-4e8b-86e5-a8ad133d19ab` | 0.231673 | 0.416749 | 0.708844 | 0.660543 |
| IMG-5 | lab-ctla2 | `2f4fa3d1-b871-4d60-a53a-29ef62abde9e` | 0.072921 | 0.404295 | 0.829772 | 0.577068 |
| IMG-6 | lab-ctla2 | `58914774-02ed-45f0-a823-95dce8ad09db` | 0.163946 | 0.468069 | 0.653180 | 0.671600 |
| IMG-7 | lab-ctla2 | `5a702b8a-106d-4c98-928e-517bbaef8fe5` | 0.085693 | 0.279274 | 0.840695 | 0.510506 |
| IMG-8 | lab-ctla2 | `d6fef99d-87ba-4cba-b8ed-63c3b9238c64` | 0.103176 | 0.277810 | 0.685392 | 0.584552 |
| IMG-9 | lab-ctla2 | `ef2935bd-9d2c-4b62-8005-361377e6db95` | 0.100709 | 0.346179 | 0.853569 | 0.606070 |
| IMG-11 | lab-ctla2 | `4d01103a-865d-486f-869f-b56cbb9953b9` | 0.237389 | 0.422995 | 0.725217 | 0.668176 |

## Hard stop

`ValidationStop: exact camera replay provenance is absent for 12/12 cells; required fields are the selected attempt/rung and raw creator_id`

No 1800 metric is reported because the camera stage cannot be reproduced from the pinned archive without inventing provenance.

## Artifact record

`round-remint-1-01/artifact-index.json` hashes every produced artifact and this report, excluding only the index itself.

## Declaration

I declare that this validator used only the pinned local archive, changed no frozen threshold after execution, fabricated no camera setting or identity, and performed no forbidden external action.

Signed: **C8 builder (Codex) · 2026-08-30T00:58:05+10:00**
