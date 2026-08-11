# 部署與運維指南 (Deployment and Operations) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` 整合與啟動，AGENTS.md:36）＋ Kai（PostgreSQL catalog 資料流）——AI 衍生，人工核准前為 TO-BE
> **語域:** L3（工程）
> **實例:** 單例（整個系統一份）
> **定位宣告:** 本文件回答「RoomPilot Pilot 在本機單機環境怎麼安裝、設定、啟動、備份與回滾」；不包含故障處置步驟（見同目錄四份 runbook）、部署拓撲的架構視圖（見 [../03_architecture/sad.md](../03_architecture/sad.md)）與 API 行為（見 [../04_design/api_spec.md](../04_design/api_spec.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 部署架構（現況：本機單機 Pilot）](#1-部署架構現況本機單機-pilot)
- [2. 環境需求與安裝](#2-環境需求與安裝)
- [3. 環境變數](#3-環境變數)
- [4. 啟動、停止與驗證](#4-啟動停止與驗證)
- [5. 資料位置與備份](#5-資料位置與備份)
- [6. CI/CD 與部署策略](#6-cicd-與部署策略)
- [7. 監控與告警](#7-監控與告警)
- [8. 升級與回滾（git 層面）](#8-升級與回滾git-層面)
- [9. 已知運維風險](#9-已知運維風險)
- [10. 待確認](#10-待確認)
- [11. 追溯與相關文件](#11-追溯與相關文件)

## 1. 部署架構（現況：本機單機 Pilot）

無 Development → Staging → Production 分層；單一 Windows 開發機直跑 uvicorn，瀏覽器連 `127.0.0.1`。不虛構雲端拓撲，實際元件：

| 元件 | 用途 | 實際形式 | 證據 |
| :--- | :--- | :--- | :--- |
| 應用伺服器 | FastAPI 八步工作流＋靜態前端 | `uvicorn backend.server.main:app`（本機、`--reload`） | README.md:63 |
| 專案持久化 | 專案、workflow JSON、render metadata | SQLite `.runtime/projects.sqlite3`（WAL mode） | project_store.py:78、84、93 |
| 家具 catalog | 第 6 步 8,675 件正式家具 | 本機 PostgreSQL 17，view `roompilot.furniture_catalog_current`；預設 strict `postgres` | postgres_repository.py:199-204、README.md:15 |
| 3D 模型／圖片 | GLB 與三視角圖 | 外部 CloudFront（`ROOMPILOT_MODEL_DELIVERY_MODE` 預設 `cloudfront`，307 redirect） | cloud_models.py:47、main.py:4012-4040 |
| AI 生圖 | 第 7/8 步色卡比較與寫實圖 | 外部 OpenRouter API（伺服器端金鑰） | ai_render_service.py:67 |
| 交付 PDF | 第 8 步交付提案排版 | 本機 Playwright Chromium（print-to-PDF） | requirements-delivery.txt:8、main.py:2384-2402 |
| RAG 檢索 | `/rag` 家具檢索 demo | 本機 BGE-M3＋reranker（HF cache、offline-only lazy-load）＋pgvector | model_runtime.py:104-131、README.md:106-107 |
| 負載均衡／快取層／監控 | — | **無**（Pilot 不設） | — |

## 2. 環境需求與安裝

| 需求 | 版本／說明 | 證據 |
| :--- | :--- | :--- |
| OS | Windows 10/11 64-bit（Linux 走 `install.sh`＋uv） | README.md:12、38-39 |
| Python | README／install 腳本基準 **3.12**；本機現存 `.venv` 實測為 **uv 管理的 3.14.6（無 pip，須用 `uv pip`／`uv run`）**——版本漂移見 §10 | README.md:13、install.ps1:44-47；實測 `.venv\Scripts\python.exe --version` |
| Git／Node.js | Git；Node 24＋npm 11（僅 `frontend3d/` 原型與 XLSX Adapter 需要） | README.md:14 |
| PostgreSQL | 17，第 6 步正式 catalog 優先資料來源 | README.md:15 |
| Playwright Chromium | 交付提案 PDF 排版引擎；未裝時該端點回 503 | requirements-delivery.txt:2-6、main.py:2399-2402 |
| RAG 模型快取 | BGE-M3＋reranker 約 9 GB 磁碟、4.6 GB 常駐記憶體；伺服器只 lazy-load 已快取模型（`local_files_only=True`），**不會**在請求期間下載 | model_runtime.py:116-128、README.md:106-107 |

依賴檔分工：`requirements.txt`（server/vision/catalog/RAG/tests 基線，含 torch、sentence-transformers、openai）、`requirements-ocr.txt`（`-r requirements.txt`＋PaddleOCR，體積大、選裝）、`requirements-delivery.txt`（playwright＋pikepdf）。證據：requirements.txt:33-37、requirements-ocr.txt:1-6、requirements-delivery.txt:11-12。

安裝（一鍵，推薦）：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1        # pip
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uv    # uv（較快）
```

腳本涵蓋 requirements＋OCR＋交付 PDF＋`playwright.exe install chromium`＋frontend npm；選項 `-SkipOCR`／`-SkipFrontend`（install.ps1:53-76）。手動安裝與 uv extras 組合見 README.md:54-117。注意：README 安裝段引用的 `.env.example`、`requirements-rag.txt`、`scripts/rag/prefetch_models.py` 在本分支磁碟上**不存在**（見 §10）；`.env` 需手動建立（§3）。

## 3. 環境變數

讀取方式：多數模組同時讀 process env 與專案根 `.env`。**優先序不一致**——catalog 相關是 process env 蓋過 `.env`（postgres_repository.py:194-196、postgres_catalog.py:86-87），RAG 相關刻意讓 `.env` 蓋過 process env（settings.py:23-28）。`.env` 不得提交（README.md:398）。

### 3.1 工作流與伺服器

| 變數 | 用途 | 預設值 | 證據 |
| :--- | :--- | :--- | :--- |
| `ROOMPILOT_AGENT_PIPELINE` | 開啟 MasterAgent 並存管線（`""`/`0`/`false`/`no`/`off` 視為關） | 關閉 | agent_pipeline_service.py:32、43 |
| `ROOMPILOT_RUNTIME_DIR` | 覆蓋執行資料目錄 | `<repo 根>/.runtime`（worktree 共用） | runtime_paths.py:22-25 |
| `ROOMPILOT_OCR_DISABLED` | `1` 停用平面圖 OCR provider | 未設（啟用） | main.py:158 |
| `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` | 額外外部 GLB zip 目錄 | 空 | main.py:293 |

### 3.2 家具 catalog 與 PostgreSQL（ADR-003、NFR-003）

| 變數 | 用途 | 預設值 | 證據 |
| :--- | :--- | :--- | :--- |
| `ROOMPILOT_CATALOG_PROVIDER` | catalog 來源；`json`/`local`/`fallback` 才走離線 JSON，其餘一律 strict `postgres`；postgres 模式須回滿 8,675 筆才採用 | `postgres` | postgres_repository.py:199-204、main.py:917-921 |
| `DB_HOST`／`DB_PORT`／`DB_NAME`／`DB_USER`／`DB_PASSWORD` | PostgreSQL 連線 | `localhost`／`5432`／`roompilot_db`／`postgres`／空 | postgres_catalog.py:90-94 |
| `DB_CONNECT_TIMEOUT`／`DB_SSLMODE`／`DB_APPLICATION_NAME` | 連線逾時／SSL／識別 | `3`／`disable`／`roompilot_catalog_api` | postgres_catalog.py:95-97 |
| `ROOMPILOT_MODEL_DELIVERY_MODE` | GLB 交付模式 | `cloudfront` | cloud_models.py:47 |
| `ROOMPILOT_CLOUDFRONT_BASE_URL` | CloudFront base URL | 程式內建預設 | cloud_models.py:67、cloud_images.py:54 |
| `ROOMPILOT_CLOUD_CATALOG_PATH` | 覆蓋 catalog JSON 路徑 | `JSON/furniture/furniture_official_catagory.json` | main.py:130-136 |
| `ROOMPILOT_GLB_MANIFEST_PATH`／`ROOMPILOT_IMAGE_MANIFEST_PATH` | GLB／圖片 manifest CSV 路徑 | `JSON/manifests/glb_upload_all_result.csv`／程式預設 | main.py:137-140、cloud_images.py:59 |

### 3.3 OpenRouter（intake／場景規劃／生圖）

| 變數 | 用途 | 預設值 | 證據 |
| :--- | :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | OpenRouter 金鑰（僅存伺服器端；未設時生圖端點回 503） | 空 | ai_render_service.py:67、main.py:2110-2116 |
| `OPENROUTER_MODEL`／`OPENROUTER_MODELS` | 單一或逗號分隔模型清單 | 空 | intake_service.py:44-47、scene_service.py:76-82 |
| `OPENROUTER_INTAKE_ENABLED` | `1` 才啟用 intake LLM 修飾 | 關閉 | intake_service.py:138 |
| `OPENROUTER_SCENE_PLANNING_ENABLED` | `1` 才啟用 LLM 場景規劃 | 關閉 | scene_service.py:96、377 |
| `OPENROUTER_SITE_URL`／`OPENROUTER_APP_NAME` | 請求標頭用站台識別 | `http://127.0.0.1:8000`／`test_furniture scene planner` | scene_service.py:374-375 |
| `ROOMPILOT_GENPIC_MODEL`／`ROOMPILOT_GENPIC_FALLBACK_MODEL` | 第 8 步生圖主／備援模型 | 程式內建 `DEFAULT_IMAGE_MODEL` | ai_render_service.py:71-72 |
| `ROOMPILOT_GENPIC_PALETTE_MODEL`／`ROOMPILOT_GENPIC_PALETTE_FALLBACK_MODEL` | 第 7 步色卡比較圖模型 | 程式內建預設 | ai_render_service.py:291-293 |

### 3.4 RAG（`.env` 優先於 process env）

| 變數 | 用途 | 預設值 | 證據 |
| :--- | :--- | :--- | :--- |
| `ROOMPILOT_RAG_ENABLED` | 啟用 `/rag` 檢索 | `false` | settings.py:76 |
| `ROOMPILOT_RAG_PARSER_PROVIDER` | `openai`／`anthropic`／`openrouter` | `openai` | settings.py:61、parser.py:27 |
| `OPENAI_API_KEY`／`ANTHROPIC_API_KEY` | 對應 provider 金鑰（缺時 raise `RagDependencyError`） | 空 | settings.py:78-79、openai_parser.py:74 |
| `ROOMPILOT_RAG_PARSER_MODEL` | 覆蓋解析模型 | 依 provider（`gpt-5.6-sol`／`claude-sonnet-4-6`／OPENROUTER_MODEL） | settings.py:62-71、82 |
| `ROOMPILOT_RAG_MODEL_CACHE` | BGE 模型快取目錄 | `HF_HOME` 或 `~/.cache/huggingface` | settings.py:59-60、96 |
| `ROOMPILOT_RAG_DEVICE` | `auto`／`cuda`／`mps`／`cpu` | `auto` | settings.py:97、model_runtime.py:90-94 |
| `ROOMPILOT_RAG_TIMEOUT_SECONDS`／`ROOMPILOT_RAG_OPENAI_TIMEOUT_SECONDS`／`ROOMPILOT_RAG_REASONING_EFFORT`／`ROOMPILOT_RAG_ANTHROPIC_MAX_TOKENS` | 解析呼叫細部參數 | `30`／`30`／`low`／`4096` | settings.py:72-95 |

### 3.5 遠端渲染 provider（選配）

| 變數 | 用途 | 預設值 | 證據 |
| :--- | :--- | :--- | :--- |
| `ROOMPILOT_RENDER_PROVIDER_URL`／`_TOKEN`／`_NAME`／`_TIMEOUT_SECONDS` | 泛用遠端渲染 job 端點 | 空／空／`remote_renderer`／`60` | render_service.py:34-44 |

## 4. 啟動、停止與驗證

| 動作 | 指令 | 說明 |
| :--- | :--- | :--- |
| 啟動 | `.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload` | README.md:63；port 8002 被占用改 `--port 8023` 等（README.md:68） |
| 停止 | 前景執行，`Ctrl+C` 終止 uvicorn | 無 service／daemon 化 |
| 驗證（基線） | `.\.venv\Scripts\python.exe -m pytest -q`＋`git diff --check`＋`git status --short` | README.md:121-124；對照 yen HEAD 既有失敗基準（ACPT-016） |
| 驗證（可用性） | `GET /api/catalog/status`、`/api/ai-render/status`、`/api/delivery-proposal/status`、`/api/rag/status`、`/api/agent/pipeline/status` | main.py:3144、2064、2378、rag_api.py:164、main.py:3504 |

部署前檢查（Pilot 精簡版）：`.env` 就緒（§3）→ PostgreSQL 起動且 catalog 回滿 8,675 筆（ACPT-012）→ Chromium 已裝（如需交付 PDF）→ pytest 基線 → 啟動 → status 端點掃一輪。

## 5. 資料位置與備份

執行資料集中於 `<repo 根>/.runtime/`（worktree 共用，`ROOMPILOT_RUNTIME_DIR` 可覆蓋；不得提交 git，README.md:399）：

| 路徑 | 內容 | 證據 |
| :--- | :--- | :--- |
| `.runtime/projects.sqlite3` | 專案、workflow JSON、render metadata（SQLite，WAL mode → 同目錄 `-wal`/`-shm` 檔須一起備份，或用 `sqlite3 .backup`） | project_store.py:84、93 |
| `.runtime/uploads/` | 上傳的原始平面圖 | project_store.py:82 |
| `.runtime/renders/` | 第 7 步 3D 截圖 PNG（生圖 img2img 參考） | project_store.py:83 |
| `.runtime/manuals/<project_id>/` | 設計手冊／交付提案 PDF | main.py:2290-2291 |
| PostgreSQL `roompilot_db` | 家具 catalog、向量、runtime catalog | postgres_catalog.py:92 |
| RAG 模型快取 | `HF_HOME` 或 `~/.cache/huggingface`（repo 外，約 9 GB） | settings.py:59-60 |

備份程序：**無自動備份（TO-BE）**。手動備份＝停機後整份複製 `.runtime/`＋`pg_dump roompilot_db`。PostgreSQL 家具資料可由 `scripts/sql/import_official_catalog_to_postgres.py` 重灌（先 `--dry-run`；`--replace-existing` 須人工確認並重灌向量，README.md:326-335）；但 **project store／runtime catalog 的 Phase 3/4 schema 與 migration 腳本不在本 repo 工具樹，新環境無法從零重建**（README.md:321）。AI 生圖結果存於 workflow JSON `ai_render` 節點，隨 SQLite 一起備份（main.py:2117-2126）。

## 6. CI/CD 與部署策略

| 項目 | 現況 |
| :--- | :--- |
| CI 流水線 | **無**（TO-BE）；驗證靠本機 `pytest -q`＋`git diff --check`（README.md:121-124） |
| 環境晉升（dev→staging→prod） | **無**；單一本機環境 |
| Blue-Green／Rolling／Canary | **不適用**（單機前景行程） |
| Artifact／容器化 | **無**；直接以 git working tree 執行 |

## 7. 監控與告警

**無監控與告警系統（TO-BE）。** 現有可觀測性僅：uvicorn 主控台日誌，與 §4 列出的五個 status 端點（人工查詢；RAG status 會回 `blockers` 明細，service.py:75-114）。README 提及的 `GET /api/health`（Phase 5 契約）在本分支 `main.py` 中**不存在**（見 §10）。

## 8. 升級與回滾（git 層面）

無獨立部署產物，升級＝切換 git working tree 版本後重啟 uvicorn：

1. 升級前記錄現行 commit：`git rev-parse HEAD`；有未提交變更先處理（不得 stash 帶過，.claude/rules/git-workflow.md）。
2. `git fetch origin` → 檢視差異（`git diff --name-status`、`git log --oneline`）→ 切至目標 commit／分支。
3. 依賴變更時重跑 `install.ps1`（或對應 `uv pip install -r ...`）。
4. 重啟 uvicorn → 跑 §4 驗證。
5. 回滾＝`git switch` 回步驟 1 記錄的 commit → 重啟。破壞性操作（`reset --hard` 等）前先打 backup tag（git-workflow.md）。

資料層注意：SQLite schema 由 `ProjectStore._initialize` 啟動時自動 `CREATE TABLE IF NOT EXISTS`＋補欄位（project_store.py:96-142），舊版程式讀新版資料庫**無降版遷移**——回滾前先備份 `.runtime/`（§5）。

## 9. 已知運維風險

| 症狀 | 影響 | 處置 |
| :--- | :--- | :--- |
| 第 8 步交付提案回 503 `delivery_engine_not_configured` | 無法產出提案 PDF（ACPT-011） | [runbook-delivery-proposal-503.md](./runbook-delivery-proposal-503.md) |
| 第 6 步家具清單空／provider 回 `json_fallback, available=False` | catalog 不可用或不足 8,675 筆（ACPT-012） | [runbook-catalog-db-unavailable.md](./runbook-catalog-db-unavailable.md) |
| 保存工作流回 409 `project_revision_conflict` | 多分頁互踩，落後方被拒（ACPT-014） | [runbook-workflow-revision-conflict.md](./runbook-workflow-revision-conflict.md) |
| `/rag` 不可用，status 回 `*_cache_missing` blockers | RAG 模型快取缺失，offline-only 不自動下載 | [runbook-rag-model-cache-missing.md](./runbook-rag-model-cache-missing.md) |

另：`OPENROUTER_API_KEY` 未設時第 7/8 步生圖端點回 503（main.py:2110-2116），屬設定缺失而非故障，依 §3.3 補設定即可。

## 10. 待確認

1. **Python 版本漂移**：README／install 腳本基準 3.12（README.md:13、install.ps1:44），本機現存 `.venv` 實測 3.14.6（uv 管理、無 pip）。何者為正式基準須由 owner 拍板並同步文件。
2. **README 安裝段引用的檔案不存在**（yen@8863a36c 實測）：`.env.example`（README.md:48、62）、`requirements-rag.txt`（README.md:97；RAG 依賴實際已併入 requirements.txt:33-37）、`scripts/rag/prefetch_models.py`（README.md:98-100、install.ps1:15）。RAG 模型快取目前無 repo 內建置腳本，離線包取得方式待確認。
3. **`GET /api/health` 不存在**：README.md:318 稱 Phase 5 已提供，本分支 `main.py` 無此 route。
4. **`ROOMPILOT_RUNTIME_CATALOG_PROVIDER` 無程式讀取**：README.md:296 的 `.env` 範例含此變數，backend 全樹 grep 無命中；疑為文件殘留。
5. **工程文件 MVP 段落與本分支不符**：README.md:159-191 的 `/engineering` 頁、`ROOMPILOT_DEMO_MODE`、`ROOMPILOT_ARTIFACT_*` 在 `backend/server/` 無對應程式碼。
6. **備份策略未定**：§5 的手動備份為建議做法，備份頻率、保存位置與還原演練由 owner 決定（TO-BE）。
7. **`.env` 優先序不一致**（§3 開頭）是否統一，待 owner 決定。

## 11. 追溯與相關文件

| 項目 | ID／來源 |
| :--- | :--- |
| 上游 | NFR-002/003（[../00-registry.md](../00-registry.md) §2.2）、ACPT-011/012/014/015/016（§2.3）、ADR-003（[../03_architecture/adr/ADR-003-catalog-postgres-first-json-fallback.md](../03_architecture/adr/ADR-003-catalog-postgres-first-json-fallback.md)）、ADR-005（[../03_architecture/adr/ADR-005-agent-pipeline-parallel-flag.md](../03_architecture/adr/ADR-005-agent-pipeline-parallel-flag.md)）、ADR-007（[../03_architecture/adr/ADR-007-workflow-json-single-snapshot-store.md](../03_architecture/adr/ADR-007-workflow-json-single-snapshot-store.md)） |
| 證據來源 | README.md、install.ps1、requirements*.txt、scripts/README.md、`backend/server/`＋`backend/catalog/`＋`backend/spatial_data/rag/` 程式碼（git yen@8863a36c，行號皆經實讀） |
| 下游 | 同目錄四份 runbook（§9）、[../05_qa/test_plan.md](../05_qa/test_plan.md)（環境前置條件）、[../03_architecture/sad.md](../03_architecture/sad.md) §部署視圖 |
