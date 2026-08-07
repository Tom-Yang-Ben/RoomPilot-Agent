# UI 規格書 (UI Spec) - 八步工作流主頁（/scene）

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** Bella（`frontend/` 目錄 owner，見 `AGENTS.md` 目錄責任表）
> **回答的問題:** `/scene` 頁有哪些區塊、欄位、狀態、操作與文案？前端不用猜。
> **語域:** L3（工程）
> **實例:** 每頁面一份（`ui_spec-<page>.md`）；本份為八步工作流主頁
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/02_ux_ui/ui_spec.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

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

讓設計師在單一頁面完成八步流程：建立專案 → 上傳平面圖 → 確定尺寸 → 空間與結構 → 需求問卷 → 配置與預覽（2D＋3D）→ 方案鎖定與視角 → AI 渲染與成果包。旅程對應 `ux_research_and_journey.md` §5（同輪產出）。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | `/projects` 專案卡「繼續設計」（帶 `?project_id=`）、首頁 hero「開始設計」（`index.html:43`）；未登入由 `requireSignedIn()` 轉 `/login?next=`（`scene_v2.js:13257`） |
| 出口 | 品牌 logo「離開專案」→ `/`（confirm 後，`scene_v2.js:1161-1177`）；「估」圖示與第 8 步「輸出簡報」→ `/engineering?project_id=`（後者加 `&auto=1`，`engineering_link.js`） |

檔案組成：`scene.html`（1,239 行）＋ `scene_v2.js`（主控，13,259 行）＋ `scene_workflow.js`（步驟狀態機）＋ `engineering_link.js`；three.js 由本機 vendor 載入（`scene.html:1228-1235` importmap → `/static/vendor/three/`，REVISION `'165'`），**不再走 unpkg CDN**（舊文件 2026-07-26 的描述已過時）。

## 2. 版面配置 (Layout)

```text
topbar：logo（離開）｜ 保存狀態 #project-save-status ｜「估」連結 ｜ ↻ 重新開始
rp-progress：8 顆步驟按鈕（nav[data-workflow-count="8"]）
rp-guidance-band：步驟編號 + 一句指引 + #global-status（aria-live）
rp-step-panel × 10（同時只顯示一塊；雙欄「圖面/3D 主區 + 右側控制欄」為主）
dialog × 4：逐房 A/B 選擇、房間 3D 預覽、家具更換、家具型錄
```

**步驟按鈕數以現行 DOM 為準：8 顆**（`scene.html:24-33`，`data-step` 依序為 `project / upload / recognition / space_confirmation / requirements / layout_2d / proposal_review / ai_render`）。內部狀態機是 **11 個步驟**（`scene_workflow.js:4-16` `WORKFLOW_STEPS`），由 `publicWorkflowStep()` 收斂到 8 顆按鈕（`scene_v2.js:377-381`）：`calibration`→`recognition`、`white_model_3d`/`realistic_3d`→`layout_2d`。面板共 10 塊（`recognition` 與 `calibration` 共用 `scale` 面板，`WORKFLOW_PANEL_BY_STEP`）。

## 3. 欄位與元件 (Fields / Components)

逐步驟主要元件（id 取自 `scene.html`；欄位級細節看各步驟 section 原始碼）：

| 步驟（面板） | 主要欄位／元件 | 來源／說明 |
| :--- | :--- | :--- |
| 1 project | `#project-name`（required）、`#project-notes`、`#create-project` | `POST /api/projects`；已載入專案時按鈕文案改「繼續此專案」（`scene_v2.js:1356`） |
| 2 upload | `#floorplan-file`（accept `.dxf,.png,.jpg,.jpeg`）、預覽圖、`#project-floorplan-confirmation` 勾選、`#confirm-upload` | 勾選內容確認前送出鈕 disabled（`scene_v2.js:1578`） |
| 3 scale | 標定舞台 `#floorplan-calibration-stage`（role=application）＋三段任務清單、`#floorplan-scale-cm`（number，min 1，公分）、`#apply-floorplan-calibration` | 兩點拖曳＋輸入實際公分；單位固定公分 |
| 4 space | 房間／結構雙 tab（`data-space-tab`）、結構五類 tab（門/窗/牆/樑/柱）、房間編輯器（`#room-name` select、節點合併/切割）、結構編輯器（尺寸/長度/深度/高度 `_cm` 輸入、開口寬度 slider 30–400）、兩顆確認勾選、`#confirm-space`、尺寸標註審視區 `#space-dimension-review` | 樑柱為手繪標定（設計決策，不是辨識缺口）；完成後顯示尺寸標註圖與 `#confirm-dimensioned-plan` |
| 5 requirements | 初回面談 `#first-meeting-questionnaire`（逐題卡片＋上一題/下一題）；舊三段問卷（profile/rooms/summary）DOM 仍在但 `hidden aria-hidden="true"`（`scene.html:480`） | 完成鍵 `#confirm-requirements` 在隱藏的 legacy 區塊內，由 JS 流程觸發 |
| 6 layout-2d | 方案 A/B 切換、`#layout-room-filter`、2D 舞台（`#layout-furniture-layer`）、家具搜尋、已選家具編輯（寬/深 cm、旋轉、更換、刪除）、`#confirm-layout-2d` | 拖曳貼牆轉正由後端家具引擎判定（前端不自算合法座標） |
| 6 white-model-3d | 3D 檢視器 `#white-model-viewer`、檢視/操作模式切換、走動空間選單、同步 2D 側欄（同步平面/待處理/選取家具三 tab）、外觀鎖定、`#confirm-white-model` | 待處理清單非空時不能進下一步（`scene_v2.js:7669`） |
| 6 realistic-3d | 色卡格 `#style-pack-grid`、牆/地材質與色彩、混搭界線、天花與燈具、`#save-realistic-scene` | 色卡選擇即時同步 3D |
| 7 proposal-review | 三段流程：方案摘要→色卡（radiogroup）→鎖定比較視角；`#proposal-content-confirmed` 勾選、`#lock-master-view`、下載/保存 PNG | 鎖定視角需相機 `position_cm`/`target_cm`/`fov_deg`（§7） |
| 8 ai-render | 三 tab（色卡比較/逐房渲染/成果）、渲染設定 6 選單、`#request-palette-renders`、`#save-room-view`、`#submit-room-renders`、`#export-proposal`（有 `project_id` 才顯示）、`#remote-render-jobs` | 生圖服務狀態列 `#ai-render-provider-state`（`GET /api/render-provider/status`，`scene_v2.js:11300`） |

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 步驟導航 | 8 顆進度鈕 click | `canEnter()` 通過才 `goTo()`；否則 `#global-status` 顯示阻擋文案（§7）。特例：`recognition` 已完成 calibration 時直達 `calibration`；`layout_2d` 可進 `white_model_3d` 時直達 3D 主畫面（`scene_v2.js:12800-12814`） | 登入成員 |
| 自動保存 | 每次確認／編輯後 `scheduleSave()` | `PUT /api/projects/{id}/workflow`；狀態列顯示保存進度（§5） | 專案 owner/editor |
| 離開專案 | logo click | confirm →等待保存序列清空→ `location.assign("/")`；pending 未清則擋下（`scene_v2.js:1161-1177`） | — |
| 重新開始 | `#reset-project` | confirm → 清除本機 workflow 狀態 → `history.replaceState("/scene")` → reload（`scene_v2.js:12815-12820`） | — |
| 輸出簡報 | 第 8 步 `#export-proposal` | 導向 `/engineering?project_id=…&auto=1` 自動跑快照→鎖版→成果包（`engineering_link.js:15-23`） | designer |
| 回上游修改 | 「返回第 4 步修改樑」等 | 下游步驟標 stale 並清資料（`markDownstreamStale`／`invalidateFrom`，`scene_workflow.js:207-219,329-343`） | — |

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案（程式碼實值） |
| :--- | :--- | :--- |
| 初始（無專案） | 只有步驟 1 面板 active | `#project-save-status`＝「尚未建立專案」（`scene.html:16`） |
| 保存中 | 狀態列 | 「正在保存…」（`scene_v2.js:1130`）；離開時「正在完成儲存…」 |
| 保存成功 | 狀態列 | 「已自動保存 · {專案名}」；建立當下「已建立 · {名}」 |
| 保存失敗 | 狀態列＋`#global-status` error | 「保存失敗」＋錯誤訊息（`scene_v2.js:1152-1154`） |
| 步驟完成/當前 | 進度鈕 `is-complete`／`is-active`（`scene_v2.js:1394-1401`） | — |
| 步驟被擋 | `#global-status` error | §7 阻擋文案表 |
| 下游失效（stale） | 完成標記與資料被清，需重走 | 例：「即時寫實方案已修改；請重新保存並鎖定渲染視角。」（`scene_v2.js:1343`） |
| 未保存離頁 | `beforeunload` 攔截（`scene_v2.js:12823-12829`） | 瀏覽器原生提示 |
| 家具來源退化 | 第 6 步頂部 `#furniture-source-notice`（aria-live）顯示候選集失效／退回全型錄的通知（`scene_furniture_offers.js:461-465`） | 由 shortlist 狀態組字 |
| 各步錯誤 | 每面板有專屬 `.rp-field-error[aria-live="polite"]`（project/upload/scale/space/requirements/layout/white-model/proposal/ai-render 各一） | 由對應流程寫入 |

Loading skeleton：無統一 skeleton 元件；3D 檢視器以 `.rp-viewer-status` 文字回報（如「正在準備資料庫家具配置。」）。Permission Denied：非成員打 API 回 404，前端以錯誤文案呈現（無專屬畫面，未查證逐一文案）。

## 6. 互動規格 (Interaction Spec)

| 元素 | 防重複／Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- |
| 自動保存 | 保存序列 `saveSequence` promise 串行；每筆先寫 localStorage pending（`roompilot.pending-save.{projectId}`） | 失敗重試 3 次、退避 180ms×(n+1)（`scene_v2.js:1106-1123`） | 狀態列「保存失敗」＋ error status |
| 斷線恢復 | 載入時 `base_updated_at` 相符才 `replay_pending` 重放；409 直接捨棄 pending 並重新 GET（`scene_v2.js:12914-12941`；`shouldReplayPendingSave`） | — | 捨棄時以伺服器版本為準 |
| `#confirm-upload` | 未勾內容確認即 disabled | — | `#upload-error` |
| `#apply-floorplan-calibration` | 兩點未就緒 disabled；`#floorplan-scale-cm` 選點前 disabled | — | `#scale-error` |
| `#confirm-space` | 房間＋結構＋兩勾選未齊 disabled（`scene_v2.js:3101`） | — | `#space-error` |
| 第 6 步確認 | 待處理（碰撞/淨空/超界/載入失敗）非空時 disabled（`scene_v2.js:7669`） | — | 待處理清單逐項列出 |
| 3D 檢視器 | 家具拖曳落點打 `/api/scene/validate`，前端不自算合法性 | `.rp-viewer-status` | 紅色標示＋待處理 tab 徽章 |
| 身分驗證 | `auth_client.js` fetch 攔截器附 Bearer；401 自動 refresh 一次，失敗轉登入頁 | — | — |

## 7. 驗證規則 (Validation)

步驟完成判準（`scene_workflow.js:159-193` `validCompletion()`）與導航阻擋文案（`scene_v2.js:1489-1503`）：

| 內部步驟 | 完成條件（程式碼） | 被擋時文案 |
| :--- | :--- | :--- |
| project | `name` 非空 | 「請先建立專案。」（擋 upload） |
| upload | `filename` 非空 | 「請先上傳平面圖並確認圖檔內容。」 |
| recognition | `engine === "cody"` 或 `"dxf"` | 「請先完成平面圖辨識。」 |
| calibration | `distanceCm > 0` | 「請先拖曳兩端並確認公分尺度。」 |
| space_confirmation | 房間＋結構＋比例三項皆 `true` | 「請先確認房間與牆、門、窗、樑、柱。」 |
| requirements | `basicConfirmed && roomsResolved` | 「請先完成基本問卷與每一個房間需求。」 |
| layout_2d | `confirmed === true` | 「請先確認 2D 家具尺寸與配置。」 |
| white_model_3d | `confirmed` 且（預期家具數 0 或可見家具數 > 0） | 「請先確認 3D 家具確實可見，並確認指定家具需求。」 |
| realistic_3d | `confirmed === true` | 「請先完成並保存即時寫實方案。」 |
| proposal_review | `confirmed` 且相機 `position_cm[3]`/`target_cm[3]`/`fov_deg > 0` | 「請先在第 7 步確認完整方案、三種候選色卡與比較視角。」 |
| ai_render | `confirmed === true` | —（終點） |

欄位級：`#project-name` required；`#floorplan-scale-cm` number min 1 step 0.1；結構尺寸輸入 min 1 step 1（公分）；開口寬度 slider 30–400 cm。前置依賴只由前端狀態機強制，伺服器端驗步驟名不驗順序（沿用 2026-07-26 版描述，未複核 main.py 該段）。

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** 無統一斷點系統；`site.css` 為逐案 `@media` 取值，桌面優先、未承諾行動裝置（沿用 2026-07-26 版結論；本輪未重新逐條清點）。
- **鍵盤操作:** 未系統性驗證（未查證）；dialog 使用原生 `<dialog>`，Esc 行為依瀏覽器預設。
- **ARIA:** 進度列 `aria-label="空間規劃流程"`；指引帶與各錯誤欄位 `aria-live="polite"`；標定舞台 `role="application"`；色卡 `role="radiogroup"`；tab 群組有 `role="tablist"/"tab"` 與 `aria-selected`。對比與螢幕閱讀器支援未驗證（未查證）。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | **無**（repo 內 `rg -i figma` 零命中，2026-08-07 實測；無設計稿交付） |
| Design Tokens | 無 tokens 檔；樣式為手寫 `site.css`。風格內容資料（6 風格 × 3 色卡）屬設計資料非 tokens，SSOT 見 `docs/contracts/STYLEPACK_RENDERING_CONTRACT.md` |
| 元件對照 | 無元件庫；`scene_*.js` 檔名前綴即模組邊界 |
| 已知限制 | 第 5 步 legacy 問卷 DOM 仍在頁面中（hidden）；`#confirm-requirements` 位於其中，僅由 JS 流程觸發 |

## 10. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應需求 | FR-SCENE-*、FR-FP-*（上傳/辨識/標定）、FR-LAYOUT-*（步驟 4）、FR-CATALOG-*（第 6 步家具）、FR-ENGINE-*（合法性）、FR-RENDER-*（第 7–8 步）——編號以本輪 `../01_requirements/srs.md` 為準（撰寫中，待對齊） |
| 對應情境 | SCN-SCENE-*、SCN-RENDER-*（同上，待對齊） |
| 上游文件 | `ux_research_and_journey.md` §5（旅程）、`information_architecture.md`（頁面清單與路由，均為同輪產出） |
| 對應元件規格 | 無獨立前端技術設計文件於本輪；舊版參考 `docs/vibecoding/02_ux_ui/frontend_technical_design.md`（2026-07-26，部分已過時：unpkg CDN、10 顆按鈕、frontend3d 均與現況不符） |
