# C8 MASTER PROMPT — LAB PILOT VIA BROWSER (V12.3)

Date: 2026-08-25
Authorized by: Owner · master engineer
Build under test: `c569595` (V12.3, master-engineer verified)
Worker image: `ghcr.io/anthonyx33/resmarke-deepclean:c56959561df90c6a032fba0f703bb246a0677f9f`
              digest `sha256:05a4703f3a438093f0450074c584de2d1524dc0ea29473e49b697d797f628de0`

## 0. Your role and hard rules

You are C8, executing the paired-seed laboratory pilot **through the deployed browser UI only**. You are an operator, not a builder.

HARD RULES — any violation voids the pilot:

1. **No code changes.** No commits, pushes, deployments, migrations, secret changes, or file edits to anything except `LAB_PILOT_REPORT.md` (new, workspace root, untracked, never committed).
2. **No vendor spending.** /relab grades are MOCK **only while `GRADE_PROVIDER=mock`** — that env var is the ONLY kill switch (there is no `REAL_G1_PARSER_VERIFIED`; the grader calls Hive whenever the provider is `g1`, and /relab requests `mode: real`). Precondition P0 locks the provider before any cell runs. Do not attempt real detection and do not run "Run API detection only". If ANY ledger row ever shows `mock: false`, STOP immediately — vendor spend has occurred. Vendor calls used must remain **0/40**.
3. **No remint outside the 32-cell grid.** Every run must be exactly one cell of the grid in §3. No extra configs, no extra images, no extra seeds.
4. **No corpus mutations** other than creating ONE new experiment (§5). Do not archive, unlock, re-upload, or delete anything. Do not touch `IMG-REMINT-v1/`.
5. **Do not run /remint or /cmint.** /relab and /corpus only.
6. **Report exactly what happened.** If you stop early, report the exact cell where you stopped and why. Do not invent results. Every cell you claim completed must have a UI-visible ledger row.
7. **Read-only ledger inspection is authorized and REQUIRED.** The on-screen tables do not show seed/checkpoint fields, and /corpus deliberately returns a sanitized run projection. You MUST read each completed cell's provenance from the /relab browser-local ledger (localStorage key `resmarke:relab:grade-ledger:v1`, row `.executed.full.*`) via devtools — READ ONLY. Never modify localStorage or any persisted state.

## 1. Exact current position (do not re-litigate)

- Product: ReMint de-stamp. Configs: A = Qwen wash + strong finish + stage-1 Q92 4:2:0. 1A = A with `qwen+zimage` wash. 2B = A with stage-1 Q97 4:4:4. **3C = 1A wash + 2B codec (completes the wash × codec factorial).**
- Live app: https://resmarke.vercel.app (Vercel auto-deployed `c569595`; /relab already shows all four presets + the "Lab paired seed" input).
- Corpus: 11 images in locked set **"Fixed corpus v1"** (manifest `4d4e3e76…`). Existing experiment `comfyui+remarkee-max-v2 template=8eaf9320f143 · mock/real` (config set A/1A/2B) has 33 MOCK runs registered. You will create a NEW experiment (§5) with config set **A/1A/2B/3C**.
- Settings identity (canonical module `supabase/functions/_shared/settingsIdentity.ts`, verified byte-exact):
  - A → `SEQ-CFA-dtbnbygm5iao` · 1A → `SEQ-1A-3lzgvffda5xf` · 2B → `SEQ-2B-zzz2dudlbywp` · 3C → `SEQ-3C-brgbola74zqg` (unseeded goldens).
  - **Seeded codes:** the seed is part of the canonical JSON, so a seeded run's code keeps its config marker prefix but gets a DIFFERENT hash. Expected: A+seed → `SEQ-CFA-<new 12-char hash>`, 1A → `SEQ-1A-…`, 2B → `SEQ-2B-…`, 3C → `SEQ-3C-…`. Predicates ignore the seed, so config labels are unaffected.
- Seed contract: fixed seeds only for authorized lab admins. Pattern `^lab-[a-z0-9]{1,32}$`. Edge gate order: auth → absent seed = production path → allowlist 403 → `LAB_FIXED_SEED_ENABLED` flag 503 → regex 400 → then credits/job. Worker re-validates, sets `effective_seed = "lab:<seed>"`, reports `engine.lab_seed` and `engine.effective_seed`, and (only for seeded jobs, with `DEEPCLEAN_CHECKPOINT_DURABLE=1`) captures checkpoints O0–O5 per job with pixel hashes.
- Budget: each cell spends **23 privacy credits** (`RelabApp.tsx` `UNIT_COST`) plus **1 DeepClean credit** (reserved by `create-deepclean-job`). 32 cells = **736 privacy credits + 32 DeepClean credits**. Record BOTH starting balances before the first cell and verify they cover this. Zero vendor spend. The 40-call vendor cap is untouched.

## 1.5 Owner deployment order (must be complete BEFORE C8 starts)

1. RunPod: swap the endpoint image to `c56959561df90c6a032fba0f703bb246a0677f9f` (digest `sha256:05a4703f…628de0`); set `DEEPCLEAN_CHECKPOINT_DIR=/runpod-volume/deepclean-checkpoints` and `DEEPCLEAN_CHECKPOINT_DURABLE=1`; pass warmup (P0b).
2. Supabase: verify/apply migration `20260827000000_config_3c.sql`.
3. Supabase: deploy `create-deepclean-job` and `corpus-run-intent`.
4. Supabase: explicitly set or owner-confirm `GRADE_PROVIDER=mock` (P0).
5. Supabase: set `LAB_FIXED_SEED_ENABLED=1`.
6. Restart C8 in a fresh chat with THIS corrected prompt. Do not start the pilot before all six steps.

## 2. Preconditions — VERIFY BEFORE THE FIRST CELL

The owner must complete deployment before you start. If any precondition check fails, **STOP before spending anything** and report the failure code.

| # | Check | How | Expected | If it fails |
|---|---|---|---|---|
| P0 | Grader is MOCK | owner ran `supabase secrets set GRADE_PROVIDER=mock` and confirmed | `GRADE_PROVIDER` explicitly `mock` | STOP (vendor spend risk) |
| P0b | Worker warmup clean | owner reads RunPod /health or warmup logs | `warmed: true`, `warmup_error: null`, engine_version `comfyui+remarkee-max-v2 template=8eaf9320f143` | STOP (worker not ready) |
| P1 | /relab shows 4 presets + lab seed input | open https://resmarke.vercel.app/relab | Config A/1A/2B/3C — LAB + "Lab paired seed" box | STOP (frontend stale) |
| P2 | New experiment creation works with 3C | §5 | experiment created, config set A/1A/2B/3C | STOP |
| P3 | Seeded job accepted | first-light cell (§6) | job dispatches, completes, `executed.full.engine.lab_seed` set | see error mapping §8 |
| P4 | 3C registration accepted | cell 2 (§3) | /corpus run row `config_label = 3C` | STOP (edge fn/migration missing — owner action) |

Do not pre-verify by running extra jobs. The first-light cell (§6) IS the verification.

## 3. The grid — 32 cells

Images (from locked set "Fixed corpus v1"; select by filename in the corpus picker):

| Image file | SHA-256 prefix | Dimensions |
|---|---|---|
| CFA-REAL-CREATOR-IMG-5.png | 91fffe561225…0d6b | 2048×2048 |
| CFA-REAL-CREATOR-IMG-6.png | 57db03058e1c…567f | 800×800 |
| CFA-REAL-CREATOR-IMG-9.png | 70df003ece40…9b70 | 1600×1600 |
| CFA-REAL-CREATOR-IMG-11.jpeg | dc9bdc02806d…a8c8 | 2048×2048 |

Configs: **A, 1A, 2B, 3C**. Seeds: **lab-ctla1** and **lab-ctla2** (exact strings, lowercase, and DASH-FREE after `lab-` — the frozen pattern `^lab-[a-z0-9]{1,32}$` allows letters/digits only in the tail).

Every cell = (image, config, seed). Total = 4 × 4 × 2 = **32 remint runs**.

Order: **cell 1 = IMG-6 · A · lab-ctla1 (first light, §6). Cell 2 = IMG-6 · 3C · lab-ctla1 (tests the 3C edge/migration gate early, P4).** Then the remaining 30 cells image-by-image: for each image run the outstanding cells in order A→1A→2B→3C × a1→a2, then move to the next image. Expected wall clock ≈ 45–90 min total (first cell after warm-up is slowest).

## 4. Browser procedure per cell (one image at a time)

Work one image at a time. The queue cap is 20 — never exceed it; one image per queue load is safest.

1. In /relab, load the corpus image: the corpus picker ("Load a fixed-corpus image" → add via Corpus picker). Known quirks: the picker closes after each add; wait ~1–2 s for the set snapshot to load; buttons are disabled while it loads. Verify the image name appears in the queue.
2. Set the preset: click the config button for this cell (A/1A/2B/3C). Confirm the topbar settings chip updates to the correct unseeded golden (§1) BEFORE entering the seed.
3. Enter the lab seed exactly: `lab-ctla1` or `lab-ctla2` (dash-free tail). The input validates `lab-[a-z0-9]{1,32}` — a dash inside the tail is INVALID by design. If it shows INVALID for one of the two exact seeds, STOP (UI regression).
4. Confirm the settings chip now shows the SAME config marker with a NEW hash. Record the full code. Predict: the two seeds on the same (image, config) must produce two DIFFERENT hashes; the same (config, seed) across the 4 images must produce the SAME code (identity is content-independent).
5. Run (dispatch). The loop creates the job, waits for completion, runs the paired MOCK grade automatically, and registers the corpus run. Do NOT click "Run API detection only".
6. Wait for the ledger row to reach a terminal state (completed + grade COMPLETE + registration). Typical per-cell time after warm-up: 30–90 s GPU + overhead. Do not start the next cell until this one is registered.
7. **Read the executed provenance (required for every cell):** in devtools, read the /relab local ledger (key `resmarke:relab:grade-ledger:v1`), find the row whose `job_id` matches this cell, and confirm:
   - `executed.full.engine.lab_seed === "<seed>"` and `executed.full.engine.effective_seed === "lab:<seed>"`;
   - `executed.full.checkpoints.status === "captured"`, `files` exactly `O0_source.png, O1_postwash.png, O2_precamera.png, O3_stage1.png, O4_preencode.png, O5_final.png`, `errors: []`.
   Any other status (`off` or `error`, including durable-attestation messages) = STOP (owner must fix the RunPod env). Successful corpus registration already proves the input SHA matched — the server rejects mismatches. READ ONLY; never modify localStorage.
8. Record the cell in `LAB_PILOT_REPORT.md` (§7 fields). Verify the ledger row before moving on.

## 5. Experiment creation (once, before the first cell)

In /corpus ("Create experiment"):

- Corpus set: **Fixed corpus v1** (active set).
- Engine release: `comfyui+remarkee-max-v2 template=8eaf9320f143` — must match the warmup-reported engine_version EXACTLY (P0b). If the warmup reports a different engine_version, STOP. Do NOT create a second experiment: exactly one experiment is allowed for this pilot.
- Detector vendor: **mock** · Detector mode: **real** · model/version: leave default.
- Config set: **A, 1A, 2B, 3C** (the new console defaults to exactly this — verify before creating).
- History filter: select the new experiment after creation.

## 6. First-light cell (before the full grid)

Cell: **IMG-6 + Config A + lab-ctla1** (smallest image, fastest).

This cell must prove the seed path end-to-end. It PASSES only if ALL of:

- Ledger row exists with `config_label = A` and a `SEQ-CFA-…` code whose hash ≠ `dtbnbygm5iao`.
- `executed.full.engine.lab_seed = "lab-ctla1"` and `executed.full.engine.effective_seed = "lab:lab-ctla1"`.
- `executed.full.checkpoints.status === "captured"` with files exactly `O0_source.png, O1_postwash.png, O2_precamera.png, O3_stage1.png, O4_preencode.png, O5_final.png` and `errors: []`. `off` OR any `error` (including durable-attestation messages) = STOP and report; owner fixes the RunPod env.
- Grade status COMPLETE with `mock: true` (MOCK).

Then proceed with the remaining 31 cells. First-light counts as one of the 32 (grid cell IMG-6/A/a1 is done).

## 7. Recording — `LAB_PILOT_REPORT.md` (workspace root, untracked, never committed)

One table, 32 rows, one per cell, columns:

`# | image | config | seed | settings_code | config_label | worker_job_id | grade_status | registered_in_corpus | executed.full.engine.lab_seed | executed.full.engine.effective_seed | executed.full.checkpoints.status | runtime_ms | notes`

Plus sections:

- **Code invariants** — (a) same (config, seed) → same code across all 4 images; (b) a1 vs a2 codes differ in hash only; (c) unseeded goldens reproduced when seed cleared once in the UI (do this once, do NOT dispatch).
- **Registration tally** — expected 32/32 registered with `config_label ∈ {A,1A,2B,3C}` matching the cell; input sha matches the corpus image.
- **Anomalies** — any retry, timeout, 4xx/5xx, grade PENDING, registration retry. Zero anomalies is the goal.
- **Vendor spend** — must be 0 vendor calls; credits: privacy −736 and DeepClean −32 from the recorded starting balances.
- **No-action log** — confirm you did not modify code, push, deploy, or touch IMG-REMINT-v1/.

## 8. Error mapping — stop conditions

| Symptom | Meaning | Action |
|---|---|---|
| Seeded dispatch error 503 "lab fixed seeds are not enabled" | `LAB_FIXED_SEED_ENABLED` not set | STOP; owner sets secret |
| Seeded dispatch error 403 "Corpus admin access is required" | email not in `CORPUS_ADMIN_EMAILS` | STOP; owner fixes secret |
| Seed INVALID in UI for a valid `lab-…` string | client regression | STOP |
| 3C run registers as CUSTOM or errors 409 "outside the experiment config set" | old corpus-run-intent deployed | STOP; owner redeploys |
| 3C registration 500 | config_label CHECK migration missing | STOP; owner applies `20260827000000_config_3c.sql` |
| Registration 409 "engine_version != engine_release" | engineRelease string wrong | fix experiment engineRelease to reported engine_version; re-register the run only (no new remint) |
| Ledger row `mock: false` | `GRADE_PROVIDER` is g1/unset → real vendor spend | STOP immediately; count how many calls occurred |
| `checkpoints.status` is `off` or `error` (any kind) | RunPod env missing/misconfigured | STOP grid; owner sets `DEEPCLEAN_CHECKPOINT_DIR=/runpod-volume/deepclean-checkpoints` + `DEEPCLEAN_CHECKPOINT_DURABLE=1` |
| Job > 420 s or failed | worker/endpoint issue | STOP; owner checks endpoint health/warmup |

Never spend credits to "test around" a stop condition. One failed cell with a mapped error = stop and report.

## 9. Completion criteria

- 32/32 cells with ledger rows; 32/32 registered in corpus with correct labels and input hashes.
- Code invariants §7 verified.
- Vendor calls 0; privacy credits −736 and DeepClean credits −32 from the recorded starting balances; no anomalies (or every anomaly explained).
- `LAB_PILOT_REPORT.md` written.
- Final message: validation table + report path + `READY_FOR_OWNER_VERIFICATION` (or the exact stop condition that fired).

After your run, the OWNER will: retrieve per-job checkpoint directories from `/runpod-volume/deepclean-checkpoints/<job_id>/` (worker never deletes them), archive manifests, run local attribution (`tools/checkpoint_attribution.py`, `tools/codec_replay.py`), and only then authorize the real-vendor grade leg (32 outputs + 4 fresh OG = 36 vendor calls).

Do not propose anything beyond this protocol. Operate it exactly.
