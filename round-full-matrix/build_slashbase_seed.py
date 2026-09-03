#!/usr/bin/env python3
"""Build the SlashBase matrix seed JSONL and the detection-matrix analysis.

Inputs (already independently verified):
- round-full-matrix/phase-b-detection-ledger.json (44 real g1 RM rows)
- round-remint-1-01/full-corpus/phase-b-detection-ledger.json (11 OG + 11 RM rows)
- round-full-matrix/ledger.jsonl (44 cells with settings codes)
"""
import json
from pathlib import Path

HERE = Path("/Users/a/Documents/NOSYNF/round-full-matrix")
CORPUS = Path("/Users/a/Documents/NOSYNF/round-remint-1-01/full-corpus")

PRESET_CODES = {
    "Config A": "SEQ-CFA-lhbmeve33nn3",
    "Config 1A": "SEQ-1A-tpxokpv5c53f",
    "Config 2B": "SEQ-2B-vr6sikgjt3ap",
    "Config 3C": "SEQ-3C-nzzomjahxuyi",
    "ReMint 1.01": "SEQ-1.01-yg63qja3got4",
}
EXT = {1: "jpg", 2: "jpg", 3: "png", 4: "png", 5: "png", 6: "png",
       7: "png", 8: "png", 9: "png", 10: "png", 11: "jpeg"}

# OG real grades (verbatim from the 1.01 phase-b leg, task ids pinned)
OG = {
    "IMG-1":  dict(ai=0.99999,  task="e738f6de-a43f-11f1-b1eb-5ff77038449d", ts="2026-08-30T06:58:31.590Z", sha="442a1ccd4338d777b9a1bc7bfedb21aeb3846ae6f4f9f8ee761b9ef38d3b0dc8"),
    "IMG-2":  dict(ai=0.999825, task="5aef585d-a440-11f1-9a31-cab10ff00188", ts="2026-08-30T06:59:34.745Z", sha="90b8cc8a257454b39bb67d3f8065b01ec3e17b29a3f6e1ebb80e620f02d38e91"),
    "IMG-3":  dict(ai=0.999937, task="612e2ee7-a440-11f1-b0a0-5809c2b6ed59", ts="2026-08-30T06:59:45.065Z", sha="357d9aa522ea4d12ba3583f86477472b526168747c682cdc828ac073ce5af6a6"),
    "IMG-4":  dict(ai=0.999633, task="671a04cb-a440-11f1-b046-6245115acf08", ts="2026-08-30T06:59:54.527Z", sha="9f4cfa27845ffb49f595f90c332c43b4db2bbcde6ce30633b7dcea2396fe8e1a"),
    "IMG-5":  dict(ai=0.999978, task="6ccd33db-a440-11f1-879c-bb1c02e9a8d5", ts="2026-08-30T07:00:04.262Z", sha="91fffe56122550743c9c18da0bed78c89ca702cabb08ce125e626a89a67b0d6b"),
    "IMG-6":  dict(ai=0.994176, task="73e9ac5b-a440-11f1-83c7-ca026097af93", ts="2026-08-30T07:00:16.505Z", sha="57db03058e1ce49e15aff4a7b95f0d6d6e1e23660732aa1c54f991bec1ea567f"),
    "IMG-7":  dict(ai=0.999796, task="7a52d7cd-a440-11f1-9a19-c376cb9952c9", ts="2026-08-30T07:00:27.152Z", sha="dd6b9afc1cc79c2a6dcd6a4e5fb9592e9838614876754e72f9bccbcd21f7a69b"),
    "IMG-8":  dict(ai=0.999895, task="ac7af70a-a029-11f1-ada3-cbef6b77a714", ts="2026-08-30T07:00:33.274Z", sha="bb1325d84ba3dd2ac8162b5c9f3607932ae6d50a7b245c467024599ad4d2319c"),
    "IMG-9":  dict(ai=0.99997,  task="85ee6f81-a440-11f1-aa35-40a3394bb535", ts="2026-08-30T07:00:46.268Z", sha="70df003ece40710c00ae4173237322e88125baa4993aa8a79a69b2beccee9b70"),
    "IMG-10": dict(ai=0.999889, task="8bcd9b9d-a440-11f1-8109-e1fb6d8f3aa0", ts="2026-08-30T07:00:56.105Z", sha="96379ecb1b1b5fa97ec5ef3c3149765eb9a0d4162e038db1fe882e3f7aea8de3"),
    "IMG-11": dict(ai=0.99256,  task="b84b30e4-a440-11f1-ba35-afcc4a3662bc", ts="2026-08-30T07:02:10.753Z", sha="dc9bdc02806d2391a22f092f4539be875b06c0fdf049d67b4cc3ea843da0a8c8"),
}

matrix_pb = json.loads((HERE / "phase-b-detection-ledger.json").read_text())
matrix_rows = matrix_pb["rows"]
assert matrix_pb["count"] == 44 and len(matrix_rows) == 44

one01_pb = json.loads((CORPUS / "phase-b-detection-ledger.json").read_text())
one01_rows = one01_pb["rows"] if isinstance(one01_pb, dict) else one01_pb

rm101 = {}
for r in one01_rows:
    fn = r.get("file_name", "")
    if fn.startswith("1.01_"):
        g = r.get("grade") or {}
        raw = g.get("raw") or {}
        image = fn.split("_")[1]  # IMG-N
        srcs = g.get("sources") or {}
        flux_keys = [v for k, v in srcs.items() if "flux" in k.lower()]
        rm101[image] = {
            "ai": g.get("ai_probability"),
            "df": g.get("deepfake_probability"),
            "verdict": g.get("verdict"),
            "top": g.get("top_source"),
            "flux": max(flux_keys) if flux_keys else 0.0,
            "task": raw.get("task_id"),
            "ts": r.get("timestamp"),
            "sha": g.get("image_sha256") or r.get("image_sha256"),
        }
assert len(rm101) == 11, len(rm101)

# ---------- seed JSONL for the 4 matrix presets ----------
seed = []
for pb in matrix_rows:
    preset = pb["preset"]
    image = pb["image"]
    seed.append({
        "event": "cell_complete",
        "preset": preset,
        "image": image,
        "settings_code": PRESET_CODES[preset],
    })
for preset in ("Config A", "Config 1A", "Config 2B", "Config 3C"):
    for n in range(1, 12):
        image = f"IMG-{n}"
        og = OG[image]
        seed.append({
            "event": "phase_b_grade",
            "preset": preset,
            "image": image,
            "group": "OG",
            "file_name": f"{image}_source.{EXT[n]}",
            "image_sha256": og["sha"],
            "mock": False,
            "mode": "real",
            "vendor": "g1",
            "ai_probability": og["ai"],
            "deepfake_probability": 0,
            "task_id": og["task"],
            "timestamp": og["ts"],
            "verdict": "FAIL",
        })
for pb in matrix_rows:
    seed.append({
        "event": "phase_b_grade",
        "preset": pb["preset"],
        "image": pb["image"],
        "group": "RM",
        "file_name": pb["file_name"],
        "image_sha256": pb["image_sha256"],
        "mock": False,
        "mode": "real",
        "vendor": "g1",
        "ai_probability": pb["ai_probability"],
        "deepfake_probability": pb["deepfake_probability"],
        "task_id": pb["task_id"],
        "timestamp": pb["timestamp_utc"],
        "verdict": pb["verdict"],
    })

with (HERE / "slashbase-matrix-seed.jsonl").open("w") as fh:
    for row in seed:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
print("matrix seed rows:", len(seed), "(44 cell_complete + 44 OG + 44 RM)")

# ---------- detection analysis ----------
def flux_of(pb):
    return pb.get("flux_family", 0)

table = {}
for pb in matrix_rows:
    key = (pb["preset"], pb["image"])
    table[key] = {
        "rm_ai": pb["ai_probability"],
        "verdict": pb["verdict"],
        "top_source": pb["top_source"],
        "flux_family": flux_of(pb),
        "og_ai": OG[pb["image"]]["ai"],
    }
for n in range(1, 12):
    image = f"IMG-{n}"
    r = rm101[image]
    table[("ReMint 1.01", image)] = {
        "rm_ai": r["ai"],
        "verdict": r["verdict"],
        "top_source": r["top"],
        "flux_family": r["flux"],
        "og_ai": OG[image]["ai"],
    }

presets = ["Config A", "Config 1A", "Config 2B", "Config 3C", "ReMint 1.01"]
analysis = {"per_preset": {}, "per_image_best": {}}
for preset in presets:
    rows = [table[(preset, f"IMG-{n}")] for n in range(1, 12)]
    analysis["per_preset"][preset] = {
        "images": {f"IMG-{n}": table[(preset, f"IMG-{n}")] for n in range(1, 12)},
        "threshold_pass_count": sum(
            1 for r in rows if r["rm_ai"] <= 0.45 and r["flux_family"] <= 0.30),
        "threshold_pass_images": sorted(
            f"IMG-{n}" for n in range(1, 12)
            if table[(preset, f"IMG-{n}")]["rm_ai"] <= 0.45
            and table[(preset, f"IMG-{n}")]["flux_family"] <= 0.30),
        "clear_count": sum(1 for r in rows if r["verdict"] == "CLEAR"),
        "border_count": sum(1 for r in rows if r["verdict"] == "BORDER"),
        "non_amplification_count": sum(1 for r in rows if r["rm_ai"] <= r["og_ai"]),
        "median_ai": sorted(r["rm_ai"] for r in rows)[5],
    }
for n in range(1, 12):
    image = f"IMG-{n}"
    per = {p: table[(p, image)]["rm_ai"] for p in presets}
    analysis["per_image_best"][image] = {
        "best_preset": min(per, key=per.get),
        "best_ai": min(per.values()),
        "all": per,
    }

(HERE / "matrix-detection-analysis.json").write_text(
    json.dumps(analysis, indent=2, sort_keys=True) + "\n")
print("analysis per-preset:")
for p in presets:
    s = analysis["per_preset"][p]
    print(f"  {p:12s} pass {s['threshold_pass_count']}/11  CLEAR {s['clear_count']}  "
          f"BORDER {s['border_count']}  non-amp {s['non_amplification_count']}/11  medAI {s['median_ai']:.4f}")
print("best per image:", analysis["per_image_best"])
