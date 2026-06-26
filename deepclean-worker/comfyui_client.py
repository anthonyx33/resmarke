"""Thin client for the localhost ComfyUI service.

The Remarkee Max engine is ComfyUI running the Remarkee Max workflow. This
module talks to ComfyUI's HTTP API (http://127.0.0.1:8188 by default):

    upload_image(path) -> filename        POST /upload/image
    load_template(path) -> graph          read API-format workflow JSON
    set_loadimage(graph, filename)        mutate the LoadImage node
    set_seed(graph, seed)                 mutate every node with a `seed` input
    set_adaptive_level(graph, level)      mutate RemarkeeMax-AdaptiveDenoise
    bypass_face_path(graph)               prune face-only nodes for standard
    post_prompt(graph) -> prompt_id       POST /prompt
    wait_for_prompt(prompt_id, timeout)   poll GET /history/{id}
    get_output_image(prompt_id) -> bytes  GET /view

The workflow template is the **API format** (flat {node_id: {class_type, inputs}}),
exported once from ComfyUI's UI via "Save (API Format)" — see
workflows/EXPORT.md. We only mutate fields with stable, well-known API input
names (LoadImage.image, seed, adaptive_level, SaveImage.images).
"""
import copy
import json
import os
import time
import uuid
from collections import Counter
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


def _node_sort_key(node_id: str):
    try:
        return (0, int(node_id))
    except (TypeError, ValueError):
        return (1, str(node_id))


def _looks_like_node_link(value) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _is_node_link(value, graph: dict) -> bool:
    return _looks_like_node_link(value) and value[0] in graph


def _iter_node_links(value):
    if _looks_like_node_link(value):
        yield value[0]
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_node_links(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_node_links(child)


def _dependency_closure(graph: dict, root_id: str) -> set[str]:
    seen = set()
    stack = [root_id]
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        if node_id not in graph:
            raise RuntimeError(f"Workflow references missing node {node_id!r}.")
        seen.add(node_id)
        node = graph[node_id]
        stack.extend(_iter_node_links(node.get("inputs", {})))
    return seen


def _single_node_by_class(graph: dict, class_type: str):
    matches = list(_find_nodes_by_class(graph, class_type))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {class_type} node, found {len(matches)}.")
    return matches[0]


def _assert_no_dangling_refs(graph: dict) -> None:
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            continue
        for dep_id in _iter_node_links(node.get("inputs", {})):
            if dep_id not in graph:
                raise RuntimeError(f"Node {node_id} references missing node {dep_id}.")


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


def set_adaptive_level(graph: dict, level: int) -> int:
    """Set Remarkee Max's global adaptive denoise level."""
    count = 0
    for _, node in _find_nodes_by_class(graph, "RemarkeeMax-AdaptiveDenoise"):
        inputs = node.setdefault("inputs", {})
        if "adaptive_level" in inputs:
            inputs["adaptive_level"] = int(level)
            count += 1
    if count == 0:
        raise RuntimeError("Workflow template has no RemarkeeMax-AdaptiveDenoise.adaptive_level input.")
    return count


def bypass_face_path(graph: dict) -> dict:
    """Prune the Z-Image face path for standard jobs.

    The API export includes non-SaveImage output nodes, so deleting only the
    SEGSPaste chain can leave dangling references. This rewires SaveImage to
    the global Qwen output, then keeps only nodes reachable from SaveImage.
    If discovery fails, the original graph is left untouched.
    """
    try:
        candidate = copy.deepcopy(graph)
        before_count = len(candidate)

        save_id, save_node = _single_node_by_class(candidate, "SaveImage")
        save_inputs = save_node.setdefault("inputs", {})
        save_images = save_inputs.get("images")
        if not _is_node_link(save_images, candidate):
            raise RuntimeError("SaveImage.images is not a node link.")

        paste_id = save_images[0]
        paste_node = candidate[paste_id]
        if paste_node.get("class_type") != "SEGSPaste":
            raise RuntimeError(f"SaveImage does not point at SEGSPaste; found {paste_node.get('class_type')}.")

        base_link = paste_node.get("inputs", {}).get("image")
        if not _is_node_link(base_link, candidate):
            raise RuntimeError("SEGSPaste.image is not a node link.")

        save_inputs["images"] = list(base_link)
        keep = _dependency_closure(candidate, save_id)
        removed_ids = [node_id for node_id in list(candidate) if node_id not in keep]
        removed_classes = Counter(candidate[node_id].get("class_type", "unknown") for node_id in removed_ids)
        for node_id in removed_ids:
            del candidate[node_id]

        _assert_no_dangling_refs(candidate)
    except Exception as exc:  # noqa: BLE001
        return {
            "applied": False,
            "reason": str(exc),
            "nodes_before": len(graph),
            "nodes_after": len(graph),
            "removed_nodes": 0,
        }

    graph.clear()
    graph.update(candidate)
    return {
        "applied": True,
        "save_node": save_id,
        "base_node": base_link[0],
        "nodes_before": before_count,
        "nodes_after": len(graph),
        "removed_nodes": len(removed_ids),
        "removed_class_counts": dict(sorted(removed_classes.items())),
        "removed_node_ids": sorted(removed_ids, key=_node_sort_key),
    }


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
