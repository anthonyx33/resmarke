#!/usr/bin/env python3
"""Boot ComfyUI on CPU and validate the deployed API workflow surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import IO, Any


APP_ROOT = Path(__file__).resolve().parent
COMFYUI_ROOT = APP_ROOT / "ComfyUI"
WORKFLOW_PATH = APP_ROOT / "workflows" / "remarkee-max-v2.api.json"
HOST = "127.0.0.1"
PORT = 8199
OBJECT_INFO_URL = f"http://{HOST}:{PORT}/object_info"
STARTUP_TIMEOUT_SECONDS = 240


def load_workflow_class_types() -> set[str]:
    graph = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    if not isinstance(graph, dict):
        raise RuntimeError(f"Workflow top level is not an object: {WORKFLOW_PATH}")

    class_types: set[str] = set()
    for node_id, node in graph.items():
        if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
            raise RuntimeError(f"Workflow node {node_id!r} has no string class_type")
        class_types.add(node["class_type"])
    return class_types


def wait_for_object_info(process: subprocess.Popen[Any]) -> dict[str, Any]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error: BaseException | None = None

    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"ComfyUI exited with status {return_code} before /object_info was ready"
            )

        try:
            request = urllib.request.Request(
                OBJECT_INFO_URL,
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise RuntimeError("/object_info did not return a JSON object")
            return payload
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(2)

    raise RuntimeError(
        f"Timed out after {STARTUP_TIMEOUT_SECONDS}s waiting for {OBJECT_INFO_URL}; "
        f"last error: {last_error!r}"
    )


def sampler_choices(object_info: dict[str, Any]) -> list[str]:
    try:
        field = object_info["KSampler"]["input"]["required"]["sampler_name"]
        choices = field[0]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "KSampler.input.required.sampler_name is missing from /object_info"
        ) from exc

    if not isinstance(choices, list) or not all(isinstance(item, str) for item in choices):
        raise RuntimeError("KSampler sampler_name choices are not a list of strings")
    return choices


def stop_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def print_log_tail(log_file: IO[str], lines: int = 200) -> None:
    log_file.flush()
    log_file.seek(0)
    tail = log_file.readlines()[-lines:]
    print("--- ComfyUI smoke-test log (tail) ---", file=sys.stderr)
    sys.stderr.writelines(tail)
    print("--- end ComfyUI smoke-test log ---", file=sys.stderr)


def main() -> int:
    class_types = load_workflow_class_types()
    command = [
        sys.executable,
        "main.py",
        "--cpu",
        "--listen",
        HOST,
        "--port",
        str(PORT),
        "--preview-method",
        "none",
        "--disable-metadata",
    ]

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=COMFYUI_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            object_info = wait_for_object_info(process)
            missing = sorted(class_types - set(object_info))
            if missing:
                raise RuntimeError(
                    "Workflow class_type values missing from /object_info: "
                    + ", ".join(missing)
                )

            choices = sampler_choices(object_info)
            if "res_2s" not in choices:
                raise RuntimeError("res_2s is missing from KSampler sampler_name choices")

            print(f"OK: /object_info registered all {len(class_types)} workflow class types")
            print("OK: KSampler sampler_name choices include res_2s")
        except BaseException:
            stop_process(process)
            print_log_tail(log_file)
            raise
        else:
            stop_process(process)

    print("OK: ComfyUI smoke-test process stopped cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
