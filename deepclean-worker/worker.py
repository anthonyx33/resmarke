import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import requests
import runpod
from PIL import Image, ImageDraw, ImageFont

# The cleaning engine is ComfyUI running the Synthid-Bypass v2 workflow, started
# as a localhost service by start.sh (see comfyui_client.py). The workflow
# template is the API-format export at DEEPCLEAN_WORKFLOW (default
# /app/workflows/synthid-bypass-v2.api.json — see workflows/README.md).
TEMPLATE_PATH = Path(
    os.environ.get("DEEPCLEAN_WORKFLOW", "/app/workflows/synthid-bypass-v2.api.json")
)

# Profiles drive the python-side optimizations (resolution cap + restore-to-
# original + timeout). The ComfyUI workflow's own AdaptiveDenoise node still
# scales denoise per resolution inside the graph.
#
# TODO(v2): `face_path` is not yet wired into the graph — bypassing the
# Z-Image/SAM/MediaPipe/RES4LYF face subgraph requires the API-format template
# to be exported first so we can identify the face-path node IDs. v1 runs the
# full v2 workflow for every profile (correct, just not yet face-conditional).
# `upscale_back` is lanczos for all tiers in v1; neural upscale (Real-ESRGAN
# via a ComfyUI UpscaleModelLoader node) is a follow-up to avoid a fragile
# realesrgan pip install in the ComfyUI image.
PROFILE_CONFIG = {
    "standard": {"timeout": 180, "process_cap": 1536, "upscale_back": "lanczos", "face_path": False},
    "strong": {"timeout": 240, "process_cap": 1536, "upscale_back": "lanczos", "face_path": True},
    "max": {"timeout": 360, "process_cap": 1800, "upscale_back": "lanczos", "face_path": True},
}


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


# ---------------------------------------------------------------------------
# Engine: ComfyUI + Synthid-Bypass v2 workflow
# ---------------------------------------------------------------------------

def run_deepclean(input_path, output_path, profile):
    return run_deepclean_comfyui(input_path, output_path, profile)


def run_deepclean_comfyui(input_path, output_path, profile):
    import comfyui_client as cc

    cfg = get_profile_config(profile)
    started = time.time()

    # --- Preprocess: normalize to RGB + cap to process_cap (lossless PNG). ---
    # SynthID is resolution-dependent (remove-ai-watermarks only certifies at
    # <=1536; reverse-SynthID-gpu confirms a resolution-dependent carrier), so
    # processing a 4K image costs 4x compute for no removal gain. We cap, run
    # the bypass, then restore to the original size in postprocess.
    source = Image.open(input_path).convert("RGB")
    orig_w, orig_h = source.size
    cap = cfg["process_cap"]
    proc_w, proc_h = orig_w, orig_h
    if cap and max(orig_w, orig_h) > cap:
        ratio = cap / float(max(orig_w, orig_h))
        proc_w = max(1, int(orig_w * ratio))
        proc_h = max(1, int(orig_h * ratio))
        proc_img = source.resize((proc_w, proc_h), Image.Resampling.LANCZOS)
    else:
        proc_img = source

    if not TEMPLATE_PATH.exists():
        raise RuntimeError(
            f"Workflow template missing at {TEMPLATE_PATH}. Export the API-format "
            "workflow from ComfyUI — see deepclean-worker/workflows/README.md."
        )

    seed = env_int("DEEPCLEAN_SEED")

    with tempfile.TemporaryDirectory(prefix="deepclean-comfy-") as tmpd:
        tmp = Path(tmpd)
        proc_png = tmp / "proc.png"
        proc_img.save(proc_png, format="PNG")

        filename = cc.upload_image(proc_png)
        graph = cc.load_template(str(TEMPLATE_PATH))
        cc.set_loadimage(graph, filename)
        if seed is not None:
            cc.set_seed(graph, seed)

        prompt_id = cc.post_prompt(graph)
        entry = cc.wait_for_prompt(prompt_id, timeout=cfg["timeout"])
        out_bytes = cc.get_output_image(entry)

        cap_png = tmp / "cleaned_cap.png"
        cap_png.write_bytes(out_bytes)

        # --- Postprocess: restore to the creator's original resolution. ---
        cleaned = Image.open(cap_png).convert("RGB")
        if (cleaned.width, cleaned.height) != (orig_w, orig_h):
            cleaned = cleaned.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
        cleaned.save(output_path, format="PNG")

    return {
        "profile": profile,
        "method": "comfyui",
        "engine": "synthid-bypass-v2",
        "params": public_profile_config(cfg),
        "seed": seed,
        "process_resolution": [proc_w, proc_h],
        "output_resolution": [orig_w, orig_h],
        "upscale_back": cfg["upscale_back"],
        "runtime_ms": int((time.time() - started) * 1000),
    }


def warmup(profile):
    """Push a small neutral image through the workflow so Qwen + controlnet
    land in VRAM at boot. A flat image has no faces, so the Z-Image face path
    stays unloaded until a real portrait arrives."""
    import comfyui_client as cc

    started = time.time()
    cfg = get_profile_config(profile)
    warmed = False
    err = None
    if TEMPLATE_PATH.exists():
        with tempfile.TemporaryDirectory(prefix="deepclean-warm-") as tmpd:
            warm_png = Path(tmpd) / "warm.png"
            Image.new("RGB", (512, 512), (128, 128, 128)).save(warm_png, format="PNG")
            try:
                filename = cc.upload_image(warm_png)
                graph = cc.load_template(str(TEMPLATE_PATH))
                cc.set_loadimage(graph, filename)
                prompt_id = cc.post_prompt(graph)
                cc.wait_for_prompt(prompt_id, timeout=cfg["timeout"])
                warmed = True
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                print(f"[deepclean] warmup prompt failed: {exc}", flush=True)
    else:
        err = f"template missing at {TEMPLATE_PATH}"
        print(f"[deepclean] warmup skipped: {err}", flush=True)

    return {
        "ok": True,
        "action": "warmup",
        "profile": profile,
        "warmed": warmed,
        "warmup_error": err,
        "engine": "synthid-bypass-v2",
        "runtime_ms": int((time.time() - started) * 1000),
        "gpu_type": os.environ.get("RUNPOD_GPU_TYPE", "unknown"),
        "engine_version": engine_version(),
    }


def get_profile_config(profile):
    return PROFILE_CONFIG.get(profile, PROFILE_CONFIG["standard"])


def public_profile_config(cfg):
    return {
        "process_cap": cfg["process_cap"],
        "upscale_back": cfg["upscale_back"],
        "face_path": cfg["face_path"],
        "timeout": cfg["timeout"],
    }


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
    # Preserve the creator's native resolution. The engine already restored the
    # cleaned image to the original size; here we just cap the final export
    # (keeps JPEGs sane on huge inputs) and apply the Fibonacci-88 seal at that
    # size. The seal's 8x8 block distribution works at any dimension.
    MAX_FINAL = 2048
    image = Image.open(cleaned_path).convert("RGB")
    if max(image.width, image.height) > MAX_FINAL:
        image.thumbnail((MAX_FINAL, MAX_FINAL), Image.Resampling.LANCZOS)

    if output_mode in ("sealed", "sealed-stamped"):
        apply_fibonacci_88(image, creator_id)

    if output_mode == "sealed-stamped":
        draw = ImageDraw.Draw(image)
        label = "ResMarke"
        w, h = image.size
        bw = min(340, w - 64)
        bh = min(54, h - 32)
        margin = 32
        box = (w - bw - margin, h - bh - margin, w - margin, h - margin)
        draw.rounded_rectangle(box, radius=8, fill=(30, 37, 37))
        draw.text((box[0] + 32, box[1] + 18), label, fill=(255, 255, 255), font=ImageFont.load_default())

    image.save(output_path, format="JPEG", quality=88, optimize=True)


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
    """Before/after watermark inventory via the `remove-ai-watermarks identify`
    CLI. Optional — if the package is absent or broken (e.g. dropped to keep the
    image lean), this returns ok=False and the webhook report simply omits it.
    Must NEVER raise: a missing optional tool must not fail a clean job."""
    try:
        completed = subprocess.run(
            ["remove-ai-watermarks", "identify", str(path), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return {"ok": False, "reason": "remove-ai-watermarks not installed"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"identify failed: {exc}"}
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
    if TEMPLATE_PATH.exists():
        try:
            return f"comfyui+synthid-bypass-v2 template={sha256_file(TEMPLATE_PATH)[:12]}"
        except Exception:
            pass
    return "comfyui+synthid-bypass-v2 template=missing"


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
        "COMFYUI_BASE",
    ):
        print(f"[deepclean:cache] {key}={os.environ.get(key)}", flush=True)

    volume = "/runpod-volume"
    print(f"[deepclean:cache] {volume} mounted={os.path.isdir(volume)}", flush=True)

    comfy_base = os.environ.get("COMFYUI_BASE", f"{volume}/ComfyUI")
    models_dir = os.path.join(comfy_base, "models")
    try:
        populated = os.path.isdir(models_dir) and bool(os.listdir(models_dir))
    except OSError:
        populated = False
    print(f"[deepclean:cache] comfy models populated={populated} ({models_dir})", flush=True)

    if TEMPLATE_PATH.exists():
        print(f"[deepclean:cache] workflow template present ({TEMPLATE_PATH})", flush=True)
    else:
        print(
            f"[deepclean:cache] WARNING: workflow template missing ({TEMPLATE_PATH}) "
            "— export API-format workflow, see workflows/README.md",
            flush=True,
        )


def maybe_preload_on_start():
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
