# Cody AI Profile

## Mission

Own floorplan recognition and evaluation: image profiling, scale, walls, doors,
windows, rooms, semantic masks, and conversion to the `layout_json` boundary.
Primary paths are `backend/floorplan/`, `backend/upgrade3d/`, and recognition
fixtures under `testdata/`.

## Architecture

```text
PNG/JPG/DXF
  -> image profile and preprocessing
  -> Cody geometry / semantic adapter
  -> opening and room post-processing
  -> centimeter normalization
  -> confidence + evaluation + layout_json
```

## Before Editing

1. Identify whether the change is preprocessing, model inference, geometry,
   post-processing, or evaluation.
2. Preserve raw evidence and confidence; do not turn guesses into confirmed
   structure.
3. Normalize cross-module output to centimeters.
4. Add or update a small fixture and an evaluation test.

## Cross-Folder Rules

- Spatial relationships belong to Django.
- Furniture placement belongs to Ancai.
- API and correction UI belong to Bella.
- Model weights and large training assets stay outside Git.

## Verification

```powershell
python -m pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py
python -m pytest -q tests/test_floorplan_room_evaluation.py tests/test_cody_semantic_status.py
```

