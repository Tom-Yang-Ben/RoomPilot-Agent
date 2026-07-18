# Godzilla 工作票順序

| 工作票 | Seam | 依賴 | 狀態 |
|---|---|---|---|
| WF-01 | 流程狀態／localStorage | Floorplan Vision API | 已完成 |
| WF-02 | 智慧材質 A/B/C／家具換色 | WF-01 | 已完成 |
| WF-03 | walk／topdown／orbit Viewer | WF-02 | 已完成 |
| WF-04 | BOM／PNG／GLB／DXF／PDF E2E | WF-03 | 已完成 |
| WF-05 | 630 golden 圖自動辨識／逐房尺寸 | WF-01 | 已完成 |
| WF-06 | 隱私／基本資料／局部修正／逐房 brief | WF-05 | 已完成 |
| WF-07 | 包牆幾何／可解釋建議／雙層報告 | WF-06 | 已完成 |
| WF-08 | 台灣網路行情概算／來源註記 | WF-07 | 已完成 |

每張票都必須先執行對應單檔 RED，最小實作後 GREEN；最後才跑完整 pytest 與 code review。
