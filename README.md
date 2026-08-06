# RoomPilot-Agent

RoomPilot 是 AIPE03 第四組的 AI 室內設計系統。它把平面圖辨識、人工
校正、逐房需求、家具資料庫、幾何配置、2D/3D 編輯、方案視角與 AI
渲染整合成一個可恢復的網頁流程。

## 快速啟動

需求：

- Windows 10/11 64-bit
- Python 3.12
- Git
- Node.js 24 與 npm 11 只供 `frontend3d/` 次要原型使用
- PostgreSQL 17：第 6 步正式家具 catalog 的優先資料來源

### 方式一：Python venv 與 requirements.txt

在 repo 根目錄開啟 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

開啟 <http://127.0.0.1:8002>。

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
<http://127.0.0.1:8002/rag>。BGE-M3 與 reranker 約需 4.6 GB 常駐記憶體；
伺服器只會 lazy-load 已快取的模型，不會在請求期間自動下載。

OCR 套件較大，且不是啟動網站或執行目前標準測試的必要條件。

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
-> 5 完成全屋與逐房問卷、家具需求與三張風格色卡
-> 6 產生並確認單一配置，同步預覽 2D/3D；牆面與地面材質以房間為單位調整
-> 7 為每房產生三個綁定 room_id 的全室候選視角，逐房選定後一次鎖定
-> 8 AI 渲染與成果包：先確認依問卷與 RAG 組成的大致生圖詞彙，完成全屋初稿後，每張房間初稿各限一次成功修圖
   -> 確認全部房間後，產生逐房裝潢簡報、工程報告、資安審核與家具／裝潢預算明細
```

未處理的家具碰撞、淨空、超界或模型載入問題會阻擋下一步。結構變更
必須回到第 4 步，系統會重新驗證目前家具。

第 6 步只保存一份 `configuration_snapshot`，正式 UI 不公開 A／B 方案。第 7 步
候選視角必須位於對應房間並呈現全室，不會改寫家具配置；第 8 步修圖只修改使用者
指定的房間圖片，生圖失敗不消耗每房一次的修圖額度。送出前會提醒使用者不得改變
空間尺寸、牆、門窗、固定家具與鎖定視角。設計師姓名只可作為方法論參照並附上非本人背書聲明；無可靠
單價的項目一律標記「待報價」，不得補猜金額。

### 現行接線狀態

| 能力 | 狀態 | 現行入口／限制 |
|---|---|---|
| 第 5 步家具 RAG | 已實作 | 正式前端呼叫 `/api/rag/search/jobs`；只負責檢索與排序，不決定座標 |
| Yen `GenPicAgent` | 已實作 | `backend/server/ai_render_service.py` 直接呼叫，需設定 `OPENROUTER_API_KEY` |
| Yen `RequirementSkill`／`MasterAgent` | 待整合 | 模組與測試存在，但正式 FastAPI 八步流程尚未呼叫 |
| Yen `ReportAgent` | 待整合 | 模組與 PDF 工具存在，但 `/design-delivery` 尚未使用它 |
| Web／JSON 成果包 | 已實作 | `/design-delivery` 以 deterministic builder 產生逐房簡報、工程與預算資料 |
| 資安檢查 | 部分實作 | 目前依敏感欄位名稱 denylist 遞迴移除；不是完整 whitelist，也不是最終專業資安審查 |

目前第 7、8 步的主要 API：

```text
GET  /api/ai-render/status
POST /api/projects/{project_id}/ai-renders
POST /api/projects/{project_id}/ai-renders/{room_id}/edit
POST /api/projects/{project_id}/design-delivery
```

`/render-jobs` 是相容舊資料的 legacy 路徑，不是現行八步流程的主要入口。

### 生圖 provider 啟用條件

| 路徑 | 啟用條件 | 未設定時 |
|---|---|---|
| 現行 Step 8 `/ai-renders`、`/edit` | 伺服器有非空 `OPENROUTER_API_KEY`；模型可用 `ROOMPILOT_GENPIC_MODEL` 與 `ROOMPILOT_GENPIC_FALLBACK_MODEL` 覆寫 | `GET /api/ai-render/status` 回 `configured=false`，送出生圖回 503 |
| Legacy `/render-jobs` | `ROOMPILOT_RENDER_PROVIDER_URL` 非空；token 視 provider 需求設定 | `GET /api/render-provider/status` 回 `configured=false`，送出 legacy job 回 503 |

兩條設定互不替代。只設定 legacy URL 不會啟用現行 Step 8；只設定
`OPENROUTER_API_KEY` 也不代表 legacy `/render-jobs` 已啟用。金鑰只放伺服器環境，
不得送到瀏覽器或成果包。

## 第 8 步交付報告

全部房間完成首次生圖與必要修圖後，主服務由
`POST /api/projects/{project_id}/design-delivery` 直接讀取同一份 project state，輸出：

- 逐房裝潢簡報與設計說明。
- 設計師方法論參照與「非本人參與／背書」聲明。
- 每房工程內容、完成狀態與待現場確認事項。
- 敏感欄位名稱 denylist 掃描與移除結果；目前不得宣稱完整 whitelist 審核。
- 家具、裝潢費用明細；可信價格列參考小計，缺價保留 `pending_quote`／待報價。
- 可下載的 JSON 成果包。

目前正式 UI 第一版是 Web + JSON，repository 沒有獨立 `/engineering` 頁、XLSX
Adapter 或 `backend.server.engineering.export_contracts`。AI 不得引用舊文件恢復這些
不存在的入口。詳細狀態見[現行版本總覽](docs/RoomPilot_現行版本總覽.md)與
[第 6–8 步 Yen Agent 執行與驗證契約](docs/contracts/BELLA_6_8_YEN_AGENT_EXECUTION_AND_VERIFICATION.md)。

## 系統架構

```text
瀏覽器 HTML/CSS/JavaScript/Three.js
  <-> Bella FastAPI API 與八步狀態機
      -> SQLite ProjectStore（目前 project／workflow／render 的實際持久層）
      -> Cody 平面圖辨識
      -> Django 空間關係與 layout evaluation
      -> layout_json
      -> 第 5 步家具 RAG jobs（已接線）；Yen RequirementSkill 專業化 adapter 待整合
      -> Kai catalog / AWS / PostgreSQL / 關係檢索
      -> Ancai 幾何配置、碰撞與淨空
      -> 單一 configuration_snapshot / scene_json
      -> Yen 第 7 步逐房視角候選與第 8 步 GenPic
      -> Bella 2D/3D 編輯、逐房一次修圖與 deterministic design-delivery 組稿
      -> Yen ReportAgent：模組已存在，尚未接入正式成果包端點
```

原八步流程的 Graph RAG 邊界維持不變。設計師鎖定後的工程文件功能另採
Advanced RAG（Structured Retrieval + 可替換的 Vector Retriever Adapter），
不使用 Neo4j；目前工程 Vector Adapter 為明示的 Mock／Noop，不得宣稱為真實
Vector Retrieval。幾何、碰撞、淨空或結構合法性仍只由既有 Engine／Rule 邊界處理。

## 團隊責任

| 分支／人員 | 主要路徑 | 功能 |
|---|---|---|
| Bella | `backend/server/`, `backend/server/static/` | FastAPI、SQLite 專案保存、八步 UI、2D/3D、渲染與最終交付整合 |
| Cody | `backend/floorplan/`, `backend/upgrade3d/` | PNG/DXF、牆門窗房間辨識、`layout_json` |
| Django | `backend/spatial_data/`, floorplan spatial helpers | 房間尺寸、面積、關係、layout evaluation 與可追溯 RAG 證據 |
| Kai | `backend/catalog/`, `JSON/`, `scripts/sql/` | 家具型錄、AWS/CloudFront、Manifest、PostgreSQL |
| Yen | `backend/agent/` | 專業化問卷、選件、內部候選評估、逐房視角、生圖／修圖與報告文字 |
| Ancai | `backend/engine/` | 家具座標、碰撞、淨空、移動與合法性 |
| Ben | `testdata/`, evaluation/docs support | 辨識資料 QA、模型評估與版本證據 |

AI 或新成員開始修改前，必須依序閱讀：

1. [AGENTS.md](AGENTS.md)
2. [CLAUDE.md](CLAUDE.md)
3. [現行版本總覽](docs/RoomPilot_現行版本總覽.md)
4. [使用者流程與系統架構圖](docs/使用者流程與系統架構圖.md)
5. [團隊 AI ownership 與架構](docs/TEAM_AI_OWNERSHIP.md)
6. `docs/owners/` 內對應成員檔案
7. 目標資料夾內的 `AGENTS.md` 與相關 `docs/contracts/`

跨資料夾修改前必須列出雙方 owner、資料契約、修改原因與兩側測試。

## 主要資料夾

| 路徑 | 用途 |
|---|---|
| `backend/agent/` | 需求與家具決策 |
| `backend/catalog/` | 家具、材質與正式雲端 catalog |
| `backend/engine/` | 幾何擺放與驗證 |
| `backend/floorplan/` | 平面圖辨識與確認 |
| `backend/spatial_data/` | 空間關係與 evaluation 的共享邊界 |
| `backend/server/` | 正式 FastAPI 與 production frontend |
| `backend/upgrade3d/` | 已確認格局轉 3D 幾何 |
| `frontend3d/` | 次要 React/R3F 原型 |
| `JSON/` | Catalog/manifest 交接資料 |
| `scripts/sql/` | PostgreSQL schema 與匯入 |
| `testdata/` | 小型辨識測資與 ground truth |
| `tests/` | 單元、API、契約與視覺回歸測試 |
| `docs/contracts/` | 跨模組資料契約 |

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

- 2026-08-06 live runtime：`roompilot.furniture_catalog_current` 對外提供 7,958 筆家具，7,958 筆皆有 CloudFront GLB 與正面、側面、45 度圖，共 23,874 張圖片
- `/api/rag/status` 同步驗證 7,958 筆 current BGE-M3 向量；家具 API、RAG 與第 6 步必須使用同一組 current ID
- 舊匯入契約中的 8,675／8,076 是歷史上游批次，不是目前服務 readiness 數；JSON 只供明確指定的離線開發模式使用
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

Phase 2 的歷史實作包含受 Bearer token 保護的家具管理 CRUD、transaction、版本衝突
檢查、軟刪除、啟用門檻與 audit；目前 repository 沒有原先引用的
`POSTGRESQL_CATALOG_CRUD_PHASE2.md`，不得把不存在的文件當成操作手冊。可執行狀態與
現存契約以 [SQL／RAG 契約索引](docs/contracts/README.md) 為準。

Phase 3 文件記錄 PostgreSQL project store 的遷移目標與歷史 adapter；目前主程式仍直接
建立 `backend/server/project_store.py` 的 SQLite `ProjectStore`，且尚未依
`ROOMPILOT_PROJECT_STORE_PROVIDER` 切換 provider。因此 project、workflow 與 render
metadata 的現行持久層仍是 SQLite，不得宣稱已完成 PostgreSQL 搬遷。目標保存與
rollback 契約見
[`docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md`](docs/contracts/POSTGRESQL_PROJECT_STORE_PHASE3.md)。

Phase 4 已將 18 張風格色卡、571 筆 surface material、6 筆裝修費率與 10,518 筆 external quarantine 匯入 PostgreSQL。問卷定義仍保留版控 JSON／Python，問卷答案沿用 Phase 3 project JSONB；RAG 只讀 595 筆正式 style/material/cost 文件並排除 quarantine。完整流程見
[`docs/contracts/POSTGRESQL_RUNTIME_CATALOG_PHASE4.md`](docs/contracts/POSTGRESQL_RUNTIME_CATALOG_PHASE4.md)。

Phase 5 已移除正式 catalog 雙來源與 process-lifetime 資料 cache：provider 未設定時也預設 strict PostgreSQL，正式 status 不再讀 manifest CSV，重新匯入後下一次 API 請求即可看見新資料。現行主程式沒有 `/api/health`；家具與 runtime 狀態請用 `GET /api/catalog/status`，AI 生圖狀態請用 `GET /api/ai-render/status`。完整契約與尚未完成的 readiness 目標見
[`docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md`](docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md)。

目前 repository 的 `scripts/` 只保留家具 catalog 與家具向量匯入工具。
`scripts/project_store/`、`scripts/runtime_catalog/` 的 schema／migration／importer 不在
目前工具樹；新環境不可宣稱能由本 repo 從零重建 Phase 3／4。若要把主流程的
ProjectStore 遷移到 PostgreSQL，必須先補齊 runtime provider 接線、migration、rollback
與 API 回歸測試。

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
