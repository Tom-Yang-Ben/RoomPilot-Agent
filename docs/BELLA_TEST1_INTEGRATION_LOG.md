# Bella Test1 Integration Log

Last updated: 2026-07-26
Branch: `bella-test1`
Remote push status: not pushed

## Current Local Commits

```text
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

## Verification

Latest full suite:

```text
409 passed, 2 skipped, 3 warnings
```

Targeted floorplan suite:

```text
30 passed, 3 warnings
```

## Cleanup Notes

- No `.patch`, `.rej`, or `.orig` files are left in the worktree.
- Backup/source patches were integrated into formal project files only.
- Worktree was clean after commit `9dc25eda`.

## Remaining Work

- Start or install PostgreSQL locally, configure `.env`, run the 10,550 import, and verify live SQL counts.
- Decide whether to wire Cody v5 inference/weight download into Bella runtime.
- Use `room_evaluation` with real reference-room fixtures before replacing current room-labeling behavior.
