# Vacuum task — quality finisher, SEVENTH iteration (V7): the final reiteration — consumer-grade smoothness at Config A, without touching detection

## The task, in a vacuum

You designed the finisher through six iterations. All are shipped, and the
system is LIVE again after an infrastructure outage (new RunPod endpoint,
volume re-attached, worker booting, model cache verified). The detection
problem is SOLVED: **Config A** (strength deep · restoration STRONG ·
smoothing 1.25× · wall smoothing ON · native delivery) is the first
configuration in the project's history to clear all three test images on
both graders with clean margins — including the lit brick wall (image 3).

What remains is consumer quality only. The operator's verdict on the
current delivery:

> "so far it looks very bad quality… it will perform well just because how
> pixelated it is… but it definitely loses points for the consumer
> personally, conversion rate will be low."

This is the FINAL optimization before a beta launch to trusted testers and
creators. The operator has re-affirmed two strategies; your job is to audit
the new data, rank them (or design a hybrid), and specify the LAST finisher
changes — V7 — that visibly reduce grain/pixelation on Config A outputs at
100% zoom, with zero regression to the cleared detection results.

## Where the system stands (all shipped, verified)

- **Stage one** (coherent remint, Qwen wash, byte-identical, ≤1250px native
  path): FROZEN. Detection-validated. Any change requires a detector A/B.
- **Quality finisher** (non-generative, deterministic, CPU-only, one Q97
  4:4:4 encode): decode → JPEG cleanup → material mask → region suppression
  → case-B guard → chroma repair → **Mobile Clean wall branch (V5)** →
  enlarge → decorrelation → SNR sharpen → **Final Polish (V6: 3-scale
  à-trous soft shrinkage, structure-gated)** → adaptive dither → 8-bit →
  Q97 4:4:4 → QC.
- V6 constants (in `deepclean-worker/quality_finish.py`):
  `POLISH_G_MIN=(0.40,0.55,0.75)`, `POLISH_TAU=(0.004,0.007,0.010)`,
  `WALL_DITHER_Y=0.13/255`, `WALL_DITHER_C=0.04/255`, wall RMS targets
  bright 0.32 / dark 0.55 LSB, chroma 0.08 LSB, polish structure gate
  P>0.75 → gain ≥ 0.9. Ladder retries + polish-disabled retry on
  TDR<0.95 + dither boost on staircase>0.7.
- **Known defect, being fixed before this loop**: `material_clean` is
  supported by the worker and edge function but DROPPED by the web client
  (`src/lib/deepcleanClient.ts` serializes `quality_finish` as
  `{preset, scale, overrides}` only). Until fixed, the M1 vs M0 wall toggle
  cannot be A/B tested through the UI. Assume it is fixed by the time the
  matrix below runs; if not, the M1/M0 rows are invalid.
- Naming: settings-code filenames (`SEQ-STR-N-M1-<hash>.jpg`) are the
  DEFAULT, so every split-test export is self-describing.
- New `/remint` console is being built on Config A defaults — the product
  shape is locked: **Config A fixed default + the three pro-tuning
  multipliers + wall toggle**, everything else hidden.

## Split-test matrix — run these FIRST, fill in the table, then answer

Protocol: 3 known images (1 dusk wall+house, 2 pale wall beams, 3 lit
terracotta brick) + **one real-photo control** (non-rendered, mixed
foliage/product — the content class the beta will actually receive).
Every row: 2 independent graders, same scoring as before, PLUS a human
100%-zoom quality rubric: grain visibility, edge crispness, banding,
chroma blotch, "premium or not" 1–5.

| Row | Change vs Config A | img1 | img2 | img3 | control | 100% zoom rubric |
|---|---|---|---|---|---|---|
| R0 | none — Config A on LIVE worker (baseline re-grade) | — | — | — | — | — |
| R1 | wall smoothing OFF (M0) | — | — | — | — | — |
| R2 | Final Polish OFF (V6 reverted) | — | — | — | — | — |
| R3 | smoothing 1.5× (1.25→1.5) | — | — | — | — | — |
| R4 | delivery 1.6× HD (2000px path) | — | — | — | — | — |
| R5 | dither 0.7× on brick-class images | — | — | — | — | — |

R0 is mandatory even though rounds G/H exist: the endpoint was rebuilt
during the outage and G/H may predate it. Re-prove the all-clear on the
live worker before any V7 build.

## The open questions (answer with exact numbers and pseudo-code)

1. Rank **Strategy A** (locked Config A), **Strategy B** (post-clean
   smoothing — note V6 Final Polish already IS a first implementation),
   and a **hybrid**, for a beta launch. Which maximizes CONSISTENT
   professional quality across wall, brick, foliage, product scenes
   without regressing the cleared images?
2. Brick (image 3) is the joint failure: smoothed more = clears but
   pixelated; smoothed less = flagged. Design the V7 brick treatment:
   hue-preserving luma smoothing + structure-preserving shrinkage that
   keeps mortar lines and brick edges. Give the structure map definition,
   per-band targets in LSB, and the exact interplay with
   `POLISH_G_MIN`/`POLISH_TAU`. The lit-brick texture must NOT smear.
3. Delivery size: Config A ships native (≤1250px). Does the premium
   consumer complaint (pixelated at 100% zoom) argue for 1.6× HD as the
   beta default? Use R4. If 1.6× regresses detection on any image, state
   the fallback (e.g., native default, 1.6× behind a toggle).
4. Preset collapse: Fidelity HD ≈ Standard visually and is
   detection-worse on this content. Specify the final preset set (2 or 3?)
   and the measurable difference (a named QC metric with a threshold) a
   preset must produce to justify existing.
5. Auto-selection: for beta, is a fixed config + manual multipliers
   correct (predictable, settings-code provenance), or should the worker
   auto-escalate (e.g., smoothing ladder triggered by a borderline
   detector probe)? If the latter, give the exact rule and thresholds.
   Default recommendation expected: fixed config for beta, ladder as a
   flagged post-beta candidate.
6. V7 algorithm: specify the concrete finisher changes — where they sit
   relative to the existing V5/V6 stages and the final encode, what they
   change, what they must NOT touch (edge acutance floors, sky, fine
   structure on foliage), and the new QC gates (named, with thresholds)
   that prove each change did its job.
7. Top five concrete changes ranked, each with its trade-off and the
   minimal experiment to validate it. Flag the single largest expected
   visible win for the "pixelated/grainy" complaint.

## Constraints (frozen unless you argue with data)

- Stage one byte-identical; any stage-one change needs a detector A/B.
- Finisher: non-generative, deterministic, CPU-only, one encode, and must
  stay sub-second at 1080p on the worker CPU (currently ~340–670 ms).
- Acceptance gate thresholds frozen; near-threshold outputs flagged for
  manual QA, never shipped silently.
- Knobs stay: a handful of presets + dither/smoothing/sharpen multipliers
  + wall toggle. No new user-facing knobs unless one earns its place.
- GPU budget unchanged: all V7 work is in the CPU finisher; the warm
  ComfyUI stage is untouched.

## What we do NOT need

Product, pricing, or business discussion. Pure technical system and design
recommendations building on your V5/V6 finisher. Return a build order a
backend engineer can execute directly in `deepclean-worker/quality_finish.py`,
plus the exact split-test data you still need if the matrix above is
insufficient.
