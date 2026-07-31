# RoomPilot 第 5 步「需求問卷」Design QA

## 比對目標

- Source visual truth：`/Users/yangbenhao/.codex/generated_images/019fa9d2-07aa-74d2-913f-be6f73d0132a/exec-de495c8f-4815-43ff-ab1b-2a2782b6acd0.png`
- Implementation screenshot：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-questionnaire-option1-implementation-final.png`
- Full-view comparison：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-questionnaire-option1-comparison-final.png`
- Focused question comparison：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-questionnaire-option1-focused-comparison.png`
- Responsive fix evidence：`/Users/yangbenhao/.codex/visualizations/2026/07/28/019fa9d2-07aa-74d2-913f-be6f73d0132a/roompilot-questionnaire-option1-tablet-768.png`

## 尺寸、正規化與狀態

- Source pixels：1487 × 1058。
- Browser implementation capture：1425 × 1013；瀏覽器 CSS viewport override 為 1440 × 1024。
- Density normalization：source 與 implementation 等比例重採樣為 1440 × 1024，再放進同一張並排比較圖；沒有裁切主畫面。聚焦比較使用兩張正規化圖相同的 `(275, 135)–(1420, 990)` 題目區域。
- State：正式第 5 步、客廳、生活偏好、第 1 / 15 題，三個房間皆有測試答案，平衡權重為目前狀態，固定操作列可見。
- Responsive states：另以 768 × 1024 與 390 × 844 CSS viewport 驗證房間佇列、三段式導覽、內容區與固定操作列。

## Findings

- 沒有剩餘 P0、P1 或 P2 問題。
- [P3] 選定稿的兩張客廳圖是專為構圖產生的示意圖；正式實作使用題庫既有、可保存且有語意對應的真實參考圖，因此主題與裁切相近，但畫面內容不逐像素相同。
- [P3] 選定稿示範未完成、進行中與已完成三種房間狀態；瀏覽器證據專案的三個房間都已完成，所以證據畫面只顯示已完成狀態。進度列仍依實際答案、家具設備與材質資料動態計算。

## 必要設計面向

- Fonts and typography：延用 RoomPilot 首頁的襯線展示標題與無襯線操作字；題目、房間名稱、段落導覽、進度與輔助文字的尺寸和權重接近視覺稿，桌面、平板與手機沒有截字。動態題目較長時可自然換行。
- Spacing and layout rhythm：桌面保持約 348 px 左側房間佇列與較寬主內容區；三段式導覽、題目、圖片卡、偏好尺度、補充欄及固定操作列有一致間距。平板以下改為橫向房間佇列並把問卷完整下移，避免雙欄擠壓。
- Colors and visual tokens：暖象牙背景、深咖啡主 CTA、墨綠進度與選取狀態、低對比灰棕邊框均對應選定稿；陰影與圓角保持克制，沒有新增裝飾漸層或泛用大圓卡。
- Image quality and asset fidelity：使用正式題庫 1536 × 1024 參考圖，以 `object-fit: cover` 填滿卡片且沒有變形、透明邊或占位圖；品牌 logo 沿用正式資產。沒有用 CSS art、手繪 SVG、emoji 或文字符號替代目標中的可見圖片資產。
- Copy and content：生活偏好、家具與設備、材質與風格三段文案可獨立理解；補充欄、保存提示、上一題與繼續動作清楚。既有家具、冷氣、材質、全屋資料與摘要內容全部保留。
- Icons：品牌 logo 與既有流程圓形步驟標記保持一致；房間狀態與選項 radio 使用簡單幾何狀態，不另造不具功能的圖示。
- States and interactions：已實測房間切換、生活偏好權重選擇、三段式導覽、冷氣與家具段、材質段、完成房間後前往全屋資料、摘要單一展開、返回修改此房與自動保存。
- Accessibility：導覽與摘要使用實際 button，active/expanded 狀態有 `aria-current`、`aria-pressed` 或 `aria-expanded`；textarea、select 與圖片均保留 label/alt，固定操作列不遮住主要控制。Console error 為 0。

## 比對迭代紀錄

1. 第一輪 full-view 比對：桌面構圖、左側房間進度、三段式導覽、雙圖問題、五點權重、補充欄與底部操作列均符合選定稿，沒有 P0/P1；家具與材質仍保留完整功能但改到各自分段。
2. 第一輪 P2：768 px 平板寬度仍使用雙欄，左側房間卡受既有三欄規則影響而互相擠壓，主題圖卡也過窄。修正：把 Step 5 單欄斷點提高至 900 px，平板改為橫向房間佇列，主問卷置於下方，固定操作列維持可見。修正證據：`roompilot-questionnaire-option1-tablet-768.png`。
3. 摘要密度 P2：第一個展開房間仍一次列出 15 項生活偏好，雖然只展開一房，頁面仍偏長。修正：預設顯示前 4 項，其餘放入原生可展開的「查看其餘 N 項偏好」，保留完整檢查能力。瀏覽器驗證同時確認只有一個房間摘要 body 可見。
4. 最終 full-view 與 focused comparison：版面比例、字體層級、色彩、圖片裁切、主 CTA、補充欄及三段式導覽沒有剩餘可執行的 P0/P1/P2。

## Primary interactions tested

- 客廳、餐廳與主臥房間切換，題目標題與房間進度同步更新。
- 生活偏好從「平衡」切到「強偏 A」再切回「平衡」，`aria-pressed` 與自動保存正確。
- 「家具與設備」與「材質與風格」分段切換，冷氣、家具推薦、色卡、牆地材質、天花板、照明與套用範圍仍存在。
- 確認房間後進入全屋資料；確認全屋資料後進入逐房摘要。
- 摘要切換到第二個房間時，第一個房間同步收合；可見摘要 body 數量為 1。
- 「返回修改此房」回到對應房間與生活偏好段落。
- 1440 × 1024、768 × 1024、390 × 844 三種 viewport 均確認導覽與固定操作列可用。
- Console errors checked：0。

## Follow-up Polish

- P3：若題庫日後有更接近選定稿暖色客廳的正式雙圖，可只替換題庫圖片資產，不需更動本次版面或保存契約。
- P3：房間很多時，平板與手機目前使用橫向滑動佇列；未來可補一個「目前房間 x / n」文字提示，但不是本次三房流程的阻擋問題。

final result: passed
