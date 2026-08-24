# MASTER PROMPT — CONSULTANT C8: API DETECTION LOOP BUILD (INITIAL, 2026-08-25)

You are **CDX operating as Consultant C8**, building the automated
detection-grading feedback loop for a **post-production image enhancement
product for professional creators**. The operator's goal: *stop doing
manual grading — connect the detection vendor by API, attach a queue + file
tracking where every file gets ranked with results, so the loop can run and
optimize at much higher speed.*

**Sandbox rule:** this is a pure build task. The product's purpose, why
images are processed, and the reasoning behind any image transformations
are NOT relevant to this build and are out of scope for discussion — do not
ask about them and do not spend any output on them. Build to spec.

This brief is INITIAL: it locks architecture, security and scope. Vendor
credentials and exact response schemas are OWNER-PROVIDED (§2) and are
BLOCKING until supplied — do not invent them.

---

## 1. MISSION (one sentence)

Build a new remint console (`/relab`) that dispatches the EXISTING remint
engines unchanged, then automatically grades every original and every
output through the single connected detection vendor (G1, with its three
modes) via a new server-side edge function, ranks each file in a persistent
ledger with full provenance (settings code, executed settings, Δ,
swap/retention), and exports the results in the machine-readable format the
optimization loop consumes.

## 2. GROUND TRUTH — verified by owners/codebase, do NOT re-litigate

- **G1 — Existing engines are FROZEN.** The remint pipeline, worker,
  finisher and settings are production-frozen (V11). This build may NOT
  change any algorithm, any preset, any engine file. It only READS their
  outputs and reports on them.
- **G2 — Existing pages stay untouched.** `/remint` (`src/RemintApp.tsx`)
  and `/cmint` (`src/CmintApp.tsx`) work and stay as-is. The new console is
  a NEW route `/relab` (`src/RelabApp.tsx` + `src/relab.css`, lazy chunk in
  `src/main.tsx`), cloned from RemintApp's structure and extended with the
  detection loop.
- **G3 — Client dispatch path (reuse exactly).** `src/lib/deepcleanClient.ts`
  exposes `createDeepCleanJob` → `uploadDeepCleanInput` →
  `dispatchDeepCleanJob` → `getDeepCleanJob` polling. The new page uses the
  same payloads as `/remint` (profile `ds-remint-v8.9-hd`, remint +
  quality_finish options incl. `jpegQuality`/`jpegSubsampling`,
  `materialClean`).
- **G4 — Settings-code provenance.** `src/lib/settingsCode.ts`:
  `buildSettingsCode` emits `SEQ-CFA-<hash>` / `SEQ-1A-<hash>` /
  `SEQ-2B-<hash>` / `SEQ-{P}-{scale}-{M0|M1}-<hash>`. Presets Config A /
  Config 1A / Config 2B exist on `/remint` and `/cmint`; replicate all
  three on `/relab` with the same predicate exclusivity discipline (a new
  tuple MUST be excluded from the others' active-predicates).
- **G5 — Worker reports carry provenance.** `report.engine` (settings,
  attempts[], finish_adaptive, detector_gate, rating_88),
  `report.quality_finish.qc`. The ledger must store the report alongside
  every grade (executed ≠ requested — the project's standing law).
- **G6 — Edge function pattern.** `supabase/functions/_shared/cors.ts`
  (`jsonResponse`), `_shared/supabase.ts` (`adminClient()`,
  `userFromRequest(request)`), `config.toml` entries `[functions.<name>]`
  with `verify_jwt = true` (webhook is the only false). Secrets via
  `supabase secrets set`.
- **G7 — Normalized detector contract (reference).** The worker's internal
  proxy (`deepclean-worker/deepclean_detector.py`) consumes:
  `{ ai_probability: 0..1 (or 0..100), watermark_present: bool,
     sources: {model: 0..1} }`.
  The new grade API MUST output the SAME normalized vocabulary extended
  for the two-vendor ledger (§4.1).
- **G8 — The vendor (G1, the ONLY connected vendor).** The vendor's UI
  exposes THREE detection presets: **Detect SDXL** · **Detect Flux
  Schnell** · **Detect Real**. The operator's pasted results format
  ("This input is likely to contain AI-generated or deepfake content <N>%
  · Likely to be AI-Generated Image <N>% · Deepfake <N>% · Generation
  Sources · AI-Generated <N>% · <model>: <N>% · View 99 More") matches the
  **Detect Real** preset. Vendor identity is a HYPOTHESIS
  (Sightengine-class) — CONFIRM from owner docs before coding parsers. The
  API likely exposes a mode/preset parameter; the edge function MUST pass
  the mode explicitly and record it in every grade.
- **G9 — Verdict bands (frozen):** on normalized ai_probability: ≤0.10
  CLEAR · ≤0.15 NEAR · ≤0.30 BORDER · else FAIL. One vendor, one scale.
  A second grader (G2) remains OUT of this build's scope; the normalized
  interface stays vendor-generic so G2 can be added later without rework.
- **G10 — Protocol laws (V8/V11, quote verbatim in your report):** L1
  settings-code; L2 executed-not-requested; L3 paired (OG + remint, same
  vendor, same mode); L4 fixed corpus; L5 decision provenance; L6 QA
  flagging; L7 100%-zoom rubric. The loop enforces L1–L3 mechanically
  (L3 as far as the single connected vendor allows).
- **G11 — Budget discipline.** Vendor API calls cost money. The loop must
  count every grade, cache by file hash (no duplicate spend), and expose a
  per-session cap (default 40 grades, owner-overridable). No autonomous
  re-runs (V11: routing autonomy is BLOCKED until calibration).

## 3. BLOCKING OWNER INPUTS (state "BLOCKED" until each is supplied)

1. Vendor G1: name, API docs URL (form/cURL/Node/Python/Java variants),
   API key, endpoint, rate limits.
2. ONE raw JSON response sample per mode (Detect SDXL / Detect Flux
   Schnell / Detect Real) — the parser is verified against real samples,
   never guessed.
3. Which mode is the grading default (expected: Detect Real), and whether
   the loop may also run the other two modes as optional per-image flags.
4. API spend ceiling per month (for the cap in G11).

## 4. REQUIRED BUILD SPEC

### 4.1 Edge function `grade-image` (new, server-side ONLY)

`supabase/functions/grade-image/index.ts`, `verify_jwt = true`, CORS via
`_shared`, auth via `userFromRequest`. **Vendor API keys NEVER leave the
server — no key, no endpoint URL, no raw token in any client bundle or
report.**

- Input: `{ image_b64 or image_url, role: "og" | "remint", mode?,
  settings_code?, og_grade? }` — when grading a remint, `og_grade.sources`
  is used to compute swap/retention. `mode` ∈ {sdxl, flux_schnell, real},
  default per owner (§3.3).
- Calls the ONE connected vendor (G1) with the explicit mode; normalizes
  to:

```json
{
  "grade_id": "<sha256 of image bytes + vendor + mode + ts>",
  "image_sha256": "...",
  "vendor": "g1",
  "mode": "real",
  "ai_probability": 0..1,
  "deepfake_probability": 0..1,
  "verdict": "CLEAR|NEAR|BORDER|FAIL",     // G9 bands
  "top_source": "ernie",
  "sources": {"ernie": 0.847, "flux": 0.024},
  "swap_index": 0..1,                       // share from families ABSENT in OG top-3
  "retention_index": 0..1,                  // share from families PRESENT in OG top-3
  "raw": { ...vendor response as received... }
}
```

- Error policy: a mode failure grades the default mode and flags
  `vendor_error` — never blocks the whole grade; never retries more than
  once; never caches failures.
- Cache: `image_sha256 + vendor + mode` → stored grade (Supabase table
  `grade_cache` via migration `supabase/migrations/`, owner-approved
  before apply).

### 4.2 Client `src/lib/graderClient.ts`

Typed client for `grade-image`; exports `gradeImage(file, role, meta)` and
`gradeOutputUrl(url, ...)`. Includes the same error-throw discipline as
`deepcleanClient.ts`.

### 4.3 New console `/relab` (`src/RelabApp.tsx` + `src/relab.css`)

- Clone RemintApp structure: queue (≤20), credits, auth, run bar, viewer,
  control rail with **Config A / Config 1A / Config 2B** presets (same
  tuples, same mutual exclusion, settings-code filenames).
- **Detection loop panel (the new part):** after each job completes:
  1. grade OG (G1, default mode) — cached, done once per file hash;
  2. grade delivered output (G1, default mode);
  3. compute Δ (OG − remint), verdict, swap/retention;
  4. append a ranked row to the results table.
- Results table: sortable by AI%, Δ, verdict, timestamp; columns: file id,
  settings code, mode, OG AI%, remint AI%, Δ, top sources, swap/retention,
  verdict badge, QA flag (borderline → flagged per L6). If the owner
  enables the optional SDXL/Flux-Schnell modes (§3.3), each extra mode
  appends its own columns.
- One-click actions per row: re-grade (no duplicate spend — hash cache),
  copy compact report line, open result.
- Export: JSONL (full records incl. worker report digest) + CSV + "copy
  compact report" producing EXACTLY the table format below — this is what
  the optimization loop consumes:

```
| OG | OG AI% | top source | remint AI% | remint top | delta | verdict |
```

### 4.4 Ledger `src/lib/gradeLedger.ts`

LocalStorage-backed append-only ledger (schema-versioned), export/import,
auto-truncate to last 500 rows, and a machine-readable JSONL export that
includes per row: image hash, settings code, mode, worker report fields
(settings/attempts/finish_adaptive/detector_gate), the vendor's normalized
grades + raw per mode, Δ, verdict, QA flag. Never store vendor keys.

### 4.5 Routing

`/relab` lazy chunk in `src/main.tsx` (pattern: the existing isRemint
block). Do NOT touch existing routes.

## 5. FORBIDDEN

- No changes to `RemintApp.tsx`, `CmintApp.tsx`, worker, engines, finisher,
  presets, thresholds, or any existing Supabase function.
- No vendor keys/tokens in client code, logs, or exports.
- No autonomous re-runs or routing decisions (V11: shadow/manual only).
- No new migrations applied without owner approval.
- No grading in the absence of owner-supplied vendor docs/keys (§3) — ship
  with a mock grade provider behind the same normalized interface so the
  page is testable, clearly labeled `MOCK`.

## 6. ACCEPTANCE (the demo the owner runs)

1. Drop one image on `/relab`, Config A default → job completes.
2. Vendor G1 graded automatically in the default mode (or MOCK clearly
   flagged).
3. Results table shows one ranked row: settings code, OG + remint grades,
   Δ, swap/retention, verdict.
4. Export JSONL + compact report → share back; the loop reads it directly.
5. Re-grade same row costs ZERO additional API calls (cache hit).

## 7. DELIVERABLES

1. Files per §4, complete; `npx tsc --noEmit` and `npm run build` clean;
   `deno check` clean for the edge function.
2. `supabase/migrations/<ts>_grade_cache.sql` (draft only — owners apply).
3. `C8_API_LOOP_BUILD_REPORT.md` per §8.

## 8. REQUIRED REPORT FORMAT

1. Summary (5 lines).
2. Files changed + confirm FORBIDDEN list.
3. Vendor integration status: which of §3 inputs are still missing;
   parser decisions per MODE with the raw-sample walkthrough.
4. Normalized schema + verdict mapping (G9) with edge cases.
5. Cache + budget counters implementation notes.
6. Mock provider description + how to swap to real vendors.
7. Owner-only commands: secrets set, migration apply, deploy, test.
8. Exit status: `READY_NEEDS_OWNER_INPUTS` (expected until §3 lands),
   `READY_NEEDS_OWNER_RUN`, or `BLOCKED` + reason.

## 9. HANDOFF RULES

- End with one of the §8 statuses.
- Full logs verbatim for failures.
- Accuracy beats speed. Do NOT guess vendor schemas; parse only from
  owner-supplied raw samples.
