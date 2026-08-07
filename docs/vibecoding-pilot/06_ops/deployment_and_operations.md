# 部署與運維指南 (Deployment and Operations Guide) - RoomPilot

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** Bella（FastAPI 服務與整合運維）／Kai（PostgreSQL、CloudFront 資產）
> **語域:** L3（工程）
> **定位:** 怎麼啟動、怎麼檢查、怎麼回滾的單一來源；故障情境處置歸 `runbook-*.md`，部署拓撲的架構視圖歸 [sad §7](../03_architecture/sad.md#7-部署視圖)。
> **實例:** 單例（整個系統一份）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/06_ops/deployment_and_operations.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

**現況一句話：本專案沒有正式部署環境，唯一部署形態是本機 uvicorn（127.0.0.1:8002）＋本機 PostgreSQL 17.10。** Docker 已於 2026-08-06 整套移除（commit `09891216`，刪 Dockerfile／docker-compose.yml／docs/DOCKER.md／requirements-container.txt；決策見 [ADR-009](../03_architecture/ADR-009-docker-removal.md)）。常態雲端依賴只有 CloudFront GLB 交付；OpenRouter LLM／生圖為選用，未設定時走確定性 fallback 或回 503，不假成功。凡機制不存在，本文一律照實標「現況：無」。

---

## 目錄

- [1. 部署架構](#1-部署架構)
- [2. CI/CD 流水線](#2-cicd-流水線)
- [3. 部署檢查清單](#3-部署檢查清單)
- [4. 部署策略](#4-部署策略)
- [5. 監控與告警](#5-監控與告警)
- [6. 回滾與備份](#6-回滾與備份)
- [7. 追溯與相關文件](#7-追溯與相關文件)

## 1. 部署架構

```
現況：Development（本機）only — 無 Staging、無 Production
```

部署節點拓撲圖只畫在 [sad §7 部署視圖](../03_architecture/sad.md#7-部署視圖)，此處不重畫。從零佈建一台新機器（PostgreSQL＋pgvector 編譯、四份 schema、模型快取搬遷）依 [`docs/NEW_MACHINE_SETUP.md`](../../NEW_MACHINE_SETUP.md)，本節只涵蓋日常啟停與組態。

### 1.1 基礎設施元件現況（2026-08-07 對 1268b2b4 查證）

| 元件 | 模板角色 | 現況 |
| :--- | :--- | :--- |
| 負載均衡 | 流量分配 | **無**；uvicorn 單進程，無反向代理，無 CORS middleware（僅 GZip，`main.py:245`） |
| 應用伺服器 | 核心應用 | uvicorn（本機 .venv 實測 0.50.0）＋ FastAPI（實測 0.139.0）；**無容器化**（README baseline 寫 0.51.0／0.140.0，與本機 .venv 不一致，見 §1.4 附註） |
| 資料庫 | 持久化 | PostgreSQL 17.10 + pgvector 0.8.2（service `postgresql-x64-17`，2026-08-07 實測 Running）；三個 provider 預設 postgres（`.env.example`）。SQLite `.runtime/projects.sqlite3` 為離線模式備援 |
| 快取層 | 效能 | **無** Redis/Memcached；僅進程內快取（JSON 模式啟動預熱，`main.py:1401-1408`） |
| CDN | 靜態資源 | CloudFront `https://ddgsm1yg3xikc.cloudfront.net`（`services/cloud_models.py:32`）只交付家具 GLB/PNG；網頁靜態資源由 FastAPI `/static` 直出（磁碟位置唯一由 `backend/paths.py` `STATIC_DIR` 決定） |
| 監控 | 健康檢查 | 無監控系統；有 `/api/health` 與多個狀態端點（見 §5） |
| Node.js | XLSX 子行程 | 第 9 步工程文件 XLSX 需 Node（實測 v24.15.0）；`@oai/artifact-tool` 為私有套件，裝不到的機器用本機相容層 `tools/artifact_tool_local/`（commit `3f479c6b`，安裝見其 README） |

### 1.2 啟動、停止與重啟

在 repo 根目錄（前置：`.venv` 已依 README「快速啟動」建好、`.env` 已從 `.env.example` 複製填值）：

```powershell
.\dev.ps1            # 一鍵啟動：uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
.\dev.ps1 8023       # 8002 被占用時換 port
```

或等價的手動指令（`dev.ps1` 即此指令加 `param([int]$Port = 8002)` 的參數包裝）：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

- `main.py` 無 `__main__` 區塊（grep 實測），必須經 uvicorn 啟動。
- 停止＝終止 uvicorn 進程（Ctrl+C）；重啟前必停舊進程，避免驗到舊程式。
- 啟動時：合併舊 worktree 的 legacy `.runtime`（`main.py:171` `import_runtime`）；JSON 模式才預熱型錄快取，失敗只印 warning 不擋啟動（`main.py:1401-1408`；`on_event` 為 FastAPI 已棄用 API，pytest 有 deprecation warning）。
- 服務起來後開 <http://127.0.0.1:8002>，`/login` 註冊或登入後進 `/projects`（README「帳戶端」）。

### 1.3 組態解析順位（誰蓋過誰）

**鐵律：作業系統環境變數永遠蓋過 `.env`。** 所有讀取端一致採 `os.getenv(name, file_values.get(name, default))` 模式：

| 讀取端 | 位置 | 行為 |
| :--- | :--- | :--- |
| 型錄 provider／DB 連線 | `backend/catalog/postgres_repository.py:196-198` | env → `.env` → 預設 |
| 專案儲存 provider | `backend/server/project_store.py:651-656` | 同上（程式碼預設 `sqlite`，`.env.example` 設 `postgres`） |
| runtime 型錄 provider | `backend/catalog/runtime_catalog_repository.py:48-55` | 同上；留空時沿用型錄 provider 模式 |
| 認證金鑰／TTL | `backend/server/auth/tokens.py:54-61` | 同上 |
| OpenRouter／dotenv | `services/cloud_models.py:25`（`load_dotenv(override=False)`）、`scene_service.py:47-61` | `.env` 只補進程缺的鍵，不覆蓋 |

實務後果（換機部署已踩過的坑，`docs/NEW_MACHINE_SETUP.md`「兩個容易踩的坑」）：PowerShell profile 或殘留終端機若設過 `ROOMPILOT_*_PROVIDER`，改 `.env` 不會生效。**任何 provider 驗證前先跑：**

```powershell
Get-ChildItem env:ROOMPILOT_*
```

### 1.4 環境變數（逐一對 `.env.example`＋讀取端程式碼複核，2026-08-07）

`.env` 不進版控（README「不得提交」）；範本為 git 追蹤的 `.env.example`，其值另有契約測試 `tests/test_env_example_contract.py` 錨定。

**服務與資料來源：**

| 變數 | `.env.example` 值／預設 | 讀取位置 |
| :--- | :--- | :--- |
| `ROOMPILOT_CATALOG_PROVIDER` | `postgres`（程式碼預設亦 postgres；`json` 為明確離線模式） | `catalog/postgres_repository.py:203` |
| `ROOMPILOT_PROJECT_STORE_PROVIDER` | `postgres`（程式碼預設 `sqlite`＝離線開發模式） | `server/project_store.py:654` |
| `ROOMPILOT_RUNTIME_CATALOG_PROVIDER` | `postgres`＝嚴格模式：讀不到回 503，不靜默退 JSON（`.env.example` 註記） | `catalog/runtime_catalog_repository.py:51` |
| `ROOMPILOT_MODEL_DELIVERY_MODE` | `cloudfront`（`local`＝離線 GLB） | `services/cloud_models.py:47` |
| `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` | 空；local 模式離線 GLB zip 路徑 | `server/main.py:345` |
| `DB_HOST`／`DB_PORT`／`DB_NAME`／`DB_USER`／`DB_PASSWORD` | `localhost`／`5432`／`roompilot_db`／`postgres`／空（**必填**） | `catalog/postgres_repository.py:213-225`、`server/postgres_project_store.py:57-69` |
| `DB_ADMIN_DB` | `postgres`；僅匯入器 `--create-database` 用 | `scripts/sql/import_official_catalog_to_postgres.py:798` |
| `DB_SSLMODE`／`DB_CONNECT_TIMEOUT` | `disable`／`10`（程式碼預設 3，`.env` 值優先） | 同 DB 連線讀取端 |
| `DB_APPLICATION_NAME`／`DB_PROJECT_APPLICATION_NAME` | `roompilot_catalog_import`／`roompilot_project_store` | 同上 |
| `DB_POOL_MIN`／`DB_POOL_MAX`／`DB_POOL_TIMEOUT` | `1`／`24`／`10`：滿載時排隊 10 秒才回 503 | `catalog/postgres_repository.py:254-256` |

**LLM 與生圖（全部選用；未設走 fallback 或 503）：**

| 變數 | `.env.example` 值／預設 | 讀取位置 |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | 空＝所有 LLM 功能走本地規則 | `scene_service.py:82`、`render_providers.py:57`、`rag/settings.py:84` |
| `OPENROUTER_MODELS`／`OPENROUTER_MODEL` | 免費模型輪詢清單／單一模型（皆空時預設 `qwen/qwen3-32b:free`） | `scene_service.py:64-77` |
| `OPENROUTER_SITE_URL`／`OPENROUTER_APP_NAME` | `http://127.0.0.1:8002`／`roompilot`（請求標頭；程式碼 fallback 為 8000） | `scene_service.py:129-130` |
| `OPENROUTER_SELECTION_ENABLED` | `1`：第 6 步選件 agent 隨 API key 預設啟用；輸出經候選白名單驗證，設 `0` 完全離線 | `scene_service.py:99-111` |
| `OPENROUTER_SCENE_PLANNING_ENABLED` | 不在 `.env.example`；`=1` 才啟用 LLM 場景規劃 | `scene_service.py:87,94` |
| `ROOMPILOT_RENDER_PROVIDER_URL`／`_TOKEN`／`_NAME`／`_TIMEOUT_SECONDS` | 空／空／`remote_renderer`／`60`（夾 5–180）；URL 有值時優先走自訂遠端契約 | `render_service.py:38-49` |
| `ROOMPILOT_RENDER_IMAGE_MODEL`／`_DISABLED` | 註解列；內建生圖預設 `google/gemini-2.5-flash-image`，沿用 OPENROUTER_API_KEY，`_DISABLED=1` 整段停用 | `render_providers.py:51-61` |

**RAG（預設由 `.env.example` 設 `false`；參考機器實跑 `true`）：**

| 變數 | `.env.example` 值／預設 | 讀取位置 |
| :--- | :--- | :--- |
| `ROOMPILOT_RAG_ENABLED` | `false`（換機清單目標狀態為 `true`） | `rag/settings.py:80`、`rag/service.py:136-140` |
| `ROOMPILOT_RAG_PARSER_PROVIDER` | `openrouter`（或 `openai`／`anthropic`，對應金鑰 `OPENAI_API_KEY`／`ANTHROPIC_API_KEY` 留空） | `rag/settings.py:61` |
| `ROOMPILOT_RAG_*_MODEL`／`_PARSER_MODEL`／`_OPENROUTER_BASE_URL` | 各 provider 模型與端點 | `rag/settings.py:64-96` |
| `ROOMPILOT_RAG_REASONING_EFFORT`／`_ANTHROPIC_MAX_TOKENS`／`_TIMEOUT_SECONDS`／`_DEVICE` | `low`／`4096`／`30`／`auto` | `rag/settings.py:100-111` |
| `ROOMPILOT_RAG_MODEL_CACHE` | 空＝使用者預設 HuggingFace cache（bge-m3 4.3GB＋reranker 2.2GB） | `rag/settings.py:60` |

**認證、報告與其他：**

| 變數 | 值／預設 | 讀取位置 |
| :--- | :--- | :--- |
| `ROOMPILOT_AUTH_SECRET` | **不在 `.env.example`**；README 要求在 `.env` 明確設定（≥32 bytes）。未設時自動產生並存 `.runtime/auth_secret.key`——換機沒帶這把＝全帳號 token 失效 | `auth/tokens.py:77-95` |
| `ROOMPILOT_AUTH_ACCESS_TTL_MINUTES`／`_REFRESH_TTL_DAYS` | 不在 `.env.example`；README 範例 30／14 | `auth/tokens.py:121-130` |
| `ROOMPILOT_AUTH_DISABLE_FIRST_ADMIN` | 不在 `.env.example`；`=1` 關閉「首註冊帳號自動 admin」 | `auth/service.py:59-62` |
| `ROOMPILOT_CATALOG_ADMIN_TOKEN` | 空＝停用 `/api/admin/furniture` 寫入端點 | `catalog/postgres_admin_repository.py:69` |
| `ROOMPILOT_DEMO_MODE` | `false`：缺報價／工時的項目維持 pending，不臆測數值 | `engineering/cost.py:84`、`schedule.py:164`、`api.py:107` |
| `ROOMPILOT_ARTIFACT_NODE`／`ROOMPILOT_ARTIFACT_TOOL_MODULES`／`ROOMPILOT_XLSX_TIMEOUT_SECONDS` | `node`／空（指向 `tools/artifact_tool_local` 啟用本機相容層）／`90` | `engineering/documents.py:149,171`、`workbook_builder.mjs:9` |
| `ROOMPILOT_OCR_DISABLED` | 註解列；`=1` 演示現場緊急停用 OCR（paddle 未裝時本就安靜停用） | `server/main.py:226` |

僅存在程式碼、不在 `.env.example` 的覆寫項（按需使用）：`ROOMPILOT_RUNTIME_DIR`（`runtime_paths.py:22`）、`ROOMPILOT_CLOUDFRONT_BASE_URL`（`cloud_models.py:67`）、`ROOMPILOT_GLB_MANIFEST_PATH`、`ROOMPILOT_IMAGE_MANIFEST_PATH`、`ROOMPILOT_CLOUD_CATALOG_PATH`（`main.py:153`）、`ROOMPILOT_RAG_PRELOAD`（`rag/preload.py`）、`ROOMPILOT_SHORTLIST_PARSER`（`rag/query_refinement.py`）、`DB_PROJECT_POOL_MIN`（`postgres_project_store.py:84`）、測試專用 `ROOMPILOT_TEST_POSTGRES_*`（`run_postgres_live_tests.ps1`）。

附註（版本基準不一致，待對齊）：README「套件版本」寫 Python 3.12.13／FastAPI 0.140.0／uvicorn 0.51.0；本機 `.venv` 2026-08-07 實測 Python 3.12.10／FastAPI 0.139.0／uvicorn 0.50.0／psycopg2-binary 2.9.12／torch 2.13.0+cpu／pytest 9.1.1。直接依賴以 `requirements.txt`（2026-07-27 baseline）為準。

## 2. CI/CD 流水線

**現況：無任何 CI/CD。** repo 無 `.github/`、無 Dockerfile、無 pipeline 設定（2026-08-07 實測）。實際流程是手動閘門：

| 階段 | 現況實際做法 |
| :--- | :--- |
| **建置** | 無編譯產物；`uv sync --extra server --extra vision --extra catalog --group dev` 或 pip 裝 `requirements.txt` 即完成。前端不經打包（`frontend/` 原生 ES module，README） |
| **測試** | `.\.venv\Scripts\python.exe -m pytest -q`＋`git diff --check`＋`git status --short`（AGENTS.md 最終整合指令）。現行基準：2026-08-07 本機全量實跑 **1,043 passed／10 skipped／0 failed**（收集 1,053 筆；執行紀錄見 [test_plan §4.1](../05_qa/test_plan.md#4-測試報告結論-qa-report)）；2026-08-05 參考機器的 1018 passed／11 skipped（`docs/NEW_MACHINE_SETUP.md` §9）降為歷史參考。預設測試把 provider 釘 sqlite/json（`tests/conftest.py`），正式資料路徑另跑 `run_postgres_live_tests.ps1`（7 支 live 測試＋postgres provider 全套） |
| **部署** | 無部署動作；各成員本機 `git pull` 後重啟 uvicorn |

環境晉升（dev → staging → production）：**不適用**——只有一個環境。2026-08-20 成果發表（未查證，團隊口述）的 demo 環境形態未定義（待補）。

待辦：

- [ ] CI 導入（repo 內無任何 CI 設定與規劃文字，grep 實測；是否口頭規劃過未查證）
- [ ] 發表用環境形態拍板（本機 demo 或雲端；容器化重建條件＝Ben 裁定達標後，見 ADR-009）

## 3. 部署檢查清單

本專案「部署」＝成員本機更新到指定 commit 並重啟。

### 更新前

- [ ] `pytest -q` 全綠（含既有 skip；紅燈先查再更新）
- [ ] `git diff --check` 無衝突標記、`git status --short` 乾淨（保留他人未提交變更，AGENTS.md）
- [ ] `Get-ChildItem env:ROOMPILOT_*` 確認終端機沒有殘留 provider 覆寫（§1.3）
- [ ] 停止舊 uvicorn 進程

### 更新中

- [ ] `git fetch origin` → 切到約定分支 → `git pull --ff-only`
- [ ] `git rev-parse --short HEAD` 與整合者宣布的 commit 一致
- [ ] 重啟：`.\dev.ps1`

### 更新後（煙霧測試）

- [ ] `GET /api/health`：`status=ready`（provider 為 postgres 時須 `formal=true`；`unavailable`＝正式模式但 DB 讀不到）
- [ ] `GET /api/catalog/status`：postgres provider 下型錄可用（本機 DB 基準：`furniture_items` 8,557、active／`furniture_catalog_current` 7,958，2026-08-07 實測；匯入驗收全表見 `docs/NEW_MACHINE_SETUP.md` §6）
- [ ] `/login` 登入 → `/projects` 開啟既有專案（token 失效＝金鑰變動，查 §1.4 `ROOMPILOT_AUTH_SECRET`）
- [ ] 專案資料在 postgres store：`project_id` 綁本機資料庫，不能拿別台機器的專案網址驗證版本

## 4. 部署策略

| 模板策略 | 本專案現況 |
| :--- | :--- |
| Blue-Green | 不適用；單機單進程，無第二套環境 |
| Rolling | 不適用；無多實例 |
| Canary | 不適用；無流量分配 |

實際策略：**更新即停機重啟**（短暫斷線）。專案資料在 PostgreSQL（或離線模式的 `.runtime/` SQLite）持久化，重啟不掉資料。版本控制即發佈控制：分支與整合規則歸 README「版本控制與整合」與 `docs/TEAM_AI_OWNERSHIP.md`，此處不重抄。

## 5. 監控與告警

**現況：無監控系統、無指標蒐集、無告警。** 可當健康檢查用的狀態端點（全數查證於現行程式碼；路由總量 2026-08-07 實測 **77 個端點／70 條路徑**，經 app import 實數）：

| 端點 | 回報內容 | 定義位置 |
| :--- | :--- | :--- |
| `GET /api/health` | 總體就緒：型錄＋專案儲存 provider；`ready`／`unavailable`（正式模式故障）／`offline`（離線模式） | `main.py:1103` |
| `GET /api/catalog/status` | 型錄 provider、CloudFront manifest 健康度、surfaces/style_cards 供應者 | `main.py:1098` |
| `GET /api/render-provider/status` | 生圖供應者：自訂遠端 URL 或內建 OpenRouter 生圖 | `projects_api.py:556` |
| `GET /api/scene/provider-status`、`/api/scene/llm-status` | LLM 場景規劃／選件啟用狀態 | `scene_api.py:294-295` |
| `GET /api/rag/status` | RAG 啟用與模型狀態（登入後） | `rag_api.py:147` |
| `GET /api/v1/engineering/health` | 工程文件生成健康度，含 `xlsx.module_path_configured` | `engineering/api.py:134` |

### 日誌現況

- 所有輸出走 uvicorn stdout（access log＋應用訊息），終端機關閉即消失；**無日誌落檔、無集中式日誌**。
- `backend/server/` 無任何 `logging` 設定（grep 實測 0 檔）；啟動預熱失敗用 `print`（`main.py:1408`）。

### 關鍵指標與告警規則

現況皆無。模板的 P95／錯誤率／資源閾值表在單機開發階段無對應設施；若走向正式部署，最小前置是 uvicorn 日誌落檔＋指標蒐集（待補，無既定計畫）。

## 6. 回滾與備份

### 自動回滾

現況：無。

### 手動回滾（git 是唯一版本機制）

1. `git rev-parse --short HEAD` 記下目前版本；`git log --oneline` 找上一個穩定 commit
2. `git switch --detach <穩定commit>`（或切回已知穩定分支）
3. 重啟 uvicorn，跑 §3「更新後」煙霧測試

### 資料層注意事項

- **資料不隨 git 回滾。** 專案／workflow_json／render metadata 在 PostgreSQL（`ROOMPILOT_PROJECT_STORE_PROVIDER=postgres`）；程式回舊版後資料庫仍是新資料。專案 API 有樂觀鎖（`expected_revision` 衝突回 409），回滾不會靜默覆寫，但前端須重新載入。
- **無版本化 DB migration 機制**：四份 schema（`scripts/sql/`、`scripts/project_store/`、`scripts/runtime_catalog/`）為手動 apply-forward 腳本，無 expand-contract 慣例、無降版腳本（repo 實測）。跨 schema 版本回滾前先做一次手動備份。
- SQLite→PostgreSQL 專案搬遷有現成腳本：`scripts/project_store/migrate_sqlite_projects_to_postgres.py`。

### 備份現況（2026-08-07 盤點）

| 項目 | 現況 |
| :--- | :--- |
| 自動備份 | **無任何備份腳本或排程**（`scripts/` glob 實測無 backup 檔） |
| PostgreSQL（正式專案資料） | 無既有備份方法文件；`pg_dump roompilot_db` 為標準做法（TO-BE，repo 內無現成腳本） |
| `.runtime/` | 含 `auth_secret.key`（64B，全帳號簽章能力）、`engineering/`（鎖版報告產物約 29MB）、`uploads/`、離線模式 SQLite；被 `.gitignore` 排除，**完全不在 git 保護範圍**。換機搬遷清單見 `docs/NEW_MACHINE_SETUP.md` §10 |
| 模型快取 | `~/.cache/torch/hub`＋`~/.cache/huggingface/hub` 共約 6.6GB；遺失只是重新下載，不算資料損失 |
| 型錄資產 | GLB 正本在 CloudFront/S3（Kai 維護）；型錄中繼資料可由 `JSON/`＋匯入腳本重建 |

待辦：

- [ ] 發表日前建立 PostgreSQL＋`.runtime/` 的最小備份（目前是單點；發表日 2026-08-20 未查證，團隊口述）
- [ ] 跨 schema 版本回滾的資料相容策略（待補）

## 7. 追溯與相關文件

- 上游：[sad §7 部署視圖](../03_architecture/sad.md#7-部署視圖)（拓撲 SSOT）、[ADR-009](../03_architecture/ADR-009-docker-removal.md)（Docker 移除）、[ADR-006](../03_architecture/ADR-006-postgres-single-source-five-phases.md)（PostgreSQL 單一來源，provider 組態的決策脈絡）；對應 NFR：NFR-可用性-01／NFR-維運-01（[srs](../01_requirements/srs.md) §2 已定編；監控與備份現況以本檔 §5–§6 表為準）
- 下游：`runbook-*.md`（本資料夾，一症狀一份）；部署／驗證證據歸 [test_plan](../05_qa/test_plan.md) 與 `/verify` 產出
- 佈建程序權威：[`docs/NEW_MACHINE_SETUP.md`](../../NEW_MACHINE_SETUP.md)（本檔不重抄其步驟）；分支與整合規則：README「版本控制與整合」、`AGENTS.md`
- 生成憑證：基準 `docs/vibecoding-restructure` @ `1268b2b4`（2026-08-07）；本檔所有「實測」皆指當日對該基準的唯讀驗證
