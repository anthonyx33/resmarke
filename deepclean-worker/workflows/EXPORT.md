# Remarkee Max workflow — API-format export (one-time)

The cleaning engine is ComfyUI running this workflow. ComfyUI's `/prompt`
endpoint requires the **API format** (a flat `{node_id: {class_type, inputs}}`
object), not the editor/UI format that ships in the repo.

`remarkee-max-v2.0.json` checked in here is the **editor format** (straight
from the editor-format graph checked in here) — useful as a reference and to load by hand, but
the worker does not consume it directly.

## One-time export

Run ComfyUI locally with all the v2 custom nodes + models installed (see the
upstream workflow repo README §7–8), then:

1. Drag `remarkee-max-v2.0.json` onto the ComfyUI canvas.
2. Fix any missing-model / missing-node errors until the graph is green.
3. **Menu → Save (API Format)** → save as
   `deepclean-worker/workflows/remarkee-max-v2.api.json`.

That `.api.json` file is the template the worker mutates per job (`worker.py`
`TEMPLATE_PATH`, overridable via `DEEPCLEAN_WORKFLOW`). Commit it.

## What the worker mutates

Only fields with stable, well-known API input names:

- `LoadImage.inputs.image` — set to the uploaded input filename.
- every node with a `seed` input (KSampler, SEGSDetailerModelSwap, …) — set to
  `DEEPCLEAN_SEED` when that env var is set, for deterministic output.

Everything else — the `RemarkeeMax-AdaptiveDenoise` node that scales denoise
by resolution, the Canny→`QwenImageDiffsynthControlnet` structure lock, the
Z-Image face detailer, the 4-step Lightning KSampler — runs as-authored.

## Fast-follows that need this template

Once `remarkee-max-v2.api.json` exists, two optimizations land on top of it
(both are stubbed in `worker.py` `PROFILE_CONFIG`):

- **Conditional face path** — for the `standard` profile, set the face nodes' `mode = 4` (skip)
  on the face subgraph nodes (the second `UnetLoaderGGUF`/`CLIPLoaderGGUF`/
  `VAELoader` for Z-Image, `BboxDetectorCombined_v2`, `SAMLoader`,
  `MediaPipe-FaceMeshPreprocessor`, `MediaPipeFaceMeshToSEGS`,
  `ImpactSimpleDetectorSEGS`, `SEGSDetailerModelSwap`, `SEGSPaste`,
  `InpaintCropImproved`×2) and rewire `SaveImage.inputs.images` to the global
  redraw's `VAEDecode` output. Skips the heaviest path on faceless images.
- **Per-profile adaptive level** — set the `RemarkeeMax-AdaptiveDenoise`
  widget values per profile (raise the denoise ceiling for `max`).
- **Neural upscale-back** — append a `UpscaleModelLoader` +
  `ImageUpscaleWithModel` (Real-ESRGAN x2/x4) for the `max` profile instead of
  the python Lanczos restore, so fine texture survives the cap→restore path.
