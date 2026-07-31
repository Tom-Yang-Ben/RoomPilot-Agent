# RAG 家具向量交付需求

## 請交付的檔案

請提供一個包含全部正式家具向量的 JSONL 檔案，例如：

```text
furniture_embeddings_bge_m3.jsonl
```

正式家具總數必須為 **9,349 筆**，每一行代表一件家具。

## 每筆必要欄位

1. `item_id`
   - 必須對應 `JSON/furniture/furniture_official_catagory.json` 裡的正式家具 ID。
   - 9,349 筆資料的 `item_id` 不得重複。

2. `embedding`
   - 使用 `BAAI/bge-m3` 產生的實際向量。
   - 每筆必須包含完整的 1,024 個數值。
   - 不得包含 `NaN`、`Infinity`、字串或空值。
   - 向量必須完成正規化。

最小交付格式：

```json
{"item_id":"ikea-chair-001","embedding":[0.012,-0.034,0.056]}
```

上面的向量僅為格式範例；正式資料必須包含完整的 1,024 維向量。

## 建議一併提供的欄位

為了方便追蹤模型與文字版本，建議每筆都提供：

```json
{
  "item_id": "ikea-chair-001",
  "embedding_model": "BAAI/bge-m3",
  "embedding_dimension": 1024,
  "embedded_text": "實際用來產生這筆向量的完整文字",
  "text_hash": "embedded_text的64字元SHA-256",
  "normalized": true,
  "embedding": [0.012, -0.034, 0.056]
}
```

規格如下：

| 欄位 | 要求 |
|---|---|
| `embedding_model` | `BAAI/bge-m3` |
| `embedding_dimension` | `1024` |
| `embedded_text` | 必須與官方家具 JSON 目前的 `embedded_text` 完全一致 |
| `text_hash` | 必須與官方家具 JSON 目前的 `text_hash` 完全一致 |
| `normalized` | `true` |

## 不需要提供的欄位

以下欄位由 PostgreSQL 或匯入器處理，不需要放入向量檔：

- `embedding_id`
- `annotation_id`
- `created_at`
- 家具名稱與分類
- GLB 雲端網址
- 三視圖圖片網址

## 產生向量時的來源限制

- 必須使用目前的 `JSON/furniture/furniture_official_catagory.json`。
- 必須直接使用每筆家具現有的 `embedded_text` 產生向量。
- 不可自行修改、重新組合或使用舊版 `embedded_text`。
- `text_hash` 必須是該筆 `embedded_text` 的 SHA-256。
- 不可加入已排除或未匹配的家具。
- 不可另外建立一套 SQL Table。

## 交付前驗收清單

- [ ] 總筆數為 9,349
- [ ] 9,349 個 `item_id` 全部唯一
- [ ] 所有 `item_id` 都存在於官方家具 JSON
- [ ] 每筆都有 `embedding`
- [ ] 每個向量都是 1,024 維
- [ ] 所有向量值都是有限數值
- [ ] 使用模型為 `BAAI/bge-m3`
- [ ] 所有向量皆已正規化
- [ ] `embedded_text` 與官方 JSON 完全一致
- [ ] `text_hash` 與官方 JSON 完全一致

## SQL 匯入方式

收到向量檔後，SQL 負責人會執行：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_furniture_embeddings_to_postgres.py `
  --embeddings D:\path\furniture_embeddings_bge_m3.jsonl `
  --require-all
```

匯入器會自動驗證家具 ID、文字版本、SHA-256、模型、維度、數值內容、正規化與完整筆數，再 UPSERT 至：

```text
roompilot.furniture_embeddings
```

目前向量表已建立，但仍是空表；收到這份包含實際數值向量的檔案後才能完成正式匯入。
