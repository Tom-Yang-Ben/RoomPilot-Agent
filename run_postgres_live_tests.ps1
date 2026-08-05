# RoomPilot-Agent —— 7 支 PostgreSQL live 測試（預設全 skip 的那批）
#
# 用途：讓 pytest 走你日常實跑的正式資料路徑（PostgreSQL），而不是 conftest.py
# 預設釘死的 sqlite/json 備援路徑。
#
# 在 repo 根目錄執行：
#     powershell -ExecutionPolicy Bypass -File .\run_postgres_live_tests.ps1
#
# 連線設定沿用 .env 的 DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD，
# 這個腳本不碰它們。
#
# 注意：ROOMPILOT_TEST_POSTGRES_CRUD 那支會真的對 /api/admin/furniture 建立、
# 修改、刪除一筆 `kai-phase2-smoke-*` 測試資料，並只清掉自己建的列。

$ErrorActionPreference = "Stop"

$env:ROOMPILOT_TEST_POSTGRES_MAIN             = "1"   # conftest：專案儲存改走 postgres
$env:ROOMPILOT_TEST_POSTGRES_CATALOGS         = "1"   # 型錄 provider 改走 postgres（解鎖 3 支）
$env:ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS = "1"   # runtime 型錄 provider（解鎖 1 支）
$env:ROOMPILOT_TEST_POSTGRES_CRUD             = "1"   # 解鎖 1 支
$env:ROOMPILOT_TEST_POSTGRES_PROJECTS         = "1"   # 解鎖 1 支
$env:ROOMPILOT_TEST_POSTGRES_LIGHTING         = "1"   # 解鎖 1 支

Write-Host "=== 只跑那 7 支 live 測試（約 1 分鐘）===" -ForegroundColor Cyan
python -m pytest -v `
    tests/test_postgres_catalog_crud.py::test_live_postgres_crud_transaction_and_cleanup `
    tests/test_postgres_project_store.py::test_live_postgres_project_jsonb_revision_render_and_cleanup `
    tests/test_runtime_catalog_phase4.py::test_live_phase4_postgres_counts_and_quarantine_boundary `
    tests/test_postgres_single_source_phase5.py::test_live_postgres_updates_are_visible_without_restart_or_cache_clear `
    tests/test_lighting_assets_catalog.py::test_live_lighting_view_only_exposes_verified_contract_fixtures `
    tests/test_catalog_vocabulary_contract.py::test_light_role_actually_returns_a_lamp_in_postgres_mode `
    tests/test_catalog_vocabulary_contract.py::test_snapshot_still_matches_the_live_catalog

Write-Host ""
Write-Host "=== 全套測試跑在 PostgreSQL provider 上（約 13 分鐘）===" -ForegroundColor Cyan
Write-Host "這一段才是真正的重點：證明的是正式資料路徑沒壞，不是 JSON 備援沒壞。" -ForegroundColor Yellow
python -m pytest -q
