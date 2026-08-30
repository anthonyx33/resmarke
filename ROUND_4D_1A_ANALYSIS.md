# ROUND 4D-1A — MASTER ENGINEER ANALYSIS & VERDICT

Experiment: `ba947d6b-2c21-4740-9d20-2b60fc9123cc` · Sealed variable: H1/H2
source-energy transfer α=0.10 ON vs OFF · 24 cells, all MOCK · Operator: Flash
Max · Analysis: master engineer · Date: 2026-08-27

## 0. Verdict

**4D-1a is REJECTED — the transfer never fired.** All 12 C cells are
byte-identical to their paired B cells on all six checkpoints
(`applied: false`, reason `no_eligible_quantized_change`). Gates 2, 3, 4 fail
by construction (zero effect). The round is scientifically decisive: it proves
WHERE the design blocked, and the band-energy map points exactly where the next
round should go. No panel, no vendor leg (vendor 0/40).

## 1. Provenance (G1) — PASS

- 24 dirs retrieved, 180 files; OR/O2 hashes match the ledger for all 24 cells;
  ledger O5 spot-checks pass; 12/12 pairs: O0 and O5 pixel-equal; C dirs carry
  `O2_transfer.png` (hash == O2, the no-op in data); B dirs carry no transfer
  file. Codes exact: 12× `SEQ-CFA-*`, 12× `SEQ-4D1A-*`; all MOCK,
  `provider_calls: 0`.

## 2. Gates (pre-registered, frozen)

| Gate | Required | Measured | |
|---|---:|---:|---|
| G1 provenance | all pairs equal | **PASS** (file-level) | ✅ |
| G2 O2→O5 loss reduction | ≥25% (ceiling 0.07366275) | **0.0%** (C ≡ B; C mean = 0.098217) | ❌ |
| G3 hard subset | ≤ 0.07951875 | **0.098217** | ❌ |
| G4 delivered detail | +0.04 / +8% / 5-of-6 | **0.0 / 0.0** | ❌ |
| G5 safety | floors | trivially PASS (identical outputs) | ⚪ |
| G6 edge ESF | tolerances | trivially PASS (identical outputs) | ⚪ |
| G7 MOCK carrier screen | thresholds | trivially PASS (identical bytes) | ⚪ |

G5–G7 pass only because nothing changed; they carry no evidence for the
candidate. G2–G4 decide the round: **FAIL → REJECT.**

## 3. Why it never fired (measured, not guessed)

Per-C transfer report blocks (DB): support coverage **0.023%–0.126%** of
pixels. Reject counts (of ~1.56M pixels at 1250²):

- NCC (signed local correlation ≥0.80 with source): rejected **0.60M–1.55M**
- alignment scale agreement: rejected **0.62M–1.53M**
- orientation ≤15°: rejected **0.32M–1.02M**
- cross-scale persistence (H1 AND H2): rejected **≈100%**
- complete support: rejected **≈100%**

**Root cause:** the generative Qwen wash REGENERATES content, so the remint no
longer corresponds geometrically to the source. The phase/agreement support
gates — which C88 correctly required for carrier safety and double-edge
protection — therefore pass almost nowhere. The energy-only design was
architecturally sound but the wash makes source-relative support structurally
scarce.

## 4. The band-energy map (the round's real prize)

Per-band energy ratio vs the geometry-matched source reference, mean over
12 B cells:

| stage | H0 (fine) | H1 (mid) | H2 (coarse) |
|---|---:|---:|---:|
| O0 source | 1.000 | 1.000 | 1.000 |
| O1 post-wash | 0.608 | 0.938 | 1.123 |
| O2 post-camera | 0.290 | **0.484** | 0.866 |
| O3 stage-1 codec | 0.161 | 0.410 | 0.787 |
| O4 finisher | 0.125 | 0.358 | 0.754 |
| O5 delivery | **0.126** | **0.362** | **0.755** |

- **87% of H0 and 64% of H1 source energy is gone by delivery.**
- The **camera stage (O1→O2) is the dominant killer**: H1 0.938→0.484 (45% of
  the wash's mid-band destroyed), H0 0.608→0.290 (52%).
- The wash output O1 still holds most of the source's H1 (0.938) — the detail
  EXISTS before the camera and is then thrown away.

## 5. What this changes for the program

The correct reference for detail restoration is not the ORIGINAL (wash breaks
correspondence) — it is **O1, the remint's own post-wash buffer**. O1 and O2
are the same image separated by a deterministic blur chain; their geometry
agrees by construction, so the agreement gates that strangled 4D-1a pass
trivially. And because O1 is already carrier-broken, the H0 exclusion that
was mandatory for SOURCE transfer is no longer required — H0 restoration from
O1 is carrier-safe by construction.

**Recommended next brief: 4D-1b — wash-detail preservation.** Reinject O1's
H0/H1 band structure into O2 (pre-camera → post-camera), remint-internal,
support-gated, with the same pre-registered discipline. If it recovers even
half of the 45–52% camera-stage loss, it beats the entire 4D-1a target.

## 6. Books & housekeeping

- Credits: 992115→991563 (552 privacy) + 999518→999494 (24 deepclean), exact.
  Vendor 0/40. No re-runs, no stop-condition fires.
- Cell 16 (IMG-6 C ctla2): corpus registration 409 (output cap 20/IMG-6) —
  23/24 registered; does not affect this verdict.
- Volume: 24 round dirs + tar removed after retrieval (master engineer).
- No production change: the 4D-1A preset remains lab-only; nothing promotes.
  Owner decision: disable the preset in `/relab` (same as 4D-CAM-1 after its
  rejection).

## 7. Artifacts

- `round-4d-1a/checkpoints/` (24 dirs, 180 files, verified)
- `round-4d-1a/expected-manifest.json` (ledger-derived)
- `round-4d-1a/band-energy-map.json`
- `deepclean-worker/tools/round_4d_1a_verify.py`
- This report.
