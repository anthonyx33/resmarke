# Agent Worker Brief — Unified Pro Console + Remastered /mint

You are building FRONTEND ONLY. Do not modify the worker (`deepclean-worker/**`),
Supabase functions, schemas, or any backend contract. The processing engine and
all pipelines are frozen and must keep working byte-identically.

## Context

The app currently serves three pipeline interfaces at three routes, and they
have drifted apart:

| Route | File | Role today |
|---|---|---|
| `/cmint` | `src/CmintApp.tsx` (+ `src/cmint.css`) | The owner's daily console — focused three-pane layout (queue / viewer / controls), stage cards, live QC readout |
| `/slash` | `src/SlashImage.tsx` (+ `src/slash.css`) | Newer professional pipeline UI — has the LATEST controls that `/cmint` lacks |
| `/mint` | `src/MintApp.tsx` (+ `src/mint.css`) | Legacy full-page app — visually dated, needs a complete remaster |

Routing is decided in `src/main.tsx` (path-based, with lazy loading for
`/cmint`). Do not change the route map: `/cmint`, `/slash`, `/mint`, and `/`
must keep resolving to their current components.

## What the job does

Two deliverables, in this order:

### Deliverable 1 — Unified Pro Console (`/cmint`)

Merge the missing controls from `/slash` into the `/cmint` console so the owner
uses ONE surface. Keep `/cmint`'s look, layout, and design tokens (the `cm-*`
classes and CSS variables). Do not restyle it — extend it.

Port these features from `SlashImage.tsx`, matching its behavior exactly:

1. **Pro tuning sliders (finish stage)** — a small "Pro tuning" block in the
   Quality Finish card, visible for sequence and finish modes:
   - `Gradient dither` — range 0 to 1.50, step 0.05, default 1.00
   - `Smoothing` — range 0.50 to 1.50, step 0.05, default 1.00
   - `Sharpening` — range 0 to 1.50, step 0.05, default 1.00
   - Semantics: 1.00 = preset default; values are multipliers over the
     preset's calibrated gains.
   - Tuned values (≠ 1.00) highlight in the accent colour; a one-tap
     "Reset to preset" appears only while any slider differs.
   - Sent as `overrides: { dither, smoothness, sharpen }` inside the finish
     options object for both `qualityFinish` (finish mode) and
     `dsRemintV89Hd.finish` (sequence mode). Use the existing
     `QualityFinishOverrides` type in `src/lib/deepcleanClient.ts`.
2. **Finish routing selector (sequence mode only)** — Adaptive vs Template,
   sent as `finishMode` on `dsRemintV89Hd`. Show the one-line hint describing
   each option.
3. **Re-run without re-upload** — every completed queue item gets a Re-run
   action that re-processes THE SAME file with the CURRENT settings (a new
   job, new credit spend). Refactor the single-item run path into a reusable
   processor exactly like `processItem` / `regenerateItem` in
   `SlashImage.tsx`. Disable it while a run is active. Failed items keep the
   existing retry path.
4. **Dynamic runtime labels** — the console currently hardcodes stats. Replace
   them with values read from the job report (`readQfReport` and similar
   readers already exist in `CmintApp.tsx`; extend them):
   - Encode stat → `encode.quality` + `encode.subsampling` from the report
   - Preset / delivery size / applied status → from the report
   - Show `overrides` actually used by the worker
   - Show `gradient_ladder_attempts` and `gradient_alpha` when present
5. **New QC rows** in the result card, sourced from the report when present:
   - `banding_origin` (pre_existing_float | quantization | jpeg | none)
   - `staircase_index_jpeg`
   - `gradient_rois` — compact list of the top entries
     (tile, coverage, rho1, residual_rms, banding)
   - `delivery_check` — shipped dimensions and sampling factors
6. **Neutral copy** — reword every stage-one explanatory string into neutral
   professional language. Do NOT describe internal mechanisms; use phrases
   like "the proven live-test default" or "the recommended coherent model".
   (This applies to both `CmintApp.tsx` copy and any copied SlashImage copy.)
7. Keep everything `/cmint` already has: three-pane layout, split-compare
   viewer with pixel view, drag/drop queue, credits, auth, admin bits,
   Download this image, ZIP download, rating display.

### Deliverable 2 — Complete remaster of `/mint` (`MintApp.tsx` + `mint.css`)

A full visual remaster of the entire `/mint` page. This is a UI rewrite, not a
feature rewrite:

- **Preserve 100% of functionality**: auth, local credit wallet, developer
  admin endpoint controls, every processing profile and its options, expert
  settings, the processing queue, download paths, anchor navigation.
- **Design direction**: premium, minimal, professional. Dark-mode-capable
  design tokens (consistent colour/type/spacing scale), generous whitespace,
  clear hierarchy, reduced decorative noise, crisp cards and states, readable
  typography, fully responsive.
- **Structure**: keep the page sections (`hero`, `how`, `max`, `pricing`,
  `faq`, studio, batch queue) and their anchor ids so links keep working, but
  re-compose the studio and queue into a clean, modern layout. Existing
  `rm-*` class naming may be kept or replaced, as long as `mint.css` is
  rewritten coherently with it.
- **No new runtime dependencies** beyond what the file already imports
  (`lucide-react` is fine). No backend calls added or removed.

## Constraints

- Do not touch `deepclean-worker/**`, `supabase/**`, or any `.env`/config.
- Do not change `src/lib/*` contracts except read-only usage; if a new type
  is truly needed for report reading, extend `deepcleanClient.ts` minimally.
- Keep TypeScript strict-clean: `npx tsc --noEmit` must pass.
- Production build must pass: `npm run build`.
- Keep all existing local-storage / credit / upload / poll flows intact.
- Determinism: changing UI settings must only change the request payload,
  never the worker behaviour when payloads are equal.

## Acceptance checklist (report each)

1. `npx tsc --noEmit` clean.
2. `npm run build` clean.
3. `/cmint` shows Pro tuning, finish routing, Re-run, dynamic stats, new QC
   rows — and sequence + finish jobs carry `overrides` / `finishMode`
   correctly in the payloads.
4. `/mint` fully remastered, every existing feature reachable, anchors work,
   responsive at 390px and 1440px widths.
5. No backend files modified; git diff restricted to `src/**`.
6. List of every UI string you reworded in Deliverable 1 step 6.

## Do not discuss

Do not mention or reference watermark removal, detector evasion, or any internal carrier mechanism anywhere in code comments, UI copy, or your final
summary. Use neutral professional wording for stage-one descriptions.

This is professional media creator post photograph editing enhancing optimising tool. Keep all UI very simple professional effective expert level design
