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
  -> roompilot.furniture_catalog_api_current
  -> Bella /api/furniture 與第 6 步
```

正式 catalog 共 8,675 筆家具與 8,675 個 GLB，其中 8,076 筆為 active／RAG-indexable，透過 PostgreSQL API view 提供給正式 API／RAG；另有 599 筆 inactive 家具保留複核且不得進正式 API／RAG。SQL `styles` 只保存六個正式風格代碼，三視角圖片共 26,025 張。每筆 catalog 家具需提供 GLB 與 `front`、`side`、`angle-45` 圖片。JSON 來源只供 importer 與明確指定的離線開發模式，不得在正式 `postgres` 模式自動取代資料庫。

Phase 2 由 Kai 維護家具 SQL 寫入 transaction、taxonomy reference、啟用門檻與 `furniture_admin_audit`；Bella 的 FastAPI 只負責 Bearer 權限、request/response 驗證與路由接入。管理端只能軟刪除，不得用 CRUD 直接移除正式資料或讓家電進入公開家具 API。

Phase 3 的 project/workflow 行為由 Bella 擁有；Kai 只協助 PostgreSQL 邊界，不改寫 workflow、layout 或 scene 的領域內容。目前 repository 沒有 `scripts/project_store/` schema／migration，不能把歷史 Phase 3 migration 指令當成可執行 runbook。

Phase 4/5 的 design styles、style cards、surface、cost、quarantine 與 RAG view 也由 Kai PostgreSQL repository 供應。正式 provider 未設定時仍預設 strict PostgreSQL；JSON／CSV 不得由 FastAPI 直接掃描。目前 live PostgreSQL 與 read repository 可用，但 repository 沒有 `scripts/runtime_catalog/` schema／importer，因此新環境尚不能從本 repo 重建這批 runtime catalog。

家電問卷資料不屬於第 6 步正式家具 catalog；它只作第 8 步生圖的需求上下文。

家具向量資料依 `docs/contracts/POSTGRESQL_FURNITURE_EMBEDDINGS.md` 協作。Kai 維護來源 View、約束與 UPSERT 匯入器；目前正式批次是 8,076 筆 `BAAI/bge-m3`、1,024 維、cosine、L2-normalized 向量。SQL 欄位仍保留開放維度且尚未建立 HNSW；Django 負責文字、向量生成與檢索品質。

## 修改前

1. 核對來源筆數、唯一 `item_id`、CloudFront URL 與所有 manifest 一致。
2. 寫入資料庫前必須先執行 dry-run。
3. 密碼只放 `.env`，不可提交。
4. 保留 transaction、UPSERT 與明確 `--replace-existing` 行為；完整重建後重新匯入向量。

## 跨目錄規則

- Yen 可使用 RAG metadata，但不可重定義官方家具 ID。
- Django 可加入關係標註，但不可改變資產身分與交付 URL。
- Django 家具 RAG 可透過受控 SQL 函式檢索向量與 metadata；不得直接改寫正式家具或 embedding。
- Bella 維護 API 與 UI adapter；Kai 提供穩定資料契約。
- 大型 GLB、產品圖片原檔留在 Git 之外。

## 驗證

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe -m pytest -q tests/test_official_cloud_catalog.py tests/test_official_catalog_sql.py tests/test_image_manifest_contract.py
```
