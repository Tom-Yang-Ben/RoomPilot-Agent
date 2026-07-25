# RoomPilot PostgreSQL Import

This importer validates and loads the official 9,350-item cloud furniture
catalog into PostgreSQL.

Source files:

```text
backend/catalog/data/furniture_catalog_cloud_9350.json
backend/catalog/data/manifests/glb_upload_all_result.csv
```

The legacy six-style catalog is enrichment only. It can add style, taxonomy,
and placement metadata, but it cannot add furniture outside the official 9,350
cloud item IDs.

## Dry Run

```powershell
python scripts/sql/import_official_catalog_to_postgres.py --dry-run
```

Expected diagnostics:

- `official_items: 9350`
- `manifest_items: 9350`
- `style_enriched_items: 9021`
- `style_unclassified_items: 329`
- `legacy_rows_excluded: 1514`

## Import

Install the `catalog` extra and configure the database in `.env` or the process
environment:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=postgres
DB_PASSWORD=...
```

Run:

```powershell
python scripts/sql/import_official_catalog_to_postgres.py
```

The importer runs in one transaction and UPSERTs the official 9,350 IDs. By
default it does not delete other catalog rows already in the database.

To explicitly remove rows outside the official cloud set, run:

```powershell
python scripts/sql/import_official_catalog_to_postgres.py --prune-extra
```
