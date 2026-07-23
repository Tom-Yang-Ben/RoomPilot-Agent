# 未對應雲端家具隔離區

此目錄由 Kai 維護，保存 Bella 家具型錄中尚未能安全對應至
`kai-aws` CloudFront Manifest 的項目。

- `unmatched_catalog_items.json`：目前 1,514 件待確認資料。
- 網頁、Agent 選件與 3D 場景不得直接讀取此目錄。
- 修正家具 ID、唯一品名或雲端 Manifest 後，必須通過
  `tests/test_cloud_quarantine.py` 才能重新進入網站型錄。
- 不要把這些項目直接補上猜測的 `model_url`。

網站正式來源仍是：

```text
roompilot/catalog/data/furniture_catalog_6styles_zh.json
roompilot/catalog/data/manifests/glb_upload_all_result.csv
```
