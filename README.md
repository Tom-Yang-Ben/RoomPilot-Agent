# RoomPilot

RoomPilot 是 AIPE03 第四組開發的 AI 室內設計系統。使用者上傳一張平面圖，
系統即可完成辨識與尺寸校正、逐房需求訪談、家具自動配置、2D/3D 同步編輯、
AI 渲染出圖，最後產出含設計語彙、家具採購明細、工程費用與初步工期的成果報告。
整個流程以專案為單位保存，隨時可以中斷、恢復與分享。

## 功能總覽

| 步驟 | 功能 | 產出 |
|---|---|---|
| 0 | 帳號註冊／登入，進入「我的專案」 | 使用者、角色與專案清單 |
| 1 | 建立專案 | 可保存、恢復與分享的 `project_id` |
| 2 | 上傳 PNG／JPG／DXF 平面圖 | 原始平面圖 |
| 3 | 兩點標定，確認公分尺度 | 統一公分制的比例尺 |
| 4 | 校正空間、牆、門、窗、樑與柱 | `layout_json` |
| 5 | 全屋風格、材質、冷氣範圍，再逐房確認用途、家具類型、尺寸與數量 | 問卷與三張風格色卡 |
| 6 | 自動配置家具，同一畫面同步編輯 2D／3D 並走動預覽 | `scene_json` |
| 7 | 鎖定方案，逐房選擇並微調生成視角 | 鎖定的逐房相機 |
| 8 | AI 渲染：依問卷、家具、材質、色卡與視角逐房出圖 | 逐房渲染圖與成果包 |
| 9 | 成果報告：設計語彙、家具採購明細、工程施工費與初步工期 | HTML／XLSX／JSON 三份文件 |

- 家具碰撞、淨空不足、超出邊界或模型載入失敗都會在畫面上標示原因，並阻擋進入下一步；
  第 4 步結構一旦變更，系統會重新驗證目前所有家具。
- 第 6 步的家具是否合法只由幾何引擎判定，前端只負責呈現與送出操作。
- 冰箱、洗衣機等家電由問卷保存並帶進第 8 步生圖，不參與第 6 步的自動擺設。
- 第 9 步在 `/engineering`：把鎖定版 `ProjectSnapshot` 轉成三份文件。家具採購與
  工程施工費是兩筆獨立預算，報告分別列示、不合計；設計語彙來自團隊編纂的
  `backend/catalog/data/design/`，報告會如實標示其信心等級。

## 系統架構

```text
瀏覽器 HTML/CSS/JavaScript/Three.js（frontend/）
  <-> FastAPI API 與專案持久化（backend/server/）
      -> 平面圖辨識（backend/floorplan/）
      -> 空間關係與 layout evaluation（backend/spatial_data/）
      -> layout_json
      -> 需求解析與家具選件（backend/agent/）
      -> 家具型錄 / CloudFront / PostgreSQL / RAG（backend/catalog/）
      -> 幾何配置、碰撞與淨空（backend/engine/）
      -> scene_json
      -> 2D/3D 編輯、方案視角、AI 渲染、成果報告（backend/server/ + frontend/）
```

- 辨識止於 `layout_json`；方案生成與編輯以 `scene_json` 為準。
- Graph RAG 只負責房間、家具、風格、材質與限制關係的檢索與證據，
  幾何、碰撞、淨空與結構合法性一律由 `backend/engine/` 計算。
- 前端不經打包：`frontend/` 以原生 ES module 直接載入 `vendor/three/`，沒有 Node.js 建置步驟。

完整圖解見 [使用者流程與系統架構圖](docs/使用者流程與系統架構圖.md)；
跨模組協作與資料邊界見 [現行版本總覽](docs/RoomPilot_現行版本總覽.md)。

## 快速啟動

### 環境需求

- Windows 10／11 64-bit
- Python 3.12
- Git 與 Git LFS（家具向量檔 `JSON/RAG/furniture_embeddings_bge_m3.jsonl` 以 LFS 儲存）
- PostgreSQL 17 + pgvector：家具型錄、風格材質與專案的正式資料來源
- Node.js 22+：第 9 步 XLSX 匯出使用

在乾淨的新機器上從零佈到「三個 provider 全走 PostgreSQL、RAG 開啟」的完整狀態，
請依 [換機部署清單](docs/NEW_MACHINE_SETUP.md) 逐節執行；本節只涵蓋最短的啟動路徑。

### 安裝與啟動

方式一：Python venv 與 `requirements.txt`

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\dev.ps1            # 等同 uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

方式二：uv

```powershell
uv sync --extra server --extra vision --extra catalog --group dev
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

開啟 <http://127.0.0.1:8002>，在 `/login` 註冊第一個帳號後即可建立專案。
`8002` 已被占用時改成 `.\dev.ps1 8023` 或其他未使用的連接埠。

### 選配元件

| 元件 | 用途 | 安裝 |
|---|---|---|
| 房型語意層（DINOv2） | 提高第 4 步房型判讀準確度；未安裝時退回面積規則，`room_label_source` 標示 `area_rules` 而非 `dinov2_semantic` | `uv sync --extra semantic`（torch 約 2 GB） |
| PaddleOCR | 尺度文字與繁中房名 OCR；未安裝時比例尺改由第 3 步手動標定 | `uv sync --extra ocr` 或 `pip install -r requirements-ocr.txt` |
| 家具 RAG（BGE-M3 + pgvector） | `/rag` 需求解析與向量檢索 | `uv pip install -r requirements-rag.txt`，並在 `.env` 開啟 `ROOMPILOT_RAG_ENABLED=true`；模型快取約 6.5 GB，見換機部署清單 |
| XLSX 匯出 | 第 9 步估價表 | `cd tools/artifact_tool_local; npm ci`，並在 `.env` 設 `ROOMPILOT_ARTIFACT_TOOL_MODULES=<repo>\tools\artifact_tool_local` |

## 設定（`.env`）

完整清單與說明見 [`.env.example`](.env.example)。常用項目：

| 群組 | 變數 | 說明 |
|---|---|---|
| 資料來源 | `ROOMPILOT_CATALOG_PROVIDER` | 家具型錄來源，預設 `postgres`（嚴格模式，連不上回 503）；離線開發才明確設 `json` |
| | `ROOMPILOT_RUNTIME_CATALOG_PROVIDER` | 風格卡、表面材質、裝修費率來源，預設 `postgres` |
| | `ROOMPILOT_PROJECT_STORE_PROVIDER` | 專案與 workflow 保存位置，`postgres` 或 `sqlite` |
| | `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL 連線；`DB_POOL_MAX` 控制併發上限 |
| 帳戶 | `ROOMPILOT_AUTH_SECRET` | Token 簽章金鑰，多節點部署必須設定同一把 |
| | `ROOMPILOT_AUTH_ACCESS_TTL_MINUTES` / `ROOMPILOT_AUTH_REFRESH_TTL_DAYS` | Token 有效期 |
| | `ROOMPILOT_AUTH_DISABLE_FIRST_ADMIN` | 設 `1` 關閉「第一個註冊帳號自動成為 admin」 |
| LLM 與生圖 | `OPENROUTER_API_KEY` / `OPENROUTER_MODELS` | 第 6 步選件 agent 與第 8 步內建生圖共用；留空則選件走本地規則 |
| | `ROOMPILOT_RENDER_IMAGE_MODEL` | 第 8 步生圖模型，預設 `google/gemini-2.5-flash-image` |
| | `ROOMPILOT_RENDER_PROVIDER_URL` / `_TOKEN` | 自訂遠端渲染服務；設定後優先於內建生圖 |
| RAG | `ROOMPILOT_RAG_ENABLED` / `ROOMPILOT_RAG_PARSER_PROVIDER` | 開關與需求解析 provider（`openrouter` / `openai` / `anthropic`） |
| 工程報告 | `ROOMPILOT_DEMO_MODE` | 預設 `false`：缺報價或工率的項目保持待確認，不臆測數值；只有流程展示才設 `true` |
| | `ROOMPILOT_ARTIFACT_NODE` / `ROOMPILOT_ARTIFACT_TOOL_MODULES` | XLSX 匯出用的 Node 與 adapter 路徑 |

## 帳戶與權限

- 八步流程之前需要登入：`/login` 註冊或登入後進入 `/projects`（我的專案），再建立或開啟專案。
- 第一個註冊的帳號自動成為 `admin`，並收養帳戶端上線前建立的既有專案。
  正式部署請在開放註冊前先建 admin，或設 `ROOMPILOT_AUTH_DISABLE_FIRST_ADMIN=1`。
- 角色：`designer` 建立與編輯專案、鎖版出報告；`client` 只檢視被分享的專案；`admin` 可跨帳號維運。
- 專案可分享給其他帳號，成員角色為 `editor`（可編輯）或 `viewer`（唯讀）。
- 改密碼：「我的專案」頁的帳號設定；成功後撤銷所有既有 session。
- 忘記密碼：由 admin 以 `POST /api/auth/admin/reset-password` 設臨時密碼並告知，登入後自行修改。
- 停用帳號：admin 以 `POST /api/auth/admin/set-active` 停用／恢復；停用立即生效，不能停用自己。

簽章金鑰請在 `.env` 明確設定，否則每個節點會各自產生一把，token 無法跨節點驗證：

```dotenv
ROOMPILOT_AUTH_SECRET=用 python -c "import secrets;print(secrets.token_urlsafe(48))" 產生
ROOMPILOT_AUTH_ACCESS_TTL_MINUTES=30
ROOMPILOT_AUTH_REFRESH_TTL_DAYS=14
```

PostgreSQL 專案儲存需先套用使用者與成員資料表：

```powershell
psql -U postgres -d roompilot_db -f scripts/project_store/roompilot_project_store_schema.sql
```

## 家具資料與 PostgreSQL

- 第 6 步讀取 PostgreSQL view `roompilot.furniture_catalog_current`：7,958 筆啟用家具
  （`furniture_items` 共 8,557 筆，599 筆因品質標記 `is_active = false` 不進 view）。
- 每筆家具都有 CloudFront 交付的 GLB 與正面、側面、45 度三視角 PNG，
  以及房間類型、風格、材質、尺寸與 VLM／RAG 說明。
- 燈具另走 `roompilot.lighting_assets`（`lighting_assets_current` 637 筆可用）。
- `JSON/furniture/furniture_official_catagory.json` 為同一份 8,557 筆的離線備援，
  只在明確設定 `ROOMPILOT_CATALOG_PROVIDER=json` 時使用。
- 未匹配或隔離資料不會出現在 API、Agent 候選或 3D 場景。

匯入正式型錄（先 dry-run，再正式執行）：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py
```

匯入採 transaction 與 UPSERT，預設不刪除其他資料。需要完整重建家具 tables／views／staging 時，
先通過 dry-run，再使用 `--replace-existing`（只影響家具型錄，不動 project、render 或 runtime catalog），
完成後重新匯入家具向量。安裝與驗收細節見
[PostgreSQL 17.10 安裝與資料匯入指南](scripts/sql/PostgreSQL%2017.10%20安裝與資料匯入指南.md)。

Phase 1～5 的資料契約（讀取、CRUD、專案儲存、runtime catalog、單一來源）與 RAG 相關契約
都在 [`docs/contracts/`](docs/contracts/)。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

只跑平面圖辨識：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py
```

只跑網頁流程與專案恢復：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_scene_workflow.py tests/test_project_workflow_api.py tests/test_scene_v2_contract.py
```

需要 PostgreSQL 的 live 測試以 `run_postgres_live_tests.ps1` 執行。

## 專案結構

| 路徑 | 用途 |
|---|---|
| `backend/server/` | FastAPI、專案持久化、帳戶、八步流程、渲染與工程文件（`engineering/`） |
| `frontend/` | 正式前端：登入、我的專案、八步場景、RAG 與工程文件頁 |
| `backend/floorplan/` | 平面圖辨識、房型語意層與確認 |
| `backend/spatial_data/` | 空間關係與 layout evaluation |
| `backend/agent/` | 需求結構化、選件、排序與說明 |
| `backend/catalog/` | 家具、材質、風格卡與 PostgreSQL／CloudFront 型錄 |
| `backend/engine/` | 幾何擺放、碰撞、淨空與合法性 |
| `backend/upgrade3d/` | 已確認格局轉 3D 幾何 |
| `rag/` | 家具 RAG 管線與 VLM 標註 |
| `JSON/` | 型錄、manifest 與家具向量交接資料 |
| `scripts/sql/`、`scripts/project_store/`、`scripts/runtime_catalog/` | PostgreSQL schema、匯入與遷移 |
| `tools/artifact_tool_local/` | 第 9 步 XLSX 匯出的本機 adapter |
| `testdata/` | 辨識測資與 ground truth |
| `tests/` | 單元、API、契約與視覺回歸測試 |
| `docs/` | 契約、架構、部署與團隊文件 |

## 資料契約

- 跨模組長度與座標使用公分，新欄位以 `_cm` 結尾；面積使用 `_m2`。
- 相容欄位 `width`、`depth`、`pos_x`、`pos_y` 必須搭配 `coordinate_unit: "cm"` 與 schema version。
- 平面圖辨識輸出是 `layout_json`；方案生成與編輯輸出是 `scene_json`。
- 家具是否合法只能由 `backend/engine/` 判斷。
- 正式前端只有 `frontend/` 一套。

主要契約：

- [Layout 與 Scene 邊界](docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md)
- [Agent 前後端契約](docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)
- [家具模型交付](docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md)
- [StylePack 渲染](docs/contracts/STYLEPACK_RENDERING_CONTRACT.md)
- [遠端渲染](docs/contracts/REMOTE_RENDER_CONTRACT.md)
- [工程文件](docs/contracts/ENGINEERING_DOCUMENT_MVP.md)（machine-readable 版本可用
  `python -m backend.server.engineering.export_contracts` 重建）

## 團隊與模組分工

| 成員 | 主要模組 | 負責功能 |
|---|---|---|
| Bella | `backend/server/`、`frontend/` | FastAPI、專案、八步流程、2D/3D UI、整合 |
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | PNG/DXF、牆門窗房間辨識、`layout_json` |
| Django | `backend/spatial_data/` | 房間尺寸、面積、關係、layout evaluation、RAG 關係 |
| Kai | `backend/catalog/`、`JSON/`、`scripts/sql/` | 家具型錄、AWS/CloudFront、Manifest、PostgreSQL |
| Yen | `backend/agent/` | 需求結構化、選件、排序、修復意圖與說明 |
| Ancai | `backend/engine/` | 家具座標、碰撞、淨空、移動與合法性 |
| Ben | `testdata/`、評估與文件 | 辨識資料 QA、模型評估、整合與版本證據 |

協作規範、跨模組修改流程與各成員的 owner 文件見
[AGENTS.md](AGENTS.md)、[CLAUDE.md](CLAUDE.md) 與
[團隊 AI 責任與整合架構](docs/TEAM_AI_OWNERSHIP.md)。

## 套件版本

Python baseline（實測於 Python 3.12.13）：FastAPI 0.140.0、Uvicorn 0.51.0、
Shapely 2.1.2、NumPy 2.5.1、OpenCV 4.13.0.92、ezdxf 1.4.4、Pillow 12.3.0、pytest 9.1.1。
完整清單以 [requirements.txt](requirements.txt) 為準；選配 extra 由 `pyproject.toml` 與 `uv.lock` 管理。

## 授權

本專案採 [GNU General Public License v3.0](LICENSE)。
