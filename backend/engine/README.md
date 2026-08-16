# Geometry and placement engine

`backend/engine/` is RoomPilot's only authority for furniture coordinates, rotation, room containment, collision and operational clearance. Agent, RAG, server and browser code may supply candidates or explain results, but they may not declare an illegal placement valid.

## Public contract

- Every length and planar coordinate is in centimetres.
- `pos_x` and `pos_y` are the furniture centre on the floor plane; `pos_y` is not height.
- Rotation is degrees counter-clockwise; `0` faces `+Y`.
- Compatibility payloads using `width`, `depth`, `pos_x` or `pos_y` include `schema_version` and `coordinate_unit: "cm"`.
- The same input produces the same result. The engine does not call LLMs, catalogs, remote services or project storage.

The validation order is stable:

1. outside the room;
2. intersects a wall;
3. overlaps another furniture body;
4. its clearance intersects a wall;
5. its clearance intersects another furniture body;
6. clearance zones overlap;
7. its body blocks another item's clearance.

When several violations apply, the first one is returned. Consumers must preserve the structured failure instead of turning it into a successful placement.

## Modules

| Module | Responsibility |
|---|---|
| `models.py`, `schema.py` | Public Python objects, centimetre serialization and tool schemas |
| `geometry.py`, `clearance.py`, `obb.py` | Body, wall, oriented-box and clearance checks |
| `placement.py`, `adjustment.py` | Deterministic placement and legal move/rotate operations |
| `raster.py`, `constraints.py` | Occupancy grid, passages and forbidden masks |
| `rules.py`, `layout_model.py` | Room rules and confirmed-layout data models |
| `dxf_room.py` | Legacy DXF adapter; unit conversion is isolated at its input boundary |

`place_furniture()` and `place_furniture_batch()` provide the core placement API. `adjust_furniture()` supports legal move and rotate operations. `schema.py` contains the compatibility serialization used by server and agent adapters.

## Integration rules

- A catalog candidate needs a stable ID and positive centimetre dimensions before placement.
- Door, window, wall, beam, column and circulation evidence comes from the confirmed `layout_json` revision.
- Agent replacement or repair must call the engine again; it cannot reuse coordinates from a different-sized item.
- Portable procedural fixtures and full-profile GLBs use the same dimension and legality checks. Rendering mode never changes the geometry result.

## Verification

```powershell
uv run pytest -q tests/test_placement.py tests/test_clearance.py tests/test_layout_spec.py
uv run pytest -q tests/test_scene_visual_regressions.py
```

The first group covers the engine boundary and deterministic grid planner. Scene integration tests verify that server and browser consumers preserve the engine result.
