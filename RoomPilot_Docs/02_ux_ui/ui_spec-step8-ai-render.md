# UI 規格：第 8 步 AI 渲染與成果包 (UI Spec - Step 8 AI Render) - RoomPilot

> **版本：** v1.0 ｜ **更新：** 2026-08-12 ｜ **狀態：** 草稿（待 owner 核准）
> **Owner:** MOD-WEB owner（Bella）＋ MOD-SRV-RENDER owner（Bella，§7 伺服器側）＋ MOD-AGT owner（Yen，Gen_Pic／Report Agent 提示詞與失敗政策）＋ 產品 owner（交付主件與改圖額度口徑）
> **語域:** L3（工程）——直接寫 DOM id、端點、狀態欄位與失敗行為
> **實例:** 八步之一（`ui_spec-step8-ai-render.md`）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12；行號對應該版

本文件回答：第 8 步畫面由哪些區塊與 DOM 節點組成、逐房生圖與一鍵全生怎麼送出、生圖疊層 `#ai-render-image-stage` 的兩種模式、改圖額度在畫面上怎麼呈現與被擋、三份交付物各由哪個按鈕產出、失敗時畫面顯示什麼原文。
本文件**不含**：相機鎖定與色卡比較（見 [ui-spec-step7](ui_spec-step7-proposal-review.md)）、家具擺位與合法性（見 [ui-spec-step6](ui_spec-step6-layout-2d.md)）、提示詞組裝演算法與生成治理取捨（見 [ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)、[ADR-006](../03_architecture/adr/ADR-006-appliances-render-context-only.md)）。
要找端點欄位契約去 [api-spec](../04_design/api_spec.md) 與 [openapi-render-delivery](../04_design/openapi-render-delivery-v1.yaml)；要找測試對應去 [test-plan](../05_qa/test_plan.md)；失效處置去 [runbook-genpic](../06_ops/runbook-genpic-provider-failure.md)（RB-002）與 [runbook-delivery-pdf](../06_ops/runbook-delivery-pdf-engine-missing.md)（RB-005）。

**DOM 權威來源：** `scene.html:980`–`986` 的 `#room-render-section` 靜態內容（「2. 逐房間視角」、`#render-room-list`、`#save-room-view`、`#submit-room-renders`）在進入本步後被 `renderFinalRoomWorkflow()` 以 `innerHTML` **整段取代**（`scene_v2.js:16551`–`16601`），側欄「1. 色卡比較」整個 `.rp-editor-box` 於進場被設為 `hidden`（`scene_v2.js:16633`）。**本文件一律以執行期 DOM 為準**，靜態骨架僅列作對照。

---

## 目錄

- [1. 頁面目的 (Page Purpose)](#1-頁面目的-page-purpose)
- [2. 版面配置 (Layout)](#2-版面配置-layout)
- [3. 欄位與元件 (Fields / Components)](#3-欄位與元件-fields--components)
- [4. 使用者操作 (Actions)](#4-使用者操作-actions)
- [5. UI 狀態 (States)](#5-ui-狀態-states)
- [6. 互動規格 (Interaction Spec)](#6-互動規格-interaction-spec)
- [7. 生圖與交付整合](#7-生圖與交付整合)
- [8. 驗證規則 (Validation)](#8-驗證規則-validation)
- [9. 響應式與無障礙 (Responsive / A11y)](#9-響應式與無障礙-responsive--a11y)
- [10. 設計交付 (Design Handoff)](#10-設計交付-design-handoff)
- [11. 追溯](#11-追溯)

## 1. 頁面目的 (Page Purpose)

把第 7 步鎖定的逐房視角截圖送去 OpenRouter 生成寫實效果圖（客廳額外一張夜景），再把需求、配置、生圖成果、工程與預算打包成可交付成果。對應 User Flow 節點見 [ux-research](ux_research_and_journey.md) 第 8 步；面板在資訊架構中的位置見 [ia](information_architecture.md)。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 7 步 `#proposal-confirm-render-palette`（JS 注入，建立於 `scene_v2.js:16187`、綁定於 `:16201`）→ `confirmRenderPalette()` 先 `complete("proposal_review")`、再 `seedRepresentativeRoomRenderFromPalette()`、最後 `goTo("ai_render")`（`scene_v2.js:15770`–`15806`）；或還原專案時 `showStep("ai_render")`。（`scene.html:978` 的同名 `#confirm-render-palette` 是本步側欄「1. 色卡比較」的遺留舊控制項，進場即隨整個 `.rp-editor-box` 被隱藏，見本文開頭「DOM 權威來源」與 §10 已知限制②） |
| 出口 | 本步為旅程終點；成果經 `#design-delivery-generate`（`scene.html:992`）或 `#download-engineering-delivery`（JS 注入）開啟 `dialog#design-delivery-dialog`（`scene.html:1014`）下載 |
| 面板 | `section#ai-render-step[data-panel="ai-render"]`（`scene.html:950`）；導覽列 `data-step="ai_render"`（`scene.html:30`）；進場由 `showStep()` 觸發 `prepareAiRender()`（`scene_v2.js:1580`、`:16620`–`16663`） |
| 前置閘門 | `REQUIRED_COMPLETIONS.ai_render` 要求前七步全部完成（`scene_workflow.js:93`–`103`）；未達提示「請先在第 7 步確認完整方案、三種候選色卡與比較視角。」（`scene_v2.js:1699`） |
| 完成判定 | `validCompletion("ai_render")` 只要求 `data.confirmed === true`（`scene_workflow.js:159`）；由最後一房初稿完成時自動寫入（`scene_v2.js:17061`、`:17117`） |

## 2. 版面配置 (Layout)

```text
#ai-render-step  [data-panel="ai-render"]
└─ .rp-3d-workspace
   ├─ .rp-viewer-pane
   │  ├─ .rp-viewer-toolbar   #ai-render-view-title | #ai-render-provider-state
   │  ├─ #ai-render-viewer（Three.js，createSceneViewer，scene_v2.js:613）
   │  │   └─ #ai-render-image-stage [hidden][role=button][tabindex=0]
   │  │        #ai-render-image | #ai-render-image-caption
   │  │        #ai-render-gallery [hidden]（gallery 模式，見 §7 註）
   │  │        #ai-render-stage-close | .rp-render-image-hint
   │  │      #ai-render-image-toggle [hidden]
   │  └─ #ai-render-status
   └─ aside.rp-control-pane.rp-style-sidebar
      ├─ section.rp-editor-box「1. 色卡比較」→ 進場被 setAttribute("hidden")
      ├─ #room-render-section  ← [JS 注入] renderFinalRoomWorkflow() 全量取代
      │    .rp-render-room-list（逐房膠囊＋狀態）
      │    #submit-all-room-renders | .rp-final-render-summary
      │    .rp-final-render-thumbs（[data-render-thumb="day"|"night"]）
      │    #final-room-adjustment + #submit-final-room-render | #request-room-revision
      │    #download-engineering-delivery
      ├─ #remote-render-jobs
      └─ #delivery-proposal-section → #design-delivery-generate

dialog#render-brief-dialog（scene.html:998）  #render-brief-summary / #render-brief-notes
                                             #render-brief-warning / -cancel / -confirm
dialog#design-delivery-dialog（scene.html:1014） #design-delivery-content
    #delivery-proposal-generate | #delivery-proposal-download | #delivery-proposal-status
    #download-design-delivery-json | #design-delivery-done | #close-design-delivery
```

左側 viewer 與生圖疊層共用同一容器：疊層為 `#ai-render-viewer` 內的絕對定位層，`hidden` 切換即在「3D 場景」與「生圖」之間互換（`scene_v2.js:17447`–`17493`）。

## 3. 欄位與元件 (Fields / Components)

| 元件 | 型態 | 寫入的 state 路徑 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| 逐房膠囊 `[data-final-render-room]` | 按鈕清單 | 讀 `state.proposalReview.finalRooms[roomId]`；點擊寫 `state.selectedRenderRoomId` | 副標三態「待初稿」／「初稿完成」／「已修改一次」（`scene_v2.js:16570`–`16574`） |
| `#submit-all-room-renders` | 按鈕 | — | 僅在 `anyPending`（有房未送初稿）時渲染（`scene_v2.js:16564`、`:16575`） |
| `.rp-final-render-summary` | 唯讀摘要 | 讀 `roomQuestionnaireContext(room.id)` | 顯示生圖詞彙（`renderPromptKeywords()`，`scene_v2.js:15892`–`15910`）與「已鎖定家具」 |
| `[data-render-thumb="day"]` | 縮圖按鈕 | 讀 `finalRooms[id].revision_image_data_url \|\| image_data_url` | 小標「日光」；已改圖時改為「已修改」 |
| `[data-render-thumb="night"]` | 縮圖按鈕 | 讀 `finalRooms[id].night_image_data_url` | 僅客廳有值時渲染（`scene_v2.js:16561`、`:16581`） |
| `#final-room-adjustment` | textarea | 送入 `renderBrief.user_notes` | 未生初稿時為「本房初稿補充」；全房初稿完成且未改過時改為「針對這張圖修改一次」（`scene_v2.js:16581`–`16584`） |
| `#render-brief-notes` | textarea | `confirmedRenderBrief()` → `state.proposalReview.renderBriefs[]`（`scene_v2.js:16684`） | 送出前確認視窗；`renderBriefs` 會進 workflow（`scene_v2.js:1279`） |
| `#ai-render-image` / `#ai-render-image-caption` | 疊層單張圖＋標籤 | 讀 `renderStageView`（`scene_v2.js:273`） | `renderStageView.label` 標明是哪一房／日光或夜間 |
| `#ai-render-image-toggle` | 按鈕 | — | 疊層關閉且有已完成圖時顯示，文案「查看生圖（<房名>）」（`scene_v2.js:17456`–`17458`） |
| `#design-delivery-content` | 對話框內容 | 讀 `latestDesignDelivery`（`scene_v2.js:271`） | 五章：逐房設計／工程報告書／資安工程審核／預算報告書／設計提案 PDF（`scene_v2.js:17258`–`17270`） |
| `#delivery-proposal-download` | 連結 | `href = /api/projects/{id}/delivery-proposal/pdf` | 僅在有 `workflow.delivery_proposal` 紀錄時顯示（`scene_v2.js:17523`–`17532`） |

**未持久化欄位（重要）**：`state.proposalReview.finalRooms`（含所有生圖 base64 data URL）**不在 `workflowPayload()` 的輸出中**（`scene_v2.js:1273`–`1281` 只寫 `masterView`／`confirmedStyleCardId`／`roomViews`／`jobs`／`renderBriefs`），還原時亦不重建（`scene_v2.js:19460`–`19470`）。見 §11 待確認 2。

## 4. 使用者操作 (Actions)

| 操作 | 觸發元素 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 切換房間 | `[data-final-render-room]` | `selectRenderRoom()`：鎖相機、套第 7 步視角、重繪面板（`scene_v2.js:16602`–`16619`） | 無角色控制（Pilot 全 app 無認證，NFR-019） |
| 送本房初稿 | `#submit-final-room-render` → `openRenderBriefDialog("room_final","initial")` → `#render-brief-confirm` | `submitRoomRenders()` POST `/api/projects/{id}/ai-renders`，body 只帶該房一項（`scene_v2.js:16992`–`17073`） | 同上 |
| 一鍵全生 | `#submit-all-room-renders` | `submitAllRoomRenders()` 對所有已鎖視角且未生的房一次送出，顯示全螢幕遮罩（`scene_v2.js:17075`–`17124`） | 同上 |
| 改圖一次 | `#request-room-revision` → 確認視窗 → `#render-brief-confirm` | POST `/api/projects/{id}/ai-renders/{room_id}/edit`（`scene_v2.js:17016`–`17023`） | 同上 |
| 放大／關閉疊層 | 縮圖 `[data-render-thumb]`；`#ai-render-image-toggle`；`#ai-render-stage-close`；點疊層空白 | `showRenderImageEnlarged()`／`closeRenderImageStage()`（`scene_v2.js:17434`–`17445`、事件接線 `:19001`–`19022`） | 同上 |
| 產出成果包 | `#design-delivery-generate` 或 `#download-engineering-delivery` | POST `/api/projects/{id}/design-delivery`，成功後 `showModal()`（`scene_v2.js:17287`–`17337`、`:17604`–`17681`） | 同上 |
| 產出交付提案 PDF | `#delivery-proposal-generate`（成果包視窗內） | POST `/api/projects/{id}/delivery-proposal`，成功後顯示下載連結（`scene_v2.js:17566`–`17600`） | 同上 |
| 下載成果包 JSON | `#download-design-delivery-json` | 以 Blob 下載 `roompilot-design-delivery-<project_id>.json`（`scene_v2.js:17278`–`17285`） | 同上 |
| 產出九章設計手冊 PDF | **本 repo 前端無此入口** | 端點存在（`main.py:2300`–`2350`）但 `backend/server/static/` 全目錄查無 `design-manual` 呼叫點 | — |

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案（原文） |
| :--- | :--- | :--- |
| Loading（進場） | 全畫面遮罩 `beginPlacementBusy()`（viewer 無 GLB 快取，需整場重建） | 「正在準備第 8 步渲染場景，請稍候…」（`scene_v2.js:16635`） |
| Loading（單張生圖） | 只更新 `#ai-render-status`，**不顯示遮罩**（`scene_v2.js:17012`） | 「生圖中，請稍候…」 |
| Loading（一鍵全生） | 遮罩＋狀態列 | 「正在一次生成 N 個房間的寫實圖，請稍候…（依房間數與模型速度可能需一至數分鐘）」／「一鍵生圖中（N 房），請稍候…」（`scene_v2.js:17084`–`17085`） |
| 服務狀態 | `#ai-render-provider-state`（查 `GET /api/ai-render/status`，`main.py:2064`–`2067`） | 「正在檢查生圖服務…」→「生圖服務已連接｜<model>」／「尚未設定生圖服務」／「無法取得生圖服務狀態：<原因>」（`scene_v2.js:16653`–`16660`） |
| Empty（未生任何圖） | 疊層 `hidden`，`#ai-render-image-toggle` 亦 `hidden`（無 `completedOpenrouterRows()`） | `#ai-render-status`：「已沿用第 7 步確認的視角；請確認本房問卷與生圖詞彙。」（`scene_v2.js:16613`） |
| Error（單房失敗） | 狀態列文字；該房仍留在「待初稿」 | 「生圖失敗：<notices 以；串接>」（`scene_v2.js:17069`） |
| Error（一鍵全生部分失敗） | 狀態列 | 「一鍵生圖完成 N 房、失敗 M 房；失敗的可單獨重試。」（`scene_v2.js:17121`） |
| Error（額度用罄） | 前端先擋；伺服器再擋 409 | 前端「此房已使用一次修改額度。」（`scene_v2.js:17004`）；伺服器「這個房間只能修改一次，額度已用完。」（`main.py:2249`–`2250`） |
| Error（PDF 引擎缺席） | `#delivery-proposal-status` | 由 `GET /api/delivery-proposal/status` 的 `reason` 帶出，取不到時「設計提案排版引擎尚未安裝。」（`scene_v2.js:17557`–`17563`） |
| Permission Denied | 不適用（Pilot 全 app 無認證與角色，NFR-019；服務邊界待 DEC-014 核准） | — |
| Success（逐房） | 生圖完成即把圖放大到左側疊層 | 「已一次完成 N 個房間的生圖；點縮圖可放大到左側 3D 區。」／「本房初稿已送出。請完成其他房間初稿後，再回來做每張圖一次修改。」／「本房已使用一次修改額度。」 |
| Success（成果包） | `dialog#design-delivery-dialog` `showModal()` | 「成果包已完成並通過後端資安審核；設計提案 PDF 可在同一視窗產出。」（`scene_v2.js:17676`）／「成果包已完成，並已通過後端資安工程審核。」（`scene_v2.js:17331`） |
| Success（交付提案） | 下載連結顯示 | 「設計提案完成（含 N 房生圖）」／「設計提案完成（未含生圖）」＋第一則 warning（`scene_v2.js:17588`–`17595`） |

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover／選取 | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `[data-final-render-room]` | 目前房加 `.is-active` | — | — | — |
| `#submit-final-room-render`／`#request-room-revision` | — | 不 disable（改以條件不渲染：初稿完成即不渲染送出鈕；未全房完成即不渲染改圖鈕） | 只改狀態列文字 | 例外一律寫 `#ai-render-status`，面板不重繪 |
| `#submit-all-room-renders` | — | 條件不渲染（無 pending 房時不出現） | `beginPlacementBusy()` 遮罩＋`finally` 解除（`scene_v2.js:17123`） | 「一鍵生圖失敗：<原因>」 |
| `#design-delivery-generate`／`#download-engineering-delivery` | — | 送出期間 `disabled = true`，`finally` 還原（`scene_v2.js:17319`–`17335`、`:17610`） | 狀態列「正在建立裝潢簡報、工程報告、資安審核與預算明細…」 | 「成果包建立失敗：<原因>」 |
| `#delivery-proposal-generate` | — | 送出期間 `disabled = true`，`finally` 還原（`scene_v2.js:17573`、`:17598`） | 狀態列顯示排版中 | `setDeliveryProposalStatus(errorMessage(error))` |
| `#ai-render-image-stage` | `role="button"` `tabindex="0"`；點空白關閉 | — | — | Enter／Space／Esc 同步支援（`scene_v2.js:19007`–`19013`） |
| `#render-brief-confirm` | — | — | — | 命中 `移(動\|到)\|搬\|拆\|打通\|開放式\|走道\|門口\|窗邊\|牆\|改格局\|重新擺` 時第一次點擊只顯示警語、需再點一次才送出（`scene_v2.js:15888`–`15890`、`:15966`–`15971`） |

結構性改動警語原文（`scene_v2.js:15969`）：「偵測到可能改變格局、門窗、家具位置或空間大小的描述。送出後仍會保留第 4 步結構、已鎖定家具與確認視角；系統只會請生圖服務在可行範圍內調整材質、氛圍與軟裝。再次按確認即可送出。」

## 7. 生圖與交付整合

| 項目 | 行為 | 證據 |
| :--- | :--- | :--- |
| 逐房併發 | `ThreadPoolExecutor(max_workers=max(1, len(rooms)))` + `pool.map`，**結果順序對齊輸入 `rooms`** | `ai_render_service.py:423`–`427` |
| 客廳夜景 | `room_type == "living_room"` 或房名含「客廳」時，同視角同色卡再跑一次 `stage="full_render_night"`、`lighting="night"` | `ai_render_service.py:319`–`325`、`:404`–`417`；光影提示 `tools/genpic_info.py:37`–`41` |
| 單房失敗 | `GenPicFailure` 只回該房 `{status:"failed", notices}`，其餘房照常回傳 | `ai_render_service.py:378`–`388` |
| 夜景失敗 | 只在該房結果附 `night_notices`，不影響日光初稿、不擋整批 | `ai_render_service.py:396`–`397`（註解）、`:412`–`413`（`except GenPicFailure` → `result["night_notices"]`） |
| 重試政策 | 主模型最多 3 次 → fallback 模型再 3 次 → 拋 `GenPicFailure`（`notices` 逐次記錄原因） | `subagents/genpic_agent.py:29`–`31`、`:155`–`190` |
| 提示詞 | deterministic 組裝；`strip_measurements()` 清掉所有尺寸串，提示詞**不含任何尺寸數字**；家電只在此以 `render_context.appliance_requirements` 進入畫面描述 | `tools/genpic_info.py:80`–`94`、`:177`–`248`；`ai_render_service.py:200`–`214` |
| 房間尺寸 | 提示詞用**整體平面圖** `floorplan.width_cm/depth_cm` 當房間長寬（多房為近似值），實際構圖由 img2img 參考截圖鎖定 | `ai_render_service.py:118`–`127` |
| 改圖額度 | 伺服器強制**逐房各一次**：`ai_render.rooms[].edit_used >= 1` → 409 `ai_edit_budget_exhausted`；未生圖 → 409 `room_not_generated`；上游拒絕 → 502 `ai_edit_failed`；未設金鑰 → 503 | `main.py:2240`–`2274` |
| 疊層兩模式 | `renderStageView = {mode:"single"\|"gallery"}`；`single` 顯示 `#ai-render-image`＋caption，`gallery` 改顯示 `#ai-render-gallery` 圖片牆 | `scene_v2.js:17452`–`17498` |
| 疊層狀態旗標 | `aiRenderImageVisible` 決定疊層開／關。**曾在 `886b7f7f` 帶狀拼接時整行宣告被刪**，留下 5 處使用、0 處宣告；本檔以 `type="module"` 載入（嚴格模式）→ `updateAiRenderImageStage()` 一讀就 `ReferenceError`，連帶 `prepareAiRender` 中斷、一鍵全房生圖走進 catch（`scheduleSave` 沒跑到、生圖結果不落地）、縮圖點了沒反應 | 宣告 `scene_v2.js:276`；使用 `:17446`–`17478`；回歸守門 `tests/test_render_image_stage.py::test_module_state_assignments_are_all_declared` |
| 代表房不進全房生圖 | 第 7 步色卡比較的代表房（實測專案為 room-6＝客廳）確認色卡後，該張比較圖被 `seedRepresentativeRoomRenderFromPalette()` 直接當日光初稿寫進 `finalRooms` 並設 `submitted_at` → 被一鍵生圖的 pending 過濾排除（實測 `ai_render.rooms` 只有 room-1,2,3,4,5,7）。**代表房是客廳時，`full_render_night` 因此從未被請求** | `scene_v2.js:15816`–`15837`（seed）、`:17106`–`17111`（pending 過濾） |
| 夜間圖補生（night_only） | 一鍵生圖時把「有日光初稿、卻沒有夜間圖的客廳」以 `night_only: true` 併進同一次請求，只生夜間那張（省一次生成）。同一條路徑也用於夜景先前失敗的補生。初稿全完成但夜間圖仍缺時，一鍵按鈕改標「補生客廳夜間燈光圖」，否則沒有觸發點 | `scene_v2.js:17090`–`17104`（`isLivingRoomForRender`／`roomsMissingNightRender`）、`:17117`–`17121`（併入請求）、`:17142`–`17157`（結果合併不覆蓋 `submitted_at`）；`ai_render_service.py:406`–`437` |
| 夜間圖進報告 | `deliveryRoomsPayload()` 一併送 `night_image_data_url`／`night_model` → 圖庫多建一筆 `stage="full_render_night"` → 設計手冊第七章日光／夜間並列、交付提案放進該空間的 `extra_images`（封面仍用日光那張） | `scene_v2.js:17519`–`17536`；`design_manual_service.py:166`–`179`；`skills/delivery/__init__.py:135`–`179`（落檔）、`:596`＋`:685`–`696`（進 content.json） |
| **gallery 模式現況** | 分支存在但**無任何寫入點**：全 repo 僅 `mode:"single"` 被賦值，`showRenderGallery()`／`#ai-openrouter-gallery`／`element.aiOpenrouterResults` 皆不存在 → `#ai-render-gallery` 永不渲染 | `scene_v2.js:17436`（唯一賦值）；`tests/test_render_image_stage.py:38`–`73` 有 3 筆紅燈斷言（2026-08-12 實跑 `pytest -q tests/test_render_image_stage.py` = 3 failed／2 passed） |
| 三份交付物 | ①設計手冊 PDF（九章，末章報價單；LLM 不可用走 deterministic 底稿）②交付提案 PDF（品牌排版）③成果包 JSON（`schema_version 1.1`、`artifact_type roompilot.web_design_delivery.v1`、六章 `web_report.sections`） | `main.py:2300`–`2350`、`:2384`–`2437`、`:2921`–`2944`；`design_manual_service.py:210`–`239`、`:241`–`262` |
| 成果包脫敏 | `_delivery_security_review()` 掃出 `DELIVERY_SENSITIVE_KEYS` 命中路徑並列入 `redacted_paths`，`_delivery_sanitized_copy()` 移除該些鍵 | `main.py:2475`–`2491`、`:2715`–`2768` |
| 工程概算 `needs_quote` | 查無費率或單位不符 → 進 `needs_quote`，前端呈現 `status_label:"待報價"`、金額為 `null`；總計只加已估項 | `cost_estimation.py:57`–`68`、`:96`–`107`；`main.py:2701`–`2713`、`:2868`–`2886`；前端 `scene_v2.js:17210`–`17216` |
| 免責 | `DISCLAIMER_ZH`「網路公開行情概算；施工前須現場丈量並取得正式報價。」；成果包另用 `budget_report.disclaimer` | `cost_estimation.py:11`；`main.py:2885` |

## 8. 驗證規則 (Validation)

| 對象 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| 進場前置 | 需 `confirmedStyleCardId` 且每房皆有第 7 步視角，否則 `throw` 並停在原地 | 「請先回第 7 步確認 <房名> 的視角。」／「請先回第 7 步確認代表房色卡。」 | `prepareAiRender()`（`scene_v2.js:16623`–`16630`） |
| 改圖前置（前端） | 需該房 `image_data_url` 存在且未 `revision_submitted_at`；沿用色卡圖者（`reused_from_palette` 且無 `image_id`）自動改走整房重生 | 「請先完成此房初稿，再提出一次修改。」／「此房已使用一次修改額度。」 | 按 `#request-room-revision` 後送出（`scene_v2.js:16997`–`17010`） |
| 生圖 payload（伺服器） | `project_id` 需相符（422 `render_project_mismatch`）；`scene.scene_objects` 必填（422 `scene_required`）；`rooms` 非空（422 `room_views_required`）；每房需 `room_id`（422 `room_id_required`）與 `data:image/` 開頭的截圖（422 `reference_png_required`） | 「生圖資料與目前專案不一致。」「缺少場景資料，請先完成第 6 步配置。」「缺少逐房視角，請先在第 7 步鎖定視角。」「每個房間視角都需要 room_id。」「每個房間視角都需要 3D 視角截圖。」 | POST `/ai-renders`（`main.py:2079`–`2107`） |
| 生圖服務可用性 | 無 `OPENROUTER_API_KEY` → `AiRenderNotConfigured` → 503，且**不回任何影像** | 「尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。」 | 同上（`main.py:2109`–`2116`；`ai_render_service.py:60`–`61`、`:344`–`345`） |
| 改圖 payload | `feedback` 必填（422 `feedback_required`）；`image_data_url` 需為 PNG data URL（422 `base_image_required`） | 「請描述想修改的內容。」「缺少要修改的原圖。」 | POST `/ai-renders/{room_id}/edit`（`main.py:2251`–`2259`） |
| 報告 payload | `design-manual` 與 `delivery-proposal` 共用驗證：`project_id` 相符、`scene`／`rooms` 非空 | 「報告資料與目前專案不一致。」「缺少房間資料，無法組成果報告。」 | `_validated_report_payload()`（`main.py:2353`–`2376`） |
| PDF 排版引擎 | 未安裝 → 503 `delivery_engine_not_configured`（訊息含安裝指引）；排版失敗 → 502 `delivery_proposal_failed` | 由後端 `reason` 原文帶出 | POST `/delivery-proposal`（`main.py:2400`–`2408`；`design_manual_service.py:255`–`258`） |
| PDF 下載 | 無紀錄 404；紀錄在但檔不在 410 | 「尚未產出設計手冊。」／「設計手冊紀錄存在，但檔案已遺失，請重新產出。」（交付提案同構） | GET `.../design-manual/pdf`（`main.py:2334`–`2350`）、`.../delivery-proposal/pdf`（`main.py:2421`–`2437`） |
| 成果包大小 | 生圖 base64 **不寫入 workflow**（伺服器只存 `rooms[].lock_manifest` 與 `edit_used`），避免撞 2 MB 上限（NFR-001）；上限由 `project_store.py:224`–`225` 強制（`MAX_WORKFLOW_BYTES = 2 * 1024 * 1024`，`:11`） | 413 `workflow_too_large` **只在 workflow 儲存端點被映射**（`main.py:1859`–`1866`）；`/ai-renders` 未攔截 `WorkflowTooLargeError`，超量會以 500 呈現（見 §11 待確認 8） | `/ai-renders` 寫回 workflow 時（`main.py:2117`–`2126`） |

## 9. 響應式與無障礙 (Responsive / A11y)

- **斷點行為：** 版面由 `site.css` 的 `.rp-3d-workspace`（viewer＋側欄雙欄）控制，與第 6／7 步同一套；本 repo 無獨立斷點規格文件，實際斷點值**待確認**（見 §11）。
- **鍵盤操作：** 房間膠囊、生圖按鈕、對話框按鈕皆為原生 `<button>`，Tab 可達；`#ai-render-image-stage` 以 `role="button"` `tabindex="0"` 補上鍵盤可達性，Enter／Space 放大 gallery 磚、Esc 關閉疊層（`scene_v2.js:19007`–`19013`）；`#render-brief-dialog` 與 `#design-delivery-dialog` 為原生 `<dialog>`（Esc 關閉為瀏覽器預設）。
- **ARIA 現況：** `#ai-render-viewer[aria-label="逐房間渲染視角"]`、`#ai-render-image-stage[aria-label="點擊空白處切回 3D 場景"]`、`#ai-render-gallery[aria-label="已生成圖片牆"]`、`#ai-render-image-caption[aria-live="polite"]`、`#remote-render-jobs[aria-live="polite"]`、`#render-brief-warning[aria-live="polite"]`、`#design-delivery-content[aria-live="polite"]`（`scene.html:957`–`1020`）。
- **未驗證項：** `#ai-render-status` **無 `aria-live`**，生圖進度與失敗訊息不會被螢幕閱讀器主動播報；生圖圖片 `alt` 只有房名與「生圖」字樣，無畫面內容描述；對比度、focus ring 與遮罩期間的焦點鎖定皆無稽核紀錄，WCAG 等級未定，屬 TO-BE。

## 10. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | 無（repo 內查無 Figma 連結或設計稿）——**待確認** |
| Design Tokens | 無獨立 token 檔；樣式集中於 `backend/server/static/site.css`（單檔），本步用 `.rp-render-image-stage`／`.rp-render-gallery`／`.rp-final-render-*`／`.rp-delivery-*` 類名 |
| 元件對照 | 無元件庫；DOM id 與 `[data-*]` 選擇器即介面契約，斷言於 `tests/test_scene_v2_contract.py:872`–`955` 與 `tests/test_render_image_stage.py` |
| 快取鍵 | `scene.html` 對 `scene_v2.js`／`site.css` 的 `?v=sha256-<前 12 碼>` 必須等於實檔雜湊，由 `tests/test_scene_v2_contract.py:20`–`28` 強制；`site.css` 現值 `sha256-e76c2d47ab75`（`scene.html:7`） |
| 已知限制 | ①`#ai-render-gallery` 圖片牆無實作（§7）；②側欄靜態「1. 色卡比較」「2. 逐房間視角」為第 7 步遺留骨架，執行期被隱藏或整段取代；③設計手冊 PDF 無前端入口（§4） |

## 11. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-011（逐房效果圖＋有限次改圖）、DEC-012（正式交付主件唯一）、DEC-013（只給公開行情概算）、DEC-006（家電只影響效果圖）、DEC-017（外部服務誠實中止）——狀態皆為**待 owner 核准** |
| 對應功能需求 | FR-025（疊層 single／gallery 兩模式）、FR-058（逐房併發生圖＋客廳夜景＋失敗隔離）、FR-059（提示詞不含尺寸、家電只進畫面描述）、FR-060（改圖額度與三種 4xx／5xx）、FR-061（設計手冊 PDF）、FR-062（交付提案 PDF）、FR-063（成果包 JSON）、FR-064（`needs_quote` 不猜價） |
| 對應非功能需求 | NFR-011（LLM 逾時）、NFR-012（3＋3 重試政策、夜景失敗不擋日光）、NFR-013（PDF 引擎與逾時）、NFR-014（503／502／409 語意）、NFR-018（生圖執行緒池）、NFR-020（成果包脫敏）、NFR-001（workflow 2 MB 上限） |
| 對應驗收條件 | ACPT-050、ACPT-051、ACPT-052、ACPT-053、ACPT-054、ACPT-055（另涉 ACPT-060） |
| 對應情境 | SCN-029、SCN-030、SCN-031、SCN-032、SCN-033、SCN-034、SCN-037 |
| 對應架構決策 | [ADR-009](../03_architecture/adr/ADR-009-server-governed-ai-generation.md)、[ADR-006](../03_architecture/adr/ADR-006-appliances-render-context-only.md)、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md)、[ADR-004](../03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md) |
| 對應模組 | MOD-WEB（`backend/server/static/`）、MOD-SRV-RENDER、MOD-AGT |
| 對應測試 | TC-050（逐房併發與失敗隔離）、TC-051（提示詞無尺寸）、TC-052（改圖額度）、TC-053（兩份 PDF 與引擎缺席）、TC-054（成果包脫敏）、TC-055（`needs_quote`）、TC-060 |
| 對應 Runbook | RB-002（[runbook-genpic](../06_ops/runbook-genpic-provider-failure.md)）、RB-005（[runbook-delivery-pdf](../06_ops/runbook-delivery-pdf-engine-missing.md)）、RB-003（[runbook-workflow-save](../06_ops/runbook-workflow-save-conflict-or-oversize.md)） |
| 相鄰步驟 | [ui-spec-step7](ui_spec-step7-proposal-review.md) → 本步（終點） |
| 需求規格 | [srs](../01_requirements/srs.md)、[prd](../01_requirements/prd.md) §3.8；端點契約 [api-spec](../04_design/api_spec.md)、[openapi-render-delivery](../04_design/openapi-render-delivery-v1.yaml) |

### 待確認事項

1. **三份交付物誰是正式主件（OPEN-10）**：成果包 JSON 與交付提案 PDF 有前端入口；**九章設計手冊 PDF 端點存在卻無任何前端呼叫點**（`backend/server/static/` 全目錄查無 `design-manual`）。畫面上「4. 成果包與設計提案」的標題已把交付提案定位為附屬產物；主件歸屬待產品 owner 拍板，UAT 腳本才有可驗對象。
2. **生圖成果不隨專案保存**：`workflowPayload()` 未輸出 `ai_render` 節點，`finalRooms` 的 base64 圖只存在記憶體（`scene_v2.js:1273`–`1281`、`:19460`–`19470`）。重整後畫面全部退回「待初稿」，但伺服器端 `ai_render.rooms[].edit_used` 仍記得已用額度 → 使用者可能看不到圖卻無法再改圖。與第 7 步 OPEN-18（色卡圖重整消失）同一類問題，是否為預期行為待 owner 確認。
3. **改圖額度口徑（OPEN-16）**：程式為逐房各一次（`main.py:2240`–`2250`、workflow `rooms[].edit_used`），`docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md:32`–`33` 寫「整批共用一次」。畫面文案（「本房已使用一次修改額度。」）跟隨程式；契約與 ACPT-052 何者權威待核准。
4. **單房生圖會清掉其他房的 `lock_manifest`**：`/ai-renders` 一律以 `"rooms": [...]` 覆寫整個清單（`main.py:2123`），而 `_merge_dict` 對 list 是整體取代（`project_store.py:18`–`25`）。逐房一張張生完後，只有最後一次呼叫涵蓋的房留有 `lock_manifest`，其餘房改圖會得到 409 `room_not_generated`。是刻意的「每次生圖視為新一批」還是缺陷，待 MOD-SRV-RENDER owner 裁定。
5. **`#ai-render-gallery` 圖片牆是待實作還是已退役**：DOM、CSS 類名、事件接線與 `gallery` 分支都在，但無任何程式碼設定 `mode:"gallery"`，且 `tests/test_render_image_stage.py` 有 3 筆紅燈斷言指向不存在的 `showRenderGallery`／`#ai-openrouter-gallery`。FR-025 的「兩模式」目前只有 `single` 可達。
6. **響應式斷點、無障礙標準與 `#ai-render-status` 的 `aria-live`**：repo 內無斷點規格、無 a11y 稽核紀錄、無 Figma 來源。
7. **生圖端到端耗時與併發上限無目標值**（NFR-025）：`max_workers` 等於房數、無佇列與節流，實測數據與 SLA 待 DEC-019 核准後補。
8. **`/ai-renders` 撞 workflow 上限會回 500 而非 413**：`main.py:2117`–`2126` 呼叫 `PROJECT_STORE.update_workflow()` 但**無 try/except**，全檔亦無 exception handler（`WorkflowTooLargeError` 在 `main.py` 只出現於 `:59` import 與 `:1859` 一處 `except`）。`rooms[].lock_manifest` 累積若真的超過 2 MB，使用者看到的是未分類 500 而非 NFR-014 定義的 413 語意。是否補上映射待 MOD-SRV-RENDER owner 裁定。
