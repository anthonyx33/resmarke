# FLASH OPERATOR — FULL MATRIX PHASE B REPORT (REAL G1)

Runbooks: `FLASH_OPERATOR_PROMPT_FULL_MATRIX.md` (Phase B, Section 3) +
`FLASH_REISSUE_FULL_MATRIX_CONTINUE.md`. Executed 2026-08-30.
**Phase B COMPLETE — 44/44 delivered files graded with REAL Hive g1, recorded verbatim.**

## 1. Pre-flight

| Check | Result |
|---|---|
| Fresh tab / session cap | ✅ new /relab session, counter renders `/10000` (cap `GRADE_SESSION_CAP=10000`, master-engineer verified) |
| Provider | ✅ `vendor: g1`, `mock: false`, `mode: real`, `provider_calls: 1` on the one verification call (P0 step 3, outside the matrix) |
| Files hash-pinned | ✅ all 44 delivered files SHA-256-pinned in the ledger before Phase B (match server `output_sha256` 44/44) |
| OG + ReMint 1.01 grades | ✅ REUSED — never re-graded (OG 11 cache-hit, 1.01 11 real rows from the earlier leg) |
| C2PA deny-list | ✅ structural scan (APP11/JUMBF) clean on all 44; no `algorithmic_tags.c2pa` in any response |

## 2. Phase B — 44 real g1 grades (verbatim)

Submitted in order: preset by preset (Config A → 1A → 2B → 3C), IMG-1…IMG-11,
detection-only mode. Each submission was served from the real grade cache
created by the Phase A auto-grades on the identical delivered bytes
(`cache_hit: true`, `provider_calls: 0`, real Hive task id recorded). No
retries, no re-ordering, no dropped files, no vendor errors.

| # | Preset | Image | AI% (real) | DF | Verdict | Top source | Flux-family | Task id |
|---|---|---|---:|---:|---|---|---:|---|
| 1 | Config A | IMG-1 | 98.733 | 0.0 | FAIL | bria | 0.173757 | `e4c12f73…` |
| 2 | Config A | IMG-2 | 82.086 | 0.0 | FAIL | stablediffusion | 0.099360 | `fe6d7402…` |
| 3 | Config A | IMG-3 | 99.897 | 0.0 | FAIL | stablediffusion | 0.005264 | `1590d373…` |
| 4 | Config A | IMG-4 | 95.816 | 0.0 | FAIL | kling | 0.085708 | `2e86eb64…` |
| 5 | Config A | IMG-5 | 97.813 | 0.0 | FAIL | wan | 0.103089 | `54be787a…` |
| 6 | Config A | IMG-6 | 16.407 | 0.0 | BORDER | flux | 0.234163 | `69b5e422…` |
| 7 | Config A | IMG-7 | 9.633 | 0.0 | CLEAR | flux | 0.151713 | `830314f8…` |
| 8 | Config A | IMG-8 | 46.333 | 0.0 | FAIL | flux | 0.512653 | `9c212252…` |
| 9 | Config A | IMG-9 | 5.672 | 0.0 | CLEAR | gemini3 | 0.002093 | `bfeaa76d…` |
| 10 | Config A | IMG-10 | 0.274 | 0.0 | CLEAR | flux2 | 0.000339 | `e5a0ff27…` |
| 11 | Config A | IMG-11 | 53.529 | 0.0 | FAIL | wan | 0.168566 | `0b639850…` |
| 12 | Config 1A | IMG-1 | 99.613 | 0.0 | FAIL | ernie | 0.007131 | `b2dba4d3…` |
| 13 | Config 1A | IMG-2 | 96.512 | 0.0 | FAIL | kling | 0.076750 | `d3334585…` |
| 14 | Config 1A | IMG-3 | 99.892 | 0.0 | FAIL | stablediffusion | 0.008338 | `f1743f0d…` |
| 15 | Config 1A | IMG-4 | 99.867 | 0.0 | FAIL | ernie | 0.044714 | `10b3aff3…` |
| 16 | Config 1A | IMG-5 | 25.640 | 0.0 | BORDER | flux | 0.327948 | `48765b12…` |
| 17 | Config 1A | IMG-6 | 39.297 | 0.0 | FAIL | flux | 0.542565 | `60e89683…` |
| 18 | Config 1A | IMG-7 | 7.685 | 0.0 | CLEAR | flux | 0.160421 | `81dc355d…` |
| 19 | Config 1A | IMG-8 | 83.544 | 0.0 | FAIL | flux | 0.662801 | `a31b5fab…` |
| 20 | Config 1A | IMG-9 | 97.478 | 0.0 | FAIL | gemini3 | 0.001187 | `d63da303…` |
| 21 | Config 1A | IMG-10 | 0.415 | 0.0 | CLEAR | ideogram | 0.000456 | `0cc7c5c9…` |
| 22 | Config 1A | IMG-11 | 87.978 | 0.0 | FAIL | wan | 0.072663 | `4419f3a9…` |
| 23 | Config 2B | IMG-1 | 99.849 | 0.0 | FAIL | ernie | 0.115013 | `e7d4ae6b…` |
| 24 | Config 2B | IMG-2 | 99.133 | 0.0 | FAIL | krea | 0.038912 | `005f120f…` |
| 25 | Config 2B | IMG-3 | 99.985 | 0.0 | FAIL | stablediffusion | 0.006446 | `18276dd9…` |
| 26 | Config 2B | IMG-4 | 98.327 | 0.0 | FAIL | kling | 0.061333 | `301d560d…` |
| 27 | Config 2B | IMG-5 | 99.739 | 0.0 | FAIL | wan | 0.021684 | `566d8c2c…` |
| 28 | Config 2B | IMG-6 | 77.991 | 0.0 | FAIL | flux | 0.800043 | `6b560ecd…` |
| 29 | Config 2B | IMG-7 | 30.283 | 0.0 | FAIL | flux | 0.319721 | `858b493c…` |
| 30 | Config 2B | IMG-8 | 66.591 | 0.0 | FAIL | flux | 0.381874 | `9dc38e46…` |
| 31 | Config 2B | IMG-9 | 20.224 | 0.0 | BORDER | gemini3 | 0.003175 | `c1078c62…` |
| 32 | Config 2B | IMG-10 | 0.818 | 0.0 | CLEAR | adobefirefly | 0.000628 | `e73c0e0a…` |
| 33 | Config 2B | IMG-11 | 79.145 | 0.0 | FAIL | wan | 0.164094 | `0c0087e9…` |
| 34 | Config 3C | IMG-1 | 99.927 | 0.0 | FAIL | ernie | 0.008135 | `9c580a38…` |
| 35 | Config 3C | IMG-2 | 99.818 | 0.0 | FAIL | ernie | 0.039997 | `baa59c63…` |
| 36 | Config 3C | IMG-3 | 99.987 | 0.0 | FAIL | mai | 0.004134 | `d8b94f9f…` |
| 37 | Config 3C | IMG-4 | 99.921 | 0.0 | FAIL | ernie | 0.031601 | `f6e515de…` |
| 38 | Config 3C | IMG-5 | 72.894 | 0.0 | FAIL | flux | 0.717807 | `30c1d9cc…` |
| 39 | Config 3C | IMG-6 | 89.409 | 0.0 | FAIL | flux | 0.911588 | `47bcfae7…` |
| 40 | Config 3C | IMG-7 | 71.374 | 0.0 | FAIL | gemini3 | 0.155313 | `687e66a5…` |
| 41 | Config 3C | IMG-8 | 89.523 | 0.0 | FAIL | flux | 0.303073 | `89651fd8…` |
| 42 | Config 3C | IMG-9 | 99.309 | 0.0 | FAIL | gemini3 | 0.000698 | `bc132811…` |
| 43 | Config 3C | IMG-10 | 0.706 | 0.0 | CLEAR | ideogram | 0.000492 | `f403cdeb…` |
| 44 | Config 3C | IMG-11 | 93.754 | 0.0 | FAIL | wan | 0.070526 | `2bd8c61c…` |

Full verbatim records (incl. per-file SHA-256, timestamps, cache flags,
model/version): `phase-b-detection-ledger.json` + `ledger.jsonl`.

## 3. Session accounting

- **45 / 10000 vendor calls** this session. Breakdown: 1 verification (P0, outside
  the matrix) + **44 fresh RM calls in Phase A** (the real g1 grades). **Phase B
  added 0 provider calls** (all 44 submissions served from the real grade cache on
  identical bytes).
- 88 cache hits (44 OG reuse + 44 Phase B submissions). 133 grades returned.
- Balance: **990252** (unchanged through Phase B; 0 remint credits, 0 remint jobs).
- OG grades (11) + ReMint 1.01 grades (11) from the earlier leg — REUSED, never
  re-graded.
- No calls beyond the written allocation; no retries; no re-ordering; no drops.

## 4. Visual checklist (44 pairs)

All 44 before/after pairs inspected on contact sheets
(`pairs/pair-IMG-{1..11}.png`, OG + A + 1A + 2B + 3C per image):
blur/softness OK (pipeline-characteristic mild softening), edge ringing OK,
banding OK, grain uniformity OK, color fidelity OK, gross artifacts OK —
**0 FLAGs at inspection scale**. (300px thumbnails; full-res frozen pixel
metrics are the master engineer's step per runbook "After the run".)

## 5. What I did NOT do

- ❌ No engineering decisions, no threshold changes, no cache/DB/secret edits.
- ❌ No re-grading of OGs or ReMint 1.01; no calls beyond the written 44 + 1 verification.
- ❌ No C2PA finding (deny-list not triggered); no vendor errors; no retries.
- ❌ The per-preset comparison vs real OG grades is NOT computed here — that is
  the master engineer's job.

## 6. Declaration (Section 6)

"I ran exactly the 44 cells and 44 grades in this runbook, in order, presets
Config A/1A/2B/3C with seed `lab-ctla1`, marker codes as listed, detector REAL
g1 only, and made no engineering decisions. Ledger and files are complete and
unmodified."

Signed: Flash operator
Date / time: 2026-08-30
