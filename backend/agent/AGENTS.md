# Requirement and Selection Agent

Owner: Yen. Read `docs/owners/YEN.md`.

## Before editing

1. Keep `knowledge.py` aligned with `backend/engine/room_strategy/README.md`.
2. Convert questionnaire／RAG offers into structured choices; never invent
   coordinates.
3. Preserve user-selected and required furniture; validate LLM output before use.
4. Engine remains authoritative for legality; Agent owns order, companions,
   replace-smaller, and remove／escalate policy.

## Key files

| File | Role |
|---|---|
| `knowledge.py` | Room affinity, companions, minimum families, prompt rules |
| `select.py` | LLM／local selection boundary |
| `place.py` | Placement order hints and resolve／replace without geometry |

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_agent_select.py tests/test_agent_place.py
```
