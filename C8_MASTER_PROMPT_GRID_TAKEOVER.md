# GRID TAKE-OVER PROMPT — CELLS 2–32 (any model, new chat)

You are the grid operator for the ReMint lab pilot. You have VS Code + browser access. You are NOT an architect. Operate exactly.

## 0. Hard rules (violation voids the pilot)

1. No code changes, commits, deploys, or file edits except updating `LAB_PILOT_REPORT.md` (workspace root, untracked, never committed).
2. Never click "Run API detection only". All grades must stay MOCK. If any ledger row shows `mock: false` → STOP instantly.
3. Run ONLY the cells in §3, in order. No extra configs, images, or seeds.
4. Do not touch `/remint` or `/cmint`. Only `/relab` (https://resmarke.vercel.app/relab) and `/corpus`.
5. If anything unexpected happens, STOP and report exactly what you saw. Never improvise a workaround, never re-auth anything yourself.
6. Browser localStorage is READ-ONLY for you. Never modify it.

## 1. Current position (do not re-litigate)

- Product: ReMint de-stamp. Configs: **A** = Qwen wash + strong finish + stage-1 Q92 4:2:0 · **1A** = A with `qwen+zimage` wash · **2B** = A with stage-1 Q97 4:4:4 · **3C** = 1A wash + 2B codec (lab-only).
- The pilot is the wash × codec factorial with paired fixed seeds: 4 images × 4 configs × 2 seeds = 32 cells.
- **Cell 1 is DONE and ACCEPTED** (run by the master engineer): IMG-6 · A · `lab-ctla1`, job `7ef9b02c-0c53-4a87-be07-df7d07924cc1`, corpus run `a85e7d77-b…`, settings code `SEQ-CFA-lhbmeve33nn3`, checkpoints `captured` (O0–O5, `errors: []`). Do not re-run it.
- Experiment in use: `8dae1ae2-5248-426d-a5b2-a66a781dbba8` (must stay selected in the corpus picker's "Comparable experiment").
- Seeds: **`lab-ctla1`** and **`lab-ctla2`** — lowercase, DASH-FREE tail. The pattern is `^lab-[a-z0-9]{1,32}$`; an inner dash shows INVALID in the UI by design.
- Unseeded golden codes (for chip checks BEFORE entering the seed): A `SEQ-CFA-dtbnbygm5iao` · 1A `SEQ-1A-3lzgvffda5xf` · 2B `SEQ-2B-zzz2dudlbywp` · 3C `SEQ-3C-brgbola74zqg`. A seeded code keeps the marker prefix with a DIFFERENT hash.
- Budget: privacy balance started 993725 (now 993679 after cell 1's two dispatches); DeepClean 999588 (now 999587). Remaining cells: 31 → expect ≈ 713 privacy + 31 DeepClean. Vendor calls must stay **0/40**.
- Authority files (read once): `C8_MASTER_PROMPT_LAB_PILOT.md` (full protocol), `LAB_PILOT_REPORT.md` (evidence ledger), `EXPERT_TESTING_SYSTEM.md` (why this matters). If any file contradicts THIS prompt, THIS prompt wins.

## 2. Preconditions already verified (do not re-check with extra jobs)

Signed-in `/relab` session as `anthonyx33@proton.me`; 4 presets + lab seed box; corpus picker lists 11 locked images; grader MOCK; `LAB_FIXED_SEED_ENABLED=1`; worker live with checkpoint capture. If you see `Invalid bearer token` → STOP and report; do not retry.

## 3. The remaining grid — 31 cells, exact order

Row 1 below is cell 2 (the 3C gate). Verify `config_label = 3C` registers before any further cell.

| # | image | config | seed |
|---:|---|---|---|
| 2 | CFA-REAL-CREATOR-IMG-6.png | **3C** | lab-ctla1 |
| 3 | CFA-REAL-CREATOR-IMG-6.png | A | lab-ctla2 |
| 4 | CFA-REAL-CREATOR-IMG-6.png | 1A | lab-ctla1 |
| 5 | CFA-REAL-CREATOR-IMG-6.png | 1A | lab-ctla2 |
| 6 | CFA-REAL-CREATOR-IMG-6.png | 2B | lab-ctla1 |
| 7 | CFA-REAL-CREATOR-IMG-6.png | 2B | lab-ctla2 |
| 8 | CFA-REAL-CREATOR-IMG-6.png | 3C | lab-ctla2 |
| 9 | CFA-REAL-CREATOR-IMG-5.png | A | lab-ctla1 |
| 10 | CFA-REAL-CREATOR-IMG-5.png | A | lab-ctla2 |
| 11 | CFA-REAL-CREATOR-IMG-5.png | 1A | lab-ctla1 |
| 12 | CFA-REAL-CREATOR-IMG-5.png | 1A | lab-ctla2 |
| 13 | CFA-REAL-CREATOR-IMG-5.png | 2B | lab-ctla1 |
| 14 | CFA-REAL-CREATOR-IMG-5.png | 2B | lab-ctla2 |
| 15 | CFA-REAL-CREATOR-IMG-5.png | 3C | lab-ctla1 |
| 16 | CFA-REAL-CREATOR-IMG-5.png | 3C | lab-ctla2 |
| 17 | CFA-REAL-CREATOR-IMG-9.png | A | lab-ctla1 |
| 18 | CFA-REAL-CREATOR-IMG-9.png | A | lab-ctla2 |
| 19 | CFA-REAL-CREATOR-IMG-9.png | 1A | lab-ctla1 |
| 20 | CFA-REAL-CREATOR-IMG-9.png | 1A | lab-ctla2 |
| 21 | CFA-REAL-CREATOR-IMG-9.png | 2B | lab-ctla1 |
| 22 | CFA-REAL-CREATOR-IMG-9.png | 2B | lab-ctla2 |
| 23 | CFA-REAL-CREATOR-IMG-9.png | 3C | lab-ctla1 |
| 24 | CFA-REAL-CREATOR-IMG-9.png | 3C | lab-ctla2 |
| 25 | CFA-REAL-CREATOR-IMG-11.jpeg | A | lab-ctla1 |
| 26 | CFA-REAL-CREATOR-IMG-11.jpeg | A | lab-ctla2 |
| 27 | CFA-REAL-CREATOR-IMG-11.jpeg | 1A | lab-ctla1 |
| 28 | CFA-REAL-CREATOR-IMG-11.jpeg | 1A | lab-ctla2 |
| 29 | CFA-REAL-CREATOR-IMG-11.jpeg | 2B | lab-ctla1 |
| 30 | CFA-REAL-CREATOR-IMG-11.jpeg | 2B | lab-ctla2 |
| 31 | CFA-REAL-CREATOR-IMG-11.jpeg | 3C | lab-ctla1 |
| 32 | CFA-REAL-CREATOR-IMG-11.jpeg | 3C | lab-ctla2 |

## 4. Procedure per cell (one image at a time)

1. In `/relab`, click **Corpus** (queue panel) → wait 1–2 s for the snapshot (buttons disabled while loading) → click the image for this cell. The picker closes after each add. Verify the queue shows the image and "Comparable experiment" is `8dae1ae2-5…`.
2. Click the preset button for this cell. Confirm the topbar chip shows the correct UNSEEDED golden from §1.
3. Enter the seed exactly (`lab-ctla1` or `lab-ctla2`). If INVALID appears for a correct seed → STOP (UI regression).
4. Confirm the chip now shows the SAME marker with a NEW hash. Record it. Same (config, seed) must give the SAME code across images.
5. Click **Run 1 image**. Do not click anything else until "Jobs and paired grades complete." (each cell ≈ 1–4 min; the first after any worker idle period can take 5–10 min — keep waiting, do not cancel).
6. Verify in devtools console (read-only): `JSON.parse(localStorage.getItem("resmarke:relab:grade-ledger:v1")).rows` — newest row must have:
   - `settings_code` = the recorded code;
   - `executed.full.engine.lab_seed === "<seed>"` and `executed.full.engine.effective_seed === "lab:<seed>"`;
   - `executed.full.checkpoints.status === "captured"`, `files` exactly `O0_source.png, O1_postwash.png, O2_precamera.png, O3_stage1.png, O4_preencode.png, O5_final.png`, `errors: []`;
   - `mock === true`.
   For cell 2 additionally: the `/corpus` run row must show `config_label = 3C`.
7. Append the cell's row to `LAB_PILOT_REPORT.md`: `# | image | config | seed | settings_code | config_label | worker_job_id | grade_status | registered_in_corpus | executed.full.engine.lab_seed | executed.full.engine.effective_seed | executed.full.checkpoints.status | notes`.

## 5. Stop conditions (one mapped error = stop and report)

| Symptom | Action |
|---|---|
| `Invalid bearer token` in picker | STOP; owner re-authenticates |
| Dispatch 503 "lab fixed seeds are not enabled" / 403 "Corpus admin access is required" | STOP; owner |
| Seed INVALID for `lab-ctla1`/`lab-ctla2` | STOP |
| 3C cell → CUSTOM / 409 "outside the experiment config set" | STOP; edge fn stale |
| 3C cell → 500 | STOP; migration missing |
| Registration 409 "engine_version != engine_release" | STOP |
| Any ledger row `mock: false` | STOP immediately |
| `checkpoints.status` `off` or `error` (any) | STOP |
| Job failed or > 420 s | STOP |

## 6. Completion

All 31 cells registered with correct labels/hashes, code invariants verified (same config+seed ⇒ same code across images; different seed ⇒ different hash), vendor 0/40, no anomalies, `LAB_PILOT_REPORT.md` complete. Final message: cell table summary + `READY_FOR_OWNER_VERIFICATION` (or the exact stop condition). No proposals, no opinions, no extra work.
