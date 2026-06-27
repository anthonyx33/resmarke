"""Deterministic camera-texture restoration for final JPEG exports."""

import hashlib
import io

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

EXPERT_REFINEMENT_PRESETS = {
    "off": {
        "pixel_alignment_break": {"enabled": False, "value": 0.0},
        "sensor_noise_luma": {"enabled": False, "value": 0.0},
        "lens_vignette": {"enabled": False, "value": 0.0},
        "compression_texture": {"enabled": False, "value": 0.0},
        "bayer_cfa_lite": {"enabled": False, "value": 0.0},
        "lens_character": {"enabled": False, "value": 0.0},
        "double_quantization": {"enabled": False, "value": 0.0},
    },
    "light": {
        "pixel_alignment_break": {"enabled": True, "value": 0.25},
        "sensor_noise_luma": {"enabled": True, "value": 0.20},
        "lens_vignette": {"enabled": True, "value": 0.10},
        "compression_texture": {"enabled": True, "value": 0.20},
        "bayer_cfa_lite": {"enabled": False, "value": 0.30},
        "lens_character": {"enabled": False, "value": 0.20},
        "double_quantization": {"enabled": False, "value": 0.10},
    },
    "balanced": {
        "pixel_alignment_break": {"enabled": True, "value": 0.40},
        "sensor_noise_luma": {"enabled": True, "value": 0.35},
        "lens_vignette": {"enabled": True, "value": 0.15},
        "compression_texture": {"enabled": True, "value": 0.30},
        "bayer_cfa_lite": {"enabled": False, "value": 0.50},
        "lens_character": {"enabled": False, "value": 0.20},
        "double_quantization": {"enabled": False, "value": 0.10},
    },
    "optical": {
        "pixel_alignment_break": {"enabled": True, "value": 0.55},
        "sensor_noise_luma": {"enabled": True, "value": 0.50},
        "lens_vignette": {"enabled": True, "value": 0.20},
        "compression_texture": {"enabled": True, "value": 0.40},
        "bayer_cfa_lite": {"enabled": True, "value": 0.70},
        "lens_character": {"enabled": True, "value": 0.20},
        "double_quantization": {"enabled": True, "value": 0.10},
    },
}

EXPERT_REFINEMENT_TECHNIQUES = tuple(EXPERT_REFINEMENT_PRESETS["off"].keys())


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


def apply_expert_refinement(image, settings, creator_id, seed_extra=""):
    cfg = normalize_expert_refinement(settings)
    report = {
        "enabled": cfg["enabled"],
        "mode": cfg["mode"],
        "intensity": cfg["intensity"],
        "preserve_straight_lines": cfg["preserve_straight_lines"],
        "techniques": {},
    }
    save_options = {}
    if not cfg["enabled"]:
        return report, save_options

    seed_material = f"expert-refinement-v1:{creator_id}:{seed_extra}:{image.width}x{image.height}"
    seed = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    report["seed"] = seed

    pixel = cfg["techniques"]["pixel_alignment_break"]
    if pixel["enabled"] and pixel["effective"] > 0:
        scale = 1.02 + pixel["effective"] * 0.14
        image.paste(resample_roundtrip(image, scale, scale))
        report["techniques"]["pixel_alignment_break"] = {
            "enabled": True,
            "effective": pixel["effective"],
            "scale": scale,
        }
    else:
        report["techniques"]["pixel_alignment_break"] = {"enabled": False}

    bayer = cfg["techniques"]["bayer_cfa_lite"]
    if bayer["enabled"] and bayer["effective"] > 0:
        image.paste(apply_bayer_cfa_lite(image, bayer["effective"]))
        report["techniques"]["bayer_cfa_lite"] = {
            "enabled": True,
            "effective": bayer["effective"],
        }
    else:
        report["techniques"]["bayer_cfa_lite"] = {"enabled": False}

    noise = cfg["techniques"]["sensor_noise_luma"]
    if noise["enabled"] and noise["effective"] > 0:
        image.paste(apply_luma_signal_noise(image, rng, noise["effective"]))
        report["techniques"]["sensor_noise_luma"] = {
            "enabled": True,
            "effective": noise["effective"],
        }
    else:
        report["techniques"]["sensor_noise_luma"] = {"enabled": False}

    vignette = cfg["techniques"]["lens_vignette"]
    if vignette["enabled"] and vignette["effective"] > 0:
        image.paste(apply_micro_vignette(image, vignette["effective"]))
        report["techniques"]["lens_vignette"] = {
            "enabled": True,
            "effective": vignette["effective"],
        }
    else:
        report["techniques"]["lens_vignette"] = {"enabled": False}

    lens = cfg["techniques"]["lens_character"]
    if cfg["preserve_straight_lines"] and lens["enabled"]:
        report["techniques"]["lens_character"] = {
            "enabled": False,
            "reason": "preserve_straight_lines",
        }
    elif lens["enabled"] and lens["effective"] > 0:
        image.paste(apply_lens_character(image, lens["effective"]))
        report["techniques"]["lens_character"] = {
            "enabled": True,
            "effective": lens["effective"],
        }
    else:
        report["techniques"]["lens_character"] = {"enabled": False}

    compression = cfg["techniques"]["compression_texture"]
    if compression["enabled"] and compression["effective"] > 0:
        quality = int(round(96 - compression["effective"] * 12))
        quality = max(90, min(96, quality))
        save_options["jpeg_quality"] = quality
        save_options["jpeg_subsampling"] = "4:2:0"
        report["techniques"]["compression_texture"] = {
            "enabled": True,
            "effective": compression["effective"],
            "final_jpeg_quality": quality,
            "final_jpeg_subsampling": "4:2:0",
        }
    else:
        report["techniques"]["compression_texture"] = {"enabled": False}

    double = cfg["techniques"]["double_quantization"]
    if double["enabled"] and double["effective"] > 0:
        quality = int(round(98 - double["effective"] * 10))
        quality = max(92, min(98, quality))
        image.paste(jpeg_roundtrip(image, quality=quality, subsampling="4:2:0"))
        report["techniques"]["double_quantization"] = {
            "enabled": True,
            "effective": double["effective"],
            "intermediate_jpeg_quality": quality,
            "intermediate_jpeg_subsampling": "4:2:0",
        }
    else:
        report["techniques"]["double_quantization"] = {"enabled": False}

    return report, save_options


def normalize_expert_refinement(settings):
    if not isinstance(settings, dict):
        settings = {}
    mode = str(settings.get("mode", "off")).lower()
    if mode not in EXPERT_REFINEMENT_PRESETS:
        mode = "off"
    intensity = clamp_float(settings.get("intensity", 45), 0.0, 100.0)
    intensity_multiplier = intensity / 100.0
    preserve = bool(settings.get("preserve_straight_lines", True))
    requested = settings.get("techniques", {})
    if not isinstance(requested, dict):
        requested = {}

    techniques = {}
    for key in EXPERT_REFINEMENT_TECHNIQUES:
        preset = EXPERT_REFINEMENT_PRESETS[mode][key]
        override = requested.get(key, {})
        if not isinstance(override, dict):
            override = {}
        enabled = bool(override.get("enabled", preset["enabled"]))
        value = clamp_float(override.get("value", preset["value"]), 0.0, 1.0)
        effective = clamp_float(value * intensity_multiplier, 0.0, 1.0)
        techniques[key] = {
            "enabled": enabled,
            "value": value,
            "effective": effective if enabled else 0.0,
        }

    return {
        "enabled": mode != "off",
        "mode": mode,
        "intensity": intensity,
        "preserve_straight_lines": preserve,
        "techniques": techniques,
    }


def resample_roundtrip(image, scale_x, scale_y):
    width, height = image.size
    scaled_size = (
        max(1, int(round(width * scale_x))),
        max(1, int(round(height * scale_y))),
    )
    return image.resize(scaled_size, Image.Resampling.LANCZOS).resize(
        (width, height), Image.Resampling.LANCZOS
    )


def apply_luma_signal_noise(image, rng, amount):
    srgb = np.asarray(image).astype(np.float32) / 255.0
    linear = srgb_to_linear(srgb)
    luma = (
        linear[..., 0:1] * 0.2126
        + linear[..., 1:2] * 0.7152
        + linear[..., 2:3] * 0.0722
    )
    shot_noise = 0.0009 * amount
    read_noise = 0.0012 * amount
    variance = luma * shot_noise + read_noise ** 2
    noise = rng.normal(0.0, np.sqrt(variance).astype(np.float32)).astype(np.float32)
    linear = np.clip(linear + noise, 0.0, 1.0)
    refined = np.clip(linear_to_srgb(linear) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(refined)


def apply_bayer_cfa_lite(image, amount):
    rgb = np.asarray(image).astype(np.float32)
    height, width, _ = rgb.shape
    yy, xx = np.indices((height, width))
    red_mask = ((yy % 2) == 0) & ((xx % 2) == 0)
    blue_mask = ((yy % 2) == 1) & ((xx % 2) == 1)
    green_mask = ~(red_mask | blue_mask)

    masks = (
        red_mask.astype(np.float32),
        green_mask.astype(np.float32),
        blue_mask.astype(np.float32),
    )
    demosaiced = []
    for channel, mask in enumerate(masks):
        demosaiced.append(demosaic_channel(rgb[..., channel], mask))
    demosaiced_rgb = np.stack(demosaiced, axis=2)

    # Keep this intentionally lite: enough channel decorrelation to mimic a
    # camera color-filter array, but far below a full demosaic softness pass.
    blend = min(0.22, amount * 0.28)
    refined = rgb * (1.0 - blend) + demosaiced_rgb * blend
    refined_image = Image.fromarray(np.clip(refined + 0.5, 0, 255).astype(np.uint8))

    chroma_radius = min(0.28, amount * 0.36)
    if chroma_radius <= 0:
        return refined_image
    y, cb, cr = refined_image.convert("YCbCr").split()
    cb = cb.filter(ImageFilter.GaussianBlur(radius=chroma_radius))
    cr = cr.filter(ImageFilter.GaussianBlur(radius=chroma_radius))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


def demosaic_channel(channel, mask):
    values = channel * mask
    sum_values = box3(values)
    sum_mask = box3(mask)
    interpolated = sum_values / np.maximum(sum_mask, 1e-6)
    return np.where(mask > 0, channel, interpolated)


def box3(array):
    padded = np.pad(array, ((1, 1), (1, 1)), mode="edge")
    total = np.zeros_like(array, dtype=np.float32)
    for y_offset in range(3):
        for x_offset in range(3):
            total += padded[y_offset : y_offset + array.shape[0], x_offset : x_offset + array.shape[1]]
    return total


def apply_micro_vignette(image, amount):
    width, height = image.size
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)[None, :]
    radius = np.sqrt(x * x + y * y)
    falloff = np.clip((radius - 0.28) / 1.12, 0.0, 1.0)
    strength = 0.035 * amount
    mask = (1.0 - falloff * falloff * strength)[..., None]
    srgb = np.asarray(image).astype(np.float32) / 255.0
    refined = np.clip(srgb * mask * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(refined)


def apply_lens_character(image, amount):
    width, height = image.size
    pad = 3
    padded = np.asarray(edge_pad(image, pad)).astype(np.float32)
    norm_x, norm_y = radial_source_grid(width, height)
    base_k = -0.0045 * amount
    ca_k = 0.0018 * amount
    channels = []
    for channel, k in enumerate((base_k - ca_k, base_k, base_k + ca_k)):
        src_x, src_y = apply_radial_k(norm_x, norm_y, width, height, pad, k)
        sampled = bilinear_sample(padded[..., channel : channel + 1], src_x, src_y)
        channels.append(sampled)
    refined = np.concatenate(channels, axis=2)
    return Image.fromarray(np.clip(refined + 0.5, 0, 255).astype(np.uint8))


def radial_source_grid(width, height):
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)[None, :]
    return x, y


def apply_radial_k(norm_x, norm_y, width, height, pad, k):
    radius2 = norm_x * norm_x + norm_y * norm_y
    factor = 1.0 + k * radius2
    src_x = ((norm_x * factor + 1.0) * 0.5 * (width - 1)) + pad
    src_y = ((norm_y * factor + 1.0) * 0.5 * (height - 1)) + pad
    return src_x.astype(np.float32), src_y.astype(np.float32)


def jpeg_roundtrip(image, quality, subsampling):
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, subsampling=subsampling)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB")


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


def clamp_float(value, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = low
    if not np.isfinite(parsed):
        parsed = low
    return max(low, min(high, parsed))
