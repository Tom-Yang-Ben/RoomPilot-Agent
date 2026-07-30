# RoomPilot PostgreSQL 匯入

本資料夾目前版本專門匯入 **8,557 筆 Kai 官方家具 catalog**。本機 API 預設也讀取同一份 JSON；完成 PostgreSQL 匯入後，才以環境變數明確切換資料來源。

安裝方式請依團隊環境選擇：

- 原生 Windows PostgreSQL：[PostgreSQL 17.10 安裝與資料匯入指南](./PostgreSQL%2017.10%20安裝與資料匯入指南.md)。每位組員依 pgvector 官方 Windows 方式直接編譯安裝 v0.8.2。
- Docker（團隊環境一致性較高）：[Docker PostgreSQL 17.10 與資料匯入流程](./Docker%20PostgreSQL%2017.10%20與資料匯入流程.md)。組員不需要另外安裝 PostgreSQL、Visual Studio 或 pgvector。

## 新版輸入資料

| 資料 | 預設路徑 | 預期筆數 |
|---|---|---:|
| 官方家具與 VLM 結果 | `JSON/furniture/furniture_official_catagory.json` | 9,350 |
| GLB manifest | `JSON/manifests/glb_upload_manifest.csv` | 9,350 |
| GLB upload result | `JSON/manifests/glb_upload_all_result.csv` | 9,350 |
| 圖片 manifest | `JSON/manifests/image_upload_manifest.csv` | 28,050 |
| 圖片 upload result | `JSON/manifests/image_upload_all_result.csv` | 28,050 |

五個來源的 `item_id` 必須完整一致。每件家具必須有 1 個 GLB，以及 `front`、`side`、`angle-45` 各 1 張圖片。

## 資料表

正式資料位於 `roompilot` schema：

1. `furniture_categories`
2. `furniture_items`
3. `styles`
4. `furniture_styles`
5. `rooms`
6. `furniture_rooms`
7. `furniture_vlm_annotations`
8. `furniture_assets`
9. `furniture_embeddings`（只有 PostgreSQL 已安裝並可啟用 pgvector 時建立）
10. `furniture_quality_issues`

原始來源列會另存到 `staging.stg_furniture_catalog`、`stg_glb_manifest`、`stg_glb_upload_result`、`stg_image_manifest`、`stg_image_upload_result`。五個輸入檔的 SHA-256 會產生同一個 `batch_key` 識別 staging 批次；正式表則依 `item_id` 與各資料表的業務唯一鍵安全 UPSERT。

`roompilot.furniture_catalog_current` 是 API 常用 view，會彙整目前 VLM 標註、主次風格、房間、GLB URL 與三視角圖片 URL。

## 先執行 Dry Run

Dry Run 只讀取檔案，不連線資料庫：

```powershell
python scripts/sql/import_official_catalog_to_postgres.py --dry-run
```

成功時應看到：

```text
家具：9,350
分類／風格／房間：64／12／9
GLB／三視角圖片：9,350／28,050
VLM 標註：9,350
品質問題：2,102
```

詳細欄位、檔案 SHA-256、來源列數與品質問題統計會寫到 `scripts/sql/postgres_import_validation.json`。

## PostgreSQL 準備

基本家具匯入需要 PostgreSQL 與 `pg_trgm`；只有建立 `furniture_embeddings` 時才需要 [pgvector](https://github.com/pgvector/pgvector)。安裝專案依賴（包含 `psycopg2-binary`）：

```powershell
python -m pip install -r requirements.txt
```

正式執行 schema 前可先在 `roompilot_db` 查詢 pgvector 是否可用及是否已啟用：

```sql
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name = 'vector';

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

查得到 `vector` 時，主 schema 會啟用 extension 並建立 `furniture_embeddings` 與索引；查不到時會顯示 `NOTICE` 並跳過這三部分，其餘家具 catalog 表與 9,350 筆匯入不受影響。

在專案根目錄 `.env` 設定：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_ADMIN_DB=postgres
DB_USER=postgres
DB_PASSWORD=安裝PostgreSQL17時設定的密碼
DB_SSLMODE=disable
DB_CONNECT_TIMEOUT=10
DB_APPLICATION_NAME=roompilot_catalog_import
```

## 正式匯入

確認專案根目錄的 `.env` 已填入正確的 PostgreSQL 密碼。第一次正式匯入請直接在 PowerShell 執行：

```powershell
Set-Location 'D:\RoomPilot-Agent'
python .\scripts\sql\import_official_catalog_to_postgres.py --create-database
```

`--create-database` 會在 `roompilot_db` 不存在時，先透過 `DB_ADMIN_DB=postgres` 建立資料庫。程式接著會在同一個 transaction 內執行 schema、寫入 staging、UPSERT 正式表並核對筆數。

之後需要重新匯入或更新資料，而且 `roompilot_db` 已經存在時，執行：

```powershell
Set-Location 'D:\RoomPilot-Agent'
python .\scripts\sql\import_official_catalog_to_postgres.py
```

常用選項：

- `--skip-schema`：資料表已由 migration 管理時，不執行 schema SQL。
- `--skip-staging`：不保存本批原始來源列，只 UPSERT 正式表。
- `--allow-incomplete-uploads`：允許 upload result 不是全數 `uploaded` / `ready`；正式資料不建議使用。
- `--page-size 500`：調整 PostgreSQL 批次寫入大小。
- 各輸入檔也都能用 `--catalog`、`--glb-manifest`、`--glb-upload-result`、`--image-manifest`、`--image-upload-result` 個別覆寫。

## 匯入規則

- `item_id` 是所有資料表共用的家具識別碼。
- 分類由 `canonical_category_zh` 建立，穩定的 `category_code` 取該分類最常見的來源 `type`。
- 主風格為 `style_rank = 1`，次風格為 `style_rank = 2`。來源中有 79 筆兩個 rank 相同，因此主鍵是 `(item_id, style_rank)`。
- VLM 欄位使用內容 hash 保存版本，每件家具只允許一筆 `is_current = TRUE`。
- GLB 與圖片以 `(item_id, asset_type, view_role)` 保證一個資產槽只有一筆正式紀錄；原始 manifest/result 完整保留在 JSONB。
- catalog 內的分類衝突、重複群組、尺寸待複查、缺主色與缺 `object_type_zh` 會寫入 `furniture_quality_issues`。
- 若 pgvector 可用，`furniture_embeddings` 先允許不同向量維度；選定正式 embedding 模型與固定維度後，再建立對應的 HNSW index。
