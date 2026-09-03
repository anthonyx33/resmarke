#!/usr/bin/env python3
"""Build the FULL MATRIX phase-B detection ledger (44 real g1 grades, verbatim)
from the authoritative run ledger + flux-family values."""
import json, sys

FLUX = {
"A_IMG-1_lab-ctla1.jpg":0.173757,"A_IMG-2_lab-ctla1.jpg":0.09936,"A_IMG-3_lab-ctla1.jpg":0.005264,
"A_IMG-4_lab-ctla1.jpg":0.085708,"A_IMG-5_lab-ctla1.jpg":0.103089,"A_IMG-6_lab-ctla1.jpg":0.234163,
"A_IMG-7_lab-ctla1.jpg":0.151713,"A_IMG-8_lab-ctla1.jpg":0.512653,"A_IMG-9_lab-ctla1.jpg":0.002093,
"A_IMG-10_lab-ctla1.jpg":0.000339,"A_IMG-11_lab-ctla1.jpg":0.168566,
"1A_IMG-1_lab-ctla1.jpg":0.007131,"1A_IMG-2_lab-ctla1.jpg":0.07675,"1A_IMG-3_lab-ctla1.jpg":0.008338,
"1A_IMG-4_lab-ctla1.jpg":0.044714,"1A_IMG-5_lab-ctla1.jpg":0.327948,"1A_IMG-6_lab-ctla1.jpg":0.542565,
"1A_IMG-7_lab-ctla1.jpg":0.160421,"1A_IMG-8_lab-ctla1.jpg":0.662801,"1A_IMG-9_lab-ctla1.jpg":0.001187,
"1A_IMG-10_lab-ctla1.jpg":0.000456,"1A_IMG-11_lab-ctla1.jpg":0.072663,
"2B_IMG-1_lab-ctla1.jpg":0.115013,"2B_IMG-2_lab-ctla1.jpg":0.038912,"2B_IMG-3_lab-ctla1.jpg":0.006446,
"2B_IMG-4_lab-ctla1.jpg":0.061333,"2B_IMG-5_lab-ctla1.jpg":0.021684,"2B_IMG-6_lab-ctla1.jpg":0.800043,
"2B_IMG-7_lab-ctla1.jpg":0.319721,"2B_IMG-8_lab-ctla1.jpg":0.381874,"2B_IMG-9_lab-ctla1.jpg":0.003175,
"2B_IMG-10_lab-ctla1.jpg":0.000628,"2B_IMG-11_lab-ctla1.jpg":0.164094,
"3C_IMG-1_lab-ctla1.jpg":0.008135,"3C_IMG-2_lab-ctla1.jpg":0.039997,"3C_IMG-3_lab-ctla1.jpg":0.004134,
"3C_IMG-4_lab-ctla1.jpg":0.031601,"3C_IMG-5_lab-ctla1.jpg":0.717807,"3C_IMG-6_lab-ctla1.jpg":0.911588,
"3C_IMG-7_lab-ctla1.jpg":0.155313,"3C_IMG-8_lab-ctla1.jpg":0.303073,"3C_IMG-9_lab-ctla1.jpg":0.000698,
"3C_IMG-10_lab-ctla1.jpg":0.000492,"3C_IMG-11_lab-ctla1.jpg":0.070526,
}

cells = []
with open("ledger.jsonl") as f:
    for line in f:
        o = json.loads(line)
        if "cell" in o and "preset" in o:
            cells.append(o)

rows = []
for c in sorted(cells, key=lambda x: x["cell"]):
    fn = c["delivered_file"]
    rows.append({
        "event": "phase_b_grade",
        "preset": c["preset"],
        "image": c["image"],
        "group": "RM",
        "file_name": fn,
        "image_sha256": c["delivered_sha256"],
        "mode": "real",
        "vendor": c["vendor"],
        "mock": c["mock"],
        "ai_probability": c["rm_ai"],
        "deepfake_probability": c["rm_deepfake"],
        "verdict": c["rm_verdict"],
        "top_source": c["rm_top_source"],
        "flux_family": FLUX[fn],
        "provider_calls": c["rm_provider_calls"],
        "cache_hit": c.get("rm_cache_hit", True),
        "task_id": c["rm_task_id"],
        "model": "hive/ai-generated-and-deepfake-content-detection",
        "version": "1",
        "vendor_error": None,
        "c2pa": "absent (no algorithmic_tags.c2pa in response)",
        "timestamp_utc": c["timestamp_utc"],
    })

with open("phase-b-detection-ledger.json", "w") as f:
    json.dump({"schema_version": 1, "rows": rows, "count": len(rows)}, f, indent=1)

print(f"wrote {len(rows)} rows")
for r in rows:
    print(r["preset"], r["image"], r["ai_probability"], r["verdict"], r["top_source"], r["task_id"], "ch=" + str(r["cache_hit"]))
