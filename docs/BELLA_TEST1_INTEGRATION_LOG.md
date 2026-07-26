# Bella Test1 Integration Log

Last updated: 2026-07-26
Branch: `bella-test1`
Remote push status: not pushed

## Current Local Commits

```text
current feat(floorplan): add cody cubicasa mask adapter
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
11 passed

Command:
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=$env:TMP
.\.venv\Scripts\python.exe -m pytest `
  tests/test_cody_semantic_status.py `
  --basetemp=.tmp\pytest -p no:cacheprovider

47 passed, 3 warnings

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
  - confirm `training/CubiCasa5k` availability or an acceptable deployment fallback
  - run a real CubiCasa inference smoke test once weights/script/runtime are present
- Continue the Django Version4 backport with the door/window band-carve classifier and uncertain/autolabel training-data loop only after the Cody slice verifies cleanly.
- Integrate Kai S3/GLB management scripts only after Django/Cody floor-plan recognition work is verified.
