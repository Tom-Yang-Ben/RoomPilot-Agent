# SF3D 舊型錄隔離資料

## 狀態

此資料夾只供資料核對。RoomPilot 執行期程式不得載入 `quarantine/` 內的檔案。

## 內容

- `ikea_furniture_style_database.json`：1,509 筆舊資料，共 1,508 個唯一家具 ID。
- `style_moodboard.json`：與舊型錄配套的八風格參考資料。

舊型錄有 610 個唯一 ID 不在目前的 `furniture_catalog_6styles_zh.json`。在 Kai
將它們對應到已驗證的雲端 manifest 前，這些資料不得發布，也不得參與自動配置。

## 與「舊友：12種風格與JSON」的關係

兩個目錄有同名檔案，但**不是重複，不可擇一刪除**：

| 檔案 | 本目錄 | `../../舊友：12種風格與JSON/` |
|---|---|---|
| `ikea_furniture_style_database.json` | `furniture` 1,509 筆（已配風格的子集） | `furniture` 3,055 筆（完整 12 風格資料集） |
| `style_moodboard.json` | 8 風格 | 12 風格 |

本目錄那份是舊友那份的 styled 子集，由
`scripts/runtime_catalog/import_runtime_catalogs_to_postgres.py` 的 `DEFAULT_LEGACY`
讀取，匯入 `roompilot.external_import_quarantine`（`source_kind = 'sf3d_legacy'`，
實測 1,509 列）。舊友那份另有自己的消費者，見該目錄 README。

## 處理規則

每筆未對應資料都必須：

1. 對應到一個已驗證的雲端物件與正式家具 ID。
2. 驗證尺寸、分類、模型可用性與來源身分。
3. 經型錄管線與測試匯入，或記錄繼續隔離的原因。
4. 所有未對應資料都有明確處置後，才能刪除此隔離資料。
