# PROMPT — REMINT Console (`/remint`) · Foundational Brief for Expert UI Code Builder

You are an expert UI code builder. Build a brand-new, production-grade page at
**`/remint`** in this repo. It is a redesigned, simplified sibling of the
existing **`/cmint`** console — same backend, same engine, new experience.

**Non-negotiable rule #1: `/cmint` stays byte-for-byte untouched and 100%
working.** Do not edit `src/CmintApp.tsx` or `src/cmint.css`. Do not change the
behavior of `/slash`, `/print`, `/mint`, or the legacy console.

**Non-negotiable rule #2: reuse the existing backend client as-is.** The page
must work end-to-end on the first real job. Every control must map to the exact
fields below — no invented fields, no new edge functions.

---

## 1. Product vision

A minimal, Apple-grade console. One clean action surface, everything else
tucked away. Brand feel: **fresh, cool, mint** — accent `#89cff0` (baby neon
blue) over mint neutrals. Think iOS Settings + AirDrop aesthetic: generous
whitespace, hairline borders, soft radii, restrained type, zero clutter.

- Visible by default: drop zone + queue, **Strength** (3-way), **Restoration**
  (4-way incl. Fidelity HD), **Delivery size** (3 buttons), **Wall smoothing**
  toggle, settings-code preview chip, Run button, Results (in a collapsible).
- Everything else (wash model, engine mode, metadata, naming, pro-tuning
  sliders, finish routing, theme, credits/sign-in) lives in a **hamburger**
  drawer or accordion — present, but hidden until opened.
- Do NOT brand the run mode as "Full Quality Remint" anywhere. Default naming
  is the settings-code (see §6). Keep copy professional: "Remint" / "Process".

## 2. Files to create / edit

| Action | File |
|---|---|
| CREATE | `src/RemintApp.tsx` (default export, lazy-loadable) |
| CREATE | `src/remint.css` (imported INSIDE the component file, like cmint) |
| EDIT | `src/main.tsx` — ONLY add the route branch + lazy import. Touch nothing else. |

In `src/main.tsx` (currently a ternary at L21–34), add exactly:

```ts
const isRemint = lowerPath === "/remint" || lowerPath.startsWith("/remint/");
const RemintApp = lazy(() => import("./RemintApp"));
```

and insert `isRemint → RemintApp` into the component selection BEFORE the
`else → App` fallback (after `isPrint`). `/remint` currently falls through to
`App`; nothing else changes. Vercel rewrites `/(.*) → /` already, so no server
routing work.

## 3. Exact backend wiring (verified against source, Aug 22 2026)

Import from `src/lib/deepcleanClient.ts` (do NOT modify this file):

- `createDeepCleanJob({ file, creatorId, profile, outputMode: "stripped",
  dsRemintV89, qualityFinish, dsRemintV89Hd, outputNameStyle, outputNameCustom })`
- `uploadDeepCleanInput(job, file)` → `dispatchDeepCleanJob(job.id)` →
  `getDeepCleanJob(job.id)` polling (cmint uses 3.5 s, no timeout) →
  `cancelDeepCleanJob(id)` on failure.
- Types: `DsRemintV8_8Options { engineMode, washModel, strength, iphoneExif,
  metadataMode? }` · `QualityFinishOptions { preset, scale, overrides,
  materialClean? }` · `DsRemintV8_9HdOptions { remint, finish, finishMode? }` ·
  `DeepCleanJob { id, status, outputUrl, outputName?, runtimeMs?, gpuType?,
  report?, failureReason? }`.

Job-body shape per pipeline mode (exactly as `createDeepCleanJob` sends it):

| Mode | profile | body fields |
|---|---|---|
| sequence (remint + finish) | `"ds-remint-v8.9-hd"` | `ds_remint_v8_9_hd: { ds_remint_v8_9: {engine_mode, wash_model, strength, iphone_exif, metadata_mode}, quality_finish: {preset, scale, finish_mode, overrides} }` |
| remint only | `"ds-remint-v8.9"` | `ds_remint_v8_9: {...}` |
| finish only | `"quality-finish"` | `quality_finish: {preset, scale, overrides}` |

### Control → field mapping (copy these exactly)

| UI control | Options | Field |
|---|---|---|
| Strength | light / balanced / deep | `dsRemintV89.strength` |
| Wash model (hamburger) | qwen / zimage / qwen+zimage | `dsRemintV89.washModel` |
| Engine (hamburger) | adaptive / template | `dsRemintV89.engineMode` |
| Metadata (hamburger) | device / minimal | `dsRemintV89.metadataMode` |
| iPhone EXIF (hamburger) | on/off | `dsRemintV89.iphoneExif` |
| Finish routing (hamburger, sequence only) | adaptive / template | `dsRemintV89Hd.finishMode` |
| Restoration strength | conservative / standard / strong / fidelity (label "Fidelity HD") | `qualityFinish.preset` |
| Delivery size | Native (1) / 1.6× HD / 2× Max; expert slider 1.0–2.0 step 0.05 | `qualityFinish.scale` → send `null` when ≤ 1.001 |
| Wall smoothing · Mobile Clean | checkbox (default ON) | `qualityFinish.materialClean` ⚠️ see §8 |
| Pro tuning: dither | 0–1.5 step 0.05 (1.00 = preset) | `overrides.dither` |
| Pro tuning: smoothing | 0.5–1.5 step 0.05 | `overrides.smoothness` |
| Pro tuning: sharpen | 0–1.5 step 0.05 | `overrides.sharpen` |

### Config A — the default state on first load (EXACT)

`applyWavl()` semantics. On mount (when nothing overridden), set:

```
mode: "sequence"          // remint + finish
washModel: "qwen"
strength: "deep"
engineMode: "adaptive"
qfPreset: "strong"
qfScale: 1                // → scale: null (Native, ≤1250px remint stage)
tuneSmooth: 1.25
tuneDither: 1
tuneSharpen: 1
wallClean: true
finishMode: "adaptive"
```

Show a small "Config A · Proven" chip when the current on-screen state still
equals this tuple (same predicate idea as cmint's `wavlActive`). Provide a
"Reset to Config A" action (one tap).

## 4. Credits & auth (same rules as cmint — do not weaken)

- Unit cost: sequence = 23, remint = 17, finish = 6 (`15+2` remint/adaptive,
  `6` finish). Gate Run on `credits.privacyCredits >= totalCost` for the
  selected batch.
- `readLocalCredits` / `spendLocalPrivacyCredit` from `src/lib/localCredits.ts`;
  Supabase path via `supabase.functions.invoke("spend-privacy-credit",
  { body: { amount } })` exactly as cmint `spendCredits` does; on error it must
  throw so the job gets cancelled (cmint behavior). Sign-in pre-check with
  `supabase` from `src/lib/supabase.ts` (null-guard; supports demo mode without
  config).

## 5. Queue & image actions (must keep all)

- Drop zone + file picker; accept `image/jpeg|png|webp`, max 25 MB each, max
  20 items; previews via `createImageBitmap`.
- Per item: **download** (fetch `job.outputUrl` → blob), **redo**
  (re-run with current settings → new job + fresh credit), **remove**.
- **Download all** → dynamic `await import("fflate")` zip, filename
  `remint-images.zip` (keep fflate out of the initial chunk).
- **Change order** via HTML5 drag & drop (`draggedId` + `moveItem` pattern).
- **Re-run all** → iterate items with the CURRENT on-screen settings (each
  bills a fresh unit cost; guard `running`/busy; pre-check sign-in + credits).
- Polling: every 3.5 s per item, no timeout; statuses queued/uploading/
  processing/completed/failed; show error text per item on failure.

## 6. Naming (settings-code is DEFAULT)

- Import `buildSettingsCode` from `src/lib/settingsCode.ts`. Input shape:
  `{ mode, remint: { washModel, strength, engineMode }, finish: { preset,
  scale, finishMode, overrides, materialClean } }`. Output format
  `SEQ-STD-N-M1-<12char>` (preset codes CON/STD/STR/FID, scale `N` when null,
  `M0` when wall off). EXCEPTION: exact Config A emits `SEQ-CFA-<12char>`
  (CFA is reserved for the exact all-clear tuple and nothing else).
- Default `nameStyle: "settings-code"`. Show the live preview chip
  (recomputed from current on-screen settings). Keep `photo-style`, `original`,
  `custom` available in the hamburger (expert) menu.
- Download filenames: replicate cmint's `outputNameFor` pattern (`.jpg`
  suffix; positional suffixes `-2`, `-3`… for batches; segment suffix for
  mode). Server-side naming goes through `outputNameStyle`/`outputNameCustom`
  on create.

## 7. Results — collapsible, hidden by default

A collapsed accordion ("Results") that expands for the selected completed
item, showing (all from `job.report.engine`, read like cmint's `readQfReport`):

- runtime seconds, GPU type, delivered W×H, encode quality/subsampling
- quality finish: applied/skipped, preset, scale, overrides multipliers
- Quality index `rating_88` (clamp 0–88)
- QC rows: SSIM, noise-floor ratio, ρ₁, residual RMS, H1/H0, ringing,
  flatness Δ, staircase index, banding origin, delivery check
- gradient ROI tiles; Download + Re-run buttons

Keep it OUT of the way: collapsed card by default, expand on tap.

## 8. Known pitfalls (read before coding)

1. **`materialClean` is dropped on the wire by the current client**
   (`createDeepCleanJob` serializes `quality_finish` as `preset, scale,
   overrides` only). Mirror cmint behavior: the wall toggle affects the
   settings-code hash only. Do NOT "fix" this silently. If you believe it
   should be real, flag it in your final report as an explicit proposed
   change (`deepcleanClient` + edge function already accept `material_clean`
   server-side per the composer) — do not ship it in this task.
2. Shared libs (`deepcleanClient`, `settingsCode`, `localCredits`, `config`,
   `supabase`) are used by 5 other pages — do not change signatures. Add
   fields only as optional if absolutely necessary.
3. `styles.css`, `mint.css`, `slash.css` are statically imported in
   `main.tsx` and leak everywhere. Scope everything new: root class
   `.remint`, prefix `rx-`, scoped tokens `--rx-*` on `.remint`, and use
   `body:has(.remint)` for the full-viewport takeover (like cmint does).
4. Theme: support light + dark via `html[data-theme="dark"]` scoped tokens
   (localStorage key `resmarke:theme`, as cmint). Accent `#89cff0`; mint
   secondary (e.g. `#00d2a0`-family) — never purple.
5. React 19 StrictMode double-invokes effects in dev; keep object-URL
   cleanup idempotent.
6. `waitForJob` in cmint has no timeout — keep the same (jobs can take
   minutes; the worker is warm).
7. Keep it dependency-free beyond what's installed (lucide-react available).
   fflate stays dynamic.

## 9. Design language (Apple-grade)

- System font stack; 13–15 px UI type; 17+ px titles; tight letter-spacing.
- Cards: white / near-white, 1 px hairline borders, 12–16 px radii, soft
  shadows only on elevation.
- Accent `#89cff0` for primary actions & focus rings; mint for success states;
  red only for failures. Generous 16–24 px spacing grid; icons 18 px stroke 1.5.
- Controls: segmented controls (not raw select menus) for Strength /
  Restoration / Delivery size; iOS-style toggle for Wall smoothing; compact
  sliders in the hamburger.
- Motion: 150–200 ms ease transitions on accordions/drawer only. No flashy
  animation.
- Responsive: 2-pane desktop (queue left, controls right), single-column
  mobile with the hamburger housing controls.

## 10. Acceptance criteria (all must pass)

1. `npx tsc --noEmit` clean; `npm run build` clean (Vite + TS 5.9).
2. `/cmint` renders and behaves EXACTLY as before (no diff to its files).
3. `/remint` loads fast (lazy chunk), no console errors, dark mode works.
4. Config A default: entering the same settings on `/cmint` yields an
   IDENTICAL `buildSettingsCode` string (proves field parity).
5. Full end-to-end: drop a real image → Run (Config A) → queued →
   processing → completed → download works, download-all zip works, re-run
   bills a fresh credit, reorder/remove work, results accordion shows QC.
6. The settings-code preview matches the delivered filename for a single
   image.
7. Final report: list files created/edited, the materialClean wire-gap
   observation, and any deviations.

Work until ALL criteria pass. `/cmint` is the reference implementation for
every backend call — read it, then simplify, never alter.
