# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RoomPilot — 室內設計即時提案溝通 Agent(AIPE03 第四組,Demo 死線 2026-08-20)。主線(7/7 改版;順序 7/16 組長確認):上傳平面圖(DXF/PNG)→ 手動拉比例(公分)→ 需求問卷+特殊需求(LLM→JSON)→ 升維 3D 白模 → Agent 依風格擺位家具 → 手動拖曳微調(自然語言微調為 P1)→ 提案畫面。不做 ControlNet 圖像生成、不做自然語言換風格。

Team SSOT is `docs/01_專題進度/RoomPilot_現行版本總覽.md` — read it for scope, P0 priorities, ownership. `main` is protected; `ben` is the integration branch. Repo was reorganized 2026-07-06 into a single Python package (`roompilot/`) with the "B 殼 A 內臟" integration: 舒媁's web UI is the shell, the team's real engines are the internals.

## Layout

| Path | What | Run |
|---|---|---|
| `roompilot/engine/` | 家具擺放引擎(Shapely 碰撞+淨空)。`schema.py` = LLM tool schema 契約;`dxf_room.py` = 樓面 JSON → `Room` 轉接 | `uv run pytest tests/ -v` |
| `roompilot/upgrade3d/dxf_parser.py` | DXF → 3D 樓面 JSON(ezdxf,牆體聯集,房間=孔洞);窗段聚類合併(一扇窗=一段) | 窗 eval:`uv run python roompilot/upgrade3d/eval_window_merge.py` |
| `roompilot/floorplan/` | PNG/JPG/BMP → DXF(牆正交化+門窗偵測)+ eval。輸出圖層只有 WALL/WINDOW;批次另產 `testdata/dxf_scale/`(公分 DXF,外圍牆厚錨定比例)與 `testdata/json/`(前端交接,px+cm 雙座標+scale 信心度)。變更史見 `roompilot/floorplan/README.md` | `uv run --extra vision python roompilot/floorplan/floorplan2dxf.py testdata/png testdata/dxf` |
| `roompilot/catalog/` | `style_db.py`(型錄→引擎轉接,cm→m 在這裡)+ `data/` 風格資料庫 JSON | — |
| `roompilot/agent/` | Agent 擺放提示鏈(柏彥):擺位前用 `layout_intent` 給引擎語意提示(anchor/priority),放不下時用 `recovery` 換小款或移除。只出提示不出座標,`scene_service` 已接線;具體怎麼做見各檔 docstring 與 `prompts.py` | `uv run pytest tests/test_agent_layout_intent.py tests/test_agent_recovery.py -v` |
| `roompilot/skills/` | `roompilot-llm/SKILL.md`(舒媁):對話式 intake/風格推薦的 LLM 行為契約(JSON 輸出格式+fallback)。純規格文件,尚未被程式引用;細節見 SKILL.md 本身 | — |
| `roompilot/server/` | 唯一 FastAPI:四頁展示 + `/api/scene/generate`、`/api/scene/layout`(擺放走 engine)+ frontend3d 用的 `/api/plan`、`/api/upload` | `uv run uvicorn roompilot.server.main:app --port 8002`(必須在 repo 根目錄跑,相對 import) |
| `frontend3d/` | R3F 3D 編輯器,F6 拖曳邏輯來源(`Furniture.jsx`、`snap.js`)。與 server 前端的收斂待 F6 決策 | `npm run dev`(proxy → :8002) |
| `scripts/` | IKEA 型錄管線(下載/清洗/驗證/合併/匯入 Postgres) | 見 README |
| `examples/` | 退役參考:`demo_app`(走通骨架)、`demo_agent_flow.py`(Agent↔引擎介面範例+失敗詞彙表) | — |
| `testdata/` | dxf/ dxf_scale/ json/ png/ pngans/ chk/ door/ pic/;floor21 = Demo 基準圖 | 資料 |
| `dataset/` | 素材與資料原料:IKEA GLB 1,517 檔(2026-07-19 實數,`git ls-files "*.glb" | wc -l`)、`catalog_json/`(kai 型錄 JSON 池+manifests)、`style_rag/`(django 風格池)、地板材質包(2026-07-12 歸位) | 資料 |
| `docs/` | `01_專題進度/`(SSOT)、`04_契約與規格/`(schema/契約)、`05_狀態與稽核/`(各人狀態文件)、`archive/`;02/03 為組長本地筆記不進版控 | — |

Dependencies: `pyproject.toml` + uv only(`requirements.txt` 已廢除)。Extras: `server` / `vision` / `catalog`。

## Architecture invariants(違反前先想清楚)

- **家具座標只有 `roompilot.engine` 能算。** `scene_service.generate_layout` 的類型錨點只是候選順序,合法性由 `check_placement_with_clearance` 把關;放不下回報 `placement.failed`,不硬塞。前端 `scene.js` 的 `reflowSceneObjects` 打 `/api/scene/layout`,不做本地擺放。
- **單位**(2026-07-11 公分化):引擎與 Python 業務層一律**公分**;`engine/dxf_room.py` 是「公尺→公分」的唯一邊界(上游 `dxf_parser` 維持公尺)。payload 的 `position_cm`/`size_cm` 公分;但 payload 的 `wall/window/door segments` 與 `room_regions` 維持**公尺**(three.js 契約),轉換集中在 `scene_service.py`。
- **座標系**:引擎 `(x, y)` 角落原點,`pos_y` 是平面第二軸非高度;payload `position_cm` 是房間中心原點;`rotation_y_deg`(three.js)與引擎 rotation 方向相反,進出引擎取負號。轉換都在 `scene_service.py`。`testdata/json/` 的 cm 座標又是另一套(原點左下、y 向上,同 dxf_scale)——接前端時別直接混用。
- **`check_placement` 命名陷阱**:`placement.py`/`adjustment.py` 把含淨空的 `check_placement_with_clearance` 別名成 `check_placement`;`geometry.check_placement` 只查本體。
- 淨空(clearance)語意是「開門/抽拉空間」,只給收納類(見 `style_db.CLEARANCE_BY_TYPE` 的註解,沙發設淨空會誤殺茶几)。

## Conventions

- UI 字串、註解、toast 一律繁體中文。
- `dataset/` GLB 已進版控(2026-07-07;blob 本就在 git 歷史,去重零成本);`data/` 仍 gitignore,其他新大檔案進 git 前先問組長。
- **入倉三規則(2026-07-12,合併他人分支時把關)**:①新增「頂層目錄」需組長同意——資料原料進 `dataset/`、引擎讀的正式資料進 `roompilot/catalog/data/`、網站資產進 `server/static/`;②禁止把整包 repo 副本 / 個人工作區直接 commit;③檔名禁止空格結尾與「 2」副本(macOS 複製殘留)。
- `server/static/surface_assets/_import_all/` 名字像原料但**是活資產**(surface_catalog.json 引用全部 299 檔),勿搬勿刪。
- 尚未完成(P0,7/7 改版後):手動拉比例 F2a、3D 窗戶修正、特殊需求 LLM→JSON、Agent 風格擺位(柏彥,tool schema 在 `engine/schema.py`)、風格界定 JSON(舒媁)、F6 手動微調修復、合法重疊/擋門/動線規則(承安)。F8/F9 已移出 P0;前端主線已決定改用 `frontend3d/`(柏彥 R3F)。詳見 SSOT v3.0。

## AI Harness 制度路由(2026-07-13)

| 情境 | 先讀 |
|---|---|
| 要說「完成/修好了」之前 | `.claude/rules/verification.md` + `docs/ai-harness/DEFINITION_OF_DONE.md` 對應層 |
| 接任務 / 交辦任務 | `docs/ai-harness/TASK_TEMPLATES.md` |
| 開工前查前車之鑑、犯錯後記帳 | `docs/ai-harness/FAILURE_LOG.md` |
| 任何 git 寫入操作前 | `.claude/rules/git-safety.md` |
| 讀狀態文件前 | DoD §0.1 文件可信度指引(05 的三份 STATUS 已過時,勿當現況) |

模型分工(**本段給交辦的人讀**,session 內模型無法自行切換;AI 讀到此段時的義務只有一條:同一子任務重試兩輪仍失敗就停下,保存完整失敗軌跡並回報建議升級):搜尋/整理/機械修改用低成本模型;一般實作與除錯用中階;模糊架構、根因不明、重試兩輪失敗才升級高階;高階解出模式後,批次套用降回便宜模型。
