# RoomPilot 設計師鎖定後工程文件 MVP 契約

更新日期：2026-07-29  
主要 owner：Bella（FastAPI／正式前端／文件整合）  
協作 owner：Kai（工程知識與正式價格來源）、Django（空間欄位）、Ancai（幾何合法性）

## 目的與固定流程

```text
現有 project workflow state
→ Browser ProjectSnapshot Adapter
→ 保存 draft revision
→ 設計師鎖定 revision
→ Quantity Service
→ Advanced RAG
→ Rule Service
→ Cost Service
→ Schedule Service
→ 單一 ReportPayload
→ HTML／XLSX／JSON
```

前端只呼叫同一 FastAPI；不得直連 LLM、Embedding、Vector Index、PostgreSQL 或
工程知識檔。文件生成不重寫平面圖、2D／3D、生圖、家具決策或幾何 Engine。

## 現有欄位到 ProjectSnapshot

| 現有 workflow 欄位 | ProjectSnapshot | 處理方式 |
|---|---|---|
| `project_id`, `name`, `revision` | `project_id`, `project_name`, `revision=D{n}`, `source_project_revision` | 保留 project optimistic revision，另建立不可覆寫設計 revision |
| `space_confirmation.rooms[].polygon_cm` | `rooms[].geometry.polygon_cm` | cm；由 polygon bounds 得到長、寬 |
| `space_confirmation.structures.doors/windows` | `opening_area_m2` | 只計明示寬、高且可歸屬房間的開口，不從影像補猜 |
| `confirmed_floorplan` 或 `white_model_3d.sceneData.floorplan` | `rooms[].layout_json` | 逐房篩選／建立 `room_regions`；仍是 layout_json |
| `requirements.roomRequirementModel.roomRequirements` | room type、surface fallback、空調需求 | 問卷只作需求與工程上下文 |
| `white_model_3d.sceneData.scene_objects` | `rooms[].furniture` | 家電類型排除；保留 cm 尺寸、座標、失敗原因與 catalog ID |
| `room_surface_assignments` | `rooms[].materials` | 地、牆、天花材料與耗損率 |
| `render_context.appliance_requirements` | `equipment_requirements` | 家電不進自動配置，只進 MEP 建議 |
| `proposal_review.jobs`／project render history | `rooms[].renders` | 逐房優先；單房才允許回退 project render history |

跨模組長度與座標固定為 cm，新欄位以 `_cm` 結尾；面積以 `_m2` 結尾。
Snapshot 使用 `schema_version=roompilot.project-snapshot.v1` 與
`coordinate_unit=cm`。

## Revision 與保存

- `PUT /api/v1/projects/{project_id}/revisions/{revision}/snapshot`：只保存 Draft。
- `GET /api/v1/projects/{project_id}/revisions/{revision}/snapshot`：讀回 Draft／鎖定版與完整性。
- `POST /api/v1/projects/{project_id}/revisions/{revision}/lock`：記錄
  `confirmed_by`／`confirmed_at`，並驗證來源 project revision 未改變。
- 已鎖定 revision 再 PUT：`409 LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`。
- Snapshot 保存後 project state 已改變再鎖定：
  `409 SNAPSHOT_SOURCE_REVISION_STALE`。
- 未鎖定就生成：`409 REVISION_NOT_LOCKED`。

正式 PostgreSQL 表為 `roompilot.engineering_snapshots/jobs/packages/documents`；
離線 SQLite 使用同一 ProjectStore provider 的 `projects.sqlite3`。產出的檔案 bytes 保存在
`.runtime/engineering/{project_id}/{revision}/{package_id}/`，不得提交 Git。

## Service 責任

### Quantity Service

只做 deterministic 幾何量：polygon 地坪、天花、周長、牆面毛面積、明示開口面積與
牆面淨面積。LLM 不得計算面積、工程量、價格或工期。

### Rule Service

家具邊界／重疊／門片／走道／窗戶優先委派既有 `scene_service` 與 Ancai Engine。
MVP 自有的門片／80 cm 走道規則必須標成 `mvp_advisory`。承重牆、迴路、線徑、
管徑、排水坡度、防水規格、空調容量與法規核准一律列待專業確認，不自動決定。

### Advanced RAG

- Structured Retrieval：材料→工項、設備→水電／空調需求與工法 evidence。
- Fusion／re-ranking 必須保留 `source_id`、`confidence`、`reason` 與 retrieval mode。
- 不使用 Graph RAG 或 Neo4j。
- `NoopEngineeringSemanticRetriever` 是 Mock／Noop，不是真正 Vector Retrieval；正式接入
  Vector Index 時只替換 Adapter，不改 ReportPayload 或前端契約。

### Cost 與 Schedule

估價只讀結構化 `PriceRecord`：

```text
subtotal = quantity × (1 + waste_rate)
         × (material_unit_price + labor_unit_price + other_unit_price)
```

排程只讀結構化 `ProductivityRecord` 與 `TaskDependency`，保留日產能、工班、準備日、
施工日、等待日與前置工作。Production 缺值時 subtotal／total 為 `null` 且狀態
`pending_quote`／待確認；不得補猜。`ROOMPILOT_DEMO_MODE=true` 才能使用
`DEMO_ONLY` 合成價格與工率，前端、HTML、XLSX、JSON 都必須顯示示範聲明。

## 生成與下載 API

```http
POST /api/v1/projects/{project_id}/engineering-packages
Content-Type: application/json

{"revision":"D3","documents":["report_json","report_html","estimate_xlsx"]}
```

回應 `202` JobStatus；輪詢 `GET /api/v1/jobs/{job_id}`，完成後以
`GET /api/v1/packages/{package_id}` 取得 ReportPayload。文件使用
`GET /api/v1/documents/{document_id}/download`；HTML iframe 預覽使用同端點加
`?preview=1`，只有 HTML 會改為 inline disposition。

## 對外文件

- `design_engineering_proposal.html`：專案／revision、逐房尺寸與面積、生圖、家具、
  材料、MEP／空調建議、風險、待確認、摘要、假設與排除。
- `estimate_and_schedule.xlsx`：只含「工程估價」「初步排程」兩張工作表；由
  `@oai/artifact-tool` 生成。
- `report_payload.json`：除錯與前端預覽，不列為對外正式文件。

三份檔案由同一 `ReportPayload` 寫出並共享 `snapshot_hash`。

Machine-readable 契約由現行 Pydantic／FastAPI 程式生成，不能手動只改其中一份：

- `project_snapshot.schema.json`
- `report_payload.schema.json`
- `risk_results.schema.json`
- `engineering_openapi.yaml`（內容為相容 YAML 1.2 的 JSON 表示）

```powershell
$env:ROOMPILOT_PROJECT_STORE_PROVIDER='sqlite'
.\.venv\Scripts\python.exe -m backend.server.engineering.export_contracts --output-dir docs\contracts
```

現有欄位、Adapter 與回滾分析見 `docs/PROJECT_INTEGRATION_REPORT.md`。

## 驗證

```powershell
$env:ROOMPILOT_PROJECT_STORE_PROVIDER='sqlite'
$env:ROOMPILOT_ARTIFACT_TOOL_MODULES='C:\path\to\node_modules'
.\.venv\Scripts\python.exe -m pytest -q tests\test_engineering_snapshot_api.py tests\test_engineering_quantity_rules.py tests\test_engineering_advanced_rag.py tests\test_engineering_cost_schedule.py tests\test_engineering_documents_api.py tests\test_engineering_frontend.py
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```
