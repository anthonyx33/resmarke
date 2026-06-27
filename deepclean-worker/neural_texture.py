"""Internal Neural Texture Lab.

This is deliberately narrow: Real-ESRGAN x4plus through ComfyUI, alpha-blended
against the regenerated image, with simple QA metrics and fail-safe retries.
It is a lab path, not a public profile.
"""

import hashlib
import io
import os
import time

import numpy as np
from PIL import Image


MODEL_NAME = os.environ.get("DEEPCLEAN_NEURAL_TEXTURE_MODEL", "RealESRGAN_x4plus.pth")
DEFAULT_ALPHA = float(os.environ.get("DEEPCLEAN_NEURAL_TEXTURE_ALPHA", "0.6"))
DEFAULT_TIMEOUT = float(os.environ.get("DEEPCLEAN_NEURAL_TEXTURE_TIMEOUT", "240"))


def is_neural_texture_lab(settings):
    return isinstance(settings, dict) and settings.get("mode") == "neural-texture-lab"


def apply_neural_texture_lab(input_path, output_path, creator_id, settings=None, seed_extra=""):
    cfg = normalize_neural_texture_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "realesrgan_x4plus_alpha_lab",
        "model": cfg["model_name"],
        "requested_alpha": cfg["alpha"],
        "applied": False,
        "attempts": [],
    }
    if not cfg["enabled"]:
        return report

    started = time.time()
    base = Image.open(input_path).convert("RGB")
    restored, comfy_report = run_realesrgan_x4plus_comfyui(
        input_path=input_path,
        width=base.width,
        height=base.height,
        model_name=cfg["model_name"],
        timeout=cfg["timeout"],
    )
    report["comfyui"] = comfy_report

    candidate_alphas = unique_alphas([cfg["alpha"], 0.45, 0.30])
    best = None
    for alpha in candidate_alphas:
        blended = Image.blend(base, restored, alpha)
        metrics = compare_images(base, blended)
        gates = neural_texture_gates(metrics)
        attempt = {
            "alpha": alpha,
            "metrics": metrics,
            "gates": gates,
            "accepted": gates["accepted"],
        }
        report["attempts"].append(attempt)
        if gates["accepted"]:
            best = (blended, attempt)
            break

    if best is None:
        report["reason"] = "qa_gates_failed"
        report["runtime_ms"] = int((time.time() - started) * 1000)
        return report

    image, accepted = best
    image.save(output_path, format="PNG")
    report["applied"] = True
    report["alpha"] = accepted["alpha"]
    report["quality_gates"] = accepted["gates"]
    report["metrics"] = accepted["metrics"]
    report["input_resolution"] = [base.width, base.height]
    report["output_resolution"] = [image.width, image.height]
    report["seed"] = neural_seed(creator_id, seed_extra, base.size)
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return report


def normalize_neural_texture_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    neural = raw.get("neural_texture") if isinstance(raw.get("neural_texture"), dict) else {}
    return {
        "enabled": raw.get("mode") == "neural-texture-lab",
        "alpha": clamp_float(neural.get("alpha", DEFAULT_ALPHA), 0.0, 1.0),
        "model_name": str(neural.get("model_name", MODEL_NAME)),
        "timeout": clamp_float(neural.get("timeout", DEFAULT_TIMEOUT), 30.0, 900.0),
    }


def run_realesrgan_x4plus_comfyui(input_path, width, height, model_name, timeout):
    import comfyui_client as cc

    filename = cc.upload_image(input_path)
    graph = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": filename},
        },
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": model_name},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "image": ["1", 0],
                "upscale_model": ["2", 0],
            },
        },
        "4": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["3", 0],
                "upscale_method": "bicubic",
                "width": int(width),
                "height": int(height),
                "crop": "disabled",
            },
        },
        "5": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "remarkee_neural_texture_lab",
                "images": ["4", 0],
            },
        },
    }
    started = time.time()
    prompt_id = cc.post_prompt(graph)
    entry = cc.wait_for_prompt(prompt_id, timeout=timeout)
    out_bytes = cc.get_output_image(entry)
    image = Image.open(io.BytesIO(out_bytes)).convert("RGB")
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.BICUBIC)
    return image, {
        "prompt_id": prompt_id,
        "model_name": model_name,
        "graph_nodes": len(graph),
        "runtime_ms": int((time.time() - started) * 1000),
    }


def compare_images(source, output):
    source_arr = np.asarray(source).astype(np.float32)
    output_arr = np.asarray(output).astype(np.float32)
    source_luma = luma(source_arr)
    output_luma = luma(output_arr)
    mse = float(np.mean((source_arr - output_arr) ** 2))
    psnr = 99.0 if mse == 0 else float(20 * np.log10(255.0 / np.sqrt(mse)))
    ssim = float(global_ssim(source_luma, output_luma))
    source_detail = detail_energy(source_luma)
    output_detail = detail_energy(output_luma)
    detail_ratio = float(output_detail / max(source_detail, 1e-6))
    return {
        "psnr": psnr,
        "ssim_luma": ssim,
        "detail_energy_input": source_detail,
        "detail_energy_output": output_detail,
        "detail_ratio": detail_ratio,
    }


def neural_texture_gates(metrics):
    failures = []
    if metrics["ssim_luma"] < 0.92:
        failures.append("ssim_luma_below_0.92")
    if metrics["detail_ratio"] > 1.8:
        failures.append("detail_ratio_above_1.8")
    if metrics["psnr"] < 24:
        failures.append("psnr_below_24")
    return {
        "accepted": not failures,
        "failures": failures,
    }


def luma(rgb):
    return (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    ).astype(np.float32)


def global_ssim(a, b):
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mu_a = float(np.mean(a))
    mu_b = float(np.mean(b))
    var_a = float(np.var(a))
    var_b = float(np.var(b))
    cov = float(np.mean((a - mu_a) * (b - mu_b)))
    numerator = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    denominator = (mu_a * mu_a + mu_b * mu_b + c1) * (var_a + var_b + c2)
    return numerator / max(denominator, 1e-9)


def detail_energy(luma_array):
    gy = np.diff(luma_array, axis=0)
    gx = np.diff(luma_array, axis=1)
    return float((np.mean(np.abs(gx)) + np.mean(np.abs(gy))) * 0.5)


def unique_alphas(values):
    seen = set()
    out = []
    for value in values:
        alpha = round(clamp_float(value, 0.0, 1.0), 3)
        if alpha not in seen:
            seen.add(alpha)
            out.append(alpha)
    return out


def neural_seed(creator_id, seed_extra, size):
    material = f"neural-texture-lab-v1:{creator_id}:{seed_extra}:{size[0]}x{size[1]}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def clamp_float(value, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = low
    if not np.isfinite(parsed):
        parsed = low
    return max(low, min(high, parsed))
