#!/usr/bin/env python3
"""Offline-only 4D-S1 stage-detection ledger verifier/interpreter.

Implements C8_MASTER_PROMPT_4D_S1_STAGE_DETECTION_LEDGER.md.  This module
contains no grader, vendor client, network client, deployment path, or image
transformation.  It verifies the 24 frozen input files, defines and validates
the raw-ledger contract, and applies only the frozen section-4 arithmetic.

The production CLI is deliberately read-only:

* no flag: verify the 24 input pins;
* --print-contract: print the ledger contract and exact file pins;
* --validate-ledger: validate round-4d-s1/ledger-raw.json and print the
  fail-closed interpretation.

The owner/operator, not this program, performs the 24 real Hive calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
FREEZE_PATH = ROOT / "C8_MASTER_PROMPT_4D_S1_STAGE_DETECTION_LEDGER.md"
VENDOR_FREEZE_PATH = ROOT / "VENDOR_FREEZE_4D_1A.md"
EXPECTED_MANIFEST_PATH = ROOT / "round-4d-1a" / "expected-manifest.json"
AR1_INDEX_PATH = ROOT / "round-4d-ar1" / "artifact-index.json"
LEDGER_PATH = ROOT / "round-4d-s1" / "ledger-raw.json"

SCHEMA_VERSION = "4d-s1-ledger-v1"
ROUND_ID = "4D-S1"
SEED = "lab-ctla1"
VENDOR = "g1"
MODEL = "hive/ai-generated-and-deepfake-content-detection"
MODEL_VERSION = "1"
CALL_CAP = 40
LOGICAL_CALL_BUDGET = 24
RESERVE_CALLS = 16
AI_THRESHOLD = 0.45
FLUX_THRESHOLD = 0.30
DEEPFAKE_THRESHOLD = 0.10
STAGE_VALUE_CUTOFF = 0.05
SUM_TOLERANCE = 1e-3
IMAGES = ("IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11")
STAGES = ("O1", "OR", "O2", "O5")

FROZEN_AUTHORITY_PINS = {
    "C8_MASTER_PROMPT_4D_S1_STAGE_DETECTION_LEDGER.md":
        "896c4ca81f64ab27c07e641508ac121bcd4df68c99d215bd6dbdd9501e4aebb3",
    "VENDOR_FREEZE_4D_1A.md":
        "02d9e0de66fc400369fa5e672be329b35a459c541d2614e470f2381221899d3a",
    "round-4d-1a/expected-manifest.json":
        "6d1c730c629fda80b04b742bc75423f2f4710802a6cabc330910aaff7739c76a",
    "round-4d-ar1/artifact-index.json":
        "01a51382bea68634b957479d8b98179ae5f09ee5a65da2af89ddd21afd9d4c20",
}

# VENDOR_FREEZE_4D_1A.md v3 explicitly names this denied value.  The raw C2PA
# object and every action value are also retained in the ledger analysis so the
# master engineer can apply any separately frozen extension without losing data.
EXPLICIT_C2PA_DENY_VALUES = frozenset({"trainedAlgorithmicMedia"})

NON_SOURCE_CLASSES = frozenset({
    "ai_generated",
    "not_ai_generated",
    "deepfake",
    "inconclusive",
    "ai_generated_audio",
    "not_ai_generated_audio",
})


class FreezeViolation(RuntimeError):
    """A frozen authority, file pin, or ledger-identity contract failed."""


@dataclass(frozen=True)
class FilePin:
    logical_id: str
    image: str
    job: str
    seed: str
    stage: str
    path: str
    sha256: str
    pixel_sha256: str
    bytes: int
    format: str


@dataclass(frozen=True)
class FrozenCell:
    image: str
    job: str
    o1_sha256: str
    o1_bytes: int
    or_sha256: str
    or_bytes: int
    o2_sha256: str
    o2_bytes: int
    o5_sha256: str
    o5_bytes: int


FROZEN_CELLS = (
    FrozenCell(
        "IMG-5", "e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5",
        "266db4db24244927ca733a939beba2264117f95b2c487eb4dd0c8b095d419471", 6032219,
        "ea0a479ebe25da5e31d26ba8ccde458683ef7a3234d3cf0341a487da83100a1c", 2516349,
        "a5c1317008a4678099be228ef1af5dbb60f7120391249e3b6ec3237caacb3773", 2672542,
        "68e8d3ffdf086185b8aa83d6e371a944eb26e17d3f48bf87b2ae97aea66d71fc", 811477,
    ),
    FrozenCell(
        "IMG-6", "cfca4ae3-5400-4a2c-a025-53271e40aaa7",
        "44500fa1711bed7b267a5d533e64e7ecb5e69ad70af30cf735c2b2ea39fa74ce", 835418,
        "44500fa1711bed7b267a5d533e64e7ecb5e69ad70af30cf735c2b2ea39fa74ce", 835418,
        "2bb85894c6cfd44459fcc02c70410d417f2fef529a9df7d672434fa7a5e9737c", 1106994,
        "6a6a7c767591fa1bd719e7f8886ebfce22d5ff7d9c595c97f2a9595ec5899e9b", 327578,
    ),
    FrozenCell(
        "IMG-7", "f8b00791-fad5-4d51-a0ba-56a4b6bf98a7",
        "e06c410ffa1b98cb16eb3abba3d2f29b998b6e35a025a99c1b75c3ec20f1ef66", 1797667,
        "e06c410ffa1b98cb16eb3abba3d2f29b998b6e35a025a99c1b75c3ec20f1ef66", 1797667,
        "cb4cb25072bc02cc46fccd5c561ebf1c4bd396d31afdd03a9963ed0a0b9fd03d", 2076279,
        "1eaf3683349931f195c819dee48d813f4eba2f8313331efff32b21342808f737", 626374,
    ),
    FrozenCell(
        "IMG-8", "24ba6a88-6889-4704-b48c-3fe31c352b42",
        "1442b86abde431d87d38dbe63cef710769e47f73a589cdc25be44cbd9c90df63", 1721489,
        "1442b86abde431d87d38dbe63cef710769e47f73a589cdc25be44cbd9c90df63", 1721489,
        "245893b05d4f84932c44a7fe6185cab170549d2ad25832457d9f4541c6f8dc1d", 2003923,
        "2f1951394a439345f635e87d55343e57f93309efd1908edced840c79ea8fc677", 601685,
    ),
    FrozenCell(
        "IMG-9", "3d92e342-ff7f-4ae8-9af6-9d778f42270f",
        "a5a3663ebc81bbaa8ebbba8fb034cc5b75bf664b10d8297b4de4815c8db77b94", 4463647,
        "630dacb228ca24bdce56c4e4e389411e7f54c971d54e546fea5127a6be8268c0", 2886110,
        "e3a3a386a12b992865c28c937980c93f4be5cb77e45de1299837868d24cd0e70", 2954310,
        "64bd57d76a3dcfcc97844fe71a6d59d6be34ec1e24abc22d779bd1ea4a92e2a6", 997150,
    ),
    FrozenCell(
        "IMG-11", "0e8faaa6-647b-4e8b-86e5-a8ad133d19ab",
        "3239eaebc85a83de59acf4d13f2d068baaa9c61324da84b51ae5d2bc08ea56d1", 5146489,
        "f9ed38e3b563a4fc0dce23a72f8fca4b814eb0edaa85022e6a84eb39caf71476", 2354690,
        "3e7b40381370f09f08712d9b62a82fc6943eb4a42334ea312bdc728f258d99ca", 2788554,
        "bf42822ab5ece79dc717cdfe5631272ca4ff1b7ebae3018bb17a4dc5bb22c373", 911645,
    ),
)


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


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FreezeViolation("missing file: {}".format(path)) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FreezeViolation("malformed JSON: {}".format(path)) from error


def _record_check(checks: List[dict], name: str, actual: Any, expected: Any) -> None:
    passed = actual == expected
    checks.append({"check": name, "actual": actual, "expected": expected, "pass": passed})
    if not passed:
        raise FreezeViolation("{}: expected {!r}, got {!r}".format(name, expected, actual))


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise FreezeViolation("non-finite value cannot be emitted")
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False))


def _manifest_cells(manifest: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    rows = manifest.get("cells")
    if not isinstance(rows, list):
        raise FreezeViolation("expected-manifest cells block is missing")
    selected = {
        str(row.get("image")): row
        for row in rows
        if isinstance(row, dict) and row.get("arm") == "B" and row.get("seed") == SEED
    }
    if tuple(image for image in IMAGES if image in selected) != IMAGES or len(selected) != 6:
        raise FreezeViolation("expected-manifest ctla1 B cohort is not the frozen six images")
    return selected


def _ar1_rows(index: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    rows = index.get("files")
    if not isinstance(rows, list) or len(rows) != 349:
        raise FreezeViolation("AR1 artifact-index must contain exactly 349 file rows")
    result: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise FreezeViolation("malformed AR1 artifact-index row")
        logical = str(row["path"])
        if logical in result:
            raise FreezeViolation("duplicate AR1 artifact-index path: " + logical)
        result[logical] = row
    return result


def _pin_for_stage(
    cell: FrozenCell,
    stage: str,
    manifest_cell: Mapping[str, Any],
    index_rows: Mapping[str, Mapping[str, Any]],
) -> FilePin:
    if stage == "O1":
        filename, sha, byte_count, fmt = "O1_postwash.png", cell.o1_sha256, cell.o1_bytes, "PNG"
    elif stage == "OR":
        filename, sha, byte_count, fmt = "OR_postresample.png", cell.or_sha256, cell.or_bytes, "PNG"
    elif stage == "O2":
        filename, sha, byte_count, fmt = "O2_precamera.png", cell.o2_sha256, cell.o2_bytes, "PNG"
    elif stage == "O5":
        filename, sha, byte_count, fmt = "O5_final.jpg", cell.o5_sha256, cell.o5_bytes, "JPEG"
    else:
        raise FreezeViolation("unknown frozen stage: " + stage)

    if stage == "O5":
        logical = "round-4d-ar1/arms/A0/{}/{}".format(cell.job, filename)
        row = index_rows.get(logical)
        if not isinstance(row, Mapping):
            raise FreezeViolation("O5 is missing from AR1 artifact-index: " + logical)
        pixel_sha = row.get("pixel_sha256")
        if row.get("sha256") != sha or row.get("bytes") != byte_count:
            raise FreezeViolation("frozen O5 pin disagrees with AR1 artifact-index: " + logical)
    else:
        logical = "round-4d-1a/checkpoints/{}/{}".format(cell.job, filename)
        files = manifest_cell.get("files")
        if not isinstance(files, Mapping):
            raise FreezeViolation("manifest files block is missing for " + cell.image)
        pixel_sha = files.get(filename)

    if not isinstance(pixel_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", pixel_sha):
        raise FreezeViolation("invalid pixel pin for " + logical)
    return FilePin(
        logical_id="{}:{}".format(cell.image, stage),
        image=cell.image,
        job=cell.job,
        seed=SEED,
        stage=stage,
        path=logical,
        sha256=sha,
        pixel_sha256=pixel_sha,
        bytes=byte_count,
        format=fmt,
    )


def expected_file_pins(root: Path = ROOT, verify_bytes: bool = True) -> Tuple[List[FilePin], List[dict]]:
    """Resolve the exact 24 files and optionally verify every on-disk byte/pixel pin."""
    checks: List[dict] = []
    for relative, expected in FROZEN_AUTHORITY_PINS.items():
        authority = root / relative
        actual = _sha256(authority) if authority.is_file() else None
        _record_check(checks, "authority sha256 " + relative, actual, expected)

    manifest = _load_json(root / EXPECTED_MANIFEST_PATH.relative_to(ROOT))
    index = _load_json(root / AR1_INDEX_PATH.relative_to(ROOT))
    if not isinstance(manifest, Mapping) or not isinstance(index, Mapping):
        raise FreezeViolation("authority manifests must be JSON objects")
    manifest_cells = _manifest_cells(manifest)
    index_rows = _ar1_rows(index)

    pins: List[FilePin] = []
    for cell in FROZEN_CELLS:
        _record_check(checks, cell.image + " manifest job", manifest_cells[cell.image].get("job"), cell.job)
        for stage in STAGES:
            pin = _pin_for_stage(cell, stage, manifest_cells[cell.image], index_rows)
            pins.append(pin)
            if verify_bytes:
                path = root / pin.path
                _record_check(checks, pin.logical_id + " exists", path.is_file(), True)
                _record_check(checks, pin.logical_id + " byte count", path.stat().st_size, pin.bytes)
                _record_check(checks, pin.logical_id + " byte sha256", _sha256(path), pin.sha256)
                _record_check(checks, pin.logical_id + " pixel sha256", _pixel_sha256(path), pin.pixel_sha256)
                with Image.open(path) as image:
                    _record_check(checks, pin.logical_id + " format", image.format, pin.format)

    _record_check(checks, "graded file count", len(pins), LOGICAL_CALL_BUDGET)
    _record_check(checks, "logical id uniqueness", len({pin.logical_id for pin in pins}), len(pins))
    return pins, checks


def file_pin_records(pins: Sequence[FilePin]) -> List[dict]:
    return [asdict(pin) for pin in pins]


def ledger_contract(pins: Sequence[FilePin]) -> dict:
    """Return the frozen, operator-facing ledger contract without writing a file."""
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "vendor": VENDOR,
        "model": MODEL,
        "version": MODEL_VERSION,
        "seed": SEED,
        "grade_session_id": "one shared UUID for all 24 fresh calls",
        "call_cap": CALL_CAP,
        "logical_call_budget": LOGICAL_CALL_BUDGET,
        "reserve_calls": RESERVE_CALLS,
        "raw_response_rule": "response.raw is the complete Hive response object; scores are re-read from it",
        "call_row_required_fields": [
            "logical_id", "image", "job", "seed", "stage", "file",
            "attempt_number", "grade_session_id", "submitted_sha256", "task_id", "response",
        ],
        "response_required_fresh_fields": {
            "cache_hit": False,
            "provider_calls": 1,
            "vendor": VENDOR,
            "mode": "real",
            "requested_mode": "real",
            "mock": False,
            "session_usage.cap": CALL_CAP,
        },
        "file_pins": file_pin_records(pins),
    }


def _is_finite_probability(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _normalized_source_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _c2pa_record(output: Mapping[str, Any], errors: List[str]) -> dict:
    algorithmic = output.get("algorithmic_tags")
    if algorithmic is None:
        return {
            "present": False,
            "value": None,
            "actions_digital_source_type": [],
            "denylist_matches": [],
        }
    if not isinstance(algorithmic, Mapping):
        errors.append("raw output[0].algorithmic_tags is malformed")
        return {
            "present": False,
            "value": None,
            "actions_digital_source_type": [],
            "denylist_matches": [],
        }
    c2pa = algorithmic.get("c2pa")
    if c2pa is None or c2pa == {}:
        return {
            "present": False,
            "value": None if c2pa is None else {},
            "actions_digital_source_type": [],
            "denylist_matches": [],
        }
    if not isinstance(c2pa, Mapping):
        errors.append("raw output[0].algorithmic_tags.c2pa is malformed")
        return {
            "present": True,
            "value": c2pa,
            "actions_digital_source_type": [],
            "denylist_matches": [],
        }

    raw_actions = c2pa.get("actions_digital_source_type")
    actions: List[str] = []
    if raw_actions is None:
        pass
    elif isinstance(raw_actions, str) and raw_actions.strip():
        actions = [raw_actions.strip()]
    elif (
        isinstance(raw_actions, list)
        and raw_actions
        and all(isinstance(item, str) and item.strip() for item in raw_actions)
    ):
        actions = [item.strip() for item in raw_actions]
    else:
        errors.append("C2PA actions_digital_source_type is malformed")

    deny_normalized = {value.lower(): value for value in EXPLICIT_C2PA_DENY_VALUES}
    matches = [value for value in actions if value.lower() in deny_normalized]
    return {
        "present": True,
        "value": c2pa,
        "actions_digital_source_type": actions,
        "denylist_matches": matches,
    }


def parse_hive_raw(raw: Any) -> dict:
    """Validate v3 response integrity and extract unrounded frozen-axis scores."""
    errors: List[str] = []
    if not isinstance(raw, Mapping):
        return {"valid": False, "errors": ["response.raw is not an object"]}

    task_id = raw.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        errors.append("raw task_id is missing")
    if raw.get("model") != MODEL:
        errors.append("raw model mismatch")
    if raw.get("version") != MODEL_VERSION:
        errors.append("raw version mismatch")

    output_rows = raw.get("output")
    output: Mapping[str, Any] = {}
    if not isinstance(output_rows, list) or not output_rows or not isinstance(output_rows[0], Mapping):
        errors.append("raw output[0] is missing or malformed")
    else:
        output = output_rows[0]
    classes = output.get("classes") if output else None
    scores: Dict[str, float] = {}
    if not isinstance(classes, list):
        errors.append("raw output[0].classes is missing or malformed")
    else:
        for index, row in enumerate(classes):
            if not isinstance(row, Mapping):
                errors.append("raw class row {} is malformed".format(index))
                continue
            name, value = row.get("class"), row.get("value")
            if not isinstance(name, str) or not name:
                errors.append("raw class row {} has an invalid name".format(index))
                continue
            if name in scores:
                errors.append("raw class {} is duplicated".format(name))
                continue
            if not _is_finite_probability(value):
                errors.append("raw class {} has an invalid probability".format(name))
                continue
            scores[name] = float(value)

    ai = scores.get("ai_generated")
    not_ai = scores.get("not_ai_generated")
    deepfake = scores.get("deepfake")
    if ai is None:
        errors.append("raw ai_generated class is missing")
    if not_ai is None:
        errors.append("raw not_ai_generated class is missing")
    if deepfake is None:
        errors.append("raw deepfake class is missing")
    if ai is not None and not_ai is not None and abs(ai + not_ai - 1.0) > SUM_TOLERANCE:
        errors.append("ai_generated + not_ai_generated is outside the 1e-3 sum tolerance")

    source_scores = {
        name: value for name, value in scores.items() if name not in NON_SOURCE_CLASSES
    }
    if "none" not in source_scores:
        errors.append("raw source-family classes are missing none")
    if source_scores and abs(sum(source_scores.values()) - 1.0) > SUM_TOLERANCE:
        errors.append("source-family scores including none are outside the 1e-3 sum tolerance")
    flux_scores = [
        value
        for name, value in source_scores.items()
        if "flux" in _normalized_source_key(name) or "auraflow" in _normalized_source_key(name)
    ]
    if not flux_scores:
        errors.append("raw source-family classes contain no Flux/AuraFlow key")
    flux_family = max(flux_scores) if flux_scores else None

    c2pa = _c2pa_record(output, errors)
    return {
        "valid": not errors,
        "errors": errors,
        "task_id": task_id if isinstance(task_id, str) else None,
        "ai": ai,
        "flux_family": flux_family,
        "deepfake": deepfake,
        "source_scores": source_scores,
        "c2pa": c2pa,
    }


def _uuid_is_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError):
        return False


def _exact_int(value: Any, expected: Optional[int] = None) -> bool:
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return expected is None or value == expected


def _row_identity_errors(row: Mapping[str, Any], pin: FilePin, session_id: str) -> List[str]:
    errors: List[str] = []
    expected = {
        "logical_id": pin.logical_id,
        "image": pin.image,
        "job": pin.job,
        "seed": pin.seed,
        "stage": pin.stage,
        "submitted_sha256": pin.sha256,
        "grade_session_id": session_id,
    }
    for field, value in expected.items():
        if row.get(field) != value:
            errors.append("{} mismatch".format(field))
    if row.get("file") != asdict(pin):
        errors.append("file pin record mismatch")
    if not _exact_int(row.get("attempt_number"), 1):
        errors.append("attempt_number must be 1")
    return errors


def _fresh_response_errors(response: Any, pin: FilePin) -> List[str]:
    if not isinstance(response, Mapping):
        return ["response is not an object"]
    errors: List[str] = []
    exact = {
        "image_sha256": pin.sha256,
        "vendor": VENDOR,
        "mode": "real",
        "requested_mode": "real",
        "mock": False,
        "cache_hit": False,
    }
    for field, value in exact.items():
        if response.get(field) != value or (
            isinstance(value, bool) and response.get(field) is not value
        ):
            errors.append("response.{} mismatch".format(field))
    if not _exact_int(response.get("provider_calls"), 1):
        errors.append("response.provider_calls must be exactly 1")
    usage = response.get("session_usage")
    if not isinstance(usage, Mapping):
        errors.append("response.session_usage is missing")
    else:
        if not _exact_int(usage.get("cap"), CALL_CAP):
            errors.append("response.session_usage.cap must be 40")
        if not _exact_int(usage.get("vendor_calls")):
            errors.append("response.session_usage.vendor_calls must be an integer")
    return errors


def validate_ledger(ledger: Any, pins: Sequence[FilePin]) -> dict:
    """Validate an S1 ledger. File/cohort identity mismatches raise as tamper.

    Provider/provenance/response defects are retained as per-file or global
    fail-closed findings so the raw measurement record remains reportable.
    """
    if not isinstance(ledger, Mapping):
        raise FreezeViolation("ledger root must be an object")
    root_exact = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "vendor": VENDOR,
        "model": MODEL,
        "version": MODEL_VERSION,
        "seed": SEED,
        "call_cap": CALL_CAP,
        "logical_call_budget": LOGICAL_CALL_BUDGET,
        "reserve_calls": RESERVE_CALLS,
    }
    for field, expected in root_exact.items():
        if ledger.get(field) != expected:
            raise FreezeViolation("ledger {} mismatch".format(field))
    session_id = ledger.get("grade_session_id")
    if not _uuid_is_valid(session_id):
        raise FreezeViolation("ledger grade_session_id must be one UUID")
    if ledger.get("file_pins") != file_pin_records(pins):
        raise FreezeViolation("ledger file_pins do not exactly match the frozen 24-file set")

    calls = ledger.get("calls")
    if not isinstance(calls, list) or len(calls) != LOGICAL_CALL_BUDGET:
        raise FreezeViolation("ledger must contain exactly 24 call rows")
    expected_ids = [pin.logical_id for pin in pins]
    actual_ids = [row.get("logical_id") if isinstance(row, Mapping) else None for row in calls]
    if actual_ids != expected_ids:
        raise FreezeViolation("ledger call order/identity does not match the frozen file order")

    analyses: List[dict] = []
    task_to_rows: Dict[str, List[int]] = {}
    grade_to_rows: Dict[str, List[int]] = {}
    usage_values: List[int] = []
    for index, (row, pin) in enumerate(zip(calls, pins)):
        if not isinstance(row, Mapping):
            raise FreezeViolation("ledger call row {} is not an object".format(index))
        identity_errors = _row_identity_errors(row, pin, str(session_id))
        if identity_errors:
            raise FreezeViolation("{}: {}".format(pin.logical_id, "; ".join(identity_errors)))

        response = row.get("response")
        errors = _fresh_response_errors(response, pin)
        raw = response.get("raw") if isinstance(response, Mapping) else None
        parsed = parse_hive_raw(raw)
        errors.extend(parsed.get("errors", []))

        row_task = row.get("task_id")
        if not isinstance(row_task, str) or not row_task:
            errors.append("row task_id is missing")
        elif row_task != parsed.get("task_id"):
            errors.append("row task_id does not equal raw task_id")
        else:
            task_to_rows.setdefault(row_task, []).append(index)

        if isinstance(response, Mapping):
            grade_id = response.get("grade_id")
            if not isinstance(grade_id, str) or not grade_id:
                errors.append("response.grade_id is missing")
            else:
                grade_to_rows.setdefault(grade_id, []).append(index)
            usage = response.get("session_usage")
            if isinstance(usage, Mapping) and _exact_int(usage.get("vendor_calls")):
                usage_values.append(int(usage["vendor_calls"]))

        ai = parsed.get("ai")
        flux = parsed.get("flux_family")
        deepfake = parsed.get("deepfake")
        c2pa = parsed.get("c2pa", {})
        thresholds = None
        eligible = False
        if parsed.get("valid"):
            thresholds = {
                "ai": bool(ai <= AI_THRESHOLD),
                "flux_family": bool(flux <= FLUX_THRESHOLD),
                "deepfake": bool(deepfake <= DEEPFAKE_THRESHOLD),
                "c2pa": not bool(c2pa.get("denylist_matches")),
            }
            eligible = all(thresholds.values())
        analyses.append({
            "logical_id": pin.logical_id,
            "image": pin.image,
            "stage": pin.stage,
            "valid": not errors,
            "errors": errors,
            "scores": {"ai": ai, "flux_family": flux, "deepfake": deepfake},
            "threshold_pass": thresholds,
            "eligible": eligible if not errors else False,
            "c2pa": c2pa,
        })

    global_errors: List[str] = []
    for task_id, indexes in task_to_rows.items():
        if len(indexes) > 1:
            global_errors.append("reused raw task_id {}".format(task_id))
            for index in indexes:
                analyses[index]["valid"] = False
                analyses[index]["eligible"] = False
                analyses[index]["errors"].append("raw task_id is reused")
    for grade_id, indexes in grade_to_rows.items():
        if len(indexes) > 1:
            global_errors.append("reused grade_id {}".format(grade_id))
            for index in indexes:
                analyses[index]["valid"] = False
                analyses[index]["eligible"] = False
                analyses[index]["errors"].append("grade_id is reused")
    expected_usage = list(range(1, LOGICAL_CALL_BUDGET + 1))
    if sorted(usage_values) != expected_usage:
        global_errors.append("session_usage.vendor_calls values must be exactly 1..24")

    all_valid = not global_errors and all(row["valid"] for row in analyses)
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "all_valid": all_valid,
        "global_errors": global_errors,
        "valid_file_count": sum(1 for row in analyses if row["valid"]),
        "invalid_file_count": sum(1 for row in analyses if not row["valid"]),
        "files": analyses,
    }


def frozen_median(values: Sequence[float]) -> float:
    """Median with the v3 even-cohort rule: mean of 3rd and 4th for n=6."""
    ordered = sorted(float(value) for value in values)
    if not ordered or any(not math.isfinite(value) for value in ordered):
        raise FreezeViolation("median requires finite values")
    count = len(ordered)
    midpoint = count // 2
    if count % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def interpret_validation(validation: Mapping[str, Any]) -> dict:
    """Apply only S1 section 4, or fail closed when a file is invalid."""
    if validation.get("all_valid") is not True:
        return {
            "status": "FAIL_CLOSED",
            "reason": "one or more fresh-call provenance or Hive response checks failed",
            "metrics": None,
            "decisions": None,
            "invalid_files": [
                row.get("logical_id")
                for row in validation.get("files", [])
                if isinstance(row, Mapping) and not row.get("valid")
            ],
            "global_errors": list(validation.get("global_errors", [])),
        }

    rows = validation.get("files")
    if not isinstance(rows, list) or len(rows) != LOGICAL_CALL_BUDGET:
        raise FreezeViolation("validated file rows are incomplete")
    by_image: Dict[str, Dict[str, float]] = {image: {} for image in IMAGES}
    eligibility: List[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise FreezeViolation("validated file row is malformed")
        image, stage = row.get("image"), row.get("stage")
        score = row.get("scores", {}).get("ai") if isinstance(row.get("scores"), Mapping) else None
        if image not in by_image or stage not in STAGES or not _is_finite_probability(score):
            raise FreezeViolation("validated score matrix is malformed")
        by_image[str(image)][str(stage)] = float(score)
        eligibility.append({
            "logical_id": row.get("logical_id"),
            "threshold_pass": row.get("threshold_pass"),
            "eligible": row.get("eligible"),
        })
    if any(set(stages) != set(STAGES) for stages in by_image.values()):
        raise FreezeViolation("validated score matrix is incomplete")

    stage_medians = {
        stage: frozen_median([by_image[image][stage] for image in IMAGES])
        for stage in STAGES
    }
    per_cell = []
    for image in IMAGES:
        scores = by_image[image]
        per_cell.append({
            "image": image,
            "O1_ai": scores["O1"],
            "OR_ai": scores["OR"],
            "O2_ai": scores["O2"],
            "O5_ai": scores["O5"],
            "resample_delta": scores["OR"] - scores["O1"],
            "camera_value": scores["O2"] - scores["OR"],
            "finish_value": scores["O5"] - scores["O2"],
        })
    resample_delta = frozen_median([row["resample_delta"] for row in per_cell])
    camera_value = frozen_median([row["camera_value"] for row in per_cell])
    finish_value = frozen_median([row["finish_value"] for row in per_cell])
    wash_clear = stage_medians["O1"] <= AI_THRESHOLD
    delivered_clear = stage_medians["O5"] <= AI_THRESHOLD

    if wash_clear and camera_value <= STAGE_VALUE_CUTOFF:
        primary = "ladder_removal_or_decomposition"
    elif not wash_clear and stage_medians["O2"] <= AI_THRESHOLD:
        primary = "decompose_to_detection_essential_minimum"
    elif not wash_clear and stage_medians["O2"] > AI_THRESHOLD:
        primary = "pivot_to_wash_policy"
    else:
        primary = "not_specified_by_frozen_decision_table"

    return {
        "status": "INTERPRETED",
        "score_basis": "unrounded raw Hive class values",
        "metrics": {
            "stage_ai_medians": stage_medians,
            "wash_clear": wash_clear,
            "resample_delta": resample_delta,
            "camera_value": camera_value,
            "delivered_clear": delivered_clear,
            "finish_value": finish_value,
            "per_cell": per_cell,
            "file_eligibility": eligibility,
        },
        "decisions": {
            "primary_direction": primary,
            "delivered_action": "none" if delivered_clear else "abstention_review",
            "resample_action": "retain" if resample_delta >= STAGE_VALUE_CUTOFF else "dead_weight",
            "candidate_selected": False,
            "production_admission": False,
            "ar3_holdout_unchanged": True,
        },
    }


def validate_and_interpret(ledger: Any, pins: Sequence[FilePin]) -> dict:
    validation = validate_ledger(ledger, pins)
    return {
        "validation": validation,
        "interpretation": interpret_validation(validation),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--print-contract",
        action="store_true",
        help="print the exact offline ledger schema and 24 file pins",
    )
    modes.add_argument(
        "--validate-ledger",
        action="store_true",
        help="read only round-4d-s1/ledger-raw.json, validate, and interpret it",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    pins, checks = expected_file_pins(ROOT, verify_bytes=True)
    if args.print_contract:
        _print_json(ledger_contract(pins))
        return 0
    if args.validate_ledger:
        ledger = _load_json(LEDGER_PATH)
        result = validate_and_interpret(ledger, pins)
        result["ledger_path"] = LEDGER_PATH.relative_to(ROOT).as_posix()
        result["ledger_sha256"] = _sha256(LEDGER_PATH)
        _print_json(result)
        return 0 if result["validation"]["all_valid"] else 2
    _print_json({
        "round": ROUND_ID,
        "mode": "offline-pin-verification-only",
        "pass": True,
        "graded_file_count": len(pins),
        "check_count": len(checks),
        "network_calls": 0,
        "vendor_calls": 0,
    })
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FreezeViolation as error:
        print("S1 FREEZE VIOLATION: {}".format(error), file=sys.stderr)
        raise SystemExit(2)
