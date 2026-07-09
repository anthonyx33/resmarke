"""Coherent iPhone EXIF synthesis for CX Remint.

Why this exists
---------------
Creators shoot on recent iPhones, do a small AI touch-up, and the generative
tool strips the original camera metadata and/or stamps its own provenance. The
image then reads as "AI-generated / no camera" to detectors. CX Remint rebuilds
the image as a real capture; this module rebuilds the *metadata* half of that
claim: a self-consistent iPhone EXIF block written onto the final JPEG.

Design rules (what makes this "real", not a garbage tag):
  1. Internal coherence. FNumber, FocalLength, LensModel and FocalLengthIn35mm
     all describe the SAME physical lens. ApertureValue / ShutterSpeedValue /
     BrightnessValue are computed from FNumber / ExposureTime / ISO with the
     APEX relations a real camera obeys (Av + Tv = Bv + Sv), not random numbers.
  2. Device coherence. Model, Software (iOS), LensModel and HostComputer all
     belong to one device generation.
  3. Fresh by construction. We build a brand-new EXIF block and write it onto a
     freshly-encoded JPEG, so any inherited C2PA / XMP / SynthID-metadata /
     source-EXIF is gone -- stripping is a side effect of rebuilding.

What we deliberately DO NOT forge:
  - Apple MakerNote. Apple's MakerNote is proprietary and binary; a malformed
    one is a *stronger* tell than its absence (plenty of edited/exported iPhone
    JPEGs carry no MakerNote). We omit it rather than fake it badly.
  - GPS. Omitted on privacy grounds (and "location off" is extremely common).

This is a fabricated-provenance feature and is gated behind an explicit user
toggle in the product. See the profile's `iphone_exif` setting.
"""

import datetime
import hashlib
import math

import numpy as np
import piexif


# One entry per selectable device. focal_mm is the real (physical) focal length
# the phone records; focal35 is its 35mm-equivalent; fnumber is the fixed main
# ("Fusion"/wide) camera aperture. lens/model/software are kept consistent with
# the device generation. Values match what these phones write for a main-camera
# still.
IPHONE_DEVICES = {
    "iphone-16-pro-max": {
        "model": "iPhone 16 Pro Max",
        "software": "18.5",
        "lens": "iPhone 16 Pro Max back triple camera 6.765mm f/1.78",
        "focal_mm": 6.765, "focal35": 24, "fnumber": 1.78,
    },
    "iphone-16-pro": {
        "model": "iPhone 16 Pro",
        "software": "18.5",
        "lens": "iPhone 16 Pro back triple camera 6.765mm f/1.78",
        "focal_mm": 6.765, "focal35": 24, "fnumber": 1.78,
    },
    "iphone-16": {
        "model": "iPhone 16",
        "software": "18.4.1",
        "lens": "iPhone 16 back dual camera 5.96mm f/1.6",
        "focal_mm": 5.96, "focal35": 26, "fnumber": 1.6,
    },
    "iphone-15-pro-max": {
        "model": "iPhone 15 Pro Max",
        "software": "17.5.1",
        "lens": "iPhone 15 Pro Max back triple camera 6.765mm f/1.78",
        "focal_mm": 6.765, "focal35": 24, "fnumber": 1.78,
    },
    "iphone-15-pro": {
        "model": "iPhone 15 Pro",
        "software": "17.5.1",
        "lens": "iPhone 15 Pro back triple camera 6.765mm f/1.78",
        "focal_mm": 6.765, "focal35": 24, "fnumber": 1.78,
    },
    "iphone-15": {
        "model": "iPhone 15",
        "software": "17.4.1",
        "lens": "iPhone 15 back dual camera 5.96mm f/1.6",
        "focal_mm": 5.96, "focal35": 26, "fnumber": 1.6,
    },
    "iphone-14-pro": {
        "model": "iPhone 14 Pro",
        "software": "16.7.2",
        "lens": "iPhone 14 Pro back triple camera 6.86mm f/1.78",
        "focal_mm": 6.86, "focal35": 24, "fnumber": 1.78,
    },
}

# Weighted pool for device="auto". Skews toward the phones a professional
# creator is most likely to be shooting on right now.
_AUTO_POOL = (
    ["iphone-16-pro"] * 5
    + ["iphone-16-pro-max"] * 4
    + ["iphone-15-pro"] * 3
    + ["iphone-15-pro-max"] * 3
    + ["iphone-16"] * 2
    + ["iphone-15"] * 1
    + ["iphone-14-pro"] * 1
)

# Common iPhone still exposures (denominator of a 1/x second shutter) and ISO
# rungs. A real auto-exposure pairs a fast-ish shutter with low ISO in good
# light; we sample a coherent (shutter, iso) pair rather than each independently.
_EXPOSURE_LADDER = (
    # (shutter_denominator, iso)
    (60, 100), (100, 80), (120, 64), (120, 100), (240, 64),
    (250, 50), (500, 50), (60, 125), (100, 125), (30, 200),
)

DEVICE_KEYS = tuple(IPHONE_DEVICES.keys())


def resolve_device(device, rng):
    """Map a requested device (or 'auto') to a concrete device key."""
    if device in IPHONE_DEVICES:
        return device
    return _AUTO_POOL[int(rng.integers(0, len(_AUTO_POOL)))]


def seed_from(creator_id, seed_extra, size):
    material = f"iphone-exif-v1:{creator_id}:{seed_extra}:{size[0]}x{size[1]}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def build_iphone_exif(width, height, creator_id, seed_extra="", device="auto", when=None):
    """Return (exif_bytes, report) for a coherent iPhone still.

    exif_bytes is a piexif dump ready to pass to PIL as save(exif=...).
    report is a JSON-safe dict of the human-readable choices for the ledger.
    """
    rng = np.random.default_rng(seed_from(creator_id, seed_extra, (width, height)))
    key = resolve_device(device, rng)
    dev = IPHONE_DEVICES[key]

    shutter_den, iso = _EXPOSURE_LADDER[int(rng.integers(0, len(_EXPOSURE_LADDER)))]
    exposure_time = 1.0 / shutter_den
    fnumber = dev["fnumber"]

    # APEX values -- computed, not invented, so the block is self-consistent.
    aperture_apex = 2.0 * math.log2(fnumber)                 # Av
    shutter_apex = math.log2(shutter_den)                    # Tv (= -log2(t))
    sensitivity_apex = math.log2(iso / 3.125)                # Sv
    brightness_apex = aperture_apex + shutter_apex - sensitivity_apex  # Bv

    when = when or _plausible_recent_datetime(rng)
    dt_str = when.strftime("%Y:%m:%d %H:%M:%S")
    subsec = f"{int(rng.integers(0, 1000)):03d}"
    offset = _plausible_offset(rng)

    focal_r = _ratio(dev["focal_mm"], 1000)
    fnum_r = _ratio(fnumber, 100)

    zeroth = {
        piexif.ImageIFD.Make: b"Apple",
        piexif.ImageIFD.Model: dev["model"].encode(),
        piexif.ImageIFD.Software: dev["software"].encode(),
        piexif.ImageIFD.HostComputer: dev["model"].encode(),
        piexif.ImageIFD.DateTime: dt_str.encode(),
        piexif.ImageIFD.Orientation: 1,
        piexif.ImageIFD.XResolution: (72, 1),
        piexif.ImageIFD.YResolution: (72, 1),
        piexif.ImageIFD.ResolutionUnit: 2,
        piexif.ImageIFD.YCbCrPositioning: 1,
    }

    exif = {
        piexif.ExifIFD.ExposureTime: (1, shutter_den),
        piexif.ExifIFD.FNumber: fnum_r,
        piexif.ExifIFD.ExposureProgram: 2,           # normal program
        piexif.ExifIFD.ISOSpeedRatings: iso,
        piexif.ExifIFD.ExifVersion: b"0232",
        piexif.ExifIFD.DateTimeOriginal: dt_str.encode(),
        piexif.ExifIFD.DateTimeDigitized: dt_str.encode(),
        piexif.ExifIFD.OffsetTime: offset.encode(),
        piexif.ExifIFD.OffsetTimeOriginal: offset.encode(),
        piexif.ExifIFD.OffsetTimeDigitized: offset.encode(),
        piexif.ExifIFD.SubSecTimeOriginal: subsec.encode(),
        piexif.ExifIFD.SubSecTimeDigitized: subsec.encode(),
        piexif.ExifIFD.ComponentsConfiguration: b"\x01\x02\x03\x00",
        piexif.ExifIFD.ShutterSpeedValue: _sratio(shutter_apex, 100),
        piexif.ExifIFD.ApertureValue: _ratio(aperture_apex, 100),
        piexif.ExifIFD.MaxApertureValue: _ratio(aperture_apex, 100),
        piexif.ExifIFD.BrightnessValue: _sratio(brightness_apex, 100),
        piexif.ExifIFD.ExposureBiasValue: (0, 1),
        piexif.ExifIFD.MeteringMode: 5,              # pattern
        piexif.ExifIFD.Flash: 16,                    # off, did not fire
        piexif.ExifIFD.FocalLength: focal_r,
        piexif.ExifIFD.FlashpixVersion: b"0100",
        piexif.ExifIFD.ColorSpace: 1,                # sRGB
        piexif.ExifIFD.PixelXDimension: int(width),
        piexif.ExifIFD.PixelYDimension: int(height),
        piexif.ExifIFD.SensingMethod: 2,             # one-chip color area
        piexif.ExifIFD.SceneType: b"\x01",           # directly photographed
        piexif.ExifIFD.ExposureMode: 0,              # auto
        piexif.ExifIFD.WhiteBalance: 0,              # auto
        piexif.ExifIFD.FocalLengthIn35mmFilm: int(dev["focal35"]),
        piexif.ExifIFD.SceneCaptureType: 0,          # standard
        piexif.ExifIFD.LensSpecification: [focal_r, focal_r, fnum_r, fnum_r],
        piexif.ExifIFD.LensMake: b"Apple",
        piexif.ExifIFD.LensModel: dev["lens"].encode(),
    }

    exif_bytes = piexif.dump({"0th": zeroth, "Exif": exif, "1st": {}, "GPS": {}, "Interop": {}})
    report = {
        "enabled": True,
        "device": key,
        "model": dev["model"],
        "software": dev["software"],
        "lens": dev["lens"],
        "fnumber": fnumber,
        "exposure_time": f"1/{shutter_den}",
        "iso": iso,
        "focal_length_mm": dev["focal_mm"],
        "focal_length_35mm": dev["focal35"],
        "datetime_original": dt_str,
        "offset_time": offset,
        "apex": {
            "aperture": round(aperture_apex, 3),
            "shutter": round(shutter_apex, 3),
            "brightness": round(brightness_apex, 3),
            "sensitivity": round(sensitivity_apex, 3),
        },
        "makernote": "omitted_by_design",
        "gps": "omitted_by_design",
    }
    return exif_bytes, report


def _plausible_recent_datetime(rng):
    """A capture time in the recent past (organic, not a round timestamp)."""
    now = datetime.datetime.now()
    days_ago = int(rng.integers(1, 22))
    seconds = int(rng.integers(0, 24 * 3600))
    # Bias toward daylight hours so the exposure/ISO pairing stays believable.
    base = now - datetime.timedelta(days=days_ago)
    day_start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    daylight = day_start + datetime.timedelta(seconds=int(9 * 3600 + rng.integers(0, 9 * 3600)))
    _ = seconds
    return daylight


def _plausible_offset(rng):
    offsets = ["+10:00", "+11:00", "+00:00", "-07:00", "-08:00", "-05:00", "+01:00", "+09:00"]
    return offsets[int(rng.integers(0, len(offsets)))]


def _ratio(value, denominator):
    return (int(round(value * denominator)), int(denominator))


def _sratio(value, denominator):
    # Signed rational: piexif encodes the sign from a negative numerator.
    return (int(round(value * denominator)), int(denominator))


def write_exif_jpeg(image, output_path, exif_bytes, quality, subsampling):
    """Encode a PIL image to JPEG with the given EXIF block embedded.

    Re-encoding from the pixel buffer drops any inherited C2PA/XMP/source
    metadata; only exif_bytes remains.
    """
    from PIL import Image  # local import keeps module import cheap

    if image.mode != "RGB":
        image = image.convert("RGB")
    save_kwargs = {"format": "JPEG", "quality": int(quality), "optimize": True, "exif": exif_bytes}
    if subsampling is not None:
        save_kwargs["subsampling"] = subsampling
    image.save(output_path, **save_kwargs)


def read_back(path):
    """Small helper for tests/harness: return a flat dict of key EXIF fields."""
    data = piexif.load(path)
    zeroth, exif = data.get("0th", {}), data.get("Exif", {})
    def _s(ifd, tag):
        val = ifd.get(tag)
        return val.decode("latin-1", "ignore") if isinstance(val, bytes) else val
    return {
        "Make": _s(zeroth, piexif.ImageIFD.Make),
        "Model": _s(zeroth, piexif.ImageIFD.Model),
        "Software": _s(zeroth, piexif.ImageIFD.Software),
        "DateTime": _s(zeroth, piexif.ImageIFD.DateTime),
        "LensModel": _s(exif, piexif.ExifIFD.LensModel),
        "FNumber": exif.get(piexif.ExifIFD.FNumber),
        "ExposureTime": exif.get(piexif.ExifIFD.ExposureTime),
        "ISO": exif.get(piexif.ExifIFD.ISOSpeedRatings),
        "FocalLength": exif.get(piexif.ExifIFD.FocalLength),
        "FocalLengthIn35mmFilm": exif.get(piexif.ExifIFD.FocalLengthIn35mmFilm),
    }
