# ReMint 1.01 — PHASE B DISPOSITION (master engineer)

Date: 2026-08-30. Basis: 22 real Hive g1 grades (ledger
`round-remint-1-01/full-corpus/ledger.jsonl`,
`phase-b-detection-ledger.json`), independently re-verified by the master
engineer (order, hashes, vendor all confirmed).

## 1. Frozen thresholds, applied to delivered files

Thresholds: AI ≤ 0.45 · flux ≤ 0.30 · deepfake ≤ 0.10 · paired
non-amplification vs OG.

| Img | OG AI | RM AI | RM df | RM flux | RM verdict | Gates |
|---|---:|---:|---:|---:|---|---|
| 1 | 99.999 | 98.733 | 0.0 | 0.203 | FAIL | ✗ |
| 2 | 99.983 | 82.086 | 0.0 | 0.109 | FAIL | ✗ |
| 3 | 99.994 | 99.897 | 0.0 | 0.005 | FAIL | ✗ |
| 4 | 99.963 | 95.816 | 0.0 | 0.101 | FAIL | ✗ |
| 5 | 99.998 | 95.992 | 0.0 | 0.181 | FAIL | ✗ |
| 6 | 99.418 | 16.407 | 0.0 | 0.237 | BORDER | ✓ |
| 7 | 99.980 | 9.633 | 0.0 | 0.152 | CLEAR | ✓ |
| 8 | 99.989 | 46.333 | 0.0 | **0.522** | FAIL | ✗ (flux) |
| 9 | 99.997 | 22.008 | 0.0 | 0.004 | BORDER | ✓ |
| 10 | 99.989 | 1.501 | 0.0 | 0.001 | CLEAR | ✓ |
| 11 | 99.256 | 94.622 | 0.0 | 0.281 | FAIL | ✗ |

- All three thresholds pass on **4/11** delivered files.
- Paired non-amplification (RM AI ≤ OG AI + 0.02): **11/11 PASS** — the
  pipeline never worsens detection; it only reduces it, image-dependently.
- Deepfake 0.0 on all 22. Flux gate fails only IMG-8 (0.522).

## 2. Verdict

**ReMint 1.01 does NOT pass the Tier-2 promotion gate. It remains
non-production.** 7 of 11 delivered files are still flagged AI by the real
vendor; 2 reach CLEAR (IMG-7, IMG-10); 2 reach BORDER (IMG-6, IMG-9).

Combined with the quality floors (h1_energy PASS 0.3477; protected-EATR
5/6, IMG-9 marginal 0.947): no basis for promotion.

## 3. Honest interpretation — what this measurement actually says

1. **First real detection data in program history.** OG reads 99.3–100%
   (Hive is near-certain on all 11 originals). The chain reduces scores
   hugely on some images (99→9.6, 99→1.5) and barely on others
   (99→98.7, 99→99.9). Evasion is **image-dependent**, matching the
   earlier wash-proof-row pattern, not a config defect.
2. **MOCK was worthless for detection screening.** MOCK called IMG-5/6/7
   CLEAR and IMG-2/4/9/11 BORDER; the real vendor FAILs 5 of those and
   re-verdicts differently across the board. MOCK remains valid only as a
   mechanics check — this is now measured, not argued.
3. **The 1800 change itself is not implicated.** This leg graded OG vs
   1.01, not Config-A-fresh vs 1.01. The FAIL rows are the base pipeline's
   known wash-proof images; resolution is plausibly detection-neutral, but
   that attribution is UNMEASURED and must not be claimed.
4. **Re-stamp is real and visible:** RM top-sources are wan / flux / kling
   / bria / stablediffusion / gemini3 / adobefirefly — the wash output
   carries the generator's own fingerprints, as predicted in the layer map.

## 4. Budget reconciliation

Session vendor calls **21/40** (1 verification + 20 fresh leg calls),
2 cache hits (IMG-1 OG reused verification; IMG-8 OG pre-existing g1
entry), margin **19**. S1's original 24-call plan no longer fits; a slim
S1 (6 cells × O1/OR/O2 = 18 calls) fits the margin exactly and measures
wash value, resample value, and camera value on real grades.

## 5. Recommended next moves

1. **S1-slim stage ledger (18 calls)** — grade archived O1/OR/O2 of 6
   cells: measure where the detection margin actually comes from. This is
   the input the camera-decomposition decision needs.
2. Config-A-fresh pairs only if attribution of 1.01-vs-base is required —
   needs a new owner allocation (exceeds current margin).
3. IMG-9 protected-EATR: owner-ordered panel item I1 if promotion is ever
   re-attempted.

Signed: **Master Engineer (D) · 2026-08-30**
