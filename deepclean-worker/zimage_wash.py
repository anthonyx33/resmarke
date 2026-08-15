"""Z-Image full-frame wash (V8.3).

The V8.3 unlock: move the wash off the Qwen/Flux VAE family. Across every live
run, source-attribution detectors read Z-Image at ~4-6% where they read Qwen
at 12-72%. This module runs a full-frame Z-Image img2img pass through ComfyUI
using the exact model/clip/sampler recipe the Remarkee Max face detailer uses
(z_image_turbo GGUF + Qwen_3_4b lumina2 clip + res_2s/bong_tangent) -- the
config we KNOW the workflow boots and the graders read low.

It is a wash, not a detailer: low denoise (0.08-0.2), tiled VAE encode so
native resolution survives, one output. SynthID carrier break must be
re-verified with the live-test method per denoise choice -- Qwen remains the
proven breaker; this module is the experiment.
"""

import io
import time

from PIL import Image


MODEL_UNET = "z_image_turbo-Q4_K_M.gguf"
MODEL_CLIP = "Qwen_3_4b-imatrix-IQ4_XS.gguf"
MODEL_VAE = "ae.safetensors"


def run_zimage_wash(input_path, output_path, denoise=0.12, seed=None, process_cap=1536, timeout=300):
    import comfyui_client as cc

    started = time.time()
    source = Image.open(input_path).convert("RGB")
    orig_w, orig_h = source.size

    proc_w, proc_h = orig_w, orig_h
    if process_cap and max(orig_w, orig_h) > process_cap:
        ratio = process_cap / float(max(orig_w, orig_h))
        proc_w, proc_h = max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))
        proc_img = source.resize((proc_w, proc_h), Image.Resampling.LANCZOS)
    else:
        proc_img = source

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="v83-zwash-") as tmpd:
        proc_png = Path(tmpd) / "proc.png"
        proc_img.save(proc_png, format="PNG")
        filename = cc.upload_image(str(proc_png))

        seed_value = seed if seed is not None else int(time.time() * 1000) % (2**32)

        # Inline graph: LoadImage -> VAEEncodeTiled (Z-Image VAE) ->
        # KSampler (z_image_turbo, res_2s/bong_tangent, low denoise) ->
        # VAEDecode -> SaveImage. Mirrors the face-detailer recipe exactly.
        graph = {
            "1": {"class_type": "LoadImage", "inputs": {"image": filename}},
            "2": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": MODEL_VAE},
            },
            "3": {
                "class_type": "VAEEncodeTiled",
                "inputs": {
                    "pixels": ["1", 0],
                    "vae": ["2", 0],
                    "tile_size": 512,
                    "overlap": 64,
                    "temporal_size": 64,
                    "temporal_overlap": 8,
                },
            },
            "4": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": MODEL_UNET},
            },
            "5": {
                "class_type": "CLIPLoaderGGUF",
                "inputs": {"clip_name": MODEL_CLIP, "type": "lumina2"},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "", "clip": ["5", 0]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "blurry, ugly, bad quality,", "clip": ["5", 0]},
            },
            "8": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed_value,
                    "steps": 8,
                    "cfg": 1,
                    "sampler_name": "res_2s",
                    "scheduler": "bong_tangent",
                    "denoise": denoise,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["3", 0],
                },
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["8", 0], "vae": ["2", 0]},
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "V83Wash", "images": ["9", 0]},
            },
        }

        prompt_id = cc.post_prompt(graph)
        entry = cc.wait_for_prompt(prompt_id, timeout=timeout)
        out_bytes = cc.get_output_image(entry)

        cleaned = Image.open(io.BytesIO(out_bytes)).convert("RGB")
        if (cleaned.width, cleaned.height) != (orig_w, orig_h):
            cleaned = cleaned.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
        cleaned.save(output_path, format="PNG")

    return {
        "applied": True,
        "method": "comfyui_zimage_full_frame_img2img",
        "model": MODEL_UNET,
        "clip": MODEL_CLIP,
        "vae": MODEL_VAE,
        "denoise": denoise,
        "seed": seed_value,
        "process_resolution": [proc_w, proc_h],
        "output_resolution": [orig_w, orig_h],
        "single_vae_pass": True,
        "runtime_ms": int((time.time() - started) * 1000),
    }
