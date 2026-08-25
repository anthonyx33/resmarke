# C8 3C Build Report

Date: 2026-08-25  
Build order: `C8_MASTER_PROMPT_V12_3_FINAL.md`  
Status: implementation complete; no commit, push, deployment, secret change, migration, or vendor spend performed.

## 1. Summary

Implemented the V12.3 laboratory comparison surface:

- Config 3C exists only in `/relab`, settings identity, and corpus identity.
- `/relab` has an optional hash-visible `labSeed` control; `/remint` and `/cmint` have no seed or 3C changes.
- `create-deepclean-job` enforces the fixed-seed gate before credit/job mutations and preserves the seed through both V8.9 whitelists.
- The worker validates the seed again, computes one effective seed, and uses it across V8.9 wash/camera, every HD finisher candidate, and finalization.
- Checkpoints are lab-seed-only, explicitly per-job, manifest-complete O0–O5, and pixel-hashed. O5 is decoded from the delivered JPEG.
- Identity is defined by one dependency-free module shared by Vite and Deno.
- Attribution diagnostics now report ΔE76, genuine two-dimensional directional spatial correlation, and positional bands. A deterministic CPU-only harness locks these contracts.

No grading or detector-vendor request was made. The approved pilot remains 32 output grades plus four fresh OG grades (36 total, one G1 vendor) and requires owner authorization before execution.

## 2. Files changed

Product and identity:

- `src/RelabApp.tsx` — four shared presets, lab-seed input, canonical identity use.
- `src/CorpusApp.tsx` — experiment `config_set` is `A/1A/2B/3C`.
- `src/lib/deepcleanClient.ts` — optional remint seed type and V8.9/V8.9-HD serialization.
- `src/lib/corpusClient.ts` — 3C label unions.
- `src/lib/settingsCode.ts` — thin re-export only.
- `supabase/functions/_shared/settingsIdentity.ts` — new zero-import canonical identity module.
- `supabase/functions/_shared/settings_code.ts` — thin re-export only.
- `supabase/functions/_shared/settings_identity_test.ts` — new identity/exclusivity/golden suite.
- `supabase/functions/_shared/corpus_test.ts` — preset-derived full goldens including 3C.
- `supabase/functions/corpus-run-intent/index.ts` — type-safe canonical cast; runtime 3C identity comes from the shared module.

Seed gate:

- `supabase/functions/_shared/lab_seed.ts` — new dependency-free allowlist/flag/regex gate and typed HTTP error.
- `supabase/functions/_shared/lab_seed_test.ts` — new gate-order and no-mutation-order tests.
- `supabase/functions/create-deepclean-job/index.ts` — pre-mutation gate, typed status propagation, V8.9 seed preservation, and pre-existing profile/null-fallback type declarations required by the mandated `deno check`.

Worker, capture, diagnostics:

- `deepclean-worker/worker.py` — effective seed, worker defense, explicit capture routing, chosen-candidate O4, O5 writer, manifest/report fields.
- `deepclean-worker/ds_remint_v8_8.py` — explicit checkpoint-directory argument and O0–O3 writes.
- `deepclean-worker/quality_finish.py` — effective seed consumption already existed via `seed_extra`; added explicit checkpoint-directory argument and O4 write.
- `deepclean-worker/tools/checkpoint_capture.py` — new shared path/write/pixel-hash/manifest/O2-determinism helper. It is under `tools/`, which the existing Dockerfile already copies to `/app/tools`.
- `deepclean-worker/tools/checkpoint_attribution.py` — ΔE76, directional 2-D rho, positional-band labels.
- `deepclean-worker/tools/codec_replay.py` — corresponding ΔE76 key/label migration so the old name does not survive elsewhere.
- `deepclean-worker/tools/test_checkpoint_diagnostics.py` — new deterministic CPU-only harness.
- `C8_3C_BUILD_REPORT.md` — this report.

## 3. Forbidden-list confirmation

`git diff` is empty for all of the following:

- `src/RemintApp.tsx`, `src/CmintApp.tsx`, and all CSS files.
- `supabase/functions/dispatch-deepclean-job/**`.
- `supabase/functions/get-deepclean-job/**`.
- `supabase/functions/grade-image/**`.
- `supabase/migrations/**`.
- All other job/edge functions except the explicitly in-scope `create-deepclean-job` and `corpus-run-intent` files.

No finisher constant, threshold, rubric, credit amount, grading protocol, router, transformation algorithm, or content-adaptive behavior changed. The untracked user directory `IMG-REMINT-v1/` was not touched.

## 4. Identity layout and goldens

The preferred layout shipped successfully: browser and server both execute `supabase/functions/_shared/settingsIdentity.ts`. The module has zero imports. Both former implementations are one-line re-exports; no fallback client copy or parity shim was required. `npx tsc`, Vite, and Deno all accept the cross-tree import.

Detection predicates consistently exclude `iphoneExif`, `metadataMode`, and `seed`. Canonical hashing includes every supplied field, including those three fields. Config 1A explicitly requires the default codec, so 3C cannot collide with it.

| Preset | Exact unseeded settings code | Result |
|---|---|---|
| A | `SEQ-CFA-dtbnbygm5iao` | reproduced byte-for-byte |
| 1A | `SEQ-1A-3lzgvffda5xf` | reproduced byte-for-byte |
| 2B | `SEQ-2B-zzz2dudlbywp` | reproduced byte-for-byte |
| 3C | `SEQ-3C-brgbola74zqg` | new frozen golden |

The identity suite covers all four tuples against all four predicates, five negative tuples, exact marker emission, and preset reconstruction with the lab seed present and absent.

## 5. Fixed-seed contract

The edge and worker both use the exact pattern `^lab-[a-z0-9]{1,32}$`. The seed is returned and persisted verbatim; it is never trimmed or rewritten.

Edge order:

1. Existing authentication completes.
2. An absent seed returns immediately to the existing production path without reading any lab env.
3. A present seed requires a confirmed user email in `CORPUS_ADMIN_EMAILS`; otherwise 403.
4. `LAB_FIXED_SEED_ENABLED` must be the literal string `1`; otherwise 503 with `lab fixed seeds are not enabled`.
5. The exact regex is applied; otherwise 400 naming `remint.seed`.
6. The seed is preserved in `dsRemintV8_9ExpertRefinement`; the HD composer inherits that normalized value.
7. Only after the gate does the function read the credit profile, normalize settings, reserve credit, write the ledger, and create the job.

The blanket catch now maps `LabSeedHttpError` to 403/503/400 and retains 500 for unrelated failures.

Worker contract:

- Present valid seed: `effective_seed_extra = f"lab:{seed}"`.
- Absent seed: `effective_seed_extra = f"{job_id}:{input_sha}"` (the existing V8.9/HD behavior).
- The same effective value reaches stage-one wash/camera, every finisher attempt, and finalization. Rung indices remain internal suffix inputs to the existing seed derivation.
- Success report: `report.engine.effective_seed` and `report.engine.lab_seed` (`null` when absent).
- Invalid worker-side seed: failed result and failed-job report include `seed: "invalid"`; processing never silently continues.

Rejected-request proof is executable. The source-order test asserts that the gate call precedes the first creator-profile access and each credit, ledger, and job mutation. It passed. No live database request was made because V12.3 forbids deployment/secret use and assigns live row verification to the owner.

Rejection-test results:

```text
running 3 tests from ./supabase/functions/_shared/lab_seed_test.ts
absent lab seed takes the unchanged path without requiring lab config ... ok
lab seed gate order and typed statuses are exact ... ok
rejection gate is before every credit ledger and job mutation ... ok

ok | 3 passed | 0 failed
```

## 6. Determinism contract

`compare_o2_determinism` implements the V12.3 rule over decoded RGB pixels:

- exact pixel SHA-256 match → `kind: "exact"`, pass;
- same-hardware RMS ≤ 0.1 LSB and maximum absolute error ≤ 1 LSB → `kind: "tolerated"`, pass;
- size mismatch, larger error, or a tolerance request not marked same-hardware → `kind: "failed"`, stop before grading.

Checkpoint pixel hashes include width, height, and decoded RGB bytes; PNG/JPEG metadata is excluded. EXIF must be compared separately and byte-identical delivered JPEGs are not required. The deterministic harness exercises exact, tolerated, failed, and non-same-hardware cases.

## 7. Checkpoint capture contract

Capture behavior:

- A validated lab seed is necessary. With no lab seed, `DEEPCLEAN_CHECKPOINT_DIR` and the durable-attestation flag are ignored, the directory helper creates nothing, each checkpoint save is a no-op, and the report is `{status: "off", files: [], errors: []}`.
- A lab job additionally requires `DEEPCLEAN_CHECKPOINT_DURABLE=1`. Without this explicit operator attestation, the report is `error` and no ambiguous local path is used.
- The base comes from `DEEPCLEAN_CHECKPOINT_DIR`; every write target is explicitly passed as `<base>/<job_id>/`. No process-global environment variable is mutated.
- Stage one writes O0–O3. Adaptive finisher candidates write into isolated temporary subdirectories under the job directory; only the chosen candidate's O4 is copied to the root, then candidate subdirectories are removed.
- After `finalize_output` produces the delivered JPEG, the worker decodes it and writes `O5_final.png`.
- Manifest shape is exactly `{status: "captured"|"off"|"error", files: [{name, sha256}], errors: []}`. Missing or unreadable O0–O5 makes status `error`; complete capture produces files in O0–O5 order.

Durability and retrieval:

The repository's RunPod contract mounts its private persistent network volume at `/runpod-volume` (`deepclean-worker/Dockerfile`, `README.md`, and startup checks). The owner should configure a private subdirectory such as `/runpod-volume/deepclean-checkpoints`, verify it is retrievable from a second pod/dashboard before running the pilot, and only then set the durable-attestation flag. This checkout has no access to the deployed environment, and no environment value was set during this build.

Retention/deletion rule: after each lab run, the owner retrieves the per-job directory, archives the manifest plus analysis results, and then deletes that per-job directory. The worker deliberately does not delete a captured directory before retrieval. No customer-content capture without a validated lab seed is possible through this path.

## 8. Diagnostic corrections

| Before | After |
|---|---|
| `_delta_e00` / `delta_e00` / `dE00` while computing Euclidean Lab distance | `_delta_e76` / `delta_e76` / `dE76` everywhere |
| correlation on a flattened masked array | horizontal and vertical masked 2-D pairs at lag 1 and 2; directional values plus averages |
| fixed locations described as ROIs | `POSITIONAL_BANDS` and `positional_bands`; explicitly non-semantic |
| diagnostic authority implicit | header states metrics do not drive decisions until owner-approved |

The old ΔE00 name appears only as the harness's negative assertion that the old key is absent.

Python harness result, verbatim:

```text
PASS test_directional_spatial_correlation
PASS test_iid_like_field_is_near_zero
PASS test_delta_e76_key_migration
PASS test_per_job_checkpoint_isolation
PASS test_manifest_completeness_requires_o5
PASS test_capture_gate_without_lab_seed_writes_nothing
PASS test_o2_exact_and_same_hardware_tolerance_rules
PASS 7 deterministic diagnostic/checkpoint tests
```

Host dependency note: the first raw host invocation stopped before collection because `/usr/bin/python3` did not have Pillow, although `Pillow>=10,<13` is already declared in `deepclean-worker/requirements.txt`:

```text
Traceback (most recent call last):
  File "/Users/a/Documents/NOSYNF/deepclean-worker/tools/test_checkpoint_diagnostics.py", line 10, in <module>
    from PIL import Image
ModuleNotFoundError: No module named 'PIL'
```

No global package was installed. Pillow 11.3.0 was installed into `/tmp/c8-pydeps.P4LS7j` only, and the unchanged harness passed with that temporary target on `PYTHONPATH`. In a worker/developer environment installed from `deepclean-worker/requirements.txt`, the specified plain `python3` command is the equivalent invocation.

## 9. Verification log

Final commands, verbatim:

```text
npx tsc --noEmit
npm run build
deno check supabase/functions/_shared/settingsIdentity.ts
deno check supabase/functions/_shared/settings_code.ts
deno check supabase/functions/corpus-run-intent/index.ts
deno check supabase/functions/create-deepclean-job/index.ts
deno test supabase/functions/_shared/corpus_test.ts
deno test supabase/functions/_shared/settings_identity_test.ts
deno test --allow-read supabase/functions/_shared/lab_seed_test.ts
PYTHONPATH=/tmp/c8-pydeps.P4LS7j python3 deepclean-worker/tools/test_checkpoint_diagnostics.py
git diff --check
```

Results:

```text
npx tsc --noEmit                                      PASS (no output)
npm run build                                         PASS (1794 modules transformed)
deno check settingsIdentity.ts                        PASS
deno check settings_code.ts                           PASS
deno check corpus-run-intent/index.ts                 PASS
deno check create-deepclean-job/index.ts              PASS
deno test corpus_test.ts                              PASS (4 passed, 0 failed)
deno test settings_identity_test.ts                   PASS (4 passed, 0 failed)
deno test --allow-read lab_seed_test.ts               PASS (3 passed, 0 failed)
python diagnostic/checkpoint harness                  PASS (7 passed)
git diff --check                                      PASS (no output)
```

Owner-only live checks remain intentionally unexecuted: actual 403/503/400 HTTP requests and database no-write inspection, deployed `/relab` visibility/marker checks, corpus 3C acceptance, private-volume retrieval, two-run O2 determinism on the same worker hardware, and all vendor grading.

## 10. PROPOSALS

None. No proposal or wildcard optimization was implemented.

READY_FOR_OWNER_VERIFICATION
