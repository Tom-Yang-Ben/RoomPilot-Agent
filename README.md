# RoomPilot-Agent

RoomPilot 是 AIPE03 第四組的 AI 室內設計系統。它把平面圖辨識、人工
校正、逐房需求、家具資料庫、幾何配置、2D/3D 編輯、方案視角與 AI
渲染整合成一個可恢復的網頁流程。

## 快速啟動

### 方式零：Docker（最少前置，推薦給新環境）

只需要 Docker Desktop，不必裝 Python、Node 或 PostgreSQL：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }   # 然後填 DB_PASSWORD
docker compose up -d --build
```

開 [http://127.0.0.1:8002](http://127.0.0.1:8002)。首次啟動會自動還原完整資料庫
（8,675 筆家具 + 8,076 筆向量）。改 `backend/` 的程式碼或 `static/` 的前端檔案會自動
生效，不必 rebuild。

依功能拆成五個容器：`db`（PostgreSQL + pgvector）、`web`（FastAPI + 八步前端）、
`chromium`（第 8 步 PDF 排版）、`rag`（BGE-M3，`--profile rag`）、
`frontend`（Vite 原型，`--profile frontend`）。拆解依據、熱重載機制與已知陷阱見
[`docker/README.md`](docker/README.md)。

以下是不用 Docker 的原生安裝方式。

### 原生安裝需求：

- Windows 10/11 64-bit
- Python 3.12
- Git
- Node.js 24 與 npm 11 供工程文件 XLSX Adapter；也供 `frontend3d/` 原型使用
- PostgreSQL 17：第 6 步正式家具 catalog 的優先資料來源
- Linux 使用者需先安裝 [uv](https://docs.astral.sh/uv/)（一鍵安裝的 Linux 路徑用它建環境）

### 一鍵安裝（推薦）

`install.ps1` / `install.sh` 會裝齊全部依賴：`requirements.txt`
（server/vision/catalog/RAG/tests）＋ OCR ＋ 交付 PDF（playwright/pikepdf）＋
Playwright Chromium ＋ `frontend/` npm。

Windows（pip）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Windows（uv，較快，需先裝 uv）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uv
```

Linux（uv）：

```bash
bash install.sh
```

選項（預設全裝）：`-SkipOCR` / `-SkipFrontend`（Linux 對應 `--skip-ocr` /
`--skip-frontend`）。不含 RAG 模型快取（約 9 GB），需要時見下方「家具 RAG」段落。

安裝完成後，腳本會印出啟動指令；首次啟動前先複製環境檔：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

需要逐步手動安裝時，用下列任一方式。

### 方式一：Python venv 與 requirements.txt

在 repo 根目錄開啟 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

開啟 [http://127.0.0.1:8002](http://127.0.0.1:8002)。

如果 `8002` 已占用，把指令改成 `--port 8023` 或其他未使用連接埠。
若既有 `.venv\Scripts\python.exe` 指向已移除的舊 Python 路徑，先把
舊 `.venv` 重新命名備份，再執行上面的建立指令。

### 方式二：uv

日常開發不含大型 OCR：

```powershell
uv sync --extra server --extra vision --extra catalog --group dev
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

需要 PaddleOCR 時，使用完整環境：

```powershell
uv sync --extra server --extra vision --extra catalog --extra ocr --group dev
```

使用 pip 的 OCR 鎖定版本：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

家具 RAG 測試頁使用獨立的大型依賴與 repo 外模型快取：

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-rag.txt
.\.venv\Scripts\python.exe scripts/rag/prefetch_models.py
# 上一行只檢查；確認約 9 GB 空間後才執行下載：
.\.venv\Scripts\python.exe scripts/rag/prefetch_models.py --download
```

在 `.env` 設定 `ROOMPILOT_RAG_ENABLED=true`、
`ROOMPILOT_RAG_PARSER_PROVIDER=openai|anthropic`，並只填所選 provider 的
`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` 後，開啟
[http://127.0.0.1:8002/rag](http://127.0.0.1:8002/rag)。BGE-M3 與 reranker 約需 4.6 GB 常駐記憶體；
伺服器只會 lazy-load 已快取的模型，不會在請求期間自動下載。

OCR 套件較大，且不是啟動網站或執行目前標準測試的必要條件。

第 8 步「產出設計提案」需要 Playwright Chromium 排版引擎；未安裝時回 503
並附安裝指引：

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-delivery.txt
.venv\Scripts\playwright.exe install chromium
```

## 驗證指令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

平面圖辨識：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py
```

網頁流程與專案恢復：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_scene_workflow.py tests/test_project_workflow_api.py tests/test_scene_v2_contract.py
```

## 現行八步流程

```text
1 建立專案
-> 2 上傳 PNG/JPG/DXF 平面圖
-> 3 兩點標定並確認公分尺度
-> 4 校正空間、牆、門、窗、樑與柱
-> 5 完成逐房極與極問卷、家具需求與三張風格色卡
-> 6 產生配置，在同一畫面同步編輯 2D/3D 家具與走動預覽
-> 7 鎖定方案，每個空間選擇並微調生成視角
-> 8 AI 渲染與成果包：依問卷、家具、材質、色卡與視角產生逐房成果，
   並由 Report Agent 統整輸出設計提案 PDF
   （roompilot-delivery-pdf 品牌排版）
```

未處理的家具碰撞、淨空、超界或模型載入問題會阻擋下一步。結構變更
必須回到第 4 步，系統會重新驗證目前家具。

## 設計師鎖定後的工程文件 MVP

正式設計頁右上角「估」或以下網址可進入工程文件頁：

```text
http://127.0.0.1:8002/engineering?project_id=<project_id>
```

流程為：現有 project state → 前端 ProjectSnapshot Adapter → 保存 Draft →
設計師鎖定 D-revision → Quantity／Rule／Advanced RAG／Cost／Schedule →
同一份 ReportPayload 產生 HTML、XLSX、JSON。鎖定後不可覆寫；設計內容變更後
需保存新的 project revision。未鎖定時生成 API 回傳
`409 REVISION_NOT_LOCKED`。

正式模式是預設值：

```dotenv
ROOMPILOT_DEMO_MODE=false
```

正式模式缺單價或工率時保留 `pending_quote`／待確認，不補猜總價。只有流程展示
才可設 `ROOMPILOT_DEMO_MODE=true`；頁面與文件會醒目標示「示範資料，非正式報價」。
XLSX 由 `@oai/artifact-tool` 產生；Node 無法直接解析套件時，在 `.env` 設定其
`node_modules` 絕對路徑：

```dotenv
ROOMPILOT_ARTIFACT_NODE=node
ROOMPILOT_ARTIFACT_TOOL_MODULES=C:\path\to\node_modules
ROOMPILOT_XLSX_TIMEOUT_SECONDS=90
```

詳細 API、欄位映射、資料責任與輸出契約見
[工程文件 MVP 契約](docs/contracts/ENGINEERING_DOCUMENT_MVP.md)與
[現有專案整合報告](docs/PROJECT_INTEGRATION_REPORT.md)。Machine-readable 契約可用
`python -m backend.server.engineering.export_contracts` 從現行 Pydantic／FastAPI 重建。

## 系統架構

```text
瀏覽器 HTML/CSS/JavaScript/Three.js
  <-> FastAPI API 與專案持久化
      -> Cody 平面圖辨識
      -> Django 空間關係與 layout evaluation
      -> layout_json
      -> Yen 需求解析與家具選擇
      -> Kai catalog / AWS / PostgreSQL / 關係檢索
      -> Ancai 幾何配置、碰撞與淨空
      -> scene_json
      -> Bella 2D/3D 編輯、方案與渲染流程
```

原八步流程的 Graph RAG 邊界維持不變。設計師鎖定後的工程文件功能另採
Advanced RAG（Structured Retrieval + 可替換的 Vector Retriever Adapter），
不使用 Neo4j；目前工程 Vector Adapter 為明示的 Mock／Noop，不得宣稱為真實
Vector Retrieval。幾何、碰撞、淨空或結構合法性仍只由既有 Engine／Rule 邊界處理。

## 團隊責任

| 分支／人員 | 主要路徑                                             | 功能                                              |
| ---------- | ---------------------------------------------------- | ------------------------------------------------- |
| Bella      | `backend/server/`, `backend/server/static/`      | FastAPI、專案、八步流程、2D/3D UI、整合           |
| Cody       | `backend/floorplan/`, `backend/upgrade3d/`       | PNG/DXF、牆門窗房間辨識、`layout_json`          |
| Django     | `backend/spatial_data/`, floorplan spatial helpers | 房間尺寸、面積、關係、layout evaluation、RAG 關係 |
| Kai        | `backend/catalog/`, `JSON/`, `scripts/sql/`    | 家具型錄、AWS/CloudFront、Manifest、PostgreSQL    |
| Yen        | `backend/agent/`                                   | 需求結構化、選件、排序、修復意圖與說明            |
| Ancai      | `backend/engine/`                                  | 家具座標、碰撞、淨空、移動與合法性                |
| Ben        | `testdata/`, evaluation/docs support               | 辨識資料 QA、模型評估與版本證據                   |

AI 或新成員開始修改前，必須依序閱讀：

1. [AGENTS.md](AGENTS.md)
2. [CLAUDE.md](CLAUDE.md)
3. [團隊 AI ownership 與架構](docs/TEAM_AI_OWNERSHIP.md)
4. `docs/owners/` 內對應成員檔案
5. 目標資料夾內的 `AGENTS.md`
6. 相關 `docs/contracts/`
7. 需要需求、架構、QA、交付或平行協作工作流時，使用 [RoomPilot Workflow Max Codex skill](.agents/skills/roompilot-workflow-max/SKILL.md)

跨資料夾修改前必須列出雙方 owner、資料契約、修改原因與兩側測試。

## 主要資料夾

| 路徑                                       | 用途                                                                                                   |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `backend/agent/`                         | 需求與家具決策                                                                                         |
| `backend/catalog/`                       | 家具、材質與正式雲端 catalog                                                                           |
| `backend/engine/`                        | 幾何擺放與驗證                                                                                         |
| `backend/floorplan/`                     | 平面圖辨識與確認                                                                                       |
| `backend/spatial_data/`                  | 空間關係與 evaluation 的共享邊界                                                                       |
| `backend/server/`                        | 正式 FastAPI 與 production frontend                                                                    |
| `backend/upgrade3d/`                     | 已確認格局轉 3D 幾何                                                                                   |
| `frontend3d/`                            | 次要 React/R3F 原型                                                                                    |
| `JSON/`                                  | Catalog/manifest 交接資料                                                                              |
| `scripts/sql/`                           | PostgreSQL schema 與匯入                                                                               |
| `testdata/`                              | 小型辨識測資與 ground truth                                                                            |
| `tests/`                                 | 單元、API、契約與視覺回歸測試                                                                          |
| `docs/contracts/`                        | 跨模組資料契約                                                                                         |
| `.agents/skills/roompilot-workflow-max/` | 由 VibeCoding 01–17 與`.claude` 安全轉換的 RoomPilot Codex 工作流、模板、來源清單與最大平行協作規則 |

## 關鍵資料契約

- 跨模組長度與座標使用公分，新欄位以 `_cm` 結尾。
- 面積使用 `_m2`。
- 相容欄位 `width`, `depth`, `pos_x`, `pos_y` 必須搭配
  `coordinate_unit: "cm"` 和 schema version。
- 平面圖辨識輸出是 `layout_json`。
- 方案生成與編輯輸出是 `scene_json`。
- 家具是否合法只能由 `backend/engine/` 判斷。
- Production frontend 位於 `backend/server/static/`；`frontend3d/` 不是
  第二套正式流程。

更多契約：

- [Layout 與 Scene 邊界](docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md)
- [Agent 前後端契約](docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)
- [家具模型交付](docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md)
- [StylePack 渲染](docs/contracts/STYLEPACK_RENDERING_CONTRACT.md)

## 家具資料與 PostgreSQL

正式雲端 catalog 由 Kai 的資料流維護：

SQL／RAG 契約的現行狀態與可執行入口統一列在
[SQL／RAG 契約索引](docs/contracts/README.md)。

- PostgreSQL 正式 catalog 共 8,675 筆家具；`roompilot.furniture_catalog_api_current` 只提供其中 8,076 筆 active／RAG-indexable 家具，另有 599 筆 inactive 家具保留複核且不得進正式 API／RAG
- 8,675 筆家具各有 CloudFront GLB，三視角圖片共 26,025 張（正面、側面、45 度）
- JSON 備援 catalog 同為 8,675 筆，僅供明確指定的離線開發模式使用；公開家具仍只限 8,076 筆 active 資料
- 家電問卷需求會保留給 AI 生圖，不會進入第 6 步 2D/3D 擺設

先建立 `.env`：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=postgres
DB_PASSWORD=安裝 PostgreSQL 時自行設定的密碼
ROOMPILOT_CATALOG_PROVIDER=postgres
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=postgres
```

正式 `postgres` 模式若資料庫不可連線，家具 API 會回傳 503，不會悄悄改讀
JSON。只有需要離線開發時，才在 `.env` 明確改成：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=json
```

Phase 1 的完整資料流、責任邊界、查詢參數與驗收方式見
[`docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md`](docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md)。

Phase 2 已加入受 Bearer token 保護的家具管理 CRUD、transaction、版本衝突檢查、軟刪除、啟用門檻與 audit。管理 API 預設不回傳 `raw_data`；完整操作流程見
[`docs/contracts/POSTGRESQL_CATALOG_CRUD_PHASE2.md`](docs/contracts/POSTGRESQL_CATALOG_CRUD_PHASE2.md)。

Phase 3 已將正式 project、workflow JSONB 與 render metadata 搬到 PostgreSQL，並保留 revision 409 衝突控制及一次性 SQLite migration；完整保存與 rollback 流程見
[`docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md`](docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md)。

Phase 4 已將 18 張風格色卡、571 筆 surface material、6 筆裝修費率與 10,518 筆 external quarantine 匯入 PostgreSQL。問卷定義仍保留版控 JSON／Python，問卷答案沿用 Phase 3 project JSONB；RAG 只讀 595 筆正式 style/material/cost 文件並排除 quarantine。完整流程見
[`docs/contracts/POSTGRESQL_RUNTIME_CATALOG_PHASE4.md`](docs/contracts/POSTGRESQL_RUNTIME_CATALOG_PHASE4.md)。

Phase 5 已移除正式 catalog 雙來源與 process-lifetime 資料 cache：provider 未設定時也預設 strict PostgreSQL，正式 status 不再讀 manifest CSV，重新匯入後下一次 API 請求即可看見新資料。`GET /api/health` 會驗證家具、runtime catalog 與 project table readiness；完整契約見
[`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md`](docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md)。

目前 repository 的 `scripts/` 只保留家具 catalog 與家具向量匯入工具。既有 PostgreSQL 的 project 與 runtime catalog read path 仍可使用，但 `scripts/project_store/`、`scripts/runtime_catalog/` 的 schema／migration／importer 不在目前工具樹；新環境不可宣稱能由本 repo 從零重建 Phase 3／4。

Dry-run：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
```

正式匯入：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py
```

匯入採 transaction 與 UPSERT，預設不刪除其他資料。需要完整重建家具 tables／views／staging 時，必須先通過 dry-run，經人工確認後使用 `--replace-existing`，並在完成後重新匯入家具向量。此選項不影響 project、render 或 runtime catalog。

目前的責任、資料流與家電邊界請看
[現行版本總覽](docs/RoomPilot_現行版本總覽.md) 與
[團隊 AI 責任與整合架構](docs/TEAM_AI_OWNERSHIP.md)。

## React/R3F 原型

正式網站不需要另開 frontend server。只有開發 `frontend3d/` 原型時：

```powershell
Set-Location frontend3d
npm.cmd ci
npm.cmd run dev
```

Build 驗證：

```powershell
npm.cmd run build
```

## 套件版本

Python baseline 經實際測試：

- Python `3.12.13`
- FastAPI `0.140.0`
- Uvicorn `0.51.0`
- Shapely `2.1.2`
- NumPy `2.5.1`
- OpenCV `4.13.0.92`
- ezdxf `1.4.4`
- Pillow `12.3.0`
- pytest `9.1.1`

完整 Python 直接依賴版本以 [requirements.txt](requirements.txt) 為準。
可選 OCR 版本由 `pyproject.toml` 與 `uv.lock` 管理。

`frontend3d/package-lock.json` 鎖定：

- React `18.3.1`
- React Three Fiber `8.18.0`
- Drei `9.122.0`
- Three.js `0.160.1`
- Vite `8.1.0`

## 版本控制與整合

```powershell
git fetch origin
git switch bella
git pull --ff-only origin bella
git switch -c integration/<owner>-<feature>
git diff --name-status bella...origin/<owner-branch>
git log --oneline bella..origin/<owner-branch>
```

只移植責任範圍內、符合現行契約的 commit。禁止以整份 ours/theirs
覆蓋衝突、建立第二套 FastAPI、搬入完整舊前端或提交大型模型。

不得提交：

- `.env` 或密碼
- `.runtime/` 專案資料
- `.tmp/` 與快取
- 大型 GLB、圖片包或模型權重
- 未驗證的 catalog 或自動標註結果
