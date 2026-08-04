# RoomPilot 家具資料邊界

正式家具集合由以下兩個檔案一對一決定，**兩者都不在本目錄**：

```text
JSON/furniture/furniture_official_catagory.json     8,557 筆
JSON/manifests/glb_upload_all_result.csv            8,557 列
```

兩者必須包含相同的 8,557 個唯一 `id`／`item_id`。Manifest 的 `upload_status`
必須是可發布狀態，且 `delivery_url` 必須是 HTTPS。權威定義見
`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`。

執行期優先讀 PostgreSQL view `roompilot.furniture_catalog_current`
（7,958 筆，8,557 中 599 筆 `is_active = false` 未進 view）；資料庫不可用時
才回退上述 JSON。

## 本目錄的 9,350 檔案不是正式來源

`furniture_catalog_cloud_9350.json` 與 `manifests/` 內的 9,350 列 CSV 是
2026-07-30 燈具剝離**前**的快照。契約明文禁止再用它們做推薦、模型可用性判斷
或 SQL 匯入來源。

它們保留的唯一理由是重建燈具交付清單：`scripts/sql/build_lighting_manifest.py`
以「9,350 減 8,557」的差集產生 `manifests/lighting_assets_manifest.csv`，
燈具的品名、分類與尺寸只存在 `furniture_catalog_cloud_9350.json`。
詳見 `manifests/README.md`。

燈具走獨立表 `roompilot.lighting_assets`（793 筆，`lighting_assets_current`
637 筆可用），不在家具集合內。

## 舊型錄 enrichment

`furniture_catalog_6styles_zh.json` 是舊六風格 enrichment 來源，不是正式家具
母集合。系統只允許用下列方式映射：

1. 完全相同的家具 ID。
2. 唯一且標準化後相同的英文名稱。

歧義或無法映射的舊資料不得進入家具 API、Agent 或 3D。

隔離區 `quarantine/unmatched_cloud_furniture/` 現有 1,514 筆（實測，與
`roompilot.external_import_quarantine` 的 `unmatched_cloud` 列數一致）。

> 舊 README 記載的「可補六風格 9,021 件／無舊風格標籤 329 件」是 9,350 時期的
> 數字，剝離後未重新複核，引用前請自行實測。

## 圖片資產

商品圖與正面／側面／45° 圖使用相同正式家具 ID 銜接，但大型圖片資產不進 Git；
部署時由 CloudFront 交付。注意 `backend/server/services/cloud_images.py` 目前讀
本目錄的 9,350 圖片 manifest，`cloud_models.py` 讀 `JSON/` 的 8,557 GLB manifest；
兩者按 `item_id` 查表，多出的 793 列不會被查到。
