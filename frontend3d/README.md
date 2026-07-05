# DXF → 3D 白模 (R3F + shapely)

把 `pic/temp/` 內的 DXF 平面圖即時轉成 3D 場景：**牆壁**（實體擠出）與**窗戶**（玻璃面板），格局比例保留。

- **後端** `backend/` — FastAPI；`ezdxf` 解析 DXF，`shapely` 把牆中心線 buffer 成實體牆塊（合併雙線牆）。
- **前端** `frontend/` — Vite + React + React Three Fiber (drei) 即時渲染。

## 跑起來

兩個終端機：

```bash
# 1) 後端（在 app/backend/）
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# 2) 前端（在 app/frontend/）
npm install
npm run dev          # 開 http://localhost:5173
```

Vite 會把 `/api` 代理到 8000，所以瀏覽器不需處理 CORS。

## 用法

- **選擇平面圖**：下拉選 `pic/temp/` 既有的 7 個 DXF，或**上傳 DXF**。
- **長邊實際尺寸**：DXF 單位常不可靠（多數標 feet 但範圍像 inch/mm），所以以「最長邊 = N 公尺」校正比例；預設依長邊正規化為 12 m，可手動覆寫或按「重設為自動」。比例（長寬比）一律精確保留。
- **牆厚**：buffer 半徑×2。調大可把分開的雙線牆合併成一道實牆。
- **樓高 / 牆窗門地板顯示**：即時切換。

## 設計取捨

- 牆 = shapely `buffer`（方形端蓋，角落補成直角）合併線段 ∪ HATCH 填充多邊形（牆常以實心 hatch 畫，缺它牆會破碎）。HATCH 多迴圈用 even-odd（XOR）處理，使「外框−房間」這種環狀牆保持中空。
- **依葉節點圖層分類**：圖塊（INSERT）內的窗線常掛在 window 圖層、但圖塊本身放在別的圖層（如 DIM1）。因此遞迴展開後以「最內層實體自己的圖層」分類，才不會漏掉窗。
- **不做逐房間切割**：真實 CAD 在門窗開口處處留縫，穩健的房間分割需要牆軸圖求解，超出「主要生成牆壁及窗戶」範圍。地板用整體 bbox 板，比例正確即可。
- 自我檢查：`python backend/dxf_parser.py` 會跑過 7 個檔，斷言每個都解析出牆體與合理比例。
