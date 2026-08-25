"""Lab-only checkpoint path, PNG write, pixel hash, and manifest helpers."""

import hashlib
import re
import math
from pathlib import Path

from PIL import Image, ImageChops


EXPECTED_CHECKPOINTS = (
    "O0_source.png",
    "O1_postwash.png",
    "O2_precamera.png",
    "O3_stage1.png",
    "O4_preencode.png",
    "O5_final.png",
)

_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def lab_checkpoint_dir(base, job_id, lab_seed):
    """Return/create <base>/<job_id> only for a validated lab-seed job."""
    if not lab_seed or not base:
        return None
    job_segment = str(job_id)
    if not _SAFE_JOB_ID.fullmatch(job_segment):
        raise ValueError("job_id is unsafe for checkpoint capture")
    target = Path(base).expanduser().resolve() / job_segment
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_checkpoint(checkpoint_dir, name, image):
    """Write an RGB PNG explicitly under one per-job directory."""
    if checkpoint_dir is None:
        return None
    if name not in EXPECTED_CHECKPOINTS:
        return f"unexpected checkpoint name: {name}"
    try:
        directory = Path(checkpoint_dir)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        if isinstance(image, Image.Image):
            rgb = image.convert("RGB")
        else:
            rgb = Image.fromarray(image).convert("RGB")
        rgb.save(target, format="PNG")
        return None
    except Exception as exc:  # noqa: BLE001 - capture must not crash delivery
        return f"{name}: {type(exc).__name__}: {exc}"


def pixel_sha256(path):
    """Hash decoded RGB pixels plus dimensions (metadata/PNG bytes excluded)."""
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        digest = hashlib.sha256()
        digest.update(rgb.width.to_bytes(8, "big"))
        digest.update(rgb.height.to_bytes(8, "big"))
        digest.update(rgb.tobytes())
        return digest.hexdigest()


def build_checkpoint_manifest(checkpoint_dir, capture_requested=False, errors=None):
    """Return the report contract and make every missing O0..O5 explicit."""
    collected = [str(error) for error in (errors or []) if error]
    if not capture_requested:
        return {"status": "off", "files": [], "errors": []}
    if checkpoint_dir is None:
        if not collected:
            collected.append("checkpoint capture directory is not configured")
        return {"status": "error", "files": [], "errors": collected}

    files = []
    directory = Path(checkpoint_dir)
    for name in EXPECTED_CHECKPOINTS:
        path = directory / name
        if not path.is_file():
            collected.append(f"missing checkpoint: {name}")
            continue
        try:
            files.append({"name": name, "sha256": pixel_sha256(path)})
        except Exception as exc:  # noqa: BLE001
            collected.append(f"{name}: {type(exc).__name__}: {exc}")

    return {
        "status": "error" if collected else "captured",
        "files": files,
        "errors": list(dict.fromkeys(collected)),
    }


def compare_o2_determinism(first_path, second_path, same_hardware=True):
    """Apply the V12.3 exact-or-tolerance paired-control rule to O2 pixels."""
    with Image.open(first_path) as first_image, Image.open(second_path) as second_image:
        first = first_image.convert("RGB")
        second = second_image.convert("RGB")
        if first.size != second.size:
            return {"passed": False, "kind": "failed", "rms_lsb": None, "max_abs_lsb": None}
        exact = pixel_sha256(first_path) == pixel_sha256(second_path)
        if exact:
            return {"passed": True, "kind": "exact", "rms_lsb": 0.0, "max_abs_lsb": 0}
        difference = ImageChops.difference(first, second)
        histogram = difference.histogram()
        sample_count = first.width * first.height * 3
        squared = sum((index % 256) ** 2 * count for index, count in enumerate(histogram))
        rms = math.sqrt(squared / float(sample_count))
        max_abs = max(channel_max for _, channel_max in difference.getextrema())
        tolerated = bool(same_hardware and rms <= 0.1 and max_abs <= 1)
        return {
            "passed": tolerated,
            "kind": "tolerated" if tolerated else "failed",
            "rms_lsb": round(rms, 8),
            "max_abs_lsb": max_abs,
        }
