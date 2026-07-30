# RoomPilot 家具與向量 PostgreSQL 匯入

本資料夾是目前 RoomPilot 的正式家具 PostgreSQL 匯入入口，處理 **8,675 筆 catalog 家具**與其中 **8,076 筆啟用／可建立 RAG 向量的家具**。舊版 9,349 筆家具與 37,396 筆資產數量已不適用。

原生 Windows 安裝與第一次匯入請直接依照 [PostgreSQL 17.10 安裝與資料匯入指南](./PostgreSQL%2017.10%20安裝與資料匯入指南.md)。本 README 與該指南就是目前保留的家具及向量 SQL 操作入口。

RAG metadata／文字、向量生成、檢索與品質由 Django 負責；Kai 在 RAG 流程只負責把 Django 交付的向量存入 PostgreSQL／pgvector。本資料夾的向量 schema 與 importer 只服務這個保存邊界。

## 目前資料夾內容

| 檔案 | 用途 |
|---|---|
| `roompilot_postgresql_schema.sql` | 家具、分類、風格、房間、VLM、資產、品質問題、staging 與 API views |
| `import_official_catalog_to_postgres.py` | 驗證官方 JSON 與四份 manifest，交易式 UPSERT 家具資料 |
| `roompilot_furniture_embeddings_schema.sql` | pgvector table、向量來源 view 與搜尋 functions |
| `import_furniture_embeddings_to_postgres.py` | 驗證文字、hash、模型、維度與向量後 UPSERT |
| `PostgreSQL 17.10 安裝與資料匯入指南.md` | Windows 安裝、第一次匯入與驗收方式 |
| `README.md` | 本流程的快速操作入口 |

目前 `scripts/sql/` 只保留家具 catalog 與家具向量匯入流程；舊版 Phase 3 project migration、Phase 4 runtime catalog 與排除項目 manifest 維護腳本已不在目前的 `scripts/` 工具樹中，請勿沿用舊路徑指令。

## 正式輸入與數量

| 資料 | 預設路徑 | 預期筆數 |
|---|---|---:|
| 官方家具、VLM 與 RAG metadata | `JSON/furniture/furniture_official_catagory.json` | 8,675 |
| GLB manifest | `JSON/manifests/glb_upload_manifest.csv` | 8,675 |
| GLB upload result | `JSON/manifests/glb_upload_all_result.csv` | 8,675 |
| 三視角圖片 manifest | `JSON/manifests/image_upload_manifest.csv` | 26,025 |
| 三視角圖片 upload result | `JSON/manifests/image_upload_all_result.csv` | 26,025 |
| BGE-M3 向量 | `JSON/RAG/furniture_embeddings_bge_m3.jsonl` | 8,076 |

目前狀態邊界：

- 8,076 筆 `is_active=true`，可進正式 API 與家具向量 RAG。
- 599 筆 `is_active=false` 且 `rag_indexable=false`，保留人工複核，但不進正式 API／RAG。
- 原先排除的 792 筆燈具中已恢復 118 筆完整落地燈；其餘 674 筆非落地燈照明仍不進正式 catalog。本流程不刪除既有雲端資產。
- 每件 catalog 家具必須對應 1 個 GLB，以及 `front`、`side`、`angle-45` 各 1 張圖片。
- VLM 敘述與 RAG metadata 是正式輸入，不應由匯入器自行改寫。

## 最快驗證方式

所有 PowerShell 指令都從 repo 根目錄執行：

```powershell
Set-Location 'D:\RoomPilot-Agent'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py `
  --catalog JSON\furniture\furniture_official_catagory.json `
  --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl `
  --require-all `
  --dry-run
```

預期輸出重點：

```text
家具：8,675
分類／風格／房間：56／6／9
GLB／三視角圖片：8,675／26,025
VLM 標註：8,675
品質問題：1,669
embedded_text／text_hash：8,076
實際向量：8,076
```

Dry-run 不連線 PostgreSQL，也不寫入資料庫。家具匯入器預設不留下驗證報告；只有真的需要 JSON 報告時才明確指定：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py `
  --dry-run `
  --validation-report D:\指定位置\postgres_import_validation.json
```

## PostgreSQL 設定

從 `.env.example` 建立本機 `.env`，並填入自己的 PostgreSQL 密碼：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_ADMIN_DB=postgres
DB_USER=postgres
DB_PASSWORD=請填入本機密碼
DB_SSLMODE=disable
DB_CONNECT_TIMEOUT=10
DB_APPLICATION_NAME=roompilot_catalog_import
```

`.env` 不可提交。第一次建立 schema 與向量 extension 的帳號需要足夠的 `CREATEDB`、schema 與 extension 權限。

## 正式家具匯入

第一次建立 `roompilot_db`：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --create-database
```

資料庫已存在時做一般 UPSERT：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py
```

需要完整重建家具 catalog 時：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --replace-existing
```

`--replace-existing` 只重建家具 tables、views 與 staging，不影響 project、render 或 runtime catalog；但它會移除 `furniture_embeddings`，所以執行後必須重新匯入向量。匯入與筆數核對都在同一個 transaction，失敗會 rollback。

常用選項：

- `--skip-schema`：schema 已由 migration 管理時不重跑 SQL；不可與 `--replace-existing` 同用。
- `--skip-staging`：不保存本批原始來源列，只更新正式表。
- `--allow-incomplete-uploads`：允許未完成 upload result；正式資料不建議使用。
- `--page-size 500`：調整批次寫入大小。
- `--catalog` 與四個 manifest/result 參數：覆寫預設輸入路徑。

## 正式向量匯入

家具資料必須先匯入，因為向量 item ID 外鍵指向 `roompilot.furniture_items`：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py `
  --catalog JSON\furniture\furniture_official_catagory.json `
  --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl `
  --require-all
```

目前正式契約為 `BAAI/bge-m3`、1024 維、cosine、L2 normalized。Importer 會拒絕非 active／非 RAG-indexable item、過期文字或 hash、錯誤維度、NaN／Infinity，以及不符合 normalization 契約的向量。

## 主要資料表與 views

正式資料位於 `roompilot` schema：

- `furniture_categories`、`furniture_items`
- `styles`、`furniture_styles`
- `rooms`、`furniture_rooms`
- `furniture_vlm_annotations`
- `furniture_assets`
- `furniture_quality_issues`
- `furniture_embeddings`
- `furniture_catalog_current`
- `furniture_catalog_api_current`
- `furniture_embedding_source_current`

五個 catalog／manifest 輸入另存於 `staging` schema。正式 API views 只提供 8,076 筆 active 家具；599 筆 inactive 家具仍留在 `furniture_items` 供複核。

## 最低驗證

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py `
  --catalog JSON\furniture\furniture_official_catagory.json `
  --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl `
  --require-all `
  --dry-run
.\.venv\Scripts\python.exe -m pytest -q tests\test_furniture_embeddings_sql.py tests\test_official_cloud_catalog.py tests\test_image_manifest_contract.py
git diff --check
git status --short
```

目前 `tests/test_official_catalog_sql.py` 仍匯入已不在工具樹中的 `scripts.catalog.remove_excluded_catalog_assets_from_manifests`，會在測試收集階段失敗；在腳本或測試責任重新對齊前，不把它列入可執行的最低驗證。

本流程不建立第二套家具主表，也不把 Chroma、JSON fallback 或 quarantine 資料當成正式家具來源。
