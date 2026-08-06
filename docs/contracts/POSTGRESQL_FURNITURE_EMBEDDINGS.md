# PostgreSQL 家具向量契約

更新日期：2026-08-06

## 目前狀態

- 正式來源：`JSON/furniture/furniture_official_catagory.json`
- 正式向量來源：`JSON/RAG/furniture_embeddings_bge_m3.jsonl`
- live current catalog／RAG-indexable 筆數：7,958；舊 8,675／8,076／599 僅為歷史匯入批次
- 每筆都有可驗證的 `embedded_text` 與 SHA-256 `text_hash`
- JSON 宣告目標：`BAAI/bge-m3`、1,024 維、cosine、normalized
- `/api/rag/status` 驗證 `roompilot.furniture_embeddings` 有 7,958 筆 current 向量，全部必須連到目前 current 家具與 VLM annotation；inactive 家具不得進向量表
- 118 筆 `floor-lamp` 均屬 active source，且都有 current BGE-M3 向量
- 開發階段使用無固定維度的 `VECTOR`；尚不建立 HNSW index

## 責任邊界

Kai／SQL owner 維護：

- `roompilot.furniture_embeddings`、外鍵、唯一限制與維度檢查
- `roompilot.furniture_embedding_source_current` 來源 View
- UPSERT 匯入器與資料庫寫入驗證
- 模型與維度確定後的固定維度 migration、HNSW index、查詢 SQL

RAG owner 維護：

- `embedded_text` 組合品質與 embedding 模型選擇
- 實際向量產生
- `text_hash` 與向量長度驗證
- 檢索品質測試

RAG 不另外建立第二套資料表。正式向量必須透過本契約寫入。

## 檔案

- Schema：`scripts/sql/roompilot_furniture_embeddings_schema.sql`
- 匯入器：`scripts/sql/import_furniture_embeddings_to_postgres.py`
- 家具主資料匯入器：`scripts/sql/import_official_catalog_to_postgres.py`

## 驗證並匯入正式向量

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_furniture_embeddings_to_postgres.py `
  --embeddings JSON/RAG/furniture_embeddings_bge_m3.jsonl `
  --require-all `
  --dry-run

.\.venv\Scripts\python.exe scripts/sql/import_furniture_embeddings_to_postgres.py `
  --embeddings JSON/RAG/furniture_embeddings_bge_m3.jsonl `
  --require-all
```

第二個指令會建立或更新 Schema，確認 SQL source view 的 current／RAG-indexable 家具與官方 JSON 中對應資料的文字及 hash 完全一致，再 UPSERT 完整 current 數值向量。2026-08-06 live 驗收值為 7,958 筆；匯入器仍須以當次 source view 為準，不能硬編碼筆數。

## RAG 向量交付格式

支援 JSON array、`{"embeddings": [...]}`、`{"items": [...]}` 或 JSONL。每筆最小格式：

```json
{
  "item_id": "正式家具 item_id",
  "embedding": [0.012, -0.034]
}
```

可選欄位為 `embedding_model`、`embedding_dimension`、`embedded_text`、`text_hash`。如果提供文字與 hash，兩者必須和官方來源完全一致；未提供時由官方來源補入。

正式完整批次：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_furniture_embeddings_to_postgres.py `
  --embeddings JSON/RAG/furniture_embeddings_bge_m3.jsonl `
  --require-all
```

匯入器會拒絕未知 `item_id`、過期文字或 hash、NaN／Infinity、錯誤維度、重複資料，以及目標模型未正規化的向量。UPSERT 唯一鍵為 `(item_id, embedding_model, text_hash)`。

## 搜尋與 HNSW 時機

`roompilot.search_furniture_embeddings(query_embedding, query_model, match_count)` 只搜尋：

- 相同模型
- 相同實際向量維度
- `text_hash` 仍與目前官方家具來源一致的向量

確定單一模型、固定維度、距離方法與大部分資料已完成後，才另做 migration 將欄位固定為 `VECTOR(1024)` 並建立 cosine HNSW index。

OpenAI 解析、SQL 硬篩選、BGE reranking 與 Bella 測試頁的 runtime 契約另見
[`POSTGRESQL_FURNITURE_RAG_RUNTIME.md`](POSTGRESQL_FURNITURE_RAG_RUNTIME.md)。
