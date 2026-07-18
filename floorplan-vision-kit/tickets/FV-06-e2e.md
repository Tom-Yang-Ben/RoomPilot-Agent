# FV-06 DXF／Scene E2E

- Seam：PNG analyze → confirm → `/api/scene/generate`。
- 原始 DXF 保留外框尺寸；家具引擎使用扣除牆厚後的可擺放淨尺寸。
- 門窗必須穿越 confirm 與 scene payload。
- 證據：HTTP E2E 測試。
