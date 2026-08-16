# Vacuum task — quality finisher, third iteration: banding and residual pixelation in large flat colour regions

## The task, in a vacuum

You previously designed the quality finisher and its second iteration. We
implemented both. The second iteration succeeded directionally: the coarse
correlated grain in smooth regions is largely gone, and the measured
metrics moved into your target bands (lag-1 autocorrelation from ~0.7 to
~0.5, H1/H0 ratio from ~1.5-1.7 to ~1.0, residual RMS ~0.4 LSB at the
2000px delivery).

One complaint remains, and it is now the only complaint: large flat colour
regions — most prominently the sky, secondarily rendered walls — still
look pixelated and visibly banded on the enlarged delivery. The reviewer
inspects at 100% zoom on a 2000px file and sees faint staircase contours
and residual coarse structure in what should read as a clean premium
photographic gradient.

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
- The reviewer's grain complaint: substantially reduced.
- NEW dominant complaint: banding / contouring / residual pixelation in
  large smooth gradients, especially the sky. This appeared as the grain
  receded.

Our working hypothesis (to be challenged): suppressing the sky's noise
removed the dither that was masking 8-bit quantization staircases; the
remaining defect is now quantization contouring plus whatever residual
structure survives the final JPEG encode. The emergency dither (0.3 LSB)
is likely too weak, and may be partially erased by the final encode
itself.

## Attached visual evidence (descriptions)

The attachments show the finished 2000px deliverables of dusk exterior
scenes at 100% zoom, focused on:

1. Twilight sky: a smooth blue luminance gradient showing faint horizontal
   staircase bands plus low-amplitude residual block structure.
2. Rendered white wall under warm light: subtle contour lines in the light
   falloff gradient.
3. For reference, the same regions in the naturalized input before
   finishing: grainier, but with no visible staircase contouring.

## The open questions

1. Banding vs grain: is the remaining defect quantization contouring
   (8-bit staircase) or residual correlated noise? What cheap metrics
   separate them (gradient histogram runs, per-line variance, local
   monotonicity), and what are the target values for a premium sky?
2. Dither strategy: what amplitude, spectrum (blue-noise vs white), and
   region policy (always-on in smooth gradients vs emergency) produces an
   invisible-to-clean staircase breaker that reads photographic? Does
   0.4-0.7 LSB survive a Q95 4:4:4 encode, or must the dither be designed
   with the encoder's quantization step in mind?
3. Should the sky be suppressed LESS, not more, now that grain has
   receded? At what point does smooth-region suppression start creating
   the staircase it is meant to hide?
4. Chroma gradients: the twilight blue sky bands in chroma as well as
   luma. Should chroma receive its own gradient-fidelity treatment, and
   is 4:4:4 sufficient at 8-bit?
5. Is a dedicated "gradient fidelity" stage warranted between
   suppression and the final encode — e.g., local linear re-fitting of
   smooth gradients plus sub-LSB error diffusion — and where exactly does
   it sit?
6. What are we missing entirely? What single change most improves a large
   flat sky from "acceptable" to "premium" while keeping the surface
   photographic?

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
