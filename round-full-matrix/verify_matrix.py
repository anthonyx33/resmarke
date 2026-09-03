#!/usr/bin/env python
"""Master engineer independent verification of the full-matrix run."""
import json, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/Users/a/Documents/NOSYNF/round-remint-1-01/full-corpus"

REQUIRED = {
    "Config A": "SEQ-CFA-lhbmeve33nn3",
    "Config 1A": "SEQ-1A-tpxokpv5c53f",
    "Config 2B": "SEQ-2B-vr6sikgjt3ap",
    "Config 3C": "SEQ-3C-nzzomjahxuyi",
}

fail = []
def check(cond, msg):
    status = "PASS" if cond else "FAIL"
    if not cond:
        fail.append(msg)
    print(f"[{status}] {msg}")

lines = open(os.path.join(HERE, "ledger.jsonl")).read().strip().split("\n")
check(len(lines) == 56, f"ledger.jsonl has 56 lines (got {len(lines)})")

def _ok(ln):
    try:
        json.loads(ln); return True
    except Exception:
        return False
bad = [i for i, ln in enumerate(lines) if not _ok(ln)]
check(len(bad) == 0, f"all ledger lines parse as JSON (bad: {bad})")

cells = [json.loads(l) for l in lines if '"cell"' in l]
check(len(cells) == 44, f"44 cell rows (got {len(cells)})")

# code exactness per preset
by_preset = {}
for c in cells:
    by_preset.setdefault(c["preset"], []).append(c)
check(set(by_preset) == set(REQUIRED), f"presets exactly {sorted(REQUIRED)} (got {sorted(by_preset)})")
code_exact = sum(1 for c in cells if c["settings_code"] == REQUIRED[c["preset"]])
check(code_exact == 44, f"settings_code exact 44/44 (got {code_exact})")

# vendor/mock/cache fields
check(all(c["vendor"] == "g1" for c in cells), "all cells vendor g1")
check(all(c["mock"] is False for c in cells), "all cells mock false")
check(all(c["og_cache_hit"] is True for c in cells), "all cells og_cache_hit true (OG reuse)")
check(all(c["rm_provider_calls"] == 1 for c in cells), "all cells rm_provider_calls 1 (fresh real call)")
check(all(c["rm_deepfake"] == 0 for c in cells), "all cells rm_deepfake 0")

# per-preset: exactly IMG-1..11
for preset, cs in by_preset.items():
    imgs = [c["image"] for c in cs]
    check(imgs == [f"IMG-{i}" for i in range(1, 12)],
          f"{preset}: images IMG-1..11 in order (got {imgs})")
    check(len(cs) == 11, f"{preset}: 11 cells")

# source hashes vs canonical source files
ext = {1:"jpg",2:"jpg",3:"png",4:"png",5:"png",6:"png",7:"png",8:"png",9:"png",10:"png",11:"jpeg"}
src_mismatch = 0
for c in cells:
    n = int(c["image"].split("-")[1])
    p = os.path.join(SRC, f"{c['image']}_source.{ext[n]}")
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if h != c["source_sha256"]:
        src_mismatch += 1
        print("  source mismatch", c["image"], c["preset"])
check(src_mismatch == 0, f"source_sha256 matches canonical source files 44/44 (mismatch {src_mismatch})")

# delivered file hashes vs ledger pins
deliv_mismatch = 0
for c in cells:
    p = os.path.join(HERE, c["delivered_file"])
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if h != c["delivered_sha256"]:
        deliv_mismatch += 1
        print("  delivered mismatch", c["delivered_file"])
check(deliv_mismatch == 0, f"delivered files byte-match ledger pins 44/44 (mismatch {deliv_mismatch})")

# credits
total = sum(c["credits_consumed"] for c in cells)
check(total == 1012, f"credits total 1012 (got {total})")
check(all(c["credits_consumed"] == 23 for c in cells), "each cell 23 credits")

# job ids unique
jobs = [c["job_id"] for c in cells]
check(len(set(jobs)) == 44, f"44 unique job ids (got {len(set(jobs))})")

# phase-b detection ledger
pb = json.load(open(os.path.join(HERE, "phase-b-detection-ledger.json")))
rows = pb["rows"]
check(pb["count"] == 44, f"phase-b count 44 (got {pb['count']})")
check(len(rows) == 44, f"phase-b rows 44 (got {len(rows)})")
names = sorted(r["file_name"] for r in rows)
expect = sorted(c["delivered_file"] for c in cells)
check(names == expect, "phase-b file names == delivered file set")
check(all("task_id" in r and "flux_family" in r for r in rows), "phase-b rows carry task_id + flux_family")
check(all(r.get("mock") is False and r.get("vendor") == "g1" for r in rows), "phase-b rows real g1, no mock")
check(all(r["mode"] == "real" for r in rows), "phase-b rows mode real")
check(all(r["cache_hit"] is True for r in rows), "phase-b rows cache_hit true (0 fresh phase-b calls)")

# phase-b ai must equal phase-a rm_ai (same bytes, cache-hit grade)
cell_by_file = {c["delivered_file"]: c for c in cells}
consistent = 0
sha_consistent = 0
for r in rows:
    c = cell_by_file[r["file_name"]]
    if abs(r["ai_probability"] - c["rm_ai"]) < 1e-9:
        consistent += 1
    else:
        print("  ai mismatch", r["file_name"], r["ai_probability"], c["rm_ai"])
    if r["image_sha256"] == c["delivered_sha256"]:
        sha_consistent += 1
    else:
        print("  sha mismatch", r["file_name"])
check(consistent == 44, f"phase-b ai == phase-a rm_ai 44/44 (got {consistent})")
check(sha_consistent == 44, f"phase-b image_sha256 == delivered pins 44/44 (got {sha_consistent})")

print()
print("FAILURES:", len(fail))
if fail:
    for f in fail:
        print(" -", f)
    sys.exit(1)
print("INDEPENDENT VERIFICATION: ALL GREEN")
