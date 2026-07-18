# FV-01 尺度與座標

- Seam：`analyze_floorplan_image`
- Given：OCR `630` 與 415 px 尺寸線。
- Then：15.181 mm/px；輸出左下角、公尺座標與 evidence。
- 失敗：沒有有效錨點時 `scale_anchor_missing`。
- 證據：`tests/test_floorplan_vision.py`。
