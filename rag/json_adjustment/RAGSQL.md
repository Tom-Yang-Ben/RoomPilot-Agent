
你是 SQL 負責人的話，**RAG 的人最少要交給你一個「向量結果檔」和一個「規格說明檔」**，你才能安全地匯入 PostgreSQL。

你現在的家具主 JSON 已經有：

* `id`
* `description`
* `features`
* `search_keywords`
* `rag_text`
* 風格、材質、顏色、房間類型等欄位

而且目前資料集標示為 9,350 筆，因此家具基本資料不需要由 RAG 人員再重做一次。

# RAG 人員應該交給你的檔案

## 1. `furniture_embeddings.jsonl`

這是最重要的檔案，一行代表一件家具的向量資料。

建議格式：

```json
{"furniture_id":"abo-bed-frames-19-amazon-brand-rivet-a8910-dresser","embedded_text":"名稱：Rivet Fisher 鄉村木質床架平臺，帶床頭板。類別：抽屜櫃。顏色：木色。材質：木材。風格：rustic、french_country。描述：此抽屜櫃採用拼接木板設計……","text_hash":"c0e84c57d1b8...","embedding_model":"BAAI/bge-m3","embedding_dimension":1024,"embedding":[0.0124,-0.0361,0.0087],"embedded_at":"2026-07-27T12:00:00+08:00"}
```

實際的 `embedding` 會有 1024 個或其他指定數量的浮點數，不會只有範例中的三個。

### 必要欄位

| 欄位                    | 用途                                |
| ----------------------- | ----------------------------------- |
| `furniture_id`        | 對應家具主表的`id`                |
| `embedded_text`       | 實際送進 embedding model 的完整文字 |
| `text_hash`           | 判斷文字有沒有修改                  |
| `embedding_model`     | 使用哪個 embedding 模型             |
| `embedding_dimension` | 向量維度                            |
| `embedding`           | 真正的向量陣列                      |

### 建議附加欄位

| 欄位                      | 用途                           |
| ------------------------- | ------------------------------ |
| `embedded_at`           | 向量產生時間                   |
| `text_format_version`   | `embedded_text` 組合規格版本 |
| `source_schema_version` | 來源家具 JSON 版本             |
| `normalized`            | 模型是否輸出 normalized vector |

---

# 為什麼推薦 JSONL，不推薦 CSV？

向量可能長這樣：

```json
[0.0124, -0.0361, 0.0087, ...]
```

一筆可能有 768、1024、1536 甚至更多數值。

CSV 雖然也能存，但容易遇到：

* 逗號與引號解析問題
* 單一欄位非常長
* Python 和 PostgreSQL 轉型較麻煩
* 某一筆格式錯誤時不好定位

因此建議：

```text
家具一般資料：JSON／CSV
Embedding 向量資料：JSONL
```

---

## 2. `embedding_metadata.json`

這是整批向量的規格檔，讓你知道 SQL 要建立成什麼樣子。

範例：

```json
{
  "dataset_name": "roompilot_furniture",
  "source_file": "furniture_official_catagory.json",
  "source_schema_version": "2.0+enriched_v1+vlm_annotated",
  "source_item_count": 9350,
  "embedded_count": 9318,
  "failed_count": 32,

  "embedding_model": "BAAI/bge-m3",
  "embedding_dimension": 1024,
  "distance_metric": "cosine",
  "normalized": true,

  "text_format_version": "v1",
  "text_fields": [
    "name_zh",
    "canonical_category_zh",
    "colors",
    "materials",
    "room_types",
    "style_primary",
    "style_secondary",
    "description",
    "features",
    "search_keywords",
    "rag_text"
  ],

  "generated_at": "2026-07-27T12:00:00+08:00"
}
```

你會根據這個檔案決定：

```sql
embedding VECTOR(1024)
```

以及索引：

```sql
USING hnsw (embedding vector_cosine_ops)
```

所以這個檔案不能缺少：

```text
embedding_model
embedding_dimension
distance_metric
normalized
```

---

## 3. `embedding_failures.jsonl`

這是失敗清單。

範例：

```json
{"furniture_id":"abo-example-001","error_type":"empty_embedded_text","error_message":"embedded_text is empty"}
{"furniture_id":"abo-example-002","error_type":"model_error","error_message":"CUDA out of memory"}
{"furniture_id":"abo-example-003","error_type":"invalid_dimension","expected_dimension":1024,"actual_dimension":768}
```

你不一定要把這份匯入正式資料表，但要保留它，因為可以解釋為什麼：

```text
家具總數：9350
向量數量：9318
缺少向量：32
```

否則你看到筆數不一致時，會不知道是匯入失敗，還是原本就沒有成功產生。

---

## 4. `embedding_validation_report.json`

這是整批驗證報告。

範例：

```json
{
  "total_source_items": 9350,
  "total_embedding_records": 9318,
  "unique_furniture_ids": 9318,
  "duplicate_furniture_ids": 0,
  "missing_furniture_ids": 32,
  "invalid_vector_count": 0,
  "null_vector_count": 0,
  "dimension_distribution": {
    "1024": 9318
  },
  "model_distribution": {
    "BAAI/bge-m3": 9318
  },
  "coverage_percent": 99.66
}
```

你匯入前至少要確認：

```text
duplicate_furniture_ids = 0
invalid_vector_count = 0
null_vector_count = 0
dimension_distribution 只有一種維度
model_distribution 最好只有一個模型
```

---

# 最建議的交接資料夾

請 RAG 人員最後交給你：

```text
rag_export/
├─ furniture_embeddings.jsonl
├─ embedding_metadata.json
├─ embedding_failures.jsonl
└─ embedding_validation_report.json
```

其中：

| 檔案                                 | 是否必須 |
| ------------------------------------ | -------: |
| `furniture_embeddings.jsonl`       |     必須 |
| `embedding_metadata.json`          |     必須 |
| `embedding_failures.jsonl`         | 強烈建議 |
| `embedding_validation_report.json` | 強烈建議 |

---

# `furniture_id` 一定要怎麼設定？

一定要對應你家具 JSON 裡的：

```json
"id": "abo-bed-frames-19-amazon-brand-rivet-a8910-dresser"
```

不要使用：

```text
name_zh
name_en
glb_url
object_key
流水號
```

正確關聯應該是：

```text
家具主表 furniture_items.id
             ↓
furniture_embeddings.furniture_id
```

例如：

```sql
FOREIGN KEY (furniture_id)
REFERENCES furniture_items(id)
```

家具名稱可能修改、重複或翻譯錯誤，但 `id` 才是穩定的資料關聯鍵。

---

# RAG 人員不需要交給你的東西

你不需要拿到：

* 模型權重檔
* Hugging Face 模型資料夾
* GPU 執行環境
* VLM 圖片
* GLB render 圖片
* Kaggle Notebook
* 每個家具的原始圖片

這些不是 SQL 匯入需要的資料。

你只需要拿到：

```text
家具 ID
實際 embedded_text
文字 hash
模型名稱
維度
向量
```

---

# 建議不要讓 RAG 人員只交一個向量陣列

以下格式不合格：

```json
[
  [0.12, 0.35, -0.66],
  [0.14, 0.21, -0.19]
]
```

因為你不知道每個向量對應哪件家具。

也不要只有：

```json
{
  "furniture_id": "abc-001",
  "embedding": [0.12, 0.35]
}
```

至少還要保留：

```text
embedded_text
text_hash
embedding_model
embedding_dimension
```

不然之後文字或模型改變，你無法判斷哪些向量需要更新。

---

# 你可以直接傳給 RAG 人員的交件規格

```text
請輸出以下四個檔案：

1. furniture_embeddings.jsonl
每行一件家具，必要欄位：
- furniture_id
- embedded_text
- text_hash
- embedding_model
- embedding_dimension
- embedding
- embedded_at
- text_format_version

2. embedding_metadata.json
必要內容：
- source_file
- source_item_count
- embedded_count
- failed_count
- embedding_model
- embedding_dimension
- distance_metric
- normalized
- text_format_version
- text_fields

3. embedding_failures.jsonl
列出所有沒有成功產生向量的 furniture_id 與錯誤原因。

4. embedding_validation_report.json
包含：
- 總筆數
- 成功筆數
- 失敗筆數
- 重複 ID 數
- 缺少 ID 數
- 空向量數
- 錯誤維度數
- 模型分布
- 維度分布
- 覆蓋率

furniture_id 必須與家具主 JSON 的 id 完全相同。
全批資料只能使用已確認的單一 embedding model 和單一向量維度。
```

# 最終分工

RAG 人員負責：

```text
家具 JSON
→ embedded_text
→ text_hash
→ embedding model
→ furniture_embeddings.jsonl
```

你負責：

```text
furniture_embeddings.jsonl
→ 驗證 ID、模型及維度
→ 匯入 furniture_embeddings
→ UPSERT
→ 建立外鍵
→ 建立 HNSW index
→ 提供覆蓋率查詢
```

所以，你應該跟 RAG 人員要的核心交付物就是：

> **以家具 `id` 為關聯鍵、包含文字、hash、模型、維度及向量的 `furniture_embeddings.jsonl`。**
