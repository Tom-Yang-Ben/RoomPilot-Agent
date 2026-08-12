# UI 規格：第 6 步 配置與預覽 (UI Spec - Step 6 Layout and Preview) - RoomPilot

> **版本：** v1.0 ｜ **更新：** 2026-08-12 ｜ **狀態：** 草稿（待 owner 核准）
> **Owner:** MOD-WEB owner（Bella）＋ MOD-ENG owner（Ancai，§7 幾何裁決）＋ MOD-CAT owner（Kai，型錄與 GLB）
> **語域:** L3（工程）——直接寫 DOM id、事件、端點與失敗行為
> **實例:** 八步之一（`ui_spec-step6-layout-2d.md`）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12；行號對應該版

本文件回答：第 6 步（內部 `layout_2d`＋被折疊的 `white_model_3d`、`realistic_3d`）由哪些面板與 dialog 組成、A／B 方案怎麼逐房選定並合成、2D 疊層與 3D 拖曳各自打哪個端點、待處理清單如何硬擋進入第 7 步、逐房材質確認的鎖定狀態機。
本文件**不含**：家具合法性演算法本身（見 [srs](../01_requirements/srs.md) FR-034／FR-035 與 [ADR-003](../03_architecture/adr/ADR-003-dual-path-shapely-raster-engine.md)）、選件潛規則的伺服器實作（FR-050–052）、需求問卷欄位（見 [ui-spec-step5](ui_spec-step5-requirements.md)）、視角鎖定與色卡（見 [ui-spec-step7](ui_spec-step7-proposal-review.md)）。
端點契約去 [api-spec](../04_design/api_spec.md) 與 [openapi-scene](../04_design/openapi-scene-v1.yaml)；測試對應去 [test-plan](../05_qa/test_plan.md)。

**DOM 權威來源：** `scene.html` 提供本步靜態骨架，但所有清單、卡片、疊層與待處理項目皆由 JS 於執行期注入（`#configuration-plan-furniture-layer`／`#configuration-pending-list`（`scene_v2.js:11425`, `:11518`）、`#room-scheme-list`／`#room-scheme-choice-grid`（`:4407`, `:4420`）、`#layout-furniture-layer`／`#layout-furniture-list`（`:11039`, `:11053`）、`#layout-room-overlay`（`:10936`）），**本文件一律以執行期 DOM 為準**。三組 `[data-design-scheme]` 工具列（`scene.html:609`, `:664`, `:860`）皆 `hidden aria-hidden="true"`，僅為契約測試保留（`tests/test_scene_v2_contract.py:3938`–`3939` 斷言 A／B 各恰 3 個）。

---

## 目錄

- [1. 頁面目的 (Page Purpose)](#1-頁面目的-page-purpose)
- [2. 版面配置 (Layout)](#2-版面配置-layout)
- [3. 欄位與元件 (Fields / Components)](#3-欄位與元件-fields--components)
- [4. 使用者操作 (Actions)](#4-使用者操作-actions)
- [5. UI 狀態 (States)](#5-ui-狀態-states)
- [6. 互動規格 (Interaction Spec)](#6-互動規格-interaction-spec)
- [7. 引擎驗證整合 (Engine Validation)](#7-引擎驗證整合-engine-validation)
- [8. 驗證規則 (Validation)](#8-驗證規則-validation)
- [9. 響應式與無障礙 (Responsive / A11y)](#9-響應式與無障礙-responsive--a11y)
- [10. 設計交付 (Design Handoff)](#10-設計交付-design-handoff)
- [11. 追溯](#11-追溯)

## 1. 頁面目的 (Page Purpose)

讓使用者逐房選定 A／B 家具配置、在 3D 白模與同步 2D 側欄微調家具、清空待處理清單，再逐房確認牆面與地面材質，交出可進第 7 步的 `scene_json`。所有座標與合法性由 `backend/engine/` 裁決（ADR-002），前端只負責呈現與回打驗證。User Flow 節點見 [ux-research](ux_research_and_journey.md)，面板層級見 [ia](information_architecture.md)。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 5 步 `#confirm-requirements` 成功後由 `generateWhiteModelFromRequirements()` 直接產生 A／B 並落在 `white_model_3d`（`scene_v2.js:9153`–`9161`, `:12837`–`12894`）；或導覽列 `data-step="layout_2d"`（`scene.html:28`），由 `canEnter` 挑 `realistic_3d`→`white_model_3d`→`layout_2d` 最遠可進者（`scene_v2.js:19147`–`19155`） |
| 出口 | 第 7 步（`proposal_review`）——`#save-realistic-scene`「確認全部材質，前往第 7 步」（`scene.html:842`；handler `scene_v2.js:19128`–`19140`）；回頭出口為「返回第 4 步修改樑」`#add-white-model-beam`（`scene.html:748`） |
| 面板 | `section#layout-2d-step[data-panel="layout-2d"]`（`scene.html:606`）、`section#white-model-3d-step[data-panel="white-model-3d"]`（`:663`）；`realistic_3d` **共用** `white-model-3d` 面板（`scene_workflow.js:25`–`27`），對外一律顯示「步驟 6」（`scene_v2.js:304`–`306`, `:322`–`324`） |

三個內部 step 對外折疊為一步（FR-020）：`layout_2d`／`white_model_3d`／`realistic_3d` → `publicWorkflowStep()` 皆回 `layout_2d`（`scene_v2.js:322`–`324`），導覽列只有 8 顆按鈕（`scene.html:22`–`30`）。

## 2. 版面配置 (Layout)

```text
#layout-2d-step  [data-panel="layout-2d"]   ← 正常流程被跳過，見 §5 註
├─ #layout-scheme-bar        hidden；[data-design-scheme=A|B] + #layout-scheme-status
└─ .rp-split-workspace
   ├─ .rp-plan-pane   #auto-layout-furniture | #layout-room-filter | #layout-room-materials
   │   #layout-plan-stage(#layout-plan-image + #layout-room-overlay + [JS] #layout-furniture-layer)
   │   .rp-layout-legend（實線／紅色／拖曳三行）
   └─ aside  #furniture-icon-search | #add-2d-furniture-mode
       [JS] #layout-furniture-list | [JS] #furniture-icon-library
       #selected-2d-furniture(#selected-2d-width/-depth, #rotate-/#replace-/#delete-2d-furniture)
       #layout-error → #confirm-layout-2d

#white-model-3d-step  [data-panel="white-model-3d"]   ← white_model_3d 與 realistic_3d 共用
├─ .rp-viewer-pane
│   .rp-viewer-toolbar  [data-view-mode=orbit|topdown] | #toggle-furniture-numbers
│                       [data-white-interaction=walk|edit] | #white-walk-room | #open-furniture-catalog
│   #white-model-viewer（Three.js）+ #white-model-status
└─ aside.rp-3d-sidebar [data-scene-sidebar-mode=plan|issues|surfaces]
    .rp-scene-sidebar-tabs  [data-scene-sidebar-tab] ×3（issues 帶 #scene-sidebar-issue-badge）
    #configuration-plan-panel  #configuration-plan-toggle
      #configuration-plan-image + [JS] #configuration-plan-furniture-layer
      [JS] #configuration-plan-furniture-list
      .rp-configuration-pending  #configuration-pending-count + [JS] #configuration-pending-list
    #room-scheme-gate  #room-scheme-gate-status | #open-room-scheme-selection
    .rp-white-beam-editor  #add-white-model-beam | #white-model-beam-status
    #white-model-surface-entry [data-scene-sidebar-panel="surfaces"]
      #surface-room-title/-progress/-lock-state | #unlock-room-surfaces
      [data-step-six-surface-kind=wall|floor] → #wall-color-swatches/#wall-material-grouped
                                              → #floor-*/#material-boundary-advanced
      #confirm-room-surfaces | #save-realistic-scene
    #white-model-error → #confirm-white-model

dialogs：#room-scheme-selection-dialog（#room-scheme-list/-choice-grid/-warning/-complete）
        #room-scheme-3d-preview-dialog（#room-scheme-3d-preview + prev/next）
        #furniture-catalog-drawer（新增）｜#furniture-replacement-drawer（更換）
```

`#realistic-3d-step`（`scene.html:859`–`900`）在 `panels` map 中存在（`scene_v2.js:293`–`295`）但**無任何 step 指向它**，實務上永不顯示；其 `realisticViewer` 仍會載入場景（`scene_v2.js:1670`–`1671`, `:14498`–`14500`）——列為已知限制（§11 待確認 3）。

## 3. 欄位與元件 (Fields / Components)

### 3.1 2D 疊層（`layout_2d`）

| 元件 | 型態 | 寫入的 state 路徑 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#layout-room-filter` | `<select>` | `state.activeLayoutRoomId`（預設 `"all"`） | 只列出「有家具的房間」＋「全屋」（`scene_v2.js:10866`–`10881`） |
| `#layout-room-materials` | 色票列 | 唯讀，讀 `roomRequirementModel.roomRequirements[roomId].surfaces` | 每房顯示牆／地 `materialId` 與色塊；另以 SVG pattern 把地材貼圖以 `fill-opacity="0.28"` 疊在房間多邊形（`:10884`–`10904`, `:10911`–`10938`） |
| `#layout-furniture-layer` | 絕對定位按鈕 | `state.furniture2d[]`（`xCm`／`yCm`／`rotationDeg`） | 位置＝`planCmToLayerPixel()`（y 軸翻轉，`scene_layout2d.js:293`–`305`）；尺寸＝`furnitureFootprintStyle()`，最小 28 px（`:319`–`326`）——FR-023 |
| `#furniture-icon-library` | 圖示庫 | — | 由 `FURNITURE_2D_LIBRARY` 展開，`#furniture-icon-search` 過濾類別＋形式名（`scene_v2.js:10939`–`10955`） |
| `#selected-2d-width/-depth` | `number`（cm） | `item.widthCm`／`depthCm`，下限 1 | 變更即 `invalidateDownstreamFrom("layout_2d", …)`（`:12480`–`12489`） |

### 3.2 3D 工作台側欄（`white_model_3d`）

| 元件 | 型態 | 寫入的 state 路徑 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `[data-scene-sidebar-tab]` | 三分頁 | `sidebar.dataset.sceneSidebarMode` | `plan`／`issues`／`surfaces`；`surfaces` 分頁在 `white_model_3d` 時**不是切頁而是送出確認**（`scene_v2.js:18783`–`18792`，見 §4） |
| `#configuration-plan-furniture-layer` | 同步 2D 疊層 | 唯讀投影 `state.furniture2d` | **僅在 `state.showFurnitureNumbers` 為真時才渲染腳印**（`:11426`–`11442`）；縮放＝`configurationPlanPixelsPerCm()`（`:11383`–`11389`） |
| `#configuration-plan-furniture-list` | 清單 | — | 每列顯示編號、名稱、`W × D cm` 與「合法／待處理」（`:11444`–`11455`） |
| `#configuration-pending-count`／`#scene-sidebar-issue-badge` | 數字徽章 | `configurationBlockingFurniture().length` | 為 0 時徽章 `hidden`（`:11457`–`11462`） |
| `#configuration-pending-list` | 逐房分組 | — | 每件附原因＋「定位／只重排此家具／更換較小款」；模型載入失敗改為「更換家具」（`:11472`–`11496`） |
| `#room-scheme-gate-status` | 文字 | `state.designSchemes.room_selections` | `已選 N/M 間。請先完成所有房間的 A/B 選擇，才可微調。`（`:3858`–`3866`） |
| `#surface-room-lock-state` | 徽章 | `roomFinishDrafts[roomId].stepSixSurfaceConfirmed` | `草稿`／`已鎖定`；已鎖定時該房所有材質控制項 `disabled`（`:4340`–`4348`） |
| `#surface-room-progress` | 文字 | — | `已確認 N / M 間`（`:4338`–`4340`） |

### 3.3 家具型錄抽屜

`#furniture-catalog-drawer`（`scene.html:1116`–`1155`）在第 5 步與第 6 步共用：第 5 步走「加入本房」批次勾選（`#questionnaire-catalog-batch`），第 6 步由 `#open-furniture-catalog` 直開（`scene_v2.js:18794`），選件後進入 3D 點選擺放模式。查詢一律 `GET /api/furniture?has_model=true&detail=scene&page_size=48|24`，可帶 `q`／`group`／`types`／`type`／`color`／`material`（`scene_v2.js:13528`–`13560`；端點 `main.py:3229`–`3242`，`page_size` 1–80 越界回 422，NFR-006）。`#furniture-replacement-drawer`（`scene.html:1082`）為「更換目前家具」，含 `#replacement-3d-preview` 即時 GLB 預覽。

## 4. 使用者操作 (Actions)

| 操作 | 觸發元素 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 逐房比較方案 | `#open-room-scheme-selection` | 開 `#room-scheme-selection-dialog`；每房並列 A／B 的 2D 腳印圖與 3D 快照（`scene_v2.js:4395`–`4448`） | 無角色控制（Pilot 全 app 無認證，NFR-019） |
| 放大看 3D | `[data-room-scheme-preview-3d]` | 開 `#room-scheme-3d-preview-dialog`，可上一房／下一房 | 同上 |
| 選定本房方案 | `[data-room-scheme-choice="A|B"]` | 寫 `designSchemes.room_selections[roomId]` | 同上 |
| 完成選擇 | `#room-scheme-complete` | `completeRoomSchemeSelection()`：合成逐房家具 → `confirmLayout2d({strictSelectedFurniture:true})` → 重建 `scene_json`；失敗整包回滾（`:4574`–`4622`） | 同上 |
| 3D 拖曳家具 | `#white-model-viewer` 內家具（需先 `[data-white-interaction="edit"]`） | pointerup 後打 `POST /api/scene/validate`；`ok` 才寫回並設 `position_locked=true`，否則彈回原位（`scene_viewer.js:5396`–`5440`, `:4992`–`5010`） | 同上 |
| 2D 拖曳家具 | `#layout-furniture-layer` | pointerup 打 `POST /api/scene/layout`（單房、僅該件可動、帶 `placement_hint_cm`），失敗還原座標（`scene_v2.js:11776`–`11840`） | 同上 |
| 新增家具 | `#open-furniture-catalog` → 結果卡 → 3D 點位 | `beginPlacement()` 回呼打 `/api/scene/validate`，通過才 `whiteViewer.addObject()` 增量加入（`:13861`–`13920`） | 同上 |
| 更換家具 | `#replace-2d-furniture`／待處理列「更換家具」 | 開 `#furniture-replacement-drawer`；替換前以 `/api/scene/validate` 檢查新尺寸在原位是否合法（`:13766`–`13805`） | 同上 |
| 只重排此家具 | `[data-reflow-configuration-furniture]` | `reflowSingleConfigurationFurniture()`，同時只允許一件在途（`:11530`–`11538`） | 同上 |
| 保留全部並重新擺位 | `[data-prioritize-configuration-room]` | 該房整組重排 | 同上 |
| 依需求重新配置 | `#auto-layout-furniture` | 方案 B 時走 `relayoutFurnitureForScheme(A→B)`，否則 `autoLayoutFurniture()`；期間 `#placement-busy` 遮罩（`:18531`–`18560`） | 同上 |
| 確認家具配置 | `#confirm-white-model`，或點 `[data-scene-sidebar-tab="surfaces"]` | `confirmWhiteModel()`（§7）→ 通過後跳 `realistic_3d` 並切到材質分頁（`:13924`–`14053`, `:18783`–`18792`, `:18927`–`18936`） | 同上 |
| 確認本房材質 | `#confirm-room-surfaces` | 寫 `stepSixSurfaceConfirmed=true`＋時間戳，並自動跳下一間未確認房（`:14650`–`14683`） | 同上 |
| 解除鎖定 | `#unlock-room-surfaces`／`-sticky` | 該房回草稿；已進第 7 步後拒絕（`:14685`–`14700`） | 同上 |
| 前往第 7 步 | `#save-realistic-scene` | 全房材質確認才 `workflow.complete("realistic_3d")` → `goTo("proposal_review")`（`:19128`–`19140`） | 同上 |

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案（原文） |
| :--- | :--- | :--- |
| Loading（重新擺位） | `#placement-busy` 全畫面遮罩 | 「AI 正在重新擺放家具，請稍候…」（`scene_v2.js:18533`）／「正在確認家具配置並套用材質，請稍候…」（`:18930`） |
| Loading（3D 未就緒） | `#white-model-status` | 「正在準備資料庫家具配置。」（`scene.html:699`） |
| Loading（方案合成） | `#room-scheme-complete` 文字替換＋`disabled` | 「正在合成並驗證最終配置…」（`scene_v2.js:4594`） |
| Empty（無家具） | `#configuration-plan-furniture-list` | 「目前沒有家具。」（`:11455`） |
| Empty（無待處理） | `#configuration-pending-list` | 「目前沒有待處理家具。」（`:11520`） |
| Empty（無可比方案） | `#room-scheme-status` | 「此房沒有與方案 A 不同的擺法可比較（此房型幾何上僅一種合理配置，或方案 B 尚未就緒），系統已先採用方案 A；後續仍可挑選、替換與鎖定家具。」（`:4419`） |
| Error（擺不下） | `#layout-error`／待處理列 | 「<名稱>：<placement_reason>」（`:11821`）；分組摘要「N 件因碰撞、淨空或房間尺寸無法放入」（`:11470`） |
| Error（GLB 缺席） | `#white-model-error` | 「有 N 件資料庫 GLB 無法載入，請先修正型錄權限或更換家具，才能進入下一步。」（`:13949`–`13950`） |
| Error（3D 看不到家具） | `#white-model-error` | 「3D 中看不到家具，必須先修正載入、比例或相機框景。」（`:13945`） |
| Error（最終驗證未過） | `#white-model-error` | 「<名稱>未通過最終碰撞、淨空或房間邊界檢查，請先調整。」（`:13976`–`13978`） |
| Error（方案未選） | `#white-model-error`＋自動開 dialog | 「請先完成所有房間的 A/B 方案選擇，才能開始微調與確認最終配置。」（`:13927`） |
| Error（新增位置不合法） | `#white-model-error` | 「無法新增在該位置：<reason>。」（`:13880`） |
| Error（3D 拖曳彈回） | `#white-model-status` | 「⚠ 「<名稱>」無法放在那裡：<reason>，已彈回原位。」（`scene_viewer.js:5436`） |
| Error（型錄不可用） | 第 5 步 `#requirements-generation-help`，第 6 步不進入 | 「目前無法連線 Kai 家具型錄…」（`scene_v2.js:9114`）；狀態來源 `GET /api/catalog/status`（`main.py:3144`–`3146`），處置見 [runbook-catalog-db](../06_ops/runbook-catalog-db-unavailable.md) |
| Permission Denied | 不適用（Pilot 全 app 無認證，NFR-019；邊界待 DEC-014 核准） | — |
| Success（配置產生） | `setStatus` | 「3D 家具配置已產生，N 件資料庫家具可見。」（`:12821`）／純結構時「純結構 3D 配置已產生；此方案沒有家具需求。」（`:12818`） |
| Success（材質全確認） | `#surface-preview-status` | 「所有房間材質皆已確認，可前往第 7 步。」（`:14680`） |

**`#layout-2d-step` 在正常流程不會出現**：第 5 步確認後 `generateWhiteModelFromRequirements()` 先 `goTo("layout_2d")`，隨即由 `confirmLayout2d()` 內部 `showStep("white_model_3d")`（`scene_v2.js:12803`–`12804`, `:12856`）。使用者只有在 A 案生成失敗被退回、或從導覽列回跳且僅 `layout_2d` 可進時才看得到它。此面板是否仍屬正式交付範圍，見 §11 待確認 2。

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover／選取 | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `#confirm-white-model` | — | `roomSchemeGateBlocking()` 或待處理 >0 時 `disabled`，`title` 說明原因（`scene_v2.js:3830`–`3839`） | 點擊後 `#placement-busy` 遮罩，`finally` 必解除 | 寫 `#white-model-error`＋`setStatus(..., "error")`，不前進 |
| `[data-white-interaction="edit"]`、`#open-furniture-catalog` | `.is-active` | 未完成逐房 A／B 選擇時 `disabled`＋`title`「請先完成逐房 A/B 方案選擇，才能微調家具。」（`:3815`–`3827`） | — | — |
| `#room-scheme-complete` | — | 未全選時 `disabled`，`#room-scheme-warning` 列出缺哪幾間（`:4444`–`4452`） | 文字改「正在合成並驗證最終配置…」 | 合成失敗時回滾 `schemeA.furniture`／`sceneData` 並顯示「無法合成最終配置：<原因>」（`:4614`–`4620`） |
| 待處理列 `[data-reflow-configuration-furniture]` | — | 任一件重排在途時全部 `disabled`（`:11480`, `:11484`） | 該鈕文字改「重新配置中…」 | — |
| `#configuration-plan-toggle` | `title`／`aria-label` 隨狀態切換 | — | — | 展開時 `requestAnimationFrame(renderConfigurationPlan)` 重新對位（`:18701`–`18710`） |
| `#toggle-furniture-numbers` | `aria-pressed` 切換，文字「顯示編號／隱藏編號」（`:1089`–`1099`） | — | — | — |
| 3D 拖曳輔助框 | 合法綠、貼齊藍、`blocked` 紅（`scene_viewer.js:4893`–`4904`） | 位移 <1 cm 且未旋轉視為點選，不送驗證（`:5414`） | 「正在檢查「<名稱>」的新位置...」 | 驗證服務無回應時回 `{ok:false, reason:"驗證服務未回應"}`，彈回原位（`:5006`–`5009`） |
| 材質控制項 | 選中卡片 `.is-selected` | 該房已確認後全部 `disabled`（`scene_v2.js:4345`–`4348`） | — | — |

疊層對位：`#configuration-plan-image` 與家具層由 `syncOverlayToImage()` 依 `<img>` content rect 對齊（`:11415`–`11419`），與第 3／4／5 步同一套機制；座標一律公分（ADR-007、NFR-017）。

## 7. 引擎驗證整合 (Engine Validation)

| 項目 | 行為 | 證據 |
| :--- | :--- | :--- |
| 方案生成 | `POST /api/scene/generate`，body 帶 `selected_furniture`、`selected_furniture_exact`、`room_requirements`、`appliance_requirements` 與 **`placement_variant`** | `scene_v2.js:12681`–`12724`；`main.py:3591`, `:3628`–`3640`（非法值退回 `"A"`，FR-029） |
| A／B 差異 | B 只是同一批家具的另一種排法：`relayoutFurnitureForScheme(A, "B")` 逐房重打 `/api/scene/layout` 並帶 `placement_variant:"B"` | `scene_v2.js:10729`–`10783`；FR-031 |
| 逐房重排不動他房 | 帶 `placement_room_id` 時，標了別房 id 的物件一律 `passthrough`，不進重排 | `main.py:3673`–`3687`；FR-032 |
| 單件落點裁決 | `POST /api/scene/validate` 回 `{ok, reason}`，`reason` 為繁體中文 | `main.py:3998`–`4009`；FR-033、FR-034 |
| 最終確認只驗不排 | `confirmWhiteModel()` 送 `validate_only:true` ＋ 每件 `position_locked:true`；缺此旗標伺服器會對「整屋聯集邊界」重排，把靠陽台牆的家具推到對面（原始碼註解自陳） | `scene_v2.js:13957`–`13973`；`main.py:3705`–`3708` |
| 驗證結果回寫 | `syncFinalValidationToConfiguration()` 把回傳合併進 `scene_objects` 與 `furniture2d`，重繪待處理清單 | `scene_v2.js:11352`–`11381` |
| GLB 解析 | `resolveCatalogFurniture()` 先用既有 `model_url`＋`catalogFurnitureId`；否則查 `/api/furniture?type=…&has_model=true`，帶 `style` 無結果時去掉 `style` 再查一次；全失敗回原件（無 GLB） | `scene_v2.js:12491`–`12539` |
| 座標鎖 | `lockPositions=true`（逐房 A／B 合成）時所有件 `position_locked=true`；否則只有 `item.locked` 為真者鎖定 | `scene_v2.js:12496` |
| 3D 增量更新 | `loadScene()` 是唯一場景入口，內容未變且無 fallback 時整包跳過；`updateRoomSurfaces()` 只重建房殼、保留家具與 GLB clone | `scene_viewer.js:4142`–`4160`, `:4201`–`4216`；FR-024 |
| 診斷 | `getDiagnostics()` 回 `{requestedFurnitureCount, visibleFurnitureCount, fallbackFurnitureCount, failedFurniture[]}`；缺 GLB／載入失敗／擺放失敗三類都進 `failedFurniture` | `scene_viewer.js:3843`–`3854`, `:4280`–`4318` |
| GLB fallback | 無 `model_url` 顯示替身並附「資料庫尚未提供 GLB」；載入例外附「GLB 載入失敗，請更換家具或檢查資料庫模型權限」 | `scene_viewer.js:4224`–`4227`, `:4269`–`4276`；FR-042、[runbook-glb-asset-missing](../06_ops/runbook-glb-asset-missing.md) |

引擎是唯一幾何權威：前端不自行判定碰撞或淨空，只呈現引擎回傳的 `placement_failed`／`placement_reason`（ADR-002）。

## 8. 驗證規則 (Validation)

| 對象 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| **待處理清單硬閘（FR-024）** | `configurationBlockingFurniture()` 非空即 `#confirm-white-model` `disabled`；`confirmWhiteModel()` 再檢一次並中止 | 「目前還有 N 件家具位置不合法，請先從 2D 待處理清單定位修正。」 | 每次 `renderConfigurationPlan()`／按確認（`scene_v2.js:11065`–`11082`, `:3830`–`3839`, `:13932`–`13939`） |
| 阻擋來源 | 三類：`furniturePlacementInvalid()`、`getDiagnostics().failedFurniture`（僅 `white_model_3d` 步驟計入）、扣除舊版 `deferred` 清單 | — | `:11065`–`11092`, `:11343`–`11350` |
| 3D 可見性 | `expectedFurnitureCount > 0` 且 `visibleFurnitureCount <= 0` 即中止 | 「3D 中看不到家具，必須先修正載入、比例或相機框景。」 | `confirmWhiteModel()`（`:13941`–`13947`） |
| 逐房方案閘門 | 存在可比較的 B 時，所有房都要有 `room_selections` 才能微調與確認 | 「請先完成所有房間的 A/B 方案選擇…」 | `roomSchemeSelectionRequired()`／`roomSchemeGateBlocking()`（`:3636`–`3650`） |
| 逐房材質 | `#save-realistic-scene` 需 `allStepSixRoomSurfacesConfirmed()`；未達成時自動聚焦第一間未確認房 | 「請先確認「<房名>」的材質，再前往第 7 步。」 | `:19128`–`19137` |
| 2D 確認（非嚴格） | `confirmLayout2d()` 先整屋 `/api/scene/layout`，`placement_failed` 或 `!position_locked` 即擋（`allowPendingFurniture`／`strictSelectedFurniture` 例外） | 「<名稱>目前位置未通過碰撞、淨空或房間邊界檢查，請移動或更換尺寸。」 | `:12610`–`12628` |
| GLB 就緒 | 有 `selectedFurniture` 缺 `model_url` 時，非寬鬆模式一律擋 | 「有 N 件家具尚未找到可用的資料庫 GLB：<名稱>。請更換家具或確認型錄模型後再進入配置預覽。」 | `:12639`–`12649` |
| 嚴格合成差異 | `describeSelectedFurnitureMismatch()` 回 `{missing, unexpected, moved}` 時**不擋**，只 `console.warn` ＋非阻斷提示 | 由 `selectedSchemeMismatchNotice()` 提供 | `:12558`–`12594`, `:12727`–`12739` |
| 前進閘門 | `REQUIRED_COMPLETIONS.realistic_3d` 要求前八個內部步驟全完成；`white_model_3d` 另要求 `expectedFurnitureCount===0 或 visibleFurnitureCount>0` | 未滿足即 `goTo` 失敗，`setStatus(firstWorkflowBlocker(...), "error")` | `scene_workflow.js:63`–`81`, `:140`–`148` |
| 回頭作廢下游 | 2D 任一編輯（拖曳、旋轉、刪除、改尺寸）呼叫 `invalidateDownstreamFrom("layout_2d", …)` | 「2D 家具位置已修改，3D 家具配置與第 6 步預覽需要重新產生。」 | `:11838`, `:12487`, `:18578`–`18586` |

家電（冰箱／洗衣機等）在送出前由 `pruneRetiredAppliances()` 移出可擺放清單，只留在 `render_context`，第 6 步不擺（DEC-006、ADR-006；`scene_v2.js:11410`, `:12634`–`12635`）。

## 9. 響應式與無障礙 (Responsive / A11y)

- **斷點行為：** 版面由 `site.css` 的 `.rp-split-workspace`／`.rp-3d-workspace` 控制（3D 主畫面＋右側控制欄）；本 repo 無獨立斷點規格文件，斷點值**待確認**（§11）。窄版行為僅知 `.rp-configuration-pending { order: -1 }` 會把待處理清單提前（`tests/test_scene_v2_contract.py:1948`）。
- **鍵盤操作：** stage 切換、房間膠囊、待處理列動作皆為原生 `<button>`，Tab 可達；四個 dialog 使用原生 `<dialog>`（Esc 關閉為瀏覽器預設）。**3D viewer 內的家具選取、拖曳、旋轉只支援 pointer 事件，無鍵盤替代路徑**（`scene_viewer.js:5022`, `:5395`）——已知缺口。
- **ARIA 現況：** `#white-model-viewer[aria-label="3D 資料庫家具配置"]`（`scene.html:698`）、側欄分頁 `role="tablist"`＋`aria-selected`（`:702`–`706`）、`aria-live="polite"` 用於 `#configuration-pending-list`、`#surface-room-progress`、`#surface-preview-status`、`#room-scheme-status`、`#room-scheme-progress`、`#room-scheme-warning`、`#white-model-error`、`#layout-error`。
- **未驗證項／已知缺口：** `#white-model-status`（`scene.html:699`）**無 `aria-live`**，§5 的 Loading（3D 未就緒）與 3D 拖曳彈回訊息不會被螢幕閱讀器主動播報（同 `rp-viewer-status` 類名的 `#ai-render-status` 亦同，見 `ui_spec-step8-ai-render.md` §9）；對比度、focus ring、待處理紅色標記（`.is-invalid`）是否有非色彩替代標示、3D 場景的替代文字描述；repo 內無無障礙稽核紀錄，WCAG 等級未定，屬 TO-BE。

## 10. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | 無（repo 內查無 Figma 連結或設計稿）——**待確認** |
| Design Tokens | 無獨立 token 檔；樣式集中於 `backend/server/static/site.css`（單檔） |
| 元件對照 | 無元件庫；DOM id 與 `[data-*]` 選擇器即介面契約，斷言於 `tests/test_scene_v2_contract.py`（例：`:1926` 要求 `#configuration-pending-list`、`:3811` 要求 `#confirm-white-model`、`:3938`–`3939` 要求 A／B 各 3 組） |
| 快取鍵 | `scene.html` 對 `scene_v2.js`／`site.css` 的 `?v=sha256-<前 12 碼>` 必須等於實檔雜湊（`tests/test_scene_v2_contract.py:24`–`28`）；模組間 import 亦帶同式雜湊（`:739`–`741`），例如 `scene_viewer.js?v=sha256-71d789a189b6`（`scene_v2.js:1`） |
| 已知限制 | `#layout-2d-step` 正常流程不出現（§5）；`#realistic-3d-step` 永不顯示但仍載入 3D 場景（§2）；三組方案工具列為隱藏相容 DOM；GLB 頁面級 LRU 上限 48、面材貼圖快取無淘汰策略（NFR-021） |

## 11. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-007（只用已驗證型錄）、DEC-008（真的放得下）、DEC-009（A／B 同一套檢查）——狀態皆為**待 owner 核准** |
| 對應功能需求 | FR-029、FR-030、FR-031、FR-032、FR-033、FR-034、FR-035、FR-036、FR-037、FR-038、FR-039、FR-040、FR-041、FR-042、FR-043、FR-044、FR-045、FR-050、FR-051、FR-052；跨步 FR-020、FR-021、FR-023、FR-024 |
| 對應非功能需求 | NFR-006（分頁邊界）、NFR-007／NFR-008（型錄連線與降級）、NFR-015（5 cm 網格）、NFR-016（擺位決定性）、NFR-017（公分制）、NFR-019（無認證）、NFR-021（前端資產快取） |
| 對應驗收條件 | ACPT-027–ACPT-040、ACPT-044、ACPT-045 |
| 對應情境 | SCN-017–SCN-025、SCN-040–SCN-042 |
| 對應架構決策 | [ADR-001](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)、[ADR-002](../03_architecture/adr/ADR-002-engine-sole-geometry-authority.md)、[ADR-003](../03_architecture/adr/ADR-003-dual-path-shapely-raster-engine.md)、[ADR-005](../03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md)、[ADR-006](../03_architecture/adr/ADR-006-appliances-render-context-only.md)、[ADR-007](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md) |
| 對應模組 | MOD-WEB（`backend/server/static/`）、MOD-SRV-SCENE、MOD-ENG（`backend/engine/`）、MOD-CAT、MOD-AGT |
| 對應測試 | TC-027–TC-040、TC-044、TC-045 |
| 對應 Runbook | RB-007（[runbook-placement-blocked](../06_ops/runbook-placement-blocked.md)）、RB-008（[runbook-glb-asset-missing](../06_ops/runbook-glb-asset-missing.md)）、RB-001（[runbook-catalog-db-unavailable](../06_ops/runbook-catalog-db-unavailable.md)） |
| 相鄰步驟 | [ui-spec-step5](ui_spec-step5-requirements.md) → 本步 → [ui-spec-step7](ui_spec-step7-proposal-review.md) |
| 需求規格 | [srs](../01_requirements/srs.md)、[prd](../01_requirements/prd.md)；端點契約 [api-spec](../04_design/api_spec.md)、[openapi-scene](../04_design/openapi-scene-v1.yaml)；架構 [sad](../03_architecture/sad.md) |

### 待確認事項

1. **`validateFurniturePosition()` 是死碼**：`scene_v2.js:11761`–`11774` 定義了 2D 單件 `/api/scene/validate` 呼叫，但全檔**無任何呼叫點**；2D 拖曳實走 `resolveFurniturePosition()` → `/api/scene/layout`（`:11776`–`11815`）。「拖曳後回打 `/api/scene/validate`」只在 3D 成立（`scene_viewer.js:5420`）。ACPT-031 若以 2D 拖曳描述驗收，需改為 3D 路徑或補上 2D 呼叫；由 MOD-WEB owner 裁定。
2. **`#layout-2d-step` 面板的定位**：正常流程不顯示（§5）。它是保留的除錯／回退介面，還是應退役的舊版 UI？影響 FR-023 的驗收面（目前只能由 `#configuration-plan-furniture-layer` 涵蓋）。
3. **`#realistic-3d-step` 為不可達面板但仍耗資源**：`realisticViewer` 在 `realistic_3d` 步驟仍 `loadScene()`（`scene_v2.js:1670`–`1671`, `:14498`–`14500`），渲染進永不顯示的容器。是否移除待 owner 決定。
4. **`updateRoomSurfaces()` 的第二個參數被忽略**：呼叫端傳房間 id（`scene_v2.js:14628`, `:14751`, `:14771`），但 viewer 簽章只收 `sceneData`（`scene_viewer.js:4201`），實際一律整屋房殼比對 `shellKey`。是介面漂移還是刻意保留，需確認；影響「逐房材質只更新該房」的敘述是否成立。
5. **選件規則兩套並存**：多房與單房路徑的餐椅與同族去重規則不同（OPEN-39），第 6 步畫面上無法分辨走了哪一套，`#layout-furniture-list` 的件數差異因此不可預期。
6. **型錄基準數字不一致**：`main.py:919` 的 `== 8675` 與健康 view 實際 8,076（OPEN-06），影響 `#open-furniture-catalog` 可搜到的候選集合。
7. **響應式斷點與無障礙標準**：repo 內無斷點規格、無 a11y 稽核紀錄、無 Figma 來源；3D 編輯無鍵盤替代路徑（§9）。
