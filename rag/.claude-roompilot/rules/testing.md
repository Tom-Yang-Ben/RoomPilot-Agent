# 測試要求

> **現況：本專案目前無正式測試套件（尚未建置）。**
> 預設建議框架為 **pytest**（`.venv-rag/bin/python -m pytest`），測試置於 `tests/`。
> 在套件建立前，以下述「手動驗證替代」欄位執行；套件建立後改跑 pytest。

## 最低覆蓋率: 80%

必要測試類型（四類，對應本專案）：

1. **解析器 schema 測試** — `query_parser.parse_query()` 輸出必須符合 structured outputs schema；
   style／group 只能是受控詞彙；可為 null 的 enum 走 `anyOf`
   手動替代：`.venv-rag/bin/python rag_pipeline/query_parser.py "<需求>"`
2. **檢索排序測試** — `build_where()` 硬過濾正確、`style_score`／`mood_score` 邊界值、
   排序公式 `0.60/0.20/0.10/0.10` 加總與 `FINAL_TOP_K=8` 去重收斂
   手動替代：`.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"`
3. **資料加工測試** — `build_rag_v3.py` 只增不覆寫（原欄位整份保留）、`text_hash` 穩定、
   `chroma_metadata` 欄位齊全且不含 `rag_indexable`
   手動替代：`python3 json_adjustment/build_rag_v3.py --dry-run`
4. **端到端 CLI 測試** — 自然語言查詢 → 解析 → 檢索 → 回傳 8 筆卡片資料的完整流程
   手動替代：`.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50` 建小索引後跑 retriever

每類至少涵蓋：正常輸入、邊界值、無效輸入、業務規則（六風格相容矩陣、硬過濾 vs 軟加權界線）。

## 測試驅動開發（強制）

1. 先寫測試 (RED)
2. 執行測試 - 應該失敗
3. 寫最小實作 (GREEN)
4. 執行測試 - 應該通過
5. 重構 (IMPROVE)
6. 驗證覆蓋率 (80%+)

## 測試失敗排除

1. 載入 sunnydata-testing skill
2. 檢查測試隔離（勿共用同一個 `chroma_db/`；測試用獨立 collection 或 `--limit` 小索引）
3. 驗證 mock 正確性（Haiku 呼叫與模型載入應 mock，測試不得真的燒額度或載 4.6 GB 權重）
4. 修實作而非測試（除非測試有誤）
