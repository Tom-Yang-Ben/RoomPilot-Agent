# Geometry and Placement Engine

Owner: Ancai. Read `docs/owners/ANCAI.md` and `backend/engine/README.md`.

## Before editing

1. Read the document map in `backend/engine/README.md`.
2. Room minimum furniture lists live in `room_strategy/README.md` and must stay
   aligned with `backend/agent/knowledge.py` (Yen module).
3. Keep algorithms deterministic; never invent coordinates from LLM text.
4. Preserve clearance validation order and centimeter contracts.
5. Working notes under `notes/` are not SSOT.

## Owns

- Placement, collision, clearance, movement legality.
- Structured failure reasons for Agent／UI.

## Does not own

- Catalog truth (Kai), questionnaire UI (Bella), RAG retrieval (Django／Yen),
  or “which furniture types a room should try first” beyond consuming the
  agreed strategy／Agent knowledge tables.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_placement.py tests/test_clearance.py
.venv/bin/python -m pytest -q tests/test_agent_select.py tests/test_agent_place.py
```
