# FLASH OPERATOR — ReMint 1.01 FULL-CORPUS HIVE PASS STOP REPORT

Runbook: `FLASH_OPERATOR_PROMPT_REMINT_1_01_FULL_CORPUS.md` (Option B, locked).
Executed 2026-08-30. **Phase A COMPLETE (11/11). Phase B STOPPED before any call
per Section 1 P0 step 2 + Section 5 (real Hive provider not enabled).**

## 1. Pre-flight (P0) — all PASSED

| Check | Result |
|---|---|
| Signed in as owner | ✅ `anthonyx33@proton.me` |
| ReMint 1.01 preset | ✅ **ACTIVE** (Config A shows SELECT / OFF) |
| Lab paired seed | ✅ `lab-ctla1` |
| Settings-code chip | ✅ **`SEQ-1.01-yg63qja3got4`** (exact required marker) |
| Detector mode | ✅ MOCK (server-side; provider `mock`) |
| Credit balance before | **991517** (recorded in ledger) |
| Queue | ✅ cleared (0/20), 11 canonical sources loaded in order IMG-1…IMG-11 |
| Load method | ✅ regular `/relab` file add — NOT the corpus picker (no `item.corpus`, so no corpus-run-intent / corpus-register-run, IMG-5/6 output caps sidestepped) |

## 2. Phase A — 11/11 COMPLETE

All 11 images run through **ReMint 1.01 · seed `lab-ctla1` · marker
`SEQ-1.01-yg63qja3got4` · MOCK** in order. No stops, no code mismatches, no
errors. Every cell consumed **23 credits** (balance 991517 → 991264; total
**253**, exactly 11 × 23). All ledger rows show `settings_code` exactly
`SEQ-1.01-yg63qja3got4`, `mock:true`, `provider_calls:0`.

| # | Image | Job id | OG AI% → RM AI% | Verdict |
|---|---|---:|---:|---|
| 1 | IMG-1 | `2547e071-33e2-45ef-9dc2-aa37c1b26f73` | 36.2 → 40.4 | FAIL |
| 2 | IMG-2 | `db1f549f-e365-4775-b8a1-afb0eef8a9a4` | 4.3 → 27.8 | BORDER |
| 3 | IMG-3 | `7efebc89-186d-47a2-9fce-a81c30685b99` | 8.3 → 45.1 | FAIL |
| 4 | IMG-4 | `9817af5a-7adb-4af1-9999-82da3b79f3c3` | 39.1 → 19.8 | BORDER |
| 5 | IMG-5 | `e9aa44da-2a53-4c15-8887-1360d9de0420` | 46.2 → 9.5 | CLEAR |
| 6 | IMG-6 | `d62b5188-2d16-48ef-8d24-a5e34675ce38` | 37.7 → 8.2 | CLEAR |
| 7 | IMG-7 | `eb3dd2cf-1edb-40e8-af9d-7ba25e386fa3` | 35.7 → 9.7 | CLEAR |
| 8 | IMG-8 | `d35e67a4-7c5e-4baf-8411-87d78c2d9dc7` | 23.6 → 40.9 | FAIL |
| 9 | IMG-9 | `12a75905-3ad7-476e-93b1-45ff48fd0cfb` | 39.8 → 26.1 | BORDER |
| 10 | IMG-10 | `fd3fb4d9-c44a-47f4-9702-d45671ad7700` | 24.9 → 45.8 | FAIL |
| 11 | IMG-11 | `c34711a6-6d26-40f0-b2cb-caae4784cc82` | 47.7 → 21.4 | BORDER |

*(MOCK grades — deterministic per-hash salts; not vendor evidence.)*

## 3. Files — 22/22 downloaded and hash-pinned

All 22 files saved to `round-remint-1-01/full-corpus/` and every SHA-256
verified against the `/relab` ledger:

- **Group OG (11):** `IMG-1_source.jpg … IMG-11_source.jpeg` — byte-identical to
  the canonical `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-N.*` files; each SHA-256
  equals the ledger `og_grade.image_sha256` (11/11 OK).
- **Group RM (11):** `1.01_IMG-N_lab-ctla1.jpg` — each SHA-256 equals the ledger
  `remint_grade.image_sha256` (11/11 OK). Delivered dims: IMG-1..4 1024², IMG-5
  1800², IMG-6 800², IMG-7/8 1080², IMG-9 1600², IMG-10/11 1800² (output_target
  1800, capped by source where smaller).

Full per-file hashes: `ledger.jsonl` (events `cell_complete`, rows 1–11).

## 4. Visual checklist — 11 before/after pairs

Method: geometry-matched (source resampled to delivered lattice) objective
metrics (HF-energy retention, edge overshoot, smooth-area level ratio, tile
grain uniformity, luma/chroma shift, SSIM). Tick OK unless noted.

| Pair | Blur/soft | Ringing | Banding | Grain | Color | Gross | Note |
|---|---|---|---|---|---|---|---|
| IMG-1 | OK | OK | OK | OK | OK | OK | |
| IMG-2 | OK | OK | OK | OK | OK | OK | |
| IMG-3 | OK | OK | FLAG | OK | OK | OK | banding (level ratio 2.14) |
| IMG-4 | OK | OK | FLAG | OK | OK | OK | banding (1.88) |
| IMG-5 | FLAG | OK | OK | OK | OK | OK | softness (HF retention 0.165) |
| IMG-6 | OK | OK | OK | OK | OK | OK | |
| IMG-7 | FLAG | FLAG | OK | OK | OK | OK | softness + ringing (36.5) |
| IMG-8 | FLAG | OK | FLAG | OK | OK | OK | softness + banding (2.35) |
| IMG-9 | FLAG | FLAG | OK | OK | FLAG | OK | softness + ringing (41.1) + color (dL 16.0) |
| IMG-10 | OK | OK | OK | OK | OK | OK | |
| IMG-11 | OK | FLAG | OK | OK | OK | OK | ringing (32.6) |

No gross artifacts on any pair (SSIM 0.865–0.976). Flags are the known
wash+camera pipeline signature, consistent with prior 4D measurements.

## 5. Phase B — STOPPED before any call (Section 1 P0 step 2 / Section 5)

**Stop condition:** the real Hive provider is NOT enabled. The runbook requires
the master engineer to confirm the real Hive provider (vendor key + parser
verification) before Phase B, and the UI shows MOCK as the only grade mode.

Verified facts (operator-side):
- Deployed `GRADE_PROVIDER` secret decodes to **`mock`**
  (secret hash `ec864fe9…` = sha256("mock")). `GRADE_DEFAULT_MODE` = `real`.
- `grade-image` edge function `providerName()` returns `mock` unless
  `GRADE_PROVIDER=g1`; the `g1` path also requires `HIVE_SECRET_KEY` and only
  the server has it. The `HIVE_ACCESS_KEY_ID` / `HIVE_SECRET_KEY` secrets exist,
  but the provider switch is still `mock`.
- The `/relab` UI label "HIVE API / LIVE server-side adapter" refers to the
  adapter architecture (credentials never enter the browser), NOT to real
  vendor calls. All 13 ledger rows are `mock:true` and `provider_calls:0`.
- Vendor-call counter: **0 / 40 used** this session. Phase B calls: **0 spent**.

**Result:** 0 of the 22 authorized Phase B calls were spent. The paired
OG-vs-1.01 leg is fully prepared (all 22 files hash-pinned, ledger order = per
image OG first then RM) and requires only the provider switch before it can run.

## 6. What I did NOT do (operator discipline)

- ❌ Did not spend any Phase B call (0/22 used; 40-call cap untouched; 18 margin intact).
- ❌ Did not change `GRADE_PROVIDER`, secrets, thresholds, caps, seeds, or presets (governance/master-engineer scope).
- ❌ Did not retry, re-order, or drop any file.
- ❌ Did not compute the OG-vs-1.01 comparison (master engineer's job).
- ❌ Did not touch the S1 stage-ledger's 24 reserved calls (deferred per written allocation).

## 7. What is required to unblock Phase B (for master engineer / owner)

1. Switch the grade provider to real Hive: set `GRADE_PROVIDER=g1` (verify
   `HIVE_SECRET_KEY` / `HIVE_ACCESS_KEY_ID` and run the parser verification the
   owner gate requires), or confirm the provider was enabled and re-check.
2. Confirm the ledger entry for the 22-call allocation (written 2026-08-30:
   S1's 24 reserved calls deferred; this leg consumes 22 of the 40-call
   reserve, 18 margin) is recorded.
3. Re-issue the runbook / Phase B authorization; the operator resumes at
   Phase B with all 22 files already hash-pinned in `ledger.jsonl`.

## 8. Ledger and files

- Ledger: `round-remint-1-01/full-corpus/ledger.jsonl` — P0, queue-loaded,
  11 × `cell_complete`, `phase_a_complete`, `phase_b_provider_gate`.
- Files: `1.01_IMG-N_lab-ctla1.jpg` (11 delivered) + `IMG-N_source.*` (11
  sources) + `pairs/IMG-N_pair.jpg` (11 side-by-side checklist images).

## 9. Declaration (Section 6)

"I ran exactly the steps in this runbook, in order, preset ReMint 1.01, marker
`SEQ-1.01-yg63qja3got4`, seed `lab-ctla1`, MOCK grades in Phase A and **no** real
Hive calls in Phase B (stopped at the Section 1 P0 step 2 provider gate because
the real provider is not enabled), and made no engineering decisions. Ledger
and files are complete and unmodified."

Signed: Flash operator
Date / time: 2026-08-30
