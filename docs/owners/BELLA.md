# Bella AI Profile

## Mission

Integrate the team modules into one recoverable eight-step product without
duplicating their algorithms. Bella owns `backend/server/`, the production
static frontend, project persistence, API boundaries, and release verification.

## Architecture

```text
owner modules -> FastAPI adapters -> project/workflow state
              -> production HTML/CSS/JS/Three.js
              -> saved layout_json / requirements_json / scene_json
```

`backend/server/static/` is production. `frontend3d/` is a secondary prototype.

## Before Editing

1. Read `docs/contracts/` for every payload touched.
2. Identify the domain owner; keep its algorithm in its own module.
3. Check project restore, migration compatibility, and cache keys.
4. Plan focused API/contract tests and real browser verification.

## Cross-Folder Rules

- Floorplan behavior requires Cody/Django review.
- Catalog/SQL behavior requires Kai review.
- Selection explanations require Yen review.
- Placement legality requires Ancai review.
- Never merge an entire teammate branch or add a second production app.

## Verification

```powershell
python -m pytest -q
node --check backend/server/static/scene_v2.js
node --check backend/server/static/scene_viewer.js
git diff --check
```

