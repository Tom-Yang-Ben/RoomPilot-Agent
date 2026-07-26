# Bella Test1 Integration Log

Last updated: 2026-07-26
Branch: `bella-test1`
Remote push status: not pushed

## Current Local Commits

```text
current feat(floorplan): backport django image route profiling
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

## Cleanup Notes

- No `.patch`, `.rej`, or `.orig` files are left in the worktree.
- Backup/source patches were integrated into formal project files only.
- Worktree was clean after the Django image-route backport commit.

## Remaining Work

- Start or install PostgreSQL locally, configure `.env`, run the 10,550 import, and verify live SQL counts.
- Decide whether to wire Cody v5 inference/weight download into Bella runtime.
- Use `room_evaluation` with real reference-room fixtures before replacing current room-labeling behavior.
- Run the focused floorplan pytest suite once the local Python/pytest/cv2 environment is available again.
- Finish the Cody integration slice before starting other branches:
  - add a subprocess/CubiCasa mask inference adapter only after confirming `training/CubiCasa5k` availability or an acceptable deployment fallback
  - run the cody semantic tests with the project pytest environment once available
- Continue the Django Version4 backport with the door/window band-carve classifier and uncertain/autolabel training-data loop only after the Cody slice verifies cleanly.
- Integrate Kai S3/GLB management scripts only after Django/Cody floor-plan recognition work is verified.
