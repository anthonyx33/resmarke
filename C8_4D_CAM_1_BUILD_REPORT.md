# C8 4D-CAM-1 Build Report

Date: 2026-08-26  
Builder: C8  
Base revision: `b71ed99d3fac2c13e5085c7c76ffd2b699467030`  
Status: **LOCAL BUILD AND PROOF GATES COMPLETE; EXTERNAL EXPERIMENT OWNER-PENDING**  
Design: `C8_4D_CAM_1_BUILD_BRIEF.md`  
Instruction: `C8_MASTER_PROMPT_4D_CAM_1_BUILD.md`

## 1. Result

The sealed 4D-CAM-1 build is implemented locally with one output-affecting variable: `optics_psf_scale`, absent/`1.00` for baseline B and exactly `0.50` for candidate C.

- The four frozen identities remain exactly A/1A/2B/3C; CAM-1 is exported separately and assembled only by `/relab` (`supabase/functions/_shared/settingsIdentity.ts:9-11,75-153`; `src/RelabApp.tsx:123-128`).
- CAM-1 is `CUSTOM` with `SEQ-CAM1-*`; invalid scales fail closed at the shared edge boundary and worker boundary (`settingsIdentity.ts:155-161,221-249`; `create-deepclean-job/index.ts:1197-1217`; `deepclean-worker/ds_remint_v8_8.py:116-148`).
- The scalar is applied after scene modulation and immediately before `_per_channel_psf`, with base, scene multiplier, scale, and effective radii reported (`deepclean-worker/coherent_camera.py:169-180,200-215`).
- Every camera call receives the same scalar, including balanced+light passes in the deep branch (`deepclean-worker/ds_remint_v8_8.py:442-489`).
- `OR_postresample.png` is captured before the camera through an independent auxiliary contract; the strict O0–O5 files are untouched (`ds_remint_v8_8.py:271-289`; `deepclean-worker/tools/auxiliary_checkpoints.py:1-64`).
- Fixed-rung replay measures `max(1-EATR, 1-HFTR_H1, 0)` on an identical lattice and rejects mismatched paired OR hashes (`deepclean-worker/tools/camera_only_replay.py:32-123`).

No quality-acceptance claim is made from the synthetic fixture. The 34-cell corpus round remains separate and owner-gated.

## 2. Exact changed-file audit

Tracked `git diff --numstat` against `b71ed99`:

| File | Added | Deleted | Purpose |
|---|---:|---:|---|
| `deepclean-worker/coherent_camera.py` | 27 | 4 | strict scalar, post-scene effective radii, reporting |
| `deepclean-worker/ds_remint_v8_8.py` | 52 | 3 | worker validation, all-rung pass-through, auxiliary OR capture |
| `src/RelabApp.tsx` | 24 | 7 | lab-only preset, locked seeds, strict CUSTOM/regrade path |
| `src/lib/deepcleanClient.ts` | 4 | 0 | V8.9/HD request serialization only |
| `supabase/functions/_shared/settingsIdentity.ts` | 61 | 5 | identity, separate lab preset, strict parser, CAM1 code |
| `supabase/functions/_shared/settings_identity_test.ts` | 54 | 2 | frozen and candidate goldens, round-trip, invalid boundary values |
| `supabase/functions/create-deepclean-job/index.ts` | 14 | 1 | fail-closed V8.9 normalization and HTTP 400 mapping |

New allowlisted worker tools:

| File | Lines | SHA-256 | Purpose |
|---|---:|---|---|
| `deepclean-worker/tools/auxiliary_checkpoints.py` | 64 | `5b9e89124ed2a0e01d084c8db4852146aeb9ed4d3786d3fa7336fbf24063be16` | auxiliary whitelist/writer/manifest |
| `deepclean-worker/tools/camera_only_replay.py` | 148 | `3cf1af5c4e87e17ae81940e21f90701cd2262df8b69ba5a200004801110d40f7` | OR-relative metrics and fixed-rung paired replay |
| `deepclean-worker/tools/test_4d_cam_1.py` | 412 | `fc619a748195dc4a7f95e2ffa5e336fc0a196255e287a37dc7ef2910b45fd9cf` | nine deterministic CPU proof tests |

Totals excluding this report: **860 additions, 22 deletions across 10 allowlisted files**. `git diff --check` passes.

Tracked pre/post hashes:

| File | Before | After |
|---|---|---|
| `coherent_camera.py` | `c0a900dd8528f5f2e4fd3b4a44f01b7256bf56f88d6bbb787c284fa97d2d80d0` | `7d83e896def0a58bcee6ea6f2fa5e7e5e42dc1adc5ed34317678f54b9267b183` |
| `ds_remint_v8_8.py` | `3382168f67b80de2ad91bd8331fc6e548f5928da73ae569f6ccf6fee4f92dea2` | `3439322c3826dbdc7e60784e5b2210ca3b85a20b3a5b0589ebdd41c332c64b01` |
| `RelabApp.tsx` | `7ee93a06c5e53ac1ae81b7518a2856765a066a321cc148da62ae072150ea4522` | `a2dd59cbac62295bbe678103716786086724cb6fadd5536404beaff7169f68e2` |
| `deepcleanClient.ts` | `2b5e0c55f6e029a65ef2a1fff50dd6700ef30366b6f3fb99cd7e3ae08a9f9546` | `e1db7dc8c004ea58be79b4f9e6a87dad550f7201dc83b2fdaaf5d9837e093ab2` |
| `settingsIdentity.ts` | `fc592a9f7e7cc52751a8f5a7bfdd14ee6d3d920d7672c6c91c224a81cb34c4c6` | `5003d4909a763344f190bbc7ca1725e52f10b9fa9129f441b90a3a8df9ab7d88` |
| `settings_identity_test.ts` | `abeca00a072b13e7160f7fc02538571c30faa1f625bd1cf45029ed676817adff` | `be4ab39b3ed609a126bb8734958667e5a05ff2dfcfbd8452e77d114135012448` |
| `create-deepclean-job/index.ts` | `825dd256562e190d03e56c54a0f927222871569e31ce3a03c7e05c585f8c4aaa` | `43a8fc5984c96da31a1b2dceedda7ad3c326f4441aff51546e3b4a3e8271ed0b` |

No tracked file outside this allowlist changed.

## 3. Identity and request proof

Four frozen seed-absent settings-code goldens before/after:

| Config | Before | After | Verdict |
|---|---|---|---|
| A | `SEQ-CFA-dtbnbygm5iao` | `SEQ-CFA-dtbnbygm5iao` | byte-identical |
| 1A | `SEQ-1A-3lzgvffda5xf` | `SEQ-1A-3lzgvffda5xf` | byte-identical |
| 2B | `SEQ-2B-zzz2dudlbywp` | `SEQ-2B-zzz2dudlbywp` | byte-identical |
| 3C | `SEQ-3C-brgbola74zqg` | `SEQ-3C-brgbola74zqg` | byte-identical |

Seeded baseline goldens also remain:

- `lab-ctla1` → `SEQ-CFA-lhbmeve33nn3`
- `lab-ctla2` → `SEQ-CFA-cyi3altqyaaq`

New exact candidate keys:

- `lab-ctla1` → `SEQ-CAM1-7ltwtryshnga`
- `lab-ctla2` → `SEQ-CAM1-w4kwip3no7g4`

The test freezes both values and proves candidate reconstruction retains scale and seed (`settings_identity_test.ts:25-29,87-105`). Config A omits the field; explicit `1.00` executes as baseline but does not reuse the incumbent absent-field canonical code (`settings_identity_test.ts:107-115`). Values `0.49`, `0.60`, `0.75`, NaN, infinities, strings, null, and explicit undefined are rejected (`settings_identity_test.ts:117-130`).

## 4. Pixel and checkpoint proof

Deterministic 96×96 non-constant fixture, light fixed rung, identical creator/seed/hardware:

| Artifact | Decoded-pixel SHA-256 |
|---|---|
| Baseline OR | `531fc0a1ff8556ab2d28b8e72ec00292a40bd8a37b2b3d1e95f64509770785ed` |
| Candidate OR | `531fc0a1ff8556ab2d28b8e72ec00292a40bd8a37b2b3d1e95f64509770785ed` |
| `b71ed99` incumbent O2 | `3771369f25b7d39d36abe05cb78c95ac5970903a09566a162118d482c189ca8e` |
| Current scale-absent O2 | `3771369f25b7d39d36abe05cb78c95ac5970903a09566a162118d482c189ca8e` |
| Current explicit-1.00 O2 | `3771369f25b7d39d36abe05cb78c95ac5970903a09566a162118d482c189ca8e` |
| Current 0.50 candidate O2 | `bf309be3832d14faafde022ef5abbce80fed03b72f1a8728704ea175b2d40792` |

Proof conclusions:

1. B/C OR pixels are identical.
2. Absent = explicit `1.00` = `b71ed99` exactly; no tolerance was needed.
3. Candidate `0.50` differs, proving the scalar is live.
4. All light/balanced/deep absent paths match `b71ed99`; both deep passes receive the one scalar (`test_4d_cam_1.py:128-188`).
5. After removing only scale/effective-radius, timing, and pixel-derived fields, B/C per-rung reports are identical (`test_4d_cam_1.py:128-154,285-307`).
6. An edge-dense fixture reports base balanced radii `0.32/0.40`, scene multiplier `0.92`, and final 0.50 radii `0.1472/0.1840`, proving order (`test_4d_cam_1.py:107-126`).

Fixture-only camera loss was baseline `0.2082014316`, candidate `0.1629546552`. This is diagnostic test output, not corpus evidence and not an acceptance result.

Frozen-file proof:

- `git diff b71ed99 -- deepclean-worker/tools/checkpoint_attribution.py` → empty.
- `git diff b71ed99 -- deepclean-worker/tools/checkpoint_capture.py` → empty.
- Frozen attribution SHA-256: `335d8967560a60f32c5732fde63258d9919520fd7006d8d74c1ffa46eef53a44`.
- Frozen checkpoint-capture SHA-256: `d9f0557bf713cd826ce6d6e4ba4111fee09d83b37fa82fe2b5c974c74bebab03`.
- Auxiliary tests prove a missing OR does not change a complete main manifest and an unexpected auxiliary name writes nothing (`test_4d_cam_1.py:191-211`).

## 5. Full local test outputs

Pre-build environment check:

```text
$ python3 deepclean-worker/tools/test_checkpoint_diagnostics.py
ModuleNotFoundError: No module named 'PIL'
```

This was a pre-existing machine dependency issue before any diff. A temporary isolated Python 3.11 environment at `/tmp/cam1-py.lz20Fv` installed Pillow 12.3.0, NumPy 2.4.6, Requests 2.34.2, and piexif 1.1.3. No workspace dependency or environment file changed.

Shared identity, corpus contract, and edge check:

```text
$ deno test supabase/functions/_shared/settings_identity_test.ts supabase/functions/_shared/corpus_test.ts
running 7 settings identity tests
identity predicates are exclusive over every frozen tuple ... ok
negative codec and wash tuples emit no frozen identity ... ok
full settings-code goldens and markers are byte-for-byte stable ... ok
preset reconstruction round-trips all presets with seed absent and present ... ok
4D-CAM-1 is an exact CUSTOM identity and round-trips both locked seeds ... ok
absent and explicit 1.00 are baseline-only while the incumbent golden stays absent ... ok
optics PSF request boundary accepts only absent, 1.00, or 0.50 ... ok
running 4 corpus contract tests
edge settings-code implementation matches the frozen client contract ... ok
image header parser extracts PNG dimensions ... ok
image header parser extracts JPEG dimensions ... ok
image header parser extracts extended WebP dimensions ... ok
ok | 11 passed | 0 failed

$ deno check supabase/functions/create-deepclean-job/index.ts
Check supabase/functions/create-deepclean-job/index.ts
```

Frozen diagnostics and 4D-CAM-1 worker tests:

```text
$ /tmp/cam1-py.lz20Fv/bin/python -m py_compile <changed Python files>
(no output; exit 0)

$ /tmp/cam1-py.lz20Fv/bin/python deepclean-worker/tools/test_checkpoint_diagnostics.py
PASS test_directional_spatial_correlation
PASS test_iid_like_field_is_near_zero
PASS test_delta_e76_key_migration
PASS test_per_job_checkpoint_isolation
PASS test_manifest_completeness_requires_o5
PASS test_capture_gate_without_lab_seed_writes_nothing
PASS test_o2_exact_and_same_hardware_tolerance_rules
PASS 7 deterministic diagnostic/checkpoint tests

$ /tmp/cam1-py.lz20Fv/bin/python deepclean-worker/tools/test_4d_cam_1.py
PASS test_worker_boundary_is_fail_closed
PASS test_coherent_boundary_is_fail_closed
PASS test_absent_and_explicit_one_are_pixel_identical_and_half_is_live
PASS test_scene_modulation_precedes_scale
PASS test_every_rung_and_both_deep_passes_receive_one_scalar
PASS test_absent_baseline_matches_b71ed99_for_every_rung
PASS test_auxiliary_contract_is_independent_of_main_whitelist
PASS test_ds_path_captures_or_without_main_checkpoint_errors
PASS test_fixed_rung_replay_produces_proof_hashes_and_metrics
PROOF {"absent_scale_o2_sha256": "3771369f25b7d39d36abe05cb78c95ac5970903a09566a162118d482c189ca8e", "baseline_loss": 0.20820143163099192, "baseline_or_sha256": "531fc0a1ff8556ab2d28b8e72ec00292a40bd8a37b2b3d1e95f64509770785ed", "candidate_loss": 0.16295465518355767, "candidate_o2_sha256": "bf309be3832d14faafde022ef5abbce80fed03b72f1a8728704ea175b2d40792", "candidate_or_sha256": "531fc0a1ff8556ab2d28b8e72ec00292a40bd8a37b2b3d1e95f64509770785ed", "explicit_1_o2_sha256": "3771369f25b7d39d36abe05cb78c95ac5970903a09566a162118d482c189ca8e", "incumbent_b71ed99_o2_sha256": "3771369f25b7d39d36abe05cb78c95ac5970903a09566a162118d482c189ca8e"}
PASS 9 deterministic 4D-CAM-1 tests
```

TypeScript and production bundle:

```text
$ npm run check
> resmarke@0.1.0 check
> tsc --noEmit
(exit 0)

$ npm run build
> resmarke@0.1.0 build
> tsc && vite build
vite v7.3.6 building client environment for production...
transforming...
✓ 1794 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                              1.62 kB │ gzip:   0.71 kB
dist/assets/privacyMax.worker-DnQPOqs-.js    4.06 kB
dist/assets/CorpusApp-i4wkAEdj.css          15.39 kB │ gzip:   3.42 kB
dist/assets/RelabApp-CoUOZfMq.css           17.56 kB │ gzip:   3.74 kB
dist/assets/CmintApp-D-Ws6gdP.css           26.86 kB │ gzip:   5.55 kB
dist/assets/RemintApp-Bb-ZUtCO.css          29.18 kB │ gzip:   5.86 kB
dist/assets/PrintApp-eK-boN-M.css           35.11 kB │ gzip:   7.21 kB
dist/assets/index-CfNBWO8u.css              68.19 kB │ gzip:  12.78 kB
dist/assets/react-vendor-Da_OL1sC.js         3.66 kB │ gzip:   1.38 kB
dist/assets/icons-vendor-CPTzEEOT.js        21.23 kB │ gzip:   7.95 kB
dist/assets/browser-BzBbrBKd.js             32.14 kB │ gzip:  12.33 kB
dist/assets/CorpusApp-DnyMatB6.js           33.67 kB │ gzip:   8.93 kB
dist/assets/CmintApp-214Ww-bt.js            43.25 kB │ gzip:  12.66 kB
dist/assets/RelabApp-TPh3Im9o.js            43.72 kB │ gzip:  13.09 kB
dist/assets/RemintApp-BDT7Rzrq.js           45.76 kB │ gzip:  13.30 kB
dist/assets/corpusClient-D-CgH1zX.js        64.15 kB │ gzip:  17.34 kB
dist/assets/PrintApp-BCnxRuJb.js            99.69 kB │ gzip:  23.50 kB
dist/assets/supabase-vendor-Bpnwbzac.js    209.55 kB │ gzip:  54.62 kB
dist/assets/index-D5zCtYpn.js              359.61 kB │ gzip: 102.38 kB
✓ built in 994ms
```

## 6. Round ledger constants

Copied verbatim before candidate corpus pixels exist:

| Image | `lab-ctla1` | `lab-ctla2` |
|---|---:|---:|
| IMG-5 | 0.1131 | 0.0916 |
| IMG-6 | 0.1630 | 0.1713 |
| IMG-9 | 0.2894 | 0.2892 |
| IMG-11 | 0.2776 | 0.2697 |

Subset mean: **0.2081125**. Operational gate: **≤0.1561**. Arithmetic audit value: **0.1560844**.

## 7. External experiment handoff

No experiment was created. The build instruction contains an internal conflict:

- hard rule §0.1: **“no Supabase action”**;
- §4: create a fixed-corpus experiment in `/corpus`.

The hard rule controls. Creating the record would be a Supabase mutation and would make the build rejectable. The owner/master engineer must create it during the operational phase with exactly:

```json
["A", "SEQ-CAM1-7ltwtryshnga", "SEQ-CAM1-w4kwip3no7g4"]
```

Experiment ID: **OWNER_PENDING — intentionally not fabricated**. The generic `CUSTOM` string must not be present. No cell is authorized by this report.

## 8. Signed no-ops declaration

I, C8, attest for this build session:

- no git commit or push;
- no deployment or image publication;
- no RunPod, pod, volume, environment, or worker-scaling action;
- no Supabase action or corpus mutation;
- no grading or vendor call;
- no corpus job, first light, or experimental cell;
- no modification to `checkpoint_attribution.py`, `checkpoint_capture.py`, production `RemintApp.tsx`/`CmintApp.tsx`, wash, lattice, codec, finisher, final encode, detector providers/thresholds, database constraints, or source transfer.

Signed: **C8 · 2026-08-26 · LOCAL_BUILD_ONLY**

READY_FOR_MASTER_ENGINEER_REVIEW
