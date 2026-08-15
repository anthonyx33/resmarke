#!/usr/bin/env python3
"""CPU-safe build-time gates for the DeepClean worker image.

These run inside `docker build` on a GPU-less CI runner, so nothing here may
import `comfy_kitchen` — directly or transitively. comfy_kitchen eagerly
imports its Triton backend, and Triton instantiates a GPU driver at import
time, which raises `RuntimeError: 0 active drivers ([])` where no GPU exists.
ComfyUI is in the same bucket: comfy/ldm/modules/attention.py imports
comfy_kitchen at module level, so booting ComfyUI on a CI runner fails for the
same reason. Those checks live in runtime_self_check.py, which start.sh runs
against the live GPU before the worker accepts a job.

What this gate still proves, without a GPU:

  1. The base image really is torch 2.7.1 / CUDA 12.6.
  2. torch's `infer_schema` accepts the exact annotation shapes that torch
     2.5.1 rejected. This is the actual root cause of the outage, tested
     directly rather than inferred from a successful comfy_kitchen import.
  3. comfy-kitchen resolves to the pinned version (metadata read, no import).
  4. The engine module — pure numpy/PIL — imports cleanly.
"""

import importlib.metadata as metadata
import os
import re
import sys

EXPECTED_TORCH = "2.7.1"
EXPECTED_CUDA = "12.6"
EXPECTED_COMFY_KITCHEN = "0.2.31"

# The signature comfy_kitchen's na.py registers via @torch.library.custom_op.
# torch 2.5.1's infer_schema rejects both `list[int]` and `float | None` here;
# 2.7.1 accepts them. This exact string is the owner-verified expectation.
EXPECTED_NA3D_SCHEMA = (
    "(Tensor q, Tensor k, Tensor v, SymInt[] kernel_size, "
    "bool[] is_causal, float? scale) -> Tensor"
)


def _normalize_schema(schema):
    """Collapse whitespace and strip default values from a torch schema string."""
    return re.sub(r"=[^,)]+", "", " ".join(schema.split()))


def check_versions():
    import torch

    if not torch.__version__.startswith(EXPECTED_TORCH):
        raise SystemExit(f"FAIL: torch is {torch.__version__}, expected {EXPECTED_TORCH}.x")
    if torch.version.cuda != EXPECTED_CUDA:
        raise SystemExit(f"FAIL: torch CUDA runtime is {torch.version.cuda}, expected {EXPECTED_CUDA}")

    print(f"OK: torch {torch.__version__}, CUDA runtime {torch.version.cuda}")


def check_custom_op_schema():
    """Reproduce the na3d custom-op registration that broke under torch 2.5.1.

    Registering the op is the real regression test: @torch.library.custom_op
    calls infer_schema internally, which is precisely where 2.5.1 raised.
    """
    import torch

    @torch.library.custom_op("deepclean_build_gate::na3d", mutates_args=())
    def na3d(
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        kernel_size: list[int],
        is_causal: list[bool],
        scale: float | None = None,
    ) -> torch.Tensor:
        return q

    print("OK: @torch.library.custom_op accepted list[int] / list[bool] / float | None")

    # Evidence: print the inferred schema and hold it to the owner-verified
    # string. infer_schema is private, so a lookup failure is reported rather
    # than treated as a gate failure — the registration above is the real test.
    try:
        from torch._library.infer_schema import infer_schema
    except ImportError as exc:
        print(f"WARN: could not import infer_schema for schema evidence ({exc})")
        return

    def na3d_proto(
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        kernel_size: list[int],
        is_causal: list[bool],
        scale: float | None = None,
    ) -> torch.Tensor:
        return q

    schema = infer_schema(na3d_proto, mutates_args=())
    print(f"inferred na3d schema: {schema}")

    # Compare inferred TYPES, which is what torch 2.5.1 got wrong. Normalizing
    # away whitespace and default values (`float? scale=None` -> `float? scale`,
    # which is how the owners transcribed it) keeps a cosmetic difference from
    # failing the build, while a genuinely different type — `float` instead of
    # `float?`, or `int[]` instead of `SymInt[]` — still does.
    if _normalize_schema(schema) != _normalize_schema(EXPECTED_NA3D_SCHEMA):
        raise SystemExit(
            "FAIL: inferred na3d schema does not match the owner-verified signature.\n"
            f"  expected: {EXPECTED_NA3D_SCHEMA}\n"
            f"  actual:   {schema}"
        )
    print("OK: na3d schema matches the owner-verified signature")


def check_c_toolchain():
    """Prove Triton can JIT-compile its CUDA driver shim at runtime.

    Triton's NVIDIA backend compiles driver.c into a Python C extension the
    first time it is imported. On a `-runtime` base image with no compiler that
    raises "Failed to find C compiler" and ComfyUI never boots — and it only
    shows up on a GPU host, because a CPU-only runner bails out earlier at
    driver discovery. So compile the same shape of thing here: a C file that
    includes Python.h, built into a shared object with the interpreter's own
    include paths. That catches a missing compiler and missing Python headers
    at build time instead of on RunPod.
    """
    import shutil
    import subprocess
    import sysconfig
    import tempfile
    from pathlib import Path

    cc = os.environ.get("CC") or "gcc"
    resolved = shutil.which(cc)
    if not resolved:
        raise SystemExit(f"FAIL: C compiler {cc!r} not found on PATH")
    print(f"OK: C compiler {cc} -> {resolved}")

    include_dir = sysconfig.get_paths()["include"]
    header = Path(include_dir) / "Python.h"
    if not header.is_file():
        raise SystemExit(
            f"FAIL: Python.h not found at {header}. Triton compiles a Python C "
            "extension at import time and will fail without it; install the "
            "interpreter's development headers in the image."
        )
    print(f"OK: Python.h present at {header}")

    source = "#include <Python.h>\nint probe(void) { return 0; }\n"
    with tempfile.TemporaryDirectory() as tmp:
        c_path = Path(tmp) / "probe.c"
        so_path = Path(tmp) / "probe.so"
        c_path.write_text(source, encoding="utf-8")
        command = [
            cc, "-shared", "-fPIC",
            "-I", include_dir,
            str(c_path), "-o", str(so_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0 or not so_path.exists():
            raise SystemExit(
                "FAIL: could not compile a Python C extension — Triton will fail "
                "the same way at runtime.\n"
                f"  command: {' '.join(command)}\n"
                f"  stderr:  {result.stderr.strip()}"
            )
    print("OK: compiled a Python C extension (Python.h + linker reachable)")

    # Triton ships its own cuda.h, so a -runtime base needs no CUDA headers.
    # Confirm that assumption rather than discovering it on RunPod.
    roots = [Path(p) / "triton" / "backends" / "nvidia" / "include" / "cuda.h"
             for p in sys.path if p]
    found = next((p for p in roots if p.is_file()), None)
    if found is None:
        print("WARN: triton's bundled cuda.h not found; runtime JIT may need CUDA headers")
    else:
        print(f"OK: triton bundles cuda.h at {found}")


def check_comfy_kitchen_version():
    """Read comfy-kitchen's version from installed metadata WITHOUT importing it."""
    version = metadata.version("comfy-kitchen")
    print(f"comfy-kitchen (metadata, not imported): {version}")
    if version != EXPECTED_COMFY_KITCHEN:
        raise SystemExit(
            f"FAIL: comfy-kitchen is {version}, expected {EXPECTED_COMFY_KITCHEN}"
        )
    print(f"OK: comfy-kitchen pinned at {version}")


def check_engine_imports():
    """The v6 + v7 engines are pure numpy/PIL; ComfyUI is imported lazily."""
    import ds_remint_v6

    for attr in ("apply_ds_remint_v6", "is_ds_remint_v6", "normalize_ds_remint_v6_settings"):
        if not hasattr(ds_remint_v6, attr):
            raise SystemExit(f"FAIL: ds_remint_v6 is missing {attr}")
    print("OK: ds_remint_v6 imports cleanly with its public entry points")

    import ds_remint_v7

    for attr in ("apply_ds_remint_v7", "is_ds_remint_v7", "normalize_ds_remint_v7_settings"):
        if not hasattr(ds_remint_v7, attr):
            raise SystemExit(f"FAIL: ds_remint_v7 is missing {attr}")
    print("OK: ds_remint_v7 imports cleanly with its public entry points")

    import ds_remint_v8_8

    for attr in ("apply_ds_remint_v8_8", "is_ds_remint_v8_8", "normalize_ds_remint_v8_8_settings"):
        if not hasattr(ds_remint_v8_8, attr):
            raise SystemExit(f"FAIL: ds_remint_v8_8 is missing {attr}")
    print("OK: ds_remint_v8_8 imports cleanly with its public entry points")


def check_camera_relife_functional():
    """Run the camera re-life stack on a tiny synthetic frame (CPU-safe).

    Proves the numpy/PIL acquisition pipeline executes, not just imports."""
    import numpy as np
    from PIL import Image

    from camera_relife import apply_camera_relife

    height, width = 96, 128
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    frame = np.zeros((height, width, 3), dtype=np.float32)
    frame[..., 0] = xx / width
    frame[..., 1] = yy / height
    frame[..., 2] = 0.5 + 0.5 * np.sin(xx / 7.0)
    image = Image.fromarray(np.clip(frame * 255, 0, 255).astype(np.uint8))

    relifed, report = apply_camera_relife(
        image,
        settings={"mode": "camera-relife", "camera_relife": {"preset": "balanced"}},
        creator_id="build-gate",
        seed_extra="build",
    )
    if not report.get("applied") or relifed.size != image.size:
        raise SystemExit("FAIL: camera_relife did not produce a same-size output")
    print("OK: camera_relife applied the full balanced stack on a synthetic frame")


def main():
    print(f"--- build gate (CPU-safe) on python {sys.version.split()[0]} ---")
    check_versions()
    check_custom_op_schema()
    check_c_toolchain()
    check_comfy_kitchen_version()
    check_engine_imports()
    check_camera_relife_functional()
    print("OK: all CPU-safe build gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
