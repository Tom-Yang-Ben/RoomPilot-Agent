# PostgreSQL development boundary

The public full profile starts from the generic schema in `docker_postgresql/init/001_roompilot.sql`. It intentionally contains no catalog rows, product assets, embeddings or dump.

```powershell
Copy-Item .env.example .env
# set ROOMPILOT_PROFILE=full and DB_PASSWORD
docker compose --env-file .env -f docker_postgresql/docker-compose.yml up -d
uv run python scripts/sql/import_public_catalog_to_postgres.py --catalog backend/catalog/data/portable_furniture.json --dry-run
```

Each developer-supplied furniture row must include a stable `item_id`, positive centimeter dimensions, `source_license` and activation state. URLs are optional and remain the data provider's licensing, CORS, availability and retention responsibility.

`ROOMPILOT_CATALOG_VISIBILITY=public` 是 fail-closed 預設，只讀取 `license_status=verified` 的 active 列。只有本機私有使用才可明確設為 `private`；此模式仍不會把資料或憑證寫入 Git。

`import_public_catalog_to_postgres.py` 是唯一現行公開 importer。它會先驗證授權、ID、家具種類、公分尺寸與 URL，再以單一 transaction UPSERT；不會刪除未列在輸入檔的既有資料。

Catalog 匯入完成後，先以可回復 transaction 驗證通用 pgvector schema 與待建向量數，再正式建立 schema／同步缺少或文字已更新的向量：

```powershell
uv run python scripts/sql/sync_catalog_embeddings_to_postgres.py --create-schema --dry-run
uv run python scripts/sql/sync_catalog_embeddings_to_postgres.py --create-schema
```

既有本機資料庫可先 dry-run，再用可回復 migration 建立同一個 public/private 邊界；工具不刪除資料，並保留原始 activation 狀態：

```powershell
uv run python scripts/sql/migrate_catalog_visibility.py --dry-run
uv run python scripts/sql/migrate_catalog_visibility.py
# 如需回復遷移前狀態：
uv run python scripts/sql/migrate_catalog_visibility.py --rollback
```

Catalog visibility rollback 是離線 recovery 工具，不在 production request
path。至少保留到新 public repository 完成切換並驗證備份後，再另案決定是否封存；
不可為了減少檔案數而提前失去回復能力。

`sync_catalog_embeddings_to_postgres.py` 只 UPSERT 目前 `item_id + model + text_hash` 尚未存在的向量，不刪除 catalog 或舊向量。模型權重必須已存在 `ROOMPILOT_RAG_MODEL_CACHE` 或 Hugging Face 本機快取；工具不會靜默下載。

向量同步預設沿用 `.env` 的 catalog visibility；可用 `--visibility public` 做公開邊界驗收，或在明確的本機 private 模式使用 `--visibility private`。兩種模式共用向量表，但 source view 只讓當前模式可見的家具參與同步與檢索。

舊私有 catalog、embedding、固定筆數 schema 與匯入報告已退出公開 repository。公開 SQL 工具不得重新引入固定資料筆數、未附授權來源或 production dump。
