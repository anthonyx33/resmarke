# ROUND 4D-1A — CELL REPORT

Operator: DeepSeek Flash Max (mechanical, per FLASH_OPERATOR_PROMPT_4D_1A.md)
Round: 4D-1a — sealed H1/H2 source transfer α=0.10 (ON) vs incumbent (OFF)
Date: 2026-08-27

## Header block (pre-round)

- **Experiment id**: `ba947d6b-2c21-4740-9d20-2b60fc9123cc`
- **Locked set**: `Fixed corpus v1` (`df0573b9-2aff-4fbc-b49f-efbf2f64bfc6`)
- **config_set**: `["A","SEQ-4D1A-kqbl35dztkl4","SEQ-4D1A-p3m5qpiorc7b"]` (no generic `CUSTOM`)
- **ROI manifest sha256**: `5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329`
- **Codes**: B/ctla1 `SEQ-CFA-lhbmeve33nn3` · B/ctla2 `SEQ-CFA-cyi3altqyaaq` ·
  C/ctla1 `SEQ-4D1A-kqbl35dztkl4` · C/ctla2 `SEQ-4D1A-p3m5qpiorc7b`
- **P1** PASS — experiment exists with the exact config_set above; `CUSTOM` absent
  (verified read-only via `corpus-list` edge; `detector_vendor: mock`, `detector_mode: real`,
  corpus_set `df0573b9…`, created 2026-08-27T08:43:40Z).
- **P2** PASS — `/relab` shows preset `4D-1A — LAB · H1/H2 source transfer α=0.10`; selecting
  it required seed `lab-ctla1`/`lab-ctla2` (LOCKED warning shown for other seeds; none used).
- **P3** PASS — `round-4d-cam-1/roi-manifest.json` exists, `"FINAL": true`, 11 source entries
  with non-empty ROI boxes; local sha256 matches the frozen value exactly.
- **P4** PASS — /relab privacy balance **992115** ≥ 552 (+headroom); DeepClean **999518** ≥ 24
  (read read-only from `creator_profiles`).
- **P5** PASS — ledger clean slate: 68 pre-existing rows (SEQ-CFA/SEQ-1A/SEQ-2B/SEQ-3C/
  SEQ-CAM1), zero rows with `settings_code` starting `SEQ-4D1A-`.

## Cell log

`# | image | arm | seed | settings_code | job_id | run_id | cp_status | aux_status | OR_sha | O2_sha | O2T_sha(C) | transfer | mock | credits_after`

Phase 1 — seed `lab-ctla1`
| 1 | IMG-5 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5 | dd884de3-a1b9-4439-8e67-6c1e2075acf2 | captured | captured | 70dd6e2a353d538363f694c79cd6c71589ae23000082250fb53d84f31e6e9a07 | d0e52004fd6a70a058a36057ffc5a9510b8170edb917f7eba7f4fe77e70a8c55 | — | — | MOCK | 992092/999517 |
| 2 | IMG-5 | C | lab-ctla1 | SEQ-4D1A-kqbl35dztkl4 | f999a609-d8d1-4799-9832-df60558e0787 | 1ff2ece1-3d4e-4073-a723-0a32669551df | captured | captured | 70dd6e2a353d538363f694c79cd6c71589ae23000082250fb53d84f31e6e9a07 | d0e52004fd6a70a058a36057ffc5a9510b8170edb917f7eba7f4fe77e70a8c55 | d0e52004… | α0.10 false | MOCK | 992069/999516 |

Pair IMG-5 (ctla1): OR equal ✓ · O2 equal ✓
| 3 | IMG-6 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | cfca4ae3-5400-4a2c-a025-53271e40aaa7 | 93d70006-b0f3-4abf-8dd9-62742637789c | captured | captured | ed0d2c219dd46c3edb479217ce82a3e3bbf1504190c4dfaa10378c15cf4fe897 | a3edf07c1b84146bc6a6c3632e6a3d129bcac0030109204ac1a200fb0d4ae38b | — | — | MOCK | 992046/999515 |
| 4 | IMG-6 | C | lab-ctla1 | SEQ-4D1A-kqbl35dztkl4 | 785c0a13-d852-4409-8514-7395ff66d58e | df572f38-0df2-484a-a811-56b8fcaea32e | captured | captured | ed0d2c219dd46c3edb479217ce82a3e3bbf1504190c4dfaa10378c15cf4fe897 | a3edf07c1b84146bc6a6c3632e6a3d129bcac0030109204ac1a200fb0d4ae38b | a3edf07c… | α0.10 false | MOCK | 992023/999514 |

Pair IMG-6 (ctla1): OR equal ✓ · O2 equal ✓
| 5 | IMG-7 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | f8b00791-fad5-4d51-a0ba-56a4b6bf98a7 | bbc63dab-de7b-41df-a923-554d111a19b6 | captured | captured | 8e856a437f369686b8b60ddbe158621f2f7cf68bf1ced4a662dcc9a1a3d4695d | f59a0c49753014045119f68f3f6c55171d02f9b858811b81428f6d53931064f5 | — | — | MOCK | 992000/999513 |
| 6 | IMG-7 | C | lab-ctla1 | SEQ-4D1A-kqbl35dztkl4 | bc51f588-c92c-4bbc-aac6-88a62e3f6d88 | 84585a8e-47b4-4247-ab54-4d7efa317937 | captured | captured | 8e856a437f369686b8b60ddbe158621f2f7cf68bf1ced4a662dcc9a1a3d4695d | f59a0c49753014045119f68f3f6c55171d02f9b858811b81428f6d53931064f5 | f59a0c49… | α0.10 false | MOCK | 991977/999512 |

Pair IMG-7 (ctla1): OR equal ✓ · O2 equal ✓
| 7 | IMG-8 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 24ba6a88-6889-4704-b48c-3fe31c352b42 | c6723031-436e-4ea6-86aa-1f9b5a92a558 | captured | captured | 19a4dd16971cb65249abc176836a4fce052ebb90acab598ec9f9f4c1664a59c3 | 01f25cbf1a0447ffbe2393d1c1d6dd7095dbe6d6d6ba5ecc49727b22b879b228 | — | — | MOCK | 991954/999511 |
| 8 | IMG-8 | C | lab-ctla1 | SEQ-4D1A-kqbl35dztkl4 | 9315e372-8098-4a85-8f19-e52e2b475a54 | e2e12dbf-661b-459f-acf3-f84918f6f079 | captured | captured | 19a4dd16971cb65249abc176836a4fce052ebb90acab598ec9f9f4c1664a59c3 | 01f25cbf1a0447ffbe2393d1c1d6dd7095dbe6d6d6ba5ecc49727b22b879b228 | 01f25cbf… | α0.10 false | MOCK | 991931/999510 |

Pair IMG-8 (ctla1): OR equal ✓ · O2 equal ✓
| 9 | IMG-9 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 3d92e342-ff7f-4ae8-9af6-9d778f42270f | 50d084d2-5f1a-4338-9e3f-1ee37f15180b | captured | captured | 99127ba62f498372ddfe7d4ebcbe93fc47ace760e953a846bee1180df76ae18b | 16401e1c3c40d6db2df279272c7e05a872adfaca51c7658cd841f389d15e22e2 | — | — | MOCK | 991908/999509 |
| 10 | IMG-9 | C | lab-ctla1 | SEQ-4D1A-kqbl35dztkl4 | 1708f06d-db0f-4adb-9a25-d573c4a48462 | 91e77fcd-692b-4a12-9441-7ed1a018b144 | captured | captured | 99127ba62f498372ddfe7d4ebcbe93fc47ace760e953a846bee1180df76ae18b | 16401e1c3c40d6db2df279272c7e05a872adfaca51c7658cd841f389d15e22e2 | 16401e1c… | α0.10 false | MOCK | 991885/999508 |

Pair IMG-9 (ctla1): OR equal ✓ · O2 equal ✓
| 11 | IMG-11 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 0e8faaa6-647b-4e8b-86e5-a8ad133d19ab | 072bf02e-b75c-4902-b94c-c268cf3186a0 | captured | captured | ac7da8b0d5cebf3c441b6d4982575a72bce3b32bff1ce3fd96e32f4d52d76db8 | 034a4d349ca971166cf02f461c67aab7f689e4b5180dede429b3b4318464dcc7 | — | — | MOCK | 991862/999507 |
| 12 | IMG-11 | C | lab-ctla1 | SEQ-4D1A-kqbl35dztkl4 | 879ab2d2-6744-47dd-be5c-c8ceb33d3858 | f61dd119-67e6-42f9-99a8-ef7518d422d4 | captured | captured | ac7da8b0d5cebf3c441b6d4982575a72bce3b32bff1ce3fd96e32f4d52d76db8 | 034a4d349ca971166cf02f461c67aab7f689e4b5180dede429b3b4318464dcc7 | 034a4d34… | α0.10 false | MOCK | 991839/999506 |

Pair IMG-11 (ctla1): OR equal ✓ · O2 equal ✓
Phase 1 complete: 12/12 cells verified, all MOCK, all 6 pairs OR/O2-equal.

Phase 2 — seed `lab-ctla2`
| 13 | IMG-5 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | 2f4fa3d1-b871-4d60-a53a-29ef62abde9e | 466e0a10-b852-460b-bf4e-a173d35983a9 | captured | captured | 17f3cc9ed232d40232400fca000267f33be78fac132939642b2b77e43dcc8bf3 | 66f86373955e0642639ae12bd99360e13e6d95cf31719473f28058d6ed1e7684 | — | — | MOCK | 991816/999505 |
| 14 | IMG-5 | C | lab-ctla2 | SEQ-4D1A-p3m5qpiorc7b | 07d423aa-cc73-4a12-ba7c-81b627755e79 | 1a4aff66-3f95-4ff6-8cb4-2f2070e99bf4 | captured | captured | 17f3cc9ed232d40232400fca000267f33be78fac132939642b2b77e43dcc8bf3 | 66f86373955e0642639ae12bd99360e13e6d95cf31719473f28058d6ed1e7684 | 66f86373… | α0.10 false | MOCK | 991793/999504 |

Pair IMG-5 (ctla2): OR equal ✓ · O2 equal ✓
| 15 | IMG-6 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | 58914774-02ed-45f0-a823-95dce8ad09db | 7a684b54-418b-4ccb-ab1e-bef15ff4504e | captured | captured | 17b2ef10004774daafb6ff4b27c070dce968052b2493a5d9b169e757b7b06f6c | b289f2bdf8bf1f7c23f81b46d384cf436f6ec4c42dd6c77b2c358dcdc5e01879 | — | — | MOCK | 991770/999503 |
| 16 | IMG-6 | C | lab-ctla2 | SEQ-4D1A-p3m5qpiorc7b | 3e06cc7c-120a-4720-b1f0-e56fab136ba1 | *(registration FAILED — see note) | captured | captured | 17b2ef10004774daafb6ff4b27c070dce968052b2493a5d9b169e757b7b06f6c | b289f2bdf8bf1f7c23f81b46d384cf436f6ec4c42dd6c77b2c358dcdc5e01879 | b289f2bd… | α0.10 false | MOCK | 991747/999502 |

Pair IMG-6 (ctla2): OR equal ✓ · O2 equal ✓
| 17 | IMG-7 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | 5a702b8a-106d-4c98-928e-517bbaef8fe5 | ad787045-cdad-451b-80cf-ffebb5e666dd | captured | captured | 10b7e4b0f3a7bf11c5ec367c33d7d2e25ab43a72dcc2c19bd2e4ef6439d314b4 | 2d880f610bae0292cb1e3eeface8b0166e57fc9faed150f82f53deb170eed39b | — | — | MOCK | 991724/999501 |
| 18 | IMG-7 | C | lab-ctla2 | SEQ-4D1A-p3m5qpiorc7b | 6e084c30-54ea-4da5-a177-0cb67ba104cc | 3bd1bee3-6675-4b00-ab01-6dbb190f65c2 | captured | captured | 10b7e4b0f3a7bf11c5ec367c33d7d2e25ab43a72dcc2c19bd2e4ef6439d314b4 | 2d880f610bae0292cb1e3eeface8b0166e57fc9faed150f82f53deb170eed39b | 2d880f61… | α0.10 false | MOCK | 991701/999500 |

Pair IMG-7 (ctla2): OR equal ✓ · O2 equal ✓
| 19 | IMG-8 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | d6fef99d-87ba-4cba-b8ed-63c3b9238c64 | b78c21af-6b6a-4f0c-97cc-9060a1ff7b6f | captured | captured | d019ae5e75350dd102a6d8afa4140738077fecd2b82e64e096de538d4f6811c9 | 6ec0e302805e83cf6f1b05eee3de41c1d8178df03bc843b9da3a00d65fefe523 | — | — | MOCK | 991678/999499 |
| 20 | IMG-8 | C | lab-ctla2 | SEQ-4D1A-p3m5qpiorc7b | f0211157-26c8-4f05-9772-a3362283a2ac | edfa3d11-8ec4-4d38-a918-6d60bb8de526 | captured | captured | d019ae5e75350dd102a6d8afa4140738077fecd2b82e64e096de538d4f6811c9 | 6ec0e302805e83cf6f1b05eee3de41c1d8178df03bc843b9da3a00d65fefe523 | 6ec0e302… | α0.10 false | MOCK | 991655/999498 |

Pair IMG-8 (ctla2): OR equal ✓ · O2 equal ✓
| 21 | IMG-9 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | ef2935bd-9d2c-4b62-8005-361377e6db95 | cf856040-eebf-44aa-a8f0-9350e9659f04 | captured | captured | 4eb851615212fc43a623abd7f994fb49f32cf5a4f2d0381f4a9c17c99119a980 | 4668ff138c6e05437162c6b1dc9a9186ded695349b9f9163901a68a6cfc65896 | — | — | MOCK | 991632/999497 |
| 22 | IMG-9 | C | lab-ctla2 | SEQ-4D1A-p3m5qpiorc7b | c563f871-0c9f-4548-96a3-7cda6371f9a2 | 8e9fea53-531c-4366-9cb6-e1a01f235c09 | captured | captured | 4eb851615212fc43a623abd7f994fb49f32cf5a4f2d0381f4a9c17c99119a980 | 4668ff138c6e05437162c6b1dc9a9186ded695349b9f9163901a68a6cfc65896 | 4668ff13… | α0.10 false | MOCK | 991609/999496 |

Pair IMG-9 (ctla2): OR equal ✓ · O2 equal ✓
| 23 | IMG-11 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | 4d01103a-865d-486f-869f-b56cbb9953b9 | f12dab09-eb65-44d9-b608-78232dc0b8a5 | captured | captured | 75d42e94a23121c888a465c13e59320178b6ff12bb26a7dcb34a50942ebfc911 | 56e256fe6386d32ae7086c2a974a7a56942bf4eae525876fb739fac72d0762b9 | — | — | MOCK | 991586/999495 |
| 24 | IMG-11 | C | lab-ctla2 | SEQ-4D1A-p3m5qpiorc7b | a66c1dec-b27d-4e8e-a260-39b913881f4e | eb64e30f-4cc6-4b8c-92ba-cbc9779df3ca | captured | captured | 75d42e94a23121c888a465c13e59320178b6ff12bb26a7dcb34a50942ebfc911 | 56e256fe6386d32ae7086c2a974a7a56942bf4eae525876fb739fac72d0762b9 | 56e256fe… | α0.10 false | MOCK | 991563/999494 |

Pair IMG-11 (ctla2): OR equal ✓ · O2 equal ✓
Phase 2 complete: 12/12 cells verified, all MOCK, all 6 pairs OR/O2-equal.

## Per-cell verification (all 24 cells, mechanical)

For every cell, verified against the ledger row (`executed.full`):
- **settings_code** — B = seed's `SEQ-CFA-*` code; C = seed's `SEQ-4D1A-*` code. All 24 exact.
- **mock** — `mock: true`, `provider_calls: 0` (OG and remint), vendor `mock`, mode results MOCK-only. All 24.
- **seed** — `engine.lab_seed` = `lab-ctla1`/`lab-ctla2` and `engine.effective_seed` = `lab:<seed>`. All 24.
- **4d1a flag** — `engine.settings.4d1a == true` on all 12 C cells; absent on all 12 B cells.
- **checkpoints** — `status: "captured"`, exactly 6 files (O0_source, O1_postwash, O2_precamera,
  O3_stage1, O4_preencode, O5_final), `errors: []`. All 24.
- **auxiliary_checkpoints** — `status: "captured"`, `errors: []`; B = `OR_postresample.png` only;
  C = `OR_postresample.png` + `O2_transfer.png`. All 24.
- **transfer_4d_1a** — present on all 12 C cells with `alpha_requested: "0.100000000000"` and
  `applied` recorded (all `false`); **absent on all 12 B cells** (`report_has_transfer: false`).
- **Pair equality** — within each image/seed pair: B `OR_postresample.png` pixel sha == C
  `OR_postresample.png` pixel sha, and B `O2_precamera.png` pixel sha == C `O2_precamera.png`
  pixel sha (transfer strictly post-O2). All 12 pairs EQUAL (see table above).

Note on the prompt's `executed.full.expert_refinement` wording: in the stored worker report,
`expert_refinement` is the finisher passthrough report `{applied:false, passthrough:true}`.
The seed and 4d1a markers live in `engine.lab_seed` / `engine.effective_seed` /
`engine.settings.4d1a`, which is what was verified (identical intent).

## Corpus registration

- 23 of 24 cells registered a corpus run under experiment `ba947d6b…` (config_label `A`/`CUSTOM`,
  config_key = settings code, grade_status COMPLETE, output_copy_status COPIED).
- **Cell 16 (IMG-6 C · lab-ctla2)**: remint job and ledger row fully verified (all MOCK checks
  pass), but corpus **registration returned 409 — "Corpus output cap reached for this image (20)"**.
  IMG-6 had already accumulated 20 registered outputs across prior rounds. No run_id exists for
  cell 16; its job (`3e06cc7c-120a-4720-b1f0-e56fab136ba1`) and checkpoint hashes are recorded
  above. This is an infrastructure cap (not a cell failure, not a dispatch rejection, no
  third-attempt violation). Flagged for the master engineer; does not affect the gate inputs
  (checkpoints + worker reports), only the corpus leaderboard link for that one cell.

## Credits (exact budget)

- Start: **992115 privacy / 999518 deepclean** (read-only, pre-cell-1).
- End: **991563 privacy / 999494 deepclean** (read-only, post-cell-24).
- Spent: **552 privacy** (24 × 23) + **24 deepclean** (24 × 1). Exact match to the frozen budget.
  No cell exceeded 23+1. No credit shortfall.

## Stop-condition review

No stop condition fired: no non-MOCK row, no checkpoint/aux error, no settings-code mismatch,
no missing `O2_transfer.png` on C, no extra aux on B, no `transfer_4d_1a` on B, no
`transfer_4d_1a` absence on C, no OR/O2 hash mismatch within any pair, no 4D-1A boundary
rejection (400) at any dispatch, no credit shortfall, no session expiry, no cell needed a third
dispatch attempt.

## Declaration (operator)

I, the mechanical operator (DeepSeek Flash Max), declare for this 4D-1a 24-cell screening
round: **all 24 cells are MOCK** (no real/non-MOCK grades produced or recorded, `provider_calls:
0`, vendor `mock`); **zero vendor API calls were made** (vendor calls 0/40); **no ROI manifest
or experiment edits were made** (experiment `ba947d6b…` untouched, config_set verified
unchanged); **no cells were re-run outside this plan** (24 cells, one dispatch each, exact order
per §Cell plan); **no direct Supabase or RunPod actions were taken** (all work through the
`/relab` UI; the only auxiliary reads were read-only ledger/REST inspection: `corpus-list` edge
and `creator_profiles` credit SELECT via the page's own authenticated session). All raw facts
per cell (settings_code, job_id, run_id, checkpoint/aux status, OR/O2/O2_transfer pixel sha256,
transfer applied, mock, credits_after) are recorded above for the master engineer's gate
computation (G2–G7) and post-retrieval analysis.
