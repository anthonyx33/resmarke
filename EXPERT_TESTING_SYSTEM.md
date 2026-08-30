# EXPERT TESTING & OPTIMIZATION SYSTEM — ReMint (V12.3+)

Date: 2026-08-26 · Owner-authorized · master-engineer maintained
Sibling: `C8_MASTER_PROMPT_LAB_PILOT.md` (operator protocol), `LAB_PILOT_REPORT.md` (evidence ledger)

## 0. Purpose

One repeatable system for turning measurements into the best possible de-stamp
performance and quality, with zero unverified claims. Every optimization moves
through: **measure → attribute → hypothesize → single-variable change →
verification → accept/reject → ledger**.

## 1. Roles

| Role | Who | Duties |
|---|---|---|
| Master engineer | this assistant | Owns the system; verifies every build/claim against code; commits; gates deploys; runs attribution; issues briefs |
| C8 | builder/operator | Operates the pilot grid; implements ONLY briefed single-variable builds; reports exact evidence |
| Consultant D | independent analyst | Audits briefs and results for confounds/overclaims; proposes experiments; never deploys |
| Expert panel | owner + domain judgment | Final judgment on subjective quality; authorizes real-vendor grade spend |
| Owner | decision authority | Approves budgets, deploys, vendor legs, and shipping |

## 2. Evidence levels (nothing below L3 may change the product)

- **L1 MOCK** — pipeline-behavior signal only; never explains real scores.
- **L2 Executed provenance** — `executed.full.*` worker report per run (settings, attempts, seeds, gates).
- **L3 Checkpoint** — O0–O5 pixel evidence per lab-seeded job (O0 source, O1 postwash, O2 precamera, O3 stage1, O4 preencode, O5 delivered) + manifest sha256.
- **L4 Corpus + real grades** — registered runs on the locked set with real-vendor paired grades (≤40 vendor calls/session, owner-authorized).

## 3. Phase 0 — Pilot (in progress)

- Grid: 4 images (IMG-5/6/9/11) × 4 configs (A/1A/2B/3C) × 2 seeds (`lab-ctla1`/`lab-ctla2`) = 32 cells.
- Every cell must carry `checkpoints.status = "captured"` (6 files, `errors: []`) before the grid is valid.
- Seeds: `^lab-[a-z0-9]{1,32}$` — **dash-free tail** (`lab-ctla1`, not `lab-ctl-a1`).
- Budget: 736 privacy + 32 DeepClean credits; 0 vendor calls.
- **Current blocker (cell 1 first-light):** `checkpoints.status = "error"` — RunPod env missing. Owner must set `DEEPCLEAN_CHECKPOINT_DIR=/runpod-volume/deepclean-checkpoints` + `DEEPCLEAN_CHECKPOINT_DURABLE=1`, then cell 1 is re-run fresh.

## 4. Phase 1 — Retrieval SOP (systemised, repeatable every round)

1. **Owner, once per retrieval (≈2 min):**
   - RunPod: scale the serverless endpoint workers to 0 (grid done; no jobs may run during retrieval).
   - Create a cheap CPU pod in the SAME data center as the network volume, attach the volume at `/runpod-volume`, open TCP port 22.
   - Download the pod SSH key to a stable local path (e.g. `/Users/a/.ssh/runpod-volume` — NEVER paste key contents into chat).
   - Tell the master engineer: pod SSH `host:port` and key path (non-secret).
2. **Master engineer executes (no secrets touched):**
   - `mkdir -p checkpoints-archive`
   - `scp -i <keypath> -r root@<host>:/runpod-volume/deepclean-checkpoints/ checkpoints-archive/` (use `-P <port>` when non-22)
   - Verify: exactly the expected per-job dirs exist, each with `O0_source.png O1_postwash.png O2_precamera.png O3_stage1.png O4_preencode.png O5_final.png` + manifest; cross-check each file's sha256 against the job's ledger manifest.
   - `ssh -i <keypath> root@<host> 'rm -rf /runpod-volume/deepclean-checkpoints/*'` (delete AFTER verification; worker never auto-deletes).
3. **Owner:** tear down the utility pod; scale endpoint workers back as needed.
4. **Master engineer:** run attribution (§4 below).

## 5. Phase 1b — Attribution (after 32 captured cells)

1. Run `tools/checkpoint_attribution.py` (ΔE76, directional 2-D rho, positional bands) and `tools/codec_replay.py` on the archived pairs (venv: `python3 -m venv "$TMPDIR/attr-venv" && pip install numpy pillow`).
2. Offender ranking per transition O0→O1 (wash), O1→O2 (camera), O2→O3 (stage-1 codec), O3→O4 (finisher), O4→O5 (delivery). Dominance rule: ≥1.5× loss vs runner-up and ≥0.35× total loss.
3. Seed determinism report: per (image, config), compare `lab-ctla1` vs `lab-ctla2` O2 pixel hashes (expect different) and stagewise metric deltas (expect similar).
4. Output: `ATTRIBUTION_REPORT.md` with the dominant offender + ranked candidates. No optimization is authorized before this exists.

## 6. Phase 2 — Optimization rounds (the loop)

For each round:
1. **Brief** (master engineer writes, D audits): ONE independent variable, prediction stated in advance with acceptance thresholds, forbidden-file list, budget.
2. **Build** (C8): implement exactly the brief; no wildcards; report all files changed; no commit/deploy.
3. **Verify** (master engineer): tsc/build/deno/tests/forbidden diff; golden reproduction where applicable; commit.
4. **Deploy** (owner-run): CI image → RunPod swap → warmup; edge fns as needed.
5. **Measure**: fixed protocol — same 4 images, both seeds, config under test vs baseline config; L3 checkpoints + L4 grades if the round is detection-relevant.
6. **Accept/reject**: lexicographic — (a) detection eligibility unchanged-or-better across the grid, (b) quality metric non-regressed (SSIM/noise/plateau/TDR), (c) subjective panel approval. Any regression on (a) or (b) = reject and revert.
7. **Ledger**: every round gets a dated row in `OPTIMIZATION_LEDGER.md` (variable, prediction, result, accept/reject, evidence level).

Rules:
- One variable per round. Never stack changes.
- Prediction-first; no post-hoc explanations for surprises without a new measurement.
- A rejected round does NOT allow an emergency un-briefed follow-up.
- Real-vendor grades only when the 40-call session cap permits and the owner authorizes.

## 7. Quality vs detection — two axes, never blended

- **Detection axis** = eligibility: delivered output must clear the source-aware gate (ai ≤ 0.45 AND flux-family ≤ 0.30 AND deepfake ≤ 0.10). MOCK numbers never count.
- **Quality axis** = selection: among eligible candidates, choose by non-generative quality (SSIM ≥ 0.90, noise floor ≥ 0.65, TDR ≥ 0.60, no ringing/banding/waxy).
- The oracle so far shows per-image config diversity — the endgame is probe-driven routing, not one universal preset. Routing candidates must beat the static best on ≥ 80% of the corpus before shipping.

## 8. Stop / rollback

- Any cell with unmapped error, any `mock: false`, any vendor overrun → immediate stop and owner report.
- A shipped build that regresses any paired row on the locked set → rollback to the previous verified digest (owner action) before any further round.

## 9. Current state (2026-08-26)
- V12.3 (`c569595`) deployed: worker linked, migration applied, edge fns live, P0 flag set.
- First-light cell 1 dispatched and seeded correctly (`lab-ctla1`, `lab:lab-ctla1` verified) — checkpoint capture blocked on RunPod env (owner action pending).
- Grid resume: after env fix + fresh cell 1, C8 runs cells 2–32 per the operator protocol.
