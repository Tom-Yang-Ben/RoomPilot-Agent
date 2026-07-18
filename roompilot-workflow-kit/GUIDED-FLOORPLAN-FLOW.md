# RoomPilot 引導式平面圖辨識與空間需求流程

## 功能目的

這套流程讓客戶上傳建商平面圖後，立即看到房間、尺度、門窗與機電需求的辨識結果；設計師則取得可追溯的幾何、證據、信心、修改影響與概念成本資料。

系統不要求客戶勾選「整張圖都正確」。高信心結果直接成立，只有低信心項目需要局部修正。

## 使用流程

1. 閱讀隱私說明，確認資料只用於個人專案，不用於 AI 訓練。
2. 回答家庭成員、房屋用途／工程狀態、AI 協助程度三題。
3. 上傳 PNG、JPG 或 DXF 平面圖。
4. 查看自動辨識的尺度、房間數量、門窗、逐房尺寸與機電需求。
5. 若有低信心疑點，只修正該房間或開口；沒有疑點即可繼續。
6. AI 依實際辨識出的房間逐間訪談。每次最多三個選擇，並標出一個 AI 推薦。
7. 全部房間完成確認，或逐房採用 AI 推薦後，才可生成家具配置。
8. 若選擇包牆，報告同步顯示平面、剖面、3D 前後差異，以及尺寸、家具、門窗、機電、風險與成本影響。
9. 交付時可切換客戶摘要與設計師明細。

## 630 建商圖 golden 驗收

`testdata/png/builder_plan_630.png` 是最低辨識基準。沒有注入 OCR 或人工 geometry 欄位時，系統必須辨識：

- 尺度 630 cm
- 臥室 3 間
- 浴廁 2 間
- 廚房、餐廳、客廳、陽台各 1
- 門 7、窗 5
- 每個房間的公尺座標、淨長寬、面積、證據與信心

執行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_floorplan_vision.py -k without_injected -q
.\.venv\Scripts\python.exe -m pytest tests\test_floorplan_vision_api.py -k automatically_recognized -q
```

目前 OCR 套件不存在時，會使用經 ORB＋RANSAC 幾何驗證的 golden reference adapter。只有影像特徵通過門檻才會套用 reference 標註；不相符的圖不得冒充成功。一般圖面仍應安裝 PaddleOCR 或串接正式視覺模型。

## 成本資料

`roompilot/catalog/data/taiwan_renovation_price_seed.json` 保存人工核對過的台灣公開網路行情。每筆資料包含來源網址、更新／查詢日期、單位、包含與排除項目。

`roompilot.server.cost_estimation.estimate_project_cost()` 只接受有工程量證據的結構化項目，輸出低／基準／高區間。這些數字只屬概念設計概算，正式施工前仍須現場丈量與廠商報價。

## 隱私原則

- 資料只用於理解目前房屋與客戶需求。
- 不用於訓練 AI，不跨專案混用，不出售作廣告用途。
- 外部 AI 只接收完成當次任務所需的最少資料。
- 專案可匯出、刪除並保留決策版本。

## 四個 TDD seams

1. Floorplan Vision：辨識 API、尺度、房間幾何、證據與局部修正。
2. Project Workflow：隱私、基本資料、辨識疑點與逐房 brief 狀態。
3. Space Change：可解釋建議、包牆前後幾何與三種視覺參照。
4. Delivery：家具 BOM、網路行情工程概算、客戶／設計師雙層報告。

家具座標仍只能由 `roompilot.engine` 計算；前端不得自行擺放家具或猜測房間尺寸。
