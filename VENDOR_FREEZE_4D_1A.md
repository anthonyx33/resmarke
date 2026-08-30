# VENDOR FREEZE — 4D-1a (RECORD v3)

Date: 2026-08-27 · Status: **ACCEPTED BY OWNER — "freeze accepted" recorded 2026-08-27. Screening unblocked.**
v3 incorporates the expert verdict's seven amendments, the security correction,
and C88's final-pass amendments (fresh-call provenance contract, C2PA exactness,
evaluator mechanics). C88's disposition: **ACCEPT FREEZE** after these items.

## 1. Decision basis

Authenticated vendor access exists for exactly ONE vendor: **Hive g1**
(model `hive/ai-generated-and-deepfake-content-detection`, version `1`).
No TruthScan or Sightengine access exists. The pre-registered fallback from the
4D-CAM-1 brief §5.3 applies: single-vendor A/B, never two-vendor validation.

## 2. Frozen vendor-leg configuration (amended)

| item | frozen value |
|---|---|
| Leg type | **SINGLE-VENDOR A/B** (label used everywhere, always) |
| Vendor | Hive g1 only |
| **Seed** | **`lab-ctla1`** (as in the original fallback text) |
| Sentinels | IMG-5, 6, 7, 8, 9, 11 |
| Cells | 6 sentinels × B/C × `lab-ctla1` × Hive = **12 logical grades** |
| Model / version | `hive/ai-generated-and-deepfake-content-detection` / `1` |
| Eligibility | every C sentinel independently: ai ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10 |
| Adverse movement | `adverse_i = max(0, Δai_i, Δflux_family_i, Δdeepfake_i)`; `median(adverse_i over 6 sentinels) ≤ 0.05` |
| Combination rule | single-vendor; **the stored AI-only `verdict` field is NOT used** |

## 3. Call budget (amended)

- `GRADE_DEFAULT_MODE=real` for this leg → the mode-fallback path cannot fire
  (`defaultMode === gradeMode` throws instead of re-calling Hive).
- Maximum **2 Hive attempts per logical grade** (existing `callWithOneRetry`).
- One shared session ID; hard cap **40**.
- Nominal **12** calls; automatic worst case **24** attempts; **16 guaranteed
  reserve**. Anomaly repeats require existing owner authorization — never
  automatic.

## 4. Cache policy + fresh-call provenance (amended — fail-closed, v3)

The deployed cache key is `(image_sha256, vendor, mode)` — no model version or
date, the cache is read BEFORE any vendor call, and `ignoreDuplicates: true`
preserves existing rows. A cached B paired with a live C would not be
contemporaneous, and a forced call would still leave the old row intact.
Frozen policy (strict): **all 12 leg grades must be fresh; any
`cache_hit=true` on a leg grade blocks the entire leg.**

Frozen fresh-path contract (implemented in the hardening build, frozen now):

> The hardening build must provide an owner-authorized, vendor-leg-only fresh
> path that **bypasses cache reads** and writes **every attempt** to an
> immutable round ledger keyed by (round, sentinel, arm, seed, vendor,
> model/version, submitted SHA, task ID, attempt number). It must neither
> delete nor overwrite `grade_cache`. The evaluator reads ONLY those immutable
> leg records. Missing bypass, duplicate logical grades, reused task IDs,
> `cache_hit=true`, or zero provider calls **fails the leg before
> interpretation.**

Implementation may happen after MOCK screening; the required behavior above is
frozen before first light.

## 5. Axis evaluator (amended — pinned, not the stored verdict)

The vendor-leg verdict is computed by the master engineer's pinned evaluator
(`tools/vendor_leg_evaluator.py`, hashed before the leg) from the raw stored
grades, with the frozen formulas:

- `ai = classes.ai_generated`
- `deepfake = classes.deepfake`
- `flux_family = max(value for normalized source key containing "flux" or "auraflow")`
- `adverse_i = max(0, Δai_i, Δflux_family_i, Δdeepfake_i)`
- `median(adverse_i across six sentinels) ≤ 0.05`
- every C sentinel independently satisfies all three eligibility thresholds

Mechanical definitions (v3):

- **No Flux/AuraFlow source key present ⇒ evaluator FAILURE, never an implicit
  zero.**
- **Median of six values = arithmetic mean of the 3rd and 4th sorted values.**
- **All calculations use unrounded raw scores; rounding happens only at final
  display.**

The stored `verdict` (AI-only) is never used for the vendor leg.

## 6. Response integrity + model/version enforcement (amended — hardening build)

Required BEFORE the leg runs (does not block screening — see §9): a small
hardening patch to `grade-image/hive.ts` / `index.ts` so that every UNCACHED
response:

- must contain top-level `model` = `hive/ai-generated-and-deepfake-content-detection`
  and `version` = `1` — mismatch fails closed;
- validates `ai_generated + not_ai_generated ≈ 1` (tolerance 1e-3 absolute) and
  source-family scores (including `none`) sum to ≈ 1 (1e-3);
- required fields present and finite;
- C2PA (exact paths and values, v3): report every non-empty
  `algorithmic_tags.c2pa` object. **Fail eligibility when
  `actions_digital_source_type` matches the frozen generative/synthetic
  deny-list, including `trainedAlgorithmicMedia`.** A non-empty
  `claim_generator` or `c2pa.created` alone is reported but is NOT
  independently disqualifying. Malformed present C2PA data fails response
  integrity. (Model estimate: rejecting every non-empty C2PA object could
  wrongly reject ordinary authenticity/editor provenance — hence the
  deny-list on `actions_digital_source_type` only.)

## 7. Submitted bytes (amended)

Submit the EXACT delivered O5 file bytes (the `deepclean-outputs` object),
identified by file SHA-256; record the submitted SHA beside every Hive
`task_id`. No browser re-save, resize, metadata rewrite, or JPEG regeneration.
The operator records the file SHA before upload and verifies it equals the
delivered output SHA in the job report.

## 8. Claim scope (amended)

A pass establishes **Hive single-vendor eligibility only** — never "real-vendor
clean", never two-vendor validation. The ledger and every report retain that
limitation.

## 9. Sequencing

1. Owner replies **"freeze accepted"** → screening (24-cell MOCK round)
   unblocks.
2. Screening gates 1–7 pass → hardening build (§6) commissioned, built,
   master-engineer-verified, owner-deployed.
3. Vendor leg runs under this frozen configuration.

Upgrade path: if TruthScan/Sightengine access is obtained BEFORE the first
screening result is viewed, this freeze may upgrade to the two-vendor 24-call
plan (same combination rule). After first light: locked.

## 10. Security correction (accepted)

The pasted Hive sample's presigned S3 URL is a **bearer token** (temporary
capability for that object), expiring **2026-09-03 04:15:32 UTC**. The
`X-Amz-Credential` portion is only an access-key identifier, not a secret. If
the image is sensitive, treat it as temporarily exposed and ask Hive to
invalidate/delete the task media. No AWS key rotation is indicated by this URL
alone. Do not paste complete presigned URLs again.
