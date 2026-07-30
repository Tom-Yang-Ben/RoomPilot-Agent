# RoomPilot 家具資料邊界

正式家具集合由 repository 根目錄下列檔案一對一決定：

```text
JSON/furniture/furniture_official_catagory.json
JSON/manifests/glb_upload_all_result.csv
JSON/manifests/image_upload_all_result.csv
```

官方 JSON 與 GLB manifest 都必須包含 8,675 個唯一且相同的
`item_id`／`id`；圖片 manifest 必須包含相同 8,675 件家具的 26,025
張三視圖。`backend/catalog/data/manifests/` 是同步副本，必須與
`JSON/manifests/` 逐檔 SHA-256 相同。Manifest 的 `upload_status` 必須是
可發布狀態，且 `delivery_url` 必須是 HTTPS。

舊版 cloud catalog、修正候選、稽核輸出與 quarantine 家具 payload
不再保存在 repository。`furniture_catalog_6styles_zh.json` 只保留
top-level `styles`、`taxonomy` 與空的 `furniture` array，作風格展示定義；
舊路徑下的相容 JSON 也只保留空 array，不能補值、增加家具或進入家具
API、Agent、SQL 或 3D。現行正式結果為：

- 正式 CloudFront 家具：8,675 件。
- 正式六風格標註：8,675 件。
- 正式 GLB：8,675 個。
- 正式三視圖：26,025 張。
- `is_active=true` 且可進 API／RAG：8,076 件。
- `is_active=false` 人工隔離：599 件；manifest 與雲端資產保留。

商品圖與正面／側面／45° 圖使用相同正式家具 ID 銜接，但大型圖片
資產不進 Git；部署時應由外部物件儲存或明確設定的資產目錄提供。
