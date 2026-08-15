# V8.4 — Candidate Factory + Per-Image Selector (blueprint, 2026-08-15)

## 0. The three facts the V8.3 data proved

1. **SynthID removal and AI-detection are orthogonal.** The wash passes the
   watermark test; the graders classify pixel statistics, which are still
   100% synthetic. No laundering config has changed that — and none will.
2. **"flux" is a family label, not a model label.** Z-Image is Tongyi-family
   (the `wan: 7.5%` label appears only on Z-Image runs). Qwen and Z-Image are
   cousins; the detector reads both as flux-family. Z-Image-only scored HIGHER
   flux (23.6–27.1%) than the 50/50 blend (16.7%) — the blend splits the vote.
3. **Heavier processing → higher source-attribution; TruthScan barely moves
   for any config.** Lightest chain: 17.2% (Sightengine). Strongest chains:
   64.7–84.3% (Hive). TruthScan: 80–96 everywhere. The graders want opposite
   things, and strong configs buy unreliable TruthScan movement by spending
   our best score.

## 0.5 Consultant review (G8) — integrated

External review of the vacuum prompt returned a coherent-camera-model
redesign. Adopted (with owner decisions):

- **Inverse ISP → camera space → forward ISP** with paired inverse/forward
  CCM and WB (the biggest missing piece). WB drift reduced to ~0-1%.
- **One combined resample** at target scale; micro-rotation removed from the
  default path (the downscale IS the lattice breaker).
- **Weak synthesis-residual cleanup BEFORE camera simulation** (edge-aware,
  flat-region-only, 10-30% of residual energy) + **weak ISP denoise AFTER
  demosaic**. Replace the residual; don't bury it under camera props.
- **Optics before CFA**: per-channel RGB PSF (σ 0.25-0.5 px), restrained CA
  (0.1-0.3 px corner displacement), 0.5-1.5% vignette — all BEFORE Bayer.
- **MHC demosaic default**; bilinear only for a deliberate soft branch.
- **Restorer policy**: Lanczos default. Neural branch = Real-ESRGAN as a
  luma-restricted, edge-gated residual O = L + αG(SR − L), α ≈ 0.1-0.3.
- **Degrade floors re-classified**: mild 0.80, deep 0.68, emergency 0.50.
- **Selection criterion**: least destructive candidate that enters the
  photographic reference envelope (Pareto), measured against a real-photo
  calibration corpus (radial PSD, anisotropy, noise-vs-luminance, RGB
  residual covariance, edge-spread, JPEG/DCT stats). Grader scores remain
  acceptance/early-stop checks ONLY — never the objective.

Rejected from the review: palette quantization, synthetic PRNU, engineered
JPEG grids, visible FPN banding.

Owner decision pending: generator-family blend as default candidate vs
exceptional branch — resolved by experiment B1 below, not preference.

## 1. The V8.4 thesis

> Stop searching for one config that beats every grader. None exists. Build a
> small factory of the configs we KNOW win somewhere, and ship per image the
> LEAST DESTRUCTIVE candidate that enters the photographic reference
> envelope — with grader scores as acceptance checks.

## 2. Candidate factory

| Candidate | Recipe | Role |
|---|---|---|
| **C1 Coherent (new default)** | Target-scale single resample → weak residual cleanup → inverse tone/CCM/WB → RGB PSF + CA + vignette → Bayer + shot/read noise → WB → MHC → weak ISP denoise → forward CCM → tone/sRGB → restrained luma sharpen → one JPEG | The G8 pipeline. Expected to replace the current camera_relife stack for minimal-destruction jobs |
| **C2 Light** | Current V8.1 balanced (your 17.2% Sightengine score) | Control + watermark-critical jobs |
| **C3 Deep Clean** | Coherent model at degrade 0.68 → classical restore → light re-pass | Deep-clean branch (0.50 only as emergency) |
| **C4 Blend** | C1 with Qwen⊕Z wash blend | Empirical question B1 |

Every candidate ends with: one JPEG encode (probe bytes == delivery bytes) →
final-byte QC → verdict recorded.

## 3. Selection

- **Envelope entry (primary):** least-destructive candidate whose calibration
  features fall inside the real-photo reference band (Pareto over fidelity).
- **Acceptance (secondary):** manual TruthScan/Hive/Sightengine scores as
  early-stop + acceptance; `v82_bench.py` records them.
- **Auto mode (when available):** proxy `graders` list.

## 4. Downscale-normalization (the user-accepted lever)

- `output_target` default 1250, never upscale; single resample to it.
- No grain amplification; injected noise only to the measured deficit
  (display-domain residual RMS ~0.4-0.9/255 midtones).
- q92 4:2:0 for photography, 4:4:4 for text/detail images.

## 5. The experiments that decide V8.4 (G8's six-output matrix)

A Reference (target resize + JPEG only) · B existing pipeline · C coherent
model · D = C + pre-camera residual cleanup · E = D + LR processing +
fidelity restore · F = D + ESRGAN residual α 0.2 · plus B1 = D with
Qwen⊕Z blend wash.

Run on your 5 graded images + ~15 natural reference photos. Record SSIM,
MS-SSIM, low-freq color error, spectral distance to the calibration band,
and both manual grader scores. The winner sets C1 and the default.

## 6. Honest positioning

"Shipped configuration beat X on the harshest grader we can reach" stays the
product claim. "Passes every detector" remains not promised.
