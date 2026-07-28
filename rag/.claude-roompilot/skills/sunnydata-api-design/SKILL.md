---
name: sunnydata-api-design
description: 內部介面與資料交付契約設計 — query_parser structured output schema、retriever 回傳契約、rag_export 四個交付檔與版本化、截斷策略、錯誤格式、text_hash 冪等性。
origin: ECC
---

# 介面與資料交付契約設計

RoomPilot **沒有對外 REST API**（純本機 Gradio 檢索系統，無 HTTP 服務端、無 FastAPI）。
本技能把 API 契約設計的原則整套搬到本專案真正存在的四種介面上：

| 介面種類 | 具體對象 |
| :--- | :--- |
| 模組介面 | `query_parser.parse()` → `retriever.retrieve()` → `app.results_html()` |
| 模型介面 | Claude Haiku 4.5 structured outputs 的 JSON schema（`build_schema()`） |
| 儲存介面 | ChromaDB collection `furniture_v3` 的 `chroma_metadata` 欄位與 `where` 條件 |
| 交付契約 | `rag_export/` 四個檔案交給 SQL 端（規格見 `json_adjustment/RAGSQL.md`） |

原則不變——命名、操作語意、統一信封、截斷、過濾排序、金鑰控制、限流、版本化——
只是語境換成本專案。**契約衝突時以 `docs/` 與 `json_adjustment/*.md` 為準**（文件為契約）。

## When to Activate

- 設計或修改模組之間的函式介面（`parse` / `retrieve` / `search_item` 的參數與回傳）
- 審查既有契約（`docs/query_parser_spec.md`、`json_adjustment/RAGSQL.md`）
- 調整截斷階梯（`VEC_TOP_K` / `RERANK_TOP_K` / `FINAL_TOP_K`）或增量比對邏輯
- 設計錯誤與失敗清單格式（`embedding_failures.jsonl`）
- 規劃交付檔版本化策略（`text_format_version`、`source_schema_version`、collection 名）
- 產出要交給第三方（SQL 端 / 專題報告）的資料契約

## 契約對象設計

### 命名結構

```
# 資料鍵一律 snake_case、名詞、單複數依語意；不用縮寫
item_id                 # 家具主鍵（rag_export 與 Chroma id 共用）
category_group          # 19 檢索群組之一（不是 64 細類）
category_final          # 64 細類（只在來源 JSON，不進 LLM 選項）
style_primary           # 六風格之一
style_compat            # 6×6 相容矩陣
embedded_text           # 實際送進 bge-m3 的完整文字
text_hash               # embedded_text 的雜湊，增量與冪等的依據
semantic_query          # 每個品項專屬的 HyDE 查詢句

# 巢狀關係用「所屬物件 + 子鍵」表達，不另造扁平前綴
parsed["items"][i]["price_max"]        # 品項層預算上限
parsed["budget_total"]                 # 需求層總預算
result["items"][i]["results"][j]       # 該品項的檢索結果列
```

### 命名規則

```
# GOOD
item_id / category_group / price_twd       # snake_case、名詞
retrieve(parsed, top_k=FINAL_TOP_K)        # 動詞-受詞，參數有預設值
build_where(item, parsed, allocated, data) # 動詞開頭，回傳單一型別
embedding_failures.jsonl                   # 交付檔用「名詞_名詞.副檔名」

# BAD
itemID / CategoryGroup                     # camelCase / PascalCase 混入資料鍵
getItems()                                 # 駝峰式函式名
doQuery()                                  # 動作語意不明
data.json                                  # 交付檔名不含內容語意
rag_indexable 寫進 chroma where            # 它是頂層欄位，不在 chroma_metadata → 命中 0 筆
```

> **鐵律**：`rag_indexable` **不能**出現在任何 Chroma `where` 條件裡。
> 它是來源 JSON 的頂層欄位，`embed_v3.py` 在寫入前就已用它篩掉不可索引品項。

## 操作語意與結果狀態

### 操作語意

| 操作 | 冪等 | 唯讀 | 用於 |
| :--- | :--- | :--- | :--- |
| `query_parser.parse(text)` | 否（LLM 有隨機性，但受控詞彙收斂） | 是 | 自然語言 → 結構化條件 |
| `retriever.retrieve(parsed)` | 是（同 parsed 同索引 → 同結果） | 是 | 兩階段檢索 |
| `embed_v3.py --only-changed` | **是**（`text_hash` 相同就沿用舊向量） | 否 | 增量重建索引 |
| `embed_v3.py`（全量） | 是（結果等價，但重算一次向量） | 否 | 全量重建索引 |
| `build_rag_v3.py --dry-run` | 是 | 是 | 只印統計、不落檔 |

> `--only-changed` 的冪等性完全由 `text_hash` 保證：**它就是本專案的 `Idempotency-Key`**。
> 重複執行同一批資料不會產生第二份向量，也不會改變 `rag_export/` 內容。

### 結果狀態對照

REST 的狀態碼在本專案對應為「結果狀態」——每個狀態都有明確的呼叫端處理方式：

```
# 成功
ok                       — 檢索命中，results 非空
relaxed                  — 硬過濾放寬後才命中（需在 UI 標示條件已放寬）
reused                   — 增量模式沿用舊向量（embedding_metadata.reused_vector_count）

# 需要呼叫端介入（等價 4xx）
needs_clarification      — 需求不足，回 clarify_question + clarify_options（等價 422）
empty_after_filter       — where 過濾後 0 筆，results=[]（等價 404，非錯誤）
invalid_dimension        — 向量維度 != 1024（等價 422，寫入 failures）
empty_embedded_text      — embedded_text 為空（等價 400，寫入 failures）
not_indexable            — rag_indexable=false（等價 409，預期內跳過）

# 需要人介入（等價 5xx）
model_error              — bge-m3 / reranker 編碼失敗，向量為 None
api_error                — Anthropic API 呼叫失敗（金鑰、額度、schema 400）
```

`error_type` 的字串值**就是契約**：`embed_v3.py` 的驗證報告會直接統計這些值
（`invalid_vector_count` 數 `invalid_dimension`、`null_vector_count` 數 `model_error`）。
新增 `error_type` 時必須同步更新驗證報告的統計欄位。

### 常見錯誤

```
# BAD：所有失敗都吞掉，回空 list
except Exception:
    return []

# GOOD：分類、記錄、讓呼叫端可判斷
failures.append({"item_id": item["id"], "error_type": "invalid_dimension",
                 "expected_dimension": 1024, "actual_dimension": len(vec)})

# BAD：把「0 筆結果」當成錯誤丟例外
raise ValueError("no results")

# GOOD：0 筆是合法結果，用 relaxed 旗標表達檢索過程
return {"item": item, "where": where, "results": [], "relaxed": False}

# BAD：structured outputs 可為 null 的 enum 寫成型別陣列
{"type": ["string", "null"], "enum": [...]}      # → API 回 400

# GOOD：用 anyOf 包一層
{"anyOf": [{"type": "string", "enum": [...]}, {"type": "null"}]}
```

## 回傳格式

### 單一結果（`search_item`）

```json
{
  "item": { "item_id": "main_sofa", "label_zh": "主沙發", "category_group": "sofa" },
  "where": { "$and": [{ "category_final": { "$in": ["沙發", "L型沙發"] } },
                      { "price_twd": { "$lte": 26000 } }] },
  "results": [
    { "id": "abo-sofa-0421", "final": 0.8134, "rerank": 0.91,
      "style": 0.9, "mood": 0.67, "conf": 0.85, "meta": { "name_zh": "…" } }
  ],
  "relaxed": false
}
```

### 集合結果（`retrieve`，含截斷資訊）

```json
{
  "dominant_style": "japanese",
  "style_zh": "日式侘寂",
  "budget_total": 60000,
  "items": [ { "item": {}, "results": [], "relaxed": false } ],
  "meta": {
    "vec_top_k": 50,
    "rerank_top_k": 20,
    "final_top_k": 8,
    "returned": 8,
    "truncated": true,
    "budget_slack": 1.3
  }
}
```

### 錯誤／失敗清單（`rag_export/embedding_failures.jsonl`，一行一筆）

```json
{"item_id": "abo-chair-0012", "error_type": "invalid_dimension", "expected_dimension": 1024, "actual_dimension": 768}
{"item_id": "ikea-lamp-0331", "error_type": "empty_embedded_text", "error_message": "embedded_text is empty"}
{"item_id": "abo-rug-0907",   "error_type": "not_indexable",      "error_message": "rag_indexable=false（is_active=False 或無文本）"}
```

**失敗清單就是本專案的 error response**：不丟例外中斷整批，逐筆記錄後繼續，
最後由 `embedding_validation_report.json` 匯總。批次工作絕不因單筆失敗而全滅。

### 回傳信封變體

```python
# 方案 A：完整信封（交付給外部時採用 —— rag_export 走這條）
#   資料 + meta（規格、數量、時間）+ 失敗清單分檔
#   優點：SQL 端不必猜任何欄位；缺點：檔案數較多
{
    "data": [...],          # furniture_embeddings_bge_m3.jsonl（逐行）
    "meta": {...},          # embedding_metadata.json
    "report": {...},        # embedding_validation_report.json
    "failures": [...],      # embedding_failures.jsonl（逐行）
}

# 方案 B：扁平回傳（模組之間採用 —— retriever / query_parser 走這條）
#   成功就直接回資料 dict，失敗以旗標欄位（relaxed / needs_clarification）表達
#   優點：呼叫端程式碼短；缺點：需靠文件說明欄位語意
```

## 截斷與分頁

本專案沒有「翻頁」需求（UI 一次呈現 8 張卡片），但**截斷**的設計問題完全相同。

### 固定階梯截斷（對應 offset 分頁）

```python
VEC_TOP_K = 50           # Chroma 向量召回
RERANK_TOP_K = 20        # 送進 cross-encoder 的候選（每 50 筆約 10 秒，是延遲主因）
RERANK_TOP_K_LIGHT = 12  # 配件品項（is_inferred / accent）再降額
FINAL_TOP_K = 8          # 最終呈現
```

**優點**：延遲可預測、成本固定、實作簡單。
**缺點**：召回階段漏掉的東西後面救不回來；`VEC_TOP_K` 調小會直接傷 recall。

### 游標式增量（對應 cursor 分頁）

```bash
.venv-rag/bin/python rag_pipeline/embed_v3.py --only-changed
# 游標 = text_hash：與既有 rag_export 比對，只重算變動者
# 646 筆約 1.5 分鐘；全量 9,349 筆約 27 分鐘
```

```json
{ "source_item_count": 9349, "embedded_count": 9349,
  "reused_vector_count": 8703, "failed_count": 0 }
```

**優點**：成本與變動量成正比、可重複執行不重複計算（冪等）。
**缺點**：依賴既有 `rag_export/` 存在；檔名變更（舊 `furniture_embeddings.jsonl`）需相容讀取。

### 選用對照

| 情境 | 截斷策略 |
| :--- | :--- |
| UI 即時檢索（延遲敏感） | 固定階梯（50 → 20 → 8） |
| 配件／推論品項（`is_inferred`） | 固定階梯降額（`RERANK_TOP_K_LIGHT=12`） |
| 索引重建（資料變動小） | 游標式（`--only-changed`，text_hash） |
| 索引冒煙測試 | 固定截斷（`--limit 50`） |

## 過濾、排序與語意查詢

### 硬過濾（Chroma `where`）

```python
# 等值 / 集合
{"room_types": {"$in": ["living_room"]}}
{"category_final": {"$in": ["沙發", "L型沙發", "沙發床"]}}

# 比較運算
{"price_twd": {"$lte": 26000}}
{"width_cm": {"$lte": 220.0}}

# 複合條件一律用 $and 明寫，不靠隱式合併
{"$and": [{"category_final": {"$in": [...]}}, {"price_twd": {"$lte": 26000}}]}
```

**界線（PROJECT_BRIEF 明訂）**：房型／類別／價格／尺寸 = 硬過濾；
風格／氛圍 = 軟加權；顏色／材質 = **只進 `semantic_query`**，不做過濾。

### 排序

```python
# 單一綜合分數，權重定義在 rag_pipeline/retriever.py:47
final = 0.60 * rerank + 0.20 * style_compat + 0.10 * mood_hit + 0.10 * confidence

# 多層次：先綜合分數，再去重（同系列只留最高分），最後主導風格收斂
ranked = sorted(rows, key=lambda r: -r["final"])
```

改權重屬於**破壞性契約變更**（同一 query 的結果順序會變），必須同步
`docs/RAG檢索系統說明.md` 並在 PR 說明比對前後結果。

### 語意查詢（HyDE）

```python
# semantic_query 必須寫成與 embedded_text 相同句式，向量才對得上
"名稱：低背布沙發。類別：沙發。顏色：米白。材質：布。風格：japanese。描述：…"

# BAD：把使用者原句直接丟去 embed
"我想要一個日式的沙發，預算兩萬"
```

### 欄位精簡（對應 sparse fieldsets）

```python
# chroma_metadata 只放「過濾與排序會用到」的欄位，其餘留在來源 JSON
include=["metadatas", "distances"]      # 不要 include documents，省記憶體與傳輸
# 卡片顯示所需的長描述改用 item_id 回查 furniture_enriched_v3.json
```

## 金鑰與存取控制

### 金鑰載入契約

```python
# 優先序：環境變數 > .anthropic_key 檔案；兩者皆無 → 啟動即失敗
key = os.environ.get("ANTHROPIC_API_KEY") or KEY_FILE.read_text().strip()
if not key:
    raise SystemExit("缺少 ANTHROPIC_API_KEY 或 .anthropic_key")
```

- `.anthropic_key` 為純文字檔、已列入 `.gitignore`，**絕不可提交或回顯內容**
- 錯誤訊息只能說「缺少金鑰」，不得印出金鑰片段或檔案內容

### 存取控制模式

```python
# 服務層級：Gradio 只綁 127.0.0.1，不開 share，不做公開存取
build_ui().launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())

# 資料層級：可索引性在寫入時就決定，不靠查詢時檢查
if not item["rag_indexable"]:
    skipped.append(item)          # 不進 Chroma，不進交付檔

# 檔案層級：卡片圖走 base64 內嵌，不開放 Gradio 靜態檔路徑
uri = thumb_data_uri(png_path)    # 只讀 rendering/output/ 底下的既有檔案
```

## 速率與成本限制

本專案沒有多租戶流量，但**每一次 LLM 呼叫都在燒錢**，限制的必要性相同。

### 節流與重試

```python
# 需求解析：prompt caching + 受控詞彙，單次約 US$0.005
# 批次標註／風格判定：必須可續跑，中斷後不重跑已完成品項
MAX_RETRIES, BACKOFF, BATCH_SLEEP = 3, 2.0, 0.2

for attempt in range(MAX_RETRIES):
    try:
        return call(...)
    except Exception:
        if attempt == MAX_RETRIES - 1:
            raise                 # 有上限的重試 = 有上限的成本
        time.sleep(BACKOFF ** attempt)
```

等價於 REST 的 `429 Too Many Requests` + `Retry-After`：
本專案沒有伺服器回傳限流標頭，**上限必須由呼叫端自己守住**。

### 呼叫成本層級

| 呼叫類型 | 上限建議 | 單位 | 成本量級 |
| :--- | :--- | :--- | :--- |
| UI 需求解析（Haiku） | 1 次／查詢，`MAX_ITEMS=6` | 每次查詢 | 約 US$0.005 |
| 追問重解析（clarify） | 1 次／按鈕點擊 | 每次互動 | 約 US$0.005 |
| 六風格批次判定（Haiku） | 全量 9,349 筆 | 一輪 | 約 US$7 |
| 六風格批次判定（Ollama `qwen3:8b`） | 本機無金錢成本 | 一輪 | 只吃記憶體與時間 |
| VLM 標註（Haiku，批次可續跑） | 分批 + checkpoint | 一輪 | 依批量計 |

**超限處理**：批次腳本必須支援 `--limit` 與 `--compare N` 先小樣本驗證；
未先跑小樣本就跑全量，等於沒有速率限制。

## 版本化

### 欄位級版本（本專案主要手段）

```json
{ "text_format_version": "v1",
  "source_schema_version": "3.0+enriched_v3",
  "embedding_model": "BAAI/bge-m3",
  "embedding_dimension": 1024,
  "id_key": "item_id" }
```

**優點**：交付檔自帶版本、SQL 端可據此判斷要不要重建表。
**缺點**：需要紀律——改了組句方式卻沒升 `text_format_version`，等於騙下游。

### 資源名版本（collection / 檔名）

```
chroma_db/  collection: furniture_v3      # v1 / v2 / v3 並存，切換只改常數
rag_dataset/furniture_enriched_v3.json    # 舊版保留，不覆寫
rag_export/furniture_embeddings_bge_m3.jsonl   # 檔名含模型名，換模型即換檔
```

**優點**：新舊並存、回滾只是改一個常數。
**缺點**：磁碟占用成長；舊 collection 需人工清理。

### 版本化策略

```
1. 從 v1 起跳，沒有實際不相容就不要升版
2. 同時最多維持 2 個現役版本（現行 + 前一版），其餘歸檔
3. 汰換流程：
   - 在 rag_pipeline/README.md 標註舊版將停用
   - 新版本跑完 embed_v3 並通過驗證報告後才切換 COLLECTION 常數
   - 舊 collection 保留至少一輪，確認無回滾需求再刪
4. 非破壞性變更不需要新版本：
   - 新增 chroma_metadata 欄位（下游忽略即可）
   - 新增交付檔的選填欄位
   - 新增 error_type（但要同步驗證報告統計）
5. 破壞性變更必須升版：
   - 改 embedded_text 組句方式（→ 升 text_format_version 並全量重建）
   - 換 embedding 模型或維度（→ 換 collection 與檔名）
   - 改主鍵名（RAGSQL.md 寫 furniture_id、實作寫 item_id —— 靠 metadata.id_key 宣告）
   - 改排序權重（結果順序變動，需通知使用端）
```

> **已知契約分歧（必須靠 `id_key` 宣告，不可默默改名）**：
> `json_adjustment/RAGSQL.md` 的範例用 `furniture_id`，
> `embed_v3.py` 實際寫出的是 `item_id`，並在 `embedding_metadata.json` 以
> `"id_key": "item_id"` 明示。任何一端要改名，必須兩份文件同時改。

## 實作範例

### Python（structured outputs schema — `query_parser.py`）

```python
def nullable(inner: dict) -> dict:
    """可為 null 的欄位；直接寫 {"type": ["string","null"], "enum": [...]} 會 400。"""
    return {"anyOf": [inner, {"type": "null"}]}


def build_schema(style_keys: list, group_keys: list) -> dict:
    item = {
        "type": "object",
        "properties": {
            "item_id": {"type": "string", "description": "英文 slug，如 main_sofa"},
            "label_zh": {"type": "string", "description": "顯示用中文，如「主沙發」"},
            "category_group": nullable({"type": "string", "enum": group_keys}),
            "quantity": {"type": "integer", "description": "件數，預設 1"},
            "priority": {"type": "string", "enum": ["must_have", "nice_to_have"]},
            "semantic_query": {"type": "string", "description": "embedded_text 句式描述"},
            "styles": {"type": "array", "items": {"type": "string", "enum": style_keys}},
            "price_max": nullable({"type": "integer"}),
        },
        # API 限制：所有 object 必須 additionalProperties=false，
        # 且不支援 maxItems / minLength —— 數量上限在 prompt 講、程式端再裁切
        "required": ["item_id", "label_zh", "category_group", "quantity",
                     "priority", "semantic_query", "styles", "price_max"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item}},
        "required": ["items"],
        "additionalProperties": False,
    }
```

### Python（檢索契約 — `retriever.py`）

```python
def search_item(item: dict, parsed: dict, allocated: dict, data: dict,
                top_k: int = FINAL_TOP_K) -> dict:
    """單一品項檢索。回傳型別固定，命中 0 筆也回同一個 shape。"""
    where = build_where(item, parsed, allocated, data)
    if where is None:
        return {"item": item, "where": None, "results": [], "relaxed": False}

    hits = query_collection(query_texts=[item["semantic_query"]],
                            n_results=VEC_TOP_K, where=where,
                            include=["metadatas", "distances"])
    if not hits["ids"][0]:
        return {"item": item, "where": where, "results": [], "relaxed": False}

    # rerank 分數已是 0–1（CrossEncoder 內建 sigmoid），不可再套一次
    ranked = rank(hits, item, parsed, data)
    return {"item": item, "where": where, "results": ranked[: top_k * 3], "relaxed": False}
```

### Python（交付檔寫出 — `embed_v3.py`）

```python
with (EXPORT_DIR / EMBEDDINGS_FILE).open("w", encoding="utf-8") as fh:
    for item, vec in zip(items, vectors):
        if vec is None:
            failures.append({"item_id": item["id"], "error_type": "model_error"})
            continue
        if len(vec) != DIMENSION:
            failures.append({"item_id": item["id"], "error_type": "invalid_dimension",
                             "expected_dimension": DIMENSION,
                             "actual_dimension": int(len(vec))})
            continue
        fh.write(json.dumps({
            "item_id": item["id"],
            "embedded_text": item["embedded_text"],
            "text_hash": item["text_hash"],              # 冪等鍵
            "embedding_model": MODEL_NAME,
            "embedding_dimension": DIMENSION,
            "embedding": [round(float(x), 6) for x in vec],
            "embedded_at": now,
            "text_format_version": item["text_format_version"],
            "source_schema_version": src["schema_version"],
            "normalized": True,
        }, ensure_ascii=False) + "\n")
```

## 契約檢查清單

改動任何介面或交付檔前逐條確認：

- [ ] 資料鍵遵循命名慣例（snake_case、名詞、不縮寫、無 camelCase 混入）
- [ ] 操作語意正確（唯讀函式不寫檔；寫檔函式標明是否冪等）
- [ ] 結果狀態明確（`relaxed` / `needs_clarification` / `error_type` 都有值可判斷）
- [ ] 輸入以 schema 驗證（structured outputs schema；可為 null 的 enum 用 `anyOf`）
- [ ] 失敗逐筆記錄到 `embedding_failures.jsonl`，不因單筆中斷整批
- [ ] 截斷階梯有明示（`meta.truncated`、`vec_top_k` / `final_top_k` 寫進回傳）
- [ ] 金鑰只從環境變數或 `.anthropic_key` 讀，錯誤訊息不含金鑰片段
- [ ] 批次工作先跑 `--limit` / `--dry-run` / `--compare` 小樣本再全量（成本控制）
- [ ] 回傳不外洩內部細節（不把 traceback 或絕對路徑塞進 UI HTML）
- [ ] 與既有介面命名一致（`item_id` 對 `item_id`，不新造同義鍵）
- [ ] 版本欄位已更新（`text_format_version` / `source_schema_version` / collection 名）
- [ ] SSOT 文件已同步（`docs/query_parser_spec.md`、`docs/RAG檢索系統說明.md`、
      `json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md`、`rag_pipeline/README.md`）
