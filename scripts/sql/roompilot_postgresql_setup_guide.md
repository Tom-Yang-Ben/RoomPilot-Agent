# RoomPilot PostgreSQL 基礎安裝與開啟流程

> 適用環境：Windows、PowerShell、本機 PostgreSQL  
> 專案根目錄：`<project-root>`  
> 資料庫名稱：`roompilot_db`

本文件說明第一次安裝 PostgreSQL、啟動資料庫服務、建立專案 `.env`、匯入 RoomPilot 資料，以及之後每天重新開啟資料庫的基本流程。

---

## 1. 完整流程

```text
安裝 PostgreSQL
        ↓
安裝時自行設定 postgres 使用者密碼
        ↓
啟動 Windows PostgreSQL Service
        ↓
使用 pg_isready／psql 測試連線
        ↓
複製 .env.example 為 .env
        ↓
在 DB_PASSWORD 填入自己的密碼
        ↓
安裝 Python 套件
        ↓
執行 Strict Dry Run
        ↓
建立 roompilot_db 與 Schema
        ↓
匯入 10,550 筆 Catalog 與 GLB 資產資料
        ↓
使用 SQL 驗證匯入結果
```

---

## 2. 第一次安裝 PostgreSQL

### 2.1 下載安裝程式

從 PostgreSQL 官方 Windows 下載頁取得安裝程式：

<https://www.postgresql.org/download/windows/>

一般本機開發環境選擇仍受支援的正式穩定版本即可，不要安裝 Beta／RC 測試版本。

### 2.2 建議安裝項目

安裝時至少保留：

- PostgreSQL Server
- pgAdmin 4
- Command Line Tools

Stack Builder 不是本專案的必要項目，可先不安裝額外套件。

### 2.3 安裝設定

| 設定 | 建議值 |
|---|---|
| Installation Directory | 使用安裝程式預設值 |
| Data Directory | 使用安裝程式預設值 |
| Superuser | `postgres` |
| Password | 由使用者自行設定並妥善保存 |
| Port | `5432` |
| Locale | 使用預設值即可 |

`postgres` 密碼沒有固定值。安裝程式要求輸入密碼時，請自行設定；之後將同一組密碼填入專案根目錄 `.env` 的 `DB_PASSWORD`。

不要把實際密碼寫入 README、程式碼、Git commit 或聊天紀錄。

---

## 3. 啟動 PostgreSQL

PostgreSQL Windows 安裝程式通常會建立自動啟動的 Windows Service。重新開機後若服務已是 `Running`，不需要再次啟動。

### 3.1 查詢服務名稱與狀態

以 PowerShell 執行：

```powershell
Get-Service -Name "postgresql*"
```

可能看到類似結果：

```text
Status   Name                    DisplayName
------   ----                    -----------
Running  postgresql-x64-18       postgresql-x64-18
```

實際服務名稱會依安裝版本不同，請以自己電腦顯示的 `Name` 為準。

### 3.2 啟動服務

若狀態為 `Stopped`，請用系統管理員 PowerShell 執行：

```powershell
Start-Service -Name "postgresql-x64-版本號"
```

例如服務名稱顯示為 `postgresql-x64-18`：

```powershell
Start-Service -Name "postgresql-x64-18"
```

### 3.3 重新啟動或停止服務

```powershell
Restart-Service -Name "postgresql-x64-版本號"
Stop-Service -Name "postgresql-x64-版本號"
```

平常不需要特別停止 PostgreSQL；只有修改伺服器設定或排除問題時才需要重新啟動。

也可以按 `Win + R`，輸入 `services.msc`，在 Windows 服務管理介面中啟動或重新啟動 PostgreSQL。

---

## 4. 確認 PostgreSQL 可以連線

安裝完成後重新開啟 PowerShell，再執行：

```powershell
psql --version
pg_isready -h localhost -p 5432
```

正常的 `pg_isready` 結果：

```text
localhost:5432 - accepting connections
```

接著連線到安裝時建立的管理資料庫：

```powershell
psql -h localhost -p 5432 -U postgres -d postgres
```

出現 `Password for user postgres:` 時，輸入安裝 PostgreSQL 時自行設定的密碼。PowerShell 不會顯示輸入中的密碼字元，這是正常現象。

進入 `psql` 後可以執行：

```sql
SELECT version();
\l
\q
```

| 指令 | 用途 |
|---|---|
| `SELECT version();` | 顯示 PostgreSQL 版本 |
| `\l` | 列出資料庫 |
| `\q` | 離開 psql |

若 PowerShell 顯示找不到 `psql` 或 `pg_isready`，可以使用開始功能表中的 `SQL Shell (psql)`，或將 PostgreSQL 安裝目錄下的 `bin` 加入 Windows PATH。常見位置為：

```text
C:\Program Files\PostgreSQL\版本號\bin
```

---

## 5. 建立專案 `.env`

切換到專案根目錄：

```powershell
cd "<project-root>"
```

複製範例檔：

```powershell
Copy-Item -LiteralPath ".env.example" -Destination ".env"
```

`.env` 應使用以下變數名稱：

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

請在本機 `.env` 的 `DB_PASSWORD=` 後面填入安裝時自訂的 PostgreSQL 密碼，例如：

```dotenv
DB_PASSWORD=你的實際密碼
```

不要修改 `.env.example` 去保存真實密碼，也不要把 `.env` 提交到 Git。

### 環境變數說明

| 變數 | 用途 |
|---|---|
| `DB_HOST` | PostgreSQL 主機；本機使用 `localhost` |
| `DB_PORT` | PostgreSQL 連接埠；預設為 `5432` |
| `DB_NAME` | RoomPilot 目標資料庫名稱 |
| `DB_ADMIN_DB` | 建立目標資料庫時先連線的管理資料庫 |
| `DB_USER` | PostgreSQL 使用者；基礎流程使用 `postgres` |
| `DB_PASSWORD` | 使用者自行設定的密碼 |
| `DB_SSLMODE` | 本機連線使用 `disable` |
| `DB_CONNECT_TIMEOUT` | 連線逾時秒數 |
| `DB_APPLICATION_NAME` | PostgreSQL 內顯示的應用程式名稱 |

---

## 6. 安裝 Python 套件

從專案根目錄執行：

```powershell
cd "<project-root>"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r ".\scripts\requirements.txt"
```

如果 `.venv` 已經建立，之後只需：

```powershell
cd "<project-root>"
.\.venv\Scripts\Activate.ps1
```

PostgreSQL 匯入器需要：

- `psycopg2-binary`
- `python-dotenv`

---

## 7. 先執行 Strict Dry Run

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --dry-run
```

Dry Run 會：

- 驗證 Catalog、Manifest 與 Upload Result。
- 更新驗證 JSON 與兩份稽核 CSV。
- 不連線 PostgreSQL。
- 不建立資料庫或資料表。
- 不寫入資料庫。

目前正常結果應包含：

```text
catalog：10,550 筆
manifest：10,550 筆
upload result：10,550 筆
item types：87 種
警告：0 筆
```

若有 warning 或錯誤，先修正來源資料，不要移除 `--strict` 直接匯入。

---

## 8. 首次建立資料庫、Schema 並匯入

確認 PostgreSQL Service 正在執行、`.env` 密碼正確，而且 Strict Dry Run 為 0 warning 後，執行：

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" `
  --strict `
  --create-database `
  --create-schema
```

此命令會：

1. 使用 `.env` 連線 `DB_ADMIN_DB=postgres`。
2. 若 `roompilot_db` 不存在，建立 UTF-8 資料庫。
3. 執行 `roompilot_postgresql_schema.sql`。
4. 建立或升級資料表、索引與 View。
5. 使用 transaction 與 UPSERT 寫入資料。
6. 寫入一筆 `import_batches` 紀錄。

使用 `--create-database` 時，`DB_USER` 必須有建立資料庫的權限。基礎本機流程使用安裝時建立的 `postgres` 使用者即可。

---

## 9. 日常更新資料

資料庫已存在後，日常更新不需要再次加入 `--create-database`：

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" `
  --strict `
  --create-schema
```

`--create-schema` 可安全重複執行，會套用目前 Schema／Migration，再以 UPSERT 更新資料。

每次正式更新前仍應先執行：

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --dry-run
```

---

## 10. 匯入後驗證

連線 RoomPilot 資料庫：

```powershell
psql -h localhost -p 5432 -U postgres -d roompilot_db
```

執行：

```sql
SELECT COUNT(*) FROM catalog_items;                     -- 10550
SELECT COUNT(*) FROM glb_assets;                        -- 10550
SELECT COUNT(*) FROM item_types;                        -- 87
SELECT COUNT(*) FROM item_roles;                        -- 11
SELECT COUNT(*) FROM catalog_items WHERE NOT is_active; -- 1
SELECT COUNT(*) FROM catalog_items_for_space_planning;  -- 10542
```

確認 GLB 上傳狀態：

```sql
SELECT upload_status, COUNT(*)
FROM glb_assets
GROUP BY upload_status;
```

預期：

```text
uploaded：10,550
```

離開：

```sql
\q
```

---

## 11. 每天開啟專案的最短流程

### 11.1 確認 PostgreSQL 已啟動

```powershell
Get-Service -Name "postgresql*"
pg_isready -h localhost -p 5432
```

若服務為 `Stopped`：

```powershell
Start-Service -Name "postgresql-x64-版本號"
```

### 11.2 啟用 Python 環境

```powershell
cd "<project-root>"
.\.venv\Scripts\Activate.ps1
```

### 11.3 視需要連線或更新

開啟 SQL Shell：

```powershell
psql -h localhost -p 5432 -U postgres -d roompilot_db
```

更新 Catalog：

```powershell
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --dry-run
python ".\scripts\sql\import_catalog_to_postgres.py" --strict --create-schema
```

只要資料沒有更新，不需要每天重新匯入。

---

## 12. 使用 pgAdmin 4

若偏好圖形介面，可從 Windows 開始功能表開啟 pgAdmin 4。

第一次連線本機伺服器時使用：

| 設定 | 值 |
|---|---|
| Host name/address | `localhost` |
| Port | `5432` |
| Maintenance database | `postgres` |
| Username | `postgres` |
| Password | 安裝時自行設定的密碼 |

資料匯入完成後，在 Databases 下應看見 `roompilot_db`。

---

## 13. 常見錯誤

### 找不到 `psql` 或 `pg_isready`

原因：PostgreSQL 的 `bin` 尚未加入 PATH。

處理：重新開啟 PowerShell；若仍無法使用，改用 SQL Shell，或將下列目錄加入 PATH：

```text
C:\Program Files\PostgreSQL\版本號\bin
```

### `connection refused`／`no response`

檢查：

```powershell
Get-Service -Name "postgresql*"
pg_isready -h localhost -p 5432
```

確認 PostgreSQL Service 已啟動，並確認 `.env` 的 `DB_HOST` 與 `DB_PORT` 正確。

### `password authentication failed for user "postgres"`

代表 `.env` 的 `DB_PASSWORD` 與 PostgreSQL 實際密碼不同。請修正本機 `.env`；不要修改程式去寫死密碼。

### 無法建立 `roompilot_db`

確認：

- `DB_ADMIN_DB=postgres`。
- `DB_USER=postgres`，或使用具備 `CREATEDB` 權限的帳號。
- PostgreSQL Service 已啟動。
- 密碼正確。

### `ModuleNotFoundError: psycopg2` 或 `dotenv`

重新啟用虛擬環境並安裝套件：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r ".\scripts\requirements.txt"
```

### 找不到 `.env`

`.env` 必須位於：

```text
<project-root>\.env
```

不是放在 `scripts\sql` 內。

---

## 14. 安全原則

- `DB_PASSWORD` 由每位使用者自行設定。
- `.env.example` 的密碼保持空白。
- 真實密碼只放在本機 `.env`。
- `.env` 不可提交 Git 或傳給其他人。
- 正式匯入前先執行 `--strict --dry-run`。
- 既有資料庫正式匯入前先備份。
- 不要用關閉 `--strict` 的方式掩蓋資料錯誤。

---

## 15. 官方參考

- [PostgreSQL Windows 下載](https://www.postgresql.org/download/windows/)
- [pg_isready 官方說明](https://www.postgresql.org/docs/current/app-pg-isready.html)
- [psql 官方說明](https://www.postgresql.org/docs/current/app-psql.html)

