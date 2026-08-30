#!/usr/bin/env python3
"""Offline-only 4D-AR1 A0-A6 factorial harness.

This file implements section 5 of C8_MASTER_PROMPT_4D_AR1_MASTER_FREEZE.md.
It has no network client, detector, grader, deployment, or production imports.
The operator runs all seven frozen arms together; individual-arm execution is
intentionally not exposed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

import numpy as np
import PIL
from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
INPUT_DIR = ROOT / "round-4d-1a"
CHECKPOINTS = INPUT_DIR / "checkpoints"
MANIFEST_PATH = INPUT_DIR / "expected-manifest.json"
SETTINGS_PATH = INPUT_DIR / "cell-settings.json"
ROI_PATH = ROOT / "round-4d-cam-1" / "roi-manifest.json"
OUT = ROOT / "round-4d-ar1"
WORK_OUT = ROOT / "round-4d-ar1.in-progress"
REPORT_PATH = ROOT / "C8_4D_AR1_REPORT.md"
WORK_REPORT_PATH = ROOT / "C8_4D_AR1_REPORT.md.in-progress"

PYTHON_VERSION = "3.9.6"
NUMPY_VERSION = "2.0.2"
PILLOW_VERSION = "11.3.0"
TONE_LOCK_STRENGTH = 0.8
STAGE1_QUALITY = 92
STAGE1_SUBSAMPLING = "4:2:0"
FINAL_QUALITY = 97
FINAL_SUBSAMPLING = "4:4:4"
DELIVERY_EDGES = frozenset({800, 1080, 1250})
SIX_IMAGES = ("IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11")
SEEDS = ("lab-ctla1", "lab-ctla2")
REQUIRED_INPUTS = (
    "O0_source.png",
    "O1_postwash.png",
    "OR_postresample.png",
    "O2_precamera.png",
    "O5_final.png",
)

# These are identities of the authority, frozen transformation/metric modules,
# and frozen input manifests at implementation time. They are checked before
# any of the transformation modules are imported.
FROZEN_FILE_PINS = {
    "C8_MASTER_PROMPT_4D_AR1_MASTER_FREEZE.md": "41758ffbd3b4fbc8ff5ee97b5d7c8ec336a26e5c3465960c0d9e04098472a2e8",
    "deepclean-worker/max_cx_remint.py": "b00a084d947dc449baf78a3e36c94ce2d801cc3600b45e89b30a015151d9ab85",
    "deepclean-worker/quality_finish.py": "538c9edb3bdc7c0ebe7e8faf16b37a76d6d0c29b107a1914168bed8e4f587175",
    "deepclean-worker/tools/checkpoint_capture.py": "d9f0557bf713cd826ce6d6e4ba4111fee09d83b37fa82fe2b5c974c74bebab03",
    "deepclean-worker/tools/transfer_4d_1b.py": "2e5a281f6e46f8785694eccced0c98cb60e41e9d8ed2eea0f89bfc932bb5a5ab",
    "deepclean-worker/tools/checkpoint_attribution.py": "335d8967560a60f32c5732fde63258d9919520fd7006d8d74c1ffa46eef53a44",
    "round-4d-1a/cell-settings.json": "17691de31256b5a5f6db99bc0b94560606556e10b40a04fbb805340dffa439f6",
    "round-4d-1a/expected-manifest.json": "6d1c730c629fda80b04b742bc75423f2f4710802a6cabc330910aaff7739c76a",
    "round-4d-cam-1/roi-manifest.json": "5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329",
}


class FreezeViolation(RuntimeError):
    """A frozen prerequisite or output contract did not hold."""


@dataclass(frozen=True)
class Arm:
    name: str
    label: str
    camera: bool
    intermediate_jpeg: bool
    quality_finish: bool
    preservation: bool
    composition: str


ARMS = (
    Arm("A0", "incumbent replay", True, True, True, False, "O2 -> tone-lock -> q92 -> QF -> q97"),
    Arm("A1", "camera-off", False, True, True, False, "OR -> tone-lock -> q92 -> QF -> q97"),
    Arm("A2", "codec bypass", True, False, True, False, "O2 -> tone-lock -> QF(buffer) -> q97"),
    Arm("A3", "camera-off + bypass", False, False, True, False, "OR -> tone-lock -> QF(buffer) -> q97"),
    Arm(
        "A4",
        "4D-1b preservation",
        True,
        True,
        True,
        True,
        "build_candidate(OR,O2) -> tone-lock -> q92 -> QF -> q97",
    ),
    Arm("A5", "QF-off", True, True, False, False, "O2 -> tone-lock -> q92 -> q97"),
    Arm("A6", "QF-off + camera-off", False, True, False, False, "OR -> tone-lock -> q92 -> q97"),
)


@dataclass(frozen=True)
class FrozenFunctions:
    histogram_match: Callable[..., Image.Image]
    quality_finish: Callable[..., dict]
    build_candidate: Callable[..., Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pixel_sha256(path: Path) -> str:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        digest = hashlib.sha256()
        digest.update(rgb.width.to_bytes(8, "big"))
        digest.update(rgb.height.to_bytes(8, "big"))
        digest.update(rgb.tobytes())
        return digest.hexdigest()


def _array_pixel_sha256(rgb: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(rgb, dtype=np.uint8)[..., :3])
    height, width = array.shape[:2]
    digest = hashlib.sha256()
    digest.update(width.to_bytes(8, "big"))
    digest.update(height.to_bytes(8, "big"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise FreezeViolation(f"non-finite value cannot enter an artifact: {value}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_text(payload, encoding="utf-8")


def _jpeg_info(path: Path) -> dict:
    """Read JPEG dimensions and SOF sampling factors without guessing."""
    data = path.read_bytes()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise FreezeViolation(f"not a JPEG: {path}")
    index = 2
    while index < len(data) - 12:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            components = data[index + 9]
            samples = [data[index + 11 + offset * 3] for offset in range(min(components, 3))]
            is_444 = components >= 3 and all(sample == 0x11 for sample in samples)
            is_420 = components >= 3 and samples[:3] == [0x22, 0x11, 0x11]
            sampling = "4:4:4" if is_444 else ("4:2:0" if is_420 else "other")
            return {
                "width": width,
                "height": height,
                "sampling": sampling,
                "sampling_bytes": [hex(sample) for sample in samples],
            }
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        if index + 4 > len(data):
            break
        length = int.from_bytes(data[index + 2 : index + 4], "big")
        if length < 2:
            break
        index += 2 + length
    raise FreezeViolation(f"JPEG SOF marker not found: {path}")


def _has_exif(path: Path) -> bool:
    with Image.open(path) as image:
        return bool(image.info.get("exif")) or bool(image.getexif())


def _image_record(path: Path) -> dict:
    with Image.open(path) as image:
        record = {
            "path": path.name,
            "sha256": _sha256(path),
            "pixel_sha256": _pixel_sha256(path),
            "format": image.format,
            "mode": image.mode,
            "width": image.width,
            "height": image.height,
            "exif_present": bool(image.info.get("exif")) or bool(image.getexif()),
            "bytes": path.stat().st_size,
        }
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        record["jpeg"] = _jpeg_info(path)
    return record


def _expected_environment_path() -> Path:
    tmpdir = os.environ.get("TMPDIR")
    if not tmpdir:
        raise FreezeViolation("TMPDIR is absent; cannot resolve the frozen verify3 environment")
    return (Path(tmpdir) / "verify3").resolve()


def verify_environment(capture_freeze: bool = False) -> Tuple[dict, Optional[str]]:
    expected_prefix = _expected_environment_path()
    actual_prefix = Path(sys.prefix).resolve()
    checks = {
        "environment_prefix": str(actual_prefix),
        "expected_environment_prefix": str(expected_prefix),
        "environment_prefix_pass": actual_prefix == expected_prefix,
        "python": platform.python_version(),
        "python_pass": platform.python_version() == PYTHON_VERSION,
        "numpy": np.__version__,
        "numpy_pass": np.__version__ == NUMPY_VERSION,
        "pillow": PIL.__version__,
        "pillow_pass": PIL.__version__ == PILLOW_VERSION,
    }
    failed = [key for key, value in checks.items() if key.endswith("_pass") and not value]
    if failed:
        raise FreezeViolation(f"frozen environment mismatch: {', '.join(failed)}")
    freeze = None
    if capture_freeze:
        environment_python = expected_prefix / "bin" / "python"
        if not environment_python.is_file():
            raise FreezeViolation(f"frozen environment interpreter is missing: {environment_python}")
        completed = subprocess.run(
            [str(environment_python), "-m", "pip", "freeze"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        freeze = completed.stdout
        if freeze and not freeze.endswith("\n"):
            freeze += "\n"
    return checks, freeze


def _record_check(checks: List[dict], name: str, actual: Any, expected: Any) -> None:
    passed = actual == expected
    checks.append({"check": name, "actual": actual, "expected": expected, "pass": passed})
    if not passed:
        raise FreezeViolation(f"{name}: expected {expected!r}, got {actual!r}")


def _validate_boxes(image: str, kind: str, boxes: Any) -> bool:
    if not isinstance(boxes, list) or not boxes:
        return False
    for box in boxes:
        if not isinstance(box, list) or len(box) != 4:
            return False
        x0, y0, x1, y1 = box
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in box):
            return False
        if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
            return False
    return True


def verify_inputs(root: Path = ROOT) -> Tuple[dict, dict, dict, List[dict], List[dict]]:
    checks: List[dict] = []
    for relative, expected in FROZEN_FILE_PINS.items():
        path = root / relative
        actual = _sha256(path) if path.is_file() else None
        _record_check(checks, f"byte pin {relative}", actual, expected)

    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    settings_path = root / SETTINGS_PATH.relative_to(ROOT)
    roi_path = root / ROI_PATH.relative_to(ROOT)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    roi = json.loads(roi_path.read_text(encoding="utf-8"))

    cells = manifest.get("cells")
    _record_check(checks, "manifest cell count", len(cells) if isinstance(cells, list) else None, 24)
    b_cells = [cell for cell in cells if cell.get("arm") == "B"]
    _record_check(checks, "B-cell count", len(b_cells), 12)
    actual_cohort = sorted((cell.get("image"), cell.get("seed")) for cell in b_cells)
    expected_cohort = sorted((image, seed) for seed in SEEDS for image in SIX_IMAGES)
    _record_check(checks, "B-cell cohort", actual_cohort, expected_cohort)

    jobs = settings.get("jobs")
    _record_check(checks, "settings job count", len(jobs) if isinstance(jobs, dict) else None, 12)
    roi_images = roi.get("images")
    _record_check(checks, "ROI manifest FINAL", roi.get("FINAL"), True)
    _record_check(checks, "ROI manifest round", roi.get("round"), "4D-CAM-1")
    if not isinstance(roi_images, dict):
        raise FreezeViolation("ROI images block is missing")

    ordered_cells = sorted(b_cells, key=lambda cell: (cell["seed"], int(cell["image"].split("-")[1])))
    checkpoints = root / CHECKPOINTS.relative_to(ROOT)
    for cell in ordered_cells:
        job = cell["job"]
        block = jobs.get(job) if isinstance(jobs, dict) else None
        if not isinstance(block, dict):
            raise FreezeViolation(f"missing settings for B cell {job}")
        executed = block.get("executed")
        if not isinstance(executed, dict):
            raise FreezeViolation(f"missing executed settings for B cell {job}")
        expected_seed = f"lab:{cell['seed']}"
        literal_checks = {
            "settings seed": block.get("seed") == cell["seed"],
            "effective seed": executed.get("effective_seed") == expected_seed,
            "output mode": executed.get("output_mode") == "stripped",
            "tone-lock strength": block.get("remint", {}).get("color_restore_strength") == TONE_LOCK_STRENGTH,
            "finish preset": executed.get("finish_preset_selected") == "strong",
            "finish scale": executed.get("finish", {}).get("scale") == 1,
            "finish overrides": executed.get("finish", {}).get("overrides")
            == {"dither": 1, "sharpen": 1, "smoothness": 1.25},
            "stage-1 encode": executed.get("stage1_encode")
            == {"quality": STAGE1_QUALITY, "subsampling": STAGE1_SUBSAMPLING},
            "QF encode": executed.get("qf_encode")
            == {"quality": FINAL_QUALITY, "subsampling": FINAL_SUBSAMPLING, "single_encode": True},
            "naturalization off": executed.get("finalize", {}).get("photo_naturalization_enabled") is False,
        }
        for name, passed in literal_checks.items():
            _record_check(checks, f"{job} {name}", passed, True)

        files = cell.get("files", {})
        cell_dir = checkpoints / job
        for filename in REQUIRED_INPUTS:
            path = cell_dir / filename
            actual = _pixel_sha256(path) if path.is_file() else None
            _record_check(checks, f"{job} {filename} pixel pin", actual, files.get(filename))

        expected_size = (
            int(executed.get("finish", {}).get("width", 0)),
            int(executed.get("finish", {}).get("height", 0)),
        )
        _record_check(checks, f"{job} square delivery", expected_size[0], expected_size[1])
        _record_check(checks, f"{job} delivery edge", expected_size[0] in DELIVERY_EDGES, True)
        for filename in ("OR_postresample.png", "O2_precamera.png", "O5_final.png"):
            with Image.open(cell_dir / filename) as image:
                _record_check(checks, f"{job} {filename} geometry", image.size, expected_size)

        image_rois = roi_images.get(cell["image"])
        if not isinstance(image_rois, dict):
            raise FreezeViolation(f"ROI manifest lacks {cell['image']}")
        for kind in ("protected", "smooth", "texture"):
            _record_check(
                checks,
                f"{cell['image']} {kind} ROI syntax",
                _validate_boxes(cell["image"], kind, image_rois.get(kind)),
                True,
            )

    return manifest, settings, roi, ordered_cells, checks


def load_frozen_functions() -> FrozenFunctions:
    sys.path.insert(0, str(TOOLS_DIR))
    sys.path.insert(0, str(WORKER_DIR))
    from max_cx_remint import _histogram_match  # noqa: E402
    from quality_finish import apply_quality_finish  # noqa: E402
    from transfer_4d_1b import build_candidate  # noqa: E402

    return FrozenFunctions(_histogram_match, apply_quality_finish, build_candidate)


def _qf_settings() -> dict:
    return {
        "mode": "quality-finish",
        "quality_finish": {
            "preset": "strong",
            "scale": 1,
            "overrides": {"dither": 1, "sharpen": 1, "smoothness": 1.25},
            "material_clean": True,
            "finish_mode": "fixed-executed-replay",
        },
    }


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _save_stage1(image: Image.Image, path: Path) -> np.ndarray:
    image.save(
        path,
        format="JPEG",
        quality=STAGE1_QUALITY,
        subsampling=STAGE1_SUBSAMPLING,
        optimize=True,
    )
    info = _jpeg_info(path)
    if info["sampling"] != STAGE1_SUBSAMPLING:
        raise FreezeViolation(f"stage-1 sampling mismatch: {path}")
    if _has_exif(path):
        raise FreezeViolation(f"stage-1 EXIF is forbidden: {path}")
    return _load_rgb(path)


def _save_final(rgb: np.ndarray, path: Path) -> None:
    Image.fromarray(np.asarray(rgb, dtype=np.uint8)).save(
        path,
        format="JPEG",
        quality=FINAL_QUALITY,
        subsampling=FINAL_SUBSAMPLING,
        optimize=True,
    )


def _candidate_metrics(report: dict) -> dict:
    recovery = report.get("recovery")
    if not isinstance(recovery, dict):
        raise FreezeViolation("A4 candidate recovery report is missing")
    return {
        "eligible_recovered_energy": recovery.get("eligible_numerator"),
        "eligible_recovered_energy_definition": "sum(E_candidate-E_O2) over valid eligible windows",
        "eligible_lost_energy_mass": recovery.get("eligible_lost_energy_mass"),
        "eligible_lost_energy_mass_definition": "eligible lost energy / whole-frame positive lost energy",
        "whole_frame_recovered_energy": recovery.get("whole_frame_numerator"),
        "whole_frame_recovered_energy_definition": "sum(E_candidate-E_O2) over positive-loss windows",
        "source_report": recovery,
    }


def run_arm(
    arm: Arm,
    cell: dict,
    block: dict,
    source_path: Path,
    or_rgb: np.ndarray,
    o2_rgb: np.ndarray,
    target: Path,
    functions: FrozenFunctions,
) -> dict:
    target.mkdir(parents=True, exist_ok=False)
    candidate_report = None
    input_label = "O2_precamera" if arm.camera else "OR_postresample"
    primary_rgb = o2_rgb if arm.camera else or_rgb

    if arm.preservation:
        candidate = functions.build_candidate(or_rgb, o2_rgb)
        primary_rgb = np.ascontiguousarray(candidate.rgb, dtype=np.uint8)
        candidate_report = _json_ready(candidate.report)
        input_label = "4D-1b build_candidate(OR_postresample,O2_precamera)"
        Image.fromarray(primary_rgb).save(target / "O2_preserved.png", format="PNG")
        support = np.where(np.asarray(candidate.support, dtype=bool), 255, 0).astype(np.uint8)
        Image.fromarray(support).save(target / "A4_support.png", format="PNG")

    with Image.open(source_path) as source_image:
        source = source_image.convert("RGB")
    primary = Image.fromarray(primary_rgb)
    reference = source.resize(primary.size, Image.Resampling.LANCZOS)
    tone_locked = functions.histogram_match(primary, reference, TONE_LOCK_STRENGTH).convert("RGB")
    tone_rgb = np.asarray(tone_locked, dtype=np.uint8)

    stage_path = target / "stage1-q92.jpg"
    stage_rgb = None
    if arm.intermediate_jpeg:
        stage_rgb = _save_stage1(tone_locked, stage_path)

    final_path = target / "O5_final.jpg"
    o4_path = target / "O4_preencode.png"
    qf_report = None
    if arm.quality_finish:
        kwargs = {
            "output_path": final_path,
            "settings": _qf_settings(),
            "seed_extra": block["executed"]["effective_seed"],
            "creator_id": "unused-by-quality-finish",
            "reference": source_path,
            "checkpoint_dir": target,
        }
        if arm.intermediate_jpeg:
            kwargs["input_path"] = stage_path
        else:
            kwargs["image"] = tone_rgb
        qf_report = functions.quality_finish(**kwargs)
        if qf_report.get("applied") is not True:
            raise FreezeViolation(f"{arm.name}/{cell['job']} QF did not apply")
        if qf_report.get("checkpoint_errors"):
            raise FreezeViolation(f"{arm.name}/{cell['job']} QF checkpoint error")
        expected_standalone = arm.intermediate_jpeg
        if qf_report.get("standalone_jpeg") is not expected_standalone:
            raise FreezeViolation(f"{arm.name}/{cell['job']} QF handoff mode mismatch")
        if qf_report.get("encode") != {
            "quality": FINAL_QUALITY,
            "subsampling": FINAL_SUBSAMPLING,
            "single_encode": True,
        }:
            raise FreezeViolation(f"{arm.name}/{cell['job']} QF final encode mismatch")
        if not o4_path.is_file():
            raise FreezeViolation(f"{arm.name}/{cell['job']} missing QF pre-encode checkpoint")
    else:
        if not arm.intermediate_jpeg or stage_rgb is None:
            raise FreezeViolation(f"{arm.name} QF-off composition lacks its frozen q92 handoff")
        Image.fromarray(stage_rgb).save(o4_path, format="PNG")
        _save_final(stage_rgb, final_path)

    expected_size = (
        int(block["executed"]["finish"]["width"]),
        int(block["executed"]["finish"]["height"]),
    )
    delivery = _jpeg_info(final_path)
    if (delivery["width"], delivery["height"]) != expected_size:
        raise FreezeViolation(f"{arm.name}/{cell['job']} delivery geometry mismatch")
    if delivery["sampling"] != FINAL_SUBSAMPLING:
        raise FreezeViolation(f"{arm.name}/{cell['job']} final sampling mismatch")
    if _has_exif(final_path):
        raise FreezeViolation(f"{arm.name}/{cell['job']} final EXIF is forbidden")

    report = {
        "arm": asdict(arm),
        "cell": {"job": cell["job"], "image": cell["image"], "seed": cell["seed"]},
        "effective_seed": block["executed"]["effective_seed"],
        "input_at_O2_position": input_label,
        "input_pixel_sha256": _array_pixel_sha256(primary_rgb),
        "tone_lock": {
            "function": "max_cx_remint._histogram_match",
            "strength": TONE_LOCK_STRENGTH,
            "reference": "O0_source resized LANCZOS to delivery geometry",
            "pixel_sha256": _array_pixel_sha256(tone_rgb),
        },
        "intermediate_jpeg": _image_record(stage_path) if stage_path.is_file() else None,
        "pre_final": _image_record(o4_path),
        "delivered": _image_record(final_path),
        "delivery_contract": {
            "quality": FINAL_QUALITY,
            "sampling": FINAL_SUBSAMPLING,
            "optimize": True,
            "single_final_encode": True,
            "output_mode": "stripped",
            "exif_present": False,
        },
        "quality_finish_report": qf_report,
        "A4_candidate_report": candidate_report,
        "A4_recovery_metrics": _candidate_metrics(candidate_report) if candidate_report else None,
    }
    _write_json(target / "cell-report.json", report)
    return report


def _artifact_index(directory: Path, report_path: Optional[Path] = None) -> dict:
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "artifact-index.json":
            continue
        if report_path is not None and path.resolve() == report_path.resolve():
            continue
        row = {
            "path": str(path.relative_to(directory)),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            row["pixel_sha256"] = _pixel_sha256(path)
        files.append(row)
    if report_path is not None and report_path.is_file():
        files.append(
            {
                "path": REPORT_PATH.name,
                "sha256": _sha256(report_path),
                "bytes": report_path.stat().st_size,
            }
        )
    index = {"self_exclusion": "artifact-index.json cannot hash itself", "files": files}
    _write_json(directory / "artifact-index.json", index)
    return index


def _write_report(path: Path, status: str, cell_count: int, output_count: int, reason: Optional[str] = None) -> None:
    declaration = (
        "I declare that this harness used only the pinned local archive, executed exactly A0-A6, preserved the frozen factors and settings, and performed none of the forbidden external actions."
        if cell_count == 12 and output_count == 84 and reason is None
        else "I declare that this harness used only the pinned local archive, stopped at the recorded exception without substituting an arm or setting, and performed none of the forbidden external actions."
    )
    lines = [
        "# C8 4D-AR1 Report",
        "",
        f"**Status: {status}.**",
        "",
        "This report covers the offline M1 factorial execution only. M2 metrics, quality gates, panel results, candidate selection, detector results, production admission, and Track B are not evaluated here.",
        "",
        "## Execution record",
        "",
        f"- Frozen B cells processed: **{cell_count}/12**.",
        f"- Frozen A0-A6 delivered outputs completed: **{output_count}/84**.",
        "- Environment: `$TMPDIR/verify3` with Python 3.9.6, NumPy 2.0.2, Pillow 11.3.0.",
        "- External/live actions: **none**. No cell, grading, vendor, Supabase, RunPod, commit, or deploy action is present in this harness.",
    ]
    if reason:
        lines.append(f"- Hard-stop reason: `{reason}`")
    lines.extend(
        [
            "",
            "## Artifact record",
            "",
            "`round-4d-ar1/artifact-index.json` hashes every produced artifact and this report, excluding only the index itself.",
            "",
            "## Builder declaration",
            "",
            declaration,
            "",
            "Signed: **C88 builder (Codex)**  ",
            "Commission date: **2026-08-29 (Australia/Sydney)**",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _ensure_clean_output_targets() -> None:
    occupied = [path for path in (OUT, WORK_OUT, REPORT_PATH, WORK_REPORT_PATH) if path.exists()]
    if occupied:
        raise FreezeViolation("refusing to overwrite existing output target(s): " + ", ".join(map(str, occupied)))


def execute_factorial(
    settings: dict,
    cells: Sequence[dict],
    checks: List[dict],
    environment: dict,
    environment_freeze: str,
    functions: FrozenFunctions,
) -> Tuple[int, int]:
    _ensure_clean_output_targets()
    WORK_OUT.mkdir(parents=False, exist_ok=False)
    (WORK_OUT / "environment-freeze.txt").write_text(environment_freeze, encoding="utf-8")
    _write_json(WORK_OUT / "input-verification.json", {"pass": True, "checks": checks})
    _write_json(WORK_OUT / "environment-verification.json", {"pass": True, **environment})

    completed_cells = set()
    outputs: List[dict] = []
    try:
        for cell_index, cell in enumerate(cells, 1):
            job = cell["job"]
            source_path = CHECKPOINTS / job / "O0_source.png"
            or_rgb = _load_rgb(CHECKPOINTS / job / "OR_postresample.png")
            o2_rgb = _load_rgb(CHECKPOINTS / job / "O2_precamera.png")
            block = settings["jobs"][job]
            for arm in ARMS:
                print(
                    f"cell {cell_index:02d}/12 arm {arm.name} {cell['image']}/{cell['seed']} {job}",
                    flush=True,
                )
                target = WORK_OUT / "arms" / arm.name / job
                report = run_arm(arm, cell, block, source_path, or_rgb, o2_rgb, target, functions)
                outputs.append(
                    {
                        "arm": arm.name,
                        "job": job,
                        "image": cell["image"],
                        "seed": cell["seed"],
                        "cell_report": str((target / "cell-report.json").relative_to(WORK_OUT)),
                        "delivered_sha256": report["delivered"]["sha256"],
                        "delivered_pixel_sha256": report["delivered"]["pixel_sha256"],
                    }
                )
            completed_cells.add(job)

        _write_json(
            WORK_OUT / "run-manifest.json",
            {
                "status": "M1_FACTORIAL_COMPLETE_M2_NOT_EVALUATED",
                "arm_order": [asdict(arm) for arm in ARMS],
                "cell_count": len(completed_cells),
                "delivered_output_count": len(outputs),
                "outputs": outputs,
            },
        )
        _write_report(WORK_REPORT_PATH, "M1 FACTORIAL COMPLETE — AWAITING MASTER-ENGINEER M2", 12, 84)
        _artifact_index(WORK_OUT, WORK_REPORT_PATH)
        WORK_OUT.rename(OUT)
        WORK_REPORT_PATH.rename(REPORT_PATH)
        return 12, 84
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        _write_json(
            WORK_OUT / "run-manifest.json",
            {
                "status": "HARD_STOP",
                "reason": reason,
                "completed_cell_count": len(completed_cells),
                "delivered_output_count": len(outputs),
                "outputs": outputs,
            },
        )
        _write_report(WORK_REPORT_PATH, "HARD STOP — FACTORIAL INCOMPLETE", len(completed_cells), len(outputs), reason)
        _artifact_index(WORK_OUT, WORK_REPORT_PATH)
        WORK_OUT.rename(OUT)
        WORK_REPORT_PATH.rename(REPORT_PATH)
        raise


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify frozen inputs and environment without creating experiment artifacts",
    )
    args = parser.parse_args(argv)

    try:
        environment, environment_freeze = verify_environment(capture_freeze=not args.verify_only)
        _, settings, _, cells, checks = verify_inputs()
        if args.verify_only:
            print(f"PASS: frozen environment and {len(checks)} input checks; no artifacts written")
            return 0
        functions = load_frozen_functions()
        cell_count, output_count = execute_factorial(
            settings,
            cells,
            checks,
            environment,
            environment_freeze or "",
            functions,
        )
        print(f"PASS: {cell_count} cells, {output_count} delivered A0-A6 outputs")
        return 0
    except Exception as exc:
        print(f"HARD STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
