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
```

匯入採單一 transaction UPSERT，不會刪除資料庫內未出現在輸入檔的既有列。非家具項目、缺少授權、重複 ID、非正數公分尺寸或非 HTTP(S) 資產 URL 會在連線資料庫前被拒絕。

本機 GLB 不會自動掃描 repository、`Downloads` 或其他使用者目錄。需要本機模型時，透過 `ROOMPILOT_LOCAL_GLB_ROOTS` 指定允許的根目錄；需要 zip 時則明確設定 `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS`。多個路徑使用作業系統的 path separator 分隔。

`ROOMPILOT_CATALOG_PROVIDER` 留空時由 profile 推導；full 為 strict PostgreSQL。連線或 view 不可用時必須顯示 unavailable／503，不會靜默換成另一批資料。

## 選配辨識模型

公開 repository 不附模型或私有評測資料。需要額外的房型／符號證據時，把自行確認授權的資產放在 `.runtime/floorplan/`，或透過 `.env.example` 列出的 `ROOM_HEAD`、`ROOMPILOT_SYMBOL_LIBRARY`、`ROOMPILOT_OPENING_MODEL` 與 `ROOMPILOT_ICON_TEMPLATE_DIR` 指定外部路徑。若要使用特定 reference plan，影像與 annotations 必須同時明確設定；未設定時不會套用任何黃金答案捷徑。
