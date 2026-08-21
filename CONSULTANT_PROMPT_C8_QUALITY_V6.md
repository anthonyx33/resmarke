# Vacuum task — quality finisher, sixth iteration: the semi-final optimization — lock detection, fix quality, and resolve the smooth-vs-grain strategy question

## The task, in a vacuum

You designed the finisher and iterations 2-5. All are shipped. The system
now has: a coherent stage one (frozen, byte-identical, detection-validated),
a quality finisher with texture-preserving suppression, gradient dither,
per-ROI QC, a fail-soft ladder, a pre-JPEG handoff, original-reference
fidelity QC, and the Mobile Clean smooth-material branch (your V5 design).

We are at the last significant optimization. The operator and their team
have two competing strategies for the remaining quality problem and need
you to audit the data and rank them — or design a hybrid.

The remaining problem, stated plainly: the images pass (mostly), but the
final delivery still looks too pixelated/grainy for professional consumer
content. Detection and quality are pulling in opposite directions on
textured scenes, and the team needs the ONE strategy that maximizes
consistent quality for professional creators without sacrificing the
cleared-detection results already achieved.

## Live grading data (4 rounds, 3 images, 2 independent graders)

Images: 1 = rendered wall + house at dusk, 2 = pale rendered wall with
light beams, 3 = terracotta brick wall with warm light beams (the
difficult one). The images are attached with this prompt.

| Round | Settings | img1 | img2 | img3 |
|---|---|---|---|---|
| A | (unrecorded) | 43.2% (firefly 36.3) / 43% Real LOW | 5.4% (flux 8.1) / 71% AI MED | 93% (flux 85.2) / 11% Real HIGH |
| B "HD repair" | (unrecorded) | 43.2% / 43% Real LOW | 5.4% / 71% AI MED | 99.2% (flux 97.9) / 59% AI LOW |
| C | strength deep, restoration strong, smoothing 1.25x (dither/sharpen default) | **0.6% / 6% Real HIGH** | **31.9% (flux 21.1, krea 8.8) / 13% Real HIGH** | **16.9% (flux 20.9) / 7% Real HIGH** |
| D | strength deep, restoration strong, dither 0.9x, smoothing 1.1x, sharpen 1.2x | **0.3% / 8% Real HIGH** | **6.2% (flux 8.1) / 6% Real HIGH** | 80.3% (flux 76.2) / 43% Real LOW |

Key observations the team made while running these:

1. Round C is the ONLY round that cleared all three images. Round D is
   the cleanest on images 1-2 but fails image 3 hard. The differentiator
   for image 3 is smoothing 1.25 vs 1.1 — the brick wall flips between
   93% and 16.9% on grader A across rounds.
2. Grader divergence is common and sometimes extreme (img3 round A:
   93% vs 11% Real — an 82-point anti-correlation). The internal gate
   uses a single vendor; borderline outputs are flagged for manual QA.
3. Fidelity HD vs Standard produce visually near-identical output on
   these wall scenes (confirmed by the operator). The texture-confidence
   map already drives retention to ~1.0 in every preset, and the Mobile
   Clean branch auto-applies across presets — so presets are nearly a
   no-op on wall-heavy content; the Smoothing multiplier is the real
   lever.
4. Operator verdict on quality: "so far it looks very bad quality… it
   will perform well just because how pixelated it is… but it definitely
   loses points for the consumer personally, conversion rate will be
   low." Grain/pixelation remains the blocker for professional media.

## The team's two proposed strategies

**Strategy A — lock one best configuration for all images.**
Find the exact best settings combo and use it everywhere (the closest
candidate: deep + strong + smoothing 1.25x, which cleared all three).

**Strategy B — post-clean smoothing / touch-up.**
Leave the cleaning pipeline alone and smooth the FINAL image afterward —
"instead of adding grain, do the opposite: smooth it." Either clean the
graininess after the image is cleaned (a final polish stage), or
integrate a smoothing finish that trades pixel-grain for smooth quality.

## What already exists that these strategies interact with

- The Mobile Clean branch (V5): smooth-material confidence mask +
  cross-scale structure persistence + unstructured residual shrink to
  0.32/0.55 LSB + wall dither 0.15/0.05 LSB, auto-triggered. Built but
  NOT yet validated on these specific images.
- User knobs: preset, delivery size, finish routing, and pro-tuning
  multipliers (dither / smoothing / sharpen, each 0-1.5x over the
  preset's calibrated gains).
- Settings-code filenames now encode exact settings for feedback loops.

## The open questions

1. Rank Strategy A vs Strategy B vs a hybrid, with the reasoning. Which
   produces the highest CONSISTENT professional quality across wall,
   brick, foliage and product scenes without regressing the cleared
   images?
2. Is a fixed global config even the right product shape, or should the
   system auto-select per image (e.g., escalation ladder: start at the
   cleanest config, escalate smoothing when the detector probe is
   borderline)? Design the decision rule with exact thresholds.
3. Image 3 (brick + strong light beams) is the joint failure of quality
   AND detection stability: smoothed more = clears but pixelated;
   smoothed less = flagged. What is the right treatment for lit brick
   texture — hue-preserving smoothing, structure-preserving noise
   reduction, or something else? Give targets.
4. The operator says Fidelity HD looks identical to Standard. Should we
   collapse the preset space into fewer, clearly-different presets, and
   which two or three should remain? What measurable difference must a
   preset produce to justify existing?
5. Design the "post-clean touch-up" stage concretely if you endorse any
   part of Strategy B: where it sits relative to the final encode, what
   it changes, what it must NOT change, and its QC gates.
6. Rank the top five concrete changes with the trade-off each implies
   and the minimal experiment set to validate. Flag the single largest
   expected visible win for the consumer-quality complaint.

## Constraints (frozen unless you argue with data)

- Stage one byte-identical to the validated version (detection is
  settled; any stage-one change needs a detector A/B).
- Finisher: non-generative, deterministic, CPU-only, one encode.
- Acceptance gate thresholds frozen; near-threshold outputs get flagged
  for manual QA rather than shipped silently.
- Keep user-facing knobs simple: a handful of presets + the three
  existing multipliers.

## What we do NOT need

Product, pricing, or business discussion. Pure technical system and
design recommendations, building on your five previous finisher designs.
The attached images and the grading tables above are your full context.
