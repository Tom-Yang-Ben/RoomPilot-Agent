# 12 前端技術規格：［功能／頁面］

## 範圍

| 項目 | 內容 |
|---|---|
| 主要 owner／協作 owner | Bella／［domain owner］ |
| 前端類型 | [ ] `backend/server/static/` production　[ ] `frontend3d/` 次要原型 |
| 輸入 | ［API payload、project/workflow state、assets］ |
| 輸出 | ［UI state、API command、2D/3D render］ |
| 對應 IA／契約 | ［17 文件］／［`docs/contracts/...`］ |

未明確選擇原型時，一律以 `backend/server/static/` 的 HTML/CSS/JavaScript/Three.js 為正式實作；不要自行引入 React、TypeScript、Storybook 或第二個 frontend server。

## 技術分層

| 層 | 現有檔案／元件 | 責任 | 不得承擔 |
|---|---|---|---|
| DOM／視覺 | ［路徑］ | 頁面、提示、操作控制 | 領域合法性 |
| 互動／狀態 | ［路徑］ | step、選取、編輯 command | 私建保存 truth |
| API adapter | ［路徑］ | request/response、錯誤呈現 | 重做 backend algorithm |
| 2D／Three.js | ［路徑］ | scene 呈現、互動投影 | 自行判定合法座標 |

## 資料與契約

| UI 狀態 | API／資料來源 | schema／單位 | 保存時機 | 空／錯誤狀態 |
|---|---|---|---|---|
| ［狀態］ | ［route/model］ | ［version、cm/m2］ | ［時機］ | ［呈現］ |

- [ ] `layout_json` 只用於格局確認；家具方案與編輯使用 `scene_json`。
- [ ] `_cm`／`_m2` 轉換只發生在明確 adapter，不用像素覆蓋正式幾何。
- [ ] Engine failure/reason code 直接呈現，不用前端 fallback 宣告家具合法。
- [ ] Catalog UI 不顯示 inactive、quarantine、未匹配或家電為正式家具。

## 保存與恢復

- URL／project identity：［欄位］
- local UI state：［可丟棄狀態］
- server-persisted state：［project/workflow/scene］
- revision 衝突／reload：［409 與恢復行為］
- cache key／舊 schema：［策略］

## 體驗與品質

- 主要 CTA：［一項］
- Loading／empty／error／blocked：［行為］
- 鍵盤操作與焦點：［行為］
- 色彩對比與文字替代：［標準］
- 大型 GLB／圖片載入失敗：［可恢復提示］
- 效能預算：［可量測指標，不預填虛構門檻］

## 測試與驗證

- JavaScript syntax：［`node --check ...`］
- Contract／workflow tests：［命令］
- 實際瀏覽器 QA：［步驟、viewport、預期］
- 若為 `frontend3d/`：［`npm.cmd ci`、`npm.cmd run build` 結果］
