# Owner 與路徑路由

先讀 `docs/TEAM_AI_OWNERSHIP.md` 與實際 owner profile。本表僅提供快速路由。

| 路徑／領域 | 主要 owner | 輸入 | 輸出／責任 | 常見協作方 |
|---|---|---|---|---|
| `backend/server/` | Bella | HTTP、專案狀態、各 owner payload | FastAPI、保存、調度、`scene_json` adapter | 全部 owner |
| `backend/server/static/` | Bella | API payload、project state | 正式 HTML/CSS/JS/Three.js UI | Yen、Ancai、Cody、Django |
| `backend/floorplan/` | Cody | PNG/JPG/DXF、尺度 | 牆門窗房間、confidence、`layout_json` | Django、Ben、Bella |
| `backend/spatial_data/` | Django | 已確認 layout、自然語言查詢 | 空間關係、evaluation、RAG query/ranking | Cody、Kai、Ancai、Bella |
| `backend/catalog/`、`JSON/`、`scripts/sql/` | Kai | 官方資料與 manifest | catalog、CloudFront、PostgreSQL、RAG metadata | Django、Bella |
| `backend/agent/` | Yen | 問卷、房間、catalog candidates | 需求、選件、修復意圖與說明 | Kai、Ancai、Bella |
| `backend/engine/` | Ancai | 房間、牆、開口、家具尺寸 | 座標、碰撞、淨空、移動與合法性 | Yen、Bella |
| `backend/upgrade3d/` | Cody | 已確認 DXF/layout | 3D 可用結構 | Ancai、Bella |
| `frontend3d/` | Bella | scene/DXF API | 次要 React/R3F 原型 | Ancai review |
| `testdata/` | Cody | 來源、ground truth | 可重現辨識測資 | Django、Ben |
| `tests/` | 對應 owner | 公開行為 | 單元、API、契約、視覺回歸證據 | Bella 整合 |
| `docs/contracts/` | Bella 整合 | 已協議 schema | 跨模組公開契約 | 受影響 producer/consumer |

## 依行為路由

- 平面圖、牆門窗、尺度、`layout_json`：Cody 主責；空間語意由 Django 協作，
  API/UI 由 Bella 接入。
- 房間尺寸、相鄰、開口關係、layout evaluation、RAG query：Django 主責；
  不得變更家具身分或幾何合法性。
- 家具、材質、資產 URL、active/quarantine、SQL/embedding：Kai 主責；
  Django 維護檢索品質，Bella 維護 API adapter。
- 需求、偏好、選件、替換/移除/升級人工意圖：Yen 主責；不得產生合法座標。
- 擺放、旋轉、碰撞、淨空、房間邊界：Ancai 主責；LLM/RAG/UI 不可覆寫。
- FastAPI、project persistence、八步 workflow、正式 frontend：Bella 主責；
  adapter 不得重做領域 owner 演算法。
- 辨識 ground truth、release evidence：Ben 與 Cody；runtime 修改仍由 Cody 擁有。

## 跨 owner 修改宣告

修改前填寫：

```text
跨資料夾修改
- 主要 owner：
- 協作 owner：
- 修改檔案：
- 改變的資料契約或流程：
- 為何不能只在單一目錄完成：
- 兩端驗證測試：
```

共享 contract 由單一 writer 先穩定；producer 與 consumer 的程式與測試可在
契約固定後分開實作。跨 owner 的完成條件一定包含兩側驗證。
