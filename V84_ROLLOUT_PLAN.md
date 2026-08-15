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

## 1. The V8.4 thesis

> Stop searching for one config that beats every grader. None exists. Build a
> small factory of the configs we KNOW win somewhere, and ship per image the
> candidate with the lowest ensemble-max — with a downscale-normalized,
> grain-averse "Natural" candidate as the new default.

## 2. Candidate factory (the pieces we already have)

| Candidate | Recipe | Wins at | Cost |
|---|---|---|---|
| **C1 Natural (new default)** | Blend wash (Qwen⊕Z) → ghost_lite ladder → output capped ~1250px long edge → q92, smooth (no grain amplification, no FPN) | The "not grainy, HD+" tier. Downscale-normalization removes information density cheaply and softly — both graders lose signal without texture damage | base |
| **C2 Light** | Qwen wash → V8.1 balanced chain (your 17.2% Sightengine score) | Source-attribution graders; watermark-critical jobs (Qwen = proven breaker) | base |
| **C3 Deep Clean** | Degrade 0.62 → ghost at low res → **classical** restore (drop neural — its flux2 re-stamp never paid) → ghost_lite | TruthScan's best observed movement (80% Medium) at the least attribution cost | base |
| **C4 Deep Clean + Blend** | C3 with Qwen⊕Z wash | The V8.3 blend cut Hive flux 26.2 → 16.7 | +2 GPU passes |

Every candidate ends with: tone lock → ONE JPEG encode (probe bytes == delivery
bytes) → final-byte QC → verdict recorded with ai/flux-family/deepfake.

## 3. Selector

- **Manual mode (today):** run candidates locally via `tools/v82_bench.py`,
  paste TruthScan/Hive/Sightengine numbers, ship the min-max per image.
- **Auto mode (when available):** detector proxy returns `graders` list; the
  worker runs candidates in order C1 → C2 → C3 → C4, probes each on the
  delivered bytes, ships the first whose ensemble-max clears, else the min-max.
- **Report:** every candidate's scores + the shipped one, so support can
  always explain a verdict.

## 4. Downscale-normalization (the user-accepted lever)

You are willing to deliver 1440/1250px and mild blur, but never grain.
Concretely, C1 enforces:

- `output_target` default 1250 (never upscale).
- Ghost_lite minus FPN minus hot pixels: keep Malvar + noise-floor matching,
  cap injected noise to the measured deficit only (never amplify).
- Luma-unsharp light (14%) for crispness without halos.
- q92, 4:2:2.

This is the config built for "HD+, smooth, natural" — and it is also, per
your data, the right detector posture: less texture crime, less information
density, no restorer re-stamp.

## 5. What we stop doing in V8.4

- Neural restore as default (flux2 re-stamp never paid for itself).
- Chasing TruthScan with stronger processing (no config moved it reliably
  below 80 — spend stops there until we know what it keys on).
- Single-config shipping.

## 6. Honest positioning

The selector's min-max is the product. "Shipped configuration beat X on the
harshest grader we can reach" is true, verifiable, and per-image. "Passes
every detector" remains not promised.

## 7. Build order

1. C1 candidate in the worker (`ds-remint-v8.4`: blend wash, ghost_lite
   ladder, output cap 1250, smooth profile) + UI card.
2. Selector in the worker: candidates list + min-max shipping (manual-scores
   mode via bench tool first, auto mode behind the proxy contract).
3. Corpus run: the five images you already have numbers for, all four
   candidates, both graders — that table picks the default.
