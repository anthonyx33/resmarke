# Consultant brief — image post-processing pipeline outputs falsely flagged as AI-generated

## The ask

We operate an automated image post-processing service. The service removes an
invisible full-frame pixel watermark from images (this step is solved and must
stay), but the resulting output is consistently flagged as "AI-generated" by
third-party image detectors. We need a technically grounded optimization of
the pipeline so outputs grade as natural photographs. We are NOT asking for
adversarial evasion of a specific detector — we are asking for pipeline
design that produces genuinely camera-like pixel statistics, measured against
the strictest detectors we can reach.

Please review the system below and give ranked, concrete recommendations with
expected score deltas and experiments we should run.

## Current pipeline (all versions share this skeleton)

1. WASH (generative, full-frame — required): low-denoise img2img regeneration
   of the entire frame. Breaks the watermark carrier. Leaves a generative
   fingerprint.
2. CAMERA RE-LIFE (non-generative): simulated camera acquisition — micro-
   rotation, lens blur, Bayer RGGB mosaicing + pre-demosaic shot/read noise +
   demosaic (bilinear or Malvar-He-Cutler), white-balance drift, tone curve,
   chromatic aberration, vignette, luma unsharp.
3. Single JPEG encode + QC + detector gate.

Later versions added: quality floors (min-SSIM vs original), a degrade ->
launder at low resolution -> restore -> re-life chain (Real-ESRGAN or
classical Lanczos+dehalo+sharpen), and a wash-model choice (Qwen-family,
Z-Image/Tongyi-family, or a 50/50 blend of both).

## Version history with measured scores

| Version | Config | Sightengine-style | Hive | TruthScan |
|---|---|---|---|---|
| V6 | Qwen wash + noise/resample launder | AI 95.7%, flux 72.5% | — | 96% High |
| V7 | Qwen wash + camera re-life (Bayer + noise) | AI 27.7%, flux 12%, zimage 6% | — | — |
| V8 | V7 + full ghost (Malvar + FPN + hot pixels) | AI 76.2%, flux 28.5% | — | 90% High |
| V8.1 balanced | ghost_lite ladder (Malvar, low FPN) | **AI 17.2%, flux 12%** | — | 95% High |
| V8.1 strong | ghost_lite → ghost | 51.8%, flux2 13.3% | — | 95% High |
| V8.2 strong | degrade 0.5 → ghost → Real-ESRGAN → re-life | — | 76.4%, flux 26.2%, flux2 9.2% | **80% Medium** |
| V8.3 blend strong | Qwen⊕Z wash + V8.2 strong | — | 64.7%, flux 16.7%, flux2 6.3%, sd 5.2% | 94–96% High |
| V8.3 zimage strong | Z-Image wash only | — | 81.4%, flux 23.6%, wan 7.5% | 93% High |
| V8.3 zimage classical | Z-Image wash + classical restore | — | 84.3%, flux 27.1%, sd 8% | 82% High |

## Constraints

- RunPod GPU job ceiling 420 s; each wash is ≤300 s; classical stages are CPU
  milliseconds; a Real-ESRGAN restore is ~1 GPU pass.
- Final delivery may be downscaled to ~1250px long edge; mild blur is
  acceptable; visible grain/pixelation is NOT acceptable.
- Exactly one JPEG encode of the delivered file.
- Detectors: Sightengine-style (per-model source attribution), Hive, and
  TruthScan (claims to check CFA, noise mapping, geometry, metadata, cloning,
  lighting, GAN). All grading is currently manual; an API is possible later.

## Questions

1. Why does flux-family attribution persist across BOTH wash families (Qwen
   and Z-Image/Tongyi), and what generator family or VAE choice would
   minimize detector affinity while still reconstructing every pixel?
2. What do detectors like TruthScan most plausibly key on for a frame that is
   100% re-synthesized but camera-structured? What test would prove it?
3. Is downscale-normalization (fixed ~1250px output, light chain) the right
   default posture, and what quality cost should we expect?
4. Is a per-image candidate-factory + selector (light candidate, deep-clean
   candidate, blend candidate; ship min-max across graders) the correct
   architecture, or is there a better selection strategy?
5. What classical (non-generative) transforms are we missing? (JPEG grid
   alignment, resample kernel choice, per-channel MTF, palette/quantization,
   color-matrix simulation, sensor banding, anything else.)
6. Rank your top five concrete changes with expected effect on both grader
   classes, and the minimal experiment set to validate each.

## What we do NOT need

Product narrative, business model advice, or compliance opinions. Pure
technical system and design recommendations only.
