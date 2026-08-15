# RoomPilot 八步架構

本文件名稱保留以維持舊連結；現行公開流程請以 [README](../README.md) 與 [Architecture](ARCHITECTURE.md) 為準。

1. 建立本機專案。
2. 上傳 PNG/JPG/DXF。
3. 校正並確認公分比例。
4. 校正空間、牆、門、窗、樑與柱，形成 `layout_json`。
5. 填寫全屋與逐房需求。
6. 由 catalog 候選與 `backend/engine/` 生成、驗證並編輯 `scene_json`。
7. 鎖定方案與逐房視角。
8. 明確連接外部供應商後產生渲染／成果包；未設定時回 unavailable，不產生假成果。

portable profile 使用自製程序化家具與匿名 fixture；full profile 只讀開發者自行提供且具授權的 PostgreSQL 資料。舊分支、私有 catalog 筆數、CloudFront 資產與已移除測資不是公開 release claim。
