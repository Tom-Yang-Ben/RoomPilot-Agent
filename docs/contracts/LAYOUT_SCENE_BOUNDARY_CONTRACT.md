# Layout and Scene Boundary Contract

Last updated: 2026-07-26

This contract fixes the data responsibility boundary between floor-plan recognition,
proposal generation, Graph RAG, and rendering.

## Terms

| Name | Owner | Meaning |
|---|---|---|
| `layout_json` | floorplan vision | Recognized or confirmed architectural layout. |
| `scene_json` | proposal agent / scene service | Interior design proposal built from layout, requirements, catalog data, and rules. |
| Graph RAG result | proposal agent support layer | Relationship retrieval result used as candidate evidence, not a final decision. |

## `layout_json`

`layout_json` is the output of the floor-plan recognition path. It can be a draft
recognition result or a user-confirmed layout, but it must describe the space
itself rather than the proposed design.

Allowed content:

- Walls, wall polygons, doors, windows, beams, columns.
- Room regions, room labels, room polygons, areas, and centroids.
- Scale, coordinate unit, image profile, recognition engine, confidence, issues.
- Review requirements such as missing scale or targeted room confirmation.

Not allowed content:

- Furniture placement decisions.
- Material, ceiling, lighting, or air-conditioning selections.
- Render camera, export settings, or proposal copy.
- Final style decisions.

Current compatibility fields:

- `/api/floorplan/analyze` returns both `analysis` and `layout_json`.
- `/api/projects/{project_id}/floorplan/analyze` returns both `analysis` and `layout_json`.
- `/api/floorplan/confirm` returns both `floorplan` and `layout_json`.
- `/api/scene/generate` accepts `layout_json` as a canonical layout input.

The older names remain for frontend compatibility. New architecture diagrams and
worker contracts should call the recognition output `layout_json`.

## `scene_json`

`scene_json` is produced after `layout_json` is available and the user's
requirements have been collected.

Allowed content:

- Furniture items, GLB asset references, dimensions, placement, and rotation.
- Optional tabletop-host fields on furniture items (2026-08-03, 方案 B):
  `host_object_id`（檯面小物站在哪件家具上）與 `host_surface_height_cm`
  （3D 呈現高度）。相容表在 `backend/catalog/style_db.py`
  `TABLETOP_HOST_TYPES`，平面包含判定在
  `backend/engine/geometry.rests_within_host`。
- Wall, floor, ceiling, lighting, and air-conditioning decisions.
- Style pack, material pack, render settings, and proposal metadata.
- Geometry planner output and rule-check reports.

Required inputs:

- `layout_json`
- User requirement answers
- Catalog candidates
- Geometry planner constraints
- Rule checker constraints

Current compatibility fields:

- `/api/scene/generate` returns `scene_json` beside the legacy top-level scene
  payload.
- The browser flow now reads `response.scene_json || response`, so new responses
  use the explicit contract while legacy top-level responses remain a fallback.

## Graph RAG Boundary

Graph RAG may retrieve relationship evidence, such as:

- Which furniture categories commonly fit a room type.
- Which materials are compatible with a style.
- Which GLB assets map to a furniture category.
- Which furniture types are risky in humid, narrow, or high-traffic spaces.

Graph RAG must not be the final authority for:

- Exact object placement.
- Clearance, collision, and circulation decisions.
- Door/window conflict checks.
- Cabinet or furniture dimensional validity.
- Ceiling, lighting, AC, and structural rule decisions.

Those decisions belong to geometry planning and rule-checking code. Graph RAG can
recommend candidates and explain relationships, but deterministic planners and
validators must accept, reject, or adjust them.

## Deployment Boundary

The final deployment diagram may split slow work into workers:

- `floorplan-vision-worker`: produces `layout_json`.
- `proposal-agent-worker`: produces `scene_json`.
- `render-export-worker`: produces renders, PDF reports, GLB exports, and share files.

Object storage should be labelled by deployment target:

- Local or Docker demo: MinIO.
- Production cloud: AWS S3 or another S3-compatible provider.
