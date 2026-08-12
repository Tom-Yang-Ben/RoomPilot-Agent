# UI 規格：第 4 步 空間與結構 (UI Spec - Step 4 Space Confirmation) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-WEB（Bella）；驗收條件會簽 QA
> **語域:** L3（工程）
> **實例:** 每頁面一份（本份對應內部步驟 `space_confirmation`，對外導覽第 4 顆按鈕）
> **回答的問題:** `#space-step` 有哪些區塊、DOM id、欄位、狀態、驗證與文案？前端與 QA 不用猜。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。DOM id 與 UI 文案逐字取自 `scene.html`／`scene_v2.js` 實檔；行號隨程式碼演進，衝突時以原始碼為準。

本文件回答：第 4 步這一個面板的版面、元件 id、操作、狀態、驗證規則與輸出 payload。
本文件**不含**：跨步驟旅程與情緒（見 [ux_research_and_journey.md](ux_research_and_journey.md)）、八步導覽與面板對應表（見 [information_architecture.md](information_architecture.md)）、辨識演算法與 `layout_json` 欄位（見 [ui_spec-step3-recognition.md](ui_spec-step3-recognition.md) 與 [../01_requirements/srs.md](../01_requirements/srs.md)）、家具合法性（第 6 步，見 [ui_spec-step6-layout-2d.md](ui_spec-step6-layout-2d.md)）。

## 目錄

- [1. 頁面目的 (Page Purpose)](#1-頁面目的-page-purpose)
- [2. 版面配置 (Layout)](#2-版面配置-layout)
- [3. 欄位與元件 (Fields / Components)](#3-欄位與元件-fields--components)
- [4. 使用者操作 (Actions)](#4-使用者操作-actions)
- [5. UI 狀態 (States)](#5-ui-狀態-states)
- [6. 互動規格 (Interaction Spec)](#6-互動規格-interaction-spec)
- [7. 驗證規則 (Validation)](#7-驗證規則-validation)
- [8. 響應式與無障礙 (Responsive / A11y)](#8-響應式與無障礙-responsive--a11y)
- [9. 輸出契約 (Output Contract)](#9-輸出契約-output-contract)
- [10. 已知缺口與待確認](#10-已知缺口與待確認)
- [11. 追溯](#11-追溯)

## 1. 頁面目的 (Page Purpose)

讓使用者把「電腦辨識出來的房間與結構」逐項改成「他認可的房間與結構」，並在確認尺寸標註後把唯一結構基準交給後續步驟。這是 `layout_json` → `floorplan_editor` 的人工介入點（ADR-001）。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 3 步確定尺寸；`REQUIRED_COMPLETIONS.space_confirmation = [project, upload, recognition, calibration]`（`scene_workflow.js:47`） |
| 出口 | 第 5 步需求問卷（`confirmDimensionedPlan()` → `goTo("requirements")`，`scene_v2.js:6716`）；可退回第 3 步重新校正比例尺（`#recalibrate-space`） |

導覽膠囊文案：`步驟 4 / 先確認房間，再確認牆、門、窗、樑與柱`（`scene_v2.js:302`）。

## 2. 版面配置 (Layout)

同一個 `<section id="space-step" data-panel="space">`（`scene.html:168`）內含兩個互斥模式，由 `setSpaceReviewMode()` 切換 `hidden`（`scene_v2.js:6673-6685`）：

```text
模式 A：編輯（#space-editor-workspace，.rp-split-workspace）
┌ 左 .rp-plan-pane ───────────────────┬ 右 aside.rp-control-pane ─────────┐
│ 標題列＋#show-all-rooms＋#room-editor │ [房間 | 牆門窗樑柱] data-space-tab │
│ #plan-structure-legend（結構頁才顯示）│ #room-confirmation-panel           │
│ #space-plan-stage                    │   或 #structure-confirmation-panel  │
│   ├ img#space-plan-image             │ #space-error                        │
│   └ svg#space-plan-overlay           │ #confirm-space                      │
│ #design-scheme-compare（永遠隱藏，§10）│                                    │
│ #space-plan-caption                  │                                     │
└──────────────────────────────────────┴────────────────────────────────────┘

模式 B：尺寸複核（#space-dimension-review，整頁單欄）
 header ＋ #dimension-calibration-state
 摘要：#dimension-total-area、#dimension-room-count
 #dimensioned-plan-stage（img#dimensioned-plan-image + svg#dimensioned-plan-overlay）
 #dimensioned-plan-legend ＋ .rp-estimate-notice（±5% 免責）
 #back-to-space-editor | #recalibrate-space | #confirm-dimensioned-plan
```

無 Figma 或設計稿來源；版面唯一權威是 `backend/server/static/scene.html:168-408` 與 `site.css`（ADR-010：正式前端＝`backend/server/static/`）。

## 3. 欄位與元件 (Fields / Components)

### 3.1 平面圖疊層

| 元件 | 型態 | 來源 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#space-plan-image` | `<img>` | `GET /api/projects/{id}/floorplan/source` | 與第 3、5、6 步共用同一張原圖 |
| `#space-plan-overlay` | `<svg>` | `renderSpaceOverlay()` | `viewBox` 由 `syncOverlayToImage()` 設為 `0 0 naturalWidth naturalHeight`，並對齊 `<img>` content rect（`scene_v2.js:1935-1947`） |
| `#dimensioned-plan-overlay` | `<svg>` | `buildDimensionedPlanAnnotations()`（`scene_dimensioned_plan.js`） | 逐房彩色輪廓＋水平寬度線＋垂直長度線；圖例列出 `寬 × 深 cm` |
| 房間節點 | SVG 圓點（紫） | `state.rooms[].polygon_cm` | 可拖曳；拖曳後長寬與面積即時重算 |

### 3.2 房間分頁（`#room-confirmation-panel`）

| 欄位／元件 | 型態 | 對應狀態 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#room-name` | `<select>`（HTML 寫死 12 個 option，`scene.html:179-192`） | `room.visual_space_type` | 值域實際由 JS `ROOM_NAME_OPTIONS`（10 筆，`scene_v2.js:136-147`）決定，兩份不同步，見 §10 |
| `#save-room` | button | `saveRoom()` | 套用後 `room.confirmed=false`、`source="manual_confirmation"` |
| `#room-area` | text | `roomDimensions(room)` | `系統依目前框選計算：W × D cm，A m²` |
| `#room-list` | 動態清單 | `state.rooms` | 每列：名稱、`m²`、`W × D cm`、`已確認`／`信心 NN%`、複核提示、`確認`／`刪除` 鍵（`scene_v2.js:2974-2996`） |
| `#room-confirmation-progress` | text | 計數 | `已確認 M / N 個房間` |
| `#confirm-all-rooms` | button | `confirmAllRooms()` | 全數已確認時 `disabled` 且文案改為 `全部房間已確認` |
| `[data-room-geometry-mode]` | button×2 | `merge` / `split` | 搭配 `#apply-room-merge`、`#cancel-room-geometry`（預設 hidden） |
| `[data-room-node-mode]` | button×2 | `merge` / `split` | 節點合併與邊線切割；搭配 `#apply-node-merge`、`#cancel-node-edit` |

### 3.3 結構分頁（`#structure-confirmation-panel`）

四種結構工具由 `[data-structure-tool]` 驅動；`[data-structure-section]` 五個分頁對應 `structureCollections = {door:doors, window:windows, wall:walls, beam:beams, column:columns}`（`scene_v2.js:3418-3424`）。每個分頁的標題、單位與指引取自 `structureSectionMeta`（`scene_v2.js:3492-3528`）。

| 分頁 | 新增鍵文案 | 進度單位 | 建立方式 |
| :--- | :--- | :--- | :--- |
| 門 | `＋ 新增門` | `扇門` | 點圖放置後磁吸最近牆 |
| 窗 | `＋ 新增窗` | `扇窗` | 同上；另有窗型與窗台高 |
| 牆 | `＋ 畫牆` | `面牆` | 點起點與終點兩下 |
| 樑 | `＋ 畫樑` | `道樑` | 按住拖曳起訖，自動對齊水平／垂直並磁吸 |
| 柱 | `＋ 新增柱` | `根柱` | 點圖放置 |

選取後的編輯器 `#selected-structure-editor` 欄位：`#selected-structure-size-cm`、`#selected-structure-length-cm`、`#selected-structure-depth-cm`、`#selected-structure-height-cm`、`#selected-window-type`（`standard` / `floor_to_ceiling`）、`#window-sill-height-cm`（預設 90）、`#opening-width-slider`（`min=30 max=400 step=1`，`scene.html:327`）與 `±5 cm` 步進鍵。動作鍵：`#apply-structure-size`、`#lock-selected-door-opening`、`#flip-selected-door`、`#rotate-selected-door-180`、`#rotate-selected-structure-left|right`（±15°）、`#delete-selected-structure`。樑柱另有 `#structure-3d-preview`（正視／側視／透視，`scene_structure_preview.js`）。

面板底部：`#structure-counts`、圖例、兩個必勾核取方塊 `#structure-confirmed`、`#estimated-size-ack`（`scene.html:369-370`）。

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 下游影響 |
| :--- | :--- | :--- | :--- |
| 切換確認內容 | `[data-space-tab]` | 切 `#room-confirmation-panel` ↔ `#structure-confirmation-panel`，並改寫 `#space-plan-caption` | 無 |
| 套用空間名稱 | `#save-room` | 寫 `label/type/room_type/visual_space_type`，並把該房重設為未確認 | `invalidateDownstreamFrom("space_confirmation")` |
| 逐房確認 | `[data-confirm-room]` | `confirmed=true`、`confidence=1`、去掉標題的「（待確認）」 | 只存檔，不作廢下游 |
| 一鍵確認全部房間 | `#confirm-all-rooms` | 對**全部**房間設 `confirmed=true`（含被標記需複核者，見 OPEN-32） | 只存檔 |
| 拖曳房間節點 | pointer 拖曳紫色節點 | 重算長寬面積，該房 `confirmed=false` | 作廢下游 |
| 新增結構 | `[data-structure-tool]` 點選或拖放到 `#space-plan-stage` | 依分頁建立門／窗／牆／樑／柱，磁吸最近牆 | 作廢下游 |
| 拖曳牆端點 | pointer | 附著門窗依比例重定位並回到未確認（`applyAttachedOpeningUpdates`，`scene_v2.js:3479-3488`） | 作廢下游 |
| 鎖定門洞 | `#lock-selected-door-opening` | `snapOpeningToHostWall()` 成功才 `confirmed=true`、`opening_source="manual_confirmed"` | 作廢下游 |
| 完成空間與結構確認 | `#confirm-space` | 四道前置檢查全過才進入尺寸複核模式（§7） | 無 |
| 確認尺寸標註 | `#confirm-dimensioned-plan` | 拍下 `confirmedStructureSnapshot`、`workflow.complete("space_confirmation", …)`、跳第 5 步 | 前進 |

第 4 步無角色權限概念——Pilot 全 app 無認證（NFR-019，狀態待 DEC-014 核准）。

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案 |
| :--- | :--- | :--- |
| Loading | 全畫面遮罩 `#placement-busy`（深度計數，`scene_v2.js:1544-1558`） | 依觸發流程而定 |
| Empty（無房間） | `#room-list` 空、`#confirm-all-rooms` disabled、`#show-all-rooms` disabled | `目前只有一個空間，沒有其他框選可顯示`（title） |
| Error（欄內） | `#space-error`（`aria-live="polite"`）／結構碰撞 `#structure-wall-collision-error`／尺寸複核 `#dimension-review-error` | 見 §7 |
| 需複核提示 | `#room-list` 每列 `.rp-room-review-hint` | 由 `REVIEW_REASON_LABELS` 四種 reason 對應（`scene_recognition_review.js:14-22`） |
| 存檔被伺服器擋下 | `PUT /api/projects/{id}/workflow` 回 422 `recognition_review_unresolved` | `系統標記需人工複核的房間尚未逐一確認，無法將空間確認標為完成；請回到第 4 步處理。`（`main.py:1820-1825`） |
| Success | `#project-save-status` 與狀態列 | 例：`已一次確認 N 個房間；仍可逐房修改名稱或框選。` |
| Permission Denied | 不適用（無認證與角色，NFR-019） | — |

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover／選取 | Disabled | 錯誤反應 |
| :--- | :--- | :--- | :--- |
| `[data-structure-tool]` | 再點一次同一工具＝取消（`state.structureTool` toggle，`scene_v2.js:18021-18030`） | — | 取消時走 `cancelStructureInteraction()` |
| 結構標記（SVG） | 選取者橘黃；門橘色弧、窗藍線、牆深灰（`scene.html:362-368` 圖例） | — | — |
| 樑／柱拖曳 | 即時 `resolveStructureWallCollisions`（`touchToleranceCm=0.5`、`maxAutoShiftCm=75`、`maxIterations=16`，`scene_structure_geometry.js:262-307`） | — | 無法解時位置還原並顯示 `樑柱不可穿過牆體；位置未變更。` |
| 牆端點拖曳 | 附著門窗同步平移 | 新牆長 < 門寬 + 10 cm 時整段拒絕 | `牆端點未變更：請避開過短牆段與附著門窗洞口。` |
| `#confirm-all-rooms` | — | 無房間或全部已確認時 disabled | — |
| 所有拖曳 | 一律 pointer events，於 `window` 單一 `pointerup` 收尾（`scene_v2.js:17755-17843`） | — | 每種拖曳各有 `changed`／`blocked` 兩種收尾分支 |

## 7. 驗證規則 (Validation)

`confirmSpace()` 依序四道檢查，任一不過即停在編輯模式並把焦點送到問題處（`scene_v2.js:6584-6619`）：

| 順序 | 規則 | 錯誤訊息 | 焦點 |
| :--- | :--- | :--- | :--- |
| 1 | 每個 `state.rooms[].confirmed === true` | `尚有 N 個房間未確認，請逐一按右側房間的「確認」鍵。` | 第一個未確認的 `[data-confirm-room]` |
| 2 | 五類結構每一項 `confirmed === true` | `尚有 N 個{門/窗/牆/樑/柱}項目未確認，已為你切到「X」頁。請逐項確認或按「確認此頁全部項目」。` | 自動切到該結構分頁並聚焦第一筆 |
| 3 | `#structure-confirmed` 已勾 | `請切到「牆門窗樑柱」並確認結構。` | 結構分頁按鈕 |
| 4 | `#estimated-size-ack` 已勾 | `請確認已了解圖面估計尺寸可能與現場不同。` | 該核取方塊 |

其他欄位級規則：

| 欄位 | 規則 | 錯誤訊息 |
| :--- | :--- | :--- |
| `#room-name` | 值必須存在於 JS `ROOM_NAME_OPTIONS` | `請選擇空間名稱。` |
| 柱寬／深／高 | 寬、深 ≥ 10 cm；高 ≥ 30 cm（`validateColumnDimensionsCm`，`scene_structure_geometry.js:331`） | `柱寬與深度至少 10 公分，高度至少 30 公分。` |
| 柱旋轉後範圍 | 旋轉後外接矩形須落在 `width_cm × depth_cm` 內 | `旋轉後柱體超出平面圖範圍，請縮小尺寸、調整方向或移動位置。` |
| 門洞鎖定 | 必須找得到 host wall | `找不到可對應的牆體，請先確認門洞位置。` |
| 尺寸複核 | `roomCount > 0` 且 `totalAreaM2 > 0` | `目前沒有可確認的空間尺寸，請返回調整空間或重新校正比例尺。` |
| 刪除房間 | 至少保留一個空間 | `至少需要保留一個空間，無法刪除最後一個空間。` |

伺服器端第二道閘（ACPT-006、SCN-010）：`PUT /api/projects/{id}/workflow` 在 `_flow.completed` 含 `space_confirmation` 時，比對 `recognition.spatial_report.review_items` 與 `space_confirmation.rooms[].confirmed`，任一被標記的房間仍未確認即回 422，body 為 `{code:"recognition_review_unresolved", message, rooms:[{room_id,label,reason}]}`（`main.py:1737-1781,1815-1827`）。房間 id 已不存在（刪除／合併／切割）視為已處理。維運處置見 [../06_ops/runbook-recognition-failed-or-review-blocked.md](../06_ops/runbook-recognition-failed-or-review-blocked.md)。

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** 兩欄 `.rp-split-workspace` 的斷點只定義在 `site.css`，本文件不重述；未見獨立行動版版面。
- **鍵盤操作:** 驗證失敗會以 `.focus()` 主動移動焦點（§7）。SVG 疊層上的節點與結構拖曳**只綁 pointer events**，無鍵盤等價操作——待確認（見 §10）。
- **ARIA:** `role="tablist"` 用於 `.rp-segmented`（`scene.html:244`）與 `.rp-structure-kind-tabs`（`scene.html:264`），`[data-structure-section]` 切換時同步 `aria-selected`（`scene_v2.js:6516-6520`）；`aria-live="polite"` 用於 `#space-error`、`#structure-wall-collision-error`、`#dimension-review-error`；`#show-all-rooms` 依房間數維護 `aria-disabled` 與 `title`。
- **對比 / WCAG 等級:** 未在 repo 內宣告，亦無自動化檢查——待確認。

## 9. 輸出契約 (Output Contract)

`confirmedFloorplanEditor(schemeId)`（`scene_v2.js:2216-2241`）產出第 4 步的唯一對外 payload，寫入 `workflow.space_confirmation` 並在第 6 步隨 `POST /api/scene/generate` 送出（FR-018、ADR-007）：

```json
{
  "coordinate_unit": "cm",
  "width_cm": 0, "depth_cm": 0, "room_height_cm": 270,
  "rooms": [],
  "structures": { "walls": [], "doors": [], "windows": [], "beams": [], "columns": [] }
}
```

- `width_cm`／`depth_cm` 取 `confirmedFloorplan.floorplan` 的值，缺值時退回 `plan_bbox_px × scale` 且下限 240 cm；`room_height_cm` 預設 270。
- `structures` 來自 `state.confirmedStructureSnapshot`（在 `#confirm-dimensioned-plan` 當下拍攝），舊專案首次讀取時就地補拍一次。
- **門洞不變量**（ACPT-017、SCN-013）：已確認的門帶 `step4_confirmed:true` 與 `confirmed_wall_opening`，在 3D **不切牆洞**（`step4_skip_wall_cut`）；開口依序取 `persisted_step4_wall_gap` → `confirmed_wall_gap` → `projected_wall_line` → `unresolved_closed_leaf`（`scene_architecture.js:241-272`）。使用者可見結果：一扇已確認的門在白模只出現**一個**洞口與一片門，不會出現雙洞。
- 家具座標不在本步驟產生，也不得由本步驟計算（ADR-002）。

## 10. 已知缺口與待確認

| 項目 | 現況（可佐證） | 承接 |
| :--- | :--- | :--- |
| OPEN-32：一鍵確認未排除旗標房 | `scene_recognition_review.js:10-11` 註解寫「一鍵確認會跳過被標記的房間」，但 `confirmAllRooms()` 對 `state.rooms` 全數設 `confirmed=true`（`scene_v2.js:3037-3043`）。**結果：ACPT-006 的 422 閘門在正常操作路徑不會被觸發**，僅在直接呼叫 API 或舊資料時才會擋。是否接受待 owner 決定。 | [../05_qa/test_plan.md](../05_qa/test_plan.md)、`tests/test_recognition_review_wiring.py` |
| OPEN-29：`host_wall_id` 編輯後失效 | 辨識端以 `wall-{1-based index}` 產生（非穩定 ID）；第 4 步畫牆／刪牆會改變牆陣列順序即失效。`openingBelongsToWall` 優先信 `host_wall_id`，無 id 才走幾何比對（`scene_architecture.js:194-222`）。重算機制是否存在待確認。 | [../04_design/lld.md](../04_design/lld.md)、[../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md) |
| 房名詞彙表兩份不同步 | HTML 12 個 option vs JS `ROOM_NAME_OPTIONS` 10 筆；只有 6 個值兩邊都有。HTML 專有的 `dining_room`／`primary_bedroom`／`secondary_bedroom`／`multi_purpose`／`circulation`／`study` 是死選項（選了跳「請選擇空間名稱。」）；JS 專有的 `hallway`／`bedroom`／`stair`／`garage` 永遠選不到。登記處：`tests/test_scene_v2_contract.py:31-60`。 | 同上 |
| A/B 比較區塊永不顯示 | `#design-scheme-compare` 與 `#scheme-a-plan-image/overlay`、`#scheme-b-plan-image/overlay` 存在於 `scene.html:217-240`，但 `renderSchemeComparison()` 硬寫 `const show = false`（`scene_v2.js:4649`），註解說明「第 4 步只確認唯一結構基準；家具方案比較留在第 6 步」。`structuresForScheme()` 也 `void schemeId`（`scene_design_schemes.js:114-122`），A/B 不影響本步輸出。 | [ui_spec-step6-layout-2d.md](ui_spec-step6-layout-2d.md) |
| 可拆牆預覽恆為兩張相同圖 | `#wall-removal-preview` 在牆分頁顯示，但 `renderWallRemovalPreviews()` 一開頭呼叫 `normalizeWallDemolitionCandidates()` 把所有 `demolition_candidate` 設回 `false`（`scene_v2.js:3546-3550,3576`），且 `applyWallDemolitionType()` 對標記請求直接回警告。摘要恆為 `尚未標記可拆牆；兩個預覽目前相同。` 是否正式退役待確認。 | [../04_design/lld.md](../04_design/lld.md) |
| 疊層無鍵盤等價操作 | 節點與結構拖曳只綁 pointer events；repo 內無替代輸入路徑，亦無 a11y 稽核紀錄。 | 待 owner 決定是否納入 Pilot 範圍 |

## 11. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-004（人工確認才算數）、DEC-018（結構變更使下游失效）——狀態均為待 owner 核准 |
| 對應功能需求 | FR-007（複核閘門）、FR-018（`floorplan_editor` 公分輸出）、FR-019（已確認門不切牆洞）、FR-021（前進條件與下游作廢）、FR-023（疊層座標轉換） |
| 對應非功能需求 | NFR-017（公分單位契約） |
| 對應驗收條件 | ACPT-006、ACPT-016、ACPT-017 |
| 對應 BDD 情境 | SCN-010（旗標房未確認擋住完成）、SCN-013（新增牆與門，3D 單一門洞） |
| 對應架構決策 | [ADR-001](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)、[ADR-007](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md) |
| 對應模組 | MOD-WEB（`scene.html:168-408`、`scene_v2.js`、`scene_structure_geometry.js`、`scene_structure_utils.js`、`scene_architecture.js`、`scene_dimensioned_plan.js`、`scene_recognition_review.js`）、MOD-SRV-API（`main.py:1737-1827`） |
| 對應測試 | TC-006（`tests/test_recognition_review_wiring.py`）、TC-016（`tests/test_scene_v2_contract.py`、`tests/test_scene_shell_geometry.py`）、TC-017（`tests/test_scene_shell_geometry.py`、`tests/test_scene_3d_lifecycle_contract.py`） |
| 對應 Runbook | RB-006（[runbook-recognition-failed-or-review-blocked.md](../06_ops/runbook-recognition-failed-or-review-blocked.md)） |
| 待確認 | OPEN-29、OPEN-32（詳見 §10） |

- **上游**：[../01_requirements/srs.md](../01_requirements/srs.md)、[information_architecture.md](information_architecture.md)、[ui_spec-step3-recognition.md](ui_spec-step3-recognition.md)
- **下游**：[ui_spec-step5-requirements.md](ui_spec-step5-requirements.md)、[ui_spec-step6-layout-2d.md](ui_spec-step6-layout-2d.md)、[../04_design/lld.md](../04_design/lld.md)、[../05_qa/test_plan.md](../05_qa/test_plan.md)
