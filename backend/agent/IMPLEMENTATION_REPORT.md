# Yen Agent 架構與 Bella 整合報告

目前版本：2026-08-06。

Yen Agent 已由 2026-07-31 的獨立提案，演進為 Bella 正式八步流程的一部分。現行第 7 步消費鎖定場景與問卷 context，第 8 步已接入逐房首次生圖、每房一次修圖，以及最終 Web 成果包。下方保留初始實作背景，但「尚未接 Server」與「超出 Demo」敘述已由本次整合狀態取代。

依 `agent-design-proposal.html`（討論定案版）落地。實作全部位於
`backend/agent/`，分層為 `skills/` 與 `tools/`（使用者要求的最低分層）加上
`subagents/`、`master.py`、`documents.py`、`llm.py`、`runtime.py`。

## 2026-07-31 初始實作範圍（歷史背景）

初始落地當時沒有修改 `backend/agent/` 以外的程式碼；這不再代表目前狀態。2026-08-06 已由 Bella 在 `backend/server/ai_render_service.py`、`backend/server/main.py` 與正式前端完成整合。

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
| 需求整理（三分流＋家電防線）、家具（動線／收納內部候選策略）、驗證（雙軌）、生圖（兩階段）、改圖（鎖定清單）、報告（PDF） | `skills/<name>/`——每個 skill 一資料夾：`SKILL.md`（宣告層，提示詞與 schema 唯一來源）＋`__init__.py`（流程層，含 deterministic fallback） |
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

## 2026-08-06 Server 整合狀態

- `backend/server/ai_render_service.py` 透過 `GenPicAgent` 提供首次生圖與修圖服務。
- `GET /api/ai-render/status` 回報主模型與 fallback，不洩漏 `OPENROUTER_API_KEY`。
- `POST /api/projects/{project_id}/ai-renders` 依第 6 步配置、第 7 步視角與問卷逐房生圖。
- `POST /api/projects/{project_id}/ai-renders/{room_id}/edit` 由 ProjectStore 保存並強制每房一次修圖額度。
- `POST /api/projects/{project_id}/design-delivery` 已輸出逐房 Web 簡報、設計師方法論參照、工程報告、資安審核、家具／裝潢預算與 JSON。
- 缺價項目一律「待報價」；Web 組稿採欄位白名單與敏感 key 掃描。
- `master.to_dict()`／`restore()` 仍可供更完整 orchestrator checkpoint；目前正式第 8 步服務直接使用 Yen 的 GenPic 邊界與 Bella workflow state。

## 環境變數

| 變數 | 用途 | 預設 |
|---|---|---|
| `OPENROUTER_API_KEY` | 文字＋生圖統一金鑰（沿用既有慣例） | 空＝離線 fallback |
| `ROOMPILOT_AGENT_TEXT_MODEL` | 文字模型覆蓋 | `OPENROUTER_MODEL(S)` → `openrouter/auto` |
| `ROOMPILOT_GENPIC_MODEL` | 生圖主模型 | `google/gemini-3.1-flash-image` |
| `ROOMPILOT_GENPIC_FALLBACK_MODEL` | 生圖備援 | `google/gemini-2.5-flash-image` |
| `ROOMPILOT_AGENT_LLM_TIMEOUT` | 呼叫逾時（秒） | 120 |
| `ROOMPILOT_PDF_FONT` | 手冊 PDF 中文字型路徑 | 自動找 msjh.ttc 等 |

生圖模型 id 依 OpenRouter 目錄為準，部署時以 `.env` 覆蓋。

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

歷史範圍註記已失效：正式產品現在是八步，GenPic 首次生圖／一次修圖與 Web 成果包已屬現行功能。`tools/render_pdf.py` 仍是 Agent 可用的 PDF 工具，但正式 UI 第一版交付為 Web + JSON；PPTX／正式向量 PDF 尚未接入。未設定 `OPENROUTER_API_KEY` 或供應商回 402 時，必須顯示真實原因，不得假成功。

## 驗證結果

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend/agent/tests
$env:ROOMPILOT_RUNTIME_DIR = (Join-Path (Get-Location) '.runtime-test-integration')
.\.venv\Scripts\python.exe -m pytest -q backend/agent/tests tests/test_ai_render_openrouter.py tests/test_remote_render_workflow.py tests/test_scene_v2_contract.py tests/test_scene_delivery.py tests/test_scene_pricing.py
```

2026-08-06 第 6 至 8 步完整 focused／integration baseline 為 260 passed、3 個既有 deprecation warnings；桌面與 390 x 844 手機成果包已做實際瀏覽器驗證。

## 已知限制

- PDF 為 Pillow 點陣排版（文字不可選取）；換向量排版時替換
  `tools/render_pdf.py` 即可，介面不變。
- 生圖「未報錯但品質不佳」仍由使用者唯一一次修圖處理，尚無自動視覺品質評分。
- `FurnitureRagService.search` 的實際回傳欄位需在有 DB 環境實測對齊。
- OpenRouter 是否有額度不是程式可保證的狀態；`configured=true` 不等於供應商一定接受付費請求。
