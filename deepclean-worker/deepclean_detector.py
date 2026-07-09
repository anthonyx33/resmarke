"""Pluggable AI-image detector for CX Remint's adaptive gate.

CX Remint's adaptive mode escalates strength until a REAL detector clears the
image. This is the seam to that detector. It is deliberately env-gated: with no
configuration `make_detector()` returns None and adaptive mode degrades to a
single template run (see max_cx_remint.apply_cx_remint) -- we never blind-escalate.

Why a normalization proxy is recommended
---------------------------------------
Hive and TruthScan return different, nested JSON and evolve their schemas. Rather
than hard-code a fragile path, point CX_DETECTOR_URL at a tiny endpoint you own
that runs the image through your detector(s) of record and returns the normalized
shape below. That keeps the arms-race churn in one small place you control:

    POST {CX_DETECTOR_URL}   (multipart file field "image", or JSON {"url": ...})
    ->  { "ai_probability": 0.0-1.0 (or 0-100),
          "watermark_present": true|false,     # SynthID/C2PA decoder hit
          "sources": { "gemini3": 0.0, ... } } # optional, for the ledger

A best-effort Hive parser is included for direct use, but the proxy is the
supported path.

Env:
  CX_DETECTOR_URL       endpoint (required to enable adaptive gating)
  CX_DETECTOR_KEY       bearer token / api key (optional)
  CX_DETECTOR_PROVIDER  "normalized" (default) | "hive"
  CX_DETECTOR_TIMEOUT   seconds (default 45)
"""

import os

import requests


def make_detector():
    """Return a callable(path)->dict, or None if not configured."""
    url = os.environ.get("CX_DETECTOR_URL")
    if not url:
        return None
    key = os.environ.get("CX_DETECTOR_KEY")
    provider = os.environ.get("CX_DETECTOR_PROVIDER", "normalized").lower()
    timeout = float(os.environ.get("CX_DETECTOR_TIMEOUT", "45"))

    def detect(path):
        headers = {}
        if key:
            headers["authorization"] = f"Bearer {key}"
        with open(path, "rb") as handle:
            response = requests.post(
                url, headers=headers, files={"image": handle}, timeout=timeout
            )
        response.raise_for_status()
        payload = response.json()
        parsed = parse_hive(payload) if provider == "hive" else parse_normalized(payload)
        parsed["ok"] = True
        return parsed

    return detect


def parse_normalized(payload):
    """Parse the recommended normalized shape."""
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "non_dict_payload"}
    return {
        "ai_probability": payload.get("ai_probability"),
        "watermark_present": bool(payload.get("watermark_present", False)),
        "sources": payload.get("sources") if isinstance(payload.get("sources"), dict) else None,
    }


def parse_hive(payload):
    """Best-effort extraction from a Hive AI-generated-content response.

    Hive nests class scores under status[].response.output[].classes[] with
    {class, score}. We pull the aggregate 'ai_generated'/'not_ai_generated'
    pair and the top model source. Schemas drift -- prefer a normalization proxy.
    """
    try:
        ai_prob = None
        sources = {}
        statuses = payload.get("status") or payload.get("data") or []
        if isinstance(statuses, dict):
            statuses = [statuses]
        for status in statuses:
            outputs = (((status or {}).get("response") or {}).get("output")) or []
            for out in outputs:
                for cls in out.get("classes", []) or []:
                    name, score = cls.get("class"), cls.get("score")
                    if name is None or score is None:
                        continue
                    if name in ("ai_generated", "ai", "artificial"):
                        ai_prob = float(score)
                    elif name in ("not_ai_generated", "real", "natural"):
                        if ai_prob is None:
                            ai_prob = 1.0 - float(score)
                    else:
                        sources[name] = float(score)
        return {
            "ai_probability": ai_prob,
            "watermark_present": None,  # Hive AI-gen endpoint does not decode SynthID
            "sources": sources or None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"hive_parse_error: {str(exc)[:200]}"}
