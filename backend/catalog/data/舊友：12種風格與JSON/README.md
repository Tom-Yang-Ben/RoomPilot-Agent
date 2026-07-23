# 舊友：12種風格與JSON

此資料夾封存六風格改版前的 12 風格資料與外部匯入索引。

**⚠️ 2026-07-16 更正:本夾並非全部是死資料,先前「執行期不會讀取」的說法是錯的。** 逐檔現況:

| 檔案 | 狀態 |
|---|---|
| `external_furniture_import_index.json` | **活資產**:`backend/server/config.py`(`EXTERNAL_IMPORT_PATH`)執行期實際載入;`tests/test_catalog_six_style_contract.py` 斷言其存在。**勿刪勿搬。** |
| `ikea_furniture_style_database.json` | 執行期不載入,但契約測試斷言它存在於本夾。刪除會使測試失敗。 |
| `style_moodboard.json` | 純封存,全 repo 零引用(2026-07-16 掃描)。 |
| `taiwan_style_cards_before_six_style_alignment.json` | 純封存,全 repo 零引用;六風格對齊前的舊風格卡,僅供追溯。 |
