---
description: 對下一張平面圖辨識工作票執行一輪 RED→GREEN
---

呼叫 `floorplan-vision-specialist`，只執行一個垂直切片：先跑出 RED 證據，再做最小 GREEN。
測試必須從已確認的四個公開 seams 觀察行為，並斷言單位、來源、信心及確認狀態。
