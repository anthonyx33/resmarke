# C8 4D-1A Build Report

Date: 2026-08-27 17:37 AEST (+1000)  
Builder: C88 / Codex build executor  
Base HEAD (unchanged): `acbcead4212093e297302201d2d089d5f58e9dea`  
Build disposition: **IMPLEMENTATION COMPLETE; ALL AUTHORITATIVE LOCAL BUILD-TIME GATES PASS**

The source-energy transfer is integrated post-O2/pre-tone-lock, disabled by
default, sealed to the two locked lab seeds, and fail-closed at both request and
worker boundaries. No deployment or round execution was performed.

## 1. Exact build scope and changed-line summary

The build owns exactly seven modified tracked files and four new implementation
or proof files. Every file is within the build allowlist. The required report is
this additional untracked root deliverable. Other pre-existing untracked
workspace material is not part of this build and was not modified.

| Status | File | `+` | `-` | Change summary |
|---|---|---:|---:|---|
| modified | `deepclean-worker/ds_remint_v8_8.py` | 53 | 2 | Adds strict `4d1a` normalization, locked-tuple checks, post-O2/pre-tone transfer invocation, conditional auxiliary capture, and transfer reporting while retaining an identical OFF path. |
| modified | `deepclean-worker/tools/auxiliary_checkpoints.py` | 5 | 3 | Adds exactly `O2_transfer.png` to the auxiliary whitelist and keeps the incumbent auxiliary manifest behavior as the default. |
| modified | `deepclean-worker/worker.py` | 22 | 1 | Carries the locked lab seed through standalone/HD routes and finalizes the deterministic transfer report post-O5. |
| modified | `src/RelabApp.tsx` | 10 | 3 | Adds the sealed 4D-1A lab preset and locked-seed UI behavior. |
| modified | `src/lib/deepcleanClient.ts` | 4 | 0 | Serializes the transfer flag for standalone and HD worker payloads. |
| modified | `supabase/functions/_shared/settingsIdentity.ts` | 71 | 4 | Adds the preset, strict flag/tuple validation, seed-dependent CUSTOM identities, exact reconstruction, and marker without changing frozen/CAM identity results. |
| modified | `supabase/functions/create-deepclean-job/index.ts` | 44 | 0 | Adds strict unknown-key/boolean/tuple rejection and exact serialization before durable mutation. |
| new | `deepclean-worker/transfer_4d_1a.py` | 851 | 0 | Implements the deterministic float64 H1/H2 source-energy transfer, complete-support re-mask, cap enforcement, safe RGB synthesis, hashes, and post-O5 diagnostics. |
| new | `deepclean-worker/tools/transfer_4d_1a_harness.py` | 571 | 0 | Provides the 13-test CPU proof harness, explicit artifact hashes, fixture aggregation, frozen-file checks, and OFF/ON proofs. |
| new | `deepclean-worker/tools/transfer_4d_1a_identity_test.ts` | 139 | 0 | Proves both new codes, frozen/CAM identity stability, reconstruction, and fail-closed identity semantics. |
| new | `deepclean-worker/tools/transfer_4d_1a_edge_test.ts` | 66 | 0 | Proves edge-boundary gate order, unknown-key rejection, and standalone/HD serialization. |

Implementation/proof total: **1,836 insertions, 13 deletions**. This count
excludes this report.

`git diff --check`: exit 0, no output.

## 2. Integration and numeric-core declaration

- Transfer location: after the incumbent O2 checkpoint and before tone lock.
- OFF behavior: absent and explicit `false` retain incumbent bytes and report;
  non-lab jobs create neither transfer output nor auxiliary transfer file.
- ON behavior: exact V8.9 tuple, `optics_psf_scale` absent/1.00, strict boolean
  `4d1a: true`, and exactly one of `lab-ctla1` / `lab-ctla2`.
- HD routing rewrites the worker mode to `ds-remint-v8.9`, so the same strict
  transfer gate is reached on every route.
- Auxiliary isolation: only `O2_transfer.png` is added; the main O0-O5
  checkpoint whitelist, ordering, manifest, and O5 bytes are not changed by
  auxiliary capture.
- Numeric core: `H' = H × (1 + alpha × w × (g - 1))`, `alpha=0.10`, one-sided
  gain `[1.0, 1.10]`, energy cap `min(1.21 × E_remint, E_source)`, float64,
  single uint8 rounding, safe shared RGB delta, and fail-closed `1e-9` relative
  final cap verification.
- Complete-support invariant: `w = clip(gauss(w_raw)) × support_binary`; no
  smoothed weight can escape the complete support mask.
- Frozen primitives: `np.gradient` edge recipe, frozen quantized Gaussian
  recipe, `(1.4826 × MAD)^2` noise estimate with floor, ±0.5 parabolic alignment,
  and exact safe-delta synthesis.
- Report: input pixel hashes are captured at transfer time; the deterministic
  report is finalized post-O5 with both pre-transfer-O2→O5 and
  O2-transfer→O5 diagnostic losses.

The three accepted non-material interpretations are recorded exactly:

1. usable-band SNR uses the minimum of the two local band energies;
2. pyramid downscaling uses PIL LANCZOS;
3. final cap verification applies to valid windows with genuine source-energy
   surplus.

## 3. Frozen-file zero-diff proof

`git diff --exit-code` returned 0 for all five protected files. Their build-time
SHA-256 values are:

```text
7d83e896def0a58bcee6ea6f2fa5e7e5e42dc1adc5ed34317678f54b9267b183  deepclean-worker/coherent_camera.py
335d8967560a60f32c5732fde63258d9919520fd7006d8d74c1ffa46eef53a44  deepclean-worker/tools/checkpoint_attribution.py
3cf1af5c4e87e17ae81940e21f90701cd2262df8b69ba5a200004801110d40f7  deepclean-worker/tools/camera_only_replay.py
d9f0557bf713cd826ce6d6e4ba4111fee09d83b37fa82fe2b5c974c74bebab03  deepclean-worker/tools/checkpoint_capture.py
538c9edb3bdc7c0ebe7e8faf16b37a76d6d0c29b107a1914168bed8e4f587175  deepclean-worker/quality_finish.py
```

Camera, finisher, wash, wash-combos, lattice, ROI manifest, vendor adapter, and
`EXPECTED_CHECKPOINTS` are untouched.

## 4. Identity goldens before and after

The baseline values were captured before implementation and were emitted
unchanged by the post-build identity suite:

| Identity | Before | After | Verdict |
|---|---|---|---|
| frozen A/CFA | `SEQ-CFA-dtbnbygm5iao` | `SEQ-CFA-dtbnbygm5iao` | byte-identical |
| frozen 1A | `SEQ-1A-3lzgvffda5xf` | `SEQ-1A-3lzgvffda5xf` | byte-identical |
| frozen 2B | `SEQ-2B-zzz2dudlbywp` | `SEQ-2B-zzz2dudlbywp` | byte-identical |
| frozen 3C | `SEQ-3C-brgbola74zqg` | `SEQ-3C-brgbola74zqg` | byte-identical |
| CAM-1 / ctla1 | `SEQ-CAM1-7ltwtryshnga` | `SEQ-CAM1-7ltwtryshnga` | byte-identical |
| CAM-1 / ctla2 | `SEQ-CAM1-w4kwip3no7g4` | `SEQ-CAM1-w4kwip3no7g4` | byte-identical |

The new sealed codes round-trip exactly:

```text
lab-ctla1  SEQ-4D1A-kqbl35dztkl4
lab-ctla2  SEQ-4D1A-p3m5qpiorc7b
```

## 5. Baseline/candidate and determinism proof hashes

OFF-arm versus ON-arm proof:

```json
{"baseline_o2_sha256":"1e664e39193ce909af4301b2759037091a5c2f2a4955079c96a0aaf427a7b5b9","candidate_o2_transfer_sha256":"2589ff3efaf5a3c80ad5f9338c2c3c17ab6c0fc2e96d6fea28bf32a27a5386d8","candidate_pre_transfer_o2_sha256":"1e664e39193ce909af4301b2759037091a5c2f2a4955079c96a0aaf427a7b5b9","off_arm_bit_identity":true,"on_arm_diverged":true,"r2_sha256":"91aee710a500a21ff6d6171e7544f9255079b7915f1b772ffc28c5607a44edf1","same_machine_noise_floor_rms_lsb":"0.000000000000"}
```

Two fresh same-build/same-machine runs produced identical O2 input, R2,
`O2_transfer`, O5, and canonical deterministic report bytes:

```json
{"o2_input_pixels_sha256":"eb595a8e44424357acdeec4cdefd846f20e6fa733c10611b431d50f6016d5ef1","o2_transfer_pixels_sha256":"93a0a724a6510c9b07fa23594a2a54e456017c6a4edb394ec6eb048aa0654ebc","o5_pixels_sha256":"3980226280076dee9a2efe0dbd275499a67c1113eb586303bdd33fb9f0d81b3d","r2_pixels_sha256":"91aee710a500a21ff6d6171e7544f9255079b7915f1b772ffc28c5607a44edf1","report_sha256":"373bf49cea77a84c2d29169a4f0b6437f56ec17211e819fe5424a8326a7d9897"}
```

Same-machine measured noise floor: **0.000000000000 RMS LSB**.

Cross-machine characterization: **NOT PERFORMED / NO INDEPENDENT MACHINE WAS
AVAILABLE IN THIS WORKSPACE**. A second host cannot be truthfully represented
by another interpreter or process on this Apple M5 machine. Per FINAL §2.5,
cross-machine results are non-authoritative and cannot relax any same-machine
hash gate or screening threshold. This limitation is explicit rather than
fabricating a measurement; an owner/master-engineer with an independent host
may append the informational measurement before deployment acceptance.

## 6. FINAL §4 fixture aggregation

All required fixtures passed:

```json
{"alpha_zero_identity":"PASS","bad_alignment_rejected":"PASS","bad_orientation_rejected":"PASS","channel_difference_preserved_and_cap_fraction_truthful":"PASS","confidence_boundary_no_new_extrema":"PASS","edge_mag_exact_np_gradient_equivalence":"PASS","equal_energy_different_phase_noop":"PASS","final_window_cap_fail_closed_at_1e-9_relative":"PASS","flat_and_near_flat_unchanged":"PASS","gain_floor_after_cap_enforcement":"PASS","h1_only_cross_scale_support_rejected":"PASS","image_borders_safe":"PASS","nan_safe":"PASS","no_weight_outside_complete_support":"PASS","polarity_flip_rejected":"PASS","reject_counts_truthful":"PASS","remint_energy_at_or_above_source_noop":"PASS","slanted_edge_zero_crossing_source_shoulder_absent":"PASS","zero_energy_denominator_safe":"PASS"}
```

The harness additionally proves absent/false identity, true-without-seed
failure, non-boolean/unknown-key rejection, B/C pre-transfer O2 identity,
conditional auxiliary existence, main-manifest isolation, post-O5 reporting,
and all five-artifact same-machine determinism.

## 7. Full test outputs

Environment:

```text
Python 3.14.6
deno 2.9.0 (stable, release, aarch64-apple-darwin)
v8 14.9.207.2-rusty
typescript 6.0.3
node v24.17.0
Python proof-only dependencies: /tmp/c8-4d1a-pydeps
```

### TypeScript production check

Command: `npm run check`

```text
> resmarke@0.1.0 check
> tsc --noEmit

exit 0
```

### Production Vite build

Command: `npm run build`

```text
> resmarke@0.1.0 build
> tsc && vite build

vite v7.3.6 building client environment for production...
transforming...
✓ 1794 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                              1.62 kB │ gzip:   0.72 kB
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
dist/assets/CorpusApp-1XW8_rCy.js           33.67 kB │ gzip:   8.93 kB
dist/assets/CmintApp-BTVTIWOf.js            43.25 kB │ gzip:  12.67 kB
dist/assets/RelabApp-Bnmu8wNg.js            43.98 kB │ gzip:  13.16 kB
dist/assets/RemintApp-BR-1I80Y.js           45.76 kB │ gzip:  13.30 kB
dist/assets/corpusClient-fOBRg7kr.js        64.15 kB │ gzip:  17.34 kB
dist/assets/PrintApp-B2GHNwzt.js            99.69 kB │ gzip:  23.50 kB
dist/assets/supabase-vendor-Bpnwbzac.js    209.55 kB │ gzip:  54.62 kB
dist/assets/index-Do4Mkv26.js              360.35 kB │ gzip: 102.56 kB
✓ built in 1.14s
exit 0
```

### Deno checks

Command: `deno check` on the modified identity/edge files and both new Deno
proof files.

```text
Check supabase/functions/_shared/settingsIdentity.ts
Check supabase/functions/create-deepclean-job/index.ts
Check deepclean-worker/tools/transfer_4d_1a_identity_test.ts
Check deepclean-worker/tools/transfer_4d_1a_edge_test.ts
exit 0
```

### Deno tests

Command: `deno test --allow-read` on Hive parser regression, settings identity,
corpus, lab seed, and both new proof files.

```text
running 3 tests from ./supabase/functions/grade-image/hive_test.ts
parses the verified Hive V3 detector response ... ok
rejects responses without the required probability heads ... ok
rejects out-of-range Hive values ... ok
running 7 tests from ./supabase/functions/_shared/settings_identity_test.ts
identity predicates are exclusive over every frozen tuple ... ok
negative codec and wash tuples emit no frozen identity ... ok
full settings-code goldens and markers are byte-for-byte stable ... ok
preset reconstruction round-trips all presets with seed absent and present ... ok
4D-CAM-1 is an exact CUSTOM identity and round-trips both locked seeds ... ok
absent and explicit 1.00 are baseline-only while the incumbent golden stays absent ... ok
optics PSF request boundary accepts only absent, 1.00, or 0.50 ... ok
running 4 tests from ./supabase/functions/_shared/corpus_test.ts
edge settings-code implementation matches the frozen client contract ... ok
image header parser extracts PNG dimensions ... ok
image header parser extracts JPEG dimensions ... ok
image header parser extracts extended WebP dimensions ... ok
running 3 tests from ./supabase/functions/_shared/lab_seed_test.ts
absent lab seed takes the unchanged path without requiring lab config ... ok
lab seed gate order and typed statuses are exact ... ok
rejection gate is before every credit ledger and job mutation ... ok
running 4 tests from ./deepclean-worker/tools/transfer_4d_1a_identity_test.ts
4D-1a round-trips both sealed seed-dependent identities ... ok
four frozen and both CAM-1 identity goldens remain byte-identical ... ok
4D-1a marker requires the exact candidate tuple ... ok
4D-1a request flag and locked tuple fail closed ... ok
running 3 tests from ./deepclean-worker/tools/transfer_4d_1a_edge_test.ts
4D-1a edge boundary validates before durable mutation ... ok
4D-1a edge boundary rejects unknown V8.9 keys ... ok
4D-1a flag is serialized into standalone and HD worker payloads ... ok

ok | 24 passed | 0 failed
exit 0
```

### Python compilation

Command: Python `compileall -q` on all modified/new worker Python files.

```text
(no output)
exit 0
```

### Frozen checkpoint diagnostics

```text
PASS test_directional_spatial_correlation
PASS test_iid_like_field_is_near_zero
PASS test_delta_e76_key_migration
PASS test_per_job_checkpoint_isolation
PASS test_manifest_completeness_requires_o5
PASS test_capture_gate_without_lab_seed_writes_nothing
PASS test_o2_exact_and_same_hardware_tolerance_rules
PASS 7 deterministic diagnostic/checkpoint tests
exit 0
```

### Frozen 4D-CAM-1 regression

```text
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
exit 0
```

### 4D-1A transfer harness

```text
PASS test_worker_flag_boundary_is_strict_and_fail_closed
PASS test_absent_and_false_match_head_incumbent_bytes_and_report
PASS test_o2_identity_auxiliary_isolation_on_divergence_and_post_o5_report
PASS test_same_machine_determinism_for_all_candidate_artifacts
PASS test_frozen_edge_recipe_and_complete_support_remasking
PASS test_energy_equation_noops_phase_and_numeric_failures
PASS test_window_cap_gain_floor_and_one_nanosecond_relative_fail_closed
PASS test_channel_differences_preserved_and_capped_fraction_truthful
PASS test_support_gates_reject_independently_and_counts_are_truthful
PASS test_flat_near_flat_borders_alpha_zero_and_full_fail_closed_are_identity
PASS test_phase_zero_crossing_and_confidence_boundary_fixtures
PASS test_auxiliary_whitelist_gains_exactly_one_name_and_main_manifest_is_unchanged
PASS test_protected_files_are_zero_diff
DETERMINISM {"o2_input_pixels_sha256":"eb595a8e44424357acdeec4cdefd846f20e6fa733c10611b431d50f6016d5ef1","o2_transfer_pixels_sha256":"93a0a724a6510c9b07fa23594a2a54e456017c6a4edb394ec6eb048aa0654ebc","o5_pixels_sha256":"3980226280076dee9a2efe0dbd275499a67c1113eb586303bdd33fb9f0d81b3d","r2_pixels_sha256":"91aee710a500a21ff6d6171e7544f9255079b7915f1b772ffc28c5607a44edf1","report_sha256":"373bf49cea77a84c2d29169a4f0b6437f56ec17211e819fe5424a8326a7d9897"}
PROOF {"baseline_o2_sha256":"1e664e39193ce909af4301b2759037091a5c2f2a4955079c96a0aaf427a7b5b9","candidate_o2_transfer_sha256":"2589ff3efaf5a3c80ad5f9338c2c3c17ab6c0fc2e96d6fea28bf32a27a5386d8","candidate_pre_transfer_o2_sha256":"1e664e39193ce909af4301b2759037091a5c2f2a4955079c96a0aaf427a7b5b9","off_arm_bit_identity":true,"on_arm_diverged":true,"r2_sha256":"91aee710a500a21ff6d6171e7544f9255079b7915f1b772ffc28c5607a44edf1","same_machine_noise_floor_rms_lsb":"0.000000000000"}
FIXTURES {"alpha_zero_identity":"PASS","bad_alignment_rejected":"PASS","bad_orientation_rejected":"PASS","channel_difference_preserved_and_cap_fraction_truthful":"PASS","confidence_boundary_no_new_extrema":"PASS","edge_mag_exact_np_gradient_equivalence":"PASS","equal_energy_different_phase_noop":"PASS","final_window_cap_fail_closed_at_1e-9_relative":"PASS","flat_and_near_flat_unchanged":"PASS","gain_floor_after_cap_enforcement":"PASS","h1_only_cross_scale_support_rejected":"PASS","image_borders_safe":"PASS","nan_safe":"PASS","no_weight_outside_complete_support":"PASS","polarity_flip_rejected":"PASS","reject_counts_truthful":"PASS","remint_energy_at_or_above_source_noop":"PASS","slanted_edge_zero_crossing_source_shoulder_absent":"PASS","zero_energy_denominator_safe":"PASS"}
PASS 13 deterministic 4D-1a tests
exit 0
```

Aggregate applicable automated result: **29/29 Python proofs and 24/24 Deno
tests passed**, plus clean Python compilation, TypeScript production check,
Deno checks, Vite production build, frozen-file diff, and whitespace diff.

## 8. Signed declaration

I attest that this build was produced against the unchanged base HEAD shown
above and remains uncommitted. I performed **no commit, no push, no deploy, no
RunPod action, no Supabase action, no vendor call, no grading, and no cell run**.
I did not alter any protected or out-of-scope tracked file. Deployment and the
24-cell round remain owner actions after master-engineer acceptance and any
desired non-authoritative independent-host characterization.

Signed: **C88 / Codex build executor**  
Signature time: **2026-08-27 17:37 AEST (+1000)**
