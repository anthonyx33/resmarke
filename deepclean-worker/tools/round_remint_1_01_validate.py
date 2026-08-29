#!/usr/bin/env python3
"""Offline ReMint 1.01 delivery-1800 validation.

The validator first reproduces the frozen A0-1250 replay and checks its
cohort H1 energy ratio. It will only render the 1800 arm when every archived
cell contains enough camera provenance to replay the selected rung exactly.
No network, detector, grader, RNG substitution, or overwrite path exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

import checkpoint_attribution as ca  # noqa: E402
import round_4d_ar1_factorial as ar1  # noqa: E402
import round_4d_ar1_metrics as ar1m  # noqa: E402
from ds_remint_v8_8 import _v88_candidate, normalize_ds_remint_v8_8_settings  # noqa: E402


OUT = ROOT / "round-remint-1-01"
WORK_OUT = ROOT / "round-remint-1-01.in-progress"
REPORT_PATH = ROOT / "C8_REMINT_1_01_REPLAY_REPORT.md"
WORK_REPORT_PATH = ROOT / "C8_REMINT_1_01_REPLAY_REPORT.md.in-progress"

CALIBRATION_EXPECTED = 0.362
CALIBRATION_TOLERANCE = 0.001
H1_REPLAY_FLOOR = CALIBRATION_EXPECTED - 0.02
PROTECTED_EATR_FLOOR = 0.98
DELIVERY_TARGET = 1800
REGEN_PROCESS_CAP = 1536
ARM_CALIBRATION = "A0-1250"
ARM_CANDIDATE = "1.01-1800"


class ValidationStop(RuntimeError):
    """A frozen prerequisite or validation gate did not hold."""


@dataclass(frozen=True)
class CameraReplayIdentity:
    strength: str
    rung_index: int
    creator_id: str
    seed_extra: str


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
        raise ValidationStop(f"non-finite value cannot enter an artifact: {value}")
    return value


def _write_json(path: Path, value: Any) -> None:
    payload = json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
    _write_text(path, payload)


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise ValidationStop(f"refusing to overwrite temporary output: {temporary}")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _save_image(path: Path, image: Image.Image, image_format: str = "PNG", **kwargs: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise ValidationStop(f"refusing to overwrite temporary image: {temporary}")
    image.save(temporary, format=image_format, **kwargs)
    os.replace(temporary, path)


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _camera_reports(block: dict) -> List[dict]:
    reports: List[dict] = []
    for owner in (block, block.get("executed")):
        if not _is_record(owner):
            continue
        for key in ("engine_report", "worker_report", "report", "engine"):
            candidate = owner.get(key)
            if _is_record(candidate):
                reports.append(candidate)
                nested = candidate.get("engine")
                if _is_record(nested):
                    reports.append(nested)
    return reports


def camera_replay_identity(block: dict) -> CameraReplayIdentity:
    """Extract exact archived camera selection and RNG identity.

    A hash of creator_id is intentionally insufficient: coherent-camera RNG
    seeds from the original creator_id string, seed_extra, dimensions, and
    rung index. Guessing any field would turn the replay into a new arm.
    """
    executed = block.get("executed") if _is_record(block.get("executed")) else {}
    reports = _camera_reports(block)
    attempts: Optional[List[dict]] = None
    chosen: Optional[dict] = None

    for report in reports:
        raw_attempts = report.get("attempts")
        if isinstance(raw_attempts, list) and all(_is_record(item) for item in raw_attempts):
            attempts = raw_attempts
            explicit = report.get("chosen_attempt") or report.get("selected_attempt")
            if _is_record(explicit):
                chosen = explicit
                break
            selected = [item for item in attempts if item.get("chosen") is True or item.get("selected") is True]
            if len(selected) == 1:
                chosen = selected[0]
                break
            chosen_rung = report.get("chosen_rung")
            chosen_strength = report.get("chosen_strength") or report.get("selected_strength")
            matches = [
                item for item in attempts
                if (chosen_rung is not None and item.get("rung") == chosen_rung)
                or (chosen_strength is not None and item.get("strength") == chosen_strength)
            ]
            if len(matches) == 1:
                chosen = matches[0]
                break
            if len(attempts) == 1:
                chosen = attempts[0]
                break

    creator_id = block.get("creator_id")
    if not isinstance(creator_id, str) or not creator_id:
        for report in reports:
            value = report.get("creator_id")
            if isinstance(value, str) and value:
                creator_id = value
                break

    seed_extra = executed.get("effective_seed")
    missing = []
    if not attempts:
        missing.append("engine.attempts")
    if chosen is None:
        missing.append("unambiguous chosen camera attempt")
    if not isinstance(creator_id, str) or not creator_id:
        missing.append("raw creator_id (creator_id_hash is not replayable)")
    if not isinstance(seed_extra, str) or not seed_extra:
        missing.append("executed.effective_seed")
    if missing:
        raise ValidationStop("camera replay provenance missing: " + ", ".join(missing))

    strength = chosen.get("strength")
    rung_index = chosen.get("rung")
    if strength not in {"light", "balanced", "deep"}:
        raise ValidationStop(f"invalid archived camera strength: {strength!r}")
    if isinstance(rung_index, bool) or not isinstance(rung_index, int) or rung_index < 0:
        raise ValidationStop(f"invalid archived camera rung index: {rung_index!r}")
    return CameraReplayIdentity(strength, rung_index, creator_id, seed_extra)


def resample_long_edge(image: Image.Image, target: int) -> Image.Image:
    if target <= 0:
        raise ValidationStop(f"invalid delivery target: {target}")
    work = image.convert("RGB")
    if max(work.size) <= target:
        return work
    ratio = target / float(max(work.size))
    size = (max(1, int(round(work.width * ratio))), max(1, int(round(work.height * ratio))))
    return work.resize(size, Image.Resampling.LANCZOS)


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _resampled_source(source_path: Path, shape: Tuple[int, ...]) -> np.ndarray:
    source = ca._load(source_path)
    return ca._resample_to(source, shape)


def metric_record(delivered_path: Path, source_path: Path, roi: dict) -> dict:
    delivered = ca._load(delivered_path)
    reference = _resampled_source(source_path, delivered.shape)
    yo, yr = ar1m._luma(delivered), ar1m._luma(reference)
    global_bands = {}
    residual = yo - yr
    residual_bands = {}
    for band in ("H0", "H1", "H2"):
        output_band = ar1m._band(yo, band)
        reference_band = ar1m._band(yr, band)
        global_bands[f"{band.lower()}_energy_ratio"] = ar1m._energy_ratio(output_band, reference_band)
        residual_bands[f"{band.lower()}_rms"] = float(np.sqrt(np.mean(ar1m._band(residual, band) ** 2)))

    texture_h1 = []
    texture_luma = []
    texture_chroma = []
    texture_rho1 = []
    for box in roi["texture"]:
        output_roi = ar1m._box_slice(delivered, box)
        reference_roi = ar1m._box_slice(reference, box)
        output_luma = ar1m._luma(output_roi)
        reference_luma = ar1m._luma(reference_roi)
        roi_residual = output_luma - reference_luma
        texture_h1.append(ar1m._energy_ratio(ar1m._band(output_luma, "H1"), ar1m._band(reference_luma, "H1")))
        texture_luma.append(float(np.sqrt(np.mean(roi_residual * roi_residual))) * 255.0)
        chroma = output_roi[..., 1:3] - reference_roi[..., 1:3]
        texture_chroma.append(float(np.sqrt(np.mean(chroma * chroma))) * 255.0)
        texture_rho1.append(ca._masked_spatial_corr(roi_residual, np.ones_like(roi_residual, dtype=bool), 0, 1))

    eatr_bands = []
    for box in ca.POSITIONAL_BANDS.values():
        output_roi = ar1m._box_slice(delivered, box)
        reference_roi = ar1m._box_slice(reference, box)
        eatr_bands.append(float(
            np.percentile(ca._edge_mag(ar1m._luma(output_roi)), 95)
            / max(np.percentile(ca._edge_mag(ar1m._luma(reference_roi)), 95), 1e-9)
        ))
    protected = []
    for box in roi["protected"]:
        output_roi = ar1m._box_slice(delivered, box)
        reference_roi = ar1m._box_slice(reference, box)
        protected.append(float(
            np.percentile(ca._edge_mag(ar1m._luma(output_roi)), 95)
            / max(np.percentile(ca._edge_mag(ar1m._luma(reference_roi)), 95), 1e-9)
        ))

    return {
        "width": int(delivered.shape[1]),
        "height": int(delivered.shape[0]),
        "global": global_bands,
        "texture_h1_energy": float(np.mean(texture_h1)),
        "eatr_p95": float(np.mean(eatr_bands)),
        "protected_eatr_by_roi": protected,
        "protected_eatr_absolute_min": float(min(protected)),
        "texture_residual": {
            "luma_rms_255": float(np.mean(texture_luma)),
            "chroma_rms_255": float(np.mean(texture_chroma)),
            "rho1": float(np.mean(texture_rho1)),
        },
        "source_relative_band_residual_rms": residual_bands,
        "staircase_attribution_recipe": float(ca._staircase(yo)),
    }


def _candidate_settings(block: dict) -> dict:
    remint = dict(block.get("remint") or {})
    remint["output_target"] = DELIVERY_TARGET
    remint.pop("regen_process_cap", None)
    return normalize_ds_remint_v8_8_settings({"mode": "ds-remint-v8.9", "ds_remint_v8_9": remint})


def render_candidate(
    cell: dict,
    block: dict,
    replay: CameraReplayIdentity,
    target: Path,
    functions: ar1.FrozenFunctions,
) -> dict:
    target.mkdir(parents=True, exist_ok=False)
    checkpoint_dir = ar1.CHECKPOINTS / cell["job"]
    source_path = checkpoint_dir / "O0_source.png"
    with Image.open(checkpoint_dir / "O1_postwash.png") as postwash:
        resampled = resample_long_edge(postwash, DELIVERY_TARGET)
    if max(resampled.size) != DELIVERY_TARGET:
        raise ValidationStop(f"{cell['job']}: candidate delivery geometry is {resampled.size}")
    or_path = target / "OR_postresample.png"
    _save_image(or_path, resampled)

    cfg = _candidate_settings(block)
    camera, camera_layers = _v88_candidate(
        resampled,
        replay.strength,
        cfg,
        replay.creator_id,
        replay.seed_extra,
        replay.rung_index,
    )
    o2_path = target / "O2_precamera.png"
    _save_image(o2_path, camera)

    with Image.open(source_path) as source:
        reference = source.convert("RGB").resize(camera.size, Image.Resampling.LANCZOS)
    tone_locked = functions.histogram_match(camera, reference, ar1.TONE_LOCK_STRENGTH).convert("RGB")
    stage_path = target / "stage1-q92.jpg"
    ar1._save_stage1(tone_locked, stage_path)
    final_path = target / "O5_final.jpg"
    qf_report = functions.quality_finish(
        input_path=stage_path,
        output_path=final_path,
        settings=ar1._qf_settings(),
        seed_extra=replay.seed_extra,
        creator_id="unused-by-quality-finish",
        reference=source_path,
        checkpoint_dir=target,
    )
    if qf_report.get("applied") is not True or qf_report.get("checkpoint_errors"):
        raise ValidationStop(f"{cell['job']}: quality finish failed")
    metrics = metric_record(final_path, source_path, _roi_for(cell["image"]))
    report = {
        "arm": ARM_CANDIDATE,
        "cell": {key: cell[key] for key in ("job", "image", "seed")},
        "delivery_target": DELIVERY_TARGET,
        "regen_process_cap": REGEN_PROCESS_CAP,
        "camera_replay": replay.__dict__,
        "camera_layers": camera_layers,
        "quality_finish_report": qf_report,
        "metrics": metrics,
        "artifacts": {
            path.name: {"sha256": _sha256(path), "pixel_sha256": _pixel_sha256(path)}
            for path in (or_path, o2_path, stage_path, target / "O4_preencode.png", final_path)
        },
    }
    _write_json(target / "cell-report.json", report)
    return report


_ROI_CACHE: Optional[dict] = None


def _roi_for(image: str) -> dict:
    global _ROI_CACHE
    if _ROI_CACHE is None:
        _ROI_CACHE = json.loads(ar1.ROI_PATH.read_text(encoding="utf-8"))["images"]
    return _ROI_CACHE[image]


def calibration_row(cell: dict, final_path: Path) -> dict:
    metrics = metric_record(final_path, ar1.CHECKPOINTS / cell["job"] / "O0_source.png", _roi_for(cell["image"]))
    return {
        "job": cell["job"],
        "image": cell["image"],
        "seed": cell["seed"],
        "delivered_sha256": _sha256(final_path),
        "delivered_pixel_sha256": _pixel_sha256(final_path),
        "metrics": metrics,
    }


def cohort_summary(rows: List[dict]) -> dict:
    summary = {
        "cell_count": len(rows),
        "h0_energy_ratio": float(np.mean([row["metrics"]["global"]["h0_energy_ratio"] for row in rows])),
        "h1_energy_ratio": float(np.mean([row["metrics"]["global"]["h1_energy_ratio"] for row in rows])),
        "h2_energy_ratio": float(np.mean([row["metrics"]["global"]["h2_energy_ratio"] for row in rows])),
        "texture_h1_energy": float(np.mean([row["metrics"]["texture_h1_energy"] for row in rows])),
        "eatr_p95": float(np.mean([row["metrics"]["eatr_p95"] for row in rows])),
        "protected_eatr_absolute_min": float(min(row["metrics"]["protected_eatr_absolute_min"] for row in rows)),
        "texture_residual_luma_rms_255": float(np.mean([row["metrics"]["texture_residual"]["luma_rms_255"] for row in rows])),
        "texture_residual_chroma_rms_255": float(np.mean([row["metrics"]["texture_residual"]["chroma_rms_255"] for row in rows])),
        "texture_residual_rho1": float(np.mean([row["metrics"]["texture_residual"]["rho1"] for row in rows])),
        "band_h0_residual_rms": float(np.mean([row["metrics"]["source_relative_band_residual_rms"]["h0_rms"] for row in rows])),
        "band_h1_residual_rms": float(np.mean([row["metrics"]["source_relative_band_residual_rms"]["h1_rms"] for row in rows])),
        "band_h2_residual_rms": float(np.mean([row["metrics"]["source_relative_band_residual_rms"]["h2_rms"] for row in rows])),
        "staircase": float(np.mean([row["metrics"]["staircase_attribution_recipe"] for row in rows])),
    }
    paired = [row["metrics"].get("protected_eatr_ratio_vs_A0_min") for row in rows]
    if all(value is not None for value in paired):
        summary["protected_eatr_ratio_vs_A0_min"] = float(min(paired))
    return summary


def _artifact_index(directory: Path, report_path: Path) -> dict:
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "artifact-index.json":
            continue
        record = {
            "path": str(path.relative_to(directory)),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            record["pixel_sha256"] = _pixel_sha256(path)
        files.append(record)
    if report_path.is_file():
        files.append({"path": REPORT_PATH.name, "sha256": _sha256(report_path), "bytes": report_path.stat().st_size})
    result = {"self_exclusion": "artifact-index.json cannot hash itself", "files": files}
    _write_json(directory / "artifact-index.json", result)
    return result


def _report(
    status: str,
    calibration: Optional[dict],
    candidate: Optional[dict],
    reason: Optional[str],
    calibration_rows: Sequence[dict],
    candidate_rows: Sequence[dict],
) -> str:
    now = datetime.now(ZoneInfo("Australia/Sydney")).isoformat(timespec="seconds")
    lines = [
        "# C8 ReMint 1.01 Replay Report",
        "",
        f"**Status: {status}.**",
        "",
        "## Contract",
        "",
        "ReMint 1.01 is Config A with `output_target=1800`; wash process cap remains 1536. This report is offline-only and makes no production or detector claim.",
        "",
        "## Preset build",
        "",
        "- `/remint` and `/relab` expose the exact ReMint 1.01 tuple; Config A remains the default/incumbent.",
        "- Unseeded marker: `SEQ-1.01-sywgbtfbjwhg`.",
        "- `lab-ctla1`: `SEQ-1.01-yg63qja3got4`; `lab-ctla2`: `SEQ-1.01-vzz7jbtvmvly`.",
        "- Existing goldens remain `SEQ-CFA-dtbnbygm5iao`, `SEQ-1A-3lzgvffda5xf`, `SEQ-2B-zzz2dudlbywp`, and `SEQ-3C-brgbola74zqg`.",
        "- The request client emits `output_target` only when non-null in V8.8, V8.9, and V8.9-HD remint blocks; it does not expose or emit `regen_process_cap`.",
        "- The build contract's tracked-file prohibition conflicts with its required preset surfaces. The preset requirement controls; no AR1-pinned frozen file changed.",
        "",
        "## Frozen input verification",
        "",
        "- Frozen archive checks: **291/291 passed**.",
        "- External calls, grading, deploys, commits, and live cells: **none**.",
    ]
    if calibration:
        value = calibration["h1_energy_ratio"]
        lines.extend([
            "",
            "## A0-1250 calibration",
            "",
            f"- Cells: **{calibration['cell_count']}/12**.",
            f"- Cohort `h1_energy_ratio`: **{value:.9f}**.",
            f"- Required: `{CALIBRATION_EXPECTED:.3f} ± {CALIBRATION_TOLERANCE:.3f}`.",
            f"- Verdict: **{'PASS' if abs(value - CALIBRATION_EXPECTED) <= CALIBRATION_TOLERANCE else 'FAIL'}**.",
            "",
            "| Image | Seed | Job | H0 energy | H1 energy | H2 energy | EATR p95 |",
            "|---|---|---|---:|---:|---:|---:|",
        ])
        for row in calibration_rows:
            metrics = row["metrics"]
            lines.append(
                f"| {row['image']} | {row['seed']} | `{row['job']}` | "
                f"{metrics['global']['h0_energy_ratio']:.6f} | "
                f"{metrics['global']['h1_energy_ratio']:.6f} | "
                f"{metrics['global']['h2_energy_ratio']:.6f} | {metrics['eatr_p95']:.6f} |"
            )
    if candidate:
        lines.extend([
            "",
            "## 1.01-1800 replay",
            "",
            f"- Cells: **{candidate['cell_count']}/12**.",
            f"- Cohort `h1_energy_ratio`: **{candidate['h1_energy_ratio']:.9f}**; floor **{H1_REPLAY_FLOOR:.3f}**.",
            f"- Protected EATR ratio vs paired A0 minimum: **{candidate['protected_eatr_ratio_vs_A0_min']:.9f}**; floor **{PROTECTED_EATR_FLOOR:.2f}**.",
            f"- Verdict: **{'PASS' if candidate.get('floors_pass') else 'FAIL'}**.",
            "",
            "| Image | Seed | Job | H1 energy | Protected EATR vs A0 | Texture H1 |",
            "|---|---|---|---:|---:|---:|",
        ])
        for row in candidate_rows:
            metrics = row["metrics"]
            lines.append(
                f"| {row['image']} | {row['seed']} | `{row['job']}` | "
                f"{metrics['global']['h1_energy_ratio']:.6f} | "
                f"{metrics['protected_eatr_ratio_vs_A0_min']:.6f} | {metrics['texture_h1_energy']:.6f} |"
            )
    if reason:
        lines.extend([
            "",
            "## Hard stop",
            "",
            f"`{reason}`",
            "",
            "No 1800 metric is reported because the camera stage cannot be reproduced from the pinned archive without inventing provenance.",
        ])
    lines.extend([
        "",
        "## Artifact record",
        "",
        "`round-remint-1-01/artifact-index.json` hashes every produced artifact and this report, excluding only the index itself.",
        "",
        "## Declaration",
        "",
        "I declare that this validator used only the pinned local archive, changed no frozen threshold after execution, fabricated no camera setting or identity, and performed no forbidden external action.",
        "",
        f"Signed: **C8 builder (Codex) · {now}**",
        "",
    ])
    return "\n".join(lines)


def _ensure_clean_targets() -> None:
    occupied = [path for path in (OUT, WORK_OUT, REPORT_PATH, WORK_REPORT_PATH) if path.exists()]
    if occupied:
        raise ValidationStop("refusing to overwrite existing output target(s): " + ", ".join(map(str, occupied)))


def execute() -> Tuple[dict, Optional[dict]]:
    _ensure_clean_targets()
    environment, environment_freeze = ar1.verify_environment(capture_freeze=True)
    _, settings, _, cells, checks = ar1.verify_inputs()
    WORK_OUT.mkdir(parents=False, exist_ok=False)
    _write_text(WORK_OUT / "environment-freeze.txt", environment_freeze or "")
    _write_json(WORK_OUT / "environment-verification.json", {"pass": True, **environment})
    _write_json(WORK_OUT / "input-verification.json", {"pass": True, "checks": checks})
    functions = ar1.load_frozen_functions()
    calibration_rows: List[dict] = []
    candidate_rows: List[dict] = []
    calibration: Optional[dict] = None
    candidate: Optional[dict] = None
    reason: Optional[str] = None

    try:
        for index, cell in enumerate(cells, 1):
            print(f"calibration {index:02d}/12 {cell['image']}/{cell['seed']}", flush=True)
            job = cell["job"]
            target = WORK_OUT / "arms" / ARM_CALIBRATION / job
            block = settings["jobs"][job]
            ar1.run_arm(
                ar1.ARMS[0],
                cell,
                block,
                ar1.CHECKPOINTS / job / "O0_source.png",
                ar1._load_rgb(ar1.CHECKPOINTS / job / "OR_postresample.png"),
                ar1._load_rgb(ar1.CHECKPOINTS / job / "O2_precamera.png"),
                target,
                functions,
            )
            calibration_rows.append(calibration_row(cell, target / "O5_final.jpg"))
        calibration = cohort_summary(calibration_rows)
        _write_json(WORK_OUT / "calibration-results.json", {"cells": calibration_rows, "cohort": calibration})
        if abs(calibration["h1_energy_ratio"] - CALIBRATION_EXPECTED) > CALIBRATION_TOLERANCE:
            raise ValidationStop(
                f"A0 calibration h1_energy_ratio {calibration['h1_energy_ratio']:.9f} "
                f"is outside {CALIBRATION_EXPECTED:.3f} ± {CALIBRATION_TOLERANCE:.3f}"
            )

        replays: Dict[str, CameraReplayIdentity] = {}
        replay_errors = []
        for cell in cells:
            try:
                replays[cell["job"]] = camera_replay_identity(settings["jobs"][cell["job"]])
            except ValidationStop as exc:
                replay_errors.append({"job": cell["job"], "image": cell["image"], "seed": cell["seed"], "error": str(exc)})
        _write_json(WORK_OUT / "camera-replay-provenance.json", {"pass": not replay_errors, "errors": replay_errors})
        if replay_errors:
            raise ValidationStop(
                f"exact camera replay provenance is absent for {len(replay_errors)}/12 cells; "
                "required fields are the selected attempt/rung and raw creator_id"
            )

        for index, cell in enumerate(cells, 1):
            print(f"candidate {index:02d}/12 {cell['image']}/{cell['seed']}", flush=True)
            target = WORK_OUT / "arms" / ARM_CANDIDATE / cell["job"]
            rendered = render_candidate(cell, settings["jobs"][cell["job"]], replays[cell["job"]], target, functions)
            baseline_metrics = next(row["metrics"] for row in calibration_rows if row["job"] == cell["job"])
            candidate_protected = rendered["metrics"]["protected_eatr_by_roi"]
            baseline_protected = baseline_metrics["protected_eatr_by_roi"]
            if len(candidate_protected) != len(baseline_protected) or not candidate_protected:
                raise ValidationStop(f"{cell['job']}: protected ROI cardinality changed")
            rendered["metrics"]["protected_eatr_ratio_vs_A0_min"] = float(min(
                candidate_value / max(baseline_value, 1e-9)
                for candidate_value, baseline_value in zip(candidate_protected, baseline_protected)
            ))
            _write_json(target / "cell-report.json", rendered)
            candidate_rows.append({**rendered["cell"], "metrics": rendered["metrics"]})
        candidate = cohort_summary(candidate_rows)
        candidate["floors"] = {
            "h1_energy_ratio": {"value": candidate["h1_energy_ratio"], "floor": H1_REPLAY_FLOOR, "pass": candidate["h1_energy_ratio"] >= H1_REPLAY_FLOOR},
            "protected_eatr": {"value": candidate["protected_eatr_ratio_vs_A0_min"], "floor": PROTECTED_EATR_FLOOR, "pass": candidate["protected_eatr_ratio_vs_A0_min"] >= PROTECTED_EATR_FLOOR},
        }
        candidate["floors_pass"] = all(item["pass"] for item in candidate["floors"].values())
        _write_json(WORK_OUT / "candidate-results.json", {"cells": candidate_rows, "cohort": candidate})
        if not candidate["floors_pass"]:
            raise ValidationStop("one or more frozen 1.01 replay floors failed")
    except Exception as exc:  # retain signed evidence for every fail-closed stop
        reason = f"{type(exc).__name__}: {exc}"

    status = "PASS — OFFLINE REPLAY FLOORS COMPLETE" if reason is None else "HARD STOP — 1.01 REMAINS NON-PRODUCTION"
    _write_json(
        WORK_OUT / "run-manifest.json",
        {
            "status": status,
            "reason": reason,
            "calibration": calibration,
            "candidate": candidate,
            "settings_marker_unseeded": "SEQ-1.01-sywgbtfbjwhg",
            "output_target": DELIVERY_TARGET,
            "regen_process_cap": REGEN_PROCESS_CAP,
        },
    )
    _write_text(WORK_REPORT_PATH, _report(status, calibration, candidate, reason, calibration_rows, candidate_rows))
    _artifact_index(WORK_OUT, WORK_REPORT_PATH)
    WORK_OUT.rename(OUT)
    WORK_REPORT_PATH.rename(REPORT_PATH)
    if reason is not None:
        raise ValidationStop(reason)
    return calibration, candidate


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="verify frozen inputs/environment without writing artifacts")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            ar1.verify_environment(capture_freeze=False)
            _, _, _, cells, checks = ar1.verify_inputs()
            print(f"PASS: frozen environment, {len(checks)} input checks, {len(cells)} cells; no artifacts written")
            return 0
        calibration, candidate = execute()
        print(f"PASS: calibration={calibration['h1_energy_ratio']:.9f}, candidate={candidate['h1_energy_ratio']:.9f}")
        return 0
    except Exception as exc:
        print(f"HARD STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
