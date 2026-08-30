# MASTER ENGINEER VERIFICATION — 4D-1a BUILD (PARTIAL)

Date: 2026-08-27 · Status: **PASS on all completed work — build incomplete (C88
credit limit); do NOT deploy or run cells until the remaining items and the
build report exist.**

## 1. Worktree scope — PASS

- Modified files (7): `ds_remint_v8_8.py`, `tools/auxiliary_checkpoints.py`,
  `worker.py`, `src/RelabApp.tsx`, `src/lib/deepcleanClient.ts`,
  `_shared/settingsIdentity.ts`, `create-deepclean-job/index.ts` — all within
  the allowlist.
- New files (4): `transfer_4d_1a.py`, `tools/transfer_4d_1a_harness.py`,
  `tools/transfer_4d_1a_identity_test.ts`, `tools/transfer_4d_1a_edge_test.ts`.
- Frozen files zero-diff: `coherent_camera.py`, `checkpoint_attribution.py`,
  `camera_only_replay.py`, `checkpoint_capture.py`, `quality_finish.py`
  (also asserted by harness `test_protected_files_are_zero_diff`).
- `git diff --check` clean. No commit/push by the builder.

## 2. Integration — PASS (line-by-line)

- Transfer stage sits after the O2 capture and before tone-lock ✓; OFF path
  (`4d1a` absent/false) adds no report key, no auxiliary file, no behavior
  change (harness-proven byte identity).
- Auxiliary whitelist gains exactly ONE name (`O2_transfer.png`); main O0–O5
  manifest untouched; `include_transfer` keeps the legacy manifest identical
  on the OFF path.
- Worker: `lab_seed` plumbed to both V8.9 and HD branches; the HD branch
  rewrites `mode` to `ds-remint-v8.9` before the engine call, so the new
  `mode == "ds-remint-v8.9"` gate is satisfied on every 4D-1a path.
- Report finalization runs post-O5 on the DELIVERED file; the diagnostic uses
  the frozen `checkpoint_attribution` combiners (same positional-band recipe
  as the pre-registered denominator).
- New strict unknown-key rejection verified SAFE for all production paths:
  the client serializes exactly `{engine_mode, wash_model, strength,
  jpeg_quality, jpeg_subsampling, seed, optics_psf_scale, 4d1a, iphone_exif,
  metadata_mode}` for v8.9 (⊆ `DS_REMINT_V8_9_KEYS`) and exactly
  `{ds_remint_v8_9, quality_finish}` for v8.9-hd (matches the HD assert).
  Worker-side `_ALLOWED_REMINT_KEYS` = `DEFAULT_SETTINGS − enabled + seed`,
  a superset of every key the server emits.

## 3. Flag semantics — PASS

`4d1a: true` without a locked lab seed fails closed at BOTH the edge
(`validate4d1aTuple`) and the worker (`normalize` + `validated_lab_seed`);
non-boolean values rejected; absent/false = incumbent. Mirror discipline of
`optics_psf_scale`.

## 4. Numeric core — PASS (line-by-line against FINAL brief §2)

- Equation: `g = 1 + min(α·w·(√(E_src/E_remint) − 1), 0.10)`, one-sided
  (`E_src ≤ E_remint → g = 1`), clipped `[1, 1.10]`, α strict {0, 0.10}.
- Support re-masking AFTER smoothing: `w = clip(gauss_σ3(w_raw)) ×
  support_binary` — the blocking C88 fix, implemented exactly.
- Margins formula verbatim (scale/residual/orientation/ncc/snr, SNR saturated
  at 8); cross-scale persistence; union p92 edge exclusion (np.gradient, NOT
  Sobel) with 2 px Euclidean dilation.
- Frozen `_gauss` uint8-quantized recipe; reflect borders; 15×15/stride-3
  energy windows; NCC ε = 1e-9, tie → first occurrence.
- Noise energy = `(1.4826 × MAD)²` over lowest-20%-edge 32×32 tiles, floor
  1e-6.
- Alignment: 3-level pyramid (σ=1), 32-block/16-stride in each level's own
  pixels, ×2 coarse initialization, ±8 residual search, parabolic refinement
  clamped ±0.5, zero at degenerate peaks.
- Cap enforcement: single vectorized correction pass; corrected gain clamped
  `[1, 1.10]`; final window energies fail-closed at 1e-9 relative.
- Synthesis: `delta_safe = clip(delta, −min(RGB), 1−max(RGB))`; channel
  differences preserved; capped fraction reported.
- Deterministic fixed-format serialization; in-memory O2/R2 pixel hashes in
  the report; float64 throughout.

Accepted implementation interpretations (recorded, non-material):
- SNR uses `min(E_remint, E_source)` (conservative usable-band energy).
- Pyramid downscale kernel = LANCZOS after σ=1 gauss (downscale kernel was
  not individually frozen).
- Cap-verification "valid grid" = affected windows with `E_src > E_remint`
  (one-sided transfer cannot enhance windows without source surplus).

## 5. Test battery — PASS

- `py_compile` on all changed Python ✓
- 7/7 new deno tests ✓ (identity goldens: `SEQ-4D1A-kqbl35dztkl4` /
  `SEQ-4D1A-p3m5qpiorc7b`; frozen goldens byte-identical; boundaries)
- 10/10 existing identity/lab-seed tests ✓
- 13/13 harness proofs ✓ — incl. OFF-arm bit-identity, same-machine
  determinism (noise floor 0.0 LSB), O2 identity + auxiliary isolation,
  frozen-edge recipe, window-cap fail-closed, channel-difference
  preservation, phase/zero-crossing fixtures, flat/no-op/border fixtures
- `deno check`, `tsc --noEmit`, `vite build`, `git diff --check` ✓
- Pillow deprecation warnings (harness only, `mode=` arg): harmless —
  worker `requirements.txt` pins `Pillow>=10,<13`, and the parameter is
  removed only in Pillow 13.

## 6. REMAINING before deploy (C88 continuation)

1. `C8_4D_1A_BUILD_REPORT.md` — changed-line summary, full test outputs,
   proof hashes, signed declaration.
2. Cross-machine noise-floor measurement (brief §2.5: measured at build time,
   reported; same-machine = 0.0 already recorded).
3. Aggregation of the harness fixtures into the report per FINAL brief §4.
4. Owner deploys ONLY after items 1–3 + my final acceptance.

## 7. Round constants confirmed by this build

- Experiment codes: `SEQ-4D1A-kqbl35dztkl4` (lab-ctla1),
  `SEQ-4D1A-p3m5qpiorc7b` (lab-ctla2) — seed-dependent, frozen in tests.
- Frozen denominator, gates G1–G7, budget, vendor freeze: unchanged.
