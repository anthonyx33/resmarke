# Vacuum task — quality finisher, second iteration: residual grain in smooth regions

## The task, in a vacuum

You previously designed a two-step architecture: step 1 (frozen) re-naturalizes
re-synthesized pixels into photographic form; step 2 — the quality finisher you
designed in your last response — restores perceived quality without any
generative model. We implemented your finisher exactly in spirit. It works
directionally, but a reviewer who inspects the finished output says it is
still visibly grainy and pixelated, concentrated in smooth regions — sky and
solid-coloured walls — and the result does not yet read as premium, HD,
professional. We need your opinion on what the design is missing.

## What we implemented from your design

1. JPEG-aware cleanup: edge-aware chroma reconstruction, selective 8×8
   deblock (block-discontinuity test vs intra-block gradients), mosquito
   attenuation near strong edges.
2. Shared masks: shadow, structural flatness (noise-aware), edges,
   saturated/clipped highlights, chroma edges.
3. Two-band shadow noise shrinkage: fine band H0 = Y − G_0.6(Y) shrunk via
   Wiener with a hard residual floor; mid band H1 = G_0.6(Y) − G_1.2(Y)
   preserved fully (your waxy-output warning). Luma floors 0.88/0.70/0.65
   and chroma floors 0.80/0.60/0.50 across conservative/standard/strong.
4. Banding-gated weak gradient cleanup in smooth regions only.
5. Saturated-edge chroma-width repair: guided filter + clamped micro-sharpen.
6. Optional single-pass 1.6× enlargement: Lanczos3 luma with anti-ringing
   limiter and a Lanczos2 hybrid at extreme highlights; Lanczos2 chroma.
7. One masked band-limited luma sharpen after enlargement, with an
   overshoot limiter; flat gradients never sharpened.
8. Single final JPEG Q95 4:4:4, optimized Huffman, EXIF preserved.
9. Self-QC: SSIM ≥ 0.90, luma noise-floor retention ≥ 0.65, flatness
   variance-collapse, ringing, banding, block-grid, chroma-spread. Any
   failure ships the input unchanged.

## Measured outcome

Directional wins: chroma bleed at saturated light edges visibly reduced;
blockiness in smooth gradients reduced; shadow grain reduced. What did NOT
change enough: the reviewer's two worst complaints — grainy sky and grainy
solid walls — persist, and they worsen relative to the input after the 1.6×
enlargement.

Numeric evidence from a representative finished frame:

- SSIM vs the naturalized input ≈ 1.000: the stage barely modified this
  image at all.
- Luma fine-band RMS retained ≈ 0.85–0.90 in smooth regions (by design, the
  floors); the mid band H1 is 100% intact.
- After 1.6× upscaling, the fine-band grain becomes coarser and more
  visible; the mid-band sharpen then passes over it.

Interpretation we reached ourselves (to be challenged): the objectionable
grain in sky/walls is (a) mid-band energy we deliberately preserve, and
(b) interpolation-amplified grain created by our own enlargement — a third
grain class that is an artifact, not photographic character. Our current
design protects both of these as if they were sensor character.

## Attached visual evidence (descriptions)

The attachments are before/after pairs (naturalized input vs finished
output) of dusk exterior scenes: a textured white wall with wall-mounted
lights casting warm amber and teal cone patterns; a walkway along a low
white wall with three warm wall lights and a tiled path; close-ups of the
lit wall with shrubs. Defects the reviewer points at:

1. Sky: coarse luminance grain plus faint contour/block structure in the
   smooth evening gradient. Most objectionable region of all images.
2. Solid white walls: fine speckle grain that becomes clearly visible at
   100% zoom on the 1.6× delivery and reads as "not smooth, not premium".
3. Light-cone interiors: edges are clean; the cone fills retain texture
   noise that reads as dirty rather than photographic.
4. At native size the finished output is acceptable; at the enlarged
   delivery size (the actual product) it is not.

## The open questions

1. Was full H1 preservation the right trade? The reviewer's worst
   complaints live in that band after interpolation. Should smooth regions
   (sky, solid walls) receive a region-conditioned H1 shrinkage with its
   own residual floor, while textured regions keep H1 intact?
2. Interpolated grain: after Lanczos enlargement, the fine band is
   smooth-correlated noise created by our own resampler. Should it be
   regularized as a separate class (it is not sensor character)? Where in
   the order — suppress before enlargement in smooth regions, or clean the
   upscaled fine band after?
3. Premium smoothness without waxy: if we suppress harder in sky/walls,
   what is the minimum residual micro-structure that keeps the output
   reading as a photograph at 2000px delivery — and what should that
   structure be (film-like fine grain, deterministic luminance dither,
   per-luminance noise) so it does not read synthetic?
4. Are sky and wall actually one class ("smooth gradient") or do they need
   separate treatment from shadows?
5. Sharpening policy after enlargement: is the mid-band sharpen locking in
   the interpolated grain? Should sharpening be gated by a local noise
   estimate rather than masks alone?
6. What are we missing entirely? What single change most reduces "grainy
   sky / grainy wall" while preserving photographic character?

## Constraints (unchanged)

- No generative models, no neural networks, no learned restorers.
- Content fidelity: SSIM vs the naturalized input ≥ ~0.90 (target ~0.95).
- Photographic character preserved: too-clean is a failure equal to too-noisy.
- Exactly one JPEG encode in the finisher; CPU-only, ≤ ~300 ms at native
  size, deterministic.
- Optional 1.5–2× enlargement stays in the design.

Please rank your top five concrete changes with the quality trade-off each
implies and the minimal experiment set to validate them.

## What we do NOT need

Any product, business, or context discussion. Pure technical system and
design recommendations only, building on your previous finisher design.
