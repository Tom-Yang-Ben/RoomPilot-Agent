---
description: 強制執行測試驅動開發工作流。先定義契約、先產生 pytest 測試、再實作最小程式碼。確保 80%+ 覆蓋率。
---

# TDD 指令

此指令呼叫 **tdd-guide** agent 來強制執行測試驅動開發方法論。

> ⚠️ **本專案 pytest 尚未建置** — RoomPilot 目前沒有任何正式測試套件、沒有 `tests/`、
> 沒有 `pytest.ini`／`pyproject.toml` 測試設定。
> 因此本指令的**第一步永遠是建立測試骨架**（見下方「步驟 0」），
> 之後才進入標準 RED → GREEN → REFACTOR 循環。

## 步驟 0：建立測試骨架（首次執行必做）

```bash
PY=.venv-rag/bin/python

$PY -m pip install pytest pytest-cov      # 尚未安裝
mkdir -p tests
```

建議的最小骨架（依 PROJECT_BRIEF 的模組邊界切分）：

| 檔案 | 覆蓋對象 | 備註 |
| :--- | :--- | :--- |
| `tests/conftest.py` | 共用 fixture：載入 `taxonomy_v2.json`、`category_groups.json`、`furniture_enriched_v3.json` | 資料檔大，用 session scope 只讀一次 |
| `tests/test_query_parser.py` | `rag_pipeline/query_parser.py` 的 schema 組裝、受控詞彙、`nullable()` | Haiku 呼叫要 mock，**不可**在單元測試燒額度 |
| `tests/test_retriever_where.py` | `build_where()` 硬過濾條件組裝 | 直接斷言 dict，不碰 Chroma |
| `tests/test_retriever_score.py` | `style_score()` / `mood_score()` / 加權公式 | 純函式，最好測 |
| `tests/test_embed_v3.py` | `embedded_text` 組裝與 `text_hash` 穩定性 | 不跑真的 embedding |
| `tests/test_data_integrity.py` | v3 筆數、`rag_indexable`、`chroma_metadata` 欄位完整性 | 與 `/verify` 的資料檔完整性重疊，可共用 |

執行方式：

```bash
$PY -m pytest tests/ -v
$PY -m pytest tests/ --cov=rag_pipeline --cov-report=term-missing
```

## 功能說明

1. **建立介面** - 先定義函式簽章與回傳 dict 的欄位契約（本專案無 TypeScript，契約寫在 docstring + `docs/query_parser_spec.md`）
2. **先產生測試** - 撰寫失敗的 pytest 測試 (RED)
3. **實作最小程式碼** - 只寫足以通過的 Python 程式碼 (GREEN)
4. **重構** - 在測試保持綠燈的情況下改善程式碼 (REFACTOR)
5. **驗證覆蓋率** - 確保 80%+ 測試覆蓋率（`pytest --cov=rag_pipeline`）

## 使用時機

- 實作新功能（新增受控詞彙、新增檢索群組）
- 新增函式/模組（例如新的 `score_*` 加權項）
- 修復 bug（先寫重現 bug 的測試，例如某查詢命中 0 筆）
- 重構現有程式碼（`retriever.py` 的長函式拆分）
- 建構關鍵商業邏輯（硬過濾條件、排序公式、預算分配）

## TDD 循環

```
RED -> GREEN -> REFACTOR -> REPEAT

RED:      寫一個失敗測試
GREEN:    寫最小程式碼讓測試通過
REFACTOR: 改善程式碼，保持測試通過
REPEAT:   下一個功能/場景
```

## 最佳實踐

**應該做:**
- 在任何實作之前先寫測試
- 執行 `$PY -m pytest` 確認失敗後再實作
- 寫最小程式碼讓測試通過
- 只在測試綠燈後才重構
- 加入邊界情況和錯誤場景（空查詢、無預算、尺寸缺值、命中 0 筆）
- 關鍵程式碼目標 100% 覆蓋率
- **mock Anthropic client 與 bge-m3／reranker**：單元測試不得連網、不得載入 4.6 GB 模型

**不應該做:**
- 先寫實作再寫測試
- 跳過每次變更後的測試執行
- 一次寫太多程式碼
- 忽略失敗的測試
- 測試實作細節（應測試行為，例如「侘寂查詢應回傳 japanese 主導」而非「呼叫了幾次 `query_collection`」）
- mock 所有東西（純函式如 `style_score` 直接測真的）

## 覆蓋率要求

- **80% 最低**適用於所有程式碼
- **100% 要求**適用於：`build_where()` 硬過濾條件、`allocate_budget()` 價格分配、
  排序公式 `final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence`、
  `query_parser.py` 的 structured outputs schema 組裝

## RoomPilot 專屬 TDD 陷阱

寫測試時直接對「六個坑」設斷言，讓它們永遠不會回來：

| 坑 | 對應測試斷言 |
| :--- | :--- |
| `rag_indexable` 不能進 Chroma `where` | `assert "rag_indexable" not in build_where(...)` |
| rerank 分數不可再套 sigmoid | 給定 CrossEncoder 回傳 0.8，最終 rerank 分量必須仍是 0.8 |
| 可為 null 的 enum 要用 `anyOf` | schema 走訪，斷言沒有任何 `{"type": ["string","null"]}` |
| `HF_HUB_OFFLINE` 不可移除 | 匯入模組後 `assert os.environ["HF_HUB_OFFLINE"] == "1"` |
| 尺寸是硬過濾、LLM 不得推測 | 查詢未提尺寸時，`build_where` 不得出現 `width_cm` / `depth_cm` / `height_cm` |
| reranker 不可換成 ms-marco | `assert RERANK_MODEL == "BAAI/bge-reranker-v2-m3"` |

## 與其他指令的搭配

- 先用 `/plan` 了解要建構什麼
- 用 `/tdd` 以測試驅動方式實作
- 如有匯入／資料載入錯誤用 `/build-fix`
- 用 `/review-code` 審查實作
- 用 `/verify` 驗證覆蓋率與檢索冒煙
