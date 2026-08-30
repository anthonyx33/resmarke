# STANDING RULE R1 — PRESET TEST BATTERY (EVERY NEW PRESET)

Status: STANDING. Applies to every new preset, configuration, or pipeline
change from this point forward (1.01 and all successors). No exceptions;
exceptions require a written owner override and a new marker.

## 0. Terminology (fixed)

- **Paired** — every experimental output is paired with its control: same
  source image, same seed, same settings except the ONE variable under test.
  The pair isolates that variable's effect. B = control cell, C = candidate
  cell (same image, different preset).
- **Wash** — the generative purification step (ComfyUI Remarkee Max, Qwen
  single-VAE round-trip) that breaks embedded fingerprint carriers and
  regenerates content.
- **Process (process_cap / process_resolution)** — the resolution at which the
  wash's VAE actually works (1536 today). Output is restored to the source's
  original size afterward, so `process` ≠ `delivery`.
- **Arm** — one experimental condition in a factorial test. AR1 had A0
  (incumbent), A1 (camera-off), A2 (codec bypass), A3, A4 (4D-1b), A5
  (QF-off), A6. Each arm = one defined variation; arms are compared
  head-to-head on the same cells.
- **Delivery (delivery_resample)** — the final shipped resolution:
  `min(source, 1250)` today, `1800` for ReMint 1.01. The single Lanczos
  resample to that size.
- **Rung** — one strength level of the adaptive camera ladder
  (`light` → `balanced`). The ladder picks the least destructive rung that
  clears the detector probe.
- **Cohort** — the 12 archived B cells measured as a group.
- **Fail-closed** — a stage refuses to produce an unsafe output instead of
  shipping it (e.g., candidate with cap violations returns control pixels).
- **Fidelity** — byte-exact reproduction of archived checkpoints by replay.
- **MOCK** — the deterministic fake detector used for screening only; never
  counts as detection evidence.
- **Settings marker** — the `SEQ-<PRESET>-<hash>` code emitted with every
  output, proving which tuple produced it. Agreed for 1.01:
  `SEQ-1.01-<hash>`.

## 1. The battery — every new preset must pass all tiers

### Tier 1 — mandatory for EVERY preset, every time (no budget cost)
1. **Replay metrics** — new preset replayed on the 12 archived sentinel cells;
   frozen metric recipes; outputs hash-indexed.
2. **Live MOCK screen** — sentinel images through the new preset in /relab
   with detector = MOCK. Screening only; verifies the mechanism fires and
   nothing grossly regresses.
3. **Visual checklist** — operator completes the artifact checklist
   (blur, ringing, banding, grain uniformity, color fidelity, gross
   artifacts) per before/after pair. Checkbox observations, no opinions.
4. **Master-engineer verification** — settings code correct, credits ledgered,
   artifacts hash-indexed, no frozen file changed.

### Tier 2 — promotion gate (before ANY production admission)
5. **Hive leg** — per vendor freeze v3 mechanics: 12 calls = 6 new-preset
   delivered + 6 incumbent re-fetched hash-pinned; fresh-call ledger; C2PA
   deny-list; thresholds AI ≤ 0.45, flux ≤ 0.30, deepfake ≤ 0.10; paired
   non-amplification; median = mean of 3rd+4th sorted. A preset is
   promotion-eligible only if the leg passes.

## 2. Budget governor (hard)

- Vendor cap is **40 calls** total. 0 used to date.
- **Prior allocation has priority:** the frozen 4D-S1 stage-detection ledger
  (C8_MASTER_PROMPT_4D_S1_STAGE_DETECTION_LEDGER.md) holds **24 calls** for
  stage grading plus a planned 12-call winner leg and 4 margin → **16 calls
  remain** for preset-validation legs unless the owner re-allocates in
  writing.
- One full Hive leg = 12 calls → after S1, the reserve funds **one
  validation leg + 4 margin calls**, no more.
- Legs are allocated by the owner in writing, one preset at a time. No leg
  runs without a ledger entry first. Every leg is charged to the same
  40-call reserve as S1 and all vendor-freeze activity.

## 3. Record discipline

Every battery run produces: a job ledger (cell → job id → settings code →
mock verdicts → credits), exported delivered files, the visual checklist,
the Hive leg record, and an artifact index with SHA-256 over everything.
The master engineer verifies before any next step.
