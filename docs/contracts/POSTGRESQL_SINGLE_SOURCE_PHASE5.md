# PostgreSQL Single Source Phase 5

更新日期：2026-07-27
主要 owner：Kai（catalog／SQL）
協作 owner：Bella（FastAPI／health）

## 目標

Phase 5 移除正式 runtime 的雙來源：PostgreSQL 是正式 source of truth，JSON／CSV 只能由匯入器讀取，不能在資料庫失效時靜默接手網站流量。

本階段同時解決 Python process cache：正式資料更新或重新匯入後，API 下一次請求直接讀到新資料，不需要重啟 Uvicorn，也不需要手動呼叫 `cache_clear()`。

## 正式資料流

```text
versioned JSON / CSV
    -> official furniture importer / runtime catalog importer
    -> PostgreSQL transaction + UPSERT
    -> current views
    -> Kai repository（每次 SQL read-through）
    -> Bella FastAPI
```

禁止流程：

```text
PostgreSQL error -> JSON/CSV fallback -> HTTP 200
```

正式 SQL 異常時，家具 API 回傳 `503 postgres_catalog_unavailable`；style／surface／cost 回傳 `503 runtime_catalog_unavailable`。`/api/catalog/status` 保留診斷 payload但不讀 manifest 檔案，`/api/health` 在正式資料庫未 ready 時回傳 HTTP 503。

## Provider 契約

正式與未設定 provider 的預設值都是 strict PostgreSQL：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=postgres
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=postgres
ROOMPILOT_PROJECT_STORE_PROVIDER=postgres
```

不再存在隱含 `auto -> JSON`。只有開發者明確指定以下設定，才會啟用離線檔案模式：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=json
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json
ROOMPILOT_PROJECT_STORE_PROVIDER=sqlite
```

離線模式是測試／展示工具，不是正式故障轉移策略。

## 哪些資料已拔除 runtime 檔案依賴

| FastAPI 用途 | 正式來源 |
|---|---|
| 家具 list/detail/filter/facet/model URL | `roompilot.furniture_catalog_api_current` |
| 首頁與 styles 家具統計 | SQL `COUNT`／style aggregation |
| 六種 UI style profile | `roompilot.design_style_profiles_current` |
| 18 張 style cards | `roompilot.style_cards_current` |
| 571 筆 surface materials | `roompilot.surface_materials_current` |
| 裝修費率與來源 | `roompilot.renovation_cost_*` |
| RAG style/material/cost | `roompilot.runtime_catalog_rag_documents` |
| external／legacy | `roompilot.external_import_quarantine`，不進 API/RAG |
| project／workflow | `roompilot.projects.workflow_json` JSONB |

問卷題目定義仍是單一版控 JSON／Python 靜態契約，並非 PostgreSQL 失效時的 catalog fallback；使用者答案已存 project JSONB。GLB／PNG 位元組仍在 S3／CloudFront，SQL 保存正式 URL 與狀態。

## 匯入入口

家具與資產：

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py
```

UI styles、cards、surface、cost 與 quarantine：

```powershell
.\.venv\Scripts\python.exe scripts/runtime_catalog/import_runtime_catalogs_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts/runtime_catalog/import_runtime_catalogs_to_postgres.py
```

FastAPI 不可自行解析這些輸入檔。匯入器會保存 source path、SHA-256、版本、筆數與 imported time，家具匯入另保存 staging `batch_key`。

## Health／status

```text
GET /api/catalog/status
GET /api/health
```

正式 ready 條件：

1. `roompilot.furniture_catalog_api_current` 存在且有正式家具。
2. GLB 與三視角 SQL asset counts 完整。
3. design style、style card、surface、cost 與 RAG views 可查。
4. `roompilot.projects` 存在，正式 project store provider 是 PostgreSQL。
5. status 全程不讀 GLB/image manifest CSV。

Status 會顯示但不洩漏帳密：

- PostgreSQL server version 與 database name。
- required table/view readiness。
- 家具 `data_revision`。
- 最新 staging `batch_key`、匯入時間、來源檔與筆數。
- Phase 4/5 各 catalog 的短 SHA-256、版本、筆數與匯入時間。
- `cache_policy=database_read_through_no_runtime_file_cache`。

## Hot refresh

正式下列函式不使用 process-lifetime catalog cache：

- `load_surface_catalog()`
- `_furniture_payload_cache()` 的 PostgreSQL 分支
- `_catalog_count_summary()` 的 PostgreSQL 分支
- `build_site_payload()`
- style cards、design styles 與 cost repository

離線 JSON 分支可以保留記憶體 cache，因為它是明確的單機開發模式。家具正式列表仍由 SQL `WHERE`、`COUNT`、`GROUP BY`、`LIMIT/OFFSET` 執行；compatibility loader 只供場景與舊消費端，不用於家具分頁。

## 驗證

一般離線契約：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_postgres_single_source_phase5.py
```

Live PostgreSQL 與 hot-refresh：

```powershell
$env:ROOMPILOT_TEST_POSTGRES_CATALOGS='1'
$env:ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS='1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_postgres_single_source_phase5.py tests/test_runtime_catalog_phase4.py
Remove-Item Env:ROOMPILOT_TEST_POSTGRES_CATALOGS
Remove-Item Env:ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS
```

Live hot-refresh test 會短暫更新一筆 style、surface 與 furniture，再於 `finally` 還原原值；驗證第二次讀取不重啟、不清 cache 即看到變更。

完整 gate：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status --short
```

## Rollback

資料錯誤時，以 Git 中上一版來源重新跑 importer；不要在正式環境把 provider 改成 JSON 來遮蔽問題。若只是本機離線展示，可停止正式 server 後明確切換三個 offline provider。PostgreSQL 資料不會因切換 provider 被刪除。
