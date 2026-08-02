# 未對應雲端家具隔離區

此目錄保存舊六風格型錄中未能安全對應至正式 9,350 件 CloudFront
家具的項目。它是稽核與 enrichment 維護資料，不是候選家具池。

- `unmatched_catalog_items.json`：目前 1,514 件待確認資料。
- 網頁、Agent 選件與 3D 場景不得直接讀取此目錄。
- 修正家具 ID、唯一品名或雲端 Manifest 後，必須通過
  `tests/test_cloud_quarantine.py` 才能重新進入網站型錄。
- 不要把這些項目直接補上猜測的 `model_url`。

網站正式資產來源是：

```text
backend/catalog/data/furniture_catalog_cloud_9350.json
backend/catalog/data/manifests/glb_upload_all_result.csv
```

`furniture_catalog_6styles_zh.json` 只提供可安全映射項目的風格、RAG、
分類與擺放提示；不得把本隔離區項目重新帶回正式集合。
