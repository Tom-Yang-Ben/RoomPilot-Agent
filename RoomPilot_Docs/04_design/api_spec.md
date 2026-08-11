# API 設計規範 (API Specification) - RoomPilot

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿 | **OpenAPI 定義:** [`openapi-roompilot-v1.yaml`](./openapi-roompilot-v1.yaml)
> **契約 SSOT:** 端點與 schema 以 `openapi-roompilot-v1.yaml` 為準；本文件維護設計約定、錯誤語意與端點總表，§5–6 只放 yaml 讀不出來的說明。
> **Owner:** Bella（`backend/server/` 主要 owner，AGENTS.md:36）
> **語域:** L3（工程）
> **實例:** 約定單例；openapi 每服務一份（本專案為單一 FastAPI app）
> **定位宣告:** 本文件回答「RoomPilot 後端 API 的命名／單位／錯誤／版本約定與端點全貌」；不包含資料表設計（見 [db_design.md](./db_design.md)）、模組內部狀態機（見 [lld.md](./lld.md)）與跨模組資料邊界論述（見 [../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)）。
> **生成：** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 設計約定](#1-設計約定)
- [2. 通用行為](#2-通用行為)
- [3. 錯誤處理](#3-錯誤處理)
- [4. 安全性](#4-安全性)
- [5. API 端點總表](#5-api-端點總表)
- [6. 資料模型](#6-資料模型)
- [7. 待確認](#7-待確認)
- [8. 追溯](#8-追溯)

## 1. 設計約定

| 項目 | 規範 | 證據 |
| :--- | :--- | :--- |
| **風格** | RESTful，單一 FastAPI app（`backend/server/main.py`）＋唯一 include 的 RAG router（`backend/server/rag_api.py`） | main.py:197 |
| **Base URL** | 本機開發 `http://127.0.0.1:8000`；路徑前綴 `/api/...`，無 URL 版本段 | main.py 全部路由 |
| **格式** | `application/json` (UTF-8)；檔案上傳用 `multipart/form-data`（floorplan/renders） | main.py:1870、1937 |
| **欄位命名** | `snake_case`；長度／平面座標欄位一律 `_cm` 後綴 | AGENT_FRONTEND_BACKEND_CONTRACT.md:19-20 |
| **單位（鐵律）** | 跨模組幾何一律**公分**，payload 帶 `coordinate_unit: "cm"`；角度用度數（NFR-001）。例外：舊 3D 路徑 `/api/plan`、`/api/upload` 的 `scale_m`/`thickness`/`height` 為公尺制 query | scene_service.py:3020、main.py:4060-4081 |
| **版本控制** | 無 URL 版本；以 payload 內 `schema_version` 演進（client_brief 1.1、requirement 1.0、design-delivery 1.1、cost estimate 1.0、rag job `roompilot.rag.job.v1`）；新增欄位不升版 | main.py:2921、cost_estimation.py:98、rag_api.py:144 |
| **認證** | 無認證機制（Pilot 內部工具）；外部金鑰（OpenRouter）僅存伺服器端，status 端點不外洩 token | main.py:2064 |
| **靜態掛載** | `/static`、`/docs-assets` | main.py:216-217 |

## 2. 通用行為

- **分頁**：僅 `GET /api/furniture` 有 `page` query 分頁（main.py:3229）；其餘清單端點一次回全量。
- **過濾**：`GET /api/furniture` 支援 `style`/`group`/`type`/`q`（main.py:3229）；`GET /api/questionnaire/visual-catalog` 支援 `space_type`/`ready_only`（main.py:3195）。
- **並發控制（取代冪等 key）**：專案寫入端點以 `expected_revision`（int ≥0）樂觀鎖防多分頁互踩，落後回 409 `project_revision_conflict`（main.py:1806-1867；NFR-002／ACPT-014）。
- **快取**：`GET /scene` 頁與 `GET /api/projects/{id}` 回應帶 `Cache-Control: no-store`（main.py:1664、1800）。
- **非同步**：僅 RAG 檢索有 job 模式（202 + `GET /api/rag/search/jobs/{job_id}` 輪詢，rag_api.py:178-211）與遠端渲染 job（202，main.py:2033-2039）；其餘皆同步。
- **回應包裝**：無統一 envelope；`/api/scene/generate` 回 legacy 頂層 payload ＋ `scene_json`（deepcopy），前端讀 `response.scene_json || response`（main.py:3641-3644）。

## 3. 錯誤處理

錯誤走 FastAPI `HTTPException`，回應為 `{"detail": ...}`；`detail` 可能是字串（舊路徑）或物件 `{code, message, ...}`（新路徑，如 main.py:1850-1866）。無全域 `request_id`／統一 error type 欄位。

| code | HTTP | 端點／語意 | 證據 |
| :--- | :--- | :--- | :--- |
| `project_revision_conflict` | 409 | workflow/floorplan/renders 寫入時 revision 落後；detail 附最新 `project` | main.py:1853、1903、1992 |
| `workflow_too_large` | 413 | workflow JSON 快照 >2MB | main.py:1859-1866 |
| `recognition_review_unresolved` | 422 | 辨識複核未解決就存 workflow | main.py:1806-1867 |
| `render_not_found` | 404 | 下載不存在的 render PNG | main.py:2011 |
| （palette 已生成） | 409 | 第 7 步色卡比較圖每專案僅一次（ACPT-009） | main.py:2135-2140 |
| （改圖額度用完） | 409 | 每房一次改圖額度（ACPT-010） | main.py:2224-2226 |
| `delivery_engine_not_configured` | 503 | 缺 Playwright Chromium，交付提案不可產出（ACPT-011） | main.py:2384 |
| （AI 生圖未設金鑰） | 503 | OpenRouter 金鑰未設定 | main.py:2070-2076 |
| `rag_job_capacity_reached` | 429 | RAG job 佇列滿載 | rag_api.py:178-208 |
| `rag_job_not_found` | 404 | 查詢不存在的 RAG job | rag_api.py:211 |
| （project_id 不一致） | 422 | render-jobs payload `project_id` 與路徑不符 | main.py:2033-2039 |
| （floorplan 未確認） | 409 | 專案版辨識須先確認 floorplan | main.py:3064-3067 |

## 4. 安全性

- **認證／授權**：目前無（Pilot 內部工具，本機部署）；正式對外前須補（見 §7 待確認）。
- **敏感資訊**：`/api/ai-render/status` 只回可用性，不外洩 OpenRouter token（main.py:2064）。
- **上傳限制**：workflow JSON >2MB 回 413（main.py:1859-1866）。
- **TLS／速率限制／安全 headers**：程式碼中無實作證據（見 §7）。

## 5. API 端點總表

route 細節（request/response schema）以 [`openapi-roompilot-v1.yaml`](./openapi-roompilot-v1.yaml) 為準；本表列全貌與職責分群。行號基準 `backend/server/main.py`（yen@8863a36c）。

### 5.1 頁面與靜態

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| GET | `/`、`/styles`、`/library`、`/scene` | 首頁／風格頁／家具庫／八步工作流主頁（no-store） | main.py:1649-1664 |
| GET | `/rag` | RAG demo 頁 | rag_api.py:159 |

### 5.2 專案保存（Project Store；REQ-001、FR-001）

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| POST | `/api/projects` (201) | 建專案；`name` 必填，空回 422 | main.py:1784 |
| GET | `/api/projects/{project_id}` | 讀專案（no-store） | main.py:1800 |
| PUT | `/api/projects/{project_id}/workflow` | 存工作流草稿（樂觀鎖，見 §3） | main.py:1806-1867 |
| POST | `/api/projects/{project_id}/floorplan` (201) | 上傳平面圖（multipart） | main.py:1870 |
| GET | `/api/projects/{project_id}/floorplan/source` | 下載原始平面圖 | main.py:1919 |
| POST | `/api/projects/{project_id}/renders` (201) | 存 3D 截圖 PNG（FR-009） | main.py:1937 |
| GET | `/api/projects/{project_id}/renders`（＋`/{render_id}/png`） | 列出／下載 renders | main.py:2000、2011 |

### 5.3 平面圖辨識（產出 layout_json；REQ-002/004、FR-002/004）

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| POST | `/api/floorplan/analyze` | 圖檔＋標定/OCR/幾何 JSON → `analysis`＋`layout_json` | main.py:4106-4146 |
| POST | `/api/projects/{project_id}/floorplan/analyze` | 專案版辨識；floorplan 未確認回 409 | main.py:2981 |
| POST | `/api/floorplan/confirm` | 套用人工修正，回 `floorplan`＋`layout_json` | main.py:4149-4159 |
| GET | `/api/floorplan/sample/630` | 範例平面圖 PNG | main.py:3072 |
| GET/POST | `/api/plans`、`/api/plan`、`/api/upload` | 舊 DXF 3D 路徑（公尺制，例外見 §1） | main.py:4055-4081 |

### 5.4 場景與家具引擎（scene_json；REQ-006/007、FR-006/007、NFR-004）

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| POST | `/api/scene/generate` | 產生方案；`layout_json` canonical 輸入、`placement_variant` A/B | main.py:3591-3644 |
| POST | `/api/scene/layout` | 引擎重排全場座標；`placement_room_id` 單房重排、`validate_only` 只驗不排（ACPT-008） | main.py:3647-3709 |
| POST | `/api/scene/decorate` | 依風格加軟裝（座標仍由引擎決定） | main.py:3799 |
| POST | `/api/scene/validate` | 第 6 步拖曳落點單件合法性驗證（ACPT-007） | main.py:3998 |
| GET | `/api/scene/bootstrap`、`/api/scene/provider-status` | styles/色卡/surface catalog；OpenRouter 狀態 | main.py:3185、3331 |

### 5.5 Agent（intake／選件／並存管線；FR-005/015）

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| POST | `/api/agent/intake/start`、`/answer` | 需求訪談（client_brief schema 1.1；伺服器無狀態，brief 原樣帶回） | main.py:3336、3343 |
| POST | `/api/agent/furniture/select` | 選件閘門（offers 白名單、count 1–6、`selection_source`） | main.py:3440 |
| GET | `/api/agent/pipeline/status` | 管線開關/gateway 狀態（永遠可查，ACPT-015） | main.py:3504 |
| POST/GET | `/api/agent/pipeline/{project_id}`（`/start`、`/submit`、`/undo`、GET） | HITL 並存管線；start 需 `ROOMPILOT_AGENT_PIPELINE` flag | main.py:3518-3559 |
| POST | `/api/agent/pipeline/reconcile` | step6 vs 管線擺放對帳（SCN-010） | main.py:3569-3575 |

### 5.6 第 7/8 步生圖與交付（REQ-009~012、FR-010/011/012）

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| GET | `/api/ai-render/status`、`/api/render-provider/status` | 生圖／遠端渲染商可用性 | main.py:2064、2028 |
| POST | `/api/projects/{project_id}/ai-renders` (201) | 逐房寫實生圖（第 7 步鎖定視角截圖為 img2img 參考） | main.py:2070-2076 |
| POST | `/api/projects/{project_id}/palette-renders` (201) | 第 7 步代表房色卡比較；每專案僅一次 | main.py:2135-2140 |
| POST | `/api/projects/{project_id}/ai-renders/{room_id}/edit` (201) | 整批一次改圖；額度用完 409 | main.py:2224-2226 |
| POST | `/api/projects/{project_id}/render-jobs` (202) | 泛用遠端渲染 job（REMOTE_RENDER_CONTRACT.md） | main.py:2033-2039 |
| POST/GET | `/api/projects/{project_id}/delivery-proposal`（＋`/pdf`） | 正式交付提案 PDF (201)；下載 404/410 | main.py:2384、2421 |
| POST/GET | `/api/projects/{project_id}/design-manual`（＋`/pdf`） | 八章設計手冊 PDF（**非正式版**，UI 不觸發） | main.py:2300、2334 |
| POST | `/api/projects/{project_id}/design-delivery` | 第 8 步成果包五章 JSON（schema 1.1） | main.py:2947、2921 |
| POST | `/api/cost/estimate` | 台灣公開行情工程概算（schema 1.0） | main.py:4162 |
| GET | `/api/delivery-proposal/status` | Playwright Chromium 可用性 | main.py:2378 |

### 5.7 型錄／問卷／RAG／站台（REQ-013、FR-013、NFR-003/005）

| Method | Path | 用途 | 證據 |
|---|---|---|---|
| GET | `/api/furniture` | 型錄查詢；PostgreSQL view `roompilot.furniture_catalog_current` 優先 | main.py:3229 |
| GET | `/api/furniture/{furniture_id}/model`（＋`.gltf`/`buffer.bin`/`images/{i}`） | GLB：CloudFront 307 redirect；本機拆解在 CloudFront 模式回 410 | main.py:4012-4040 |
| GET | `/api/furniture/{name}`、`/api/sample-furniture`、`/api/catalog/status` | 家具詳情／範例／provider 狀態（ACPT-012） | main.py:4190、4174、3144 |
| GET | `/api/site-data`、`/api/home-data`、`/api/styles` | 站台/首頁/風格資料（18 張色卡） | main.py:3083-3167 |
| GET | `/api/questionnaire/visual-catalog`（＋`/visual-images/{image_id}`） | 問卷視覺題庫與圖片 | main.py:3195、3218 |
| GET/POST | `/api/rag/status`、`/api/rag/search`（＋`/jobs`、`/jobs/{job_id}`） | RAG 同步檢索與非同步 job（只回排序，不決定幾何） | rag_api.py:164-211 |

## 6. 資料模型

schema 細節在 [`openapi-roompilot-v1.yaml`](./openapi-roompilot-v1.yaml)；此處只記 yaml 讀不出來的邊界語意。

- **`layout_json`**（辨識輸出，ADR-001）：只描述空間本身——牆/門/窗/樑/柱/房間區域/scale/信心度；**禁止**家具、材質、相機、風格（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:16-34）。
- **`scene_json`**（設計方案）：`build_scene_payload` 頂層含 `requirement`（schema 1.0）、`floorplan`（`coordinate_unit: "cm"`）、`style_card`、`render_context`（僅 `appliance_requirements`——家電唯一合法去處，ADR-004/ACPT-013）、`furniture_candidates`、`scene_objects`（引擎座標，公分、房間中心原點）、`placement_resolution_report`（scene_service.py:2995-3088）。
- **舊資料相容**：無 `coordinate_unit` 的舊專案視為公尺，讀取時轉換一次（scene_service.py:1728、1762、1301）。
- **家具引擎輸入**：第 4/5 步→引擎唯一格式見 `docs/contracts/FURNITURE_ENGINE_ROOM_REQUIREMENTS_CONTRACT.md`（schema 1.0）。

## 7. 待確認

1. 認證／授權、TLS、速率限制、安全 headers 均無程式碼證據；Pilot 內部可接受與否須由 owner 於 `requirements_tracker.xlsx` 拍板。
2. `openapi-roompilot-v1.yaml` 為登錄簿 §6 計畫檔，撰寫本文件時尚未產出；產出前本表為端點清單的暫行參考。
3. layout_json `schema_version: "2.0"`（`polygon_cm` 固定結構）與第 4 步牆編輯欄位屬**待實作契約**（QUESTIONNAIRE_STYLE_MATERIAL_GENERATIVE_SPACE_CONTRACT.md:78-83、STEP4_WALL_EDITING_CONTRACT.md），非現行 API 行為。
4. ProjectStore 持久層：PostgreSQL Phase 3 runtime path 存在但 repo 缺 migration 腳本（POSTGRESQL_PROJECT_STORE_PHASE3.md:7-12）；實際落地形式待確認（登錄簿 §7 亦列）。
5. 錯誤 detail 字串／物件兩種形狀並存，是否統一為 `{code, message}` 待 owner 決定。

## 8. 追溯

| 項目 | ID／來源 |
| :--- | :--- |
| 上游 | REQ-001~014、FR-001~015、NFR-001~005（[../00-registry.md](../00-registry.md) §2）；ADR-001/002/003/004/005/007（登錄簿 §3）；`docs/contracts/` 27 檔（README.md 索引） |
| 契約 SSOT | `openapi-roompilot-v1.yaml`（登錄簿 §6） |
| 下游 | [../02_ux_ui/ui_spec-scene.md](../02_ux_ui/ui_spec-scene.md) 資料需求、[../05_qa/test_plan.md](../05_qa/test_plan.md) 整合案例（ACPT-001~015）、[lld.md](./lld.md) §5 狀態機 |
