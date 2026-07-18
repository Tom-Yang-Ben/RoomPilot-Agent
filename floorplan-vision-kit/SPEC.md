# Floorplan Vision Spec

## 目標

將建商 raster 平面圖轉成可追溯、可確認的 RoomPilot 平面資料，支援需求建立、可行性檢核、
方案生成與審查迭代。系統不得在資料不完整時進入正式家具配置。

## 公開 seams

1. `analyze_floorplan_image(image_bytes, ...)`：尺度、座標、牆、門、窗、房間、issues。
2. `infer_room_requirements(analysis, brief=None)`：水電瓦斯需求、來源與確認狀態。
3. `/api/floorplan/analyze`、`/api/floorplan/confirm`：影像分析與人工確認。
4. PNG → confirm DXF → `/api/scene/generate`：完整 E2E。

## 驗收條件

- 630 cm／415 px 的 worked example 回傳 0.015181 m/px。
- Python output unit 是 metre，原點是 plan bbox 左下角，x 向右、y 向上。
- 牆、門、窗皆有來源與 confidence；已確認幾何來源是 `confirmed_geometry`。
- 房名至少支援客廳、廚房、浴廁、臥室、餐廳、陽台、書房。
- 廚房推導給水、排水、用電與條件式瓦斯；浴廁推導冷熱水、排水、漏電保護用電與排風。
- 未確認尺度或沒有牆時 confirm 回 422。
- 自動 `opencv_geometry` 沒有完整 corrections 時 confirm 回 422。
- MEP provenance 支援 `floorplan_observation`、`room_type_rule`、`user_confirmation`。
- 確認 DXF 使用毫米，既有 parser 轉回公尺；scene E2E 保留門窗。
- 外部 OCR 不得在測試中連網。

## 非目標

- 不取代 AutoCAD 施工圖、建築師、機電技師或瓦斯專業簽證。
- 不從房名直接宣稱圖上已存在水管、電線或瓦斯管。
- 不由 LLM 自由生成幾何座標。
