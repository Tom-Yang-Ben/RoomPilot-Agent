# RoomPilot 對話式設計流程工具包

這包文件讓 Godzilla／Claude Code 的 `floorplan-vision-specialist` 能依固定工作票維護
RoomPilot 的完整流程。正式程式仍位於 `roompilot/`，本資料夾只保存流程契約、使用方式與測試證據。

## 使用者流程

1. 上傳 PNG／JPG／WEBP／DXF 平面圖。
2. 確認尺度、牆、門、窗、房間與水電瓦斯需求；未確認不得繼續。
3. 用聊天逐題補充生活需求，再確認需求摘要。
4. 建立 3D 白模並由 `roompilot.engine` 產生合法家具座標。
5. 從現有 surface catalog 與 GLB 原材質產生 A／B／C 三組智慧材質方案。
6. 選定後貼皮；可恢復 GLB 原材質，且材質操作不得改變家具座標。
7. 3D 審查／拖曳修改後確認預算與 BOM；未知價格一律顯示「待估價」。
8. 以室內行走、2D 正交俯視、完整 3D 旋轉三種模式檢視同一場景。
9. 交付目前視角 PNG、GLB、已確認 DXF，以及列印／另存 PDF。

本版本不呼叫生成式圖片 API。「最終渲染」指現有 3D 場景完成材質貼皮後的即時畫面。

## 功能檔案

- `roompilot/server/static/scene_workflow.js`：九步狀態、guard、project_id／schema_version 與 localStorage。
- `roompilot/server/static/scene_material_schemes.js`：A／B／C 方案、slot 相容性、套用與恢復。
- `roompilot/server/static/scene_view_modes.js`：walk／topdown／orbit 的公開模式契約。
- `roompilot/server/static/scene_delivery.js`：輸出清單與不猜價 BOM。
- `roompilot/server/static/scene.js`：API 與逐步 UI orchestration。
- `roompilot/server/static/scene_viewer.js`：現有材質貼皮、三模式相機、PNG／GLB 匯出。

## 啟動與使用

```powershell
.\.venv\Scripts\python.exe -m uvicorn roompilot.server.main:app --port 8002
```

開啟 `http://127.0.0.1:8002/scene`。不同專案可使用：

```text
http://127.0.0.1:8002/scene?project_id=demo-b1
```

頁面會自動保存流程狀態。按「重新開始此專案」會清除該 `project_id` 的紀錄。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scene_workflow.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_scene_material_schemes.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_scene_view_modes.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_scene_delivery.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py -q
```

完整 TDD seam 與驗收條件見 [TDD-SEAMS.md](TDD-SEAMS.md)，工作票見 [tickets](tickets/README.md)。

## 安全與專業界線

- OCR、OpenCV 與房間規則都是候選；人工確認是正式設計的 gate。
- Python 幾何一律公尺；公分只留在前端 payload 邊界。
- 家具位置只能交給 `roompilot.engine` 計算／驗證。
- 水、電、排水、瓦斯需求是提案資料，不是施工簽證；施工前須由合格專業人員確認。
