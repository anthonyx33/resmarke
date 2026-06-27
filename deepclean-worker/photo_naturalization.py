"""Deterministic camera-texture restoration for final JPEG exports."""

import hashlib

import numpy as np
from PIL import Image, ImageFilter


PHOTO_NATURALIZATION_PROFILES = {
    "standard": {
        "enabled": True,
        "blur_radius": 0.22,
        "shot_noise": 0.00055,
        "read_noise": 0.0013,
        "luma_texture": 0.0012,
        "chroma_texture": 0.00055,
        "jpeg_quality": 94,
    },
    "strong": {
        "enabled": True,
        "blur_radius": 0.42,
        "shot_noise": 0.0009,
        "read_noise": 0.0018,
        "luma_texture": 0.0018,
        "chroma_texture": 0.0008,
        "jpeg_quality": 93,
    },
    "off": {
        "enabled": False,
        "blur_radius": 0.0,
        "shot_noise": 0.0,
        "read_noise": 0.0,
        "luma_texture": 0.0,
        "chroma_texture": 0.0,
        "jpeg_quality": 93,
    },
}


def apply_photo_naturalization(image, creator_id, cfg):
    report = {
        "enabled": bool(cfg["enabled"]),
        "blur_radius": cfg["blur_radius"],
        "shot_noise": cfg["shot_noise"],
        "read_noise": cfg["read_noise"],
        "luma_texture": cfg["luma_texture"],
        "chroma_texture": cfg["chroma_texture"],
    }
    if not cfg["enabled"]:
        return report

    if cfg["blur_radius"] > 0:
        image.paste(image.filter(ImageFilter.GaussianBlur(radius=cfg["blur_radius"])))

    seed_material = f"photo-naturalization-v1:{creator_id}:{image.width}x{image.height}"
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)

    srgb = np.asarray(image).astype(np.float32) / 255.0
    linear = srgb_to_linear(srgb)

    variance = linear * cfg["shot_noise"] + cfg["read_noise"] ** 2
    sensor_noise = rng.normal(0.0, np.sqrt(variance).astype(np.float32)).astype(np.float32)

    height, width, _ = linear.shape
    luma_texture = rng.normal(0.0, cfg["luma_texture"], (height, width, 1)).astype(np.float32)
    chroma_texture = rng.normal(0.0, cfg["chroma_texture"], (height, width, 3)).astype(np.float32)

    linear = np.clip(linear + sensor_noise + luma_texture + chroma_texture, 0.0, 1.0)
    naturalized = np.clip(linear_to_srgb(linear) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    image.paste(Image.fromarray(naturalized))
    report["seed"] = seed
    return report


def srgb_to_linear(value):
    return np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(value):
    return np.where(value <= 0.0031308, value * 12.92, 1.055 * (value ** (1 / 2.4)) - 0.055).astype(np.float32)
