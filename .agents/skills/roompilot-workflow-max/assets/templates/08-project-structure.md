# 08 專案結構變更：［任務名稱］

## 變更資料

| 項目 | 內容 |
|---|---|
| 主要 owner／協作 owner | ［owner］／［owner］ |
| 輸入 | ［現有路徑、依賴、契約］ |
| 輸出 | ［新增／修改檔案與責任］ |
| 影響契約／保存 | ［契約］／［保存邊界］ |

## 現行路徑真相

| 路徑 | Owner | 責任 |
|---|---|---|
| `backend/server/`、`backend/server/static/` | Bella | FastAPI、保存、正式八步 UI |
| `backend/floorplan/`、`backend/upgrade3d/` | Cody | 辨識、`layout_json`、3D 幾何轉換 |
| `backend/spatial_data/` | Django | 空間關係、evaluation、RAG 協調 |
| `backend/catalog/`、`JSON/`、`scripts/sql/` | Kai | 正式 catalog、資產、PostgreSQL |
| `backend/agent/` | Yen | 需求、選件、修復意圖 |
| `backend/engine/` | Ancai | 配置與幾何合法性 |
| `frontend3d/` | Bella | 次要 React/R3F 原型 |
| `testdata/` | Cody／Ben／Django | 小型可重現辨識證據 |

不要套用泛用 `src/` 樹，不要新增第二套 FastAPI 或 production frontend。

## 檔案計畫

| 動作 | 路徑 | 單一職責 | Owner | Consumer | 測試 |
|---|---|---|---|---|---|
| 新增／修改 | ［路徑］ | ［責任］ | ［owner］ | ［consumer］ | ［test］ |

## 跨資料夾修改

- 主要 owner：［owner］
- 協作 owner：［owner］
- 修改檔案：［清單］
- 改變的資料契約或流程：［內容］
- 為何不能只在單一目錄完成：［理由］
- 兩端驗證測試：［producer／consumer］

## 契約與保存 Gate

- [ ] 新路徑未建立第二套 `layout_json`、`scene_json`、catalog 或幾何規則來源。
- [ ] `_cm`／`_m2` 與 schema version 規則仍由正式 producer/contract 定義。
- [ ] RAG 與 Engine 邊界、PostgreSQL/quarantine、production frontend 邊界未改變。
- [ ] 保存 adapter 位於 Bella 邊界；領域模組沒有私建 project store。
- [ ] `scripts/` 變更只以目前工作樹為基準，沒有歷史腳本回填。

## 驗證

- 目錄／import 檢查：［命令］
- Owner 測試：［命令］
- Producer／consumer 測試：［命令］
- 文件／連結：［命令或檢查］

