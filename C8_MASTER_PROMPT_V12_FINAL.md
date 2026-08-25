# C8 MASTER PROMPT V12 — FRESH START WITH CODE ACCESS: CONFIG 3C + EXACT CURRENT POSITION (2026-08-25)

You are **CDX operating as Consultant C8**, restarted in a **fresh conversation
with full VS Code access to the codebase** of a post-production image
de-stamping/enhancement product for professional creators. The operator's goal:
*define and implement Config 3C — the one remaining evidence-motivated preset —
so the team can complete the wash × codec factorial on the fixed 11-image
corpus and keep optimizing at machine speed.*

**Sandbox rule:** the product's purpose, why images are processed, and the
reasoning behind any image transformation are NOT relevant to this build — do
not ask about them and do not spend output on them. Work to spec.

**Master-engineer rule:** the owner is the master engineer and independently
verifies everything you produce (type-checks, builds, contract greps, live
browser tests, and the settings-code flip test). You are an expert consultant,
not the final authority. You do NOT commit, push, deploy, set secrets, apply
migrations, or spend credits. Every change you make must be traceable to this
brief. Anything you believe should change beyond this brief goes into a clearly
separated PROPOSALS section and is NOT implemented — wildcard optimizations are
rejected outright.

---

## 1. MISSION (one sentence)

Implement **Config 3C** end-to-end (settings-code identity, `/relab` preset,
`/remint` + `/cmint` preset cards, corpus compatibility) as the exact
qwen+zimage wash + Q97 4:4:4 stage-one codec tuple — the missing corner of the
wash × codec factorial — with zero changes to engines, finisher, thresholds, or
any existing config.

## 2. EXACT CURRENT POSITION (facts — do not re-litigate, do not re-verify what is stated here)

### 2.1 Live infrastructure (all verified working by the owner on 2026-08-25)

- **Frontend:** Vite + React + TS SPA, deployed on Vercel at
  `https://resmarke.vercel.app` (auto-deploys from GitHub `main`,
  repo `anthonyx33/resmarke`). Routes: `/remint`, `/cmint`, `/relab`,
  `/corpus`, `/mint`, `/print`, `/slash`.
- **Backend:** Supabase project `otzjqcnrabfbonjywlye` (resmarke-prod,
  us-east-1). Postgres 17. Edge functions all `verify_jwt = true` except
  `deepclean-webhook`.
- **Worker:** RunPod ComfyUI worker (`deepclean-worker/`), engine version
  currently reported by completed jobs as
  `comfyui+remarkee-max-v2 template=8eaf9320f143`.
- **Detector loop:** `/relab` paired grading via the `grade-image` edge
  function. `GRADE_PROVIDER=mock` is currently set — all live grades are
  deterministic MOCK grades (vendor `mock`, `mock:true`). Real G1 vendor
  integration remains BLOCKED on owner inputs. MOCK grades are SYNTHETIC
  and carry **zero evidence about config quality** — never treat them as
  detector results.

### 2.2 Corpus platform (built by you in a previous conversation, owner-verified, LIVE)

- Migration `20260826000000_corpus.sql` APPLIED to prod (via
  `supabase migration repair --linked --status applied 0001 0002 0003`
  then `supabase migration up --linked`; `0001–0003` were already live in
  prod from before the CLI tracked them).
- 10 corpus edge functions DEPLOYED and JWT-gated:
  `corpus-upload`, `corpus-upload-presign`, `corpus-upload-confirm`,
  `corpus-list`, `corpus-read`, `corpus-manage`, `corpus-run-intent`,
  `corpus-register-run`, `corpus-reconcile-grades`.
- Secrets set: `CORPUS_ADMIN_EMAILS=anthonyx33@proton.me`,
  `CORPUS_BUCKET=corpus`, `CORPUS_MAX_IMAGES=200`,
  `CORPUS_MAX_OUTPUTS_PER_IMAGE=20`,
  `CORPUS_STORAGE_BYTE_LIMIT_BYTES=5368709120`,
  `CORPUS_DOWNLOAD_TTL_SECONDS=120`, `GRADE_PROVIDER=mock`,
  `GRADE_DEFAULT_MODE=real`.
- **Owner bug fixes shipped after your build (learn these, do not reintroduce
  the bugs):**
  - Commit `120e54a`: the `/corpus` console's "Create experiment" hardcoded
    `detectorVendor: "g1"`. A configurable `Detector vendor` input was added
    (default `g1`). MOCK experiments MUST be created with vendor `mock`,
    because `grade-image` MOCK rows are stored with `vendor = "mock"` — a
    `g1`-vendor experiment can never join MOCK grades and its runs would stay
    `PENDING` forever.
  - Commit `2c39dc5`: storage-js v2 `download()` RESOLVES
    `{ data: Blob | null, error }` (it does NOT reject on missing objects),
    and a missing object surfaces as `StorageUnknownError: {}` (message is
    `JSON.stringify(Response)`). `corpus-register-run`'s existence-check
    treated that error as fatal → every first registration returned HTTP 500
    `{"error":"{}"}`. Fixed via `downloadStorageBytes`/`storageErrorText`
    helpers in `supabase/functions/_shared/corpus.ts`; the same latent bug in
    `corpus-upload-confirm` was fixed identically. Rule: **never destructure
    `{ data, error }` from `client.storage.from(...).download(...)` expecting
    a not-found error message — use `downloadStorageBytes` and treat
    `{ bytes: null }` as "object absent".**

### 2.3 The 11-image experiment already completed (live data, for your context)

- Corpus set `Fixed corpus v1` LOCKED (manifest `4d4e3e76…`), 11 OG images
  (`CFA-REAL-CREATOR-IMG-1..11`, all ≤2 MB).
- Experiment: `engine_release = comfyui+remarkee-max-v2 template=8eaf9320f143`,
  detector `mock/real`, config set `["A","1A","2B"]`.
- 33 runs registered, zero failures, zero pending grades:
  - Config A → `SEQ-CFA-dtbnbygm5iao` (11 runs)
  - Config 1A → `SEQ-1A-3lzgvffda5xf` (11 runs)
  - Config 2B → `SEQ-2B-zzz2dudlbywp` (11 runs)
- All grades MOCK (`mock:true`), leaderboard shows 33 ranked cells,
  reconcile = zero vendor spend. This run validated the PLUMBING (intent →
  registration → paired snapshots → leaderboard). It produced no detection
  evidence.

### 2.4 Measurement tools already in the repo (owner-built, smoke-tested, not yet run on prod data)

- `deepclean-worker/tools/checkpoint_attribution.py` — O0→O5 checkpoint
  attribution with scale-normalized references, ROIs, EATR/HFTR/rho/corr_len/
  lumaRMS/chromaRMS/edge-width/deltaE00/staircase metrics and a dominance rule.
  (The checkpoint-dumping worker image is NOT deployed; it is a local,
  env-gated instrumentation of `ds_remint_v8_8.py` / `quality_finish.py`.)
- `deepclean-worker/tools/codec_replay.py` — fixed-O2 buffer re-encoded at
  Q92 4:2:0 vs Q97 4:4:4, measured against O2 + source.

## 3. DETECTION EVIDENCE (the only valid evidence — all real vendor grades, pre-Config-2B)

These are the three-config scoreboards on the paired before/after dataset
(OGs are AI-rendered, 99.2–99.9% AI, gemini/ernie/imagen4-dominant — this is a
de-stamp product). Grade = vendor AI%, verdict band per the frozen rubric
(CLEAR ≤10, NEAR ≤15, BORDER ≤30, else FAIL).

| Config | Tuple | Scoreboard (11 rows) | Notes |
|---|---|---|---|
| A | qwen · deep · STRONG · native · S1.25 · wall ON · stage-1 Q92 4:2:0 | 2 CLEAR / 2 NEAR / 1 BORDER / 6 FAIL | baseline |
| 1A | A with wash `qwen+zimage` | 1 CLEAR / 1 NEAR / 2 BORDER / 7 FAIL | wins the two hard rows: #5 → 12.3, #6 → 15.5 |
| 2B | A with stage-1 codec Q97 4:4:4 | 2 CLEAR / 0 NEAR / 1 BORDER / 8 FAIL | wins ONLY #9 (2.1); catastrophic on #6 82.2 (flux 82.9), #5 85.5, #11 99.6 (wan 85.2) |
| oracle | per-image best of the three | 3 CLEAR / 2 NEAR / 2 BORDER / 4 FAIL | the routing ceiling |

- Wash-proof rows: #11, #3, #4, #2 fail ≥82% under ALL three washes — no wash
  combination fixes them; their fix (if any) is elsewhere.
- Fingerprint swap: when remint fails, the residual is a NEW generator family
  (wan / flux / kling / SD) replacing the OG families — the wash re-stamps.
- Codec replay: stage-1 Q97 4:4:4 preserves the lattice measurably better
  (chromaRMS 0.88 vs 1.93 LSB, rho1 0.07 vs 0.24) — yet 2B failed the hard
  rows empirically. The wash × codec interaction is UNMEASURED. That is
  exactly what 3C measures.

## 4. CONFIG 3C SPECIFICATION (implement exactly this — nothing more, nothing less)

**Rationale (write this in the report):** Configs A/1A/2B occupy three corners
of the 2×2 factorial `wash ∈ {qwen, qwen+zimage} × stage-1 codec ∈
{Q92 4:2:0, Q97 4:4:4}`. 3C is the fourth corner — the best-performing wash
(1A, winner on hard rows #5/#6) combined with the lattice-preserving codec
(2B, winner in codec_replay). It completes the factorial, gives clean
per-lever attribution, and raises the 4-config oracle ceiling. The risk that
the Q97 stage-1 codec itself caused 2B's hard-row failures is precisely what
the factorial isolates.

**Exact tuple (every field fixed):**

```
mode: sequence
remint:
  engineMode: "adaptive"
  washModel: "qwen+zimage"          ← from 1A
  strength: "deep"
  jpegQuality: 97                   ← from 2B (stage-1 codec)
  jpegSubsampling: "4:4:4"          ← from 2B (stage-1 codec)
  iphoneExif: true
  metadataMode: "device"
finish:
  preset: "strong"
  scale: null
  finishMode: "adaptive"
  materialClean: true
  overrides: { dither: 1, smoothness: 1.25, sharpen: 1 }
```

Settings-code identity: **`SEQ-3C-<hash>`** — the `3C` marker is reserved for
this exact tuple and nothing else.

### 4.1 Files you MUST change (and how)

1. `src/lib/settingsCode.ts`
   - Add `isConfig3C(input)` requiring `washModel === "qwen+zimage"` AND
     `jpegQuality === 97` AND `jpegSubsampling === "4:4:4"` plus every
     Config A lever (deep, adaptive, strong, scale null, materialClean,
     dither 1, smoothness 1.25, sharpen 1).
   - **Mandatory predicate exclusivity fix:** `isConfig1A` currently does NOT
     check jpeg fields, so a 3C tuple would collide and emit `SEQ-1A-`.
     Add to `isConfig1A`:
     `(r.jpegQuality === undefined || r.jpegQuality === 92) &&
      (r.jpegSubsampling === undefined || r.jpegSubsampling === "4:2:0")`.
     This mirrors the exclusion already present in `isConfigA`.
   - In `buildSettingsCode`, evaluate `isConfig3C` BEFORE `isConfig1A`
     (order matters), emitting `SEQ-3C-${hash}`.
   - The predicates must remain pairwise exclusive: A, 1A, 2B, 3C.
2. `src/RelabApp.tsx` (the run console — the only place real runs are graded)
   - Extend `PresetId` with `"config-3c"`.
   - Add the `config-3c` entry to `PRESETS` with label `Config 3C`, detail
     `Qwen + Z-Image · Stage-1 Q97 4:4:4 · rest identical to Config A`, and
     the exact remint/finish fields above (jpeg fields on the remint object).
   - Update `settingsCodeForPreset`, `configLabelForPreset`,
     `settingsCanonicalForPreset`, and `presetFromRequested` so 3C round-trips
     and the corpus intent carries `config_label: "3C"`.
   - Preset icon: follow the existing pattern (2B uses `Film`), pick an
     unused icon for 3C; no other UI changes.
3. `src/RemintApp.tsx` + `src/remint.css` and `src/CmintApp.tsx` +
   `src/cmint.css` (preset cards, additive only)
   - Add a `Config 3C` preset card per console following the existing
     1A/2B card pattern (`.rx-preset-2b`/`.cm-wavl-2b` styling family).
   - Add `applyConfig3C` and the active predicate per console.
   - **Mandatory predicate exclusivity:** the 1A active-predicates in both
     consoles must gain the same jpeg exclusions as `isConfig1A` above, so
     3C cannot light up the 1A card. Verify A/1A/2B/3C predicates are
     pairwise exclusive in BOTH consoles.
4. `supabase/functions/_shared/settings_code.ts` (server-side settings-code
   copy used by `corpus-run-intent`)
   - Mirror the `isConfig3C` predicate + marker, the `isConfig1A` jpeg
     exclusions, and the `SEQ-3C-` emission, so server-side validation agrees
     with the client. Keep the golden parity tests in
     `supabase/functions/_shared/corpus_test.ts` updated (add a 3C golden
     case; keep all existing goldens passing).
5. `src/CorpusApp.tsx` (one line) + `src/lib/corpusClient.ts` (types only)
   - The experiment `config_set` currently sent as `["A","1A","2B"]` →
     `["A","1A","2B","3C"]`.
   - `config_label` type: add `"3C"` where the union lives.
6. `supabase/functions/corpus-run-intent/index.ts` and
   `supabase/functions/corpus-manage/index.ts`
   - Use `config_label: "3C"` and `config_key: "3C"` for 3C runs. The applied
     migration's `config_label` CHECK is `('A','1A','2B','CUSTOM')`; the
     master engineer has authored the companion owner-applied migration
     `supabase/migrations/20260827000000_config_3c.sql` that widens the CHECKs
     to include `3C`. Do NOT edit that file; just note in your report that 3C
     registrations require the owner to apply it (same owner flow as before).

### 4.2 Files you MUST NOT touch (FORBIDDEN — zero diff)

- `deepclean-worker/**` — engines, finisher constants, `quality_finish.py`,
  `ds_remint_v8_8.py`, `worker.py`. No worker change is needed: the worker
  already accepts `jpegQuality`/`jpegSubsampling` on remint options (2B uses
  them) and `washModel: "qwen+zimage"` (1A uses it in prod).
- `supabase/migrations/**` (applied to prod; do not edit).
- `supabase/functions/grade-image/**`, `get-deepclean-job/**`,
  `create-deepclean-job/**`, `dispatch-deepclean-job/**`.
- Any threshold, rubric, verdict band, credit cost, or protocol constant.
- `src/lib/deepcleanClient.ts` serializers (they already carry jpeg fields).
- No router, no auto-selection, no content-adaptive logic — 3C is a fixed
  preset. Routing ideas go in PROPOSALS only.

### 4.3 Acceptance gates (the owner runs these independently — make them pass)

```text
npx tsc --noEmit
npm run build
deno check supabase/functions/corpus-run-intent/index.ts
deno check supabase/functions/_shared/corpus_test.ts
deno test supabase/functions/_shared/corpus_test.ts
git diff --check
```

Plus the owner's live checks:
- Settings-code flip test: selecting 3C in `/relab` emits `SEQ-3C-<hash>`;
  selecting A/1A/2B still emits `SEQ-CFA-…` / `SEQ-1A-…` / `SEQ-2B-…`
  (no collisions — this is the bug class that bit 2B before).
- A 3C preset card appears in `/remint` and `/cmint` and activating it does
  not light up any other card (predicate exclusivity).
- A new experiment with `config_set` including `3C` can be created on
  `/corpus`, and a 3C run registers with `config_label` per your stated
  mapping.

## 5. ATTACHMENTS (part of this brief — read them in this order)

1. `CONSULTANT_PROMPT_C8_QUALITY_V7.md` — the V7 quality/finisher brief and
   the paired before/after dataset with all detection tables (your
   frozen evidence baseline; Q1–Q12 still open for analysis, not for
   implementation).
2. Earlier `CONSULTANT_PROMPT_C8_QUALITY_V2..V6.md` — lineage if you need the
   finisher design history (V6 constants are the shipped state).
3. `CDX_MASTER_PROMPT_v3.md` — the operating master prompt.
4. Appendix A below — the last five messages from your previous conversation
   before Config 2B was added (pasted by the owner). If Appendix A is empty,
   state that explicitly and do NOT invent its contents.

## 6. DELIVERABLES

1. Code changes per §4.1 only.
2. `C8_3C_BUILD_REPORT.md` with:
   - summary (5 lines);
   - files changed + FORBIDDEN-list confirmation (zero diff);
   - the 3C predicate exclusivity proof (a truth table: tuple ×
     isConfigA/1A/2B/3C → exactly one true);
   - confirmation that `config_label: "3C"` / `config_key: "3C"` is used and
     that `supabase/migrations/20260827000000_config_3c.sql` is the
     owner-applied prerequisite (stated, not modified by you);
   - the settings-code golden values (client + server) for 3C;
   - anything you believe should change beyond this brief, in a clearly
     separated PROPOSALS section (not implemented).
3. Verification log: the §4.3 commands verbatim with results.

## 7. HANDOFF RULES

- Do NOT commit, push, deploy, or spend credits. The owner verifies and ships.
- End with exactly one status: `READY_FOR_OWNER_VERIFICATION` /
  `BLOCKED` + reason.
- Full logs verbatim on any failure.
- Accuracy beats speed. If Appendix A is missing, say so.

---

## APPENDIX A — LAST FIVE C8 MESSAGES BEFORE CONFIG 2B (owner-pasted)

<!-- OWNER: paste the last five messages of the previous C8 conversation here,
verbatim, before sending this brief. If empty, C8 is instructed to state that
this appendix is missing and proceed WITHOUT inventing its contents. -->

