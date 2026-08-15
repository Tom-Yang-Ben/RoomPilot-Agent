# PostgreSQL development boundary

The public full profile starts from the generic schema in `docker_postgresql/init/001_roompilot.sql`. It intentionally contains no catalog rows, product assets, embeddings or dump.

```powershell
Copy-Item .env.example .env
# set ROOMPILOT_PROFILE=full and DB_PASSWORD
docker compose --env-file .env -f docker_postgresql/docker-compose.yml up -d
uv run python scripts/sql/import_public_catalog_to_postgres.py --catalog backend/catalog/data/portable_furniture.json --dry-run
```

Each developer-supplied furniture row must include a stable `item_id`, positive centimeter dimensions, `source_license` and activation state. URLs are optional and remain the data provider's licensing, CORS, availability and retention responsibility.

`import_public_catalog_to_postgres.py` 是唯一現行公開 importer。它會先驗證授權、ID、家具種類、公分尺寸與 URL，再以單一 transaction UPSERT；不會刪除未列在輸入檔的既有資料。

舊私有 catalog、embedding、固定筆數 schema 與匯入報告已退出公開 repository。公開 SQL 工具不得重新引入固定資料筆數、未附授權來源或 production dump。
