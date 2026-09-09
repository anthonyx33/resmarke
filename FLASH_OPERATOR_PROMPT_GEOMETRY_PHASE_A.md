# FLASH OPERATOR PROMPT — GEOMETRY LADDER PHASE A (99 cells)

Role: mechanical operator. Execute exactly. The Phase A build is
master-verified: geometry 15/15 (unittest + pytest), TypeScript 4/4, Deno
18/18, frozen v4.4 contract (`C8_MASTER_PROMPT_GEOMETRY_LADDER.md`).
Phase B is NOT authorized and is NOT part of this leg.

## 0. The grid

9 arms × 11 images = 99 cells, all seed `lab-ctla1`:

| # | Arm | Geometry block | Settings code (ctla1) |
|---|---|---|---|
| 1 | Config A (live control) | none | SEQ-CFA-lhbmeve33nn3 |
| 2 | geom-r0 | bypass, 1250 | SEQ-G0-qocqnp2g2gfy |
| 3 | geom-x0 | affine identity, 1250 | SEQ-GX0-xtya3ir32ozw |
| 4 | geom-r1 | affine resize 1000 | SEQ-G1-gexfjkrr2hlb |
| 5 | geom-r2 | affine resize 800 | SEQ-G2-p3rwojlmzrov |
| 6 | geom-r3 | affine tilt 0.6° | SEQ-G3-hdhzzbffurlt |
| 7 | geom-r4 | affine tilt 1.2° | SEQ-G4-6qdn22oroob2 |
| 8 | geom-r5 | affine shift (0.5,0.3) | SEQ-G5-dxcvkvndsy33 |
| 9 | geom-r6 | affine shift+squash | SEQ-G6-jzvg3zezpltk |

Unseeded goldens (verification-only, never dispatched): r0 kanyynxeawvr,
x0 hh2qppoqbnjq, r1 e2tp35ik6kna, r2 7pxk5lv72ee6,
r3 xx7n6rnwqr3r, r4 4ozjt4hh6xd3, r5 3dg2guf3xbub,
r6 fbo7bz7ovtus.

Order: **by arm, 9 batches of 11**, images 1→11 within each arm. Run
Config A first and geom-r0 second. Compare their downloaded hashes before
starting geom-x0 or any treatment arm. This fails early if the same-build
byte control has drifted instead of wasting the remaining 77 jobs.

## 1. Pre-flight (fresh session — mandatory)

1. FRESH /relab tab (session caps only lower; never reuse old tabs).
   Owner sign-in.
2. Provider check: grade a tiny synthetic image → ledger must show
   `vendor: g1`, `mock: false`, `provider_calls: 1`. Mock → STOP.
   Session counter must render `/10000` (any `/40` → STOP).
3. Remint panel: seed `lab-ctla1`; Config A + geometry preset toggles
   present. Balance recorded (≈ 991264 expected; leg spends 99 × 23 =
   2277 remint credits).
4. Regular file-add path ONLY (no corpus picker — no registration).

## 2. Per-cell procedure (99 ×)

1. Add the exact source file in `IMG-REMINT-v1/`, preserving its real
   extension: IMG-1/2 are `.jpg`, IMG-11 is `.jpeg`, and IMG-3…10 are
   `.png`. Images remain numbered 1→11 in order.
2. Select the arm's geometry preset chip, or plain Config A for the
   Config-A batch.
3. Verify the ACTIVE code in the top bar EXACTLY matches the seeded table
   before dispatch. Preset-list cards show the unseeded reference codes;
   they are not the dispatch identity after `lab-ctla1` is entered.
   Mismatch → STOP.
4. Dispatch remint; wait for auto-grade.
5. Record in the ledger (append JSONL to
   `round-geometry-ladder/phase-a-ledger.jsonl`): arm, image, seed,
   settings_code (exact), job_id, OG row, RM row with UNROUNDED
   probabilities, task_id, `session_usage`, `cache_hit`, `provider_calls`,
   `mock`, verdicts, c2pa status.
6. Verify the RM row report geometry block (browser report / job report):
   - geom-r0: `applied: false`, `warp_affine_calls: 0`.
   - geom-x0/r1/r2: `applied: true`, `warp_affine_calls: 1`,
     `preset_id` matches, `scale: 1`, `border_mode: BORDER_REPLICATE`.
     Their source margin is not a tilt gate and may be zero.
   - geom-r3/r4: `applied: true`, `warp_affine_calls: 1`, `preset_id`
     matches, `source_margin ≥ 4`, `border_mode: BORDER_CONSTANT`.
   - geom-r5/r6: `applied: true`, `warp_affine_calls: 1`, `preset_id`
     matches, `scale: 1`, `border_mode: BORDER_REPLICATE`. Their quality
     gate is the later kernel-strip measurement, not `source_margin ≥ 4`.
   - Every `output_size` must equal the legacy aspect-preserving size with
     long edge `min(source_long_edge, resize_target)`; a cap never upscales.
   Any mismatch → STOP.
7. Download the delivered file via get-deepclean-job outputUrl + curl
   (browser download event does not fire on cross-origin signed URLs),
   hash-pin it in the ledger (`sha256`, dims).

## 3. Byte controls (frozen)

- Per image: **geom-r0 delivered bytes == Config A delivered bytes**.
  Any difference → STOP and report (do not reason it away). Record whether
  geom-x0 also hashes identically, but do not turn that observation into an
  additional control rule not present in the frozen v4.4 brief.
- IMG-6/7/8 sources ≤ 1250: r0/x0/Config A are byte-identical to the
  incumbent resize; r1/r2 shrink them. That is expected, not a stop.

## 4. Grading freshness (vendor freeze v3)

- Every uncached unique hash = ONE call, no retry, no re-submit.
- Grade caching is SHA-256 based. Cache hits are expected for repeated OG
  bytes and byte-identical Config-A/r0 outputs; geom-x0 may also be a cache
  hit if its delivered hash is identical. Record these verbatim.
- A transformed r1–r6 output returning `cache_hit: true` is unexpected:
  STOP and report its hash before proceeding.
- C2PA deny-list: `actions_digital_source_type = trainedAlgorithmicMedia`
  on any delivered row → STOP the leg.
- Do not prescribe an exact vendor-call count: the persistent hash cache
  makes it history-dependent. The hard ceiling is 111 calls including the
  synthetic provider check; expected usage is materially lower. No single
  grade may report more than one provider call.

## 5. Visual checklist (per batch, contact-sheet scale)

Blur · ringing · banding · grain · color shift · geometry artifacts.
Tilt overscan guarantees zero border contribution: any visible black edge
or corner is a FLAG, not an expected artifact. Zero flags required; flag →
note in ledger and continue (quality adjudication is the master engineer's,
not yours).

## 6. Stop conditions (report, never fix)

Mock row · cap ≠ 10000 · active seeded-code mismatch · report geometry
mismatch · Config-A/r0 byte-control failure · unexpected r1–r6 cache hit ·
vendor error · C2PA deny · out-of-order submission · more than one provider
call for a grade · more than 111 total provider calls including pre-flight ·
dropped file.

## 7. Handoff

Declare: cells completed, credits spent, vendor calls, session usage,
stop count (must be 0), ledger path, downloaded-file manifest. The
master engineer then computes GL-Q eligibility, feature winners, and
the J1–J3 tuples. Phase B is a separate second build — you do not run it.
