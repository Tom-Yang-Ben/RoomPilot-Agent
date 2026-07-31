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

### 為何保留 legacy 模組（knowledge.py / select.py / place.py / prompts/）

使用者允許刪除舊內容，但以下活代碼仍 import 它們，刪除會弄壞正式 server：

- `backend/server/main.py:23-24`（`family_of`、`parse_selections`、`request_selections` 等）
- `backend/server/scene_service.py:15`（`resolve_placements`）
- `tests/test_agent_knowledge.py`、`tests/test_agent_select.py`、`tests/test_agent_place.py`

因此 legacy 模組**原樣保留、未動一行**；新架構為本資料夾的正式內容。
未來要移除 legacy 時，需同步改上述 5 個檔案並依 AGENTS.md 跨資料夾格式申報
（主要 owner：Yen；協作 owner：Bella）。

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
- 保存/恢復：`master.to_dict()` / `master.restore()` 直接進 PostgreSQL
  project store JSONB（revision 控制即可支援可恢復上一動）。
- layout 欄位以 `scene_service.room_from_payload` 與
  `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md` 對齊（`ReadLayoutTool`
  目前接受容錯的簡化房間清單）。
- RAG 回傳欄位映射（`tools/rag_furniture._as_candidate`）需對
  `docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md` 實測校準。
- 設計手冊第七章預留與工程文件 MVP `ReportPayload` 的併章掛點。

## 環境變數

| 變數 | 用途 | 預設 |
|---|---|---|
| `OPENROUTER_API_KEY` | 文字＋生圖統一金鑰（沿用既有慣例） | 空＝離線 fallback |
| `ROOMPILOT_AGENT_TEXT_MODEL` | 文字模型覆蓋 | `OPENROUTER_MODEL(S)` → `openrouter/auto` |
| `ROOMPILOT_GENPIC_MODEL` | 生圖主模型（nano banana） | `google/gemini-2.5-flash-image` |
| `ROOMPILOT_GENPIC_FALLBACK_MODEL` | 生圖備援（nano banana 2） | `google/gemini-3-pro-image-preview` |
| `ROOMPILOT_AGENT_LLM_TIMEOUT` | 呼叫逾時（秒） | 120 |
| `ROOMPILOT_PDF_FONT` | 手冊 PDF 中文字型路徑 | 自動找 msjh.ttc 等 |

生圖模型 id 依 OpenRouter 目錄為準，部署時以 `.env` 覆蓋。

## 驗證結果（2026-07-31）

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend/agent/tests   # 21 passed
.\.venv\Scripts\python.exe -m pytest -q --continue-on-collection-errors
# 6 failed, 575 passed, 4 skipped, 3 errors
```

全套的 6 failed（engineering/rag/scene 靜態 hash 與 postgres schema 契約）
與 3 errors（test_official_catalog_sql / test_postgres_project_store /
test_runtime_catalog_phase4 收集錯誤）為本分支既有基線，與本次改動無關、
數量與清單完全一致。

## 已知限制

- PDF 為 Pillow 點陣排版（文字不可選取）；換向量排版時替換
  `tools/render_pdf.py` 即可，介面不變。
- 生圖「未報錯但品質不佳」的判定尚未定義（提案待辦項）。
- `FurnitureRagService.search` 的實際回傳欄位需在有 DB 環境實測對齊。
