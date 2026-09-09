# C8 MASTER AI-OPERATOR PROMPT — GEOMETRY LADDER PHASE A

Status: OWNER GO. Execute the live Phase-A experiment now.

Role: evidence-preserving mechanical AI operator. You may use the authenticated
browser, local shell, and experiment-output folders. You may spend the credits
and real detector calls required by this prompt. Do not edit product code,
change presets, change thresholds, commit, push, deploy, alter RunPod settings,
run Phase B, or make a winner/promotion decision.

If you lack an authenticated owner `/relab` session, browser download access,
or filesystem access to this repository, STOP before the first job and report
the missing capability. Never request or expose passwords, tokens, API keys, or
service-role secrets.

## 1. Immutable deployment and experiment contract

- Geometry implementation commit: `4526be3f0b3096c35841cad18d7b71d2122806c8`
- Worker image:
  `ghcr.io/anthonyx33/resmarke-deepclean@sha256:c0f32a4b4bb56d2e48411a849e85d1b20b99662d998be00f1759985106097182`
- Edge function: production `create-deepclean-job` version 69 or later.
- UI: `https://resmarke.vercel.app/relab`
- Frozen transform contract: `C8_MASTER_PROMPT_GEOMETRY_LADDER.md` v4.4.
- Seed for every evidence cell: `lab-ctla1`.
- Detector: real Hive unified detector (`vendor: g1`, `mode: real`) only.
- Grid: Config A plus eight geometry arms × eleven images = exactly 99
  evidence cells.
- Phase B and J1–J3 are forbidden in this run.

The experiment asks whether any frozen geometry arm improves detection over a
fresh, same-build Config A while remaining eligible under the GL-Q quality
recipe. Build completion is not a positive result.

## 2. Frozen source manifest

Use only these exact local files. Verify every SHA-256 before opening `/relab`.
Any missing file or mismatch is a STOP.

| Image | File | SHA-256 | Dimensions |
|---|---|---|---|
| IMG-1 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-1.jpg` | `442a1ccd4338d777b9a1bc7bfedb21aeb3846ae6f4f9f8ee761b9ef38d3b0dc8` | 1024×1024 |
| IMG-2 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-2.jpg` | `90b8cc8a257454b39bb67d3f8065b01ec3e17b29a3f6e1ebb80e620f02d38e91` | 1024×1024 |
| IMG-3 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-3.png` | `357d9aa522ea4d12ba3583f86477472b526168747c682cdc828ac073ce5af6a6` | 1024×1024 |
| IMG-4 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-4.png` | `9f4cfa27845ffb49f595f90c332c43b4db2bbcde6ce30633b7dcea2396fe8e1a` | 1024×1024 |
| IMG-5 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-5.png` | `91fffe56122550743c9c18da0bed78c89ca702cabb08ce125e626a89a67b0d6b` | 2048×2048 |
| IMG-6 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-6.png` | `57db03058e1ce49e15aff4a7b95f0d6d6e1e23660732aa1c54f991bec1ea567f` | 800×800 |
| IMG-7 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-7.png` | `dd6b9afc1cc79c2a6dcd6a4e5fb9592e9838614876754e72f9bccbcd21f7a69b` | 1080×1080 |
| IMG-8 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-8.png` | `bb1325d84ba3dd2ac8162b5c9f3607932ae6d50a7b245c467024599ad4d2319c` | 1080×1080 |
| IMG-9 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-9.png` | `70df003ece40710c00ae4173237322e88125baa4993aa8a79a69b2beccee9b70` | 1600×1600 |
| IMG-10 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-10.png` | `96379ecb1b1b5fa97ec5ef3c3149765eb9a0d4162e038db1fe882e3f7aea8de3` | 2048×2048 |
| IMG-11 | `IMG-REMINT-v1/CFA-REAL-CREATOR-IMG-11.jpeg` | `dc9bdc02806d2391a22f092f4539be875b06c0fdf049d67b4cc3ea843da0a8c8` | 2048×2048 |

## 3. Frozen arms and active seeded codes

The code below must be read from the ACTIVE top-bar code after entering
`lab-ctla1`. The smaller codes printed on preset-list cards are unseeded
reference codes and must not be used as the dispatch identity.

| Arm | Treatment | Required active code |
|---|---|---|
| Config A | no geometry block | `SEQ-CFA-lhbmeve33nn3` |
| geom-r0 | bypass · cap 1250 | `SEQ-G0-qocqnp2g2gfy` |
| geom-x0 | affine identity · cap 1250 | `SEQ-GX0-xtya3ir32ozw` |
| geom-r1 | affine identity · cap 1000 | `SEQ-G1-gexfjkrr2hlb` |
| geom-r2 | affine identity · cap 800 | `SEQ-G2-p3rwojlmzrov` |
| geom-r3 | tilt 0.6° · cap 1250 | `SEQ-G3-hdhzzbffurlt` |
| geom-r4 | tilt 1.2° · cap 1250 | `SEQ-G4-6qdn22oroob2` |
| geom-r5 | source shift +0.5/+0.3 px · cap 1250 | `SEQ-G5-dxcvkvndsy33` |
| geom-r6 | shift + horizontal squash 0.988 · cap 1250 | `SEQ-G6-jzvg3zezpltk` |

## 4. Artifact directory and pre-flight

Create, without deleting or overwriting prior evidence:

```text
round-geometry-ladder/
  run-manifest.json
  phase-a-ledger.jsonl
  output-manifest.json
  AI_OPERATOR_REPORT.md
  raw/
  outputs/config-a/
  outputs/geom-r0/
  outputs/geom-x0/
  outputs/geom-r1/ ... outputs/geom-r6/
```

If `round-geometry-ladder/` already contains an evidence run, STOP and report;
do not merge, replace, or invent a suffix.

Then:

1. Record start time, commit, image digest, source hashes, and operator identity
   in `run-manifest.json`.
2. Open a fresh `/relab` tab. Sign in as the authorized owner. Do not inspect,
   copy, or expose authentication material.
3. Confirm all eight geometry preset buttons are visible.
4. Export the existing Ranked grade ledger JSONL before the run and preserve it
   as `round-geometry-ladder/raw/pre-existing-relab-grades.jsonl`. Do not clear
   browser localStorage; this export is the subtraction baseline.
5. Clear only the in-memory file queue, if necessary.
6. Add IMG-1, select it, and use `Run API detection only`. This is a provider
   probe, not an evidence cell and dispatches no remint job. PASS requires:
   `vendor=g1`, `mode=real`, `mock=false`, no vendor error, and
   `session_usage.cap=10000`. `provider_calls` may be 0 for a valid SHA cache hit
   or 1 for a fresh call. Any other value or cap is a STOP.
7. Record starting privacy and DeepClean balances where observable. The 99 jobs
   consume 2,277 privacy credits and normally reserve/capture 99 DeepClean
   credits. Credits are authorized under Standing Rule R2, but accounting is
   mandatory.

## 5. First-light control pair — cells 1 and 2

This pair proves that the new worker is live and checks the same-build byte
control before the remaining 97 jobs.

### Cell 1: geom-r0 × IMG-1

1. Queue IMG-1 only.
2. Enter seed `lab-ctla1`; select `geom-r0`.
3. Confirm ACTIVE code `SEQ-G0-qocqnp2g2gfy`.
4. Dispatch once and wait through paired grading. No retry.
5. PASS requires the exported row to contain:
   `executed.full.engine.layers.geometry.applied=false`,
   `preset_id=geom-r0`, `resample_mode=bypass`, and
   `warp_affine_calls=0`. Absence of this geometry report means the new worker
   is not live: STOP.
6. Download the delivered file before clearing the queue and save it as
   `outputs/geom-r0/IMG-01.jpg`.

### Cell 2: Config A × IMG-1

Run IMG-1 once under Config A with the same seed and confirm active code
`SEQ-CFA-lhbmeve33nn3`. Config A must have no geometry block. Download as
`outputs/config-a/IMG-01.jpg`.

SHA-256 of both delivered files must be identical. If not, STOP the entire leg
and report both hashes and job IDs. Do not explain away the difference.

## 6. Remaining execution order

After the first-light pair passes, execute exactly in this order:

1. Config A × IMG-2…IMG-11.
2. geom-r0 × IMG-2…IMG-11; then verify Config-A/r0 byte equality independently
   for all eleven images. Any mismatch is a STOP.
3. geom-x0 × IMG-1…IMG-11.
4. geom-r1 × IMG-1…IMG-11.
5. geom-r2 × IMG-1…IMG-11.
6. geom-r3 × IMG-1…IMG-11.
7. geom-r4 × IMG-1…IMG-11.
8. geom-r5 × IMG-1…IMG-11.
9. geom-r6 × IMG-1…IMG-11.

Use the regular file-add path only; never use the corpus picker. Work one arm
at a time. A queue may contain the arm's ordered images, but do not mix arms in
one queue. Download every output and export a raw ledger snapshot before
clearing that completed queue.

## 7. Per-cell verification

For every evidence cell:

1. Source filename/hash is one of §2 and images remain in numeric order.
2. Seed is exactly `lab-ctla1`.
3. ACTIVE code exactly matches §3 before dispatch.
4. Exactly one job is dispatched. Never retry or re-grade.
5. Wait for completion and paired real grading.
6. Record the full, unrounded ledger row: arm, image, timestamp, job ID,
   settings code, requested settings, executed report, OG/RM grades, complete
   source maps, task IDs, cache flags, provider calls, session usage, C2PA and
   verdicts.
7. Download the delivered JPEG to `outputs/<arm>/IMG-NN.jpg`; record SHA-256,
   byte count and dimensions in `output-manifest.json`.

Geometry report rules:

- Config A: geometry block absent.
- geom-r0: `applied=false`, `warp_affine_calls=0`, `preset_id=geom-r0`.
- geom-x0/r1/r2: `applied=true`, `warp_affine_calls=1`, correct preset,
  `scale=1`, `BORDER_REPLICATE`. Source margin is not a gate and may be zero.
- geom-r3/r4: `applied=true`, `warp_affine_calls=1`, correct preset,
  `source_margin >= 4`, `BORDER_CONSTANT`.
- geom-r5/r6: `applied=true`, `warp_affine_calls=1`, correct preset,
  `scale=1`, `BORDER_REPLICATE`. Their later integrity gate is the measured
  kernel-affected strip, not source margin.

Expected square output dimensions:

- Config A, r0, x0, r3, r4, r5, r6: IMG-1…4 = 1024; IMG-5 = 1250;
  IMG-6 = 800; IMG-7/8 = 1080; IMG-9/10/11 = 1250.
- r1: IMG-1…5 = 1000 except IMG-6 = 800; IMG-7…11 = 1000.
- r2: every image = 800.

The caps never upscale. Consequently, some logical cells can produce identical
bytes—especially identity controls and IMG-6 under r1/r2. That is expected.

## 8. Detector and cache rules

- Every returned grade must say `vendor=g1`, `mode=real`, `mock=false` and have
  no vendor error.
- The grade cache is keyed by exact image SHA-256. A cache hit is valid evidence
  and should occur for repeated source bytes and byte-identical outputs.
- A cache hit must report `provider_calls=0`; a fresh grade must report
  `provider_calls=1`. Any other combination is a STOP.
- Never require a fresh call merely to re-grade identical bytes. Never submit a
  file twice to force a call.
- Record the final session usage. There is no exact expected call count because
  the persistent cache makes it history-dependent; it cannot exceed 111 in
  this protocol including the provider probe.
- `actions_digital_source_type=trainedAlgorithmicMedia` on any delivered row is
  a C2PA STOP.

## 9. Visual observation

At the end of each arm, inspect its eleven outputs at contact-sheet scale for
blur, ringing, banding, grain discontinuity, colour shift, warped content,
replicated edges and black corners. Record OK or FLAG per image. Do not exclude
or rerun a flagged cell. Tilt overscan promises zero black-border contribution;
black edges/corners are faults, not expected padding.

The operator does not determine GL-Q eligibility. Preserve all files so the
master engineer can calculate geometry-matched references, ROI gates and the
frozen quality metrics after handoff.

## 10. Stop conditions

STOP the leg immediately and preserve everything already produced on any of:

- source hash mismatch;
- owner authentication missing;
- geometry preset absent;
- cap not 10000;
- mock/non-g1 grade or vendor error;
- active seeded settings-code mismatch;
- first-light geometry report absent or wrong;
- Config-A/r0 byte mismatch;
- geometry report, call count, border mode, margin or output-size mismatch;
- a grade reports more than one provider call or contradicts its cache flag;
- C2PA deny finding;
- job failure, out-of-order submission, accidental retry or dropped output.

Do not debug, patch, substitute, or continue past a stop. Return a stop report
with the exact cell, job ID, hashes, raw error and completed-call count.

Visual flags alone are recorded and continued; the later quality recipe decides
eligibility.

## 11. Final evidence assembly

After all 99 cells:

1. Export the complete Ranked grade ledger JSONL again into `raw/`.
2. Subtract the pre-existing export and filter the run by its 99 job IDs and
   exact settings codes. Save exactly 99 unmodified rows in
   `phase-a-ledger.jsonl`; retain all raw exports.
3. Validate: nine arms × eleven images; no duplicates or omissions; every
   source and output hash present; every settings code correct; real g1 only;
   Config-A/r0 byte controls 11/11.
4. Record ending balances, credits spent, grades returned, cache hits, provider
   calls, session cap, start/end times and every visual flag.
5. Write `AI_OPERATOR_REPORT.md` containing facts only—no winner, no quality
   eligibility, no Phase-B tuple and no promotion recommendation.

Required final declaration:

> I executed exactly 99 Geometry Phase-A evidence cells using the frozen v4.4
> arms, eleven pinned source files, seed lab-ctla1, deployed worker digest
> sha256:c0f32a4b4bb56d2e48411a849e85d1b20b99662d998be00f1759985106097182,
> and real g1 grading. I made no product-code, preset, threshold, deployment or
> Phase-B change. The raw exports, filtered ledger, downloaded outputs, hashes,
> controls, accounting and stop/visual records are complete and unmodified.

Return the artifact paths and stop. The master engineer—not the operator—then
runs GL-Q quality eligibility and ranks detection performance against the live
Config A.
