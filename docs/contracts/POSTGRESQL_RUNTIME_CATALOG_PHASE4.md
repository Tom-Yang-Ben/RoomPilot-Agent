# PostgreSQL Runtime Catalog Phase 4

更新日期：2026-07-31

本文件是 Kai 資料層與 Bella FastAPI 之間的 Phase 4 正式契約。目標是讓正式 runtime 不再逐次掃描 style、surface、cost 與 external quarantine 的 JSON／CSV，同時保留可審查、可重建的版控來源。

## 現行可用性（2026-07-31）

- Live PostgreSQL 的 style／surface／cost／quarantine tables 與 current views 仍符合下列筆數，`backend/catalog/runtime_catalog_repository.py` 可讀取。
- `scripts/runtime_catalog/` 已不在目前 repository，schema 與 importer 指令不可執行。
- 現況是「既有資料庫可讀，但新環境無法從本 repo 從零重建」；恢復 schema、dry-run、transactional importer 與測試前，不得宣稱完整可部署。

## 最終決策

| 資料 | 版控／匯入來源 | 正式 runtime | RAG |
|---|---|---|---|
| 問卷題目與視覺選項 | JSON／Python 靜態定義 | 維持靜態載入 | 可作提示上下文，不需要為了速度硬搬 SQL |
| 使用者問卷答案 | 專案 `workflow_json` | PostgreSQL `roompilot.projects.workflow_json` JSONB | 依專案權限取用 |
| 18 張風格色卡 | `taiwan_style_cards.json` | `roompilot.style_cards_current` | 是 |
| 571 筆牆面／地板材質 | `surface_catalog.json` | `roompilot.surface_materials_current` | 是 |
| 6 筆裝修單價 | `taiwan_renovation_price_seed.json` | `roompilot.renovation_cost_catalog_current` | 是，必須保留來源 IDs |
| 外部匯入、未匹配與 legacy | 原始隔離 JSON | `roompilot.external_import_quarantine` | 否；未核准前也不得進正式 API |

JSON 並沒有被禁止。它很適合版控、人工 review、seed 與離線開發；PostgreSQL 負責正式多人 runtime 的查詢、篩選、關聯、一致性與 RAG 文件供應。

## 目前正式筆數

```text
style cards                 18
design style profiles        6
surface materials          571
renovation cost rates        6
cost sources                 4
external import quarantine 7495
unmatched cloud quarantine 1514
sf3d legacy quarantine     1509
quarantine total          10518
RAG documents              595
```

`sf3d_legacy` 有 1 個重複 `furniture_id`。匯入器不丟資料，第二筆使用穩定的 `#2` 隔離鍵保存。

## Schema 與 view

Phase 4 schema 的歷史預期路徑是 `scripts/runtime_catalog/roompilot_runtime_catalog_schema.sql`，但目前檔案不存在。Live DB 仍包含：

- `roompilot.runtime_catalog_imports`：來源路徑、SHA-256、版本、metadata 與筆數。
- `roompilot.style_cards`：逐張色卡、palette、前端 payload 與 RAG text。
- `roompilot.design_style_profiles`：正式 UI 使用的六種風格說明與視覺 metadata。
- `roompilot.surface_materials`：材質、用途、適用風格、texture/preview URL 與原始 payload。
- `roompilot.style_surface_profiles`：各風格牆面／地板候選關係。
- `roompilot.renovation_cost_sources`：公開行情來源與取用日期。
- `roompilot.renovation_cost_rates`：low/base/high、單位、來源 IDs 與排除項目。
- `roompilot.external_import_quarantine`：外部、未匹配與 legacy 原始資料及審查狀態。
- `roompilot.runtime_catalog_rag_documents`：統一 RAG 證據 view。

RAG view 只有 `style_card`、`surface_material`、`renovation_cost` 三類文件。quarantine 不在 view 內，也不負責家具幾何、碰撞、淨空或合法位置。

`backend.catalog.runtime_catalog_repository.search_runtime_rag_documents()` 提供關鍵字／trigram 查詢與 document type 篩選；cost 文件 metadata 會一起帶回完整來源 URL。若隔離項目通過審查，必須先移植到對應正式表，不能直接把 quarantine 列標記成可供 API 或 RAG 使用。

## Provider 規則

正式 `.env`：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=postgres
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=postgres
```

`postgres` 是 strict mode。SQL 不可用或尚未匯入時，FastAPI 回傳 `503 runtime_catalog_unavailable`，不得悄悄掃 JSON。只有明確離線開發才使用：

```dotenv
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json
```

`.env` 不可提交。`ROOMPILOT_CATALOG_ADMIN_TOKEN=0` 只適合 Kai 目前本機測試；共享環境或部署前必須換成長隨機值。

## 重建流程（目前缺失）

預期入口 `scripts/runtime_catalog/import_runtime_catalogs_to_postgres.py` 目前不存在。恢復後仍必須具備 dry-run，並在單一 PostgreSQL transaction 內執行 schema、UPSERT、隔離保存與 view 筆數核對；來源中消失的正式資料標為 inactive，隔離資料標為非 current，不可直接刪除。

## 驗證

`tests/test_runtime_catalog_phase4.py` 目前因缺少 `scripts.runtime_catalog` 在 collection 階段失敗；恢復 importer/schema 後，該測試才重新成為必要門檻。

要跑 live PostgreSQL contract：

```powershell
$env:ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS='1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_runtime_catalog_phase4.py
Remove-Item Env:ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS
```

API smoke test至少包含：

- `GET /api/catalog/status`：`runtime_catalogs.provider == "kai_postgresql"`。
- `GET /api/styles`：6 個風格群組、18 張卡、571 筆材質。
- `GET /api/scene/bootstrap`：同一份 SQL style/surface payload。
- `POST /api/cost/estimate`：使用 SQL rate 與 source payload。
- quarantine 中 `eligible_for_api OR eligible_for_rag` 必須為 0。

## 更新與 rollback

在重建工具恢復以前，不可更新 Phase 4 正式資料。恢復後的流程仍必須是：修改版控 seed、review diff、dry-run、transactional import、live contract 與完整測試；FastAPI 不得直接讀新檔案繞過 SQL。

若新版資料有問題，優先把來源修回上一個 Git 版本後重跑匯入器。緊急離線開發可暫時設 `ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json`；這是明確 fallback，不是正式部署方案，也不會刪除 PostgreSQL 現有資料。

## Owner 邊界

- Kai：schema、import、repository、資料品質、quarantine 與 RAG metadata。
- Bella：FastAPI endpoint 與前端 payload 消費，不重做 Kai 的 catalog 邏輯。
- Yen：使用 `runtime_catalog_rag_documents` 的關係與證據，不用 RAG 決定幾何合法性。
- Ancai：家具位置、碰撞與淨空仍只由 `backend/engine/` 判定。
