# RoomPilot PostgreSQL 17.10 安裝與資料匯入指南

本指南供 Windows 10／11 64-bit 的 RoomPilot 組員使用。指定環境為 **PostgreSQL 17.10 x86-64**、**pgvector v0.8.2**、Python 3.12，資料庫名稱為 `roompilot_db`。

目前匯入內容是 8,675 筆官方家具、8,675 個 GLB、26,025 張三視角圖片紀錄，以及 8,076 筆 active／RAG-indexable 家具的 BGE-M3 向量。舊文件中的 9,349 筆家具、28,047 張圖片與 37,396 筆資產已不適用。

RAG metadata／文字、向量生成、檢索與品質由 Django 負責；Kai 在 RAG 流程只負責把 Django 交付的向量存入 PostgreSQL／pgvector。本指南只涵蓋這個保存步驟與家具 catalog 的 SQL 匯入。

所有 PowerShell 指令都從專案根目錄執行。以下使用 `D:\RoomPilot-Agent`；repo 若位於其他位置，請換成實際路徑。

## 版本與官方來源

| 元件 | 指定版本 | 官方來源 |
|---|---:|---|
| PostgreSQL | 17.10 x86-64 | [PostgreSQL Windows installer](https://www.postgresql.org/download/windows/) |
| pgvector | v0.8.2 | [pgvector Windows installation](https://github.com/pgvector/pgvector/blob/v0.8.2/README.md#installation) |
| Visual Studio C++ Build Tools | MSVC v143 x64/x86 | [Microsoft C++ 安裝說明](https://learn.microsoft.com/zh-tw/cpp/build/vscpp-step-0-installation) |
| Python | 3.12 | 專案根目錄 `README.md` |

RoomPilot 的完整向量流程需要 PostgreSQL 能啟用 `vector` extension。`pg_trgm` 隨 PostgreSQL 提供；pgvector 必須另外安裝。

## 安裝流程總表

| 階段 | 操作 | 完成標準 |
|---:|---|---|
| 1 | 準備 Git、Python 3.12、Visual Studio C++ Build Tools | `git`、Python、`cl`、`nmake` 可執行 |
| 2 | 安裝 PostgreSQL 17.10 x86-64 | `psql (PostgreSQL) 17.10` |
| 3 | 確認 PostgreSQL Windows Service | PostgreSQL 17 service 為 `Running` |
| 4 | 編譯並安裝 pgvector v0.8.2 | `vector` 0.8.2 可用 |
| 5 | 建立 venv、依賴與本機 `.env` | `psycopg2` 可匯入，連線設定完成 |
| 6 | 驗證六個正式輸入 | catalog、四份 manifest/result、向量檔皆存在 |
| 7 | 執行兩個 dry-run | 8,675 catalog 與 8,076 向量通過 |
| 8 | 建立資料庫並匯入家具 | transaction 與筆數核對成功 |
| 9 | 匯入 BGE-M3 向量 | 8,076 筆向量通過 |
| 10 | SQL 驗收 | active／inactive、views、資產與向量數量吻合 |

## 1. 安裝前準備

請先安裝 Git for Windows、Python 3.12，以及 Visual Studio 2022 Build Tools 或相容的 Visual Studio C++ build environment。

在 PowerShell 確認 Git 與 Python：

```powershell
git --version
py -3.12 --version
```

### Visual Studio Installer 必要元件

pgvector 是 PostgreSQL 的原生 C extension，只安裝 Visual Studio 核心編輯器不夠。請在 Visual Studio Installer 勾選「使用 C++ 的桌面開發」，並確認包含：

- C++ 核心桌面功能。
- MSVC v143 x64/x86 建置工具。
- 一個受支援的 Windows 10／11 SDK。
- MSBuild 與 NMAKE。

完成後，以系統管理員身分開啟 **x64 Native Tools Command Prompt for VS 2022** 或相容版本，執行：

```bat
where cl
where nmake
cl
nmake /?
```

`cl.exe` 應來自 x64 工具目錄，通常包含 `Hostx64\x64`。若本機已有其他 PostgreSQL，先備份既有資料並確認 port；不要刪除既有 data directory。

## 2. 安裝 PostgreSQL 17.10

1. 從 PostgreSQL 官方 Windows installer 下載 **PostgreSQL 17.10 / Windows x86-64**。
2. 以系統管理員身分執行安裝器，預設路徑可用 `C:\Program Files\PostgreSQL\17`。
3. 至少安裝 PostgreSQL Server、pgAdmin 4 與 Command Line Tools。
4. 設定 `postgres` 管理員密碼，存入核准的密碼管理工具；不要寫進 Git。
5. Port 預設為 `5432`。若改用其他 port，後續 `.env` 必須一致。
6. 完成安裝後確認版本與 service。

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' --version
Get-Service | Where-Object { $_.Name -like 'postgres*' }
```

版本應顯示：

```text
psql (PostgreSQL) 17.10
```

若 service 尚未啟動，請在系統管理員 PowerShell 使用實際 service 名稱啟動，例如：

```powershell
Start-Service -Name 'postgresql-x64-17'
```

## 3. 安裝 pgvector v0.8.2

以下是 **x64 Native Tools Command Prompt／BAT** 語法，不要直接貼進一般 PowerShell：

```bat
set "PGROOT=C:\Program Files\PostgreSQL\17"
cd /d %TEMP%
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
nmake /F Makefile.win
nmake /F Makefile.win install
```

`nmake install` 會寫入 `C:\Program Files\PostgreSQL\17`，因此視窗必須以系統管理員身分開啟。若已 clone 過 pgvector，可進入既有目錄後先執行 `nmake /F Makefile.win clean` 再重編。

回到 PowerShell 驗證：

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' `
  -U postgres `
  -d postgres `
  -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';"
```

結果必須能找到 `vector`，指定版本應為 `0.8.2`。

## 4. 建立 Python 環境

```powershell
Set-Location 'D:\RoomPilot-Agent'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import psycopg2; print(psycopg2.__version__)"
```

也可依根目錄 `README.md` 使用 `uv sync --extra catalog --extra server --group dev` 建立環境。

## 5. 建立本機 `.env`

只有 `.env` 不存在時才從範例複製，避免覆蓋自己的設定：

```powershell
Set-Location 'D:\RoomPilot-Agent'
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
notepad .env
```

確認包含：

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_ADMIN_DB=postgres
DB_USER=postgres
DB_PASSWORD=請填入安裝時設定的密碼
DB_SSLMODE=disable
DB_CONNECT_TIMEOUT=10
DB_APPLICATION_NAME=roompilot_catalog_import
```

`.env` 是本機秘密檔，不得 commit、貼到 issue 或傳到群組。第一次建立資料庫與 extension 建議使用安裝時建立的 `postgres` 管理員帳號。

## 6. 檢查正式輸入

```powershell
Set-Location 'D:\RoomPilot-Agent'
$roompilotImportFiles = @(
  'JSON\furniture\furniture_official_catagory.json',
  'JSON\manifests\glb_upload_manifest.csv',
  'JSON\manifests\glb_upload_all_result.csv',
  'JSON\manifests\image_upload_manifest.csv',
  'JSON\manifests\image_upload_all_result.csv',
  'JSON\RAG\furniture_embeddings_bge_m3.jsonl'
)
$roompilotImportFiles | ForEach-Object {
  if (-not (Test-Path -LiteralPath $_)) { throw "缺少匯入檔：$_" }
  Get-Item -LiteralPath $_ | Select-Object FullName, Length
}
```

只要有一個檔案缺少就停止正式匯入。Catalog、GLB manifest 與 GLB result 必須有完全相同的 8,675 個 item ID；圖片兩檔必須各有 26,025 列，代表每件家具三個視角。

## 7. 先執行 dry-run

Dry-run 只讀取並驗證資料，不連線 PostgreSQL，也不寫入資料庫：

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

預期結果：

```text
家具：8,675
分類／風格／房間：56／6／9
GLB／三視角圖片：8,675／26,025
VLM 標註：8,675
品質問題：1,669
embedded_text／text_hash：8,076
catalog target：BAAI/bge-m3／1024 維／cosine／normalized=True
實際向量：8,076
```

家具匯入器預設只在終端顯示結果，不留下 `postgres_import_validation.json`。如需一次性報告，才加上：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py `
  --dry-run `
  --validation-report D:\指定位置\postgres_import_validation.json
```

## 8. 建立資料庫並匯入家具

第一次匯入使用 `--create-database`：

```powershell
Set-Location 'D:\RoomPilot-Agent'
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --create-database
```

程式會先連線 `DB_ADMIN_DB=postgres`，在需要時建立 UTF-8 的 `roompilot_db`，再於 transaction 內執行 schema、staging、UPSERT 與匯入後筆數核對。

資料庫已存在時，日後重跑一般 UPSERT：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py
```

若需清掉舊家具表並完整重建：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --replace-existing
```

`--replace-existing` 不影響 project、render 或 runtime catalog，但會移除既有 `furniture_embeddings`；完成後務必執行下一節的向量匯入。不要手動刪除 PostgreSQL data directory。

## 9. 匯入 BGE-M3 家具向量

家具匯入成功後執行：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py `
  --catalog JSON\furniture\furniture_official_catagory.json `
  --embeddings JSON\RAG\furniture_embeddings_bge_m3.jsonl `
  --require-all
```

`--require-all` 要求 8,076 筆 active／RAG-indexable 家具都有目前文字 hash 對應的向量。599 筆 inactive 家具不會進向量來源 view，也不應存在正式向量表。

## 10. 驗證 PostgreSQL

先確認 server 與 extensions：

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' `
  -U postgres `
  -d roompilot_db `
  -c "SELECT version(); SELECT extname, extversion FROM pg_extension WHERE extname IN ('pg_trgm', 'vector') ORDER BY extname;"
```

再核對主要數量：

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' `
  -U postgres `
  -d roompilot_db `
  -c "SELECT 'furniture_items' AS object_name, COUNT(*) FROM roompilot.furniture_items UNION ALL SELECT 'active_furniture', COUNT(*) FROM roompilot.furniture_items WHERE is_active UNION ALL SELECT 'inactive_furniture', COUNT(*) FROM roompilot.furniture_items WHERE NOT is_active UNION ALL SELECT 'furniture_assets', COUNT(*) FROM roompilot.furniture_assets UNION ALL SELECT 'catalog_api_current', COUNT(*) FROM roompilot.furniture_catalog_api_current UNION ALL SELECT 'embedding_source_current', COUNT(*) FROM roompilot.furniture_embedding_source_current UNION ALL SELECT 'furniture_embeddings', COUNT(*) FROM roompilot.furniture_embeddings;"
```

完整預期值：

| 項目 | 筆數 |
|---|---:|
| `furniture_items` | 8,675 |
| active furniture | 8,076 |
| inactive furniture | 599 |
| `furniture_categories` | 56 |
| `styles` | 6 |
| `furniture_styles` | 17,350 |
| `rooms` | 9 |
| `furniture_rooms` | 20,604 |
| current VLM annotations | 8,675 |
| `furniture_assets` | 34,700 |
| `furniture_quality_issues` | 1,669 |
| `furniture_catalog_current` | 8,076 |
| `furniture_catalog_api_current` | 8,076 |
| `furniture_embedding_source_current` | 8,076 |
| `furniture_embeddings` | 8,076 |
| orphan embeddings | 0 |
| stale embeddings | 0 |

查 orphan／stale 向量：

```sql
SELECT COUNT(*) AS orphan_embeddings
FROM roompilot.furniture_embeddings e
LEFT JOIN roompilot.furniture_items i ON i.item_id = e.item_id
WHERE i.item_id IS NULL;

SELECT COUNT(*) AS stale_embeddings
FROM roompilot.furniture_embeddings e
JOIN roompilot.furniture_embedding_source_current s ON s.item_id = e.item_id
WHERE e.text_hash <> s.text_hash;
```

## 常見錯誤

| 錯誤 | 原因 | 處理方式 |
|---|---|---|
| `psql` 找不到 | PostgreSQL `bin` 未加入 PATH | 使用指南中的完整 `psql.exe` 路徑 |
| `connection refused` | service 未啟動或 port 不一致 | 檢查 PostgreSQL service 與 `.env` 的 `DB_PORT` |
| `password authentication failed` | `.env` 密碼不符 | 修正本機 `.env`，不要把密碼寫死在程式中 |
| `cl`／`nmake` 找不到 | 缺 C++ workload 或開錯 shell | 安裝 MSVC v143，使用 x64 Native Tools Command Prompt |
| `extension "vector" is not available` | pgvector 未安裝到 PostgreSQL 17 | 確認 `PGROOT`，重新 build 與 install |
| `Access is denied` 安裝 pgvector | shell 沒有管理員權限 | 以系統管理員身分重開 x64 build shell |
| `permission denied to create database` | DB 帳號缺 `CREATEDB` | 第一次建立時使用 `postgres` 管理員帳號 |
| dry-run 數量或 ID 不一致 | JSON／CSV／向量不是同一批資料 | 停止匯入，先同步正式輸入，不要略過驗證 |
| 向量 hash 過期 | 名稱、分類或 RAG 文字已修改 | 更新 embedded text/hash 並只重算受影響向量 |

## 完成交付檢查表

- [ ] `psql --version` 顯示 PostgreSQL 17.10。
- [ ] PostgreSQL 17 Windows Service 為 Running。
- [ ] `cl` 與 `nmake` 可在 x64 build shell 執行。
- [ ] `vector` 0.8.2 可用並已在 `roompilot_db` 啟用。
- [ ] Python venv 可 import `psycopg2`。
- [ ] `.env` 已建立且未加入 Git。
- [ ] 家具 dry-run 顯示 8,675 件家具與 34,700 筆資產來源。
- [ ] 向量 dry-run 顯示 8,076 筆 BGE-M3 向量。
- [ ] 正式匯入的 transaction 與筆數核對成功。
- [ ] API current view 為 8,076 筆，inactive 家具為 599 筆。
- [ ] orphan 與 stale embeddings 都是 0。

本流程不會刪除雲端 S3／CloudFront 資產，也不會改寫 VLM 敘述或 RAG metadata。
