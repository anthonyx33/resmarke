# DeepClean worker candidate build report

## 1. Summary

Production fails before DS ReMint V6 because torch 2.5.1 cannot import the ComfyUI-pinned comfy-kitchen 0.2.31 custom-op schema.
The candidate preserves run #39's worker/source snapshot while changing the base stack to torch 2.7.1 / CUDA 12.6 and constraining the torch triplet.
ComfyUI, nine external node packs, and SAM2 now use immutable source commits; dependency-install failures are fatal.
CI now publishes only the immutable git-SHA tag, and fatal build gates cover imports, versions, workflow shape, registered classes, `res_2s`, and `pip check`.
Local static checks passed; Docker and GPU validation are pending the owner-triggered GitHub Actions build and release gates.

## 2. Files changed

| Path | Reason |
|---|---|
| `deepclean-worker/Dockerfile` | Pin the compatible base image and run-#39 sources, constrain every pip install, make installs fatal, and add build-time gates. |
| `deepclean-worker/constraints.txt` | Constrain only torch 2.7.1, torchvision 0.22.1, and torchaudio 2.7.1. |
| `deepclean-worker/smoke_test.py` | Boot ComfyUI on CPU, validate every workflow class through `/object_info`, verify the `res_2s` sampler choice, and stop the process cleanly. |
| `.github/workflows/deepclean-worker.yml` | Prevent candidate builds from publishing or moving `:latest`; publish only `${{ github.sha }}`. |
| `deepclean-worker/build-report.md` | Provide this owner-review and execution handoff. |

Exact CI tag-isolation diff:

```diff
           tags: |
-            ghcr.io/${{ github.repository_owner }}/resmarke-deepclean:latest
             ghcr.io/${{ github.repository_owner }}/resmarke-deepclean:${{ github.sha }}
```

No CI path, trigger, permission, runner, login, build context, or push behavior was changed. CI never writes `:latest` after this diff; any future alias promotion is an explicit owner action.

## 3. Final pinned versions

| Component | Pin |
|---|---|
| Base image | `pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime@sha256:2b59b1b91885677814f78be1f8df48a25d5dc952eb6580eaecfefca510f9afd3` |
| torch constraint | `2.7.1` |
| torchvision constraint | `0.22.1` |
| torchaudio constraint | `2.7.1` |
| comfy-kitchen | `0.2.31` through pinned ComfyUI requirements |
| ComfyUI | `7fe8a6138504f90ff7be82f3babf416da32876b1` |
| ComfyUI-GGUF | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` |
| ComfyUI-Impact-Pack | `429d0159ad429e64d2b3916e6e7be9c22d025c3c` |
| ComfyUI-Impact-Subpack | `50c7b71a6a224734cc9b21963c6d1926816a97f1` |
| rgthree-comfy | `6b76ee6f2c5a007710b5a16f97c94330d6ecc871` |
| comfyui_controlnet_aux | `e8b689a513c3e6b63edc44066560ca5919c0576e` |
| ComfyUI-KJNodes | `203eb357743402b437db8ae973a062a9b15387d2` |
| ComfyUI-Inpaint-CropAndStitch | `2dfaf6c9689f16315a428ce3df06983b22a163c0` |
| masquerade-nodes-comfyui | `432cb4d146a391b387a0cd25ace824328b5b61cf` |
| RES4LYF | `26036f647ca15d3048a193daf99a40cecfc3820d` |
| SAM2 | `2b90b9f5ceec907a1c18123530e92e794ad901a4` |

Exact SAM2 rewrite:

```dockerfile
sed -i \
    's|git+https://github.com/facebookresearch/sam2.git|git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4|' \
    /app/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/requirements.txt
```

The Dockerfile immediately checks the rewritten requirement with `grep -Fx`, so a future source-layout mismatch fails the image build.

## 4. Smoke-test plan and evidence

Docker, Podman, actionlint, and hadolint are unavailable on this machine. No container build was claimed or simulated. GitHub Actions must execute the actual Dockerfile and capture the complete build log.

| Gate | Command or behavior | Required evidence | Current status |
|---|---|---|---|
| 1. Imports | Import `torch`, `comfy_kitchen`, `comfy.utils`, and `ds_remint_v6` from `/app` with `/app/ComfyUI` on `PYTHONPATH`. | Command exits 0 and reaches the success marker. | Pending CI. |
| 2. Exact stack | Assert torch starts with `2.7.1` and `torch.version.cuda == "12.6"`. | Log prints exact torch and CUDA runtime versions. | Pending CI. |
| 3. comfy-kitchen | Read `importlib.metadata.version("comfy-kitchen")`, print `list_backends()`, and require `eager.available == true`. | Version `0.2.31`; eager true. CUDA may be unavailable without failing this gate. | Pending CI. |
| 4. Static workflow | Run `python /app/workflows/validate_api_workflow.py`. | `OK`, 43 nodes, required class counts present. | Passed locally; repeats in CI. |
| 5. ComfyUI CI boot | Run `python main.py --cpu --quick-test-for-ci` from `/app/ComfyUI`. | Exit 0; no fatal ComfyUI import/startup error. | Pending CI. |
| 6. Live API | `smoke_test.py` starts CPU ComfyUI on port 8199, polls `/object_info`, validates all 31 unique workflow classes, checks `res_2s` under `KSampler.input.required.sampler_name[0]`, then terminates ComfyUI. | Three `OK:` lines and exit 0; failures include the final 200 ComfyUI log lines. | Helper syntax/logic passed locally; live boot pending CI. |
| 7. Package consistency | Run `python -m pip check` after every install and all other gates. | `No broken requirements found.` | Pending CI. |

Local evidence collected before this report:

```text
OK: workflow YAML parses
OK: /Users/a/Documents/NOSYNF/deepclean-worker/workflows/remarkee-max-v2.api.json is ComfyUI API format.
Nodes: 43
OK: smoke-test helpers loaded 31 unique workflow class types
OK: res_2s is checked as a sampler choice, not a class type
OK: all 3 Dockerfile pip install commands apply constraints
OK: no non-fatal install fallback or moving git clone remains
OK: CI publishes only the immutable github.sha tag
OK: forbidden tracked paths unchanged
OK: final pre-report syntax and whitespace checks passed
```

The exact Dockerfile fetch operation was also executed against every pinned repository. All 11 fetches returned the requested commit exactly:

```text
OK ComfyUI 7fe8a6138504f90ff7be82f3babf416da32876b1
OK ComfyUI-GGUF 6ea2651e7df66d7585f6ffee804b20e92fb38b8a
OK Impact-Pack 429d0159ad429e64d2b3916e6e7be9c22d025c3c
OK Impact-Subpack 50c7b71a6a224734cc9b21963c6d1926816a97f1
OK rgthree-comfy 6b76ee6f2c5a007710b5a16f97c94330d6ecc871
OK controlnet_aux e8b689a513c3e6b63edc44066560ca5919c0576e
OK KJNodes 203eb357743402b437db8ae973a062a9b15387d2
OK Inpaint-CropAndStitch 2dfaf6c9689f16315a428ce3df06983b22a163c0
OK masquerade 432cb4d146a391b387a0cd25ace824328b5b61cf
OK RES4LYF 26036f647ca15d3048a193daf99a40cecfc3820d
OK SAM2 2b90b9f5ceec907a1c18123530e92e794ad901a4
```

No build logs exist yet because no build ran. Owners should attach the unabridged GitHub Actions log to this report during review.

### Non-product tooling failures

Two local audit-tool invocations initially failed without changing candidate behavior:

```text
apply_patch verification failed: invalid patch: multiple operations target /Users/a/Documents/NOSYNF/deepclean-worker/Dockerfile
```

The patch wrapper rejected a combined delete/add operation before applying it. The same intended replacement was then applied as separate patch operations.

```text
AssertionError: ['# Guard every pip install against moving the torch stack supplied by the base', '    python -m pip install --no-cache-dir -c /app/constraints.txt -r /app/ComfyUI/requirements.txt', '            python -m pip install --no-cache-dir -c /app/constraints.txt \\', 'RUN python -m pip install --no-cache-dir -c /app/constraints.txt -r /app/requirements.txt']
```

That audit helper accidentally treated a comment containing the words `pip install` as a command. Restricting it to the three executable `python -m pip install` lines passed and confirmed all three use `/app/constraints.txt`.

## 5. Traffic-pause mechanisms for owner selection

There is no existing DeepClean/V6 feature flag or maintenance switch in the inspected code. `create-deepclean-job` reserves a credit, the browser uploads the input, and the separate `dispatch-deepclean-job` function sends the RunPod request. Available owner choices are:

| Mechanism | Scope and tradeoff |
|---|---|
| UI kill switch before job creation | Fast and user-friendly, and avoids new reservations from the normal UI. It requires a frontend change/deploy and does not block direct Edge Function callers. |
| Dispatch-layer gate in `dispatch-deepclean-job` | Authoritative at the GPU handoff and blocks direct clients. It requires an owner-authored Supabase function change/deploy; jobs created immediately before the gate may require cancellation/reconciliation. |
| Shared Supabase-controlled maintenance flag checked by both create and dispatch | Most authoritative and dynamically reversible. It is a broader design/configuration change and must not be improvised during this candidate build. |
| Set `workersMin=0` only | Not a traffic pause. Requests can still queue and credits can remain reserved, so this must not be used as the submission gate. |
| Remove RunPod credentials or break the endpoint | Not recommended. Dispatch returns errors after job creation and can create avoidable recovery work. |

Recommended owner choice: an authoritative dispatch-layer maintenance response combined with a UI notice, with the exact behavior reviewed separately. CDX made no implementation or production decision here.

## 6. Open risks

- comfy-kitchen 0.2.31's compiled Linux wheels target CUDA 13 / driver r580+, while this image deliberately uses CUDA 12.6. A missing native `cuda` backend alone is expected and not a release failure when eager/Triton works. If warmup or the controlled V6 job fails specifically because of comfy-kitchen/CUDA, fallback rung 1 is the verified pure-Python wheel at the prompt-pinned URL and SHA-256; stop for owner review before applying it.
- `worker.py` warmup always reports `ok: true`. Production acceptance must additionally require `warmed: true` and `warmup_error: null`.
- Runtime code does not explicitly emit `comfy_kitchen.list_backends()` and changing `worker.py`/`start.sh` was forbidden. CI records the exact backend map. RunPod may log backend import warnings, but an exact runtime backend map requires separate owner authorization for observability code; it is not inferred from warmup success.
- The constraints cover only the torch triplet. ComfyUI, node, handler, apt, action, and transitive package versions remain partly floating. Complete hash locking is explicitly deferred follow-up work.
- CPU build gates prove imports and node registration, not native GPU execution. The single warmup and controlled V6 job remain mandatory.
- Current repository `main` is `86ae103babf6202ef49b0f1328f33b873c3b81c9`. `git diff 10d1516..HEAD -- deepclean-worker .github/workflows/deepclean-worker.yml` was empty before these candidate changes, so post-run-#39 commits did not alter the worker source snapshot being repaired.

## 7. Owner-only commands and release order

These commands are a handoff, not actions CDX executed. Use exact-path staging so the three untracked `CDX_MASTER_PROMPT*.md` files remain outside the commit.

### 7.1 Commit and run the SHA-only candidate build

```bash
CANDIDATE_BRANCH=fix/deepclean-worker-torch-2-7-1
git switch -c "$CANDIDATE_BRANCH"
git add \
  .github/workflows/deepclean-worker.yml \
  deepclean-worker/Dockerfile \
  deepclean-worker/constraints.txt \
  deepclean-worker/smoke_test.py \
  deepclean-worker/build-report.md
git diff --cached --check
git diff --cached --stat
git commit -m "Fix DeepClean worker dependency stack"
git push -u origin "$CANDIDATE_BRANCH"

CANDIDATE_SHA=$(git rev-parse HEAD)
gh workflow run deepclean-worker.yml --ref "$CANDIDATE_BRANCH"
RUN_ID=$(gh run list \
  --workflow deepclean-worker.yml \
  --branch "$CANDIDATE_BRANCH" \
  --event workflow_dispatch \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
gh run view "$RUN_ID" --log > "deepclean-worker-build-${RUN_ID}.log"
```

Review the full log against every gate in section 4. Confirm the registry contains the SHA tag and no candidate `:latest` update:

```bash
CANDIDATE_DIGEST=$(gh api --paginate \
  "/users/anthonyx33/packages/container/resmarke-deepclean/versions?per_page=100" \
  --jq ".[] | select(.metadata.container.tags[]? == \"${CANDIDATE_SHA}\") | .name" \
  | head -n 1)
test -n "$CANDIDATE_DIGEST"
printf '%s\n' "$CANDIDATE_DIGEST"
CANDIDATE_IMAGE_REF="ghcr.io/anthonyx33/resmarke-deepclean@${CANDIDATE_DIGEST}"
printf '%s\n' "$CANDIDATE_IMAGE_REF"
```

### 7.2 Pause, snapshot, scale down, and reconcile

First activate the owner-selected traffic pause. Then snapshot the complete endpoint and attached template before mutation:

```bash
curl -fsS \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  "https://rest.runpod.io/v1/endpoints/${RUNPOD_ENDPOINT_ID}" \
  > /tmp/deepclean-endpoint-before.json

RUNPOD_TEMPLATE_ID=$(jq -r '.templateId // .template.id' /tmp/deepclean-endpoint-before.json)
test -n "$RUNPOD_TEMPLATE_ID"
test "$RUNPOD_TEMPLATE_ID" != null

curl -fsS \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  "https://rest.runpod.io/v1/templates/${RUNPOD_TEMPLATE_ID}" \
  > /tmp/deepclean-template-before.json

PREVIOUS_IMAGE_REF=$(jq -r '.imageName' /tmp/deepclean-template-before.json)
test -n "$PREVIOUS_IMAGE_REF"
printf '%s\n' "$PREVIOUS_IMAGE_REF"
```

Use the existing admin control or RunPod dashboard to set `workersMin=0` while leaving `workersMax`, GPU type, timeout, scaler, and volume settings unchanged. Verify the endpoint snapshot after that one field change.

Run reconciliation dry first, review every proposed action, and only then run the real pass:

```bash
curl -fsS \
  -X POST "${SUPABASE_URL}/functions/v1/reconcile-deepclean-jobs" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'Content-Type: application/json' \
  --data '{"dry_run":true}' \
  | jq .

# OWNER REVIEW POINT: do not continue until every dry-run action is approved.

curl -fsS \
  -X POST "${SUPABASE_URL}/functions/v1/reconcile-deepclean-jobs" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H 'Content-Type: application/json' \
  --data '{"dry_run":false}' \
  | jq .
```

### 7.3 Deploy only the image digest

The endpoint references a RunPod serverless template. Update only that template's image field; the documented `runpodctl template update --image` path leaves endpoint GPU, scaling, timeout, and network-volume settings untouched:

```bash
runpodctl template update "$RUNPOD_TEMPLATE_ID" --image "$CANDIDATE_IMAGE_REF"

curl -fsS \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  "https://rest.runpod.io/v1/templates/${RUNPOD_TEMPLATE_ID}" \
  | jq '{id, name, imageName, containerDiskInGb, volumeInGb, volumeMountPath}'

curl -fsS \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  "https://rest.runpod.io/v1/endpoints/${RUNPOD_ENDPOINT_ID}" \
  > /tmp/deepclean-endpoint-after.json
```

Owners must compare `/tmp/deepclean-endpoint-before.json` and `/tmp/deepclean-endpoint-after.json` and confirm GPU type, workers maximum, execution timeout, scaler, and network volume are unchanged. Restore exactly one worker for the warmup gate.

### 7.4 One warmup, then one controlled V6 job

Run exactly one synchronous warmup:

```bash
curl -fsS \
  -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H 'Content-Type: application/json' \
  --data '{"input":{"action":"warmup"}}' \
  | tee /tmp/deepclean-warmup.json

jq -e '
  .status == "COMPLETED" and
  .output.ok == true and
  .output.warmed == true and
  .output.warmup_error == null
' /tmp/deepclean-warmup.json
```

Inspect RunPod logs for ComfyUI readiness, worker-handler startup, and absence of `ModuleNotFoundError`/comfy-kitchen schema errors. Do not infer runtime native-CUDA availability unless it is actually logged.

Run one controlled `ds-remint-v6` job only after warmup passes. Accept only if RunPod reports `COMPLETED`, `output.ok` is true, the JPEG exists and loads from storage, the webhook changes the database job to `completed`, input cleanup succeeds, and exactly one credit is captured. Then reopen submissions and record the first real V6 timeline before changing the 420-second timeout.

### 7.5 Rollback

The rollback target is the exact `PREVIOUS_IMAGE_REF` captured before deployment, not `:latest`:

```bash
runpodctl template update "$RUNPOD_TEMPLATE_ID" --image "$PREVIOUS_IMAGE_REF"
```

After rollback, verify the template image and endpoint settings again. Reopen traffic only after the rollback worker passes the owners' chosen health check.

## 8. Forbidden-scope confirmation

- `deepclean-worker/start.sh` was not changed.
- `deepclean-worker/worker.py`, handler behavior, and warmup behavior were not changed.
- `deepclean-worker/requirements.txt` was not changed.
- `deepclean-worker/ds_remint_v6.py` and every remint algorithm were not changed.
- `src/`, frontend files, and Supabase functions were not changed.
- No migration, RunPod mutation, database mutation, registry push, git commit, remote push, image build, warmup, or paid job was executed.
- No `:latest` image or tag was created.
- `CDX_MASTER_PROMPT.md`, `CDX_MASTER_PROMPT_v2.md`, and `CDX_MASTER_PROMPT_v3.md` remain unmodified and untracked.
- Only the five files listed in section 2 are intended for owner staging.

## 9. Contradictions with ground truth

None found. All source SHAs accepted the required exact shallow-fetch operation, pinned ComfyUI requirements specify comfy-kitchen 0.2.31, and the worker-related tree was unchanged between `10d1516` and the pre-candidate current `main` commit.

READY_NEEDS_OWNER_BUILD
