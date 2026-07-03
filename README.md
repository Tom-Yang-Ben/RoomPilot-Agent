# RoomPilot Agent

RoomPilot Agent 是用來整理 IKEA GLB 家具資料的 Python 專案。主要流程是先整理原始 JSON，再驗證資料格式，合併成家具 catalog，最後匯入 PostgreSQL，提供後端 API 查詢使用。

## 安裝

```bash
pip install -r requirements.txt
```

如果要匯入 PostgreSQL，請在專案根目錄建立 `.env`：

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/roompilot
```

## 資料夾用途

```text
data/
├── raw_json/
├── processed/
└── reports/
```

| 資料夾 | 用途 |
| --- | --- |
| `data/raw_json/` | 放原始家具分類 JSON，可以有子資料夾，腳本會遞迴掃描。 |
| `data/processed/` | 放合併後的輸出檔，例如 `furniture_catalog.jsonl` 和 `furniture_catalog.json`。 |
| `data/reports/` | 放驗證或匯入時產生的報告，例如錯誤 CSV、驗證 summary。 |

## Python 檔案用途

| 檔案 | 功用 |
| --- | --- |
| `scripts/ikea_category_glb_downloader.py` | 從 IKEA 分類頁尋找可用的 GLB 3D 模型，下載 `.glb` 並產生 metadata CSV / JSON。 |
| `scripts/clean_metadata_json.py` | 清理舊 metadata，例如把 `chinese name` 改成 `chinese_name`、修正 `glb_path` 斜線。 |
| `scripts/validate_json.py` | 檢查 `data/raw_json/` 裡的 JSON 是否符合後端與資料庫需求。 |
| `scripts/merge_json_to_catalog.py` | 把多個分類 JSON 的 `scene.objects` 合併成總家具 catalog。 |
| `scripts/import_furniture_to_db.py` | 把 `furniture_catalog.jsonl` 匯入 PostgreSQL 的 `furniture_items` 資料表。 |

## 建議執行順序

### 0. 下載 IKEA GLB 與 metadata

如果還沒有原始資料，可以先執行下載器：

```bash
python scripts/ikea_category_glb_downloader.py
```

下載完成後，請把要處理的 metadata JSON 放到 `data/raw_json/`。

### 1. 驗證 JSON

```bash
python scripts/validate_json.py --input data/raw_json
```

成功後會產生：

```text
data/reports/validation_report.json
data/reports/validation_errors.csv
```

如果錯誤數是 `0`，代表資料可以進入下一步。

### 2. 合併家具 catalog

```bash
python scripts/merge_json_to_catalog.py --input data/raw_json --output data/processed/furniture_catalog.jsonl
```

成功後會產生：

```text
data/processed/furniture_catalog.jsonl
data/processed/furniture_catalog.json
```

`jsonl` 適合匯入資料庫，一行一筆資料。`json` 適合人工查看或給前端測試。

### 3. 匯入 PostgreSQL

```bash
python scripts/import_furniture_to_db.py --input data/processed/furniture_catalog.jsonl
```

成功後會在 PostgreSQL 建立或更新 `furniture_items` 資料表。匯入失敗的資料會輸出到：

```text
data/reports/import_errors.csv
```

## 不上傳到 GitHub 的資料夾

以下資料夾已加入 `.gitignore`，不會上傳到 GitHub：

```text
.venv/
__pycache__/
downloaded-files/
舊的翻譯資料/
```

這些通常是本機環境、快取檔、大型 GLB 檔案或舊資料備份，不適合放進 GitHub。

## License

本專案參考 `apinanaivot/IKEA-3d-model-batch-downloader`，並沿用 GPL-3.0 授權。詳見 [LICENSE](LICENSE)。
