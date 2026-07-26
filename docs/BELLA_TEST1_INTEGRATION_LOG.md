# Bella Test1 Integration Log

Last updated: 2026-07-26
Branch: `bella-test1`
Remote push status: not pushed

## Current Local Commits

```text
current feat(floorplan): backport django band-carve openings
265f6351 feat(floorplan): validate cody semantic masks
a5130dbc feat(floorplan): add cody cubicasa mask adapter
dfe6c005 fix(test): restore local pytest environment
c1182072 feat(floorplan): add cody semantic weight contract
4b659fb5 feat(floorplan): backport django image route profiling
9f2d7260 docs: record bella-test1 integration status
9dc25eda feat(floorplan): attach room evaluation debug report
466c425a feat(floorplan): add cody room evaluation core
87c14d43 feat(sql): port kai catalog import flow
55f697cf feat(catalog): port surface material backup assets
```

## Integrated Work

### Layout / Scene Boundary Contract

- Added `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md` to lock the architecture language:
  - floor-plan recognition produces `layout_json`
  - proposal generation produces `scene_json`
  - Graph RAG retrieves relationship evidence only
  - geometry planning and rule checking remain deterministic decision layers
  - final deployment may add `render-export-worker`
  - MinIO and AWS S3 are separated by deployment target
- Added compatibility API fields without breaking existing frontend consumers:
  - `/api/floorplan/analyze` now returns `layout_json` beside the legacy `analysis`
  - `/api/projects/{project_id}/floorplan/analyze` now returns `layout_json` beside `analysis`
  - `/api/floorplan/confirm` now returns `layout_json` beside the legacy `floorplan`
  - `/api/scene/generate` now accepts `layout_json` and returns `scene_json` beside the legacy top-level scene payload
- Updated the browser scene generation flow to read `response.scene_json || response`, so the new contract is preferred while old payloads still work.
- No Redis worker, Graph RAG runtime, MinIO/S3 runtime, or render worker was implemented in this slice.

### Surface Material Backup Assets

- Ported surface material processing and wall material candidate assets.
- Added `backend/catalog/surface_material_processing.py`.
- Added surface catalog/manifest/candidate JSON files and static surface assets.
- Added scene texture UV support.
- Verification: full test suite passed after commit.

### Kai PostgreSQL Catalog Flow

- Ported the `origin/kai` 10,550-item catalog import flow.
- Kept Bella's existing 9,350 official catalog SQL flow intact.
- Added:
  - `scripts/sql/import_catalog_to_postgres.py`
  - `scripts/sql/roompilot_catalog_10550_schema.sql`
  - `scripts/sql/README_10550.md`
  - `JSON/furniture/all_furniture_appliance_catalog.json`
  - `JSON/manifests/*`
- Removed unrelated `JSON/materials/**` from the patch before commit.
- Import dry-run result:
  - catalog: 10,550
  - manifest: 10,550
  - upload result: 10,550
  - item types: 87
  - warnings: 0
- PostgreSQL connection status: local `localhost:5432` is not reachable, so no live DB fetch has been completed yet.
- Cleaned `.env.example` into a readable local setup template:
  - OpenRouter can stay blank and fall back to local rules.
  - `OPENROUTER_SITE_URL` now points to `http://127.0.0.1:8002`.
  - `OPENROUTER_APP_NAME` now uses `roompilot`.
  - PostgreSQL catalog import keys match the 10,550 importer: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_ADMIN_DB`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE`, `DB_CONNECT_TIMEOUT`, and `DB_APPLICATION_NAME`.
- Added an env-template contract test so those defaults do not drift.

### Cody Room Recognition Evaluation

- Updated Cody semantic status metadata to Cody/CubiCasa v5:
  - default weights: `training/model_finetuned_v5.pkl`
  - SHA-256: `b7a280d2d7cf2dde580a947e1ebc7b4d12e53135c05581babb3b5797a166f4cf`
- Added reusable room evaluation helpers:
  - label normalization
  - room mask IoU matching
  - confusion matrix
  - precision/recall/hit-rate/mean-IoU summary
- Added polygon-based evaluation so Bella can score existing spatial output before Cody v5 model inference is fully wired.
- `analyze_floorplan_image(..., evaluation_reference_rooms=...)` now attaches `room_evaluation` when reference room polygons are supplied.

### Django Version4 Image Route Backport

- Reviewed `origin/django` `Final-Project_Version4` and avoided a whole-directory import.
- Added a lightweight image profile seam for floor-plan uploads:
  - `color_line_art` -> `color_mask_then_otsu`
  - `grayscale_line_art` -> `otsu`
  - `scanned_grayscale` -> `adaptive_threshold_review`
- `analyze_floorplan_image()` now returns `image_profile` so the API exposes whether a colored drawing is being handled explicitly.
- Cody image decoding now applies a color/deep-ink mask before the existing grayscale recognition path when the upload is detected as colored line art.
- Added focused tests for colored line-art and black-line-art profile behavior.

### Django Version4 Band-Carve Opening Backport

- Backported the deterministic `band_carve` opening repair from `origin/django` `Final-Project_Version4/png_pipeline.py`.
- Integrated it into Bella's `backend/floorplan/cody_adapter.py` before Cody's solid wall/opening detection:
  - scans horizontal and vertical wall bands
  - detects sustained anomalous cross-sections caused by embedded door/window strokes
  - carves those runs out of the wall mask so downstream Cody detection can see a real gap
  - ignores whole-wall anomalous bands to avoid damaging hollow/double-line wall styles
- Added `diagnostics.band_carve_count` so API results can show when the Django repair path was active.
- Did not port Django's torch CNN `opening_ml.py` yet; it depends on local sample folders and runtime model training. Bella now has the safer deterministic repair first.

### Cody V5 Semantic Weight Contract

- Kept `bella-test1` as the integration baseline and reviewed other people's branches through remote refs/worktrees only.
- Deferred `origin/main` / `origin/ben` VibeCoding documentation per project priority.
- Started functional integration with `origin/cody` only, before touching Django/Kai/Yen work.
- Added a Cody v5 semantic weight preparation contract:
  - default weight path remains `training/model_finetuned_v5.pkl`
  - existing local weights short-circuit without network
  - `CC_WEIGHTS` custom overrides are never auto-downloaded
  - missing default weights can resolve the GitHub Release asset URL
  - downloads land in `.part`, pass SHA-256, then atomically replace the target
  - checksum or download failures clean up partial files and return explicit reasons
- `cody_semantic_room_labeler_status()` now exposes the Release asset API endpoint in addition to the direct URL and SHA-256.

### Cody CubiCasa Mask Adapter

- Added a safe CubiCasa v5 mask orchestration seam without importing the heavyweight torch/CubiCasa stack at API import time.
- `ensure_cody_semantic_masks(...)` now:
  - reuses existing valid `*_mask.npz` cache files when they include `room.npy`
  - prepares default Cody v5 weights through the existing weight contract only when masks are missing
  - supports `CC_INFER_SCRIPT` while defaulting to `scripts/infer_cubicasa.py`
  - returns clear fallback reasons for missing weights, missing inference script, inference failure, or missing output files
  - accepts an injected runner so the subprocess contract can be verified without downloading the 200MB model or installing torch
- The full Cody inference script was not copied yet because `training/CubiCasa5k` and runtime torch assets are not verified in Bella. The integration now has a controlled adapter point ready for that script.
- Added Cody mask cache loading and validation:
  - requires `room`, `wall`, `window`, `door`, and `icon` fields
  - requires all arrays to be 2D with matching shape
  - normalizes wall/window/door arrays to bool and room/icon arrays to uint8
  - ignores invalid cache files in semantic status instead of reporting a false ready state
- Checked `origin/cody`; the branch includes `scripts/infer_cubicasa.py` and precomputed `cubicasa/**` outputs, but not the external `training/CubiCasa5k` runtime tree. A true torch/CubiCasa smoke test is still blocked until that runtime is installed or supplied.

### Local Test Environment Recovery

- Diagnosed the failing test environment:
  - `python` and `py` resolve to WindowsApps shims inside the sandbox
  - direct `Python312` execution works with elevated command permission
  - pytest needed a project-local temp directory because `C:\Users\user\AppData\Local\Temp\pytest-of-user` was not accessible
- Created a local ignored `.venv/` from `C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe`.
- Fixed `pyproject.toml` so editable install works:
  - explicitly package `backend`
  - constrain `opencv-python` to `>=4.10,<5`
- Verified `pip install -e ".[server,vision]"` now succeeds.
- Fixed sparse colored floor-plan line art detection by adding `saturated_ratio` to `image_profile`; sparse colored drawings no longer fall through to `grayscale_line_art`.
- Rebuilt `.venv/` after its launcher was created with a mojibake worktree path:
  - stopped the local `bella-test1-clean` uvicorn process that was locking `.pyd` and `.dll` files
  - removed the broken `.venv/`
  - recreated it with `C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv`
  - reinstalled `.[server,vision]` and `pytest`
  - verified direct `.venv\Scripts\python.exe` imports for `pytest`, `cv2`, `fastapi`, and `numpy`

## Verification

Latest full suite before the Django image-route backport:

```text
409 passed, 2 skipped, 3 warnings
```

Targeted floorplan suite before the Django image-route backport:

```text
30 passed, 3 warnings
```

Current verification after the Django image-route backport:

```text
py_compile passed for:
- backend/floorplan/vision/image.py
- backend/floorplan/vision/analysis.py
- backend/floorplan/cody_adapter.py
- tests/test_floorplan_vision.py
```

Runtime pytest is currently blocked in this desktop session:

```text
python.exe: 指定的登入工作階段不存在
bundled Python: No module named pytest / cv2
uv: command not found
```

Current verification after the Cody v5 semantic weight contract:

```text
py_compile passed for:
- backend/floorplan/vision/cody_semantic.py
- tests/test_cody_semantic_status.py

direct bundled-Python contract check passed:
- existing/default download success path with fake payload
- checksum mismatch rejection and .part cleanup
- CC_WEIGHTS custom override not auto-downloaded
```

Current verification after local test environment recovery:

```text
43 passed, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_floorplan_vision.py `
  tests/test_floorplan_vision_api.py `
  tests/test_floorplan_room_inference.py `
  tests/test_floorplan_room_evaluation.py `
  tests/test_cody_semantic_status.py `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

Current verification after the Cody CubiCasa mask adapter:

```text
15 passed

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_cody_semantic_status.py `
  --basetemp=.tmp\pytest -p no:cacheprovider

51 passed, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_floorplan_vision.py `
  tests/test_floorplan_vision_api.py `
  tests/test_floorplan_room_inference.py `
  tests/test_floorplan_room_evaluation.py `
  tests/test_cody_semantic_status.py `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

Current verification after the Django band-carve opening backport:

```text
23 passed

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_floorplan_vision.py `
  --basetemp=.tmp\pytest -p no:cacheprovider

53 passed, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_floorplan_vision.py `
  tests/test_floorplan_vision_api.py `
  tests/test_floorplan_room_inference.py `
  tests/test_floorplan_room_evaluation.py `
  tests/test_cody_semantic_status.py `
  --basetemp=.tmp\pytest -p no:cacheprovider

4 passed, 19 deselected

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_floorplan_vision.py `
  -k "builder_plan_630 or floor04" `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

Current verification after the layout/scene boundary contract update:

```text
py_compile passed for:
- backend/server/main.py
- backend/floorplan/vision/confirmation.py

21 passed, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
$env:PYTHONPATH=(Resolve-Path .).Path + ';' + (Resolve-Path .venv\Lib\site-packages).Path
C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe -m pytest `
  tests/test_floorplan_vision_api.py `
  tests/test_project_workflow_api.py `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

Current verification after rebuilding `.venv/`:

```text
direct venv import check passed:
- pytest
- cv2
- fastapi
- numpy

21 passed, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_floorplan_vision_api.py `
  tests/test_project_workflow_api.py `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

Current verification after wiring `layout_json` into `/api/scene/generate`:

```text
py_compile passed for:
- backend/server/main.py
- backend/server/scene_service.py

34 passed, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_project_workflow_api.py `
  tests/test_floorplan_vision_api.py `
  tests/test_questionnaire_visual_catalog.py `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

Current verification after cleaning `.env.example`:

```text
py_compile passed for:
- tests/test_env_example_contract.py
- scripts/sql/import_catalog_to_postgres.py

4 passed, 1 skipped

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_env_example_contract.py `
  tests/test_catalog_10550_sql.py `
  --basetemp=.tmp\pytest -p no:cacheprovider

Skipped:
- tests/test_catalog_10550_sql.py::test_catalog_10550_postgres_connection_smoke
  because this worktree has no local `.env` with DB_* settings yet.
```

Current verification after frontend `scene_json` fallback support:

```text
node --check passed for:
- backend/server/static/scene_v2.js

3 passed, 96 deselected, 3 warnings

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_scene_v2_contract.py `
  tests/test_project_workflow_api.py `
  -k "scene_generate_response_prefers_scene_json_with_legacy_fallback or scene_generation_uses_the_user_confirmed_floorplan_as_canonical_geometry or scene_entrypoint_cache_key_matches_bundle_content" `
  --basetemp=.tmp\pytest -p no:cacheprovider
```

## Cleanup Notes

- No `.patch`, `.rej`, or `.orig` files are left in the worktree.
- Backup/source patches were integrated into formal project files only.
- Worktree was clean after the Django image-route backport commit.

## Remaining Work

- Start or install PostgreSQL locally, configure `.env`, run the 10,550 import, and verify live SQL counts.
- Decide whether to copy Cody's full CubiCasa inference script into Bella or package it as a deployment-only runtime script with `CC_INFER_SCRIPT`.
- Use `room_evaluation` with real reference-room fixtures before replacing current room-labeling behavior.
- Use the project-local `.venv/` plus project-local pytest temp command above for future focused test runs.
- Finish the Cody integration slice before starting other branches:
  - install or supply `training/CubiCasa5k`; `origin/cody` does not version this runtime tree
  - run a real CubiCasa inference smoke test once weights/script/runtime are present
- Continue the Django Version4 backport with the torch CNN opening classifier and uncertain/autolabel training-data loop only after the deterministic band-carve path is stable on more real samples.
- Integrate Kai S3/GLB management scripts only after Django/Cody floor-plan recognition work is verified.

## 2026-07-26 Requirements Test Shortcut

- Added a `隨機需求` button to the requirements step so test runs can quickly fill the whole questionnaire and jump to the summary stage.
- The shortcut populates:
  - whole-house answers
  - per-room visual answers
  - per-room style/material/ceiling/lighting/air-conditioning finishes
  - `roomRequirementModel.roomRequirements[*]` with confirmed room requirements
- Added room-type polar axes for test data generation:
  - living room, bedroom, dining room, kitchen, bathroom, workspace, balcony, entry, default
- Added weighted A/B preference fields for questionnaire answers:
  - frontend control: strong A, A, balanced, B, strong B
  - stored answer fields: `preferenceWeight`, `preferenceDirection`
  - RAG payload fields: `preference_weight`, `preference_direction`
- Updated the random requirements shortcut so wall and floor materials are sampled from the active style's material options instead of always using the style pack defaults.
- This is a local frontend/testing helper only. It does not change the DB/PostgreSQL work, and no remote push was performed.
