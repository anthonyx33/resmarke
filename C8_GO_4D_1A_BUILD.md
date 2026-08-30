# C88 — GO AHEAD: BUILD 4D-1a (H1/H2 SOURCE TRANSFER)

Role: builder (code access). This is the commissioned build.

## Read first (the authoritative spec)

`C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF_FINAL.md` — the SINGLE consolidated
specification. It overrides every earlier version (v1/v2/v3) and every prior
audit on any conflict. C88's final-pass audit recommended **ACCEPT FOR BUILD**
and is incorporated into that document verbatim. Build exactly what it says.

Do not re-litigate the architecture. If you find a genuine contradiction inside
the FINAL brief itself, stop and return it as a blocker list — do not choose a
reading silently.

## Scope allowlist (nothing else)

- `deepclean-worker/ds_remint_v8_8.py` — transfer stage after O2 capture,
  before tone-lock; `4d1a` flag normalization (strict boolean, fail-closed);
  report block `engine.transfer_4d_1a`.
- `deepclean-worker/tools/auxiliary_checkpoints.py` — whitelist gains exactly
  ONE name: `O2_transfer.png`. Nothing else in the contract changes.
- `deepclean-worker/worker.py` — lab-only plumbing for the flag; non-lab jobs
  unchanged.
- New transfer module (e.g. `deepclean-worker/transfer_4d_1a.py`) implementing
  §2.2–§2.5 of the FINAL brief exactly.
- New tools for proof/replay (e.g. `tools/transfer_4d_1a_harness.py`) — tools
  are new files only.
- `supabase/functions/_shared/settingsIdentity.ts` — preset id `4d-1a`, label
  `4D-1A — LAB · H1/H2 source transfer α=0.10`, marker `SEQ-4D1A-`,
  seed-dependent codes like CAM-1. Frozen predicates and goldens unchanged.
- `supabase/functions/create-deepclean-job/index.ts` — accept/validate the
  `4d1a` flag with the frozen boundary contract (mirror `optics_psf_scale`).
- `src/RelabApp.tsx` + `src/lib/deepcleanClient.ts` — preset entry + flag
  serialization, exactly like 4D-CAM-1.

## Hard rules (unchanged)

- **No commit. No push. No deploy. No RunPod or Supabase action. No grading.
  No cell run.** Return an uncommitted build report only.
- Frozen files must be byte-for-byte zero-diff:
  `coherent_camera.py`, `checkpoint_attribution.py`, `camera_only_replay.py`,
  `checkpoint_capture.py` (including `EXPECTED_CHECKPOINTS`),
  `quality_finish.py`.
- Camera, finisher, wash, wash-combos, lattice, ROI manifest: untouched.
- The vendor adapter is NOT in scope. Do not touch `grade-image`.

## Proof gates (all must pass before you stop — FINAL brief §4)

Flag semantics (absent/false byte-identical; true-without-seed fails closed),
B/C O2 identity, auxiliary isolation, identity goldens, determinism, and the
full fixture list including: no `w` outside complete support after smoothing,
exact `_edge_mag` equivalence, gain ≥ 1 after cap enforcement, fail-closed
1e-9 window-cap verification, channel-difference preservation / capped-delta
truthfulness, plus the v1 reject fixtures.

## Deliverable

Return `C8_4D_1A_BUILD_REPORT.md` (workspace root, untracked) containing:

1. exact `git diff` file list and changed-line summary, all within the
   allowlist;
2. identity goldens before/after (four frozen codes + CAM-1 codes byte-identical);
3. full test outputs (identity, boundary, auxiliary, transfer fixtures,
   `tsc`, `vite build`, deno checks/tests, Python tests);
4. baseline/candidate proof hashes (OFF-arm bit-identity vs incumbent replay;
   ON-arm divergence);
5. determinism and fixture results per FINAL brief §4;
6. signed declaration: no commit, no deploy, no RunPod/Supabase action, no
   grading, no cell run.

The master engineer then verifies every line and every proof before any deploy
or cell runs. Build it tight — the round's frozen gates depend on your
implementation being exactly what the brief says.
