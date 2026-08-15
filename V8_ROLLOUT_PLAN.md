# V8 — Ghost (multi-grader camera re-acquisition) (v1, 2026-08-15)

## 0. State of truth (the two graders)

| Grader | V6 | V7 | What changed |
|---|---|---|---|
| Sightengine-style (source attribution) | AI 95.7%, flux 72.5%, zimage 6%, deepfake 0% | **AI 27.7%, flux 12%, zimage 3.9%, kling 2.1%, deepfake 4%** | The wash + camera re-life stack worked as designed on this grader |
| TruthScan (CFA/noise/metadata/GAN checks) | — | **AI 96%, High confidence** | TruthScan runs a different checklist and still reads the frame as synthetic |

Interpretation: V7 fixed the *fingerprint* problem for grader #1 but not the
*camera-structure* problem that TruthScan's checklist targets. We are now in a
multi-grader war, and the only winning strategy is physics realism measured
against an ensemble — not per-detector tricks.

## 1. Diagnosis — TruthScan's checklist mapped to our stack

TruthScan's UI names its checks. Each maps to a specific gap in V7:

| TruthScan check | What it likely measures | V7 gap | V8 counter |
|---|---|---|---|
| **CFA** | Bayer/demosaic structure consistency | We simulate CFA but with a uniform 2x2 **bilinear** demosaic — boxy, uniform, "too clean" | **Malvar-He-Cutler demosaic** (direction-adaptive, zipper at edges) — built in `ghost` |
| **Mapping noise** | Local noise floor consistency across regions | Fixed shot/read coefficients stacked on top of whatever the wash left → bimodal noise | **Noise-floor matching**: measure the wash's floor, inject only the deficit to a camera-plausible target |
| **GAN check** | Global CNN over the whole frame | The Qwen wash still dominates the frame; a strong CNN reads it | Cross-model wash mixing (M2, not yet built) + wash-parameter sweeps (M3) |
| **Geometry** | Grid alignment, perspective, chromatic alignment | Micro-rotation + light CA exist; nothing else | Slight per-channel geometry + stronger optical distortion in `ghost` (already via CA/vignette knobs) |
| **Metadata** | EXIF coherence | Fake iPhone EXIF is the same synthetic signature every job | Isolate: run TruthScan on identical pixels with EXIF stripped vs fake vs honest-minimal; choose empirically (§6) |
| **Filetype / artifacts / pixel hex** | Encode traces, palette quantization | Single q94 4:2:2 encode | Encode sweep q90–94, 4:2:0 vs 4:2:2 against the ensemble |
| **Cloning** | Copy-move regions | None expected | Watch the benchmark; no action unless flagged |
| **Lighting** | Illumination coherence | Preserved by low-denoise wash; nothing local to do | Wash-side experiments only |

## 2. The moves, ranked by ROI

| # | Move | ROI | Status |
|---|------|-----|--------|
| **M1** | **Ghost preset** — Malvar demosaic + fixed-pattern noise (column/row banding) + hot pixels + noise-floor matching | Highest classical ROI; directly answers CFA + noise-mapping checks | **Built** (`camera_relife.PRESETS["ghost"]`), validated locally |
| **M2** | **TruthScan in the ensemble** — gate on the max across Sightengine + TruthScan + Hive | Makes every V8 decision measurable; V7 tuned against one grader only | Owner action: TruthScan API key → put behind the `CX_DETECTOR_URL` normalization proxy |
| **M3** | **Cross-model wash mixing** (Qwen + full-frame Z-Image, blended) | Attacks the GAN-check residual: grader #1 already reads flux 12% on the Qwen-only wash; two families split attribution further | Workflow-level change (second KSampler branch); spec'd in V7 plan §3.3 |
| **M4** | **Wash-parameter sweeps** (Lightning LoRA off, steps 4→8, denoise 0.08–0.15) | Distilled 4-step outputs carry their own tell | Harness rows, no code yet |
| **M5** | **Metadata isolation experiment** | Cheap, might move TruthScan alone | §6 |
| **M6** | **Encode sweep** (q90–94, 4:2:0/4:2:2) | Cheap; TruthScan "filetype/artifacts" checks | Harness rows |

Explicitly NOT recommended: query-based adversarial optimization against
TruthScan's API. It overfits, it's fragile to model updates, and it turns a
physics-based product into an evasion tool. The ghost strategy is
distribution-level realism — it survives grader updates because it moves the
image toward "actually camera-like".

## 3. Ghost preset — what was built

`camera_relife.PRESETS["ghost"]` (additive; light/balanced/strong untouched):

- **Malvar-He-Cutler demosaic** replacing bilinear — gradient-corrected
  interpolation producing the directional zipper structure real cameras emit
  (the boxy 2x2 bilinear structure is itself a tell for CFA checkers).
- **Fixed-pattern noise** — per-column + per-row sensor offsets (banding), a
  structural signature synthetic noise lacks.
- **Hot pixels** — sparse saturated sensor defects spread by the demosaic,
  exactly as a real sensor renders them.
- **Noise-floor matching** — measures the washed frame's existing noise floor
  (laplacian median) and injects only the deficit to the camera-plausible
  target; never stacks.
- Slightly stronger rotation/lens geometry than `balanced`.

Validated: runs in the V7 pipeline (template_preset="ghost"), all four
presets still pass the smoke test, V7 ladder accepts it.

## 4. Benchmark protocol (before any more tuning)

1. Corpus: the same 20–30 images, each washed once on a RunPod pod.
2. For each image run presets {light, balanced, strong, ghost} through
   `tools/ds_remint_v7_harness.py --no-wash --probe-detector` and record
   TruthScan manually (web UI or API) as a second column.
3. Score = ensemble MAX, not mean. Pareto table: detector max vs SSIM/PSNR.
4. Ship the preset that wins the Pareto point the owners choose.

## 5. Wash-side experiments (once the corpus exists)

- Qwen-only vs Qwen+Z-Image mix; Lightning LoRA on/off; steps {4,8}; denoise
  {0.08, 0.12, 0.15}. Each variant washed once, then all four re-life presets.
- Re-verify SynthID removal per variant with the live-test method.

## 6. Metadata isolation + compliance note

Run TruthScan on three copies of the same ghost output: (a) current fake
device EXIF, (b) stripped, (c) honest minimal (software: ResMarke V8,
no device claim). Pick empirically. Remember the compliance direction of
travel: fabricated device metadata on re-synthesized output is the riskiest
claim we make. If (b) or (c) scores equal-or-better, adopt it as default.

## 7. Rollout

- Phase A: corpus + TruthScan column (§4). No ladder changes yet.
- Phase B: pick ghost or keep balanced per the Pareto table; if ghost wins,
  add it to the server composer whitelist (already accepted) and the UI as a
  "Ghost" engine choice.
- Phase C: M3 wash-mix if the corpus says the GAN-check residual is the wall.
- Phase D: canary behind the existing dispatch gate; watch refunds and
  support tickets on the "different website still says 96%" class — that is
  now an honest limitation, handled by §8 wording.

## 8. Honesty & positioning

- Grader results are now plural. The product promise becomes: "removes the
  watermark and restores camera-like statistics; measured against the
  strictest graders we can reach." Never "passes every detector."
- Record both graders in the job report (`detector_gate` already carries the
  verdict shape for one; the proxy should return the ensemble max).
- The 27.7% on grader #1 is the headline win. TruthScan 96% is the next
  mountain, and it may not fully fall — say so.

## 9. What V8 retires

- Single-grader gating — the gate becomes ensemble max.
- Stacked fixed noise — replaced by measured deficit injection.
- Bilinear demosaic as the realistic option — Malvar is the realism default
  wherever the corpus supports it.
- Tuning without a TruthScan column.
