# Geometry and Placement Engine

Owner: Ancai. Read `docs/owners/ANCAI.md` and `backend/engine/README.md`.

- This module is authoritative for placement, collisions, clearances, and
  movement legality.
- Keep algorithms deterministic and independent of UI or LLM wording.
- Preserve the documented validation order and centimeter contract.
- Return structured failure reasons for Yen/Bella to present.
- Do not fetch catalogs, call external APIs, or persist projects here.

Minimum tests: `test_placement.py`, `test_clearance.py`, and affected integration
tests.
