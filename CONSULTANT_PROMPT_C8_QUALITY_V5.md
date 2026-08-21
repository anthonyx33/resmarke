# Vacuum task — quality finisher, fifth iteration: the "old phone grain" problem — grain model, rendered-wall gradients, and the shrink-then-enhance question

## The task, in a vacuum

You designed the quality finisher and iterations two, three, and four. We
implemented all of them. The acceptance side is largely settled on four of
five test classes, and the remaining problem has narrowed to one specific
visual defect: **the delivered image looks like it was shot by an amateur on
an old phone — grainy in a way no modern phone is.** The operator's words:
"the sky is okay actually, but on a white rendered building wall it gets
tough, especially outdoor rendered walls with different hues." They are
manually fixing grain in Photoshop (fill-bucketing skies and walls), and
the product is not sellable until that manual step is unnecessary.

This round has one goal: make the grain read as premium modern-phone grain
(or remove it regionally where it cannot be premium), without regressing
detection, which is frozen.

## What is shipped and validated (rounds 1-4, all in production code)

Round 2 (coarse-grain fix): four-band B/H2/H1/H0 decomposition, texture-
confidence map, region-conditioned H0/H1 suppression before enlargement,
dual-kernel enlargement, destination-scale residual decorrelation (lag-1
4-neighbour prediction subtraction until rho1 <= 0.40), SNR-gated sharpen.

Round 3 (banding fix): three-point diagnostic proved quantization-born
staircases; always-on gradient-masked shaped dither (64px blue-noise-like
tile, luma 0.30-0.40 LSB RMS, chroma 0.12-0.20 LSB RMS per preset) right
before 8-bit quantization; chroma gradient decontouring; case-B guard;
Q97 4:4:4; SOF-marker delivery self-check; banding-origin diagnostics.

Round 3.1 (system): fail-soft alpha ladder (gradient branch blends down
1.0 -> 0.75 -> 0.5 -> 0.25 -> 0 on gradient-axis QC failures); per-ROI
gradient QC (3x3 tile grid); user pro-tuning multipliers (dither,
smoothness, sharpen).

Round 4 (Fidelity HD, middle-ground revision): pre-JPEG buffer handoff
from stage one to the finisher (zero JPEG generations between stages);
a "fidelity" finisher preset (texture retention rides toward 1.0,
decorrelation capped at 2 passes, sharpen ~0.55x standard); original-source
reference QC (two-scale MS-SSIM, texture-detail transfer ratio, edge
acutance ratio). CRITICAL CONSTRAINT LEARNED THE HARD WAY: stage one's
configuration must stay byte-identical to the validated version (1250px
delivery, q92 4:2:0, adaptive ladder, user strength) — when we raised
stage one to 2000px / light strength / Q97, the finished output read
99.9% Gemini on graders. The finished file is now probed with the same
source-aware gate (ai <= 0.45 AND flux-family <= 0.30) and stage-1 gated
bytes ship when it does not clear.

## Live test data you must work from (Aug 21, two grading rounds)

Round 2 settings (recorded): wash Qwen, strength balanced, engine
adaptive, finish preset standard, delivery NATIVE (1250x1250, no
enlargement), pro tuning all 1.00x, finish routing adaptive.

Grading results, both rounds, two independent graders (A = percentage
AI-generation with source breakdown; B = AI probability with Real/AI
classification):

| Image | Round | Grader A | Grader B | Outcome |
|---|---|---|---|---|
| BBEST | 1 | 0.3% (gemini3 0.1) | 35% Real Medium | CLEAR |
| SOLTRIA-A | 1 | 94.6% (flux 94.7) | 94% AI High | HARD FAIL (source-level signature, same as a known ChatGPT-enhanced control) |
| SOLTRIA-B | 1 | 0.9% (flux 0.8) | 71% AI Medium | DIVERGENT |
| img1 | 2 | 1.3% (gemini3 0.7) | 33% Real Medium | CLEAR |
| img2 | 2 | 42.9% (flux 39.7) | 15% Real High | DIVERGENT (graders anti-correlated) |
| img3 | 2 | 5.7% (flux 8.7) | 61% AI Medium | DIVERGENT |

The finisher report for the round-2 SOLTRIA-B export (delivery 1250x1250,
Q97 4:4:4, self-QC passed): SSIM vs input 1.000, noise floor kept 0.895,
rho1 0.309, residual RMS 0.856 LSB, H1/H0 0.922, ringing 0.000,
flatness delta 0.000, staircase index 0.260, banding origin
"quantization", gradient ladder 1 attempt at alpha 1.00, per-ROI rho1
0.28-0.34 across tiles.

Operator verdict on QUALITY (verbatim): "still too grainy like it's crap
if I'm gonna be truthful... it looks like this image was taken by an
amateur sixty-year-old mum with an old phone, because none of the new
phones capture this grainy anymore."

## The open questions

1. **The delivery lattice is mobile, not 2000px.** The operator clarified:
   the product posts to Instagram/Facebook where most viewers are on
   phones, so the FINAL output should be ~1250-1440px, not 2000px. Today
   the pipeline does 1250 -> finisher upscale -> 2000, and the platform
   downscales again (two resamples after the good pixels). Should the
   pipeline instead process DIRECTLY at the delivery lattice
   (min(source, 1440), finisher upscale OFF)? Quantify the quality win of
   removing the double resample, confirm whether grain generated at 1440
   reads finer than grain enlarged from 1250, and design the smallest
   detection-safe experiment to prove 1250 -> 1440 stage-one delivery
   does not regress the graders (the 2000px jump broke detection; the
   operator will not accept that again).
2. **The grain model is the core ask.** Current grain reads "old phone".
   Modern-phone noise is finer, lower-amplitude, and spectrally different.
   What measurable grain budget (luma amplitude in LSB, chroma amplitude,
   spatial scale in px, rho1/rho2, H1/H0) produces the "new phone" look
   at a 1250-1440px delivery — and which stage should own each component
   (stage-1 injection vs finisher dither vs finisher suppression floors)?
3. **Rendered walls with hue variation are the hardest region.** Sky is
   fixed by the existing gradient branch; painted/rendered walls with
   subtle hue shifts still read grainy or, when smoothed, banded. Design
   the wall treatment: what mask distinguishes "wall" from "sky" and from
   "texture", and what hue-preserving smoothing keeps the render's colour
   variation without grain and without banding? (The operator manually
   fill-buckets these regions today — that is the benchmark to automate.)
4. **Per-image variance**: identical settings produced 0.3% clear, 94%
   fail, and three grader-divergent outputs. Is there one more
   optimization in per-image ROUTING (baseline-aware ladder, source-class
   detection, divergence-aware retry) that meaningfully raises the
   consistent-clear rate, or is manual per-image iteration the honest
   ceiling?
5. **Divergence policy**: the worker gates on one detector vendor; the
   two external graders are sometimes anti-correlated on borderline
   images. Should the shipped gate mark "borderline" outputs
   (ai 0.25-0.45 / flux 0.15-0.30) for mandatory human review, and is
   there a cheap signal the worker can compute itself to predict grader
   disagreement?
6. Rank the top five concrete changes, flag the single largest expected
   visible win for the "old phone grain" complaint specifically, and give
   the minimal experiment set per change. Keep the user-facing knobs
   simple (a handful of presets + the three existing multipliers).

## Constraints (frozen unless you argue with data)

- Stage one's configuration stays byte-identical to the validated version
  (1250px, q92 4:2:0, adaptive ladder). Any stage-one change must include
  a detector A/B proving no acceptance regression.
- The finisher stays non-generative, deterministic, CPU-only, one encode.
- The acceptance gate and thresholds are frozen.
- Changes must be implementable in the existing quality_finish.py +
  worker.py structure.

## What we do NOT need

Product, pricing, or business discussion. Pure technical system and design
recommendations, building on your four previous finisher designs.
