# C8 4D Quality Proposal — Post-Attribution Revision

## 1. Dominant-offender prediction

**Measured result:** O1→O2 (≤1250px resample + coherent camera) is the dominant first target: mean loss **0.1764**, PRIMARY in **23/32** jobs, versus wash at 0.1517/12 jobs, tone-lock+stage-1 codec at 0.0538/4, Quality Finish at 0.0488/0, and final encode at ≈0 (`ATTRIBUTION_REPORT.md:16-33`). Seed counts are symmetric (11 vs 12 O1→O2 PRIMARY), reducing the chance that this ranking is a seed artifact (`ATTRIBUTION_REPORT.md:49-59`).

My sealed O0→O1 prediction is therefore **rejected**. Camera was underestimated; the fixed-buffer result also rejects “codec smallest”: q97/4:4:4 beats q92/4:2:0 in source-relative EATR in 32/32 replays, by +0.0303 before and +0.0181 after the fixed standard finisher (`ATTRIBUTION_REPORT.md:83-108`). The codec is smaller than the camera, but real.

The first round should target the **camera**, not source transfer. Native-reference analysis changes the top ranking in only 8/32 jobs, all >1250px; the report concludes resampling is a secondary ingredient within O1→O2 (`ATTRIBUTION_REPORT.md:61-66`). More decisively, the 800px IMG-6 path performs no delivery downsample yet names camera PRIMARY in 7/8 jobs (`ATTRIBUTION_REPORT.md:35-47`; resample code at `deepclean-worker/ds_remint_v8_8.py:248-260`). This meets the consultation routing rule “camera dominates → camera retune” (`C8_MASTER_PROMPT_4D_CONSULTATION.md:98-106`).

**Component-level prediction — ESTIMATE:** the optical PSF is the largest controllable contributor inside the camera stage. O1→O2 broadens mean edge width from 3.9px to 5.6px while H1 falls 0.886→0.722 and H2 remains higher at 0.904 (`ATTRIBUTION_REPORT.md:68-81`), a blur/MTF-shaped signature. The camera applies Gaussian per-channel PSF before CFA/demosaic (`deepclean-worker/coherent_camera.py:183-217`); balanced radii are 0.32 green and 0.40 red/blue, with all presets separately fixing cleanup, noise, denoise, and sharpening (`deepclean-worker/coherent_camera.py:59-94`). Checkpoints do not isolate those internal components, so PSF—not merely “camera”—remains a pre-registered hypothesis.

The measured sequence is therefore:

1. PRIMARY: one linked optical-PSF scalar.
2. Follow-up 1: float/RGB handoff only.
3. Follow-up 2: source-supported H1/H2 transfer for the image-dependent wash loss.

Quality Finish remains later work because it is moderate and never PRIMARY; no finisher change is included in these three rounds (`ATTRIBUTION_REPORT.md:110-119`).

## 2. 4D design

**PRIMARY — Round 4D-CAM-1: `optics_psf_scale` 1.00→0.50 only.**

Change specification:

- Introduce one scalar in `deepclean-worker/coherent_camera.py` that multiplies both `psf_g` and `psf_rb` immediately before `_per_channel_psf` (`deepclean-worker/coherent_camera.py:183-191`). Candidate = 0.50; baseline = 1.00. Scaling both radii with one scalar preserves the existing chroma-heavier G:R/B ratio.
- Thread that scalar through every light/balanced/deep camera invocation in `_v88_candidate` (`deepclean-worker/ds_remint_v8_8.py:409-440`). The selected rung, deep-degrade scale, residual cleanup, CFA/demosaic, shot/read noise, ISP denoise, tone, CA, vignette, sharpening, 1250px lattice, q92 stage-1 codec, strong/S1.25 finisher, and Q97 delivery remain frozen.
- Add a diagnostic `OR_postresample.png` immediately after the existing resample and before the camera (`deepclean-worker/ds_remint_v8_8.py:248-263`). OR is non-output instrumentation and must hash identically between paired arms. It makes OR→O2 the camera-only measurement.
- Record requested/executed PSF scale and per-rung effective radii. A baseline scale of 1.00 must reproduce V12.3 O2/O5 pixel hashes in the deterministic harness before experimental cells run.

**Expected effect — ESTIMATE:** halve-PSF recovers 25–40% of the paired camera-only loss; final EATR rises 0.04–0.07 absolute; final HFTR_H1 rises 8–15% relative; the O5 edge-width gap to O0 closes by 15–35%. Smooth-region RMS changes <5%; median real-vendor score movement stays within 0.05 absolute, with no verdict-category regression.

**Accept only if all conditions pass:**

1. Paired mean OR→O2 camera loss falls ≥25%; on the four attribution images, paired O1→O2 loss falls from the 0.1764 reference to ≤0.1323 without moving OR.
2. Final median EATR gains ≥0.04 absolute and texture-ROI HFTR_H1 gains ≥8% relative versus Config A. Protected architecture/product EATR may not regress >2% in any pair.
3. Median O5 edge-width gap to O0 closes ≥10%; smooth-region luma/chroma RMS may not increase >5%, and directional ρ1/ρ2 may not increase >0.03 absolute.
4. Blinded 100%-zoom panel improvement is ≥+0.5 median, with no recurring aliasing, zippering, false texture, demosaic color, halo, or “digital oversharpening” verdict.
5. Every real-grade baseline-eligible sentinel remains eligible at `ai ≤ 0.45`, `flux-family ≤ 0.30`, and `deepfake ≤ 0.10`; no baseline receives a worse verdict category (`EXPERT_TESTING_SYSTEM.md:77-80`).

This is one sealed level, not a ladder. If 0.50 fails, reject it; do not try 0.60/0.75 post hoc without a new brief.

**Staged follow-up 1 — Round 4D-2A: finisher input transport JPEG→RGB only.** Run only after 4D-CAM-1 is fully accepted.

Change specification:

- Keep generating the identical stage-1 JPEG for adaptive camera probes and fallback, but also request the existing post-tone-lock `_pre_encode_rgb` buffer (`deepclean-worker/ds_remint_v8_8.py:335-368`).
- Decouple RGB handoff from the `fidelity` preset. In the adaptive strong/standard candidate loop, feed `image=pre_encode_rgb` rather than `input_path=stage1 JPEG`, while keeping the same candidate presets, S1.25 overrides, detector thresholds, ordering, routing, QC, and final Q97 (`deepclean-worker/worker.py:389-432`, `:468-567`). The current fidelity branch cannot be made default unchanged because it couples handoff to a different finisher preset; that would stack variables.
- Capture the actual post-tone-lock RGB input and decoded-JPEG input hashes. Transport is the only output-affecting variable.

**Expected effect:** **MEASURED ANALOG** q97 instead of q92 gives +0.0181 EATR after a fixed standard finisher (`ATTRIBUTION_REPORT.md:83-94`). **ESTIMATE for float handoff under live strong/adaptive routing:** final EATR +0.015–0.030 absolute and HFTR_H1 +3–6% relative versus the accepted camera incumbent, with unchanged smooth residual and no detection-category movement.

**Acceptance threshold:** median final EATR gain ≥0.015, positive EATR movement in ≥90% of pairs, HFTR_H1 gain ≥3%, no protected/smooth metric regression, panel ≥+0.25 median, and the complete real detection gate passes. Despite lower risk than wash retuning, zero real vendor grades have tested this exact live handoff; it is **not** “zero-risk.”

**Staged follow-up 2 — Round 4D-1a: source-supported H1/H2 transfer, α=0.10; H0=0.** Run only after both prior rounds are accepted. It addresses the remaining image-dependent wash loss, not the first-round camera loss.

Change specification:

- After existing finish retries and before reference QC/O4 encoding (`deepclean-worker/quality_finish.py:1680-1730`), apply `candidate = remint + 0.10 × support × (H1_src_aligned + H2_src_aligned)` in luma only. H1/H2 use the attribution definitions (`deepclean-worker/tools/checkpoint_attribution.py:151-162`); H0 is excluded.
- Fixed support = bounded local alignment × orientation agreement × cross-scale persistence × remint-edge support × measured detail deficit × region permission. Fail closed on ambiguous alignment and exclude gradients, smooth paint/render, specular cores, bokeh/defocus, beam boundaries, and unsupported source-only edges.
- Capture pre/post-transfer O4 buffers and support coverage. α=0 must reproduce the accepted handoff incumbent. α is the only output variable.

**Expected effect — ESTIMATE:** on wash-primary images/ROIs, HFTR_H1/H2 improves 8–15% and EATR +0.02–0.05; globally, HFTR improves 3–7%. Wash-null controls change <1% in supported-band energy. Combined 4D-CAM-1 + 4D-2A + 4D-1a is expected to exceed +15% texture-ROI HFTR versus original Config A.

**Acceptance threshold:** wash-primary strata gain ≥8% HFTR, global median gains ≥3%, combined accepted stack gains ≥15% versus Config A, and wash-null controls change ≤1%. Protected/smooth, panel, alignment-artifact, and real detection gates from the primary round all apply. Otherwise roll back to the accepted 4D-2A incumbent. No α>0.10 and no H0 are authorized by this proposal.

## 3. Measurement protocol

**Evidence gate:** the checkpoint chain is complete: 198/198 file hashes and 192/192 ledger pixel hashes match; 32 grid jobs were analyzed after excluding two non-grid/superseded directories (`ATTRIBUTION_REPORT.md:7-14`). No additional attribution or vendor spending is required before writing the first build brief.

One reproducibility item remains: `ATTRIBUTION_REPORT.md:3-5` says a patched native+normalized attribution tool produced the report, but `git show --name-status 709100e` contains only `.gitignore` and `ATTRIBUTION_REPORT.md`; the corresponding `deepclean-worker/tools/checkpoint_attribution.py` patch is currently an uncommitted tracked-file modification. Before the build brief, the master engineer must preserve that exact tool revision by commit or recorded SHA-256. This does not invalidate the verified checkpoint hashes or tables, but commit `709100e` alone cannot reproduce them.

**Each round uses 34 zero-grade screening cells on Fixed corpus v1:**

- All 11 images × baseline/candidate × `lab-ctla1` = 22 cells.
- Six pre-registered sentinels × baseline/candidate × `lab-ctla2` = 12 cells.
- Total: 34 cells, 17 paired comparisons. Baseline is the immediate accepted incumbent; original Config A remains the cumulative reference.
- Sentinels are locked before execution: smooth rendered wall, brick/timber, foliage, product close-up, historically easy clear, and historically wash-damaged. They must include IMG-5, IMG-6, and IMG-11 so wash-heavy, same-resolution camera-heavy, and wash-null behavior remain represented (`ATTRIBUTION_REPORT.md:35-47`).
- Every cell requires O0–O5, exact auxiliary checkpoint(s) for that round, manifest hashes, executed rung/finisher/preset, setting identity, and `errors: []`. Any missing or unmapped provenance stops the round (`EXPERT_TESTING_SYSTEM.md:23-29`, `:60-75`, `:83-86`).

For the camera round, run a zero-grade fixed-rung OR→O2 replay alongside the end-to-end adaptive result. Adaptive rung changes are valid end-to-end effects of the single PSF variable, but only the fixed-rung replay may support a component-level MTF causal claim. For the handoff round, stage-1 camera probe bytes must hash equal across arms. For source transfer, pre-transfer O4 must hash equal across arms.

**Grade policy per round:** MOCK, metrics, and blinded panel may prune only. Real grades are required for every surviving pixel-changing candidate. Grade six sentinels × two arms × two vendors using the designated `lab-ctla1` outputs = **24 vendor grades**, leaving 16 of the 40-call session cap for authorized repeats. The `lab-ctla2` leg remains a seed-stability/quality control and is not real-graded in that session. No candidate becomes default on MOCK or panel evidence alone.

## 4. Risk & rollback

Camera risks are sharper Bayer zippering, color aliasing, noise becoming too crisp, loss of camera-like MTF, and detector regression. Handoff risks include changing finisher behavior and adaptive candidate selection; the fixed O2 replay proves codec sensitivity, but not the exact live post-tone float path. Detail-transfer risks are double edges, source JPEG/noise copying, and watermark/fingerprint reintroduction. Six-sentinel real grading controls detection risk but cannot prove universality across all 11 images; full-corpus metric/panel screening therefore remains mandatory.

**Exact rollback condition:** a round is accepted only if every pre-registered metric, panel, provenance, and real-detection gate passes. Failure of any one gate rejects the candidate and restores the immediate prior verified incumbent: V12.3 `c569595` for 4D-CAM-1, accepted camera for 4D-2A, and accepted handoff for 4D-1a. One apparent vendor regression may be repeated once from the 16-call reserve; confirmation triggers immediate rollback. Gross aliasing, double edges, halos, or protected-edge damage roll back without a repeat. A rejected round does not authorize an emergency parameter ladder.

Operational housekeeping is outside this design-only consultation. Pod termination, network-volume attachment, and worker scaling require owner/master-engineer execution and attestation; this proposal performs none of them.

## 5. Open questions for the owner

1. Do you approve `optics_psf_scale=0.50` as the sealed first camera value, with no same-round fallback level?
2. Which exact six fixed-corpus image IDs map to the six sentinel roles, beyond mandatory IMG-5/6/11?
3. Which two real vendors define the release gate, and do you authorize 24 grades plus a 16-call repeat reserve per surviving round?
4. Do you authorize 34 remint cells and their privacy/DeepClean credit cost per round?
5. Will the master engineer freeze the patched attribution-tool revision and separately attest that the retrieval pod is terminated, the volume is attached to `remint-v6`, and workers are scaled back up?

READY_FOR_MASTER_ENGINEER_REVIEW
