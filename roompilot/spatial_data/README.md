# 空間尺寸與標註資料

此目錄是 `django` 分支功能合併到 Bella 時的唯一落點，由 Django 負責。

可放入：

- 房間長寬、面積與全屋比例計算。
- 平面圖尺寸線、色彩標註及文字標籤。
- 空間資料的序列化與驗證。

不可放入：

- PNG／DXF 辨識演算法；該功能屬於 Cody 的 `roompilot/floorplan/`
  與 `roompilot/upgrade3d/`。
- 家具選擇；該功能屬於 Yen 的 `roompilot/agent/`。
- 家具座標計算；該功能屬於 AN 的 `roompilot/engine/`。
- HTML、CSS 或頁面流程；該功能屬於 Bella 的 `roompilot/server/`
  與 `frontend3d/`。

在第一個正式模組加入前，本目錄只保留此合併契約，不建立重複 schema。
