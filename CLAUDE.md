# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RoomPilot — 室內設計即時提案溝通 Agent(AIPE03 第四組,Demo 死線 2026-08-20)。主線流程:上傳平面圖(DXF)→ 升維 3D 白模 → 自動配置家具 → 自然語言/拖曳微調 → 風格化提案 → 匯出檔案。

Multi-module Python/FastAPI monorepo. Each member develops on their own branch; `ben` is the integration branch and `main` is protected. The team SSOT is `RoomPilot_現行版本總覽.md` — read it for scope decisions, P0 priorities, and ownership. When docs conflict, the SSOT wins.

## Modules

| Path | What it is | How to run |
|---|---|---|
| `furniture_engine/` | 家具擺放引擎(Shapely):`place_furniture` / `adjust_furniture`,碰撞 + 淨空檢查。`schema.py` 是 LLM tool schema 介面契約(v0.1);`dxf_room.py` 是 dxf_parser JSON → 引擎 `Room` 的轉接層(F2 整合接點) | `uv run pytest tests/ -v`(25 cases)、`uv run python demo_agent_flow.py` |
| `floorplan2dxf.py` + `config.ini` | 平面圖 PNG → DXF(牆體強制正交,含門/窗偵測)。輸出圖層只有 `WALL` 與 `WINDOW` — 門用於過濾、不寫入 DXF | `python3 floorplan2dxf.py png`;評測:`eval_windows.py`、`eval_doors.py`(需先跑批次產生 `chk/`) |
| `app/` | 升維:`backend/dxf_parser.py` DXF → 3D 樓面 JSON(ezdxf+shapely 牆體聯集,FastAPI :8001)+ `frontend/` React Three Fiber(擠出牆、X-ray、家具拖曳與吸附,Vite :5173) | 見 `app/README.md` |
| `demo_app/` | 走通骨架 demo:一句話 → stub Agent → 真引擎配置 → stub 風格圖(FastAPI :8000)。房間目前寫死 5×4 m,待接 `dxf_room.py` | `cd demo_app && uvicorn main:app --port 8000` |
| `web_fastapi/` | 網站前端(家具庫/風格展示/GLB 檢視器)。⚠️ 目前啟動即掛:依賴不在 repo 的 `sf3d/metadata/*.json` 與 `docs/moodboard_assets/` | 需先補資料才能啟動 |
| `scripts/` | IKEA 型錄管線:下載 GLB → 清洗 → 驗證 → 合併 → 匯入 PostgreSQL。依賴 gitignore 掉的 `data/`、`downloaded-files/` 與 `.env`(見 `.env.example`) | 見 README「家具型錄管線」 |
| `png/` `pngans/` `chk/` `door/` `dxf/` `pic/` | 測試圖、人工答案、輸出預覽、門樣式、DXF 樣本 | 資料 |
| `furniture/` | GLB 家具模型,`app/` 後端的 `/api/furniture` 來源 | 素材 |
| `2Dto3D.html` | 早期單檔 three.js 原型(AI Interior Copilot)。依 SSOT 定位為「3D 直接操作 UX 的靈感來源」,**非 code 主線** | 瀏覽器直接開(需連網載 CDN) |

## Dependencies

Two separate dependency worlds — don't mix them:

- `pyproject.toml` + `uv.lock`(Python ≥3.12):furniture_engine 與 tests。用 `uv sync`。
- `requirements.txt`:平面辨識 + scripts 型錄管線(opencv / ezdxf / selenium / psycopg2 等)。

## Conventions & pitfalls

- **單位**:引擎與 dxf_parser 內部都是**公尺**;`layout.json` 是早期契約草稿、用公分 — 以引擎格式(`schema.py` 的 `placed_to_dict`)為準。
- **座標系**:引擎用 `(x, y)`、角落原點,`pos_y` 是平面第二軸(**不是高度**);dxf_parser 輸出 `(x, z)`、中心原點。`furniture_engine/dxf_room.py` 負責兩者轉換。
- **`check_placement` 命名陷阱**:`placement.py` / `adjustment.py` 把 `check_placement_with_clearance`(含淨空)以 `as check_placement` 別名匯入;`geometry.check_placement` 只查本體碰撞。
- **三個 FastAPI app 並存**(demo_app :8000、app/backend :8001、web_fastapi):port 不要撞;它們互不對接。
- 「找不到目標家具」等錯誤處理在呼叫端(見 `demo_agent_flow.py` 的 `run_adjust`),不在引擎內。
- UI 字串、註解、toast 一律**繁體中文** — 修改 UI 文字時保持一致。
