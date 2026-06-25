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
from PIL import Image, ImageDraw


PROFILE_ARGS = {
    "standard": ["--pipeline", "controlnet", "--max-resolution", "1536"],
    "strong": ["--pipeline", "controlnet", "--max-resolution", "1536", "--strength", "0.35"],
    "max": [
        "--pipeline",
        "controlnet",
        "--max-resolution",
        "2048",
        "--strength",
        "0.40",
        "--humanize",
        "2.0",
        "--unsharp",
        "0.35",
    ],
}


def handler(job):
    payload = job.get("input", {})
    started = time.time()
    job_id = payload["job_id"]
    webhook_url = payload["webhook_url"]
    webhook_secret = payload["webhook_secret"]

    with tempfile.TemporaryDirectory(prefix=f"deepclean-{job_id}-") as tmpdir:
        tmp = Path(tmpdir)
        input_path = tmp / "input"
        cleaned_path = tmp / "cleaned.png"
        final_path = tmp / "final.jpg"

        try:
            download(payload["input_url"], input_path)
            input_sha = sha256_file(input_path)

            run_deepclean(
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
                job_id=job_id,
            )

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
                        "quality": quality,
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
    args = PROFILE_ARGS.get(profile, PROFILE_ARGS["standard"])
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
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if completed.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "DeepClean engine failed: "
            + (completed.stderr.strip() or completed.stdout.strip() or "unknown error")
        )


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


def finalize_output(cleaned_path, output_path, output_mode, job_id):
    image = Image.open(cleaned_path).convert("RGB")
    canvas = Image.new("RGB", (1800, 1800), (247, 248, 244))
    image.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    x = (1800 - image.width) // 2
    y = (1800 - image.height) // 2
    canvas.paste(image, (x, y))

    if output_mode in ("sealed", "sealed-stamped"):
        apply_fibonacci_88(canvas, job_id)

    if output_mode == "sealed-stamped":
        draw = ImageDraw.Draw(canvas)
        label = "Resmarke"
        box = (1428, 1718, 1768, 1772)
        draw.rounded_rectangle(box, radius=8, fill=(30, 37, 37))
        draw.text((1460, 1734), label, fill=(255, 255, 255))

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


def engine_version():
    completed = subprocess.run(
        ["remove-ai-watermarks", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (completed.stdout or completed.stderr or "remove-ai-watermarks").strip()


def notify(webhook_url, secret, body):
    response = requests.post(
        webhook_url,
        data=json.dumps({**body, "signature": secret}),
        headers={"content-type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()


runpod.serverless.start({"handler": handler})
