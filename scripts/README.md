# Scripts 使用說明

此資料夾提供 RoomPilot 的 GLB 驗證、模型下載、JSON 維護與資料庫匯入工具。請在專案根目錄 `D:\個人抓抓` 執行指令，避免相對路徑指向錯誤位置。

> 本次先跳過 `collect_luxdoors_wood_panel_50.py`（木門圖片蒐集）。因此本說明與 `requirements.txt` 不涵蓋該工具，也不安裝它所需的 `Pillow`。

## 安裝環境

需要 Python 3.10 以上版本。建立虛擬環境並安裝外部套件：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r scripts\requirements.txt
```

| 套件 | 使用的程式 | 用途 |
| --- | --- | --- |
| `psycopg2-binary` | `import_catalog_to_postgres.py` | 連線與批次匯入 PostgreSQL |
| `python-dotenv` | `import_catalog_to_postgres.py` | 載入 `.env` 資料庫設定 |

`generate_glb_manifest.py`、`furniture_downloader.py` 與 `json_catalog_tool.py` 只使用 Python 標準函式庫。

## 工具總覽

| 程式 | 功能 | 是否修改資料 |
| --- | --- | --- |
| `generate_glb_manifest.py` | 驗證 GLB 路徑並建立上傳 Manifest | 只寫入輸出檔 |
| `furniture_downloader.py` | 由直接網址、網址檔、JSON/JSONL manifest 或 IKEA 商品頁下載 GLB | 會下載檔案並寫入下載報告 |
| `json_catalog_tool.py` | 合併、驗證、檢查或清理 JSON | 目前缺少 `_tool_helpers`，僅 `--list` 可用 |
| `import_catalog_to_postgres.py` | 批次 upsert catalog 至 PostgreSQL | 會修改資料庫 |

## 建立 GLB 上傳 Manifest

```powershell
python scripts\generate_glb_manifest.py
```

此工具會遞迴讀取 `JSON/**/*.normalized.json` 的 `items`，並執行以下工作：

- 檢查 `id`、`glb_path`、副檔名與路徑安全性。
- 檢查本機 GLB 是否存在、是否為空檔。
- 依 `source`、`kind`、`id` 產生 S3 `object_key`（預設前綴為 `models`）。
- 偵測重複的 `item_id`、`original_glb_path` 與 `object_key`。
- 輸出 CSV Manifest 與 JSON 驗證報告；可選擇計算 SHA-256。

它不會移動、重新命名或上傳 GLB。輸入每筆資料至少需要 `id` 與 `glb_path`；`source_group`、`catalog`、`kind`、`type`、`name_en` 會一併寫入 Manifest。

| 項目 | 預設位置 |
| --- | --- |
| 輸入 | `JSON/**/*.normalized.json` |
| CSV Manifest | `JSON/manifests/glb_upload_manifest.csv` |
| 驗證報告 | `JSON/manifests/glb_upload_manifest_report.json` |

```powershell
# 先驗證前 10 筆
python scripts\generate_glb_manifest.py --limit 10

# 自訂 JSON 資料夾與輸出位置
python scripts\generate_glb_manifest.py --json-root JSON --output JSON\my_manifest.csv

# 計算每個 GLB 的 SHA-256（大量檔案會較久）
python scripts\generate_glb_manifest.py --calculate-sha256

# 有 missing、invalid 或 empty_file 時回傳非 0 結束碼
python scripts\generate_glb_manifest.py --strict
```

驗證狀態為 `ready`、`missing`、`empty_file` 或 `invalid`；只有 `ready` 的資料列會標示為待上傳（`pending`）。

## 家具 GLB 下載

`furniture_downloader.py` 可從公開 HTTP/HTTPS GLB 來源下載家具模型；下載後會檢查檔頭是否為有效 GLB（`glTF`）。支援 `ikea` 與 `abo` 兩種來源，且只使用 Python 標準函式庫。

```powershell
# 顯示可用來源
python scripts/furniture_downloader.py --list

# 先確認輸出位置，不實際下載
python scripts/furniture_downloader.py ikea --url "https://example.com/chair.glb" --category chairs --dry-run

# 下載單一 GLB
python scripts/furniture_downloader.py abo --url "https://example.com/chair.glb" --category chairs

# 從 UTF-8 文字檔讀取網址；每行可為「網址」或「網址<TAB>檔名」
python scripts/furniture_downloader.py abo --url-file data\glb_urls.txt --category chairs --dry-run

# 從 JSON 或 JSONL 讀取 model_url、glb_url、download_url 或 asset_url
python scripts/furniture_downloader.py abo --manifest data\models.json --category chairs --dry-run

# 由 IKEA 商品頁尋找公開 GLB 網址
python scripts/furniture_downloader.py ikea --product-url "https://www.ikea.com/..." --category chairs --dry-run
```

預設輸出位置為 `downloaded-files/models/ikea/` 或 `downloaded-files/models/abo/`；成功或失敗的下載紀錄會寫入該來源資料夾的 `download_manifest.json`。可用 `--overwrite` 覆寫既有有效 GLB；大型下載前請先使用 `--dry-run`。下載需要網路連線，也應先確認來源授權。

## JSON 與 Catalog 維護

可用操作清單：

```powershell
python scripts\json_catalog_tool.py --list
```

- `merge`：合併 metadata JSON 為 `furniture_catalog.jsonl` 與 `.json`。
- `validate`：驗證 JSON 的必要欄位。
- `check-glb`：檢查 JSON `glb_path` 與本機 GLB 是否一致。
- `prune-missing`：先備份，再移除找不到 GLB 的 JSON 物件；此操作會修改 JSON。

目前專案內沒有 `scripts/_tool_helpers/`，而上述 action 都由該資料夾中的實作檔執行。因此現況下除了 `--list` 以外，執行任何 action 都會出現 `Missing helper`。補回 helper 目錄後，才可依下列形式執行：

```powershell
python scripts\json_catalog_tool.py merge -- --input data\raw_json --output data\processed\furniture_catalog.jsonl
python scripts\json_catalog_tool.py validate -- --input data\raw_json --report-dir data\reports
python scripts\json_catalog_tool.py check-glb
python scripts\json_catalog_tool.py prune-missing
```

## 匯入 Catalog 至 PostgreSQL

`import_catalog_to_postgres.py` reads the fixed input path
`data/processed/furniture_catalog.json` and upserts its records into the
`furniture_items` table using `sku` as the conflict key.

Create a `.env` file at the project root before running it:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=postgres
DB_PASSWORD=your-password
```

After the input JSON and `furniture_items` table are ready, run:

```powershell
python scripts/import_catalog_to_postgres.py
```

This script has no command-line options. To use a different input file, update
`CATALOG_PATH` in `scripts/import_catalog_to_postgres.py`.
