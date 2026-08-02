# RoomPilot PostgreSQL 匯入工具

這個資料夾負責將 RoomPilot 家具／家電 catalog、GLB manifest 與 S3／CloudFront 上傳結果整合後，驗證並匯入 PostgreSQL。

第一次使用請先閱讀 [RoomPilot PostgreSQL 基礎安裝與開啟流程](./roompilot_postgresql_setup_guide.md)，內容包含 Windows 安裝、服務啟動、`.env`、首次匯入、日常開啟與故障排除。

## 目前資料基準

| 項目 | 數量 |
|---|---:|
| Catalog items | 10,550 |
| GLB manifest | 10,550 |
| GLB upload result | 10,550 |
| 原始 source type | 89 |
| 標準 type | 87 |
| 標準 role | 11 |
| 停用資料 | 1 |
| 尺寸待複查 | 7 |
| 空間配置可用資料 | 10,542 |

## 整合功能

`import_catalog_to_postgres.py` 提供以下功能：

1. 自動使用目前專案的 catalog、manifest 與 upload result 路徑。
2. 驗證三份資料的 ID 是否一對一，並檢查重複 ID。
3. 比對 object key、CloudFront URL、來源、catalog、kind 與上傳狀態。
4. 使用 JSON 的 `type_code`、`role_code`、`materials`、`colors` 與品質旗標。
5. 驗證頂層 `item_roles`、`item_types` 與實際 item 統計一致。
6. 自動更新驗證 JSON、type mapping CSV 與高優先級複查 CSV。
7. 首次建置時可先建立 `roompilot_db`，再建立或升級 schema。
8. 以 transaction 和 UPSERT 安全寫入 PostgreSQL，可重複執行。
9. 提供一般 API View 與空間配置專用 View。

## 資料流程

```text
JSON/furniture/all_furniture_appliance_catalog.json
JSON/manifests/glb_upload_manifest.csv
JSON/manifests/glb_upload_all_result.csv
JSON/manifests/glb_upload_manifest_report.json
                         │
                         ▼
scripts/sql/import_catalog_to_postgres.py
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       三份驗證／稽核報告       PostgreSQL UPSERT
                                    │
                    item_roles / item_types
                    catalog_items / glb_assets
                    import_batches / SQL Views
```

## 檔案說明

| 檔案 | 功能 |
|---|---|
| [`import_catalog_to_postgres.py`](./import_catalog_to_postgres.py) | 主程式：驗證、產生報告及匯入 PostgreSQL |
| [`roompilot_catalog_10550_schema.sql`](./roompilot_catalog_10550_schema.sql) | 建立資料表、索引、migration 與 View |
| [`postgres_import_validation.json`](./postgres_import_validation.json) | Catalog、manifest、upload result 的整合驗證結果 |
| [`roompilot_type_category_mapping.csv`](./roompilot_type_category_mapping.csv) | 89 個來源 type 到 87 個標準 type 的對照與例外 |
| [`roompilot_high_priority_data_review.csv`](./roompilot_high_priority_data_review.csv) | 高優先級資料品質人工複查清單 |
| [`roompilot_postgresql_setup_guide.md`](./roompilot_postgresql_setup_guide.md) | PostgreSQL 基礎安裝、啟動、連線、匯入與故障排除 |

三份報告是由匯入器依目前 catalog 自動產生，不應手動維護統計數字。

## 預設路徑

從專案根目錄 `<project-root>` 執行時，主程式預設使用：

| 用途 | 路徑 |
|---|---|
| Catalog | `JSON/furniture/all_furniture_appliance_catalog.json` |
| Manifest | `JSON/manifests/glb_upload_manifest.csv` |
| Upload result | `JSON/manifests/glb_upload_all_result.csv` |
| Manifest report | `JSON/manifests/glb_upload_manifest_report.json` |
| PostgreSQL `.env` | `.env` |
| Schema | `scripts/sql/roompilot_catalog_10550_schema.sql` |
| 驗證報告 | `scripts/sql/postgres_import_validation.json` |
| Type mapping | `scripts/sql/roompilot_type_category_mapping.csv` |
| 高優先級複查 | `scripts/sql/roompilot_high_priority_data_review.csv` |

所有輸入與輸出路徑都可以透過命令列參數覆寫。

## PostgreSQL 基礎安裝與開啟

完整圖文步驟請閱讀 [RoomPilot PostgreSQL 基礎安裝與開啟流程](./roompilot_postgresql_setup_guide.md)。最短流程如下。

### 第一次安裝

1. 從 [PostgreSQL 官方 Windows 下載頁](https://www.postgresql.org/download/windows/) 安裝 PostgreSQL Server、pgAdmin 4 與 Command Line Tools。
2. 安裝時自行設定 `postgres` 使用者密碼，Port 使用 `5432`。
3. 重新開啟 PowerShell，確認服務與連線：

```powershell
Get-Service -Name "postgresql*"
pg_isready -h localhost -p 5432
```

若服務為 `Stopped`，請以系統管理員 PowerShell 啟動實際顯示的服務名稱：

```powershell
Start-Service -Name "postgresql-x64-版本號"
```

### 建立專案 `.env`

在專案根目錄複製 `.env.example`：

```powershell
cd "<project-root>"
Copy-Item -LiteralPath ".env.example" -Destination ".env"
```

PostgreSQL 環境變數名稱固定如下；`DB_PASSWORD` 保持由每位使用者在自己的 `.env` 內填寫：

```dotenv
# 複製此檔案為專案根目錄的 .env，再填入實際密碼。
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_ADMIN_DB=postgres
DB_USER=postgres
DB_PASSWORD=
DB_SSLMODE=disable
DB_CONNECT_TIMEOUT=10
DB_APPLICATION_NAME=roompilot_catalog_import
```

`.env.example` 不保存真實密碼，`.env` 也不可提交 Git。

### 每天開啟

```powershell
Get-Service -Name "postgresql*"
pg_isready -h localhost -p 5432
cd "<project-root>"
.\.venv\Scripts\Activate.ps1
```

服務已是 `Running` 且 `pg_isready` 顯示 `accepting connections` 時，不需要重新啟動或重新匯入資料。

## 專案快速開始

### 1. 安裝套件

```powershell
cd "<project-root>"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r ".\scripts\requirements.txt"
```

### 2. Strict Dry Run

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --dry-run
```

Dry Run 會更新三份報告，但不連線 PostgreSQL、不建立資料表，也不寫入資料庫。

正常結果：

```text
catalog：10,550 筆
manifest：10,550 筆
upload result：10,550 筆
item types：87 種
警告：0 筆
```

### 3. 首次建立資料庫、Schema 並匯入

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --create-database --create-schema
```

`--create-database` 會先連線 `DB_ADMIN_DB=postgres`，若 `roompilot_db` 不存在便建立 UTF-8 資料庫。執行帳號必須具備 PostgreSQL `CREATEDB` 權限。

資料庫已存在後，日常更新只需：

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --create-schema
```

正式匯入前應先確認 Dry Run 為 0 warning；既有資料庫也應先備份。

## 自動產生的報告

### `postgres_import_validation.json`

包含：

- 三份輸入資料筆數。
- 準備寫入的 item／asset 筆數。
- 標準 type／role 數量。
- 上傳狀態及品質旗標統計。
- 多來源分類摘要。
- 實際輸入與輸出絕對路徑。

### `roompilot_type_category_mapping.csv`

目前有 90 列 mapping，涵蓋 89 個來源 type、87 個標準 type及 10,550 筆 item。

同一個來源 type 可能依商品內容對應不同標準 type，例如：

```text
lamp → lamp：276 筆
lamp → planter：2 筆
```

因此不能只用來源 type 對整批資料直接覆蓋分類。

### `roompilot_high_priority_data_review.csv`

目前有 1,768 筆，包含：

- 疑似品牌誤判材質。
- 疑似完全重複商品。
- 缺少尺寸。
- 長寬高全部小於 5 公分。
- 疑似 type 分類錯誤。
- 標準材質／顏色、尺寸複查狀態與啟用狀態。

## PostgreSQL 結構

### 資料表

| 資料表 | 用途 |
|---|---|
| `item_roles` | 11 個第一層功能分類 |
| `item_types` | 87 個標準葉節點 type |
| `catalog_items` | 家具／家電主資料、標準欄位及品質狀態 |
| `glb_assets` | GLB、S3、CloudFront 與上傳資訊 |
| `import_batches` | 每次匯入的檔案、筆數、警告與時間 |

### View

| View | 用途 |
|---|---|
| `catalog_items_with_glb` | 一般 API／後台查詢，整合商品、分類與 GLB |
| `catalog_items_for_space_planning` | 空間配置使用，排除停用與尺寸待複查資料 |

## 匯入後快速驗證

```sql
SELECT COUNT(*) FROM catalog_items;                  -- 10550
SELECT COUNT(*) FROM glb_assets;                     -- 10550
SELECT COUNT(*) FROM item_types;                     -- 87
SELECT COUNT(*) FROM item_roles;                     -- 11
SELECT COUNT(*) FROM catalog_items WHERE NOT is_active; -- 1
SELECT COUNT(*) FROM catalog_items_for_space_planning;  -- 10542
```

確認所有 GLB 已上傳：

```sql
SELECT upload_status, COUNT(*)
FROM glb_assets
GROUP BY upload_status;
```

確認品牌誤判的標準材質已清除：

```sql
SELECT COUNT(*)
FROM catalog_items
WHERE 'suspected_brand_to_material_error' = ANY(data_quality_flags)
  AND '石材' = ANY(materials);
```

預期結果是 0。

## 常用參數

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --help
```

| 參數 | 功能 |
|---|---|
| `--dry-run` | 只驗證與產生報告，不連線 PostgreSQL |
| `--strict` | URL、上傳狀態或資料關聯不一致時停止 |
| `--create-database` | DB_NAME 不存在時，連線 DB_ADMIN_DB 建立 UTF-8 資料庫 |
| `--create-schema` | 匯入前執行 schema／migration |
| `--catalog` | 覆寫 catalog JSON 路徑 |
| `--manifest` | 覆寫 manifest CSV 路徑 |
| `--upload-result` | 覆寫 upload result CSV 路徑 |
| `--manifest-report` | 覆寫 manifest report JSON 路徑 |
| `--env` | 覆寫 `.env` 路徑 |
| `--schema-sql` | 覆寫 schema SQL 路徑 |
| `--quality-report` | 覆寫驗證 JSON 輸出路徑 |
| `--type-mapping-report` | 覆寫 type mapping CSV 輸出路徑 |
| `--review-report` | 覆寫高優先級 CSV 輸出路徑 |
| `--page-size` | 每批 UPSERT 筆數，預設 500 |

## 安全原則

- 每次正式匯入前先執行 `--strict --dry-run`。
- 不要透過移除 `--strict` 掩蓋資料錯誤。
- 不要手動把未知尺寸改成 0；未知值應保持 `NULL`。
- 不要直接刪除疑似重複商品，應先確認 GLB、來源與貼圖差異。
- 不要只修改 PostgreSQL 而不修正來源 catalog，否則下次 UPSERT 會覆蓋資料庫。
- 匯入器不會自動刪除資料庫中已存在、但新 catalog 不再包含的舊 item。

