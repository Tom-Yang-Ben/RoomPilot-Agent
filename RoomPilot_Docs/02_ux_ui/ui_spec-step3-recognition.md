# UI 規格：第 3 步 確定尺寸 (UI Spec - Step 3 Recognition) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-WEB（Bella）；辨識輸出契約由 MOD-FP（Cody）持有
> **語域:** L3（工程）
> **實例:** 八步 UI 規格之一（第 3 步）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。DOM id 與 UI 文案逐字取自 `scene.html`／`scene_v2.js` 實檔；行號隨程式碼演進，衝突時以原始碼為準。

本文件回答：`#scale-step` 面板有哪些 DOM 元素、資料從哪個欄位來、兩點標定怎麼互動、疊層座標怎麼對齊、哪些狀態與錯誤文案必須存在。
本文件**不含**：辨識演算法與 `layout_json` 欄位定義（見 [srs](../01_requirements/srs.md) 與 [lld](../04_design/lld.md)）、第 4 步房間與結構編輯（見 [ui-spec-step4](ui_spec-step4-space-confirmation.md)）、辨識失敗的維運處置（見 [runbook-recognition](../06_ops/runbook-recognition-failed-or-review-blocked.md)）。
要找端點契約去 [api-spec](../04_design/api_spec.md)；要找步驟間導覽規則去 [ia](information_architecture.md)。

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

讓屋主在辨識完成的平面圖上指定一段已知長度，把圖面像素換算成公分尺度，供第 4 步之後的所有幾何使用。對應旅程節點見 [ux-research](ux_research_and_journey.md)。

面板為 `#scale-step`（`scene.html:111`，`data-panel="scale"`）。內部工作流的 `recognition` 與 `calibration` 兩步共用這一個面板，對外折疊為第 3 步（`scene_v2.js:311-322`，ADR-010）。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 2 步 `#upload-step` 按「確認並開始辨識」；`confirmUpload()` 在 `analyze` 成功後才 `showStep("recognition")`（`scene_v2.js:1829-1863`）。另一入口是重整後還原（`scene_v2.js:19300-19332`） |
| 出口 | 第 4 步 `#space-step`；`applyCalibration()` 完成 `calibration` 後 `goTo("space_confirmation")`（`scene_v2.js:2189-2196`） |

## 2. 版面配置 (Layout)

```text
.rp-split-workspace.rp-calibration-workspace
├── .rp-plan-pane                      左：圖面
│   ├── .rp-pane-heading  「3 確定尺寸 / 選一段您確定的長度」＋ #recognition-summary
│   ├── #floorplan-calibration-stage   role="application"
│   │   ├── #floorplan-calibration-image   <img>
│   │   └── #floorplan-calibration-overlay <svg>（標定線與兩端點）
│   └── .rp-calibration-plan-hint      「建議選擇圖面上標示清楚、距離較長的牆面…」
└── .rp-control-pane.rp-calibration-panel   右：三段任務流
    ├── #calibration-task-points   ① 選擇起點與終點 → #calibration-readout
    ├── #calibration-task-measure  ② 輸入實際尺寸  → #floorplan-scale-cm、#scale-error
    ├── #calibration-task-confirm  ③ 確認比例
    └── .rp-calibration-actions    #reset-floorplan-calibration、#apply-floorplan-calibration
```

無 Figma 稿；此結構即 `scene.html:111-166` 的實際 DOM。

## 3. 欄位與元件 (Fields / Components)

| 欄位 | 型態 | 來源（API 欄位） | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#recognition-summary` | text | `analysis.walls/doors/windows` 長度，DXF 路徑退回 `analysis.floorplan.wall_count/door_count/window_count` | 「辨識結果：牆 N、門 N、窗 N」；有複核項時附「；系統標記 N 間房需人工複核」（`scene_v2.js:1848-1854`、`:2935-2944`）。初值「等待辨識」 |
| `#floorplan-calibration-image` | img | `GET /api/projects/{id}/floorplan/source`（附 `?v=<timestamp>` 破快取） | DXF 來源改用 `configureDxfPreview()` 產生的向量預覽 data URL（`scene_v2.js:1846-1848`、`:1870-1905`） |
| `#floorplan-calibration-overlay` | svg | 無（純前端繪製） | `viewBox` 於圖片載入後改寫為 `0 0 naturalWidth naturalHeight`；HTML 初值 `0 0 1000 1000`、`preserveAspectRatio="none"`（`scene.html:120`） |
| `#floorplan-scale-cm` | number（`min=1` `step=0.1` `inputmode=decimal`） | `analysis.scale.distance_cm`；無則 `distance_m × 100`（四捨五入到 0.1） | 兩端點未就緒時 `disabled`（`scene_v2.js:1855-1859`、`:2035-2037`） |
| `#calibration-readout` | text `aria-live=polite` | 前端狀態 | 0 點「請先在圖面點選起點。」／1 點「起點已選好，請再點一下終點。」／2 點「兩個端點已選好，圖上距離 N px；仍可拖曳微調。」（`scene_v2.js:1993-2010`） |
| `#scale-error` | text `aria-live=polite` | `calibrationActionState()` 回傳 `message` | 只在兩端點就緒後寫入；`dataset.kind` 取 `ready`／`instruction`（`scene_v2.js:2058-2061`） |
| `#calibration-task-*-status` | text | 前端狀態 | 三段任務各自「進行中／完成／待選點／待完成／可確認」，並切 `is-active`／`is-complete`／`is-pending`（`scene_v2.js:2013-2056`） |

**辨識結果的實際呈現範圍（誠實界線）**：第 3 步疊層只畫標定線與兩個端點（`renderCalibration()`，`scene_v2.js:1993-2007`）；牆／門／窗／房間多邊形不在此步繪製，房間框選要到第 4 步 `#space-plan-overlay` 才出現。`geometry_engine`（`"cody"`／`"dxf"`）由 analyze 回應提供並寫入 workflow `_flow.data.recognition.engine`（`main.py:3050-3053`、`scene_v2.js:1833`），**畫面上沒有對應顯示元素**——ACPT-009 的「正確標示」目前只在 API 回應與存檔快照層成立，UI 層為缺口（待確認 1）。

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 放置端點 | `#floorplan-calibration-overlay` 的 `pointerdown`（未命中既有端點） | `imagePoint()` 把游標換算成原圖像素；未滿 2 點則 push，已有 2 點則取代較近的那一點（`scene_v2.js:2066-2084`） | Pilot 無認證與角色（`main.py:195-197`，NFR-019 待 DEC-014 核准） |
| 拖曳端點 | `circle[data-calibration-point]` 的 `pointerdown` → `setPointerCapture` → `pointermove` | 即時更新該端點並重繪；`window` 的單一 `pointerup` 清 `state.calibrationDragIndex`（`scene_v2.js:2086-2092`、`:17752-17756`、`:17846`） | 同上 |
| 輸入實際公分 | `#floorplan-scale-cm` 的 `input` | `updateCalibrationAction()` 重算三段任務狀態與按鈕可用性 | 同上 |
| 重新選擇端點 | `#reset-floorplan-calibration` click | 清空 `state.calibrationPoints` 並重繪（`scene_v2.js:17845-17848`） | 同上 |
| 確認尺寸並顯示房間 | `#apply-floorplan-calibration` click | `buildScaleCalibration()` → 影像路徑再過 `applyCalibrationToAnalysis()` → 寫 `state.confirmedFloorplan`（`confirmation_status:"room_review_pending"`）→ `complete("calibration")` → `goTo/showStep("space_confirmation")` → `scheduleSave`（`scene_v2.js:2174-2200`） | 同上 |

DXF 來源（`state.sourceExtension === ".dxf"`）跳過 `applyCalibrationToAnalysis()`，直接沿用解析器輸出的公分尺度（`scene_v2.js:2183-2186`，ACPT-015）。

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案 |
| :--- | :--- | :--- |
| Loading | 第 2 步的狀態列（analyze 尚未回來，使用者仍在上傳面板） | 「正在保存原圖並辨識牆、門、窗…」（`scene_v2.js:1805`） |
| Loading（套用比例） | 狀態列 | 「正在套用確認的公分尺度…」（`scene_v2.js:2182`） |
| Empty（無建議端點） | 兩端點皆空、`#floorplan-scale-cm` disabled | 「辨識完成。現在請在圖上拉兩端，並輸入這一段的實際公分尺寸。」；有 `evidence` 時改為「已標出建議端點。請拖曳確認兩端位置，再輸入實際公分尺寸。」（`scene_v2.js:1860-1862`） |
| Error（DXF 解析失敗） | 422 `dxf_parse_failed`，寫入第 2 步 `#upload-error` 並轉紅狀態列 | 「DXF 無法解析：{原始例外訊息}」（`main.py:3002-3011`；`focus:"floorplan-file"`） |
| Error（影像辨識失敗） | 422 `cody_recognition_failed`，同上 | 「Cody 無法辨識這張平面圖：{原始例外訊息}」（`main.py:3024-3032`） |
| Error（未勾確認） | 409 `floorplan_confirmation_required` | 「請先確認圖檔內容正確，才能開始辨識。」（`main.py:2986-2993`；`focus:"project-floorplan-confirmation"`） |
| Permission Denied | 不適用（Pilot 全 app 無認證與授權層，`main.py:195-197`） | — |
| Success | 狀態列＋直接切到第 4 步 | 「尺度已確認為 {N} cm。現在開始確認 {M} 個房間。」（`scene_v2.js:2194`） |

**三個 analyze 錯誤都不在第 3 步畫面出現**：analyze 由第 2 步的 `confirmUpload()` 呼叫，失敗時 `catch` 把訊息寫進 `#upload-error`，使用者停留在上傳面板（`scene_v2.js:1829`、`:1865-1868`）。第 3 步沒有辨識重試按鈕。

**重跑辨識會清空下游（FR-016、SCN-011）**：伺服器在 analyze 成功時把 `confirmed_floorplan`／`calibration`／`space_confirmation`／`requirements`／`layout_2d`／`white_model_3d`／`realistic_3d` 七個節點一次設為 `null`，並改寫 `_flow.staleFrom="calibration"`（`main.py:3036-3063`）；前端 `complete("recognition")` 走 `markDownstreamStale()` 移除下游完成狀態並刪其 `data`（`scene_workflow.js:175-187`）。**待確認 2**：第 3 步沒有任何明示「先前問卷／配置／3D 已作廢」的警語元素，SCN-011 的可觀察表徵目前只有導覽列完成標記消失。

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `#apply-floorplan-calibration` | 待確認（`site.css` 未逐條核對） | `calibrationActionState().ready` 為 false 時（`scene_v2.js:2057`） | 不適用：套用為本機同步計算，不呼叫 API | `catch` 寫 `#scale-error` 並轉紅狀態列（`scene_v2.js:2197-2200`） |
| `#floorplan-scale-cm` | — | 兩端點不足或像素距離為 0 時 disabled | — | 值 ≤0 時按鈕保持 disabled 並顯示提示 |
| `#reset-floorplan-calibration` | — | 不 disabled，改以 `hidden` 控制（0 點時隱藏） | — | — |
| 端點 `circle` | — | — | — | 重疊時 `#calibration-readout` 改為「兩個端點重疊，請拖曳其中一點。」 |

繪製常數（`scene_v2.js:1993-2002`）：連線 `stroke=#bd5c36`、`stroke-width=5`、`stroke-dasharray="12 7"`；端點 `r=12`、`stroke-width=6`，起點描邊 `#2f6f87`、終點 `#bd5c36`。單位為原圖像素，故顯示尺寸隨圖片縮放比例改變。

### 6.1 疊層座標同步（FR-023、ACPT-021）

`syncOverlayToImage(stage, image, overlay)`（`scene_v2.js:1935-1947`）：

1. `imageContentRect(image)` 以 `Math.min(box.width/naturalWidth, box.height/naturalHeight)` 還原 `object-fit: contain` 的實際內容矩形，並置中補償留白（`scene_v2.js:1916-1933`）。
2. 疊層以 `left/top/width/height` 絕對定位到該 content rect，並把 `right`／`bottom` 設回 `auto`。
3. `viewBox` 設為 `0 0 naturalWidth naturalHeight`——**疊層座標系＝原圖像素**，因此 `state.calibrationPoints` 可以直接當 SVG 座標使用，不需再換算。

觸發點：`setPlanImages()` 對每張圖掛一次性 `load` 監聽（`scene_v2.js:1906-1913`）；`syncAllOverlays()` 一次同步 scale／space／dimension／layout／questionnaire 五個 stage 並重繪各疊層（`scene_v2.js:1962-1980`），在每次 `showStep()` 的 `requestAnimationFrame` 內執行（`scene_v2.js:1605`）。

公分換算不發生在這一層：`cm_per_px = distance_cm / pixel_distance`（`scene_calibration.js:12`）。公分→像素的反向轉換（含 y 軸翻轉）屬第 6 步 `planCmToLayerPixel()`（`scene_layout2d.js:293-305`），見 [ui-spec-step6](ui_spec-step6-layout-2d.md)。

**待確認 3**：`scene_calibration.js:46` 匯出的 `pointerToImagePoint(pointer, displayedRect, naturalSize)` 有 node 契約測試（`tests/test_scene_calibration.py:59-71`），但正式前端 `scene_v2.js:26-29` 只匯入 `buildScaleCalibration` 與 `calibrationActionState`；live 路徑改用 `scene_v2.js:1949-1959` 的 `imagePoint()`。兩者行為不同：`imagePoint()` 會把座標夾限在 content rect 內且不取整，`pointerToImagePoint()` 會 `Math.round` 但不夾限。唯一 import 前者的是未被任何 HTML 載入的孤兒檔 `scene.js:8`。該匯出是否下架，需 owner 決定。

## 7. 驗證規則 (Validation)

| 欄位 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| 端點數 | 必須恰 2 點 | 「請先在平面圖上定位兩個端點。」（`scene_calibration.js:20`） | `calibrationActionState()`；未滿 2 點時**不寫入** `#scale-error`，改由 `#calibration-readout` 承接（`scene_v2.js:2060`） |
| 端點距離 | 像素距離 > 0 | 「兩個端點不能重疊，請重新拖曳其中一點。」（`scene_calibration.js:31`） | 每次 `pointerdown`／`pointermove`／輸入 |
| `#floorplan-scale-cm` | 數值 > 0 | 「請輸入大於 0 的實際公分尺寸。」（`scene_calibration.js:37`） | `input` 事件 |
| 全部就緒 | — | 「尺寸資料已完成，可以確認並顯示房間。」（`scene_calibration.js:42`） | 同上；`#scale-error[data-kind="ready"]` |
| 套用當下 | `buildScaleCalibration()` 對 ≠2 點丟 `calibration_points_required`、對距離或公分 ≤0 丟 `calibration_measurement_invalid`（`scene_calibration.js:2-6`） | `errorMessage()` 無這兩碼的中文映射（`scene_v2.js:647-651`），會原樣顯示英文碼 | 按下確認按鈕（實務上被 disabled 擋住，屬防禦分支） |

**比例信心 <0.8（FR-013、ACPT-011、SCN-008）**：後端在自動比例信心低於 0.8 時於 `layout_json.issues` 加入 `scale_confirmation_required` 並把 `requires_confirmation` 設為 true（`vision/analysis.py:501-502,543-544,655-666`）。**正式前端不讀這兩個欄位做條件式提示**（`grep` 顯示 `scene_v2.js` 僅在 `applyCalibrationToAnalysis` 中清除它們，`:2170-2171`）：第 3 步一律強制兩點手動標定，套用後 `scale.source` 改為 `manual_confirmation`、`confidence=1`、移除 `scale_anchor_missing` 與 `scale_confirmation_required`、`requires_scale_confirmation=false`（`scene_v2.js:2094-2172`），因此低信心情境在 UI 上與高信心情境無差別。`errorMessage()` 雖有中文映射「請重新定位兩個端點並輸入實際公分尺寸。」，但該碼只由 `/api/floorplan/confirm` 產生，而正式前端不呼叫該端點（`main.py:1741` 註解）。**待確認 4**：ACPT-011 的前端側呈現要求是否維持，或改判定為「一律手動標定即滿足」。

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** 待確認——`site.css` 共 16919 行，本文件未逐條核對 `.rp-split-workspace` 的斷點規則。
- **鍵盤操作:** 端點只綁 `pointerdown`／`pointermove`（`scene_v2.js:17752-17754`），**沒有鍵盤替代路徑**，僅用鍵盤無法完成兩點標定；Tab 可達 `#floorplan-scale-cm`、`#reset-floorplan-calibration`、`#apply-floorplan-calibration`。是否納入 Pilot 範圍待 owner 決定（WCAG 2.1 AA 2.1.1）。
- **ARIA / 對比 / Focus:** `#floorplan-calibration-stage` 帶 `role="application"` 與 `aria-label="拖曳尺寸線的起點與終點"`；疊層 `aria-hidden="true"`（`scene.html:118-120`），端點與量測線對輔助技術不可見。任務流 `<ol aria-label="尺寸標定進度">`，`aria-current="step"` 由 `setCalibrationTaskState()` 維護（`scene_v2.js:2013-2020`）。`#calibration-readout` 與 `#scale-error` 為 `aria-live="polite"`；`#recognition-summary` **無** live region。對比度未量測。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | 無（repo 內無設計檔）；SSOT 為 `backend/server/static/scene.html:111-166` |
| Design Tokens | `backend/server/static/site.css`（單一樣式表，無 token 檔） |
| 元件對照 | DOM id ↔ `element` 對照表 `scene_v2.js:347-359`；純函式在 `scene_calibration.js` |
| 已知限制 | 疊層對輔助技術不可見；無鍵盤標定路徑；`geometry_engine` 無 UI 呈現；低信心比例無條件式提示；analyze 錯誤只在第 2 步顯示 |

契約測試（會擋 DOM 與文案漂移）：`tests/test_scene_calibration.py:13-21` 斷言 `#floorplan-calibration-stage`／`#floorplan-calibration-overlay`／`#apply-floorplan-calibration` 與「拖曳兩個端點，再輸入這段的實際公分」「單位固定為公分」兩句文案存在；`:34-51` 以 node 子行程驗 `buildScaleCalibration` 數值。修改文案必須同步改測試。

## 10. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-004（人必須確認尺寸才算數）、DEC-003（沿用既有平面圖）——狀態待 owner 核准 |
| 對應功能需求 | FR-010、FR-011、FR-012、FR-013、FR-016、FR-023；單位契約 NFR-017 |
| 對應驗收條件 | ACPT-009、ACPT-010、ACPT-011、ACPT-012、ACPT-013、ACPT-014、ACPT-021 |
| 對應情境 | SCN-006、SCN-007、SCN-008、SCN-009、SCN-011、SCN-012 |
| 對應架構決策 | [ADR-001](../03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md)（辨識止於 `layout_json`）、[ADR-007](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)（公分制）、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md)（11 步折疊為 8 步） |
| 對應模組 | MOD-WEB（`backend/server/static/`）、MOD-FP（`backend/floorplan/`）、MOD-SRV-API（`backend/server/main.py`） |
| 對應測試 | TC-009、TC-010、TC-011、TC-014、TC-021；實檔 `tests/test_scene_calibration.py`、`tests/test_scene_v2_contract.py` |
| 對應維運 | RB-006 → [runbook-recognition](../06_ops/runbook-recognition-failed-or-review-blocked.md) |
| 相鄰規格 | [ui-spec-step2](ui_spec-step2-upload.md)（analyze 觸發點與錯誤呈現處）、[ui-spec-step4](ui_spec-step4-space-confirmation.md)（房間與結構確認） |

**本文件標為待確認的項目**：(1) `geometry_engine` 無 UI 呈現元素；(2) 下游作廢無明示警語；(3) `pointerToImagePoint` 匯出未被 live 前端使用、是否下架；(4) ACPT-011 低信心比例的前端呈現要求是否維持；(5) `site.css` 斷點與對比度未核對。以上一律不得在下游文件寫成既成事實。
