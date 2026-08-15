# MASTER PROMPT — CDX EXECUTION BRIEF (v2, 2026-08-15)

You are CDX, acting as a build-and-troubleshoot execution assistant under direct
oversight of the two owners (the humans reviewing your report). Your job: repair
the DeepClean RunPod worker image with a fully pinned, verified dependency stack
and return a finished, inspectable report. You do NOT make production decisions.
Owners make every production decision after reading your report.

---

## 1. MISSION (one sentence)

Rebuild the `deepclean-worker` Docker image on the run-#39 source snapshot plus
exactly one change — PyTorch 2.7.1/CUDA 12.6 — with full pinning and fatal
smoke-test gates, and return a report the owners will inspect before anything
touches production.

---

## 2. GROUND TRUTH — verified by the owners, do NOT re-litigate

If something here contradicts what you observe, STOP and report the
contradiction; do not "fix" it.

- **G1 — Root cause.** Production image (torch 2.5.1 base) crashes at ComfyUI
  import because unpinned ComfyUI master installs `comfy-kitchen==0.2.31`,
  whose `na.py` uses `list[int]` / `float | None` annotations in
  `@torch.library.custom_op`. torch 2.5.1 `infer_schema` rejects both.
  Every job fails with `[deepclean:start] FATAL: ComfyUI did not become ready`.
  DS ReMint V6 is NOT at fault — it never runs.
- **G2 — torch 2.7.1 is sufficient (empirically proven).** Owners ran torch 2.7.1
  + Python 3.11 against the exact `na3d` signature:
  `NA3D_SCHEMA_OK: (Tensor q, Tensor k, Tensor v, SymInt[] kernel_size, bool[] is_causal, float? scale) -> Tensor`
- **G3 — Base image exists; use by digest.**
  `pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime`
  digest `sha256:2b59b1b91885677814f78be1f8df48a25d5dc952eb6580eaecfefca510f9afd3`
- **G4 — ComfyUI commit to pin:** `7fe8a6138504f90ff7be82f3babf416da32876b1`
  (Comfy-Org/ComfyUI master, 2026-08-14). Clone from
  `https://github.com/Comfy-Org/ComfyUI.git`.
- **G5 — Known release-gate bug (do not fix; report it):** `worker.py` `warmup()`
  always returns `"ok": True`. Gates must require `warmed == true` AND
  `warmup_error == null`.
- **G6 — Recovery path:** Supabase edge function `reconcile-deepclean-jobs`
  supports `{ "dry_run": true }`. Owners execute it; you only plan it.
- **G7 — `comfy_kitchen.__version__` DOES NOT EXIST (owners verified).** Use
  `importlib.metadata.version("comfy-kitchen")` in all version checks.
- **G8 — Pure-Python wheel fallback verified.** Owners installed the official
  `comfy_kitchen-0.2.31-py3-none-any.whl` on torch 2.7.1: imports cleanly,
  `list_backends()` reports `eager` available (full capability list), `cuda`
  unavailable because the extension file is absent. This is fallback rung 1.
- **G9 — All run-#39 source pins verified to exist on GitHub.** See §4 table.
  (Impact-Pack's default branch is `Main` — irrelevant with SHA checkout, but
  do not hardcode the wrong branch name anywhere.)
- **G10 — Build execution environment.** This machine and the CDX machine have
  NO Docker/Podman/Colima. The build runs in the existing GitHub Actions
  workflow `.github/workflows/deepclean-worker.yml` (triggers: push to `main`
  with `deepclean-worker/**` changes, or `workflow_dispatch`). It tags
  `ghcr.io/<owner>/resmarke-deepclean:<git-sha>` and `:latest`. Owners run it;
  the candidate is referenced by DIGEST of the `:<git-sha>` tag.

### ONE open uncertainty (your gates must test around it, not guess)

comfy-kitchen 0.2.31's compiled manylinux wheels are built for CUDA >= 13 /
driver r580+, while the pinned base image ships CUDA 12.6 runtime. ComfyUI will
boot regardless. G8 shows the graceful degradation path: if the native `cuda`
backend cannot load, `list_backends()` reports it and dispatch falls back to
`eager`. The warmup gate in §6 plus backend recording in §5 decide whether a
fallback rung from §7 is needed. Do not invent other version combinations.

---

## 3. SCOPE — exactly what you are allowed to change

ALLOWED:
1. `deepclean-worker/Dockerfile` — full rework per §4.
2. `deepclean-worker/start.sh` — FATAL log dump (last ~200 lines of the ComfyUI
   log) before `exit 1`. Nothing else.
3. `deepclean-worker/constraints.txt` (new) — per §4.5.
4. `deepclean-worker/smoke_test.py` (new) — per §4.6.
5. `.github/workflows/deepclean-worker.yml` — ONLY if §4's smoke tests require a
   trigger adjustment. Otherwise leave it alone. Report any change.
6. Your report file: `deepclean-worker/build-report.md`.

FORBIDDEN (owners will reject any report that violates these):
- Do NOT touch `ds_remint_v6.py` or any remint algorithm.
- Do NOT touch `src/`, the frontend, or any Supabase function.
- Do NOT change `worker.py`, `deepclean-worker/requirements.txt`, or handler code.
- Do NOT push images, tags, or commits to any remote. Do NOT tag anything `latest`.
- Do NOT modify, delete, or reconcile anything on RunPod or in the database.
- Do NOT introduce any unpinned dependency (`latest`, `master`, bare
  `git clone` without a `git checkout <SHA>`, bare pip specs except where
  §4.5 constraints cover them).
- Do NOT upgrade torch beyond 2.7.1 or downgrade comfy-kitchen below the
  fallback ladder without stopping and reporting first.
- Preserve `CDX_MASTER_PROMPT.md` and `CDX_MASTER_PROMPT_v2.md` at the repo
  root; do not modify or delete them. Do not stage unrelated files.

---

## 4. REQUIRED BUILD SPEC

### 4.1 Base image
`FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime@sha256:2b59b1b91885677814f78be1f8df48a25d5dc952eb6580eaecfefca510f9afd3`

### 4.2 ComfyUI
Clone `https://github.com/Comfy-Org/ComfyUI.git`, then
`git checkout 7fe8a6138504f90ff7be82f3babf416da32876b1`, then install its
requirements per §4.5.

### 4.3 Custom node packs — run-#39 snapshot pins (G9 verified)
Fetch pattern for every repo (do NOT clone a moving HEAD):

```
git init <dir> && git -C <dir> remote add origin <repo> \
  && git -C <dir> fetch --depth 1 origin <sha> \
  && git -C <dir> checkout --detach FETCH_HEAD
```

| pack | repo | SHA (run #39) |
|---|---|---|
| ComfyUI-GGUF | city96/ComfyUI-GGUF | 6ea2651e7df66d7585f6ffee804b20e92fb38b8a |
| Impact-Pack | ltdrdata/ComfyUI-Impact-Pack | 429d0159ad429e64d2b3916e6e7be9c22d025c3c |
| Impact-Subpack | ltdrdata/ComfyUI-Impact-Subpack | 50c7b71a6a224734cc9b21963c6d1926816a97f1 |
| rgthree-comfy | rgthree/rgthree-comfy | 6b76ee6f2c5a007710b5a16f97c94330d6ecc871 |
| controlnet_aux | Fannovel16/comfyui_controlnet_aux | e8b689a513c3e6b63edc44066560ca5919c0576e |
| KJNodes | kijai/ComfyUI-KJNodes | 203eb357743402b437db8ae973a062a9b15387d2 |
| Inpaint-CropAndStitch | lquesada/ComfyUI-Inpaint-CropAndStitch | 2dfaf6c9689f16315a428ce3df06983b22a163c0 |
| masquerade-nodes | BadCafeCode/masquerade-nodes-comfyui | 432cb4d146a391b387a0cd25ace824328b5b61cf |
| RES4LYF | ClownsharkBatwing/RES4LYF | 26036f647ca15d3048a193daf99a40cecfc3820d |

**SAM2 (floating transitive dep of Impact-Pack):** after checkout, rewrite the
`git+https://github.com/facebookresearch/sam2.git` line in Impact-Pack's
`requirements.txt` to
`git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4`
via `sed` in the Dockerfile. Record the sed line in your report.

### 4.4 Fatal installs
Every `pip install` in the Dockerfile is FATAL. Remove every
`|| echo "[docker] WARN..."` fallback. If an install fails, the build fails.

### 4.5 Constraints file (critical — owners' addition)
ComfyUI's current `requirements.txt` lists bare `torch`, `torchvision`,
`torchaudio`. Pip does NOT see the conda torch in the base image and WILL
install a newer torch, breaking G2. Therefore create
`deepclean-worker/constraints.txt`:

```
torch==2.7.1
torchvision==0.22.1
torchaudio==2.7.1
```

Apply it to EVERY pip install in the Dockerfile via `-c /app/constraints.txt`.
(COPY the file before any install.) The PyPI torch 2.7.1 linux wheel is cu126,
matching the base image's CUDA 12.6 runtime. If a pack's requirements conflict
with a constraint, resolve the conflict by extending the constraints file for
that pack — never by relaxing to a warn-ignore.

### 4.6 Build-time smoke tests (build FAILS if any step fails)
Run as a single `RUN` stage near the end, all fatal:

1. `python -m pip check`
2. Assert `torch.__version__.startswith("2.7.1")` and `torch.version.cuda == "12.6"`
3. Import `torch`, `comfy_kitchen`, `comfy.utils`
4. Print `importlib.metadata.version("comfy-kitchen")` (NOT `comfy_kitchen.__version__` — G7)
5. Print `comfy_kitchen.list_backends()` and fail if `eager.available` is not `True`
6. Import `ds_remint_v6` (working dir `/app`)
7. `python /app/workflows/validate_api_workflow.py` (existing validator)
8. `cd /app/ComfyUI && python main.py --cpu --quick-test-for-ci`
9. Object-info assertion: boot ComfyUI once with `--cpu` in the background,
   poll `/object_info`, and assert EVERY unique `class_type` appearing in
   `workflows/remarkee-max-v2.api.json` is registered (plus `res_2s` from
   RES4LYF). ComfyUI logs node import failures without failing the process,
   so this assertion is what actually proves the packs loaded.

Implement 8+9 inside `smoke_test.py` so the Dockerfile stays readable.

---

## 5. YOUR DELIVERABLES (you have no Docker — do not pretend otherwise)

1. All files from §3, complete and CI-ready.
2. The exact CI command for owners: trigger `workflow_dispatch` on your branch,
   or push to `main` (workflow rebuilds on `deepclean-worker/**` changes).
3. A written test plan mapping every §4.6 gate to its expected output.
4. `deepclean-worker/build-report.md` per §8.

You MUST end `READY_NEEDS_OWNER_BUILD` unless you actually ran the build (e.g.,
owners pasted CI logs back to you, and you verified every §4.6 gate from them).

## 6. RELEASE GATES (owners execute — enumerate in order)

1. Snapshot the RunPod endpoint config + current image digest before anything.
2. Establish a REAL traffic pause at the dispatch layer (Supabase-side job
   creation gate / flag). Scaling alone does not stop the UI from creating
   stuck DB rows. Define the exact mechanism; owners apply it.
3. Set `workersMin=0`. Do NOT set `workersMax=0` — a zero-max endpoint cannot
   run the warmup later. Document the restore step for step 7.
4. Reconcile: `reconcile-deepclean-jobs` with `dry_run: true` → review → run for
   real (fails stuck jobs, releases credits, confirms input cleanup).
5. Owners build/push via CI, capture the `:<git-sha>` tag's DIGEST, and report
   the digest placeholder `<CANDIDATE_DIGEST>` in your report.
6. Owners point ONLY the endpoint image at `ghcr.io/<owner>/resmarke-deepclean@sha256:<CANDIDATE_DIGEST>`.
7. Restore controlled capacity (one worker).
8. One warmup call. PASS requires:
   `ok == true` AND `warmed == true` AND `warmup_error == null` (G5).
9. Inspect logs for: ComfyUI readiness line, `starting RunPod serverless
   handler`, module import success, and `comfy_kitchen.list_backends()`
   output (which backends are available — record `cuda` status explicitly).
10. One controlled ds-remint-v6 job. PASS requires: RunPod `COMPLETED`,
    `output.ok == true`, JPEG present in storage, webhook sets DB `completed`,
    output URL loads, input cleaned up, exactly one credit captured.
11. Reopen submissions via the pause mechanism from step 2. Do NOT phrase this
    as "re-enable v6" — v6 has no feature flag.
12. Collect the first real v6 execution timeline before anyone reconsiders the
    420s timeout.

## 7. FALLBACK LADDER (only if warmup/logs show the CUDA backend unavailable
or failing — stop and report between rungs, do not chain)

1. Force comfy-kitchen's pure-Python wheel: install the official
   `comfy_kitchen-0.2.31-py3-none-any.whl` explicitly (download from PyPI
   files, `pip install <wheel-path>`), keeping the exact API pinned ComfyUI
   expects. Record `list_backends()` before/after. Note perf impact
   prominently as temporary.
2. Only if performance proves unacceptable AND owners confirm RunPod driver
   >= r580: evaluate `pytorch/pytorch:2.9.x-cuda13.x-cudnn9-runtime`. Report
   exact tag + digest; do not apply.
3. Legacy rollback only: `comfy-kitchen==0.2.16` + the ComfyUI commit whose
   requirements accepted it. Report the chosen commit SHA and why.

## 8. REQUIRED REPORT FORMAT (`deepclean-worker/build-report.md`)

1. Summary (5 lines max).
2. Files changed (path + one-line reason).
3. Final pinned versions table: base image + digest, torch/torchvision/
   torchaudio (constraints), comfy-kitchen, ComfyUI commit, all 9 node packs,
   SAM2, plus the SAM2 `sed` line used.
4. Smoke-test plan and expected outputs per §4.6 (and actual outputs if CI ran).
5. Open risks: comfy-kitchen CUDA-wheel uncertainty (G8 degradation path), G5
   warmup bug, `:latest` tag still emitted by CI (recommend owners stop using it).
6. Owner-only commands: CI dispatch, digest capture, endpoint image update,
   reconcile dry-run, rollback tag reference.
7. Confirmation of the FORBIDDEN list (nothing outside §3 touched; prompt files
   preserved).
8. Contradictions with Ground Truth (if any) — none expected.

## 9. FINAL HANDOFF RULES

- End with one of: `READY_NEEDS_OWNER_BUILD` (expected — you have no Docker),
  `READY_FOR_OWNER_REVIEW` (only if you verified every §4.6 gate from real CI
  logs), or `BLOCKED` + reason.
- Include full logs verbatim for anything that failed.
- Do not make any further changes after writing the report.
- Accuracy and completeness beat speed. A wrong pin that passes tests is worse
  than an honest BLOCKED.
