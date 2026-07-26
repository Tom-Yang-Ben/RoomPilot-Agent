# Yen AI Profile

## Mission

Own structured requirements, furniture selection decisions, explanations, and
repair intent. Primary domain code is `backend/agent/`; questionnaire and
workflow presentation are integrated by Bella in `backend/server/`.

## Architecture

```text
basic answers + room polar questions + selected style cards
  -> structured requirements_json
  -> catalog retrieval constraints
  -> ranked furniture choices
  -> repair intent and user-facing explanation
```

## Before Editing

1. Distinguish user preference, required function, and optional recommendation.
2. Keep every decision traceable to questionnaire or catalog evidence.
3. Return structured intent; do not invent coordinates.
4. Preserve per-room selections and deferred furniture across project reloads.

## Cross-Folder Rules

- Kai owns catalog truth and retrieval fields.
- Ancai owns placement, collision, and clearance results.
- Bella owns the visible questionnaire and persistence.
- Graph RAG evidence may support a choice but cannot overrule geometry.

## Verification

```powershell
python -m pytest -q tests/test_agent_select.py tests/test_agent_place.py
python -m pytest -q tests/test_scene_room_requirements.py tests/test_scene_furniture_retrieval.py
```

