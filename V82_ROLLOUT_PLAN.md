# V8.2 Max — Degrade → Deep Clean → Neural Restore → Re-life (v1, 2026-08-15)

## 0. State of truth (V8.1 live results)

| Config | Grader #1 (Sightengine-style) | TruthScan |
|---|---|---|
| V8.1 Balanced (ghost_lite ladder) | **AI 17.2%, flux 12%, deepfake 3.1% — "not likely AI"** | 95% High |
| V8.1 Strong (ghost_lite → ghost) | 51.8%, flux2 13.3% | 95% High |

Balanced is the best configuration ever shipped on grader #1 — down from 95.7%
at V6 launch. The plateau is real, and it has two distinct causes:

1. **Grader #1 is near its floor for a full-frame Qwen-washed image.** The
   remaining 12% flux attribution lives in the wash itself — the entire frame
   is Qwen-reconstructed, and laundering at native resolution can only dress
   that signal, not remove it.
2. **TruthScan is outside the optimization loop.** Every tuning decision so
   far optimizes the grader we can query. TruthScan's 95% is a blind spot, not
   a wall we've tested against.

## 1. Why "just mix the pixels harder" plateaued

Detectors do not read one thing. They read spectra, local correlations, noise
maps, CFA structure, geometry, and mid-level texture statistics
simultaneously. Every destructive trick (rotate, resample, noise, filters)
kills some features but either (a) is already robustness-trained into the
classifier, or (b) destroys the very camera structure that convinces other
classifiers. We saw the conflict directly: full ghost helped TruthScan (96→90)
and hurt grader #1 (27.7→76.2). There is no single transform direction that
satisfies both graders at native resolution — only *where the laundering
happens* changes the game.

## 2. Why degrade → restore → re-life works (and why V5 failed)

**Information density.** A generator's fingerprint is distributed across the
frame's fine structure. Downscaling to ~62% destroys roughly half the sample
points and a far larger fraction of the fingerprint's information density —
full ghost cleaning at low resolution is both cheaper and far more total. The
trade (lost detail) is then recovered by a neural restorer.

**V5's actual failure was not the idea — it was never stripping the
restorer's fingerprint.** V5 downscaled, regenerated, upscaled, and shipped;
the upscaler (Real-ESRGAN-family) stamps its own GAN/SR signature, which
detectors read just as eagerly as the diffusion one. V8.2 closes that hole:

```
wash (SynthID breaker, unchanged)
 -> degrade (50-78% scale, floor-gated by quality floor)
 -> full ghost launder AT LOW RESOLUTION (cheap + total)
 -> neural restore to delivery size (Real-ESRGAN x4plus via ComfyUI,
    alpha-blended against Lanczos for hallucination control)
 -> ghost_lite re-life at delivery resolution (strips the restorer's
    fingerprint)
 -> tone lock -> ONE JPEG encode -> ensemble gate
```

Every generative stage is followed by a non-generative acquisition stage.
That pairing is the architectural rule: *no generator's output ever reaches
the grader un-re-lifed.*

## 3. What was built (live)

- `ds-remint-v8.2` mode in the worker: `apply_ds_remint_v8_2` with floors
  - Studio: degrade 0.78, ghost launder, classical-feel restore (max quality)
  - Balanced: degrade 0.62, ghost launder, Real-ESRGAN + ghost_lite (recommended)
  - Strong: degrade 0.50, deepest destruction, then neural rebuild
- Adaptive mode runs floors lightest-first and probes each candidate on the
  DELIVERED bytes against the ensemble gate; ships the first that clears.
- Graceful degradation: neural restore failure falls back to Lanczos + report
  note (validated locally).
- UI toggle card (V8.2 · Max), 14 credits +2 adaptive, server whitelist,
  metadata mode control.

## 4. The moves that remain (ranked)

| # | Move | Why it matters now |
|---|---|---|
| M1 | **Manual-grader bench loop** (`tools/v82_bench.py`) | Built. You already grade TruthScan + Hive manually — this turns each of those checks into ranking data: run the config matrix, paste verdicts into `scores.json`, re-run, and the tool tells you which config wins per image and across the corpus |
| M2 | **Cross-model wash mix** (Qwen + Z-Image at the wash) | The last big lever on the flux residual: grader #1 reads Z-Image at ~4% |
| M3 | **Component ablation corpus** (degrade scale × launder preset × restore alpha) | Picks the Pareto point for V8.2 defaults instead of guessing |
| M4 | **Encode sweep** (q90–94, 4:2:0 vs 4:2:2) | Cheap; one corpus column |

### 4.1 The manual loop (how to run M1)

You are already grading every output by hand — this is the operating procedure
that converts those checks into decisions:

```
# 1. Export washed frames (or any inputs) and run the matrix locally:
python3 tools/v82_bench.py washed/ out/ --floors balanced,strong \
    --metadata device,minimal --control v8.1-balanced

# 2. Grade each output on TruthScan + Hive + the source detector, then
#    fill out/ scores.json keyed by output filename:
#    {"image__v8.2__balanced__device.jpg": {"truthscan": 95, "hive": 62, "sightengine": 17.2}}

# 3. Re-run (outputs are skipped, only ranking recomputes):
python3 tools/v82_bench.py washed/ out/ --scores out/scores.json \
    --floors balanced,strong --metadata device,minimal --control v8.1-balanced
```

Decision rule: lowest **ensemble-max** wins per image; quality (SSIM) breaks
ties; the config with the most wins becomes the V8.2 default. This is the
first time every manual TruthScan/Hive number you produce becomes data.

### 4.2 The exact matrix to run this week

Per image (use the 3–5 images you already have TruthScan/Hive numbers for):

- v8.2 balanced / device
- v8.2 balanced / minimal
- v8.2 strong / device
- v8.2 strong / minimal
- control: v8.1 balanced / device (your 17.2% grader #1 baseline)

Five candidates per image, two numbers each — that table decides the V8.2
default floor and the metadata mode for both graders. No GPU needed for the
bench runs (classical restore); run the winning config once through the live
site with the neural restore to confirm.

## 5. Honesty

- Grader #1 at 17.2% with "not likely AI" as the headline is within the noise
  band of real photographs. The residual flux 12% is the Qwen wash — M2 is the
  only lever that attacks it at the source.
- TruthScan at 95% on a 100% synthetic frame is a strong classifier doing its
  job. The manual bench loop (M1) is the only way to know whether V8.2's
  degrade path moves it — and it costs you nothing beyond the checks you
  already do.
- The product claim stays: "measured against the strictest graders we can
  reach" — never "invisible".
