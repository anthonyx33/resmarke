#!/usr/bin/env python3
"""Validate the Remarkee Max ComfyUI API-format workflow.

This intentionally checks format and critical nodes only. It does not execute
the workflow; that happens in RunPod warmup after the image is rebuilt.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_PATH = ROOT / "remarkee-max-v2.api.json"

REQUIRED_CLASSES = {
    "LoadImage",
    "KSampler",
    "UnetLoaderGGUF",
    "CLIPLoaderGGUF",
    "VAELoader",
    "ModelPatchLoader",
    "QwenImageDiffsynthControlnet",
    "RemarkeeMax-AdaptiveDenoise",
    "Canny",
    "Get Image Size",
    "BboxDetectorCombined_v2",
    "MaskToSEGS",
    "ImpactSEGSToMaskBatch",
    "SAMLoader",
    "MediaPipe-FaceMeshPreprocessor",
    "MediaPipeFaceMeshToSEGS",
    "ImpactSimpleDetectorSEGS",
    "SEGSDetailerModelSwap",
    "SEGSPaste",
    "InpaintCropImproved",
    "ImageResizeKJv2",
    "Image Comparer (rgthree)",
    "Power Lora Loader (rgthree)",
    "UltralyticsDetectorProvider",
    "SaveImage",
}

REQUIRED_MODEL_STRINGS = {
    "qwen-image-2512-Q4_K_M.gguf",
    "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf",
    "qwen_image_vae.safetensors",
    "qwen_image_canny_diffsynth_controlnet.safetensors",
    "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
    "z_image_turbo-Q4_K_M.gguf",
    "Qwen_3_4b-imatrix-IQ4_XS.gguf",
    "ae.safetensors",
    "yolov8n-face.pt",
    "sam_vit_b_01ec64.pth",
}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    errors: list[str] = []

    if not path.exists():
        print(f"ERROR: missing {path}")
        print("Export it from ComfyUI using Save (API Format).")
        return 1

    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: {path} is not valid JSON: {exc}")
        return 1

    if not isinstance(graph, dict):
        errors.append("Top-level JSON must be an object.")
    else:
        if "nodes" in graph or "links" in graph or "groups" in graph:
            errors.append(
                "This is still editor format. API format must not have top-level "
                "'nodes', 'links', or 'groups'."
            )

        classes = Counter()
        model_strings = set()
        seed_nodes = 0
        load_image_nodes = 0

        for node_id, node in graph.items():
            if not isinstance(node, dict):
                errors.append(f"Node {node_id!r} is not an object.")
                continue

            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(class_type, str):
                errors.append(f"Node {node_id!r} is missing string class_type.")
                continue
            if not isinstance(inputs, dict):
                errors.append(f"Node {node_id!r} ({class_type}) is missing inputs object.")
                continue

            classes[class_type] += 1
            if class_type == "LoadImage":
                load_image_nodes += 1
                if "image" not in inputs:
                    errors.append(f"LoadImage node {node_id!r} has no inputs.image.")
            if "seed" in inputs:
                seed_nodes += 1
            collect_strings(inputs, model_strings)

        missing_classes = sorted(REQUIRED_CLASSES - set(classes))
        if missing_classes:
            errors.append("Missing required class_type values: " + ", ".join(missing_classes))

        missing_models = sorted(
            required
            for required in REQUIRED_MODEL_STRINGS
            if not any(required in found for found in model_strings)
        )
        if missing_models:
            errors.append("Missing expected model references: " + ", ".join(missing_models))

        if load_image_nodes != 1:
            errors.append(f"Expected exactly one LoadImage node, found {load_image_nodes}.")
        if seed_nodes == 0:
            errors.append("No node exposes a seed input; deterministic seed override will do nothing.")

    if errors:
        print(f"ERROR: {path} is not a valid Remarkee Max API workflow.")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OK: {path} is ComfyUI API format.")
    print(f"Nodes: {len(graph)}")
    print("Key class counts:")
    for class_type in sorted(REQUIRED_CLASSES):
        print(f"- {class_type}: {classes[class_type]}")
    return 0


def collect_strings(value: Any, output: set[str]) -> None:
    if isinstance(value, str):
        output.add(value)
    elif isinstance(value, list):
        for item in value:
            collect_strings(item, output)
    elif isinstance(value, dict):
        for item in value.values():
            collect_strings(item, output)


if __name__ == "__main__":
    raise SystemExit(main())
