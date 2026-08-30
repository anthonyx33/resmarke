# C8 MASTER PROMPT — BUILD 4D-CAM-1 (camera Gaussian-radius retune, sealed 0.50)

Date: 2026-08-26 · Issued by: master engineer · Owner-authorized design, build only

## 0. Your role

You are C8, builder for round **4D-CAM-1**. You write code and run **local tests only**.
The design is frozen: `C8_4D_CAM_1_BUILD_BRIEF.md` (master-engineer-reviewed and accepted).
This prompt does not add or change any design parameter — it tells you how to execute.

Hard rules (any violation = build rejected):
1. **No git commit, no push, no deploy, no RunPod action, no Supabase action, no grading, no corpus run.**
2. Only the file allowlist in §3 may change. Wash, lattice, codec, finisher, final encode,
   detection thresholds/providers, database constraints, production UI (`RemintApp.tsx` /
   `CmintApp.tsx`), and the frozen tool `checkpoint_attribution.py` (commit `b71ed99`) are
   **untouchable**. A diff touching them rejects the build.
3. Every claim you make in the build report cites file/line and test output. No estimates
   about the build itself — the build is executable, the design holds the estimates.
4. Baseline B and candidate C are the ONLY two settings tuples authorized in code.
   `optics_psf_scale` accepts exactly `absent`, `1.00`, or `0.50`. No `0.60`/`0.75`, no
   clamps, no silent defaults for invalid values — validation errors fail closed.
5. Stop after proof gates and hand back the uncommitted build report. The master engineer
   verifies line by line; the owner performs every operational action.

## 1. Evidence stack (read first, cite only these)

- `C8_4D_CAM_1_BUILD_BRIEF.md` — the accepted spec (normative, §3 is your implementation scope)
- `ATTRIBUTION_REPORT.md` — evidence background (commit `709100e`)
- `deepclean-worker/tools/checkpoint_attribution.py` at commit `b71ed99` — frozen, do not touch
- Subset baseline (verify against `retrieval-checkpoints/attribution.jsonl`, frozen):
  IMG-5 0.1131/0.0916 · IMG-6 0.1630/0.1713 · IMG-9 0.2894/0.2892 · IMG-11 0.2776/0.2697
  (ctla1/ctla2) → subset mean **0.2081125**, gate **≤0.1561** (audit 0.1560844). Copy these
  numbers verbatim into the round ledger; never recompute them after candidate pixels exist.

## 2. Lab identity (frontend + edge)

File: `supabase/functions/_shared/settingsIdentity.ts`
- Add optional `opticsPsfScale?: number` to `RemintSettings`.
- Refactor the frozen-tuple predicate: Config A/1A/2B/3C require the field **absent or `1.00`**.
- Add an exact 4D-CAM-1 predicate: Config A tuple + default codec + `opticsPsfScale === 0.50`.
- `buildSettingsCode` must emit `SEQ-CAM1-<hash>` for the exact candidate; `configIdentity`
  returns `{ label: "CUSTOM", key: <full settings code> }`. No schema migration, no new frozen label.

File: `src/RelabApp.tsx`
- Add a **lab-only** `4d-cam-1` preset to the /relab preset list (`PresetDefinition` area and
  the helpers at lines ~1135-1146). Do NOT touch `src/RemintApp.tsx` or any production surface.
- Permit `CUSTOM` only when the 4D-CAM-1 predicate passes AND a locked lab seed is present.
  Regrade/reconstruction (~488-539, 758) must restore the exact candidate tuple — never fall
  back to the UI-selected preset.
- Baseline B omits `opticsPsfScale` from its canonical JSON; its `SEQ-CFA-*` golden string
  must remain **byte-for-byte identical** to today.

File: `src/lib/deepcleanClient.ts`
- Add `opticsPsfScale?: number` to `DsRemintV8_8Options` (~86-101) and serialize it as
  `optics_psf_scale` only in the V8.9/HD remint request (~278-325). Keep the public V8.8
  contract unchanged.

File: `supabase/functions/create-deepclean-job/index.ts`
- In `dsRemintV8_9ExpertRefinement` (~1188-1210): accept absence → `1.00`; explicit candidate
  exactly `0.50`; anything else returns a validation error (no clamp, no default).
  Serialize into `ds_remint_v8_9` settings for the worker request.

File: `supabase/functions/_shared/settings_identity_test.ts` (or its existing test location)
- New tests: (a) four frozen predicates + settings-code goldens unchanged;
  (b) absent and explicit `1.00` both execute as baseline, only absent emits the incumbent
  code; (c) `0.50` matches only 4D-CAM-1, label `CUSTOM`, emits `SEQ-CAM1-*`;
  (d) `0.49`, `0.60`, `0.75`, NaN, infinity, strings, null rejected at the boundary;
  (e) candidate reconstruction round-trips both locked seeds without losing the scale.

## 3. Worker pixel path

File: `deepclean-worker/coherent_camera.py`
- Add `psf_scale` to coherent-camera settings normalization, default `1.00`.
- **After** the existing optional `0.92` scene/texture adjustment (~341-355) and **immediately
  before** `_per_channel_psf` (~158-192): compute
  `effective_psf_g = cfg["psf_g"] × psf_scale`, `effective_psf_rb = cfg["psf_rb"] × psf_scale`.
  Pass only the effective radii into `_per_channel_psf` (~295-305).
- Report per attempted rung: `base_psf_g`, `base_psf_rb`, scene multiplier,
  `psf_scale`, `effective_psf_g`, `effective_psf_rb`. No other field may differ between
  paired fixed-rung calls.

File: `deepclean-worker/ds_remint_v8_8.py`
- `normalize_ds_remint_v8_8_settings` (~114-173): default `optics_psf_scale = 1.00`,
  strict allowed set `{0.50, 1.00}`, invalid explicit values fail closed. Include
  requested/executed scale in the engine report (~183-199).
- `_v88_candidate` (~409-440): pass that one value through the `coherent_camera` sub-settings
  for **every** camera call, including both passes of the manual deep branch. Do not
  precompute separate green/red-blue overrides.

File: `deepclean-worker/tools/` — new auxiliary checkpoint contract (NEW files only)
- **Do not modify** `checkpoint_capture.py` (`EXPECTED_CHECKPOINTS` stays byte-for-byte) and
  **do not modify** frozen `checkpoint_attribution.py`.
- New module (e.g. `auxiliary_checkpoints.py`): explicit whitelist containing only
  `OR_postresample.png`, path-safety identical to the main helper, decoded-pixel SHA-256
  identical to `pixel_sha256`, manifest under `report.auxiliary_checkpoints` with
  `{status, files, errors}`. Auxiliary errors never append to the main O0–O5 error list.
- New analysis helper (e.g. `tools/camera_only_replay.py`): camera-only loss
  `max(1 − EATR(O2|OR), 1 − HFTR_H1(O2|OR), 0)` on the identical lattice, with fixed-rung
  paired replay support. Do not touch the frozen attribution tool.
- Worker change in `ds_remint_v8_8.py`: capture `OR_postresample.png` from `reference = base`
  immediately after the single LANCZOS resample and **before** the camera ladder (~248-263),
  through the auxiliary contract only. Never pass it to `save_checkpoint`.
  Non-lab jobs write no auxiliary files.

## 4. Browser operator step (data, not code)

After tests pass, in your own browser (never the shared pages):
1. Open `/corpus` → create a **new fixed-corpus experiment** whose `config_set` permits
   label `A` and the two exact seed-specific `SEQ-CAM1-*` keys only. Do **not** permit the
   generic string `CUSTOM` (`corpus-run-intent` accepts label or key — a generic CUSTOM
   would let any custom tuple through).
2. Report the experiment id, its exact `config_set`, and the two `SEQ-CAM1-*` strings.
3. Do not run any cell.

## 5. Build-time proof gates (all must pass before you stop)

1. `git diff b71ed99 -- deepclean-worker/tools/checkpoint_attribution.py` is **empty**.
2. `EXPECTED_CHECKPOINTS` unchanged; new tests prove a missing auxiliary never flips a
   legacy main O0–O5 manifest to error.
3. Baseline (scale absent) reproduces the Config A canonical JSON + settings code.
   Same fixed OR input/creator/seed/rung/hardware → exact O2 pixel hash vs incumbent; if the
   documented same-hardware tolerance is needed: RMS ≤0.1 LSB and max ≤1 (different hardware
   requires exact).
4. Per fixed rung, B vs C reports differ only in requested/effective scale/radii, timing,
   and pixel-derived metrics/hashes. Seeds, other settings, and input OR hash equal.
5. Candidate O2 differs from B on a non-constant fixture (scalar is live); scale `1.00` and
   absence are pixel-identical.
6. Request-boundary tests, shared identity tests, auxiliary tests, worker camera tests,
   `npm run check`, and `npm run build` all pass. Any unrelated pre-existing failure is
   documented before the diff; it may not be waived silently.

## 6. Deliverable (uncommitted build report)

Return `C8_4D_CAM_1_BUILD_REPORT.md` (workspace root, untracked) containing:
- exact `git diff` file list and changed-line summary, all within §2-§3 allowlist
- the four settings-code goldens before/after (prove `SEQ-CFA-*` unchanged)
- full test outputs (identity, boundary, auxiliary, camera, check, build)
- baseline/candidate proof hashes (OR identity, O2 identity at 1.00, O2 divergence at 0.50)
- the new experiment id + `config_set` + `SEQ-CAM1-*` strings
- a signed declaration: no commit, no deploy, no RunPod/Supabase action, no grading, no cell run.

Then STOP. No first light, no cells, no vendor calls.

## 7. What happens next (not yours)

Master engineer verifies the diff line-by-line against this prompt and the brief; owner then
performs every operational action (image build, deploy, env, experiment GO). The 34-cell
round, panel, and real-vendor grading are separate, owner-gated phases.
