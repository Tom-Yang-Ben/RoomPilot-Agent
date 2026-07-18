---
name: roompilot-floorplan-vision
description: 實作或維護 RoomPilot 的建商平面圖尺度、牆門窗、房間語意與水電瓦斯需求辨識。涉及 floorplan image、OCR、630 公分、門窗、空間分類或 MEP 需求時使用。
---

# RoomPilot Floorplan Vision

先讀 `floorplan-vision-kit/README.md` 與 `floorplan-vision-kit/SPEC.md`，再使用
`floorplan-vision-specialist` agent。

## 路由

- 尺度、OCR、座標：`roompilot/floorplan/vision/analysis.py`
- 牆、門、窗：`roompilot/floorplan/vision/geometry.py`
- 人工確認、DXF：`roompilot/floorplan/vision/confirmation.py`
- 水電瓦斯：`roompilot/floorplan/vision/requirements.py`
- OCR adapter：`roompilot/floorplan/vision/ocr.py`
- HTTP：`roompilot/server/main.py`
- 測試：`tests/test_floorplan_vision.py`、`tests/test_floorplan_vision_api.py`

## 強制流程

1. 固定公開 seam，先寫一個會失敗的行為測試。
2. 不 mock 內部函式；OCR 可透過 observation adapter 隔離。
3. RED → 最小 GREEN；重構留到 review。
4. 低信心不進場景生成，改走 `/api/floorplan/confirm`。
5. 最後跑單檔、完整 pytest、`git diff --check` 與 code review。
