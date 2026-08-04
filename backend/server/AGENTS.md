# Server and Production UI

Owner: Bella. Read `docs/owners/BELLA.md`.

- This is the only production FastAPI app and web frontend.
- Adapt owner modules; do not copy their algorithms into `main.py` or JS.
- Persist backward-compatible project state and version schema changes.
- `layout_json` is recognition output; `scene_json` is proposal output.
- Any static JS/CSS change requires focused tests, content-hash updates, and
  real browser verification.
- Cross-folder changes must name the producer owner and test both boundaries.

Minimum tests: API/contract tests for the feature plus full `pytest -q`.

