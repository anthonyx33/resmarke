# Vacuum task — separate quality-finishing stage for naturalized photographs

## The task, in a vacuum

Previously you designed a coherent camera model (inverse ISP → optics → CFA
→ demosaic → forward ISP) that re-naturalizes the pixels of a re-synthesized
image so they read as photographed. We implemented it, and it is now frozen:
no changes to that stage are on the table.

A new, separate problem exists. The naturalized output is photographically
coherent but reads as low quality on large displays: visible grain in
shadows, mild pixelation, soft edges, and chroma bleed at saturated light
edges. We want a SECOND, completely independent stage — a non-generative,
deterministic quality finisher that runs after the naturalization output and
maximizes perceived quality, without any generative or neural model, and
without undoing the photographic character the first stage established.

Architecture: two steps. Step 1 (frozen) naturalizes. Step 2 (new) finishes.
The finisher must work both as an in-pipeline continuation of step 1 and as
a standalone pass over an already-encoded naturalized JPEG.

## What the input looks like (output of the frozen stage)

- ≤ ~1250px long edge, one JPEG encode at q92 with 4:2:0 chroma.
- Deliberate optical character: per-channel optical PSF (G ~0.25–0.4px,
  R/B ~0.3–0.5px), Bayer CFA round-trip with shot/read noise injected
  before demosaic (Malvar-He-Cutler), weak ISP denoise, WB drift ≤1%,
  subtle CA + vignette, restrained luma sharpening.
- Low-light scenes carry a stronger noise model (intentional); flat regions
  received targeted residual cleanup.

Perceived defects users report, in order: (1) visible grain in shadows and
low-light areas, (2) pixelation / low perceived resolution, (3) chroma
bleed at saturated light edges (warm and teal light cones on walls),
(4) blockiness in smooth gradients (flat walls, sky).

## Constraints (new stage only)

- No generative models, no neural networks, no learned restorers.
  Classical, deterministic transforms only: resampling, frequency
  filtering, tone/color math, deblocking.
- Content fidelity: this is finishing, not re-naturalization. SSIM vs the
  naturalized input ≥ ~0.90 (target ~0.95). No content may be added,
  removed, or invented.
- Photographic character must be preserved. The noise structure is
  intentional character — refine it, never erase it. An output that reads
  "too clean / synthetic-smooth" is a failure mode equal in weight to
  "too noisy".
- Exactly one JPEG encode in the finishing stage. In-pipeline mode may
  consume step 1's pre-encode buffer; standalone mode re-decodes.
- CPU-only, total budget ≤ ~300 ms at 1250px. Deterministic: same input
  must produce the same output.
- The design must include optional 1.5–2× enlargement to ~1900–2500px long
  edge (delivery at native size stays the quality floor; enlargement is the
  HD path).

## Questions

1. What is the minimal-destruction ordered finishing pipeline that
   maximizes perceived quality — crispness, resolution, cleanliness —
   while keeping the naturalized pixels photographic?
2. Enlargement: which classical resampler design (edge-directed / NEDI,
   Lanczos with ringing control, two-pass, per-channel kernels) adds the
   most perceived resolution with the fewest artifacts? When is upscaling
   strictly better than delivering at native size?
3. Grain taxonomy: how do we measurably separate the two grain families —
   sensor-like luminance noise (keep / regularize) vs JPEG mosquito noise
   (remove)? Which cheap local features (frequency band, edge correlation,
   per-channel energy) classify them?
4. Sharpening policy: where in frequency space is sharpening safe on this
   input, and how do we prevent halos at clipped highlight edges (light
   cones) and banding on flat gradients (walls, sky)?
5. Color: how do we repair 4:2:0 chroma bleed at saturated edges and set
   the final encode (quality, subsampling, tables)? Is 4:4:4 worth the
   bytes here?
6. Failure modes: what makes a finished output read LESS photographic
   (over-denoised flatness, oversharpening halos, banding, painterly
   smoothing)? What cheap self-QC metrics catch each (ringing metric,
   banding detection, noise-floor variance, flatness index)?
7. Presets: define three strength levels — conservative / standard /
   strong — with per-stage parameters and a default recommendation.
8. Rank your top five concrete changes with the quality trade-off each
   implies and the minimal experiment set to validate them.

## What we do NOT need

Any product, business, or context discussion. Pure technical system and
design recommendations only, building on your previous coherent-camera
design.
