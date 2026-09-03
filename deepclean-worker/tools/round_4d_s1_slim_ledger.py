#!/usr/bin/env python3
"""Offline-only builder for the frozen 4D S1-slim stage ledger.

This tool implements C8_MASTER_PROMPT_4D_S1_SLIM_STAGE_LEDGER.md.  It has no
grader, network client, image transformation, regeneration path, or random
number generation.  It verifies the 18 archived PNG inputs, validates an
operator-produced real-grade JSONL in frozen order, computes the frozen stage
statistics, and atomically publishes exactly three JSON artifacts.

With no arguments the CLI performs a read-only preflight.  ``--print-contract``
prints the 18-row operator contract.  ``--input`` validates and interprets a
raw JSONL, refusing to overwrite an existing output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
FREEZE_PATH = ROOT / "C8_MASTER_PROMPT_4D_S1_SLIM_STAGE_LEDGER.md"
DEFAULT_OUTPUT_DIR = ROOT / "round-4d-s1-slim"

SCHEMA_VERSION = "4d-s1-slim-ledger-v1"
ROUND_ID = "4D-S1-SLIM"
SEED = "lab-ctla1"
VENDOR = "g1"
MODEL = "hive/ai-generated-and-deepfake-content-detection"
MODEL_VERSION = "1"
LOGICAL_CALL_BUDGET = 18
AI_THRESHOLD = 0.45
FLUX_THRESHOLD = 0.30
DEEPFAKE_THRESHOLD = 0.10
MATERIAL_THRESHOLD = 0.05
SUM_TOLERANCE = 1e-3
IMAGES = ("IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11")
STAGES = ("O1", "OR", "O2")
STAGE_FILES = {
    "O1": "O1_postwash.png",
    "OR": "OR_postresample.png",
    "O2": "O2_precamera.png",
}

FROZEN_AUTHORITY_PINS = {
    "C8_MASTER_PROMPT_4D_S1_SLIM_STAGE_LEDGER.md":
        "2e7b83890033f7c065cbf4f9b0e47dce15f75375e768434b1ec4e224f9e543b0",
    "VENDOR_FREEZE_4D_1A.md":
        "02d9e0de66fc400369fa5e672be329b35a459c541d2614e470f2381221899d3a",
    "round-4d-1a/expected-manifest.json":
        "6d1c730c629fda80b04b742bc75423f2f4710802a6cabc330910aaff7739c76a",
    "round-remint-1-01/full-corpus/floors-1.01-live.json":
        "88d30d7a46dd16d7b7d9fd2c8ec7f8cee3cc1e18248dfd1dca80925f45f4d4db",
    "round-full-matrix/phase-b-detection-ledger.json":
        "9f4292df6b90c053b601c1f061e165244339ef31cf6b462970867077b0c0eaec",
}

# Vendor freeze v3 names trainedAlgorithmicMedia explicitly.  Normalization
# makes spelling separators/case immaterial while preserving the raw row.
C2PA_DENY_VALUES = frozenset({"trainedalgorithmicmedia"})


class FreezeViolation(RuntimeError):
    """The frozen pin, grade schema, call order, or decision contract failed."""


@dataclass(frozen=True)
class StagePin:
    logical_id: str
    order: int
    image: str
    job: str
    seed: str
    source_path: str
    source_sha256: str
    stage: str
    filename: str
    path: str
    sha256: str
    bytes: int
    width: int
    height: int
    format: str = "PNG"


@dataclass(frozen=True)
class FrozenCell:
    image: str
    job: str
    source_path: str
    source_sha256: str
    archived_o5_path: str
    archived_o5_sha256: str
    matrix_o5_path: str
    matrix_o5_sha256: str
    stages: Tuple[Tuple[str, str, int, int, int], ...]


FROZEN_CELLS = (
    FrozenCell(
        "IMG-5", "e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5",
        "round-remint-1-01/full-corpus/IMG-5_source.png",
        "91fffe56122550743c9c18da0bed78c89ca702cabb08ce125e626a89a67b0d6b",
        "round-remint-1-01/arms/A0-1250/e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5/O5_final.jpg",
        "68e8d3ffdf086185b8aa83d6e371a944eb26e17d3f48bf87b2ae97aea66d71fc",
        "round-full-matrix/A_IMG-5_lab-ctla1.jpg",
        "07bcc5ef616e3bb0cc10d68e2270775dc543840dbe042f4d02612b1c0bcc67c5",
        (
            ("O1", "266db4db24244927ca733a939beba2264117f95b2c487eb4dd0c8b095d419471", 6032219, 2048, 2048),
            ("OR", "ea0a479ebe25da5e31d26ba8ccde458683ef7a3234d3cf0341a487da83100a1c", 2516349, 1250, 1250),
            ("O2", "a5c1317008a4678099be228ef1af5dbb60f7120391249e3b6ec3237caacb3773", 2672542, 1250, 1250),
        ),
    ),
    FrozenCell(
        "IMG-6", "cfca4ae3-5400-4a2c-a025-53271e40aaa7",
        "round-remint-1-01/full-corpus/IMG-6_source.png",
        "57db03058e1ce49e15aff4a7b95f0d6d6e1e23660732aa1c54f991bec1ea567f",
        "round-remint-1-01/arms/A0-1250/cfca4ae3-5400-4a2c-a025-53271e40aaa7/O5_final.jpg",
        "6a6a7c767591fa1bd719e7f8886ebfce22d5ff7d9c595c97f2a9595ec5899e9b",
        "round-full-matrix/A_IMG-6_lab-ctla1.jpg",
        "0d23d2b9f3b3377c01ee4b40fbcfefec4af9a7abe6e4f09edf6dfd34dde45924",
        (
            ("O1", "44500fa1711bed7b267a5d533e64e7ecb5e69ad70af30cf735c2b2ea39fa74ce", 835418, 800, 800),
            ("OR", "44500fa1711bed7b267a5d533e64e7ecb5e69ad70af30cf735c2b2ea39fa74ce", 835418, 800, 800),
            ("O2", "2bb85894c6cfd44459fcc02c70410d417f2fef529a9df7d672434fa7a5e9737c", 1106994, 800, 800),
        ),
    ),
    FrozenCell(
        "IMG-7", "f8b00791-fad5-4d51-a0ba-56a4b6bf98a7",
        "round-remint-1-01/full-corpus/IMG-7_source.png",
        "dd6b9afc1cc79c2a6dcd6a4e5fb9592e9838614876754e72f9bccbcd21f7a69b",
        "round-remint-1-01/arms/A0-1250/f8b00791-fad5-4d51-a0ba-56a4b6bf98a7/O5_final.jpg",
        "1eaf3683349931f195c819dee48d813f4eba2f8313331efff32b21342808f737",
        "round-full-matrix/A_IMG-7_lab-ctla1.jpg",
        "12f2bdc4f35876966f25e257ab71f4ee2fc6cea8a6cf2a7faab88126c447860a",
        (
            ("O1", "e06c410ffa1b98cb16eb3abba3d2f29b998b6e35a025a99c1b75c3ec20f1ef66", 1797667, 1080, 1080),
            ("OR", "e06c410ffa1b98cb16eb3abba3d2f29b998b6e35a025a99c1b75c3ec20f1ef66", 1797667, 1080, 1080),
            ("O2", "cb4cb25072bc02cc46fccd5c561ebf1c4bd396d31afdd03a9963ed0a0b9fd03d", 2076279, 1080, 1080),
        ),
    ),
    FrozenCell(
        "IMG-8", "24ba6a88-6889-4704-b48c-3fe31c352b42",
        "round-remint-1-01/full-corpus/IMG-8_source.png",
        "bb1325d84ba3dd2ac8162b5c9f3607932ae6d50a7b245c467024599ad4d2319c",
        "round-remint-1-01/arms/A0-1250/24ba6a88-6889-4704-b48c-3fe31c352b42/O5_final.jpg",
        "2f1951394a439345f635e87d55343e57f93309efd1908edced840c79ea8fc677",
        "round-full-matrix/A_IMG-8_lab-ctla1.jpg",
        "59a899714baff8ad19f69a0e0f285d62ac4c17bb62182e9881827068fbabf4dd",
        (
            ("O1", "1442b86abde431d87d38dbe63cef710769e47f73a589cdc25be44cbd9c90df63", 1721489, 1080, 1080),
            ("OR", "1442b86abde431d87d38dbe63cef710769e47f73a589cdc25be44cbd9c90df63", 1721489, 1080, 1080),
            ("O2", "245893b05d4f84932c44a7fe6185cab170549d2ad25832457d9f4541c6f8dc1d", 2003923, 1080, 1080),
        ),
    ),
    FrozenCell(
        "IMG-9", "3d92e342-ff7f-4ae8-9af6-9d778f42270f",
        "round-remint-1-01/full-corpus/IMG-9_source.png",
        "70df003ece40710c00ae4173237322e88125baa4993aa8a79a69b2beccee9b70",
        "round-remint-1-01/arms/A0-1250/3d92e342-ff7f-4ae8-9af6-9d778f42270f/O5_final.jpg",
        "64bd57d76a3dcfcc97844fe71a6d59d6be34ec1e24abc22d779bd1ea4a92e2a6",
        "round-full-matrix/A_IMG-9_lab-ctla1.jpg",
        "fcd0ed7d528c8a7b676a119017258cfdc80bddc8fbdbac3f227c293841302b56",
        (
            ("O1", "a5a3663ebc81bbaa8ebbba8fb034cc5b75bf664b10d8297b4de4815c8db77b94", 4463647, 1600, 1600),
            ("OR", "630dacb228ca24bdce56c4e4e389411e7f54c971d54e546fea5127a6be8268c0", 2886110, 1250, 1250),
            ("O2", "e3a3a386a12b992865c28c937980c93f4be5cb77e45de1299837868d24cd0e70", 2954310, 1250, 1250),
        ),
    ),
    FrozenCell(
        "IMG-11", "0e8faaa6-647b-4e8b-86e5-a8ad133d19ab",
        "round-remint-1-01/full-corpus/IMG-11_source.jpeg",
        "dc9bdc02806d2391a22f092f4539be875b06c0fdf049d67b4cc3ea843da0a8c8",
        "round-remint-1-01/arms/A0-1250/0e8faaa6-647b-4e8b-86e5-a8ad133d19ab/O5_final.jpg",
        "bf42822ab5ece79dc717cdfe5631272ca4ff1b7ebae3018bb17a4dc5bb22c373",
        "round-full-matrix/A_IMG-11_lab-ctla1.jpg",
        "1f19567a23f1cc17aad30b8e7f66313b95f0ef483ef82878f2b6090e25ff2068",
        (
            ("O1", "3239eaebc85a83de59acf4d13f2d068baaa9c61324da84b51ae5d2bc08ea56d1", 5146489, 2048, 2048),
            ("OR", "f9ed38e3b563a4fc0dce23a72f8fca4b814eb0edaa85022e6a84eb39caf71476", 2354690, 1250, 1250),
            ("O2", "3e7b40381370f09f08712d9b62a82fc6943eb4a42334ea312bdc728f258d99ca", 2788554, 1250, 1250),
        ),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FreezeViolation("missing file: {}".format(path)) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FreezeViolation("malformed JSON: {}".format(path)) from error


def _finite_probability(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _record_check(checks: List[dict], name: str, actual: Any, expected: Any) -> None:
    passed = actual == expected
    checks.append({"check": name, "actual": actual, "expected": expected, "pass": passed})
    if not passed:
        raise FreezeViolation("{}: expected {!r}, got {!r}".format(name, expected, actual))


def png_properties(path: Path) -> Tuple[int, int, int, int, int]:
    """Read the deterministic PNG signature/IHDR fields without an image library."""
    with path.open("rb") as handle:
        header = handle.read(33)
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise FreezeViolation("not a PNG: {}".format(path))
    length = struct.unpack(">I", header[8:12])[0]
    if length != 13 or header[12:16] != b"IHDR":
        raise FreezeViolation("PNG IHDR missing: {}".format(path))
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", header[16:29]
    )
    if (bit_depth, color_type, compression, filtering, interlace) != (8, 2, 0, 0, 0):
        raise FreezeViolation("PNG is not frozen 8-bit RGB non-interlaced: {}".format(path))
    return width, height, bit_depth, color_type, interlace


def expected_stage_pins() -> List[StagePin]:
    pins: List[StagePin] = []
    order = 1
    for cell in FROZEN_CELLS:
        for stage, sha, byte_count, width, height in cell.stages:
            filename = STAGE_FILES[stage]
            logical_path = "round-4d-1a/checkpoints/{}/{}".format(cell.job, filename)
            pins.append(StagePin(
                logical_id="{}:{}".format(cell.image, stage),
                order=order,
                image=cell.image,
                job=cell.job,
                seed=SEED,
                source_path=cell.source_path,
                source_sha256=cell.source_sha256,
                stage=stage,
                filename=filename,
                path=logical_path,
                sha256=sha,
                bytes=byte_count,
                width=width,
                height=height,
            ))
            order += 1
    return pins


def _matrix_grade_rows(root: Path) -> Dict[str, Mapping[str, Any]]:
    payload = _load_json(root / "round-full-matrix/phase-b-detection-ledger.json")
    rows = payload.get("rows") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        raise FreezeViolation("matrix detection ledger rows are missing")
    selected: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise FreezeViolation("matrix detection ledger contains a malformed row")
        if row.get("preset") == "Config A" and row.get("image") in IMAGES:
            image = str(row["image"])
            if image in selected:
                raise FreezeViolation("duplicate Config A matrix grade for " + image)
            selected[image] = row
    if set(selected) != set(IMAGES):
        raise FreezeViolation("matrix ledger does not contain the frozen six Config A grades")
    return selected


def preflight(root: Path = ROOT) -> Tuple[List[StagePin], List[dict], List[dict]]:
    """Verify all authority/source/stage/O5 bytes and resolve O5 reuse status."""
    checks: List[dict] = []
    for relative, expected in FROZEN_AUTHORITY_PINS.items():
        path = root / relative
        actual = sha256_file(path) if path.is_file() else None
        _record_check(checks, "authority sha256 " + relative, actual, expected)

    pins = expected_stage_pins()
    for pin in pins:
        source = root / pin.source_path
        _record_check(checks, pin.image + " source exists", source.is_file(), True)
        _record_check(checks, pin.image + " source sha256", sha256_file(source), pin.source_sha256)
        path = root / pin.path
        _record_check(checks, pin.logical_id + " exists", path.is_file(), True)
        _record_check(checks, pin.logical_id + " bytes", path.stat().st_size, pin.bytes)
        _record_check(checks, pin.logical_id + " sha256", sha256_file(path), pin.sha256)
        width, height, _, _, _ = png_properties(path)
        _record_check(checks, pin.logical_id + " dimensions", [width, height], [pin.width, pin.height])

    _record_check(checks, "18 stage pins", len(pins), LOGICAL_CALL_BUDGET)
    _record_check(checks, "stage logical ids unique", len({pin.logical_id for pin in pins}), len(pins))
    _record_check(checks, "frozen stage order", [pin.stage for pin in pins], list(STAGES) * 6)

    matrix_rows = _matrix_grade_rows(root)
    reuse: List[dict] = []
    for cell in FROZEN_CELLS:
        archived_path = root / cell.archived_o5_path
        matrix_path = root / cell.matrix_o5_path
        _record_check(checks, cell.image + " archived O5 exists", archived_path.is_file(), True)
        _record_check(
            checks, cell.image + " archived O5 sha256",
            sha256_file(archived_path), cell.archived_o5_sha256,
        )
        _record_check(checks, cell.image + " matrix O5 exists", matrix_path.is_file(), True)
        _record_check(
            checks, cell.image + " matrix O5 sha256",
            sha256_file(matrix_path), cell.matrix_o5_sha256,
        )
        grade = matrix_rows[cell.image]
        grade_exact = {
            "preset": "Config A",
            "image": cell.image,
            "image_sha256": cell.matrix_o5_sha256,
            "vendor": VENDOR,
            "mode": "real",
            "mock": False,
            "model": MODEL,
            "version": MODEL_VERSION,
            "vendor_error": None,
        }
        for field, expected in grade_exact.items():
            _record_check(checks, "{} matrix grade {}".format(cell.image, field), grade.get(field), expected)
        for field in ("ai_probability", "flux_family", "deepfake_probability"):
            if not _finite_probability(grade.get(field)):
                raise FreezeViolation("{} matrix grade {} is invalid".format(cell.image, field))
        match = cell.archived_o5_sha256 == cell.matrix_o5_sha256
        reuse.append({
            "image": cell.image,
            "archived_o5": {"path": cell.archived_o5_path, "sha256": cell.archived_o5_sha256},
            "matrix_o5": {"path": cell.matrix_o5_path, "sha256": cell.matrix_o5_sha256},
            "status": "hash_verified_reuse" if match else "o5_hash_mismatch",
            "o5_equivalent": "matrix_config_a_delivered_grade",
            "reused_grade": dict(grade),
        })
    return pins, checks, reuse


def contract(pins: Sequence[StagePin], reuse: Sequence[Mapping[str, Any]]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "seed": SEED,
        "vendor": VENDOR,
        "model": MODEL,
        "version": MODEL_VERSION,
        "logical_call_budget": LOGICAL_CALL_BUDGET,
        "call_order": [pin.logical_id for pin in pins],
        "required_grade_fields": [
            "logical_id", "image", "job", "seed", "source", "stage", "file",
            "attempt_number", "submitted_sha256", "ai_probability",
            "deepfake_probability", "verdict", "sources", "flux_family",
            "top_source", "task_id", "model", "version", "vendor", "mode",
            "mock", "cache_hit", "provider_calls", "session_usage",
            "vendor_error", "c2pa",
        ],
        "freshness": {
            "attempt_number": 1,
            "mode": "real",
            "mock": False,
            "cache_hit": "false per unique byte stream; true for verbatim byte-identical stage pairs",
            "provider_calls": "1 per unique byte stream; 0 for byte-identical stage pairs",
            "task_ids": "unique per unique byte stream; byte-identical pairs copy the first",
            "session_usage.vendor_calls": "advances by one per fresh submission; repeats on byte-identical pairs",
        },
        "vendor_call_budget": len({pin.sha256 for pin in pins}),
        "file_pins": [asdict(pin) for pin in pins],
        "o5_reuse": list(reuse),
    }


def read_grade_jsonl(path: Path) -> List[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, UnicodeDecodeError) as error:
        raise FreezeViolation("cannot read grade JSONL: {}".format(path)) from error
    if len(lines) != LOGICAL_CALL_BUDGET or any(not line.strip() for line in lines):
        raise FreezeViolation("grade JSONL must contain exactly 18 non-blank lines")
    rows: List[dict] = []
    for index, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise FreezeViolation("malformed grade JSONL line {}".format(index)) from error
        if not isinstance(row, dict):
            raise FreezeViolation("grade JSONL line {} is not an object".format(index))
        rows.append(row)
    return rows


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _c2pa_deny_matches(value: Any) -> List[str]:
    if isinstance(value, str):
        if value.lower().startswith("absent"):
            return []
        raise FreezeViolation("C2PA string must explicitly report absence")
    if not isinstance(value, Mapping):
        raise FreezeViolation("C2PA record is missing or malformed")
    actions = value.get("actions_digital_source_type")
    if actions is None:
        nested = value.get("value")
        if isinstance(nested, Mapping):
            actions = nested.get("actions_digital_source_type")
    if actions is None:
        return []
    if isinstance(actions, str) and actions.strip():
        values = [actions.strip()]
    elif isinstance(actions, list) and all(isinstance(item, str) and item.strip() for item in actions):
        values = [item.strip() for item in actions]
    else:
        raise FreezeViolation("C2PA actions_digital_source_type is malformed")
    return [value for value in values if _normalized_key(value) in C2PA_DENY_VALUES]


def _require_exact(row: Mapping[str, Any], field: str, expected: Any, logical_id: str) -> None:
    if field not in row:
        raise FreezeViolation("{}: {} is missing".format(logical_id, field))
    actual = row.get(field)
    if actual != expected or (isinstance(expected, bool) and actual is not expected):
        raise FreezeViolation("{}: {} mismatch".format(logical_id, field))


def validate_grade_rows(rows: Sequence[Mapping[str, Any]], pins: Sequence[StagePin]) -> List[dict]:
    """Validate the exact 18 real rows and return normalized, verbatim-preserving rows."""
    if len(rows) != LOGICAL_CALL_BUDGET:
        raise FreezeViolation("exactly 18 grade rows are required")
    task_ids: Set[str] = set()
    seen_rows: List[Mapping[str, Any]] = []
    seen_sha: Dict[str, int] = {}
    last_fresh_calls: Optional[int] = None
    usage_values: List[int] = []
    usage_caps: Set[int] = set()
    normalized: List[dict] = []

    for row, pin in zip(rows, pins):
        if not isinstance(row, Mapping):
            raise FreezeViolation("{} grade row is not an object".format(pin.logical_id))
        logical_id = pin.logical_id
        exact = {
            "logical_id": logical_id,
            "image": pin.image,
            "job": pin.job,
            "seed": pin.seed,
            "source": {"path": pin.source_path, "sha256": pin.source_sha256},
            "stage": pin.stage,
            "file": asdict(pin),
            "attempt_number": 1,
            "submitted_sha256": pin.sha256,
            "model": MODEL,
            "version": MODEL_VERSION,
            "vendor": VENDOR,
            "mode": "real",
            "mock": False,
            "vendor_error": None,
        }
        for field, expected in exact.items():
            _require_exact(row, field, expected, logical_id)

        first_index = seen_sha.get(pin.sha256)
        if first_index is None:
            # Fresh byte stream: the only row allowed to buy a vendor call.
            _require_exact(row, "cache_hit", False, logical_id)
            _require_exact(row, "provider_calls", 1, logical_id)
        else:
            # Freeze Addendum 1 item 4: byte-identical stage pair recorded
            # verbatim from the first grade without a new vendor call.
            _require_exact(row, "cache_hit", True, logical_id)
            _require_exact(row, "provider_calls", 0, logical_id)
            first_row = seen_rows[first_index]
            for field in ("ai_probability", "deepfake_probability", "flux_family",
                          "verdict", "top_source", "sources"):
                if row.get(field) != first_row.get(field):
                    raise FreezeViolation("{}: duplicate byte-stream row must copy {} verbatim".format(logical_id, field))

        for field in ("ai_probability", "deepfake_probability", "flux_family"):
            if not _finite_probability(row.get(field)):
                raise FreezeViolation("{}: {} is not a finite probability".format(logical_id, field))
        if not isinstance(row.get("verdict"), str) or not row["verdict"].strip():
            raise FreezeViolation("{}: verdict is missing".format(logical_id))
        if not isinstance(row.get("top_source"), str) or not row["top_source"].strip():
            raise FreezeViolation("{}: top_source is missing".format(logical_id))

        sources = row.get("sources")
        if not isinstance(sources, Mapping) or not sources:
            raise FreezeViolation("{}: sources are missing".format(logical_id))
        source_scores: Dict[str, float] = {}
        for name, score in sources.items():
            if not isinstance(name, str) or not name or not _finite_probability(score):
                raise FreezeViolation("{}: malformed source score".format(logical_id))
            source_scores[name] = float(score)
        if not any(_normalized_key(name) == "none" for name in source_scores):
            pass  # freeze addendum 1: real Hive v3 payloads carry no none class
        if abs(sum(source_scores.values()) - 1.0) > SUM_TOLERANCE:
            raise FreezeViolation("{}: source scores are outside the 1e-3 sum tolerance".format(logical_id))
        flux_scores = [
            value for name, value in source_scores.items()
            if "flux" in _normalized_key(name) or "auraflow" in _normalized_key(name)
        ]
        if not flux_scores:
            raise FreezeViolation("{}: sources contain no Flux/AuraFlow key".format(logical_id))
        if abs(max(flux_scores) - float(row["flux_family"])) > 1e-12:
            raise FreezeViolation("{}: flux_family is not the source-family maximum".format(logical_id))

        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise FreezeViolation("{}: task_id is missing".format(logical_id))
        if first_index is None:
            if task_id in task_ids:
                raise FreezeViolation("{}: task_id is reused".format(logical_id))
            task_ids.add(task_id)
        else:
            expected_task = seen_rows[first_index].get("task_id")
            if task_id != expected_task:
                raise FreezeViolation("{}: duplicate byte-stream row must copy the first task_id".format(logical_id))

        usage = row.get("session_usage")
        if not isinstance(usage, Mapping):
            raise FreezeViolation("{}: session_usage is missing".format(logical_id))
        vendor_calls, cap = usage.get("vendor_calls"), usage.get("cap")
        if not isinstance(vendor_calls, int) or isinstance(vendor_calls, bool):
            raise FreezeViolation("{}: session_usage.vendor_calls is invalid".format(logical_id))
        if not isinstance(cap, int) or isinstance(cap, bool) or cap < LOGICAL_CALL_BUDGET:
            raise FreezeViolation("{}: session_usage.cap is invalid".format(logical_id))
        if first_index is None:
            if last_fresh_calls is not None and vendor_calls != last_fresh_calls + 1:
                raise FreezeViolation("{}: vendor_calls must advance by one per fresh submission".format(logical_id))
            last_fresh_calls = vendor_calls
        else:
            expected_calls = seen_rows[first_index].get("session_usage", {}).get("vendor_calls")
            if vendor_calls != expected_calls:
                raise FreezeViolation("{}: duplicate byte-stream row must copy the first vendor_calls".format(logical_id))
        usage_values.append(vendor_calls)
        usage_caps.add(cap)

        matches = _c2pa_deny_matches(row.get("c2pa"))
        if matches:
            raise FreezeViolation("{}: C2PA deny-list finding {}".format(logical_id, matches))

        normalized.append({
            "order": pin.order,
            "logical_id": logical_id,
            "raw_grade": dict(row),
            "scores": {
                "ai_probability": float(row["ai_probability"]),
                "flux_family": float(row["flux_family"]),
                "deepfake_probability": float(row["deepfake_probability"]),
            },
            "full_v3_pass": (
                float(row["ai_probability"]) <= AI_THRESHOLD
                and float(row["flux_family"]) <= FLUX_THRESHOLD
                and float(row["deepfake_probability"]) <= DEEPFAKE_THRESHOLD
            ),
        })
        seen_rows.append(row)
        seen_sha.setdefault(pin.sha256, len(seen_rows) - 1)

    if len(usage_caps) != 1:
        raise FreezeViolation("session_usage.cap changed within the 18-call leg")
    return normalized


def frozen_median(values: Sequence[float]) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered or any(not math.isfinite(value) for value in ordered):
        raise FreezeViolation("median requires finite values")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def materiality(gains: Sequence[Tuple[str, float]], passing_images: Set[str]) -> dict:
    if len(gains) != 6 or {image for image, _ in gains} != set(IMAGES):
        raise FreezeViolation("materiality requires the frozen six-cell cohort")
    values = [float(value) for _, value in gains]
    if any(not math.isfinite(value) for value in values):
        raise FreezeViolation("materiality gains must be finite")
    median_gain = frozen_median(values)
    magnitude_material = abs(median_gain) + 1e-15 >= MATERIAL_THRESHOLD
    non_negative = sum(1 for value in values if value >= 0.0)
    passing_veto = [image for image, value in gains if image in passing_images and value < 0.0]
    consistent = non_negative >= 4 and not passing_veto
    return {
        "median_gain": median_gain,
        "absolute_threshold": MATERIAL_THRESHOLD,
        "magnitude_material": magnitude_material,
        "non_negative_count": non_negative,
        "directionally_consistent": non_negative >= 4,
        "passing_cell_veto": passing_veto,
        "material": magnitude_material and consistent,
        "mixed_signs": magnitude_material and not consistent,
    }


def _verified_o5_scores(reuse: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, dict], Set[str]]:
    by_image: Dict[str, dict] = {}
    passing: Set[str] = set()
    mismatches: List[str] = []
    for record in reuse:
        image = record.get("image")
        if image not in IMAGES:
            raise FreezeViolation("malformed O5 reuse record")
        if record.get("status") != "hash_verified_reuse":
            # Freeze Addendum 1: mismatch is informational; the matrix
            # Config A delivered grade is the frozen O5-equivalent.
            mismatches.append(str(image))
        if record.get("o5_equivalent") != "matrix_config_a_delivered_grade":
            raise FreezeViolation("{} O5 record has no frozen equivalent source".format(image))
        grade = record.get("reused_grade")
        if not isinstance(grade, Mapping):
            raise FreezeViolation("{} O5 record has no grade".format(image))
        for field in ("ai_probability", "flux_family", "deepfake_probability"):
            if not _finite_probability(grade.get(field)):
                raise FreezeViolation("{} verified O5 grade {} is invalid".format(image, field))
        normalized = {
            "ai_probability": float(grade["ai_probability"]),
            "flux_family": float(grade["flux_family"]),
            "deepfake_probability": float(grade["deepfake_probability"]),
        }
        by_image[str(image)] = normalized
        if (
            normalized["ai_probability"] <= AI_THRESHOLD
            and normalized["flux_family"] <= FLUX_THRESHOLD
            and normalized["deepfake_probability"] <= DEEPFAKE_THRESHOLD
        ):
            passing.add(str(image))
    if set(by_image) != set(IMAGES):
        raise FreezeViolation("O5 reuse does not cover the frozen six cells")
    return by_image, passing, mismatches


def compute_stage_deltas(validated: Sequence[Mapping[str, Any]], reuse: Sequence[Mapping[str, Any]]) -> dict:
    o5_scores, passing_images, o5_mismatches = _verified_o5_scores(reuse)
    by_image: Dict[str, Dict[str, float]] = {image: {} for image in IMAGES}
    for row in validated:
        raw = row.get("raw_grade")
        scores = row.get("scores")
        if not isinstance(raw, Mapping) or not isinstance(scores, Mapping):
            raise FreezeViolation("validated grade row is malformed")
        image, stage = raw.get("image"), raw.get("stage")
        if image not in by_image or stage not in STAGES:
            raise FreezeViolation("validated grade identity is malformed")
        by_image[str(image)][str(stage)] = float(scores["ai_probability"])
    if any(set(stages) != set(STAGES) for stages in by_image.values()):
        raise FreezeViolation("validated stage matrix is incomplete")

    per_cell: List[dict] = []
    resample_pairs: List[Tuple[str, float]] = []
    camera_pairs: List[Tuple[str, float]] = []
    for image in IMAGES:
        stage = by_image[image]
        resample_gain = stage["O1"] - stage["OR"]
        camera_gain = stage["OR"] - stage["O2"]
        resample_pairs.append((image, resample_gain))
        camera_pairs.append((image, camera_gain))
        per_cell.append({
            "image": image,
            "O1_ai": stage["O1"],
            "OR_ai": stage["OR"],
            "O2_ai": stage["O2"],
            "O5_ai": o5_scores[image]["ai_probability"],
            "resample_gain": resample_gain,
            "camera_gain": camera_gain,
            "o5_full_v3_pass": image in passing_images,
        })

    stage_medians = {
        stage: frozen_median([by_image[image][stage] for image in IMAGES])
        for stage in STAGES
    }
    o5_median = frozen_median([o5_scores[image]["ai_probability"] for image in IMAGES])
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "cohort": list(IMAGES),
        "score_basis": "operator-recorded unrounded real Hive g1 probabilities",
        "stage_ai_medians": dict(stage_medians, O5=o5_median),
        "wash_clear": stage_medians["O1"] <= AI_THRESHOLD,
        "o2_clear": stage_medians["O2"] <= AI_THRESHOLD,
        "delivered_clear": o5_median <= AI_THRESHOLD,
        "resample_gain": materiality(resample_pairs, passing_images),
        "camera_gain": materiality(camera_pairs, passing_images),
        "per_cell": per_cell,
        "o5_passing_images": sorted(passing_images, key=IMAGES.index),
        "o5_hash_mismatch_images": sorted(o5_mismatches, key=IMAGES.index),
    }


DECISION_TEXT = {
    "camera_removal": "Commission camera-ladder removal / minimum strength (AR2 quality gates govern any challenger)",
    "camera_decompose": "Commission camera sub-step decomposition to the minimum passing strength",
    "camera_stop": "Stop camera work; commission wash-policy / photo-naturalization / stage-order work",
    "camera_retain": "Retain the camera ladder (detection-essential); commission wash-policy / stage-1 encoding work",
    "camera_neutral": "Retain camera at minimum strength (neutral); commission wash-policy / resample-attribution work",
    "resample_retain": "Retain resample as detection-essential",
    "resample_dead": "Mark resample dead weight; exclude from future freezes unless AR2 passes without it",
    "mixed": "No universal change; a holdout-designed per-image policy is required before any routing",
}


def decide(metrics: Mapping[str, Any]) -> dict:
    wash_clear = metrics.get("wash_clear") is True
    o2_clear = metrics.get("o2_clear") is True
    camera = metrics.get("camera_gain")
    resample = metrics.get("resample_gain")
    if not isinstance(camera, Mapping) or not isinstance(resample, Mapping):
        raise FreezeViolation("stage metrics are malformed")

    mixed_stages = [
        name for name, value in (("resample", resample), ("camera", camera))
        if value.get("mixed_signs") is True
    ]
    if wash_clear and camera.get("material") is True:
        primary_id, primary = "wash_clear_camera_material", DECISION_TEXT["camera_retain"]
    elif wash_clear and camera.get("material") is not True:
        primary_id, primary = "wash_clear_camera_not_material", DECISION_TEXT["camera_removal"]
    elif not wash_clear and o2_clear and camera.get("material") is True:
        primary_id, primary = "wash_not_clear_o2_clear_camera_material", DECISION_TEXT["camera_decompose"]
    elif not wash_clear and o2_clear:
        primary_id, primary = "wash_not_clear_o2_clear_camera_not_material", DECISION_TEXT["camera_neutral"]
    elif not wash_clear and not o2_clear:
        primary_id, primary = "wash_not_clear_o2_not_clear", DECISION_TEXT["camera_stop"]
    else:
        raise FreezeViolation("measured combination is not covered by the frozen primary decision table")

    if resample.get("material") is True:
        resample_id, resample_text = "resample_gain_material", DECISION_TEXT["resample_retain"]
    else:
        resample_id, resample_text = "resample_not_material", DECISION_TEXT["resample_dead"]

    row = {
        "primary_condition": primary_id,
        "primary_decision": primary,
        "resample_condition": resample_id,
        "resample_decision": resample_text,
        "mixed_sign_stages": mixed_stages,
        "universal_change_decision": DECISION_TEXT["mixed"] if mixed_stages else primary,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "decision_row_count": 1,
        "decision": row,
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def atomic_publish(output_dir: Path, artifacts: Mapping[str, Any]) -> None:
    """Publish all artifacts with one deterministic directory rename."""
    expected_names = {"ledger-raw.json", "stage-deltas.json", "decision.json"}
    if set(artifacts) != expected_names:
        raise FreezeViolation("atomic publish requires exactly the three frozen artifacts")
    if output_dir.exists():
        raise FreezeViolation("overwrite refused: {}".format(output_dir))
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp_dir = parent / ("." + output_dir.name + ".tmp")
    if temp_dir.exists():
        raise FreezeViolation("stale atomic-write directory exists: {}".format(temp_dir))
    temp_dir.mkdir()
    try:
        for name in sorted(artifacts):
            path = temp_dir / name
            with path.open("xb") as handle:
                handle.write(_json_bytes(artifacts[name]))
                handle.flush()
                os.fsync(handle.fileno())
        os.rename(str(temp_dir), str(output_dir))
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(str(temp_dir))
        raise


def build_artifacts(
    input_path: Path,
    pins: Sequence[StagePin],
    reuse: Sequence[Mapping[str, Any]],
) -> Dict[str, dict]:
    raw_rows = read_grade_jsonl(input_path)
    validated = validate_grade_rows(raw_rows, pins)
    metrics = compute_stage_deltas(validated, reuse)
    decision = decide(metrics)
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND_ID,
        "seed": SEED,
        "vendor": VENDOR,
        "model": MODEL,
        "version": MODEL_VERSION,
        "logical_call_budget": LOGICAL_CALL_BUDGET,
        "input_jsonl_sha256": sha256_file(input_path),
        "input_rows_sha256": _json_sha256(raw_rows),
        "file_pins": [asdict(pin) for pin in pins],
        "o5_reuse": list(reuse),
        "rows": validated,
    }
    return {
        "ledger-raw.json": ledger,
        "stage-deltas.json": metrics,
        "decision.json": decision,
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--print-contract", action="store_true")
    modes.add_argument("--input", type=Path, help="operator-produced 18-row real-grade JSONL")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    pins, checks, reuse = preflight(ROOT)
    if args.print_contract:
        _print_json(contract(pins, reuse))
        return 0
    if args.input is not None:
        artifacts = build_artifacts(args.input, pins, reuse)
        atomic_publish(args.output_dir, artifacts)
        _print_json({
            "round": ROUND_ID,
            "status": "published",
            "output_dir": str(args.output_dir),
            "artifacts": sorted(artifacts),
            "vendor_calls": 0,
            "network_calls": 0,
        })
        return 0
    statuses = [record["status"] for record in reuse]
    _print_json({
        "round": ROUND_ID,
        "mode": "offline-preflight-only",
        "stage_pin_count": len(pins),
        "check_count": len(checks),
        "all_stage_pins_valid": all(row["pass"] for row in checks),
        "o5_hash_verified_reuse_count": statuses.count("hash_verified_reuse"),
        "o5_hash_mismatch_count": statuses.count("o5_hash_mismatch"),
        "o5_reuse_status": reuse,
        "decision_ready": all(record.get("reused_grade") is not None for record in reuse),
        "vendor_calls": 0,
        "network_calls": 0,
    })
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FreezeViolation as error:
        print("S1-SLIM FREEZE VIOLATION: {}".format(error), file=sys.stderr)
        raise SystemExit(2)
