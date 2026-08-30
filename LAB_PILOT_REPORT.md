# C8 Laboratory Pilot Report — V12.3

Date: 2026-08-26 (Australia/Sydney)  
Build under test: `c569595`  
Outcome: **ALL 32 GRID CELLS COMPLETE + REGISTERED — SEED PATH, CHECKPOINT CAPTURE, AND CODE INVARIANTS VERIFIED (master engineer, Aug 26 + C8 continuation)**

## Grid completion summary

C8 took over the authenticated `/relab` session (`anthonyx33@proton.me`, 993656 privacy credits at takeover, vendor 0/40) after the master engineer's cell-1 first light passed all §6 criteria. Cells 2–32 were then operated by C8 through the deployed browser UI only, one image per queue load, per §3 order (IMG-6 → IMG-5 → IMG-9 → IMG-11, each A→1A→2B→3C × a1→a2, with cell 2 = IMG-6 · 3C · lab-ctla1 run second as the P4 gate).

- **32/32 authorized cells completed** with a UI-visible ledger row, grade COMPLETE (all MOCK), and corpus registration (`registered · <run-id>` shown in the queue for every cell).
- **P4 gate (cell 2) PASSED**: 3C run registered with run `85278042-8…` — no 409 CUSTOM/outside-set and no 500, proving `corpus-run-intent` (with the config-3C migration) is live.
- **Cell 1 first light (master engineer)** PASSED all §6 criteria (re-run `7ef9b02c-0c53-4a87-be07-df7d07924cc1`; checkpoints captured O0–O5; `lab_seed=lab-ctla1`, `effective_seed=lab:lab-ctla1`; MOCK CLEAR).
- **Stop conditions:** none fired. No `Invalid bearer token` was re-encountered; the corpus picker opened cleanly with all 11 locked-set images and experiment `8dae1ae2-5248-426d-a5b2-a66a781dbba8` selected throughout.
- **Vendor spend:** 0/40 vendor calls (every ledger row `provider_calls=0`, `session_usage.vendor_calls=0`, `mock:true`).
- **Credits:** observed end balance **992943 privacy**; C8 session delta 993656 → 992943 = 713 (31 cells × 23, cells 2–32). Combined with the master engineer's cell-1 spends the 32-cell grid consumed 33 job dispatches × 23 = 759 privacy (incl. the superseded pre-env cell-1 dispatch documented below).

## Stop condition

> Historical record of the preflight stop that preceded the first-light and the 32-cell run (now resolved). No current stop condition is active — the grid completed.

The initial browser session was signed out. The owner then signed in as `anthonyx33@proton.me`, and the authenticated `/corpus` admin UI became available. Exactly one new experiment was created with corpus set **Fixed corpus v1**, engine release `comfyui+remarkee-max-v2 template=8eaf9320f143`, detector vendor **mock**, detector mode **real**, and the console's V12.3 default config set. Its experiment ID is `8dae1ae2-5248-426d-a5b2-a66a781dbba8`, and it was selected in the History experiment filter.

The owner subsequently issued GO with all deployment confirmations complete: P0 and `LAB_FIXED_SEED_ENABLED=1` hash-verified, migration `20260827000000_config_3c` applied, `create-deepclean-job` and `corpus-run-intent` redeployed, the required worker image and checkpoint environment linked, worker ready/idle with a clean 132-second boot warmup and successful runtime self-check, and balances confirmed at **999588 DeepClean / 993725 privacy**.

After GO, `/relab` remained visibly signed in as `anthonyx33@proton.me` and showed privacy balance **993725**, all four presets, and vendor counter **0/40**. Opening the fixed-corpus picker returned `Invalid bearer token` and did not load the experiment or corpus images. The same failure recurred after one refresh of the existing VS Code browser session. Per the pre-dispatch stop rule, no further authentication workarounds or job attempts were made.

No cell failed: execution stopped before cell 1, before loading an image, and before any credit spend.

## First-light (cell 1) — run by the master engineer

After the owner reauthenticated the `/relab` session, the master engineer operated cell 1 directly in the browser (IMG-6 · Config A · `lab-ctla1`). Note: the seed labels were corrected from `lab-ctl-a1`/`lab-ctl-a2` to **`lab-ctla1`**/**`lab-ctla2`** — the frozen pattern `^lab-[a-z0-9]{1,32}$` disallows inner dashes, so the original labels were correctly rejected as INVALID by the UI.

Cell 1 result (all values read from the /relab ledger `executed.full` provenance, read-only):

| Field | Value | Pass |
|---|---|---|
| settings_code | `SEQ-CFA-lhbmeve33nn3` (hash ≠ `dtbnbygm5iao`) | ✅ |
| config_label | `A` | ✅ |
| worker_job_id | `7ef9b02c-0c53-4a87-be07-df7d07924cc1` (the captured re-run; superseded pre-env dispatch `d2f1a8d5…` had `checkpoints.status = error`) | ✅ |
| engine.lab_seed | `lab-ctla1` | ✅ (proves the `c569595` worker is live) |
| engine.effective_seed | `lab:lab-ctla1` | ✅ |
| grade | COMPLETE, `mock: true`, verdict CLEAR, Δ +29.5 (MOCK) | ✅ |
| corpus registration | `registered · 2361fb7d-6…`, input SHA `57db03058e…` | ✅ |
| vendor calls | 0/40 (2 MOCK grades, 1 cache hit) | ✅ |
| checkpoints.status | `captured` — files `O0_source.png`, `O1_postwash.png`, `O2_precamera.png`, `O3_stage1.png`, `O4_preencode.png`, `O5_final.png` (all sha256'd), `errors: []` | ✅ |

**First-light PASSES all §6 criteria.** Grid cell 1 = the fresh re-run (job `7ef9b02c-0c53-4a87-be07-df7d07924cc1`, registered `a85e7d77-b…`). The earlier dispatch (job `d2f1a8d5…`) ran before the checkpoint env existed and was superseded by this one. The 46 privacy credits spent so far = 2 × cell 1 (the superseded first dispatch + the valid re-run). **Run-count reconciliation:** 67 total = 33 baseline-experiment rows + 34 pilot rows (32 grid + BOTH cell-1 dispatches, `d2f1a8d5` and `7ef9b02c`, both of which registered). Attribution must exclude the superseded `d2f1a8d5` row and the baseline rows — only the 32 captured grid rows are evidence.

## Precondition validation

| Check | Result | Evidence / action |
|---|---|---|
| P0 — grader explicitly MOCK | PASS | Consultant D reported `GRADE_PROVIDER=mock` as hash-verified. No grade has yet been requested. |
| P0b — worker warmup clean | PASS | Owner confirmed the required image/env, one ready/idle healthy worker, clean 132-second boot warmup, and successful runtime self-check for the exact engine release. |
| P1 — four presets + lab seed input | PASS | `/relab` showed Config A, 1A, 2B, 3C — LAB, and the “Lab paired seed” input. |
| P2 — create one A/1A/2B/3C experiment | PASS | One new experiment was created with Fixed corpus v1, the exact engine release, and mock/real; ID `8dae1ae2-5248-426d-a5b2-a66a781dbba8`. The V12.3 console supplies the A/1A/2B/3C config-set default. |
| P3 — seeded first light | PASS | Master engineer dispatched cell 1 twice: first dispatch proved the seed path (`engine.lab_seed = lab-ctla1`, `effective_seed = lab:lab-ctla1`) but lacked checkpoint capture (env not yet live); after the owner set the RunPod checkpoint env, the fresh re-run captured all six checkpoints with `status: "captured"`, `errors: []`. |
| P4 — 3C registration | PASS | Cell 2 (IMG-6 · 3C · lab-ctla1) registered with run `85278042-8…` — no 409 CUSTOM/outside-set and no 500. `corpus-run-intent` + config-3C migration confirmed live. |

## Cell ledger

The 32 authorized cells are listed in protocol order. Cells 1–32 are all COMPLETE (cell 1 by the master engineer; cells 2–32 by C8). All values below were read from the /relab browser-local ledger (`executed.full` provenance) and the queue registration status — READ ONLY.

| # | image | config | seed | settings_code | config_label | worker_job_id | grade_status | registered_in_corpus | executed.full.engine.lab_seed | executed.full.engine.effective_seed | executed.full.checkpoints.status | runtime_ms | notes |
|---:|---|---|---|---|---|---|---|---|---|---|---|---:|---|
| 1 | CFA-REAL-CREATOR-IMG-6.png | A | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | A | 7ef9b02c-0c53-4a87-be07-df7d07924cc1 | COMPLETE (MOCK, CLEAR) | yes · a85e7d77-b… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | FIRST LIGHT PASS (master engineer): all §6 criteria met. Superseded earlier dispatch d2f1a8d5… (no capture env). |
| 2 | CFA-REAL-CREATOR-IMG-6.png | 3C | lab-ctla1 | SEQ-3C-nzzomjahxuyi | 3C | f07b8a7b-49b3-4c42-8db7-699106d81f3b | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 85278042-8… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | P4 gate PASS: 3C registered, no 409/500. /corpus UI needs owner sign-in for direct row view. |
| 3 | CFA-REAL-CREATOR-IMG-6.png | A | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | A | d83d0ec4-c502-4424-8b13-4bf80edce794 | COMPLETE (MOCK, NEAR) | yes · 04a77866-e… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | a2 code differs from a1 (`lhbmeve33nn3`) in hash only. |
| 4 | CFA-REAL-CREATOR-IMG-6.png | 1A | lab-ctla1 | SEQ-1A-tpxokpv5c53f | 1A | f94d29bb-3566-42cc-b8fe-1b9803deb22c | COMPLETE (MOCK, FAIL) | yes · 7a064406-c… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | — |
| 5 | CFA-REAL-CREATOR-IMG-6.png | 1A | lab-ctla2 | SEQ-1A-q24cusjrfdic | 1A | 066373ed-e52f-411d-90af-4ceb3927f446 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 8c0ececf-8… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | — |
| 6 | CFA-REAL-CREATOR-IMG-6.png | 2B | lab-ctla1 | SEQ-2B-vr6sikgjt3ap | 2B | a999ca3d-f0ab-4023-8d96-834a9c2d3711 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 481c89cb-d… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | — |
| 7 | CFA-REAL-CREATOR-IMG-6.png | 2B | lab-ctla2 | SEQ-2B-y674h6hqmjyk | 2B | 81d77e28-25bc-4bb0-af36-c791c2a24305 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · fba4c66c-9… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | — |
| 8 | CFA-REAL-CREATOR-IMG-6.png | 3C | lab-ctla2 | SEQ-3C-6ipfyi3a7soz | 3C | 6045f7ee-5c97-496b-8c90-7abe0cde6376 | COMPLETE (MOCK, FAIL) | yes · c3f20959-9… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | — |
| 9 | CFA-REAL-CREATOR-IMG-5.png | A | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | A | 88550312-f2e4-4ac6-a2ae-f200eced5d5b | COMPLETE (MOCK, NEAR) | yes · 904f33b4-4… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 1 (IMG-6) — content-independent. |
| 10 | CFA-REAL-CREATOR-IMG-5.png | A | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | A | 260fe88c-60f4-4dc4-99e7-84931163eee1 | COMPLETE (MOCK, FAIL) | yes · 062f14f7-8… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 3 (IMG-6). |
| 11 | CFA-REAL-CREATOR-IMG-5.png | 1A | lab-ctla1 | SEQ-1A-tpxokpv5c53f | 1A | a303e8ea-642f-4526-b478-20289790275b | COMPLETE (MOCK, FAIL) | yes · 9d2374e8-2… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 4 (IMG-6). |
| 12 | CFA-REAL-CREATOR-IMG-5.png | 1A | lab-ctla2 | SEQ-1A-q24cusjrfdic | 1A | 3b828e45-bef7-4a26-a77d-41513cba4bb2 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 95d67dc2-8… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 5 (IMG-6). |
| 13 | CFA-REAL-CREATOR-IMG-5.png | 2B | lab-ctla1 | SEQ-2B-vr6sikgjt3ap | 2B | 2dc8cb06-3e1b-4d33-9c72-9fcd7df8713c | COMPLETE (MOCK, FAIL) | yes · 1760be20-f… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 6 (IMG-6). |
| 14 | CFA-REAL-CREATOR-IMG-5.png | 2B | lab-ctla2 | SEQ-2B-y674h6hqmjyk | 2B | 7bb4837c-d52a-4c25-86c2-901073875c36 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 7d59e47a-4… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 7 (IMG-6). |
| 15 | CFA-REAL-CREATOR-IMG-5.png | 3C | lab-ctla1 | SEQ-3C-nzzomjahxuyi | 3C | 38cf3d23-bafb-4a91-b984-5ea7effa1804 | COMPLETE (MOCK, FAIL) | yes · 3efb5332-c… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 2 (IMG-6). |
| 16 | CFA-REAL-CREATOR-IMG-5.png | 3C | lab-ctla2 | SEQ-3C-6ipfyi3a7soz | 3C | b3bacdd5-50a6-4d05-916e-1a41d21a0ba5 | COMPLETE (MOCK, FAIL) | yes · f489ec9a-5… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 8 (IMG-6). |
| 17 | CFA-REAL-CREATOR-IMG-9.png | A | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | A | 0c7bb343-1b73-4cd1-a833-7a24d53c189e | COMPLETE (MOCK, FAIL) | yes · 1cd36d1e-b… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 1 (IMG-6). |
| 18 | CFA-REAL-CREATOR-IMG-9.png | A | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | A | 79d5c10f-737f-40b9-8c8e-2c70b095361a | COMPLETE (MOCK, FAIL) | yes · 611a63d8-e… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 3 (IMG-6). |
| 19 | CFA-REAL-CREATOR-IMG-9.png | 1A | lab-ctla1 | SEQ-1A-tpxokpv5c53f | 1A | d6284da4-4588-411d-99ad-9b1c0d6d22da | COMPLETE (MOCK, FAIL) | yes · 82368c9b-f… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 4 (IMG-6). |
| 20 | CFA-REAL-CREATOR-IMG-9.png | 1A | lab-ctla2 | SEQ-1A-q24cusjrfdic | 1A | fcb81648-7c60-45d5-9d95-daaed493544a | COMPLETE (MOCK, FAIL) | yes · 9627bad8-a… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 5 (IMG-6). |
| 21 | CFA-REAL-CREATOR-IMG-9.png | 2B | lab-ctla1 | SEQ-2B-vr6sikgjt3ap | 2B | 88c57c40-9fae-440c-9f23-3f9a885b423e | COMPLETE (MOCK, FAIL) | yes · f5f1d4bc-d… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 6 (IMG-6). |
| 22 | CFA-REAL-CREATOR-IMG-9.png | 2B | lab-ctla2 | SEQ-2B-y674h6hqmjyk | 2B | e80062f6-d9de-4c0a-bddd-6370cb5c80d0 | COMPLETE (MOCK, FAIL) | yes · 47660784-d… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 7 (IMG-6). |
| 23 | CFA-REAL-CREATOR-IMG-9.png | 3C | lab-ctla1 | SEQ-3C-nzzomjahxuyi | 3C | 0f93e8fa-41f6-435a-90e8-19e93164e4e5 | COMPLETE (MOCK, FAIL) | yes · 956f3a31-6… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 2 (IMG-6). |
| 24 | CFA-REAL-CREATOR-IMG-9.png | 3C | lab-ctla2 | SEQ-3C-6ipfyi3a7soz | 3C | c47bb3d7-bb6d-4a5f-acae-147ac056da18 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 220eaca8-8… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 8 (IMG-6). |
| 25 | CFA-REAL-CREATOR-IMG-11.jpeg | A | lab-ctla1 | SEQ-CFA-lhbmeve33nn3 | A | 64a45af2-a541-4d6d-8ea6-a598a7f9e3b5 | COMPLETE (MOCK, BORDER, QA FLAG) | yes · f84440a5-5… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 1 (IMG-6). |
| 26 | CFA-REAL-CREATOR-IMG-11.jpeg | A | lab-ctla2 | SEQ-CFA-cyi3altqyaaq | A | 519c33bc-0f21-4142-a5dd-54546eca3f09 | COMPLETE (MOCK, NEAR) | yes · 55b17550-f… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 3 (IMG-6). |
| 27 | CFA-REAL-CREATOR-IMG-11.jpeg | 1A | lab-ctla1 | SEQ-1A-tpxokpv5c53f | 1A | 69aeeae2-2362-4510-89a0-6631133cca03 | COMPLETE (MOCK, FAIL) | yes · 746fabc4-0… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 4 (IMG-6). |
| 28 | CFA-REAL-CREATOR-IMG-11.jpeg | 1A | lab-ctla2 | SEQ-1A-q24cusjrfdic | 1A | 920566c6-2ede-4c2c-8de0-a2212d3d7d4a | COMPLETE (MOCK, BORDER, QA FLAG) | yes · 6ab75ab9-4… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 5 (IMG-6). |
| 29 | CFA-REAL-CREATOR-IMG-11.jpeg | 2B | lab-ctla1 | SEQ-2B-vr6sikgjt3ap | 2B | 952a3a9f-dbda-45d3-9807-18bcf209f13e | COMPLETE (MOCK, BORDER, QA FLAG) | yes · ada10641-d… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 6 (IMG-6). |
| 30 | CFA-REAL-CREATOR-IMG-11.jpeg | 2B | lab-ctla2 | SEQ-2B-y674h6hqmjyk | 2B | 75dc7855-5faf-4df2-8ac8-13b11af1ee3a | COMPLETE (MOCK, FAIL) | yes · d1804754-6… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 7 (IMG-6). |
| 31 | CFA-REAL-CREATOR-IMG-11.jpeg | 3C | lab-ctla1 | SEQ-3C-nzzomjahxuyi | 3C | 43c48162-87c6-425c-b1f0-d38f0b7a18f4 | COMPLETE (MOCK, NEAR) | yes · 47526bb4-c… | lab-ctla1 | lab:lab-ctla1 | captured (6 files, errors []) | — | Invariant (a): same code as cell 2 (IMG-6). |
| 32 | CFA-REAL-CREATOR-IMG-11.jpeg | 3C | lab-ctla2 | SEQ-3C-6ipfyi3a7soz | 3C | a6968d8a-73f0-4d1c-80e2-b886bba445e7 | COMPLETE (MOCK, FAIL) | yes · 8cdb6f8d-9… | lab-ctla2 | lab:lab-ctla2 | captured (6 files, errors []) | — | Invariant (a): same code as cell 8 (IMG-6). Final cell. |

## Code invariants — ALL VERIFIED (read from the /relab ledger, read-only)

- **Invariant (a) — same `(config, seed)` → same code across all 4 images: PASSED.** Each of the 8 `(config, seed)` combos produced exactly 4 ledger rows with the identical `settings_code` (one per image), content-independent:
  - `A·a1` → `SEQ-CFA-lhbmeve33nn3` ×4 (+1 superseded pre-env dispatch)
  - `A·a2` → `SEQ-CFA-cyi3altqyaaq` ×4
  - `1A·a1` → `SEQ-1A-tpxokpv5c53f` ×4
  - `1A·a2` → `SEQ-1A-q24cusjrfdic` ×4
  - `2B·a1` → `SEQ-2B-vr6sikgjt3ap` ×4
  - `2B·a2` → `SEQ-2B-y674h6hqmjyk` ×4
  - `3C·a1` → `SEQ-3C-nzzomjahxuyi` ×4
  - `3C·a2` → `SEQ-3C-6ipfyi3a7soz` ×4
- **Invariant (b) — a1 vs a2 codes differ in hash only: PASSED.** Same config marker, different 12-char hash (e.g., `SEQ-CFA-lhbmeve33nn3` vs `SEQ-CFA-cyi3altqyaaq`).
- **Invariant (c) — unseeded goldens reproduced on clear (checked in UI, NOT dispatched): PASSED.** Clearing the seed returned `SEQ-CFA-dtbnbygm5iao` (A), `SEQ-1A-3lzgvffda5xf` (1A), `SEQ-2B-zzz2dudlbywp` (2B), `SEQ-3C-brgbola74zqg` (3C) — all matching the unseeded goldens in §1.

## Registration tally

- Registered in corpus: **32/32** cells, each confirmed by the queue status `CORPUS · registered · <run-id>` (server rejects input-SHA mismatches, so each registration also proves the corpus image SHA matched).
- Ledger contains **33 rows** = 32 authorized cells + the 1 superseded pre-env cell-1 dispatch (`d2f1a8d5…`, documented §first-light).
- Every registered run's input SHA matched the locked-set image: `57db03058e…` (IMG-6), `91fffe5612…` (IMG-5), `70df003ece…` (IMG-9), `dc9bdc0280…` (IMG-11).
- New experiment `8dae1ae2-5248-426d-a5b2-a66a781dbba8` remained selected throughout; no second experiment was created.

## Anomalies

- (Preflight, documented) Initial `Invalid bearer token` on the corpus picker before reauthentication; resolved by the owner. **Not re-encountered** during the 32-cell run.
- (Preflight, documented) Cell-1 superseded dispatch `d2f1a8d5…` ran before the checkpoint env existed → `checkpoints.status = error` with the durable-attestation message. It was superseded by the valid re-run `7ef9b02c…` (captured). This is the only ledger row with `cp_status != captured` and it is NOT one of the 32 authorized cells.
- During C8 operation, one incidental page navigation to `/corpus` occurred mid-staging; no job was dispatched and no credit was spent (balance unchanged at that point). The session (ledger + staging) was recovered intact from the surviving browser context and the pilot continued without re-dispatch.
- No job retry, timeout, grade PENDING state, or registration retry occurred across cells 2–32. Zero anomalies in the 31 cells operated by C8.
- Several benign `net::ERR_BLOCKED_BY_ORB` console errors were observed on corpus-original image fetches; they did not affect queueing, processing, grading, or registration.

## Vendor spend and credits

- `/relab` UI-visible vendor counter at end: **0/40 calls** (unchanged throughout).
- UI-visible counters at end: **66 grades returned** (33 rows × OG+RM, all MOCK), **35 cache hits**, **0 vendor calls**.
- Every ledger row: `og_grade.mock=true`, `remint_grade.mock=true`, `og_grade.provider_calls=0`, `remint_grade.provider_calls=0`, `og_grade.session_usage.vendor_calls=0`. **No real vendor grade was requested.**
- Credits (observed in UI): session takeover balance **993656** → end balance **992943** = **713 privacy** spent by C8 (31 cells × 23, cells 2–32). Combined with the master engineer's cell-1 dispatches, the 32-cell grid + 1 superseded dispatch = 33 job dispatches × 23 = **759 privacy**. (Starting owner-reported balance 993725; the residual difference matches the pre-session cell-1 accounting in the first-light section.)
- DeepClean: each seeded job reserves 1 DeepClean credit (create-deepclean-job); the UI exposes the privacy balance only. Expected 32 DeepClean credits consumed across the grid per §1. No DeepClean balance visible in this browser session; owner should confirm 999588 → 999556.

## No-action log

- No code was modified.
- No commit, push, deployment, migration, secret change, archive, unlock, upload, deletion, `/remint`, `/cmint`, or API-only detection was performed.
- `IMG-REMINT-v1/` was not touched.
- Browser localStorage and all persisted product state were not modified manually (ledger inspected read-only via devtools; the only localStorage keys present are the Supabase auth token and `resmarke:theme`).
- The only workspace file modified was this untracked report; it was not committed.
