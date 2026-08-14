# Agent 架構實作報告（2026-07-31）

依 `agent-design-proposal.html`（討論定案版）落地。實作全部位於
`backend/agent/`，分層為 `skills/` 與 `tools/`（使用者要求的最低分層）加上
`subagents/`、`master.py`、`documents.py`、`llm.py`、`runtime.py`。

## 外部修改報告

**本次沒有修改 `backend/agent/` 以外的任何程式碼。**

| 檔案 | 狀態 |
|---|---|
| `backend/agent/__init__.py` | 修改（改寫 docstring、輸出新 API；不影響既有 submodule import） |
| `backend/agent/AGENTS.md` | 改寫（記錄新架構與邊界） |
| 其他全部 | 新增檔案，均在 `backend/agent/` 內（含 `tests/`） |

### room_pilot2 移植版三模組（knowledge.py / select.py / place.py）必須保留

以下活代碼經套件 `__init__` import 它們，移除 re-export 會弄壞 server
（2026-08-01 已因此壞過一次並修復）：

- `backend/server/services/layout_service.py:17`（`parse_selections`、
  `request_selections`、`placement_hints`、`resolve_placements` 等）
- `backend/server/services/scene_service.py:15`（`placement_hints`、`resolve_placements`）
- `tests/test_agent_knowledge.py`、`tests/test_agent_select.py`、`tests/test_agent_place.py`

因此三模組**原樣保留、未動一行**，且 `__init__.py` 同時輸出
room_pilot2 re-export 與新架構 API（見檔內註記）。

## 架構對應（提案 → 程式）

| 提案元素 | 程式位置 |
|---|---|
| Master state machine（HITL 暫停、修復迴圈 ≤3、改圖 ≤1、checkpoint/undo） | `master.py` |
| Furniture / Validation / Gen_Pic / Report sub-agents | `subagents/` |
| 需求整理（三分流＋家電防線）、家具（A/B 策略）、驗證（雙軌）、生圖（兩階段）、改圖（鎖定清單）、報告（PDF） | `skills/<name>/`——每個 skill 一資料夾：`SKILL.md`（宣告層，提示詞與 schema 唯一來源）＋`__init__.py`（流程層，含 deterministic fallback） |
| RAG家具、挑家具（白名單）、擺家具（engine）、讀室內架構、讀規則/需求、engine 驗證、生圖資訊整理、拿舊圖、讀文件、組版 PDF | `tools/` |
| Docs 層 blackboard（含驗證報告、鎖定清單、設計手冊等新增節點） | `documents.py`（`DocStore`，JSONB-ready） |
| OpenRouter 單一 gateway（文字＋nano banana；fallback nano banana 2） | `llm.py` |
| 生圖失敗政策：3 次 → 提示原因 → 換備援模型；失敗不消耗改圖額度 | `subagents/genpic_agent.py`（政策數字在 `MasterConfig`） |

## 邊界遵循

- 座標與合法性只來自 `backend/engine/`（`place_furniture`、
  `check_placement_with_clearance`）；LLM 只產生語意意圖與修復方案。
- RAG 只檢索排序（`SpatialRagRetriever` 包 Django `FurnitureRagService`）；
  不可用時回報可讀錯誤，不悄悄改用未驗證資料。
- 家電由 `RequirementSkill._enforce_contracts` 強制移入 appliances，
  只進生圖 context。
- 所有文字 skill 都有 deterministic fallback：無 `OPENROUTER_API_KEY`
  可跑完整流程（生圖階段以可讀原因暫停，可 retry/skip）。

## Server 整合掛點（後續工作，未在本次範圍）

- 建立 orchestrator：`from backend.agent import build_master`；
  `master.start(layout_json)` → `master.submit(payload)` → `master.undo()`。
- 保存/恢復：`master.to_dict()` / `master.restore()` 為 plain dict，可直接
  存進 `backend/server/storage/` 的 SQLite 專案狀態（`.runtime/`）。
- layout 欄位以 `backend/server/services/scene_service.room_from_payload`
  對齊（`ReadLayoutTool` 目前接受容錯的簡化房間清單；注意 payload 的
  牆/窗段為公尺、`position_cm` 為房間中心原點——轉換集中在 scene_service）。
- RAG 檢索器：`SpatialRagRetriever` 包 `backend/spatial_data/rag`。回傳形狀
  已依 `roompilot.rag.search.v1` 對齊（`flatten_rag_payload` 讀 `blocks`／
  `hits.furniture`，價格取 `price_twd`、風格取 `style_primary`），但仍未對
  真實 DB 實測；不可用時 `RagFurnitureTool` 回報可讀錯誤，選件可由呼叫端
  注入其他候選來源（如 `backend/catalog/style_db` 轉接的候選白名單）。
  `price_is_estimated`（估價旗標）目前未帶進 `CandidateItem`，報告無法區分
  估價與實際牌價。
- 設計手冊第七章為工程/預算章節的預留掛點（本分支尚無工程文件模組，
  缺價一律保留待確認、不補猜）。

## 環境變數

模型 id 全部從 `.env` 讀；哪個功能用哪顆、對應哪個變數、內建預設是什麼，
以 [`backend/model_config.py`](../model_config.py) 的 `REGISTRY` 為準（本檔不重複那張表）。
agent 側另有兩個非模型變數：

| 變數 | 用途 | 預設 |
|---|---|---|
| `OPENROUTER_API_KEY` | 文字＋生圖統一金鑰（沿用既有慣例） | 空＝離線 fallback |
| `ROOMPILOT_AGENT_LLM_TIMEOUT` | 呼叫逾時（秒） | 120 |
| `ROOMPILOT_PDF_FONT` | 手冊 PDF 中文字型路徑 | 自動找 msjh.ttc 等 |

## 2026-08-01 yen 分支遷移適配

本架構以 commit `9fbd079` 落到 `yen` 分支後，依該分支現況做了五項適配：

1. `__init__.py` 恢復 room_pilot2 re-export 並與新架構 API 並存
   （否則 `backend/server/services/` ImportError）。
2. `tools/place_furniture.py` 改為 engine 能力偵測：本分支引擎只有
   `place_furniture`／`place_furniture_batch`，adjacent／overlay 意圖降級
   free 自由擺放（座標仍全由 engine 決定，agent 不補幾何）。
3. `llm.py` 由 httpx 改 stdlib `urllib`＋`certifi`——CLAUDE.md 規定業務碼
   禁 import httpx（dev 群組 httpx2 只供 fastapi.testclient）。
4. 場景列的 `schema_version: "2.0"` 假設移除（本分支 `placed_to_dict`
   無版本欄），改由擺家具 tool 附加 `coordinate_unit: "cm"` 標記。
5. 驗證指令改用 uv（`requirements.txt` 已廢除）。

範圍註記：現行五階段產品「不做 ControlNet 圖像生成、不做自然語言換風格」，
終點是 3D 白模取景＋提案 PNG。本架構的 Gen_Pic（nano banana 生圖/改圖）
與設計手冊 PDF 屬**提案功能**，超出現行 Demo 範圍；未設定
`OPENROUTER_API_KEY` 時 Master 會在生圖階段以可讀原因暫停並可 skip，
其餘流程完整可用，不影響五階段主線。

## 驗證結果（2026-08-01，yen 分支）

```bash
uv run pytest backend/agent/tests -q   # 24 passed
uv run pytest tests/ -q                # 122 passed, 1 skipped
```

root tests 全綠（含經 `backend.agent` 套件 import 的 test_layout_api、
test_requirements_api 與 room_pilot2 三模組自身的 test_agent_*）。

## 已知限制

- PDF 為 Pillow 點陣排版（文字不可選取）；換向量排版時替換
  `tools/render_pdf.py` 即可，介面不變。
- 生圖「未報錯但品質不佳」的判定尚未定義（提案待辦項）。
- `FurnitureRagService.search` 的實際回傳欄位需在有 DB 環境實測對齊。
