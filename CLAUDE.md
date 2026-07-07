# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RoomPilot — 室內設計即時提案溝通 Agent(AIPE03 第四組,Demo 死線 2026-08-20)。主線:上傳平面圖(DXF)→ 升維 3D 白模 → 自動配置家具 → 自然語言/拖曳微調 → 風格化提案 → 匯出。

Team SSOT is `docs/RoomPilot_現行版本總覽.md` — read it for scope, P0 priorities, ownership. `main` is protected; `ben` is the integration branch. Repo was reorganized 2026-07-06 into a single Python package (`roompilot/`) with the "B 殼 A 內臟" integration: 舒媁's web UI is the shell, the team's real engines are the internals.

## Layout

| Path | What | Run |
|---|---|---|
| `roompilot/engine/` | 家具擺放引擎(Shapely 碰撞+淨空)。`schema.py` = LLM tool schema 契約;`dxf_room.py` = 樓面 JSON → `Room` 轉接 | `uv run pytest tests/ -v` |
| `roompilot/upgrade3d/dxf_parser.py` | DXF → 3D 樓面 JSON(ezdxf,牆體聯集,房間=孔洞) | — |
| `roompilot/floorplan/` | PNG → DXF(牆正交化+門窗偵測)+ eval。輸出圖層只有 WALL/WINDOW | `uv run python roompilot/floorplan/floorplan2dxf.py testdata/png testdata/dxf` |
| `roompilot/catalog/` | `style_db.py`(型錄→引擎轉接,cm→m 在這裡)+ `data/` 風格資料庫 JSON | — |
| `roompilot/server/` | 唯一 FastAPI:四頁展示 + `/api/scene/generate`、`/api/scene/layout`(擺放走 engine)+ frontend3d 用的 `/api/plan`、`/api/upload` | `uv run uvicorn roompilot.server.main:app --port 8002`(必須在 repo 根目錄跑,相對 import) |
| `frontend3d/` | R3F 3D 編輯器,F6 拖曳邏輯來源(`Furniture.jsx`、`snap.js`)。與 server 前端的收斂待 F6 決策 | `npm run dev`(proxy → :8002) |
| `scripts/` | IKEA 型錄管線(下載/清洗/驗證/合併/匯入 Postgres) | 見 README |
| `examples/` | 退役參考:`demo_app`(走通骨架)、`demo_agent_flow.py`(Agent↔引擎介面範例+失敗詞彙表) | — |
| `testdata/` | dxf/ png/ pngans/ chk/ door/ pic/ sample_glb/ | 資料 |
| `dataset/` | IKEA GLB 1,662 檔(2026-07-07 起進版控,clone 即用) | 資料 |
| `docs/archive/` | `2Dto3D.html`(早期原型,非主線)、`layout.json`(作廢的公分契約) | — |

Dependencies: `pyproject.toml` + uv only(`requirements.txt` 已廢除)。Extras: `server` / `vision` / `catalog`。

## Architecture invariants(違反前先想清楚)

- **家具座標只有 `roompilot.engine` 能算。** `scene_service.generate_layout` 的類型錨點只是候選順序,合法性由 `check_placement_with_clearance` 把關;放不下回報 `placement.failed`,不硬塞。前端 `scene.js` 的 `reflowSceneObjects` 打 `/api/scene/layout`,不做本地擺放。
- **單位**:Python 一律公尺。公分只在兩個邊界:`catalog/style_db.py`(資料庫 cm→m)與 payload 的 `position_cm`/`size_cm`(前端契約)。
- **座標系**:引擎 `(x, y)` 角落原點,`pos_y` 是平面第二軸非高度;payload `position_cm` 是房間中心原點;`rotation_y_deg`(three.js)與引擎 rotation 方向相反,進出引擎取負號。轉換都在 `scene_service.py`。
- **`check_placement` 命名陷阱**:`placement.py`/`adjustment.py` 把含淨空的 `check_placement_with_clearance` 別名成 `check_placement`;`geometry.check_placement` 只查本體。
- 淨空(clearance)語意是「開門/抽拉空間」,只給收納類(見 `style_db.CLEARANCE_BY_TYPE` 的註解,沙發設淨空會誤殺茶几)。

## Conventions

- UI 字串、註解、toast 一律繁體中文。
- `dataset/` GLB 已進版控(2026-07-07;blob 本就在 git 歷史,去重零成本);`data/` 仍 gitignore,其他新大檔案進 git 前先問組長。
- 尚未完成(P0):F3 LLM Agent(tool schema 已備妥於 `engine/schema.py`)、F4 `render_style`(已拍板走 OpenRouter 託管 API)、F8 Demo Mode、F9 匯出。F6 3D 拖曳已完成(2026-07-06)。
