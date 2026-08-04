# 問卷與 RAG 串接契約

## 目的

第 5 步問卷以 Kai PostgreSQL catalog 為唯一家具資料來源。使用者確認一個房間後，前端可非同步送出 RAG 檢索，將該房間的家具候選重新排序；RAG 不可用時，問卷仍可繼續。

## 資料流

1. 問卷以房間用途、已選家具類型與使用者輸入的家具偏好組成查詢字串。
2. 前端 `backend/server/static/scene_v2.js` 呼叫 `POST /api/rag/search/jobs`。
3. 後端 `backend/server/rag_api.py` 交給 `backend/spatial_data/rag/`：LLM 將自然語言轉成結構化需求，BGE-M3 搜尋 PostgreSQL/pgvector，reranker 排序。
4. 結果只回傳 `furniture_id` 排序，前端以既有的 Kai catalog 候選資料重新排序。
5. 第 6 步才依實際 GLB 尺寸、門窗淨空、走道與朝向驗證是否能放入。第 5 步不因缺 GLB 或幾何衝突阻止使用者繼續。

## 非阻塞規則

- RAG 工作失敗、尚未啟用或模型尚未下載時，保留基本推薦並顯示狀態訊息。
- 不可因 RAG 失敗、缺 GLB 或不合法擺放卡住問卷。
- RAG 不得產生、修改或覆寫房間邊界、門窗、家具座標及合法性判定。

## 啟用條件

`.env` 必須設定：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=postgres
ROOMPILOT_RAG_ENABLED=true
ROOMPILOT_RAG_PARSER_PROVIDER=openrouter
OPENROUTER_API_KEY=...
```

並安裝 `requirements.txt` 的 RAG 套件。首次執行會下載 `BAAI/bge-m3` 與 `BAAI/bge-reranker-v2-m3` 到 `ROOMPILOT_RAG_MODEL_CACHE` 或 Hugging Face 預設快取。

## 驗證端點

- `GET /api/catalog/status`：`catalog_provider.ready=true`、`count=7958`。
- `GET /api/rag/status`：資料庫 `current_embeddings=7958` 且 `search_function_available=true`；所有 blockers 消失後 `ready=true`。
- `POST /api/rag/search/jobs`：可建立工作；問卷即使收到失敗狀態也能前往下一個房間與第 6 步。
