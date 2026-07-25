# 流程 6：需求問卷

## 功能定位

流程 6 將設計師與客戶的訪談結果整理成可供家具配置、風險提醒與後續 RAG 使用的結構化需求。

進入頁面時必須先顯示：

> 目前只選擇格局；色卡與風格尚未定義。

本階段不決定最終風格；對照圖使用穩定的 `imageKey`。目前 86 個 A／B 端點已有 16 個 `ready`（客廳 12、廚房 2、浴室 2），其餘維持 `pending_discussion` placeholder，不能假裝已完成。

## 兩種填寫方式

### 設計師與客戶一起填

入口為既有 `/scene?project_id={project_id}` 的流程 6。

功能包含：

- 全屋基本問卷，每題都有快速選項與該題專屬例句。
- 逐房間多軸對比，不把一個房間簡化成單一選擇。每一軸第一排固定呈現有圖的選項 A／B，第二排才是「偏重 A／兩者平衡／偏重 B」。
- 真正互斥的題目（例如開放式或封閉式廚房）只允許 A／B，不顯示「兩者平衡」。
- 每一軸可展開「補充我的想法」，範例只作為 placeholder，不算答案；使用者可記錄未被 A／B 涵蓋的實際做法，供設計師與 Agent 納入需求。
- 基本問卷與逐房選擇都採一次一題的卡片式流程，顯示目前題號，提供上一題與下一題。
- 必填題沒有答案時停留在原題，不讓使用者帶著空值往後。
- 每個房間都有天花板與燈光題；冷氣只出現在客廳、臥室與餐廳等可居住空間。
- 設計師先設定最低完成淨高；天花選擇估算後若低於該值，系統直接阻擋繼續，並顯示估算完成淨高與門檻。
- 切換房間時保留尚未確認的草稿，客戶邀請頁也會依序自動保存；回到該房間或重新整理後可繼續填寫，草稿不會被視為已完成。
- 家具採單一核取卡介面，不重複顯示另一組下拉多選。
- 隨機靈感只填入畫面，不會在設計師確認前寫入正式需求。
- 可跳過、維持現況、複製已完成房間後修改。
- 可快速跳到下一個未完成項目。
- 設計師專案筆記不限制字數，且不會自動當成正式需求。
- 拆牆、瓦斯、水電與排煙等警示以 `1/3`、`2/3` 方式逐則顯示，並提供上一則、下一則。
- 同一套逐則警示也顯示在客戶邀請頁；偏重 A／B 代表仍保留另一端機能，因此會合併兩端的安全風險。
- 客戶邀請頁也可填牆面、地板、家具材質與特殊切割偏好。

### 客戶透過邀請連結填

設計師在流程 6 按「建立客戶問卷連結」，系統會產生：

`/questionnaire/{invite_token}`

此頁只可讀取房間與需求問卷，並且只可更新該專案的 `requirements`。頁面只取得 token 範圍的平面圖預覽與房間定位多邊形，不提供可編輯的完整平面圖結構、家具配置、3D 或其他設計師工作流程。

邀請 API 不回傳專案 ID、設計師筆記或內部 `clientBrief`。寫入時只接受問卷白名單欄位，會驗證選項、保留設計師擁有的欄位，並以 `updated_at` 做版本衝突檢查，避免設計師與客戶同時修改時互相覆蓋。
當客戶端提交 `basicConfirmed` 或房間 `confirmed` 時，API 會重新檢查全部必填題、用途、房間軸與最低完成淨高；直接繞過前端送出不完整資料會得到 `422`，不能被標成完成。

API：

- `POST /api/projects/{project_id}/questionnaire-invite`
- `DELETE /api/projects/{project_id}/questionnaire-invites`
- `GET /api/questionnaire/{invite_token}`
- `PUT /api/questionnaire/{invite_token}`

## 問卷資料

問卷定義與轉換函式位於：

- `backend/server/static/scene_requirements.js`

主要欄位：

- `schemaVersion: "3.0"`
- `schema_version`
- `basic`
- `rooms`
- `keepExistingRoomIds`
- `mode`
- `designerNotes`
- `clientBrief`

`clientBrief` 是後續 Agent、RAG 與家具引擎的主要交接資料，包含：

- 居住成員與生活型態
- 未來家庭變化
- 各房間的使用、家具、格局軸與素材偏好
- 牆體改動策略
- 風險提醒
- 專案限定、不用於訓練的隱私聲明
- 各選擇軸的 A／B 端點、偏重值、選擇理由與補充想法

設計師頁另提供「查看完整問卷 JSON」與「下載問卷 JSON」。完整文件由
`buildQuestionnaireDocument()` 即時計算，不保存一份可能過期的副本。其欄位包括：

- `document_type: "roompilot.requirements_questionnaire"`
- `schema_version`
- `project_id`
- `basic_questions`：題目 ID、顯示文字、所選值、所選文字與補充
- `rooms[].axes`：選擇軸 ID、題目、答案文字、`image_key`、圖片狀態、補充、風險標籤及全部 `available_options`
- `rooms[].uses`、`furniture`、`material_preferences`
- `rooms[].material_preferences.available_*_options`：材質顯示文字、穩定值與圖片 key
- `image_assets.required_image_keys` 與 `selected_image_keys`
- `client_brief`：給 Agent、RAG 與家具引擎的精簡執行資料

`image_assets.status` 與每個軸的 `image_status` 依 runtime catalog 計算為
`ready`、`partially_ready` 或 `pending_discussion`。新增圖片後重建 catalog 即可，
不更改問卷答案契約。

無論最後由設計師頁或客戶邀請頁保存，`clientBrief` 都維持相同欄位契約，包括 `material_preferences.status`、`structure_strategy` 與編號後的 `warnings`。

## 圖片接口

每個問卷選項已有唯一 `imageKey`。目前 manifest 共 334 個不重複欄位：

- 86 個格局、機能、天花、冷氣與燈光 A／B 對照端點。
- 248 個牆面、地板、家具、色彩與表面光澤選項。

目前已完成 16／86 個 A／B 端點；素材資料庫位於
問卷圖片資產此次不同步；網站沿用遠端 `bella` 既有的視覺題庫與圖片服務。

尚未完成的端點，UI 必須顯示「對照圖待後續確認」，不可用錯誤照片假裝完成。

後續圖片素材確認後，只要建立 `imageKey → asset URL + metadata` 的素材索引，不需重寫問卷答案或 API 契約。

## 驗證

主要測試：

- `tests/test_questionnaire_architecture.py`
- `tests/test_project_workflow_api.py`
- `tests/test_scene_workflow.py`
- `tests/test_scene_v2_contract.py`

## 聚焦版介面與房間定位

- 設計師端一次只展開一題，將專案管理、JSON 與房間快捷工具收進可展開區塊。
- 設計師端左側與客戶邀請版上方都固定顯示「現在討論的房間」，並以原始平面圖作為定位底圖。
- 目前房間使用藍色範圍高亮，其他房間使用淡綠色提示；圖上直接顯示房間名稱。
- 點擊平面圖中的其他房間，會同步切換目前房間、題目與草稿；鍵盤 Enter／Space 亦可操作。
- 全屋基本問卷階段不顯示房間定位圖，進入逐房問卷後才顯示，避免造成錯誤脈絡。
- 驗收同時包含 DOM／CSS 契約測試與真實瀏覽器點擊測試；SVG 必須可接收指標事件。
- 空間用途與家具題皆有附範例的選填補充欄，分別保存為 `stageNotes.uses` 與 `stageNotes.furniture`，供 RAG／Agent 判讀未列入快選的需求。
- 客戶邀請連結只透過 token 範圍讀取平面圖，預設七天到期，設計師可撤銷；一般專案儲存會檢查版本，避免覆寫客戶剛提交的答案。
- 若客戶與設計師同時修改，設計師草稿會保留在本機，畫面只在衝突時提供「合併並保留我的編輯」與「採用客戶最新版本」。合併採基準版本、設計師草稿與客戶最新版本的三方比較，只套用設計師實際改動的欄位；未選擇前不會丟棄草稿。
- DXF 客戶問卷會使用 token 範圍的 SVG 預覽；PNG／JPG／DXF 均可顯示同一套房間定位提示。
- 流程 5 會先把 DXF 中心原點資料正規化為左下原點；邀請頁明確接收 `coordinate_space: "lower_left_m"`，高亮多邊形與 SVG 底圖不再重複平移。

瀏覽器驗收路徑：

1. 完成基本問卷。
2. 確認一般房間每一軸先顯示 A／B 圖卡，再顯示偏重 A／平衡／偏重 B；「補充我的想法」預設收合，範例僅為 placeholder。
3. 確認臥室文案為「舒適休息、空間寬鬆」，不出現「留白睡眠」。
4. 廚房開放／封閉題只有 A／B；選擇開放式後，確認立即出現拆牆、瓦斯、排煙等逐則提醒。
5. 將天花選擇調到會低於設計師最低完成淨高，確認無法前往下一題。
6. 另一房間使用「維持現況」。
7. 確認進度完成並產生 2D 家具配置。
8. 建立客戶邀請連結，確認客戶頁沒有設計師工作流程，且既有答案可載入與保存。
9. 確認設計師頁與客戶邀請頁一次只顯示一題，上一題、下一題與必填阻擋可用。
10. 展開完整問卷 JSON，確認包含答案文字、`imageKey`、素材偏好、選擇理由與 `clientBrief`。
11. 在未完成房間選一個答案後切換房間，再切回原房間，確認草稿仍在且未被誤標為已完成。
