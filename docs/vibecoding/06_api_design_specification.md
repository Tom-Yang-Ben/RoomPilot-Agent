# API 設計規範 - RoomPilot-Agent 後端(backend/server)

> 本文件由 VibeCoding 模板 06_api_design_specification.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 已發布(依現行程式碼逐條核對整理) | **OpenAPI 定義:** 由 FastAPI 自動生成(伺服器啟動後於 `/docs` 與 `/openapi.json` 取得;repo 內未維護靜態 OpenAPI 檔)

本文件描述 `backend/server/main.py` 中唯一的 FastAPI 應用(`app = FastAPI(title="AI 室內風格與家具配置展示系統")`,main.py:144)實際存在的全部 HTTP 端點。路由總數 44 條(27 GET + 16 POST + 1 PUT),全部定義於 main.py,無 APIRouter 拆分;另有 2 個靜態掛載與 1 個 `@app.on_event("startup")` 預熱(main.py:2102-2108,FastAPI 已標示棄用的 API,啟動失敗只印警告不擋服務)。

---

## 1. 設計約定

| 項目 | 規範(現況照實描述) |
| :--- | :--- |
| **風格** | REST 風味但非嚴格 RESTful:資源型路徑(`/api/projects/{project_id}`)與動作型路徑(`/api/scene/generate`、`/api/floorplan/analyze`)並存;無 DELETE/PATCH 方法 |
| **Base URL** | 程式碼未寫死 port。README.md:185 標準啟動:`uv run uvicorn backend.server.main:app --port 8002`(8002 被占用時改 8010/8014;不給 `--port` 則為 uvicorn 預設 8000)。無 production 網域 |
| **格式** | 回應以 `application/json`(UTF-8)為主;檔案上傳走 `multipart/form-data`;圖檔/GLB 下載回 `FileResponse` / 二進位 `Response` |
| **資源路徑** | 小寫;多字路徑段用連字符(`/api/render-provider/status`、`/api/scene/provider-status`);路徑參數用 `snake_case`(`{project_id}`、`{furniture_id}`、`{render_id}`、`{image_id}`) |
| **欄位命名** | `snake_case`。少數舊契約同時接受 camelCase(如 workflow 內 privacy 確認:`project_only`/`projectOnly`、`no_training`/`noTraining` 皆可,main.py:1789-1794) |
| **日期格式** | ISO 8601 UTC:`datetime.now(timezone.utc).isoformat()`(project_store.py:14-15),如 `created_at`/`updated_at` |
| **認證** | 無。全部端點皆無認證與授權機制;亦無 CORS middleware(全 backend/ grep 無 `add_middleware`/`cors` 命中)。僅對外呼叫遠端渲染供應商時,由伺服器附 `Authorization: Bearer <ROOMPILOT_RENDER_PROVIDER_TOKEN>`(render_service.py:136-138) |
| **版本控制** | (模板段落保留;現況:未採用 URL 版本策略,無 `/v1/` 前綴。) 取而代之的是三種資料層版本:(1) 專案樂觀鎖 `revision`(整數,見第 2 節);(2) 回應內 `schema_version` 欄位(scene payload、cost estimate、confirm 契約均為 `"1.0"`;client_brief 為 `"1.1"`);(3) 前端 workflow 契約 `WORKFLOW_SCHEMA_VERSION = 2`(static/scene_workflow.js:1) |

### 主流程步驟(程式碼權威順序)

`PUT /api/projects/{project_id}/workflow` 的 `current_step` 只接受以下 11 個步驟名。有序來源是前端 `backend/server/static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS`;伺服器端 `main.py:113-125` 的 `WORKFLOW_STEPS` 是同名集合(set,無序),只驗名稱不驗順序,步驟前置依賴僅由前端強制——伺服器無法阻止跳步驟寫入。

```
project → upload → recognition → calibration → space_confirmation → requirements
→ layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render
```

(`recognition` 與 `calibration` 在 UI 共用同一個 "scale" 面板,故 scene.html 只顯示 10 顆步驟按鈕。)

---

## 2. 通用行為

### 分頁

(模板的游標分頁未採用。)只有 `GET /api/furniture` 有分頁,採頁碼式:`page`(≥1,預設 1)+ `page_size`(1–80,預設 24);回應含 `total` 與 `has_next_page`(main.py:2024-2061)。其餘列表端點(如 `/api/projects/{id}/renders`)一次回全部。

### 排序

現況:無任何端點提供排序參數。`GET /api/projects/{id}/renders` 固定依 `created_at DESC, render_id DESC`(project_store.py:405-416)。

### 過濾

`GET /api/furniture` 以欄位名直接作 query 參數:`style`、`group`、`type`、`q`(關鍵字)、`has_model`、`color`、`material`、`size`、`detail`(`card`|`scene`)。`GET /api/questionnaire/visual-catalog` 支援 `space_type` 與 `ready_only`。

### 冪等性與並行控制

- 用戶端對本伺服器**不**傳 `Idempotency-Key`(模板段落保留;現況未實作)。伺服器轉送遠端渲染任務時,自己對供應商附 `Idempotency-Key: <request_id>` 與 `X-RoomPilot-Scene-Version` 標頭(render_service.py:131-135)。
- 專案寫入採**樂觀鎖**:`PUT .../workflow`、`POST .../floorplan`、`POST .../renders` 皆吃 `expected_revision`(非負整數);與資料庫 `revision` 不符時回 `409 project_revision_conflict`,錯誤 detail 內附最新 `project` 供前端合併重試。
- workflow JSON 上限 2 MB(`MAX_WORKFLOW_BYTES = 2 * 1024 * 1024`,project_store.py:11),超過回 `413 workflow_too_large`。

### 持久化

專案/上傳/渲染紀錄存 SQLite(WAL):`.runtime/projects.sqlite3`;上傳檔在 `.runtime/uploads/{project_id}/floorplan{ext}`;渲染 PNG 在 `.runtime/renders/{project_id}/`。`.runtime` 位置 = repo 根或環境變數 `ROOMPILOT_RUNTIME_DIR`(runtime_paths.py:20-25)。

---

## 3. 錯誤處理

全部錯誤經 FastAPI `HTTPException`,實際 HTTP body 是 FastAPI 預設包裝 `{"detail": ...}`,其中 `detail` 有兩種形狀(並存,未統一):

**結構化 detail(專案/上傳/場景等主流程端點):**

```json
{
  "detail": {
    "code": "project_revision_conflict",
    "message": "專案已在另一個分頁更新，請載入最新版本後再儲存。",
    "project": { "...最新專案物件,僅衝突類錯誤附帶..." }
  }
}
```

部分錯誤另帶 `focus`(前端聚焦欄位,如 `"floorplan-file"`)或 `allowed_extensions` 等輔助欄位。

**純字串 detail(舊移植路由與簡單驗證):** 如 `{"detail": "invalid_workflow_step"}`、`{"detail": "parse failed: ..."}`。

模板的 `type`/`param`/`request_id` 欄位現況未實作。

### 錯誤碼一覽(逐條自程式碼核對)

| 錯誤碼(code / detail) | HTTP | 出處與描述 |
| :--- | :--- | :--- |
| `project_not_found` | 404 | 專案不存在(main.py:1455-1465) |
| `render_not_found` | 404 | 渲染紀錄不存在(main.py:1734-1741) |
| `questionnaire_image_not_found` | 404 | 問卷視覺圖 ID 不存在(main.py:2007-2015) |
| `sample_floorplan_not_found` | 404 | demo 樣張檔案不存在(main.py:1885-1888) |
| `plan not found: {name}`(字串) | 404 | 舊 R3F 路由查無 DXF(main.py:2674-2675) |
| `project_name_required` | 422 | 建立專案缺 `name`(main.py:1520-1531) |
| `invalid_workflow_step` / `workflow_must_be_an_object` / `expected_revision_must_be_a_non_negative_integer` / `pending_save_base_version_required`(字串) | 422 | workflow 儲存驗證(main.py:1546-1562) |
| `empty_floorplan` / `invalid_floorplan_image` | 422 | 上傳空檔/副檔名對但內容非圖(main.py:1493-1517) |
| `dxf_parse_failed` / `cody_recognition_failed` | 422 | 辨識失敗(main.py:1819-1848) |
| `render_versions_must_be_non_negative` / `unsupported_render_provider` / `invalid_render_png`(損壞) | 422 | 渲染 PNG 上傳驗證(main.py:1672-1699) |
| `render_project_mismatch`、及 render_service 的 `unsupported_render_mode`/`scene_version_required`/`style_card_ids_required`/`locked_master_camera_required`/`room_views_required`/`room_view_room_id_required`/`room_view_camera_required` | 422 | 遠端渲染 payload 驗證(main.py:1759-1770、render_service.py:100-116) |
| `analysis_required` / `cost_items_required` / `invalid_{field}_json` / `floorplan_image_required`(415)/ `parse failed: ...`(字串) | 422 / 415 | 無專案分析、成本概算、舊 DXF 路由(main.py:2696-2768) |
| `unsupported_floorplan_type` | 415 | 平面圖副檔名不在 `.dxf/.png/.jpg/.jpeg`(main.py:1602-1610) |
| `invalid_render_png`(magic bytes) | 415 | 渲染上傳非 PNG(main.py:1687-1691) |
| `floorplan_missing` / `floorplan_confirmation_required` / `decor_model_missing` / `project_revision_conflict` / `project_version_conflict` | 409 | 前置條件未滿足或版本衝突(main.py:1468-1480、1801-1809、2409-2416、1571-1581) |
| `floorplan_source_missing` / `render_file_missing` / CloudFront 模式各 GLB 端點(字串訊息) | 410 | 紀錄在但檔案遺失;或 cloudfront 模式下本機 GLB 端點永久關閉(main.py:1481-1489、1742-1747、2627-2653、2791-2792) |
| `workflow_too_large` / `render_too_large` | 413 | workflow >2MB、PNG >20MB(main.py:1582-1589、1681-1686) |
| `render_provider_http_{status}` / `render_provider_invalid_json` / `render_provider_invalid_response`、遠端 GLB 讀取失敗(字串) | 502 | 渲染供應商拒絕、遠端 GLB 損壞(render_service.py:143-155、main.py:905-909) |
| `render_provider_not_configured` / `render_provider_unreachable` | 503 | 渲染供應商未設定或連不上(render_service.py:127-128、147-148) |

(模板中的 401/403/429 現況不存在——無認證即無認證失敗;無速率限制。)

---

## 4. 安全性

照實描述,模板項目未實作者標記現況:

- **TLS**:(現況:未實作)應用本身以 uvicorn HTTP 服務,無 HTTPS 強制;無反向代理設定在 repo 內。
- **速率限制**:(現況:未實作)無任何 rate limit 與 `RateLimit-*` 標頭。
- **安全 Headers**:(現況:未實作)無 HSTS/CSP middleware。僅 `GET /scene` 與 `GET /api/projects/{id}` 加 `Cache-Control: no-store` 防舊快取。
- **實際存在的防護**:
  - 上傳驗證:平面圖副檔名白名單 + PIL `Image.verify()`;渲染 PNG 驗 magic bytes + PIL verify + 20 MB 上限。
  - 路徑跳脫防護:檔名一律取 `Path(name).name` basename(main.py:1600、2673、2793)。
  - 個資剝除:送遠端渲染前遞迴移除 `name`/`phone`/`email`/`address` 等 `PRIVATE_KEYS` 欄位(render_service.py:12-22、52-61)。
  - GLB 供應信任邊界:cloudfront 模式(預設)只回 manifest 驗證過的 CloudFront URL,本機 GLB 拆解端點一律 410(services/cloud_models.py:48-54、main.py:914-935)。
  - 樂觀鎖防止多分頁互相覆蓋(見第 2 節)。
- **OWASP API Top 10**:(現況:未系統性評估)最大缺口為全面無認證——任何能連到 port 的人可讀寫所有專案。目前定位為區網 demo 系統。

---

## 5. API 端點定義

### 資源:頁面與靜態資源

| 方法/路徑 | 用途 |
| :--- | :--- |
| `GET /` | 回 `static/index.html`(首頁) |
| `GET /styles` | 回 `static/styles.html`(風格頁) |
| `GET /library` | 回 `static/library.html`(型錄頁) |
| `GET /scene` | 回 `static/scene.html`(10 步主流程單頁應用),附 `Cache-Control: no-store` |
| `MOUNT /static` | `backend/server/static/` 靜態檔(main.py:163) |
| `MOUNT /docs-assets` | `backend/server/static/moodboard_assets/`(main.py:164) |

---

### 資源:專案(Projects)

**路徑:** `/api/projects`

#### `POST /api/projects` - 建立專案

- **請求體**: `{"name": "三房兩廳提案", "notes": "備註(選填)"}`;`name` 必填,空值回 422 `project_name_required`
- **回應**: `201 Created` → `{"project": Project}`(Project 形狀見第 6 節)

#### `GET /api/projects/{project_id}` - 取得專案

- **回應**: `200 OK` → `{"project": Project}`;附 `Cache-Control: no-store`;404 `project_not_found`

#### `PUT /api/projects/{project_id}/workflow` - 保存工作流草稿

- **請求體**:

```json
{
  "current_step": "layout_2d",
  "workflow": { "...前端 10 步流程的完整草稿 JSON..." },
  "expected_revision": 7,
  "replay_pending": false,
  "base_updated_at": "2026-07-26T00:10:00+00:00"
}
```

  - `current_step` 須在第 1 節的 11 個步驟名內,否則 422 `invalid_workflow_step`
  - `expected_revision` 選填;帶了就啟用樂觀鎖
  - `replay_pending: true`(離線補存)時 `base_updated_at` 必填
- **回應**: `200 OK` → `{"project": Project}`;409 `project_revision_conflict`(detail 附最新 `project`)/ 413 `workflow_too_large`

---

### 資源:平面圖(Floorplan,綁定專案)

#### `POST /api/projects/{project_id}/floorplan` - 上傳平面圖

- **請求體**: `multipart/form-data`:`file`(必填;副檔名限 `.dxf`/`.png`/`.jpg`/`.jpeg`)+ `expected_revision`(Form,選填整數)
- **回應**: `201 Created` →

```json
{
  "project": { "...Project..." },
  "upload": {
    "filename": "floor04.png",
    "extension": ".png",
    "mime_type": "image/png",
    "source_url": "/api/projects/{project_id}/floorplan/source"
  }
}
```

- **錯誤**: 415 `unsupported_floorplan_type`(附 `allowed_extensions`)/ 422 `empty_floorplan`、`invalid_floorplan_image` / 409 `project_revision_conflict`

#### `GET /api/projects/{project_id}/floorplan/source` - 下載原始上傳檔

- **回應**: `200 OK` → 原檔 `FileResponse`;409 `floorplan_missing`(還沒上傳)/ 410 `floorplan_source_missing`(紀錄在、檔案遺失)

#### `POST /api/projects/{project_id}/floorplan/analyze` - 啟動辨識

- **請求體**: 無(前置條件在 workflow 內:`workflow.floorplan_confirmation.confirmed === true`,或舊 privacy 形狀確認;否則 409 `floorplan_confirmation_required`)
- **行為**: DXF 走 `parse_floorplan_with_engine`(`geometry_engine: "dxf"`);PNG/JPG 走 `analyze_floorplan_image`(`geometry_engine: "cody"`)。成功後**重置下游步驟**並寫入 `_flow: {currentStep: "recognition", completed: ["project","upload","recognition"], staleFrom: "calibration"}`(main.py:1851-1878)
- **回應**: `200 OK` → `{"analysis": {...}, "geometry_engine": "dxf" | "cody"}`
- **錯誤**: 422 `dxf_parse_failed` / `cody_recognition_failed`

#### `GET /api/floorplan/sample/630` - Demo 樣張

- **回應**: `200 OK` → `testdata/png/builder_plan_630.png`;404 `sample_floorplan_not_found`

---

### 資源:渲染成品與遠端渲染(Renders / Render Jobs)

#### `POST /api/projects/{project_id}/renders` - 上傳瀏覽器輸出的最終 PNG

- **請求體**: `multipart/form-data`:`file`(PNG,≤20 MB)+ Form 欄位:`expected_revision`(**必填**整數)、`white_model_version`/`viewpoint_version`/`style_version`(預設 0)、`style_card_id`(預設 `"unassigned"`)、`provider`(只接受 `"browser_capture"`)
- **回應**: `201 Created` → `{"project": Project, "render": Render}`(Render 含 `download_url`,見第 6 節)
- **錯誤**: 413 `render_too_large` / 415 `invalid_render_png`(非 PNG)/ 422 `invalid_render_png`(損壞)、`unsupported_render_provider` / 409 `project_revision_conflict`

#### `GET /api/projects/{project_id}/renders` - 列出渲染紀錄

- **回應**: `200 OK` → `{"renders": [Render, ...]}`(依 `created_at` 新到舊);404 `project_not_found`

#### `GET /api/projects/{project_id}/renders/{render_id}/png` - 下載 PNG

- **回應**: `200 OK` → PNG `FileResponse`;404 `render_not_found` / 410 `render_file_missing`

#### `GET /api/render-provider/status` - 遠端渲染供應商狀態

- **回應**: `{"configured": false, "provider": "remote_renderer", "has_token": false}`(讀環境變數 `ROOMPILOT_RENDER_PROVIDER_URL` / `_NAME` / `_TOKEN`,不外洩憑證)

#### `POST /api/projects/{project_id}/render-jobs` - 提交遠端渲染任務

- **請求體**(節錄必要欄位;`payload.project_id` 必須等於路徑 `project_id`,否則 422 `render_project_mismatch`):

```json
{
  "project_id": "…",
  "mode": "palette_comparison",
  "scene_version": "sv_20260726_01",
  "style_card_ids": ["scandinavian-01", "japanese-02"],
  "master_view": { "camera": { "position_cm": [320, 150, 480], "target_cm": [0, 90, 0], "fov_deg": 55 } },
  "room_views": [ { "room_id": "room-1", "camera": { "position_cm": [0, 0, 0], "target_cm": [0, 0, 0] } } ],
  "requirements": { "…送出前伺服器剝除 name/phone/email/address 等個資欄位…" }
}
```

  - `mode` 限 `palette_comparison` | `room_final`;`room_final` 才要求 `room_views`
- **回應**: `202 Accepted` → 供應商回傳的 JSON,伺服器補上 `request_id` 與 `provider` 預設值
- **錯誤**: 422(驗證碼見第 3 節)/ 503(未設定或連不上)/ 502(供應商拒絕)
- **環境變數**: `ROOMPILOT_RENDER_PROVIDER_URL` / `_TOKEN` / `_NAME`、`ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS`(5–180,預設 60)

---

### 資源:站台資料與家具型錄(Catalog)

#### `GET /api/site-data` - 全站 payload

- **回應**: `200 OK` → 全站資料,但 `furniture` 與 `featured_models` 固定清空,`catalog_merge_summary.delivery` 指示「請使用 /api/furniture 分頁取得家具資料。」(main.py:1896-1905)

#### `GET /api/catalog/status` - 型錄供應狀態

- **回應**:

```json
{
  "furniture": { "…manifest_status():verified_model_count、cloudfront_base_url、manifest_ready 等…" },
  "surfaces": { "provider": "local_pending_aws_manifest", "wall_count": 110, "floor_count": 299 },
  "doors": { "provider": "procedural_pending_aws_catalog", "catalog_count": 0 },
  "style_cards": { "provider": "local_allowed", "count": 6 }
}
```

(`wall_count`/`floor_count` 由版控 surface catalog 的 usage 標籤計數、`style_cards.count` = `len(load_taiwan_style_cards())`,以上為 TestClient 實測值;`doors.catalog_count` 為程式硬寫 0。)

#### `GET /api/home-data` - 首頁摘要

- **回應**: `{"project": {"title": "RoomPilot", "subtitle": "AI 室內配置與 3D 場景提案"}, "summary": {"total_furniture", "styled_furniture"}, "styles": [前 6 風格], "taiwan_style_cards": [前 6 卡], "catalog_status": {...}}`

#### `GET /api/styles` - 全部風格資料

- **回應**: `{"styles", "taiwan_style_cards", "surface_catalog", "summary": {"total_furniture","styled_furniture","fallback_furniture"}, "style_furniture_counts", "style_type_counts", "catalog_status"}`

#### `GET /api/scene/bootstrap` - 場景初始化包

- **回應**: `{"styles", "taiwan_style_cards", "surface_catalog", "catalog_status"}`

#### `GET /api/questionnaire/visual-catalog` - 問卷視覺題庫

- **參數**: `space_type`(選填)、`ready_only`(預設 false)
- **回應**: `{"version", "notice_zh", "question_count", "image_count", "ready_image_count", "questions": [...]}`;來源為版控 JSON `backend/server/data/questionnaire_visual_catalog.json`,SQLite(`.runtime/indexes/questionnaire_visuals.sqlite3`)只是惰性建立的查詢索引

#### `GET /api/questionnaire/visual-images/{image_id}` - 單張問卷圖紀錄

- **回應**: `200 OK` → 圖片紀錄;404 `questionnaire_image_not_found`

#### `GET /api/furniture` - 分頁家具型錄(正式集合 9,350 件 + 六風格 enrichment)

- **參數**: `style`、`group`、`type`、`q`、`page`(≥1)、`page_size`(1–80,預設 24)、`has_model`、`detail`(`card`|`scene`,預設 `card`)、`color`、`material`、`size`
- **回應**:

```json
{
  "items": [ { "…FurnitureCard(見第 6 節)…" } ],
  "page": 1,
  "page_size": 24,
  "total": 9350,
  "has_next_page": true,
  "styles": [ "…風格過濾選項…" ],
  "type_options": [], "category_groups": [], "filter_options": {},
  "furniture": [ "…舊 R3F 檢視器相容鍵(cloudfront 模式回去重後前 24 個 https model_url)…" ],
  "catalog_status": {}
}
```

---

### 資源:Agent 需求訪談與選件(Agent)

#### `GET /api/scene/provider-status` - OpenRouter 場景規劃狀態

- **回應**: `{"enabled", "has_api_key", "has_model", "model", "models", "model_count", "provider": "openrouter"|"fallback", "scene_planning_enabled"}`;`enabled` 需同時有 `OPENROUTER_API_KEY` 且 `OPENROUTER_SCENE_PLANNING_ENABLED=1`

#### `POST /api/agent/intake/start` - 開始引導式需求訪談

- **請求體**: 選填 `{"session_id": "..."}`(預設 `"roompilot-local"`)
- **回應**: `{"session_id", "mode": "guided_llm"|"guided_fallback", "step": "space_type", "question": "你想規劃哪一個空間？…", "client_brief": ClientBrief, "ready_for_confirmation": false}`
- 六步固定順序(intake_service.py:13-20):`space_type → occupants → needs → style → materials → constraints`;LLM 模式需 `OPENROUTER_API_KEY` + `OPENROUTER_INTAKE_ENABLED=1`(預設模型 `qwen/qwen3-32b:free`,逾時 8 秒),失敗自動退正則抽取

#### `POST /api/agent/intake/answer` - 前進一輪訪談

- **請求體**: `{"session_id", "step": "space_type", "answer": "兩位大人一隻貓的客廳…", "client_brief": ClientBrief}`;`step` 與 `answer` 必填,缺一回 422
- **回應**: `{"session_id", "mode", "step": 下一步|null, "question": 下一題|null, "reply", "client_brief": 更新後 brief, "ready_for_confirmation", "llm_model"}`

#### `POST /api/agent/furniture/select` - 伺服器端選件驗證閘

- **請求體**: `{"rooms": [{"room_id", "room_type", ...}], "offers": {"room_id": [候選家具]}, "style_id", "context", "llm_selection": {選填,前端已取得的 LLM 選擇}}`;`rooms` 非 list 回 422
- **行為(三層降級)**: 先驗 `llm_selection`(通過即 `source: "openrouter"`)→ 驗不過改本地規則(每房每族系取第一個候選,`source: "local_rules"`,warnings 說明原因)→ 再失敗保留每房前 8 個候選(`source: "local_rules_unvalidated"`)
- **回應**: `{"source", "model", "warnings": [], "rooms": [{"room_id", "items": [{...候選欄位, "count", "selection_source"}]}]}`

---

### 資源:場景生成與擺位(Scene)

#### `POST /api/scene/generate` - 生成完整場景

- **請求體**(主要欄位,main.py:2294-2326;全部選填、有預設):`space_type`、`style_preference`、`style_card_id`、`required_furniture`、`selected_furniture`、`selected_furniture_exact`、`custom_furniture`、`preferred_colors`、`custom_colors`、`personal_notes`、`questionnaire`(Test2 問卷)、`keep_window_clear`、`keep_door_clear`、`need_storage`、`prefer_low_saturation`、`client_brief`、`floorplan_filename`、`floorplan_dxf_text`、`floorplan_editor`、`wall_option`/`floor_option`(預設 `"auto"`)、`furniture_random_seed`、`room_width_cm`(預設 420)、`room_depth_cm`(預設 360)
- **回應**: `200 OK`,頂層鍵(scene_service.py:1770-1858):

```json
{
  "scene_id": "scene_ab12cd34ef",
  "llm_mode": "…", "llm_model": "…",
  "questionnaire": {}, "requirement": { "schema_version": "1.0", "room_type": "…", "constraints": {} },
  "plan_json": {},
  "floorplan": { "coordinate_unit": "cm", "width_cm": 420, "depth_cm": 360, "wall_segments": [], "door_segments": [], "window_segments": [], "room_regions": [], "…": "…" },
  "style": { "style_id", "style_name_zh", "scene_background", "palette_hex", "surface_profile" },
  "style_card": {},
  "design_choices": { "style_card_id", "wall_option", "floor_option", "single_room_mode", "accurate_dxf_mode" },
  "surface_catalog": {},
  "furniture_candidates": { "schema_version": "1.0", "candidates": [], "layout_relations": [] },
  "selected_furniture": [],
  "scene_objects": [],
  "placement_resolution_report": {},
  "placement": { "engine": "furniture_engine", "failed": [{ "furniture_id", "type", "name", "reason" }], "unavailable_types": [] }
}
```

#### `POST /api/scene/layout` - 前端操作後全場重排

- **請求體**: `{"scene_objects": [...], "floorplan": {...} 或 "floorplan_editor": {...}, "placement_room_id", "placement_variant": "A"|"B"(預設 "A",非法值靜默改 "A")}`;帶 `position_locked` 的物件(使用者拖曳過)位置仍合法就不重排
- **回應**: `{"scene_objects": [...]}`

#### `POST /api/scene/decorate` - 依房型自動軟裝

- **請求體**: `{"scene_objects", "floorplan"|"floorplan_editor", "placement_room_id", "room": {"type": "..."}, "style"}`
- **行為**: 依房內既有家具與房型決定加 `light`/`rug`/`plant`/`curtain`;先移除該房舊 auto_decor 再重算(重跑=重算而非累加);放不下的軟裝直接捨棄不硬塞。布簾用固定假想品項 `model_url: "/static/models/roompilot-curtain.glb"`(main.py:2446)——**注意:該 GLB 實際不存在**(`find backend/server/static -name '*.glb'` 為 0,`static/models/` 目錄不存在)。前端已有兜底:scene_viewer.js 的 `loader.loadAsync` 失敗會被 catch,改放同尺寸白色替代物並在狀態列列為「GLB 載入失敗,已顯示同尺寸白色替代物」(scene_viewer.js:2907、2935-2938、2954-2957),故此 404 不會中斷場景
- **回應**: `{"scene_objects": [...], "decor_summary": {"requested": ["light","rug"], "placed": ["light"], "engine": "furniture_engine"}}`
- **錯誤**: 型錄缺某角色 GLB **不再回 409**;該角色列進 `decor_summary.skipped`,其餘照常配置。舊行為 409 `decor_model_missing`(型錄找不到對應角色的 GLB)

#### `POST /api/scene/validate` - 單件家具落點驗證(F6 拖曳)

- **請求體**: `{"floorplan"|"floorplan_editor", "item": {單件場景物件}, "others": [其餘物件]}`
- **回應**: `{"ok": true, "reason": null}` 或 `{"ok": false, "reason": "超出房間範圍(需完整放在某一間房內,不能跨牆)"}`(scene_service.py:1185-1213)

#### `POST /api/cost/estimate` - 工程概念概算

- **請求體**: `{"items": [...]}`;`items` 非 list 回 422 `cost_items_required`
- **回應**: `{"schema_version": "1.0", "catalog_version", "currency": "TWD", "region": "台灣", "items": [...], "needs_quote": [...], "totals_twd": {...}, "status": "concept_estimate", "disclaimer_zh": "..."}`(cost_estimation.py:97-107;費率來自版控內台灣公開行情)

---

### 資源:GLB 模型供應(Model Delivery)

供應模式由 `ROOMPILOT_MODEL_DELIVERY_MODE` 決定,預設 `cloudfront`(services/cloud_models.py:47-54;base URL `https://ddgsm1yg3xikc.cloudfront.net` 定義於 cloud_models.py:34,可用 `ROOMPILOT_CLOUDFRONT_BASE_URL` 覆寫,cloud_models.py:69)。

#### `GET /api/furniture/{furniture_id}/model` - 取得家具 GLB

- **回應**: manifest 驗證過的家具 → `307 Temporary Redirect` 到 CloudFront URL;cloudfront 模式下 manifest 無此列 → 404;local 模式才嘗試外部 zip/本機檔/遠端 URL fallback(main.py:914-935)

#### `GET /api/furniture/{furniture_id}/model.gltf` / `buffer.bin` / `images/{image_index}` - 本機 glTF 拆解端點

- **回應**: cloudfront 模式(預設)一律 `410 Gone`;local 模式回拆解後的 glTF JSON / 二進位 chunk / 內嵌圖

#### `GET /api/sample-furniture` - 範例 GLB 清單

- **回應**: cloudfront 模式 → `{"furniture": [], "provider": "aws_cloudfront", "message": "請由家具型錄取得已驗證的 CloudFront model_url。"}`;local 模式 → `{"furniture": ["xxx.glb", ...]}`(`testdata/sample_glb/`)

#### `GET /api/furniture/{name}` - 雙用途端點(定義在 main.py 最末,2787)

- `name` 以 `.glb` 結尾:回 `testdata/sample_glb/` 實體 GLB(cloudfront 模式 410;檔案不在 404)
- 否則視為 `furniture_id`:回合併後家具詳情 payload(FurnitureCard + `merged_furniture_ids`、`model_priority_ids`、`catalog_merge_key`、`source_count`)
- 與 `/api/furniture/{furniture_id}/model` 等特定路徑並存;特定路徑先匹配(已以 FastAPI TestClient 實測:`…/model` 命中 model 端點、`…/model.gltf` 命中 glTF 端點回 410、`xxx.glb` 才落入本端點)

---

### 資源:舊 R3F 檢視器移植路由(main.py:2656 起,註解標明供 frontend3d 使用)

#### `GET /api/plans` - 列出內建 DXF

- **回應**: `{"plans": [...]}`(來源 `testdata/pic/temp/`)

#### `GET /api/plan` - 解析單一 DXF

- **參數**: `name`(必填)、`scale_m`(選填,>0 且 ≤500)、`thickness`(預設 0.18,≤2)、`height`(預設 2.7,≤10);單位公尺
- **回應**: DXF 解析結果(`wall_segments`/`wall_polys`/`windows`/`doors`/`bbox`/`stats` 等,公尺+公分混合契約,詳見 `backend/upgrade3d/dxf_parser.py`);404 / 422 `parse failed: ...`

#### `POST /api/upload` - 直接上傳 DXF 解析

- **請求體**: `multipart/form-data` 的 `file` + query `scale_m`/`thickness`/`height`(同上)
- **回應**: 同 `GET /api/plan`;解析失敗 422

---

### 資源:無專案平面圖分析(Floorplan,免建專案)

#### `POST /api/floorplan/analyze` - PNG/JPG 分析

- **請求體**: `multipart/form-data`:`file`(限 `.png`/`.jpg`/`.jpeg`,否則 415 `floorplan_image_required`)+ 選填 Form JSON 字串:`calibration_json`(手動兩點尺度)、`ocr_json`、`geometry_json`(人工確認幾何)、`observed_utilities_json`、`brief_json`;JSON 壞掉回 422 `invalid_{field}_json`
- **回應**: `{"analysis": {...含 observed_utilities、requirement_brief...}, "requirements": {...}, "geometry_engine": "manual"(有 geometry_json)| "cody", "ocr_provider": "provided_or_reference_semantics"}`(main.py:2738-2743;伺服器內 OCR provider 硬寫 `None`,不執行 PaddleOCR)

#### `POST /api/floorplan/confirm` - 套用使用者確認/修正

- **請求體**: `{"analysis": {...必填 dict...}, "corrections": {...}}`;缺 analysis 回 422 `analysis_required`
- **回應**: `{"schema_version": "1.0", "ready_for_design": true, "analysis", "requirements", "dxf_text", "floorplan"}`(confirmation.py:174-181;`floorplan` 為公分制契約,`coordinate_unit: "cm"`);確認閘門不通過時(尺度未確認、無牆、有待複核房間)以 422 帶 ValueError 訊息拒絕

---

## 6. 資料模型

### `Project`(project_store.py:145-155)

```json
{
  "project_id": "hex uuid4",
  "name": "string",
  "notes": "string",
  "current_step": "project | …(11 步之一)",
  "workflow": { "…前端流程草稿 JSON,上限 2MB…" },
  "revision": 0,
  "created_at": "2026-07-26T00:00:00+00:00",
  "updated_at": "2026-07-26T00:00:00+00:00"
}
```

### `Render`(project_store.py:322-335 + main.py:1652-1657 附加 `download_url`)

```json
{
  "render_id": "hex uuid4",
  "project_id": "…",
  "white_model_version": 0,
  "viewpoint_version": 0,
  "style_version": 0,
  "style_card_id": "unassigned",
  "provider": "browser_capture",
  "mime_type": "image/png",
  "filename": "roompilot-{project8}-{render8}.png",
  "byte_size": 123456,
  "created_at": "…",
  "download_url": "/api/projects/{project_id}/renders/{render_id}/png"
}
```

### `ClientBrief`(intake_service.py:55-56,schema_version 1.1)

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

### `FurnitureCard`(`GET /api/furniture` 的 `detail=card` 項目,main.py:791-811)

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
  "model_url": "https://ddgsm1yg3xikc.cloudfront.net/models/…/xxx.glb"
}
```

### 座標與單位約定(跨端點通用)

- 對外 API 契約一律**公分**(`coordinate_unit: "cm"`);場景物件 `position_cm` 為房間中心原點,`rotation_y_deg` 為 three.js Y 軸旋轉(scene_service.py `generate_layout` docstring)。
- 例外:舊 R3F 路由(`/api/plan`、`/api/upload`)的查詢參數與 `bbox`/`wall_polys` 用公尺,`wall_segments`/`door_segments`/`window_segments` 給公分(dxf_parser.py 輸出契約)。

---

## 待補與已知落差

- `POST /api/scene/decorate` 引用的 `/static/models/roompilot-curtain.glb` 實際不存在於 repo(已實測);前端 scene_viewer.js 對 GLB 載入失敗有兜底(同尺寸白色替代物,見第 5 節 decorate 條目),已實測程式碼路徑確認。
- 伺服器端無步驟順序/前置檢查,`PUT .../workflow` 可寫入任意合法步驟名;順序僅由前端 `scene_workflow.js` 強制。
- `@app.on_event("startup")` 為 FastAPI 已棄用 API;已實測:import `backend.server.main` 即發出「on_event is deprecated, use lifespan event handlers instead.」DeprecationWarning。是否遷移 lifespan 未裁決。
- `GET /api/furniture/{name}` 與 `/api/furniture/{furniture_id}/model` 等路徑的匹配優先序已以 FastAPI TestClient 實測:特定路徑先匹配,`{name}` 僅接住其餘(見第 5 節)。
- 全部端點無認證、無 CORS、無速率限制(見第 4 節);若要對外部署,此為最優先缺口。
