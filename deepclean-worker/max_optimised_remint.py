"""Max Optimised Re Mint -- quality-preserving SynthID removal.

The pivot from the two existing profiles:

  - Max Mint (full Qwen regeneration at adaptive_level 8) DOES remove SynthID
    but destroys quality -- the regen reinterprets the whole frame (grain, detail
    loss, "looks off") and the heavy `max` naturalization piles more grain on
    top. This is the death-spiral the user reported ("quality drastically
    declines after every minting").
  - Max ReMint (non-generative FFT reshape) preserves quality but CANNOT remove
    SynthID -- statistical reshaping only shuffles the model fingerprint, it does
    not break the watermark carrier. Proven dead by the source-attribution drift.

Max Optimised Re Mint takes the structurally correct path: **moderate-strength
diffusion regeneration** -- strong enough to break the SynthID carrier (every
pixel is reconstructed, which is the only known removal mechanism per the
remove-ai-watermarks invisible engine), but at a moderate adaptive_level and
with structure/edge preservation rather than free reinterpretation. Minimum
reliable regeneration = maximum quality preserved.

Three quality levers vs Max Mint:
  1. adaptive_level 4 (down from 8) -- less reinterpretation, same all-pixel
     reconstruction. `standard` already clears the identify oracle per
     SETUP_AND_TEST; level 8 was overkill.
  2. single VAE round-trip, original resolution preserved (no cap/restore
     resample loss beyond what the watermark's resolution-dependence requires).
  3. light `optimised` naturalization (subtle grain) instead of the heavy
     `max` profile whose 0.55 blur + jitter was itself a source of the grain.

Plus an unsharp-mask quality-restoration pass to recover perceived sharpness
the regeneration softened, a tight PSNR/SSIM quality gate (the
quality-preservation guarantee), and idempotent skip-if-already-processed so
re-minting a clean image does NOT re-run diffusion (kills the per-minting
death-spiral).

Honest oracle constraint (verified in remove-ai-watermarks.identify): SynthID
is a PIXEL watermark with no local decoder. `identify` can only verify the
metadata/sparkle signals -- it cannot confirm pixel-SynthID removal. So the
oracle gates the verifiable portion (C2PA/IPTC/sparkle), and pixel-SynthID is
reported honestly as "removed via regeneration, not locally verifiable" rather
than falsely claimed clean. No auto-calibrate loop: there is no local signal to
calibrate against, so we run once at the configured reliable level.
"""

import hashlib
import io
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from neural_texture import compare_images


# Workflow template -- same env contract as worker.TEMPLATE_PATH.
TEMPLATE_PATH = Path(
    os.environ.get("DEEPCLEAN_WORKFLOW", "/app/workflows/remarkee-max-v2.api.json")
)

# Lightweight provenance marker so re-minting an already-processed image can skip
# regeneration entirely (idempotency). Stored in the APPNATION/EXIF UserComment
# as a plain ASCII string -- no forged device metadata, just our own tag.
RESMARKE_MARKER = "ResMarke:processed:max-optimised-remint:v1"

DEFAULT_SETTINGS = {
    "enabled": True,
    "preset": "balanced",
    # Purification (regeneration) -- moderate, structure-preserving.
    "adaptive_level": 4,        # 4 = reliable removal, far less loss than max's 8
    "adaptive_level_min": 3,    # never go below this (lighter risks leaving SynthID)
    "adaptive_level_max": 6,    # never exceed this (heavier = quality loss)
    "process_cap": 1800,        # cap long edge; SynthID carrier is resolution-dependent
    "timeout": 280,             # per-run ComfyUI timeout (s)
    # Quality restoration (classical, non-generative -- does not re-add SynthID).
    "unsharp_radius": 1.2,
    "unsharp_percent": 35,      # subtle perceptual-sharpness recovery
    "unsharp_threshold": 2,
    # Quality gate -- the quality-preservation guarantee.
    "min_psnr_db": 28.0,
    "min_ssim": 0.90,
    # Idempotency.
    "skip_if_processed": True,
}


def is_max_optimised_remint(settings):
    return isinstance(settings, dict) and settings.get("mode") == "max-optimised-remint"


def normalize_max_optimised_remint_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = raw.get("max_optimised_remint") if isinstance(raw.get("max_optimised_remint"), dict) else {}
    cfg = dict(DEFAULT_SETTINGS)
    cfg["enabled"] = raw.get("mode") == "max-optimised-remint"
    preset = str(sub.get("preset", cfg["preset"]))
    cfg["preset"] = preset if preset in ("conservative", "balanced", "aggressive") else "balanced"
    if cfg["preset"] == "conservative":
        cfg["adaptive_level"] = 3
        cfg["unsharp_percent"] = 25
    elif cfg["preset"] == "aggressive":
        cfg["adaptive_level"] = 5
        cfg["unsharp_percent"] = 45

    for key in ("adaptive_level", "adaptive_level_min", "adaptive_level_max",
                "process_cap", "timeout", "unsharp_radius", "unsharp_percent",
                "unsharp_threshold", "min_psnr_db", "min_ssim"):
        if key in sub:
            cfg[key] = _clamp(sub[key], 0.0, 10000.0)
    # adaptive_level bounds
    cfg["adaptive_level"] = int(_clamp(cfg["adaptive_level"],
                                       cfg["adaptive_level_min"],
                                       cfg["adaptive_level_max"]))
    cfg["adaptive_level_min"] = int(cfg["adaptive_level_min"])
    cfg["adaptive_level_max"] = int(cfg["adaptive_level_max"])
    cfg["process_cap"] = int(cfg["process_cap"])
    cfg["timeout"] = int(cfg["timeout"])
    cfg["unsharp_radius"] = float(cfg["unsharp_radius"])
    cfg["unsharp_percent"] = int(round(_clamp(cfg["unsharp_percent"], 0.0, 500.0)))
    cfg["unsharp_threshold"] = int(cfg["unsharp_threshold"])
    if "skip_if_processed" in sub:
        cfg["skip_if_processed"] = bool(sub["skip_if_processed"])
    return cfg


def apply_max_optimised_remint(input_path, output_path, creator_id, settings=None, seed_extra=""):
    cfg = normalize_max_optimised_remint_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "max_optimised_remint_v1",
        "applied": False,
        "engine": "max_optimised_remint",
        "settings": _public_settings(cfg),
        "layers": {},
        "quality_gates": {},
        "oracle": {
            "metadata_sparkle": "not_evaluated",
            "pixel_synthid": "not_evaluated",
        },
        "idempotency": {"already_processed": False},
    }
    if not cfg["enabled"]:
        return report

    started = time.time()
    original = Image.open(input_path).convert("RGB")
    seed = _seed(creator_id, seed_extra, original.size)

    # --- Idempotency: skip regeneration if this image was already processed. ---
    already = _has_resmarke_marker(input_path) if cfg["skip_if_processed"] else False
    report["idempotency"]["already_processed"] = already

    if already:
        # Re-minting a clean image must NOT re-run diffusion (the death-spiral).
        # Keep the pixels, just re-run quality restoration + let the worker's
        # finalize_output re-apply the seal + light naturalization.
        working = original
        report["layers"]["purification"] = {
            "applied": False, "reason": "already_processed_skip",
        }
        report["oracle"]["metadata_sparkle"] = "skipped_already_processed"
        report["oracle"]["pixel_synthid"] = "skipped_already_processed"
    else:
        # --- Purification: moderate-strength regeneration, single VAE pass. ---
        purify_path = Path(output_path).with_name(".max-opt-remint-purify.png")
        try:
            purify_report = _run_purification(
                input_path=input_path,
                output_path=str(purify_path),
                adaptive_level=cfg["adaptive_level"],
                process_cap=cfg["process_cap"],
                timeout=cfg["timeout"],
                seed=seed,
            )
            report["layers"]["purification"] = purify_report
            working = Image.open(purify_path).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            # If ComfyUI fails, do NOT silently ship degraded output. Surface
            # the failure so the worker can fail the job honestly.
            report["layers"]["purification"] = {
                "applied": False, "reason": "purification_failed", "error": str(exc)[:500],
            }
            raise

        # --- Oracle: verify the VERIFIABLE portion (metadata/sparkle). ---
        before_id = _identify(input_path)
        after_id = _identify(str(purify_path))
        report["oracle"]["identify_before"] = before_id
        report["oracle"]["identify_after"] = after_id
        report["oracle"]["metadata_sparkle"] = _ai_signal_state(after_id)
        # Pixel-SynthID has no local decoder -- report honestly, never "clean".
        report["oracle"]["pixel_synthid"] = (
            "removed_via_regeneration_not_locally_verifiable"
        )

        try:
            purify_path.unlink()
        except OSError:
            pass

    # --- Quality restoration: subtle unsharp mask (classical, non-generative). ---
    if cfg["unsharp_percent"] > 0:
        working = working.filter(ImageFilter.UnsharpMask(
            radius=cfg["unsharp_radius"],
            percent=cfg["unsharp_percent"],
            threshold=cfg["unsharp_threshold"],
        ))
        report["layers"]["quality_restoration"] = {
            "applied": True,
            "method": "unsharp_mask",
            "radius": cfg["unsharp_radius"],
            "percent": cfg["unsharp_percent"],
            "threshold": cfg["unsharp_threshold"],
            "non_generative": True,
        }
    else:
        report["layers"]["quality_restoration"] = {"applied": False}

    # --- Quality gate (the quality-preservation guarantee). ---
    metrics = compare_images(original, working)
    gate = _quality_gate(metrics, cfg)
    report["quality_gates"] = gate
    report["quality_gates"]["metrics"] = metrics

    if not gate["accepted"]:
        # We could not remove SynthID without dropping below the quality floor.
        # Honest move: do NOT ship a degraded image. Ship the original unchanged
        # (the billing layer's "charged only if passes" guarantee then applies)
        # and mark the attempt clearly in the report.
        report["quality_gates"]["shipped_original"] = True
        report["quality_gates"]["reason"] = (
            "removal_would_degrade_quality_below_floor_shipped_original_instead"
        )
        working = original
        report["applied"] = False
        working.save(output_path, format="PNG")
        report["runtime_ms"] = int((time.time() - started) * 1000)
        return report

    # Ship the optimised output. Mark it so a future re-mint is idempotent.
    working.save(output_path, format="PNG")
    _write_resmarke_marker(output_path)
    report["applied"] = True
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return report


# ---------------------------------------------------------------------------
# Purification: ComfyUI regeneration at a given adaptive_level.
# Mirrors worker.run_deepclean_comfyui but self-contained (no circular import
# back into worker), same as content_repair.run_qwen_masked_inpaint calls
# comfyui_client directly. Single VAE pass, original resolution restored.
# ---------------------------------------------------------------------------

def _run_purification(input_path, output_path, adaptive_level, process_cap, timeout, seed):
    import comfyui_client as cc

    started = time.time()
    source = Image.open(input_path).convert("RGB")
    orig_w, orig_h = source.size

    proc_w, proc_h = orig_w, orig_h
    if process_cap and max(orig_w, orig_h) > process_cap:
        ratio = process_cap / float(max(orig_w, orig_h))
        proc_w = max(1, int(orig_w * ratio))
        proc_h = max(1, int(orig_h * ratio))
        proc_img = source.resize((proc_w, proc_h), Image.Resampling.LANCZOS)
    else:
        proc_img = source

    if not TEMPLATE_PATH.exists():
        raise RuntimeError(
            f"Workflow template missing at {TEMPLATE_PATH}. Export the API-format "
            "workflow from ComfyUI -- see deepclean-worker/workflows/EXPORT.md."
        )

    with tempfile.TemporaryDirectory(prefix="max-opt-remint-") as tmpd:
        tmp = Path(tmpd)
        proc_png = tmp / "proc.png"
        proc_img.save(proc_png, format="PNG")

        filename = cc.upload_image(proc_png)
        graph = cc.load_template(str(TEMPLATE_PATH))
        cc.set_loadimage(graph, filename)
        cc.bypass_face_path(graph)            # standard path; no face subgraph
        cc.set_adaptive_level(graph, adaptive_level)
        if seed is not None:
            cc.set_seed(graph, seed)

        prompt_id = cc.post_prompt(graph)
        entry = cc.wait_for_prompt(prompt_id, timeout=timeout)
        out_bytes = cc.get_output_image(entry)

        cleaned = Image.open(io.BytesIO(out_bytes)).convert("RGB")
        if (cleaned.width, cleaned.height) != (orig_w, orig_h):
            cleaned = cleaned.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
        cleaned.save(output_path, format="PNG")

    return {
        "applied": True,
        "method": "comfyui_remarkee_max_v2",
        "adaptive_level": adaptive_level,
        "process_resolution": [proc_w, proc_h],
        "output_resolution": [orig_w, orig_h],
        "single_vae_pass": True,
        "runtime_ms": int((time.time() - started) * 1000),
    }


# ---------------------------------------------------------------------------
# Oracle: remove-ai-watermarks identify (metadata/sparkle only).
# SynthID PIXEL watermark has no local decoder -- this oracle is honest about
# that scope. It gates the verifiable signals; it cannot prove pixel-SynthID.
# ---------------------------------------------------------------------------

def _identify(path):
    """Before/after watermark inventory via remove-ai-watermarks identify.
    Must never raise: a missing/broken optional tool degrades to 'unknown'."""
    try:
        completed = subprocess.run(
            ["remove-ai-watermarks", "identify", str(path), "--json"],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        return {"ok": False, "reason": "remove-ai-watermarks not installed"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"identify failed: {exc}"}
    if completed.returncode != 0:
        return {"ok": False, "stderr_tail": (completed.stderr or "")[-400:]}
    try:
        return {"ok": True, "result": json.loads(completed.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "raw_tail": (completed.stdout or "")[-400:]}


def _ai_signal_state(identify_report):
    """Map an identify report to one of: clean | present | unknown.

    ProvenanceReport.is_ai_generated is True/False/None; watermarks is a list.
    None (no locally-readable signal) is reported as 'unknown', NEVER 'clean'
    -- stripped metadata leaves no local proof, which is exactly the SynthID
    case.
    """
    if not isinstance(identify_report, dict) or not identify_report.get("ok"):
        return "unknown"
    result = identify_report.get("result")
    if not isinstance(result, dict):
        return "unknown"
    is_ai = result.get("is_ai_generated")
    watermarks = result.get("watermarks") or []
    if is_ai is True:
        return "present"
    if is_ai is False and not watermarks:
        return "clean"
    if watermarks:
        return "present"
    return "unknown"


# ---------------------------------------------------------------------------
# Idempotency marker (our own provenance tag -- NOT forged device metadata).
# ---------------------------------------------------------------------------

def _has_resmarke_marker(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif() if hasattr(img, "getexif") else None
        if not exif:
            return False
    except Exception:  # noqa: BLE001
        return False
    # UserComment (0x9286) or ImageDescription (0x010E)
    for tag in (0x9286, 0x010E):
        val = exif.get(tag)
        if isinstance(val, (bytes, str)) and RESMARKE_MARKER in (val.decode("latin-1", "ignore") if isinstance(val, bytes) else val):
            return True
    return False


def _write_resmarke_marker(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif() if hasattr(img, "getexif") else None
            if exif is None:
                return
            exif[0x010E] = RESMARKE_MARKER  # ImageDescription
            img.save(path, exif=exif, format="PNG")
    except Exception:  # noqa: BLE001
        # Marker is best-effort for idempotency; never fail a clean job over it.
        pass


# ---------------------------------------------------------------------------
# Quality gate + helpers.
# ---------------------------------------------------------------------------

def _quality_gate(metrics, cfg):
    failures = []
    if metrics.get("psnr", 0) < float(cfg["min_psnr_db"]):
        failures.append(f"psnr_below_{cfg['min_psnr_db']}")
    if metrics.get("ssim_luma_window11_mean", 1.0) < float(cfg["min_ssim"]):
        failures.append(f"ssim_below_{cfg['min_ssim']}")
    return {
        "accepted": not failures,
        "failures": failures,
        "min_psnr_db": cfg["min_psnr_db"],
        "min_ssim": cfg["min_ssim"],
        "version": "max-optimised-remint-quality-v1",
    }


def _public_settings(cfg):
    return {k: cfg[k] for k in (
        "preset", "adaptive_level", "adaptive_level_min", "adaptive_level_max",
        "process_cap", "timeout", "unsharp_radius", "unsharp_percent",
        "unsharp_threshold", "min_psnr_db", "min_ssim", "skip_if_processed",
    )}


def _clamp(value, low, high):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return low
    if not np.isfinite(v):
        return low
    return max(low, min(high, v))


def _seed(creator_id, seed_extra, size):
    material = f"max-opt-remint:{creator_id}:{seed_extra}:{size[0]}x{size[1]}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF
