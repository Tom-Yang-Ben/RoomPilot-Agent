# Cody Full Pipeline Integration Plan

Date: 2026-07-31

Goal: make `bella-test1` use the same Cody recognition pipeline as `origin/cody-dev` / `origin/ben`, while preserving Bella/Kai/RAG work already present in the local branch.

## Current Situation

Current branch:

- `bella-test1`
- Current Cody commit added locally: `36ae12f1 feat(floorplan): integrate Cody DINO room labeler`

Current integration level:

- Partial Cody integration only.
- Uses `backend/floorplan/vision/cody_room_labeler.py`.
- Model head is expected at `.runtime/cody/room_head.npz`.
- Does not include Cody's full `floorplan2room` semantic pipeline.

Original Cody / Ben pipeline:

- `origin/cody-dev`
- Also included by `origin/ben`.
- Key commit: `a8f8b1ea feat(floorplan): cody 辨識管線併入 ben 結構，房型 79.2%→90.3% 且解除 CC BY-NC 商用閘`

## Target Outcome

After integration, `bella-test1` should use Cody's original recognition path:

- `recognize_cody_geometry(...)` for geometry
- `recognize_cody_rooms(...)` for semantic room labels
- `floorplan2room.py` as the main Cody room semantic pipeline
- `room_classifier.py` with `backend/floorplan/room_head.npz`
- `symbol_match.py` with `backend/floorplan/symbol_lib.npz`
- Cody's OCR/room-label priority rules in `vision/analysis.py`

The local lightweight file should be retired:

- Remove or stop using `backend/floorplan/vision/cody_room_labeler.py`

## Do Not Directly Merge All of `origin/ben`

`origin/ben` contains much more than Cody:

- Full frontend workflow changes
- RAG pipeline
- vendored Three.js
- rendering provider changes
- large training/test data
- scene bug fixes

Direct merge is risky because the current worktree has many uncommitted Bella/Kai/RAG changes. Prefer a targeted Cody integration.

## Recommended Integration Strategy

Use `origin/cody-dev` as the source for recognition code, not all of `origin/ben`.

Bring these files from `origin/cody-dev`:

```text
backend/floorplan/floorplan2room.py
backend/floorplan/floorplan2dxf_color.py
backend/floorplan/config_color.ini
backend/floorplan/symbol_match.py
backend/floorplan/symbol_lib.npz
backend/floorplan/room_head.npz
backend/floorplan/room_classifier.py
backend/floorplan/cody_adapter.py
backend/floorplan/vision/cody_semantic.py
backend/floorplan/vision/ocr.py
```

Manually merge, not blindly overwrite:

```text
backend/floorplan/vision/analysis.py
backend/server/main.py
requirements.txt
pyproject.toml
uv.lock
tests/test_floorplan_vision.py
tests/test_floorplan_vision_api.py
tests/test_cody_semantic_status.py
```

Add these Cody tests if practical:

```text
tests/test_cody_pipeline_modules.py
tests/test_cody_room_recognition.py
tests/test_floorplan2room_paths.py
tests/test_ocr_wiring.py
tests/test_semantic_cache_alignment.py
```

Large data decision:

- Minimum runnable integration needs `room_head.npz` and `symbol_lib.npz`.
- Full Cody parity also needs selected `testdata/Identify_ans/**`, `testdata/Asset/**`, and `training/**` tests/data.
- If repo size is a concern, bring only required fixtures for tests first.

## Key Code Changes Required

### 1. Replace Lightweight Room Labeler

Current local path:

```text
backend/floorplan/vision/cody_room_labeler.py
```

Target:

- Remove this from `analysis.py` imports.
- Replace with:

```python
from ..cody_adapter import recognize_cody_geometry, recognize_cody_rooms
from .cody_semantic import cody_semantic_room_labeler_status
```

### 2. Adopt Cody Room Semantics in `analysis.py`

Bring the `origin/cody-dev` logic for:

- `ROOM_LABELS` with English aliases
- `CODY_ROOM_TYPE_MAP`
- `_semantic_cache_key(...)`
- `_room_centre_px(...)`
- `apply_floorplan2room_labels(...)`
- `_drop_duplicate_ocr_label_rooms(...)`
- OCR fallback handling
- Imperial dimension parsing

Target analysis flow:

```text
decode image
collect reference/OCR observations
recognize Cody geometry
recognize Cody rooms via floorplan2room
infer/label rooms
apply icon labels
apply Cody semantic labels with priority rules
return cody_room_semantics and cody_room_semantic_labels_applied
```

### 3. Use Cody's Model Asset Paths

Current local lightweight integration expects:

```text
.runtime/cody/room_head.npz
```

Original Cody expects:

```text
backend/floorplan/room_head.npz
backend/floorplan/symbol_lib.npz
```

Adopt original Cody path for branch parity. Keep `ROOM_HEAD` env override for local A/B testing.

### 4. Connect OCR Provider

Bring the `origin/ben` / `origin/cody-dev` OCR provider connection:

```python
from ..floorplan.vision.ocr import default_ocr_provider

def _floorplan_ocr_provider():
    if os.environ.get("ROOMPILOT_OCR_DISABLED") == "1":
        return None
    return default_ocr_provider()
```

Then pass it into:

- project floorplan analysis
- upload floorplan analysis

This improves printed room names, English labels, and scale extraction.

### 5. Keep Bella/Kai Frontend Stable

Avoid replacing the full frontend from `origin/ben` unless explicitly desired.

Small frontend fixes worth cherry-picking separately:

```text
bdf5d501 fix(scene): 修復房間確認面板 room is not defined
b52d231d fix(scene): bindEvents 綁定不存在的按鈕使初始化中斷，右欄互動全失效
3bb336b5 fix: bella-test1 合併後修——cache key、房間尺寸測試、軟裝燈具類型
```

Do these after Cody pipeline integration or in a separate small patch.

## Suggested Work Order

1. Create a safety branch from current `bella-test1`.
2. Commit or stash current unrelated RAG/catalog/frontend dirty work.
3. Import Cody core files from `origin/cody-dev`.
4. Manually merge `vision/analysis.py`.
5. Update `server/main.py` only for OCR provider wiring if missing.
6. Remove/retire `cody_room_labeler.py`.
7. Add required tests.
8. Run focused Cody tests.
9. Run floorplan API tests.
10. Run scene/frontend contract tests.
11. Run full test suite.
12. Only after green focused tests, cherry-pick Ben frontend bug fixes.

## Verification Commands

Focused Cody:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_cody_semantic_status.py `
  tests/test_cody_pipeline_modules.py `
  tests/test_cody_room_recognition.py `
  tests/test_floorplan2room_paths.py `
  tests/test_ocr_wiring.py `
  tests/test_semantic_cache_alignment.py
```

Floorplan:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_floorplan_vision.py `
  tests/test_floorplan_vision_api.py
```

Scene/frontend contracts:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_scene_v2_contract.py `
  tests/test_scene_workflow.py
```

Full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Acceptance Criteria

The integration is done when:

- `analysis.py` reports `cody_room_semantics`.
- Rooms can receive `source = "cody_floorplan2room"`.
- Cody semantic status reports the DINOv2 room head path and availability/fallback correctly.
- Lightweight `cody_room_labeler.py` is no longer required by production code.
- Focused Cody/floorplan tests pass.
- Existing Bella 2D/3D workflow tests still pass.

## Known Separate Issue

The `decor_model_missing` floor-lamp failure is catalog data mapping, not Cody recognition. See:

```text
docs/FULL_PROFILE.md
```

Handle it separately from Cody pipeline integration.
