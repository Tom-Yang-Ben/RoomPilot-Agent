# RoomPilot 瀏覽器 E2E Gate

## 目的

這個 Gate 用真實 Chrome 驗證 `floor04.png` 專案從 Step 6「需求問卷」
進入 Step 7「方案工作台」的主要操作。它用來阻擋問卷、材質選擇或方案工作台
已經無法操作的版本進入 `bella`。

目前正式流程共有 11 步，但這支 Gate 的範圍只有 Step 6 → Step 7。其他步驟
必須由各自的契約測試、API 測試或後續新增的瀏覽器 Gate 驗證，不得把本文件
解讀成完整 11 步皆已通過瀏覽器驗收。

## CI 執行方式

GitHub Actions 在每次 `push` 與 `pull_request` 執行：

```bash
uv sync --extra server --extra e2e
uv run pytest tests/test_browser_step6_step7_e2e.py -q
```

CI 設定檔：

```text
.github/workflows/browser-e2e.yml
```

測試固定使用：

```text
testdata/png/floor04.png
```

不得再以 630 cm 舊圖或網頁上的測試快捷鍵取代 `floor04.png`。

## 通過條件

測試必須在真實 Chrome 中完成以下行為：

1. 建立並載入一個以 `floor04.png` 為基礎的專案。
2. Step 6 能逐房回答 A／B 題目，答案切換後仍正確保存。
3. 天花板、冷氣與燈光選項能保存到對應房間。
4. 未完成房間時不得把整份問卷標示為完成。
5. 完成逐房需求後，進入 Step 6 最後的材質與風格區。
6. 顯示 6 個風格家族，且所選家族提供 3 個風格方向。
7. 顯示目前房間的平面圖定位。
8. 牆面與地板推薦會依風格切換，並能分頁瀏覽。
9. 牆面、地板、主要材質與第二材質可以分別選取。
10. 材質切割工具可以建立非固定水平／垂直方向的分界。
11. 每個房間必須個別確認，未確認房間不得直接完成。
12. 完成 Step 6 後，Step 7 必須顯示三個方案。
13. Step 7 必須顯示 GLB 搜尋、牆面材質、地板材質、切割材質與第二材質控制。

以上任一操作失敗、元素不存在、狀態未保存或伺服器無法啟動，Gate 都必須失敗。

## 本機執行

PowerShell：

```powershell
$env:ROOMPILOT_BROWSER_E2E = "1"
uv run pytest tests/test_browser_step6_step7_e2e.py -q
```

若缺少依賴，先執行：

```powershell
uv sync --extra server --extra e2e
```

沒有設定 `ROOMPILOT_BROWSER_E2E=1` 時，這支測試會標示為 skipped；不能把 skipped
當成通過。

## 失敗判讀

- `server did not start`：先檢查後端匯入錯誤、埠號與依賴。
- 找不到元素：通常代表 HTML ID、data attribute 或流程顯示條件已改變。
- 等待狀態逾時：檢查前端是否送出請求，以及專案 JSON 是否實際保存。
- 圖片 `naturalWidth` 為 0：圖片路徑不存在或瀏覽器無法載入。
- 推薦清單沒有隨風格改變：檢查材質排序條件與風格 ID。
- 無法進入 Step 7：檢查逐房確認、材質確認與 `requirements` completion payload。

修正測試前應先確認產品規格是否真的改變。不得只刪除 assertion、增加任意等待時間，
或預先寫入完成狀態來讓 Gate 假通過。

## 尚未涵蓋

這支 Gate 目前不驗證：

- Step 1–5 的真實上傳、比例定位、辨識與結構校正完整流程。
- Step 8–11 的 3D 白模、即時寫實、方案鎖定與 AI 渲染。
- RAG、家具 Agent、AWS 素材與 Mac 獨立後端的實際可用性。
- 問卷圖片內容是否符合設計語意。
- 視覺像素比對、無障礙完整稽核或 LLM Judge。

上述能力若要成為 CI 阻擋條件，必須另外建立可重現的 Gate，不能只靠人工截圖或文字報告。
