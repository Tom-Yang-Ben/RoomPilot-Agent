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

### Ancai-dev 3D Selection Backport

- Reviewed `origin/ancai-dev` without switching away from `bella-test1`.
- Did not merge the branch wholesale because it removes many Bella catalog, SQL, surface asset, and test files.
- Backported only the low-risk viewer behavior that keeps the current `/scene` visual style intact:
  - GLB model scaling now stays inside the model root, while the furniture wrapper remains in centimeter scale.
  - Furniture selection uses an invisible pick proxy sized from `size_cm`, so oversized GLB meshes do not swallow clicks.
  - Thin floor-overlay objects such as rugs are easier to select because picking falls back to the furniture footprint.
  - Number markers, labels, and contact shadows are excluded from raycast selection.
  - Viewer exposes selected furniture id and projected furniture centers for later 2D/3D sync.
- Added 2D-to-3D furniture selection sync:
  - 2D furniture ids are matched to `scene_objects[].furniture_id`.
  - Clicking a 2D furniture icon or list row syncs to the active 3D viewer when a scene already exists.
  - Confirming 2D layout and entering 3D white model preserves the selected 2D furniture.
- Added 3D-to-2D furniture selection sync:
  - White-model and realistic viewers emit selected scene object changes through `onObjectSelect`.
  - User clicks in 3D update the matching 2D furniture selection by `furniture_id`.
  - Programmatic 2D-to-3D sync does not re-emit selection events, avoiding callback loops.
- Fixed the 2D/3D mirror boundary in the 3D viewer:
  - `sceneData` and 2D layout remain in engine coordinates.
  - The viewer builds a world-frame clone with `z` flipped for floorplan geometry and surface overrides.
  - Furniture positions and rotations are flipped only at render time.
  - Dragging, manual placement, and beam placement convert world coordinates back to scene coordinates before validation/saving.
  - Existing manual 3D add/delete controls and furniture number markers are preserved.
- Verification:
  - `node --check backend/server/static/scene_viewer.js`
  - `node --check backend/server/static/scene_v2.js`
  - `pytest tests/test_scene_v2_contract.py -k "scene_entrypoint_cache_key_matches_bundle_content or changed_scene_module_cache_keys_match_dependency_content or scene_viewer_uses_stable_furniture_pick_proxies_for_3d_selection or 2d_furniture_selection_syncs_to_matching_3d_scene_object or 3d_scene_selection_syncs_back_to_2d_furniture_state or 3d_viewer_flips_scene_z_at_the_visual_boundary_only or 3d_viewer_keeps_manual_furniture_controls_and_number_markers"`

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
- Expanded questionnaire wall/floor recommendations so each style card derives its own ordered material suggestions and color swatches instead of sharing the same two style-level options.
- This is a local frontend/testing helper only. It does not change the DB/PostgreSQL work, and no remote push was performed.

## 2026-07-26 3D Viewer Coordinate Boundary

- Kept canonical scene data in layout/scene coordinates and added a viewer-only world transform for floorplan geometry and furniture display.
- Fixed topdown furniture dragging so screen movement maps directly to topdown world movement; dragging right now increases the saved scene `x` instead of moving the object left.
- Changed 3D manual drag completion from `/api/scene/layout` relayout to `/api/scene/validate` validation, so a user-dragged legal position is preserved instead of being re-snapped by the automatic placement engine.
- Kept manual furniture add/delete controls and numbered 3D markers intact.
- Browser smoke verified on local `http://127.0.0.1:8022/static/verify_scene_viewer.html` before deleting the temporary verification page:
  - two visible fallback furniture objects
  - visible number markers `1` and `2`
  - rightward topdown drag changed `position_cm.x` from `-120` to `65`
  - projected screen `x` moved from `561` to `682`
- Screenshot saved outside the repo:
  `C:/Users/user/.codex/visualizations/2026/07/24/019f93b8-1038-7900-843e-c01e4c13226f/bella-test1-3d-drag-verification.png`

## 2026-07-26 Step 6-8 Condensed Workflow Specification

- Added `docs/BELLA_6_8_CONDENSED_FLOW_SPEC.md`.
- Finalized the reduction from ten workflow steps to eight:
  - Step 6: configuration and preview
  - Step 7: proposal locking and camera selection
  - Step 8: AI rendering and proposal package
- Recorded the accepted 2D/3D workspace, furniture validation, indoor walk,
  material/ceiling/light editing, structure-return, palette, camera, rendering,
  regeneration, proposal-version, and UI/UX decisions.
- Defined the formal `/scene` flow and public APIs as the primary testing seam.
- This update is documentation only. No frontend/backend implementation, commit,
  or remote push was performed.

## 2026-07-26 Step 6 Configuration and Preview Slice

- Changed the visible workflow navigation from ten steps to the approved eight steps.
- Kept the existing internal workflow states for backward-compatible project restore,
  while grouping `layout_2d`, `white_model_3d`, and `realistic_3d` under visible Step 6.
- Integrated a collapsible 2D review panel into the formal Step 6 3D workspace:
  - floor-plan image
  - furniture footprints
  - furniture list
  - matching 2D/3D furniture numbers
  - two-way furniture selection
  - pending invalid-furniture list
- Blocked Step 6 completion while invalid furniture remains and provided a direct
  locate path through the pending list.
- Synchronized successful 3D furniture moves back to the 2D furniture state before
  auto-saving.
- Added a tested scene-to-2D inventory boundary for 3D add, replace, move, and
  delete operations.
- Added a per-item pending action that relayouts only the selected invalid
  furniture while keeping all other furniture position-locked.
- Locked the pending-item reflow action while its request is running to prevent
  repeated clicks or concurrent relayout responses from overwriting newer state.
- Synced final server-side placement failures back into both scene and 2D
  furniture state so rejected items appear in the pending list instead of
  silently blocking the workflow.
- Changed the visible Step 6 navigation entry to reopen the integrated 3D
  configuration workspace after the 2D prerequisite has been completed.
- Aligned the compact furniture layer to the actual rendered image content box,
  including non-4:3 floor-plan images with letterboxing.
- Added a whole-model camera mode as the safe initial overview, while preserving
  free orbit, top-down, and indoor walk modes.
- Browser verification on the restored local project confirmed:
  - 14 furniture items rendered in the synchronized 2D panel
  - zero horizontal page overflow at 1280 x 720
  - collapsible panel state and accessible label changes
  - matching `#8` furniture selection from the 3D list to the 2D list
  - clicking the active Step 6 progress item remains in the integrated 3D workspace
  - zero pending invalid furniture for the verified project
- Verification:
  - `node --check backend/server/static/scene_v2.js`
  - `git diff --check`
  - 117 focused scene workflow, contract, delivery, and walk/edit tests passed
  - full suite: 442 passed, 2 skipped
- No remote push was performed.

## 2026-07-26 3D Door Leaf Wall Alignment

- Changed the 3D display state for confirmed hinged doors from a fixed 58-degree
  partial opening to a 180-degree fully open position.
- Kept the confirmed hinge endpoint, opening width, wall opening, and left/right
  door metadata unchanged.
- Added a diagonal-wall regression test that verifies the open door leaf is
  parallel to the host wall and extends away from the doorway.
- Browser-verified the restored project in both whole-model and top-down views;
  door leaves now fold along the wall instead of crossing the room at an angle.
- Full suite verification: 443 passed, 2 skipped.
- No remote push was performed.

## 2026-07-26 Split-Wall Window Rendering

- Confirmed that the restored project retained five `window_segments`, including
  one `floor_to_ceiling` window; the loss happened only in 3D rendering.
- Added a shared wall-interval check that distinguishes openings embedded in one
  wall segment from openings already represented as gaps between split walls.
- Added standalone 3D assemblies for unmatched gap openings so their frame,
  glazing, sill, and header are generated instead of silently skipped.
- Preserved `sill_height_cm: 0` and `height_cm` for floor-to-ceiling windows.
- Added regression coverage using the restored project's split `wall-6` and
  `window-1` geometry.
- Browser-verified visible window frames and glazing in the restored whole-model
  view.
- Full suite verification: 445 passed, 2 skipped.
- No remote push was performed.

## 2026-07-26 Closed Doors and Opening Edge Cleanup

- Changed the default 3D door presentation from fully open to closed while
  preserving the confirmed hinge endpoint and doorway width.
- Prevented split-wall endpoints that border a door or window from receiving
  junction-cap columns.
- Removed the wall-thickness extension from each split wall top cap so it no
  longer projects into door and window gaps.
- Reduced standalone window sill/header overlap from 12.6 cm per side to a
  0.6 cm seam allowance per side.
- Added regression coverage for closed-door alignment and opening-edge cap
  suppression using the restored project geometry.
- Browser-verified closed doors, cleaner wall faces, and aligned window edges in
  the restored whole-model view.
- Full suite verification: 446 passed, 2 skipped.
- No remote push was performed.

## 2026-07-26 Window Host-Wall Material Consistency

- Fixed standalone gap-window sill and header sections using the first wall's
  material for every opening.
- Added host-wall resolution by `host_wall_id`, with geometry fallback when an
  explicit host id is unavailable.
- Each window now receives the same surface material as its confirmed wall:
  white-wall windows remain white and dark-wall windows remain dark.
- Preserved the existing standard and floor-to-ceiling window height rules.
- Added regression coverage using project `window-5` on `wall-14`.
- Browser-verified consistent window-adjacent wall materials in the restored
  whole-model view.
- Full suite verification: 447 passed, 2 skipped.
- No remote push was performed.

## 2026-07-26 Questionnaire RAG Catalog Furniture in Step 6

- Moved catalog retrieval ahead of the furniture selection Agent so Step 5
  questionnaire data now selects actual database GLBs before Step 6 placement.
- Ranked candidates per room using the selected style card, palette, furniture
  material language, requested footprint, and semantic product-name checks.
- Preserved the database furniture id, GLB URL, match reason, room assignment,
  and stable local scene id through 2D layout and 3D generation.
- Added type routes for dirty or split catalog taxonomies, including real sofa
  families, bathroom storage, mirror cabinets, refrigerators, and washers.
- Added `/api/appliances` without changing the official 9,350-furniture
  contract. The endpoint reads the 10,550 combined Kai catalog and verifies
  appliance assets against the matching 10,550-row upload manifest.
- Browser verification confirmed all 14 generated 2D items carried database
  GLBs, including a LAGAN refrigerator, UDDARP washer/dryer, HEMNES mirror
  cabinet, and a full-size sofa rather than the previous wrong-type chair.
- Allowed real loft-bed models to keep their catalog height instead of being
  rejected by the standard low-bed height guard. The final 2D/3D markers are
  now unique and continuous from 1 through 14.
- Removed runtime white-box fallback rendering. Missing or inaccessible GLBs
  are now listed as blocking Step 6 items and prevent progression.
- Compacted `space_confirmation.design_schemes` so it no longer duplicates the
  complete furniture list and 3D scene payload. The restored test project
  dropped from about 1.05 million serialized characters to about 118 thousand
  without losing its Step 6 furniture.
- Final browser verification rendered 12 of 14 real catalog GLBs. The two AWS
  appliance failures appeared in the pending list, no white fallback was
  created, and progression to Step 7 remained disabled.
- External blocker discovered during live verification:
  - the Kai manifest marks the tested appliance uploads as uploaded
  - both CloudFront and direct S3 URLs for the refrigerator and washer return
    HTTP 403
  - the repository and inspected Kai/Django branches do not contain the
    original local appliance GLB files
  - AWS object/distribution access must be corrected before those two assets
    can render; the UI now reports this instead of showing white models
- Full suite verification: 454 passed, 2 skipped.
- No remote push was performed.

## 2026-07-26 Sticky 2D Review and Direct Furniture Replacement

- Moved the Step 6 pending-furniture section to the top of the 2D review panel.
- Made the 2D plan sticky inside its scroll container so it remains visible
  while the user scrolls through the furniture list.
- Clicking a numbered furniture footprint or its list item now selects and
  focuses that object, then opens the existing database replacement dialog.
- Reused the questionnaire-aware catalog ranking and appliance routes in the
  replacement dialog. Refrigerators and washers now receive appliance
  candidates instead of querying the general furniture endpoint.
- Browser-verified the sticky plan after 708 px of panel scrolling and confirmed
  that clicking furniture opens the replacement dialog with the correct type.
- Full suite verification: 454 passed, 2 skipped.
- No remote push was performed.

## 2026-07-26 Architectural and Placement Validity Gate

- Separated exterior boundary-wall material from questionnaire-selected
  interior wall finishes so room styling no longer recolors the facade.
- Built closed door leaves inside the wall-snapped opening assembly instead of
  placing them again from the raw recognition endpoints.
- Added confirmed-window and floor-to-ceiling-window clearance bands to both
  automatic layout and manual placement validation.
- Added relationship-aware orientation for automatically placed office chairs,
  dining chairs, armchairs, sofas, sofa beds, and desks.
- Added a post-generation gate that keeps the user in Step 6 layout review when
  any generated furniture still lacks a legal position.
- Added regression coverage for window clearance, chair-to-desk orientation,
  boundary-wall material isolation, and snapped closed-door geometry.
- Browser-verified the updated bundle, closed door placement, neutral exterior
  walls, persistent 2D plan, and blocking pending list on project
  `47abb48d539c46a0afd1fc1acce34add`.
- Full suite verification: 457 passed, 2 skipped.
- The two appliance GLBs remain blocked by external AWS HTTP 403 responses;
  they are still shown as pending and do not fall back to white models.
- No remote push was performed.

## 2026-07-27 In-Room Furniture Replacement Preview

- Replaced the free-text replacement search with a compatible furniture-type
  selector. Sofa replacement supports all compatible, fabric, leather,
  modular, and general sofa options without allowing unrelated furniture.
- Changed the replacement preview from an isolated 360 cm demo box to a cloned
  copy of the current project scene.
- Candidate furniture now replaces the selected object at its existing room,
  position, and rotation in the preview while keeping the real walls, doors,
  windows, finishes, and surrounding furniture visible.
- Captured the loaded candidate as a PNG data URL and inserted it into the
  selected catalog card. The loading state replaces the former generic `3D`
  text placeholder when the source catalog has no product image.
- Browser-verified the current living-room sofa replacement, generated PNG,
  full-room context, and leather-sofa selector on project
  `47abb48d539c46a0afd1fc1acce34add`.
- Full suite verification: 458 passed, 2 skipped.
- No remote push was performed.

## 2026-07-27 Door Topology and Empty Opening Correction

- Corrected the earlier diagnosis that `door-2` and `door-3` were duplicate
  edges. They are two adjacent open door leaves whose `host_wall_id` was
  incorrectly assigned to nearby horizontal `wall-2`.
- Found the corresponding two approximately 110 cm gaps in the central
  vertical partition. Treating the open leaves as horizontal wall openings
  created a door in the wrong wall and left the real topology gaps empty.
- Added topology-aware door placement. A door now snaps to a nearby existing
  wall gap when the gap matches its width, touches its hinge, and runs
  perpendicular to the detected open leaf.
- Restored `door-3` in project `47abb48d539c46a0afd1fc1acce34add`
  after the earlier incorrect deduplication had persisted its removal.
- Added regression coverage using the exact wall and door coordinates from the
  affected project. The test asserts that both doors use distinct vertical gaps
  and neither cuts horizontal `wall-2`.
- Browser verification confirmed 5/5 doors in Step 4 and a successful Step 6
  3D restore with the current cache-keyed modules.
- Full suite verification: 461 passed, 2 skipped.
- No remote push was performed.

## 2026-07-27 Step 6 Duplicate Furniture List Removal

- Removed the lower `Actual GLB Furniture` summary and scene-object list from
  the Step 6 sidebar because it repeated the furniture already shown with the
  sticky 2D configuration plan.
- Kept the sticky plan, pending items, and configuration furniture list as the
  single Step 6 selection surface.
- Moved the white-model delete action into the existing furniture replacement
  dialog so selecting a furniture item still supports both replacement and
  deletion.
- Added a dialog open/close fallback for browser environments without native
  `showModal()` support.
- Browser verification confirmed the duplicate heading and list are absent,
  the configuration list remains present, and the current bundle restores
  without a scene error.
- Full suite verification: 461 passed, 2 skipped.
- No remote push was performed.

## 2026-07-27 GLB Thumbnails and 2D-to-3D Furniture Focus

- Replaced the generic `GLB` search-result placeholder with an automatically
  captured PNG thumbnail rendered from each available GLB model.
- Added sequential thumbnail generation and URL-based caching so the hidden
  renderer does not compete with the main 3D scene or repeatedly load the same
  model.
- Strengthened furniture numbers on both the 2D plan and synchronized list with
  high-contrast circular badges and a blue selected state.
- Clicking a numbered footprint on the 2D plan now selects the matching list
  item and focuses the corresponding object in the 3D scene without opening the
  replacement dialog. List-item clicks still open furniture replacement.
- Browser verification on project
  `47abb48d539c46a0afd1fc1acce34add` generated PNG data URLs for all 12 returned
  `書桌` search results and confirmed synchronized selection of furniture 2 in
  the plan, list, and 3D scene.
- Full suite verification: 463 passed, 2 skipped.
- No remote push was performed.

## 2026-07-27 Flush Wall Ends and Window Openings

- Reproduced the right-facade defect with the exact `window-5` coordinates from
  project `47abb48d539c46a0afd1fc1acce34add`.
- Stopped wall sections at their confirmed endpoints instead of extending every
  segment by half a wall thickness.
- Removed redundant wall-junction cap meshes that appeared as full-height
  protruding strips at exposed wall ends.
- Made standalone window sill and header spans exactly match the detected gap
  instead of adding 1.2 cm of overlap.
- Added regression coverage for exact endpoint spans, internal seam overlap,
  window-gap width, and the absence of junction-cap geometry.
- Browser verification confirmed the current cache-keyed bundle restores the
  project and renders the right-side window without the former overlapping wall
  strip.
- Full suite verification: 464 passed, 2 skipped.
- No remote push was performed.

## 2026-07-27 Traditional Chinese Text Recovery

- Added guarded UTF-8 mojibake recovery for JSON API payloads restored from
  existing project and catalog data.
- The repair only replaces byte-like strings when decoding increases valid CJK
  characters, preserving already-correct Traditional Chinese, English, and
  accented names such as `Café`.
- Applied the repair to project loading, catalog responses, scene generation,
  and workflow-save responses before they enter frontend state.
- Browser verification restored `臥室`, `客廳`, `LAGAN 雙門冰箱，獨立式/白色`,
  and `UDDARP 洗脫烘衣機` on project
  `47abb48d539c46a0afd1fc1acce34add`.
- Full suite verification: 466 passed, 2 skipped.
- No remote push was performed.

## 2026-07-27 Furniture-Only Catalog Thumbnails

- Kept native AWS `image_url`, `thumbnail_url`, `preview_url`, and product-image
  fields as the fastest thumbnail source when catalog records provide them.
- Added a dedicated catalog-thumbnail render mode for records that only provide
  a GLB model.
- GLB fallback thumbnails now omit walls, floors, ceilings, doors, windows,
  structural elements, selection guides, plan labels, and furniture numbers.
- Browser verification generated 12/12 PNG thumbnails for the `書桌` search and
  confirmed the first image contains only the furniture against the viewer
  background.
- The current 12 search records expose `model_url` but no native preview field,
  so they correctly use the GLB fallback path.
- Full suite verification: 467 passed, 2 skipped.
- No remote push was performed.
