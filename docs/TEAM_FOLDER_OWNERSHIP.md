# 團隊資料夾責任

Bella 不改成照片中的扁平 `backend/` 結構。`roompilot/` 是可安裝的 Python
套件；照片中的後端路徑依下表放入現有套件。

| 負責人 | 唯一主要目錄 | 職責 |
|---|---|---|
| Cody | `roompilot/floorplan/`、`roompilot/upgrade3d/` | PNG、DXF、牆與門窗辨識 |
| Kai | `roompilot/catalog/` | 家具型錄、AWS Manifest、CloudFront 與 quarantine |
| Django | `roompilot/spatial_data/` | 房間尺寸、面積、比例與平面圖尺寸標註 |
| Yen | `roompilot/agent/` | 家具選件與擺放失敗修復策略 |
| AN | `roompilot/engine/` | 家具座標、碰撞與淨空檢查 |
| Bella | `roompilot/server/`、`frontend3d/` | FastAPI、1–8 流程、2D／3D UI |

## 照片路徑對照

| 組員舊分支 | Bella 目前落點 |
|---|---|
| `backend/floorplan/` | `roompilot/floorplan/` |
| `backend/upgrade3d/` | `roompilot/upgrade3d/` |
| `backend/catalog/` | `roompilot/catalog/` |
| `backend/agent/` | `roompilot/agent/` |
| `backend/engine/` | `roompilot/engine/` |
| `backend/server/` | `roompilot/server/` |
| `frontend/` | `roompilot/server/static/` 或 `frontend3d/` |
| `data/dataset/` | 雲端模型不搬；metadata 放 `roompilot/catalog/data/` |
| `data/testdata/` | `testdata/` |
| `Final-Project_Version3/` | 只移植空間邏輯到 `roompilot/spatial_data/` |

## 修改規則

1. 每位成員只修改自己的主要目錄及對應測試。
2. 不把演算法直接寫入 `roompilot/server/main.py`。
3. 跨模組欄位先沿用現有 schema；需要改契約時由受影響成員共同確認。
4. 家具座標只能由 `roompilot/engine/` 計算。
5. Python 使用公尺；公分只允許出現在既有 catalog 與前端 payload 邊界。
6. `quarantine/` 內資料不得提供給網頁。
