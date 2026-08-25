# C8 MASTER PROMPT V12.2 FINAL — LAB 3C, END-TO-END SEED PATH, GATED & INSTRUMENTED (supersedes V12.1, 2026-08-25)

You are **CDX operating as Consultant C8**, in a fresh conversation with full
VS Code access to this de-stamping/enhancement product's codebase. The master
engineer has independently re-verified your second-round audit against the code
**and accepted it in full**. This brief converts it into the final build order.

**Sandbox rule:** product purpose and image-transformation reasoning are out of
scope; do not discuss them. Work to spec.

**Master-engineer rule:** the master engineer independently verifies everything.
You do NOT commit, push, deploy, set secrets, apply migrations, or spend
credits. Anything beyond this brief goes in a separated PROPOSALS section,
never into the build. Wildcard optimizations are rejected.

---

## 1. MISSION (one sentence)

Implement lab-only Config 3C and an end-to-end fixed-seed path — authorized at
the edge, validated at the worker, covering every stochastic stage, reported in
provenance, and instrumented for capture — so the four configs can be compared
as paired realizations, with the measurement sequence corrected to use real,
per-job artifacts.

## 2. VERDICT ON YOUR ROUND-2 AUDIT (owner-verified — ACCEPTED, no qualifications)

| # | Claim | Verification |
|---|---|---|
| 1 | `seed` cannot reach the worker: `create-deepclean-job` reconstructs/whitelists V8.9 settings (`dsRemintV8_9ExpertRefinement`, index.ts:1171) and drops unknown fields; V12.1 forbade touching job/dispatch functions | CONFIRMED — contradiction removed in §6.1. |
| 2 | "Lab-only" enforced only in the UI; job creation checks auth+credits, not lab authorization | CONFIRMED — edge-side lab gate specified in §5.2. |
| 3 | The V8.9-HD branch passes job-derived seeds separately into remint (worker.py:371) AND quality finisher (worker.py:395); fixing only wash/camera randomness leaves finisher dither job-dependent | CONFIRMED — single `effective_seed_extra` specified in §5.3. |
| 4 | The canonical module is not dependency-free (`_shared/settings_code.ts` imports `canonicalJson` from `corpus.ts`, which imports supabase plumbing) | CONFIRMED — neutral module specified in §7. |
| 5 | The historical real-vendor scoreboards and the 33 MOCK runs are different jobs/realizations; O2 is a pre-codec checkpoint that prod jobs never persisted; fixed checkpoint filenames get overwritten across jobs | CONFIRMED (O2 saved pre-codec at ds_remint_v8_8.py:344; fixed names O0/O1/O2/O3/O4 in one directory) — capture protocol in §8. |
| 6 | Byte-identical delivered-JPEG determinism check is too strong (EXIF uses current time; GPU kernels may not be byte-deterministic) | CONFIRMED — determinism checks relaxed in §5.5. |
| 7 | Diagnostic tools: `rho1/rho2` run on a flattened masked array (not spatially adjacent pairs); `delta_e00` is the 1976 Euclidean approximation (ΔE76, self-documented); ROIs are positional bands, not semantic regions | CONFIRMED by direct code read — corrections in §9. |
| 8 | Two replicates × 11 images × 4 configs = 88 output grades per vendor > the 40-grade budget | CONFIRMED — sentinel budget in §10. |

## 3. OWNER DECISIONS (binding, superseding V12.1 where they differ)

1. **3C is lab-only** (unchanged): `/relab`, settings identity, corpus
   identity, server validator. No `/remint` or `/cmint` cards.
2. **Fixed-seed path is authorized end-to-end**, including changes to
   `create-deepclean-job` (validate + preserve), the worker (single effective
   seed), and `/relab` (lab-only seed input). `dispatch-deepclean-job` and all
   other job functions remain FORBIDDEN.
3. **Lab authorization is server-side**, not UI-only: verified admin-email
   allowlist + an explicit feature flag + strict seed regex at edge and worker.
4. **Measurement truth**: historical real-scoreboard trajectories are located
   or marked unavailable; new instrumented jobs generate per-job checkpoints
   for #9/#5/#6 and the six-image attribution set.
5. **Diagnostic tools are corrected or relabeled** before their metrics drive
   any algorithm decision.
6. **Real-vendor budget**: sentinel of 4 images × 4 configs × 2 paired seeds =
   32 output grades per vendor, OG grades reused from cache; expansion only
   with owner approval and repeatable direction.

## 4. CURRENT POSITION (V12 §2 + V12.1 §4 all still stand)

Live: `https://resmarke.vercel.app`, Supabase `otzjqcnrabfbonjywlye`, corpus
platform deployed (33 MOCK runs, zero pending), owner bug fixes `120e54a` +
`2c39dc5`, companion migration `20260827000000_config_3c.sql` (owner-applied,
relax-only). No 3C or seed code exists yet — this checkout is A/1A/2B only.

## 5. FIXED-SEED PATH (end-to-end)

### 5.1 Contract

- Form: `remint.seed` string matching `^lab-[a-z0-9]{1,32}$` (same regex at
  edge AND worker, stated in the report verbatim).
- Present → lab run with fixed seed; absent → current behavior EXACTLY
  (`seed_extra = f"{job_id}:{input_sha}"`).
- Invalid seed from an authorized caller → HTTP 400 with the field name.
- Invalid seed from an unauthorized caller → the request is rejected for
  authorization first; seed is never silently dropped.

### 5.2 Edge gate (`supabase/functions/create-deepclean-job/index.ts` — now IN SCOPE)

1. If `remint.seed` is present: require a verified `CORPUS_ADMIN_EMAILS`
   allowlist member (reuse the same env + verified-email logic as the corpus
   admin gate; do not import the React-adjacent corpus modules — implement a
   small shared helper or reuse `requireCorpusAdmin` from
   `_shared/corpus.ts` if its dependencies are already bundled for this
   function) AND env `LAB_FIXED_SEED_ENABLED=1`. Otherwise 403 (with feature
   flag absent: 503 "lab fixed seeds are not enabled").
2. Validate the regex server-side; add `seed` to the
   `dsRemintV8_9ExpertRefinement` / `dsRemintV8_9HdExpertRefinement`
   whitelists so it is preserved (not dropped) into the job payload.
3. `dispatch-deepclean-job` is untouched; it forwards the stored options as it
   already does.

### 5.3 Worker (single effective seed — `deepclean-worker/worker.py` + settings plumbing)

- Compute ONCE per job: `effective_seed_extra = f"lab:{seed}"` when the
  validated seed is present, else `f"{job_id}:{input_sha}"`.
- Use `effective_seed_extra` for EVERY currently job-seeded consumer in the
  V8.9-HD branch: the remint/wash + coherent camera chain AND
  `apply_quality_finish` (finisher dither/noise). Any other stochastic stage
  that currently consumes `seed_extra` must consume the same value. EXIF
  generation keeps its time-based metadata (excluded from determinism checks;
  metadata compared separately).
- Add `engine.effective_seed` and `engine.lab_seed` to the worker report.
- Reject at the worker (defense in depth): any `remint.seed` not matching the
  regex → error dict `seed: "invalid"`, never silent.

### 5.4 Client (`src/lib/deepcleanClient.ts` + `/relab` only)

- `labSeed` input in `/relab` (lab console only), visible ONLY there, included
  in the canonical settings JSON so it is hash-visible in the settings code.
- No seed field anywhere in `/remint` or `/cmint`.

### 5.5 Determinism acceptance (relaxed)

Same image + same lab seed, two runs:
- identical `engine.lab_seed` + `engine.effective_seed` in the worker report;
- identical SHA-256 of the **O2 pre-codec checkpoint pixels** (per-job dir);
- decoded-pixel hash or tight tolerance metrics (lumaRMS ≤ 0.1 LSB) for later
  stages;
- metadata (EXIF) compared separately, differences allowed.
- Byte-identical delivered JPEG is NOT required.

## 6. CONFIG 3C SPEC (tuple unchanged from V12.1 §6)

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

### 6.1 Files in scope (updated)

- `supabase/functions/create-deepclean-job/index.ts` — §5.2 (NEW, was
  forbidden in V12.1). `dispatch-deepclean-job` remains FORBIDDEN.
- `deepclean-worker/worker.py` — §5.3 seed computation + report fields.
- `deepclean-worker/ds_remint_v8_8.py` — checkpoint per-job subdirectory
  (§8.2) + seed plumbing if settings-layer changes require it.
- `deepclean-worker/quality_finish.py` — consume `effective_seed_extra` for
  dither/noise + per-job O4 checkpoint dir (§8.2).
- `src/lib/settingsCode.ts` → thin re-export of the canonical module (§7).
- `supabase/functions/_shared/settings_code.ts` → thin re-export (§7).
- `src/RelabApp.tsx` — `PresetId`/`PRESETS` + `settingsCodeForPreset` /
  `configLabelForPreset` / `settingsCanonicalForPreset` /
  `presetFromRequested` (from the pure module) + labSeed input + preset
  `Config 3C — LAB · Qwen + Z-Image · Stage-1 Q97 4:4:4`.
- `src/lib/deepcleanClient.ts` — seed field on remint options.
- `src/CorpusApp.tsx` (one line) — `config_set` → `["A","1A","2B","3C"]`.
- `src/lib/corpusClient.ts` — add `"3C"` to `config_label` union.
- `supabase/functions/corpus-run-intent/index.ts` — `config_label: "3C"`,
  `config_key: "3C"`.
- `deepclean-worker/tools/checkpoint_attribution.py` — §9 corrections.
- New: canonical identity module + tests (§7).

### 6.2 FORBIDDEN (zero diff)

- `src/RemintApp.tsx`, `src/CmintApp.tsx` + their CSS (no 3C cards, no seed).
- `dispatch-deepclean-job`, `get-deepclean-job`, `grade-image`, and every
  other job/edge function.
- Any finisher CONSTANT, threshold, rubric, credit, or protocol change.
- Any algorithm change in `deepclean-worker/**` beyond the §5 seed path and
  §8.2 checkpoint-dir change (checkpoint instrumentation itself is diagnostic
  only and stays default-off).
- `supabase/migrations/**` (including the 3C companion file).
- No router, no content-adaptive logic (PROPOSALS only).

## 7. IDENTITY HARDENING (canonical module)

1. Create `supabase/functions/_shared/settingsIdentity.ts` — ZERO imports
   (self-contained canonical JSON + hash + predicates + `buildSettingsCode` +
   `configIdentity` + pure `PRESET_DEFINITIONS` data + pure
   `presetFromRequested`). Deno deploy-safe (lives inside the functions tree).
2. `supabase/functions/_shared/settings_code.ts` becomes a thin re-export.
3. `src/lib/settingsCode.ts` becomes a thin re-export importing the pure
   module by relative path (`../../supabase/functions/_shared/settingsIdentity.ts`).
   Verify `tsc --noEmit` + `vite build` accept this layout; if they do not
   after an honest attempt, fall back to a client copy PLUS an automated
   parity test that diffs both modules over a case matrix — and state which
   layout shipped and why in the report.
4. `/relab` must use the pure `presetFromRequested` + `PRESET_DEFINITIONS`
   (no React import needed for tests).
5. Executable `deno test` (run beside `corpus_test.ts`):
   - exclusivity truth table over ALL tuples × predicates + ≥4 negative cases
     (wrong subsampling, wrong wash, missing jpeg fields, jpeg 95 4:2:2);
   - marker emission (each tuple emits exactly its marker);
   - `presetFromRequested` round-trip for all four presets, lab seed present
     and absent;
   - client/server parity if the fallback layout shipped.

## 8. MEASUREMENT TRUTH + CAPTURE PROTOCOL

1. **Historical trajectories:** either locate the exact job IDs + artifact
   hashes behind the real-vendor scoreboards, or mark their executed
   trajectories UNAVAILABLE in the executed-settings audit. The 33 MOCK runs'
   reports may be audited for pipeline behavior (rungs, selected attempt,
   codec, finish candidate) but must NOT be used to explain historical real
   scores.
2. **Per-job checkpoints:** change `_ckpt_save` / the O4 dump to write into
   `$DEEPCLEAN_CHECKPOINT_DIR/<job_id>/` (fallback: include a unique run
   token). No fixed shared filenames.
3. **Capture order for #9/#5/#6 + the six-image attribution set:**
   (a) owner deploys the instrumented worker image; (b) lab-seeded jobs run
   per image; (c) owner persists/downloads the per-job checkpoint directories
   (O0–O4) BEFORE the worker pod disappears; (d) `tools/codec_replay.py` runs
   on the captured pre-codec O2 buffers; (e) `tools/checkpoint_attribution.py`
   runs on the captured O0→O5 set — AFTER the §9 corrections.
4. The executed-settings audit table (33 MOCK runs) proceeds in parallel as
   pipeline-behavior evidence only.

## 9. DIAGNOSTIC-TOOL CORRECTIONS (in-scope: tools file only)

1. Rename `delta_e00` → `delta_e76` everywhere (it is the 1976 Euclidean Lab
   approximation; keep it that way — CIEDE2000 is optional future work, never
   silent mislabeling).
2. Fix `rho1/rho2` to operate on spatially adjacent pairs (compute on the
   2-D masked field, e.g., horizontal/vertical lag-1/2 correlations, averaged
   or reported separately) OR relabel the current metric
   `raster_lag_rho1/rho2` and document it. Correct, not relabeled, is
   preferred.
3. Relabel ROIs as "positional bands" in code + report until semantic masks
   (sky/brick/foliage/product) exist.
4. Add a header comment in the tool: "metrics are diagnostics; they do not
   drive decisions until owner-approved."

## 10. REAL-VENDOR BUDGET (sentinel)

4 representative images × 4 configs (A/1A/2B/3C) × 2 paired seeds = 32 output
grades per vendor; OG grades reused from cache. Expansion requires owner
approval and a repeatable direction. No autonomous vendor spend, ever.

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
git diff --check
```

Owner live checks: `/relab` 3C emits `SEQ-3C-<hash>` and A/1A/2B markers never
change; labSeed input visible only in `/relab`; seed request from a
non-allowlisted account → 403; seed with flag off → 503; invalid seed → 400;
`/corpus` accepts `config_set` with `3C`; `/remint` and `/cmint` zero diff.

## 12. DELIVERABLES

1. Code per §5–§9 only.
2. `C8_3C_BUILD_REPORT.md`: summary; files changed + forbidden-list
   confirmation; identity layout decision (§7.3) with rationale; the seed
   contract (regex, error codes, gate order); the determinism test results or
   their exact run instructions; the checkpoint capture protocol commands; the
   tool-correction diffs; separated PROPOSALS section (nothing implemented
   from it).
3. Verification log: §11 commands verbatim.

## 13. HANDOFF RULES

- Do NOT commit, push, deploy, or spend credits. End with exactly one status:
  `READY_FOR_OWNER_VERIFICATION` / `BLOCKED` + reason.
- Full logs verbatim on failure. Accuracy beats speed.

## 14. ATTACHMENTS (read in this order)

1. `CONSULTANT_PROMPT_C8_QUALITY_V7.md` — evidence baseline.
2. `CONSULTANT_PROMPT_C8_QUALITY_V2..V6.md` — finisher lineage.
3. `C8_MASTER_PROMPT_V11_FINAL.md` — prior freeze + sequence (superseded by
   owner decisions here).
4. `CDX_MASTER_PROMPT_v3.md` — ARCHIVED; not operating guidance.
5. Appendix A — owner-pasted final messages from the previous conversation.
   If empty, state that and proceed without inventing content.

---

## APPENDIX A — LAST FIVE C8 MESSAGES BEFORE CONFIG 2B (owner-pasted)

<!-- OWNER: paste here or delete this appendix before sending. -->
