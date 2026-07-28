# 通用模式

本檔記錄 RoomPilot 實際在用的模式。新功能一律沿用，要偏離必須先在 `docs/` 留下理由。

## 既有實作優先策略

實作新功能時：
1. 先在專案內找既有實作（`rag_pipeline/`、`json_adjustment/`、`vlm_annotation/` 常有可複製的骨架）
2. 平行評估選項（正確性、對現行索引的相容性、相關性）
3. 以最佳匹配作為基礎（例如新批次腳本直接抄 `reclassify_styles.py` 的續跑骨架）
4. 在成熟結構中迭代，不另起爐灶

## 檢索管線分層

Advanced RAG 固定八段，任一段只做自己的事，不得跨層取捷徑：

Query Understanding → Query Rewriting（同一次 Haiku 呼叫）→ Metadata Filtering（Chroma `where`）→
Vector Retrieval（bge-m3，`VEC_TOP_K=50`）→ Re-ranking（`RERANK_TOP_K=20`／配件 `RERANK_TOP_K_LIGHT=12`）→
Budget Allocation（中位價比例分配）→ Set Composition（主導風格收斂、去重）→ Result Presenter（`FINAL_TOP_K=8`）

- 解析層只吐受控詞彙，不碰 Chroma
- 檢索層只讀 parsed dict，不再呼叫 LLM
- 呈現層只排版，不改分數

## 硬過濾 vs 軟加權界線

界線是規格，不是實作細節，改動前先讀 `docs/RAG檢索系統說明.md`：

| 欄位 | 處理方式 | 位置 |
| :--- | :--- | :--- |
| 房型／類別／價格／尺寸 | **硬過濾** | `build_where()` 組 Chroma `where` |
| 風格／氛圍 | **軟加權** | `style_score()` / `mood_score()` 進排序公式 |
| 顏色／材質 | **只進 `semantic_query`**，不過濾 | 向量檢索文字 |

排序公式（`rag_pipeline/retriever.py:47`）：`final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence`

- 尺寸是硬過濾，LLM 不得用常識推測——猜錯直接濾掉正確結果
- `rag_indexable` 是頂層欄位、不在 `chroma_metadata` 裡，寫進 `where` 會命中 0 筆

## 資料存取封裝

本專案的「資料庫」有兩個：ChromaDB collection `furniture_v3` 與 JSON 資料集
`rag_dataset/furniture_enriched_v3.json`。**兩者的存取一律集中在一致介面後**，
不得在 `retriever.py` / `app.py` / 批次腳本各自散開寫 `chromadb.PersistentClient(...)` 或 `json.loads(...)`。

現行落點（`rag_pipeline/retriever.py`）：

| 角色 | 實作 | 說明 |
| :--- | :--- | :--- |
| 常數 | `V3` / `GROUPS` / `TAXONOMY` / `CHROMA_DIR` / `COLLECTION`（`retriever.py:33-37`） | **唯一**的路徑與 collection 名稱來源 |
| JSON 存取 | `load_data()`（`@lru_cache(maxsize=1)`） | 讀 v3 + 群組表 + 詞表，組成 `items` 索引與價格分佈 |
| 向量庫存取 | `load_collection()` | `PersistentClient(CHROMA_DIR).get_collection(COLLECTION)`，單例 |
| 模型 | `load_models()` | bge-m3 + reranker，Gradio 重複查詢不重載 |

本專案的標準操作（相當於一般 Repository 的 CRUD，語意見
`output-styles/04-ddd-aggregate-spec.md` 的「4. 倉儲接口 (Repository Interface)」）：

- **依 id 取回聚合根** — `items[item_id]`，找不到回 `None`，不得丟例外中斷整批
- **依 `where` 條件查詢** — 只吃硬過濾欄位（房型／類別／價格／尺寸）；
  風格／氛圍**不進 `where`**，它們只影響排序
- **依檢索群組查詢** — 群組鍵展開成細類清單後以 `$in` 送進 `where`
- **批次 upsert** — `embed_v3.py` 整批寫入，逐筆失敗記進 `embedding_failures.jsonl` 後繼續
- **count／一致性檢查** — 建索引後確認 `furniture_v3` 筆數與資料集相符（現為 9,349 筆）

鐵律：

- **業務邏輯只依賴這層介面**，不直接碰 `chromadb` API 或檔案路徑字串
- **退版／切換資料源只改常數** —— 換回 v2 或換 collection，只動 `V3` 與 `COLLECTION`，
  不必掃全專案改字串。看到程式碼裡出現硬寫的 `"furniture_v3"` 或 `furniture_enriched_v3.json`，
  就是這條規則被破壞了
- 單例用 `@lru_cache(maxsize=1)`，不要每次查詢重開 client（16 GB 機器上模型常駐約 4.6 GB）

## 統一回傳格式

本專案有**兩種**回傳信封，用途不同，不可互換（完整規格見
`output-styles/05-api-contract-spec.md` 與 sunnydata-api-design skill 的「回傳信封變體」）：

**A. 模組間扁平回傳**（`query_parser.parse_query()` → `retriever.retrieve()` → `app.py`）

- 成功就直接回**資料 dict**，不包一層 `{"success": ..., "data": ...}`
- 「非正常但非錯誤」的狀態用**旗標欄位**表達，不丟例外：
  - `relaxed`（bool）— 硬過濾命中太少而放寬條件，UI 需據此提示使用者
  - `needs_clarification`（bool）+ `clarify_question` / `clarify_options` — 需求太模糊，UI 出追問按鈕
- 命中 0 筆是**合法結果**（回空 `results` + 旗標），不是錯誤

**B. `rag_export/` 對外完整信封**（交給 SQL 端的交付檔，`embed_v3.py` 產出）

| 檔案 | 角色 |
| :--- | :--- |
| `furniture_embeddings_bge_m3.jsonl` | 資料酬載（逐行一筆） |
| `embedding_metadata.json` | meta：模型／維度／`normalized`／數量／`generated_at` |
| `embedding_validation_report.json` | 驗證匯總（筆數、維度、失敗統計） |
| `embedding_failures.jsonl` | **失敗清單分檔**，逐筆 `item_id` + `error_type`（目前為 0 bytes = 全數成功） |

- 對外交付一律走 A**以外**的完整信封：**資料 + meta + 失敗清單分檔**，SQL 端不必猜任何欄位
- **失敗清單就是本專案的 error response**：批次工作絕不因單筆失敗而全滅，逐筆記錄後繼續
- 欄位規格以 `json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md` 為準（文件為契約）

## 只增不覆寫的資料加工

所有 `json_adjustment/` 加工腳本共用一致介面：

- 讀入 → `new = dict(item)` 建新物件 → 只新增欄位，原欄位整份保留
- 新版本另存新檔（`v1` → `v2` → `v3`），不就地改寫上游
- 先跑 `--dry-run` 看統計，確認後才落檔
- 易於回溯與比對，任何一版都能重跑重現

```bash
python3 json_adjustment/build_rag_v3.py --dry-run   # v2→v3 加工（先看統計）
```

## text_hash 增量重算

`embed_v3.py` 用 `text_hash` 判定哪些品項需要重算向量：

- 全量：`.venv-rag/bin/python rag_pipeline/embed_v3.py`（約 27 分鐘）
- 增量：`--only-changed`，比對 `rag_export/` 既有 `text_hash`，未變者沿用舊向量（646 筆約 1.5 分鐘）
- 冒煙：`--limit 50`
- 因為 hash 綁 embedded_text，不會出現「demo 正常但 SQL 端結果不同」

## Taxonomy 受控詞彙

`vlm_annotation/taxonomy_v2.json` 是風格詞彙的唯一事實來源：

- 六風格：`scandinavian` / `japanese` / `modern_minimal` / `cream` / `industrial` / `american`
- 內含 6×6 `style_compat` 相容矩陣（japanese↔scandinavian 0.9、cream↔american 0.7）
- 18 張色卡、24 個氛圍詞、9 種房型、64 細類 →`category_groups.json` 的 19 檢索群組
- 解析器 schema 的 enum 由詞表動態生成，**不得在程式碼硬寫字串**；新增風格＝改詞表＋重建索引

## 可續跑批次（resumable jsonl）

會燒額度的批次工作（VLM 標註、風格判定）一律可中斷續跑：

- 進度檔用 append-only jsonl（`vlm_annotation/annotations.jsonl`、`render_meta.jsonl`）
- 啟動時先 `load_done_ids()`，已完成的 id 自動跳過
- 提供 `--limit` 先跑小批驗證，再放全量
- 每筆寫完立刻 flush，中斷不丟進度

完整檢索介面與回傳結構規範請載入 sunnydata-api-design skill。
