# Vacuum task — EIGHTH iteration (V8): the paired-corpus pivot — Config A cleared walls but fails real content; kill the fingerprint swap first, then kill the grain, then lock the systemization

## The task, in a vacuum

You designed the finisher through seven iterations. V7 assumed detection was
settled: Config A cleared 3/3 rendered walls on both graders, so V7 was
quality-only. The new paired corpus data — 12 real product-photo pairs with
Config A payloads, settings-coded filenames, and an explicit per-image
OG→remint mapping — overturns that premise on the harder content class:

- Scoreboard on 11 recorded remints: **1 CLEAR** (0.5%), **3 near-clear**
  (8.9\*, 11.0, 11.5), **1 borderline** (24.9), **6 FAIL** (51.2, 83.2, 91.1,
  96.3, 99.1, 99.9).
- The dominant failure mode is **fingerprint SWAP**: the residual source
  families after remint (wan / flux / kling / SD / other) are DISJOINT from
  the OG families (gemini / ernie / imagen4) in 8/11 rows. The stage-one
  Qwen wash re-stamps when it fails.
- The operator's quality verdict is unchanged and now confirmed on real
  content at 100% zoom: *"SUCH POOR QUALITY REMINT. THIS IS NOT
  ACCEPTABLE."*

V8 therefore has three tracks and one meta-demand from the operator: as an
expert team, produce the **best effective optimisation and systemisation for
optimal performance, results and quality**.

- **Track F** (re-opened, PRIMARY): detection on the real-photo class.
- **Track Q**: the grain/pixelation complaint on night content.
- **Track S**: systemization — corpus registry, grading ledger, protocol
  laws — so no future batch is ever un-attributable again.

## The new ground truth — full paired expert test (2026-08-24, Config A payloads)

**Settings attestation:** the operator states every remint used WAVL-v1
Config A (the `isConfigA` predicate in `src/lib/settingsCode.ts`: sequence ·
qwen wash · strength deep · adaptive · preset strong · native scale ·
material clean ON · overrides dither 1.0 / smoothness 1.25 / sharpen 1.0).
OG filenames: `CFA-REAL-CREATOR-IMG-X`. Remint filenames: `SEQ-CFA-x`.
Treat this table as Config-A-requested data on the hard class.

| OG | OG AI% (G1) | OG top sources (G1) | OG G2 | remint file | remint AI% (G1) | remint top sources (G1) | remint G2 | Δ | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 12 | 99.9 | ernie 84.7 / qwen 3.4 / flux 2.4 | 97% Synthetic HIGH | — | — | — | — | — | remint not recorded |
| 11 | 99.2 | ernie 55.7 / qwen 21.8 / SDXL 7.0 | missing | F1 | 99.1 | wan 70.3 / flux 9.2 / SDXL 3.8 | missing | −0.1 | FAIL (no-op) |
| 10 | 99.9 | gemini3 99.3 | missing | F2 | 0.5 | firefly 0.2 | missing | −99.4 | CLEAR |
| 9 | 99.9 | gemini3 50.1 / ernie 49.7 | missing | F3 | 11.0 | gemini3 3.7 / flux 2.5 | missing | −88.9 | NEAR-CLEAR |
| 8 | 99.9 | gemini3 99.3 | missing | F4 | 24.9 | flux 22.3 / 4o 1.9 / qwen 1.2 | missing | −75.0 | BORDERLINE |
| 7 | 99.9 | gemini3 99.1 | missing | F11 | 11.5 | flux 15.5 | missing | −88.4 | NEAR-CLEAR |
| 6 | 99.9 | gemini3 99.3 | missing | F5 | 51.2 | flux 74.4 | missing | −48.7 | FAIL |
| 5 | 99.9 | ernie 63.7 / gemini3 36.2 | missing | F6 | 83.2 | wan 78.0 / flux 10.1 | missing | −16.7 | FAIL |
| 4 | 99.9 | gemini 70.4 / 4o 11.2 / imagen4 7.1 | missing | F7 | 91.1 | flux 35.4 / kling 28.1 / zimage 5.2 | missing | −8.8 | FAIL |
| 3 | 99.9 | gemini 91.7 / imagen4 5.0 | missing | F8 | 99.9 | SD 73.5 / kling 19.6 / wan 2.5 | missing | 0 | FAIL (pure swap) |
| 2 | 99.9 | gemini3 65.0 / 4o 22.1 / imagen4 8.1 | missing | F9 | 96.3 | other 35.3 / kling 16.7 / SD 13.1 | missing | −3.6 | FAIL |
| 1 | 99.9 | imagen4 98.2 | missing | F10 | 8.9\* | ernie 37.5 / flux2 9.2 / bria 7.9 | missing | −91.0 | NEAR-CLEAR\* |

(\* F10 is internally inconsistent: headline "8.9%" but the breakdown block
reports "AI-Generated 78.9%". Re-grade before any routing decision uses this
row. — F8 is a pure fingerprint swap with ZERO delta: the remint is as
stamped as the source, just by SD/kling instead of gemini.)

**Residual-family census (11 remints):** wan-dominant 2 (F1, F6) · flux-
dominant 4 (F4, F11, F5, F7) · kling co-dominant 3 (F7, F8, F9) · SD
dominant/co 2 (F8, F9) · "other" dominant 1 (F9) · ernie residual 1 (F10) ·
firefly 1 (F2, the only clean wash outcome) · gemini3 residual 1 (F3, under
the 11% total).

**Content class (the 22 attached images):** night/twilight exterior lighting
product photography — bollard path lights, wall-wash scallop lights on
rendered/brick walls, fence downlights, solar spot lights on foliage, deep
blue twilight skies, glowing interior windows. This is the beta content
class. Harder than the rendered-wall set.

## Config 1A cross-wash test (2026-08-24, WAVL-v1 Config 1A — the toggle preset)

The operator ran the SAME 12 pairs through the new Config 1A preset (every
Config A lever unchanged, ONE variable moved: `wash_model` qwen →
qwen+zimage). G1 graded; G2 still missing. Side-by-side:

| OG | OG AI% | Config A | A residual | Config 1A | 1A residual | head-to-head |
|---|---|---|---|---|---|---|
| 11 | 99.2 | 99.1 | wan 70.3 | 97.3 | ernie 58.1 / imagen4 21.8 | 1A (marginal, both fail) |
| 10 | 99.9 | 0.5 | firefly 0.2 | 1.1 | gemini3 0.9 | A (both clear) |
| 9 | 99.9 | 11.0 | gemini3 3.7 / flux 2.5 | 83.9 | gemini3 93.5 | A — 1A CATASTROPHIC |
| 8 | 99.9 | 24.9 | flux 22.3 | 67.5\* | flux 33.4 / 4o 16.1 / kling 6.5 | A (\* same "24.9" headline cache appears in BOTH tests) |
| 7 | 99.9 | 11.5 | flux 15.5 | 19.0 | flux 23.9 | A |
| 6 | 99.9 | 51.2 | flux 74.4 | 15.5 | flux 23.6 | 1A — flips FAIL→border |
| 5 | 99.9 | 83.2 | wan 78.0 | 12.3 | gemini3 5.5 / flux 5.4 | 1A — flips FAIL→near |
| 4 | 99.9 | 91.1 | flux 35.4 / kling 28.1 | 99.9 | gemini 55 / kling 21.6 | A (both fail) |
| 3 | 99.9 | 99.9 | SD 73.5 / kling 19.6 | 99.9 | stablecascade 64.6 / SD 18.7 | tie — both pure swap |
| 2 | 99.9 | 96.3 | other 35.3 / kling 16.7 | 82.3 | kling 41.9 / other 13.3 | 1A (both fail) |
| 1 | 99.9 | 8.9\* | ernie 37.5 | 99.6 | ernie 80.6 | A — 1A CATASTROPHIC |

Scoreboards: **Config A** 2 clear / 2 near / 1 border / 6 fail (F10's 8.9\*
is now strongly suspected false — its 1A sibling reads 99.6 and the "78.9"
breakdown matches). **Config 1A** 1 clear / 1 near / 2 border / 7 fail.
Head-to-head: A wins 6 pairs, 1A wins 4, 1 tie. **Config A remains the
better single default — do NOT promote Config 1A.**

The mechanism (both washes dissected):

- **qwen (Config A) is a RELIABLE breaker, poor de-stamper.** Its failures
always carry a NEW family (wan/flux/kling/SD) — the source fingerprint is
gone, but a fresh detectable one replaces it.
- **qwen+zimage (Config 1A) is an UNRELIABLE breaker.** Where it fails hard
(#9: gemini3 93.5, #1: ernie 80.6, #11: ernie 58.1) the SOURCE fingerprint
survives nearly intact — the zimage component dilutes the wash. Where it
wins (#6, #5) it does what qwen could not. Wash efficacy is per-CONTENT,
not per-source.
- **Oracle (pick the better wash per image):** 2 clear / 3 near / 2 border /
4 fail — it rescues #5 and #6 from the FAIL column. Probe-routed wash
selection is therefore PROVEN as the architecture (ROUTING_V1), not
hypothetical.
- **Wash-proof rows:** #11, #3, #4, #2 fail ≥82% under BOTH washes. Four
images need the non-generative escape hatch (no regen → no re-stamp) or
manual QA — no wash variant will fix them.
- **F4 conflict repeat:** the same "24.9%" headline appears in both tests
while the breakdown says 67.5% — a grader-UI cache artifact. Conflicts
must auto-trigger re-grade (hardened L3).

**Quality verdict (unchanged and now measured):** the Config 1A outputs are
"slightly darker and lower resolution than the first set" — the wash swap
does nothing for the 360p complaint. The quality gap is born upstream of
the finisher: HD source → single-Lanczos ≤1250px → q92 4:2:0 (≈84–96% of
pixels discarded) → 1536-capped regen → finisher strong + S1.25 on a tiny
file. The only fix with real magnitude is the stage-one lattice; the
finisher cannot restore discarded detail (the V4 2000px lesson stands:
lattice changes are detection-coupled and need a full-registry detector
A/B).

## Audit of V7 — what the new data and a code read correct

1. **V7's central premise is false for the beta class.** "Detection is
   SOLVED" held only for the 3 rendered walls. Config A on real content:
   2/11 clear-or-better under a strict reading. V7's Track Q ("finisher-only
   changes on top of Config A") can no longer be the whole plan — Track F
   is now the critical path.
2. **V7's settings assumption was wrong.** V7 said the Aug-24 batch "ran
   the round-E defaults". Operator attestation + `SEQ-CFA-*` filenames say
   Config A. The corrected reading matters: Config A's real-world
   performance is known to be mostly-fail, and V7's mandatory R0 has
   effectively been answered for this class: **Config A does not
   generalize.**
3. **Requested ≠ executed (code-audited in the worker).** Config A requests
   `strength: deep` + `engineMode: adaptive`. But the frozen V8.9 engine's
   adaptive ladder is `["light", "balanced"]` — **deep is retired from the
   adaptive ladder** (`ds_remint_v8_8.py`): `strength` only takes effect in
   template mode. So the batch almost certainly never exercised the deep
   rung that cleared the brick wall in rounds C/G. Additionally, the
   sequence path's adaptive finish probes `strong` vs `standard` and picks
   per-image with the internal detector — so even the finish preset is
   decided by an internal grader whose sensitivity on this class is
   unproven. **The settings-code filename proves what was REQUESTED, not
   what EXECUTED.** Every corpus row must archive the worker report
   (`attempts[]`, `strength` per rung, `finish_adaptive`, `detector_gate`)
   next to the filename.
4. **The V7-known client defect is still open.** `materialClean` exists in
   `QualityFinishOptions` (`src/lib/deepcleanClient.ts`) but is still
   DROPPED by both serializers (`quality_finish` and
   `ds_remint_v8_9_hd.quality_finish` only emit preset/scale/overrides).
   The M1 vs M0 wall A/B still cannot run through the UI. Fix before any
   matrix row that touches the wall toggle.
5. **The internal ship-gate is more lenient than the external protocol.**
   The frozen source-aware gate (ai ≤ 0.45 AND flux-family ≤ 0.30) would
   ship F4 (flux 22.3) and all near-clears — yet the two-vendor protocol
   classifies F4 as BORDERLINE. The internal detector's verdicts on night
   content must be calibrated against the external vendors before the
   internal gate is trusted as a routing signal on this class.
6. **Data gaps that block conclusions:** G2 (the second grader) is missing
   for 11/12 pairs; pair 12 has no remint grade; F10 conflicts internally.
   None of these can be answered by code — they are protocol failures the
   corpus system below exists to prevent.

## Where the system stands (unchanged from V7 except where corrected above)

- **Stage one** (frozen V8.9 sequence: Qwen wash → single resample → coherent
  camera → gate → q92 4:2:0): code frozen. Runtime parameters only:
  `wash_model` (qwen | zimage | qwen+zimage), `zimage_denoise`,
  `route_by_baseline`, `strength` (template only), `deep_degrade_scale`,
  `color_restore`, `output_target`, jpeg settings.
- **Quality finisher** (non-generative, deterministic, CPU-only, one Q97
  4:4:4 encode): decode → JPEG cleanup → material mask → region suppression
  → case-B guard → chroma repair → Mobile Clean wall branch (V5) → enlarge →
  decorrelation → SNR sharpen → Final Polish (V6: 3-scale à-trous soft
  shrinkage, structure-gated) → adaptive dither → 8-bit → Q97 4:4:4 → QC.
- V6 constants: `POLISH_G_MIN=(0.40,0.55,0.75)`, `POLISH_TAU=(0.004,0.007,
  0.010)`, `WALL_DITHER_Y=0.13/255`, `WALL_DITHER_C=0.04/255`, wall RMS
  targets bright 0.32 / dark 0.55 LSB, chroma 0.08 LSB, polish structure
  gate P>0.75 → gain ≥ 0.9.
- Settings-code scheme (`src/lib/settingsCode.ts`): `SEQ-CFA-<hash>` = exact
  Config A payload; otherwise `SEQ-{CON|STD|STR|FID}-{scale}-{M0|M1}-<hash>`.
- Harness pattern (JSONL ledgers) exists in `deepclean-worker/tools/`.

## Systemization — Protocol Lock v2 (applies to every future run, no exceptions)

The Aug-24 unrecorded-settings failure must be impossible by construction.
The operator's demand is systemization, so these are LAWS, not suggestions:

- **L1 — Settings-code law.** No export without a settings-code filename;
  no grade recorded without the filename attached to the row.
- **L2 — Executed-not-requested law.** Every corpus export archives its
  worker report (attempts, rung strengths, wash model, finish_adaptive,
  detector_gate, routing decision block). Filename alone is insufficient
  provenance.
- **L3 — Paired law.** Every batch grades OG + remint on the SAME two
  vendors, same day, per-image mapping, screenshots/JSON archived. Δ is the
  primary metric; absolute scores are noise between vendors.
- **L4 — Corpus law.** All experiments grade on the fixed 20-image registry
  (12 SOLVARIA pairs + 3 rendered walls + 5 real photos). OG baselines are
  recorded once and reused forever. No ad-hoc images enter grading.
- **L5 — Decision-provenance law.** Every routing decision (wash variant,
  ladder rung, non-generative re-route, manual-QA flag) is recorded in the
  worker report as a `routing_decision` block carrying the rule version
  (`ROUTING_V1`, `ROUTING_V2`, …). Any grade anomaly can be blamed on the
  exact rule version that produced it.
- **L6 — QA law.** Borderline outputs (ai 0.25–0.45 / flux-family
  0.15–0.30) are flagged for manual QA and never shipped silently.
- **L7 — Rubric law.** Every batch carries the human 100%-zoom rubric:
  grain visibility, edge crispness, banding, chroma blotch, "premium or
  not" 1–5. The operator's conversion verdict is a first-class metric, not
  an anecdote.

## V8 split-test matrix — run these FIRST, fill in the table, then answer

Every row grades on the registry (L4), paired (L3), both vendors (L3).
R0 must be completed before any V8 design decision is final.

| Row | Change | Purpose | Data needed |
|---|---|---|---|
| R0a | Re-grade the 3 rendered walls on the LIVE endpoint (Config A payload) | Prove the wall all-clear survives the rebuilt endpoint | both graders + worker reports |
| R0b | Backfill: G2 on all 22 files; re-grade F10; grade pair 12's remint | Close the V8 data gaps | both vendors, screenshots |
| R0c | Dump the worker reports for the 12 jobs | Confirm which rungs EXECUTED (audit §3) | `attempts[]`, `finish_adaptive`, `detector_gate` |
| R1 | Wash-variant matrix on the 6 fails: qwen vs zimage vs qwen+zimage (strength balanced, same finish) | Identify the wash that does NOT re-stamp flux/wan/kling/SD | Δ per variant + residual family |
| R2 | Wash-only ablation (camera OFF) on 3 fails + 2 clears | Isolate the stamp source | post-wash probe grades |
| R3 | Camera-only ablation (wash OFF) on 3 fails + 2 clears | Isolate the camera's contribution | probe grades |
| R4 | Non-generative re-route on the 6 fails (camera_relife strong, then max_optimised) | Prove the escape hatch for un-washable images | Δ + quality rubric |
| R5 | Smoothing 1.0 vs 1.25 vs 1.5 on 3 clears + 3 fails (Track Q × F cross-check) | Does the smoothing multiplier reach the visible grain band, and does it move detection? | per-band RMS + grades |
| R6 | Wall toggle M0 vs M1 on the corpus (only after the client fix in audit §4) | Finally run the V5 A/B | material_wall QC + grades |
| R7 | Final Polish OFF on 3 corpus images | Isolate V6's quality contribution on night content | rubric + grades |
| R8 | Delivery 1.6× HD (2000px path) on the corpus | Answer the delivery-lattice question on the real class | rubric + grades |
| R9 | Dither sweep (0.7× / 1.0× / 1.3×) on brick/fence classes | Grain amplitude at the visible band | rubric + staircase index |
| R10 | V8 finisher build A/B: each new stage ON vs OFF on the full registry | Prove each V8 stage did its job | named QC gates + rubric + grades |

## The open questions (answer with exact numbers and pseudo-code)

**Track F — detection on the real class (PRIMARY):**

1. Why does Config A clear 3/3 rendered walls but 2/11 real photos? Separate
   the two hypotheses — (a) content difficulty (night scenes, speculars,
   light beams read generative), (b) wash re-stamp (fingerprint swap). Give
   the minimal ablation set (R2/R3 above) with the exact decision rule that
   assigns each failure to (a) or (b).
2. The wash-variant ladder. `wash_model` already supports
   `qwen | zimage | qwen+zimage` at runtime (code frozen — this is a
   ROUTING change, not a stage-one change). Specify the V8 adaptive ladder
   over (strength × wash_model) with exact thresholds, ordering, and the
   escalation rule when the post-wash probe reads a stamp-family dominant.
   Define the probe signal precisely: which source families count as
   "stamp" ({wan, flux, kling, stablediffusion, other}? anything disjoint
   from the OG top-3?), at what share threshold, on which detector.
3. The de-stamp decision surface. Give the routing table: OG probe value →
   route. Include at minimum: non-generative-only (camera_relife /
   max_optimised) for inputs that already read photographic; full regen for
   heavy stamps; the fallback when every wash variant re-stamps. Every
   branch must state what ships and what gets the manual-QA flag. (This
   becomes `ROUTING_V1` in the worker report.)
4. Fingerprint-swap quantification. Define the two report metrics —
   `swap_index` = share of the remint's AI% attributable to families ABSENT
   from the OG top-3, and `retention_index` = share attributable to families
   present in the OG top-3 — and compute them for the 11 rows (e.g., F8:
   swap 93.1%, retention 0% = pure swap). Which of the two metrics best
   predicts the Δ? Can the FINISHER measurably suppress a fresh post-regen
   stamp (structure-preserving), or is re-stamping irreducible without a
   stage-one debate? Give the diagnostic that separates the two.
5. The WAN-family night hypothesis. wan dominates the two twilight fails
   (F1, F6) and wan/kling/SD dominate the others. Is there a measurable
   spatial/spectral signature the finisher can target regionally (e.g.,
   correlated chroma noise in the dark-blue sky band, block artifacts on
   beam gradients)? Give the per-ROI metric targets and the experiment that
   proves or kills the hypothesis.
6. Internal-gate calibration. The internal detector is the routing signal
   in the sequence path, but its verdicts produced the 6 shipped fails.
   Design the calibration run: same files, internal detector vs both
   external vendors; what agreement level (exact statistic + threshold)
   must hold before the internal probe may drive routing on night content?

**Track Q — the grain/pixelation complaint on night content:**

7. The night-scene class treatment. The corpus content is: twilight sky
   gradients, warm scallop beams on rendered/brick walls and wooden fences,
   hard speculars on glass/filaments, dark foliage and mulch. Specify per
   region — (a) what may be smoothed and to what target, (b) what must NOT
   be touched (beam edges, falloff gradients, specular cores), (c) the mask
   definitions (extend `_material_smooth_confidence` or add a parallel
   region map), (d) the QC gates (named, with thresholds).
8. The grain budget at 1250px native delivery. Is the complaint amplitude,
   correlation, or scale? Give the three measurements that separate them
   (per-luma RMS in the 0–0.25 luma band, rho1 on sky, correlation length
   on smooth regions) and the target bands for "modern phone" grain:
   amplitude per luma band in LSB, rho1 ceiling, correlation-length ceiling
   (≤ 1.5px?), chroma amplitude.
9. Does the smoothing multiplier actually reach the visible grain? Config A
   runs smoothness 1.25× + wall ON and the output is STILL pixelated.
   Measure per-band RMS reduction (H0 vs H1 vs H2) against the multiplier
   and state where the visible grain lives and which stage must own it
   (stage-1 injection vs finisher suppression floor vs finisher dither).
10. Delivery lattice. The complaint is judged at 100% zoom on the delivered
    file. Native (≤1250px) vs 1.6× HD (2000px): use R8. If 1.6× regresses
    detection on any registry image, state the fallback (native default,
    1.6× behind the existing scale knob).
11. Preset collapse. Final preset set (2 or 3) and the measurable
    difference (a named QC metric with a threshold, e.g., ≥ 20% relative
    movement in TDR or residual RMS) a preset must produce to justify
    existing.
12. The V8 finisher algorithm spec. Concrete stage list with order relative
    to V5/V6 and the final encode, what each stage changes, what it must
    NOT touch, the new constants, and the named QC gates with thresholds
    that prove each stage did its job. Candidates to rank: night region
    map + per-region polish targets; per-luma (not binary bright/dark) wall
    RMS targets; correlation-length cap with a fine shrinkage retry; region
    adaptive dither amplitude; chroma-only beam-gradient decontour;
    specular exclusion masks. Flag the single largest expected visible win
    for the operator's complaint.
13. Auto-selection for beta. Fixed Config A default is now disproven on the
    real class. Design the beta default: routed config (baseline-aware
    ladder + wash-variant escalation) with settings-code provenance per
    image, or fixed config + manual multipliers. Give the exact rule and
    thresholds; state what must be true for a fixed default to return.

14. NEW (Config 1A data): the wash is a per-image coin flip — qwen swaps to
    wan/flux/kling/SD, qwen+zimage sometimes leaves the SOURCE fingerprint
    intact (gemini3 93.5 on #9, ernie 80.6 on #1). Design the pre-wash
    routing rule that predicts WHICH wash will win from the OG probe: what
    signal separates the rows where qwen wins (#9, #7, #1) from the rows
    where qwen+zimage wins (#6, #5)? If no OG-probe signal predicts it,
    state that honestly and make both-candidates-plus-probe (ROUTING_V1)
    the answer, with the exact cost of the extra wash pass.

15. NEW (Config 1A data): four rows fail ≥82% under BOTH washes (#11, #3,
    #4, #2) — the wash-proof class. Specify the detection rule that sends
    these to the non-generative profiles (camera_relife / max_optimised)
    and what QC/QA gates apply. Quantify the expected quality gain of
    skipping regen on these rows (the non-generative path does not resample
    or regenerate — it may preserve MORE of the source's HD crispness).

16. NEW (operator verdict): the quality gap is now measured as structural —
    HD crisp source → ≤1250px lattice → "360p" delivery, unchanged by wash
    choice. Specify the lattice experiment (output_target ∈ {1250, 1600,
    2000} × wash variants on the full registry, both vendors + the 100%
    zoom rubric) and state the exact acceptance criteria that would allow
    raising the default lattice without repeating V4's detection
    regression. This is the single highest-value experiment remaining.

**Top five concrete changes ranked** across all three tracks, each with its
trade-off and the minimal experiment (matrix row) to validate it. Flag the
single largest expected visible win for quality and the single largest
expected win for detection, separately.

## Constraints (frozen unless you argue with data)

- Stage-one CODE is frozen; Track F changes are runtime routing only
  (wash_model, ladder ordering, baseline routing, re-route to existing
  non-generative profiles). Any stage-one code change needs a detector A/B
  on the full registry.
- Finisher: non-generative, deterministic, CPU-only, one encode, sub-second
  at 1080p on the worker CPU (~340–670 ms today).
- Acceptance gate thresholds frozen (ai ≤ 0.45, flux-family ≤ 0.30,
  deepfake ≤ 0.10); new diagnostics may be added as report fields, but ship
  logic changes need owner sign-off.
- Knobs stay: a handful of presets + dither/smoothing/sharpen multipliers +
  wall toggle + delivery scale. No new user-facing knobs unless one earns
  its place with registry data.
- All new finisher stages ship as constants behind report metrics first;
  default-ON only after the R10 A/B.
- GPU budget unchanged: warm ComfyUI stage untouched; wash-variant sweeps
  reuse the existing warm workflow with different runtime parameters.

## What we do NOT need

Product, pricing, or business discussion. Pure technical system and design
recommendations. Return a build order an engineer can execute directly in
`deepclean-worker/quality_finish.py` + `deepclean-worker/worker.py` routing
(runtime-only) + `src/lib/deepcleanClient.ts` (the materialClean fix), plus
the exact split-test data you still need if the matrix above is
insufficient. Your answers feed §4 of `C8_MASTER_PROMPT_V8.md`.
