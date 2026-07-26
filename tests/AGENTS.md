# Test Suite

Ownership follows the module under test; Bella owns end-to-end integration
gates.

- Prefer behavior tests over raw source-string assertions when practical.
- Keep tests deterministic and offline by default.
- External assets, PostgreSQL, OCR weights, and network calls must be explicit
  opt-in or safely skipped.
- A cross-folder contract change needs producer and consumer tests.
- Do not weaken a test merely to accept a regression.

Final gate: focused tests, full `python -m pytest -q`, and `git diff --check`.

