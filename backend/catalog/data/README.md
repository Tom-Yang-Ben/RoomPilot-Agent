# RoomPilot 家具資料邊界

正式家具集合由以下兩個檔案一對一決定：

```text
furniture_catalog_cloud_9350.json
manifests/glb_upload_all_result.csv
```

兩者都必須包含 9,350 個唯一且相同的 `item_id`／`id`。Manifest 的
`upload_status` 必須是可發布狀態，且 `delivery_url` 必須是 HTTPS。

`furniture_catalog_6styles_zh.json` 是舊六風格 enrichment 來源，不是
正式家具母集合。系統只允許用下列方式映射：

1. 完全相同的家具 ID。
2. 唯一且標準化後相同的英文名稱。

歧義或無法映射的舊資料不得進入家具 API、Agent 或 3D。現行整合
結果為：

- 正式 CloudFront 家具：9,350 件。
- 可補六風格／RAG／擺放資料：9,021 件。
- 尚無舊風格標籤：329 件。
- 排除的舊 catalog 列：1,514 筆。

商品圖與正面／側面／45° 圖使用相同正式家具 ID 銜接，但大型圖片
資產不進 Git；部署時應由外部物件儲存或明確設定的資產目錄提供。
