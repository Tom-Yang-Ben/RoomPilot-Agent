# RAG 檢索管線（風格/設計 → 合適物件）

輸入自然語言的家具風格需求，從 9,349 件家具中找出最合適的物件。

> 系統總說明見 `docs/RAG檢索系統說明.md`，需求解析器規格見 `docs/query_parser_spec.md`。
> 目前狀態：索引已建置完成（9,349 筆 / **覆蓋率 100%**），UI 可在 `:7860` 啟動。

```
使用者輸入
   │
   │ query_parser.py     Claude Haiku 4.5 + structured outputs
   ▼                     自然語言 → 受控詞彙條件 + HyDE 查詢文本
結構化條件 { room_type, styles, moods, items[], budget… }
   │
   │ retriever.py
   ├─ Chroma where 硬過濾（房型 / 類別 / 價格 / 尺寸）
   ├─ bge-m3 向量檢索 top 50
   ├─ bge-reranker-v2-m3 重排 top 20（is_inferred / accent 配件降為 12，rerank 是延遲主因）
   ├─ style_compat 風格加權 + mood 命中加權
   └─ 跨品項去重（duplicate_group）
   ▼
top 8 / 每個品項  →  app.py（Gradio，卡片帶預渲染圖）
```

## 檔案

| 檔案 | 職責 |
| :-- | :-- |
| `category_groups.json` | 64 個 `category_final` → 19 個檢索群組；含各房型典型組合 |
| 風格詞表 | `vlm_annotation/taxonomy_v2.json`（6 風格 × 3 色卡 + 6×6 相容矩陣） |
| `embed_v3.py` | v3 → bge-m3 向量 → ChromaDB **同時** 產出 `rag_export/` 四個交付檔 |
| `query_parser.py` | 需求解析（規格見 `docs/query_parser_spec.md`） |
| `retriever.py` | 兩階段檢索 + 排序 + set 層收斂 |
| `app.py` | Gradio UI |

## 執行

```bash
PY=.venv-rag/bin/python

# 1. 建索引（實測 27 分鐘 / 9,349 筆 / MPS；--limit 50 可先冒煙測試）
$PY rag_pipeline/embed_v3.py
$PY rag_pipeline/embed_v3.py --only-changed   # 增量：只重算 text_hash 變動者

# 2. 單獨測解析
$PY rag_pipeline/query_parser.py "想要日式侘寂感、預算兩萬內的客廳沙發"

# 3. 命令列跑完整檢索
$PY rag_pipeline/retriever.py "北歐風溫馨感的客廳，幫我配一整組，預算十萬"

# 4. 開 UI
$PY rag_pipeline/app.py     # http://127.0.0.1:7860
```

環境變數：`ANTHROPIC_API_KEY`；未設定時自動讀專案根目錄的 `.anthropic_key`。

## 模型

| 用途 | 模型 | 備註 |
| :-- | :-- | :-- |
| 需求解析 | `claude-haiku-4-5` | 雲端 API。structured outputs 強制 JSON schema；系統提示走 prompt caching |
| 風格判定（批次） | `qwen3:8b` | 本機 Ollama，見 `json_adjustment/reclassify_styles.py` |
| Embedding | `BAAI/bge-m3` | 1024 維、cosine、normalized、max_len 512 |
| Rerank | `BAAI/bge-reranker-v2-m3` | 中文 cross-encoder；**勿**換成 ms-marco MiniLM（英文模型） |

## 改動時容易踩的三個坑（實測）

1. **`rag_indexable` 不能寫進 Chroma `where`** — 它是 v3 頂層欄位、不在 `chroma_metadata` 裡，
   過濾它會命中 0 筆。collection 本來就只收可索引的 9,349 筆。
2. **rerank 分數不可再套 sigmoid** — `bge-reranker-v2-m3` 經 CrossEncoder 已輸出 0-1；
   再套一次會把 0.984 壓成 0.728、0.0001 壓成 0.5，判別力歸零。
3. **structured outputs 的可為 null enum 要用 `anyOf`** —
   `{"type": ["string","null"], "enum": [...]}` 會被 API 以 400 拒絕。

## 排序公式

```
final = 0.60 × rerank(sigmoid) + 0.20 × style_compat + 0.10 × mood 命中率 + 0.10 × confidence
```

權重定義在 `retriever.py` 的 `W_RERANK / W_STYLE / W_MOOD / W_CONF`。

**風格為什麼是加權而不是硬過濾**：japandi 硬過濾只剩 362 筆，疊上房型與類別後可能剩個位數。
`taxonomy_v1.json` 的 12×12 `style_compat` 矩陣（japandi↔nordic 0.9）讓相容風格也撈得進來。

## 交付 SQL 的檔案（`rag_export/`）

`embed_v3.py` 一次算向量、同時寫 Chroma 與交付檔，保證兩邊同一批向量、同一個 `text_hash`。
規格見 `json_adjustment/RAGSQL.md`。

| 檔案 | 內容 |
| :-- | :-- |
| `furniture_embeddings_bge_m3.jsonl` | 每行一件：furniture_id / embedded_text / text_hash / model / dimension / embedding。⚠️ `RAGSQL.md` 的交付契約寫的是 `furniture_embeddings.jsonl`，實際輸出多了 `_bge_m3` 後綴（`embed_v3.py:37`），交付前需與 SQL 端確認檔名 |
| `embedding_metadata.json` | 批次規格（模型、維度、distance_metric、normalized、text_fields） |
| `embedding_failures.jsonl` | 失敗清單與原因 |
| `embedding_validation_report.json` | 覆蓋率、重複 ID、維度分布 |
