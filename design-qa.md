# RoomPilot 第 4 步「空間與結構」Design QA

## 比對目標

- Source visual truth：`/Users/yangbenhao/.codex/generated_images/019fa9d2-07aa-74d2-913f-be6f73d0132a/exec-1055515d-34e6-4b06-8a33-968b7922530d.png`
- Implementation screenshot：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-space-structure-build/13-final-approved-1440x1024.png`
- Full-view comparison：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-space-structure-build/comparison-final-full.png`
- Focused panel comparison：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-space-structure-build/comparison-final-panel.png`
- Structure review evidence：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-space-structure-build/12-final-structure-1440x1024.png`

## 尺寸與狀態

- Source pixels：1488 × 1058。
- Implementation pixels：1440 × 1024；CSS viewport 1440 × 1024，device pixel ratio 1。
- Normalization：兩張圖以幾乎相同的 1.406:1 比例正規化為 1440 × 1024，再放進同一張並排比對圖；沒有裁切主要內容。
- State：正式第 4 步、房間頁籤、3 個房間、客廳為目前房間、0 / 3 已確認、完成按鈕停用。
- 另於預設 1280 × 720 視窗驗證頁面捲動、底部完成列及較矮桌面視窗。

## Findings

- 沒有剩餘 P0、P1 或 P2 問題。
- [P3] 視覺稿含選取、平移、框選和尺寸顯示圖示；正式產品目前沒有對應的既有操作契約，因此實作保留「查看全部空間」與現有畫布操作，沒有加入假的圖示或無作用按鈕。
- [P3] 視覺稿的房間尺寸較大，實作證據使用 240 × 240 cm 的人工測試房間；這是 QA 測試資料差異，不是版面或契約差異。

## 必要設計面向

- Fonts and typography：延用首頁與選定稿的襯線展示標題，操作文字使用清楚的無襯線字體；標題、進度、欄位、狀態與次要說明的層級一致，沒有截字或異常換行。
- Spacing and layout rhythm：畫布維持主要視覺面積，右欄只展開目前房間，其他房間收為單列佇列；頁籤、目前房間、佇列、更多操作與底部完成列之間有明確間距。1440 × 1024 內可看見主要確認動作與底部狀態。
- Colors and visual tokens：暖白、深墨、木色邊框、柔和陰影與首頁語言一致；主要 CTA 只使用深墨色，停用完成按鈕與停用批次按鈕均降低飽和度，不與目前任務競爭。
- Image quality and asset fidelity：保留真實 RoomPilot logo 與使用者平面圖；沒有新增占位圖、CSS 圖像、手繪 SVG 或假圖示。畫布保持清晰且使用既有 overlay。
- Copy and content：保留「房間／牆門窗樑柱」、命名、面積、尺寸、新增、合併、切割與完成等正式功能文案；說明改為一次只引導一個任務。
- Icons：沒有用文字符號或 CSS 圖形仿造視覺稿圖示；正式頁面沿用現有品牌 logo 與既有結構圖例。
- States and interactions：已實測房間選取、重新命名、稍後處理、確認後自動前往下一間、更多操作展開／收合、房間／結構頁籤切換、停用完成狀態與自動保存。
- Accessibility：目前房間、頁籤、進度、欄位與完成狀態都有語意標籤；按鈕維持實際 button 控制，輸入框保留 label，停用狀態同時使用 `disabled` 與 `aria-disabled`。瀏覽器錯誤紀錄為空。

## 比對迭代紀錄

1. 第一輪 P2：舊版標題工具列的 `display: contents` 規則壓縮房間名稱輸入框。修正為只在引導式卡片內使用獨立 grid，並固定名稱欄與套用按鈕的最小高度。修正證據：`02-guided-review-fixed.png`。
2. 第二輪 P2：完成列與畫布列在較矮視窗中發生重疊。修正 workspace row sizing，並把完成列改為獨立全寬列。修正證據：`07-final-completion-bar.png`。
3. 第三輪 P2：結構頁空狀態的批次確認按鈕仍過度醒目，標題和兩個操作也互相擠壓。修正為兩欄低密度操作列及中性停用色。修正證據：`12-final-structure-1440x1024.png`。
4. 最終比對：目前房間卡、佇列、畫布比例、底部完成列、色彩及主要 CTA 均符合選定稿的層級；沒有剩餘可執行的 P0／P1／P2。

## Primary interactions tested

- 選取三個房間並切換目前房間。
- 修改房間名稱並觸發既有自動保存。
- 「確認並查看下一間」確認目前房間後自動選取下一個未確認房間。
- 「稍後處理」只切換房間，不寫入新的 workflow 欄位。
- 「更多操作」正常展開／收合，既有新增、全部確認、刪除目前房間、合併與切割入口仍存在。
- 切換到牆門窗樑柱，門／窗／牆／樑／柱頁籤及確認勾選保持可用。
- 完成按鈕在房間、結構及兩項確認尚未完成時維持停用。
- Console errors checked：0。

## Follow-up Polish

- P3：若未來正式新增畫布縮放、平移或尺寸顯示功能，可再選定同一套圖示庫補上視覺稿中的工具列；本次不為視覺相似度新增沒有行為的控制。
- P3：保留 860px 與 560px 單欄斷點；本次視覺真值為桌面畫面，因此沒有把行動版截圖列為阻擋條件。

final result: passed
