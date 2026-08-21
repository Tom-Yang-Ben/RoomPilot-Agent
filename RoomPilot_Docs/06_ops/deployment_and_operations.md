# 部署與維運指南 (Deployment and Operations) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-OPS（Bella 整合）；服務邊界（DEC-014）與資料保存政策（DEC-015）的欄位權威為產品 owner（[`requirements_tracker.xlsx`](../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ①需求決策）
> **語域:** L3（工程）——直接寫指令、環境變數、路徑與失敗行為
> **實例:** 單例（整個 RoomPilot 一份）
>
> **本文件回答**：這套系統怎麼裝起來、用什麼指令啟動、需要哪些環境變數與外部相依、沒有健康檢查時拿什麼替代、執行資料長在哪裡、以及**本 repo 現在沒有哪些維運機制**。
> **本文件不含**：單一症狀的處置步驟（見 §9 的 `runbook-*`）、部署拓撲的架構視圖與取捨理由（見 [`../03_architecture/diagrams/deployment_topology.md`](../03_architecture/diagrams/deployment_topology.md) 與 [`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md)）、端點欄位契約（見 [`../04_design/api_spec.md`](../04_design/api_spec.md)）、資料表結構（見 [`../04_design/db_design.md`](../04_design/db_design.md)）、測試基準線（見 [`../05_qa/test_plan.md`](../05_qa/test_plan.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 部署形態](#1-部署形態)
- [2. 安裝與啟動](#2-安裝與啟動)
- [3. 環境變數總表](#3-環境變數總表)
- [4. 外部相依供應](#4-外部相依供應)
- [5. 健康檢查與可觀測性](#5-健康檢查與可觀測性)
- [6. 執行資料佈局與成長](#6-執行資料佈局與成長)
- [7. 本 repo 沒有的維運機制](#7-本-repo-沒有的維運機制)
- [8. 部署檢查清單](#8-部署檢查清單)
- [9. Runbook 索引](#9-runbook-索引)
- [10. 待確認](#10-待確認)
- [11. 追溯](#11-追溯)

---

## 1. 部署形態

**AS-IS：單機、單行程、回送位址。** 無 dev／staging／production 三環境晉升，無容器化應用映像（repo 內無 `Dockerfile`），唯一被容器化的元件是 PostgreSQL。

| 元件 | 形態 | 佐證 |
| :--- | :--- | :--- |
| 應用伺服器 | 單一 uvicorn 行程掛 `FastAPI`，唯一中介層是 `GZipMiddleware(minimum_size=1024)`；**無 CORS、無認證、無 rate limit** | `main.py:195-196` |
| 前端 | 同行程靜態檔（`backend/server/static/`），不另起 web server | `main.py:125` |
| 路由總數 | 60 條 `@app.*` ＋ 5 條 `@router.*`（RAG）＝ 65 | `main.py`、`rag_api.py` 實測計數 |
| 資料庫（專案狀態） | 本機 SQLite 檔，隨行程啟動開啟 | `main.py:147-149`；`runtime_paths.py:20-25` |
| 資料庫（家具型錄） | 外部 PostgreSQL 17 ＋ pgvector，容器或原生皆可 | `docker-compose.yml:16` |
| 反向代理／負載均衡／CDN（自營） | **無** | 無設定檔；GLB 與型錄圖走第三方 CloudFront，見 §4 |
| 網路邊界 | 僅 `--host 127.0.0.1`（回送位址），**是否為既定範圍待 DEC-014 核准** | `README.md:49`；NFR-019、OPEN-02 |

啟動時會把 legacy worktree 的 `.runtime/` 合流進共用資料庫（`updated_at` 決勝、上傳檔 `copy2`、render `INSERT OR IGNORE`），這是**每次啟動都會跑**的副作用，不是一次性遷移（`main.py:148-149`；`runtime_paths.py:28-53`；FR-008）。

---

## 2. 安裝與啟動

### 2.1 一鍵安裝

| 步 | Windows（`install.ps1`） | Linux（`install.sh`） | 佐證 |
| :--- | :--- | :--- | :--- |
| 1 建 venv | `py -3.12 -m venv .venv`（或 `uv venv --python 3.12`，`-Uv` 時） | `uv venv --python 3.12 .venv`（**強制 uv**，缺 uv 直接 exit 1） | `install.ps1:41-51`；`install.sh:26-36` |
| 2 Python 相依 | `-r requirements-ocr.txt`（內含 `requirements.txt`）；`-SkipOCR` 時只裝基線 | 同左，旗標為 `--skip-ocr` | `install.ps1:54-60`；`install.sh:39-45` |
| 3 交付 PDF | `-r requirements-delivery.txt` ＋ `playwright install chromium` | 同左（另提示 `playwright install-deps`） | `install.ps1:63-66`；`install.sh:48-51` |
| 4 前端 npm | `npm --prefix frontend install`；缺 npm 只警告不中斷 | 同左，旗標為 `--skip-frontend` | `install.ps1:69-76`；`install.sh:54-61` |

**不含**：檢索模型權重（腳本註解記約 9 GB 下載量），需另行預備，見 §4.2（`install.ps1:15`；`install.sh:11`）。

### 2.2 啟動

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload
```

佐證 `README.md:48-49`；安裝腳本結尾印出同一行（`install.ps1:78-79`；`install.sh:64-65`）。連接埠被占用時改 `--port`（`README.md:68`）。`--reload` 屬開發旗標；**Pilot 是否應關閉 reload、是否需要行程守護（systemd／NSSM／工作排程）待確認**，repo 內無任何服務單元檔。

### 2.3 Python 版本落差（NFR-023）

| 來源 | 版本 | 佐證 |
| :--- | :--- | :--- |
| 專案宣告 | `requires-python = ">=3.12"` | `pyproject.toml:5` |
| 安裝腳本釘選 | 3.12 | `install.ps1:43,47`；`install.sh:34` |
| 現場虛擬環境 | **3.13.5**（`home = C:\Python313`，由 uv 0.11.26 建立） | `.venv/pyvenv.cfg` |

現場環境非由本 repo 腳本產出。落差本身不違反 `>=3.12`，但**測試基準線（NFR-024）是在 3.13.5 上取得的，與腳本承諾的 3.12 不同**；要不要把宣告收斂到 3.13 或把現場降回 3.12，待確認。

---

## 3. 環境變數總表

全表由 `rg "os.environ|os.getenv"` 於 `backend/` 逐點核對而得。**外接模型 id 一律走
`backend/model_config.py` 的 `REGISTRY`**——哪個功能用哪顆、對應哪個變數、內建預設是什麼，
以那張表為準；本表只列變數本身。**兩套 `.env` 讀取順序相反**，同名變數在型錄與檢索兩邊行為不同：型錄側 `os.getenv` 優先於 `.env` 檔（`postgres_repository.py:194-196`），檢索側 `.env` 檔優先於 `os.getenv`（`spatial_data/rag/settings.py:23-28`，註解說明是刻意避免父行程環境污染）。另有兩支服務會把 `.env` 內容寫回 `os.environ`（`scene_service.py:56-70`；`intake_service.py:25-40`）。

| 變數 | 預設 | 作用 | 佐證 |
| :--- | :--- | :--- | :--- |
| `ROOMPILOT_CATALOG_PROVIDER` | `postgres` | `json`／`local`／`fallback` → 走已驗證 JSON；其餘（含未設）→ PostgreSQL | `postgres_repository.py:199-204` |
| `DB_HOST`／`DB_PORT`／`DB_NAME`／`DB_USER`／`DB_PASSWORD` | `localhost`／`5432`／`roompilot_db`／`postgres`／空 | 型錄與向量連線 | `postgres_repository.py:213-217` |
| `DB_CONNECT_TIMEOUT` | `3`（秒） | 連線逾時 | `postgres_repository.py:218` |
| `DB_SSLMODE`／`DB_APPLICATION_NAME` | `disable`／`roompilot_catalog_api` | 連線屬性 | `postgres_repository.py:219-222` |
| `DB_POOL_MIN`／`DB_POOL_MAX` | `1`／`8` | `ThreadedConnectionPool` 上下界（NFR-007） | `postgres_repository.py:241-242` |
| `DB_ADMIN_DB` | `postgres` | 容器初始化用資料庫名 | `docker-compose.yml:13` |
| `OPENROUTER_API_KEY` | 空 | 生圖／色卡／改圖／文案 LLM 唯一金鑰；未設 → 503 | `ai_render_service.py:67`；`agent/llm.py:133`；`main.py:2107-2115` |
| `OPENROUTER_MODEL`／`OPENROUTER_MODELS` | 空 | 文字模型單選／逗號清單；**各功能專屬變數優先**，這兩個只是共用回退池 | `model_config.py:REGISTRY` |
| `OPENROUTER_SITE_URL`／`OPENROUTER_APP_NAME` | `http://127.0.0.1:8002`／`roompilot` | OpenRouter 歸因標頭 | `agent/llm.py:144-146` |
| `ROOMPILOT_INTAKE_MODEL` | 空（回落 `qwen/qwen3-32b:free`） | 第 1 步問卷需求抽取 | `model_config.py`；`intake_service.py:_models` |
| `ROOMPILOT_SCENE_MODEL` | 空（回落 `qwen/qwen3-32b:free`） | 第 6 步 LLM 場景規劃 | `model_config.py`；`scene_service.py:get_openrouter_models` |
| `ROOMPILOT_AGENT_TEXT_MODEL` | 空（回落 `openrouter/auto`） | agent 通用文字（優先於 `OPENROUTER_MODEL`） | `model_config.py`；`agent/llm.py:default_text_model` |
| `ROOMPILOT_REPORT_MODEL` | 空（回落 `openai/gpt-5.6-luna`） | 第 8 步設計手冊／交付提案文案 | `model_config.py`；`agent/llm.py:report_model` |
| `ROOMPILOT_AGENT_LLM_TIMEOUT` | `120`（秒） | agent 側 LLM 逾時（NFR-011） | `agent/llm.py:147-148` |
| `ROOMPILOT_GENPIC_MODEL`／`..._FALLBACK_MODEL` | 空（回落 `google/gemini-3.1-flash-image`／`google/gemini-2.5-flash-image`） | 第 8 步逐房生圖主／備模型 | `model_config.py`；`ai_render_service.py:ai_render_status` |
| `ROOMPILOT_GENPIC_PALETTE_MODEL`／`..._PALETTE_FALLBACK_MODEL` | 空（回落 `google/gemini-3-pro-image-preview`／第 8 步主模型） | 第 7 步色卡模型 | `model_config.py`；`ai_render_service.py:_palette_gateway` |
| `OPENROUTER_SCENE_PLANNING_ENABLED` | 未設＝關 | `=1` 才啟用第 6 步 LLM 場景規劃 | `scene_service.py:96,103,377` |
| `OPENROUTER_INTAKE_ENABLED` | 未設＝關 | `=1` 才啟用進件 LLM 解析 | `intake_service.py:138,157` |
| `ROOMPILOT_AGENT_PIPELINE` | 未設＝關 | 並存 MasterAgent 管線旗標；`""/0/false/no/off` 皆視為關（FR-053） | `agent_pipeline_service.py:31,43` |
| `ROOMPILOT_RAG_ENABLED` | `false` | 檢索總開關（安全預設） | `rag/settings.py:76` |
| `ROOMPILOT_RAG_MODEL_CACHE`／`HF_HOME` | 未設 → `~/.cache/huggingface` | 模型權重快取根目錄 | `rag/settings.py:59-60,96` |
| `ROOMPILOT_RAG_DEVICE` | `auto` | `cpu`／`cuda` 覆寫 | `rag/settings.py:97` |
| `ROOMPILOT_RAG_PARSER_PROVIDER`／`..._PARSER_MODEL`／`..._REASONING_EFFORT`／`..._TIMEOUT_SECONDS`／`..._ANTHROPIC_MAX_TOKENS` | `openai`／依 provider／`low`／`30`／`4096` | 檢索 parser 設定 | `rag/settings.py:61-95` |
| `OPENAI_API_KEY`／`ANTHROPIC_API_KEY` | 空 | 檢索 parser 金鑰（只需所選 provider） | `rag/settings.py:78-79` |
| `ROOMPILOT_RUNTIME_DIR` | 未設 → repo 根 `.runtime/` | 覆寫執行資料根目錄 | `runtime_paths.py:20-25` |
| `ROOMPILOT_RENDER_PROVIDER_URL`／`..._TOKEN`／`..._NAME` | 空／空／`remote_renderer` | 外部 render provider（現況未接） | `render_service.py:41-49` |
| `ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS` | `60`，夾在 5–180 | 同上逾時 | `render_service.py:33-38` |
| `ROOMPILOT_CLOUDFRONT_BASE_URL` | `https://ddgsm1yg3xikc.cloudfront.net` | GLB 與型錄圖 CDN | `services/cloud_models.py:32,67`；`services/cloud_images.py:54` |
| `ROOMPILOT_MODEL_DELIVERY_MODE` | `cloudfront` | GLB 交付模式 | `services/cloud_models.py:47` |
| `ROOMPILOT_GLB_MANIFEST_PATH`／`ROOMPILOT_IMAGE_MANIFEST_PATH`／`ROOMPILOT_CLOUD_CATALOG_PATH` | 內建 `JSON/` 路徑 | 資產索引覆寫（相對路徑以 repo 根解析） | `main.py:117-140`；`services/cloud_images.py:59` |
| `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` | 空 | 外部 GLB 壓縮檔搜尋根 | `main.py:293` |
| `ROOMPILOT_PDF_FONT` | 空 | 設計手冊 PDF 字型覆寫 | `agent/tools/render_pdf.py:39` |
| `ROOMPILOT_OCR_DISABLED` | 未設 | `=1` 關閉印刷房名／尺寸 OCR | `main.py:156-160` |
| `FP2DXF_VLM`／`FP2DXF_SVM`／`FP2DXF_SEG`／`SYMBOL_KINDS`／`ROOM_HEAD`／`OPENROUTER_VISION_MODELS` | `auto`／未設／未設 `=0` 才關／`kstove,ksink`／內建路徑／空（回落三顆免費視覺模型） | 辨識管線旁路開關；視覺模型池見 `model_config.py` 的 `floorplan_vision` | `vlm_judge.py:get_vision_models,67`；`opening_classifier.py:38`；`seg_infer.py:34`；`symbol_match.py:49`；`room_classifier.py:24` |

`.env` 位於 repo 根、由 `.gitignore:2` 排除；`.env.example` 為範本，`README.md:48` 要求先複製。

---

## 4. 外部相依供應

### 4.1 PostgreSQL（Docker 一鍵，FR-066／ACPT-057）

**供應資料庫的 compose 只有一份**：根目錄 `docker-compose.yml` 的 `db` 服務（`:14-39`）。全堆疊（db／web／chromium ＋ profile `rag`／`frontend`）的拆解理由見 [`docker/README.md`](../../docker/README.md)。

> **合併紀錄（2026-08-22）**：`docker_postgresql/` 下原本另有一份只起 DB 的 compose，容器名與本份撞車導致無法同時啟動，現已合併刪除。合併前逐張比對兩份 volume 的內容：25 張表的**精確列數**與**內容 md5**（含全部 8,076 條向量）完全相同，schema DDL 差異僅 `pg_dump` 每次隨機產生的 `\restrict` nonce 與等價的 ARRAY 轉型渲染（歸一化後差異 0 行），因此無資料需要搬遷。容器名 `roompilot-postgres` 沿用至 `db` 服務（`:19`），既有 runbook 的 `docker exec roompilot-postgres …` 不受影響。舊資料留在具名 volume `roompilot-agent_roompilot_pgdata`，本份既不讀也不動。

`db` 服務：映像 `pgvector/pgvector:pg17`（官方 PostgreSQL 17 ＋ pgvector，`:16`）、埠 `${DB_HOST_PORT:-${DB_PORT:-5432}}:5432`（`:27`；`DB_HOST_PORT` 供主機已跑原生 PostgreSQL 時避開衝突，容器之間一律走 `db:5432`）、具名 volume `roompilot_pgdata`（`:29` 的 `pgdata` ＋ 專案名 `roompilot`）、healthcheck `pg_isready -U ${DB_USER:-postgres}` 每 5 秒／逾時 3 秒／重試 20 次（`:34-38`）。`DB_PASSWORD` 未設直接失敗（`:22` 的 `:?` 語法）。

**空 volume 首次啟動才會還原 dump**；volume 已存在時換新 dump 不生效，須先 `docker compose down -v`（`DOCKER_ONECLICK.md:42`）。dump 約 55 MB，由 `.gitattributes` 以 Git LFS 追蹤（`*.sql.gz`），並由 `.gitignore:106` 排除 `roompilot_db_dump.sql*` 的一般提交路徑。

> **路徑不一致已修正（2026-08-22，見 §10）**：原本掛載來源寫 `./scripts/sql/roompilot_db_dump.sql.gz`，但該相對路徑以 compose 檔所在的 `docker_postgresql/` 解析，而該目錄下無 `scripts/`，實檔在 `docker_postgresql/roompilot_db_dump.sql.gz`（54.8 MB）——docker 會把不存在的來源建成空目錄，自動還原靜默不發生。現改掛整個資料夾（`:33` 的 `./docker_postgresql:/docker-entrypoint-initdb.d:ro`）；postgres 只執行 `*.sql`／`*.sql.gz`／`*.sh`，同目錄的 `.md`／`.yml` 會自動略過。

驗證指令（`DOCKER_ONECLICK.md:29`）——容器名與 compose 服務名兩種寫法皆可：

```powershell
docker exec roompilot-postgres psql -U postgres -d roompilot_db -c "SELECT count(*) FROM roompilot.furniture_catalog_api_current;"  # 期望 8076
docker compose exec -T db psql -U postgres -d roompilot_db -tAc "SELECT count(*) FROM roompilot.furniture_catalog_api_current;"     # 期望 8076
```

**實跑證據（2026-08-22，根目錄 compose，空 volume）**：`vector` extension 已啟用；`roompilot.furniture_catalog_api_current` 與第 6 步實際讀的 view `roompilot.furniture_catalog_current` 皆回 **8076**。

### 4.2 檢索模型權重（offline-only，NFR-010）

`SentenceTransformer` 與 `CrossEncoder` 皆以 `local_files_only=True` 載入，未快取直接 `RagDependencyError`，**絕不在請求路徑下載**（`model_runtime.py:100-127`）。容量兩個數字不同義：**下載／磁碟約 9 GB**（`README.md:43`；`install.ps1:15`），**常駐記憶體約 4.6 GB**（`README.md:106`；`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md:102`，該處建議至少 8 GB VRAM）。

> **文件指向不存在的腳本**：`README.md:98-100` 與 `install.ps1:15`／`install.sh:11` 都要求跑 `scripts/rag/prefetch_models.py --download` 預備權重，但本分支 `scripts/` 下**無 `rag/` 子目錄、全 repo 找不到 `prefetch_models*`**。屬 OPEN-25 同一類（README 記載本分支不存在的產物）。

### 4.3 其他外部相依

| 相依 | 失敗表現 | 佐證 | Runbook |
| :--- | :--- | :--- | :--- |
| OpenRouter（生圖／色卡／改圖／文案） | 未設金鑰 503；上游拒絕 502；主模型 3 次 ＋ fallback 3 次後 `GenPicFailure` | `main.py:2107-2115`；NFR-012 | RB-002 |
| PDF 排版引擎（Playwright Chromium 子行程） | 缺 `build_pdf.py` 或缺 `playwright` → 503 `delivery_engine_not_configured` 並附安裝指令；排版逾時 180 秒；失敗 502 `delivery_proposal_failed` | `agent/skills/delivery/__init__.py:43-56,274-296`；`main.py:2399-2406` | RB-005 |
| CloudFront（GLB／型錄圖） | `/model` 307 導向；`model.gltf`／`buffer.bin`／`images/{i}` 410；前端以 fallback 替身呈現並附中文原因 | FR-042 | RB-008 |

---

## 5. 健康檢查與可觀測性

**本 repo 無 `/health`／`/healthz`／`/readyz` 端點**（`main.py` 與 `rag_api.py` 的路由裝飾器逐條核對後無此類路徑），也無 metrics 匯出。替代方案是七個具名狀態端點；它們皆只回布林與原因字串，不外洩金鑰、token 或伺服器檔案佈局（FR-067、NFR-020）。

| 端點 | 判讀 | 佐證 | Runbook |
| :--- | :--- | :--- | :--- |
| `GET /api/catalog/status` | `available:false` ＋ `reason`（例外類別名）＝ 型錄 DB 不可用，Web 不整體停擺 | `main.py:3144`；`postgres_repository.py:748,843-850` | RB-001 |
| `GET /api/ai-render/status` | 生圖服務是否已設定（不回 token） | `main.py:2064`；`ai_render_service.py:67-72` | RB-002 |
| `GET /api/delivery-proposal/status` | 排版引擎是否可用；不可用時附安裝指引 | `main.py:2378` | RB-005 |
| `GET /api/render-provider/status` | 外部 render provider 是否設定（`configured`／`has_token`） | `main.py:2028`；`render_service.py:41-49` | — |
| `GET /api/scene/provider-status` | 第 6 步 LLM 場景規劃是否啟用 | `main.py:3331`；`scene_service.py:90-103` | — |
| `GET /api/agent/pipeline/status` | 旗標開關與 gateway 狀態；**旗標關閉時仍可查** | `main.py:3504`；`agent_pipeline_service.py:45-50` | — |
| `GET /api/rag/status` | 10 種具名 blocker；不載模型也不呼叫 LLM | `rag_api.py:164`；FR-046 | RB-004 |

**日誌**：全 `backend/` 僅 5 個檔案 `import logging`（`agent/place.py`、`agent/select.py`、`floorplan/cody_adapter.py`、`floorplan/vision/ocr.py`、`rag/openrouter_parser.py`），無任何 `basicConfig` 或 handler 設定，亦無日誌檔輪替。實務上可觀測的只有 uvicorn 預設輸出到終端機的存取日誌。

---

## 6. 執行資料佈局與成長

根目錄由 `ROOMPILOT_RUNTIME_DIR` 決定，未設時為 repo 根 `.runtime/`（`runtime_paths.py:20-25`），並由 `.gitignore:16` 整目錄排除。

| 路徑 | 內容 | 2026-08-12 實測（`du -sh .runtime/*`） |
| :--- | :--- | :--- |
| `projects.sqlite3`（＋`-wal`／`-shm`） | 專案與八步 `workflow_json` 單一快照 | **67 MB** |
| `uploads/<project_id>/` | 原始平面圖，固定檔名、重傳直接覆蓋 | **115 MB**（451 個專案目錄） |
| `manuals/<project_id>/` | 設計手冊／交付提案 PDF ＋ 文案側車 JSON | **45 MB**（3 個專案） |
| `renders/<project_id>/` | 瀏覽器輸出 PNG（僅追加） | 0（本機未產生） |
| `indexes/questionnaire_visuals.sqlite3` | 問卷影像索引，每次 `sync()` 清表重灌 | 232 KB |
| `agent_pipeline/<project_id>.json` | 並存管線側寫（刻意不進 workflow blob） | 0（旗標未啟用） |
| `engineering/`、`auth_secret.key` | **來源不明**：`backend/` 內無任何寫入點（`rg auth_secret backend/` 零命中） | 208 KB／1 KB |
| 合計 | — | **226 MB** |

> SRS NFR-022 記 `uploads/` 為 114 MB，本文件量到 115 MB，屬同日不同時點的量測差，不是矛盾。

**無配額、無輪替、無備份腳本、無專案刪除 API**（NFR-022）。全 `backend/server/*.py` 只有兩處刪除：`project_store.py:401` 的 **render 存檔失敗回滾** `unlink(missing_ok=True)`（`save_render()` 的 `except` 分支；上傳路徑 `save_upload()` 沒有 unlink，寫檔後才更新 DB，交易失敗會留下孤兒檔，見 RB-009 §3.4），與 `questionnaire_visuals.py:182-183` 的索引重灌 `DELETE FROM`。既無 TTL、也無 `VACUUM`。**備份頻率、保留天數、結案交還或刪除程序、責任人一律待 DEC-015 核准（OPEN-13）**，處置面見 RB-009。

---

## 7. 本 repo 沒有的維運機制

模板 §2／§4／§5／§6 對應的機制在本分支**均不存在**。誠實登記，不以 TO-BE 充數：

| 模板要求 | 本 repo 現況 | 佐證 |
| :--- | :--- | :--- |
| CI/CD 流水線 | **無**：無 `.github/`、`.gitlab-ci.yml`、`Jenkinsfile`、`.circleci` | 目錄不存在 |
| lint／type-check／覆蓋率 | **無**：`pyproject.toml` 只有 `[tool.pytest.ini_options]` 與 `[tool.setuptools]`，無 ruff／mypy／black／coverage 設定 | `pyproject.toml:63-66` |
| 環境晉升（dev→staging→prod） | **無**：只有一個本機環境，無 artifact／image digest 概念 | 無 `Dockerfile` |
| 部署策略（Blue-Green／Rolling／Canary） | **無**：單行程，部署＝停掉再啟動 | §1 |
| 監控、指標、告警 | **無**：無 metrics 端點、無 Prometheus／Grafana／Datadog 設定、無告警規則 | §5 |
| 自動回滾 | **無**：回滾＝`git checkout` 舊 commit 後重啟；`.runtime/` 資料**不隨程式碼回滾**，且無快照可還原 | §6 |
| DB migration 機制 | **無**：SQLite schema 由 `ProjectStore` 啟動時建立；PostgreSQL 由匯入器交易式重建 | `main.py:147` |
| 測試基準線 | 有實測、但**紅燈未收斂**：SRS NFR-024 記 2026-08-12 實跑 947 收集／905 passed／35 failed／7 skipped（本文件未重跑） | `srs.md` NFR-024、OPEN-46 |

---

## 8. 部署檢查清單

新機安裝（照序）：

- [ ] Docker Desktop 已安裝；於 repo 根建立 `.env` 並填 `DB_PASSWORD`（`.env.example` 複製）
- [ ] 確認 dump 檔實際位置與 `docker-compose.yml:19` 掛載來源一致（見 §4.1 的路徑不一致）
- [ ] `docker compose up -d` 後以 `SELECT count(*) … = 8076` 驗證還原成功
- [ ] 跑 `install.ps1` 或 `install.sh`；確認 `.venv` 的 Python 版本與 §2.3 的決議一致
- [ ] 需要檢索時：另行預備約 9 GB 模型快取（預備腳本本分支缺席，見 §4.2）並設 `ROOMPILOT_RAG_ENABLED=true`
- [ ] 需要生圖時：設 `OPENROUTER_API_KEY`；`playwright install chromium` 已完成（交付 PDF 相依）

啟動後煙霧驗證（無自動化，逐條人工打）：

- [ ] `GET /api/catalog/status` → `available:true`、`ready:true`
- [ ] `GET /api/ai-render/status`、`/api/delivery-proposal/status` → 依本次部署預期的 `configured`
- [ ] `GET /api/rag/status` → 啟用時 blocker 為空；未啟用時應是 `feature_disabled`
- [ ] 開 `http://127.0.0.1:8002/scene` 建一個空專案，確認 `PUT /workflow` 回 `revision` 遞增
- [ ] `du -sh .runtime` 記錄本次基準值（無自動監控，只能人工留底）

---

## 9. Runbook 索引

一個症狀一份。首要判讀訊號一律先看 §5 的狀態端點，再看端點回的錯誤碼。

| RB | 症狀 | 首要訊號 | 影響需求 |
| :--- | :--- | :--- | :--- |
| RB-001 | [型錄資料庫不可用](./runbook-catalog-db-unavailable.md) | `/api/catalog/status` → `available:false` ＋ `reason` | FR-040、FR-041、NFR-007、NFR-008 |
| RB-002 | [生圖服務失敗](./runbook-genpic-provider-failure.md) | 503 未設定／502 上游拒絕／重試耗盡 `GenPicFailure` | FR-056、FR-058、FR-060、NFR-012、NFR-014 |
| RB-003 | [存檔衝突或快照超限](./runbook-workflow-save-conflict-or-oversize.md) | 409 `project_revision_conflict`／413 `workflow_too_large` | FR-003、FR-004、FR-022、NFR-001、NFR-003 |
| RB-004 | [檢索模型快取缺失](./runbook-rag-model-cache-missing.md) | `/api/rag/status` 具名 blocker → 503 | FR-046、FR-049、NFR-010 |
| RB-005 | [交付 PDF 排版引擎缺席](./runbook-delivery-pdf-engine-missing.md) | 503 `delivery_engine_not_configured`（附安裝指令） | FR-061、FR-062、NFR-013 |
| RB-006 | [辨識失敗或複核被擋](./runbook-recognition-failed-or-review-blocked.md) | 422 `cody_recognition_failed`／`dxf_parse_failed`／`recognition_review_unresolved`；409 `floorplan_confirmation_required` | FR-007、FR-010、FR-011、FR-013 |
| RB-007 | [家具擺不下](./runbook-placement-blocked.md) | `placement.failed[]`／`unavailable_types[]`／`placement_resolution_report[]` | FR-034、FR-035、FR-037、NFR-015、NFR-016 |
| RB-008 | [GLB 資產取不到](./runbook-glb-asset-missing.md) | `/model` 307 後 410；前端 fallback 替身 ＋ 中文原因 | FR-042、NFR-021 |
| RB-009 | [執行資料成長](./runbook-runtime-storage-growth.md) | `du -sh .runtime` 人工比對；無告警 | NFR-022、NFR-025 |

---

## 10. 待確認

| 承接 | 待確認內容 | 目前可驗證的事實 | 阻擋 |
| :--- | :--- | :--- | :--- |
| OPEN-02（DEC-014） | Pilot 服務邊界是否即「僅本機／內網、不需帳號」；`--reload` 是否應在 Pilot 關閉；是否需要行程守護 | 全 app 無認證、無 CORS、無 rate limit，唯一邊界是 `--host 127.0.0.1`（`main.py:195-196`）；repo 內無服務單元檔 | NFR-019、ACPT-056 |
| OPEN-13（DEC-015） | 備份頻率、保留天數、配額告警閾值、結案交還／刪除程序、責任人 | `.runtime/` 226 MB 且無配額／輪替／備份／刪除 API（§6） | NFR-022、NFR-025、ACPT-058 |
| OPEN-25 同類 | `scripts/rag/prefetch_models.py` 在本分支不存在，README 與兩支安裝腳本仍指向它 | `scripts/` 下無 `rag/`；全 repo 無 `prefetch_models*` | FR-046、NFR-010 |
| ~~本文件新增~~ **已結（2026-08-22）** | ~~dump 掛載來源與檔案實際位置不一致，自動還原是否仍成立**未實跑驗證**~~ | 掛載改為整個 `docker_postgresql/` 資料夾；空 volume 實跑還原成功，兩個 view 皆 8076（§4.1）。「根目錄無 compose 檔」也已不成立——根目錄現有全堆疊 compose | FR-066、ACPT-057 |
| 本文件新增 | Python 版本以哪一個為準（宣告 `>=3.12`／腳本釘 3.12／現場 3.13.5） | `pyproject.toml:5`；`install.ps1:43`；`.venv/pyvenv.cfg` | NFR-023、ACPT-056 |
| 本文件新增 | `.runtime/engineering/`（208 KB）與 `.runtime/auth_secret.key` 的產生者與是否可刪 | `backend/` 內無任何寫入點 | NFR-022 |
| 本文件新增 | `.env` 讀取順序兩套相反（型錄 env 優先、檢索 file 優先）是否刻意；同名變數會有不同結果 | `postgres_repository.py:194-196` vs `rag/settings.py:23-28`（後者有註解說明理由） | NFR-014 |

---

## 11. 追溯

| 方向 | 內容 |
| :--- | :--- |
| 上游需求 | FR-065（一鍵安裝與啟動）、FR-066（Docker PostgreSQL）、FR-067（狀態端點群）、FR-008（legacy runtime 合流）、FR-041（provider 決策）、FR-046（RAG blocker）、FR-062（PDF 引擎 503）；NFR-007、NFR-010–014、NFR-019、NFR-020、NFR-022–025 |
| 上游決策 | [ADR-012](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md)（Pilot 回送部署形態）、[ADR-005](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)（型錄權威）、[ADR-008](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)（離線模型）、[ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)（伺服器治理生圖）、[ADR-011](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md)（旗標隔離）、[ADR-004](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)（單快照 SQLite） |
| 驗收與場景 | ACPT-056（安裝啟動與狀態端點不外洩）、ACPT-057（Docker 還原）、ACPT-058（維運政策，**受阻於 DEC-015**）、ACPT-059（測試基準線，**受阻於 DEC-019**）；SCN-035、SCN-036 |
| 測試 | TC-056、TC-057、TC-058、TC-059（見 [`../05_qa/test_plan.md`](../05_qa/test_plan.md)）；證據登錄於 [`../05_qa/qa_tracker.xlsx`](../05_qa/qa_tracker.xlsx) ②執行證據 |
| 上游文件 | [`../01_requirements/srs.md`](../01_requirements/srs.md)（FR／NFR 權威）、[`../01_requirements/brd.md`](../01_requirements/brd.md)（DEC-014／DEC-015）、[`../03_architecture/sad.md`](../03_architecture/sad.md)、[`../03_architecture/diagrams/deployment_topology.md`](../03_architecture/diagrams/deployment_topology.md) |
| 下游文件 | RB-001..RB-009 九份 runbook（§9）、[`../05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md`](../05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md)、[`../03_architecture/engineering_tracker.xlsx`](../03_architecture/engineering_tracker.xlsx) ①規格追溯 |
| 決策權威 | 服務邊界（DEC-014）與資料保存政策（DEC-015）屬產品 owner 權責，記於需求追蹤簿 ①需求決策、③Gate 簽核；本文件只記錄 AS-IS 與待確認項，**狀態為待 owner 核准** |
