# API 設計規範 (API Specification) - RoomPilot backend/server

> **版本:** v2.0 | **更新:** 2026-08-07 | **狀態:** 已發布（逐條對現行程式碼與 `app.openapi()` 匯出核對）| **OpenAPI 定義:** [openapi-roompilot-v1.yaml](./openapi-roompilot-v1.yaml)（機器生成快照）；程式碼變更後以伺服器執行期 `/openapi.json` 為準
> **契約 SSOT:** 端點與 schema 以 [`openapi-roompilot-v1.yaml`](./openapi-roompilot-v1.yaml) 為準；本文件維護設計約定、錯誤語意與認證守衛，§5 路由總表只補 yaml 讀不出來的守衛歸屬與狀態語意。工程文件 API 另有先行契約 `docs/contracts/engineering_openapi.yaml` 與 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`。
> **定位:** 本文件回答「這台 FastAPI 有哪些端點、誰能呼叫、錯誤長什麼樣、單位與版本怎麼約定」；欄位級資料契約歸 `docs/contracts/`，資料庫結構歸同目錄 db_design，模組內部設計歸 lld。
> **Owner:** Bella（`backend/server/` 目錄 owner，見 `AGENTS.md` 目錄責任表）
> **語域:** L2（橋接）
> **實例:** 約定單例；openapi 每服務一份（本系統只有一個 FastAPI app，`backend/server/main.py:244`）
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/04_design/api_spec.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 設計約定](#1-設計約定)
- [2. 通用行為](#2-通用行為)
- [3. 錯誤處理](#3-錯誤處理)
- [4. 安全性（認證與授權守衛）](#4-安全性認證與授權守衛)
- [5. API 端點定義（路由總表）](#5-api-端點定義路由總表)
- [6. 資料模型與單位約定](#6-資料模型與單位約定)
- [7. 追溯](#7-追溯)

## 1. 設計約定

| 項目 | 規範（現況照實描述） |
| :--- | :--- |
| **App** | 唯一 FastAPI app：`AI 室內風格與家具配置展示系統`，info.version `0.1.0`（main.py:244）。路由已從單檔 main.py 拆為 7 個 router：auth、catalog-admin、rag、engineering、shortlist、scene、projects（main.py:246-291），main.py 保留型錄／頁面／舊 R3F 端點 |
| **風格** | REST 風味但非嚴格 RESTful：資源型（`/api/projects/{project_id}`）與動作型（`/api/scene/generate`）並存 |
| **Base URL** | 程式碼未寫死 port；標準啟動 `uvicorn backend.server.main:app --host 127.0.0.1 --port 8002`（README「快速啟動」）。Docker 已於 2026-08-06 整套移除（commit 09891216），本機 uvicorn 是唯一啟動方式。無 production 網域 |
| **格式** | `application/json`（UTF-8）為主；上傳走 `multipart/form-data`；圖檔／GLB 下載回 `FileResponse`；全站掛 GZip（`minimum_size=1024`，main.py:245） |
| **路徑與欄位命名** | 路徑小寫、多字段用連字符（`/api/render-provider/status`）；欄位 `snake_case`。例外：workflow 草稿內前端鍵（`roomRequirementModel` 等）為 camelCase，屬 `scene_json` 草稿契約非 API 欄位 |
| **日期格式** | ISO 8601 UTC（`project_store.py:17-18`） |
| **認證** | JWT Bearer（HS256），自訂解析非 FastAPI Security 機制；守衛詳見 §4。型錄後台另用獨立靜態 token（§4.3） |
| **版本策略** | 混合三層：(1) URL 版本只有工程文件 API 用 `/api/v1` 前綴（engineering/api.py:66），其餘 `/api/*` 無版本段；(2) payload 層 `schema_version` 字串（清單見 §6.2）；(3) 專案樂觀鎖 `revision` 整數（§2）。前端 workflow 草稿另有 `WORKFLOW_SCHEMA_VERSION = 2`（frontend/scene_workflow.js:1） |

## 2. 通用行為

### 2.1 分頁、排序、過濾

- 只有 `GET /api/furniture` 有分頁：頁碼式 `page`（≥1，預設 1）＋ `page_size`（1–80，預設 24），回應含 `total`、`has_next_page`（main.py:1288-1294）。其餘列表端點一次回全部。
- 無任何端點提供排序參數；`GET /api/projects/{id}/renders` 固定新到舊。
- `GET /api/furniture` 過濾參數：`style`、`group`、`type`、`q`、`has_model`、`color`、`material`、`size`、`detail`（`card`|`scene`）。

### 2.2 樂觀鎖與並行控制

- 專案寫入採樂觀鎖：`PUT .../workflow`、`POST .../floorplan`、`POST .../renders` 吃 `expected_revision`；與儲存的 `revision` 不符回 `409 project_revision_conflict`，detail 附最新 `project` 供前端合併重試（projects_api.py:371-381）。
- `POST .../furniture-shortlist` 對 revision 衝突自動以最新版本重試一次，仍衝突才回 409（shortlist_api.py:302-324）——檢索期間前端自動存檔幾乎必然推進 revision，此設計是實走 QA 後的修正。
- 型錄後台寫入用 `expected_updated_at`（timezone-aware datetime）做同型防護（catalog_admin.py:112-167）。
- 用戶端不傳 `Idempotency-Key`；伺服器轉送遠端渲染時自己對供應商附 `Idempotency-Key: <request_id>` 與 `X-RoomPilot-Scene-Version`（render_service.py:218-222）。

### 2.3 上限（超過即 4xx，不靜默截斷）

| 上限 | 值 | 出處 |
| :--- | :--- | :--- |
| workflow 草稿 JSON | 2 MB → 413 `workflow_too_large` | project_store.py:14 |
| 平面圖上傳 | 20 MB → 413 `upload_too_large` | projects_api.py:49 |
| 最終渲染 PNG | 20 MB → 413 `render_too_large` | projects_api.py:46 |
| 候選集寫入 workflow | workflow 上限的 1/4，超過自動降 `per_family` 重算 | shortlist_api.py:38 |
| render-jobs 風格卡數 | 18 → 422 `render_style_cards_exceed_limit` | render_service.py:15 |
| render-jobs 逐房視角數 | 24 → 422 `render_room_views_exceed_limit` | render_service.py:16 |
| RAG 併發工作 | 1 → 429 `rag_job_capacity_reached`；完成工作保留 60 分鐘 | rag_api.py:35-36 |
| 專案名稱／備註 | 120／2000 字 → 422 | projects_api.py:50-51 |

### 2.4 持久化 Provider

專案儲存由 `ROOMPILOT_PROJECT_STORE_PROVIDER` 明確切換（`sqlite` 預設｜`postgres`），無靜默 fallback（project_store.py:654-670）；家具型錄 provider 見 `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md`。`GET /api/health` 綜合回報兩者就緒狀態，正式模式（雙 postgres）未就緒回 503（main.py:1103-1132）。終端機環境變數會蓋過 `.env`（實測驗證，見專案 memory），驗證前先清掉 `ROOMPILOT_*_PROVIDER`。

## 3. 錯誤處理

全部錯誤經 `HTTPException`，HTTP body 是 FastAPI 包裝 `{"detail": ...}`。`detail` 有三種形狀並存（未統一，照實描述）：

| 形狀 | 使用範圍 | 範例 |
| :--- | :--- | :--- |
| `{"code", "message", ...輔助欄}` | projects／scene／rag／catalog-admin 路由群 | `{"code": "project_revision_conflict", "message": "...", "project": {...}}`；上傳類另帶 `focus`、`allowed_extensions` |
| `{"error_code", "message"}` | auth／shortlist／engineering 路由群（error_code 全大寫） | `{"error_code": "PROJECT_NOT_FOUND", "message": "找不到專案"}` |
| 純字串 | 舊移植路由與部分 workflow 驗證 | `"invalid_workflow_step"`、`"parse failed: ..."` |

另外：Pydantic 驗證失敗回 FastAPI 標準 422 `{"detail": [...]}`。RAG 錯誤 detail 額外帶 `retryable: bool`（502/503 為 true，rag_api.py:39-47）。模板的 `type`/`param`/`request_id` 欄位未實作。

### 3.1 代表性錯誤碼（依狀態碼；完整清單以各 router 原始碼為準）

| HTTP | 錯誤碼 | 語意與出處 |
| :--- | :--- | :--- |
| 400 | `CURRENT_PASSWORD_INCORRECT` | 改密碼時舊密碼錯（auth/api.py:144-150） |
| 401 | `INVALID_CREDENTIALS`／`MISSING_BEARER_TOKEN`／token 過期原因碼 | 登入失敗不區分帳號不存在與密碼錯，防帳號列舉（auth/api.py:93-100）；帶 `WWW-Authenticate: Bearer` |
| 401 | `catalog_admin_unauthorized` | 型錄後台 token 錯（catalog_admin.py:196-200） |
| 403 | `ACCOUNT_DISABLED`／`INSUFFICIENT_ROLE`／`PROJECT_READ_ONLY`／`PROJECT_OWNER_REQUIRED` | 身分正確但權限不足；**專案不可見一律 404 不用 403**（§4.2） |
| 404 | `PROJECT_NOT_FOUND` | 專案不存在**或呼叫者非成員**，刻意同碼（auth/dependencies.py:59-68） |
| 404 | `SHORTLIST_NOT_BUILT`／`SNAPSHOT_NOT_FOUND`／`JOB_NOT_FOUND`／`PACKAGE_NOT_FOUND`／`DOCUMENT_NOT_FOUND`／`render_not_found`／`rag_job_not_found`／`USER_NOT_FOUND` | 各資源查無 |
| 409 | `project_revision_conflict`／`PROJECT_REVISION_CONFLICT` | 樂觀鎖衝突，detail 附最新 project（§2.2；兩種大小寫依路由群） |
| 409 | `floorplan_missing`／`floorplan_confirmation_required` | 前置條件未滿足（projects_api.py:276-283、606-614） |
| 409 | `EMAIL_ALREADY_REGISTERED`／`CANNOT_REMOVE_OWNER`／`SELF_DEACTIVATION_BLOCKED` | 帳戶與成員衝突（auth/api.py） |
| 409 | `LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`／`SNAPSHOT_SOURCE_REVISION_STALE`／`REVISION_NOT_LOCKED`／`ROOMS_NOT_CONFIRMED` | 工程文件與候選集狀態閘（engineering/api.py、shortlist_api.py） |
| 410 | `floorplan_source_missing`／`render_file_missing`；CloudFront 模式下本機 GLB 拆解端點 | 紀錄在、檔案遺失；或端點永久關閉（main.py:1527-1550） |
| 413 | `workflow_too_large`／`upload_too_large`／`render_too_large` | §2.3 |
| 415 | `unsupported_floorplan_type`／`binary_dxf_unsupported`／`invalid_render_png`／`floorplan_image_required` | 型式不符；二進位 DXF 明確拒收並指引另存 ASCII（projects_api.py:97-105） |
| 422 | `invalid_floorplan_dxf`／`invalid_floorplan_image`／`dxf_parse_failed`／`cody_recognition_failed`／`recognition_review_unresolved`／`render_project_mismatch`／render payload 驗證碼（render_service.py:179-200）等 | 內容驗證失敗；`recognition_review_unresolved` 會列出未確認房間（projects_api.py:338-350） |
| 429 | `TOO_MANY_LOGIN_ATTEMPTS`／`rag_job_capacity_reached` | 皆帶 `Retry-After`（登入節流見 §4.1） |
| 502 | `render_provider_http_*`／`rag_upstream_*` | 上游服務拒絕 |
| 503 | `project_store_busy`／`project_store_unavailable`／`catalog_pool_busy`／`runtime_catalog_unavailable` | app 層 exception handler 統一轉譯；busy 類帶 `Retry-After: 2`（main.py:297-333）。瞬時滿載與「型錄沒匯入」訊息刻意分開，避免把使用者導去修沒壞的東西 |
| 503 | `render_provider_not_configured`／`rag_disabled`類／`catalog_admin_requires_strict_postgres`／`catalog_admin_not_configured`／`AUTH_NOT_CONFIGURED` | 功能未設定或依賴未就緒 |

## 4. 安全性（認證與授權守衛）

### 4.1 認證

- JWT Bearer（HS256）放 `Authorization` header；access token 預設 30 分鐘、refresh token 預設 14 天（tokens.py:27-28），可由 `ROOMPILOT_AUTH_ACCESS_TTL_MINUTES`／`ROOMPILOT_AUTH_REFRESH_TTL_DAYS` 覆寫。簽章金鑰 `ROOMPILOT_AUTH_SECRET` 低於 32 bytes 硬性拒絕（`MIN_SECRET_BYTES = 32`，tokens.py:33）。
- 登入節流：同一「client IP｜email」5 分鐘內 8 次失敗即 429＋`Retry-After`；行程內記憶體實作，多 worker 各自計數，定位是提高成本而非嚴格上限（throttle.py:1-16）。
- 改密碼成功撤銷所有既有 session；停用帳號立即使既有 token 失效（README「帳戶端」）。第一個註冊帳號自動成為 admin（可用 `ROOMPILOT_AUTH_DISABLE_FIRST_ADMIN=1` 關閉）。

### 4.2 授權守衛（`backend/server/auth/dependencies.py`，路由端不自己拼授權條件）

| 守衛 | 語意 |
| :--- | :--- |
| `current_user` | 有效 access token 即可 |
| `require_system_role("designer")` | 系統角色閘；admin 恆通過。建立專案需要 designer |
| `project_reader` | 專案成員（含 viewer）可讀 |
| `project_editor` | owner/editor 可寫；viewer 回 403 `PROJECT_READ_ONLY` |
| `project_owner` | 只有 owner：加減成員 |

**404-not-403 鐵律**（AGENTS.md 不可違反契約）：非成員與不存在的專案回同一個 404 `PROJECT_NOT_FOUND`，刻意讓外人無法靠狀態碼判斷 project_id 是否存在（dependencies.py:59-68）。403 只用於「看得到專案但權限不足」。工程文件 API 的 job／package／document 只帶自己的 id，授權會回推所屬專案再做同樣檢查（engineering/api.py:79-93）。

### 4.3 型錄後台的獨立信任邊界

`/api/admin/furniture*` 不走 JWT：需 strict postgres 模式＋`ROOMPILOT_CATALOG_ADMIN_TOKEN` 靜態 Bearer（constant-time 比對），操作者記錄在 `X-RoomPilot-Admin-Actor` header（catalog_admin.py:170-208）。這是維運通道，與帳戶端角色系統分離。

### 4.4 無守衛面（照實列出，部署對外前必須重新評估）

- **免登入頁面**：8 個 HTML 頁全公開——頁面本身沒有資料，身分由頁面 JS 導向 `/login`（rag_api.py:27-30 的設計註解）。
- **免登入 API**：型錄與站台資料讀取（`/api/furniture*`、`/api/site-data` 等）、`/api/health`、`/api/render-provider/status`、`/api/rag/embedding-status`、demo 樣張、舊 R3F 路由（`/api/plans`、`/api/plan`、`/api/upload`）、無專案平面圖分析（`/api/floorplan/analyze`、`/api/floorplan/confirm`）、以及**全部 `/api/scene/*` 與 `/api/agent/furniture/select` 計算端點**。
- **其他現況**：無 CORS middleware（全 backend/server grep 僅 GZip 一筆）、無 TLS 強制、除登入與 RAG 佇列外無速率限制。定位仍是區網 demo 系統；對外部署缺口清單見 `.claude/skills/roompilot-security` 基線與 Codex 報告追蹤。
- **實際存在的防護**：上傳副檔名白名單＋magic bytes＋PIL verify、檔名一律取 basename、送遠端渲染前遞迴剝除個資欄位（render_service.py `_strip_private_fields`）、CloudFront 模式只回 manifest 驗證過的 URL、文件下載限制在生成目錄內（engineering/api.py:390-396）。

## 5. API 端點定義（路由總表）

2026-08-07 由 `app.openapi()` 實數：**70 paths、77 operations**（GET 44／POST 28／PUT 2／PATCH 1／DELETE 2）＝ 8 個頁面路由＋69 個 API 端點；另有 `/static` mount 不入 schema。舊文件的 44 條已過時。請求／回應 schema 一律看 [openapi-roompilot-v1.yaml](./openapi-roompilot-v1.yaml)，下表只補守衛與狀態語意。

### 5.1 頁面（8 條，全公開，HTML 無資料）

`GET /`、`/login`、`/projects`、`/scene`、`/styles`、`/library`、`/engineering`、`/rag`。`/scene`、`/projects`、`/engineering`、`/rag`、`/login` 附 `Cache-Control: no-store`。

### 5.2 帳戶與 Session（`auth/api.py`，8 條）

| 方法 路徑 | 守衛 | 語意（主要狀態碼） |
| :--- | :--- | :--- |
| POST `/api/auth/register` | 公開 | 201 → TokenPair；409 email 已註冊 |
| POST `/api/auth/login` | 公開＋節流 | 200 → TokenPair；401 不區分帳號／密碼錯；403 帳號停用；429 |
| POST `/api/auth/refresh` | 公開（憑 refresh_token） | 200 → 新 TokenPair；401 |
| POST `/api/auth/logout` | 公開（憑 refresh_token） | 204 |
| GET `/api/auth/me` | current_user | 200 → UserPublic |
| POST `/api/auth/password` | current_user | 200 → 新 TokenPair（撤銷其他 session）；400 |
| POST `/api/auth/admin/reset-password` | admin | 200；404（無寄信基礎設施，臨時密碼口頭告知） |
| POST `/api/auth/admin/set-active` | admin | 200；404；409 不能停用自己 |

### 5.3 我的專案與成員（`auth/api.py`，4 條）

| 方法 路徑 | 守衛 | 語意 |
| :--- | :--- | :--- |
| GET `/api/projects` | current_user | 200 → 我可見的專案清單（ProjectSummary[]） |
| GET `/api/projects/{id}/members` | project_reader | 200 → ProjectMember[] |
| POST `/api/projects/{id}/members` | project_owner | 201；404 email 未註冊；成員角色 editor／viewer |
| DELETE `/api/projects/{id}/members/{user_id}` | project_owner | 204；409 不能移除 owner |

### 5.4 專案生命週期：CRUD、平面圖、渲染（`projects_api.py`，14 條）

| 方法 路徑 | 守衛 | 語意 |
| :--- | :--- | :--- |
| POST `/api/projects` | designer | 201 → `{project}`；422 名稱缺／過長；建立者立即成為 owner |
| GET `/api/projects/{id}` | project_reader | 200 → `{project}`，no-store |
| PUT `/api/projects/{id}/workflow` | project_editor | 200；`current_step` 限 11 個步驟名（projects_api.py:52-64）；409／413／422（含 `recognition_review_unresolved` 複核閘） |
| POST `/api/projects/{id}/floorplan` | project_editor | 201；限 `.dxf/.png/.jpg/.jpeg` ≤20MB；二進位 DXF 415 拒收；409 revision |
| GET `/api/projects/{id}/floorplan/source` | project_reader | 200 原檔；409 未上傳／410 檔案遺失 |
| POST `/api/projects/{id}/floorplan/analyze` | project_editor | 200 → `{analysis, layout_json, geometry_engine: "dxf"|"cody"}`；409 未確認圖檔；成功即重置下游步驟 |
| POST `/api/projects/{id}/renders` | project_editor | 201；PNG ≤20MB、`provider` 限 `browser_capture`；`expected_revision` 必填 |
| GET `/api/projects/{id}/renders` | project_reader | 200 → 新到舊 |
| GET `/api/projects/{id}/renders/{rid}/png` | project_reader | 200；`Cache-Control: immutable`（PNG 不可變）；404／410 |
| POST `/api/projects/{id}/render-jobs` | project_editor | 202；內建生圖 provider 可用時直接生圖回 completed，否則轉送遠端；422（含風格卡≤18、視角≤24、鏡頭在房內驗證）／502／503 |
| GET `/api/render-provider/status` | 公開 | 200 → 供應商設定狀態，不外洩憑證 |
| GET `/api/floorplan/sample/630` | 公開 | 200 demo 樣張；404 |
| POST `/api/floorplan/analyze` | 公開 | 免專案分析：multipart＋選填 JSON Form 欄位；422 |
| POST `/api/floorplan/confirm` | 公開 | 200 → 公分制確認契約（`ready_for_design`）；422 閘門不過 |

### 5.5 家具候選集與 RAG（`shortlist_api.py`＋`rag_api.py`，7 條）

| 方法 路徑 | 守衛 | 語意 |
| :--- | :--- | :--- |
| GET `/api/rag/embedding-status` | 公開 | 200 → 語意檢索模型預載狀態（bge-m3 冷載約 34 秒，main.py:292-294） |
| GET `/api/projects/{id}/furniture-shortlist` | project_reader | 200；404 `SHORTLIST_NOT_BUILT` |
| POST `/api/projects/{id}/furniture-shortlist` | project_editor | 201 → 候選集寫入 workflow；需求指紋未變即 `reused: true`；409 `ROOMS_NOT_CONFIRMED` |
| GET `/api/rag/status` | current_user | 200 → `roompilot.rag.status.v1` |
| POST `/api/rag/search` | current_user | 200 → `roompilot.rag.search.v1`；502／503 帶 `retryable` |
| POST `/api/rag/search/jobs` | current_user | 202 → `roompilot.rag.job.v1`；429 併發上限 1 |
| GET `/api/rag/search/jobs/{job_id}` | current_user | 200；404（完成後保留 60 分鐘） |

### 5.6 場景生成與選件（`scene_api.py`，8 條，**全公開**）

| 方法 路徑 | 語意 |
| :--- | :--- |
| GET `/api/scene/bootstrap` | 200 → 風格／色卡／surface catalog 初始化包 |
| GET `/api/scene/llm-status`＋`/api/scene/provider-status` | 同一 handler 雙路徑：OpenRouter 場景規劃與選件開關狀態 |
| POST `/api/agent/furniture/select` | 伺服器端選件驗證閘（Yen 選件紀律）：LLM → 本地規則 → 未驗證候選三層降級，`source` 欄位如實標示 |
| POST `/api/scene/generate` | 200 → 完整場景 payload，頂層另附 `scene_json`（deepcopy，scene_api.py:436-439） |
| POST `/api/scene/layout` | 全場重排；`position_locked` 物件位置仍合法就不動；擺放失敗才觸發換小款重算 |
| POST `/api/scene/decorate` | 依房型自動軟裝；重跑＝重算非累加；放不下列入 `decor_summary.skipped` 不回 409 |
| POST `/api/scene/validate` | 單件落點驗證 → `{ok, reason}` |

### 5.7 型錄與站台資料（main.py，16 條，全公開）

| 方法 路徑 | 語意 |
| :--- | :--- |
| GET `/api/site-data`、`/api/home-data`、`/api/styles`、`/api/catalog/status` | 站台 payload 與型錄供應狀態；site-data 的 `furniture` 固定清空，家具一律走分頁端點 |
| GET `/api/health` | 綜合就緒探針；正式模式未就緒回 503（§2.4） |
| GET `/api/furniture` | 分頁家具型錄（§2.1）；來源 provider 見 §2.4 |
| POST `/api/furniture/by-ids` | 依 item_id 批次還原完整家具資料，供第 6 步從候選集取圖與 GLB |
| GET `/api/furniture/{fid}/model` | manifest 驗證過 → 307 轉 CloudFront；cloudfront 模式查無 → 404 |
| GET `/api/furniture/{fid}/model.gltf`／`buffer.bin`／`images/{i}` | 本機 glTF 拆解端點；cloudfront 模式（預設）一律 410 |
| GET `/api/sample-furniture`、GET `/api/furniture/{name}` | 範例 GLB 清單與雙用途端點（`.glb` 結尾回實體檔，否則回家具詳情）；特定路徑先匹配 |
| GET `/api/plans`、GET `/api/plan`、POST `/api/upload` | 舊 R3F 檢視器移植路由；**查詢參數與 bbox 用公尺**（§6.1 例外） |

### 5.8 型錄後台（`catalog_admin.py`，4 條，獨立 token，見 §4.3）

`POST /api/admin/furniture`（201）、`GET/PATCH/DELETE /api/admin/furniture/{item_id}`。PATCH 禁空補丁與關鍵欄位 null；DELETE 是軟刪除（`soft_deleted`）。契約全文見 `docs/contracts/POSTGRESQL_CATALOG_CRUD_PHASE2.md`。

### 5.9 工程文件（`engineering/api.py`，prefix `/api/v1`，8 條）

| 方法 路徑 | 守衛 | 語意 |
| :--- | :--- | :--- |
| GET `/api/v1/engineering/health` | 公開（見 §7 已知落差） | 200 → 知識庫／XLSX adapter／定價 provider 就緒狀態 |
| PUT `/api/v1/projects/{id}/revisions/{rev}/snapshot` | project_editor | 200 → SnapshotEnvelope；409 已鎖定不可覆寫／來源已過期；422 path 與 payload 不一致 |
| GET `/api/v1/projects/{id}/revisions/{rev}/snapshot` | project_reader | 200；404 |
| POST `/api/v1/projects/{id}/revisions/{rev}/lock` | project_editor | 200 → 設計師鎖版；409 來源過期 |
| POST `/api/v1/projects/{id}/engineering-packages` | project_editor | 202 → JobStatus；409 `REVISION_NOT_LOCKED`（未鎖版不得出報告） |
| GET `/api/v1/jobs/{job_id}` | current_user＋回推專案 | 200 → 進度；失敗帶 `error_code`（含 `XLSX_ADAPTER_UNAVAILABLE`） |
| GET `/api/v1/packages/{package_id}` | current_user＋回推專案 | 200 → ReportPayload（`roompilot.report-payload.v1`） |
| GET `/api/v1/documents/{document_id}/download` | current_user＋回推專案 | 200 → HTML／XLSX／JSON；`?preview=true` 對 HTML 改 inline |

## 6. 資料模型與單位約定

Pydantic 定義過的模型（TokenPair、UserPublic、ProjectSummary、ProjectMember、RagSearchRequest、ProjectSnapshot、ReportPayload、JobStatus、FurnitureCreateInput 等）**以 openapi yaml 的 components.schemas 為準，本文件不重抄**。本節只放 yaml 讀不出來的約定。

### 6.1 座標與單位（AGENTS.md 不可違反契約的 API 落地）

- 對外契約一律**公分**：`coordinate_unit: "cm"`、長度欄位 `_cm` 結尾、面積 `_m2`；場景物件 `position_cm` 以房間中心為原點、`rotation_y_deg` 為 three.js Y 軸旋轉。舊欄位（`width`、`pos_x` 等）必須同時帶 `coordinate_unit: "cm"` 與 schema version。無 `coordinate_unit` 的舊資料讀取時視為公尺轉一次（scene_service.py:1419）。
- 邊界：平面圖辨識輸出是 **`layout_json`**（`POST .../floorplan/analyze` 回傳），方案生成與編輯輸出是 **`scene_json`**（`POST /api/scene/generate` 回傳）；兩者不可互替，詳見 `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`。
- **例外**：舊 R3F 路由 `GET /api/plan`／`POST /api/upload` 的查詢參數（`scale_m`、`thickness`、`height`）與 `bbox`/`wall_polys` 用公尺，`wall_segments` 等段落給公分（`backend/upgrade3d/dxf_parser.py` 輸出契約）。

### 6.2 payload 層 schema_version 一覽（本次逐一 grep 核對）

| 值 | 所在 payload | 出處 |
| :--- | :--- | :--- |
| `"1.0"` | scene 生成的 requirement／floorplan／furniture_candidates 段 | scene_service.py:2830、2979、3055 |
| `roompilot.furniture-shortlist.v1` | 候選集文件 | backend/spatial_data/rag/shortlist.py:35 |
| `roompilot.rag.status.v1`／`.search.v1`／`.job.v1` | RAG 狀態／結果／工作 | rag/service.py:110、466、rag_api.py:127 |
| `roompilot.report-payload.v1` | 工程報告 | engineering/models.py:490 |
| `WORKFLOW_SCHEMA_VERSION = 2` | 前端 workflow 草稿（存於 project.workflow） | frontend/scene_workflow.js:1 |

### 6.3 dict 收件端點的欄位契約出處

`payload: dict` 收件、openapi 只顯示空 object 的端點，欄位契約以下列文件為準（引用不重抄）：render-jobs → `docs/contracts/REMOTE_RENDER_CONTRACT.md`；scene 生成／編輯 → `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md`＋`LAYOUT_SCENE_BOUNDARY_CONTRACT.md`；snapshot → `docs/contracts/project_snapshot.schema.json`；報告 → `docs/contracts/report_payload.schema.json`；GLB 交付 → `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`；候選集 → `docs/contracts/QUESTIONNAIRE_RAG_HANDOFF.md`。

## 7. 追溯

| 項目 | 內容 |
| :--- | :--- |
| 上游 | `FR-AUTH-*`（帳戶與成員）、`FR-PROJ-*`（專案與 workflow）、`FR-FP-*`（平面圖辨識）、`FR-SCENE-*`（場景生成編輯）、`FR-CATALOG-*`（型錄）、`FR-RAG-*`（檢索與候選集）、`FR-AGENT-*`（選件）、`FR-RENDER-*`（渲染）、`FR-REPORT-*`（工程文件）；sad 元件對應見 `../03_architecture/sad.md` |
| 契約 SSOT | [`openapi-roompilot-v1.yaml`](./openapi-roompilot-v1.yaml)（本快照）＋執行期 `/openapi.json`；欄位級契約 `docs/contracts/`（§6.3） |
| 下游 | `../02_ux_ui/ui_spec-*.md` 的資料需求、`../05_qa/test_plan.md` 的 API／契約案例、同目錄 db_design（§2.4 provider）與 lld |
| 驗證 | 路由總數與 openapi 匯出：本文件 §5 於 2026-08-07 以 `.venv` Python 對 `backend.server.main:app` 實跑 `app.openapi()` 核對（77 operations）；守衛歸屬逐檔讀碼核對 |
| 已知落差 | 見 §7.1（盤點性質的開放項清單，非追溯鏈內容；逐項狀態未裁決前不得寫成已修） |

### 7.1 已知落差（2026-08-07 盤點，狀態未裁決前不得寫成已修）

- `GET /api/v1/engineering/health` 無守衛，而 AGENTS.md 寫「`/api/v1/*` 的每個端點都要掛守衛」——health 是否豁免待 Bella／Ben 確認。
- `GET /api/v1/documents/{id}/download` 在文件無法回推所屬專案時跳過專案授權（engineering/api.py:387-389 的 `if owning_project is not None`），任何登入者可下載孤兒文件；風險待資安確認。
- `/api/scene/*`、`/api/agent/furniture/select`、`/api/floorplan/analyze|confirm`、`/api/upload` 為免登入計算端點（§4.4）；區網 demo 定位下未收斂，對外部署前必須裁決。
- 錯誤 detail 三種形狀並存（§3），未有統一計畫。
- README 套件基線寫 FastAPI 0.140.0，本機 `.venv` 實測 `fastapi.__version__ == 0.139.0`——文件與環境不一致，待對齊。
- 舊文件（`docs/vibecoding/04_design/api_spec.md`，2026-07-26）記載的 `/api/agent/intake/*`、`/api/cost/estimate`、`/api/questionnaire/*` 端點已不存在於現行路由（77 條實數中查無）。
- FastAPI 已標棄用的 `@app.on_event` 仍在用：startup 型錄快取預熱（JSON 模式限定）與 shutdown 連線池關閉（main.py:1401-1414）；RAG 模型預載改為 module-level `PRELOADER.start`（main.py:294）。是否遷移 lifespan 未裁決（沿 2026-07-26 版待補項）。
