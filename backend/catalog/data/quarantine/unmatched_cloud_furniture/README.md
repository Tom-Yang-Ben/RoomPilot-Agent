# 未對應雲端家具隔離區

此目錄保存舊六風格型錄中未能安全對應至正式 CloudFront 家具的項目。
它是稽核與 enrichment 維護資料，不是候選家具池。

（隔離判定是在 2026-07-30 燈具剝離前、以當時的 9,350 件集合做的；
正式集合現為 8,557 件，燈具另走獨立表。）

- `unmatched_catalog_items.json`：目前 1,514 件待確認資料。
- 網頁、Agent 選件與 3D 場景不得直接讀取此目錄。
- 修正家具 ID、唯一品名或雲端 Manifest 後，必須通過
  `tests/test_cloud_quarantine.py` 才能重新進入網站型錄。
- 不要把這些項目直接補上猜測的 `model_url`。

網站正式資產來源是：

```text
JSON/furniture/furniture_official_catagory.json
JSON/manifests/glb_upload_all_result.csv
```

`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md` 明文禁止再以
`backend/catalog/data/furniture_catalog_cloud_9350.json` 或其 manifest 複本
做推薦、模型可用性判斷或 SQL 匯入來源。

`furniture_catalog_6styles_zh.json` 只提供可安全映射項目的風格、RAG、
分類與擺放提示；不得把本隔離區項目重新帶回正式集合。
