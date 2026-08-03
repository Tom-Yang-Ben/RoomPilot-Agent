# RoomPilot Agent（Master ＋ 4 Sub-agents）

Owner: Yen（`docs/owners/YEN.md`）。本資料夾為 2026-07 架構提案的實作：
Master state machine 編排 Furniture／Validation／Gen_Pic／Report 四個
sub-agent，分層為 `skills/`（LLM 語意決策）與 `tools/`（deterministic 契約
函式），共享文件走 `documents.DocStore`（blackboard）。

## 結構

| 模組 | 內容 |
|---|---|
| `master.py` | 固定流程 state machine：HITL 暫停/resume、修復迴圈 ≤3、改圖 ≤1、生圖失敗 3 次→提示原因→fallback、checkpoint 可恢復上一動 |
| `knowledge.py` / `select.py` / `place.py` | room_pilot2 移植版（2026-07-21）：`backend/server/services/` 經套件 `__init__` import，其 re-export 不可移除 |
| `subagents/` | 四個 sub-agent 的組裝與服務介面 |
| `skills/` | 每個 skill 一個資料夾＋一份 `SKILL.md`（宣告層：frontmatter＋提示詞＋輸出 schema＋流程說明，為提示詞唯一來源）＋`__init__.py`（流程層）：需求整理、家具（A/B 策略）、驗證（雙軌）、生圖（兩階段）、改圖（鎖定清單）、報告（PDF）。另有兩份知識型 skill（`interior_design_principles`、`interior_designer`；foundry-skills 英文原文，只有 SKILL.md、無流程層），由 `design_knowledge` tool 節錄進選件提示與生圖措辭 |
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

## 驗證

```bash
uv run pytest backend/agent/tests -q
```

改動 skills/tools/master 任何一項，最少跑上述測試；動到與 server 的
整合面（含 `__init__` re-export）時，另跑 `uv run pytest tests/ -q`。
