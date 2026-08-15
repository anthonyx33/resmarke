# Vacuum task — naturalize re-synthesized image pixels

## The task, in a vacuum

A real photograph has been passed through an image generation model. Every
pixel was re-synthesized by the model's encoder/decoder at low strength: the
content, framing, and composition are nearly identical to the original, but
the fine pixel statistics now read as "generated" rather than photographed.
We now need to post-process this re-synthesized image so its pixels read as a
natural photograph again — same content, same framing, minimal visible change.

There is no prior context to this task. We only need your technical answer to
the question below.

**Question: given an image whose pixels were re-synthesized by a generative
model (content preserved), what is the best strategy to blend, clean, and
naturalize those pixels back into natural photographic form — with the least
possible change to the actual image?**

## What we already do (the current stack)

Non-generative simulated camera acquisition, applied after the
re-synthesis step, in this order:

1. Micro-rotation + center crop + resample (grid/phase break)
2. Lens MTF blur (chroma heavier than luma)
3. Bayer RGGB mosaicing → shot/read noise injected BEFORE demosaic →
   bilinear or Malvar-He-Cutler demosaic
4. White-balance / per-channel gain drift
5. Linear→sRGB + subtle S-curve tone
6. Chromatic aberration + micro vignette
7. Luma-only unsharp (light)
8. Single JPEG encode

Additional variants we have built:

- Quality floors (minimum SSIM vs the re-synthesized input; light /
  balanced / strong ladders of the above stages)
- A degrade → clean → restore → re-clean chain: downscale to 50–78%,
  run the camera simulation at low resolution, restore to delivery size
  with either Real-ESRGAN (alpha-blended vs Lanczos) or classical
  Lanczos + dehalo + luma sharpening, then one final light camera pass
- Re-synthesis with two different generator families blended 50/50

## Constraints

- Content fidelity is the top priority: SSIM floors of 0.75–0.88 vs the
  re-synthesized input are enforced.
- Delivery may be downscaled to ~1250px long edge; mild softness is
  acceptable; visible grain or pixelation is NOT acceptable.
- Exactly one JPEG encode of the delivered file.
- Budget: classical stages run in CPU milliseconds; up to one GPU pass is
  available for restoration; total pipeline must stay fast.

## Questions

1. What pixel-level signatures distinguish a model re-synthesis from a
   camera photograph, and which of them are removable by non-generative
   transforms without changing content?
2. What is the minimal-destruction ordered pipeline that makes
   re-synthesized pixels statistically photographic again (spectrum,
   noise structure, color, geometry)? Where should each stage sit relative
   to the others, and what strengths?
3. When is low-resolution processing + restoration strictly better than
   processing at native resolution, and which restorer family minimizes
   visible artifacts while adding the fewest of its own?
4. Which non-generative transforms are we missing? (JPEG grid alignment,
   resample kernel choice, per-channel MTF, palette/quantization,
   color-matrix simulation, sensor banding, per-channel noise correlation,
   anything else.)
5. Is a per-image candidate-factory architecture (a light candidate, a
   deep-clean candidate, a mixed-generator candidate; select per image)
   the right design, or is there a better selection strategy when no
   ground-truth score exists?
6. Rank your top five concrete changes with the quality trade-off each
   implies, and the minimal experiment set to validate them.

## What we do NOT need

Any product, business, or context discussion. Pure technical system and
design recommendations only.

