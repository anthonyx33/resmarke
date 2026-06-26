import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import requests
import runpod
from PIL import Image, ImageDraw, ImageFont


PROFILE_CONFIG = {
    "standard": {
        "timeout": 240,
        "pipeline": "controlnet",
        "steps": 40,
        "strength": 0.30,
        "max_resolution": 1536,
        "min_resolution": 1024,
        "controlnet_scale": 1.0,
        "humanize": 0.0,
        "unsharp": 0.25,
        "adaptive_polish": True,
        "tile": False,
        "tile_size": 1024,
        "tile_overlap": 128,
    },
    "strong": {
        "timeout": 300,
        "pipeline": "controlnet",
        "steps": 50,
        "strength": 0.35,
        "max_resolution": 1800,
        "min_resolution": 1024,
        "controlnet_scale": 1.0,
        "humanize": 1.25,
        "unsharp": 0.35,
        "adaptive_polish": True,
        "tile": False,
        "tile_size": 1024,
        "tile_overlap": 128,
    },
    "max": {
        "timeout": 420,
        "pipeline": "controlnet",
        "steps": 60,
        "strength": 0.42,
        "max_resolution": 0,
        "min_resolution": 1024,
        "controlnet_scale": 1.1,
        "humanize": 2.0,
        "unsharp": 0.45,
        "adaptive_polish": True,
        "tile": True,
        "tile_size": 1024,
        "tile_overlap": 160,
    },
}

ENGINE_CACHE = {}


def handler(job):
    payload = job.get("input", {})
    if payload.get("action") == "warmup":
        return warmup(payload.get("profile", "standard"))

    started = time.time()
    job_id = payload["job_id"]
    webhook_url = payload["webhook_url"]
    webhook_secret = payload["webhook_secret"]
    creator_id = payload.get("creator_id") or job_id

    with tempfile.TemporaryDirectory(prefix=f"deepclean-{job_id}-") as tmpdir:
        tmp = Path(tmpdir)
        # Keep a real image extension so PIL / the engine can infer the format.
        input_suffix = Path(payload.get("input_path", "")).suffix.lower()
        if input_suffix not in (".jpg", ".jpeg", ".png", ".webp"):
            input_suffix = ".jpg"
        input_path = tmp / f"input{input_suffix}"
        cleaned_path = tmp / "cleaned.png"
        final_path = tmp / "final.jpg"

        try:
            download(payload["input_url"], input_path)
            input_sha = sha256_file(input_path)
            before_report = identify_image(input_path)

            engine_report = run_deepclean(
                input_path=input_path,
                output_path=cleaned_path,
                profile=payload.get("profile", "standard"),
            )

            quality = quality_check(input_path, cleaned_path)
            if not quality["ok"]:
                raise RuntimeError(quality["reason"])

            finalize_output(
                cleaned_path=cleaned_path,
                output_path=final_path,
                output_mode=payload.get("output_mode", "sealed"),
                creator_id=creator_id,
            )

            after_report = identify_image(final_path)
            output_sha = sha256_file(final_path)
            upload_output(payload["output_path"], final_path)
            runtime_ms = int((time.time() - started) * 1000)

            notify(
                webhook_url,
                webhook_secret,
                {
                    "job_id": job_id,
                    "status": "completed",
                    "input_sha256": input_sha,
                    "output_sha256": output_sha,
                    "engine_version": engine_version(),
                    "runtime_ms": runtime_ms,
                    "gpu_type": os.environ.get("RUNPOD_GPU_TYPE", "unknown"),
                    "report": {
                        "profile": payload.get("profile", "standard"),
                        "output_mode": payload.get("output_mode", "sealed"),
                        "creator_id_hash": short_hash(creator_id),
                        "engine": engine_report,
                        "quality": quality,
                        "identify_before": before_report,
                        "identify_after": after_report,
                    },
                },
            )
            return {"ok": True, "job_id": job_id, "runtime_ms": runtime_ms}
        except Exception as exc:
            runtime_ms = int((time.time() - started) * 1000)
            notify(
                webhook_url,
                webhook_secret,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "engine_version": engine_version(),
                    "runtime_ms": runtime_ms,
                    "gpu_type": os.environ.get("RUNPOD_GPU_TYPE", "unknown"),
                    "failure_reason": str(exc),
                    "report": {
                        "profile": payload.get("profile", "standard"),
                        "output_mode": payload.get("output_mode", "sealed"),
                    },
                },
            )
            return {"ok": False, "job_id": job_id, "error": str(exc)}
        finally:
            if payload.get("input_path"):
                delete_storage_object("deepclean-inputs", payload["input_path"])
            shutil.rmtree(tmp, ignore_errors=True)


def download(url, path):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    path.write_bytes(response.content)


def upload_output(storage_path, path):
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    bucket = os.environ.get("DEEPCLEAN_OUTPUT_BUCKET", "deepclean-outputs")
    url = f"{supabase_url}/storage/v1/object/{bucket}/{storage_path}"
    with path.open("rb") as file_handle:
        response = requests.post(
            url,
            data=file_handle,
            headers={
                "authorization": f"Bearer {service_key}",
                "apikey": service_key,
                "content-type": "image/jpeg",
                "cache-control": "max-age=3600",
                "x-upsert": "false",
            },
            timeout=120,
        )
    response.raise_for_status()


def run_deepclean(input_path, output_path, profile):
    if os.environ.get("DEEPCLEAN_ENGINE_MODE", "python").lower() == "cli":
        return run_deepclean_cli(input_path, output_path, profile)

    try:
        return run_deepclean_python(input_path, output_path, profile)
    except Exception as exc:
        if os.environ.get("DEEPCLEAN_CLI_FALLBACK", "0") != "1":
            raise
        if output_path.exists():
            output_path.unlink()
        fallback_report = run_deepclean_cli(input_path, output_path, profile)
        fallback_report["python_api_error"] = str(exc)
        return fallback_report


def run_deepclean_python(input_path, output_path, profile):
    profile_config = get_profile_config(profile)
    started = time.time()
    engine, engine_report = get_engine(profile)
    progress_messages = []

    def progress(message):
        print(f"[deepclean] {message}", flush=True)
        progress_messages.append(message)
        del progress_messages[:-12]

    # The engine keeps the original progress callback from construction. For now
    # progress is startup-scoped; per-job progress is still represented by runtime.
    seed = env_int("DEEPCLEAN_SEED")
    engine.remove_watermark(
        image_path=Path(input_path),
        output_path=Path(output_path),
        strength=profile_config["strength"],
        num_inference_steps=profile_config["steps"],
        guidance_scale=None,
        seed=seed,
        humanize=profile_config["humanize"],
        max_resolution=profile_config["max_resolution"],
        min_resolution=profile_config["min_resolution"],
        vendor=None,
        unsharp=profile_config["unsharp"],
        adaptive_polish=profile_config["adaptive_polish"],
        upscaler="lanczos",
        tile=profile_config["tile"],
        tile_size=profile_config["tile_size"],
        tile_overlap=profile_config["tile_overlap"],
    )
    if not output_path.exists():
        raise RuntimeError("DeepClean engine failed: Python API did not write an output file.")

    return {
        "profile": profile,
        "method": "python-api",
        "params": public_profile_config(profile_config),
        "engine": engine_report,
        "seed": seed,
        "runtime_ms": int((time.time() - started) * 1000),
        "progress_tail": progress_messages,
    }


def run_deepclean_cli(input_path, output_path, profile):
    profile_config = get_profile_config(profile)
    args = cli_args_for_profile(profile_config)
    if token := os.environ.get("HF_TOKEN"):
        args.extend(["--hf-token", token])
    if model := os.environ.get("DEEPCLEAN_MODEL"):
        args.extend(["--model", model])

    command = [
        "remove-ai-watermarks",
        "all",
        str(input_path),
        "-o",
        str(output_path),
        "--device",
        "cuda",
        *args,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=profile_config["timeout"],
    )
    if completed.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "DeepClean engine failed: "
            + (completed.stderr.strip() or completed.stdout.strip() or "unknown error")
        )
    return {
        "profile": profile,
        "method": "cli",
        "command": redact_command(command),
        "stdout_tail": tail(completed.stdout),
        "stderr_tail": tail(completed.stderr),
    }


def get_engine(profile):
    profile_config = get_profile_config(profile)
    pipeline = profile_config["pipeline"]
    model_id = os.environ.get("DEEPCLEAN_MODEL") or None
    hf_token = os.environ.get("HF_TOKEN") or None
    device = os.environ.get("DEEPCLEAN_DEVICE") or "cuda"
    controlnet_scale = profile_config["controlnet_scale"]
    cache_key = (pipeline, model_id, device, bool(hf_token), controlnet_scale)

    if cache_key in ENGINE_CACHE:
        return ENGINE_CACHE[cache_key]["engine"], {
            "cached": True,
            "pipeline": pipeline,
            "device": device,
            "model": model_id or "default",
            "controlnet_scale": controlnet_scale,
            "load_ms": ENGINE_CACHE[cache_key]["load_ms"],
        }

    print(
        f"[deepclean] Loading engine pipeline={pipeline} device={device} "
        f"model={model_id or 'default'} controlnet_scale={controlnet_scale}",
        flush=True,
    )
    started = time.time()

    from remove_ai_watermarks.invisible_engine import InvisibleEngine

    def progress(message):
        print(f"[deepclean:init] {message}", flush=True)

    engine = InvisibleEngine(
        model_id=model_id,
        device=device,
        pipeline=pipeline,
        hf_token=hf_token,
        progress_callback=progress,
        controlnet_conditioning_scale=controlnet_scale,
    )
    engine.preload()
    load_ms = int((time.time() - started) * 1000)
    ENGINE_CACHE[cache_key] = {"engine": engine, "load_ms": load_ms}
    print(f"[deepclean] Engine ready in {load_ms}ms", flush=True)
    return engine, {
        "cached": False,
        "pipeline": pipeline,
        "device": device,
        "model": model_id or "default",
        "controlnet_scale": controlnet_scale,
        "load_ms": load_ms,
    }


def warmup(profile):
    started = time.time()
    _, engine_report = get_engine(profile)
    return {
        "ok": True,
        "action": "warmup",
        "profile": profile,
        "engine": engine_report,
        "runtime_ms": int((time.time() - started) * 1000),
        "gpu_type": os.environ.get("RUNPOD_GPU_TYPE", "unknown"),
        "engine_version": engine_version(),
    }


def get_profile_config(profile):
    return PROFILE_CONFIG.get(profile, PROFILE_CONFIG["standard"])


def public_profile_config(profile_config):
    return {
        "pipeline": profile_config["pipeline"],
        "steps": profile_config["steps"],
        "strength": profile_config["strength"],
        "max_resolution": profile_config["max_resolution"],
        "min_resolution": profile_config["min_resolution"],
        "controlnet_scale": profile_config["controlnet_scale"],
        "humanize": profile_config["humanize"],
        "unsharp": profile_config["unsharp"],
        "adaptive_polish": profile_config["adaptive_polish"],
        "tile": profile_config["tile"],
        "tile_size": profile_config["tile_size"],
        "tile_overlap": profile_config["tile_overlap"],
    }


def cli_args_for_profile(profile_config):
    args = [
        "--pipeline",
        profile_config["pipeline"],
        "--force",
        "--steps",
        str(profile_config["steps"]),
        "--strength",
        str(profile_config["strength"]),
        "--max-resolution",
        str(profile_config["max_resolution"]),
        "--min-resolution",
        str(profile_config["min_resolution"]),
        "--controlnet-scale",
        str(profile_config["controlnet_scale"]),
        "--unsharp",
        str(profile_config["unsharp"]),
    ]
    if profile_config["humanize"] > 0:
        args.extend(["--humanize", str(profile_config["humanize"])])
    if profile_config["adaptive_polish"]:
        args.append("--adaptive-polish")
    else:
        args.append("--no-adaptive-polish")
    if profile_config["tile"]:
        args.extend(
            [
                "--tile",
                "--tile-size",
                str(profile_config["tile_size"]),
                "--tile-overlap",
                str(profile_config["tile_overlap"]),
            ]
        )
    return args


def env_int(name):
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    return int(value)


def quality_check(input_path, output_path):
    source = Image.open(input_path).convert("RGB")
    output = Image.open(output_path).convert("RGB")
    if output.width < 256 or output.height < 256:
        return {"ok": False, "reason": "Output image is too small."}

    resized_source = source.resize(output.size, Image.Resampling.LANCZOS)
    source_arr = np.asarray(resized_source).astype(np.float32)
    output_arr = np.asarray(output).astype(np.float32)
    mse = float(np.mean((source_arr - output_arr) ** 2))
    psnr = 99.0 if mse == 0 else float(20 * np.log10(255.0 / np.sqrt(mse)))
    variance = float(np.var(output_arr))

    if variance < 12:
        return {"ok": False, "reason": "Output appears blank.", "psnr": psnr}
    if psnr < 18:
        return {"ok": False, "reason": "Output drift exceeded quality gate.", "psnr": psnr}
    return {"ok": True, "psnr": psnr, "variance": variance}


def finalize_output(cleaned_path, output_path, output_mode, creator_id):
    image = Image.open(cleaned_path).convert("RGB")
    canvas = Image.new("RGB", (1800, 1800), (247, 248, 244))
    image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    x = (1800 - image.width) // 2
    y = (1800 - image.height) // 2
    canvas.paste(image, (x, y))

    if output_mode in ("sealed", "sealed-stamped"):
        apply_fibonacci_88(canvas, creator_id)

    if output_mode == "sealed-stamped":
        draw = ImageDraw.Draw(canvas)
        label = "ResMarke"
        box = (1428, 1718, 1768, 1772)
        draw.rounded_rectangle(box, radius=8, fill=(30, 37, 37))
        draw.text((1460, 1734), label, fill=(255, 255, 255), font=ImageFont.load_default())

    canvas.save(output_path, format="JPEG", quality=88, optimize=True)


def apply_fibonacci_88(image, creator_id):
    pixels = image.load()
    width, height = image.size
    seed = int(hashlib.sha256(creator_id.encode("utf-8")).hexdigest()[:8], 16)
    bits = []
    digest = hashlib.sha256(f"resmarke:{creator_id}".encode("utf-8")).digest()
    for byte in digest:
        for bit in range(8):
            bits.append((byte >> bit) & 1)
            if len(bits) == 88:
                break
        if len(bits) == 88:
            break

    fib_a = 1 + seed % 13
    fib_b = 1 + (seed >> 4) % 17
    blocks_x = width // 8
    blocks_y = height // 8
    total_blocks = blocks_x * blocks_y
    used = set()
    index = 0

    while index < len(bits) * 9 and len(used) < total_blocks:
        fib_a, fib_b = fib_b, (fib_a + fib_b + seed + index * 2654435761) & 0xFFFFFFFF
        block = fib_b % total_blocks
        if block in used:
            continue
        used.add(block)
        bit = bits[index % len(bits)]
        direction = 1 if bit else -1
        bx = (block % blocks_x) * 8
        by = (block // blocks_x) * 8
        for y in range(by, min(by + 8, height)):
            for x in range(bx, min(bx + 8, width)):
                r, g, b = pixels[x, y]
                checker = 1 if (x + y + index) % 2 == 0 else -1
                delta = direction * checker * 3
                pixels[x, y] = (
                    r,
                    clamp(g - delta),
                    clamp(b + delta),
                )
        index += 1


def clamp(value):
    return max(0, min(255, int(round(value))))


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def short_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def identify_image(path):
    completed = subprocess.run(
        ["remove-ai-watermarks", "identify", str(path), "--json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "stderr_tail": tail(completed.stderr),
            "stdout_tail": tail(completed.stdout),
        }
    try:
        return {"ok": True, "result": json.loads(completed.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "raw_tail": tail(completed.stdout)}


def engine_version():
    completed = subprocess.run(
        ["remove-ai-watermarks", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (completed.stdout or completed.stderr or "remove-ai-watermarks").strip()


def redact_command(command):
    redacted = []
    skip_next = False
    for item in command:
        if skip_next:
            redacted.append("[redacted]")
            skip_next = False
            continue
        redacted.append(item)
        if item == "--hf-token":
            skip_next = True
    return " ".join(shlex.quote(part) for part in redacted)


def tail(text, limit=2000):
    text = (text or "").strip()
    return text[-limit:]


def delete_storage_object(bucket, storage_path):
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return
    response = requests.delete(
        f"{supabase_url}/storage/v1/object/{bucket}",
        data=json.dumps({"prefixes": [storage_path]}),
        headers={
            "authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "content-type": "application/json",
        },
        timeout=30,
    )
    if response.status_code not in (200, 204):
        print(f"Warning: failed to delete {bucket}/{storage_path}: {response.status_code}")


def notify(webhook_url, secret, body):
    response = requests.post(
        webhook_url,
        data=json.dumps({**body, "signature": secret}),
        headers={"content-type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()


def log_cache_env():
    """Log where model weights cache to, so we can confirm the network volume is used."""
    for key in (
        "HF_HOME",
        "HF_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "DIFFUSERS_CACHE",
        "TORCH_HOME",
    ):
        print(f"[deepclean:cache] {key}={os.environ.get(key)}", flush=True)

    volume = "/runpod-volume"
    print(f"[deepclean:cache] {volume} mounted={os.path.isdir(volume)}", flush=True)

    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(os.environ.get("HF_HOME", ""), "hub")
    try:
        populated = os.path.isdir(hub) and bool(os.listdir(hub))
    except OSError:
        populated = False
    print(f"[deepclean:cache] weights cached={populated} ({hub})", flush=True)


def maybe_preload_on_start():
    if os.environ.get("DEEPCLEAN_ENGINE_MODE", "python").lower() == "cli":
        return
    if os.environ.get("DEEPCLEAN_PRELOAD", "1") == "0":
        return
    profile = os.environ.get("DEEPCLEAN_PRELOAD_PROFILE", "standard")
    try:
        report = warmup(profile)
        print(f"[deepclean] Startup preload complete: {json.dumps(report)}", flush=True)
    except Exception as exc:
        print(f"[deepclean] Startup preload failed: {exc}", flush=True)
        if os.environ.get("DEEPCLEAN_PRELOAD_REQUIRED") == "1":
            raise


log_cache_env()
maybe_preload_on_start()
runpod.serverless.start({"handler": handler})
