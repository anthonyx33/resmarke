# C88 4D-CAM-1 Build Brief — Camera Gaussian-Radius Retune

Date: 2026-08-26  
Status: design only; implementation, build, deployment, pod, volume, worker-scaling, and grading actions are not authorized by this document  
Incumbent: V12.3 (`c569595`)  
Attribution evidence: `709100e` + frozen tool `b71ed99` (diagnostic harness 7/7)  
Round owner: owner; line-by-line verifier: master engineer

## 1. Sealed round contract

4D-CAM-1 changes one output-affecting independent variable:

- Baseline B: incumbent Config A with `optics_psf_scale` absent; executed default = `1.00`.
- Candidate C: the identical Config A tuple with `optics_psf_scale = 0.50`.
- `optics_psf_scale` multiplies the existing per-channel Gaussian blur radii `psf_g` and `psf_rb` after scene modulation and immediately before `_per_channel_psf`. These values are GaussianBlur radii in camera RGB, not an optical PSF kernel (`deepclean-worker/coherent_camera.py:59-94,158-192,295-305,341-355`).
- The same scalar must reach every light/balanced/deep camera call, including both camera passes in the manual deep branch (`deepclean-worker/ds_remint_v8_8.py:409-440`). This preserves the chroma-heavier G:R/B relationship.

No value other than absent/`1.00` for B and exactly `0.50` for C is authorized. There is no `0.60`/`0.75` ladder and no post-hoc fallback level.

The following remain frozen: wash model and steps, histogram restore, 1250px delivery lattice, rung order and routing, scene modulation, cleanup, CFA/demosaic, noise, denoise, tone, chromatic aberration, vignette, sharpening, q92/4:2:0 stage-1 encode, strong/S1.25 adaptive Quality Finish, and Q97 delivery. Adaptive selection may respond downstream to the changed pixels; that is a mediated effect of the one sealed input, not a second independent variable. Only the fixed-rung replay described in §5 may support a component-level causal claim.

The existing fidelity branch is out of scope. It couples the RGB handoff to `finish_adaptive.enabled = false` (`deepclean-worker/worker.py:389-467`) and would stack a finisher-policy change with the camera retune.

## 2. Corrected baseline and prediction

The all-32 O1→O2 mean of `0.1764` remains descriptive evidence only (`ATTRIBUTION_REPORT.md:16-33`). It is not an acceptance baseline.

The valid historical baseline is Config A on the same IMG-5/6/9/11 subset and the same two seeds that will carry the absolute gate. It is derived from the job mapping in `LAB_PILOT_REPORT.md:67-98` and the corresponding frozen `retrieval-checkpoints/attr-logs/<job_id>.txt` O1→O2 losses:

| Image | `lab-ctla1` | `lab-ctla2` | Two-seed mean |
|---|---:|---:|---:|
| IMG-5 | 0.1131 | 0.0916 | 0.10235 |
| IMG-6 | 0.1630 | 0.1713 | 0.16715 |
| IMG-9 | 0.2894 | 0.2892 | 0.28930 |
| IMG-11 | 0.2776 | 0.2697 | 0.27365 |
| **Same-subset Config A mean (n=8)** |  |  | **0.2081125** |

The derived 25% reduction cutoff is `0.2081125 × 0.75 = 0.156084375`. Because the archived per-cell transition losses are reported to four decimals, the operational pre-registered gate is **candidate mean ≤0.1561** on those same eight cells; `0.1560844` is retained only as the arithmetic audit value. Both values must be copied into the round ledger before first light and may not be recomputed after candidate pixels are viewed.

Prediction — **labeled estimate**:

- Camera-only OR→O2 mean loss falls by 25–40% versus paired B.
- O5 EATR improves by 0.04–0.07 absolute; O5 HFTR_H1 improves by 8–15% relative in the locked texture ROIs.
- The O5 edge-width gap to O0 closes by 15–35%.
- Smooth-region luma/chroma RMS changes by <5%; median real-vendor score movement is no worse than +0.05 absolute, with no verdict-category regression.

## 3. Implementation specification for the future builder

### 3.1 Lab identity and request path

The experiment must never present C as Config A.

1. In `supabase/functions/_shared/settingsIdentity.ts`, add optional `opticsPsfScale` to `RemintSettings`. Refactor the frozen tuple predicate so Config A/1A/2B/3C require the scale to be absent or `1.00`. Add an exact 4D-CAM-1 predicate requiring the Config A tuple, default codec, and `opticsPsfScale === 0.50`.
2. Add a lab-only `4d-cam-1` preset for `/relab`; do not expose the control in `src/RemintApp.tsx` or any production-facing preset surface. `buildSettingsCode` must emit `SEQ-CAM1-<hash>` for the exact candidate. `configIdentity` must return `{ label: "CUSTOM", key: <full candidate settings code> }`; no schema migration or new frozen config label is authorized.
3. Preserve all four incumbent settings-code golden strings byte-for-byte. Baseline B omits `opticsPsfScale`, so its canonical JSON and `SEQ-CFA-*` code remain unchanged. Explicit `1.00` may execute as baseline in a worker harness, but `/relab` must omit it from the B request.
4. Permit `CUSTOM` in `src/RelabApp.tsx` only when the exact 4D-CAM-1 predicate passes and a valid locked lab seed is present. Regrade/reconstruction must restore the exact candidate tuple; it must not fall back to whatever preset happens to be selected in the UI (`src/RelabApp.tsx:488-539,758,1135-1146`).
5. Create a new fixed-corpus experiment whose `config_set` permits `A` and the two exact seed-specific `SEQ-CAM1-*` keys. Do not permit the generic string `CUSTOM`, because `corpus-run-intent` accepts either label or key (`supabase/functions/corpus-run-intent/index.ts:31-58, configAllowed`).
6. Add `opticsPsfScale?: number` to `DsRemintV8_8Options` and serialize it as `optics_psf_scale` only in the V8.9/HD remint request (`src/lib/deepcleanClient.ts:86-101,278-325`).
7. In `dsRemintV8_9ExpertRefinement`, accept absence as `1.00` and an explicit candidate as exactly `0.50`. Any other supplied value must return a validation error, not clamp or silently default (`supabase/functions/create-deepclean-job/index.ts:1188-1210`). The V8.8 public contract remains unchanged.

Required identity tests in `supabase/functions/_shared/settings_identity_test.ts`:

- four existing frozen predicates and full settings-code goldens remain unchanged;
- absent and explicit `1.00` execute as baseline, but only absent produces the incumbent canonical code used by `/relab`;
- `0.50` matches only 4D-CAM-1, is labeled `CUSTOM`, and emits `SEQ-CAM1-*`;
- `0.49`, `0.60`, `0.75`, NaN, infinity, strings, and null are rejected at the request boundary;
- candidate reconstruction round-trips both locked seeds without losing the scale.

### 3.2 Worker pixel path

1. Add a worker default `optics_psf_scale = 1.00` and strict allowed set `{0.50, 1.00}` in `normalize_ds_remint_v8_8_settings`; include requested/executed scale in the engine report (`deepclean-worker/ds_remint_v8_8.py:114-173,183-199`). Invalid explicit values fail closed.
2. Pass that one value in the `coherent_camera` sub-settings for every call in `_v88_candidate` (`deepclean-worker/ds_remint_v8_8.py:409-440`). Do not precompute independent green and red/blue overrides.
3. Add `psf_scale` to coherent-camera normalization with default `1.00`. After `_modulate_scene` has applied the existing optional `0.92` texture/architecture adjustment, compute `effective_psf_g = cfg["psf_g"] × psf_scale` and `effective_psf_rb = cfg["psf_rb"] × psf_scale` at the call site (`deepclean-worker/coherent_camera.py:158-192,341-355`). Pass only those effective radii to `_per_channel_psf`.
4. Report `base_psf_g`, `base_psf_rb`, any scene multiplier, `psf_scale`, `effective_psf_g`, and `effective_psf_rb` per attempted rung. No other coherent-camera field may differ between paired fixed-rung calls.

Expected unmodulated candidate radii are light `0.125/0.150`, balanced `0.160/0.200`, and deep `0.200/0.250` for G/RB. For edge-dense balanced scenes, the existing `0.92` scene adjustment happens first, yielding `0.1472/0.1840`. These are derived values, not new tuneable parameters.

### 3.3 Auxiliary OR checkpoint — strict-whitelist trap closed

`O2_precamera.png` is a legacy-misleading filename: it is currently written after the selected camera candidate (`deepclean-worker/ds_remint_v8_8.py:287-333`). Do not rename it during this round.

Capture `OR_postresample.png` from `reference = base` immediately after the single resample and before the camera ladder (`deepclean-worker/ds_remint_v8_8.py:248-263`), but implement it through a separate auxiliary contract:

- `EXPECTED_CHECKPOINTS` in `deepclean-worker/tools/checkpoint_capture.py:11-18` must remain byte-for-byte unchanged.
- `save_checkpoint` and `build_checkpoint_manifest` remain the strict O0–O5 contract. `OR_postresample.png` must never be passed to `save_checkpoint`; that function rejects unexpected names (`checkpoint_capture.py:35-40`).
- Add a separate explicit auxiliary whitelist/writer/manifest, with path safety and decoded-pixel SHA-256 identical to the main helper. Report it under `report.auxiliary_checkpoints`, never append an auxiliary absence/error to the main O0–O5 error list.
- Non-lab jobs write no auxiliary files. New-round lab jobs require auxiliary status `captured`, one file named exactly `OR_postresample.png`, and `errors: []` at the protocol layer. Legacy jobs without OR remain valid and keep `checkpoints.status = captured`.
- Add a new analysis helper rather than modifying frozen `checkpoint_attribution.py` at `b71ed99`. Define camera-only loss as `max(1 − EATR(O2|OR), 1 − HFTR_H1(O2|OR), 0)` on the identical lattice.

## 4. Build-time proof gates

No experimental cell may run until all gates below pass and the master engineer records the evidence.

1. `git diff b71ed99 -- deepclean-worker/tools/checkpoint_attribution.py` is empty; its existing 7/7 diagnostic harness remains green.
2. The exact tuple `EXPECTED_CHECKPOINTS` is unchanged. New tests prove a missing auxiliary does not flip a legacy/main O0–O5 manifest to error, while a 4D-CAM round rejects that cell at the protocol layer.
3. Baseline with scale absent produces the existing Config A canonical JSON/settings code. The same fixed OR input, creator, seed, rung, and hardware produces an exact O2 pixel hash versus the incumbent path. If the documented same-hardware determinism allowance is needed, RMS must be ≤0.1 LSB and max absolute error ≤1; different hardware requires an exact match (`deepclean-worker/tools/checkpoint_capture.py:104-128`).
4. For each fixed rung, B and C reports differ only in requested/effective PSF scale/radii, timing, and pixel-derived metrics/hashes. RNG seeds, other normalized settings, and input OR hash are equal.
5. Candidate O2 must differ from B on a non-constant fixture, proving the scalar is live. Scale `1.00` and absence must be pixel-identical.
6. Request-boundary tests, shared identity tests, auxiliary checkpoint tests, worker camera tests, `npm run check`, and `npm run build` all pass. Any unrelated failing pre-existing check is documented before the diff and may not be waived silently.

Implementation scope may include only the files needed for the exact lab setting, strict validation/identity, camera scalar, auxiliary capture, and their tests. Changes to wash, lattice, codec, finisher, final encoding, detection thresholds/providers, source transfer, database constraints, production UI, or the frozen attribution tool reject the build before image testing.

## 5. Experimental protocol

### 5.1 Locked cells and seeds

Run 34 MOCK screening cells on Fixed corpus v1:

- all 11 images × B/C × `lab-ctla1` = 22 cells;
- six sentinels × B/C × `lab-ctla2` = 12 cells;
- total = 34 cells / 17 paired comparisons / 782 privacy credits / 34 DeepClean credits.

Locked sentinels:

- IMG-5 — attribution wash-damaged control;
- IMG-6 — historically easy-clear, same-resolution camera control;
- IMG-9 — mixed 1600px attribution case;
- IMG-11 — 2048px camera-stressed control;
- IMG-7 — smooth rendered wall/sky/light-gradient regression sentinel;
- IMG-8 — high-texture timber/decking/architecture gain sentinel.

IMG-7 and IMG-8 replace the content-blind IMG-10/IMG-8 fallback after a source-image visual pass. IMG-10 remains in the all-11 `lab-ctla1` screen.

Before execution, freeze a source-only ROI manifest for every image: protected architecture/product edges, smooth render/sky/gradients, and texture regions. Store coordinates, role, source image SHA-256, and manifest SHA-256. Do not select or move ROIs after outputs are visible.

Every cell requires O0–O5 captured, OR auxiliary captured, decoded-pixel hashes, requested and executed setting identities, selected camera rung, every effective radius, finisher selection, and empty errors. OR must hash identically between B/C for each image/seed pair. Missing provenance invalidates the pair and stops analysis; it does not authorize replacement with an unpaired cell.

Run one zero-grade fixed-rung OR→O2 replay per paired cell in addition to the live adaptive result. It uses the live selected rung recorded by B as the fixed rung for both arms. Report live end-to-end and fixed-rung results separately.

### 5.2 Pre-registered acceptance gates

Accept 4D-CAM-1 only if every gate passes:

1. **Identity/provenance:** all 17 OR hashes match within pairs; all B identities are A and all C identities are the exact `CUSTOM`/`SEQ-CAM1-*` tuple; no unmapped or missing checkpoint/report field exists.
2. **Camera-only effect:** paired mean fixed-rung OR→O2 loss falls by ≥25%. The paired live-adaptive mean must also improve; no image-level two-seed sentinel mean may worsen.
3. **Correct subset gate:** on IMG-5/6/9/11 × two seeds, C mean O1→O2 loss is ≤0.1561 (exact derived audit value `0.1560844`). The archived Config A reference is 0.2081125; the all-32 value 0.1764 is not used in this calculation.
4. **Delivered detail:** median O5 EATR gain is ≥0.04 absolute across 17 pairs, and median texture-ROI HFTR_H1 gain is ≥8% relative. At least five of the six sentinel image means must move in the predicted direction across both seeds.
5. **Protected/smooth safety:** protected architecture/product EATR may not regress >2% in any pair. Smooth-region luma or chroma RMS may not increase >5%; directional rho1 or rho2 may not rise >0.03 absolute.
6. **Edge behavior:** median O5 edge-width gap to O0 closes ≥10%. One confirmed zipper, color-alias, false-texture, demosaic-color, halo, or oversharpening failure on a protected edge rejects the round.
7. **Panel:** owner + two blinded reviewers score randomized B/C pairs and locked crops at 100% zoom using a frozen −2 to +2 candidate preference scale. Compute the three-reviewer mean for each pair, then the median of the 17 pair means; that median must be ≥+0.5. A recurring artifact is the same named artifact flagged by at least two reviewers on at least two images; any recurrence rejects.
8. **Real detection:** after gates 1–7 pass, every baseline-eligible sentinel must remain eligible at `ai ≤ 0.45`, `flux-family ≤ 0.30`, and `deepfake ≤ 0.10`. C may not receive a worse verdict category than B from either selected vendor, and each vendor's median adverse score movement must be ≤+0.05.

MOCK, objective metrics, and panel evidence may prune or reject; they cannot promote. Real grades are required before owner acceptance of this pixel-changing round.

### 5.3 Vendor budget

- Vendor 1: Hive g1.
- Vendor 2: owner must freeze either TruthScan or Sightengine, based on existing authenticated access, before any grade is requested.
- Grade six sentinels × B/C × two vendors on `lab-ctla1` = 24 calls, leaving 16 of the owner-authorized 40-call session cap.
- A suspected vendor anomaly may consume one paired repeat from the reserve; a confirmed regression rejects. No reserve call is spent without an anomaly note and owner authorization.
- If only one vendor is actually available, the leg is 6 × 2 × 1 = 12 calls and must be labeled single-vendor A/B. It must never be described as two-vendor validation or inflated to 24 by duplicate calls.

## 6. Stop, rollback, and handoff

Stop before the 34-cell round if any build-time proof gate fails. Stop before vendor grading if any screening or panel gate fails.

Failure of any pre-registered acceptance condition rejects `0.50` and restores the hash-verified V12.3 incumbent (`c569595`). One apparent vendor regression may be repeated once; confirmation rolls back immediately. Gross aliasing, double edges, halos, false texture, demosaic color, or protected-edge damage rolls back without a repeat. Rejection does not authorize another scale.

Passing this round authorizes only an owner decision on promotion; it does not authorize deployment. 4D-2A float/RGB handoff remains the next independent brief, followed by the already-approved 4D-1a H1/H2 source transfer at alpha `0.10`, H0 excluded. Neither follow-up may be included in this build or round.

The future builder returns an uncommitted build report containing the exact diff, changed-file list, settings-code goldens, test outputs, baseline/candidate hashes, and a declaration that no deploy/worker/volume/pod action occurred. The master engineer verifies line by line; the owner decides and performs any operational action.

READY_FOR_MASTER_ENGINEER_REVIEW
