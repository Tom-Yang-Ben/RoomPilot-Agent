# API 設計規範 - RoomPilot-Agent 後端（backend/server）

> 本文件由 VibeCoding v5.0 模板 04_design/api_design.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04 | **狀態:** 已發布（依現行程式碼逐條核對） | **OpenAPI 定義:** 由 FastAPI 自動生成（伺服器啟動後於 `/docs` 與 `/openapi.json` 取得）；工程文件 API 另維護靜態契約 `docs/contracts/engineering_openapi.yaml`

本文件描述 `backend/server/main.py` 中唯一的 FastAPI 應用（`app = FastAPI(title="AI 室內風格與家具配置展示系統")`，main.py:214）實際存在的**全部 63 條 HTTP 路由**：

| 來源檔 | 路由數 | 掛載方式 |
| :--- | :--- | :--- |
| `backend/server/main.py` | 46 | `@app.*` 直掛 |
| `backend/server/rag_api.py` | 5 | `app.include_router(rag_router)`（main.py:217；router 無 prefix，rag_api.py:26） |
| `backend/server/catalog_admin.py` | 4 | `app.include_router(catalog_admin_router)`（main.py:216；prefix=`/api/admin/furniture`，catalog_admin.py:29） |
| `backend/server/engineering/api.py` | 8 | `app.include_router(build_engineering_router(...))`（main.py:218-223；prefix=`/api/v1`，api.py:50） |

數法：`grep -rn -E '@(app|router)\.(get|post|put|delete|patch|head|options|websocket)\(' backend/server/ --include='*.py'` = 63 條；main.py 另以 `grep -c` 得 46 交叉驗證。2026-08-05 另以實際載入 app 逐條列舉交叉驗證（`from backend.server.main import app` 後展開 `app.routes` 與三個 include_router 的 `original_router.routes`）＝46＋4＋5＋8＝63，方法/路徑/掛載前綴全數相符。無 websocket、無 head/options 路由。63 條是本專案自行宣告的路由；FastAPI 另自動掛 4 條文件路由（`GET /openapi.json`、`GET /docs`、`GET /docs/oauth2-redirect`、`GET /redoc`），不計入本文件的 63 條。另有 2 個 StaticFiles 掛載（非路由）：`/static`（main.py:285）、`/docs-assets`（main.py:286）。

與 2026-07-26 舊導入版（44 條、全部集中 main.py）相比，本版新增三個 APIRouter 子系統：**家具 RAG runtime**（`backend/spatial_data/rag/` 經 rag_api.py 曝露）、**PostgreSQL 型錄管理 CRUD**（catalog_admin.py，Phase 2）、**工程文件 MVP**（engineering/，snapshot→lock→packages→jobs→documents，契約見 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`）。

---

## 1. 設計約定

| 項目 | 規範（現況照實描述） |
| :--- | :--- |
| **風格** | REST 風味但非嚴格 RESTful：資源型路徑（`/api/projects/{project_id}`、`/api/admin/furniture/{item_id}`）與動作型路徑（`/api/scene/generate`、`/api/floorplan/analyze`）並存。catalog_admin 與 engineering 兩個新 router 較貼近 RESTful（含 PATCH/DELETE 與 202 非同步 job） |
| **Base URL** | 程式碼未寫死 port；main.py 無 `__main__` 區塊。README.md:30、README.md:46 標準啟動：`uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload`（8002 被占用時改 8023，README.md:35）。無 production 網域 |
| **格式** | 回應以 `application/json`（UTF-8）為主；檔案上傳走 `multipart/form-data`；圖檔/GLB/xlsx 下載回 `FileResponse` / 二進位 `Response`；全站掛 `GZipMiddleware(minimum_size=1024)`（main.py:215） |
| **資源路徑** | 小寫；多字路徑段用連字符（`/api/render-provider/status`、`/api/v1/engineering-packages`）；路徑參數用 `snake_case`（`{project_id}`、`{furniture_id}`、`{item_id}`、`{job_id}`、`{package_id}`、`{document_id}`） |
| **欄位命名** | `snake_case`；長度欄位帶單位後綴 `_cm`（跨模組幾何一律公分）。少數舊契約同時接受 camelCase（workflow 內 privacy 確認 `project_only`/`projectOnly`、`no_training`/`noTraining`，`_floorplan_is_confirmed` 相容層 main.py:2310-2311） |
| **日期格式** | ISO 8601 UTC（`datetime.now(timezone.utc)`，如 `created_at`/`updated_at`；engineering JobStatus.updated_at 同，engineering/api.py:268） |
| **認證** | **僅 catalog_admin 4 條路由有認證**：`Authorization: Bearer <ROOMPILOT_CATALOG_ADMIN_TOKEN>`（`secrets.compare_digest` 比對，catalog_admin.py:186-200；token 讀取 postgres_admin_repository.py:69）＋選填 `X-RoomPilot-Admin-Actor` 操作者標頭。其餘 59 條路由皆無認證與授權；無 CORS middleware。對外呼叫遠端渲染供應商時由伺服器附 `Authorization: Bearer <ROOMPILOT_RENDER_PROVIDER_TOKEN>`（render_service.py:136） |
| **版本控制** | 混用三軌：(1) **engineering router 採 URL 版本前綴 `/api/v1`**（engineering/api.py:50，全站唯一）；(2) 專案樂觀鎖 `revision`（整數）與工程 snapshot 的 `revision` 字串；(3) 回應內 `schema_version` 欄位——scene payload/cost estimate/confirm 契約 `"1.0"`、client_brief `"1.1"`（intake_service.py:56）、RAG `"roompilot.rag.search.v1"`/`"roompilot.rag.status.v1"`/`"roompilot.rag.job.v1"`（service.py:461、service.py:107、rag_api.py:121）、前端 workflow 契約 `WORKFLOW_SCHEMA_VERSION = 2`（static/scene_workflow.js:1） |

### 主流程步驟（程式碼權威順序）

`PUT /api/projects/{project_id}/workflow` 的 `current_step` 只接受 11 個步驟名（main.py:183-195 的 `WORKFLOW_STEPS` set，只驗名稱不驗順序；順序由前端 `static/scene_workflow.js` 強制）：

```
project → upload → recognition → calibration → space_confirmation → requirements
→ layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render
```

---

## 2. 通用行為

### 分頁

（模板的游標分頁未採用。）只有 `GET /api/furniture` 有分頁，採頁碼式：`page`（≥1，預設 1）＋ `page_size`（1–80，預設 24；main.py:2714）；回應含 `total` 與 `has_next_page`。其餘列表端點一次回全部。

### 排序

無任何端點提供排序參數。`GET /api/projects/{id}/renders` 固定依 `created_at` 新到舊。

### 過濾

`GET /api/furniture` 以欄位名直接作 query 參數：`style`、`group`、`type`、`q`、`has_model`、`color`、`material`、`size`、`detail`（`card`|`scene`）。`GET /api/questionnaire/visual-catalog` 支援 `space_type` 與 `ready_only`。catalog_admin 讀取端點支援 `include_raw_data`（預設 false）。

### 冪等性與並行控制

- 用戶端對本伺服器不傳 `Idempotency-Key`（模板段落保留；現況未實作）。伺服器轉送遠端渲染任務時，自己對供應商附 `Idempotency-Key: <request_id>`（render_service.py:133）。
- 專案寫入採**樂觀鎖**：`PUT .../workflow`、`POST .../floorplan`、`POST .../renders` 皆吃 `expected_revision`；不符回 `409 project_revision_conflict`（main.py:2080、2130、2219），detail 附最新 `project` 供前端合併重試。
- catalog_admin 的 PATCH/DELETE 支援 `expected_updated_at`（必須帶時區，否則 422 `expected_updated_at_timezone_required`，catalog_admin.py:165-166、301-305）；衝突回 409（`CatalogAdminConflict` 映射，catalog_admin.py:214-215）。
- 工程 snapshot 以 `revision` 字串為版本單位：鎖定後不可覆寫（409 `LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`）、專案已前進則 409 `SNAPSHOT_SOURCE_REVISION_STALE`（engineering/api.py:126-142）。
- 大小上限：workflow JSON 2 MB（`MAX_WORKFLOW_BYTES`，project_store.py:13，postgres 版共用同一常數）→ 413 `workflow_too_large`；渲染 PNG 20 MB（`MAX_RENDER_BYTES`，main.py:177）→ 413 `render_too_large`；平面圖上傳 20 MB（`MAX_FLOORPLAN_BYTES`，main.py:180）；專案名 120 字、備註 2000 字（main.py:181-182）。

### 非同步 Job 模式（三處，形狀各自獨立）

| 端點 | 執行方式 | 併發/生命週期 |
| :--- | :--- | :--- |
| `POST /api/rag/search/jobs`（202） | daemon Thread（rag_api.py:183） | 同時最多 `RAG_JOB_MAX_ACTIVE = 1`，超過 429 `rag_job_capacity_reached`；完成後保留 1 小時（TTL 3600s，rag_api.py:29-30）；in-memory dict |
| `POST /api/v1/projects/{id}/engineering-packages`（202） | FastAPI BackgroundTasks（engineering/api.py:208） | job_id=`job_<uuid4 hex 12 碼>`；狀態 queued→processing→completed/failed；經 repository 持久化 |
| `POST /api/projects/{id}/render-jobs`（202） | 兩條路徑（main.py:2279-2283）：`OPENROUTER_API_KEY` 有設、`ROOMPILOT_RENDER_IMAGE_DISABLED != 1` 且未設舊遠端 URL 時走內建轉接層 `run_direct_render_jobs`（render_providers.py:353）同步生圖並入庫；否則 `submit_render_jobs` 同步轉送遠端供應商，由供應商非同步執行 | 內建路徑逐張生成、單間失敗不中止整批（全數失敗才拋原錯誤），回 `jobs[]`（`status` 已是 `completed`/`failed`）＋`failed_count`；遠端路徑回供應商 JSON＋`request_id` |

### 持久化

專案/上傳/渲染紀錄的 provider 由 `ROOMPILOT_PROJECT_STORE_PROVIDER` 決定（預設 `sqlite`，可設 `postgres` 走 Phase 3 `PostgresProjectStore`；顯式設定、**無靜默回退**，project_store.py:601-620）。SQLite 模式存 `.runtime/projects.sqlite3`；上傳檔在 `.runtime/uploads/`；渲染 PNG 在 `.runtime/renders/`；工程文件產出在 `.runtime/engineering/`（engineering/api.py:55）。家具型錄以 Kai PostgreSQL 優先（postgres_catalog.py），runtime catalog（styles/surfaces/costs/quarantine）為 Phase 4 PostgreSQL（runtime_catalog_repository）。

---

## 3. 錯誤處理

全部錯誤經 FastAPI `HTTPException` 或全域 exception handler，HTTP body 為 `{"detail": ...}`，其中 `detail` 有三種形狀（並存，未統一）：

**結構化 detail（主流程／rag／admin／全域 503）：**

```json
{
  "detail": {
    "code": "project_revision_conflict",
    "message": "專案已在另一個分頁更新，請載入最新版本後再儲存。",
    "project": { "...最新專案物件，僅衝突類錯誤附帶..." }
  }
}
```

rag_api 另附 `retryable`（502/503 為 true，rag_api.py:33-41）；catalog_admin 附 `code` 與 repository 例外的 `context` 展開（catalog_admin.py:228-231）。

**engineering 專用形狀**：欄位名是 `error_code`（大寫蛇形）＋ `message`，部分附 `current_project_revision`（engineering/api.py:117-147）。

**純字串 detail（舊移植路由與簡單驗證）**：如 `{"detail": "invalid_workflow_step"}`、`{"detail": "cost_items_required"}`（main.py:3663）。

模板的 `type`/`param`/`request_id` 欄位現況未實作。

### 全域 exception handler（main.py:226-266）

| 例外 | HTTP | code |
| :--- | :--- | :--- |
| `ProjectStoreBusy` | 503（`Retry-After: 2`） | `project_store_busy` |
| `ProjectStoreUnavailable` | 503 | `project_store_unavailable` |
| `RuntimeCatalogUnavailable`（reason 為 `CatalogPoolTimeout`） | 503（`Retry-After: 2`） | `catalog_pool_busy` |
| `RuntimeCatalogUnavailable`（其他） | 503 | `runtime_catalog_unavailable`（附 `catalog` 鍵名） |

### 錯誤碼一覽（依子系統）

**主流程（main.py，節錄常用）：** `project_not_found`(404)、`render_not_found`(404)、`questionnaire_image_not_found`(404)、`project_name_required`(422)、`invalid_workflow_step`(422)、`empty_floorplan`/`invalid_floorplan_image`(422)、`dxf_parse_failed`/`cody_recognition_failed`(422)、`unsupported_floorplan_type`(415，main.py:2110)、`invalid_render_png`(415/422)、`floorplan_missing`/`floorplan_confirmation_required`/`project_revision_conflict`(409)、`floorplan_source_missing`/`render_file_missing`(410)、`workflow_too_large`/`render_too_large`(413)、`cost_items_required`(422)、render_service 驗證碼 `unsupported_render_mode`/`scene_version_required`/`style_card_ids_required`/`room_views_required`(422，render_service.py:92-111)、`render_provider_not_configured`/`render_provider_unreachable`(503)、`render_provider_http_{status}`(502)。

**rag_api（rag_api.py:44-53）：** `RagDisabledError`→503（RAG 未啟用）、`RagDependencyError`→503（套件/模型/設定未就緒）、`RagDatabaseError`→503（pgvector 不可用）、`RagUpstreamError`→502（LLM 解析失敗）、`rag_internal_error`→500、`rag_job_capacity_reached`→429、`rag_job_not_found`→404。

**catalog_admin（catalog_admin.py:170-231）：** `catalog_admin_requires_strict_postgres`(503)、`catalog_admin_not_configured`(503)、`catalog_admin_unauthorized`(401，附 `WWW-Authenticate: Bearer`)、`catalog_admin_actor_invalid`(422)、`catalog_item_not_found`(404)、`expected_updated_at_timezone_required`(422)；repository 例外映射：NotFound→404、Conflict→409、Reference/Activation→422、其他 CatalogAdminError→400、非預期→503 `postgres_catalog_write_unavailable`。

**engineering（engineering/api.py）：** `PATH_PAYLOAD_MISMATCH`(422)、`LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`(409)、`SNAPSHOT_SOURCE_REVISION_STALE`(409)、`PROJECT_NOT_FOUND`(404)、`SNAPSHOT_NOT_FOUND`(404)、`REVISION_NOT_LOCKED`(409)、`JOB_NOT_FOUND`(404)、`PACKAGE_NOT_FOUND`(404)、`DOCUMENT_NOT_FOUND`(404)；job 失敗兩類 `error_code`：`XLSX_ADAPTER_UNAVAILABLE`、`ENGINEERING_PACKAGE_FAILED`（api.py:253-266）。

（模板中的 403 現況不存在；401 僅 catalog_admin、429 僅 RAG job。）

---

## 4. 安全性

照實描述，模板項目未實作者標記現況：

- **TLS**：（未實作）uvicorn HTTP 服務，repo 內無反向代理設定。
- **速率限制**：（大致未實作）無 `RateLimit-*` 標頭；唯二節流是 RAG job 併發上限 1（429）與 PostgreSQL 連線池滿載時的 503＋`Retry-After: 2`。
- **安全 Headers**：（未實作）無 HSTS/CSP middleware；`GET /scene`（main.py:1902）、`GET /rag`（rag_api.py:138）、`GET /engineering`（main.py:2569）、`GET /api/health`（main.py:2561）、`GET /api/projects/{id}`（main.py:2042）加 `Cache-Control: no-store` 防舊快取。
- **實際存在的防護**：
  - **catalog_admin Bearer token**：`secrets.compare_digest` 常數時間比對；strict PostgreSQL 模式未開或 token 未設定一律 503（先擋功能再驗身份，catalog_admin.py:174-184）；Pydantic `extra="forbid"` 嚴格輸入模型；actor 標頭長度/控制字元驗證。
  - **上傳驗證**：平面圖副檔名白名單（`.dxf/.png/.jpg/.jpeg`，main.py:164）＋ PIL 驗證＋20 MB 上限；渲染 PNG 驗 magic bytes＋PIL verify＋20 MB 上限。
  - **路徑跳脫防護**：檔名取 `Path(name).name` basename；工程文件下載強制 `path.is_relative_to(<PROJECT_DIR>/.runtime/engineering)`（engineering/api.py:297-302）。
  - **個資剝除**：送遠端渲染前遞迴移除 `PRIVATE_KEYS`（name/phone/email/address 等，render_service.py:12、60）。
  - **GLB 供應信任邊界**：`ROOMPILOT_MODEL_DELIVERY_MODE` 預設 cloudfront，只回 manifest 驗證過的 CloudFront URL，本機 GLB 拆解端點一律 410。
  - **樂觀鎖**防止多分頁互相覆蓋（第 2 節）。
- **OWASP API Top 10**：（未系統性評估）最大缺口仍是主流程全面無認證——任何能連到 port 的人可讀寫所有專案與工程文件。目前定位為區網 demo 系統。資安風險基線與補強流程見 `.claude/skills/roompilot-security/`（專案 skill）。

---

## 5. API 端點定義

### 5.0 全路由清單（63 條逐條，行號為證據）

**頁面（HTML，6 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 1 | `GET /` | main.py:1883 |
| 2 | `GET /styles` | main.py:1888 |
| 3 | `GET /library` | main.py:1893 |
| 4 | `GET /scene` | main.py:1898 |
| 5 | `GET /engineering` | main.py:2565 |
| 6 | `GET /rag` | rag_api.py:136 |

**專案與圖面（main.py，12 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 7 | `POST /api/projects`（201） | main.py:2024 |
| 8 | `GET /api/projects/{project_id}` | main.py:2040 |
| 9 | `PUT /api/projects/{project_id}/workflow` | main.py:2046 |
| 10 | `POST /api/projects/{project_id}/floorplan`（201） | main.py:2097 |
| 11 | `GET /api/projects/{project_id}/floorplan/source` | main.py:2146 |
| 12 | `POST /api/projects/{project_id}/renders`（201） | main.py:2164 |
| 13 | `GET /api/projects/{project_id}/renders` | main.py:2227 |
| 14 | `GET /api/projects/{project_id}/renders/{render_id}/png` | main.py:2238 |
| 15 | `GET /api/render-provider/status` | main.py:2262 |
| 16 | `POST /api/projects/{project_id}/render-jobs`（202） | main.py:2270 |
| 17 | `POST /api/projects/{project_id}/floorplan/analyze` | main.py:2315 |
| 18 | `GET /api/floorplan/sample/630` | main.py:2406 |

**站台資料與健康（main.py，6 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 19 | `GET /api/site-data` | main.py:2417 |
| 20 | `GET /api/catalog/status` | main.py:2528 |
| 21 | `GET /api/health` | main.py:2533 |
| 22 | `GET /api/home-data` | main.py:2573 |
| 23 | `GET /api/styles` | main.py:2591 |
| 24 | `GET /api/scene/bootstrap` | main.py:2609 |

**問卷視覺（main.py，2 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 25 | `GET /api/questionnaire/visual-catalog` | main.py:2619 |
| 26 | `GET /api/questionnaire/visual-images/{image_id}` | main.py:2642 |

**家具與場景工作流（main.py，9 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 27 | `GET /api/furniture` | main.py:2707 |
| 28 | `GET /api/scene/provider-status` | main.py:2837 |
| 29 | `POST /api/agent/intake/start` | main.py:2842 |
| 30 | `POST /api/agent/intake/answer` | main.py:2849 |
| 31 | `POST /api/agent/furniture/select` | main.py:2948 |
| 32 | `POST /api/scene/generate` | main.py:3033 |
| 33 | `POST /api/scene/layout` | main.py:3136 |
| 34 | `POST /api/scene/decorate` | main.py:3316 |
| 35 | `POST /api/scene/validate` | main.py:3492 |

**家具模型交付（main.py，4 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 36 | `GET /api/furniture/{furniture_id}/model` | main.py:3508 |
| 37 | `GET /api/furniture/{furniture_id}/model.gltf` | main.py:3517 |
| 38 | `GET /api/furniture/{furniture_id}/buffer.bin` | main.py:3526 |
| 39 | `GET /api/furniture/{furniture_id}/images/{image_index}` | main.py:3536 |

**其他 API（main.py，8 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 40 | `GET /api/plans` | main.py:3551 |
| 41 | `GET /api/plan` | main.py:3556 |
| 42 | `POST /api/upload` | main.py:3572 |
| 43 | `POST /api/floorplan/analyze` | main.py:3602 |
| 44 | `POST /api/floorplan/confirm` | main.py:3645 |
| 45 | `POST /api/cost/estimate` | main.py:3658 |
| 46 | `GET /api/sample-furniture` | main.py:3670 |
| 47 | `GET /api/furniture/{name}` | main.py:3686 |

**家具 RAG runtime（rag_api.py 共 5 條；`GET /rag` 已列頁面區 #6，此處列其餘 4 條）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 48 | `GET /api/rag/status` | rag_api.py:141 |
| 49 | `POST /api/rag/search` | rag_api.py:146 |
| 50 | `POST /api/rag/search/jobs`（202） | rag_api.py:155 |
| 51 | `GET /api/rag/search/jobs/{job_id}` | rag_api.py:187 |

**型錄管理 CRUD（catalog_admin.py，4 條，prefix=/api/admin/furniture）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 52 | `POST /api/admin/furniture`（201） | catalog_admin.py:234 |
| 53 | `GET /api/admin/furniture/{item_id}` | catalog_admin.py:252 |
| 54 | `PATCH /api/admin/furniture/{item_id}` | catalog_admin.py:274 |
| 55 | `DELETE /api/admin/furniture/{item_id}` | catalog_admin.py:294 |

**工程文件 MVP（engineering/api.py，8 條，prefix=/api/v1）**

| # | 方法 路徑 | 出處 |
| :--- | :--- | :--- |
| 56 | `GET /api/v1/engineering/health` | api.py:77 |
| 57 | `PUT /api/v1/projects/{project_id}/revisions/{revision}/snapshot` | api.py:107 |
| 58 | `GET /api/v1/projects/{project_id}/revisions/{revision}/snapshot` | api.py:153 |
| 59 | `POST /api/v1/projects/{project_id}/engineering-packages`（202） | api.py:172 |
| 60 | `GET /api/v1/jobs/{job_id}` | api.py:271 |
| 61 | `GET /api/v1/packages/{package_id}` | api.py:281 |
| 62 | `GET /api/v1/documents/{document_id}/download` | api.py:294 |
| 63 | `POST /api/v1/projects/{project_id}/revisions/{revision}/lock` | api.py:325 |

（46＋5＋4＋8＝63。）

---

### 資源：專案（Projects）

#### `POST /api/projects` - 建立專案

- **請求體**: `{"name": "三房兩廳提案", "notes": "備註(選填)"}`；`name` 必填（上限 120 字，notes 上限 2000 字，main.py:181-182），空值回 422 `project_name_required`
- **回應**: `201 Created` → `{"project": Project}`

#### `GET /api/projects/{project_id}` - 取得專案

- **回應**: `200 OK` → `{"project": Project}`；附 `Cache-Control: no-store`；404 `project_not_found`

#### `PUT /api/projects/{project_id}/workflow` - 保存工作流草稿

- **請求體**: `{"current_step": "layout_2d", "workflow": {...}, "expected_revision": 7, "replay_pending": false, "base_updated_at": "..."}`
  - `current_step` 須在 11 個步驟名內（第 1 節），否則 422 `invalid_workflow_step`
  - `expected_revision` 選填，帶了就啟用樂觀鎖；`replay_pending: true`（離線補存）時 `base_updated_at` 必填
- **回應**: `200 OK` → `{"project": Project}`；409 `project_revision_conflict`（detail 附最新 `project`，main.py:2080）/ 413 `workflow_too_large`

### 資源：平面圖（Floorplan，綁定專案）

#### `POST /api/projects/{project_id}/floorplan` - 上傳平面圖

- **請求體**: `multipart/form-data`：`file`（副檔名限 `.dxf/.png/.jpg/.jpeg`，≤20 MB）＋ `expected_revision`（Form 選填）
- **回應**: `201 Created` → `{"project": Project, "upload": {"filename", "extension", "mime_type", "source_url"}}`
- **錯誤**: 415 `unsupported_floorplan_type`（main.py:2110）/ 422 `empty_floorplan`、`invalid_floorplan_image` / 409 `project_revision_conflict`

#### `GET /api/projects/{project_id}/floorplan/source` - 下載原始上傳檔

- **回應**: `200 OK` → 原檔 `FileResponse`；409 `floorplan_missing` / 410 `floorplan_source_missing`

#### `POST /api/projects/{project_id}/floorplan/analyze` - 啟動辨識

- **前置**: workflow 內平面圖確認已勾選，否則 409 `floorplan_confirmation_required`
- **行為**: DXF 走 `geometry_engine: "dxf"`；PNG/JPG 走 Cody 影像辨識（`geometry_engine: "cody"`）；成功後重置下游步驟。印刷房名/尺寸 OCR 由 `_floorplan_ocr_provider` 接線（paddle 未安裝回 None；`ROOMPILOT_OCR_DISABLED=1` 可停用，main.py:167-176）
- **回應**: `200 OK` → `{"analysis": {...}, "geometry_engine": "dxf"|"cody"}`；422 `dxf_parse_failed` / `cody_recognition_failed`

#### `GET /api/floorplan/sample/630` - Demo 樣張

- **回應**: `200 OK` → `testdata/png/builder_plan_630.png`（main.py:153 的 `SAMPLE_FLOORPLAN_630`）；404 `sample_floorplan_not_found`

### 資源：渲染成品與遠端渲染（Renders / Render Jobs）

#### `POST /api/projects/{project_id}/renders` - 上傳瀏覽器輸出的最終 PNG

- **請求體**: `multipart/form-data`：`file`（PNG，≤20 MB）＋ Form：`expected_revision`（必填）、`white_model_version`/`viewpoint_version`/`style_version`（預設 0）、`style_card_id`（預設 `"unassigned"`）、`provider`（只接受 `"browser_capture"`）
- **回應**: `201 Created` → `{"project": Project, "render": Render}`；413 `render_too_large`（main.py:2189）/ 415/422 `invalid_render_png` / 409 `project_revision_conflict`

#### `GET /api/projects/{project_id}/renders` - 列出渲染紀錄

- **回應**: `200 OK` → `{"renders": [Render, ...]}`（新到舊）；404 `project_not_found`

#### `GET /api/projects/{project_id}/renders/{render_id}/png` - 下載 PNG

- **回應**: `200 OK` → PNG；404 `render_not_found` / 410 `render_file_missing`

#### `GET /api/render-provider/status` - 遠端渲染供應商狀態

- **回應**: `{"configured", "provider", "has_token"}`，不外洩憑證。兩種來源（main.py:2265-2267）：內建生圖轉接層可用時回 `direct_image_provider_status()`（`configured: true`、`provider: "openrouter:<ROOMPILOT_RENDER_IMAGE_MODEL>"`、`has_token: true`，render_providers.py:60-66）；否則回 `render_provider_status()`（讀 `ROOMPILOT_RENDER_PROVIDER_URL`/`_TOKEN`/`_NAME`，render_service.py:42-44）

#### `POST /api/projects/{project_id}/render-jobs` - 提交遠端渲染任務（第 8 步生圖）

- **請求體**: `{"project_id"（須等於路徑，否則 422 render_project_mismatch）, "mode": "palette_comparison"|"room_final", "scene_version", "style_card_ids": [...], "master_view": {...}, "room_views": [...]（room_final 必填）, "requirements": {...}}`；送出前伺服器剝除個資欄位（`prepare_render_payload`，render_service.py:60），轉送遠端供應商時另附 `Idempotency-Key: <request_id>`（render_service.py:133）
- **回應**: `202 Accepted`。內建生圖路徑（`OPENROUTER_API_KEY` 已設且未設舊遠端 URL）→ `{"request_id", "provider": "openrouter:<model>", "jobs": [{job_id（=render_id）, style_card_id, room_id, status, preview_url/image_url, label} | {job_id: null, status: "failed", error_code, message_zh}], "failed_count"}`，PNG 已入庫為 `Render`（provider `openrouter_image`），前端首回即可顯示、不需輪詢（render_providers.py:423-444）；遠端供應商路徑 → 供應商 JSON＋`request_id`＋`provider`（render_service.py:156-158）
- **錯誤**: 422 `render_project_mismatch`（main.py:2276）與其餘驗證碼（見第 3 節）/ 503 `render_provider_not_configured`、`render_provider_unreachable` / 502 `render_provider_http_{status}`、`render_provider_invalid_json`、`render_provider_invalid_response`
- **契約**: `docs/contracts/REMOTE_RENDER_CONTRACT.md`；逾時 `ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS`（預設 60，render_service.py:34）

### 資源：站台資料與家具型錄（Catalog）

#### `GET /api/site-data` - 全站 payload

- **回應**: 全站資料，`furniture` 與 `featured_models` 固定清空，指示改用 `/api/furniture` 分頁

#### `GET /api/catalog/status` - 型錄供應狀態

- **回應**: `{"furniture": {manifest 狀態}, "surfaces": {...}, "doors": {...}, "style_cards": {...}}`；家具資料以 Kai PostgreSQL view `roompilot.furniture_catalog_current` 優先，DB 不可用才退已驗證 JSON（CLAUDE.md 產品邊界；postgres_catalog.py 的 `catalog_provider_status`）

#### `GET /api/health` - 健康檢查（main.py:2533）

#### `GET /api/home-data` / `GET /api/styles` / `GET /api/scene/bootstrap`

- 首頁摘要／全部風格資料（含 `taiwan_style_cards`、`surface_catalog`、六風格統計）／場景初始化包。風格卡由 `style_cards.py` 讀 Phase 4 runtime catalog（`load_runtime_style_cards`）

#### `GET /api/questionnaire/visual-catalog` / `GET /api/questionnaire/visual-images/{image_id}` - 問卷視覺題庫

- **參數**: `space_type`（選填）、`ready_only`（預設 false）
- 來源為版控 JSON（questionnaire_visuals.py 載入，main.py:161）；`.runtime/indexes/questionnaire_visuals.sqlite3` 只是惰性建立的查詢索引（main.py:269-283）；單張不存在回 404 `questionnaire_image_not_found`

#### `GET /api/furniture` - 分頁家具型錄

- **參數**: `style`、`group`、`type`、`q`、`page`（≥1）、`page_size`（1–80，預設 24，main.py:2714）、`has_model`、`detail`（`card`|`scene`）、`color`、`material`、`size`
- **回應**: `{"items": [FurnitureCard], "page", "page_size", "total", "has_next_page", "styles", "type_options", "category_groups", "filter_options", "furniture", "catalog_status"}`；PostgreSQL 模式下由 `query_postgres_catalog` 在 DB 端 filter/count/facet/paginate（postgres_repository.py 原則：「FastAPI 不得為了 filter/count/facet/paginate 而載入完整型錄」）

### 資源：Agent 需求訪談與選件（Agent）

#### `GET /api/scene/provider-status` - OpenRouter 場景規劃狀態

- **回應**: `{"enabled", "has_api_key", "has_model", "model", "models", "model_count", "provider", "scene_planning_enabled", "selection_enabled"}`

#### `POST /api/agent/intake/start` / `POST /api/agent/intake/answer` - 引導式需求訪談

- 六步固定順序（intake_service.py:13 起）：`space_type → occupants → needs → style → materials → constraints`；LLM 模式需 `OPENROUTER_API_KEY`＋`OPENROUTER_INTAKE_ENABLED=1`，失敗自動退正則抽取（`mode: "guided_llm"|"guided_fallback"`）
- **回應**: `{"session_id", "mode", "step", "question", "reply", "client_brief": ClientBrief, "ready_for_confirmation", ...}`；`step`/`answer` 缺一回 422

#### `POST /api/agent/furniture/select` - 伺服器端選件驗證閘

- **請求體**: `{"rooms": [...], "offers": {...}, "style_id", "context", "llm_selection"（選填）}`
- **行為（三層降級）**: 驗 `llm_selection`（`source: "openrouter"`）→ 本地規則（`source: "local_rules"`）→ 保留候選（`source: "local_rules_unvalidated"`）；LLM 只選件、不得捏造家具或輸出座標（backend/agent/select.py 邊界）

### 資源：場景生成與擺位（Scene）

#### `POST /api/scene/generate` - 生成完整場景

- **請求體**（全部選填、有預設）: `space_type`、`style_preference`、`style_card_id`、`required_furniture`、`selected_furniture(_exact)`、`custom_furniture`、`preferred_colors`、`personal_notes`、`questionnaire`、`keep_window_clear`、`keep_door_clear`、`need_storage`、`prefer_low_saturation`、`client_brief`、`floorplan_*`、`wall_option`/`floor_option`、`furniture_random_seed`、`room_width_cm`（預設 420）、`room_depth_cm`（預設 360）
- **回應**: `200 OK`，頂層鍵含 `scene_id`、`llm_mode`、`requirement`（schema_version "1.0"）、`plan_json`、`floorplan`（`coordinate_unit: "cm"`）、`style`、`style_card`、`design_choices`、`surface_catalog`、`furniture_candidates`、`selected_furniture`、`scene_objects`、`placement_resolution_report`、`placement`（`engine: "furniture_engine"`、`failed`、`unavailable_types`），另有 `render_context` 與 `scene_json`（整份 payload 的深拷貝，供第 7/8 步方案與編輯使用，main.py:3086-3089）；家電需求留在問卷與 `render_context` 協助第 8 步生圖、不列入 2D/3D 擺設（CLAUDE.md 產品邊界）

#### `POST /api/scene/layout` - 前端操作後全場重排

- **請求體**: `{"scene_objects", "floorplan"|"floorplan_editor", "placement_room_id", "placement_variant": "A"|"B"（非 A/B 一律退回 "A"，main.py:3152-3154）, "placement_preferences"}`；`position_locked` 物件位置仍合法就不重排
- **回應**: `{"floorplan", "scene_objects", "placement_resolution_report", "placement_preferences_applied", "placement_preferences_ignored"}`（main.py:3211-3218；後兩鍵明列哪些偏好真的進了引擎）

#### `POST /api/scene/decorate` - 依房型自動軟裝

- **行為**: 依房內既有家具與房型加 `light`/`rug`/`plant`/`curtain`；重跑＝重算而非累加；放不下直接捨棄。布簾為固定假想品項：GLB 檔（`static/models/roompilot-curtain.glb`）**不存在時回 None、列進 `decor_summary.skipped`**，不再硬塞壞品項（main.py:3294-3303 docstring 明述此修正；`static/models/` 目錄現不存在，已實查）
- **回應**: `{"scene_objects", "decor_summary": {"requested", "placed", "skipped", "engine"}}`

#### `POST /api/scene/validate` - 單件家具落點驗證（拖曳）

- **請求體**: `{"floorplan"|"floorplan_editor", "item", "others", "placement_preferences"}`；`placement_preferences` 必須同時帶給 `/api/scene/layout` 與本端點，拖曳驗證才會用同一份禁區規則（main.py:3499-3505）
- **回應**: `{"ok": true, "reason": null}` 或 `{"ok": false, "reason": "超出房間範圍(...)"}`（scene_service.py:1717）；幾何合法性一律由 `backend/engine/` 計算（產品邊界）

#### `POST /api/cost/estimate` - 工程概念概算

- **請求體**: `{"items": [...]}`；非 list 回 422 `cost_items_required`（main.py:3663）
- **回應**: `{"schema_version": "1.0", "catalog_version", "currency": "TWD", "region", "items", "needs_quote", "totals_twd", "status": "concept_estimate", "disclaimer_zh"}`（cost_estimation.py `estimate_project_cost`；費率經 Phase 4 `load_runtime_cost_catalog` 取自 PostgreSQL runtime catalog，來源為版控台灣公開行情種子）

### 資源：GLB 模型供應（Model Delivery）

供應模式由 `ROOMPILOT_MODEL_DELIVERY_MODE` 決定，預設 `cloudfront`（services/cloud_models.py）。

- `GET /api/furniture/{furniture_id}/model`：manifest 驗證過 → `307` 轉 CloudFront URL；cloudfront 模式 manifest 無此列 → 404；local 模式才嘗試本機 fallback
- `GET /api/furniture/{furniture_id}/model.gltf` / `buffer.bin` / `images/{image_index}`：cloudfront 模式一律 `410 Gone`；local 模式回拆解後的 glTF JSON／二進位 chunk／內嵌圖
- `GET /api/sample-furniture`：cloudfront 模式回空清單＋提示；local 模式回 `testdata/sample_glb/` 清單
- `GET /api/furniture/{name}`（main.py:3686，雙用途）：`name` 以 `.glb` 結尾回實體 GLB（cloudfront 模式 410）；否則視為 `furniture_id` 回合併後家具詳情。特定路徑（`.../model` 等）先匹配，`{name}` 僅接住其餘（FastAPI 路由順序；舊版曾以 TestClient 實測，本版未重測＝(未查證)）

### 資源：舊 R3F 檢視器移植路由（供 frontend3d 原型）

- `GET /api/plans`：列出 `testdata/pic/temp/` 內建 DXF（main.py:151 的 `PLAN_DIR`）
- `GET /api/plan`：`name`（必填）、`scale_m`/`thickness`/`height`（單位公尺）→ DXF 解析結果（`backend/upgrade3d/dxf_parser.py` 契約，公尺＋公分混合）
- `POST /api/upload`：直接上傳 DXF 解析，參數同上

### 資源：無專案平面圖分析（免建專案）

- `POST /api/floorplan/analyze`：`multipart/form-data` `file`（限 png/jpg/jpeg，否則 415）＋選填 Form JSON：`calibration_json`、`ocr_json`、`geometry_json`、`observed_utilities_json`、`brief_json`（壞 JSON 回 422 `invalid_{field}_json`）
- `POST /api/floorplan/confirm`：`{"analysis": {...必填...}, "corrections": {...}}` → `{"schema_version": "1.0", "ready_for_design", "analysis", "layout_json", "requirements", "dxf_text", "floorplan"}`（公分制契約，`layout_json` 與 `floorplan` 是同一份正規化結果；confirmation.py:174-182）；確認閘門不過以 422 拒絕（`analysis_required`、`geometry_confirmation_required`、`scale_confirmation_required`）

---

### 資源：家具 RAG 檢索（rag_api.py → backend/spatial_data/rag/）

Django 的家具 RAG runtime（LLM 查詢解析 → PostgreSQL pgvector → BGE reranker），經 Bella 的 FastAPI adapter 曝露（rag_api.py:1 docstring）。契約：`docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md`。口語需求→受控詞彙檢索句的轉譯規則見專案 skill `roompilot-furniture-query`（六風格、24 氛圍詞、19 家具群組，與 `rag/data/taxonomy.json`、`rag/data/category_groups.json` 一致）。

#### `GET /rag` - RAG 演示頁

- **回應**: `static/rag.html`，`Cache-Control: no-store`

#### `GET /api/rag/status` - 就緒狀態

- **回應**: `{"schema_version": "roompilot.rag.status.v1", ..., "blockers": [...]}`；blockers 逐項列出未就緒原因：`feature_disabled`、`{provider}_api_key_missing`、`{provider}_package_missing`、`rag_model_packages_missing`、`embedding_model_cache_missing`、`reranker_model_cache_missing`、`furniture_embeddings_empty` 等（service.py:61-91）
- **設定**: `ROOMPILOT_RAG_ENABLED`（預設 false）、`ROOMPILOT_RAG_PARSER_PROVIDER`（`openai`|`anthropic`，預設 openai）、`ROOMPILOT_RAG_OPENAI_MODEL`/`ROOMPILOT_RAG_ANTHROPIC_MODEL`、`ROOMPILOT_RAG_MODEL_CACHE` 等（settings.py:54-74）；embedding 模型 `BAAI/bge-m3`（backend/catalog/rag_repository.py:12）

#### `POST /api/rag/search` - 同步檢索

- **請求體**: `RagSearchRequest`＝`{"query": str（1–1000 字）, "top_k": int（1–8，預設 8）}`，`extra="forbid"`（models.py:80-84）
- **回應**: `{"schema_version": "roompilot.rag.search.v1", "query", "source": {parser/embedding/reranker/vector_store/current_embeddings}, "parsed_query", "parser_usage", "clarification": {"needed", "question", "options"}, "dominant_style", "style_zh", "budget_total", "estimated_total", "blocks": [{item_id, label_zh, category_group, quantity, is_inferred, price_cap, filters, hits}], "timings_ms", "boundary": "retrieval_only_no_geometry_legality"}`（service.py:460-491）
- **錯誤**: 見第 3 節 rag 段（503/502，detail 附 `retryable`）

#### `POST /api/rag/search/jobs` - 非同步檢索（202）

- 同一 `RagSearchRequest`；active job 上限 1，超過 429 `rag_job_capacity_reached`；以 daemon Thread 執行，回 job snapshot
- **Job snapshot**: `{"schema_version": "roompilot.rag.job.v1", "job_id", "status": "queued"|"running"|"completed"|"failed", "progress", "stage", "message", "elapsed_ms", "result"?（完成）, "error"?（失敗，含 code/message/http_status）}`（rag_api.py:117-133）

#### `GET /api/rag/search/jobs/{job_id}` - 輪詢

- **回應**: 同 job snapshot；不存在或過期（TTL 1 小時）回 404 `rag_job_not_found`

---

### 資源：型錄管理 CRUD（catalog_admin.py，PostgreSQL Phase 2）

Kai 的 PostgreSQL 家具寫入層（`backend/catalog/postgres_admin_repository.py`：寫交易、參照驗證、activation gate、樂觀併發、audit record）。契約：`docs/contracts/POSTGRESQL_CATALOG_CRUD_PHASE2.md`。**全站唯一有認證的資源**（第 4 節）；strict PostgreSQL 模式未開回 503 `catalog_admin_requires_strict_postgres`。

#### `POST /api/admin/furniture` - 建立家具（201）

- **授權**: Bearer `ROOMPILOT_CATALOG_ADMIN_TOKEN`＋選填 `X-RoomPilot-Admin-Actor`
- **請求體**: `FurnitureCreateInput`（`extra="forbid"`）：`item_id`（必填，pattern `^[A-Za-z0-9][A-Za-z0-9._:-]*$`）、`category_code`（必填）、`name_en`（必填）、`name_zh`、`colors`/`materials`/`room_codes`（去重驗證）、`width_cm`/`depth_cm`/`height_cm`（>0）、`price_twd`（≥0）、`styles`（最多 2 個 `{style_code, confidence}`，style_code 不可重複）、`annotation`（VLM 標註欄位組）、`raw_data`
- **參數**: `include_raw_data`（預設 false）
- **回應**: `201` → `{"action": "created", "item": {...}}`

#### `GET /api/admin/furniture/{item_id}` - 讀取（含未上架/軟刪列）

- **回應**: `{"item": {...}}`；404 `catalog_item_not_found`

#### `PATCH /api/admin/furniture/{item_id}` - 部分更新

- **請求體**: `FurniturePatchInput`：任意子集，但至少一個變更欄位（否則 422 `catalog_patch_empty`）；`name_en`/`colors`/`materials`/`price_is_estimated`/`is_active` 不可設 null（422 `null_not_allowed_for:...`）；`expected_updated_at` 樂觀鎖（須帶時區）
- **回應**: `{"action": "updated", "item": {...}}`

#### `DELETE /api/admin/furniture/{item_id}` - 軟刪除

- **參數**: `expected_updated_at`（Query 選填，須帶時區）、`include_raw_data`
- **回應**: `{"action": "soft_deleted", "item": {...}}`（公開型錄維持唯讀，刪除即下架）

---

### 資源：工程文件 MVP（engineering/api.py，prefix=/api/v1）

Bella 的設計師鎖定後工程文件流程：**snapshot → lock → packages → jobs → documents**。契約：`docs/contracts/ENGINEERING_DOCUMENT_MVP.md`、`docs/contracts/engineering_openapi.yaml`；schema：`docs/contracts/project_snapshot.schema.json`、`report_payload.schema.json`。知識庫為版控 JSON 種子 `backend/catalog/data/engineering/`（api.py:52-54）。ReportPayload 的下游交付見專案 skill `roompilot-budget`（工程估價）與 `roompilot-proposal`（商業提案）。

#### `GET /api/v1/engineering/health` - 子系統健康

- **回應**: `{"status": "ok", "snapshot_store": <project store provider>, "demo_mode": <ROOMPILOT_DEMO_MODE>, "knowledge": {"provider": "versioned_json_seed", "status": "ready"|"invalid:...", "counts"}, "advanced_rag": {"structured_retrieval": "active", "semantic_retriever": "noop_not_vector_retrieval"}, "xlsx": {"adapter": "@oai/artifact-tool", "node": <ROOMPILOT_ARTIFACT_NODE>, "module_path_configured"}}`（api.py:85-105）

#### `PUT /api/v1/projects/{project_id}/revisions/{revision}/snapshot` - 保存 snapshot

- **請求體**: `ProjectSnapshot`（Pydantic；path 的 `project_id`/`revision` 必須與 payload 一致，否則 422 `PATH_PAYLOAD_MISMATCH`，api.py:116-123）
- **回應**: `SnapshotEnvelope`＝`{"snapshot": ProjectSnapshot, "completeness": snapshot_completeness(...)}`
- **錯誤**: 409 `LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`（鎖定版本不可覆寫）/ 409 `SNAPSHOT_SOURCE_REVISION_STALE`（附 `current_project_revision`）/ 404 `PROJECT_NOT_FOUND`

#### `GET /api/v1/projects/{project_id}/revisions/{revision}/snapshot` - 取得 snapshot

- **回應**: `SnapshotEnvelope`；404 `SNAPSHOT_NOT_FOUND`

#### `POST /api/v1/projects/{project_id}/revisions/{revision}/lock` - 設計師鎖定

- **請求體**: `LockRevisionRequest`（`confirmed_by`）
- **回應**: `SnapshotEnvelope`（approval_status 轉 `designer_confirmed`）；404 `SNAPSHOT_NOT_FOUND` / 409 `SNAPSHOT_SOURCE_REVISION_STALE`

#### `POST /api/v1/projects/{project_id}/engineering-packages` - 產生工程文件包（202）

- **請求體**: `EngineeringPackageRequest`（`revision`、`documents`）
- **前置**: snapshot 存在且 `approval_status == "designer_confirmed"`，否則 409 `REVISION_NOT_LOCKED`（api.py:191-198）
- **回應**: `202` → `JobStatus`（`job_id="job_<uuid4 hex 12>"`, `status: "queued"`）；BackgroundTasks 執行 Orchestrator（QuantityService＋AdvancedRAGService＋ExistingEngineRuleService＋CostService＋ScheduleService＋TemplateNarrativeService＋DocumentService，api.py:57-75；demo 模式由 `ROOMPILOT_DEMO_MODE` 控制）

#### `GET /api/v1/jobs/{job_id}` - 輪詢

- **回應**: `JobStatus`（逐階段 `progress`/`stage`；成功附 `package_id` 與 `documents`；失敗 `error_code`＝`XLSX_ADAPTER_UNAVAILABLE` 或 `ENGINEERING_PACKAGE_FAILED`＋`error` 訊息截 1000 字）；404 `JOB_NOT_FOUND`

#### `GET /api/v1/packages/{package_id}` - 取得報告 payload

- **回應**: `ReportPayload`（`docs/contracts/report_payload.schema.json`）；404 `PACKAGE_NOT_FOUND`

#### `GET /api/v1/documents/{document_id}/download` - 下載產出文件

- **參數**: `preview`（預設 false；true 且 `.html` 時以 inline Content-Disposition 回傳）
- **回應**: `FileResponse`，media type 支援 `.json`/`.html`/`.xlsx`（xlsx 經 Node adapter `engineering/workbook_builder.mjs` 產生，node 執行檔由 `ROOMPILOT_ARTIFACT_NODE` 指定）；僅允許落在 `<PROJECT_DIR>/.runtime/engineering` 之下的實檔（`is_relative_to` 防護，api.py:297-302）；404 `DOCUMENT_NOT_FOUND`

---

## 6. 資料模型

### `Project`

```json
{
  "project_id": "hex uuid4",
  "name": "string (≤120 字)",
  "notes": "string (≤2000 字)",
  "current_step": "project | …(11 步之一)",
  "workflow": { "…前端流程草稿 JSON，上限 2MB…" },
  "revision": 0,
  "created_at": "ISO 8601 UTC",
  "updated_at": "ISO 8601 UTC"
}
```

### `Render`

```json
{
  "render_id": "hex uuid4",
  "project_id": "…",
  "white_model_version": 0,
  "viewpoint_version": 0,
  "style_version": 0,
  "style_card_id": "unassigned",
  "provider": "browser_capture | openrouter_image",
  "mime_type": "image/png",
  "filename": "…png",
  "byte_size": 123456,
  "created_at": "…",
  "download_url": "/api/projects/{project_id}/renders/{render_id}/png"
}
```

### `ClientBrief`（intake_service.py:56，schema_version 1.1）

```json
{
  "schema_version": "1.1",
  "created_at": "ISO 8601 UTC",
  "space": { "type": null, "width_cm": 420, "depth_cm": 360, "floorplan_filename": null },
  "occupants": { "adults": 0, "children": 0, "elderly": 0, "pets": 0 },
  "needs": [],
  "style": { "preferred": [], "colors": [], "materials": [], "selected_card_id": null },
  "constraints": [],
  "notes": "",
  "confirmation": { "status": "draft", "confirmed_at": null },
  "evidence": []
}
```

### `FurnitureCard`（`GET /api/furniture` 的 `detail=card` 項目）

```json
{
  "furniture_id": "string",
  "name_en": "string", "name_zh": "string", "name_zh_raw": "string",
  "category_label": "string",
  "taxonomy_group": "string", "taxonomy_group_zh": "string", "taxonomy_type_zh": "string",
  "catalog_scope": "string",
  "normalized_type": "sofa | bed | …",
  "primary_style": "scandinavian | japanese | modern_minimal | cream | industrial | american | null",
  "style_candidates": [],
  "color": "string", "material": "string",
  "size_cm": { "width": 0, "depth": 0, "height": 0 },
  "has_model": true,
  "missing_model_reason": null,
  "model_url": "https://<cloudfront>/models/…/xxx.glb"
}
```

### `RagSearchRequest`（backend/spatial_data/rag/models.py:80-84）

```json
{ "query": "string (1–1000 字, required)", "top_k": "int (1–8, 預設 8)" }
```

### `JobStatus`（engineering/models.py；欄位由 api.py 使用面歸納）

```json
{
  "job_id": "job_<uuid4 hex 12>",
  "project_id": "…", "revision": "…",
  "status": "queued | processing | completed | failed",
  "progress": 0, "stage": "queued | starting | … | completed | failed",
  "package_id": "…（成功）", "documents": ["…（成功）"],
  "error_code": "XLSX_ADAPTER_UNAVAILABLE | ENGINEERING_PACKAGE_FAILED | null",
  "error": "…（截 1000 字）", "updated_at": "ISO 8601 UTC"
}
```

（`ProjectSnapshot`／`SnapshotEnvelope`／`ReportPayload` 的完整欄位以 `docs/contracts/project_snapshot.schema.json`、`report_payload.schema.json`、`engineering_openapi.yaml` 為權威，本文件不複寫。）

### 座標與單位約定（跨端點通用）

- 對外 API 契約一律**公分**（`coordinate_unit: "cm"`）；場景物件 `position_cm` 為房間中心原點，`rotation_y_deg` 為 three.js Y 軸旋轉。改動公分制 payload 必須同步更新兩端測試（CLAUDE.md 禁止事項）。
- 例外：舊 R3F 路由（`/api/plan`、`/api/upload`）查詢參數與 `bbox`/`wall_polys` 用公尺，`wall_segments` 等給公分（dxf_parser.py 輸出契約）。

---

## 待補與已知落差

- 主流程 59 條路由（catalog_admin 以外）無認證、無 CORS、無速率限制；對外部署前為最優先缺口（資安基線見 `.claude/skills/roompilot-security/`）。
- 伺服器端無步驟順序/前置檢查，`PUT .../workflow` 可寫入任意合法步驟名；順序僅由前端 `scene_workflow.js` 強制。
- 錯誤 detail 三種形狀並存（結構化 code／engineering 的 `error_code`／純字串），未統一；rag 另帶 `retryable`。
- 三處非同步 job（rag／engineering／render-jobs）各自定義 job 契約與儲存（in-memory dict／repository 持久化／遠端供應商），無共用 job 模型。
- RAG in-memory job 表在多 worker 部署下不共享（單 process demo 前提）；engineering job 經 repository 持久化無此限制。
- `GET /api/furniture/{name}` 與特定子路徑的匹配優先序，本版未以 TestClient 重測（舊導入版曾實測特定路徑先匹配）＝(未查證)。
- 模板指向的包外治理文件（`docs/document-system/architecture.md` 等）＝(未查證：來源不在 repo)。
