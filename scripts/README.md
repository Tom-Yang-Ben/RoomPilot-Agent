# Scripts 使用說明

此資料夾集中 RoomPilot 的 catalog、GLB 與圖片命令列工具，以及 SQL 支援工具。請在專案根目錄 `D:\RoomPilot-Agent` 執行所有指令，讓相對路徑以正確的專案位置解析。

## 工具一覽

| 程式 | 功能 | 主要影響 |
| --- | --- | --- |
| `roompilot_glb_downloader.py` | 從 URL、URL 清單、manifest 或 IKEA 商品頁下載 GLB | 下載 GLB 並建立下載紀錄；支援 `--dry-run` |
| `roompilot_s3_glb_uploader.py` | 依既有 CSV manifest 將 GLB 上傳至 Amazon S3 | 預設只檢查；加 `--execute` 才會修改 S3 |
| `roompilot_s3_image_uploader.py` | 依既有 CSV manifest 將 PNG 圖片上傳至 Amazon S3 | 預設只檢查；加 `--execute` 才會修改 S3 |
| `roompilot_catalog_manager.py` | 合併、驗證、檢查或清理 JSON/catalog | 清理預設預覽；加 `--apply` 才修改 catalog |
| `sql/` | PostgreSQL 家具與向量 schema、匯入及驗證工具 | 詳見 [`sql/README.md`](sql/README.md) |

## 目前正式資料進度

PostgreSQL 匯入器目前以 `JSON/` 下的正式 catalog、四份資產 manifest／result 與 BGE-M3 向量為輸入：

- Catalog 共 8,675 筆家具，其中 8,076 筆為 active／RAG-indexable，599 筆保留複核且不進正式 API／RAG。
- GLB 8,675 筆、三視角圖片 26,025 筆，合計 34,700 筆資產紀錄。
- BGE-M3 正式向量 8,076 筆；Django 負責 RAG metadata／文字、向量生成、檢索與品質，Kai 在 RAG 流程只負責把交付向量存入 PostgreSQL／pgvector。
- 家具、VLM、RAG metadata 的正式來源是 `JSON/furniture/furniture_official_catagory.json`；資產匯入來源是 `JSON/manifests/`。

完整 dry-run、PostgreSQL 匯入與驗收方式請見 [`sql/README.md`](sql/README.md)。

## 安裝環境

專案基準環境是 Python 3.12。先依根目錄 `README.md` 建立 `.venv` 並安裝專案依賴。S3 上傳工具另外需要 `boto3`：

```powershell
Set-Location 'D:\RoomPilot-Agent'
.\.venv\Scripts\python.exe -m pip install boto3
```

`roompilot_glb_downloader.py` 與 `roompilot_catalog_manager.py` 只使用 Python 標準函式庫。`roompilot_s3_image_uploader.py` 會重用 `roompilot_s3_glb_uploader.py` 的 S3、續傳與結果 CSV 邏輯，因此兩個檔案必須放在同一個 `scripts/` 目錄。

AWS 憑證只應透過 AWS Profile、環境變數或執行環境提供，不得寫入腳本、README、manifest 或 Git。

## Normalized catalog 格式

`roompilot_glb_downloader.py` 的 catalog 與 `roompilot_catalog_manager.py merge` 的 JSON 輸出，統一使用 `roompilot-rag normalized v1`：

```text
schema, source_catalog, source_group, kind, dataset_name,
count, empty_material, empty_color, items
```

每個 `items` 元素固定依序包含 22 個欄位：

```text
id, name_en, name_zh, category, type, role, color, material,
style_confidence, style_source, style_top,
width_cm, depth_cm, height_cm,
glb_path, has_local_glb, is_ikea,
source_group, kind, catalog, source_dataset, product_url
```

JSONL 則是一行一個相同格式的 item，不包含頂層 catalog envelope。

## 家具 GLB 下載

`roompilot_glb_downloader.py` 可處理 IKEA 與 ABO 兩種來源。它會檢查下載檔至少有 12 bytes，且開頭四個 bytes 為 GLB 的 `glTF` magic header。

```powershell
# 顯示來源
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py --list

# 先預覽，不下載
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py ikea --url 'https://example.com/chair.glb' --category chairs --dry-run

# 下載單一 GLB
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py abo `
  --url 'https://example.com/chair.glb' `
  --source-page 'https://example.com/products/chair' `
  --category chairs `
  --kind furniture `
  --catalog abo_furniture `
  --dataset-name 'ABO downloaded furniture'

# 從 UTF-8 文字檔讀取網址；每行可加 TAB、自訂名稱與商品網址
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py abo --url-file data\glb_urls.txt --category chairs --dry-run

# 遞迴讀取 JSON/JSONL 的 model_url、glb_url、download_url 或 asset_url
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py abo --manifest data\models.json --category chairs --dry-run

# 從 IKEA 商品頁尋找公開的 .glb URL
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py ikea --product-url 'https://www.ikea.com/...' --category chairs --dry-run
```

預設輸出位置：

- IKEA：`downloaded-files/models/ikea/{category}/`
- ABO：`downloaded-files/models/abo/{category}/`
- Normalized JSON：來源輸出資料夾內的 `download_catalog.normalized.json`
- Normalized JSONL：來源輸出資料夾內的 `download_catalog.normalized.jsonl`
- 下載狀態、URL 與錯誤：來源輸出資料夾內的 `download_report.json`

只有成功下載或略過既有有效 GLB 的項目會寫入 normalized catalog；失敗項目只會保留在 `download_report.json`。同一次執行會依 URL 去重，檔名衝突時自動加序號。既有且有效的 GLB 預設略過，可用 `--overwrite` 重新下載。下載前應確認 URL 的存取方式與模型授權。大型 GLB 與下載輸出不得提交到 Git。

## 依 Manifest 上傳 GLB 至 S3

此工具只讀取既有 CSV manifest，不會自行產生 manifest。專案目前的正式 GLB manifest 是 `JSON/manifests/glb_upload_manifest.csv`，正式執行產生的結果 CSV 應放在 `.runtime/` 或其他不提交的作業目錄。

CSV 至少需要以下欄位：

```text
item_id,source,original_glb_path,object_key,file_size_bytes,validation_status,upload_status
```

先做本機 dry-run：

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_s3_glb_uploader.py `
  --manifest 'JSON\manifests\glb_upload_manifest.csv' `
  --project-root 'D:\RoomPilot-Agent' `
  --bucket 'your-bucket' `
  --region 'ap-east-2' `
  --profile 'your-aws-profile' `
  --sources ikea abo
```

Dry-run 只驗證本機設定與顯示計畫，不連線 AWS，也不建立結果 CSV。確認後加入 `--execute`：

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_s3_glb_uploader.py `
  --manifest 'JSON\manifests\glb_upload_manifest.csv' `
  --output '.runtime\catalog-uploads\glb_upload_results.csv' `
  --project-root 'D:\RoomPilot-Agent' `
  --bucket 'your-bucket' `
  --region 'ap-east-2' `
  --profile 'your-aws-profile' `
  --sources ikea abo `
  --execute
```

## 依 Manifest 上傳 PNG 圖片至 S3

圖片工具沿用 GLB uploader 的安全與續傳流程。專案目前的正式圖片 manifest 是 `JSON/manifests/image_upload_manifest.csv`，並要求 `image_role` 為 `front`、`side` 或 `angle-45`、檔案為 PNG、`object_key` 預設以 `images/` 開頭。

```powershell
# 本機 dry-run
.\.venv\Scripts\python.exe scripts\roompilot_s3_image_uploader.py `
  --manifest 'JSON\manifests\image_upload_manifest.csv' `
  --project-root 'D:\RoomPilot-Agent' `
  --bucket 'your-bucket' `
  --region 'ap-east-2' `
  --profile 'your-aws-profile' `
  --sources ikea abo

# 正式上傳
.\.venv\Scripts\python.exe scripts\roompilot_s3_image_uploader.py `
  --manifest 'JSON\manifests\image_upload_manifest.csv' `
  --output '.runtime\catalog-uploads\image_upload_results.csv' `
  --project-root 'D:\RoomPilot-Agent' `
  --bucket 'your-bucket' `
  --region 'ap-east-2' `
  --profile 'your-aws-profile' `
  --sources ikea abo `
  --execute
```

兩個 S3 uploader 共同遵守：

- S3 已有相同 object key 且檔案大小相同時，記為 `already_exists`，不重複上傳。
- 同 object key 但大小不同時預設記為衝突；只有明確加 `--force` 才覆蓋。
- 執行中定期原子寫入結果 CSV；中斷後以相同 `--output` 搭配 `--resume` 繼續。
- 可用 `--limit 5` 做小批次驗證。
- `--delivery-base-url` 可建立 CloudFront URL；`--presign-seconds` 可建立最長 7 天的臨時 URL。
- 原始 manifest 不得當作 `--output`，也不得提交 AWS 憑證或大型資產。

## JSON 與 Catalog 維護

列出功能或進入互動式選單：

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py --list
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py
```

### 合併 JSON

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py merge `
  --input data\raw_json `
  --output data\processed\furniture_catalog.normalized.jsonl `
  --json-output data\processed\furniture_catalog.normalized.json `
  --source-catalog custom_furniture `
  --source-group non-IKEA `
  --kind furniture `
  --dataset-name custom_furniture_dataset
```

`merge` 支援 item 陣列、含 `items` 陣列的 catalog，或單一 item object。輸出會正規化為上述欄位，並預設拒絕重複的 `sku`／`id`。只有確定要保留重複識別碼時才使用 `--allow-duplicate-sku`。

### 驗證 JSON

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py validate `
  --input JSON\furniture `
  --pattern *.normalized.json `
  --report-dir JSON\reports
```

`validate` 會檢查識別欄位、名稱、`glb_path`、`.glb` 副檔名及 `product_url`，並產生 JSON 與 CSV 問題報告；有問題時回傳結束碼 `1`。

### 檢查 GLB

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py check-glb `
  --input JSON `
  --project-root 'D:\RoomPilot-Agent' `
  --report JSON\reports\json_glb_consistency_report.json
```

### 清除找不到 GLB 的 item

預設只預覽並寫報告：

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py prune-missing
```

確認報告後，才加入 `--apply`：

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py prune-missing --apply
```

套用前會把原始 JSON 備份到 `JSON/backups/prune_missing_日期時間/`，如有同名 `.jsonl` 也會備份並同步更新。此功能只移除狀態為 `missing_file` 的資料，不會自動移除空路徑、不安全路徑、非 `.glb` 路徑或空 GLB。

## 非破壞性驗證

```powershell
.\.venv\Scripts\python.exe scripts\roompilot_glb_downloader.py --help
.\.venv\Scripts\python.exe scripts\roompilot_s3_glb_uploader.py --help
.\.venv\Scripts\python.exe scripts\roompilot_s3_image_uploader.py --help
.\.venv\Scripts\python.exe scripts\roompilot_catalog_manager.py --list
.\.venv\Scripts\python.exe -m pytest -q tests\test_image_manifest_contract.py
git diff --check
git status --short
```
