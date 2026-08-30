# VENDOR FREEZE — 4D-1a (OWNER STEPS)

**RESOLVED (2026-08-27):** the owner reported authenticated access to Hive g1
ONLY — no TruthScan or Sightengine. The pre-registered single-vendor fallback
therefore applies; the freeze record is `VENDOR_FREEZE_4D_1A.md` (12-call
single-vendor A/B leg, Hive only). The steps below remain valid ONLY for the
optional upgrade path: obtaining second-vendor access BEFORE the first screening
result is viewed. After first light nothing can change.

Round: 4D-1a · Precondition per frozen brief §6: Vendor 2 + all vendor-leg
constants must be frozen **before the first screening result is viewed**.
Screening may not start without this. Vendor calls happen ONLY after screening
gates 1–7 pass; nothing below spends a vendor call.

Current state of the grading code (verified):
- `supabase/functions/grade-image` supports ONE real vendor: **Hive ("g1")** —
  env `GRADE_PROVIDER=g1` + `HIVE_SECRET_KEY`, parser `grade-image/hive.ts`.
- The three mission axes are `ai` (ai_probability), `flux-family`
  (sources["flux"/"flux-schnell"]), `deepfake` (deepfake_probability).
- Session cap 40 via `reserve_grade_call`. There is NO TruthScan or Sightengine
  code yet. The freeze therefore has a decision part (yours, now) and a small
  adapter-build part (C88, later — it does NOT block screening; only the
  recorded decision does).

## Step 1 — Check which vendor you can actually use

Log into both dashboards and confirm API access. You freeze the one you have
**authenticated working access** for:

- **TruthScan** — https://www.truthscan.com (account + API plan)
- **Sightengine** — https://sightengine.com (account; AI-generated detection
  model)

If neither has an active key, sign up first (you, not C88 and not me). If both
work, choose the one whose single-call AI-image API returns BOTH an AI/real
probability AND a per-family/source breakdown — we need both to feed the three
mission axes.

## Step 2 — Gather the freeze constants (paste to me)

For the chosen vendor, collect and send me (no secrets in chat):

1. API documentation URL + the exact endpoint/version string you will pin.
2. The **model/version identifier** the response reports.
3. One **redacted sample JSON response** from a test call on a known image
   (your OG + a known Config A remint) — strip keys, keep field structure.
4. The score fields: which field(s) map to ai-probability, which to
   deepfake, which to family/source scores (flux-family axis).
5. Retry/error behavior you want frozen (default: reuse the existing
   `VendorAttemptError` 2-attempt pattern with 60s timeout).

## Step 3 — Record the freeze (I will produce the record file)

Once you give me the vendor name + docs, I will write
`VENDOR_FREEZE_4D_1A.md` containing, verbatim and signed:

- Vendor 1 = Hive g1 (deployed) · Vendor 2 = <your choice> (API + model
  version pinned, score-field mapping table).
- The six sentinels: IMG-5, 6, 7, 8, 9, 11.
- Combination rule (carry-over from 4D-CAM-1 gate 8): lexicographic
  worst-category; each vendor's median adverse score movement ≤ +0.05; every
  C sentinel must satisfy the fixed eligibility thresholds
  (ai ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10) at EACH required vendor.
- Budget: 6 × B/C × 2 vendors = 24 calls, 16 reserve of 40.
- Retry/error policy and the per-vendor eligibility interpretation.
You review it, then reply "freeze accepted". That reply is the recorded
precondition — screening can start the moment it exists.

## Step 4 — Set the secret yourself (never through me or chat)

In a terminal only you control:

```
supabase secrets set VENDOR2_SECRET_KEY=<your-api-key> \
  --project-ref otzjqcnrabfbonjywlye
```

(Secret name finalized in the adapter brief; this is the convention.)

## Step 5 — Vendor adapter build (parallel, after screening OK)

The `grade-image` function needs a second-provider branch: parser
`grade-image/truthscan.ts` or `grade-image/sightengine.ts`, env
`GRADE_PROVIDER_V2`, dual-vendor grading on the vendor leg. I will write the
adapter brief, C88 builds, I verify line-by-line, you deploy — exactly like
every other piece. This does NOT block the 24-cell screening round.

## Step 6 — Sequence

1. You pick the vendor + send docs (Steps 1–2).
2. I write the freeze record; you accept it (Step 3) → **screening unblocks**.
3. C88 builds 4D-1a per the FINAL brief → I verify → you deploy → Flash runs
   the 24 cells (all MOCK, 0 vendor calls).
4. Only if gates 1–7 pass → adapter build (Step 5) → you set the secret
   (Step 4) → the 24-call vendor leg.

Rule that never bends: Vendor 2 is frozen before ANY screening result exists.
There is no path that chooses the vendor after results.
