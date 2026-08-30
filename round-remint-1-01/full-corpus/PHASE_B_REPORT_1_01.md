# FLASH OPERATOR — ReMint 1.01 FULL-CORPUS PHASE B REPORT (REAL HIVE)

Runbook: `FLASH_OPERATOR_PROMPT_REMINT_1_01_FULL_CORPUS.md` (Phase B, Section 3)
+ `HIVE_ENABLEMENT_RUNBOOK.md`. Executed 2026-08-30. **Phase B COMPLETE — 22/22
grades recorded verbatim, all real Hive (g1).**

## 1. Pre-flight (before any leg call)

| Check | Result |
|---|---|
| `GRADE_PROVIDER` | ✅ **`g1`** (secret hash `711430f6…` = sha256("g1"), updated 2026-08-30T06:50) |
| `GRADE_DEFAULT_MODE` | ✅ `real` |
| `HIVE_SECRET_KEY` / `HIVE_ACCESS_KEY_ID` | ✅ present (server-only) |
| C2PA deny-list | ✅ all 22 files structurally clean (no APP11/JUMBF; no PNG C2PA chunks); the one raw `jumb` byte hit was inside compressed data = false positive |
| Files hash-pinned | ✅ all 22 (sources + delivered), SHA-256s match the ledger |
| Allocation on record | ✅ 22 authorized; S1's 24 deferred; 18 margin written |
| Credits | balance 991264, **0 remint credits spent** (detection-only only) |

## 2. Verification call (Step 3 — the only call outside the leg)

`IMG-1_source.jpg` via "Run API detection only":
- `vendor: g1`, `mock: false`, `provider_calls: 1`, `cache_hit: false`
- ai 0.99999 (100%), deepfake 0, verdict FAIL, top source `imagen4`
- Hive task `e738f6de-a43f-11f1-b1eb-5ff77038449d` (model
  `hive/ai-generated-and-deepfake-content-detection` v1)
- **Result: PASS — real provider confirmed.** Proceeded to Phase B.

## 3. Phase B — 22 paired real Hive grades (verbatim)

Submitted in ledger order (per image: OG first, then its 1.01 delivered). Every
response recorded verbatim with ai, deepfake, top source, full source vector,
flux-family, task id, model/version, vendor_error. No retries, no re-ordering,
no dropped files. No vendor errors, no evaluator failures, no C2PA in any
response.

| Image | Group | AI% (real) | Deepfake | Verdict | Top source | Flux-family | Provider calls | Task id |
|---|---|---:|---:|---|---|---:|---:|---|
| IMG-1 | OG | 99.999 | 0.0 | FAIL | imagen4 | 0.007341 | 1* | `e738f6de…` |
| IMG-1 | RM | 98.733 | 0.0 | FAIL | bria | 0.203070 | 1 | `aeef2580…` |
| IMG-2 | OG | 99.983 | 0.0 | FAIL | gemini3 | 0.000960 | 1 | `5aef585d…` |
| IMG-2 | RM | 82.086 | 0.0 | FAIL | stablediffusion | 0.109182 | 1 | `5e96e12c…` |
| IMG-3 | OG | 99.994 | 0.0 | FAIL | gemini | 0.005949 | 1 | `612e2ee7…` |
| IMG-3 | RM | 99.897 | 0.0 | FAIL | stablediffusion | 0.005276 | 1 | `63d420bc…` |
| IMG-4 | OG | 99.963 | 0.0 | FAIL | gemini | 0.020784 | 1 | `671a04cb…` |
| IMG-4 | RM | 95.816 | 0.0 | FAIL | kling | 0.100455 | 1 | `6940d054…` |
| IMG-5 | OG | 99.998 | 0.0 | FAIL | ernie | 0.000054 | 1 | `6ccd33db…` |
| IMG-5 | RM | 95.992 | 0.0 | FAIL | wan | 0.180810 | 1 | `70c95753…` |
| IMG-6 | OG | 99.418 | 0.0 | FAIL | flux | 0.644038 | 1 | `73e9ac5b…` |
| IMG-6 | RM | 16.407 | 0.0 | BORDER | flux | 0.236838 | 1 | `77727d12…` |
| IMG-7 | OG | 99.980 | 0.0 | FAIL | gemini3 | 0.000080 | 1 | `7a52d7cd…` |
| IMG-7 | RM | 9.633 | 0.0 | CLEAR | flux | 0.151955 | 1 | `7d343690…` |
| IMG-8 | OG | 99.989 | 0.0 | FAIL | gemini3 | 0.000029 | 0** | `ac7af70a…` |
| IMG-8 | RM | 46.333 | 0.0 | FAIL | flux | 0.521686 | 1 | `813f0485…` |
| IMG-9 | OG | 99.997 | 0.0 | FAIL | gemini3 | 0.000029 | 1 | `85ee6f81…` |
| IMG-9 | RM | 22.008 | 0.0 | BORDER | gemini3 | 0.004177 | 1 | `89091859…` |
| IMG-10 | OG | 99.989 | 0.0 | FAIL | gemini3 | 0.000010 | 1 | `8bcd9b9d…` |
| IMG-10 | RM | 1.501 | 0.0 | CLEAR | adobefirefly | 0.000867 | 1 | `8e78c769…` |
| IMG-11 | OG | 99.256 | 0.0 | FAIL | ernie | 0.010494 | 1 | `b84b30e4…` |
| IMG-11 | RM | 94.622 | 0.0 | FAIL | wan | 0.280562 | 1 | `be6ee5a7…` |

\* IMG-1 OG: the leg submission returned a **cache hit** (0 calls) — the real
grade was obtained by the Step-3 verification call on the identical bytes
(same task id). Recorded verbatim.
\*\* IMG-8 OG: **cache hit** (0 calls) — a pre-existing g1/real grade_cache
entry from an earlier session (task `ac7af70a-a029-11f1-…`), real Hive, not
created in this session. Recorded verbatim.

Full verbatim responses (full source vectors, raw Hive output): 
`phase-b-detection-ledger.json` (23 rows incl. verification).

## 4. Session accounting

- **21 / 40 vendor calls** used this session (UI-verified), **2 cache hits**, **23 grades returned**.
- Breakdown: 1 verification call (IMG-1 OG, outside the leg) + **20 fresh leg calls** + **2 leg cache hits** = 22 leg submissions, all graded.
- Written allocation 22; actual 21 calls consumed → margin **19** (not 18) because 2 leg submissions were served from cache (both real grades).
- Credits: 991264 (unchanged) — detection-only path, 0 remint credits.

## 5. What I did NOT do

- ❌ No retries, no re-ordering, no dropped files.
- ❌ No calls beyond the written allocation (21 ≤ 22; 40-cap untouched with 19 margin).
- ❌ No C2PA present on any graded file (deny-list not triggered).
- ❌ No engineering decisions; no cache/DB modifications; no thresholds/secrets changed.
- ❌ The OG-vs-1.01 comparison is NOT computed here — that is the master engineer's job.

## 6. Declaration (Section 6)

"I ran exactly the steps in this runbook, in order, with the real Hive provider
(`GRADE_PROVIDER=g1`) verified by one call, then submitted all 22 hash-pinned
files in ledger order (OG first, then 1.01 per image) and recorded every
response verbatim with no retries, no re-ordering, no dropped files, no calls
beyond the written allocation, and made no engineering decisions. Ledger and
files are complete and unmodified."

Signed: Flash operator
Date / time: 2026-08-30
