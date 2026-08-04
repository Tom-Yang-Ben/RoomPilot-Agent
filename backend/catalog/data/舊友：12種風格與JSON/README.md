# 舊友：12種風格與JSON

此資料夾封存六風格改版前的 12 風格資料與外部匯入索引。
它們僅供追溯與比對，strict PostgreSQL 模式下 FastAPI 不會讀取。

## 檔案與消費者

| 檔案 | 讀取者 |
|---|---|
| `external_furniture_import_index.json` | `backend/server/main.py` 的 `EXTERNAL_IMPORT_PATH`（僅 `ROOMPILOT_RUNTIME_CATALOG_PROVIDER=json` 的離線模式會實際讀檔）；`scripts/runtime_catalog/import_runtime_catalogs_to_postgres.py` 的匯入來源 |
| `ikea_furniture_style_database.json` | `tests/test_catalog_six_style_contract.py` 斷言存在 |
| `style_moodboard.json`、`taiwan_style_cards_before_six_style_alignment.json` | 無程式讀取者，純封存 |

## 與 `quarantine/sf3d_legacy/` 的關係

兩個目錄有同名檔案，但**不是重複，不可擇一刪除**：

| 檔案 | 本目錄 | `../quarantine/sf3d_legacy/` |
|---|---|---|
| `ikea_furniture_style_database.json` | `furniture` 3,055 筆（完整資料集） | `furniture` 1,509 筆（已配風格的子集） |
| `style_moodboard.json` | 12 風格 | 8 風格 |

隔離區那份是本目錄的子集，且是 PostgreSQL `external_import_quarantine` 的匯入來源。

## 目錄名稱

文件裡曾記錄的「舊有：12種風格與JSON」重複目錄已不存在，磁碟上只有本目錄一份。
但 `import_runtime_catalogs_to_postgres.py` 仍以
`CATALOG_DATA.glob("*/external_furniture_import_index.json")` 取第一個結果，
再出現同名檔案就會變成不確定行為——新增同層目錄前先確認這點。
