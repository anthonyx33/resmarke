# BUILD REPORT — CORPUS VISUAL RUN HISTORY

Date: 2026-08-26 · Builder pass against `BRIEF_CORPUS_VISUAL_HISTORY.md`
Status: **built, validated offline, NOT committed / NOT deployed** (gate 5 honoured).

## 1. Scope

| Brief item | State |
|---|---|
| A · edge function `corpus-run-history` | Built |
| B · CorpusApp "Visual history" panel + before/after modal | Built |
| C · `/relab` one-click corpus round runner | **NOT built — OPTIONAL, owner approves separately** |

Item C is untouched by design: the brief marks it as requiring separate approval, so
`src/RelabApp.tsx` has zero diff.

## 2. Files changed

| File | Change |
|---|---|
| `supabase/functions/corpus-run-history/index.ts` | **new** — 230 lines, admin-only paginated run history with signed URL pairs |
| `supabase/config.toml` | **+3 lines** — `[functions.corpus-run-history] verify_jwt = true` |
| `src/lib/corpusClient.ts` | `CorpusVisualRun` / `CorpusVisualHistory` types, `fetchCorpusRunHistory()`, `compactVisualReport()` |
| `src/CorpusApp.tsx` | Visual history panel, before/after modal, `VisualThumb` / `VisualFigure` / `GradeCard`, `shortCode()` |
| `src/corpus.css` | +68 lines appended, all under new `cp-vh-*` / `cp-modal-*` / `cp-grade-*` classes |

No new dependencies. No new storage buckets. No migration. No vendor call. No credit path touched.

`supabase/config.toml` is not on the forbidden list and the edit is mandatory — without the
`verify_jwt = true` entry the new function would deploy unauthenticated. It is the only
non-corpus-scoped file touched.

## 3. Server contract — `corpus-run-history`

POST, `verify_jwt = true`, `requireCorpusAdmin` (same UUID/verified-email allowlist as every
other corpus function). Any non-admin gets the existing 403; unconfigured allowlist gets 503.

Request (all optional):

```json
{ "experiment_id": "uuid", "corpus_image_id": "uuid",
  "config_label": "A|1A|2B|3C|CUSTOM", "limit": 20, "offset": 0 }
```

- `limit` default 20, clamped to 1..100 — out-of-range or non-integer → **400** before any query.
- `offset` default 0, 0..100000 → 400 otherwise.
- `config_label` outside the five labels → 400.
- No filter = **all runs across all experiments**, `created_at desc`, `id desc` tiebreak.

Response:

```json
{ "runs": [ … ], "total": 67, "limit": 20, "offset": 0,
  "has_more": true, "signed_url_ttl_seconds": 120, "signed_at": "…" }
```

Each row: `run_id, created_at, experiment_id, corpus_image_id, file_name, config_label,
config_key, settings_code, requested_settings_canonical, requested_settings_sha256,
executed_settings_sha256, worker_report_sha256, og_sha256, output_sha256, output_byte_size,
output_copy_status, og_grade, remint_grade, delta, swap_index, retention_index, grade_status,
verdict, qa_flag, mock, engine_version, engine_release, detector_{vendor,mode,model,version},
runtime_ms, job_id, og_width, og_height, og_url, output_url`.

Design notes:

- **Signed URLs**: one `createSignedUrls(paths, corpusDownloadTtl())` call per request over the
  deduped set of original + output paths — the exact `corpus-read` pattern, 120 s default TTL,
  nothing cached beyond the response.
- **`raw` is stripped** from both grades before serialising. It is the untouched vendor payload,
  durable in `grade_cache` / `corpus_runs`, and would dominate a 20-row page. Everything the
  viewer shows (ai/deepfake probability, verdict, top_source, sources, mock, vendor/mode) survives.
- `mock` is derived from the grade JSON (`remint_grade.mock || og_grade.mock`) — there is no
  `mock` column on `corpus_runs`.
- `verdict` is `remint_grade.verdict`, falling back to `grade_status` for PENDING rows — same
  precedence the existing Run history table uses.
- Pagination uses `count: "exact"` + `.range()`, so `total` is the true filtered count.

## 4. Client

**Panel** (`.cp-visual`, sits directly above the existing text Run history, which is unchanged):
80×80 OG thumb → arrow → 80×80 remint thumb, file name + short settings code, config chip,
`OG% → RM%` with signed delta, verdict badge, FLAG/MOCK chips, timestamp. Rows are `<button>`s.
Filters: experiment (All + each), image (All + every registered original), config
(All/A/1A/2B/3C/CUSTOM) — every filter change resets to page 1. 20/page, Newer/Older pager,
`loading="lazy" decoding="async"` on every thumbnail. Distinct loading / empty / error states,
independent of the legacy Run history state so nothing about the old panel changed.

**Modal**: side-by-side full-size OG vs remint, both fit-to-viewport (`object-fit: contain`,
`max-height: min(62vh, 620px)`); a **Swap** mode shows one image full-width and click-toggles
OG↔remint in place for A/B flicker comparison. Below: both grade breakdowns (headline AI%,
verdict, deepfake%, top source, detector, top-5 source bars), delta, swap/retention, grade
status, runtime, config key, engine, OG/output sha256, run id, job id; full settings code in a
selectable readonly field; canonical settings JSON in a collapsed `<details>`. Footer: Copy
settings code, Copy compact report line, Open original, Open output. Esc and backdrop click close.

**Signed-URL expiry** — the one real UX hazard, handled explicitly. A 120 s TTL means a modal
opened three minutes after page load would fetch a dead URL. The panel tracks browser-side
receipt time, warns once the links pass `ttl − 20 s`, silently re-fetches the page before
opening a modal against stale links, offers an explicit "Refresh links" button in both the panel
and the modal, and every `<img>` falls back to an "expired — refresh links" placeholder on error
instead of a broken-image icon.

## 5. Validation log

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | **pass** (clean) |
| `npm run build` | **pass** — `✓ built in 1.03s`, `CorpusApp` chunk 33.67 kB gzip 8.92 kB |
| `deno check supabase/functions/corpus-run-history/index.ts` | **pass** |
| `git diff --check` | **pass** (no whitespace errors) |
| Forbidden-list zero diff | **pass** — verified empty `git diff --stat` over `src/RemintApp.tsx`, `src/CmintApp.tsx`, every CSS file except `src/corpus.css`, `dispatch-deepclean-job/**`, `grade-image/**`, `get-deepclean-job/**`, `supabase/migrations/**`, `deepclean-worker/**`; `IMG-REMINT-v1/` still untracked and untouched |
| Gate 3 — 67 rows + valid signed URLs, filters, pagination | **NOT verified — requires deploy** |
| Gate 4 — browser smoke of grid + modal | **NOT verified — requires deploy; no browser tooling in this session** |
| Gate 5 — no commit/push/deploy | **honoured** — working tree only |

Gates 3 and 4 cannot be closed by the builder: both need the function live, and deploying is
explicitly the master engineer's call. There are no screenshots for the same reason. The
commands below close them in one pass after your deploy.

## 6. Master-engineer verification steps

```bash
supabase functions deploy corpus-run-history          # after reviewing the diff

# Gate 3 — total must be 67, both URLs must be non-null and fetchable
curl -s -X POST "$SUPABASE_URL/functions/v1/corpus-run-history" \
  -H "authorization: Bearer $OWNER_JWT" -H "content-type: application/json" \
  -d '{"limit":20,"offset":0}' | jq '{total, returned: (.runs|length),
      first: .runs[0] | {run_id, config_label, settings_code, og_url: (.og_url != null),
      output_url: (.output_url != null), verdict, delta}}'

# pagination: page 2 must not repeat page 1 run_ids
curl -s … -d '{"limit":20,"offset":20}' | jq '[.runs[].run_id]'

# filters: config + experiment + image, and the 400 gates
curl -s … -d '{"config_label":"3C"}'   | jq '[.runs[].config_label]|unique'
curl -s … -d '{"limit":101}'           | jq .error   # expect 400 "limit must be an integer between 1 and 100."
curl -s … -d '{"config_label":"ZZ"}'   | jq .error   # expect 400
```

Gate 4: open `/corpus` as the allowlisted owner → the Visual history panel renders 80×80 pairs;
click the 3C pilot row (`SEQ-3C-nzzomjahxuyi`) → full-size before/after opens with both grade
breakdowns. No vendor call and no credit mutation is possible on this path — the function only
reads `corpus_runs`, `corpus_images`, `corpus_experiments` and signs storage URLs.

## 7. Follow-ups for the owner

1. Approve or decline item C (one-click 11-image corpus round from `/relab`) as a separate build.
2. If you want thumbnails to survive long browsing sessions without a refresh click, the clean
   fix is a longer `CORPUS_DOWNLOAD_TTL_SECONDS` for this path — an env change, not a code
   change, and it widens the signed-link window, so it is your call rather than a default.
