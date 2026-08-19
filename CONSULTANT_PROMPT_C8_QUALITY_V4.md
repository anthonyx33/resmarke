# Vacuum task — quality finisher, fourth iteration: the 360p problem — grain, pixelation, and lost resolution vs the original

## The task, in a vacuum

You designed the quality finisher and its second and third iterations. We
implemented all of them in full, and the acceptance side of the pipeline is
now settled: five distinct content classes clear both graders at high
confidence, and a foreign-source control is still correctly caught at
~88/91. Nothing about detection is in scope this round.

Exactly one problem remains, and it is existential for the product: the
final delivery looks dramatically worse than the source file. A professional
creator's high-resolution input comes out looking like a 2010 phone photo —
grainy, pixelated, mushy. The operator's words: "it looks like 360p". The
images pass as real, but no working photographer will pay for a service that
tanks image quality this hard. This round has one goal: close the quality
gap between input and output without breaking the settled acceptance side.

## What we implemented from your previous designs (all shipped, all validated)

Round 2 (grain):
1. Four-band decomposition B / H2 / H1 / H0, B and H2 preserved.
2. Texture-confidence map (anisotropy + H1/H2 cross-scale support + H2
   energy) modulating band retention.
3. Region-conditioned H0/H1 suppression BEFORE enlargement (retention
   0.70 / 0.45 / 0.35 across three presets).
4. Dual-kernel enlargement: Lanczos3 for structure, Mitchell for smooth
   regions, feathered by texture confidence.
5. Destination-scale residual decorrelation (subtract the lag-1
   four-neighbour prediction until rho1 clears 0.40; up to 6 passes).
6. SNR-gated mid-band sharpening (k = 3) with fail-soft half-gain retry.
7. Destination-scale QC: SSIM floor 0.90, rho1 ceiling 0.40, residual RMS
   anti-plastic floor 0.15 LSB, H1/H0 ratio, flatness collapse, ringing,
   block grid, chroma spread.

Round 3 (banding / pixelation):
8. Three-point diagnostic proved the staircase is born at 8-bit rounding
   (float buffer is a continuous ramp; JPEG preserves, doesn't create).
9. Always-on gradient-masked shaped dither immediately before quantization
   (deterministic 64px blue-noise-like tile, low-freq suppressed, Nyquist
   rolloff; luma 0.30/0.35/0.40 and chroma 0.12/0.15/0.20 LSB RMS per
   preset). Nothing follows except quantization + one Q97 4:4:4 encode.
10. Chroma gradient decontouring (guided, r=4) for twilight skies.
11. Case-B guard: local surface reconstruction only when the float buffer
    itself carries staircases, gated on a coherence staircase index (>2).
12. Banding-origin diagnostics (float/8-bit/jpeg) + staircase index on the
    decoded delivery + a SOF-marker delivery self-check (dims + sampling).
13. Q95 -> Q97 4:4:4.

Round 3.1 (system):
14. Fail-soft alpha ladder: gradient-axis QC failures retry with the
    smooth-gradient branch blended down (alpha 1.0 -> 0.75 -> 0.5 -> 0.25
    -> 0); texture processing untouched.
15. Per-ROI gradient QC (3x3 tile grid: rho1 / residual RMS / banding /
    coverage per tile) in every report.
16. User pro-tuning: dither 0-1.5x, smoothness 0.5-1.5x, sharpen 0-1.5x
    multipliers over each preset, clamped at the edge and in the worker.

## Measured outcome after round 3.1

- Metrics: rho1 0.089-0.40 (ceiling 0.40), SSIM >= 0.9986, all six
  preset x scale combinations pass QC; delivery_check confirms 4:4:4.
- Acceptance: 4/4 nano-banana classes clear both graders (3.8-13.8% /
  6-28% Real); a ChatGPT-enhanced source still reads 87.7/91 after the
  same remint — the gate correctly blocks it.
- Operator verdict on QUALITY: "very grainy, very pixelated compared to
  the original high-quality image… looks like it was taken in 2010…
  probably 360p." Passing, but not sellable to professionals.

## Pipeline facts you must challenge (audited from the live build)

1. Stage one (the coherent camera pass) delivers at UP TO 1250px on the
   long edge, encoded once at q92 with 4:2:0 chroma. Professional sources
   arrive at 2000-6000px. The pipeline therefore DISCARDS most of the
   source resolution before stage two ever sees a pixel.
2. Stage one injects synthetic sensor/optical character (deliberate
   grain) as part of the camera re-acquisition; amplitude tracks the
   "strength" setting (light/balanced/deep).
3. Stage two (the finisher) then ENLARGES that 1250px q92 4:2:0 file to
   2000px and re-encodes at Q97 4:4:4. It cannot restore detail stage one
   destroyed; its H0/H1 suppression removes grain by removing high/mid
   band energy, which on an already small file reads as mush.
4. The finisher's QC floors prevent total smoothing but do not measure
   "perceived HD" vs the ORIGINAL high-res source — they compare against
   the already-degraded stage-one file (SSIM vs input = SSIM vs a 1250px
   q92 image).
5. Known tension: graders read over-smooth AI-looking output as fake, so
   grain cannot simply be zeroed. The quality fix must remove the WRONG
   grain (coarse, correlated, 4:2:0 chroma) while keeping or replacing
   the RIGHT grain (fine, uncorrelated, camera-like).

## The open questions

1. Where is most quality actually lost — stage one's resample/encode, the
   injected grain, the finisher's suppression, or the enlargement? What is
   the cheapest two-image experiment that isolates each loss and measures
   it in dB?
2. Should stage one's delivery ceiling rise (e.g. 2000px q95 4:4:4) and
   the finisher clamp enlargement accordingly? What breaks in the
   acceptance side if it does? (This is the single largest suspected win.)
3. Design ONE new finisher setting — "Fidelity HD" or similar — that a
   creator can select for maximum output quality: what exactly does it
   change (suppression floors, dither, sharpen, upscale kernel, chroma
   handling), and what does it cost (size, runtime, risk)?
4. What should the finisher measure against the ORIGINAL pre-stage-one
   source (which it never sees today) to gate "too much destruction"? If
   it can't see the source, what proxy metric on the delivered file best
   predicts the operator's 360p verdict?
5. Grain budget: given the grader tension, what measurable grain budget
   (amplitude, rho1, H1/H0, per-ROI RMS) keeps acceptance while reading
   as premium? Which of our existing metrics is the best predictor?
6. Is the 4:2:0 chroma from stage one responsible for a meaningful share
   of the pixelation look, and does chroma upsampling before luma work
   change the outcome?

## Constraints (unchanged unless you explicitly argue a change with data)

- The finisher stays non-generative, deterministic, CPU-only.
- Exactly one encode in the finisher.
- The acceptance gate and its thresholds are frozen; any proposal that
  raises grader scores on current clear classes is a non-starter unless
  you quantify the trade.
- User-facing knobs stay simple: at most a handful of presets plus the
  existing three pro-tuning multipliers.

## What we do NOT need

Product, pricing, or business discussion. Pure technical system and design
recommendations only, building on your three previous finisher designs.

Please rank your top five concrete changes with the quality trade-off each
implies, flag which single change you expect to deliver the largest visible
win, and give the minimal experiment set to validate each. Be explicit
about anything that must change OUTSIDE the finisher (stage one), since
the team can re-open that stage if the evidence justifies it.
