# Scripts

Public release utilities:

| Script | Purpose |
|---|---|
| `generate_public_fixtures.py` | Rebuild the anonymous PNG/DXF fixture and provenance manifest |
| `public_repo_check.py` | Reject private paths, large/model artifacts, obvious secrets and broken fixture hashes |
| `update_static_hashes.py` | Refresh local static dependency cache hashes |
| `sql/import_public_catalog_to_postgres.py` | Current generic, license-validating full-profile importer |
| `sql/` | PostgreSQL public importer and generic schema workflow |

Run scripts from the repository root with `uv run python ...`. No public script may assume that private JSON, manifests, embeddings or a fixed-size catalog are bundled.

Cloud upload/download utilities can change external state. Use only with data and credentials you are authorized to handle, always run a dry-run where supported, and never commit resulting assets, manifests or secrets.
