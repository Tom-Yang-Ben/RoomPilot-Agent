# Cody AI 責任與交接說明

文件版本：2026-08-06。Cody 擁有平面圖辨識到 `layout_json` 的生產邊界，以及確認版 layout 轉 3D 結構的 adapter。

## AI 快速結論

Cody 回傳的是帶信心度的「辨識證據與結構草稿」。使用者在第 4 步確認前，不得把低信心牆、門窗、房間或 OCR 推論視為確定結構。

## 主要責任

- 維護 `backend/floorplan/` 的影像輪廓、尺度、牆、門、窗、房間、semantic mask 與評估。
- 維護 `backend/upgrade3d/` 將確認版 layout 轉成牆、地板、門窗 3D 幾何的能力。
- 維護 `testdata/` 中可重現的小型辨識 fixtures；大型模型與訓練資產留在 Git 外。
- 所有跨模組輸出統一為公分，並保留 confidence、evidence source 與 schema version。

## 輸入與輸出

```text
PNG／JPG／DXF
  -> 影像 profile／預處理／模型或規則辨識
  -> 牆、開口、房間後處理
  -> 尺度正規化（cm）與信心度
  -> layout_json 草稿
  -> 使用者第 4 步確認
```

`layout_json` 可以包含空間、牆、門、窗、樑、柱、尺度與辨識證據；不能包含家具設計決策、材質、色卡、Yen 視角或生圖結果。

## 八步流程中的位置

- 第 2 步：保存原始平面圖，不假設辨識已完成。
- 第 3 步：建立公分比例與辨識摘要。
- 第 4 步：提供可校正結構，讓使用者確認後形成 layout 邊界。
- 第 6 至 8 步：只提供確認版結構；不得因生圖需求反向改 layout。
- 第 6、7 步的房間 polygon、地面、牆與相機 room binding 都必須引用確認版 `room_id` 與全域公分座標；前端不得為了逐房預覽平移 geometry。

## 跨 owner 邊界

- 房間相鄰、採光面、淨空區與格局評估由 Django enrichment。
- 家具位置與合法性由 Ancai。
- UI 校正、API 與保存由 Bella。
- ground truth 與發布品質證據與 Ben 共同維護。

## 禁止事項

- 不用畫面像素座標跨模組傳遞真實尺寸。
- 不把 OCR 房名或圖示猜測直接升級為 confirmed room。
- 不在辨識模組加入家具配置、RAG 或生圖決策。

## 最低驗證

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_floorplan_room_inference.py tests/test_floorplan_room_evaluation.py tests/test_cody_semantic_status.py
```
