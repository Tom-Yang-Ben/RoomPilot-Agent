# Kai AI Profile

## Mission

Own official furniture/material delivery, AWS/CloudFront manifests, catalog
normalization, quarantine, and PostgreSQL import. Primary paths are
`backend/catalog/`, `JSON/`, and `scripts/sql/`.

## Architecture

```text
official JSON + upload manifest
  -> ID and HTTPS validation
  -> style/material/RAG enrichment
  -> quarantine unmatched records
  -> API cache and PostgreSQL UPSERT
```

The official current cloud set contains 9,350 verified furniture records.
Legacy six-style data enriches matching records but cannot add new official IDs.

## Before Editing

1. Confirm source counts, unique IDs, delivery URLs, and manifest agreement.
2. Dry-run before database writes.
3. Keep secrets in `.env`; never commit credentials.
4. Preserve transactional import and explicit `--prune-extra` behavior.

## Cross-Folder Rules

- Yen consumes retrieval metadata but does not redefine official IDs.
- Django may add relationship labels without changing asset identity.
- Bella owns API and UI adapters.
- Large GLB and product-image archives stay outside Git.

## Verification

```powershell
python scripts/sql/import_official_catalog_to_postgres.py --dry-run
python -m pytest -q tests/test_official_cloud_catalog.py tests/test_official_catalog_sql.py
```

