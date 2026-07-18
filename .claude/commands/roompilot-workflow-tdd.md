# RoomPilot Workflow TDD

使用 `floorplan-vision-specialist`，先讀 `roompilot-workflow-kit/README.md`、
`roompilot-workflow-kit/TDD-SEAMS.md` 與 `roompilot-workflow-kit/tickets/README.md`。

只選一張依賴已滿足的工作票，執行一個 RED→GREEN 垂直切片。不得改變家具座標契約，
不得新增生成式圖片 API，不得以猜測價格填 BOM。完成後回報失敗測試、通過測試、修改檔案與人工確認界線。
