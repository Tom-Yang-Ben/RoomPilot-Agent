# UI 規格：第 7 步 方案鎖定與視角 (UI Spec - Step 7 Proposal Review) - RoomPilot

> **版本：** v1.0 ｜ **更新：** 2026-08-12 ｜ **狀態：** 草稿（待 owner 核准）
> **Owner:** MOD-WEB owner（Bella）＋ MOD-SRV-RENDER owner（Bella，§7）＋ 產品 owner（每案一次的成本政策，OPEN-17）
> **語域:** L3（工程）——直接寫 DOM id、事件、相機欄位與失敗行為
> **實例:** 八步之一（`ui_spec-step7-proposal-review.md`）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12；行號對應該版

本文件回答：第 7 步畫面由哪些區塊與 DOM 節點組成、逐房相機三元組怎麼產生與鎖定、代表房三張色卡比較圖的觸發與失敗行為、色卡疊層 `#proposal-review-image-stage` 的開關規則、選定色卡後寫到哪裡並如何接到第 8 步。
本文件**不含**：逐房生圖與成果包（見 [ui-spec-step8](ui_spec-step8-ai-render.md)）、A／B 方案產生與家具合法性（見 [ui-spec-step6](ui_spec-step6-layout-2d.md)、[ADR-002](../03_architecture/adr/ADR-002-engine-sole-geometry-authority.md)）、生圖服務治理理由（見 [ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)）。
要找端點契約去 [api-spec](../04_design/api_spec.md) 與 [openapi-render-delivery](../04_design/openapi-render-delivery-v1.yaml)；測試對應去 [test-plan](../05_qa/test_plan.md)；生圖供應者失效處置去 [runbook-genpic-provider-failure](../06_ops/runbook-genpic-provider-failure.md)（RB-002）。

**DOM 權威來源：** 本步的**主要操作面板由 JS 動態注入**——`#proposal-room-view-lock`（`scene_v2.js:17133`–`17160`）與 `#proposal-style-stage`（`:16169`–`16211`）在進入本步時 append 到 `#proposal-review-step .rp-control-pane`。`scene.html:902`–`948` 的靜態骨架有部分節點在現行流程中**不被填值**（見 §3.3）。**本文件一律以執行期 DOM 為準。**

---

## 目錄

- [1. 頁面目的 (Page Purpose)](#1-頁面目的-page-purpose)
- [2. 版面配置 (Layout)](#2-版面配置-layout)
- [3. 欄位與元件 (Fields / Components)](#3-欄位與元件-fields--components)
- [4. 使用者操作 (Actions)](#4-使用者操作-actions)
- [5. UI 狀態 (States)](#5-ui-狀態-states)
- [6. 互動規格 (Interaction Spec)](#6-互動規格-interaction-spec)
- [7. 色卡比較圖整合](#7-色卡比較圖整合)
- [8. 驗證規則 (Validation)](#8-驗證規則-validation)
- [9. 響應式與無障礙 (Responsive / A11y)](#9-響應式與無障礙-responsive--a11y)
- [10. 設計交付 (Design Handoff)](#10-設計交付-design-handoff)
- [11. 追溯](#11-追溯)

## 1. 頁面目的 (Page Purpose)

在已鎖定的家具配置上，替**每個房間**選定並鎖定一組生圖相機（`position_cm`／`target_cm`／`fov_deg`），再對**一間代表房**產出三張色卡比較圖、選定其中一張作為全案色彩基準，然後進入第 8 步逐房生圖。內部 step id 為 `proposal_review`，對外是第 7 步（`scene.html:29`）。使用者旅程節點見 [ux-research](ux_research_and_journey.md)，面板在資訊架構中的位置見 [ia](information_architecture.md)。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 6 步（內部 `realistic_3d`）完成後 `goTo("proposal_review")`（`scene_v2.js:16390`）；或還原專案時 `showStep("proposal_review")` → `prepareProposalReview()`（`scene_v2.js:1579`） |
| 出口 | 第 8 步（`ai_render`）——`#proposal-confirm-render-palette` → `confirmRenderPalette()` → `workflow.complete("proposal_review")` → `goTo("ai_render")`（`scene_v2.js:15793`–`15810`） |
| 回頭 | `#return-to-realistic`「返回第 6 步修改」→ `goTo("realistic_3d")`（`scene.html:937`；`scene_v2.js:18981`） |
| 面板 | `section#proposal-review-step[data-panel="proposal-review"]`（`scene.html:902`）；step→panel 對應 `proposal_review: "proposal-review"`（`scene_workflow.js:28`） |

## 2. 版面配置 (Layout)

```text
#proposal-review-step                              scene.html:902
└─ .rp-3d-workspace（左 3D／右側欄雙欄）
   ├─ .rp-viewer-pane
   │  ├─ .rp-viewer-toolbar
   │  │    [data-proposal-view-mode]=orbit|walk   :907-908
   │  │    #locked-scheme-label                    :910
   │  ├─ #proposal-review-viewer   ← proposalViewer  :912
   │  │  └─ #proposal-review-image-stage（色卡疊層，預設 hidden） :913
   │  │       #proposal-review-image | #proposal-review-image-caption
   │  │       #proposal-review-stage-close | .rp-render-image-hint  :914-917
   │  └─ #proposal-review-status（viewer 狀態列）   :920
   └─ aside.rp-control-pane
      ├─ #proposal-review-summary                   :926   ← 現行流程多半留空，見 §3.3
      ├─ #proposal-palette-grid | #proposal-palette-status :930-931 ← 同上
      ├─ #proposal-content-confirmed                :934   ← 同上
      ├─ #return-to-realistic                       :937
      ├─ #suggest-master-view | #lock-master-view | #master-view-status :942-944
      ├─ [JS 注入] #proposal-room-view-lock          scene_v2.js:17133-17160
      │    #proposal-room-view-list | #proposal-room-view-candidates
      │    #lock-proposal-room-view | #confirm-proposal-room-views
      │    #proposal-room-view-status
      └─ [JS 注入] #proposal-style-stage             scene_v2.js:16169-16211
           #proposal-representative-room | #proposal-representative-context
           #open-palette-render-brief
           #proposal-palette-render-options | #proposal-palette-render-results
           #proposal-confirm-render-palette | #proposal-style-stage-status
```

兩個注入面板是**串接的兩關**：`#proposal-style-stage` 只有在「每一房都有合法的已鎖視角」時才 `hidden=false`（`scene_v2.js:16215`–`16217`）。共用的送出前確認視窗 `#render-brief-dialog` 與第 8 步同一個（`scene.html:998`–`1010`）。

## 3. 欄位與元件 (Fields / Components)

### 3.1 逐房視角（`#proposal-room-view-lock`）

| 元件 | 型態 | 寫入的 state 路徑 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#proposal-room-view-list` | 房間按鈕列 | `state.selectedProposalRoomId` | 每房副標 `已鎖定`／`待確認`，判定用 `validProposalRoomView()`（`scene_v2.js:17173`–`17176`） |
| `#proposal-room-view-candidates` | 三張候選構圖（3D 即時截圖） | `state.selectedProposalRoomCandidateIndex` | 標籤固定「完整主視角／入口對向視角／空間側向視角」（`scene_v2.js:15370`–`15381`）；截圖未就緒顯示佔位（§5） |
| `#lock-proposal-room-view` | 按鈕 | `state.proposalReview.roomViews[roomId] = {room_id, room_label, camera, candidate_index, scene_version, saved_at}` | `camera.preset` 覆寫為 `full-room-v2-locked`（`scene_v2.js:15521`–`15540`） |
| `#confirm-proposal-room-views` | 按鈕 | `state.proposalReview.viewsConfirmedAt` | 通過後 `proposalViewer.lockRenderCamera(true)` 並顯示色卡關卡（`scene_v2.js:17187`–`17200`） |

相機三元組由 `roomCameraForAnchor()` 產生：`camera_type:"perspective"`、`preset:"full-room-v2"`、`position_cm:[x,145,z]`、`target_cm:[x,92,z]`、`up:[0,1,0]`、`fov_deg:72`、`zoom:1`（`scene_v2.js:15340`–`15353`）。三個候選只差 `position_cm` 的房內錨點。座標與高度一律公分（ADR-007）。

### 3.2 色卡比較（`#proposal-style-stage`）

| 元件 | 型態 | 寫入的 state 路徑 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#proposal-representative-room` | `<select>` | `state.proposalReview.representativeRoomId` | 選項＝全部房間；預設取 `selectedProposalRoomId` 或第一房（`scene_v2.js:16219`–`16223`） |
| `#proposal-representative-context` | 唯讀摘要 | — | 顯示問卷摘要、`context.note`、已鎖定家具；無逐房需求時附「本房未填獨立需求，已套用全屋問卷與鎖定配置。」（`scene_v2.js:15615`, `:16225`） |
| `#open-palette-render-brief` | 按鈕 | — | 開 `#render-brief-dialog`；已生成過時 `disabled` 且文字改為「色卡比較圖已生成（每專案限一次）」（`scene_v2.js:16229`–`16235`） |
| `#proposal-palette-render-options` | 三張色卡預覽卡 | — | `paletteChoicesForActiveStyle()` 取**與全屋主風格同 `styleId` 的 3 張**（`scene_v2.js:16911`–`16917`、`:16483`–`16499`）；`STYLE_PACKS` 為 6 風格 × 3 卡（`scene_style_packs.js:13`–`80`, `:301`–`305`） |
| `#proposal-palette-render-results` | 三張生圖結果＋單選 | `radio[name="confirmed-render-style"]` | 圖來源 `state.paletteRenderImages[styleCardId]`（僅記憶體）；缺圖時依狀態顯示佔位文案（§5，`scene_v2.js:15739`–`15767`） |
| `#proposal-confirm-render-palette` | 按鈕 | `state.proposalReview.confirmedStyleCardId`、`styleCardLockedAt`、`masterView.style_card_id` | 有任一 palette job 才顯示（`scene_v2.js:15767`）；成功即完成本步並跳第 8 步 |

### 3.3 靜態骨架中「現行流程不填值」的節點

`prepareProposalReview()`（`scene_v2.js:16807`–`16838`）只呼叫 `renderProposalRoomViewPanel()` 與 `renderProposalStyleStage()`，**不呼叫** `renderProposalSummary()`／`renderProposalPaletteSelection()`。後兩者僅在第 6 步 A／B 方案切換路徑被呼叫（`scene_v2.js:1507`–`1514`）與彼此互叫（`:15119`–`15120`）。因此在正常「6→7」路徑下：

- `#proposal-review-summary`（`scene.html:926`）為空 `<div>`。
- `#proposal-palette-grid`（`:930`）為空 → `selectProposalPalette()` 無從觸發 → `confirmedStyleCardId` 只能由 §3.2 的路徑產生。
- `#proposal-content-confirmed`（`:934`）與 `#suggest-master-view`／`#lock-master-view`（`:942`–`943`）仍綁著 `lockMasterRenderView()`（`scene_v2.js:18965`–`18980`），但該函式要求 `confirmedStyleCardId` 已存在（`:15200`–`15202`），在未經 §3.2 之前一律停在「請先選擇一張同風格色卡，作為遠端生圖的色彩基準。」
- `#locked-scheme-label`（`:910`）只由 `renderSchemeControls()` 寫入，且 `designSchemes.locked_scheme_id` 僅在 `lockMasterRenderView()` 設定（`scene_v2.js:4638`–`4642`, `:15223`）；現行主路徑不經該函式，標籤停在「尚未鎖定方案」。

以上屬**現況**，不得在其他文件寫成「已移除」或「已修復」；歸屬見 §11 待確認 1。

## 4. 使用者操作 (Actions)

| 操作 | 觸發元素 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 切換觀看模式 | `[data-proposal-view-mode]`（`scene.html:907`–`908`） | `lockRenderCamera(false)` ＋ `setViewMode("orbit"\|"walk")`（`scene_v2.js:18960`–`18964`） | 無角色控制（Pilot 全 app 無認證，NFR-019） |
| 選房 | `#proposal-room-view-list [data-proposal-room]` | `selectProposalRoomView()`：載入已鎖相機或候選 0（`scene_v2.js:15489`–`15506`） | 同上 |
| 選候選構圖 | `[data-proposal-room-candidate]` | `selectProposalRoomCandidate()` 直接把相機切到該候選（`:15509`–`15519`） | 同上 |
| 微調視角 | 在 `#proposal-review-viewer` 內拖曳 | 未鎖定時可自由轉動；鎖定後 `lockRenderCamera(true)` | 同上 |
| 鎖定本房視角 | `#lock-proposal-room-view` | 寫入 `roomViews[roomId]`＋`refreshConfigurationSnapshot()`＋`scheduleSave("proposal_review")`（`:15521`–`15540`） | 同上 |
| 完成全部視角 | `#confirm-proposal-room-views` | 缺房時跳到第一個缺的房並提示；全齊則鎖相機並展開色卡關卡（`:17187`–`17200`） | 同上 |
| 換代表房 | `#proposal-representative-room` | 改 `representativeRoomId` 並重繪（`:16195`–`16199`） | 同上 |
| 產生三張色卡 | `#open-palette-render-brief` → `#render-brief-confirm` | `openRenderBriefDialog("palette_comparison")` → `requestPaletteRenders(brief)`（`:16205`, `:15964`–`15977`） | 同上 |
| 放大色卡圖 | 點 `#proposal-palette-render-results` 內的 `<img>` | `showProposalPaletteImageEnlarged()` 開啟 `#proposal-review-image-stage`（`:16207`–`16210`, `:17417`–`17427`） | 同上 |
| 關閉疊層 | 疊層任一處、`#proposal-review-stage-close`、Enter／Space／Esc | `closeProposalPaletteImageStage()`（`:19024`–`19029`） | 同上 |
| 選定色卡並進入第 8 步 | `#proposal-confirm-render-palette` | `confirmRenderPalette()`（見 §8）→ `seedRepresentativeRoomRenderFromPalette()` → `goTo("ai_render")`（`:15770`–`15810`） | 同上 |
| 返回第 6 步 | `#return-to-realistic` | `goTo("realistic_3d")`；第 6 步再編輯會清空 `proposalReview` 並作廢本步（`:1381`–`1392`, `:1522`–`1533`） | 同上 |

**A／B 方案在本步不可切換**：`[data-design-scheme]` 在 `currentStep` 為 `proposal_review`／`ai_render` 時直接回「方案已於第 6 步選定；要更換 A/B 請先返回第 6 步。」（`scene_v2.js:18486`–`18491`）。

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案（原文） |
| :--- | :--- | :--- |
| Loading（首次載入 3D） | 全畫面遮罩 `#placement-busy`（`scene_v2.js:1545`） | 遮罩「正在準備第 7 步 3D 場景，請稍候…」；`#master-view-status`「場景還在準備中，請稍候…」（`:17348`–`17349`） |
| Success（場景就緒） | 遮罩收起，可操作 | 「場景已就緒；請核對方案並鎖定比較視角。」（`:17356`） |
| Error（3D 載入失敗） | `#master-view-status` ＋ 全域 `setStatus(..., "error")` | 「3D 場景載入失敗：<原因>。請返回第 6 步重新確認方案後再進入。」／「第 7 步 3D 場景載入失敗，請返回第 6 步重新確認。」（`:17361`–`17363`） |
| Empty（無場景） | 不渲染面板 | 「尚未有可用的 3D 場景，請返回第 6 步確認方案後再進入。」（`:16808`–`16810`） |
| 候選構圖產生中 | 佔位方塊 | 「正在建立 3D 預覽」（`:17181`） |
| 逐房進度 | `#proposal-room-view-status` | 「<房名>：確認畫面能看見完整空間後儲存。已完成 N / M 間。」（`:17183`–`17184`） |
| 逐房未齊 | 同上 | 「請先確認 <房名、房名> 的視角。」（`:17191`–`17192`） |
| 色卡未生成 | `#proposal-style-stage-status` | 「請先產生代表房的 3 張色卡比較圖，再選一張確定。」（`:16238`–`16240`） |
| 色卡生成中 | 同上 | 「正在為「<代表房>」一次送出 3 張色卡比較圖…」（`:16719`） |
| 色卡生成完成 | 同上 | 「已為代表房一次產生 N 張色卡比較圖；選一張後確定進入第 8 步（每專案只生一次）。」（`:16740`） |
| 色卡全部失敗 | 同上；`paletteGenerated` **不**設為 true | 「色卡比較圖生成失敗，請稍後再試。」（`:16741`） |
| 已生成過（409／重整後） | 產圖鈕 disabled | 「此專案的色卡比較圖已生成過，每個專案只能生成一次。」（`:16712`, `:16748`） |
| 已生成但圖不在（重整） | 結果卡顯示佔位 | 「已生成（重新整理後不保留預覽）」；其他狀態為「生成失敗」／「等待生成」（`:15749`–`15753`） |
| 色卡未選即確定 | `#proposal-style-stage-status` ＋ `#ai-render-status` | 「請先從 3 張生圖中選擇 1 張色卡。」（`:15775`） |
| 視角資料不完整 | 同上 | 「第 7 步視角資料尚未完整，請重新確認逐房視角後再選色卡。」（`:15798`） |
| Permission Denied | 不適用（Pilot 全 app 無認證與角色，NFR-019；服務邊界待 DEC-014 核准） | — |

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover／選取 | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `#proposal-room-view-list button` | 當前房 `.is-active`（`scene_v2.js:17175`） | — | — | — |
| `[data-proposal-room-candidate]` | 當前候選 `.is-active`；`.rp-view-candidate-list > button.is-active` 有獨立描邊（`site.css:7117`–`7122`） | — | 佔位「正在建立 3D 預覽」；截圖以 `scene_version + room.id` 為鍵快取（`scene_v2.js:15383`–`15406`） | 截圖例外時刪除快取鍵，下次重試（`:15398`–`15400`） |
| `#confirm-proposal-room-views` | — | 不 disable | — | 缺房時只提示並跳到缺的房，不前進 |
| `#open-palette-render-brief` | — | `state.proposalReview.paletteGenerated === true` 時 disabled（`:16230`–`16235`） | 送出期間狀態列顯示「正在為…送出」 | 409 時把 `paletteGenerated` 設 true 並重繪，**不視為錯誤**（`:16744`–`16750`） |
| `#proposal-style-stage` 整段 | — | 未完成逐房視角時整段 `hidden`（`:16215`–`16217`） | — | — |
| `#proposal-confirm-render-palette` | 選中的 radio `checked` | 無 palette job 時 `hidden`（`:15767`） | — | 未選色卡或工作流未過閘一律只寫狀態列，不前進 |
| `#proposal-review-image-stage` | `cursor:pointer`，覆蓋整個 viewer（`site.css:13724`–`13733`） | — | — | 點任一處（含關閉鈕）或 Enter／Space／Esc 關閉（`scene_v2.js:19024`–`19029`） |
| `#render-brief-dialog` | 原生 `<dialog>`，`showModal()` | — | — | 描述疑似改格局時先出警語，再按一次才送（`:15966`–`15971`） |

**兩套疊層彼此獨立**：第 7 步 `#proposal-review-image-stage` 只由 `showProposalPaletteImageEnlarged()`／`closeProposalPaletteImageStage()` 控制、無 gallery 模式、無 `state` 旗標；第 8 步 `#ai-render-image-stage` 由 `updateAiRenderImageStage()` 依 `renderStageView` 走 `single`／`gallery` 兩模式（`scene_v2.js:17417`–`17431` vs `:17447`–`17494`；`scene.html:913` vs `:958`）。兩者掛在不同 viewer、不同 panel，不得合併敘述（FR-025）。

## 7. 色卡比較圖整合

| 項目 | 行為 | 證據 |
| :--- | :--- | :--- |
| 觸發 | `#open-palette-render-brief` → 確認視窗 → `requestPaletteRenders(brief)`；前置需代表房、該房已鎖視角、3 張色卡皆備 | `scene_v2.js:16700`–`16709` |
| 參考圖 | 把相機切到該房已鎖 `camera` 後 `proposalViewer.capturePng()`，作為 img2img 參考鎖住家具與格局 | `scene_v2.js:16716`–`16717` |
| 請求 | `POST /api/projects/{id}/palette-renders`，body `{project_id, scene, room:{room_id, room_label, reference_png_data_url, note}, style_card_ids[]}` | `scene_v2.js:16720`–`16734` |
| 伺服器端併發 | 同一代表房 × N 張色卡，執行緒池 `max_workers=len(ids)` 一次送出；每執行緒各自 agent／`SceneDoc`，僅共用無狀態 gateway | `ai_render_service.py:432`–`488` |
| 每案一次 | `workflow.palette_render.generated` 為真即 409 `palette_already_generated`，不再呼叫模型 | `main.py:2148`–`2156` |
| 全失敗不鎖定 | 無任何 `status=="completed"` 時直接回結果、**不寫 workflow**，可重試 | `main.py:2191`–`2199`；前端 `scene_v2.js:16775`–`16778` |
| 成功即鎖定 | 有任一張成功才 `update_workflow({palette_render:{generated:true, room_id, cards[]}})`，**只存 id 與狀態，不存 base64**（NFR-001 的 2 MB 上限） | `main.py:2200`–`2214`；`scene_v2.js:242`–`253`, `:16759`–`16770` |
| 未設定金鑰 | `AiRenderNotConfigured` → 503「尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。」 | `main.py:2181`–`2190` |
| 單張失敗 | 只該張 `status:"failed"` 並帶 `notices`，其餘照常回傳 | `ai_render_service.py:470`–`483` |
| 選定色卡的落點 | `state.proposalReview.confirmedStyleCardId` → `masterView.style_card_id`；配置快照另存 `selected_style_card_id` | `scene_v2.js:15782`–`15788`, `:3762`–`3763` |
| 套 STYLE_PACK | 寫實化由第 6 步的 `applyStylePackToScene()`／`confirmWhiteModel()` 寫 `scene.style`、`scene.style_card`、`design_choices.*`；第 7 步的選擇在**送第 8 步時**才由 `aiRenderSceneForBrief()` 合成 `design_choices.style_card_id` 與 `style_card` | `scene_v2.js:14024`–`14036`, `:14447`–`14477`, `:16927`–`16951` |
| 伺服器端讀取 | 生圖服務取 `scene.style_card.card_id`，缺值才退到 `design_choices.style_card_id` | `ai_render_service.py:222`–`228` |
| 少生一張 | 選定色卡那張圖直接塞進 `finalRooms[代表房]` 當第 8 步初稿（`reused_from_palette:true`，無 lock manifest 故改圖需整房重生） | `scene_v2.js:15813`–`15834` |

## 8. 驗證規則 (Validation)

| 對象 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| 逐房視角有效性 | `validProposalRoomView()`：`saved.room_id` 與房相符、`camera.preset` 以 `full-room-v2` 開頭、`target_cm` 落在該房多邊形內 | 該房顯示「待確認」 | 每次 render（`scene_v2.js:15479`–`15487`, `:15361`–`15367`） |
| 全房視角齊備 | 任一房 `validProposalRoomView()` 為 null 即不得進色卡關卡 | 「請先確認 <房名> 的視角。」 | `#confirm-proposal-room-views`（`:17187`–`17193`） |
| 前進閘門（本步完成） | `validCompletion("proposal_review")`：`confirmed===true` 且 `masterView.camera.position_cm` 長度 3、`target_cm` 長度 3、`fov_deg>0` | 「第 7 步視角資料尚未完整，請重新確認逐房視角後再選色卡。」 | `workflow.complete()`（`scene_workflow.js:150`–`157`） |
| 前進閘門（可進第 8 步） | `REQUIRED_COMPLETIONS.ai_render` 要求前十個內部步驟全部完成 | 「請先在第 7 步確認完整方案、三種候選色卡與比較視角。」 | `canEnter()`（`scene_workflow.js:93`–`104`；`scene_v2.js:1699`） |
| 色卡必選 | `input[name="confirmed-render-style"]:checked` 必須有值 | 「請先從 3 張生圖中選擇 1 張色卡。」 | `#proposal-confirm-render-palette`（`scene_v2.js:15770`–`15779`） |
| 色卡每案一次 | 前端 `paletteGenerated` 先擋，後端 `palette_render.generated` 再擋（409） | 「此專案的代表房色卡比較圖已生成過，每個專案只能生成一次。」 | 送出前與端點（`scene_v2.js:16710`–`16714`；`main.py:2148`–`2156`） |
| 請求完整性 | 專案不符 422 `render_project_mismatch`；缺場景 422 `scene_required`；缺代表房 422 `room_required`；參考圖非 PNG data URL 422 `reference_png_required`；色卡清單空 422 `style_card_ids_required` | 各附中文 message | 端點入口（`main.py:2143`–`2180`） |
| 生圖描述不得改格局 | `renderBriefHasSpatialConflict(notes)` 命中時先出警語，需再按一次才送 | 「偵測到可能改變格局、門窗、家具位置或空間大小的描述。…再次按確認即可送出。」 | `#render-brief-confirm`（`scene_v2.js:15966`–`15971`） |
| 上游變更作廢本步 | 第 6 步再編輯 → `markRealisticSceneEdited()` 清空 `proposalReview` 並 `invalidateFrom("realistic_3d")` | 「即時寫實方案已修改；請重新保存並鎖定渲染視角。」 | `scene_v2.js:1522`–`1533`, `:1381`–`1392` |

**幾何與合法性不在本步重算**：本步只決定相機與色彩，家具座標與合法性一律由 `backend/engine/` 在第 6 步裁定（ADR-002）；場景以 `currentSceneVersion()` 為鍵快取，同版本切色卡不重載 3D（`scene_v2.js:15080`–`15087`, `:17339`–`17370`）。

## 9. 響應式與無障礙 (Responsive / A11y)

- **斷點行為：** `.rp-3d-workspace` 預設 `minmax(0,1fr) 460px`（`site.css:8367`–`8371`）；≤1120 px 側欄縮為 340 px（`:8895`, `:8903`–`8905`）；≤820 px 改單欄（`:8914`, `:8969`–`8971`）。色卡與候選圖以 `width:100%` 與 grid 換行避免撐爆側欄，由 `tests/test_scene_v2_contract.py:94`–`111` 斷言。
- **鍵盤操作：** 房間、候選構圖、鎖定與確認皆為原生 `<button>`；`#proposal-review-image-stage` 為 `role="button" tabindex="0"`，Enter／Space／Esc 皆可關閉（`scene.html:913`；`scene_v2.js:19025`–`19029`）。`#render-brief-dialog` 為原生 `<dialog>`（Esc 關閉為瀏覽器預設行為）。
- **ARIA 現況：** `#proposal-review-viewer[aria-label="方案與渲染比較視角"]`、`#proposal-review-image-stage[aria-label="點擊空白處切回 3D 場景"]`（`scene.html:912`–`913`）；`aria-live="polite"` 用於 `#proposal-review-image-caption`（`scene.html:915`）、`#proposal-palette-status`（`:931`）、`#master-view-status`（`:944`）、`#proposal-room-view-candidates`／`#proposal-room-view-status`（`scene_v2.js:15421`, `:15424`）、`#proposal-style-stage-status`（`:15643`）。
- **未驗證項：** 主狀態列 `#proposal-review-status` **無 `aria-live`**（`scene.html:920`），本步的流程提示與失敗訊息不會被螢幕閱讀器主動播報——與第 6 步 `#white-model-status`、第 8 步 `#ai-render-status` 同屬 `rp-viewer-status` 模式的共同缺口；房間／候選按鈕的 `.is-active` 目前只靠邊框與底色，**無 `aria-current` 或 `aria-pressed`**（`scene_v2.js:17173`–`17181`）；對比度、focus ring、色卡「已選」是否有非色彩替代標示皆無稽核紀錄；WCAG 等級未定，屬 TO-BE。

## 10. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | 無（repo 內查無 Figma 連結或設計稿）——**待確認** |
| Design Tokens | 無獨立 token 檔；本步樣式集中在 `site.css` 的 `.rp-proposal-style-stage`（`:6937`–`7079`）、`.rp-view-candidate-list`（`:7081`–`7127`）、`.rp-render-image-stage`（`:13724`–`13760`） |
| 元件對照 | 無元件庫；DOM id 與 `[data-*]` 選擇器即介面契約，斷言於 `tests/test_scene_v2_contract.py:94`–`143`, `:825`–`843`, `:886`–`895` |
| 快取鍵 | 頁面資產 `?v=sha256-<前 12 碼>` 必須等於實檔雜湊（`tests/test_scene_v2_contract.py:20`–`28`）；本步另有兩個執行期快取鍵——3D 場景 `currentSceneVersion()`、候選截圖 `<scene_version>:full-room-v2:<room_id>`（`scene_v2.js:15080`–`15087`, `:15383`） |
| 已知限制 | §3.3 的靜態骨架殘留；`#palette-render-options`／`#palette-render-results`／`#request-palette-renders`（`scene.html:975`–`978`）是第 8 步的同名舊容器，`element.paletteRenderOptions/paletteRenderResults` 會在注入色卡面板時被改指到第 7 步節點（`scene_v2.js:16191`–`16193`），舊容器維持空白 |

## 11. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-010（先鎖視角、代表房色卡每案一次）——狀態**待 owner 核准** |
| 對應功能需求 | FR-055（逐房相機三元組與 `master_view`）、FR-056（色卡端點與每案一次）、FR-057（選定色卡與 STYLE_PACK）、FR-009（瀏覽器輸出 PNG 上傳）；相關 FR-025（兩套疊層）、FR-024（3D viewer 單一入口） |
| 對應非功能需求 | NFR-001（快照 ≤ 2 MB，故 base64 不入 workflow）、NFR-002（PNG ≤ 20 MB）、NFR-012（生圖重試與失敗政策）、NFR-014（503／502／409 誠實表達）、NFR-017（公分制）、NFR-018（執行緒池併發）、NFR-019（無認證，Pilot 現況） |
| 對應驗收條件 | ACPT-047、ACPT-048、ACPT-049；另涉 ACPT-008、ACPT-023 |
| 對應情境 | SCN-026（逐房鎖定後才可前進）、SCN-027（選定色卡並被告知每案一次）、SCN-028（全失敗可重試） |
| 對應架構決策 | [ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md)、[ADR-007](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)、[ADR-004](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md) |
| 對應模組 | MOD-WEB（`backend/server/static/`）、MOD-SRV-RENDER（`ai_render_service.py`）、MOD-SRV-STORE（`palette_render` 快照） |
| 對應測試 | TC-047、TC-048、TC-049（實測檔：`tests/test_palette_renders_openrouter.py:112`–`227`、`tests/test_scene_v2_contract.py:94`–`143`, `:825`–`843`, `:886`–`895`） |
| 對應 Runbook | RB-002（[runbook-genpic-provider-failure](../06_ops/runbook-genpic-provider-failure.md)） |
| 相鄰步驟 | [ui-spec-step6](ui_spec-step6-layout-2d.md) → 本步 → [ui-spec-step8](ui_spec-step8-ai-render.md) |
| 需求規格 | [srs](../01_requirements/srs.md)、[prd](../01_requirements/prd.md)；端點契約 [api-spec](../04_design/api_spec.md)、[openapi-render-delivery](../04_design/openapi-render-delivery-v1.yaml) |

### 待確認事項

1. **靜態骨架與注入面板並存（§3.3）**：`#proposal-review-summary`、`#proposal-palette-grid`、`#proposal-content-confirmed`、`#lock-master-view`／`#suggest-master-view`、`#locked-scheme-label` 在現行主路徑不被填值或不被走到。是保留給回退路徑、還是應退役的死 DOM？由 MOD-WEB owner 裁定；退役前不得在 UAT 腳本中要求使用者操作這些控制項。
2. **OPEN-18（既有編號）——色卡圖重整後消失但「已產生」狀態仍在**：`paletteGenerated` 於還原時以伺服器 `palette_render.generated` 為準（`scene_v2.js:19469`–`19471`），而 base64 只放 `state.paletteRenderImages` 且還原時清空（`:19472`），結果卡改顯示「已生成（重新整理後不保留預覽）」（`:15749`–`15753`）。**行為與程式碼一致，但是否為預期的使用者體驗待 owner 核准。**
3. **OPEN-17（既有編號）——「每案只做一次」的依據**：程式與畫面只寫規則，未載明是成本控管或產品定案；理由待 owner 追認。
4. **代表房初稿沿用色卡圖後不可改圖**：`reused_from_palette:true` 的房沒有伺服器端 lock manifest，第 8 步改圖須整房重生（`scene_v2.js:15813`–`15828`）。這與 FR-060 的改圖額度口徑（OPEN-16）交互影響，需與第 8 步 owner 一併裁定。
5. **`design_choices.style_card_id` 的寫入時機**：第 7 步只寫 `state.proposalReview.confirmedStyleCardId`，`design_choices.style_card_id` 到第 8 步 `aiRenderSceneForBrief()` 才被合成（`scene_v2.js:16938`–`16941`），伺服器端優先讀 `style_card.card_id`（`ai_render_service.py:222`–`228`）。FR-057 敘述的「選定色卡後寫入 `design_choices.style_card_id`」在第 7 步結束時尚未成立，需修正 FR-057 措辭或改寫程式。
6. **SRS FR-055 佐證行號偏移**：`srs.md` 引 `scene_v2.js:232-241`，實際 `state.proposalReview` 定義在 `:242`–`249`。屬行號漂移，請於下次 SRS 更新時校正。
7. **響應式與無障礙標準**：repo 內無斷點規格文件、無 a11y 稽核紀錄、無 Figma 來源；房間／候選按鈕缺 `aria-current`／`aria-pressed`，`#proposal-review-status` 缺 `aria-live`（§9）。後者與第 6 步 `#white-model-status`、第 8 步 `#ai-render-status` 是同一個 `rp-viewer-status` 缺口，宜一次補齊而非逐步修。
