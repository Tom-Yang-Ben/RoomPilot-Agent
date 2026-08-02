# Ancai AI Profile

## Mission

Own deterministic furniture geometry: placement, movement, collision,
clearance, wall relationships, and legality. Primary path is `backend/engine/`.
`origin/ancai-dev` scene-lab work is an interaction prototype that requires
Bella review before production integration.

## Architecture

```text
room + walls + openings + catalog dimensions + requested furniture
  -> candidate placement
  -> boundary / wall / overlap / clearance checks
  -> legal placed furniture or structured failure
```

## Before Editing

1. Read `backend/engine/README.md` and preserve validation order.
2. Keep geometry deterministic and independent from LLM phrasing.
3. Use centimeters and explicit rotation units.
4. Add tests for legal placement and each new failure mode.

## Cross-Folder Rules

- Yen explains failures but cannot change legality.
- Bella renders and persists results but cannot duplicate placement rules.
- Cody/Django provide confirmed geometry; uncertain detections are not walls.
- Scene-lab UI changes must be ported selectively into production.

## Verification

```powershell
python -m pytest -q tests/test_placement.py tests/test_clearance.py
python -m pytest -q tests/test_scene_visual_regressions.py
```

