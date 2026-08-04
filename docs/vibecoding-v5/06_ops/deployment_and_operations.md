# 部署與運維指南 - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 06_ops/deployment_and_operations.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04

**現況一句話：本專案目前沒有正式部署環境。** 後端以本機 uvicorn 單進程啟動；常態雲端元件是 CloudFront GLB 模型交付；PostgreSQL 17 已成為 `.env.example` 的預設資料來源（catalog／runtime catalog／專案保存三個 provider 預設皆 `postgres`，本機未匯入時明文改回 json/sqlite）。OpenRouter LLM、內建生圖與遠端渲染供應商為選用外部服務，未設定時以確定性 fallback 或 503 回應，不假成功。本文件保留模板章節骨架，機制不存在一律照實標「現況：無」，並把可查證的本機運維事實（啟動、環境變數、資料、日誌、備份）寫齊。

先行素材：`docs/vibecoding/14_deployment_and_operations_guide.md`（2026-07-26 對舊分支填寫）。該版的 44 條路由、無 `/api/health`、「伺服器執行期不連 Postgres」等事實已全數過期，本文件所有數字均對現行工作樹重查。

---

## 1. 部署架構

```
現況：Development（本機）only — 無 Staging、無 Production
```

實際執行拓撲（依 `backend/server/main.py`、`.env.example` 與 README 查證）：

```
瀏覽器 ─ http://127.0.0.1:8002 ─→ uvicorn 單進程（backend.server.main:app）
                                    ├─ 63 條 HTTP 路由：main.py 46 + rag_api.py 5
                                    │   + catalog_admin.py 4 + engineering/api.py 8
                                    ├─ 靜態掛載 /static、/docs-assets（main.py:285-286）
                                    ├─ GZipMiddleware minimum_size=1024（main.py:215）
                                    ├─ PostgreSQL（預設 provider；catalog 讀取、
                                    │   /api/admin/furniture 寫入、roompilot.projects 專案保存、
                                    │   Phase 4 runtime catalogs、RAG pgvector）
                                    ├─ SQLite .runtime/projects.sqlite3（WAL；
                                    │   ROOMPILOT_PROJECT_STORE_PROVIDER=sqlite 離線模式）
                                    └─ 檔案 .runtime/uploads/、renders/、engineering/
瀏覽器 ─ GLB 模型 ──────────────→ CloudFront https://ddgsm1yg3xikc.cloudfront.net
                                    （services/cloud_models.py:32 預設值）
選用外部服務（未設定即停用／503）：OpenRouter API（intake／場景規劃／選件／內建生圖）、
遠端渲染供應商（ROOMPILOT_RENDER_PROVIDER_URL）
XLSX 匯出 side-process：Node 執行 engineering/workbook_builder.mjs
```

### 基礎設施元件

| 元件 | 用途 | 現況（2026-08-04 實測） |
| :--- | :--- | :--- |
| 負載均衡 | 流量分配與故障轉移 | **無**；單機 uvicorn，無反向代理 |
| 應用伺服器 | 核心應用託管 | uvicorn 0.51.0 + FastAPI 0.140.0（requirements.txt 鎖版）；**無 Dockerfile、無容器化、無 Makefile**（repo 根 ls/find 實測） |
| 資料庫 | 資料持久化 | 雙模式：PostgreSQL 17 為 `.env.example` 預設（`ROOMPILOT_PROJECT_STORE_PROVIDER=postgres` → `roompilot.projects`；catalog 讀 `roompilot.furniture_catalog_current`）；程式碼層預設 sqlite（`project_store.py:605` 預設值 `"sqlite"`，由 `.env` 覆寫），SQLite 檔為 `.runtime/projects.sqlite3`（WAL，`project_store.py:107`）。連線池參數 DB_POOL_MIN/MAX/TIMEOUT 由 `.env` 控制，池滿排隊逾時回 503 busy 並附 `Retry-After: 2`（main.py:226-243） |
| 快取層 | 效能優化 | **無** Redis/Memcached；postgres 模式為 database read-through 不留 runtime 檔案快取、json 模式為明示離線檔案快取（`/api/catalog/status` 的 `cache_policy` 欄位，main.py:2495-2499）；啟動時僅 json 模式預熱進程內家具 payload（main.py:2821-2828） |
| CDN | 靜態資源交付 | CloudFront `https://ddgsm1yg3xikc.cloudfront.net` 交付 GLB（預設 manifest 為 `JSON/manifests/glb_upload_all_result.csv`，共 8,557 筆資料列、wc -l 8,558 行含表頭，與 `OFFICIAL_CATALOG_COUNT = 8_557` 同一母集合；路徑定義在 `main.py:144-147` 與 `services/cloud_models.py:26-31`，可用 `ROOMPILOT_GLB_MANIFEST_PATH` 覆寫。repo 另存在 `backend/catalog/data/manifests/glb_upload_all_result.csv`（9,351 行），但程式碼未引用）；網頁靜態資源不走 CDN，由 FastAPI `/static` 直出（含自帶 Three.js vendor，無 CDN 依賴） |
| 監控 | 健康檢查與告警 | 有 `GET /api/health`（main.py:2533，ready/formal 語意見第 5 節）與 5 個子系統狀態端點；**無外部監控、無告警** |
| 向量檢索 | 家具 RAG | pgvector（`backend/spatial_data/rag/`，BGE-M3 嵌入）；預設 `ROOMPILOT_RAG_ENABLED=false`，啟用需另裝 `requirements-rag.txt`（torch 2.13.0、sentence-transformers 5.6.1 等），模型權重放 repo 外（`ROOMPILOT_RAG_MODEL_CACHE`） |
| 文件產生 | 工程文件 MVP | `backend/server/engineering/`：XLSX 經 Node 子進程 `workbook_builder.mjs`（node 路徑 `ROOMPILOT_ARTIFACT_NODE`，逾時 `ROOMPILOT_XLSX_TIMEOUT_SECONDS` 預設 90，documents.py:142-164）；產出檔落在 `.runtime/engineering/` |
| 問卷視覺索引 | 第 5 步問卷視覺素材查詢 | 內嵌 SQLite `.runtime/indexes/questionnaire_visuals.sqlite3`（建立與 sync 於 `main.py:276-281`，由 `QuestionnaireVisualStore` 管理）；**資料真源是版控 JSON**（`backend/server/data/questionnaire_visual_catalog.json`），索引可刪除重建，不需備份 |
| 開發用前端原型 | frontend3d DXF 白模檢視 | Vite dev server + React Three Fiber（`frontend3d/`，次要原型）；只在開發者本機手動 `npm run dev` 啟動，proxy `/api` → `http://localhost:8002`（`vite.config.js:8`）；**不屬正式部署拓撲**，正式前端是 FastAPI `/static` 直出的六頁 |

### 開發環境需求（README「快速啟動」查證）

| 項目 | 需求 | 依據 |
| :--- | :--- | :--- |
| OS | README 以 Windows 10/11 64-bit 為基準（macOS/Linux 可跑但非 baseline 文件對象） | README「快速啟動」 |
| Python | 3.12（本機 .venv 實測 3.12.13） | README、requirements.txt 標頭 |
| PostgreSQL | 17：第 6 步正式家具 catalog 優先資料來源 | README「快速啟動」需求列 |
| 安裝方式一 | `pip install -r requirements.txt`（21 個鎖版 pin，依 owner 分 5 組） | README、requirements.txt |
| 安裝方式二 | `uv sync --extra server --extra vision --extra catalog --group dev`；OCR 加 `--extra ocr`、CubiCasa 語意房型加 `--extra semantic`（torch，缺它房型退回面積規則不會壞） | README |
| 選配需求檔 | `requirements-ocr.txt`（paddleocr 3.7.0 + paddlepaddle 3.3.1）、`requirements-rag.txt`（RAG runtime，皆 `-r requirements.txt` 疊加） | 兩檔案標頭 |
| Node.js | frontend3d 原型與工程文件 XLSX 匯出用（README 記 Node 24 + npm 11） | README、engineering/documents.py:142 |

### 後端啟動指令（README:30,46 查證）

```powershell
# repo 根目錄；.env 不存在時先 Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
# 或 uv：
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

啟動後開啟 <http://127.0.0.1:8002>。

- **port 未寫死在程式碼**：`main.py` 無 `__main__` 區塊（grep 實測），必須經 uvicorn；README 慣例 8002，被占用改 **8023**（README:35；舊文件的 8010/8014 已不是現行慣例）。
- 啟動 warmup：`@app.on_event("startup")` 只在 `ROOMPILOT_CATALOG_PROVIDER=json` 時預熱家具 payload 與站台資料，失敗印 `[RoomPilot] catalog cache warmup skipped: ...` 不擋啟動（main.py:2821-2828）；shutdown 時關閉 catalog 連線池與 PROJECT_STORE（main.py:2831-2834）。`on_event` 為 FastAPI 已棄用 API，pytest 有 DeprecationWarning（2026-08-04 實測仍在）。
- 模組載入時把舊 worktree 的 legacy `.runtime` 合併進共用資料庫（main.py:159-160 → `import_runtime`；`.runtime` 位置解析 `runtime_paths.py`，可用 `ROOMPILOT_RUNTIME_DIR` 覆寫）。

### 環境變數（grep `backend/` 字串常數去重實測 58 個鍵，`.env.example` 本身列 45 個 `KEY=` 項；下表依子系統分組，預設值以 `.env.example` 與程式碼為準）

`.env` 載入路徑：`services/cloud_models.py:24-25` 以 python-dotenv 讀 repo 根 `.env`（override=False）；`intake_service.py:23` 另讀 repo 根與 `backend/server/.env`；`spatial_data/rag/settings.py:24` 與 `catalog/postgres_repository.py` 自行解析 `.env` 檔。`.env` 被 `.gitignore` 排除，不進版控。

| 分組 | 主要變數（預設） | 用途 |
| :--- | :--- | :--- |
| 執行資料 | `ROOMPILOT_RUNTIME_DIR`（空=repo 根 `.runtime/`） | 覆寫執行資料目錄 |
| 家具資料來源 | `ROOMPILOT_CATALOG_PROVIDER`（**postgres**；json=離線）、`ROOMPILOT_CLOUD_CATALOG_PATH` | 第 6 步家具 metadata 來源；postgres 讀不到自動用已驗證 JSON 備援（README） |
| 模型交付 | `ROOMPILOT_MODEL_DELIVERY_MODE`（cloudfront）、`ROOMPILOT_CLOUDFRONT_BASE_URL`、`ROOMPILOT_GLB_MANIFEST_PATH`、`ROOMPILOT_IMAGE_MANIFEST_PATH`、`ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` | GLB／圖片交付。README 明示本機 IKEA GLB 備援**尚未完成**，完成前勿啟用 local 模式（舊版 `scripts/verify_ikea_offline_backup.py` 已不存在，ls scripts/ 實測） |
| 專案保存 | `ROOMPILOT_PROJECT_STORE_PROVIDER`（`.env.example`=postgres；程式碼預設 sqlite） | Phase 3：postgres 走 `roompilot.projects`，sqlite 走 `.runtime/projects.sqlite3`；無效值直接 raise，不靜默回退（project_store.py:603-611） |
| Runtime catalogs | `ROOMPILOT_RUNTIME_CATALOG_PROVIDER`（postgres 嚴格模式） | Phase 4 風格卡／表面材質／費率／quarantine；讀不到回 503，不靜默退回 JSON（`.env.example` 註解、runtime_catalog_repository.py） |
| PostgreSQL 連線 | `DB_HOST`/`DB_PORT`/`DB_NAME`(roompilot_db)/`DB_USER`/`DB_PASSWORD`/`DB_SSLMODE`/`DB_CONNECT_TIMEOUT`/`DB_APPLICATION_NAME`/`DB_PROJECT_APPLICATION_NAME`/`DB_POOL_MIN`(1)/`DB_POOL_MAX`(24)/`DB_POOL_TIMEOUT`(10)/`DB_PROJECT_POOL_MIN`/`DB_PROJECT_POOL_MAX` | 伺服器執行期與離線匯入器共用；池滿排隊逾時回 503 |
| 型錄管理寫入 | `ROOMPILOT_CATALOG_ADMIN_TOKEN`（空=停用） | `/api/admin/furniture` bearer token；未設回 503 `catalog_admin_not_configured`、token 不符回 401（catalog_admin.py:180-200，`secrets.compare_digest` 比對） |
| OpenRouter LLM | `OPENROUTER_API_KEY`、`OPENROUTER_MODELS`/`OPENROUTER_MODEL`、`OPENROUTER_SITE_URL`(http://127.0.0.1:8002)、`OPENROUTER_APP_NAME`(roompilot)、`OPENROUTER_INTAKE_ENABLED`、`OPENROUTER_SCENE_PLANNING_ENABLED`、`OPENROUTER_SELECTION_ENABLED`(1) | 引導式需求／場景規劃／第 6 步選件；未設金鑰走本地 deterministic fallback，選件輸出一律經候選白名單驗證 |
| 渲染 | `ROOMPILOT_RENDER_PROVIDER_URL`/`TOKEN`/`NAME`/`TIMEOUT_SECONDS`(60)、`ROOMPILOT_RENDER_IMAGE_MODEL`(google/gemini-2.5-flash-image)、`ROOMPILOT_RENDER_IMAGE_DISABLED` | 自訂遠端契約優先；否則內建 OpenRouter 生圖（render_providers.py，同步回圖入庫）；兩者皆無回 503 |
| 家具 RAG | `ROOMPILOT_RAG_ENABLED`(false)、`ROOMPILOT_RAG_PARSER_PROVIDER`(openai)、`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`、`ROOMPILOT_RAG_OPENAI_MODEL`/`ANTHROPIC_MODEL`/`PARSER_MODEL`/`REASONING_EFFORT`/`ANTHROPIC_MAX_TOKENS`/`TIMEOUT_SECONDS`(30)/`OPENAI_TIMEOUT_SECONDS`/`MODEL_CACHE`/`DEVICE`(auto) | `/api/rag/*`；BGE-M3 + pgvector，就緒守門檢查模型快取與 embeddings 表非空（rag/service.py:82-90） |
| 工程文件 | `ROOMPILOT_DEMO_MODE`(false)、`ROOMPILOT_ARTIFACT_NODE`(node)、`ROOMPILOT_ARTIFACT_TOOL_MODULES`、`ROOMPILOT_XLSX_TIMEOUT_SECONDS`(90) | demo_mode=false 為安全預設：缺報價／工時維持 pending 不臆測；price/productivity 為 DEMO_ONLY 合成資料不得當正式報價（`.env.example` 註解） |
| OCR | `ROOMPILOT_OCR_DISABLED`（=1 緊急停用） | 印刷房名／尺寸 OCR；未裝 paddle 自動安靜停用（main.py:171-174） |

---

## 2. CI/CD 流水線

**現況：無任何 CI/CD。** repo 無 `.github/`、無 Dockerfile、無 docker-compose、無 Makefile（2026-08-04 ls/find 實測）。實際流程是手動閘門：

| 階段 | 步驟（現況實際做法） |
| :--- | :--- |
| **建置** | 無編譯產物；裝依賴即完成（requirements.txt 或 uv extras，見第 1 節） |
| **測試** | `.\.venv\Scripts\python.exe -m pytest -q`（README:77、AGENTS.md:77「驗證指令」）。`pyproject.toml` 未設 `testpaths`，所以在 repo 根跑會同時收集 `tests/` 與 `training/`。2026-08-04 全量實測（macOS .venv Python 3.12.13）：repo 根 `pytest -q` = **3 failed, 916 passed, 9 skipped, 7 warnings, 93.40s**；只跑 `pytest -q tests` = **1 failed, 811 passed, 9 skipped, 7 warnings, 73.38s**。三個紅燈：`tests/test_scene_v2_contract.py::test_scene_entrypoint_cache_key_matches_bundle_content`（scene.html 引用的 scene_v2.js/site.css 內容雜湊過期——scene_v2.js 實測 `7d938e1fdc28` 對上 html 內 `27f24b6bede3`；雜湊為手動維護、無自動重算腳本）、`training/tests/test_annotation_drafts.py::test_house_round_trip`、`training/tests/test_room_office_stair.py::test_gt_label_separates_office_and_stairwell`，皆屬本 commit 既有紅燈。另有 `tests/static/` 3 支 Node `.test.mjs` 前端測試（pytest 不收集）與 `training/tests/` 11 支測試檔 |
| **整合閘門** | `git diff --check` + `git status --short`（README 驗證指令；AGENTS.md:76-80 最終整合三指令同此） |
| **部署** | 無部署動作；組員本機 `git pull` 後重啟 uvicorn（見第 3 節） |

待辦：

- [ ] 引入 CI 自動跑 pytest；repo 內無任何 CI 設定（實測），是否口頭規劃過（未查證）
- [ ] 發表用 demo 環境形態（本機 demo 或雲端部署）repo 內無定義文件（未查證）

---

## 3. 部署檢查清單

本專案「部署」= 組員本機更新到指定 commit 並重啟。以下依 README「版本控制與整合」與 AGENTS.md 驗證矩陣改寫：

### 更新前
- [ ] `pytest -q` 通過（現況基準：repo 根 916 過、3 敗、9 跳過；只跑 `tests/` 則 811 過、1 敗、9 跳過。敗者為既有雜湊契約紅燈與 2 支 training 紅燈，見第 2 節）
- [ ] `git diff --check` 無殘留衝突標記、`git status --short` 乾淨（不覆蓋他人未提交變更，AGENTS.md）
- [ ] 停止舊的 uvicorn 進程，避免驗到舊程式
- [ ] `.env` 對齊 `.env.example`：三個 provider（catalog／runtime catalog／project store）在本機 PostgreSQL 未匯入時明文改 json/sqlite，不留 postgres 讓端點吃 503

### 更新中
- [ ] `git fetch origin` → `git switch <目標分支>` → `git pull --ff-only origin <目標分支>`
- [ ] `git rev-parse --short HEAD` 確認 commit 與整合者宣布一致
- [ ] 重啟：`uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload`

### 更新後（煙霧測試）
- [ ] `GET /api/health`：`status` 為 `ready`（正式 postgres 模式）或 `offline`（明文 json/sqlite 離線模式）；`unavailable` + 503 = postgres 設定了但連不上，需先修資料庫或改離線模式
- [ ] `GET /api/catalog/status`：`catalog_provider`、`runtime_catalogs`、`cache_policy` 與預期 provider 一致
- [ ] 開啟 `/scene`：頁面帶 `Cache-Control: no-store`，JS 以內容雜湊防快取（注意本 commit scene.html 的 scene_v2.js/site.css 雜湊已過期；`/library` 的 library.html 其 library.js/site.css 雜湊同樣過期，但不在 pytest 契約覆蓋內。改前端後須手動更新 `?v=sha256-` 參數）
- [ ] 上傳 `floor04.png` 的辨識基準（未查證：現行 README 已無此驗收數字，舊版「19 面牆、5 扇門、5 扇窗、7 個房間」是否仍適用需向 Cody/Ben 確認）
- [ ] 注意：`project_id` 存於各機 `.runtime/` 或本機 PostgreSQL，**不能**拿另一台電腦的專案網址驗證程式版本

---

## 4. 部署策略

| 模板策略 | 本專案現況 |
| :--- | :--- |
| Blue-Green | 不適用；單機單進程，無第二套環境 |
| Rolling | 不適用；無多實例 |
| Canary | 不適用；無流量分配 |

實際策略：**更新即停機重啟**（短暫斷線；SQLite/PostgreSQL 與上傳檔持久化，重啟不掉資料）。版本控制即發佈控制：

- 遠端分支 17 條（`git branch -r` 實測，排除 origin/HEAD）：main、bella、bella-test1/2、ancai、ancai-dev、ben、ben-kai-migration、cody、cody-dev、django、django-RAG、django-skill、kai、kai-new、yen、Kai-Django-RAG-report。
- 整合流程（README「版本控制與整合」）：從 bella 開 `integration/<owner>-<feature>` 分支，`git diff --name-status bella...origin/<owner-branch>` 只移植責任範圍內、符合契約的 commit；禁止整份 ours/theirs 覆蓋、第二套 FastAPI、大型模型入庫。
- 責任歸屬以 `docs/TEAM_AI_OWNERSHIP.md` 為準，Git author 不可單獨視為 owner。

---

## 5. 監控與告警

**現況：無外部監控系統、無告警。** 健康檢查端點已具備：

| 端點 | 回報內容 | 定義位置 |
| :--- | :--- | :--- |
| `GET /api/health` | 總健康：`status` ready/offline/unavailable、`ready`、`formal`（catalog+project store 皆 postgres 才 true）、`source_of_truth`；formal 且未 ready 回 **503**，其餘 200；`Cache-Control: no-store` | main.py:2533-2562 |
| `GET /api/catalog/status` | catalog provider、Phase 4 runtime catalogs、furniture/surfaces/doors/style_cards 供應者與數量、cache_policy | main.py:2528-2530（實作 2429 起） |
| `GET /api/render-provider/status` | 內建 OpenRouter 生圖啟用時如實回報，否則回舊遠端契約狀態 `{configured, provider, has_token}` | main.py:2262-2267 |
| `GET /api/scene/provider-status` | OpenRouter 場景規劃啟用狀態 | main.py:2837-2839 |
| `GET /api/rag/status` | RAG 就緒狀態（停用／模型快取缺失／embeddings 空為 blocker） | rag_api.py:141、rag/service.py:82-90 |
| `GET /api/v1/engineering/health` | snapshot store provider、demo_mode、knowledge counts、advanced_rag 狀態、xlsx adapter（node 路徑） | engineering/api.py:77-104 |

### 日誌現況

- **無日誌檔、無集中式日誌**；輸出走 uvicorn stdout，終端關閉即消失。
- `backend/server/*.py` 無任何 `import logging`（grep 實測）；warmup 失敗用 `print`（main.py:2828，全檔唯一 print）。`backend/agent/select.py` 是後端少數用 logging 的模組（選件丟棄警告）。
- 前端錯誤無上報機制（先行素材實測結論；現行未重查=(未查證)）。

### 關鍵指標與告警規則

現況皆無。模板的 P95 延遲、錯誤率、CPU/記憶體閾值與告警表在單機開發階段無對應設施。資安基線另見 `.claude/skills/roompilot-security/`（專案原生 skill，明言現況「全端點無認證/授權」——唯一例外是 `/api/admin/furniture` 的 bearer token——可作上線前補強清單起點）與 `docs/vibecoding-v5/05_qa/`（若已導入）。

待辦：

- [ ] 若走向雲端部署，需先補 uvicorn 日誌落檔與最小告警（`/api/health` 已可作探針）

---

## 6. 回滾流程

### 自動回滾
現況：無。

### 手動回滾步驟（git 是唯一版本機制）

1. `git log --oneline` 找上一個穩定 commit（先 `git rev-parse --short HEAD` 記下現版）
2. `git switch --detach <穩定commit>`（或切回已知穩定分支）
3. 重啟 uvicorn
4. 跑第 3 節「更新後」煙霧測試

### 資料層注意事項

- `.runtime/` 與 PostgreSQL 不隨 git 回滾：程式回舊版後，資料庫內可能有新版程式寫入的資料。前端 workflow schema 為 `WORKFLOW_SCHEMA_VERSION = 2`（scene_workflow.js:1，localStorage 鍵 `roompilot.workflow.v2`）；後端把 workflow 存成不驗 schema 的 JSON 欄位，回滾後端本身不受影響，跨大版本回滾前建議先備份。
- 專案 API 有樂觀鎖（`expected_revision`，衝突回 409 `project_revision_conflict`），回滾不會靜默覆寫。
- 工程文件 snapshot 有獨立鎖定語意：鎖定版本覆寫回 409 `LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`、過期來源回 409 `SNAPSHOT_SOURCE_REVISION_STALE`（engineering/api.py:126-142；另一處 STALE 檢查在 api.py:348）。

### 備份現況（2026-08-04 本機實測）

| 項目 | 現況 |
| :--- | :--- |
| `.runtime/` 內容 | 1.1M（2026-08-04 23:51 實測，隨本機使用持續變動）：`projects.sqlite3`（258,048 bytes = 252KB）、`uploads/`（空）、`renders/`（空）、`engineering/`（工程文件產出，22 個 package 目錄）、`auth_secret.key`（64 bytes、0600；repo 程式碼 grep 無任何引用，來源未查證） |
| 版控狀態 | `.runtime/` 被 `.gitignore:12` 排除，**完全不在 git 保護範圍**；README 明文禁止提交 `.runtime/` 與 `.env` |
| PostgreSQL 備份 | **無備份腳本或排程**（scripts/ 僅 catalog 管線、sql/project_store/runtime_catalog 匯入器）；匯入器採 transaction+UPSERT，`--prune-extra` 需人工確認（README） |
| SQLite 手動備份 | WAL 模式，複製須同時帶 `projects.sqlite3` + `-wal` + `-shm`，或停機時 `sqlite3 .runtime/projects.sqlite3 ".backup <目的檔>"`（標準 SQLite 做法；repo 無現成腳本） |
| SQLite→PostgreSQL 遷移 | `scripts/project_store/migrate_sqlite_projects_to_postgres.py`（Phase 3 單向遷移工具，非備份） |
| 跨 worktree 合併 | 啟動時自動把舊 worktree `.runtime` 合併進共用資料庫（main.py:159-160）；設計對象是同機多 worktree，不是跨機備援 |
| 離線 GLB 備援 | README 首節明示 IKEA 地端 GLB 備援**尚未完成**，CloudFront 是唯一正式模型來源；舊版驗證腳本 `verify_ikea_offline_backup.py` 已移除（ls scripts/ 實測） |

待辦：

- [ ] 建立 `.runtime/` 與 PostgreSQL 定期備份；demo 前的專案資料目前是單點
- [ ] 查明 `.runtime/auth_secret.key` 的產生者與用途（程式碼無引用，未查證）

---

## 7. Runbook：RoomPilot FastAPI 服務

```markdown
# 服務 Runbook: backend.server.main:app

## 服務概覽
- 用途：AI 室內風格與家具配置展示系統（FastAPI title，main.py:214）；
  八步工作流 UI（scene.html:25-32）對應 11 個內部步驟（scene_workflow.js:4-16）。
  另有 /rag 家具 RAG 測試台與 /engineering 工程估算文件頁。
- 依賴服務：
  - PostgreSQL 17（.env.example 預設 provider；未匯入時明文改 json/sqlite 離線模式，
    postgres 讀不到 catalog 自動用已驗證 JSON 備援，Phase 4 runtime catalog 嚴格模式則回 503）
  - CloudFront（GLB 模型；斷線時 3D 家具載不出來，伺服器仍可啟動）
  - OpenRouter（選用；未設走 deterministic fallback，選件輸出經候選白名單驗證）
  - 遠端渲染供應商或內建 OpenRouter 生圖（皆未設時第 8 步回 503，不產生假結果）
  - Node（XLSX 匯出 side-process；缺少時工程 job 以 XLSX_ADAPTER_UNAVAILABLE 失敗）
- 架構圖：見本文件第 1 節拓撲

## 部署流程
- 啟動：第 1 節指令；更新：第 3 節清單
- 配置：`.env` 參照版控內 `.env.example`（45 個 `KEY=` 項的權威範例）；金鑰不進版控
- 健康檢查：GET /api/health（ready/offline=200、formal 未 ready=503）

## 監控
- 儀表板／告警：無
- 日誌位置：uvicorn stdout（無落檔）

## 故障排除（常見問題，均查證自程式碼）
- port 被占用 → 改 `--port 8023`（README:35）
- 啟動印 `[RoomPilot] catalog cache warmup skipped:` → json 模式型錄載入失敗，
  檢查 backend/catalog/data/ 的 JSON 與 manifests/（main.py:2821-2828）
- 多數 API 回 503 `runtime_catalog_unavailable` / `catalog_pool_busy` → Phase 4 嚴格
  postgres 模式讀不到資料表或池忙（main.py:246-266）；本機沒 DB 就把
  ROOMPILOT_RUNTIME_CATALOG_PROVIDER 與 ROOMPILOT_CATALOG_PROVIDER 改 json
- 503 且附 Retry-After: 2 → 專案保存層忙（ProjectStoreBusy，main.py:226-243）；
  持續發生時調 DB_POOL_MAX / DB_POOL_TIMEOUT
- /api/admin/furniture 回 503 catalog_admin_not_configured → 未設
  ROOMPILOT_CATALOG_ADMIN_TOKEN；401 → bearer token 不符（catalog_admin.py:180-200）
- /api/rag/search 回 RAG 停用／就緒錯誤 → ROOMPILOT_RAG_ENABLED=false 或
  模型快取缺失／pgvector embeddings 表為空（rag/service.py:82-90）；
  /api/rag/search/jobs 回 429 rag_job_capacity_reached → 同時任務上限
  RAG_JOB_MAX_ACTIVE=1（rag_api.py:30,163）
- 工程 job 失敗 error_code=XLSX_ADAPTER_UNAVAILABLE → Node 不在 PATH 或
  ROOMPILOT_ARTIFACT_NODE 指錯（documents.py:142-164）；
  ENGINEERING_PACKAGE_FAILED → 看 job 回傳訊息（engineering/api.py:216-268）
- POST engineering-packages 回 409 REVISION_NOT_LOCKED → snapshot 尚未
  designer_confirmed，先走 lock 流程（engineering/api.py:180-198）
- POST render-jobs 回 503 → 遠端供應商與內建生圖皆未設定或連不上；502 → 供應商拒絕
- GLB 端點回 410 → cloudfront 模式下本機模型端點固定 410，屬設計行為；
  IKEA 本機備援尚未完成，勿啟用 local 模式（README 首節）
- LLM 功能沒反應 → 檢查 OPENROUTER_API_KEY 與各 *_ENABLED 開關；未設走本地
  fallback 是契約行為，不是故障
- 換電腦找不到專案 → project_id 綁本機 .runtime/ 或本機 DB，資料不跟 git 走
- 前端存檔回 409 project_revision_conflict → 樂觀鎖衝突，前端以最新 project 重套
- 演示現場 OCR 出問題 → 設 ROOMPILOT_OCR_DISABLED=1 緊急停用（main.py:174）
- pytest 出現 on_event / HTTP_422 DeprecationWarning → 已知現象（2026-08-04 實測 7 個警告）

## 緊急聯絡人 / 升級流程
- 責任目錄表見 docs/TEAM_AI_OWNERSHIP.md 與 README「團隊責任」：backend/server=Bella、
  backend/catalog 與 PostgreSQL=Kai、RAG runtime=Django、其餘依表
- 正式 on-call／升級流程：無書面約定（未查證）
```

---

## 附：本文件的已知缺口（待補清單）

- 發表用環境的部署形態（本機 demo 或雲端）repo 內無定義（未查證）
- 前端錯誤上報機制：沿用先行素材 2026-07-26 的「無」結論，現行樹未重查（未查證）
- `.runtime/auth_secret.key` 來源與用途（程式碼 grep 無引用，未查證）
- floor04.png 辨識驗收基準數字是否仍有效（現行 README 已無此段，未查證）
- CI 導入與備份機制：現況皆無，列於第 2、6 節待辦
- 模板 INDEX 指向的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/`（未查證：來源不在 repo）
