# 17 前端資訊架構：［功能／流程］

## 範圍與責任

| 項目 | 內容 |
|---|---|
| 主要 owner／協作 owner | Bella／［domain owner］ |
| 正式前端 | `backend/server/static/` |
| 輸入 | ［PRD、八步狀態、API、project identity］ |
| 輸出 | ［旅程、頁面、CTA、route、跨頁資料］ |
| 技術規格／契約 | ［12 文件］／［`docs/contracts/...`］ |

`frontend3d/` 不得列為第二套正式 IA，除非任務明確是次要原型且不取代八步流程。

## 八步旅程映射

| 步驟 | 使用者目標 | 主要畫面／狀態 | 主要 CTA | 輸入 | 輸出／保存 | 阻擋條件 |
|---|---|---|---|---|---|---|
| 1 建立專案 | ［目標］ | ［畫面］ | ［CTA］ | ［輸入］ | project | ［條件］ |
| 2 上傳平面圖 | ［目標］ | ［畫面］ | ［CTA］ | PNG/JPG/DXF | source/layout draft | ［條件］ |
| 3 公分標定 | ［目標］ | ［畫面］ | ［CTA］ | 兩點/尺度 | cm calibration | ［條件］ |
| 4 校正結構 | ［目標］ | ［畫面］ | ［CTA］ | layout draft | confirmed `layout_json` | ［條件］ |
| 5 逐房問卷 | ［目標］ | ［畫面］ | ［CTA］ | rooms/preferences | requirements/render context | ［條件］ |
| 6 2D/3D 配置 | ［目標］ | ［畫面］ | ［CTA］ | layout/requirements/catalog | `scene_json` | collision/clearance/out-of-bounds |
| 7 鎖定視角 | ［目標］ | ［畫面］ | ［CTA］ | legal scene | locked views/revision | ［條件］ |
| 8 AI 成果 | ［目標］ | ［畫面］ | ［CTA］ | questionnaire/scene/material/view | render/results | ［條件］ |

## 頁面與 Route

| Route／入口 | 頁面單一職責 | 顯示條件 | 主要 CTA | API／資料 | 空／錯誤／返回 |
|---|---|---|---|---|---|
| ［現有 route］ | ［職責］ | ［project/step/role］ | ［一項］ | ［來源］ | ［行為］ |

只有程式與 README 已存在的 `/rag`、`/engineering` 或其他路由才能列為現況；新 route 必須有 Bella adapter、保存與測試計畫。

## 跨頁資料模型

| 來源 | 目標 | 資料 | 載體 | 保存 owner | reload 行為 |
|---|---|---|---|---|---|
| ［頁面］ | ［頁面］ | ［project_id/layout_version/scene revision］ | ［URL/API/project state/local UI］ | ［owner］ | ［行為］ |

## IA 契約 Gate

- [ ] 每頁只有一個主要 CTA，且對應八步合法轉移。
- [ ] 結構變更回到第 4 步並重新驗證既有家具，不由前端跳過 Engine。
- [ ] `layout_json`、requirements、`scene_json` 與 render state 保存責任清楚。
- [ ] cm／`_cm`／`_m2` 不被像素或 Three.js 座標靜默覆蓋。
- [ ] RAG 建議與 Engine reason code 在文案與操作上清楚區分。
- [ ] Inactive/quarantine/家電不作為第 6 步正式家具頁面內容。
- [ ] 409、503、載入失敗、空狀態都有回到主旅程的下一步。

## 驗證

- Journey／workflow contract tests：［命令］
- Project reload／revision tests：［命令］
- JavaScript syntax：［命令］
- 實際瀏覽器 QA：［逐步操作、viewport、預期］

