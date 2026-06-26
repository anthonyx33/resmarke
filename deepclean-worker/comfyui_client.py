"""Thin client for the localhost ComfyUI service.

The Remarkee Max engine is ComfyUI running the Remarkee Max workflow. This
module talks to ComfyUI's HTTP API (http://127.0.0.1:8188 by default):

    upload_image(path) -> filename        POST /upload/image
    load_template(path) -> graph          read API-format workflow JSON
    set_loadimage(graph, filename)        mutate the LoadImage node
    set_seed(graph, seed)                 mutate every node with a `seed` input
    post_prompt(graph) -> prompt_id       POST /prompt
    wait_for_prompt(prompt_id, timeout)   poll GET /history/{id}
    get_output_image(prompt_id) -> bytes  GET /view

The workflow template is the **API format** (flat {node_id: {class_type, inputs}}),
exported once from ComfyUI's UI via "Save (API Format)" — see
workflows/EXPORT.md. We only mutate fields with stable, well-known API input
names (LoadImage.image, KSampler.seed); the workflow's own AdaptiveDenoise node
continues to drive per-resolution denoise untouched.
"""
import json
import os
import time
import uuid
from pathlib import Path

import requests

COMFY_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
HTTP_TIMEOUT = 60


def _client_id() -> str:
    return "deepclean-" + uuid.uuid4().hex


def upload_image(path) -> str:
    """Upload an input image to ComfyUI's input folder. Returns the filename
    ComfyUI stores it under (suitable for LoadImage.inputs.image)."""
    path = Path(path)
    with path.open("rb") as fh:
        resp = requests.post(
            f"{COMFY_URL}/upload/image",
            files={"image": (path.name, fh, "image/png")},
            data={"overwrite": "true"},
            timeout=HTTP_TIMEOUT,
        )
    resp.raise_for_status()
    data = resp.json()
    # {"name": <filename>, "subfolder": "", "type": "input"}
    name = data.get("name") or path.name
    sub = data.get("subfolder")
    return f"{sub}/{name}" if sub else name


def load_template(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _find_nodes_by_class(graph: dict, class_type: str):
    """Yield (node_id, node_dict) for every node of the given class_type."""
    for node_id, node in graph.items():
        if isinstance(node, dict) and node.get("class_type") == class_type:
            yield node_id, node


def set_loadimage(graph: dict, filename: str) -> int:
    """Point every LoadImage node at the uploaded filename."""
    count = 0
    for _, node in _find_nodes_by_class(graph, "LoadImage"):
        node.setdefault("inputs", {})
        node["inputs"]["image"] = filename
        count += 1
    if count == 0:
        raise RuntimeError("Workflow template has no LoadImage node to bind the input to.")
    return count


def set_seed(graph: dict, seed: int) -> int:
    """Set the seed on every node that exposes a `seed` input (KSampler,
    SEGSDetailerModelSwap, etc.) for deterministic output.

    Also flips `control_after_generate` to 'fixed' on those nodes — the v2
    workflow ships KSampler with control_after_generate='randomize', which in
    API format is a separate input that would otherwise overwrite our seed."""
    count = 0
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, dict) and "seed" in inputs:
            inputs["seed"] = int(seed)
            if "control_after_generate" in inputs:
                inputs["control_after_generate"] = "fixed"
            count += 1
    return count


def post_prompt(graph: dict) -> str:
    payload = {"prompt": graph, "client_id": _client_id()}
    resp = requests.post(f"{COMFY_URL}/prompt", json=payload, timeout=HTTP_TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"ComfyUI /prompt rejected the graph: {resp.status_code} {resp.text[:500]}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"ComfyUI /prompt error: {data['error']}")
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI /prompt returned no prompt_id: {data}")
    return prompt_id


def wait_for_prompt(prompt_id: str, timeout: float) -> dict:
    """Poll /history until the run finishes or timeout. Returns the history
    entry. Raises on execution error or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        history = resp.json()
        entry = history.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            status_str = status.get("status_str", "")
            if status_str == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"ComfyUI execution error: {msgs}")
            # status_str == 'success' or 'interrupted'
            return entry
        time.sleep(1.0)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} did not finish within {timeout:.0f}s")


def get_output_image(entry: dict) -> bytes:
    """Find the SaveImage (or any output) image bytes from a finished history
    entry."""
    outputs = entry.get("outputs", {})
    for _node_id, out in outputs.items():
        images = out.get("images") or []
        for img in images:
            if img.get("type") == "output":
                filename = img["filename"]
                subfolder = img.get("subfolder", "")
                folder_type = img.get("type", "output")
                resp = requests.get(
                    f"{COMFY_URL}/view",
                    params={"filename": filename, "subfolder": subfolder, "type": folder_type},
                    timeout=HTTP_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.content
    raise RuntimeError("ComfyUI run produced no output image.")


def system_stats() -> dict:
    resp = requests.get(f"{COMFY_URL}/system_stats", timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()
