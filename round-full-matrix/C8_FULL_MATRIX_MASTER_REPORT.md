# FULL MATRIX — MASTER ENGINEER REPORT (real-only, 5 presets × 11 images)

Date: 2026-08-30 · Master engineer · Frozen recipes from
`tools/round_remint_1_01_validate.py` (metric_record + _roi_for).

## 1. What was run

Flash executed the reissued runbook on a fresh /relab session (cap 10000):
**44 cells** (Config A, Config 1A, Config 2B, Config 3C × IMG-1..11, seed
`lab-ctla1`) + **44 real g1 grades**. OG grades (11) and ReMint 1.01 grades
(11) were reused, never re-graded. Zero mock rows. 1,012 credits
(991264 → 990252, exact).

## 2. Independent verification (mine, not Flash's)

| Check | Result |
|---|---|
| ledger.jsonl JSON validity | 56/56 lines parse |
| Cell rows / presets / order | 44 cells, 4 presets, IMG-1..11 in order |
| Settings codes exact | 44/44 (hard-checked against the four required codes) |
| vendor / mock | g1 44/44, mock false 44/44 |
| OG reuse / RM freshness | og_cache_hit 44/44, rm fresh 1 call each |
| Source hashes vs canonical files | 44/44 byte-match |
| Delivered SHA-256 pins | 44/44 byte-match (I re-hashed every file) |
| Phase-B verbatim ledger | 44 rows, task ids + flux-family present |
| Phase-B ai == Phase-A rm_ai | 44/44 (cache-hit consistency) |
| C2PA deny-list | 44/44 clean |
| Credits | 44 × 23 = 1012 exact |

**Frozen floors reproduction:** my metric run reproduces
`floors-1.01-live.json` to 9 decimals on all 6 sentinels (H1 energy and
protected EATR for Config A and ReMint 1.01). The recipe is bit-exact.

## 3. Frozen quality metrics (cohort, same frozen recipe)

| Preset | H1 energy | H0 energy | H2 energy | protected EATR min | eatr p95 | tex luma RMS | rho1 |
|---|---|---|---|---|---|---|---|
| Config A | 0.4550 | 0.1622 | 0.7750 | 0.4430 | 0.6914 | 23.90 | 0.7254 |
| Config 1A | 0.3853 | 0.1307 | 0.6672 | 0.3190 | 0.6382 | 18.69 | 0.6288 |
| Config 2B | 0.4873 | 0.2474 | 0.7806 | 0.4623 | 0.7116 | 24.03 | 0.7170 |
| Config 3C | 0.4185 | 0.2112 | 0.6728 | 0.3432 | 0.6604 | 18.78 | 0.6167 |
| ReMint 1.01 | 0.4509 | 0.1590 | 0.7829 | 0.4194 | 0.6909 | 24.57 | 0.7493 |

Caveat (frozen): vs-source energy ratios are resolution-sensitive; delivered
dims differ per preset/cell (Config A caps delivery at 1250, 1.01 at 1800).
Full per-file record: `round-full-matrix/frozen-metrics.json`.

## 4. Real detection matrix (vendor freeze v3 thresholds: AI ≤ 0.45, flux ≤ 0.30)

| Image | OG | Config A | Config 1A | Config 2B | Config 3C | ReMint 1.01 |
|---|---|---|---|---|---|---|
| IMG-1 | 100.0 FAIL | 98.7 FAIL | 99.6 FAIL | 99.8 FAIL | 99.9 FAIL | 98.7 FAIL |
| IMG-2 | 100.0 FAIL | 82.1 FAIL | 96.5 FAIL | 99.1 FAIL | 99.8 FAIL | 82.1 FAIL |
| IMG-3 | 100.0 FAIL | 99.9 FAIL | 99.9 FAIL | 100.0 FAIL | 100.0 FAIL | 99.9 FAIL |
| IMG-4 | 100.0 FAIL | 95.8 FAIL | 99.9 FAIL | 98.3 FAIL | 99.9 FAIL | 95.8 FAIL |
| IMG-5 | 100.0 FAIL | 97.8 FAIL | **25.6 BORDER** | 99.7 FAIL | 72.9 FAIL | 96.0 FAIL |
| IMG-6 | 99.4 FAIL | **16.4 BORDER** | 39.3 FAIL | 78.0 FAIL | 89.4 FAIL | **16.4 BORDER** |
| IMG-7 | 100.0 FAIL | **9.6 CLEAR** | **7.7 CLEAR** | 30.3 FAIL | 71.4 FAIL | **9.6 CLEAR** |
| IMG-8 | 100.0 FAIL | 46.3 FAIL | 83.5 FAIL | 66.6 FAIL | 89.5 FAIL | 46.3 FAIL |
| IMG-9 | 100.0 FAIL | **5.7 CLEAR** | 97.5 FAIL | **20.2 BORDER** | 99.3 FAIL | **22.0 BORDER** |
| IMG-10 | 100.0 FAIL | **0.3 CLEAR** | **0.4 CLEAR** | **0.8 CLEAR** | **0.7 CLEAR** | **1.5 CLEAR** |
| IMG-11 | 99.3 FAIL | 53.5 FAIL | 88.0 FAIL | 79.1 FAIL | 93.8 FAIL | 94.6 FAIL |

Per-preset summary:

| Preset | threshold pass | CLEAR | BORDER | non-amplification |
|---|---|---|---|---|
| Config A | **4/11** | 3 | 1 | 11/11 |
| Config 1A | 2/11 | 2 | 1 | 11/11 |
| Config 2B | 2/11 | 1 | 1 | 11/11 |
| Config 3C | 1/11 | 1 | 0 | 11/11 |
| ReMint 1.01 | 4/11 | 2 | 2 | 11/11 |

Non-amplification (RM ≤ OG) holds **55/55** across every preset and image.

## 5. Findings

1. **No preset passes production promotion.** Best case is Config A / ReMint
   1.01 at 4/11 under thresholds. The wash pipeline cannot clear 7 of 11
   images at any tested configuration.
2. **Evasion is image-dependent, not config-dependent.** IMG-7/9/10 clear
   under multiple presets; IMG-1/2/3/4/5/8/11 resist everything. The
   decision boundary is dominated by source image properties.
3. **Resolution lever is real but narrow.** Config A (delivery 1250) beats
   ReMint 1.01 (delivery ≤1800) on IMG-9 (5.7 vs 22.0) and IMG-11
   (53.5 vs 94.6); sources ≤1250 produce byte-identical outputs for both.
4. **Fidelity vs detection tradeoff measured:** Config 2B retains the most
   H1 energy (0.487) yet scores worst-tier detection (2/11). Config A
   balances best (0.455 H1, 4/11).
5. **Config 1A is the only preset that clears IMG-5** (25.6 BORDER) and
   narrowly bests Config A on IMG-7 — but it regresses 6 other images vs A.
   No free lunch.
6. **Mock grades are dead for screening.** Every historical mock CLEAR/BORDER
   on these presets was mechanical; the real matrix re-ranks everything
   (e.g., mock-clear IMG-5 fails real grading under A/2B/3C/1.01).

## 6. SlashBase wiring (done, deploy pending)

- Importer now preset-aware (fail-closed, real-only unchanged).
- Seed: 22 verified 1.01 rows + **88 new matrix rows** (44 OG-stamped + 44
  delivered), generated from the verified ledger.
- 55 cards across 5 preset filters; exact delivered bytes as image assets
  (Grade button grades the true delivered file).
- Tests 4/4 green, `tsc` clean, production build clean (66 image assets
  emitted).

Owner action: deploy to Vercel (auto-deploy on push or manual).

## 7. Next options (new commission needed)

1. **S1-slim stage ledger** (18 real calls) — grade O1/OR/O2 intermediates
   to find which stage carries the detection signal per image.
2. **Image-dependent preset routing** — Config A for most, Config 1A for
   IMG-5/7-class images; needs a router spec + new freeze.
3. **Wash policy redesign** — the 7 resistent images define the real
   wash-policy problem; camera ladder decomposition is the measured lever.
