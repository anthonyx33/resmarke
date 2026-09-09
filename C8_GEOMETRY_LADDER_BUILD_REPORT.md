# C8 Geometry Ladder v4.2 — C88 Build Report (v4.4 resolution appended 2026-09-09)

- **Build date:** 2026-09-06 (Australia/Sydney)
- **Source base:** `e02c4904784b`
- **Status:** Phase-A implementation and offline contract gate PASS. No live leg, grading, deployment, or Phase-B preset was run or added.

## Delivered build

- Added the closed eight-cell Phase-A schema and presets: `geom-r0`, `geom-x0`, and `geom-r1`–`geom-r6`.
- Added a deterministic geometry module using one content-image `cv2.warpAffine` call for every `affine` arm. `geom-r0` stays on the incumbent resize path and does not call the transform.
- Preserved operation order: wash → incumbent Pillow LANCZOS cap resize → optional geometry → coherent camera → Quality Finish.
- Added strict camelCase and snake_case validators. Partial blocks, extra fields, arbitrary tuples, and conflicting `output_target` / `resize_target` requests fail closed at the shared edge contract and Python worker contract.
- Added `/relab` selectors for all eight arms with visible settings codes.
- Pinned `opencv-python-headless==4.10.0.84`, copied the new module into the worker image, and made its contract suite a fatal Docker build step.
- Left detector, wash, camera, finish algorithms, thresholds, and existing preset definitions unchanged.

## Frozen Phase-A settings codes

| Arm | Unseeded | `lab-ctla1` |
|---|---|---|
| `geom-r0` | `SEQ-G0-kanyynxeawvr` | `SEQ-G0-qocqnp2g2gfy` |
| `geom-x0` | `SEQ-GX0-hh2qppoqbnjq` | `SEQ-GX0-xtya3ir32ozw` |
| `geom-r1` | `SEQ-G1-e2tp35ik6kna` | `SEQ-G1-gexfjkrr2hlb` |
| `geom-r2` | `SEQ-G2-7pxk5lv72ee6` | `SEQ-G2-p3rwojlmzrov` |
| `geom-r3` | `SEQ-G3-xx7n6rnwqr3r` | `SEQ-G3-hdhzzbffurlt` |
| `geom-r4` | `SEQ-G4-4ozjt4hh6xd3` | `SEQ-G4-6qdn22oroob2` |
| `geom-r5` | `SEQ-G5-3dg2guf3xbub` | `SEQ-G5-dxcvkvndsy33` |
| `geom-r6` | `SEQ-G6-fbo7bz7ovtus` | `SEQ-G6-jzvg3zezpltk` |

The TypeScript suite is canonical for these goldens. Python reads the pinned JSON vectors and implements no settings-code hash.

Existing settings-code goldens remain unchanged, including Config A `SEQ-CFA-dtbnbygm5iao`.

## Numeric transform gate

Tests ran with OpenCV 4.10.0, Pillow 11.3.0, and NumPy 2.0.2. All matrices below are the float64 inverse matrices supplied with `WARP_INVERSE_MAP`.

| Fixture | Arm | Overscan `s` | Minimum source margin | Mask minimum |
|---|---:|---:|---:|---:|
| 1250×1250 | r3 / 0.6° | 1.0170322127124942 | 4.062043795620353 px | 255 |
| 1250×1250 | r4 / 1.2° | 1.0274058375584240 | 4.062043795620507 px | 255 |
| 1250×703 | r3 / 0.6° | 1.0304211402485680 | 4.034696530346992 px | 255 |
| 1250×703 | r4 / 1.2° | 1.0491007529479508 | 4.034696530347004 px | 255 |
| 703×1250 | r3 / 0.6° | 1.0304211402485680 | 4.034696530346992 px | 255 |
| 703×1250 | r4 / 1.2° | 1.0491007529479508 | 4.034696530347052 px | 255 |

All six masks are exactly 255 at every pixel and all analytic margins exceed the frozen Lanczos4 support `L=4`.

Pinned inverse matrices:

```text
1250×1250 r3 [[0.9831991129352631,-0.010296413412822815,16.92226414823605],[0.010296413412822815,0.9831991129352631,4.062043795620388]]
1250×1250 r4 [[0.973111741170141,-0.020383785177944393,29.521391482873053],[0.020383785177944393,0.973111741170141,4.062043795620519]]
1250×703  r3 [[0.9704237717059025,-0.010162625461779335,22.03743610674847],[0.010162625461779335,0.9704237717059025,4.034696530347028]]
1250×703  r4 [[0.9529882431839676,-0.019962257985717,36.3655946845988],[0.019962257985717,0.9529882431839676,4.034696530347004]]
703×1250  r3 [[0.9704237717059025,-0.010162625461779335,16.72781573210946],[0.010162625461779335,0.9704237717059025,14.90327303257928]]
703×1250  r4 [[0.9529882431839676,-0.019962257985717,28.967556754507587],[0.019962257985717,0.9529882431839676,22.352089578625534]]
```

## Replicated-border diagnostic

Widths are edge-normal runs from the exact all-255/constant-zero diagnostic warp. Corner overlap is excluded by considering scanlines whose orthogonal centre pixel is unaffected; the maximum eligible run is reported per edge.

| Fixture | Arm | Left | Right | Top | Bottom | Gate |
|---|---:|---:|---:|---:|---:|---|
| 1250×1250 | r5 | 0 | 1 | 0 | 1 | PASS (≤6 H/V) |
| 1250×1250 | r6 | 7 | 8 | 0 | 1 | PASS (≤14 H, ≤6 V) |
| 1250×703 | r5 | 0 | 1 | 0 | 1 | PASS |
| 1250×703 | r6 | 7 | 8 | 0 | 1 | PASS |
| 703×1250 | r5 | 0 | 1 | 0 | 1 | PASS |
| 703×1250 | r6 | 4 | 5 | 0 | 1 | PASS |

## Identity and determinism gates

- Pinned small post-wash RGB fixture SHA-256: `51f7b3ec57be8ae386b3f3d5a4c0505743ffc0f01042f629aa95a2a4d75535a4`.
- Pinned 1403×907 post-wash RGB fixture SHA-256: `e932131aad663d422ce72f83bd2989d27d24d5f2db22fc3e5a36daf8e6fd6238`.
- Incumbent Config A resize output, current Config A output, and `geom-r0` output are pixel- and JPEG-byte-identical on the large fixture; output is 1250×808.
- `geom-r0`: zero transform calls and unchanged image object/bytes.
- `geom-x0`: one identity affine call, unchanged dimensions, and pixel equality on the pinned fixture.
- Every affine arm: one content-image warp call, unchanged geometry-stage dimensions, and identical bytes across repeat runs on the same machine/build.

## Verification executed

| Command | Result |
|---|---|
| `npm test` | PASS — 4/4 |
| `npm run build` | PASS — TypeScript + Vite production build |
| `deno test --allow-read supabase/functions/_shared` | PASS — 18/18 |
| `deno check supabase/functions/create-deepclean-job/index.ts` | PASS |
| `python -m unittest tools/test_geometry_ladder.py` | PASS — 15/15 after v4.4 |
| `python -m py_compile geometry_ladder.py ds_remint_v8_8.py tools/test_geometry_ladder.py` | PASS |
| `git diff --check` | PASS |

The repository's full `deepclean-worker/build_gate.py` was not executable in the local host environment because that gate imports PyTorch and the host has no PyTorch installation. The Docker base image supplies PyTorch, and the geometry suite is now independently wired as a fatal Docker build step. No Docker image or GPU runtime was built in this commission.

## Frozen-spec observations requiring master review

These do not affect the eight Phase-A pixel transforms or their build tests, but they prevent claiming that all of v4.2 is mathematically closed:

1. **The 0.94 retained-area statement is not aspect-ratio safe.** The brief's cited square values are correct: r4 retains 0.9404953748824313 at 800×800 and 0.9473619595013648 at 1250×1250. Under the same registered definition (`1/s²` for a tilt-only arm), r4 at either 1250×703 or 703×1250 retains only **0.9085850833907536**, below 0.94. Therefore r4 is pre-ineligible on these rectangular fixtures even though §7 says the floor was calibrated so r4 passes at all corpus sizes.
2. **The future joint formula does not always provide the claimed 4 px analytic margin.** For the frozen general rule at 1250×703 with `tilt=0.6` plus `shift_squash`, computed margin is **3.9576494565 px**; at `tilt=1.2` it is **3.8833833080 px**. The Phase-A allowlists correctly reject these joint tuples, so the current build is unaffected. The second C88 Phase-B build must not add J1–J3 until an amendment corrects and re-fixtures the general formula.

## v4.3 master resolution (appended 2026-09-09)

The v4.3 master brief retired both observations above:

1. **Retained-area floor 0.94 → 0.90 (aspect-safe).** The v4.3 §7 gate is
   `retained ≥ 0.90`, calibrated so geom-r4 passes at all corpus sizes:
   0.9405 at 800², 0.9474 at 1250², 0.9086 on 1250×703/703×1250. The 0.94
   floor pre-rejects r4 on rectangular inputs by construction and is
   retired. Pinned by
   `test_retained_area_r4_passes_the_aspect_safe_floor_on_rectangles`.
2. **Joint margin formula → per-corner construction.** v4.3 §5 replaces the
   v4.2 analytic denominator formula with the per-corner margin scale
   (`s = max_k max(|q_k.x|/(half.x−L), |q_k.y|/(half.y−L))`, floored at
   1.0, ×(1+1e-4)), which guarantees margin ≥ L by construction. Ported
   into `geometry_ladder.overscan_scale`. Verified: all six pinned Phase-A
   matrices reproduce numerically within tolerance (atol 1e-12); all twelve
   prospective joint fixtures (1250², 1250×703, 703×1250 × {0.6°, 1.2°} ×
   {shift, shift_squash}) hold margin ≥ 4.005 with a clean 255 diagnostic
   mask. Pinned by `test_prospective_joint_tuples_keep_the_lanczos_margin`.
   The J1–J3 boundary extension remains a separate Phase-B build; the
   transform construction it must reuse is now the v4.3 one.

### v4.4 addendum (2026-09-09): v4.3 per-corner formula superseded

C88 reproduced the ported tests and proved the v4.3 §5 form
`s ≥ |B·p_k + t|/(half − L)` is algebraically inconsistent with the
executed inverse `p_src = B·(p_dst − c)/s + c + t`: the source-space
shift `t` is NOT divided by `s`, so the v4.3 form under-scales when
t ≠ 0. Measured source margins below L = 4 on the permitted resize
caps: 450×800 @1.2° shift_squash 3.9891 px; 450×800 @1.2° shift
3.9945 px; 562×1000 @1.2° shift_squash 3.9966 px; 450×800 @0.6°
shift_squash 3.9974 px (the 1+1e-4 safety factor masks this on the
1250-based fixtures). The v4.4 conservative construction
(`s = max(1, |v_k|/den)` with `den = half − L − |t|`) holds margin
≥ 4.022 px on all 36 joint fixtures (3 caps × 3 orientations × 2
angles × 2 warps). Phase A is numerically unchanged: pinned matrices
reproduce within 1e-12 tolerance — the earlier "bit-exact" wording is
retired; that is numerical equivalence, not byte equality. Phase B
remains blocked until the second build; the general construction it
must reuse is now the v4.4 one. Pinned by
`test_prospective_joint_tuples_keep_the_lanczos_margin_all_caps` and
`test_v43_joint_formula_underscales_on_small_portrait_regression`.

## Handoff boundary

Phase A remains a master-verification handoff. This report does not
authorize deployment or the 99-cell operator leg. Phase B remains a
separate build and is no longer held by the joint-formula observation: the
general construction is frozen and verified at code level; the Phase-B
addendum may only select tuples and codes.
