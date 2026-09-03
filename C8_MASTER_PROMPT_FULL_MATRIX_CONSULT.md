# C8 MASTER PROMPT — FULL-MATRIX RESULTS CONSULTATION (opinion + improvement)

Role: C8 builder-architect, consulted in a fresh chat. **Analysis only — no
code changes.** Do not dispute the measured data; argue from it. Your
deliverable is an opinion report the owner reads before commissioning the
next build.

## 0. What happened (verified)

The ReMint deep-clean pipeline was run against all 11 corpus images under
4 frozen presets (44 remint cells + 44 real Hive g1 grades) plus the
existing ReMint 1.01 leg. All 55 delivered-vs-original pairs have real
detection grades. Everything was independently verified: settings codes
exact 44/44, byte-hashes 44/44, zero mock rows, non-amplification 55/55,
C2PA clean 44/44. The frozen quality-metric recipe reproduces the archived
1.01 floors bit-exact.

Governance (fixed, not up for debate here): real g1 grades only; vendor
freeze v3 thresholds AI ≤ 0.45, flux ≤ 0.30, deepfake ≤ 0.10; AR2 quality
gates still govern any future challenger; no production claim without a
promotion pass.

## 1. What each preset changes (the only differences)

| Preset | Difference from Config A |
|---|---|
| Config A | qwen wash · deep · finish strong S1.25 · delivery capped 1250 |
| Config 1A | wash = qwen + z-image (two-model wash) |
| Config 2B | stage-1 JPEG Q97 + 4:4:4 subsampling (higher-fidelity intermediate) |
| Config 3C | both: qwen+zimage wash AND Q97 4:4:4 (lab control) |
| ReMint 1.01 | identical to A except output_target 1800 (delivery = min(src,1800)) |

## 2. Real detection matrix (AI %, verdict; thresholds pass ≤ 0.45)

| Image | OG | A | 1A | 2B | 3C | 1.01 |
|---|---|---|---|---|---|---|
| IMG-1 | 100 FAIL | 98.7 FAIL | 99.6 FAIL | 99.8 FAIL | 99.9 FAIL | 98.7 FAIL |
| IMG-2 | 100 FAIL | 82.1 FAIL | 96.5 FAIL | 99.1 FAIL | 99.8 FAIL | 82.1 FAIL |
| IMG-3 | 100 FAIL | 99.9 FAIL | 99.9 FAIL | 100 FAIL | 100 FAIL | 99.9 FAIL |
| IMG-4 | 100 FAIL | 95.8 FAIL | 99.9 FAIL | 98.3 FAIL | 99.9 FAIL | 95.8 FAIL |
| IMG-5 | 100 FAIL | 97.8 FAIL | **25.6 BORDER** | 99.7 FAIL | 72.9 FAIL | 96.0 FAIL |
| IMG-6 | 99.4 FAIL | **16.4 BORDER** | 39.3 FAIL | 78.0 FAIL | 89.4 FAIL | **16.4 BORDER** |
| IMG-7 | 100 FAIL | **9.6 CLEAR** | **7.7 CLEAR** | 30.3 FAIL | 71.4 FAIL | **9.6 CLEAR** |
| IMG-8 | 100 FAIL | 46.3 FAIL | 83.5 FAIL | 66.6 FAIL | 89.5 FAIL | 46.3 FAIL |
| IMG-9 | 100 FAIL | **5.7 CLEAR** | 97.5 FAIL | **20.2 BORDER** | 99.3 FAIL | **22.0 BORDER** |
| IMG-10 | 100 FAIL | **0.3 CLEAR** | **0.4 CLEAR** | **0.8 CLEAR** | **0.7 CLEAR** | **1.5 CLEAR** |
| IMG-11 | 99.3 FAIL | 53.5 FAIL | 88.0 FAIL | 79.1 FAIL | 93.8 FAIL | 94.6 FAIL |

Pass counts: A 4/11 · 1A 2/11 · 2B 2/11 · 3C 1/11 · 1.01 4/11.
Sources ≤ 1250 produce byte-identical outputs for A and 1.01 (IMG-1..4, 6, 7, 8).

## 3. Frozen quality metrics (cohort means, same recipe)

| Preset | H1 energy | H0 | H2 | prot. EATR min | tex luma RMS |
|---|---|---|---|---|---|
| A | 0.4550 | 0.1622 | 0.7750 | 0.4430 | 23.90 |
| 1A | 0.3853 | 0.1307 | 0.6672 | 0.3190 | 18.69 |
| 2B | 0.4873 | 0.2474 | 0.7806 | 0.4623 | 24.03 |
| 3C | 0.4185 | 0.2112 | 0.6728 | 0.3432 | 18.78 |
| 1.01 | 0.4509 | 0.1590 | 0.7829 | 0.4194 | 24.57 |

## 4. The measured puzzles (answer all)

1. **Seven of eleven images resist every preset.** No wash model, encoding
   quality, or delivery size in this matrix moves IMG-1/2/3/4/5/8/11 below
   the threshold. Where is the surviving signal? Propose the most likely
   layer(s) per the L1–L4 map (watermark / statistical fingerprint /
   physical-optical / semantic) and why a wash that kills one fingerprint
   class leaves another.
2. **Config 1A (z-image added) is the only preset that moves IMG-5**
   (97.8 → 25.6) and edges IMG-7 — but it regresses IMG-1/2/4/8/9/11
   versus plain Config A. What mechanism could make a second wash model
   image-specific in BOTH directions?
3. **Config 2B (Q97 4:4:4 stage-1) keeps the most H1 energy (0.487) yet
   clears the least.** Why does higher-fidelity intermediate encoding
   INCREASE detector scores? This implies the default stage-1 encoding is
   itself destroying signal — quantify the implication.
4. **Config 3C is not the sum of 1A and 2B** (IMG-5: 25.6 and 99.7 compose
   into 72.9; IMG-9: 97.5 and 20.2 compose into 99.3). The two changes
   interact non-additively. What does that tell us about stage ordering?
5. **Delivery resolution:** A (1250) beats 1.01 (1800) on IMG-9 (5.7 vs
   22.0) and IMG-11 (53.5 vs 94.6). Why would the DETECTOR prefer the
   smaller delivery, and what does that say about where the signal lives?

## 5. Improvement options (rank them)

Rank each with expected detection gain (coarse), fidelity cost, build
cost, and freeze/replay impact. Use the measured numbers above as
evidence, not vibes. Consider at least: (a) wash depth policy per image;
(b) camera-ladder decomposition or minimum-strength camera; (c) delivery
resolution policy; (d) stage-1 encoding as a deliberate signal-destruction
layer; (e) detector-adaptive ladder strength; (f) dormant
photo_naturalization I2I path; (g) image-dependent preset routing;
(h) reordering wash/camera/resample. Say explicitly which options are
already falsified by this matrix and should NOT be funded.

## 6. Next experiment (decide one)

Pick the single highest-information next experiment and specify: exact
cells, frozen settings, real-grade budget, freeze requirements, and the
decision rule it feeds. Budget context: 18 real calls are reserved for the
S1-slim stage ledger (grade O1/OR/O2 intermediates); propose more only if
clearly better.

## 7. Deliverable

Report ≤ 2 pages: per-question verdicts (§4), ranked options with a single
recommended next commission (§5–6). Owner + master engineer will read it
and freeze the next build.
