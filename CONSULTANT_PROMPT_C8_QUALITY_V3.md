# Vacuum task — quality finisher, third iteration: banding and residual pixelation in large flat colour regions

## The task, in a vacuum

You previously designed the quality finisher and its second iteration. We
implemented both in full. Iteration two succeeded: the coarse correlated
grain in smooth regions is largely gone and the measured metrics moved
into your target bands (lag-1 autocorrelation ~0.7 -> ~0.5, H1/H0 ratio
~1.5-1.7 -> ~1.0, residual RMS ~0.4 LSB at the 2000px delivery).

The acceptance side of the overall pipeline is now consistent across four
distinct content classes at high confidence, so it is settled and out of
scope for this round.

Exactly one visual defect remains, and the reviewer inspects it at 100%
zoom on the 2000px delivery: large flat colour regions — most prominently
the sky, secondarily rendered walls — look pixelated and faintly banded.
Faint staircase contours and residual coarse structure in what should read
as a clean, premium photographic gradient. This round has one goal: make
those gradients premium without breaking anything else.

## What we implemented from your last design (all of it)

1. Four-band decomposition B / H2 / H1 / H0 with B and H2 preserved.
2. Texture-confidence map (structure anisotropy + H1/H2 cross-scale
   support + H2 energy) modulating band retention.
3. Region-conditioned H0/H1 suppression BEFORE enlargement (smooth-region
   retention 0.70 / 0.45 / 0.35 across three presets).
4. Dual-kernel enlargement: Lanczos3 for structure, Mitchell-Netravali for
   smooth regions, feathered by texture confidence.
5. Destination-scale residual decorrelation (subtract the lag-1
   four-neighbour prediction of the fine residual in smooth regions until
   lag-1 autocorrelation clears a ceiling).
6. SNR-gated mid-band sharpening (k = 3) with a fail-soft half-gain retry.
7. Destination-scale QC: lag-1 autocorrelation ceiling, residual RMS
   anti-plastic floor, H1/H0 ratio, banding staircase index measured on
   the quantized result, ringing, block-grid, chroma spread.
8. Emergency deterministic dither (0.3 LSB) only when the banding QC trips.
9. Single final JPEG Q95 4:4:4.

## Measured outcome after iteration two

- Grain metrics: improved into target bands (above).
- Reviewer's grain complaint: substantially reduced.
- NEW dominant complaint, stated plainly: pixelation / faint banding in
  large flat gradients, especially the sky. It appeared as the grain
  receded.

Our working hypothesis (to be challenged): suppressing the sky's noise
removed the dither that was masking 8-bit quantization staircases. The
remaining defect is quantization contouring plus whatever residual
structure survives the final JPEG encode, and the 0.3 LSB emergency
dither is too weak and may be partially erased by that encode.

## Attached visual evidence (descriptions)

The attachments show finished 2000px deliverables at 100% zoom, focused on:

1. Twilight sky in wide exterior scenes: a smooth blue gradient showing
   faint horizontal staircase bands plus low-amplitude residual block
   structure. The most objectionable region in every image.
2. Sky backgrounds in close-up garden shots: same defect, smaller area.
3. Rendered white wall under warm light: subtle contour lines in the light
   falloff gradient.
4. Reference: the same regions in the naturalized input before finishing —
   grainier, but with no visible staircase contouring.

## The open questions

1. Is the remaining defect quantization contouring (8-bit staircase) or
   residual correlated noise? What are the two cheapest metrics that
   separate them, and what are their target values for a premium sky?
2. Dither strategy: amplitude, spectrum (blue-noise vs white), and region
   policy (always-on in smooth gradients vs emergency-only). What design
   survives a Q95 4:4:4 encode and remains sub-visible at 100%?
3. Should smooth-region suppression be CAPPED, not raised, now that grain
   has receded? At what point does suppression create the staircase it
   was meant to hide?
4. Chroma: the twilight blue sky bands in chroma too. Does it need its own
   gradient treatment, or does luma dither plus 4:4:4 suffice?
5. Is a dedicated final "gradient fidelity" stage warranted (local linear
   re-fitting of smooth gradients + sub-LSB error diffusion), and where
   exactly does it sit relative to the single final encode?
6. What single, minimal, safe change most improves a large flat sky from
   acceptable to premium while keeping the surface photographic?

## Constraints (unchanged)

- No generative models, no neural networks, no learned restorers.
- Content fidelity: SSIM vs the naturalized input ≥ ~0.90 (target ~0.95).
- Photographic character preserved: too-clean is a failure equal to too-noisy.
- Exactly one JPEG encode in the finisher; CPU-only, ≤ ~300 ms at native
  size, deterministic.
- Optional 1.5-2x enlargement stays in the design; the reviewer grades the
  enlarged file.

Please rank your top five concrete changes with the quality trade-off each
implies and the minimal experiment set to validate them.

## What we do NOT need

Any product, business, or context discussion. Pure technical system and
design recommendations only, building on your previous finisher designs.

