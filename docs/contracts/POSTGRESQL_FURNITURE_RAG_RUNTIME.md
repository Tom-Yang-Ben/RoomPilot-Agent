# PostgreSQL Furniture RAG Runtime Contract

更新日期：2026-07-29  
主要 owner：Django  
協作 owner：Kai（PostgreSQL/catalog）、Bella（FastAPI/正式前端）

## 目的與邊界

本契約把 Django 的家具 RAG 接到 Kai 的正式 PostgreSQL/pgvector。所選的 OpenAI
或 Anthropic 只把自然語言轉成受控查詢；Django runtime 產生 BGE-M3 query vector、呼叫
SQL、以 `BAAI/bge-reranker-v2-m3` 排序並輸出證據；Bella 只轉接 API 與頁面。

RAG 不得決定家具位置、碰撞、淨空、結構或幾何合法性，不得修改
`layout_json`/`scene_json`，也不取代 Yen 的正式選件政策。第一版只供 `/rag`
驗證，不接入八步流程第 6 步。

## 執行資料流

```text
POST /api/rag/search/jobs
  -> GET /api/rag/search/jobs/{job_id} 輪詢真實執行階段
  -> selected RAG parser provider (OpenAI Responses or Anthropic Messages)
  -> Pydantic Structured Outputs
  -> semantic_query
  -> BAAI/bge-m3 normalized 1024-d vector（多品項批次推論）
  -> roompilot.search_furniture_embeddings_filtered(...)
  -> top 50 cosine candidates
  -> reranker top 20（inferred/accent 為 12；多品項合併成單一 batch）
  -> 0.60 rerank + 0.20 style + 0.10 mood + 0.10 confidence
  -> item/duplicate_group 去重
  -> Kai current catalog 補齊 CloudFront assets
```

房型、類別、價格、最大寬高、role、size class 是 SQL 硬條件；風格、氛圍
與 pattern 只能影響排序。未由使用者指定的硬條件保持 `null`。

## PostgreSQL 介面

`roompilot.furniture_embedding_source_current` 增加 `chroma_metadata JSONB`，資料仍
來自 active `furniture_items.raw_data`，並以 current `text_hash` 綁定 embedding。

`roompilot.search_furniture_embeddings_filtered` 輸入：

- `query_embedding VECTOR`、`query_model VARCHAR`、`match_count INTEGER`
- `room_type VARCHAR`、`category_values TEXT[]`
- `price_min`/`price_max INTEGER`
- `max_width_cm`/`max_height_cm NUMERIC`
- `item_role VARCHAR`、`item_size_class VARCHAR`

輸出只有 `item_id`、`annotation_id`、`embedded_text`、`metadata`、cosine
distance/similarity；不得輸出 embedding。函式只命中相同 model/dimension、active
item 與 current text hash。舊的 `search_furniture_embeddings` 保留相容。

v1 使用 exact cosine scan，固定模型為 `BAAI/bge-m3`、維度 1024；不建立 HNSW，
不重匯現有 9,349 筆向量。

## HTTP 介面

### `GET /api/rag/status`

不得呼叫 OpenAI／Anthropic 或載入模型。回傳 provider/model/key/package/cache/load/database 狀態、
current embedding 數量與 blockers；不得回傳 secret、DB host 或密碼。

### `POST /api/rag/search`

Request：

```json
{"query": "北歐風小客廳沙發，寬度 180 公分內", "top_k": 8}
```

`query` 為 1–1000 字，`top_k` 為 1–8。Response schema 是
`roompilot.rag.search.v1`，包含 source、`parsed_query`、clarification、風格、預算、
blocks/hits、各分數與 timings。尺寸欄位使用 `*_cm` 並帶
`coordinate_unit: "cm"`；家具只使用 Kai current catalog 的 ID 與 CloudFront URL。

錯誤：request validation 為 422；未啟用、DB、套件、模型或 key 缺失為 503；
所選 LLM provider 的 timeout/refusal/invalid structured output 為 502。不得 fallback 到另一個 provider、Chroma、
JSON、keyword search 或其他 LLM。

### 背景工作與進度

正式 `/rag` 頁面先呼叫 `POST /api/rag/search/jobs`，收到 202 與
`roompilot.rag.job.v1` 後，再輪詢 `GET /api/rag/search/jobs/{job_id}`。工作回傳
`status`、0–100 `progress`、`stage`、安全訊息與 `elapsed_ms`；完成時才附上
`roompilot.rag.search.v1` result。百分比代表已完成的後端階段，不是預估剩餘時間，
所以 CPU 執行 BGE-M3 或 reranker 時可能停在同一百分比較久。同步
`POST /api/rag/search` 保留給既有消費端。

同一 FastAPI 行程最多執行一個背景 RAG 工作，避免兩個 CPU 模型工作互相搶資源。
完成／失敗工作保留一小時後清除；錯誤內容沿用同步 API 的安全映射，不回傳例外、key
或連線資訊。

## 效能邊界

PostgreSQL/pgvector 已是正式資料來源；目前 9,349 筆 exact cosine top-50 約為秒級，
不是分鐘級等待的主要來源。CPU lazy-load、BGE-M3 embedding 與 cross-encoder reranker
才是主要成本。runtime 將同一次多品項查詢的 embedding 與 reranker 合併批次，但不減少
top-50、top-20/12，也不改變評分公式。

常駐服務完成第一次 lazy-load 後可避免反覆載入權重。若仍需明顯縮短時間，優先使用
能容納約 4.6 GB 常駐模型的 CUDA GPU（建議至少 8 GB VRAM，12 GB 較有餘裕），或另行
驗證 OpenVINO/ONNX INT8 CPU runtime。HNSW 只會優化 SQL 的秒級區段；降低 rerank
候選數或更換小模型可再加速，但屬於會影響召回／排序品質的另一份契約變更。

## 設定與模型

- `ROOMPILOT_RAG_ENABLED=false`（安全預設）
- `ROOMPILOT_RAG_PARSER_PROVIDER=openai|anthropic`（只控制 RAG parser）
- `OPENAI_API_KEY`／`ANTHROPIC_API_KEY`（server only；只需填所選 provider）
- `ROOMPILOT_RAG_OPENAI_MODEL=gpt-5.6-sol`
- `ROOMPILOT_RAG_ANTHROPIC_MODEL=claude-sonnet-4-6`
- `ROOMPILOT_RAG_PARSER_MODEL=`（選填；覆寫所選 provider 的預設模型）
- `ROOMPILOT_RAG_REASONING_EFFORT=low`（OpenAI only）
- `ROOMPILOT_RAG_ANTHROPIC_MAX_TOKENS=4096`
- `ROOMPILOT_RAG_TIMEOUT_SECONDS=30`
- `ROOMPILOT_RAG_MODEL_CACHE`（可選，repo 外）
- `ROOMPILOT_RAG_DEVICE=auto|cpu|cuda|mps`

Runtime 只 lazy-load 已快取模型。檢查模型使用
`python scripts/rag/prefetch_models.py`；只有明確加 `--download` 才可下載。不得提交
API key、cache、權重、ChromaDB 或 Django Gradio runtime。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_rag_domain.py tests/test_rag_api.py tests/test_furniture_embeddings_sql.py
node --check backend/server/static/rag.js
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```
