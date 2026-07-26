# RoomPilot AI Working Agreement

This file applies to the whole repository. Read it before editing any file.

## Mandatory Read-Before-Write Gate

An AI must complete these steps before making changes:

1. Read `README.md` for the current eight-step product flow and startup commands.
2. Read `docs/TEAM_AI_OWNERSHIP.md` and the profile under `docs/owners/` for
   the primary owner of the target path.
3. Read the nearest `AGENTS.md` and all relevant files in `docs/contracts/`.
4. Run `git status --short` and preserve unrelated user changes.
5. Trace the input, output, coordinate unit, persistence boundary, and tests for
   the behavior being changed.
6. State the intended files and verification commands before editing.

Do not copy an entire remote branch into this tree. Inspect and port only the
smallest compatible behavior.

## Cross-Folder Change Gate

Changing files outside the primary owner's area is allowed only when the
integration genuinely requires it. Before editing, record:

```text
Cross-folder change
- Primary owner:
- Collaborating owner:
- Files:
- Contract or data flow being changed:
- Why one folder cannot contain the change:
- Tests that prove both sides still work:
```

For shared contracts, both producer and consumer tests are required. A frontend
fallback must not silently replace a backend algorithm, and backend integration
must not duplicate an owner's domain logic.

## Canonical Ownership

| Path | Primary owner | Main responsibility |
|---|---|---|
| `backend/server/` | Bella | FastAPI, project persistence, eight-step UI, 2D/3D orchestration |
| `backend/floorplan/` | Cody | Image/DXF recognition, walls, openings, rooms, `layout_json` |
| `backend/spatial_data/` | Django | Spatial measurements, room relationships, layout evaluation schema |
| `backend/catalog/`, `JSON/`, `scripts/sql/` | Kai | Furniture/material catalog, AWS/CloudFront manifest, PostgreSQL import |
| `backend/agent/` | Yen | Requirement interpretation, furniture selection, repair decisions |
| `backend/engine/` | Ancai | Placement, collision, clearance, movement, geometry rules |
| `backend/upgrade3d/` | Cody | Confirmed DXF/layout conversion into 3D-ready geometry |
| `frontend3d/` | Bella | Secondary React/R3F prototype; production UI remains in `backend/server/static/` |
| `testdata/` | Cody | Recognition fixtures; Django reviews room/spatial labels |
| `tests/` | Matching module owner | Contract and regression coverage; Bella owns end-to-end integration gates |
| `docs/contracts/` | Bella integration | Cross-module public contracts; affected owners must review |

See `docs/TEAM_AI_OWNERSHIP.md` for branch history, collaborators, generated
data, and the exact workflow for every owner.

## Non-Negotiable Contracts

- Cross-module geometry uses centimeters. New length and coordinate fields end
  in `_cm`; areas end in `_m2`.
- Legacy `width`, `depth`, `pos_x`, and `pos_y` remain compatible only when the
  payload includes `coordinate_unit: "cm"` and a schema version.
- Floorplan recognition produces `layout_json`. Proposal generation produces
  `scene_json`.
- Graph RAG retrieves relationships and evidence. It does not decide geometry,
  collisions, clearances, or structural legality.
- Furniture placement legality belongs to `backend/engine/`.
- The official furniture set is the verified cloud catalog plus its matching
  manifest. Quarantined or unmatched records never enter the API or scene.
- Production web assets live in `backend/server/static/`. `frontend3d/` is not
  a replacement application unless an explicit migration is approved.
- Do not commit `.env`, runtime project data, generated caches, model weights,
  or large GLB archives.

## Verification Matrix

| Change | Minimum verification |
|---|---|
| Python domain module | Focused tests plus `pytest -q` |
| FastAPI or persistence | API tests plus `pytest -q` |
| Static frontend/Three.js | JS syntax check, focused contract tests, real browser QA |
| Floorplan recognition | Vision/evaluation tests using `testdata/` |
| Catalog/SQL | Dry-run validation and catalog contract tests |
| React prototype | `npm ci` and `npm run build` in `frontend3d/` |
| Documentation/ownership | Link/path check and command verification |

Final integration commands:

```powershell
python -m pytest -q
git diff --check
git status --short
```

