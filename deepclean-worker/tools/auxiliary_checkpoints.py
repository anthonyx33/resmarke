"""Lab-only auxiliary checkpoints independent of the strict O0-O5 contract."""

from pathlib import Path

from PIL import Image

from tools.checkpoint_capture import pixel_sha256


AUXILIARY_CHECKPOINTS = ("OR_postresample.png",)
AUXILIARY_CHECKPOINT_WHITELIST = AUXILIARY_CHECKPOINTS + ("O2_transfer.png",)


def save_auxiliary_checkpoint(checkpoint_dir, name, image):
    """Write one explicitly allowed auxiliary RGB PNG under a per-job directory."""
    if checkpoint_dir is None:
        return None
    if name not in AUXILIARY_CHECKPOINT_WHITELIST:
        return f"unexpected auxiliary checkpoint name: {name}"
    try:
        directory = Path(checkpoint_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / name).resolve()
        if target.parent != directory:
            return f"unsafe auxiliary checkpoint path: {name}"
        if isinstance(image, Image.Image):
            rgb = image.convert("RGB")
        else:
            rgb = Image.fromarray(image).convert("RGB")
        rgb.save(target, format="PNG")
        return None
    except Exception as exc:  # noqa: BLE001 - diagnostics must not crash delivery
        return f"{name}: {type(exc).__name__}: {exc}"


def build_auxiliary_manifest(checkpoint_dir, capture_requested=False, errors=None, include_transfer=False):
    """Return auxiliary status without changing the strict O0-O5 manifest."""
    collected = [str(error) for error in (errors or []) if error]
    if not capture_requested:
        return {"status": "off", "files": [], "errors": []}
    if checkpoint_dir is None:
        if not collected:
            collected.append("auxiliary checkpoint capture directory is not configured")
        return {"status": "error", "files": [], "errors": collected}

    files = []
    directory = Path(checkpoint_dir).resolve()
    expected = AUXILIARY_CHECKPOINT_WHITELIST if include_transfer else AUXILIARY_CHECKPOINTS
    for name in expected:
        path = (directory / name).resolve()
        if path.parent != directory:
            collected.append(f"unsafe auxiliary checkpoint path: {name}")
            continue
        if not path.is_file():
            collected.append(f"missing auxiliary checkpoint: {name}")
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
