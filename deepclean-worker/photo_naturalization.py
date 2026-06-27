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
    "standard-plus": {
        "enabled": True,
        "blur_radius": 0.32,
        "chroma_blur_multiplier": 1.15,
        "shot_noise": 0.00072,
        "read_noise": 0.0015,
        "luma_texture": 0.00145,
        "chroma_texture": 0.00068,
        "resample_scale_x": 0.97,
        "resample_scale_y": 0.9708,
        "subpixel_shift": 0.18,
        "micro_texture_jitter": False,
        "micro_texture_jitter_sigma": 0.0,
        "jpeg_quality": 93,
        "jpeg_subsampling": "4:2:2",
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
    "max": {
        "enabled": True,
        "blur_radius": 0.55,
        "chroma_blur_multiplier": 1.2,
        "shot_noise": 0.0012,
        "read_noise": 0.0022,
        "luma_texture": 0.0024,
        "chroma_texture": 0.0011,
        "resample_scale_x": 0.94,
        "resample_scale_y": 0.9408,
        "subpixel_shift": 0.35,
        "micro_texture_jitter": False,
        "micro_texture_jitter_sigma": 0.18,
        "jpeg_quality": 91,
        "jpeg_subsampling": "4:2:2",
    },
    "max-jitter": {
        "enabled": True,
        "blur_radius": 0.55,
        "chroma_blur_multiplier": 1.2,
        "shot_noise": 0.0012,
        "read_noise": 0.0022,
        "luma_texture": 0.0024,
        "chroma_texture": 0.0011,
        "resample_scale_x": 0.94,
        "resample_scale_y": 0.9408,
        "subpixel_shift": 0.35,
        "micro_texture_jitter": True,
        "micro_texture_jitter_sigma": 0.18,
        "jpeg_quality": 91,
        "jpeg_subsampling": "4:2:2",
    },
    "off": {
        "enabled": False,
        "blur_radius": 0.0,
        "chroma_blur_multiplier": 1.0,
        "shot_noise": 0.0,
        "read_noise": 0.0,
        "luma_texture": 0.0,
        "chroma_texture": 0.0,
        "jpeg_quality": 93,
    },
}


def apply_photo_naturalization(image, creator_id, cfg, seed_extra=""):
    report = {
        "enabled": bool(cfg["enabled"]),
        "blur_radius": cfg["blur_radius"],
        "chroma_blur_multiplier": cfg.get("chroma_blur_multiplier", 1.0),
        "shot_noise": cfg["shot_noise"],
        "read_noise": cfg["read_noise"],
        "luma_texture": cfg["luma_texture"],
        "chroma_texture": cfg["chroma_texture"],
        "resample_scale_x": cfg.get("resample_scale_x", 1.0),
        "resample_scale_y": cfg.get("resample_scale_y", 1.0),
        "subpixel_shift": cfg.get("subpixel_shift", 0.0),
        "micro_texture_jitter": bool(cfg.get("micro_texture_jitter", False)),
        "micro_texture_jitter_sigma": cfg.get("micro_texture_jitter_sigma", 0.0),
        "jpeg_subsampling": cfg.get("jpeg_subsampling", "pillow-default"),
    }
    if not cfg["enabled"]:
        return report

    seed_material = f"photo-naturalization-v2:{creator_id}:{seed_extra}:{image.width}x{image.height}"
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)

    if cfg.get("subpixel_shift", 0.0) > 0:
        shifted, shift_x, shift_y = subpixel_translate(image, rng, cfg["subpixel_shift"])
        image.paste(shifted)
        report["subpixel_shift_x"] = shift_x
        report["subpixel_shift_y"] = shift_y

    if cfg.get("micro_texture_jitter", False):
        jittered = micro_texture_jitter(
            image,
            rng,
            sigma=cfg.get("micro_texture_jitter_sigma", 0.18),
        )
        image.paste(jittered)

    scale_x = cfg.get("resample_scale_x", 1.0)
    scale_y = cfg.get("resample_scale_y", 1.0)
    if scale_x < 1.0 or scale_y < 1.0:
        image.paste(resample_roundtrip(image, scale_x, scale_y))

    if cfg["blur_radius"] > 0:
        image.paste(split_channel_blur(image, cfg["blur_radius"], cfg.get("chroma_blur_multiplier", 1.0)))

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


def resample_roundtrip(image, scale_x, scale_y):
    width, height = image.size
    scaled_size = (
        max(1, int(round(width * scale_x))),
        max(1, int(round(height * scale_y))),
    )
    return image.resize(scaled_size, Image.Resampling.LANCZOS).resize(
        (width, height), Image.Resampling.LANCZOS
    )


def subpixel_translate(image, rng, amount):
    width, height = image.size
    shift_x = float(rng.uniform(-amount, amount))
    shift_y = float(rng.uniform(-amount, amount))
    pad = 3
    padded = edge_pad(image, pad)
    shifted = padded.transform(
        padded.size,
        Image.Transform.AFFINE,
        (1, 0, -shift_x, 0, 1, -shift_y),
        resample=Image.Resampling.BICUBIC,
    )
    return shifted.crop((pad, pad, pad + width, pad + height)), shift_x, shift_y


def micro_texture_jitter(image, rng, sigma):
    if sigma <= 0:
        return image

    width, height = image.size
    pad = 2
    padded = np.asarray(edge_pad(image, pad)).astype(np.float32)
    src_y = np.arange(height, dtype=np.float32)[:, None] + pad
    src_x = np.arange(width, dtype=np.float32)[None, :] + pad
    src_x = src_x + rng.normal(0.0, sigma, (height, width)).astype(np.float32)
    src_y = src_y + rng.normal(0.0, sigma, (height, width)).astype(np.float32)
    sampled = bilinear_sample(padded, src_x, src_y)
    return Image.fromarray(np.clip(sampled + 0.5, 0, 255).astype(np.uint8))


def bilinear_sample(image_array, src_x, src_y):
    height, width, _ = image_array.shape
    x0 = np.floor(src_x).astype(np.int32)
    y0 = np.floor(src_y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    x0 = np.clip(x0, 0, width - 1)
    y0 = np.clip(y0, 0, height - 1)

    wx = (src_x - x0).astype(np.float32)[..., None]
    wy = (src_y - y0).astype(np.float32)[..., None]

    top = image_array[y0, x0] * (1.0 - wx) + image_array[y0, x1] * wx
    bottom = image_array[y1, x0] * (1.0 - wx) + image_array[y1, x1] * wx
    return top * (1.0 - wy) + bottom * wy


def split_channel_blur(image, radius, chroma_multiplier):
    if chroma_multiplier <= 1.0:
        return image.filter(ImageFilter.GaussianBlur(radius=radius))

    y, cb, cr = image.convert("YCbCr").split()
    y = y.filter(ImageFilter.GaussianBlur(radius=radius))
    chroma_radius = radius * chroma_multiplier
    cb = cb.filter(ImageFilter.GaussianBlur(radius=chroma_radius))
    cr = cr.filter(ImageFilter.GaussianBlur(radius=chroma_radius))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


def edge_pad(image, pad):
    return Image.fromarray(np.pad(np.asarray(image), ((pad, pad), (pad, pad), (0, 0)), mode="edge"))


def srgb_to_linear(value):
    return np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(value):
    return np.where(value <= 0.0031308, value * 12.92, 1.055 * (value ** (1 / 2.4)) - 0.055).astype(np.float32)
