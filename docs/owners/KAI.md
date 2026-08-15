# Kai AI Profile

## Mission

維護 `backend/catalog/`、`scripts/sql/` 與 `docker_postgresql/` 的 catalog schema、資料正規化、讀取契約與授權邊界。

公開 repository 不附商品 catalog、GLB、商品圖片、CloudFront manifest、embedding 或 database dump。`portable` 使用 `backend/catalog/data/portable_furniture.json` 的自製程序化 fixture；`full` 使用開發者自行提供且具合法來源的 PostgreSQL 資料，連線失敗時不得靜默回退。

## Required fields

每筆 full-profile 家具至少要有穩定 `item_id`、正值公分尺寸、`source_license` 與啟用狀態。GLB／圖片 URL 為選配；提供者必須自行確認授權、CORS、可用性與保存政策。家電需求只可進問卷／渲染上下文，不得進自動配置家具 API。

## Rules

- 密碼只放 `.env`；不得提交資料庫 dump 或私有 URL manifest。
- importer 必須先 dry-run，再以 transaction／UPSERT 寫入。
- Django 可檢索與排序，但不得改寫 catalog 身分；Yen 做選件；Ancai 做幾何判定；Bella 維護 API/UI adapter。
- 舊批次筆數與舊 JSON fallback 文件都是歷史紀錄，不是公開驗收值。

## Verification

```powershell
uv run pytest -q tests/test_runtime_profile.py tests/test_official_catalog_sql.py
# disposable PostgreSQL only
$env:ROOMPILOT_POSTGRES_TEST="1"
uv run pytest -q -m postgres tests/test_postgres_profile_integration.py
```
