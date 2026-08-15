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

`ROOMPILOT_CATALOG_PROVIDER` 留空時由 profile 推導；full 為 strict PostgreSQL。連線或 view 不可用時必須顯示 unavailable／503，不會靜默換成另一批資料。

## 選配辨識模型

公開 repository 不附模型或私有評測資料。需要額外的房型／符號證據時，把自行確認授權的資產放在 `.runtime/floorplan/`，或透過 `.env.example` 列出的 `ROOM_HEAD`、`ROOMPILOT_SYMBOL_LIBRARY`、`ROOMPILOT_OPENING_MODEL` 與 `ROOMPILOT_ICON_TEMPLATE_DIR` 指定外部路徑。若要使用特定 reference plan，影像與 annotations 必須同時明確設定；未設定時不會套用任何黃金答案捷徑。
