# RoomPilot Kai Catalog Export

This directory preserves the source layout used by `origin/kai` for the
10,550-item PostgreSQL catalog import.

The canonical bella catalog data still lives under `backend/catalog/data/`.
Files in this top-level `JSON/` directory are compatibility inputs for:

```powershell
python scripts/sql/import_catalog_to_postgres.py --strict --dry-run
```

## Files

| Path | Purpose |
|---|---|
| `furniture/all_furniture_appliance_catalog.json` | 10,550 furniture/appliance catalog records plus role/type metadata |
| `manifests/glb_upload_manifest.csv` | GLB manifest rows keyed by `item_id` |
| `manifests/glb_upload_all_result.csv` | S3/CloudFront upload results keyed by `item_id` |
| `manifests/glb_upload_manifest_report.json` | Upload manifest summary used for import auditing |

The importer validates that catalog, manifest, and upload-result IDs are
one-to-one before it writes anything to PostgreSQL.
