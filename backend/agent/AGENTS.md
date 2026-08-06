# RoomPilot Yen Agent（Master + 4 Sub-agents）

Owner：Yen（`docs/owners/YEN.md`）。文件版本：2026-08-06。

本資料夾原為 2026-07 架構提案，目前已接入 Bella 第 8 步生圖與一次修圖路徑：
Master state machine 編排 Furniture／Validation／Gen_Pic／Report 四個
sub-agent，分層為 `skills/`（LLM 語意決策）與 `tools/`（deterministic 契約
函式），共享文件走 `documents.DocStore`（blackboard）。

## 結構

| 模組 | 內容 |
|---|---|
| `master.py` | 固定流程 state machine：HITL 暫停/resume、修復迴圈 ≤3、改圖 ≤1、生圖失敗 3 次→提示原因→fallback、checkpoint 可恢復上一動 |
| `knowledge.py` / `select.py` / `place.py` | room_pilot2 移植版（2026-07-21）：`backend/server/services/` 經套件 `__init__` import，其 re-export 不可移除 |
| `subagents/` | 四個 sub-agent 的組裝與服務介面 |
| `skills/` | 每個 skill 一個資料夾＋一份 `SKILL.md`（frontmatter、提示詞、輸出 schema 與流程說明的唯一來源）＋`__init__.py`（流程層）：需求專業化、家具候選策略、驗證、生圖、改圖與報告。Agent 內部可比較候選，但不得把它變成第 6 步公開 A/B 流程。另有 `interior_design_principles`、`interior_designer` 兩份知識型 skill，由 `design_knowledge` tool 節錄進選件與生圖措辭 |
| `tools/` | read_layout、read_rules、rag_furniture、pick_furniture、place_furniture、engine_validate、genpic_info、fetch_image、read_docs、render_pdf、design_knowledge |
| `documents.py` | Docs 層資料契約與 DocStore（plain dict、可整包存專案 storage、checkpoint/undo） |
| `llm.py` | OpenRouter gateway：文字＋生圖（nano banana；fallback nano banana 2）；stdlib urllib＋certifi，業務碼禁 httpx |
| `runtime.py` | 預設組裝 `build_master()` |

## 不可違反

- 座標與幾何合法性只由 `backend/engine/` 判定；LLM 與 skills 不得產生或
  修改座標（`place_furniture` tool 只翻譯語意意圖成 engine 呼叫）。
- 家具向量 RAG 只解析需求、檢索與排序；檢索不可用時回報可讀錯誤，
  不得改用未驗證資料。
- 家電（冰箱、洗衣機、冷氣、電視等）只進需求文件的 `appliances` 與生圖
  context；`RequirementSkill._enforce_contracts` 是強制防線。
- 所有 LLM skill 必須有 deterministic fallback（無金鑰可完整跑通流程，
  生圖除外——生圖以可讀原因暫停）。
- 提示詞與輸出 schema 只能寫在各 skill 的 `SKILL.md`（`load_skill_doc()`
  於匯入期解析驗證）；改提示詞不需動 Python，但要跑 skills 測試。
- 迴圈上限、額度與模型切換由 Master 程式控制，不交給 LLM 自律。
- 公分制；場景 placed 條目沿用 `backend.engine.schema.placed_to_dict`，
  由擺家具 tool 附加 `coordinate_unit: "cm"` 與 catalog 追溯欄位。
- engine 進階擺位（adjacent/overlay）是能力偵測的選配：引擎沒有時意圖
  降級 free 自由擺放，agent 層不得自行實作幾何補位。
- 套件 `__init__` 的 room_pilot2 re-export（`parse_selections`、
  `resolve_placements` 等）被 `backend/server/services/` 依賴，不可移除。
- `GenPicInfoTool` 必須保留問卷、整體風格、材質、家具、固定結構與第 7 步 Yen 鎖定視角；不得把 prompt 原文 `print` 到 stdout。
- 每房成功修圖最多一次；前端顯示、Master 狀態與 Bella ProjectStore 後端都要維持同一額度。
- 設計師參照只能描述方法論，不得捏造原話或暗示本人參與／背書。

## 現行 Bella Server 接點

| 接點 | Agent 責任 | Bella 責任 |
|---|---|---|
| `GET /api/ai-render/status` | 提供模型預設與 provider 狀態資料 | 過濾金鑰後回前端 |
| `POST /api/projects/{project_id}/ai-renders` | 依鎖定快照與逐房 context 建 GenPic prompt | 驗證 payload、保存結果與 revision |
| `POST /api/projects/{project_id}/ai-renders/{room_id}/edit` | 依回饋修圖，保留結構鎖定 | 強制每房一次額度並保存 |
| `POST /api/projects/{project_id}/design-delivery` | 提供設計說明與報告語意節點 | 白名單組稿、資安掃描、價格真實性與 Web UI |

第 7 步三個候選視角由 Bella Three.js 依第 6 步場景擷取，不消耗生圖額度；Yen 消費鎖定相機與問卷 context，不產生家具座標。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q backend/agent/tests
```

改動 skills/tools/master 任何一項，最少跑上述測試；動到與 server 的
整合面（含 `__init__` re-export）時，另跑：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_render_openrouter.py tests/test_scene_delivery.py tests/test_scene_room_requirements.py
```
