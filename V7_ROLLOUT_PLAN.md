# DS ReMint V7 — Keep Real Pixels Real (v1, 2026-08-15)

## 0. State of truth (what the V6 launch data proves)

- V6 shipped and improved results ~33% when quality + detection are scored
  together. The delivered file is still graded by the target detector as:
  **AI-Generated 95.7%, Deepfake 0%, flux: 72.5%, stablediffusionxl: 9.2%,
  zimage: 6%**.
- That breakdown is the diagnosis. It tells us exactly which stage of our own
  pipeline is producing the flag:
  - `zimage: 6%` = the **regional** Z-Image face-detailer path. The only
    masked generator in our stack barely registers.
  - `flux: 72.5%` = the **global** Qwen-Image regeneration (AuraFlow-family
    statistics misattributed as Flux by this detector).
- Every shipped pipeline (`max`, `max-optimised`, `cx`, `ds-v6`) starts from a
  **full-frame VAE round-trip**: `remarkee-max-v2.api.json` runs
  `LoadImage(11) -> Canny(551) -> QwenImageDiffsynthControlnet(552) ->
  KSampler(3)` at denoise 0.08–0.15 across the WHOLE image (node `595`
  RemarkeeMax-AdaptiveDenoise). Even the face path pastes its SEGS onto node
  `568`, which is a resize of the **global Qwen output `61`**, not the
  original. Therefore **100% of delivered pixels are diffusion-reconstructed**
  on every job, regardless of mode.
- The V6 classical chain (spectral reshape, degrid shift+downscale, grain,
  one JPEG encode) can only *shuffle* a fingerprint. It cannot erase a
  full-frame synthetic fingerprint without destroying the image. Proof: the
  adaptive ladder escalated to maximum destruction (5 rungs, downscale −192px)
  and still shipped at 95.7%.
- `detector_gate` is recorded but **never enforced** in `worker.py` or
  Supabase. The only thing that can fail a job is `quality_check` (PSNR ≥ 18).
- Detector probe bytes (`_encode_probe`: q92, 4:2:0) do **not** match the
  delivered bytes (q94, 4:2:2) — the gate measures a different file than the
  grader sees.

### The one-line root cause

We regenerate the whole photograph **because we must**. SynthID embeds
invisibly across the ENTIRE frame, and full-frame reconstruction is the only
mechanism proven (in live tests) to break the carrier. That wash is
non-negotiable — and it leaves behind a fresh full-frame generative
fingerprint. V6's classical chain *shuffled* that fingerprint (noise,
resample, spectral reshape); it never *replaced* it. A shuffled synthetic
frame is still a synthetic frame — 95.7% after five escalation rungs proves
it. The fix is not "regenerate less". The fix is: **after the wash, re-life
the frame the way a camera would acquire it** — a non-generative, physically
modeled acquisition pipeline that replaces generator pixel statistics with
camera pixel statistics.

Two separate jobs, two separate layers:

- **The wash** (generative, full-frame) — where the watermark dies.
- **The re-life** (non-generative, full-frame) — where the fingerprint dies.

V7 keeps the first exactly as it is and rebuilds the second from scratch.

---

## 1. The V7 thesis

> Wash once. Re-life once. Gate everything.

Layer 0 stays exactly as it is: full-frame Qwen regeneration (Canny-guided,
denoise 0.08–0.15, adaptive level as today) — the proven SynthID
carrier-breaker. We keep it.

V7 changes what happens **after** the wash. Today the washed frame goes
through a noise/resample chain that only obscures the Qwen fingerprint. V7
replaces that with a **camera re-life stack**: the washed RGB frame is
re-acquired through a simulated camera pipeline — Bayer CFA mosaicing,
pre-demosaic sensor noise, demosaic reconstruction, micro-rotation/resample,
lens character, white-balance drift, tone curve, and a single JPEG encode.
Every pixel is transformed by non-generative, physics-modeled stages whose
output statistics are camera statistics, not any generator's.

Why this structure, and not another wash:

1. **A second generative pass would re-stamp, not clean.** "Clean it again"
   with another diffusion run replaces Qwen's fingerprint with another
   model's fingerprint (or the same model's, again) and adds another
   smoothing/VAE round-trip on top. The second pass must be non-generative.
   There is no third option.
2. **The Bayer mosaic is the strongest classical move available.** Diffusion
   decoders never produce Bayer/demosaic structure; cameras always do. A
   full-strength CFA round-trip discards half the samples and re-interpolates
   them — destroying the VAE high-frequency fingerprint — while *adding* the
   exact local correlation patterns (channel decorrelation, zipper
   artifacts) that camera-vs-AI classifiers associate with real photographs.
   V6's `bayer_cfa_lite` blended only ~22% and blurred chroma — decorative.
   V7's is a full replacement.
3. **Sensor noise belongs BEFORE demosaic.** Real shot/read noise is added at
   the sensor and then spread by demosaicing. V6 added noise on top of the
   finished frame — it sat *on* the fingerprint. Noise injected at the mosaic
   becomes *part of the image structure*: the fingerprint is made incoherent,
   not merely noisier.
4. **The washed frame is the closest living relative of the original art.**
   Low-denoise Canny-guided regen preserves content; the re-life stack
   preserves it further and only replaces micro-texture. That is as close to
   "as it was originally" as physics allows — the pre-edit pixels are gone
   forever (nano banana overwrote them). What can be restored is the
   *acquisition character* of a real photograph: its noise, its CFA
   structure, its lens, its color pipeline, its compression.

One honest constraint stands: for inputs that arrive fully synthetic
(nano-banana output), there is no untouched original left to preserve. The
re-life stack must therefore be strong enough to clear a 100% synthetic frame
on its own — which is exactly the battle V6 lost, and exactly what the Bayer
round-trip + cross-model mixing in §2 are built to win.

---

## 2. The four moves, ranked by ROI

| # | Move | Expected ROI | Why |
|---|------|--------------|-----|
| **M1** | **Full Bayer camera re-life stack** (non-generative, after the wash) | Largest by far. Replaces synthetic pixel statistics with camera statistics instead of hiding them | V6 proved noise+resample alone cannot clear a full synthetic frame (95.7% after 5 rungs). The CFA round-trip + pre-demosaic noise + lens/color pipeline is the only classical chain that *replaces* the fingerprint rather than shuffles it |
| **M2** | **Cross-model wash mixing** (Qwen + Z-Image full-frame passes, blended) | High, must be verified on the corpus | The detector reads Qwen as "flux: 72.5%" but Z-Image as 6%. Splitting the wash between two generator families halves each fingerprint and forces the source classifier to split its vote. Cost: one extra low-denoise pass (the Z-Image model is already loaded in the workflow). |
| **M3** | **Enforce the source-aware detector gate** (flux-family threshold; probe bytes == delivery bytes) | High | Stops shipping known-flagged files and makes every tuning decision measurable. V6 tuned in the dark |
| **M4** | **Wash-parameter experiments** (Lightning 4-step LoRA off / more steps / lower denoise / Z-Image as the wash generator) | Medium | Distilled 4-step outputs have their own statistical tell; the corpus will rank wash variants by post-re-life detector score. Also answers whether Z-Image can replace Qwen as the wash outright |

Supporting moves (cheap, do with the above):

- **S5** Rewire the adaptive loop from "destroy the whole image harder" to
  "re-life harder, then re-wash differently": rung 0 = wash + balanced
  re-life → stronger re-life preset → cross-model wash → lower denoise →
  only as the last resort a stronger wash. Quality cost is spent where the
  corpus says it pays.
- **S6** Match probe encoding to delivery encoding (same quality,
  subsampling, EXIF), and add an **input baseline probe** to every job
  report (input → wash → re-life, three detector reads).
- **S7** Per-job seed rotation for every stochastic stage (wash seed, noise
  fields, rotation angle, WB drift) so no two jobs share an identical
  fingerprint; keep per-image reproducibility via creator/job seed.
- **S8** Wash at native resolution — the global path's `InpaintCropImproved`
  1024 tiles double-resample the whole frame before the re-life stack even
  runs. Re-life must start from the cleanest wash possible.

---

## 3. M1 — The camera re-life stack (the core build)

### 3.1 Pipeline order (all non-generative, in `camera_relife.py`)

```
washed RGB (output of the unchanged Qwen pre-wash)
  -> micro-rotation + center crop + resample   (phase/grid break)
  -> lens MTF blur (chroma-heavier than luma)  (optics)
  -> sRGB -> linear                            (sensor domain)
  -> Bayer RGGB mosaicing                      (half the samples discarded)
  -> shot + read noise BEFORE demosaic         (sensor noise, physically placed)
  -> bilinear demosaic                         (CFA interpolation structure)
  -> white-balance / channel-gain drift        (color pipeline)
  -> linear -> sRGB + subtle S-curve           (rendering)
  -> chromatic aberration + micro vignette     (lens character)
  -> luma-only unsharp (light)                 (default camera sharpening)
  -> ONE JPEG encode (worker, final bytes)     (delivery)
```

Implemented: `deepclean-worker/camera_relife.py`
(`apply_camera_relife(image, settings, creator_id, seed_extra)` with
`light | balanced | strong` presets) and the local lab harness
`deepclean-worker/tools/camera_relife_harness.py` (corpus runner + live
detector probe via `CX_DETECTOR_URL` when configured).

**Built (2026-08-15):** `deepclean-worker/ds_remint_v7.py` — the full V7
pipeline (wash → color restore → camera re-life ladder → final tone lock →
one JPEG + EXIF → final-byte QC → enforced source-aware gate), wired into
`worker.py` as a new terminal profile `ds-remint-v7` (additive branch only;
V5/V6 code untouched, pass-through single encode). Adaptive gate verified
against the launch verdict (ai 95.7 / flux 72.5 → fail with both reasons;
clear at rung 0 → ships `light`; infra error → no blind escalation).
Harness: `tools/ds_remint_v7_harness.py` (`--no-wash` local mode for
pre-washed frames, `--wash` for the worker image, live probes optional).
Validated locally: all presets run (~50 ms at 640×480), template + adaptive
ledgers correct.

### 3.2 Why each stage, and why the ORDER matters

| Stage | What it destroys / adds | Why it is ordered here |
|-------|-------------------------|------------------------|
| Micro-rotation + resample | Breaks the pixel grid and phase alignment every generator leaves; kills residual Canny-guidance edges | First: later stages must build camera structure on top of a frame with no generator grid left |
| Lens MTF blur | Attenuates the VAE's characteristic high-frequency band | Before mosaicing, exactly like optics before the sensor |
| Bayer mosaicing + **pre-demosaic noise** + demosaic | Discards half the samples; injects sensor noise; re-interpolates with CFA correlation | The core. Noise before demosaic makes noise part of the image structure instead of a coat on top of it |
| WB drift + tone curve | Real camera color-pipeline variance | After the sensor, before the lens-character output stage |
| CA + vignette + luma unsharp | Lens geometry and default sharpening | Last, at delivery resolution |
| One JPEG encode | Final quantization texture | Exactly once, so the gate probes the bytes the grader sees |

The washed frame is synthetic everywhere. The stack's job is to make the
*statistics* of every pixel — spectrum, correlation, noise, color — read as
camera statistics. The Bayer stage is the qualitative difference from V6:
V6 added camera-like grain; V7 rebuilds the frame the way a sensor would
sample it.

### 3.3 Cross-model wash mixing (M2, ComfyUI side)

- Run the existing wash twice: Qwen (current) + a full-frame Z-Image
  img2img at matched low denoise, same Canny guidance.
- Blend 50/50 (or wavelet-domain mix) *before* the re-life stack.
- Two generator families each at half strength + interference = the source
  classifier splits its vote. `zimage: 6%` in the launch output is the
  hypothesis; the corpus is the verdict.
- Implement as a second KSampler branch in the workflow template behind a
  profile flag (`wash_mix: "qwen" | "qwen+zimage"`), not a new workflow.

### 3.4 Why this beats every V6 lever

V6's best lever was "escalate global destruction until the detector clears".
The data says that lever is **exhausted**: five rungs later, still 95.7%.
V7 replaces it with the only classical chain that *replaces* a fingerprint
rather than shuffling it, and adds a second generator family to split the
source attribution at the wash itself.

---

## 4. M3 — Detector gate: make it real and source-aware

Today: recorded, never enforced; probe bytes differ from delivery bytes;
`ai_probability` only.

V7:

1. `_encode_probe()` must encode exactly like delivery (same quality,
   subsampling, EXIF stripped or kept identically). Add a config so the two
   can never drift silently.
2. `_detector_pass()` gains a source gate:
   - `ai_probability <= ai_threshold` (default 0.45)
   - AND `max(flux_family, sd_family, ...) <= source_threshold` (default 0.30)
     parsed from `sources` in the normalized detector payload
     (`deepclean_detector.parse_normalized` already carries `sources`).
   - A `flux: 72.5%` verdict must fail even if `ai_probability` were low.
3. Enforcement policy (owner decision, §9): default = **retry once with the
   next escalation rung** (stronger re-life preset → cross-model wash), then
   ship-best-with-flag if still blocked; the webhook/DB records
   `detector_gate` + `sources` so support and billing can see it. Never
   silently ship a known-flagged file without a ledger entry.
4. Store `detector_gate.cleared`, `ai_probability`, `top_source`,
   `input_baseline` in the job report (existing JSON column or a migration —
   reuse `0003_deepclean_max_jitter_profile` pattern).

---

## 5. Measurement first (this is what V6 skipped)

Do not tune blind again. Before any parameter sweep:

1. Build the corpus: 20–30 images across the real customer segments —
   portraits, group photos, product shots, street, screenshots — each first
   run through a representative upstream AI edit (nano-banana style) so the
   corpus reproduces the full-frame-watermark reality, not just the small
   mask.
2. Detector ensemble for all tuning and gating:
   - the target detector from the launch screenshots (Sightengine-style
     source-attribution output) via `CX_DETECTOR_URL` proxy,
   - Hive,
   - the proxy's `watermark_present` field for the watermark inventory.
   Gate on the **max**, not the mean — you are scored by the harshest grader.
3. KPIs per candidate, measured at three points (input → washed → re-lived):
   - `wash_fidelity` = SSIM/PSNR of the washed frame vs the input (the wash
     must stay content-faithful; re-life must not drop below V6 floors),
   - detector clear rate (ensemble max) and **flux-family top score** as the
     leading detection metric,
   - `deepfake_probability` (must stay ~0 — the red line),
   - human QC rubric (detail, grain, halos, banding, "AI look"),
   - p50/p95 runtime (wash + re-life must fit under the 420 s RunPod cap —
     re-life is CPU-side and should be seconds, not the bottleneck).
4. Sweep only then, ranking by detector clear rate at fixed quality floor:
   - re-life presets {light, balanced, strong} and per-stage amounts
     (rotation, shot/read noise, WB drift, tone),
   - wash variants: Qwen-only vs Qwen+Z-Image mix, Lightning LoRA on/off,
     steps {4, 8}, denoise {0.08, 0.12, 0.15},
   - encode pair {q94 4:2:2 vs q93 4:2:0}.

---

## 6. Service tiers (who gets which pipeline)

| Tier | Trigger | Pipeline | Detector expectation |
|------|---------|----------|----------------------|
| **Standard** (default) | Any job arriving with an upstream AI edit / watermark suspicion | Wash (Qwen, unchanged) → camera re-life (balanced) → enforced gate | Corpus best-case must clear the ensemble; quality floor unchanged |
| **Deep Clean** | Fully-synthetic inputs, or standard tier fails the gate | Cross-model wash mix (Qwen+Z-Image) → re-life (strong) → gate | Best effort; input baseline disclosed before billing |
| **No-wash fast path** (future, optional) | Input baseline probe reads clean AND no watermark signals | Re-life light only, no generative pass | Reserved until the corpus proves it safe — SynthID is not locally verifiable, so this path stays OFF by default |

Route by input baseline probe + standard-tier gate outcome. The dispatch layer
(`dispatch-deepclean-job`) already has profile gating — extend it with
`ds_remint_v7_rollout ∈ {off, all, percent-N}` as the kill switch.

---

## 7. Rollout phases (mirrors the V6 ladder, minus its mistakes)

- **Phase A — First light:** one controlled v7 job (unchanged wash + balanced
  re-life). Record wash_fidelity, the three detector reads, runtime. No
  tuning.
- **Phase B — Corpus + harness:** build the §5 corpus; run
  `tools/camera_relife_harness.py` over washed inputs (wash once on a RunPod
  pod, iterate the re-life locally on the Mac — no GPU needed).
- **Phase C — Sweeps:** the §5 table. Pick defaults; decide wash-mix rollout
  and the source-gate thresholds from data.
- **Phase D — Canary:** 5% → 25% → 100% behind the dispatch gate, watching
  clear rate, quality complaints, credit burn, refunds.

---

## 8. Honesty & positioning (protects the business, not just the bytes)
ash
  fidelity, ensemble verdict before/after. Customers of fully-synthetic
  inputs see the ceiling *before* paying; you avoid refund abuse and
  "it still says 95%" support tickets.
- Position V7 as what it actually does: *"the watermark is removed, and the
  photograph's natural acquisition character is restored."* Do **not** promise
  pixel-identical recovery of the pre-edit image — those pixels were
  overwritten upstream. "As it was originally" means statistically camera-
  like: noise, CFA structure, lens, color pipeline, compression.
- SynthID wording stays exactly as today: removed via regeneration, not
  locally verifiable. Never claim clean on signals you cannot measure.
- Keep the "Deepfake 0%" asset. The gate holds a `deepfake_probability` red
  line (default 0.10) — a regional or wash config that trips it is rejected in the gate
  (a separate `deepfake_probability` threshold, default 0.10).

## 9. Owner decisions needed before Phase C

1. Gate enforcement policy when the ensemble still fails after one escalation
   rung: fail-and-refund vs ship-with-flag (and at which thresholds).
2. Full-clean tier pricing/disclosure wording.
3. Default tier for existing customers during the v7 canary (route v6
   requests to v7 privacy-edit? or keep v6 until 100%?).

## 10. What V7 explicitly retires
dead by
  the launch data; replaced by wash → re-life escalation.
- The v6 "shuffle" chain as the PRIMARY laundering mechanism (spectral
  reshape + degrid + grain-on-top) — demoted to optional supports inside the
  re-life stack, never the mechanism itself.
- Full-frame regeneration as a controversial default — now declared the
  permanent Layer 0 (the SynthID breaker), with the re-life stack as its
  mandatory companionneration as the default path — demoted to the opt-in
  full-clean tier.
- Recording-but-ignoring the detector gate — the gate now gates.
- Blind tuning — corpus + ensemble or nothing.
