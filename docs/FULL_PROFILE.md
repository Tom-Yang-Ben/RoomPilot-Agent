# Full profile

Full profile 是 PostgreSQL/pgvector catalog 的開發整合模式，不是 production deployment 宣告。

```powershell
.\install.ps1 -Full
Copy-Item .env.example .env
# 編輯 .env：ROOMPILOT_PROFILE=full、DB_PASSWORD=...
docker compose --env-file .env -f docker_postgresql/docker-compose.yml up -d
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002
```

repository 只建立通用 schema，不附資料庫 dump、正式家具、embedding 或雲端資產。匯入自有資料前，每筆至少要有穩定 `item_id`、公分尺寸、來源、授權、啟用狀態；若提供 GLB／圖片 URL，使用者須自行確認授權、CORS、可用性與保存政策。

先用專案自製 fixture 驗證 importer；實際匯入時將路徑換成自己的授權 JSON：

```powershell
uv run python scripts/sql/import_public_catalog_to_postgres.py --catalog backend/catalog/data/portable_furniture.json --dry-run
uv run python scripts/sql/import_public_catalog_to_postgres.py --catalog path/to/licensed-catalog.json --create-schema
uv run python scripts/sql/sync_catalog_embeddings_to_postgres.py --create-schema --dry-run
uv run python scripts/sql/sync_catalog_embeddings_to_postgres.py --create-schema
```

匯入採單一 transaction UPSERT，不會刪除資料庫內未出現在輸入檔的既有列。非家具項目、缺少授權、重複 ID、非正數公分尺寸或非 HTTP(S) 資產 URL 會在連線資料庫前被拒絕。

本機 GLB 不會自動掃描 repository、`Downloads` 或其他使用者目錄。需要本機模型時，透過 `ROOMPILOT_LOCAL_GLB_ROOTS` 指定允許的根目錄；需要 zip 時則明確設定 `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS`。多個路徑使用作業系統的 path separator 分隔。

需要遠端模型交付時，必須同時明確設定 `ROOMPILOT_MODEL_DELIVERY_MODE=cloudfront`、`ROOMPILOT_GLB_MANIFEST_PATH`，以及 manifest 只有 object key 時所需的 `ROOMPILOT_CLOUDFRONT_BASE_URL`。遠端縮圖另設定 `ROOMPILOT_IMAGE_MANIFEST_PATH`。repository 沒有預設 CDN、bucket 或私有 manifest 路徑；缺少任一必要設定時會回報 unavailable，不會猜測舊環境。

`ROOMPILOT_CATALOG_PROVIDER` 留空時由 profile 推導；full 為 strict PostgreSQL。連線或 view 不可用時必須顯示 unavailable／503，不會靜默換成另一批資料。

`ROOMPILOT_CATALOG_VISIBILITY` 預設為 `public`：PostgreSQL session 只可見 active 且 `license_status=verified` 的家具，API 與 RAG 共用同一個 view。`private` 必須在本機 `.env` 明確開啟，才會納入 active 但授權仍待確認的 operator 私有資料；程式不會因 full profile 自動切到 private。既有資料庫使用 `scripts/sql/migrate_catalog_visibility.py` 先 dry-run，migration 會備份 activation 狀態且支援 `--rollback`。

## Public RAG bootstrap

Catalog importer 是 `roompilot.furniture_catalog_current` 的生產端；`docker_postgresql/init/002_roompilot_rag.sql` 將目前 PostgreSQL session 可見的 active catalog 投影成 `roompilot.furniture_embedding_source_current`，資料形狀固定為 `item_id`、可空的 `annotation_id`、`embedded_text`、SHA-256 `text_hash`、style、更新時間與 `chroma_metadata`。`backend/catalog/rag_repository.py` 是消費端，僅依該 view 取得價格統計與 pgvector 候選。因此 public/private 切換會同時作用於家具 API、選件回查與 RAG，不會產生兩套互相矛盾的 catalog。

這是跨模組契約，無法只補 API 或只補 SQL：fresh PostgreSQL 必須能建立 source view／搜尋函式，Python runtime 也必須只使用公開 view，才能同時支援空白公開資料庫與 operator 既有資料庫。兩端驗證為 `tests/test_rag_postgres_bootstrap.py` 的 data-free SQL 契約，以及啟用後 `/api/rag/status` 的 embedding 筆數與 `search_function_available=true`。

## 選配辨識模型

公開 repository 不附模型或私有評測資料。需要額外的房型／符號證據時，把自行確認授權的資產放在 `.runtime/floorplan/`，或透過 `.env.example` 列出的 `ROOM_HEAD`、`ROOMPILOT_SYMBOL_LIBRARY`、`ROOMPILOT_OPENING_MODEL` 與 `ROOMPILOT_ICON_TEMPLATE_DIR` 指定外部路徑。若要使用特定 reference plan，影像與 annotations 必須同時明確設定；未設定時不會套用任何黃金答案捷徑。
