<<<<<<< HEAD
# RoomPilot-Agent

RoomPilot — 室內設計即時提案溝通 Agent(AIPE03 第四組 ・ Demo:2026-08-20)。

把使用者的平面圖與需求,在幾分鐘內變成可即時換風格、調軟裝的 3D 提案畫面。主線流程:

```
上傳平面圖(DXF)→ 升維 3D 白模 → 自動配置家具 → 自然語言/拖曳微調 → 風格化提案 → 匯出檔案
```

> 詳細規劃、分工與時程以團隊 SSOT《RoomPilot_現行版本總覽》為準(在「團隊專案」文件資料夾)。

## 模組地圖(誰做什麼)

| 模組 / 檔案 | 功用 | 負責人 | 狀態 |
|---|---|---|---|
| `floorplan2dxf.py` + `config.ini` | 平面圖 PNG → DXF,牆體強制正交;含門/窗偵測 | 陳峙宏 | 🟢 窗 精準89%/召回91%、門過濾 ~100% |
| `eval_doors.py` / `eval_windows.py` | 門/窗偵測評測腳本(對 `door/`、`pngans/` 答案) | 陳峙宏 | 🟢 |
| `png/` `pngans/` `chk/` `door/` `dxf/` | 測試圖、答案、輸出預覽、門樣式、DXF 樣本 | — | 資料 |
| `furniture_engine/` | 家具擺放引擎:`place_furniture` / `adjust_furniture` / 碰撞 / 淨空(Shapely) | 蔡承安 | 🟢 25 個 pytest 通過 |
| `tests/` | 引擎測試(placement 15 + clearance 10) | 蔡承安 | 🟢 |
| `demo_agent_flow.py` | Agent ↔ 引擎介面互動範例(tool schema 見 `furniture_engine/schema.py`) | 蔡承安 | 🟢 |
| `app/` | **升維**:`backend/dxf_parser.py` DXF → 3D 樓面 JSON(ezdxf+shapely)+ FastAPI 上傳解析;`frontend/` React Three Fiber 3D(擠出牆體、X-ray) | 林柏彥 | 🟠 已併入,待與 `Room` 介面對齊 |
| `web_fastapi/` | 網站前端:首頁 / 家具庫 / 風格展示 / before-after 比較 / GLB 3D 檢視器 | 楊舒媁 | 🟡 依賴的 `sf3d/`、`docs/moodboard_assets/` 不在 repo,啟動需先補資料 |
| `demo_app/` | 走通骨架 Demo:一句話 → Agent(stub)→ 真引擎配置 → 風格圖(stub),端到端可跑 | 楊本顥 | 🟢 展示用 |
| `scripts/` | IKEA GLB 下載、metadata 清洗/驗證、合併 catalog、匯入 PostgreSQL | 蘇立凱、鄭典 | 🟢 |

尚未開始(P0 缺口):F3 LLM Agent(`demo_app/agent_stub.py` 佔位)、F4 風格生成 `render_style`(`render_style_stub.py` 佔位)、F9 檔案匯出、F8 Demo Mode。

## 快速開始

### 家具引擎(測試 + 範例)

```bash
uv sync                          # 或 pip install shapely pytest
uv run pytest tests/ -v          # 25 cases
uv run python demo_agent_flow.py
```

### 走通骨架 Demo(給老師看的端到端)

```bash
cd demo_app
pip install fastapi uvicorn shapely pillow
uvicorn main:app --reload --port 8000     # 開 http://127.0.0.1:8000
```

### 平面辨識(PNG → DXF)

```bash
pip install opencv-python ezdxf numpy
python3 floorplan2dxf.py png/floor01.png   # 輸出同名 .dxf;參數見 config.ini
python3 eval_windows.py && python3 eval_doors.py
```

### 升維 + 3D 檢視(app/)

```bash
cd app/backend && pip install -r requirements.txt && uvicorn main:app --port 8001
cd app/frontend && npm install && npm run dev   # Vite + React Three Fiber
```

### 家具型錄管線(scripts/)

```bash
pip install -r requirements.txt
# 匯入 PostgreSQL 前,在專案根目錄建立 .env:
# DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/roompilot
python scripts/validate_json.py
python scripts/merge_json_to_catalog.py
python scripts/import_catalog_to_postgres.py
```

資料夾約定(已列入 `.gitignore`,不上傳):`data/`(raw_json / processed / reports)、`downloaded-files/`(GLB 大檔)、`.venv/`、`__pycache__/`、`舊的翻譯資料/`。

## 分支

`main` 受保護;各自開分支 → PR 合併。成員分支:`ancai`(引擎)、`cody`(平面辨識)、`yen`(升維+3D,已併入)、`bella`(web 前端)、`kai`(後端/型錄)、`django`(GLB 下載)、`ben`(整合)。

## License

IKEA 下載器參考 `apinanaivot/IKEA-3d-model-batch-downloader`,沿用 GPL-3.0 授權,詳見 [LICENSE](LICENSE)。
=======
### 後端環境設定 (Frontend)

1. **開啟新的終端機，進入 backend 目錄**：

    ```bash
    cd d:\app\backend
    ```

2. **建立虛擬環境及安裝套件**：

    ```
    python -m venv .venv

    .venv\\Scripts\\activate

    pip install -r requirements.txt
    ```

3. **啟動後端**：

    ```
    python -m uvicorn main:app --reload --port 8000
    ```

### 前端環境設定 (Frontend)

## 安裝 Node.js

前端使用 React + Vite，需要安裝 [Node.js](https://nodejs.org/) (建議 v18 以上版本)。

1. **開啟新的終端機，進入 frontend 目錄**：

    ```bash
    cd d:\app\frontend
    ```

2. **安裝 npm 套件**：

   ```bash
   npm install
   ```

3. **啟動前端**：

    ```bash
    npm run dev
    ```

### 開啟網頁

**於網址列輸入 localhost:5173**
>>>>>>> origin/yen
