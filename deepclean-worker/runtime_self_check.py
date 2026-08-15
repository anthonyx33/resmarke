#!/usr/bin/env python3
"""GPU-side self-check, run once at container start before the worker accepts jobs.

These are the gates that cannot run during `docker build`: they need a live
CUDA driver, which GitHub Actions runners do not have. Running them here — on
RunPod, after start.sh has ComfyUI up but before the serverless handler is
exec'd — means a broken image fails its warmup loudly instead of failing every
job silently.

This deliberately reuses the ComfyUI instance start.sh already launched rather
than booting a second one, so the added cold-start cost is one localhost
request plus the comfy_kitchen import.

Checks:
  1. comfy_kitchen imports and reports an available eager backend (this is the
     import that crashed under torch 2.5.1 and took production down).
  2. Every class_type in the deployed workflow is registered in /object_info.
  3. `res_2s` is offered as a KSampler sampler_name choice.

Set DEEPCLEAN_SKIP_SELFCHECK=1 to bypass — an escape hatch for the case where
the check itself misfires in production, not a routine setting.
"""

import json
import os
import sys
import urllib.error
import urllib.request

from smoke_test import load_workflow_class_types, sampler_choices

HOST = os.environ.get("COMFYUI_SELFCHECK_HOST", "127.0.0.1")
PORT = os.environ.get("COMFYUI_PORT", "8188")
OBJECT_INFO_URL = f"http://{HOST}:{PORT}/object_info"
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("DEEPCLEAN_SELFCHECK_TIMEOUT", "60"))


def check_comfy_kitchen():
    """Import comfy_kitchen and require a usable eager backend.

    On a GPU-less host this raises `RuntimeError: 0 active drivers` from
    Triton's import-time driver init — which is exactly why this check cannot
    live in the Dockerfile.
    """
    import importlib.metadata as metadata

    import comfy_kitchen

    version = metadata.version("comfy-kitchen")
    backends = comfy_kitchen.list_backends()
    print(f"comfy-kitchen: {version}")
    print(f"comfy-kitchen backends: {json.dumps(backends, sort_keys=True)}")

    if backends.get("eager", {}).get("available") is not True:
        raise RuntimeError(f"comfy_kitchen eager backend is not available: {backends}")
    print("OK: comfy_kitchen imported with an available eager backend")


def fetch_object_info():
    request = urllib.request.Request(OBJECT_INFO_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise RuntimeError(
            f"could not read {OBJECT_INFO_URL} from the running ComfyUI: {exc!r}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError("/object_info did not return a JSON object")
    return payload


def check_workflow_surface(object_info):
    class_types = load_workflow_class_types()
    missing = sorted(class_types - set(object_info))
    if missing:
        raise RuntimeError(
            "workflow class_type values missing from /object_info: " + ", ".join(missing)
        )
    print(f"OK: /object_info registered all {len(class_types)} workflow class types")

    choices = sampler_choices(object_info)
    if "res_2s" not in choices:
        raise RuntimeError("res_2s is missing from KSampler sampler_name choices")
    print("OK: KSampler sampler_name choices include res_2s")


def main():
    if os.environ.get("DEEPCLEAN_SKIP_SELFCHECK") == "1":
        print("[deepclean:selfcheck] SKIPPED via DEEPCLEAN_SKIP_SELFCHECK=1")
        return 0

    print("--- deepclean runtime self-check (GPU side) ---")
    try:
        check_comfy_kitchen()
        check_workflow_surface(fetch_object_info())
    except Exception as exc:  # noqa: BLE001 - surface any failure as a fatal gate
        print(f"[deepclean:selfcheck] FATAL: {exc}", file=sys.stderr)
        return 1

    print("OK: runtime self-check passed; worker may accept jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
