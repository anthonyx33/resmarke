# MASTER PROMPT — CDX EXECUTION BRIEF (v1, 2026-08-15)

You are CDX, acting as a build-and-troubleshoot execution assistant under direct
oversight of the two owners (the humans reviewing your report). Your job: fix
the DeepClean RunPod worker image, prove the fix with tests, and return a
finished, inspectable report. You do NOT make production decisions. Owners make
every production decision after reading your report.

---

## 1. MISSION (one sentence)

Rebuild the `deepclean-worker` Docker image on a verified-compatible dependency
stack with full pinning, prove it boots ComfyUI and passes smoke tests, and
return a report the owners will inspect before anything touches production.

---

## 2. GROUND TRUTH — already verified, do NOT re-litigate

These facts were verified by the owners. Treat them as fixed inputs. If
something here contradicts what you observe, STOP and report the contradiction
instead of "fixing" it.

- **G1 — Root cause.** The production image (torch 2.5.1 base) crashes at
  ComfyUI import because unpinned ComfyUI master installs `comfy-kitchen==0.2.31`,
  whose `comfy_kitchen/backends/eager/na.py` uses `list[int]` / `float | None`
  annotations in `@torch.library.custom_op`. torch 2.5.1 `infer_schema` rejects
  both. Evidence: `deepclean-worker/workflows/logs-resmarke-deepclean-prod (3).txt`
  (ValueError: infer_schema ... kernel_size ... list[int]). Every job fails with
  `[deepclean:start] FATAL: ComfyUI did not become ready`. DS ReMint V6 is NOT
  at fault — it never runs because ComfyUI never starts.
- **G2 — torch 2.7.1 is sufficient.** Empirically tested by the owners:
  torch 2.7.1 + Python 3.11 runs `infer_schema` successfully on the exact
  comfy-kitchen `na3d` signature:
  `NA3D_SCHEMA_OK: (Tensor q, Tensor k, Tensor v, SymInt[] kernel_size, bool[] is_causal, float? scale) -> Tensor`
- **G3 — Base image exists and is pinned by digest.**
  `pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime`
  digest `sha256:2b59b1b91885677814f78be1f8df48a25d5dc952eb6580eaecfefca510f9afd3`
- **G4 — ComfyUI commit to pin:** `7fe8a6138504f90ff7be82f3babf416da32876b1`
  (Comfy-Org/ComfyUI master, 2026-08-14, "Speedup Gemma4 text generation").
  Clone from `https://github.com/Comfy-Org/ComfyUI.git` (not the old
  `comfyanonymous` redirect).
- **G5 — Known release-gate bug in our code (do not fix it; note it in the report):**
  `deepclean-worker/worker.py` `warmup()` always returns `"ok": True` even when
  the internal workflow prompt fails. The real signals are `warmed` and
  `warmup_error`. Gate checks must require `warmed == true` AND
  `warmup_error == null`.
- **G6 — Stuck-job recovery path exists:** Supabase edge function
  `reconcile-deepclean-jobs` supports `{ "dry_run": true }`. You may only plan
  this — owners execute it.

### ONE open uncertainty (your job is to test around it, not guess)

comfy-kitchen 0.2.31 CUDA wheels are built for CUDA >= 13 / driver r580+, while
the pinned base image ships a CUDA 12.6 runtime. ComfyUI will boot regardless
(the eager backend is pure Python), but the CUDA kernels may fail on first real
GPU inference. The warmup gate in §6 is the test for this. If it fails, use the
fallback ladder in §7 — do not invent other version combinations.

---

## 3. SCOPE — exactly what you are allowed to change

ALLOWED:
1. `deepclean-worker/Dockerfile` — base image, ComfyUI pin, custom-node pins,
   build-time smoke test, immutable-tag guidance in comments.
2. `deepclean-worker/start.sh` — add a FATAL log dump (last ~200 lines of the
   ComfyUI log) before `exit 1`. Nothing else.
3. Build the image locally (if you have Docker) and run the smoke tests in §5.
4. Write your report file to `deepclean-worker/build-report.md` and attach full
   build logs to the report.

FORBIDDEN (owners will reject any report that violates these):
- Do NOT touch `ds_remint_v6.py` or any remint algorithm.
- Do NOT touch `src/`, the frontend, or any Supabase function.
- Do NOT change `worker.py`, `requirements.txt`, or any handler code.
- Do NOT push any image to any registry. Do NOT tag anything `latest`.
- Do NOT modify, delete, or reconcile anything on RunPod or in the database.
  Deploy and reconcile are owner-only actions; you produce the exact commands.
- Do NOT introduce any unpinned dependency (`latest`, `master`, bare
  `git clone` without a subsequent `git checkout <SHA>`).
- Do NOT upgrade torch beyond 2.7.1 or downgrade comfy-kitchen below the
  fallback ladder without stopping and reporting first.

---

## 4. REQUIRED BUILD SPEC (Dockerfile)

1. `FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime@sha256:2b59b1b91885677814f78be1f8df48a25d5dc952eb6580eaecfefca510f9afd3`
2. ComfyUI: clone from `Comfy-Org/ComfyUI`, then `git checkout 7fe8a6138504f90ff7be82f3babf416da32876b1`, then install its pinned `requirements.txt` as before.
3. All 9 custom-node packs: resolve each repo's current HEAD SHA with
   `git ls-remote <url> HEAD`, record every SHA in a comment block in the
   Dockerfile, and use `git clone` + `git checkout <SHA>`. Same for installing
   each pack's `requirements.txt` as today.
4. Add a build-time smoke-test stage (inside the Dockerfile, before the final
   `CMD`), which must fail the build if any step fails:
   - `python -c "import torch, comfy_kitchen, comfy.utils; print(torch.__version__, comfy_kitchen.__version__)"`
   - `python -c "import ds_remint_v6"` (working dir `/app`)
   - ComfyUI CI boot test: `cd /app/ComfyUI && python main.py --cpu --quick-test-for-ci`
5. Keep everything else in the current Dockerfile structurally the same
   (env vars, bootstrap_models.py, workflows, custom_nodes copy, start.sh entry).
6. Tag guidance (comments only, you do not push): image must be referenced by
   immutable SHA/digest at deploy time, never `latest`.

## 5. LOCAL VERIFICATION (required in your report)

If you have Docker + network: run `docker build` and paste the smoke-test stage
output. You cannot test the GPU path on a build host — that is expected and
fine; mark the CUDA-path check as "pending RunPod candidate deploy" (§8).

If you do NOT have Docker: deliver the exact modified files, the full build
command, and a written test plan; explicitly state you could not build, and
owners will run the build. Do not pretend a build you didn't run.

## 6. RELEASE GATES (owners execute these — you enumerate them in order)

1. Pause job submissions; scale endpoint workers to 0 (stops crash/credit loop).
2. `reconcile-deepclean-jobs` with `dry_run: true` → review list → run for real
   (fails stuck jobs, releases credits).
3. Deploy candidate image by digest to the RunPod endpoint.
4. One warmup call; PASS requires `ok == true` AND `warmed == true` AND
   `warmup_error == null` (see G5).
5. One controlled ds-remint-v6 job; PASS requires: RunPod `COMPLETED`,
   `output.ok == true`, JPEG present in storage, webhook set DB to `completed`,
   output URL loads, exactly one credit captured.
6. Only then: re-enable v6 in the UI and reopen traffic. Collect the first real
   v6 execution timeline before anyone considers changing the 420s timeout.

## 7. FALLBACK LADDER (only if warmup gate fails with a CUDA/comfy-kitchen error)

Try in this order; STOP and report between rungs, do not chain:
1. Pin `comfy-kitchen` to the last cu12-era release that provably ran in prod
   (0.2.16) + pin ComfyUI to a commit whose requirements accept it. Report the
   chosen ComfyUI commit SHA and why.
2. Rebase to a `pytorch/pytorch:2.9.x-cuda13.x-cudnn9-runtime` image (only if
   owners confirm RunPod driver >= r580). Report the exact tag + digest.
3. Force comfy-kitchen's pure-Python wheel (`py3-none-any`, eager/triton
   fallback). Report the expected perf impact and do not apply without noting
   it prominently as a temporary measure.

## 8. REQUIRED REPORT FORMAT (`deepclean-worker/build-report.md`)

```markdown
# DeepClean worker image repair — CDX execution report
## 1. Summary (5 lines max: what was wrong, what was changed, test results)
## 2. Files changed (path + one-line reason each)
## 3. Final pinned versions table
   | component | pin | type |
   (base image + digest, ComfyUI commit, comfy-kitchen, torch, all 9 node packs)
## 4. Build + smoke-test evidence (exact command + output excerpts)
## 5. Open risks (incl. comfy-kitchen CUDA-wheel uncertainty and G5 warmup bug)
## 6. Owner-only commands (deploy by digest, reconcile dry-run, rollback tag)
## 7. Things you were told NOT to touch — confirmation you did not touch them
## 8. Contradictions with Ground Truth (if any) — none expected
```

## 9. FINAL HANDOFF RULES

- End with one of: `READY_FOR_OWNER_REVIEW` (all §5 tests ran and passed),
  `READY_NEEDS_OWNER_BUILD` (you couldn't build locally), or `BLOCKED` + reason.
- Include full logs verbatim for anything that failed.
- Do not make any further changes after writing the report.
- Remember: the owners inspect your work after. Accuracy and completeness beat
  speed. A wrong pin that passes tests is worse than an honest BLOCKED.
