# 02 任務簡報與 PRD：［任務名稱］

> 以現行 RoomPilot 八步流程為基準；不要用本模板改寫既有 owner 或正式契約。

## 基本資料

| 項目 | 內容 |
|---|---|
| 主要 owner | ［Bella／Cody／Django／Kai／Yen／Ancai／Ben］ |
| 協作 owner | ［無／姓名與責任］ |
| 影響步驟 | ［1–8／工程文件］ |
| 目標路徑 | ［repo 相對路徑］ |
| 狀態／日期 | ［草稿／確認／完成］／［YYYY-MM-DD］ |

## 問題、目標與邊界

- 使用者痛點：［可觀察的問題］
- 目標：［最多三項可驗收結果］
- 成功指標：［指標、基準、目標值、量測方式］
- 非目標：［本次明確不處理的內容］
- 假設／依賴：［資料、服務、owner 決策］

## 輸入與輸出

| 類型 | 名稱／格式 | 生產者／消費者 | 版本與單位 |
|---|---|---|---|
| 輸入 | ［例如 `layout_json`、問卷、catalog row］ | ［owner］ | ［schema；cm／m2］ |
| 輸出 | ［例如 `scene_json`、API payload、報告］ | ［owner］ | ［schema；cm／m2］ |

## 使用者故事與驗收

| ID | 身為…我想…以便… | 可觀察的驗收條件 | 對應測試 |
|---|---|---|---|
| US-001 | ［故事］ | ［正常、失敗、邊界、恢復］ | ［test 檔］ |

## RoomPilot 契約 Gate

- [ ] 格局辨識輸出仍為 `layout_json`；方案生成／編輯輸出仍為 `scene_json`。
- [ ] 跨模組長度與座標使用 cm；新欄位用 `_cm`，面積用 `_m2`。
- [ ] RAG 只提供檢索、排序與證據；幾何合法性只由 `backend/engine/` 判定。
- [ ] 第 6 步正式家具遵守 PostgreSQL active catalog；家電與 quarantine 不進正式配置。
- [ ] 正式前端仍是 `backend/server/static/`；`frontend3d/` 只在明確原型範圍使用。

## 保存與相容性

- 保存位置／欄位：［project/workflow JSONB、render metadata、其他］
- revision／衝突行為：［例如 409；不適用則說明］
- 舊 schema／reload 行為：［相容、migration、明確不相容］
- 失敗與 fallback：［不得靜默改變正式 provider 或領域演算法］

## 驗證計畫

- Owner 單元測試：［命令／檔案］
- Producer 測試：［命令／檔案］
- Consumer／API／UI 測試：［命令／檔案］
- 手動驗收：［八步中的操作與預期］
- 未驗證風險：［項目與原因］

