# DeepClean (ComfyUI engine) — Setup & Testing Guide

The DeepClean worker now runs the **Remarkee Max ComfyUI workflow** (the
exact engine twotensors.ai uses): Qwen Image global redraw + Z-Image Turbo face
cleanup, Q4_K_M GGUF, on a 24 GB GPU. This guide gets it built, deployed, and
verified end-to-end.

---

## 0. Prerequisites

- Docker (Desktop or OrbStack) to build the image, **or** the GitHub Actions
  workflow in the repo.
- A RunPod account with serverless enabled.
- Your Supabase project (URL + service role key) with the `deepclean-*` edge
  functions deployed (see `LAUNCH.md` §3).
- An HuggingFace token is **not** required — all 10 model files are public. Set
  `HF_TOKEN` only if you hit rate limits during the first download.

---

## 1. One-time: export the API-format workflow  ⚠️ REQUIRED

This is the one manual step. The worker **will not run** without it.

The workflow ships in `deepclean-worker/workflows/remarkee-max-v2.0.json`
(editor format). ComfyUI's `/prompt` API needs the **API format**.

1. Run ComfyUI locally with all 8 custom-node packs + the 10 models installed.
   The pack list (7 public packs + the vendored Remarkee Max pack) is in the
   `Dockerfile` clone block; the model list + download URLs are in
   `bootstrap_models.py`. Easiest: use a RunPod pod with the ComfyUI template,
   drop `custom_nodes/RemarkeeMax/` into `custom_nodes/`, clone the other 7
   packs, and download the models into the dirs `bootstrap_models.py` specifies.
2. Open the ComfyUI UI, drag `remarkee-max-v2.0.json` onto the canvas.
3. Resolve every red/missing-node / missing-model error until the graph loads
   green. The face path needs RES4LYF's `res_2s` sampler — confirm that node
   pack loaded (it is the most common point of failure; see Troubleshooting).
4. **Menu (top-right gear) → Save (API Format)** → save as
   `deepclean-worker/workflows/remarkee-max-v2.api.json`.
5. Commit it. The worker reads this file at `DEEPCLEAN_WORKFLOW` (default
   `/app/workflows/remarkee-max-v2.api.json`, baked into the image).

Verify the file is the flat API format — it should be a JSON object whose values
look like `"<id>": {"class_type": "LoadImage", "inputs": {"image": "..."}}`,
**not** `{"nodes": [...], "links": [...]}`.

---

## 2. Build the image

```bash
cd deepclean-worker
docker build -t ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest .
docker push ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest
```

Or push the branch to GitHub and run the `DeepClean Worker Image` workflow.

The image is large (ComfyUI + 8 custom-node packs). Expect a long first build.
Container disk on RunPod must be **60 GB+**.

> **Build will fail if** any custom-node `requirements.txt` pulls an
> incompatible torch/diffusers. RES4LYF and `comfyui_controlnet_aux` are the
> usual culprits — see Troubleshooting.

---

## 3. RunPod Serverless endpoint

Create a **Serverless** endpoint:

| Setting | Value |
|---|---|
| Image | `ghcr.io/YOUR_GITHUB_USER/resmarke-deepclean:latest` |
| GPU | 24 GB class: RTX 3090 / 4090 / L4 / A5000 (40 GB+ A6000/L40S keeps both models resident) |
| Concurrency | `1` |
| Timeout | `240s` standard · `300s` strong · `420s` max |
| Container disk | `60 GB` |
| **Network volume** | mount one at `/runpod-volume` |
| Boot timeout | raise to **`1200s`+** for the first cold start (see Troubleshooting) |

Scaling — pick one:

- **Cost beta:** Active workers `0`, Max `1`, Idle timeout `60–300s`. First job
  pays cold start + 10 GB model download.
- **Fast/warm:** Active workers `1`, Max `1`. Worker stays up; `DEEPCLEAN_PRELOAD=1`
  warms Qwen into VRAM at boot so the first real job skips model load.

Worker environment:

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs
DEEPCLEAN_PRELOAD=1
DEEPCLEAN_PRELOAD_PROFILE=standard
DEEPCLEAN_SEED=0
HF_TOKEN=...                # optional, public models
# Optional overrides (defaults shown):
# COMFYUI_BASE=/runpod-volume/ComfyUI
# COMFYUI_URL=http://127.0.0.1:8188
# DEEPCLEAN_WORKFLOW=/app/workflows/remarkee-max-v2.api.json
```

Then copy the endpoint ID into Supabase:

```bash
supabase secrets set RUNPOD_ENDPOINT_ID=YOUR_ENDPOINT_ID
```

---

## 4. Seed the model volume (first cold start)

On the first worker boot, `start.sh` runs `bootstrap_models.py`, which downloads
the 10 model files (~10 GB) into `/runpod-volume/ComfyUI/models/`. Watch the
worker logs in the RunPod console — you should see:

```
[bootstrap] 3/10 files missing; downloading
[bootstrap] qwen-image-2512-Q4_K_M.gguf -> models/diffusion_models/
  qwen-image-2512-Q4_K_M.gguf: 12% (...)
...
[bootstrap] complete
[deepclean:start] launching ComfyUI on 127.0.0.1:8188
[deepclean:start] ComfyUI ready after 18s
[deepclean:cache] workflow template present (...)
[deepclean] Startup preload complete: ...
```

The network volume persists, so **only the first worker ever downloads** — later
boots skip straight to `[bootstrap] all 10 model files already present`.

You can confirm the files landed by checking the volume contents in the RunPod
console, or by sending the warmup payload (§5) and reading the log line
`comfy models populated=True`.

---

## 5. Smoke test: warmup

In the RunPod endpoint **test console**, run:

```json
{ "input": { "action": "warmup", "profile": "standard" } }
```

Expect a response with `"warmed": true` and `"engine": "remarkee-max-v2"`.
If `"warmed": false`, read `warmup_error` — most often it means the API-format
workflow is missing or a node failed to load (Troubleshooting).

---

## 6. End-to-end test through the app

1. Grant yourself credits:
   ```sql
   update public.creator_profiles
   set deepclean_credits = 10
   where user_id = 'YOUR_UUID';
   ```
2. In the app, upload a **known watermarked AI image** (e.g. a Gemini / Nano Banana
   output) as the ground-truth positive to test removal against.
3. Pick profile `standard`, output mode `stripped` (no seal, easiest to inspect).
4. Queue the job. Poll `get-deepclean-job` until `status = completed`.
5. Inspect the `report` in the database:
   ```sql
   select status, runtime_ms, gpu_type,
          report->'engine' as engine,
          report->'quality' as quality,
          report->'identify_before' as before,
          report->'identify_after' as after
   from public.deepclean_jobs order by created_at desc limit 1;
   ```
   - `identify_before` should flag a hidden watermark (C2PA/Google issuer).
   - `identify_after` should read clean (or at least: watermark disrupted).
   - `quality.psnr` should pass the gate (≥18, typically 25–40 for a good
     redraw; too low = over-denoised, too high = under-cleaned).
6. Download the output from `deepclean-outputs` and eyeball faces/text against
   the input. This is the real quality bar.

---

## 7. Per-profile + efficiency check

Run the **same 4K image** through each profile and check `report.engine`:

| profile | expect `process_resolution` | expect `output_resolution` | runtime (warm) |
|---|---|---|---|
| standard | ≤1536 | original | fastest |
| strong | ≤1536 | original | medium |
| max | ≤1800 | original | slowest |

The key efficiency claim to verify: a **4K input** should process at 1536 (or
1800 for max), not 4K — so its runtime should be close to a native-1536 image's
runtime, **not 4× slower**. If a 4K job takes 4× as long, the cap isn't applied
(check `process_resolution` in the report).

Fidelity compare: optionally run the same input through another hidden-watermark
remover
and our `max` output side by side. Faces and text are where differences show.

---

## 8. Troubleshooting

**`workflow template missing` / `warmed: false`**
You skipped step 1. Export `remarkee-max-v2.api.json`, rebuild, redeploy.

**RES4LYF / `res_2s` sampler not found → face path fails**
RES4LYF is the most fragile install. If its `pip install` failed during the
image build (check build log for `WARN: requirements install failed for RES4LYF`),
the face-detailer pass (`SEGSDetailerModelSwap`) errors at runtime.
Rebuild and watch that line. RES4LYF sometimes needs a specific ComfyUI commit.

**First cold start hits the boot timeout**
The 10 GB download can exceed RunPod's default boot timeout. Raise the endpoint's
boot timeout to `1200s+`. Once the network volume is seeded, drop it back to
normal. Alternatively, pre-seed the volume manually by running
`bootstrap_models.py` once on a throwaway pod that mounts the same volume.

**`remove-ai-watermarks` conflicts with ComfyUI's torch at build time**
It's in `requirements.txt` only for the optional `identify` report. If its deps
break the build, delete that line from `requirements.txt` and rebuild —
`identify_image` degrades gracefully (`ok: false`, jobs still succeed), you just
lose the before/after watermark inventory in the report.

**Job fails with `ComfyUI /prompt rejected the graph`**
The API-format workflow references a node or model that isn't present in the
image. The error body (first 500 chars) names the offending node. Usually a
custom-node pack that didn't load, or a model file with the wrong name — all 10
filenames in `bootstrap_models.py` already match the workflow exactly, so a name
mismatch means someone edited the workflow after export.

**Output dimensions look wrong**
Output preserves the creator's native resolution, capped at 2048 px max and
sealed with Fibonacci-88 at that size (no letterboxing). If an output is
unexpectedly small, check `report.engine.output_resolution` — the cap is
`MAX_FINAL = 2048` in `finalize_output()`; raise it if you ship larger.
