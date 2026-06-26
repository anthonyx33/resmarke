# Remarkee Max API workflow export runbook

The worker needs:

```text
deepclean-worker/workflows/remarkee-max-v2.api.json
```

That file is currently missing. The checked-in file:

```text
deepclean-worker/workflows/remarkee-max-v2.0.json
```

is **ComfyUI editor format**. It has `nodes`, `links`, `groups`, and canvas
positions. The RunPod worker cannot send that to ComfyUI's `/prompt` endpoint.

The required output is **ComfyUI API format**: one flat JSON object keyed by
node id, where every node looks like:

```json
{
  "10": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "example.png"
    }
  }
}
```

If the exported file still has top-level `nodes` or `links`, it is wrong.

---

## Recommended path: export from a temporary RunPod ComfyUI pod

Do this from a temporary GPU pod, not the serverless endpoint. The endpoint is
for production jobs; a pod gives you a browser UI, terminal, and file access.

### 1. Start a temporary pod

In RunPod:

1. Go to **Pods**.
2. Deploy a **ComfyUI** template.
3. Pick any available GPU. A cheap 16-24 GB GPU is fine because this is mostly a
   workflow export, not a production run.
4. Wait until the pod is running.
5. Open the pod's **Web Terminal**.

### 2. Install the exact custom nodes

In the pod terminal, find the ComfyUI directory. Common locations are
`/workspace/ComfyUI`, `/ComfyUI`, or `/app/ComfyUI`.

Run:

```bash
find / -maxdepth 3 -type d -name ComfyUI 2>/dev/null | head
```

Set `COMFY` to the result. Example:

```bash
export COMFY=/workspace/ComfyUI
cd "$COMFY/custom_nodes"
```

Install the public node packs used by the production Dockerfile:

```bash
git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git ComfyUI-GGUF
git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Impact-Pack.git ComfyUI-Impact-Pack
git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Impact-Subpack.git ComfyUI-Impact-Subpack
git clone --depth 1 https://github.com/rgthree/rgthree-comfy.git rgthree-comfy
git clone --depth 1 https://github.com/Fannovel16/comfyui_controlnet_aux.git comfyui_controlnet_aux
git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes.git ComfyUI-KJNodes
git clone --depth 1 https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch.git ComfyUI-Inpaint-CropAndStitch
git clone --depth 1 https://github.com/BadCafeCode/masquerade-nodes-comfyui.git masquerade-nodes-comfyui
git clone --depth 1 https://github.com/ClownsharkBatwing/RES4LYF.git RES4LYF
```

Install their requirements:

```bash
for d in ComfyUI-GGUF ComfyUI-Impact-Pack ComfyUI-Impact-Subpack rgthree-comfy comfyui_controlnet_aux ComfyUI-KJNodes ComfyUI-Inpaint-CropAndStitch masquerade-nodes-comfyui RES4LYF; do
  if [ -f "$d/requirements.txt" ]; then
    /usr/bin/python3 -m pip install -r "$d/requirements.txt"
  fi
done
```

Now add the vendored Remarkee Max node pack from this repo:

```bash
cd /workspace
git clone https://github.com/anthonyx33/resmarke.git
cp -R /workspace/resmarke/deepclean-worker/custom_nodes/RemarkeeMax "$COMFY/custom_nodes/RemarkeeMax"
/usr/bin/python3 -m pip install -r "$COMFY/custom_nodes/RemarkeeMax/requirements.txt"
```

Restart ComfyUI after installing nodes. In the RunPod pod UI, use the template's
restart button if it has one. Otherwise stop and start the ComfyUI process from
the pod console.

### 3. Load the editor workflow

Open the ComfyUI web UI for the pod.

Load this file:

```text
/workspace/resmarke/deepclean-worker/workflows/remarkee-max-v2.0.json
```

You can either:

- drag the file into the ComfyUI canvas from the file browser, or
- use ComfyUI's **Load** button and select the file.

### 4. Confirm required nodes are present

The loaded graph should not show red “missing node type” boxes.

The important node classes are:

```text
LoadImage
KSampler
UnetLoaderGGUF
CLIPLoaderGGUF
VAELoader
ModelPatchLoader
QwenImageDiffsynthControlnet
RemarkeeMax-AdaptiveDenoise
Canny
BboxDetectorCombined_v2
SAMLoader
MediaPipe-FaceMeshPreprocessor
MediaPipeFaceMeshToSEGS
ImpactSimpleDetectorSEGS
SEGSDetailerModelSwap
SEGSPaste
InpaintCropImproved
ImageResizeKJv2
Image Comparer (rgthree)
Power Lora Loader (rgthree)
```

Common missing-node fixes:

| Missing node text | Install/check |
|---|---|
| `UnetLoaderGGUF`, `CLIPLoaderGGUF` | `ComfyUI-GGUF` |
| `UltralyticsDetectorProvider` | `ComfyUI-Impact-Subpack` |
| `BboxDetectorCombined_v2`, `SAMLoader`, `SEGSDetailerModelSwap` | `ComfyUI-Impact-Pack`, `ComfyUI-Impact-Subpack`, and `RemarkeeMax` |
| `ImageResizeKJv2` | `ComfyUI-KJNodes` |
| `Get Image Size` | `masquerade-nodes-comfyui` plus `ComfyUI-KJNodes` |
| `Image Comparer (rgthree)`, `Power Lora Loader (rgthree)` | `rgthree-comfy` |
| `Canny` | `comfyui_controlnet_aux` |
| `InpaintCropImproved` | `ComfyUI-Inpaint-CropAndStitch` |
| `res_2s` sampler errors | `RES4LYF` loaded incorrectly |
| `RemarkeeMax-AdaptiveDenoise` | vendored `RemarkeeMax` folder missing |

### 5. Save in API format

In ComfyUI:

1. Open **Settings** / gear icon.
2. Enable **Dev mode Options** if it is available.
3. Open the workflow menu.
4. Click **Save (API Format)**.
5. Save/download the file as:

```text
remarkee-max-v2.api.json
```

Put it into your local repo at:

```text
deepclean-worker/workflows/remarkee-max-v2.api.json
```

ComfyUI UI wording changes by version. If you do not see **Save (API Format)**,
the usual cause is that **Dev mode Options** is off.

### 6. Validate locally before committing

From the repo root:

```bash
python3 deepclean-worker/workflows/validate_api_workflow.py
```

Expected result:

```text
OK: deepclean-worker/workflows/remarkee-max-v2.api.json is ComfyUI API format.
```

If it says the file has `nodes` or `links`, you saved the editor format again.
Go back to ComfyUI and choose **Save (API Format)** specifically.

### 7. Commit and push

```bash
git add deepclean-worker/workflows/remarkee-max-v2.api.json
git commit -m "worker: add Remarkee Max API workflow"
git push origin main
```

GitHub Actions will rebuild the worker image because `deepclean-worker/**`
changed. Use the new SHA image in RunPod.

---

## Required model filenames

The export should preserve these model references:

```text
qwen-image-2512-Q4_K_M.gguf
Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf
qwen_image_vae.safetensors
qwen_image_canny_diffsynth_controlnet.safetensors
Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors
z_image_turbo-Q4_K_M.gguf
Qwen_3_4b-imatrix-IQ4_XS.gguf
ae.safetensors
yolov8n-face.pt
sam_vit_b_01ec64.pth
```

The production worker downloads these into `/runpod-volume/ComfyUI/models/`
using `bootstrap_models.py`, so the export pod does not need to be permanent.
