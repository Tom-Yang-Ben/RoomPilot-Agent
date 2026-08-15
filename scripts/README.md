# Scripts

Public release utilities:

| Script | Purpose |
|---|---|
| `generate_public_fixtures.py` | Rebuild the anonymous PNG/DXF fixture and provenance manifest |
| `public_repo_check.py` | Reject private paths, large/model artifacts, obvious secrets and broken fixture hashes |
| `update_static_hashes.py` | Refresh local static dependency cache hashes |
| `sql/import_catalog_to_postgres.py` | Generic full-profile catalog import helper |
| `sql/` | PostgreSQL schema and historical import utilities |

Run scripts from the repository root with `uv run python ...`. Tools that refer to removed private JSON/manifests are retained only as migration history; they are not a public quick-start path and must not be used as evidence that a catalog is bundled.

Cloud upload/download utilities can change external state. Use only with data and credentials you are authorized to handle, always run a dry-run where supported, and never commit resulting assets, manifests or secrets.
