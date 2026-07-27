# Kai AI 責任說明

## 任務

維護正式家具與材質資料交付、AWS/CloudFront manifest、catalog 正規化、quarantine 與 PostgreSQL 匯入。主要目錄是 `backend/catalog/`、`JSON/`、`scripts/sql/`。

## 資料流程

```text
官方 JSON + GLB/圖片 upload manifest
  -> ID、筆數、HTTPS URL 驗證
  -> 風格／材質／房間／RAG metadata
  -> 未匹配資料隔離
  -> PostgreSQL staging + UPSERT 正式表
  -> roompilot.furniture_catalog_current
  -> Bella /api/furniture 與第 6 步
```

正式 PostgreSQL view 目前有 9,349 筆啟用家具；每筆需提供 GLB 與 `front`、`side`、`angle-45` 圖片。JSON 9,350 筆是資料庫不可用時的驗證備援，不應取代正式資料庫。

家電問卷資料不屬於第 6 步正式家具 catalog；它只作第 8 步生圖的需求上下文。

## 修改前

1. 核對來源筆數、唯一 `item_id`、CloudFront URL 與所有 manifest 一致。
2. 寫入資料庫前必須先執行 dry-run。
3. 密碼只放 `.env`，不可提交。
4. 保留 transaction、UPSERT 與明確 `--prune-extra` 行為。

## 跨目錄規則

- Yen 可使用 RAG metadata，但不可重定義官方家具 ID。
- Django 可加入關係標註，但不可改變資產身分與交付 URL。
- Bella 維護 API 與 UI adapter；Kai 提供穩定資料契約。
- 大型 GLB、產品圖片原檔留在 Git 之外。

## 驗證

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe -m pytest -q tests/test_official_cloud_catalog.py tests/test_official_catalog_sql.py tests/test_image_manifest_contract.py
```
