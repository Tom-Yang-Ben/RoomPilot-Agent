# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RoomPilot — 室內設計即時提案溝通 Agent(AIPE03 第四組,Demo 死線 2026-08-20)。現行五階段:上傳平面圖(DXF/PNG)與辨識確認 → 沿牆手動校尺(公分)→ 需求問卷+特殊需求(LLM→JSON)→ Agent 選件、引擎計算 2D 配置與人工微調 → 3D 白模、取景、色卡與提案 PNG。不做 ControlNet 圖像生成、不做自然語言換風格。

Team SSOT is `docs/01_專題進度/RoomPilot_現行版本總覽.md` — read it for scope, P0 priorities, ownership. `main` is protected; `ben` is the integration branch. 唯一使用者入口是 FastAPI 交付的 React 工作流:`http://127.0.0.1:8002/scene`。

2026-07-22 起頂層依技術層重組:`backend/`(原 `roompilot/` 套件,內部結構不變)、`frontend/`(原 `frontend3d/`)、`data/dataset/` + `data/testdata/`(原根目錄 `dataset/`、`testdata/`)。import 一律 `backend.*`。合併重組前的舊分支必遇 rename 衝突,對應:`roompilot/X` → `backend/X`、`frontend3d/src/X` → `frontend/src/(components|lib)/X`、`testdata/X` → `data/testdata/X`、`dataset/X` → `data/dataset/X`。

## Commands

```bash
# 後端測試(全部 / 單檔 / 單測試)
uv run pytest tests/ -v
uv run pytest tests/test_layout_api.py -v
uv run pytest tests/test_placement.py::test_name -v

# 前端測試與建置(在 frontend/;建置產物進 backend/server/static/frontend3d/,由 FastAPI 交付)
npm ci
npm test          # node --test src/lib/*.test.js
npm run build     # 改前端後必跑,否則 8002 看不到變更

# 啟動唯一後端(必須在 repo 根目錄跑)
uv run --extra vision uvicorn backend.server.main:app --port 8002
# 開 http://127.0.0.1:8002/scene;npm run dev(5173)只供熱更新,/api 代理到 8002

# 平面圖辨識批次 + eval
uv run --extra vision python backend/floorplan/floorplan2dxf.py data/testdata/png data/testdata/dxf
uv run python backend/upgrade3d/eval_window_merge.py   # 窗段合併 eval
```

Dependencies: `pyproject.toml` + uv only(`requirements.txt` 已廢除)。Extras: `server` / `vision` / `catalog`。業務碼無 anthropic/httpx 依賴,勿引入(唯一例外:dev 群組的 `httpx2` 是 fastapi.testclient 的傳輸層,只准測試用、不得刪);LLM 一律走 OpenRouter(`OPENROUTER_API_KEY`),以依賴注入方式接進模組。

## Layout

| Path | What |
|---|---|
| `backend/engine/` | 家具擺放引擎(Shapely 碰撞+淨空)。`schema.py` = LLM tool schema 契約;`dxf_room.py` = 樓面 JSON → `Room` 轉接 |
| `backend/upgrade3d/` | `dxf_parser.py`:DXF → 3D 樓面 JSON(ezdxf,牆體聯集,房間=孔洞);窗段聚類合併(一扇窗=一段) |
| `backend/floorplan/` | PNG → DXF(牆正交化+門窗偵測)+ eval。輸出圖層只有 WALL/WINDOW;批次另產 `data/testdata/dxf_scale/`(公分 DXF)與 `data/testdata/json/`(px+cm 雙座標)。變更史見其 README |
| `backend/catalog/` | `style_db.py`(型錄→引擎轉接)+ `data/` 風格資料庫 JSON |
| `backend/agent/` | 2026-07-21 以 room_pilot2 概念移植重建的三模組:`knowledge.py`(擺位潛規則 SSOT)、`select.py`(LLM 只選件不出座標)、`place.py`(確定性擺位紀律,執行仍交 Shapely 引擎)。選件驗證邊界在 `parse_selections`(白名單/count 夾限/同族一款/房型適配/成組依賴);副件紀律=寧缺勿亂 |
| `backend/server/` | 唯一 FastAPI:`routes/`(pages/projects/floorplan/scene/library)、`services/`(scene_service 為引擎↔前端轉換樞紐)、`storage/`(SQLite 專案狀態,runtime 在 `.runtime/`,可用 `ROOMPILOT_RUNTIME_DIR` 覆蓋) |
| `backend/skills/roompilot-llm/` | SKILL.md:對話式 intake/風格推薦的 LLM 行為契約。純規格文件,尚未被程式引用 |
| `frontend/` | Vite + React + R3F。`src/components/` 各階段 UI(App/FloorplanReview/RequirementsQuestionnaire/Layout2DReview/Scene/Furniture)、`src/lib/` 純邏輯+同名 node --test 測試 |
| `data/testdata/` | dxf/ dxf_scale/ json/ png/ pngans/ chk/ door/ pic/;floor21 = Demo 基準圖 |
| `data/dataset/` | 素材原料:IKEA GLB(`ikea_glb_db/`)、`catalog_json/`、`style_rag/`、地板材質包 |
| `docs/` | `資料夾功能總覽.md`(現行地圖)、`01_專題進度/`(SSOT)、`04_契約與規格/`、`ai-harness/`(驗收制度)、`archive/`(歷史,只當證據不當現況) |
| `examples/demo_agent_flow.py` | Agent↔引擎介面範例 |

## Architecture invariants(違反前先想清楚)

- **家具座標只有 `backend.engine` 能算。** Agent 只選件/給紀律,合法性由 `check_placement_with_clearance` 把關;放不下回報 `placement.failed`,不硬塞。前端不做本地擺放,一律打 `/api/scene/layout`。
- **單位**:引擎與 Python 業務層一律**公分**;`engine/dxf_room.py` 是「公尺→公分」的唯一邊界(上游 `dxf_parser` 維持公尺)。payload 的 `position_cm`/`size_cm` 公分;但 payload 的 `wall/window/door segments` 與 `room_regions` 維持**公尺**(three.js 契約),轉換集中在 `scene_service.py`。
- **座標系**:引擎 `(x, y)` 角落原點,`pos_y` 是平面第二軸非高度;payload `position_cm` 是房間中心原點;`rotation_y_deg`(three.js)與引擎 rotation 方向相反,進出引擎取負號。轉換都在 `scene_service.py`。`data/testdata/json/` 的 cm 座標又是另一套(原點左下、y 向上)——接前端時別直接混用。
- **對外契約與模組路徑已脫鉤,以下名稱不可因重構改動**:URL `/static/frontend3d/`(vite build 產物目錄名仍叫 frontend3d)、URL `/dataset/...`(model_url)、SQLite 資料鍵 `workflow.frontend3d`、localStorage `roompilot:sceneProposal`、環境變數 `ROOMPILOT_RUNTIME_DIR`、DB 名 `roompilot_db`。改壞任何一個都會壞前端或既存專案資料。
- **`check_placement` 命名陷阱**:`placement.py`/`adjustment.py` 把含淨空的 `check_placement_with_clearance` 別名成 `check_placement`;`geometry.check_placement` 只查本體。
- 淨空(clearance)語意是「開門/抽拉空間」,只給收納類(見 `style_db.CLEARANCE_BY_TYPE` 註解,沙發設淨空會誤殺茶几)。

## Conventions

- UI 字串、註解、toast 一律繁體中文。
- **入倉三規則(合併他人分支時把關)**:①新增「頂層目錄」需組長同意——資料原料進 `data/dataset/`、引擎讀的正式資料進 `backend/catalog/data/`、網站資產進 `backend/server/static/`;②禁止把整包 repo 副本 / 個人工作區直接 commit;③檔名禁止空格結尾與「 2」副本(macOS 複製殘留)。
- `backend/server/static/surface_assets/_import_all/` 名字像原料但**是活資產**(surface_catalog.json 引用全部 299 檔),勿搬勿刪。
- 新增大檔案進 git 前先問組長。

## Git safety(七人共用 repo)

- 動手前 `git status` + `git branch --show-current`;使用者未提交的修改一律視為要保留。`git add` 用明確路徑,不用 `git add .`。
- 未經使用者明確要求,不得:`git push`(任何形式)、merge/rebase 進共用分支、`reset --hard`、`git clean`、`checkout -- .`/`restore .`、改寫歷史、刪除分支。個人分支(`ancai-dev`/`rule`/`kai-dev` 等)勿動。
- 合併他人分支先 `git log target..source` + `diff --stat` 盤點回報再動手;衝突涉及他人模組時列選項讓人裁決。

## 宣稱完成前必須有證據

說「完成/修好了」之前,對照 `docs/ai-harness/DEFINITION_OF_DONE.md` 對應層,證據至少一項:測試輸出(貼數字)、實跑輸出、檔案回讀、API 實測(curl)。前端/互動類要瀏覽器實際操作結果,後端測試通過不算。無法驗證就寫「已修改,尚未驗證」。動了 floorplan 偵測邏輯必須貼 eval 數字;動了路由必須貼 curl。接任務前看 `docs/ai-harness/TASK_TEMPLATES.md`,犯錯後記帳 `docs/ai-harness/FAILURE_LOG.md`。
