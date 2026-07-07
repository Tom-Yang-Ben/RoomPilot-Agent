# RoomPilot-Agent

RoomPilot — 室內設計即時提案溝通 Agent(AIPE03 第四組 ・ Demo:2026-08-20)。

把使用者的平面圖與需求,在幾分鐘內變成可即時換風格、調軟裝的 3D 提案畫面。主線流程:

```
上傳平面圖(DXF)→ 升維 3D 白模 → 自動配置家具 → 自然語言/拖曳微調 → 風格化提案 → 匯出檔案
```

> 詳細規劃、分工與時程以團隊 SSOT《[RoomPilot_現行版本總覽](docs/RoomPilot_現行版本總覽.md)》為準。

## 專案結構(2026-07-06 重整後)

```
roompilot/            後端主套件(唯一的 Python 套件)
├── engine/           家具擺放引擎:place/adjust、碰撞+淨空(Shapely)、LLM tool schema、
│                     dxf_room.py(DXF 樓面 JSON → Room 轉接層)
├── upgrade3d/        dxf_parser.py:DXF → 3D 樓面 JSON(ezdxf+shapely)
├── floorplan/        floorplan2dxf.py:PNG → DXF(牆體正交化、門窗偵測)+ eval 腳本
├── catalog/          style_db.py(型錄→引擎轉接,公分→公尺)+ data/(12 風格資料庫 JSON)
└── server/           唯一的 FastAPI 網站:四頁展示 + 場景生成(擺放一律走 engine)
    └── static/       前端頁面(首頁/風格/家具庫/3D 場景)+ moodboard + DRACO

frontend3d/           React Three Fiber 3D 編輯器(F6 拖曳來源;與 server 的收斂待 F6 決策)
scripts/              IKEA 型錄管線:下載 → 清洗 → 驗證 → 合併 → 匯入 PostgreSQL
tests/                pytest(引擎 25 案例)
testdata/             測試素材:dxf/ png/ pngans/ chk/ door/ pic/ sample_glb/
dataset/              (gitignore)IKEA GLB 1,517 檔 —— 找舒媁拿雲端連結,放到這裡
examples/             退役參考:demo_app(走通骨架)、demo_agent_flow.py(Agent↔引擎介面範例)
docs/                 SSOT、changelog、archive/(2Dto3D.html 原型、layout.json 舊契約)
```

## 新機器上手(第一次 clone 必讀)

```bash
# 0. 裝 uv(唯一前置;Python 3.12 不用另裝,uv 會自動抓)
#    macOS:
brew install uv
#    Windows(PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 1. Clone + 裝依賴(⚠️ 一定要 --extra server:純 uv sync 只裝引擎最小依賴,網站起不來)
git clone https://github.com/Tom-Yang-Ben/RoomPilot-Agent.git
cd RoomPilot-Agent
uv sync --extra server

# 2. 驗證環境(應該 25 passed)
uv run pytest tests/ -v

# 3. 啟動網站(必須在 repo 根目錄跑)
uv run uvicorn roompilot.server.main:app --port 8002   # 開 http://127.0.0.1:8002
```

兩個不在 git 裡的東西:

- **`dataset/`**:IKEA GLB 模型,向舒媁拿雲端連結解壓到 repo 根目錄。沒有它網站照跑,只是家具無 3D 模型。
- **`.env`**:`cp .env.example .env`。兩組變數皆選配 — `OPENROUTER_API_KEY` 沒填走本地規則 fallback;DB 變數只有型錄匯入 script 用到。

按角色加裝(不是人人需要):

| 誰 | 額外步驟 |
|---|---|
| 平面辨識 | `uv sync --extra vision`(OpenCV,見下方指令) |
| 型錄 / DB | `uv sync --extra catalog` + 本機 PostgreSQL + `.env` 填 DB 變數 |
| R3F 編輯器 | Node.js 18+,`cd frontend3d && npm install && npm run dev` |
| 其他人 | 上面 0–3 就夠 |

## 快速開始

```bash
uv sync --extra server               # 引擎 + 網站後端依賴
uv run pytest tests/ -v              # 25 cases
uv run uvicorn roompilot.server.main:app --port 8002   # 開 http://127.0.0.1:8002
```

網站四頁:`/` 首頁、`/styles` 風格、`/library` 家具庫、`/scene` 3D 場景(上傳 DXF + 問卷 → 引擎配置)。
家具 3D 模型需要 `dataset/`(不在 git,向舒媁要雲端連結);沒有 dataset 時網站可跑、家具無模型。
LLM 挑家具為選配:複製 `.env.example` 為 `.env` 填 `OPENROUTER_API_KEY`;沒填走本地規則 fallback。

### 平面辨識(PNG → DXF)

```bash
uv sync --extra vision    # 或 pip install opencv-python ezdxf numpy
uv run python roompilot/floorplan/floorplan2dxf.py testdata/png testdata/dxf
uv run python roompilot/floorplan/eval_windows.py && uv run python roompilot/floorplan/eval_doors.py
```

### R3F 3D 編輯器(frontend3d/)

```bash
uv run uvicorn roompilot.server.main:app --port 8002   # 後端(/api/plan、/api/upload 已併入)
cd frontend3d && npm install && npm run dev             # Vite,/api 代理到 :8002
```

### 家具型錄管線(scripts/)

```bash
uv sync --extra catalog
# 匯入 PostgreSQL 前,複製 .env.example 為 .env 並填入 DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
python scripts/validate_json.py && python scripts/merge_json_to_catalog.py
python scripts/import_catalog_to_postgres.py
```

## 架構重點(2026-07-06「B 殼 A 內臟」整合)

- **家具座標只有引擎能算**:`/api/scene/generate` 與 `/api/scene/layout` 的擺放一律走
  `roompilot.engine`(Shapely 碰撞 + 淨空);LLM/問卷只決定「放什麼」,不決定「放哪裡」。
  放不下的家具誠實回報在 `payload.placement.failed`,不硬塞。
- **DXF 升維單一路徑**:`upgrade3d/dxf_parser` 解析 → `engine/dxf_room` 取最大封閉房間轉 `Room`。
- **單位契約**:Python 端一律公尺;公分只出現在資料庫讀入(`catalog/style_db.py` ÷100)與
  前端 payload 邊界(`position_cm`、`size_cm`)。
- 尚未完成(P0):F3 LLM Agent 編排、F4 風格生成 `render_style`、F8 Demo Mode、F9 檔案匯出
  (F6 3D 直接拖曳已於 2026-07-06 完成)。

## 分支

`main` 受保護;各自從最新 `ben`(整合分支)開分支 → PR 合併。
大檔案(GLB、資料集)一律走雲端硬碟,不進 git。

## License

IKEA 下載器參考 `apinanaivot/IKEA-3d-model-batch-downloader`,沿用 GPL-3.0 授權,詳見 [LICENSE](LICENSE)。
