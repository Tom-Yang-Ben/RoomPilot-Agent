# 編碼風格

語言統一 Python 3.11，執行一律 `.venv-rag/bin/python`（專案唯一環境）。

## 不可變性 (CRITICAL)

永遠建立新物件，絕不修改既有物件：
- 用 `dict(item)` / `{**meta, ...}` / `[*items, new]` 建新物件，不對傳入的 dict 就地 `update()`
  （對照 `json_adjustment/build_rag_v3.py:316` 的 `new = dict(item)  # 只增不覆寫`）
- 不可變資料防止隱藏副作用、簡化除錯、確保批次可重跑結果一致
- 禁用可變預設參數（`def f(items=[])`），一律 `None` + 函式內建新容器

## 檔案組織

多個小檔案 > 少數大檔案：
- 200-400 行典型，800 行上限（現況 `retriever.py` 369 行、`build_rag_v3.py` 417 行，皆在範圍內）
- 依功能/領域組織，非依類型：`rag_pipeline/` 檢索管線、`json_adjustment/` 資料加工、`vlm_annotation/` 標註
- 高內聚、低耦合：解析（`query_parser.py`）／檢索（`retriever.py`）／呈現（`app.py`）不互相反向依賴

## 錯誤處理

- 每個層級明確處理錯誤：解析失敗、Chroma 查無結果、模型載入失敗要分開處理
- UI 面向使用者的友善錯誤訊息（Gradio 卡片區顯示「找不到符合條件的家具，請放寬預算或尺寸」）
- CLI／終端機記錄詳細錯誤上下文（查詢字串、parsed 結果、`where` 條件、命中筆數）
- 絕不靜默吞噬錯誤：禁止裸 `except:` 與 `except Exception: pass`

## 輸入驗證

在系統邊界驗證：
- 驗證所有使用者輸入（Gradio 輸入框與 CLI argv 的自然語言查詢：長度上限、非空、去除控制字元）
- 使用 schema-based 驗證：Haiku structured outputs 的 JSON Schema（`query_parser.py:build_schema`）
  是需求解析的唯一契約；可為 null 的 enum 必須用 `anyOf`，直接寫 type 陣列會 400
- 快速失敗，清晰錯誤訊息：受控詞彙以外的 style／group 值一律拒絕，不做模糊比對
- 永遠不信任外部資料：LLM 回傳、`furniture_enriched_v3.json` 欄位、VLM 標註都要先驗型別再用

## 命名慣例

- 模組檔案：snake_case（`query_parser.py`、`build_rag_v3.py`、`embed_v3.py`）
- 類別：PascalCase（`SentenceTransformer`、`CrossEncoder` 的自訂包裝亦同）
- 函式／變數：snake_case，動詞-名詞（`parse_query`、`build_where`、`allocate_budget`、`style_score`）
- 模組級常數：UPPER_SNAKE（`VEC_TOP_K`、`RERANK_TOP_K`、`FINAL_TOP_K`、`W_RERANK`）
- 資料檔／交付檔：snake_case + 版本後綴（`furniture_enriched_v3.json`、`taxonomy_v2.json`）
- 一律加型別註記（`def retrieve(parsed: dict, top_k: int = FINAL_TOP_K) -> dict:`）；
  避免 `Any`，容器型別要寫內層（`list[dict]`、`dict[str, float]`、`int | None`）

## 品質檢查清單

- [ ] 程式碼可讀、命名良好
- [ ] 函式 < 50 行
- [ ] 檔案 < 800 行
- [ ] 無深層巢狀 (> 4 層)
- [ ] 適當錯誤處理（無裸 `except`）
- [ ] 無硬編碼值（權重／TOP_K／路徑集中在模組頂端常數）
- [ ] 不可變模式（資料加工只增不覆寫）
- [ ] 型別註記完整，無 `Any`
