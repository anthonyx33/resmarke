# C8 MASTER PROMPT V12.3 FINAL — BUILD-READY: LAB 3C, GATED FIXED-SEED, CAPTURE + DIAGNOSTIC CONTRACTS (supersedes V12.2, 2026-08-25)

You are **CDX operating as Consultant C8**, in a fresh conversation with full
VS Code access to this de-stamping/enhancement product's codebase. The master
engineer re-verified your round-3 audit against the code and **accepted every
point**. This brief is the final build order. After these amendments, no
further architectural redesign is expected — build to this spec.

**Sandbox rule:** product purpose and image-transformation reasoning are out of
scope; do not discuss them. Work to spec.

**Master-engineer rule:** the master engineer independently verifies everything.
You do NOT commit, push, deploy, set secrets, apply migrations, or spend
credits. Anything beyond this brief goes in a separated PROPOSALS section,
never into the build. Wildcard optimizations are rejected.

---

## 1. MISSION (one sentence)

Implement lab-only Config 3C and a gated end-to-end fixed-seed path with
authorized, manifest-complete checkpoint capture and corrected, test-locked
diagnostics, so the four configs can be compared as paired realizations inside
a single-vendor 36-grade pilot that fits the frozen 40-grade budget.

## 2. VERDICT ON YOUR ROUND-3 AUDIT (owner-verified — ACCEPTED, no qualifications)

| # | Claim | Verification |
|---|---|---|
| 1 | Budget contradiction: V11's ≤40 grades is a TOTAL, while V12.2's "32 per vendor" becomes 64–72 across two vendors; and the grade cache identity is only `(image_sha256, vendor, mode)` — no detector model/version — so old OG grades cannot be safely reused without exact detector-identity proof | CONFIRMED (migration line 18: `primary key (image_sha256, vendor, mode)`). Budget fixed in §10. |
| 2 | Checkpoint capture is env-gated only — it would persist ordinary customer images; per-job dir must be a function argument, not a mutated process-global env; there is no O5 writer although `checkpoint_attribution.py` expects `O5_final.png` (tool line 52) | CONFIRMED (only O0–O4 writers exist; O0/O1/O2/O3 in `ds_remint_v8_8.py`, O4 in `quality_finish.py`). Capture contract in §8. |
| 3 | `create-deepclean-job` converts every thrown exception into HTTP 500 (index.ts:339-342); reusing `requireCorpusAdmin` alone will not produce 403/503 | CONFIRMED. Structured error contract in §5. |
| 4 | Determinism needs exact-or-tolerance rules; Python diagnostics need a deterministic test harness | CONFIRMED. §5.5 + §9. |
| 5 | Golden values must be full settings-code values, not merely unchanged prefixes | CONFIRMED. §7.5. |

## 3. OWNER DECISIONS (binding, superseding earlier briefs where they differ)

1. **3C is lab-only** (unchanged): `/relab`, settings identity, corpus
   identity, server validator. No `/remint` or `/cmint` cards.
2. **Fixed-seed path is authorized end-to-end**: `create-deepclean-job`
   (validate + preserve + structured errors), worker (single effective seed +
   O5 writer + capture contract), `/relab` (lab-only seed input).
   `dispatch-deepclean-job` and all other job/edge functions remain FORBIDDEN.
3. **Lab authorization is server-side** with exact gate order (§5.2).
4. **Capture is lab-only** — never for normal jobs — with a per-job manifest,
   durable retrieval, retention, and an O5 writer (§8).
5. **Budget: single-vendor pilot** — 4 images × 4 configs × 2 paired seeds =
   32 output grades + 4 fresh OG grades = 36 total (≤ the frozen 40).
   Cross-vendor validation requires separate owner approval (§10).
6. **Diagnostics are corrected AND test-locked** before any metric drives a
   decision (§9).

## 4. CURRENT POSITION (V12 §2 + V12.1 §4 + V12.2 §4 all still stand)

Live: `https://resmarke.vercel.app`, Supabase `otzjqcnrabfbonjywlye`, corpus
platform deployed (33 MOCK runs, zero pending), owner bug fixes `120e54a` +
`2c39dc5`, companion migration `20260827000000_config_3c.sql` (owner-applied,
relax-only). No 3C or seed code exists yet — this checkout is A/1A/2B only.

## 5. FIXED-SEED PATH (end-to-end)

### 5.1 Contract

- Form: `remint.seed` string matching `^lab-[a-z0-9]{1,32}$` (same regex at
  edge AND worker, verbatim in the report).
- Present → lab run with fixed seed; absent → current behavior EXACTLY
  (`seed_extra = f"{job_id}:{input_sha}"`).
- Seed is never silently dropped, never normalized into something else.

### 5.2 Edge gate + structured errors (`create-deepclean-job/index.ts` — IN SCOPE)

**Gate order (exact, sequential):**
1. Authenticate (existing path).
2. Seed absent → the unchanged production path (step 7 onward as today).
3. Seed present → verified `CORPUS_ADMIN_EMAILS` allowlist member (verified
   email, same env as the corpus admin gate) → else **403**.
4. `LAB_FIXED_SEED_ENABLED` env configured/enabled → else **503**
   "lab fixed seeds are not enabled".
5. Validate `^lab-[a-z0-9]{1,32}$` → else **400** with the field name.
6. Normalize/persist the seed into the V8.9 / V8.9-HD expert refinement
   whitelists (`dsRemintV8_9ExpertRefinement` /
   `dsRemintV8_9HdExpertRefinement`).
7. Only NOW: reserve credits and create the job row.

**Error propagation (fixes the blanket 500 at index.ts:339):** thrown
`CorpusHttpError`-style typed errors must map to their status codes (403/503/
400) instead of 500. Do not reuse `requireCorpusAdmin` from `_shared/corpus.ts`
if its dependencies pull in corpus plumbing — implement a small shared
allowlist helper with the same env source and document it.

**Rejection tests (executable, owner-runnable):** a rejected seed request
creates NO job row, reserves NO credit, and writes NO ledger row. Prove it in
the report (test list + results).

### 5.3 Worker (single effective seed — `deepclean-worker/worker.py`)

- Compute ONCE per job: `effective_seed_extra = f"lab:{seed}"` when the
  validated seed is present, else `f"{job_id}:{input_sha}"`.
- Use it for EVERY currently job-seeded consumer in the V8.9-HD branch: the
  remint/wash + coherent camera chain AND `apply_quality_finish` (dither/noise).
  Any other stochastic stage that consumes `seed_extra` consumes the same value.
  EXIF stays time-based (excluded from determinism checks; compared separately).
- Report fields: `engine.effective_seed` + `engine.lab_seed` (null when absent).
- Defense in depth: invalid `remint.seed` at the worker → error dict
  `seed: "invalid"`, never silent.

### 5.4 Client (`src/lib/deepcleanClient.ts` + `/relab` only)

- `labSeed` input in `/relab` only; included in the canonical settings JSON
  (hash-visible in the settings code). No seed field in `/remint` or `/cmint`.

### 5.5 Determinism rules (exact-or-tolerance)

Same image + same lab seed, two runs on the same hardware:
- identical `engine.lab_seed` + `engine.effective_seed`;
- **preferred pass:** exact SHA-256 equality of the O2 pre-codec checkpoint
  pixels;
- **tolerated pass (same hardware only):** O2 RMS ≤ 0.1 LSB AND max absolute
  pixel error ≤ 1 LSB;
- otherwise: the paired-control assumption FAILS — stop and investigate, do
  not proceed to grading;
- metadata (EXIF) compared separately, differences allowed;
- byte-identical delivered JPEG is NOT required.

## 6. CONFIG 3C SPEC (tuple unchanged)

```
mode: sequence
remint:
  engineMode: "adaptive"
  washModel: "qwen+zimage"
  strength: "deep"
  jpegQuality: 97
  jpegSubsampling: "4:4:4"
  iphoneExif: true
  metadataMode: "device"
finish:
  preset: "strong"
  scale: null
  finishMode: "adaptive"
  materialClean: true
  overrides: { dither: 1, smoothness: 1.25, sharpen: 1 }
```

Settings-code identity: **`SEQ-3C-<hash>`**, detection-relevant tuple only
(`iphoneExif`/`metadataMode` excluded consistently across all predicates).

### 6.1 Files in scope (final list)

- `supabase/functions/create-deepclean-job/index.ts` — §5.2 (structured
  errors + gate + whitelist).
- `deepclean-worker/worker.py` — §5.3 + §8 (effective seed, O5 hook,
  checkpoint manifest).
- `deepclean-worker/ds_remint_v8_8.py` — per-job checkpoint dir (§8.2) + O2
  capture gating.
- `deepclean-worker/quality_finish.py` — `effective_seed_extra` consumption +
  per-job O4 dir (§8.2).
- `src/lib/settingsCode.ts` → thin re-export of the canonical module (§7).
- `supabase/functions/_shared/settings_code.ts` → thin re-export (§7).
- `supabase/functions/_shared/settingsIdentity.ts` — NEW canonical module (§7).
- `src/RelabApp.tsx` — presets + pure `presetFromRequested` +
  `Config 3C — LAB · Qwen + Z-Image · Stage-1 Q97 4:4:4` + labSeed input.
- `src/lib/deepcleanClient.ts` — seed field on remint options.
- `src/CorpusApp.tsx` (one line) — `config_set` → `["A","1A","2B","3C"]`.
- `src/lib/corpusClient.ts` — add `"3C"` to `config_label` union.
- `supabase/functions/corpus-run-intent/index.ts` — `config_label: "3C"`,
  `config_key: "3C"`.
- `deepclean-worker/tools/checkpoint_attribution.py` — §9 corrections.
- NEW: Python diagnostic test harness (§9).

### 6.2 FORBIDDEN (zero diff)

- `src/RemintApp.tsx`, `src/CmintApp.tsx` + CSS (no 3C cards, no seed).
- `dispatch-deepclean-job`, `get-deepclean-job`, `grade-image`, and every
  other job/edge function.
- Any finisher CONSTANT, threshold, rubric, credit, or protocol change.
- Any algorithm change in `deepclean-worker/**` beyond §5.3 and §8.
- `supabase/migrations/**` (including the 3C companion file).
- No router, no content-adaptive logic (PROPOSALS only).

## 7. IDENTITY HARDENING (canonical module + full goldens)

1. `supabase/functions/_shared/settingsIdentity.ts` — ZERO imports
   (self-contained canonical JSON + hash + predicates + `buildSettingsCode` +
   `configIdentity` + pure `PRESET_DEFINITIONS` + pure `presetFromRequested`).
   Deno-deploy-safe (inside the functions tree).
2. `supabase/functions/_shared/settings_code.ts` and
   `src/lib/settingsCode.ts` become thin re-exports of it. If Vite/tsc reject
   the cross-tree import after an honest attempt, fall back to a client copy
   PLUS an automated parity test; state the decision in the report.
3. `/relab` uses the pure `presetFromRequested` + `PRESET_DEFINITIONS`.
4. Executable `deno test` identity suite:
   - exclusivity truth table over ALL tuples × predicates + ≥4 negative cases
     (wrong subsampling, wrong wash, missing jpeg fields, jpeg 95 4:2:2);
   - marker emission (each tuple emits exactly its marker);
   - `presetFromRequested` round-trip for all four presets, lab seed present
     and absent;
   - client/server parity if the fallback layout shipped.
5. **Full-value goldens (not prefixes):** the identity module MUST reproduce,
   byte-for-byte, the shipped settings codes:
   `SEQ-CFA-dtbnbygm5iao`, `SEQ-1A-3lzgvffda5xf`, `SEQ-2B-zzz2dudlbywp`
   for their exact tuples (construct the tuples from the preset definitions —
   the live codes above are the regression gate; if the module reproduces
   them, it is compatible with the shipped exports). Add the 3C golden once
   produced. Keep `corpus_test.ts` existing goldens green.

## 8. CHECKPOINT CAPTURE CONTRACT (lab-only, manifest, O5)

1. **Capture gate:** checkpoint writing happens ONLY when a validated,
   authorized lab seed is present for the job. Normal production jobs write
   nothing even if `DEEPCLEAN_CHECKPOINT_DIR` is set.
2. **Per-job directory as an argument:** the capture directory is
   `<base>/<job_id>/` passed explicitly through the pipeline (function
   arguments) — never by mutating a process-global env var mid-run.
3. **Durable retrieval:** confirm (and document in the report) that the
   configured base is on private durable storage or a network volume the
   owner can retrieve from before the worker pod disappears.
4. **O5 writer (NEW):** after the delivered JPEG is produced, decode it and
   write `O5_final.png` into the same per-job directory, so O0→O5 attribution
   is actually runnable.
5. **Manifest:** the worker report gains a `checkpoints` block:
   `{ status: "captured"|"off"|"error", files: [{name, sha256}], errors: [] }`
   — every expected checkpoint O0..O5 with its pixel hash, or the capture
   error. The owner verifies manifest completeness before running attribution.
6. **Retention/deletion:** default rule (stated in the report): the owner
   archives the manifest + analysis results, then deletes the per-job
   checkpoint directories; no checkpoint data is retained beyond the owner's
   archive. No capture of customer content without a lab seed, ever.

## 9. DIAGNOSTIC CORRECTIONS + TEST-LOCK (tools file + NEW Python harness)

1. Rename `delta_e00` → `delta_e76` everywhere (1976 Euclidean Lab
   approximation; CIEDE2000 is optional future work, never silent mislabeling).
2. Fix `rho1/rho2` to spatially adjacent pairs on the 2-D masked field
   (horizontal/vertical lag-1/2, reported separately or averaged) — correct,
   not relabeled.
3. Relabel ROIs "positional bands" until semantic masks exist.
4. Header comment: "metrics are diagnostics; they do not drive decisions
   until owner-approved."
5. **Deterministic Python test harness** (new file under
   `deepclean-worker/tools/`, runnable with plain Python 3, no GPU):
   - synthetic horizontal/vertical spatially-correlated fields → high
     directional rho, correct lag-1 vs lag-2 ordering;
   - IID noise field → near-zero spatial correlation;
   - `delta_e76` key/name migration check (old key absent, new key present);
   - per-job checkpoint isolation (two simulated jobs do not overwrite);
   - O0–O5 manifest completeness (missing O5 → reported as error);
   - checkpoint-capture gating (no lab seed → no files).
   All tests deterministic, no randomness in expected values.

## 10. BUDGET (single-vendor pilot, ≤40 total)

- **4 representative images × 4 configs (A/1A/2B/3C) × 2 paired seeds =
  32 output grades + 4 fresh OG grades = 36 total.** One vendor (G1) only.
- No cached OG reuse unless the exact detector identity (vendor, mode, model,
  version) is independently proven for the cache rows — the cache PK is only
  `(image_sha256, vendor, mode)`, so identity is NOT implied by a key hit.
  State per-row which cache rows were reused and the proof.
- Cross-vendor validation: separate owner approval, new budget.
- No autonomous vendor spend, ever.

## 11. ACCEPTANCE GATES (owner runs independently)

```text
npx tsc --noEmit
npm run build
deno check supabase/functions/_shared/settingsIdentity.ts
deno check supabase/functions/_shared/settings_code.ts
deno check supabase/functions/corpus-run-intent/index.ts
deno check supabase/functions/create-deepclean-job/index.ts
deno test supabase/functions/_shared/corpus_test.ts
deno test <your new identity tests>
python3 deepclean-worker/tools/<diagnostic_harness>.py
git diff --check
```

Owner live checks: `/relab` 3C emits `SEQ-3C-<hash>` and A/1A/2B markers never
change; labSeed input visible only in `/relab`; seed from non-allowlisted
account → 403; flag off → 503; invalid seed → 400; rejected requests create
no job/credit/ledger rows; `/corpus` accepts `config_set` with `3C`;
`/remint` and `/cmint` zero diff.

## 12. DELIVERABLES

1. Code per §5–§10 only.
2. `C8_3C_BUILD_REPORT.md`: summary; files changed + forbidden-list
   confirmation; identity layout decision; seed contract (regex, gate order,
   error codes); determinism rules implemented; capture contract implemented
   (manifest shape, O5 writer, gating proof); diagnostic corrections diff;
   Python harness results verbatim; golden-value reproduction table
   (A/1A/2B/3C); rejection-test results; separated PROPOSALS section (nothing
   implemented from it).
3. Verification log: §11 commands verbatim.

## 13. HANDOFF RULES

- Do NOT commit, push, deploy, or spend credits. End with exactly one status:
  `READY_FOR_OWNER_VERIFICATION` / `BLOCKED` + reason.
- Full logs verbatim on failure. Accuracy beats speed.

## 14. ATTACHMENTS (read in this order)

1. `CONSULTANT_PROMPT_C8_QUALITY_V7.md` — evidence baseline.
2. `CONSULTANT_PROMPT_C8_QUALITY_V2..V6.md` — finisher lineage.
3. `C8_MASTER_PROMPT_V11_FINAL.md` — prior freeze + budget (superseded by the
   owner decisions here).
4. `CDX_MASTER_PROMPT_v3.md` — ARCHIVED; not operating guidance.
5. Appendix A — owner-pasted final messages from the previous conversation.
   If empty, state that and proceed without inventing content.

---

## APPENDIX A — LAST FIVE C8 MESSAGES BEFORE CONFIG 2B (owner-pasted)

<!-- OWNER: paste here or delete this appendix before sending. -->
