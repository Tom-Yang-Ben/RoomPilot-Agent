# Kai AI 責任與交接說明

文件版本：2026-08-06。Kai 擁有正式 catalog、資產 manifest、PostgreSQL 資料交付、RAG metadata 與可追溯價格來源。

## AI 快速結論

家具 ID、尺寸、GLB／圖片 URL、啟用狀態、材質與價格來源只能以 Kai 正式資料為準。沒有價格來源的家具或裝潢工程只能標記「待報價」，任何 Agent、前端或成果包都不得猜金額。

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

2026-08-06 live runtime 由 `roompilot.furniture_catalog_current` 對外提供 7,958 筆家具；`/api/catalog/status` 驗證 7,958 個 GLB 與 23,874 張 `front`、`side`、`angle-45` 三視圖，`/api/rag/status` 驗證 7,958 筆 current BGE-M3 向量。`backend/server/postgres_catalog.py` 與 `backend/catalog/postgres_repository.py` 都讀這個 view；`furniture_catalog_api_current` 可能仍存在於歷史 schema，但不是目前 Python runtime 的讀取來源。舊文件中的 8,675／8,076／599 是歷史匯入批次，不得拿來宣稱目前 API／RAG ready。JSON 來源只供 importer 與明確指定的離線開發模式，不得在正式 `postgres` 模式自動取代資料庫。

Phase 2 由 Kai 維護家具 SQL 寫入 transaction、taxonomy reference、啟用門檻與 `furniture_admin_audit`；Bella 的 FastAPI 只負責 Bearer 權限、request/response 驗證與路由接入。管理端只能軟刪除，不得用 CRUD 直接移除正式資料或讓家電進入公開家具 API。

Phase 3 的 project/workflow 行為由 Bella 擁有；Kai 只協助 PostgreSQL 邊界，不改寫 workflow、layout 或 scene 的領域內容。目前 repository 沒有 `scripts/project_store/` schema／migration，不能把歷史 Phase 3 migration 指令當成可執行 runbook。

Phase 4/5 的 design styles、style cards、surface、cost、quarantine 與 RAG view 也由 Kai PostgreSQL repository 供應。正式 provider 未設定時仍預設 strict PostgreSQL；JSON／CSV 不得由 FastAPI 直接掃描。目前 live PostgreSQL 與 read repository 可用，但 repository 沒有 `scripts/runtime_catalog/` schema／importer，因此新環境尚不能從本 repo 重建這批 runtime catalog。

家電問卷資料不屬於第 6 步正式家具 catalog；它只作第 8 步生圖的需求上下文。

## 八步流程中的位置

- 第 5 步：提供可選家具、材質、風格與價格證據，不決定使用者需求。
- 第 6 步：以 active／可交付 catalog 供搜尋、替換與 3D 模型載入；替換清單優先顯示 `image_url`／`thumbnail_url` 型錄照片，位置由 Ancai 驗證。
- 第 7 步：提供色卡、材質與家具外觀證據；Yen 視角不得改 catalog 身分。
- 第 8 步：把已選家具的 `price_twd`、`price_source` 與交付狀態帶入成果包；未知價格一律待報價。

目標契約要求 `POST /api/projects/{project_id}/design-delivery` 只有在家具同時具有可信價格與 `price_source` 時才列參考小計。現行 builder 只檢查正數價格，尚未強制來源欄位；這是待修正的 consumer 驗證，不代表 Kai 可提供無來源價格。裝潢工程、未知家具與需現場丈量項目不估假總價；正式報價仍需丈量、材料確認與廠商報價。

家具向量資料依 `docs/contracts/POSTGRESQL_FURNITURE_EMBEDDINGS.md` 協作。Kai 維護來源 View、約束與 UPSERT 匯入器；目前 live current 是 7,958 筆 `BAAI/bge-m3`、1,024 維、cosine、L2-normalized 向量。SQL 欄位仍保留開放維度且尚未建立 HNSW；Django 負責文字、向量生成與檢索品質。

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

## 禁止事項

- 不讓 inactive、quarantine 或未匹配資料進正式 API、RAG、場景或成果包。
- 不由 UI 或 LLM 改寫官方 `item_id`、尺寸、價格與 CloudFront URL。
- 不把 JSON fallback 說成正式 PostgreSQL 已成功連線。
- 不提交 AWS 金鑰、資料庫密碼、Bearer token 或真實使用者資料。

## 最低驗證

```powershell
.\.venv\Scripts\python.exe scripts/sql/import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe -m pytest -q tests/test_official_cloud_catalog.py tests/test_official_catalog_sql.py tests/test_image_manifest_contract.py
```
