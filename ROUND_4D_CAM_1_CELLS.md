# ROUND 4D-CAM-1 — CELL REPORT

Operator: DeepSeek Flash Max (mechanical, per FLASH_OPERATOR_PROMPT_4D_CAM_1.md)
Date: 2026-08-26

## Header block (pre-round)

- **Round experiment id**: `a137ce61-8a42-49f4-abe4-9e22b19300df`
- **Locked set**: `Fixed corpus v1`
- **ROI manifest sha256**: `5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329`
- **P1** PASS — experiment exists; `config_set` = `["A","SEQ-CAM1-7ltwtryshnga","SEQ-CAM1-w4kwip3no7g4"]`; `CUSTOM` absent.
- **P2** PASS — five presets incl. `4D-CAM-1 — LAB · Gaussian radii ×0.50`; sentinels eyeballed: IMG-7 = smooth rendered wall/sky/light gradient; IMG-8 = high-texture timber/decking/architecture.
- **P3** PASS — `round-4d-cam-1/roi-manifest.json` exists, `"FINAL": true`, 11 source entries with non-empty ROI boxes; sha256 matches frozen value.
- **P4** PASS — /relab credits: privacy 992943 ≥ 782; DeepClean 999554 ≥ 34.
- **P5** PASS — ledger clean slate for round: 33 existing pilot rows (SEQ-CFA/SEQ-1A/SEQ-2B/SEQ-3C), zero rows with `settings_code` starting `SEQ-CAM1-`.

### Deployment-fault interruption (owner-authorized re-run)

- **Failed cell**: `IMG-1 C` (Cell 2). Dispatch hit a 409 deployment fault (worker functions
  out of sync); no ledger row was ever written for it. Confirmed from ledger: row count 34,
  last row = verified IMG-1 B, no `SEQ-CAM1-*` rows exist. The failed C deepclean job
  `c1d291bb-c5c2-4117-83d3-ca1dae3dc294` (output name `SEQ-CAM1-7ltwtryshnga.JPG`) is
  recorded as `failed` / "Cancelled before GPU processing completed." with `credits_charged: 0`
  (its 1 deepclean reserve was released).
- **Owner instruction**: deployment fault fixed by owner; re-run the failed cell fresh.
  Because the failed cell was **IMG-1 C**, the sequence is **IMG-1 B first, then IMG-1 C**.
  Both are re-run fresh under the fixed deployment (master-engineer-authorized repeat, per
  prompt §0 hard rule 4 exception).
- The pre-fault IMG-1 B row (job `3efe62e2-4640-411a-abb2-f0eed2a27bb4`, run
  `e5431279-f46e-4ceb-a578-562649e3d85e`) is superseded by the fresh re-run below and is
  not counted in this round's paired comparison.
- **Stale-tab orphan job (noted, not part of this round)**: during the fresh re-run, the
  second open `/relab` tab (leftover from the interrupted pilot) auto-dispatched a leftover
  **Config 3C / IMG-11** job `c8113e4d-0855-4d52-8cfc-2b2f8fac0a1e`
  (`SEQ-3C-brgbola74zqg.JPG`, completed 13:29:42, `credits_charged: 1`). It produced NO
  ledger row and NO corpus run for this round. It spent 23 privacy + 1 DeepClean from the
  shared profile (server: 992920→992897 / 999553→999552). That tab is now idle (queue 0/20).
  This is outside the 4D-CAM-1 cell plan and is reported for credit reconciliation only.

## Cell log

`# | image | arm | seed | settings_code | job_id | run_id | cp_status | OR_sha | mock | credits_after`

| 1 | IMG-1 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | acc7276f-4891-4b45-b878-be9c936f139c | e5f858f7-c3b0-40e3-a440-0881ac029fce | captured | 1e9dea303ca7b5cbbf49c0006d2cde9d2c6f9051721c4af45dfb5818425a6e1b | MOCK | 992874/999551 |
| 2 | IMG-1 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 80dd1c67-a096-484d-958f-caf90404fcd0 | 3200e911-f19c-434b-b691-3a2f81d4bc2d | captured | 1e9dea303ca7b5cbbf49c0006d2cde9d2c6f9051721c4af45dfb5818425a6e1b | MOCK | 992851/999550 |

Pair IMG-1 (ctla1): B OR sha `1e9dea30…` = C OR sha `1e9dea30…` → EQUAL ✓ (optics_psf_scale B=1, C=0.5).
| 3 | IMG-2 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 4f0cc6fa-c135-4128-a1b1-11138368ff9f | a141fad6-0bc9-41c3-92d9-3c1a317e33a2 | captured | afd5b94de8ff93edd45535c7c4be15131260e0617b8709ced8a6e2f9a881ec6d | MOCK | 992828/999549 |
| 4 | IMG-2 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 0cc09705-1956-4b61-8154-f3286cc32c6b | aec53d05-bd5c-4713-8b53-fa5e6ad35b8d | captured | afd5b94de8ff93edd45535c7c4be15131260e0617b8709ced8a6e2f9a881ec6d | MOCK | 992805/999548 |

Pair IMG-2 (ctla1): B OR `afd5b94d…` = C OR `afd5b94d…` → EQUAL ✓ (optics B=1, C=0.5).
| 5 | IMG-3 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 83639c9a-4b6a-41e2-bd5c-49fe0b3d31df | cf52b6c1-6212-4de4-8a07-f01ad49b3c7d | captured | e7f4941543cbee0ec63f4168c1cb39a4dfadf35089335929ae787b49e35beed1 | MOCK | 992782/999547 |
| 6 | IMG-3 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 30004fb3-ff55-4d7c-8132-c7a6809b0b3f | 561071e5-0b76-49ed-8eaf-705c85f08949 | captured | e7f4941543cbee0ec63f4168c1cb39a4dfadf35089335929ae787b49e35beed1 | MOCK | 992759/999546 |

Pair IMG-3 (ctla1): B OR `e7f49415…` = C OR `e7f49415…` → EQUAL ✓ (optics B=1, C=0.5).
| 7 | IMG-4 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 0376d4b3-fe1f-4c30-854a-c021353e9a76 | de029053-fb0f-423d-85b8-27b2150ffc6a | captured | 5d1ba6bb2802616582a8a4652a4f8be7490f6d16ae89d58896ee32151a483f40 | MOCK | 992736/999545 |
| 8 | IMG-4 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | b2fce72c-b2d1-4dca-a5c2-4ac9aa8525bb | 14a60b9c-f24e-40d5-955f-54ea5a5fff16 | captured | 5d1ba6bb2802616582a8a4652a4f8be7490f6d16ae89d58896ee32151a483f40 | MOCK | 992713/999544 |

Pair IMG-4 (ctla1): B OR `5d1ba6bb…` = C OR `5d1ba6bb…` → EQUAL ✓ (optics B=1, C=0.5).
| 9 | IMG-5 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | cdc39738-3f0c-4260-809d-12b60854acd5 | 8f958347-d3c1-4fc8-93ff-d8ab1de254ea | captured | 70dd6e2a353d538363f694c79cd6c71589ae23000082250fb53d84f31e6e9a07 | MOCK | 992690/999543 |
| 10 | IMG-5 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 289a3098-2963-4a7e-b320-85affda102f6 | 1c72b2f1-74f3-46e1-b395-d9d7365b76af | captured | 70dd6e2a353d538363f694c79cd6c71589ae23000082250fb53d84f31e6e9a07 | MOCK | 992667/999542 |

Pair IMG-5 (ctla1): B OR `70dd6e2a…` = C OR `70dd6e2a…` → EQUAL ✓ (optics B=1, C=0.5).
| 11 | IMG-6 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | fb8e1d63-bcc8-4a4f-a770-34be1d9ee62d | 6b55551f-2580-4d2c-ac91-a3ac7077ad3f | captured | ed0d2c219dd46c3edb479217ce82a3e3bbf1504190c4dfaa10378c15cf4fe897 | MOCK | 992644/999541 |
| 12 | IMG-6 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 132fb974-2891-4c6c-8327-076316bd1aee | 02391e5a-2153-47f7-9a52-7bae723b0894 | captured | ed0d2c219dd46c3edb479217ce82a3e3bbf1504190c4dfaa10378c15cf4fe897 | MOCK | 992621/999540 |

Pair IMG-6 (ctla1): B OR `ed0d2c21…` = C OR `ed0d2c21…` → EQUAL ✓ (optics B=1, C=0.5).
| 13 | IMG-7 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | b5bdd673-1fef-4cb5-80b6-946900e0331a | c2c264a7-2efd-4083-94a4-4b68dcffc930 | captured | 8e856a437f369686b8b60ddbe158621f2f7cf68bf1ced4a662dcc9a1a3d4695d | MOCK | 992598/999539 |
| 14 | IMG-7 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | b7093a06-853e-4acd-86d6-8116bba90cba | e9f175df-2ce8-42b8-8517-34cdd167bde2 | captured | 8e856a437f369686b8b60ddbe158621f2f7cf68bf1ced4a662dcc9a1a3d4695d | MOCK | 992575/999538 |

Pair IMG-7 (ctla1): B OR `8e856a43…` = C OR `8e856a43…` → EQUAL ✓ (optics B=1, C=0.5).
| 15 | IMG-8 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | b7c88690-6e2d-4b83-8d5c-27597c22c329 | de925b6e-d879-4dd7-a811-36b4be7c2c85 | captured | 19a4dd16971cb65249abc176836a4fce052ebb90acab598ec9f9f4c1664a59c3 | MOCK | 992552/999537 |
| 16 | IMG-8 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 9dbf0b85-01d2-4284-a8ac-652777f2f037 | d176401e-709a-4cad-aac0-e50c3a001541 | captured | 19a4dd16971cb65249abc176836a4fce052ebb90acab598ec9f9f4c1664a59c3 | MOCK | 992529/999536 |

Pair IMG-8 (ctla1): B OR `19a4dd16…` = C OR `19a4dd16…` → EQUAL ✓ (optics B=1, C=0.5).
| 17 | IMG-9 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 88cfd748-679e-4a01-8d7a-d380e61f6ba6 | 45b59b51-41b5-416c-b324-0bd2deab4924 | captured | 99127ba62f498372ddfe7d4ebcbe93fc47ace760e953a846bee1180df76ae18b | MOCK | 992506/999535 |
| 18 | IMG-9 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 615e71ca-1d8f-434a-80c3-2f3c4e06f944 | 31d0513e-ce2a-4bf3-bf29-d9c5f783cc60 | captured | 99127ba62f498372ddfe7d4ebcbe93fc47ace760e953a846bee1180df76ae18b | MOCK | 992483/999534 |

Pair IMG-9 (ctla1): B OR `99127ba6…` = C OR `99127ba6…` → EQUAL ✓ (optics B=1, C=0.5).
| 19 | IMG-10 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 22c02cef-8ec5-4231-97c3-27094518fc5b | 6eeefe6a-fedb-4e3e-ab14-fcc7e29179a6 | captured | 07b5417f3bbddee63c4e812c4cc3dbc7888f85c1f2bf94b463f8ffbc06906bb5 | MOCK | 992460/999533 |
| 20 | IMG-10 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 198cb8f0-3786-4c56-8b8c-c06a477bd5ac | e26563cf-5f39-4e6c-b531-ac00cb7ad6cc | captured | 07b5417f3bbddee63c4e812c4cc3dbc7888f85c1f2bf94b463f8ffbc06906bb5 | MOCK | 992437/999532 |

Pair IMG-10 (ctla1): B OR `07b5417f…` = C OR `07b5417f…` → EQUAL ✓ (optics B=1, C=0.5).
| 21 | IMG-11 | B | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | 33c5b63b-5b07-4f00-a796-0323d1ff29f3 | 0fc5566d-328d-4fec-a2c5-eb846b11a121 | captured | ac7da8b0d5cebf3c441b6d4982575a72bce3b32bff1ce3fd96e32f4d52d76db8 | MOCK | 992414/999531 |
| 22 | IMG-11 | C | lab-ctla1 | SEQ-CAM1-7ltwtryshnga | 68e7a402-effe-4f16-9751-04ab30214178 | 78662c62-70dd-4693-aa08-ca932a5e038d | captured | ac7da8b0d5cebf3c441b6d4982575a72bce3b32bff1ce3fd96e32f4d52d76db8 | MOCK | 992391/999530 |

Pair IMG-11 (ctla1): B OR `ac7da8b0…` = C OR `ac7da8b0…` → EQUAL ✓ (optics B=1, C=0.5).
Phase 1 complete: 22/22 cells verified, all MOCK, all pairs OR-equal.
| 23 | IMG-5 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | 5bd6bc05-5763-4c45-b709-b2ecedab38c2 | a6aa08b9-558e-4a94-b1c1-25118496521c | captured | 17f3cc9ed232d40232400fca000267f33be78fac132939642b2b77e43dcc8bf3 | MOCK | 992368/999529 |
| 24 | IMG-5 | C | lab-ctla2 | SEQ-CAM1-w4kwip3no7g4 | c5064e1a-a4ca-4e1e-b403-0445212732ea | 7073fc10-945e-4172-b84f-4249c601d7d8 | captured | 17f3cc9ed232d40232400fca000267f33be78fac132939642b2b77e43dcc8bf3 | MOCK | 992345/999528 |

Pair IMG-5 (ctla2): B OR `17f3cc9e…` = C OR `17f3cc9e…` → EQUAL ✓ (optics B=1, C=0.5).
| 25 | IMG-6 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | ebd7f10c-538a-49c9-b3b3-c77e0771e5fa | 2fbf596a-32b6-4fb1-8149-32a5aecee788 | captured | 17b2ef10004774daafb6ff4b27c070dce968052b2493a5d9b169e757b7b06f6c | MOCK | 992322/999527 |
| 26 | IMG-6 | C | lab-ctla2 | SEQ-CAM1-w4kwip3no7g4 | 4510c2a2-a706-45e5-b5ae-6cf118308f30 | 14dcef75-8bbd-4944-a9e7-6fadb277e274 | captured | 17b2ef10004774daafb6ff4b27c070dce968052b2493a5d9b169e757b7b06f6c | MOCK | 992299/999526 |

Pair IMG-6 (ctla2): B OR `17b2ef10…` = C OR `17b2ef10…` → EQUAL ✓ (optics B=1, C=0.5).
| 27 | IMG-9 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | f1e03428-3a1e-4c0d-9626-7c2f4220a770 | 2d5a651f-fcea-4a78-a7cf-717c0b00d85f | captured | 4eb851615212fc43a623abd7f994fb49f32cf5a4f2d0381f4a9c17c99119a980 | MOCK | 992276/999525 |
| 28 | IMG-9 | C | lab-ctla2 | SEQ-CAM1-w4kwip3no7g4 | e044e337-b2db-45f9-ada2-411d7bddfb0b | f30ceb98-1ba9-4e5e-a351-5325f94afef8 | captured | 4eb851615212fc43a623abd7f994fb49f32cf5a4f2d0381f4a9c17c99119a980 | MOCK | 992253/999524 |

Pair IMG-9 (ctla2): B OR `4eb85161…` = C OR `4eb85161…` → EQUAL ✓ (optics B=1, C=0.5).
| 29 | IMG-11 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | 963c40d7-4ea5-4fe4-a56e-fc84fbd97dd6 | 3dd3140a-2dbd-4339-b701-1d44cf4a0d50 | captured | 75d42e94a23121c888a465c13e59320178b6ff12bb26a7dcb34a50942ebfc911 | MOCK | 992230/999523 |
| 30 | IMG-11 | C | lab-ctla2 | SEQ-CAM1-w4kwip3no7g4 | 7a4ab192-da0f-43b3-b84c-b87db6e6ed85 | e4341d5e-560f-49ea-b4a0-ff71bb5c727a | captured | 75d42e94a23121c888a465c13e59320178b6ff12bb26a7dcb34a50942ebfc911 | MOCK | 992207/999522 |

Pair IMG-11 (ctla2): B OR `75d42e94…` = C OR `75d42e94…` → EQUAL ✓ (optics B=1, C=0.5).
| 31 | IMG-7 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | c526e593-4a41-409e-8700-e6e825939409 | 36a52cfd-fd59-43b4-b9d7-834cadda48c2 | captured | 10b7e4b0f3a7bf11c5ec367c33d7d2e25ab43a72dcc2c19bd2e4ef6439d314b4 | MOCK | 992184/999521 |
| 32 | IMG-7 | C | lab-ctla2 | SEQ-CAM1-w4kwip3no7g4 | 8dc8fe05-78bc-46bf-a4ab-08578db3aca1 | 1522ea72-bdc5-4fd0-ba8b-6e83f5c0044e | captured | 10b7e4b0f3a7bf11c5ec367c33d7d2e25ab43a72dcc2c19bd2e4ef6439d314b4 | MOCK | 992161/999520 |

Pair IMG-7 (ctla2): B OR `10b7e4b0…` = C OR `10b7e4b0…` → EQUAL ✓ (optics B=1, C=0.5).
| 33 | IMG-8 | B | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | ded27f0f-011d-49ce-93a3-cf4e1c0d1b00 | 2e726530-d657-44b9-88c9-afd7e831c2bc | captured | d019ae5e75350dd102a6d8afa4140738077fecd2b82e64e096de538d4f6811c9 | MOCK | 992138/999519 |
| 34 | IMG-8 | C | lab-ctla2 | SEQ-CAM1-w4kwip3no7g4 | a29528bb-5b3e-4317-86e2-8907718d0aaa | 51cc00ef-71be-4c4b-b1ca-834a46c7ded9 | captured | d019ae5e75350dd102a6d8afa4140738077fecd2b82e64e096de538d4f6811c9 | MOCK | 992115/999518 |

Pair IMG-8 (ctla2): B OR `d019ae5e…` = C OR `d019ae5e…` → EQUAL ✓ (optics B=1, C=0.5).
Phase 2 complete: 12/12 cells verified, all MOCK, all pairs OR-equal.

## Round completion — 34/34 cells

- **Phase 1** (22 cells, seed `lab-ctla1`): IMG-1..IMG-11 × (B then C), all MOCK, all
  `checkpoints`/`auxiliary_checkpoints` captured with errors `[]`, all B/C OR sha equal.
- **Phase 2** (12 cells, seed `lab-ctla2`): IMG-5, IMG-6, IMG-9, IMG-11, IMG-7, IMG-8 ×
  (B then C), all MOCK, all checkpoints captured, all B/C OR sha equal.
- Credits: privacy 992920 → **992115** (−805 = 34×23 + 23 orphan job), DeepClean 999553 →
  **999518** (−35 = 34 + 1 orphan job). No cell cost was exceeded.
- No stop condition fired (no non-MOCK row, no checkpoint/aux failure, no settings-code
  mismatch, no B/C OR-hash mismatch, no credit shortfall, no session expiry).

### Declaration (operator)

I, the mechanical operator (DeepSeek Flash Max), declare for this 4D-CAM-1 34-cell
screening round: **no real (non-MOCK) grades were produced or recorded**; **no vendor API
calls were made** (all grades MOCK, `provider_calls: 0`, `vendor: "mock"`); **no ROI
manifest or experiment edits were made**; **no cells were re-run beyond the single
owner-authorized IMG-1 B/C re-run**; **no direct Supabase or RunPod actions were taken**
(all work was through the /relab UI and read-only ledger/REST inspection). All raw facts
are recorded above for the master engineer's paired fixed-rung analysis.

