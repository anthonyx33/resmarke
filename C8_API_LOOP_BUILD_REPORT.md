# C8 API Loop Build Report

Build date: 2026-08-25  
Consultant: C8

## 1. Summary

- `/relab` now has an isolated **Run API detection only** event for the selected original; it does not create or dispatch a remint job and spends zero remint credits.
- The authenticated `grade-image` Edge Function is connected to Hive's unified AI-generated/deepfake detector with credentials stored only as Supabase server secrets.
- The production cache/budget migration is applied: first live grade used one provider call; an identical second grade was a cache hit with zero provider calls.
- The website's SDXL, Flux Schnell, and Real controls are example-image presets, not separate API parameters; the ledger records the unified API as canonical mode `real` and preserves `requested_mode` for compatibility.
- The UI and CSV exports rank the top five AI source families, alongside deepfake probability and cache/call/hash provenance; full normalized sources and raw data remain in JSONL.

Protocol laws (verbatim): **L1 settings-code; L2 executed-not-requested; L3 paired (OG + remint, same vendor, same mode); L4 fixed corpus; L5 decision provenance; L6 QA flagging; L7 100%-zoom rubric.** The implementation mechanically enforces L1-L3. L4-L7 remain operator protocol; BORDER results and provider fallback errors are mechanically QA-flagged for L6.

## 2. Files changed and forbidden-scope confirmation

Current integration changes:

- `supabase/functions/grade-image/index.ts` - live Hive request, retry policy, canonical unified mode, cache/budget integration, portable base64 upload, and server-safe errors.
- `supabase/functions/grade-image/hive.ts` - strict verified Hive response parser.
- `supabase/functions/grade-image/hive_test.ts` - parser success and rejection tests.
- `src/RelabApp.tsx` - unified Hive detector UI, isolated detection-only action, top-five source rankings, and compact API provenance views.
- `src/lib/gradeLedger.ts` - stable top-five source derivation plus richer paired and detection-only CSV exports; the full source map remains the ledger ground truth.
- `src/relab.css` - live-provider status styles.
- `supabase/migrations/20260825000000_grade_cache.sql` - applied cache, session counter, RLS, and atomic reservation RPC.
- `deno.lock` - locked Deno test dependencies.
- `C8_API_LOOP_BUILD_REPORT.md` - this deployment handoff.

The previously delivered `/relab` files remain in place: `src/lib/graderClient.ts`, `src/lib/gradeLedger.ts`, the lazy route in `src/main.tsx`, and `[functions.grade-image] verify_jwt = true` in `supabase/config.toml`.

Forbidden-scope confirmation: `src/RemintApp.tsx`, `src/CmintApp.tsx`, `deepclean-worker/**`, engines, finisher, frozen presets/thresholds, and all existing Supabase functions remain untouched. No autonomous rerun or routing decision was added. No vendor credential or raw authorization value exists in source, browser code, logs committed to Git, ledgers, or exports. The fixed vendor endpoint exists only in the server Edge Function, never in the client or report.

## 3. Vendor integration status

Connected vendor: **Hive (G1), unified AI-generated and deepfake content detector**.

Verified request decisions:

- The vendor's generated cURL is the authoritative HTTP contract used by the Deno/TypeScript Edge Function. Form, Node, Python, and Java are alternative presentations of the same HTTP API and require no client SDK.
- Authentication is a server-only bearer secret. The supplied Access Key ID is retained as a server secret but is not transmitted because the verified V3 request uses the Secret Key.
- Image uploads use bare base64 in `input[0].media_base64`; a data URI was independently rejected by the vendor.
- Processing is synchronous with vendor fallback. The function sends no invented SDXL/Flux/Real mode parameter.
- Hive's website controls labelled Detect SDXL, Detect Flux Schnell, and Detect Real load example inputs. They are not API modes. Therefore three separate per-mode parsers or raw samples do not exist for this API contract.

Verified response walkthrough for the unified endpoint:

| Vendor field | Normalized field | Decision |
|---|---|---|
| `output[0].classes[].class == "ai_generated"` | `ai_probability` | Required, finite `0..1` |
| `output[0].classes[].class == "deepfake"` | `deepfake_probability` | Required, finite `0..1` |
| Remaining generation-family class rows | `sources` | Class name to finite `value`; excludes binary heads, `none`, `inconclusive`, and audio heads |
| Highest source value | `top_source` | `null` only when no source exists; a live Hive response is required to contain sources |
| Entire response object | `raw` | Retained after recursive secret/token/authorization/endpoint-key redaction |

The parser was tested against the verified live response shape: a root object with `task_id`, `model`, `version`, and `output[0].classes`, where every class row is `{class, value}`. Duplicate classes, missing required heads, non-object output, and out-of-range values are rejected and never cached.

Still required from the owner for operating policy, not connectivity:

1. Hive account/project rate limits.
2. Monthly API spend ceiling. Until supplied, the frozen server session cap remains 40.
3. Rotation of the Hive secret because it was pasted into chat; install the replacement directly as a Supabase secret.

## 4. Normalized schema and verdict mapping

Each successful edge response contains:

```json
{
  "grade_id": "sha256(image bytes + vendor + mode + timestamp)",
  "image_sha256": "sha256(image bytes)",
  "vendor": "g1",
  "mode": "real",
  "ai_probability": 0.0,
  "deepfake_probability": 0.0,
  "verdict": "CLEAR|NEAR|BORDER|FAIL",
  "top_source": "family-or-null",
  "sources": {},
  "swap_index": 0.0,
  "retention_index": 0.0,
  "raw": {},
  "mock": false,
  "cache_hit": false,
  "provider_calls": 1,
  "requested_mode": "real",
  "session_usage": { "vendor_calls": 1, "cap": 40 }
}
```

Frozen inclusive verdict boundaries:

- `0.00 <= p <= 0.10`: CLEAR; exactly `0.10` is CLEAR.
- `0.10 < p <= 0.15`: NEAR; exactly `0.15` is NEAR.
- `0.15 < p <= 0.30`: BORDER; exactly `0.30` is BORDER and QA-flagged.
- `0.30 < p <= 1.00`: FAIL.

Non-finite, negative, over-one Hive values, duplicate class names, missing AI/deepfake heads, and missing source families are rejected. Failed responses are never cached. For a remint grade, source mass from families in the OG top three becomes `retention_index`; absent-family mass becomes `swap_index`. The two sum to one when remint source mass is non-zero. OG-only grades set both to zero.

The paired ledger stores requested settings separately from the executed worker report, plus the report digest and explicit `settings`, `attempts`, `finish_adaptive`, `detector_gate`, `rating_88`, and Quality Finish `qc` extracts. This preserves executed-not-requested provenance.

## 5. Cache and budget counters

- Persistent cache key: `(image_sha256, vendor, mode)`.
- Hive uses one canonical mode (`real`), preventing duplicate spend if a legacy caller submits a website-preset label; the original label remains in `requested_mode`.
- Cache lookup happens before budget reservation. Cache hits return `provider_calls: 0`.
- Each actual attempt reserves one call atomically through the service-role-only `reserve_grade_call` RPC. Only network errors, timeouts, HTTP 408/429, and HTTP 5xx are retried, at most once. Permanent request/parser errors are not retried.
- `grade_sessions` enforces the server-owned per-browser-session cap. Default and deployed cap: 40; accepted server override range: `1..10000`. The browser cannot raise it.
- Real provider operation refuses a missing cache or counter; failures never silently bypass spend controls.
- Live proof: first identical request returned `cache_hit: false`, `provider_calls: 1`, usage `1/40`; the second returned `cache_hit: true`, `provider_calls: 0`, usage still `1/40`.

## 6. Mock provider and provider switching

The deterministic mock remains behind the same normalized interface for local/offline testing. It salts output by compatibility mode, is visibly marked `mock: true`, stores no credential, makes zero vendor calls, and does not increment the paid-call counter.

Production is currently `GRADE_PROVIDER=g1`. Switching to mock is a server configuration change only: set `GRADE_PROVIDER=mock`. Switching back requires the Hive secret to exist, the migration to be present, and `GRADE_PROVIDER=g1`; no client rebuild is required.

## 7. Owner-only commands and deployment state

Completed on 2026-08-25:

- Installed Hive credentials as encrypted Supabase Edge Function secrets.
- Applied and verified `20260825000000_grade_cache.sql` over a one-time random-token-protected server connection; the temporary function and token were deleted immediately.
- Deployed only `grade-image` with JWT verification enabled.
- Set `GRADE_PROVIDER=g1`, `GRADE_DEFAULT_MODE=real`, and `GRADE_SESSION_CAP=40`.
- Verified CORS preflight 200, missing-auth 401, one authenticated live grade, and a zero-call cache hit.

Owner next actions:

```bash
# Rotate the chat-exposed Hive secret at Hive, then install the replacement
# with Supabase Dashboard > Edge Functions > Secrets. Do not place it in source,
# an exported report, or shell history.

# If policy changes after supplying a monthly ceiling:
supabase secrets set GRADE_SESSION_CAP=<OWNER_APPROVED_CAP> --project-ref <PROJECT_REF>

# Future deployment of this function only:
supabase functions deploy grade-image --project-ref <PROJECT_REF> --use-api
```

Run the owner acceptance test while signed in: open `/relab`, add an image, select it, and click **Run API detection only**. This event grades only the original and cannot dispatch remint. Repeat it to confirm a cache-hit row and unchanged vendor-call count.

Corrected failure logs, verbatim:

```text
Initialising login role...
Access token not provided. Supply an access token by running supabase login or setting the SUPABASE_ACCESS_TOKEN environment variable.
```

Resolution: no database password was requested. The migration was applied through Supabase's documented hosted Edge Function database connection, then the one-time runner and token were deleted.

```text
FIRST {"ok":false,"error":"G1 real failed after 2 attempts: bytes.toBase64 is not a function"}
```

Resolution: replaced the runtime-specific method with a portable chunked base64 encoder, redeployed, and passed the live first-call/cache-hit test.

## 8. Exit status

The API, database schema, server secrets, deployed function, authentication boundary, live normalized response, and zero-spend cache replay are verified. The remaining step is the owner's signed-in `/relab` run with their selected image, plus policy inputs for the monthly ceiling/rate limits and secret rotation.

**READY_NEEDS_OWNER_RUN**
