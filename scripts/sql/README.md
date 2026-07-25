# RoomPilot PostgreSQL：正式 9,350 筆家具

正式家具與 GLB 來源：

```text
backend/catalog/data/furniture_catalog_cloud_9350.json
backend/catalog/data/manifests/glb_upload_all_result.csv
```

舊六風格 catalog 只作 enrichment。正式查詢、家具 Agent 與 3D 選件只發布這
9,350 個 ID；沒有對應的 1,514 筆舊資料不會匯入。

## 先驗證、不寫入資料庫

```powershell
python scripts/sql/import_official_catalog_to_postgres.py --dry-run
```

必須得到：

- `official_items: 9350`
- `manifest_items: 9350`
- `style_enriched_items: 9021`
- `style_unclassified_items: 329`
- `legacy_rows_excluded: 1514`

## 匯入

安裝 `catalog` extra，並在 `.env` 或執行環境設定：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=postgres
DB_PASSWORD=...
```

執行：

```powershell
python scripts/sql/import_official_catalog_to_postgres.py
```

匯入採單一 transaction 與 UPSERT。預設會刪除資料庫內不屬於正式 9,350 ID
的 catalog 資料；若只做並存檢查，可明確加上 `--keep-extra`。
