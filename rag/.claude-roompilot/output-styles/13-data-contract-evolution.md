---
name: 13-data-contract-evolution
description: "RoomPilot 資料契約演進 - v1→v2→v3 世代、只增不覆寫、text_hash 漂移偵測、taxonomy v1→v2 遷移"
stage: "Design & Operations"
template_ref: "05_architecture_and_design_document.md"
---

# 指令 (你是資料架構師)

輸出 RoomPilot 資料 Schema 與演進規則,提供稽核欄位、漂移告警與測試資料集生成指南。確保資料模型的演進不破壞現有消費者——本專案的消費者有三個:
**Chroma 索引端**(`rag_pipeline/embed_v3.py` → collection `furniture_v3`)、
**檢索端**(`rag_pipeline/retriever.py` 讀 `chroma_metadata` 做硬過濾與加權)、
**SQL 交付端**(`rag_export/` 四個檔,由另一組匯入其資料庫)。

RoomPilot 的資料契約沒有資料庫遷移工具,**世代靠檔案演進**:
`rag_dataset/furniture_enriched_v1.json` → `v2.json` → `v3.json`(現役,9,349 筆)。
本專案**尚未 git init**,因此「舊版本可回溯」靠的是**保留舊世代檔案本身**,不是 git 歷史。

## 交付結構

### 1. Schema 定義與版本

**範例: RoomPilot furniture item Schema v3.0+rag_ready**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FurnitureItem",
  "type": "object",
  "version": "3.0+rag_ready",
  "required": ["id", "name_zh", "category_final", "style_primary",
               "embedded_text", "text_hash", "rag_indexable", "chroma_metadata"],
  "properties": {
    "id":             {"type": "string", "pattern": "^(abo|jp)-[a-z0-9-]+$"},
    "name_zh":        {"type": "string", "minLength": 1},
    "category_final": {"type": "string", "description": "64 細類之一;衝突時取 suggested_category"},
    "style_primary":  {"enum": ["scandinavian", "japanese", "modern_minimal",
                                "cream", "industrial", "american"]},
    "style_secondary":{"enum": ["scandinavian", "japanese", "modern_minimal",
                                "cream", "industrial", "american"]},
    "style_primary_v1": {"type": "string", "description": "taxonomy v1 的 12 風格值,回溯用"},
    "style_confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "price_twd":      {"type": "number", "minimum": 0},
    "embedded_text":  {"type": "string", "description": "embedding 的唯一輸入來源"},
    "text_hash":      {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "text_format_version": {"type": "string", "default": "v1"},
    "rag_indexable":  {"type": "boolean", "description": "頂層欄位,不在 chroma_metadata 內"},
    "chroma_metadata":{"type": "object", "description": "已攤平為純量,可直接餵 collection.add()"}
  }
}
```

**資料集層級的版本欄位**(`furniture_enriched_v3.json` 頂層):

| 欄位 | 現值 | 意義 |
| :--- | :--- | :--- |
| `schema` | `roompilot` | 契約家族名 |
| `schema_version` | `3.0+rag_ready` | 本世代版本 |
| `source_schema_version` | `2.0+enriched_v1+vlm_annotated+...` | 上一世代版本(可追溯) |
| `source_file` | `rag_dataset/furniture_enriched_v2.json` | 來源檔 |
| `taxonomy_version` | `v1-draft` | 詞表版本(⚠️ 見第 6 節的已知落差) |
| `text_format_version` | `v1` | `embedded_text` 組合規格版本 |
| `count` / `indexable_count` | 9,349 / 9,349 | 實際筆數 |
| `source_item_count` | 9,350 | 上游筆數(差 1 = 被排除者) |

### 2. 演進策略

**向後相容變更** (可直接跑 `--only-changed` 增量重建):
- ✅ 新增可選欄位 (帶 default,如 `style_palette_hex`)
- ✅ 放寬驗證規則 (如 `price_twd` 允許 null)
- ✅ 新增 enum 值 (如 `mood_vocab` 從 24 個加到 26 個)
- ✅ 新增 `chroma_metadata` 純量鍵(Chroma 允許 metadata 不齊)

**破壞性變更** (需開新世代檔 `v4.json` + 全量重建索引):
- ❌ 刪除欄位 (下游 `retriever.py` 的 `where` 會直接命中 0 筆)
- ❌ 修改欄位類型 (如 `price_twd` 從 number 改字串)
- ❌ 收緊驗證規則 (如 `style_primary` 從 6 值縮到 4 值)
- ❌ 刪除 enum 值 (舊資料會變成非法值)
- ❌ 變更 `embedded_text` 組合規格 → 必須同步升 `text_format_version` 並**全量重算向量**

**判斷口訣**:動到 `embedded_text` 的組成 = 全量;只動 `chroma_metadata` = 增量;
只動展示欄位(如 `style_reason`) = 不必重建索引。

### 3. 只增不覆寫(世代鐵律)

v3 的 notes 第一條就是契約:**「v3 只新增衍生欄位,v2 既有欄位原封不動保留。」**

```
v1  原始 catalog + 初版 enrich
     │  (VLM 標註:style/pattern/mood/description/confidence)
     ▼
v2  + vlm_annotated + abo_from_folder_render + full_render_vlm + export_supplemented
     │  (build_rag_v3.py:六風格重判、category_final、embedded_text、text_hash、chroma_metadata)
     ▼
v3  3.0+rag_ready —— 現役,9,349 筆
```

規則:

1. **舊檔不刪** — `v1.json` / `v2.json` 留在 `rag_dataset/`,是回溯與比對的唯一依據(專案尚未 git init)
2. **同名欄位不就地改語意** — 要換語意就開新欄位名(如 `style_primary` 改判後,舊值搬到 `style_primary_v1`)
3. **加工腳本一律先 `--dry-run`** — `python3 json_adjustment/build_rag_v3.py --dry-run` 先看統計再落檔
4. **就地更新必先備份** — `vlm_annotation/annotate_full.py merge` 會寫 `furniture_enriched_v2.bak_before_full.json`
5. **`schema_version` 用累加後綴** — `2.0+enriched_v1+vlm_annotated+full_render_vlm`,一眼看出經過哪些加工

### 4. `rag_indexable` 排除規則

`rag_indexable` 是**頂層布林欄位**,決定該筆是否進索引。

| 情境 | `rag_indexable` | 結果 |
| :--- | :--- | :--- |
| 正常品項 | `true` | 進 Chroma + 進 `rag_export` 向量檔 |
| `is_active=False` | `false` | 從 v3 `items` 排除,明細寫入 `excluded_items` |
| 無可用文本(`embedded_text` 為空) | `false` | 同上,並記入 `embedding_failures.jsonl` |

`embed_v3.py` 的篩選:

```python
items   = [i for i in src["items"] if i.get("rag_indexable")]
skipped = [i for i in src["items"] if not i.get("rag_indexable")]
# skipped 會以 error_message="rag_indexable=false（is_active=False 或無文本）"
# 寫入 rag_export/embedding_failures.jsonl，交給 SQL 端對帳
```

**⚠️ 契約第一坑**:`rag_indexable` **不能寫進 Chroma `where`**。
它是頂層欄位、不在 `chroma_metadata` 裡,寫了會命中 0 筆。
語意上「不可索引的資料根本不在 collection 裡」,所以查詢端**不需要也不可以**過濾它。

現況:`source_item_count=9350`、`indexable_count=9349`、`excluded_items` 1 筆
(`jp-armchairs-01-underl-tta-vacuum-flask-black-1-2-l`,reason `is_active=False`)。
v1/v2 仍完整保留這筆,供回溯。

### 5. `text_hash` 相容性與增量重算

`text_hash = sha256(embedded_text)`,是整條資料契約的**變更偵測主鍵**。

**相容性承諾**:

- 同一 `text_format_version` 內,`text_hash` 相同 ⇒ 向量可直接沿用,不必重算
- `text_format_version` 一改(欄位順序、分隔符、納入欄位變動),**所有 hash 全部失效**,必須全量重跑
- `rag_export/furniture_embeddings_bge_m3.jsonl` 每列都帶 `text_hash`,SQL 端據此判斷「文字有沒有被改過」

**增量流程**:

```bash
PY=.venv-rag/bin/python

$PY rag_pipeline/embed_v3.py --limit 50      # 冒煙:先確認 50 筆能跑通
$PY rag_pipeline/embed_v3.py --only-changed  # 增量:只重算 text_hash 變動者（646 筆約 1.5 分鐘）
$PY rag_pipeline/embed_v3.py                 # 全量:約 27 分鐘
```

`--only-changed` 會讀既有 `rag_export/furniture_embeddings_bge_m3.jsonl`
(找不到時相容讀取舊檔名 `furniture_embeddings.jsonl`),
比對 `text_hash` 不同者才重算,其餘沿用舊向量。

**同批寫兩邊的保證**:`embed_v3.py` 一次算向量、同時寫 Chroma 與 `rag_export/`,
保證「Chroma 內的向量」與「交給 SQL 的 jsonl」是同一批、同一個 `text_hash`,
不會出現「Demo 正常但 SQL 端結果不同」。

### 6. taxonomy v1(12 風格)→ v2(6 風格)遷移

風格詞表本身也是資料契約,且是**破壞性收斂**:12 → 6。

| | taxonomy v1 (`v1-draft`) | taxonomy v2 (`v2-six-style`) |
| :--- | :--- | :--- |
| 風格數 | 12 | 6 |
| 相容矩陣 | 12×12 | 6×6 |
| 詞表檔 | `vlm_annotation/taxonomy_v1.json` | `vlm_annotation/taxonomy_v2.json` |
| 色卡 | 無 | 18 張(每風格 3 張,如 japanese_1「侘寂自然」) |

v2 以 `supersedes: "v1-draft"` 明示取代關係,並用 `legacy_style_hint` 定義映射:

| v1 風格 | → v2 | v1 風格 | → v2 |
| :--- | :--- | :--- | :--- |
| `nordic` | `scandinavian` | `mid_century` | **null(需重判)** |
| `japandi` | `japanese` | `scandi_luxe` | **null(需重判)** |
| `minimalist` | `modern_minimal` | `french_country` | **null(需重判)** |
| `modern` | `modern_minimal` | `rustic` | **null(需重判)** |
| `contemporary` | `modern_minimal` | `boho` | **null(需重判)** |
| `industrial` | `industrial` | | |
| `american_classic` | `american` | | |

**5 個 null 是重點**:它們沒有安全的機械映射,必須交給 LLM 依 v2 定義重新判定
(`json_adjustment/reclassify_styles.py`,本機 Ollama `qwen3:8b`,可 `--provider anthropic` 切 `claude-haiku-4-5`)。

**回溯欄位承諾**:重判時舊值不覆寫,而是搬進 `style_primary_v1` / `style_secondary_v1`,
並同步寫進 `chroma_metadata.style_primary_v1`(空值以 `""` 表示,Chroma 不吃 null)。
因此任何時候都能回答「這件家具在 12 風格時代被判成什麼」。

**遷移驗收**:

```bash
$PY json_adjustment/reclassify_styles.py --compare 30   # 抽 30 筆比對一致率
```

輸出會列出 (v1 值, v2 值) 的分布 Top 12,人工確認 `rustic → american`、
`french_country → cream` 這類跨界判定是否合理。

### 7. 稽核欄位

本專案沒有資料表,稽核欄位落在**資料集頂層**與**每筆 item**兩層(對應原本 DDL 的五個稽核欄位):

```python
# 資料集頂層（furniture_enriched_v3.json）
DATASET_AUDIT_FIELDS = {
    "generated_at":          "2026-07-27T22:34:45+08:00",              # 何時產生（等同 created_at）
    "source_file":           "rag_dataset/furniture_enriched_v2.json",  # 從何而來（等同 created_by）
    "source_schema_version": "2.0+enriched_v1+vlm_annotated+...",       # 上游版本（等同 updated_by）
    "schema_version":        "3.0+rag_ready",                           # 本世代版本（等同 version）
    "taxonomy_version":      "v1-draft",                                # 詞表版本
}

# 每筆 item
ITEM_AUDIT_FIELDS = {
    "text_hash":           "b4ecf0a1...",         # 內容指紋，變更偵測用
    "text_format_version": "v1",                  # 文本組合規格
    "style_source":        "text_reclassify_v2",  # 風格判定來源
    "desc_source":         "glb_render",          # 描述來源：glb_render / text_inference（灰模）
    "rag_text_source":     "original",            # rag_text 來源
}
```

**⚠️ 已知落差(需記入 ADR)**:v3 頂層寫 `taxonomy_version: "v1-draft"`,
但風格值實際已是 v2 六風格(`style_source: text_reclassify_v2`)。
下一次重建 v3 時應修正為 `v2-six-style`;在修正前,**以 `style_source` 為準,勿信 `taxonomy_version`**。

### 8. Schema 註冊與驗證

本專案**沒有 Schema Registry**(無 Confluent、無外部服務)。
取而代之的「註冊表」是 `rag_export/` 裡由 `embed_v3.py` 自動產生的兩個檔:

**`rag_export/embedding_metadata.json`**(規格檔,SQL 端據此建欄位與索引):

```json
{
  "dataset_name": "ABO + IKEA furniture catalog ... + legacy product links",
  "source_file": "rag_dataset/furniture_enriched_v3.json",
  "source_schema_version": "3.0+rag_ready",
  "source_item_count": 9349,
  "embedded_count": 9349,
  "reused_vector_count": 9349,
  "failed_count": 0,
  "embedding_model": "BAAI/bge-m3",
  "embedding_dimension": 1024,
  "distance_metric": "cosine",
  "normalized": true,
  "text_format_version": "v1",
  "text_fields": ["name_zh", "category_final", "object_type_zh", "colors", "materials",
                  "room_types", "style_primary", "style_secondary", "style_card",
                  "mood_tags", "pattern", "shape_tags", "description",
                  "features", "search_keywords"],
  "id_key": "item_id",
  "device": "mps",
  "generated_at": "2026-07-28T02:17:09+08:00"
}
```

**`rag_export/embedding_validation_report.json`**(驗證報告,交付前必看):

```json
{
  "total_source_items": 9349,
  "total_embedding_records": 9349,
  "unique_furniture_ids": 9349,
  "duplicate_furniture_ids": 0,
  "missing_furniture_ids": 0,
  "invalid_vector_count": 0,
  "null_vector_count": 0,
  "dimension_distribution": {"1024": 9349},
  "model_distribution": {"BAAI/bge-m3": 9349},
  "coverage_percent": 100.0
}
```

驗收門檻:`coverage_percent == 100.0`、`duplicate_furniture_ids == 0`、
`dimension_distribution` 只有一個鍵 `"1024"`、`model_distribution` 只有一個模型。

### 9. `rag_export` 對 SQL 端的相容承諾

RAG 端交付 4 個檔給 SQL 端(規格見 `json_adjustment/RAGSQL.md`、`i_need_rag.md`):

| 檔案 | 內容 | 承諾 |
| :--- | :--- | :--- |
| `furniture_embeddings_bge_m3.jsonl` | 一列一件家具的向量 | `furniture_id` 對得上主表 `id`;1024 維、normalized |
| `embedding_metadata.json` | 整批規格 | 一定含 `embedding_model` / `embedding_dimension` / `distance_metric` / `normalized` |
| `embedding_failures.jsonl` | 失敗與排除清單 | 每列帶 `error_message`,可逐筆對帳 |
| `furniture_official_catagory.json` | 官方分類主檔 | 類別詞彙與 `category_final` 同源 |

**必要欄位**(jsonl 每列):`furniture_id`、`embedded_text`、`text_hash`、
`embedding_model`、`embedding_dimension`、`embedding`。
**建議附加**:`embedded_at`、`text_format_version`、`source_schema_version`、`normalized`。

**相容承諾條款**:

1. **不改欄位名** — 已交付的六個必要欄位名視為凍結;要加欄位只能新增,不能改名
2. **不改 id 語意** — `furniture_id` 永遠等於 v3 的 `id`(`abo-*` / `jp-*` slug),不重編號
3. **維度與距離不默默變** — 換 embedding 模型 = 破壞性變更,必須先通知 SQL 端並升 `text_format_version`
4. **JSONL 不改成 CSV** — 1024 個浮點數放 CSV 會踩逗號與引號解析、單欄過長、型別轉換與定位錯誤列的四個坑
5. **失敗清單一定給** — 即使 `failed_count=0` 也交付空的 `embedding_failures.jsonl`,讓對帳流程恆定

### 10. 漂移偵測

定期比對「現役 v3 檔」與「已交付 / 已索引的內容」,及時發現未記錄的變更。

| 漂移類型 | 偵測方式 | 處置 |
| :--- | :--- | :--- |
| 文本漂移 | `text_hash` 與 `rag_export` jsonl 不一致 | `--only-changed` 增量重算 |
| 筆數漂移 | Chroma `collection.count()` ≠ `indexable_count` | 全量重建 |
| 維度漂移 | `dimension_distribution` 出現非 1024 的鍵 | 立刻停,查是否誤換模型 |
| 重複 ID | `duplicate_furniture_ids > 0` | 回頭查 v2→v3 加工是否重複 merge |
| 詞表漂移 | `style_primary` 出現不在六風格內的值 | 依 `legacy_style_hint` 或重判 |
| 版本標示漂移 | `taxonomy_version` 與 `style_source` 對不上 | 修正頂層欄位並記 ADR |

**冒煙檢查腳本**(可直接貼進終端機):

```bash
PY=.venv-rag/bin/python

$PY - <<'PYEOF'
import json, collections
d = json.load(open("rag_dataset/furniture_enriched_v3.json"))
items = d["items"]
ids = [i["id"] for i in items]
six = {"scandinavian","japanese","modern_minimal","cream","industrial","american"}
print("筆數        :", len(items), "/ 宣告", d["indexable_count"])
print("重複 ID     :", len(ids) - len(set(ids)))
print("非法風格值  :", {s for s in (i.get("style_primary") for i in items) if s not in six})
print("缺 text_hash:", sum(1 for i in items if not i.get("text_hash")))
print("非 indexable:", sum(1 for i in items if not i.get("rag_indexable")))
print("風格分布    :", collections.Counter(i["style_primary"] for i in items).most_common())
PYEOF
```

### 11. 測試資料集生成指南

本專案**尚無 pytest 套件(尚未建置)**。導入時建議這樣造測試資料:

- **不要複製 49.9 MB 的 v3 全檔** — 抽 20–50 筆做 fixture,務必涵蓋六風格各至少 1 筆
- **必含邊界樣本**:`rag_indexable=false` 1 筆、`category_conflict=true` 1 筆、
  `price_is_estimated=true` 1 筆、`desc_source=text_inference`(灰模)1 筆、`style_primary_v1` 為 null 對應風格 1 筆
- **`text_hash` 要真的算** — fixture 內的 hash 必須等於 `sha256(embedded_text)`,否則增量測試永遠假通過
- **不要在測試裡呼叫真模型** — bge-m3 載入約數 GB;用固定的假向量(維度仍為 1024)驗證管線接線

```python
# tests/conftest.py（建議樣板，尚未建置）
import hashlib, json, pytest

@pytest.fixture
def sample_item() -> dict:
    text = "名稱：測試單椅。類別：椅子。風格：日式(japanese)、北歐(scandinavian)。"
    return {
        "id": "abo-chairs-test-0001",
        "name_zh": "測試單椅",
        "category_final": "椅子",
        "style_primary": "japanese",
        "style_secondary": "scandinavian",
        "style_primary_v1": "japandi",
        "style_confidence": 0.82,
        "price_twd": 4200,
        "embedded_text": text,
        "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_format_version": "v1",
        "rag_indexable": True,
        "chroma_metadata": {"furniture_id": "abo-chairs-test-0001", "category": "椅子",
                            "style_primary": "japanese", "price_twd": 4200},
    }
```

---

**記住**: 資料契約是 RAG 端、Chroma 端與 SQL 端之間的重要約定,演進需謹慎,確保向後相容。
本專案沒有 migration 工具、也沒有 git 歷史可回滾——**舊世代檔案本身就是你的回退鍵**,永遠只增不覆寫。
