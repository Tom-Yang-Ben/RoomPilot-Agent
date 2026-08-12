# UI 規格：第 1 步 建立專案 (UI Spec - Step 1 Project) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-WEB（Bella）＋ PM 三方確認
> **語域:** L3（工程）
> **實例:** 每頁面一份（本份對應 `backend/server/static/scene.html:41` 的 `#project-step` 面板）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。DOM id 與 UI 文案逐字取自 `scene.html`／`scene_v2.js` 實檔；行號隨程式碼演進，衝突時以原始碼為準。

本文件回答：第 1 步面板有哪些欄位、送出後畫面經過哪些狀態、存檔狀態列會顯示什麼字、離開專案時前端怎麼攔截。
本文件**不含**：`POST /api/projects` 與 `PUT /api/projects/{id}/workflow` 的 request／response 形狀（屬 [`openapi-project-workflow-v1.yaml`](../04_design/openapi-project-workflow-v1.yaml)）、快照儲存與樂觀鎖的內部機制（屬 [`ADR-004`](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)）、第 2 步之後的畫面（屬 [`ui_spec-step2-upload.md`](ui_spec-step2-upload.md)）。
要找八步導覽的整體結構去 [`information_architecture.md`](information_architecture.md)；要找使用者旅程去 [`ux_research_and_journey.md`](ux_research_and_journey.md)。

## 目錄

- [1. 頁面目的 (Page Purpose)](#1-頁面目的-page-purpose)
- [2. 版面配置 (Layout)](#2-版面配置-layout)
- [3. 欄位與元件 (Fields / Components)](#3-欄位與元件-fields--components)
- [4. 使用者操作 (Actions)](#4-使用者操作-actions)
- [5. UI 狀態 (States)](#5-ui-狀態-states)
- [6. 互動規格 (Interaction Spec)](#6-互動規格-interaction-spec)
- [7. 驗證規則 (Validation)](#7-驗證規則-validation)
- [8. 響應式與無障礙 (Responsive / A11y)](#8-響應式與無障礙-responsive--a11y)
- [9. 設計交付 (Design Handoff)](#9-設計交付-design-handoff)
- [10. 追溯](#10-追溯)

## 1. 頁面目的 (Page Purpose)

讓屋主替這個空間取名並建立一個可回訪的專案身分，之後每一步的確認結果都掛在這個 `project_id` 下自動保存。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | `/scene` 直接開啟（`state.projectId` 為 null 時 `restoreProject()` 直接 `showStep("project")`，`scene_v2.js:19255-19259`）；`/scene?project_id=<id>` 帶既有專案回訪時不停留在本步 |
| 出口 | 第 2 步 上傳平面圖（`goTo("upload")`，`scene_v2.js:1728`）；離開專案回首頁 `/`（`#exit-project`） |

本步是 `WORKFLOW_STEPS` 的第一個內部步驟 `project`，同時是對外八步導覽的第 1 顆按鈕（`scene_workflow.js:4-16`；`scene.html:23`）。

## 2. 版面配置 (Layout)

```text
header.app-topbar         : #exit-project(品牌/離開) │ #project-save-status │ #reset-project(↻)
nav.rp-progress           : 8 顆步驟按鈕，data-step="project" 帶 is-active
section.rp-guidance-band  : #current-step-number「步驟 1」/ #step-instruction / #global-status
section#project-step      : .rp-simple-step 兩欄
  ├─ 左 .rp-simple-copy   : eyebrow「PROJECT」+ 標題文案 + .rp-project-benefits 三枚標籤
  └─ 右 form#project-form : 表單標題 + #project-name + #project-notes + #project-error + #create-project
```

無 wireframe 檔；以上區塊圖由 `scene.html:10-73` 逐行對照產生。

## 3. 欄位與元件 (Fields / Components)

| 欄位／元件 | 型態 | 來源／去向 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#project-name` | `input[type=text][required]`、`autocomplete="off"` | 送出時 `.trim()` 後寫入建立請求的 `name`；回訪時由 `project.name` 回填（`scene_v2.js:19301`） | placeholder「例如：林宅全室規劃」 |
| `#project-notes` | `textarea[rows=3]` | 送出時 `.trim()` 後寫入 `notes`；回訪時由 `project.notes` 回填（`scene_v2.js:19302`） | placeholder「例如：預計八月底入住」；選填 |
| `#project-error` | `p.rp-field-error`、`aria-live="polite"` | 由 `createProject()` 寫入前端驗證或 `errorMessage(error)` 的結果 | 預設空字串，每次送出先清空 |
| `#create-project` | `button[type=submit].primary-action` | 觸發 `#project-form` 的 submit → `createProject()` | 固定文案「建立專案並繼續」 |
| `#project-save-status` | `span`（位於 topbar，跨全部八步共用） | 由建立、載入、存檔三條路徑改寫 `textContent`，見 §5 | 靜態初值「尚未建立專案」（`scene.html:16`） |
| `#step-instruction` / `#global-status` | 指引帶文字 | `setStatus()` 改寫 `#global-status`（`scene_v2.js:637-640`） | 初值「先建立專案，之後每一次確認都會自動保存」／「請輸入專案名稱。」 |

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 建立專案 | `#project-form` submit（點 `#create-project` 或欄位內 Enter） | `POST /api/projects` → 取得 `project_id` → `history.replaceState` 寫入 `/scene?project_id=<id>` → `workflow.complete("project")` → `scheduleSave("upload")` → `goTo("upload")`（`scene_v2.js:1704-1731`） | 無認證機制；Pilot 全 app 無登入（NFR-019，待 DEC-014 核准） |
| 離開專案回首頁 | `#exit-project` click | 原生 `confirm` →（有未完成存檔時）等 `saveSequence` 完成 → 仍有 pending 則中止並報錯，否則 `location.assign("/")`（`scene_v2.js:1363-1381`） | 同上 |
| 重新開始專案 | `#reset-project` click | 原生 `confirm` → `workflow.reset()` → `replaceState("/scene")` → `location.reload()`；**只清本機流程狀態，不刪伺服器專案**（`scene_v2.js:19160-19164`） | 同上 |
| 直接跳步 | `.rp-progress` 按鈕 | `workflow.canEnter(step)` 不成立時只以 `setStatus(..., "error")` 提示，不換面板（`scene_v2.js:19143-19158`） | 同上 |

## 5. UI 狀態 (States)

`#project-save-status` 的七種文字（四種屬 FR-022 存檔週期，以粗體標示）：

| 狀態 | 呈現位置 | 文案 | 觸發 |
| :--- | :--- | :--- | :--- |
| 未建立（Empty） | `#project-save-status` | `尚未建立專案` | 靜態初值，`scene.html:16` |
| 建立成功 | 同上 | `已建立 · {name}` | `scene_v2.js:1724` |
| 回訪載入成功 | 同上 | `已載入 · {name}` | `scene_v2.js:19303` |
| **存檔中（Loading）** | 同上 | `正在保存…` | `scheduleSave()` 進入佇列時，`scene_v2.js:1332` |
| **已存檔（Success）** | 同上 | `已自動保存 · {name}` | `PUT` 成功，`scene_v2.js:1353` |
| **失敗（Error）** | 同上 ＋ `#global-status`（`data-kind="error"`） | `保存失敗`（狀態列同時顯示 `errorMessage(error)`） | 三次重試皆失敗，`scene_v2.js:1355-1356` |
| **離開前收尾** | 同上 | `正在完成儲存…` | `confirmProjectExit()` 且 `pendingSaveCount > 0`，`scene_v2.js:1368` |

面板層級的錯誤狀態：

| 情境 | 呈現 | 文案 |
| :--- | :--- | :--- |
| 空名稱（前端先擋，FR-001 同一條規則的客戶端鏡像） | `#project-error` ＋ `#project-name` 取得焦點 | `請輸入專案名稱，才能建立專案。`（`scene_v2.js:1708-1710`） |
| 空名稱（伺服器 422 `project_name_required`） | `#project-error` 顯示伺服器 `detail.message` | `請輸入專案名稱。`（`main.py:1786-1794`，附 `focus:"project-name"`；**前端目前未消費 `focus` 欄位——待確認**） |
| 網址帶的 `project_id` 不存在（404 `project_not_found`） | 清除 `state.projectId`、`replaceState("/scene")`、回到第 1 步面板，`#global-status` 標紅 | `原網址的專案無法載入：找不到這個專案，請返回專案列表重新選擇。`（`scene_v2.js:19559-19563`；`main.py:1676-1682`） |
| 專案讀到了但畫面還原失敗 | 停在 `workflow.currentStep`，不退回第 1 步 | `專案資料已載入，但畫面還原失敗：{原因}`（`scene_v2.js:19554-19558`） |
| 離線暫存版本過期被丟棄 | `#global-status` | `已恢復專案「{name}」；較舊的離線暫存未覆蓋目前版本。`（`scene_v2.js:19549-19551`） |

Permission Denied：不適用（Pilot 無認證與角色，`main.py:195-197` 無 auth／CORS／rate limit）。

## 6. 互動規格 (Interaction Spec)

FR-022 雙寫持久化在本頁的可見表現——建立成功後立刻觸發一次 `scheduleSave("upload")`，使用者會看到狀態列由「已建立 · {name}」→「正在保存…」→「已自動保存 · {name}」：

| 元素 | Hover | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `#create-project` | `site.css:14372` 定義 hover 樣式 | **無 disabled 狀態**：送出期間按鈕保持可點，重複點擊會再送一次 `POST` 並建立第二個專案——待確認是否為預期 | 無 spinner；唯一進度線索是 §5 的狀態列 | `#project-error` 顯示訊息，面板不切換 |
| 存檔佇列 | — | — | 所有存檔以單一 `saveSequence` Promise 串鏈，不併發（`scene_v2.js:1285,1330`） | `saveWorkflowRequest()` 重試 3 次、退避 180ms×n（`scene_v2.js:1305-1323`） |
| 重試中 | — | — | — | **UI 上不可辨識**：重試期間狀態列維持「正在保存…」，沒有獨立的「重試中」文案 |

離開攔截兩條路徑：

- **應用內離開**（`#exit-project`）：先 `confirm("要離開目前專案並返回首頁嗎？系統會先完成目前的自動儲存。")`，取消即中止；確認後等待 `saveSequence`，若 `localStorage["roompilot.pending-save.<projectId>"]` 仍在則以 `專案尚未完成保存，請稍後再試。` 中止導頁，成功才設 `projectExitConfirmed = true` 並 `location.assign("/")`。
- **瀏覽器層離開**（關分頁／重整／改網址）：`beforeunload` 在 `projectExitConfirmed` 為 false、且（`pendingSaveCount > 0` 或 localStorage 尚有 pending）時 `preventDefault()` ＋ `returnValue = ""`，由瀏覽器顯示原生離開確認（`scene_v2.js:19167-19172`）。文案由瀏覽器決定，前端無法自訂。

回訪重播：`shouldReplayPendingSave()` 只在 pending 的 `base_updated_at` 與伺服器 `updated_at` 字串完全相同時才重播，否則直接丟棄暫存而非覆蓋伺服器版本（`scene_workflow.js:32-41`；`scene_v2.js:19267-19292`）。

## 7. 驗證規則 (Validation)

| 欄位 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| `#project-name` | HTML `required`（原生阻擋空白提交） | 瀏覽器原生提示，文案依瀏覽器語系 | submit |
| `#project-name` | `.trim()` 後不得為空（純空白字元視同空值） | `請輸入專案名稱，才能建立專案。` | submit，前端先判 |
| `#project-name` | 伺服器 `str(payload.get("name") or "").strip()` 為空 → 422 `project_name_required` | `請輸入專案名稱。` | 送出後（前端已擋，屬防繞過的第二道） |
| `#project-notes` | 無必填、無格式限制，`.trim()` 後送出 | — | submit |
| 兩欄位長度上限 | 前端無 `maxlength`，`create_project()` 也未截斷；NFR-005 的 512 字元壓縮只作用於 workflow 快照內的顯示字串，不涵蓋 `projects.name`／`notes` 欄位（`project_store.py:40-74,165-178`） | — | **待確認**：是否需要為名稱／備註設上限 |

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為**（`site.css:14209-14660`）：≥901px 為左文案／右表單雙欄（`minmax(0,0.96fr) minmax(420px,1.04fr)`）；≤900px 收窄為 `0.9fr / 1.1fr`；≤820px 改為單欄 `1fr` 並縮小圓角與內距；≤520px 進一步壓縮內距與標題級數；另有 `max-height:780px and min-width:821px` 的矮螢幕微調。
- **鍵盤操作**：`#project-name` → `#project-notes` → `#create-project` 依 DOM 順序 Tab；表單內 Enter 由原生 submit 行為觸發 `createProject()`。**未實作自訂 Escape／焦點陷阱**；錯誤時僅 `#project-name.focus()` 一處程式化移動焦點。
- **ARIA**：`#project-error` 帶 `aria-live="polite"`、指引帶 `section.rp-guidance-band` 帶 `aria-live="polite"`、`#exit-project` 與 `#reset-project` 各有 `aria-label`、`.rp-project-benefits` 帶 `aria-label="專案功能"`。
- **未驗證項（待確認）**：`#project-save-status` 無 `aria-live`，狀態變更不會被螢幕閱讀器播報；色彩對比（如 `#d7cab9` 底色區塊）未實測，無 WCAG 稽核紀錄；無 skip link。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | **無 Figma 來源，規格以現行 DOM 為準**（`backend/server/static/scene.html:41-73` 與 `site.css:14209-14660`） |
| Design Tokens | 無 token 檔；樣式為 `site.css` 內硬編碼色值與 `clamp()` 尺寸 |
| 元件對照 | 無元件庫；正式前端為香草 JS 單頁，DOM id 直接對應 `scene_v2.js:332-336` 的 `element` 快取 |
| 已知限制 | 送出中按鈕不 disable（§6）；重試中無獨立文案（§6）；伺服器回傳的 `focus` 欄位未被消費（§5）；`site.css` 以 `?v=sha256-<前12碼>` 查詢字串做快取破壞，改樣式須同步更新雜湊（NFR-021） |

## 10. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-002（可保存、可恢復的專案身分，待 owner 核准） |
| 對應功能需求 | FR-001（建立與 422 空名稱）、FR-002（讀取與 404）、FR-022（雙寫持久化與離開攔截）、FR-020（八步導覽折疊） |
| 對應非功能需求 | NFR-005（顯示字串防爆）、NFR-019（無認證邊界）、NFR-021（靜態資產快取雜湊） |
| 對應驗收條件 | ACPT-001、ACPT-020 |
| 對應情境 | SCN-001 |
| 對應架構決策 | [ADR-004](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md)、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md) |
| 對應規格與測試 | [srs.md](../01_requirements/srs.md)、[openapi-project-workflow-v1.yaml](../04_design/openapi-project-workflow-v1.yaml)、[test_plan.md](../05_qa/test_plan.md)（TC-001、TC-020）、[runbook-workflow-save-conflict-or-oversize.md](../06_ops/runbook-workflow-save-conflict-or-oversize.md) |
| 待確認項 | OPEN-14（一般存檔不帶 `expected_revision`，等同 last-write-wins，影響本頁「已自動保存」的實際保證強度） |
| 元件規格位置 | 無獨立元件庫；以 `backend/server/static/scene.html`、`scene_v2.js`、`site.css` 為準 |
