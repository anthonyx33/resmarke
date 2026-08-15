# Vacuum task — follow-up: implementation results, remaining problems, next unlock

This continues the same sandbox task you reviewed previously: naturalize the
pixels of an image that was re-synthesized by a generative model (content
preserved), with the least possible change. Your previous response designed a
coherent camera model (inverse ISP → optics → CFA → demosaic → forward ISP).
We implemented it. Below are the measured results and the three problems we
now need solved. Please build directly on your previous recommendations.

## What we implemented from your design

Your 10-stage production path, verbatim in spirit:

1. single target-scale resample (~1250px long edge, no micro-rotation)
2. weak edge-aware synthesis-residual cleanup (flat regions, 10–30%)
3. inverse tone → inverse camera CCM → inverse WB
4. per-channel optical PSF (G ~0.25–0.4px, R/B ~0.3–0.5px) + CA + vignette,
   all before CFA
5. Bayer RGGB → shot/read noise before demosaic → Malvar-He-Cutler
6. weak edge-aware ISP denoise
7. forward CCM → tone → sRGB
8. restrained luma sharpening → exactly one JPEG encode

Strength ladder: light / balanced / deep (deep = degrade to 68–75% → balanced
pass at low resolution → Lanczos restore → light pass at delivery). WB drift
≤1%, no FPN, no synthetic PRNU, no palette tricks. Your advice on restorers
was taken: Lanczos is the default path; no full-strength perceptual restorer.

## Measured results (two test images, three strength levels, three wash choices)

We score with two independent automated evaluation systems:

- **System P** — per-family source attribution (reports a top model-family
  score; lower is better).
- **System Q** — a multi-check photographic grader (CFA, noise mapping,
  geometry, metadata, cloning, lighting, GAN).

### Image A (exterior dusk scene, warm wall lights)

| Config | System P (AI %) | System P top family | System Q | Notes |
|---|---|---|---|---|
| Qwen wash, Light | **0.2** | 0% | 52% (Low confidence) | |
| Qwen wash, Balanced | **2.6** | 0.7% | 62% (Medium) | |
| Qwen wash, Deep | 2.3 | 0.9% | **6% (High confidence, "real")** | **visibly degraded quality** |
| Qwen⊕Z blend, Balanced | 33.4 | 10% (new family label) | 85% (High) | blend lost |
| Z-Image wash, Balanced | 42.3 | 6.9% (mixed) | 74% (Medium) | blend lost |

### Image B (same content class, different framing/exposure)

| Config | System P (AI %) | System P top family | System Q |
|---|---|---|---|
| Qwen wash, Light | 96.9 | 80.4% | 97% (High) |
| Qwen wash, Balanced | 86.9 | 90.4% | **10% (High, "real")** |
| Qwen wash, Deep | 87.6 | 47.2% + 28% secondary | **18% (High, "real")** |
| Qwen⊕Z blend, Balanced | 55.0 | 72.4% | 45% (Low, "real") |

## The three problems

**P1 — Per-image divergence.** On image A, System P reads clean and System Q
flags. On image B, System Q reads real and System P flags. The same config
scores 2.6% vs 86.9% on P across the two images. No single strength wins both
evaluators on both images. What is the correct optimization target and
selection policy when the evaluators disagree per image and no ground truth
exists?

**P2 — Deep's verdict gain costs visible quality.** Deep earns System Q's
only "real, high confidence" verdict on image A (6%) but is visibly degraded.
We already softened the degrade (68 → 75%). Is there a structurally different
way to win System Q at Balanced without the deep branch's damage — or is the
quality cost intrinsic?

**P3 — The blend counterexample.** You cautioned against generator blending;
we tested it: the 50/50 blend read WORSE than the single wash on both
evaluators (33.4% vs 2.6% on P; 85% vs 62% on Q) and produced a new family
label (10% attribution to a family neither wash showed). What is the
mechanism, and is there a mixing design that actually splits attribution
(e.g., spatial tiling, frequency-band mixing, per-region selection)?

## Questions

1. Given P1, is a single strength axis the wrong abstraction? Should
   candidates branch on image content class (low-light, texture-heavy, text,
   flat gradients), and what cheap pre-classifier features would drive it?
2. What is the minimal feature set to make the per-image selection decision
   between light/balanced/deep without evaluator access at inference time —
   using only our own calibration corpus of genuine photographs?
3. Why does the 50/50 blend fail under the coherent model, and what mixing
   design would you test next?
4. What single refinement to the coherent model most improves System Q at
   Balanced strength (your candidates: stronger pre-CFA MTF, denoise tuning,
   per-luminance noise, CCM choice, second-pass structure)?
5. Are we missing any non-generative transform now that results are in?
6. Rank your top five next changes with expected effect on both evaluators,
   quality trade-offs, and the minimal experiment set.

## Constraints (unchanged)

- Content fidelity first: SSIM floors 0.75–0.88 vs the re-synthesized input.
- Delivery ≤ ~1250px long edge; mild softness fine; visible grain/pixelation
  not fine.
- Exactly one JPEG encode of the delivered file.
- Classical stages CPU milliseconds; one GPU pass available for restoration;
  total pipeline fast.

## What we do NOT need

Any product, business, or context discussion. Pure technical system and
design recommendations only, building on your previous response.
