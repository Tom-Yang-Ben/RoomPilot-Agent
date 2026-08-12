# API 設計規範 (API Specification) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-SRV-API owner（Bella）；各端點群的行為權威為該群 MOD-* owner（見 [`sad.md`](../03_architecture/sad.md)）
> **語域:** L2（橋接）——端點與 FR-*／NFR-* 並列，跨層一律用穩定 ID
> **實例:** 單例（約定與端點總覽一份）；欄位級 schema 每群一份 `openapi-*.yaml`
>
> **本文件回答**：`backend/server/` 到底開了哪些路由、分屬哪個模組 owner、每條端點的關鍵失敗碼是什麼、狀態碼在本 repo 的一致慣例（NFR-014），以及哪些路由已無生產前端呼叫。
> **本文件不含**：逐欄位請求／回應 schema（去 [`openapi-project-workflow-v1.yaml`](./openapi-project-workflow-v1.yaml)、[`openapi-scene-v1.yaml`](./openapi-scene-v1.yaml)、[`openapi-agent-rag-v1.yaml`](./openapi-agent-rag-v1.yaml)、[`openapi-render-delivery-v1.yaml`](./openapi-render-delivery-v1.yaml)）、內部函式與演算法（去 [`lld.md`](./lld.md)）、資料表與型錄（去 [`db_design.md`](./db_design.md)）、畫面行為（去 `02_ux_ui/ui_spec-step*.md`）、架構取捨理由（去 `03_architecture/adr/`）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 設計約定](#1-設計約定)
- [2. 通用行為](#2-通用行為)
- [3. 錯誤語意](#3-錯誤語意)
- [4. 安全性](#4-安全性)
- [5. API 端點群](#5-api-端點群)
- [6. 資料模型與契約邊界](#6-資料模型與契約邊界)
- [7. 待確認](#7-待確認)
- [8. 追溯](#8-追溯)

---

## 1. 設計約定

| 項目 | 本 repo 現況 | 佐證 |
| :--- | :--- | :--- |
| **風格** | REST-ish：資源路徑 ＋ 動詞化子路徑並存（`/api/projects/{id}/workflow`、`/api/scene/layout`、`/api/agent/pipeline/{id}/undo`） | `main.py:1806,3647,3549` |
| **Base URL** | 單一來源 `http://127.0.0.1:8002`（無 staging／production 分離，見 [`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md)） | `README.md:49`；`install.ps1:41-79` |
| **版本控制** | **路徑無版本號**（無 `/v1`）；契約版本改由 payload 內 `schema_version` 承載 | `main.py:1784-4199` 全域無 `/v` 前綴；`engine/schema.py:18-32` |
| **格式** | `application/json`（UTF-8）為主；上傳走 `multipart/form-data`，下載回 `image/png`／`application/pdf`／`model/gltf-binary` | `main.py:1870-1876,2334-2351,4190-4199` |
| **欄位命名** | `snake_case`；長度與座標一律 `_cm`、面積 `_m2`、角度度數（NFR-017、[`ADR-007`](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)） | [`AGENTS.md`](../../AGENTS.md) §不可違反的契約 |
| **認證** | **無**：全 app 無認證相依、無 API key、無 session（NFR-019） | `main.py:195-197` 無 `Depends`／`add_middleware(CORS…)`；全檔零 `APIKeyHeader` |
| **路由總數** | 65 條：`main.py` 60（含 4 個頁面 GET）＋ `rag_api.py` 5（以 `include_router` 併入同一 app） | `main.py:197`；`rag_api.py:27,159-221` |

---

## 2. 通用行為

| 行為 | 規範／現況 | 佐證 |
| :--- | :--- | :--- |
| **分頁** | 僅 `GET /api/furniture` 有分頁：`page ≥ 1`、`page_size` 1–80（預設 24），回 `total`／`has_next_page`；越界由 FastAPI 擋成 422（NFR-006） | `main.py:3235-3236,3269-3273` |
| **過濾** | 欄位名直接當 query：`style`／`group`／`type`（alias）／`q`／`color`／`material`／`size`／`has_model`／`detail`；`detail=scene` 回完整物件、否則回卡片投影 | `main.py:3231-3241,3266` |
| **排序** | 無排序參數。擺位順序由引擎決定性 tie-break 產生，不開放呼叫端指定（NFR-016） | `engine/rules.py:52`；`engine/obb.py:22-27` |
| **冪等性** | 無 `Idempotency-Key`。寫入衝突改用**樂觀鎖**：`expected_revision`（不符 409 附最新 project）與 `replay_pending`＋`base_updated_at`（不符回裸字串 `project_version_conflict`） | `main.py:1828-1858`；`project_store.py:199-243` |
| **併發控制** | 儲存端 `BEGIN IMMEDIATE` ＋ `UPDATE … AND revision = ?` 雙重防護（NFR-004） | `project_store.py:92-93,199-243` |
| **快取** | `GET /api/projects/{id}` 與 `/scene` 頁強制 `Cache-Control: no-store`；靜態資產以 `?v=sha256-<前12碼>` 破快取（NFR-021） | `main.py:1800-1803,1664-1670`；`scene.html:1217` |
| **壓縮** | 全域 GZip，`minimum_size=1024` | `main.py:196` |
| **非同步** | 只有兩處 202：`POST /api/projects/{id}/render-jobs`（外部渲染商）與 `POST /api/rag/search/jobs`（本機佇列＋輪詢）。第 7／8 步生圖是**同步長請求**，無進度與取消（見 [`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md) §4.2） | `main.py:2033`；`rag_api.py:178-221` |
| **上限** | workflow 快照 ≤ 2 MB（413）、瀏覽器 PNG ≤ 20 MB（413）、檢索佇列 ≤ 24（429） | `project_store.py:11,223-225`；`main.py:163,1958-1962`；`rag_api.py:32,186-191` |

---

## 3. 錯誤語意

### 3.1 回應形狀（三種並存，非單一慣例）

| 形狀 | 範例 | 佐證 |
| :--- | :--- | :--- |
| **結構化**（多數業務錯誤）：`{"detail": {"code", "message", 可選 "focus"／"rooms"／"project"}}` | `project_name_required`、`recognition_review_unresolved` | `main.py:1786-1793,1817-1827` |
| **裸字串**：`{"detail": "invalid_workflow_step"}` | 工作流欄位驗證與 legacy 路由 | `main.py:1811,1814,1858,4073` |
| **FastAPI 內建驗證**：`{"detail": [{loc, msg, type}, …]}` | `page`／`page_size` 越界、pydantic `RagSearchRequest` 欄位不符 | `main.py:3235-3236`；`rag_api.py:169-170` |

> 前端 `errorMessage()` 同時吃字串與物件兩種形狀，第三種只會落到通用文案（`scene_v2.js:642-653`）。形狀不統一屬既有債，尚未收斂——不得在下游文件寫成「統一錯誤信封」。

### 3.2 狀態碼慣例總表（NFR-014）

| 碼 | 慣例語意 | 代表 code | 佐證 |
| :--- | :--- | :--- | :--- |
| **404** | 資源不存在（含**旗標未啟用**：Agent 管線關閉時四支路由一律 404） | `project_not_found`、`render_not_found`、`design_manual_not_found`、`rag_job_not_found` | `main.py:1672-1682,2018-2022,2338-2342,3511-3516`；`rag_api.py:216-220` |
| **409** | 前置條件未達成、版本衝突或一次性額度用罄——**業務衝突不是輸入錯誤** | `floorplan_confirmation_required`、`floorplan_missing`、`project_revision_conflict`、`palette_already_generated`、`ai_edit_budget_exhausted`、`room_not_generated`（`decor_model_missing` 已定義但 **HTTP 層不可達**，見 §5.3） | `main.py:1691-1699,1848-1858,2147-2155,2237-2248,2985-2992` |
| **410** | 紀錄還在、實體檔已失，或該模式刻意不提供本機資產（CloudFront） | `floorplan_source_missing`、`render_file_missing`、`design_manual_file_missing`、`delivery_proposal_file_missing`、CloudFront 模式的 glTF／buffer／images | `main.py:1700-1707,2021-2025,2343-2347,2430-2434,4021-4048` |
| **413** | 超過硬上限，整筆拒收、上一版完好 | `workflow_too_large`、`render_too_large` | `main.py:1859-1866,1958-1962` |
| **415** | 型別／magic 不符 | `unsupported_floorplan_type`、`invalid_render_png`、`floorplan_image_required` | `main.py:1877-1885,1963-1967,4116-4118` |
| **422** | 輸入不完整或欄位不合法（含辨識失敗——**演算法無法產出可用結果視為輸入問題**） | `project_name_required`、`scene_required`、`room_views_required`、`reference_png_required`、`dxf_parse_failed`、`cody_recognition_failed`、`render_project_mismatch` | `main.py:1786-1793,2085-2107,3004-3011,3030-3037` |
| **502** | 上游明確拒絕或產出失敗 | `ai_edit_failed`、`design_manual_failed`、`delivery_proposal_failed`、`RenderProviderRejected`、RAG `RagUpstreamError` | `main.py:2270-2274,2326-2328,2403-2406,2058-2061`；`rag_api.py:56-57` |
| **503** | 外部相依未設定或不可連線——**禁止假成功、禁止占位圖** | `openrouter_api_key_not_configured`、`delivery_engine_not_configured`、RAG `feature_disabled`／模型快取缺／DB 不可用 | `main.py:2109-2116,2262-2269,2399-2402,2053-2057`；`rag_api.py:49-55` |
| **429** | 佇列飽和（本 repo 唯一的限流面） | `rag_job_capacity_reached` | `rag_api.py:186-191` |
| **307** | GLB 直送 CloudFront 遠端 URL | 無 code | `main.py:4012-4018` |

> **不使用**的碼：401／403（無認證，NFR-019）、201 以外的 2xx 建立語意、`204`。**部分失敗不進錯誤碼**：逐房生圖單房失敗只標 `status:"failed"`、夜景失敗只附 `night_notices`、色卡全失敗仍回 **201** 且不鎖旗標（`ai_render_service.py:376-385,395-413`；狀態碼由路由宣告 `main.py:2135` 的 `status_code=201` 套用到全失敗早退分支 `main.py:2191-2198`，與 [`openapi-render-delivery-v1.yaml`](./openapi-render-delivery-v1.yaml) `:224-225` 一致）。

---

## 4. 安全性

| 面向 | 現況 | 佐證 |
| :--- | :--- | :--- |
| **認證／授權** | 無。唯一邊界是 `--host 127.0.0.1` loopback 綁定（NFR-019、DEC-014 **待核准**） | `main.py:195-197`；`README.md:49` |
| **CORS／限流** | 無 CORS middleware；除 RAG 佇列 429 外無任何 rate limit | `main.py:196` 僅 GZip |
| **TLS** | 無（HTTP 明文 loopback） | 同上；[`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md) |
| **秘密不外洩** | 七個 `*/status` 端點只回布林與非敏感描述；RAG 狀態移除 `cache_dir` | `main.py:2028,2064,2378,3144,3331,3504`；`rag_api.py:164`；`rag/service.py:66` |
| **PII 剝除** | 遠端渲染請求剝除 address／email／name／phone；成果包依 `DELIVERY_SENSITIVE_KEYS` 脫敏（NFR-020） | `render_service.py:52-61`；`main.py:2475-2491` |
| **路徑跳脫防護** | 檔名一律取 `Path(name).name` basename | `main.py:1877,4067,4196`；`project_store.py:275-278` |
| **顯示字串防爆** | 儲存層對 `name`／`label`／`title` 等超過 512 字元者以識別碼取代（NFR-005） | `project_store.py:40-74` |

---

## 5. API 端點群

> 「FR」欄為 [`srs.md`](../01_requirements/srs.md) §2 的正式編號；未對到 FR 者為輔助或已無呼叫端的路由（見 §5.7）。「失敗碼」只列該端點特有者，共通的 404 `project_not_found` 不重複列。

### 5.1 專案與工作流（MOD-SRV-API／MOD-SRV-STORE，owner：Bella）

契約：[`openapi-project-workflow-v1.yaml`](./openapi-project-workflow-v1.yaml)

| 方法 | 路徑 | 用途 | 關鍵失敗碼 | FR | 佐證 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GET | `/`、`/styles`、`/library`、`/scene` | 四個靜態頁面入口（`/scene` 為八步主頁，`no-store`） | — | FR-020 | `main.py:1649-1670` |
| POST | `/api/projects` | 建專案，回 `project_id/current_step/workflow/revision`（201） | 422 `project_name_required` | FR-001 | `main.py:1784-1797` |
| GET | `/api/projects/{id}` | 唯讀取回專案，強制 `no-store` | 404 | FR-002 | `main.py:1800-1803` |
| PUT | `/api/projects/{id}/workflow` | 單一快照深合併寫入＋步驟白名單＋第 4 步複核閘門 | 422 `invalid_workflow_step`／`workflow_must_be_an_object`／`recognition_review_unresolved`、409 `project_revision_conflict`／`project_version_conflict`、413 `workflow_too_large` | FR-003, FR-004, FR-007 | `main.py:1806-1867` |
| POST | `/api/projects/{id}/floorplan` | 上傳平面圖，寫 `uploads/<id>/floorplan<ext>` 並 revision+1（201） | 415 `unsupported_floorplan_type`、422 `empty_floorplan`／`invalid_floorplan_image`、409 | FR-005 | `main.py:1870-1916` |
| GET | `/api/projects/{id}/floorplan/source` | 回原始上傳檔 | 409 `floorplan_missing`、410 `floorplan_source_missing` | FR-006 | `main.py:1919-1926` |
| POST | `/api/projects/{id}/renders` | 收瀏覽器輸出 PNG（201） | 422 `unsupported_render_provider`、413 `render_too_large`、415 `invalid_render_png`、409 | FR-009, NFR-002 | `main.py:1937-1997` |
| GET | `/api/projects/{id}/renders` | 列出該專案 PNG 紀錄 | 404 | FR-009 | `main.py:2000-2008` |
| GET | `/api/projects/{id}/renders/{render_id}/png` | 下載單張 PNG | 404 `render_not_found`、410 `render_file_missing` | FR-009 | `main.py:2011-2025` |

### 5.2 平面圖與辨識（MOD-FP／MOD-U3D，owner：Cody）

契約：[`openapi-project-workflow-v1.yaml`](./openapi-project-workflow-v1.yaml)

| 方法 | 路徑 | 用途 | 關鍵失敗碼 | FR | 佐證 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| POST | `/api/projects/{id}/floorplan/analyze` | 依副檔名分流 DXF／影像管線，輸出 `layout_json` ＋ `spatial_report`，並重設七個下游節點為 null | 409 `floorplan_confirmation_required`／`floorplan_missing`、410、422 `dxf_parse_failed`／`cody_recognition_failed` | FR-010–FR-016 | `main.py:2981-3069` |
| GET | `/api/floorplan/sample/630` | 內建示範平面圖 PNG | 404 `sample_floorplan_not_found` | — | `main.py:3072-3080` |

### 5.3 場景、引擎與家具型錄（MOD-SRV-SCENE／MOD-ENG／MOD-CAT，owner：Bella＋Ancai＋Kai）

契約：[`openapi-scene-v1.yaml`](./openapi-scene-v1.yaml)

| 方法 | 路徑 | 用途 | 關鍵失敗碼 | FR | 佐證 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| POST | `/api/scene/generate` | 問卷＋`layout_json`／`floorplan_editor` → `scene_json`（含 `placement_variant`，非法值靜默退回 A） | 無顯式 4xx | FR-029, FR-031 | `main.py:3591-3644` |
| POST | `/api/scene/layout` | 全場或單房重排／驗證；`validate_only:true` 不改座標；他房 passthrough | 無顯式 4xx | FR-032, FR-037 | `main.py:3647-3709` |
| POST | `/api/scene/decorate` | 依風格加軟裝，座標仍由引擎決定 | 無顯式 4xx（`decor_model_missing` 於 `main.py:3939-3943` 被攔截改走 `unavailable_roles` 回 200，HTTP 不可達，見 [`openapi-scene-v1.yaml`](./openapi-scene-v1.yaml) `§x-open-question`） | FR-038 | `main.py:3799-3995`（拋出點 `3756-3762`） |
| POST | `/api/scene/validate` | 單件拖曳落點合法性，回 `{ok, reason}`（中文理由） | 無顯式 4xx | FR-033, FR-034 | `main.py:3998-4009` |
| GET | `/api/furniture` | 型錄分頁查詢與 facet | 422（`page`／`page_size` 越界） | FR-039, NFR-006 | `main.py:3229-3279` |
| GET | `/api/catalog/status` | 型錄供應者、GLB／圖片 manifest、面材與色卡數；不外洩連線設定 | 無（不可用時 200 ＋ `available:false`） | FR-040, NFR-008 | `main.py:3144-3146` |
| GET | `/api/furniture/{id}/model` | GLB 交付：遠端 URL 走 307 | 307、404 | FR-042 | `main.py:4012-4018` |
| GET | `/api/furniture/{id}/model.gltf`、`/buffer.bin`、`/images/{i}` | 本機 GLB 拆解（僅非 CloudFront 模式） | 410（CloudFront 模式）、404 | FR-042 | `main.py:4021-4048` |
| GET | `/api/scene/bootstrap`、`/api/site-data`、`/api/home-data`、`/api/styles` | 風格卡、面材型錄、統計與型錄狀態的頁面級初始化資料 | — | — | `main.py:3083-3092,3149-3192` |
| GET | `/api/scene/provider-status` | OpenRouter gateway 狀態（不外洩 token） | — | FR-067 | `main.py:3331-3333` |

### 5.4 問卷與檢索（MOD-SRV-SCENE／MOD-RAG，owner：Bella＋Django）

契約：[`openapi-agent-rag-v1.yaml`](./openapi-agent-rag-v1.yaml)

| 方法 | 路徑 | 用途 | 關鍵失敗碼 | FR | 佐證 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GET | `/api/questionnaire/visual-catalog` | 視覺題庫（可依 `space_type`／`ready_only` 篩） | — | FR-026 | `main.py:3195-3215` |
| GET | `/api/questionnaire/visual-images/{image_id}` | 單張題目影像 | 404 `questionnaire_image_not_found` | FR-026 | `main.py:3218-3226` |
| GET | `/rag` | 檢索驗證頁（`no-store`） | — | — | `rag_api.py:159-161` |
| GET | `/api/rag/status` | 10 種具名 blocker；不載模型也不呼叫 LLM | — | FR-046 | `rag_api.py:164-166` |
| POST | `/api/rag/search` | 同步檢索（硬篩→rerank→加權排序→去重） | 503 `feature_disabled`／依賴缺／DB 不可用、502 上游失敗、500 | FR-047 | `rag_api.py:169-175` |
| POST | `/api/rag/search/jobs` | 非同步檢索入列（202） | 429 `rag_job_capacity_reached` | FR-048, NFR-009 | `rag_api.py:178-208` |
| GET | `/api/rag/search/jobs/{job_id}` | 輪詢工作狀態（完成後保留 3600 秒） | 404 `rag_job_not_found`（含逾時） | FR-048 | `rag_api.py:211-221` |

### 5.5 Agent 選件與並存管線（MOD-AGT，owner：Yen）

契約：[`openapi-agent-rag-v1.yaml`](./openapi-agent-rag-v1.yaml)

| 方法 | 路徑 | 用途 | 關鍵失敗碼 | FR | 佐證 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| POST | `/api/agent/furniture/select` | 伺服器端選件閘門：LLM 選擇須過本地白名單，未過整批降級 `local_rules` | 422（`rooms` 非 list） | FR-050, FR-051, FR-052 | `main.py:3440-3501` |
| POST | `/api/agent/intake/start`、`/answer` | 結構化需求訪談（不呼叫 LLM 的骨架） | 422（缺 `step`／`answer`） | — | `main.py:3336-3356` |
| GET | `/api/agent/pipeline/status` | 旗標與 gateway 狀態，**未啟用也永遠可查** | — | FR-053 | `main.py:3504-3507` |
| POST | `/api/agent/pipeline/{id}/start`、`/submit`、`/undo` | 並存管線 HITL 推進與回復 | **404（`ROOMPILOT_AGENT_PIPELINE` 未設）**、422、409 `PipelineNotStarted` | FR-053 | `main.py:3511-3557` |
| GET | `/api/agent/pipeline/{id}` | 查詢暫停點與最近階段產物 | 404（旗標未設或未啟動） | FR-053 | `main.py:3559-3567` |
| POST | `/api/agent/pipeline/reconcile` | 對帳第 6 步擺放 vs 管線擺放（比覆蓋與合法性，不比座標） | 404、422 | FR-054 | `main.py:3569-3588` |

### 5.6 生圖與交付（MOD-SRV-RENDER，owner：Bella）

契約：[`openapi-render-delivery-v1.yaml`](./openapi-render-delivery-v1.yaml)；治理理由見 [`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)

| 方法 | 路徑 | 用途 | 關鍵失敗碼 | FR | 佐證 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GET | `/api/render-provider/status`、`/api/ai-render/status`、`/api/delivery-proposal/status` | 三個外部相依的就緒狀態（只回布林與模型 id／安裝指引） | — | FR-067 | `main.py:2028-2030,2064-2067,2378-2381` |
| POST | `/api/projects/{id}/render-jobs` | 送外部渲染商（202 ＋輪詢；Pilot 預設未設定） | 422 `render_project_mismatch`、503 未設定／不可連線、502 上游拒絕 | FR-067, NFR-014 | `main.py:2033-2061` |
| POST | `/api/projects/{id}/ai-renders` | 逐房生圖（執行緒池），客廳額外 `full_render_night`（201） | 422 `scene_required`／`room_views_required`／`room_id_required`／`reference_png_required`、503 `openrouter_api_key_not_configured` | FR-058, FR-059, NFR-012 | `main.py:2070-2132` |
| POST | `/api/projects/{id}/palette-renders` | 代表房色卡比較圖，**每案僅能成功一次**；全失敗不鎖定（201） | 409 `palette_already_generated`、422 `room_required`／`style_card_ids_required`、503 | FR-056 | `main.py:2135-2221` |
| POST | `/api/projects/{id}/ai-renders/{room_id}/edit` | 改圖（現行程式為逐房各一次，見 OPEN-16）（201） | 409 `room_not_generated`／`ai_edit_budget_exhausted`、422 `feedback_required`／`base_image_required`、503、502 `ai_edit_failed` | FR-060 | `main.py:2224-2287` |
| POST | `/api/projects/{id}/design-manual` | 八章設計手冊 PDF（LLM 不可用走 deterministic 底稿）（201） | 422 `manual_project_mismatch`／`scene_required`／`rooms_required`、502 `design_manual_failed` | FR-061 | `main.py:2300-2332` |
| GET | `/api/projects/{id}/design-manual/pdf` | 下載設計手冊 | 404 `design_manual_not_found`、410 `design_manual_file_missing` | FR-061 | `main.py:2334-2351` |
| POST | `/api/projects/{id}/delivery-proposal` | 品牌交付提案 PDF（Chromium 子行程排版）（201） | 503 `delivery_engine_not_configured`（附安裝指引）、502 `delivery_proposal_failed`、422 | FR-062, NFR-013 | `main.py:2384-2418` |
| GET | `/api/projects/{id}/delivery-proposal/pdf` | 下載交付提案 | 404 `delivery_proposal_not_found`、410 `delivery_proposal_file_missing` | FR-062 | `main.py:2421-2437` |
| POST | `/api/projects/{id}/design-delivery` | 成果包 JSON（六章、依 `DELIVERY_SENSITIVE_KEYS` 脫敏） | 422 `delivery_project_mismatch` | FR-063, NFR-020 | `main.py:2947-2964` |

### 5.7 無生產前端呼叫的路由（OPEN-03 候選）

以 `backend/server/static/`（排除 `frontend3d/` 打包產物與已無載入路徑的 `scene.js`）掃描 `fetch` 目標，比對後**下列 24 條路由零呼叫端**。`scene.js`（3,128 行）未被任何 HTML `<script>` 引用（`scene.html:1217` 只載 `scene_v2.js`），其獨佔的端點一併列入。

| 群 | 路由 | 現況 | 佐證 |
| :--- | :--- | :--- | :--- |
| S1／S7 | `POST`／`GET /api/projects/{id}/renders`、`GET .../renders/{id}/png` | 瀏覽器 PNG 上傳鏈完整實作但無呼叫端（ACPT-008 只能由 TC 覆蓋） | `main.py:1937-2025` |
| S8 | `POST /api/projects/{id}/design-manual`、`GET .../pdf` | 與 OPEN-10「哪份是正式主件」相關 | `main.py:2300-2351` |
| S6 | `POST /api/scene/decorate` | 軟裝自動配置 | `main.py:3799-3995` |
| S6 | `GET /api/furniture/{id}/model`、`/model.gltf`、`/buffer.bin`、`/images/{i}` | 3D 直接讀型錄 `item.model_url`（CloudFront），不經本機 proxy | `scene_viewer.js:4224-4230` |
| S5 | `GET /api/questionnaire/visual-images/{id}`、`POST /api/rag/search`（同步版） | 前端只走 catalog ＋ jobs 佇列 | `scene_v2.js:7634`；`rag_api.py:169` |
| S5 | `POST /api/agent/intake/start`、`/answer` | 僅 `scene.js` 呼叫 | `scene.js:1686,2203,2466` |
| S2／S3 | `GET /api/floorplan/sample/630`、`GET /api/scene/provider-status` | 僅 `scene.js` 呼叫 | `main.py:3072,3331` |
| legacy | `GET /api/plans`、`GET /api/plan`、`POST /api/upload`、`POST /api/floorplan/analyze`、`POST /api/floorplan/confirm`、`POST /api/cost/estimate`、`GET /api/sample-furniture`、`GET /api/furniture/{name}` | 自舊 `app/backend/main.py` 移植，供 `frontend3d/` 與 `scene.js`；`cost/estimate` 的估價邏輯（FR-064）本身仍是唯一實作 | `main.py:4050-4199`；`cost_estimation.py:20-107` |

> **不列入退役候選**：`/api/agent/pipeline/*` 五條由 `ROOMPILOT_AGENT_PIPELINE` 旗標刻意隔離、預設 404，無前端呼叫是設計意圖而非殘留（FR-053、[`ADR-011`](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md)）。

---

## 6. 資料模型與契約邊界

逐欄位 schema 一律以四份 `openapi-*.yaml` 為 SSOT；本節只記 yaml 讀不出來的邊界。

| 邊界 | 規範 | 佐證 |
| :--- | :--- | :--- |
| `layout_json` vs `scene_json` | 辨識輸出止於 `layout_json`；方案生成與編輯輸出 `scene_json`。兩者不得互相冒充（[`ADR-001`](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)） | [`AGENTS.md`](../../AGENTS.md) §不可違反的契約；`vision/analysis.py:438-677` |
| 座標決定權 | 任何端點回傳的 `position_cm`／`rotation_y_deg` 一律由 `backend/engine/` 產出；前端與 LLM 只能提議（[`ADR-002`](../03_architecture/adr/ADR-002-engine-sole-geometry-authority.md)） | `engine/clearance.py:118-143`；`main.py:3799-3803` |
| 家電 | 只寫入 `scene_json.render_context.appliance_requirements`，不進 `scene_objects`、不進 `/api/furniture`（[`ADR-006`](../03_architecture/adr/ADR-006-appliances-render-context-only.md)） | `scene_service.py:3043-3072`；`main.py:930-931` |
| 型錄來源 | 第 6 步以 PostgreSQL view `roompilot.furniture_catalog_current` 優先；隔離區集合零外洩（[`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)） | `postgres_repository.py:199-204`；`tests/test_cloud_quarantine.py:23-40` |
| 自動產生的 OpenAPI | FastAPI 在 `/openapi.json`／`/docs` 自動輸出，但**幾乎所有 handler 的型別註記是裸 `dict`**，產物無欄位級 schema——這正是本目錄手寫四份 yaml 的原因 | `main.py:1784,3591,3647` 等簽章皆為 `payload: dict) -> dict` |

---

## 7. 待確認

> 程式碼看不出答案者一律列此；下游文件引用時不得寫成既成事實。

| ID | 內容 | 目前可驗證的事實 | 承接處 |
| :--- | :--- | :--- | :--- |
| OPEN-03 | §5.7 的 24 條無呼叫端路由該退役、保留為相容面，還是補回前端？`scene.js` 與 `frontend3d/` 的去留是同一個決定 | 靜態掃描結果如 §5.7；`scene.html:1217` 只載 `scene_v2.js`；`frontend3d/` 依 [`AGENTS.md`](../../AGENTS.md) §目錄責任僅為次要原型 | [`ADR-010`](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md)（OPEN-50 同源）、[`engineering_tracker.xlsx`](../03_architecture/engineering_tracker.xlsx) |
| OPEN-16 | 改圖額度是「整批一次」還是「逐房一次」 | 契約寫整批共用一次（`docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md:32-33`）；實作以 `room_state["edit_used"]>=1` 逐房擋（`main.py:2244-2248`），docstring 仍寫「整批一次」（`main.py:2226`），回應 `edit_remaining` 是常數 1／0（`main.py:2129,2284`） | [`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md) §4.4、[`prd.md`](../01_requirements/prd.md) §6 |
| 待確認（無既有編號） | 錯誤回應形狀三套並存（§3.1）是否收斂為單一信封；收斂會改動前端 `errorMessage()` 與全部 openapi 的 `ErrorResponse` | `main.py:1786-1793` vs `1811` vs FastAPI 內建；`scene_v2.js:642-653` 兩套都吃 | [`engineering_tracker.xlsx`](../03_architecture/engineering_tracker.xlsx) ①規格追溯 |
| 待確認（無既有編號） | 路徑無版本號（`/api/…` 而非 `/api/v1/…`）在 Pilot 之後是否仍成立；一旦有第二個消費端就需要版本策略 | 全 65 條路由零版本前綴；契約版本目前只靠 payload 的 `schema_version`（`engine/schema.py:18-32`） | [`sad.md`](../03_architecture/sad.md)、[`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md) |

---

## 8. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 上游 | FR-001–FR-067、NFR-002–NFR-006、NFR-009、NFR-013、NFR-014、NFR-017、NFR-019–NFR-021（[`srs.md`](../01_requirements/srs.md) §2、§3、§5）；DEC-001、DEC-002、DEC-007、DEC-010–DEC-013、DEC-016、DEC-017（[`brd.md`](../01_requirements/brd.md)） |
| 架構依據 | MOD-SRV-API、MOD-SRV-STORE、MOD-SRV-SCENE、MOD-SRV-RENDER、MOD-FP、MOD-U3D、MOD-ENG、MOD-CAT、MOD-RAG、MOD-AGT（[`sad.md`](../03_architecture/sad.md)）；[`ADR-001`](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)、[`ADR-002`](../03_architecture/adr/ADR-002-engine-sole-geometry-authority.md)、[`ADR-005`](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)、[`ADR-006`](../03_architecture/adr/ADR-006-appliances-render-context-only.md)、[`ADR-007`](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)、[`ADR-008`](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)、[`ADR-009`](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)、[`ADR-010`](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md)、[`ADR-011`](../03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md)、[`ADR-012`](../03_architecture/adr/ADR-012-pilot-loopback-deployment.md) |
| 契約 SSOT | [`openapi-project-workflow-v1.yaml`](./openapi-project-workflow-v1.yaml)（§5.1、§5.2）、[`openapi-scene-v1.yaml`](./openapi-scene-v1.yaml)（§5.3）、[`openapi-agent-rag-v1.yaml`](./openapi-agent-rag-v1.yaml)（§5.4、§5.5）、[`openapi-render-delivery-v1.yaml`](./openapi-render-delivery-v1.yaml)（§5.6）；repo 內契約 `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`、`AI_RENDER_OPENROUTER_CONTRACT.md`、`REMOTE_RENDER_CONTRACT.md`、`POSTGRESQL_FURNITURE_RAG_RUNTIME.md` |
| 驗收對應 | ACPT-001–ACPT-009、ACPT-024、ACPT-026、ACPT-027、ACPT-029–ACPT-031、ACPT-035–ACPT-038、ACPT-041–ACPT-046、ACPT-048、ACPT-050、ACPT-052–ACPT-054、ACPT-060（[`prd.md`](../01_requirements/prd.md)）；UC-001–UC-003（[`srs.md`](../01_requirements/srs.md) §6） |
| 下游 | [`lld.md`](./lld.md)（處理流程與內部函式）、[`db_design.md`](./db_design.md)（儲存層）、[`test_plan.md`](../05_qa/test_plan.md) TC-001–TC-060 的 API 整合案例、[`UAT_RoomPilot_Pilot_內部_2026-08-12.md`](../05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md)、`02_ux_ui/ui_spec-step1-project.md`–`ui_spec-step8-ai-render.md` 的資料需求段 |
| 維運承接 | RB-001（[`runbook-catalog-db-unavailable.md`](../06_ops/runbook-catalog-db-unavailable.md)）、RB-002（[`runbook-genpic-provider-failure.md`](../06_ops/runbook-genpic-provider-failure.md)）、RB-003（[`runbook-workflow-save-conflict-or-oversize.md`](../06_ops/runbook-workflow-save-conflict-or-oversize.md)）、RB-004（[`runbook-rag-model-cache-missing.md`](../06_ops/runbook-rag-model-cache-missing.md)）、RB-005（[`runbook-delivery-pdf-engine-missing.md`](../06_ops/runbook-delivery-pdf-engine-missing.md)）、RB-006（[`runbook-recognition-failed-or-review-blocked.md`](../06_ops/runbook-recognition-failed-or-review-blocked.md)）、RB-008（[`runbook-glb-asset-missing.md`](../06_ops/runbook-glb-asset-missing.md)） |
| 文件索引 | [`00-registry.md`](../00-registry.md) |
