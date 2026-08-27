"""Deterministic 4D-1a H1/H2 source-energy transfer.

The source supplies only local energy targets.  Output coefficients always come
from the remint bands, so source phase and source pixels are never synthesized
into the result.  All arrays used by the transfer are float64; the only
quantization before final output is the frozen PIL Gaussian recipe.
"""

import hashlib
import math

import numpy as np
from PIL import Image, ImageFilter


ALPHA_REQUESTED = 0.10
GAIN_MAX = 1.10
ENERGY_GAIN_MAX = 1.21
CAP_RELATIVE_TOLERANCE = 1e-9
NCC_EPSILON = 1e-9
LOCKED_SEEDS = frozenset(("lab-ctla1", "lab-ctla2"))

LUMA_COEFFICIENTS = np.array((0.2126, 0.7152, 0.0722), dtype=np.float64)


class Transfer4D1AError(RuntimeError):
    """A candidate-only failure that must leave incumbent pixels untouched."""


def pixel_sha256_array(rgb_uint8):
    """Hash RGB dimensions and pixels using the checkpoint pixel-hash contract."""
    array = np.ascontiguousarray(rgb_uint8, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("pixel hash requires an HxWx3 RGB buffer")
    digest = hashlib.sha256()
    digest.update(int(array.shape[1]).to_bytes(8, "big"))
    digest.update(int(array.shape[0]).to_bytes(8, "big"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def apply_transfer_4d_1a(remint_image, source_image, alpha=ALPHA_REQUESTED):
    """Apply the sealed source-energy transfer and return ``(RGB image, report)``.

    ``alpha=0`` is accepted only for the build fixture.  A production candidate
    is always requested at exactly 0.10 by the pipeline boundary.
    """
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float, np.integer, np.floating)):
        raise ValueError("4D-1a alpha must be exactly 0 or 0.10")
    alpha = float(alpha)
    if not np.isfinite(alpha) or alpha not in (0.0, ALPHA_REQUESTED):
        raise ValueError("4D-1a alpha must be exactly 0 or 0.10")

    remint_pil = _rgb_image(remint_image)
    source_pil = _rgb_image(source_image)
    remint_u8 = np.asarray(remint_pil, dtype=np.uint8).copy()
    r2_pil = source_pil.resize(remint_pil.size, Image.Resampling.LANCZOS)
    r2_u8 = np.asarray(r2_pil, dtype=np.uint8).copy()
    input_hashes = {
        "o2_pre_transfer_pixels_sha256": pixel_sha256_array(remint_u8),
        "r2_pixels_sha256": pixel_sha256_array(r2_u8),
    }

    if alpha == 0.0:
        report = _empty_report(input_hashes, reason="alpha_zero")
        return remint_pil.copy(), report
    if min(remint_u8.shape[:2]) < 2:
        report = _empty_report(input_hashes, reason="insufficient_image_geometry")
        return remint_pil.copy(), report

    remint_rgb = remint_u8.astype(np.float64) / 255.0
    r2_rgb = r2_u8.astype(np.float64) / 255.0
    remint_luma = _luma(remint_rgb)
    source_luma = _luma(r2_rgb)
    if not np.isfinite(remint_luma).all() or not np.isfinite(source_luma).all():
        report = _empty_report(input_hashes, reason="non_finite_input")
        return remint_pil.copy(), report

    displacement = _pyramid_alignment(remint_luma, source_luma)
    dx = displacement["dx"]
    dy = displacement["dy"]
    d_scale = displacement["scale_agreement"]

    remint_smooth = {
        "H1": _gauss(remint_luma, 0.7),
        "H1_END": _gauss(remint_luma, 1.4),
        "H2_END": _gauss(remint_luma, 4.0),
    }
    source_smooth = {
        "H1": _gauss(source_luma, 0.7),
        "H1_END": _gauss(source_luma, 1.4),
        "H2_END": _gauss(source_luma, 4.0),
    }
    remint_bands = {
        "H1": remint_smooth["H1"] - remint_smooth["H1_END"],
        "H2": remint_smooth["H1_END"] - remint_smooth["H2_END"],
    }
    source_bands = {
        "H1": _warp_bilinear(source_smooth["H1"] - source_smooth["H1_END"], dx, dy),
        "H2": _warp_bilinear(source_smooth["H1_END"] - source_smooth["H2_END"], dx, dy),
    }

    noise_energy = _noise_energy(source_luma, source_smooth["H1_END"] - source_smooth["H2_END"])
    edge_exclusion = _strong_edge_exclusion(remint_smooth, source_smooth, dx, dy)
    support_details = {
        name: _band_support(remint_bands[name], source_bands[name], d_scale, noise_energy)
        for name in ("H1", "H2")
    }
    cross_scale = support_details["H1"]["numeric_support"] & support_details["H2"]["numeric_support"]
    complete_support = cross_scale & ~edge_exclusion

    weights = {}
    for name in ("H1", "H2"):
        details = support_details[name]
        w_raw = np.minimum.reduce((
            details["margins"]["scale"],
            details["margins"]["residual"],
            details["margins"]["orientation"],
            details["margins"]["ncc"],
            details["margins"]["snr"],
        ))
        w_raw = np.where(complete_support, w_raw, 0.0)
        weights[name] = _smooth_weight(w_raw, complete_support)

    corrected_bands = {}
    gains = {}
    cap_results = {}
    effective_alpha = {}
    cap_failed = False
    for name in ("H1", "H2"):
        band_result = _transfer_band(
            remint_bands[name], source_bands[name], weights[name], alpha
        )
        corrected_bands[name] = band_result["band"]
        gains[name] = band_result["gain"]
        cap_results[name] = band_result["cap"]
        effective_alpha[name] = band_result["alpha_effective"]
        cap_failed = cap_failed or not band_result["cap"]["passed"]

    reject_counts = _reject_counts(support_details, cross_scale, edge_exclusion, complete_support)
    if cap_failed:
        report = _build_report(
            applied=False,
            fail_closed_reason="window_energy_cap_verification",
            input_hashes=input_hashes,
            weights=weights,
            support=complete_support,
            reject_counts=reject_counts,
            remint_bands=remint_bands,
            source_bands=source_bands,
            corrected_bands=remint_bands,
            gains={name: np.ones_like(remint_luma) for name in ("H1", "H2")},
            alpha_effective={name: np.zeros_like(remint_luma) for name in ("H1", "H2")},
            cap_results=cap_results,
            noise_energy=noise_energy,
            capped_fraction=0.0,
        )
        return remint_pil.copy(), report

    delta = ((corrected_bands["H1"] - remint_bands["H1"])
             + (corrected_bands["H2"] - remint_bands["H2"]))
    out_u8, capped_fraction = _synthesize_rgb(remint_rgb, delta)
    output = Image.fromarray(out_u8, mode="RGB")
    applied = not np.array_equal(out_u8, remint_u8)
    report = _build_report(
        applied=applied,
        fail_closed_reason=None if applied else "no_eligible_quantized_change",
        input_hashes=input_hashes,
        weights=weights,
        support=complete_support,
        reject_counts=reject_counts,
        remint_bands=remint_bands,
        source_bands=source_bands,
        corrected_bands=corrected_bands,
        gains=gains,
        alpha_effective=effective_alpha,
        cap_results=cap_results,
        noise_energy=noise_energy,
        capped_fraction=capped_fraction,
    )
    return output, report


def attach_transfer_diagnostic_context(report, source_image, o2_image, transfer_image):
    """Attach private, in-memory context that the worker consumes after O5."""
    if not isinstance(report, dict):
        return
    source = np.asarray(_rgb_image(source_image), dtype=np.uint8).copy()
    o2 = np.asarray(_rgb_image(o2_image), dtype=np.uint8).copy()
    transferred = np.asarray(_rgb_image(transfer_image), dtype=np.uint8).copy()
    report["_diagnostic_context"] = {
        "source": source,
        "o2": o2,
        "transfer": transferred,
    }


def finalize_transfer_report(report, o5_image):
    """Finalize O2/O2_transfer to O5 losses and remove private array context."""
    if not isinstance(report, dict):
        return report
    context = report.pop("_diagnostic_context", None)
    if not isinstance(context, dict):
        return report
    try:
        source = context["source"]
        o2 = context["o2"]
        transferred = context["transfer"]
        o5 = np.asarray(_rgb_image(o5_image), dtype=np.uint8).copy()
        m_o2 = _detail_metrics(o2, source)
        m_transfer = _detail_metrics(transferred, source)
        m_o5 = _detail_metrics(o5, source)
        report["diagnostic_losses"] = {
            "pre_transfer_o2_to_o5": _transition_loss(m_o2, m_o5),
            "o2_transfer_to_o5": _transition_loss(m_transfer, m_o5),
        }
        report["o5_pixels_sha256"] = pixel_sha256_array(o5)
        report["finalized_post_o5"] = True
    except Exception as exc:  # noqa: BLE001 - report diagnostics cannot alter delivery
        report["diagnostic_losses"] = {
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
        }
        report["finalized_post_o5"] = False
    return report


def discard_transfer_diagnostic_context(report):
    """Make a partially built report serialization-safe on a downstream error."""
    if isinstance(report, dict):
        report.pop("_diagnostic_context", None)


def _rgb_image(value):
    if isinstance(value, Image.Image):
        return value.convert("RGB")
    array = np.asarray(value)
    if array.dtype != np.uint8:
        if np.issubdtype(array.dtype, np.floating):
            array = np.rint(np.clip(array, 0.0, 1.0) * 255.0).astype(np.uint8)
        else:
            array = np.clip(array, 0, 255).astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def _luma(rgb):
    return np.sum(np.asarray(rgb, dtype=np.float64) * LUMA_COEFFICIENTS, axis=2)


def _gauss(values, sigma):
    """Exact frozen checkpoint_attribution._gauss numeric recipe."""
    quantized = (np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0) * 255.0).astype(np.uint8)
    image = Image.fromarray(quantized, mode="L")
    image = image.filter(ImageFilter.GaussianBlur(radius=float(sigma)))
    return np.asarray(image, dtype=np.float64) / 255.0


def _edge_mag(values):
    """Exact frozen np.gradient magnitude recipe (deliberately not Sobel)."""
    gy, gx = np.gradient(np.asarray(values, dtype=np.float64))
    return np.hypot(gx, gy)


def _pyramid_alignment(target, source):
    target_pyramid = [np.asarray(target, dtype=np.float64)]
    source_pyramid = [np.asarray(source, dtype=np.float64)]
    for _ in range(2):
        target_pyramid.append(_downsample_two(_gauss(target_pyramid[-1], 1.0)))
        source_pyramid.append(_downsample_two(_gauss(source_pyramid[-1], 1.0)))

    previous = None
    previous_agreement = None
    final = None
    for level in (2, 1, 0):
        target_level = target_pyramid[level]
        source_level = source_pyramid[level]
        if previous is None:
            init_dx = np.zeros_like(target_level)
            init_dy = np.zeros_like(target_level)
        else:
            init_dx = _resize_bilinear(previous["dx"], target_level.shape) * 2.0
            init_dy = _resize_bilinear(previous["dy"], target_level.shape) * 2.0
        matched = _block_match_level(target_level, source_level, init_dx, init_dy)
        if previous is None:
            agreement = np.zeros_like(target_level)
        else:
            current = np.hypot(matched["dx"] - init_dx, matched["dy"] - init_dy) * (2.0 ** level)
            prior = _resize_bilinear(previous_agreement, target_level.shape)
            agreement = np.maximum(current, prior)
        matched["scale_agreement"] = agreement
        previous = matched
        previous_agreement = agreement
        final = matched
    return final


def _downsample_two(values):
    array = (np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
    height, width = array.shape
    image = Image.fromarray(array, mode="L")
    image = image.resize((max(1, (width + 1) // 2), max(1, (height + 1) // 2)), Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.float64) / 255.0


def _block_match_level(target, source, init_dx, init_dy, block=32, stride=16, radius=8):
    height, width = target.shape
    ys = _grid_axis(height, stride)
    xs = _grid_axis(width, stride)
    grid_dx = np.zeros((len(ys), len(xs)), dtype=np.float64)
    grid_dy = np.zeros_like(grid_dx)
    offsets = np.arange(-(block // 2), block - block // 2, dtype=np.float64)
    for yi, center_y in enumerate(ys):
        for xi, center_x in enumerate(xs):
            initial_x = float(init_dx[center_y, center_x])
            initial_y = float(init_dy[center_y, center_x])
            target_patch = _sample_bilinear(
                target,
                center_y + offsets[:, None],
                center_x + offsets[None, :],
            )
            patch_offsets = np.arange(-(block // 2) - radius, block - block // 2 + radius, dtype=np.float64)
            source_search = _sample_bilinear(
                source,
                center_y + initial_y + patch_offsets[:, None],
                center_x + initial_x + patch_offsets[None, :],
            )
            windows = np.lib.stride_tricks.sliding_window_view(source_search, (block, block))
            scores = _ncc_candidates(target_patch, windows)
            flat_index = int(np.argmax(scores))
            peak_y, peak_x = np.unravel_index(flat_index, scores.shape)
            residual_x = float(peak_x - radius)
            residual_y = float(peak_y - radius)
            sub_x = _parabolic_offset(scores[peak_y, :], peak_x)
            sub_y = _parabolic_offset(scores[:, peak_x], peak_y)
            grid_dx[yi, xi] = initial_x + residual_x + sub_x
            grid_dy[yi, xi] = initial_y + residual_y + sub_y
    return {
        "dx": _interpolate_grid(grid_dx, ys, xs, target.shape),
        "dy": _interpolate_grid(grid_dy, ys, xs, target.shape),
    }


def _ncc_candidates(target_patch, windows):
    target_centered = target_patch - float(np.mean(target_patch))
    target_energy = float(np.sum(target_centered * target_centered))
    window_mean = np.mean(windows, axis=(-2, -1), dtype=np.float64)
    centered = windows - window_mean[..., None, None]
    numerator = np.einsum("ij,xyij->xy", target_centered, centered, optimize=True)
    denominator = np.sqrt(target_energy * np.sum(centered * centered, axis=(-2, -1), dtype=np.float64))
    scores = np.full(numerator.shape, -np.inf, dtype=np.float64)
    valid = np.isfinite(numerator) & np.isfinite(denominator) & (denominator > NCC_EPSILON)
    scores[valid] = numerator[valid] / denominator[valid]
    return scores


def _parabolic_offset(profile, index):
    if index <= 0 or index >= len(profile) - 1:
        return 0.0
    left = float(profile[index - 1])
    center = float(profile[index])
    right = float(profile[index + 1])
    if not np.isfinite((left, center, right)).all():
        return 0.0
    denominator = left - 2.0 * center + right
    if denominator >= -1e-15:
        return 0.0
    offset = 0.5 * (left - right) / denominator
    return float(np.clip(offset, -0.5, 0.5)) if np.isfinite(offset) else 0.0


def _band_support(remint_band, source_band, d_scale, noise_energy):
    energy_remint = _window_field(remint_band * remint_band)
    energy_source = _window_field(source_band * source_band)
    ncc = _local_ncc(remint_band, source_band)
    orientation = _orientation_difference(remint_band, source_band)
    residual = _residual_displacement(remint_band, source_band)
    snr = np.minimum(energy_remint["full"], energy_source["full"]) / max(float(noise_energy), 1e-6)

    gates = {
        "scale": np.isfinite(d_scale) & (d_scale <= 0.25),
        "residual": np.isfinite(residual) & (residual <= 0.50),
        "orientation": np.isfinite(orientation) & (orientation <= 15.0),
        "ncc": np.isfinite(ncc) & (ncc >= 0.80),
        "snr": np.isfinite(snr) & (snr >= 4.0),
    }
    numeric_support = np.logical_and.reduce(tuple(gates.values()))
    margins = {
        "scale": np.clip((0.25 - d_scale) / 0.25, 0.0, 1.0),
        "residual": np.clip((0.50 - residual) / 0.50, 0.0, 1.0),
        "orientation": np.clip((15.0 - orientation) / 15.0, 0.0, 1.0),
        "ncc": np.clip((ncc - 0.80) / 0.20, 0.0, 1.0),
        "snr": np.clip((np.minimum(snr, 8.0) - 4.0) / 4.0, 0.0, 1.0),
    }
    for key in margins:
        margins[key] = np.where(np.isfinite(margins[key]), margins[key], 0.0)
    return {
        "gates": gates,
        "margins": margins,
        "numeric_support": numeric_support,
        "energy_remint": energy_remint,
        "energy_source": energy_source,
        "ncc": ncc,
        "orientation": orientation,
        "residual": residual,
        "snr": snr,
    }


def _local_ncc(left, right):
    mean_left = _window_field(left)["full"]
    mean_right = _window_field(right)["full"]
    mean_left2 = _window_field(left * left)["full"]
    mean_right2 = _window_field(right * right)["full"]
    mean_product = _window_field(left * right)["full"]
    covariance = mean_product - mean_left * mean_right
    variance_left = np.maximum(mean_left2 - mean_left * mean_left, 0.0)
    variance_right = np.maximum(mean_right2 - mean_right * mean_right, 0.0)
    denominator = np.sqrt(variance_left * variance_right)
    result = np.zeros_like(covariance)
    valid = np.isfinite(covariance) & np.isfinite(denominator) & (denominator > NCC_EPSILON)
    result[valid] = covariance[valid] / denominator[valid]
    return np.clip(result, -1.0, 1.0)


def _orientation_difference(left, right):
    ly, lx = np.gradient(left)
    ry, rx = np.gradient(right)
    left_angle = _tensor_angle(lx, ly)
    right_angle = _tensor_angle(rx, ry)
    difference = np.abs(left_angle - right_angle)
    difference = np.minimum(difference, np.pi - difference)
    return np.degrees(np.clip(difference, 0.0, np.pi / 2.0))


def _tensor_angle(gx, gy):
    jxx = _window_field(gx * gx)["full"]
    jyy = _window_field(gy * gy)["full"]
    jxy = _window_field(gx * gy)["full"]
    return np.mod(0.5 * np.arctan2(2.0 * jxy, jxx - jyy), np.pi)


def _residual_displacement(target_band, aligned_source_band):
    gy, gx = np.gradient(aligned_source_band)
    error = aligned_source_band - target_band
    jxx = _window_field(gx * gx)["full"]
    jyy = _window_field(gy * gy)["full"]
    jxy = _window_field(gx * gy)["full"]
    bx = _window_field(gx * error)["full"]
    by = _window_field(gy * error)["full"]
    determinant = jxx * jyy - jxy * jxy
    dx = np.full_like(determinant, np.inf)
    dy = np.full_like(determinant, np.inf)
    valid = np.isfinite(determinant) & (np.abs(determinant) > 1e-12)
    dx[valid] = -(jyy[valid] * bx[valid] - jxy[valid] * by[valid]) / determinant[valid]
    dy[valid] = -(-jxy[valid] * bx[valid] + jxx[valid] * by[valid]) / determinant[valid]
    residual = np.hypot(dx, dy)
    residual[~np.isfinite(residual)] = np.inf
    return residual


def _strong_edge_exclusion(remint_smooth, source_smooth, dx, dy):
    masks = []
    for key in ("H1", "H1_END"):
        remint_edge = _edge_mag(remint_smooth[key])
        source_edge = _edge_mag(_warp_bilinear(source_smooth[key], dx, dy))
        remint_threshold = float(np.percentile(remint_edge, 92))
        source_threshold = float(np.percentile(source_edge, 92))
        masks.append(remint_edge > remint_threshold)
        masks.append(source_edge > source_threshold)
    union = np.logical_or.reduce(masks)
    return _euclidean_dilate_two(union)


def _euclidean_dilate_two(mask):
    mask = np.asarray(mask, dtype=bool)
    height, width = mask.shape
    output = np.zeros_like(mask)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx * dx + dy * dy > 4:
                continue
            src_y0 = max(0, -dy)
            src_y1 = min(height, height - dy)
            src_x0 = max(0, -dx)
            src_x1 = min(width, width - dx)
            dst_y0 = src_y0 + dy
            dst_y1 = src_y1 + dy
            dst_x0 = src_x0 + dx
            dst_x1 = src_x1 + dx
            output[dst_y0:dst_y1, dst_x0:dst_x1] |= mask[src_y0:src_y1, src_x0:src_x1]
    return output


def _noise_energy(source_luma, source_h2):
    edge = _edge_mag(source_luma)
    height, width = source_luma.shape
    tiles = []
    order = 0
    for y0 in range(0, height, 32):
        for x0 in range(0, width, 32):
            y1 = min(height, y0 + 32)
            x1 = min(width, x0 + 32)
            score = float(np.mean(edge[y0:y1, x0:x1] ** 2, dtype=np.float64))
            tiles.append((score, order, source_h2[y0:y1, x0:x1].reshape(-1)))
            order += 1
    count = max(1, int(math.ceil(len(tiles) * 0.20)))
    selected = sorted(tiles, key=lambda item: (item[0], item[1]))[:count]
    samples = np.concatenate([item[2] for item in selected]).astype(np.float64, copy=False)
    samples = samples[np.isfinite(samples)]
    if samples.size == 0:
        return 1e-6
    median = float(np.median(samples))
    mad = float(np.median(np.abs(samples - median)))
    return max((1.4826 * mad) ** 2, 1e-6)


def _smooth_weight(w_raw, support_binary):
    smoothed = np.clip(_gauss(np.clip(w_raw, 0.0, 1.0), 3.0), 0.0, 1.0)
    return smoothed * np.asarray(support_binary, dtype=np.float64)


def _initial_gain(energy_source, energy_remint, weight, alpha):
    energy_source = np.asarray(energy_source, dtype=np.float64)
    energy_remint = np.asarray(energy_remint, dtype=np.float64)
    weight = np.asarray(weight, dtype=np.float64)
    gain = np.ones_like(energy_remint)
    valid = (np.isfinite(energy_source) & np.isfinite(energy_remint) & np.isfinite(weight)
             & (energy_source > energy_remint) & (energy_remint > 0.0) & (weight > 0.0))
    ratio_term = np.zeros_like(gain)
    ratio_term[valid] = np.sqrt(energy_source[valid] / energy_remint[valid]) - 1.0
    dose = np.minimum(float(alpha) * np.clip(weight, 0.0, 1.0) * ratio_term, 0.10)
    dose = np.where(np.isfinite(dose) & (dose > 0.0), dose, 0.0)
    gain += dose
    return np.clip(gain, 1.0, GAIN_MAX)


def _transfer_band(remint_band, source_band, weight, alpha):
    energy_remint = _window_field(remint_band * remint_band)
    energy_source = _window_field(source_band * source_band)
    gain = _initial_gain(energy_source["full"], energy_remint["full"], weight, alpha)
    initial_gain = gain.copy()
    post = _window_field((gain * remint_band) ** 2)
    target_grid = np.minimum(ENERGY_GAIN_MAX * energy_remint["grid"], energy_source["grid"])
    affected_grid = _window_grid_only((gain > 1.0).astype(np.float64), energy_remint["ys"], energy_remint["xs"]) > 0.0
    valid_grid = affected_grid & (energy_source["grid"] > energy_remint["grid"])
    correction_grid = np.ones_like(target_grid)
    # An enhanced window whose source has no energy surplus is suppressed.  It
    # is not a valid cap-verification window because the untouched remint may
    # already exceed the source target there.
    correction_grid[affected_grid & ~valid_grid] = 0.0
    needs_correction = valid_grid & np.isfinite(post["grid"]) & np.isfinite(target_grid) & (post["grid"] > target_grid)
    positive_target = needs_correction & (target_grid > 0.0) & (post["grid"] > 0.0)
    correction_grid[positive_target] = np.sqrt(target_grid[positive_target] / post["grid"][positive_target])
    correction_grid[needs_correction & ~positive_target] = 0.0
    correction = _interpolate_grid(correction_grid, energy_remint["ys"], energy_remint["xs"], remint_band.shape)
    gain = np.clip(gain * correction, 1.0, GAIN_MAX)
    corrected = gain * remint_band
    final_energy = _window_field(corrected * corrected)
    cap = _verify_caps(final_energy["grid"], target_grid, valid_grid)

    ratio_term = np.zeros_like(gain)
    eligible = ((energy_source["full"] > energy_remint["full"])
                & (energy_remint["full"] > 0.0) & (weight > 0.0))
    ratio_term[eligible] = np.sqrt(energy_source["full"][eligible] / energy_remint["full"][eligible]) - 1.0
    alpha_effective = np.zeros_like(gain)
    alpha_valid = eligible & (ratio_term > 0.0)
    alpha_effective[alpha_valid] = (gain[alpha_valid] - 1.0) / ratio_term[alpha_valid]
    alpha_effective = np.clip(np.where(np.isfinite(alpha_effective), alpha_effective, 0.0), 0.0, alpha)
    cap["initial_gain_max"] = _fixed(np.max(initial_gain))
    cap["final_gain_min"] = _fixed(np.min(gain))
    cap["final_gain_max"] = _fixed(np.max(gain))
    return {"band": corrected, "gain": gain, "cap": cap, "alpha_effective": alpha_effective}


def _verify_caps(final_grid, target_grid, valid_grid):
    valid = np.asarray(valid_grid, dtype=bool) & np.isfinite(final_grid) & np.isfinite(target_grid)
    invalid_numeric = np.asarray(valid_grid, dtype=bool) & ~(
        np.isfinite(final_grid) & np.isfinite(target_grid)
    )
    excess = np.zeros_like(final_grid, dtype=np.float64)
    positive = valid & (target_grid > 0.0)
    excess[positive] = np.maximum(final_grid[positive] / target_grid[positive] - 1.0, 0.0)
    zero_target = valid & (target_grid <= 0.0)
    excess[zero_target & (final_grid > 0.0)] = np.inf
    maximum = float(np.max(excess[valid])) if np.any(valid) else 0.0
    passed = not np.any(invalid_numeric) and maximum <= CAP_RELATIVE_TOLERANCE
    return {
        "passed": bool(passed),
        "relative_tolerance": "0.000000001000",
        "valid_windows": int(np.count_nonzero(valid_grid)),
        "invalid_numeric_windows": int(np.count_nonzero(invalid_numeric)),
        "max_relative_excess": _fixed(maximum) if np.isfinite(maximum) else "inf",
    }


def _synthesize_rgb(remint_rgb, delta):
    remint_rgb = np.asarray(remint_rgb, dtype=np.float64)
    delta = np.where(np.isfinite(delta), delta, 0.0)
    lower = -np.min(remint_rgb, axis=2)
    upper = 1.0 - np.max(remint_rgb, axis=2)
    safe = np.clip(delta, lower, upper)
    capped = safe != delta
    output = remint_rgb + safe[..., None]
    output_u8 = np.rint(np.clip(output, 0.0, 1.0) * 255.0).astype(np.uint8)
    return output_u8, float(np.mean(capped, dtype=np.float64))


def _window_field(values, size=15, stride=3):
    values = np.asarray(values, dtype=np.float64)
    ys = _grid_axis(values.shape[0], stride)
    xs = _grid_axis(values.shape[1], stride)
    grid = _window_grid_only(values, ys, xs, size=size)
    return {
        "grid": grid,
        "full": _interpolate_grid(grid, ys, xs, values.shape),
        "ys": ys,
        "xs": xs,
    }


def _window_grid_only(values, ys, xs, size=15):
    radius = size // 2
    y_offsets = np.arange(-radius, radius + 1)
    x_offsets = np.arange(-radius, radius + 1)
    y_indices = _reflect_indices(ys[:, None] + y_offsets[None, :], values.shape[0])
    x_indices = _reflect_indices(xs[:, None] + x_offsets[None, :], values.shape[1])
    rows = np.take(values, y_indices, axis=0)
    sampled = np.take(rows, x_indices, axis=2)
    return np.mean(sampled, axis=(1, 3), dtype=np.float64)


def _grid_axis(length, stride):
    if length <= 1:
        return np.array((0,), dtype=np.int64)
    values = list(range(0, length, stride))
    if values[-1] != length - 1:
        values.append(length - 1)
    return np.asarray(values, dtype=np.int64)


def _interpolate_grid(grid, ys, xs, shape):
    height, width = shape
    x_full = np.arange(width, dtype=np.float64)
    y_full = np.arange(height, dtype=np.float64)
    horizontal = np.empty((len(ys), width), dtype=np.float64)
    for row in range(len(ys)):
        horizontal[row] = np.interp(x_full, xs, grid[row])
    output = np.empty((height, width), dtype=np.float64)
    for column in range(width):
        output[:, column] = np.interp(y_full, ys, horizontal[:, column])
    return output


def _resize_bilinear(values, shape):
    source_y = np.linspace(0.0, max(values.shape[0] - 1, 0), shape[0], dtype=np.float64)
    source_x = np.linspace(0.0, max(values.shape[1] - 1, 0), shape[1], dtype=np.float64)
    x_base = np.arange(values.shape[1], dtype=np.float64)
    y_base = np.arange(values.shape[0], dtype=np.float64)
    horizontal = np.empty((values.shape[0], shape[1]), dtype=np.float64)
    for row in range(values.shape[0]):
        horizontal[row] = np.interp(source_x, x_base, values[row])
    output = np.empty(shape, dtype=np.float64)
    for column in range(shape[1]):
        output[:, column] = np.interp(source_y, y_base, horizontal[:, column])
    return output


def _warp_bilinear(values, dx, dy):
    y, x = np.mgrid[0:values.shape[0], 0:values.shape[1]]
    return _sample_bilinear(values, y.astype(np.float64) + dy, x.astype(np.float64) + dx)


def _sample_bilinear(values, y, x):
    y_reflected = _reflect_coordinates(np.broadcast_to(y, np.broadcast_shapes(np.shape(y), np.shape(x))), values.shape[0])
    x_reflected = _reflect_coordinates(np.broadcast_to(x, np.broadcast_shapes(np.shape(y), np.shape(x))), values.shape[1])
    y0 = np.floor(y_reflected).astype(np.int64)
    x0 = np.floor(x_reflected).astype(np.int64)
    y1 = np.minimum(y0 + 1, values.shape[0] - 1)
    x1 = np.minimum(x0 + 1, values.shape[1] - 1)
    wy = y_reflected - y0
    wx = x_reflected - x0
    return ((1.0 - wy) * (1.0 - wx) * values[y0, x0]
            + (1.0 - wy) * wx * values[y0, x1]
            + wy * (1.0 - wx) * values[y1, x0]
            + wy * wx * values[y1, x1])


def _reflect_coordinates(coordinates, length):
    coordinates = np.asarray(coordinates, dtype=np.float64)
    if length <= 1:
        return np.zeros_like(coordinates)
    period = float(2 * (length - 1))
    folded = np.mod(coordinates, period)
    return np.where(folded <= length - 1, folded, period - folded)


def _reflect_indices(indices, length):
    indices = np.asarray(indices, dtype=np.int64)
    if length <= 1:
        return np.zeros_like(indices)
    period = 2 * (length - 1)
    folded = np.mod(indices, period)
    return np.where(folded < length, folded, period - folded).astype(np.int64)


def _reject_counts(details, cross_scale, edge_exclusion, complete_support):
    total = int(cross_scale.size)
    counts = {}
    for name in ("H1", "H2"):
        counts[name] = {
            gate: int(total - np.count_nonzero(details[name]["gates"][gate]))
            for gate in ("scale", "residual", "orientation", "ncc", "snr")
        }
    counts["cross_scale"] = int(total - np.count_nonzero(cross_scale))
    counts["strong_edge_exclusion"] = int(np.count_nonzero(edge_exclusion))
    counts["complete_support"] = int(total - np.count_nonzero(complete_support))
    counts["pixels"] = total
    return counts


def _build_report(applied, fail_closed_reason, input_hashes, weights, support,
                  reject_counts, remint_bands, source_bands, corrected_bands,
                  gains, alpha_effective, cap_results, noise_energy,
                  capped_fraction):
    supported_count = int(np.count_nonzero(support))
    pixel_count = int(support.size)
    executed = (gains["H1"] > 1.0) | (gains["H2"] > 1.0)
    weight_values = np.concatenate([weights[name][support] for name in ("H1", "H2")]) if supported_count else np.array([], dtype=np.float64)
    return {
        "applied": bool(applied),
        "alpha_requested": "0.100000000000",
        "alpha_effective": {
            name: _stats(alpha_effective[name], gains[name] > 1.0)
            for name in ("H1", "H2")
        },
        "coverage": _fixed(np.count_nonzero(executed) / float(max(pixel_count, 1))),
        "support_coverage": _fixed(supported_count / float(max(pixel_count, 1))),
        "mean_w": _fixed(np.mean(weight_values, dtype=np.float64) if weight_values.size else 0.0),
        "per_gate_reject_counts": reject_counts,
        "band_energy_ratios": {
            name: {
                "source_to_remint_before": _energy_ratio(source_bands[name], remint_bands[name]),
                "after_to_remint": _energy_ratio(corrected_bands[name], remint_bands[name]),
                "after_to_source": _energy_ratio(corrected_bands[name], source_bands[name]),
            }
            for name in ("H1", "H2")
        },
        "capped_delta_pixel_fraction": _fixed(capped_fraction),
        "cap_enforcement": {
            "passed": bool(all(cap_results[name]["passed"] for name in ("H1", "H2"))),
            "H1": cap_results["H1"],
            "H2": cap_results["H2"],
        },
        "input_pixel_hashes": input_hashes,
        "noise_energy": _fixed(noise_energy),
        "fail_closed_reason": fail_closed_reason,
        "finalized_post_o5": False,
    }


def _empty_report(input_hashes, reason):
    empty_cap = {
        "passed": True,
        "relative_tolerance": "0.000000001000",
        "valid_windows": 0,
        "invalid_numeric_windows": 0,
        "max_relative_excess": "0.000000000000",
        "initial_gain_max": "1.000000000000",
        "final_gain_min": "1.000000000000",
        "final_gain_max": "1.000000000000",
    }
    return {
        "applied": False,
        "alpha_requested": "0.100000000000",
        "alpha_effective": {"H1": _zero_stats(), "H2": _zero_stats()},
        "coverage": "0.000000000000",
        "support_coverage": "0.000000000000",
        "mean_w": "0.000000000000",
        "per_gate_reject_counts": {},
        "band_energy_ratios": {},
        "capped_delta_pixel_fraction": "0.000000000000",
        "cap_enforcement": {"passed": True, "H1": dict(empty_cap), "H2": dict(empty_cap)},
        "input_pixel_hashes": input_hashes,
        "noise_energy": "0.000001000000",
        "fail_closed_reason": reason,
        "finalized_post_o5": False,
    }


def _detail_metrics(image_u8, source_u8):
    # Reuse the frozen attribution evaluator so the worker diagnostic is on the
    # exact same positional-band reduction as the pre-registered denominator.
    from tools.checkpoint_attribution import (  # noqa: PLC0415
        POSITIONAL_BANDS,
        _combine,
        _crop,
        _metrics_for,
        _resample_to,
    )

    image = image_u8.astype(np.float64) / 255.0
    source = source_u8.astype(np.float64) / 255.0
    reference = _resample_to(source, image.shape)
    metrics = [
        _metrics_for(_crop(image, box), _crop(reference, box))
        for box in POSITIONAL_BANDS.values()
    ]
    combined = _combine(metrics)
    return {"eatr": float(combined["eatr"]), "hftr_H1": float(combined["hftr_H1"])}


def _transition_loss(before, after):
    d_eatr = float(after["eatr"] - before["eatr"])
    d_h1 = float(after["hftr_H1"] - before["hftr_H1"])
    return {
        "dEATR": _fixed(d_eatr),
        "dHFTR_H1": _fixed(d_h1),
        "loss": _fixed(max(abs(min(d_eatr, 0.0)), abs(min(d_h1, 0.0)))),
    }


def _energy_ratio(numerator, denominator):
    num = float(np.mean(np.asarray(numerator, dtype=np.float64) ** 2, dtype=np.float64))
    den = float(np.mean(np.asarray(denominator, dtype=np.float64) ** 2, dtype=np.float64))
    return _fixed(num / max(den, 1e-12))


def _stats(values, mask):
    selected = np.asarray(values, dtype=np.float64)[np.asarray(mask, dtype=bool)]
    selected = selected[np.isfinite(selected)]
    if selected.size == 0:
        return _zero_stats()
    return {
        "min": _fixed(np.min(selected)),
        "mean": _fixed(np.mean(selected, dtype=np.float64)),
        "max": _fixed(np.max(selected)),
        "pixels": int(selected.size),
    }


def _zero_stats():
    return {
        "min": "0.000000000000",
        "mean": "0.000000000000",
        "max": "0.000000000000",
        "pixels": 0,
    }


def _fixed(value):
    return format(float(value), ".12f")
