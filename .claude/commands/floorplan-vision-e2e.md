---
description: 驗證 PNG 分析、人工確認、DXF 與場景生成的完整旅程
---

執行：

```bash
uv run pytest tests/test_floorplan_vision_api.py -v
```

必須覆蓋上傳影像、尺度、牆門窗、房間需求、確認 DXF、`/api/scene/generate`，不得呼叫外部 OCR 網路服務。
