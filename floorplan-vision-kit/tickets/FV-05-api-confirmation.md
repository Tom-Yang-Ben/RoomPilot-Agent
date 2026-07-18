# FV-05 Analyze／Confirm API

- Seam：`/api/floorplan/analyze`、`/api/floorplan/confirm`。
- Analyze 接受影像與可選 OCR／尺度／幾何 observations。
- Confirm 缺尺度或牆回 422；成功輸出毫米 DXF 與 engine payload。
- 證據：`tests/test_floorplan_vision_api.py`。
