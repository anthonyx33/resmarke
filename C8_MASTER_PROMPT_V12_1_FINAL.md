# C8 MASTER PROMPT V12.1 FINAL — AUDIT ACCEPTED: LAB-ONLY 3C + SEED CONTROL + IDENTITY HARDENING (supersedes V12, 2026-08-25)

You are **CDX operating as Consultant C8**, in a fresh conversation with full
VS Code access to this de-stamping/enhancement product's codebase. The operator
and the master engineer have **independently verified your audit of V12 — it is
accepted**. This brief converts the accepted audit into a build order.

**Sandbox rule:** product purpose and image-transformation reasoning are out of
scope; do not discuss them. Work to spec.

**Master-engineer rule:** the master engineer independently verifies everything
you produce. You do NOT commit, push, deploy, set secrets, apply migrations, or
spend credits. Anything beyond this brief goes in a separated PROPOSALS section,
never into the build. Wildcard optimizations are rejected.

---

## 1. MISSION (one sentence)

Implement Config 3C as a **lab-only fourth corpus cell** with **executable
identity guarantees**, preceded by an **opt-in fixed-seed control** in the
worker so all four configs can finally be compared as paired realizations — and
nothing else.

## 2. VERDICT ON YOUR V12 AUDIT (owner-verified — accepted in full, with two qualifications)

The master engineer re-verified every load-bearing claim against the code:

| # | Your claim | Verdict |
|---|---|---|
| 1 | Each run gets a unique seed: `worker.py` passes `seed_extra=f"{job_id}:{input_sha}"` → `_seed(...)` in `ds_remint_v7.py:269` via `ds_remint_v8_8.py:241` | CONFIRMED. A/1A/2B cells each contain one different realization; wash, codec, camera noise, and seed are entangled. |
| 2 | The adaptive ladder probes encoded bytes (`_encode_probe`, `ds_remint_v8_8.py:226-228`), so a codec change also perturbs routing | CONFIRMED. 2B/3C measure the total request effect, not a codec-only effect. |
| 3 | `isConfigA` ignores `iphoneExif`/`metadataMode`, so "exact tuple" was overclaimed | CONFIRMED as code fact; the exclusion is deliberate and documented, but V12's wording was wrong. Fixed below. |
| 4 | Identity logic is duplicated across client, server, /relab reconstruction, and two console predicates — that is why collisions recur | CONFIRMED (2B/CFA collision shipped once; a 1A/3C collision was imminent). Hardening below. |
| 5 | V11 froze new presets and wash-combination experiments until attribution/replay measurements complete; those measurements never ran on prod | CONFIRMED (V11 §3 "THE FIVE STOPS"; the 33-run corpus test was MOCK and produced zero evidence). V12 reversed V11 on owner instruction but did not say so. Fixed below. |
| 6 | 3C is not built in this checkout; the verification suite passing validates A/1A/2B only | CONFIRMED. |
| 7 | The 3C constraint migration must be applied before any frontend that emits `config_label:"3C"` goes live | CONFIRMED. It is relax-only; the owner can apply it immediately. |
| 8 | `CDX_MASTER_PROMPT_v3.md` is an unrelated historical Docker incident brief that conflicts with this work | CONFIRMED. Marked ARCHIVAL; removed from the attachment package. |
| 9 | Appendix A was empty | CONFIRMED (owner's paste pending; see §13). |

**Two qualifications (the only places your audit overreached):**

- "Q97 stores the already-poor pixels more faithfully" is a plausible but
  UNMEASURED hypothesis. Treat it as G23-class prior, never as fact, until
  `codec_replay.py` runs on #9/#5/#6.
- "Do not spend grading credits on the current design" — currently moot
  (`GRADE_PROVIDER=mock`; vendor credits are not spendable). The correct
  rule, which this brief enforces: **no real-vendor grading of any 3C run
  until the seed control and the V11 measurement sequence are complete.**

## 3. OWNER DECISIONS (binding)

1. **3C is lab-only.** It exists in `/relab`, the settings-code system, the
   corpus identity, and the server validator. It does NOT get preset cards in
   `/remint` or `/cmint`. Promotion to a customer preset requires: (a) seed-
   controlled detection results that improve on A/1A/2B, and (b) a 100%-zoom
   human quality pass with no regression. Until then it is a measurement cell.
2. **Seed control is approved as the one worker change** (measurement
   infrastructure, not an algorithm change). Spec in §5.
3. **V11's measurement sequence runs before any causal claims.** Spec in §7.
4. **V12's wording errors are corrected** in this brief: the settings identity
   covers the detection-relevant tuple, not `iphoneExif`/`metadataMode`;
   "1A is the best-performing wash" is wrong (A wins overall; 1A wins the hard
   rows #5/#6); adding a config cannot LOWER the in-sample oracle, only leave
   it unchanged or raise it.

## 4. CURRENT POSITION (unchanged from V12 §2 — all of it still stands)

Live: `https://resmarke.vercel.app` (Vercel from GitHub `main`), Supabase
`otzjqcnrabfbonjywlye`, corpus platform deployed and verified (33 MOCK runs,
zero pending), owner bug fixes `120e54a` + `2c39dc5` (do not reintroduce),
companion migration `supabase/migrations/20260827000000_config_3c.sql`
authored by the master engineer (owner-applied, relax-only — do not edit).

## 5. SEED-CONTROL SPEC (worker change — the ONLY worker change)

Goal: lab runs can fix the generation/camera seed so the four configs are
compared as paired realizations; production behavior is unchanged by default.

1. `deepclean-worker/ds_remint_v8_8.py` / `ds_remint_v7.py` (via settings):
   accept an optional `remint.seed` string (exact form: `lab-<token>` where
   `<token>` is `[a-z0-9]{1,32}`, validated in the worker). When present,
   the wash generation and coherent-camera draws derive from
   `_seed(creator_id, f"lab-seed:{seed}", original.size, salt)` instead of
   the job-unique `seed_extra`. The rung suffixes (`:v88:<rung_index>` etc.)
   stay, so the adaptive ladder remains deterministic per fixed seed.
2. `deepclean-worker/worker.py`: build `seed_extra` from the setting when
   present, else keep `f"{job_id}:{input_sha}"` (default unchanged —
   byte-for-byte current behavior for all non-lab jobs).
3. `src/lib/deepcleanClient.ts` + `/relab`: expose an optional
   `labSeed` input ONLY inside `/relab` (lab console), never in `/remint` or
   `/cmint`; when set, it rides the remint options as `seed` and is included
   in the canonical settings JSON so it is hash-visible in the settings code.
4. Report the seed in the worker report (`engine.seed_extra` already flows;
   add `engine.lab_seed` when the override is active) — L2 provenance for
   the executed run.
5. Paired-seed experiment protocol (runs later, not in this build):
   same image → same `lab-<token>` across A/1A/2B/3C; two replicates
   (`lab-<token>1`, `lab-<token>2`). Determinism check: same seed re-run
   must produce byte-identical stage-one output.

## 6. CONFIG 3C SPEC (tuple unchanged; scope reduced)

```
mode: sequence
remint:
  engineMode: "adaptive"
  washModel: "qwen+zimage"
  strength: "deep"
  jpegQuality: 97
  jpegSubsampling: "4:4:4"
  iphoneExif: true
  metadataMode: "device"
finish:
  preset: "strong"
  scale: null
  finishMode: "adaptive"
  materialClean: true
  overrides: { dither: 1, smoothness: 1.25, sharpen: 1 }
```

Settings-code identity: **`SEQ-3C-<hash>`**, reserved for this tuple only.
Wording rule (replaces V12's "exact tuple" claim): the identity is defined on
the **detection-relevant tuple** (wash, strength, engine mode, stage-1 codec,
finish preset/scale/mode, materialClean, dither/smoothness/sharpen).
`iphoneExif`/`metadataMode` remain deliberately excluded from predicates —
state this explicitly in the report, and keep the exclusion CONSISTENT across
all four predicates.

### 6.1 Files in scope

- `src/lib/settingsCode.ts`: `isConfig3C` + `SEQ-3C-` emission; the mandatory
  `isConfig1A` jpeg exclusions
  (`(r.jpegQuality === undefined || r.jpegQuality === 92) &&
   (r.jpegSubsampling === undefined || r.jpegSubsampling === "4:2:0")`);
  check order: 3C BEFORE 1A.
- `src/RelabApp.tsx`: `PresetId` + `PRESETS` + `settingsCodeForPreset` /
  `configLabelForPreset` / `settingsCanonicalForPreset` /
  `presetFromRequested`; the lab-seed input (§5.3). Preset label: `Config 3C
  — LAB · Qwen + Z-Image · Stage-1 Q97 4:4:4`.
- `src/CorpusApp.tsx` (one line): experiment `config_set` →
  `["A","1A","2B","3C"]`.
- `src/lib/corpusClient.ts`: add `"3C"` to the `config_label` type union.
- `supabase/functions/_shared/settings_code.ts` + `corpus_test.ts`: mirror
  predicate/marker + a 3C golden case; keep all existing goldens green.
- `supabase/functions/corpus-run-intent/index.ts` / `corpus-manage`:
  `config_label: "3C"`, `config_key: "3C"` (companion migration already
  authored; you do not edit it).
- Identity hardening (§6.2).
- Seed control (§5): worker files + deepcleanClient + `/relab`.

### 6.2 Identity hardening (mandatory — this is the anti-collision fix)

1. **Consolidate to one canonical identity module.** The pure settings-code
   logic (predicates, markers, canonical JSON, hash) must live in ONE
   dependency-free TS file. Preferred layout: keep it in
   `supabase/functions/_shared/settings_code.ts` and make
   `src/lib/settingsCode.ts` a thin re-export of it (Vite may import a pure
   TS file outside `src/` within the project root). If that import layout
   fails `tsc`/`vite build` after an honest attempt, fall back to keeping the
   client copy but add an **automated parity test** that runs both modules
   over a case matrix and fails on any divergence — and state which layout
   shipped and why in the report.
2. **Executable identity tests** (this repo has no test runner; use `deno
   test`, which already runs `supabase/functions/_shared/corpus_test.ts`):
   - exclusivity truth table over ALL tuples × predicates (A/1A/2B/3C and
     at least four negative/custom cases — wrong subsampling, wrong wash,
     missing jpeg fields, jpeg 95 4:2:2);
   - marker emission: each tuple emits exactly its marker, never another;
   - `presetFromRequested` round-trip for all four presets, including the
     lab-seed field present and absent.
   These tests must run green in CI-style locally (`deno test`) and be
   re-runnable by the owner.

### 6.3 NOT in scope / FORBIDDEN (zero diff)

- `src/RemintApp.tsx`, `src/CmintApp.tsx`, and their CSS — NO 3C preset
  cards (owner decision 1).
- Any finisher constant, threshold, rubric, credit, or protocol change.
- Any algorithm change in `deepclean-worker/**` beyond the §5 seed override
  (checkpoint instrumentation already present stays untouched).
- `supabase/migrations/**` (including the 3C companion file).
- `grade-image` and the job/dispatch functions.
- No router, no content-adaptive logic (PROPOSALS only).

## 7. MEASUREMENT SEQUENCE (owner runs; you document exact commands in your report)

1. Apply the 3C constraint migration (owner, relax-only).
2. Deploy the worker image with the §5 seed control + existing checkpoint
   instrumentation (owner deploy by digest).
3. Executed-settings audit: one mechanical table for the existing 33 runs
   (11 × A/1A/2B) from `deepclean_jobs.report` — wash executed, rungs,
   selected attempt, camera params, stage-one codec + dims, finish candidate,
   retries, final hash. Rows named `OG-09`, `A-09`, `1A-09`, `2B-09`.
4. `tools/codec_replay.py` on #9/#5/#6 against the delivered O2 buffers.
5. O0→O5 `tools/checkpoint_attribution.py` on the six-image set from V11.
6. Only then: the paired-seed A/1A/2B/3C lab run (§5.5) with MOCK grades for
   plumbing, real grades only after G1 lands.

## 8. ACCEPTANCE GATES (owner runs independently)

```text
npx tsc --noEmit
npm run build
deno check supabase/functions/_shared/settings_code.ts
deno check supabase/functions/corpus-run-intent/index.ts
deno test supabase/functions/_shared/corpus_test.ts
deno test <your new identity tests>
git diff --check
```

Plus owner live checks: `/relab` 3C emits `SEQ-3C-<hash>` and the other three
markers never change; lab-seed input appears only in `/relab`; `config_set`
with `3C` can be created on `/corpus`; no console (`/remint`, `/cmint`) diff.

## 9. DELIVERABLES

1. Code changes per §5 and §6 only.
2. `C8_3C_BUILD_REPORT.md`: summary; files changed + forbidden-list
   confirmation; identity layout decision (§6.2.1) with rationale; the
   exclusivity test matrix; lab-seed provenance fields; the worker-report
   shape for `engine.lab_seed`; exact owner commands for §7 steps 1–2;
   separated PROPOSALS section (nothing implemented from it).
3. Verification log: §8 commands verbatim.

## 10. HANDOFF RULES

- Do NOT commit, push, deploy, or spend credits. End with exactly one status:
  `READY_FOR_OWNER_VERIFICATION` / `BLOCKED` + reason.
- Full logs verbatim on failure. Accuracy beats speed.

## 11. ATTACHMENTS (read in this order)

1. `CONSULTANT_PROMPT_C8_QUALITY_V7.md` — evidence baseline (paired dataset,
   scoreboards, Q1–Q12).
2. `CONSULTANT_PROMPT_C8_QUALITY_V2..V6.md` — finisher design lineage.
3. `C8_MASTER_PROMPT_V11_FINAL.md` — the prior freeze and its measurement
   sequence (now superseded by this brief's owner decisions 1–4).
4. `CDX_MASTER_PROMPT_v3.md` — ARCHIVED, do NOT read as operating guidance;
   attached only so its existence is not a surprise.
5. Appendix A below — owner-pasted final messages from the previous C8
   conversation. If empty, state that and proceed without inventing content.

---

## APPENDIX A — LAST FIVE C8 MESSAGES BEFORE CONFIG 2B (owner-pasted)

<!-- OWNER: paste here or delete this appendix before sending. -->
