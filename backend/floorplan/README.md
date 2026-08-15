# Floor-plan recognition

`backend/floorplan/` converts PNG/JPG/DXF input into reviewable walls, doors, windows, rooms and centimeter-normalized `layout_json` evidence. The user must confirm scale and uncertain structure before design generation.

## Public portable path

The portable profile uses deterministic OpenCV/raster rules and the self-authored files in `examples/fixtures/`. It does not ship training data, customer plans, model weights, icon templates or precomputed semantic heads.

Optional assets default to `.runtime/floorplan/` and may be overridden with the variables documented in `.env.example`. Missing assets disable only the corresponding evidence layer; API output must report the fallback honestly.

## Boundaries

- Cross-module coordinates and lengths are centimeters; area is square meters.
- Recognition evidence never becomes confirmed structure without the confirmation step.
- Room relationships belong to `backend/spatial_data/`; furniture legality belongs to `backend/engine/`.
- New public fixtures must be anonymous, reproducible and listed in `examples/fixtures/manifest.json`.

## Verification

```powershell
uv run pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py
uv run pytest -q tests/test_cody_room_recognition.py tests/test_floorplan2room_paths.py
```

Historical benchmark scripts remain research utilities only. They require external, appropriately licensed evaluation data and are not part of the portable release claim.
