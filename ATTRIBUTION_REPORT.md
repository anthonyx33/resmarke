# ATTRIBUTION_REPORT — 32-cell seeded lab pilot (V12.3, c569595)

Date: 2026-08-26 · Master engineer · zero vendor grades consumed
Tools: `deepclean-worker/tools/checkpoint_attribution.py` (patched, native + normalized) + `tools/codec_replay.py`
Data: retrieved RunPod volume checkpoints, pixel-hash verified vs the /relab ledger

## 0. Data provenance (why this is trustworthy)

- 33 checkpoint dirs retrieved from `/runpod-volume/deepclean-checkpoints` (506 MB tarball, 198 files).
- Transfer integrity: local file-sha256 vs pod-side manifest — **198/198, zero diff**.
- Ledger identity: all 32 `captured` jobs re-hashed **pixel-wise** (`pixel_sha256` = width‖height‖RGB tobytes) against the /relab ledger — **192/192 match, zero mismatches**.
  (Ledger hashes are pixel hashes, not PNG hashes — that is why a naive file-hash check "fails".)
- Excluded: `d2f1a8d5` (error row, no checkpoints — correct), `daf0f0a7` (volume dir with no ledger row — superseded dispatch).
- Metrics are diagnostics only; no production thresholds. All grades below are MOCK by design.

## 1. Global dominance — where quality is lost

Transition loss = max(|min(dEATR,0)|, |min(dHFTR_H1,0)|) between consecutive checkpoints.
Band rule: PRIMARY ≥35% · CO-PRIMARY ≥25% · SECONDARY 10–25% · NEGLIGIBLE <10%.

| Transition | Content (code-verified) | Mean loss | PRIMARY count (n=32) |
|---|---|---|---|
| O0→O1 | wash (source res) + histogram restore | 0.1517 | **12/32** |
| O1→O2 | LANCZOS resample ≤1250 + camera ladder | **0.1764** | **23/32** |
| O2→O3 | tone-lock + stage-1 JPEG q92 4:2:0 | 0.0538 | 4/32 |
| O3→O4 | Quality Finish | 0.0488 | 0/32 (secondary) |
| O4→O5 | final JPEG encode | ≈0.0000 | 0/32 |

Mean transition deltas: O0→O1 dEATR −0.1450 / dHFTR_H1 −0.1136 · O1→O2 −0.1710 / −0.1645 ·
O2→O3 −0.0524 / −0.0456 · O3→O4 −0.0321 / −0.0488 · O4→O5 +0.0028 / +0.0036.

**Top line: the resample+camera step (O1→O2) is the largest single loss (mean 0.176, PRIMARY in 72% of jobs),**
with the regenerative wash (O0→O1) a close second (0.152, PRIMARY in 38%).

## 2. By image (resolution split)

| Source (long edge) | PRIMARY pattern |
|---|---|
| IMG-5 (2048px) | wash 8/8 — wash dominates at max resolution |
| IMG-11 (2048px) | camera+resample 8/8 — wash not primary at all |
| IMG-9 (1600px) | camera 8, wash 4 |
| IMG-6 (800px, same-resolution) | camera 7, stage-1 codec 4, wash 0 |

Wash damage is **image-dependent** (catastrophic on IMG-5, absent on IMG-6/11);
camera+resample damage is universal. At same-resolution material (IMG-6) the camera
ladder itself — not resample — is the dominant loss, and the stage-1 codec becomes
visible as a primary in half the jobs.

## 3. By config and seed

| Config | PRIMARY |
|---|---|
| A | O1→O2 6, O0→O1 2, O2→O3 2 |
| 1A | O1→O2 5, O0→O1 4, O2→O3 2 |
| 2B | O1→O2 6, O0→O1 2 |
| 3C | O1→O2 6, O0→O1 4 |

Seed symmetry (good sign — no seed-side pathology):
`lab-ctla1`: O1→O2 11, O0→O1 6, O2→O3 2 · `lab-ctla2`: O1→O2 12, O0→O1 6, O2→O3 2.

## 4. Native vs normalized (resample cost)

Native reference (checkpoint upscaled to O0 geometry, so lattice cost is INCLUDED)
changes the top-transition ranking in **8/32 jobs** — all from the >1250px sources.
For the other 24 jobs the normalized ranking already holds. Conclusion: resample is a
real but secondary ingredient inside O1→O2; the camera ladder itself carries the bulk.

## 5. Checkpoint trajectory (source-relative means, 32 jobs)

| Ckpt | EATR | HFTR H0/H1/H2 | edgeW | ΔE76 | lumaRMS | chromaRMS | ρ1 | corr_len |
|---|---|---|---|---|---|---|---|---|
| O0 | 1.000 | 1.000/1.000/1.000 | 4.2px | 0.00 | 0.00 | 0.00 | 0.000 | 1.0 |
| O1 | 0.855 | 0.657/0.886/1.008 | 3.9px | 4.84 | 8.78 | 15.26 | 0.758 | 23.2 |
| O2 | 0.684 | 0.584/0.722/0.904 | 5.6px | 9.01 | 10.17 | 17.94 | 0.779 | 26.2 |
| O3 | 0.632 | 0.477/0.676/0.861 | 6.1px | 7.58 | 8.86 | 16.25 | 0.780 | 25.0 |
| O4 | 0.600 | 0.392/0.627/0.839 | 5.2px | 6.83 | 8.68 | 16.69 | 0.808 | 25.6 |
| O5 | 0.602 | 0.411/0.631/0.839 | 5.2px | 7.01 | 8.73 | 16.78 | 0.799 | 25.4 |

Cumulative: edge energy drops to ~60% of source by delivery; fine texture (H0) drops to
~40%; chroma residual peaks at ~18 LSB post-camera. The wash itself already loses
~15% EATR and ~34% H0 at source resolution.

## 6. Fixed-buffer codec replay (closes the 2B question)

Identical O2 buffer → JPEG q92 4:2:0 (C0) vs q97 4:4:4 (C1) → decode → finisher(standard) → metrics.

- **32/32 jobs: q97 source-relative EATR > q92** (mean +0.0303 raw, +0.0181 after finisher).
- HFTR_H1: 0.677 → 0.700 (q97). Encode delta C0-vs-C1: luma 5.21 LSB, chroma 6.96 LSB.

**Verdict: the codec bytes genuinely matter** — a fixed-buffer q92→q97 swap recovers
~3% EATR in every job. This re-opens the codec as a REAL, isolated lever (2B was
previously confounded because the adaptive ladder probes encoded candidates). It is
smaller than the camera loss (0.054 vs 0.176) but it is proven, cheap, and zero-risk
to detection behaviour compared to wash retuning.

## 7. Sealed prediction vs data

| Prediction (pre-registered) | Data | Verdict |
|---|---|---|
| wash largest | 0.152, PRIMARY 12/32 (image-dependent; 8/8 on IMG-5, 0 on IMG-6/11) | PARTLY |
| camera second | 0.176 combined with resample — largest, PRIMARY 23/32 | camera underestimated |
| resample co-primary >1250 | 8/32 ranking flips under native ref; ingredient inside O1→O2 | confirmed minor |
| finisher moderate | 0.049, never primary | confirmed |
| codec smallest | 0.054 (≈ finisher) AND fixed-buffer replay 32/32 positive | **rejected** — codec is real |

The data wins: camera (+resample) is the top lever, wash is second and
image-dependent, and the codec is a proven small-but-universal lever — contrary to the
"codec smallest, deprioritized" prediction.

## 8. Conditional first-round decision (per consultation §7)

Data says: **camera dominates → first round = camera MTF/noise retune (single param).**
- Camera+resample: PRIMARY 23/32, largest mean loss → single-parameter camera retune first.
- Codec: re-open JUSTIFIED by fixed-buffer replay (32/32) → candidate 4D-2A (float/RGB
  handoff instead of stage-1 JPEG roundtrip) as the second, independent round.
- Wash: PRIMARY only on high-res IMG-5/9 material → do NOT retune wash first; prefer
  4D-1 source-supported detail transfer (restores what wash destroys without touching
  detection behaviour).
- Finisher: moderate, never primary → 4D-3 (do-less) only after camera+codec rounds.

## 9. Artifacts

- Checkpoints (gitignored): `retrieval-checkpoints/deepclean-checkpoints/<job_id>/` (33 dirs) + `cpk.tar` + `cpk-manifest.txt`
- Per-job logs: `retrieval-checkpoints/attr-logs/`
- JSONL: `retrieval-checkpoints/attribution.jsonl` (32), `retrieval-checkpoints/codec.jsonl` (32)
- Ledger pixel-manifest: `/tmp/ledger-cp.json` (32 captured + 1 error row)
- Volume state: `deepclean-checkpoints` emptied on pod; pod handed back for termination.
