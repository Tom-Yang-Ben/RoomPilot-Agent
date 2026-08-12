# UI 規格：第 5 步 需求問卷 (UI Spec - Step 5 Requirements) - RoomPilot

> **版本：** v1.0 ｜ **更新：** 2026-08-12 ｜ **狀態：** 草稿（待 owner 核准）
> **Owner:** MOD-WEB owner（Bella）＋ 產品 owner（文案與範圍）＋ MOD-RAG owner（Django，§7）
> **語域:** L3（工程）——直接寫 DOM id、事件、欄位與失敗行為
> **實例:** 八步之一（`ui_spec-step5-requirements.md`）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12；行號對應該版

本文件回答：第 5 步畫面由哪些區塊與 DOM 節點組成、三層 stage 與逐房五 section 如何切換、每個欄位寫進 `roomRequirementModel` 的哪個路徑、完成判定與錯誤文案是什麼、RAG 不可用時畫面怎麼降級。
本文件**不含**：需求問卷收哪些題目的業務理由（見 [prd](../01_requirements/prd.md)）、`scene_json` 生成與家具擺位（見 [ui-spec-step6](ui_spec-step6-layout-2d.md)）、RAG 內部檢索與排序演算法（見 [ADR-008](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)）。
要找端點契約去 [api-spec](../04_design/api_spec.md) 與 [openapi-agent-rag](../04_design/openapi-agent-rag-v1.yaml)；要找測試對應去 [test-plan](../05_qa/test_plan.md)。

**DOM 權威來源：** 本步驟部分節點由 JS 動態注入（`#questionnaire-room-section-nav`、`#questionnaire-active-room-title`、`#questionnaire-room-save-state`（`scene_v2.js:8108`–`8113`）、`#questionnaire-room-action-bar`（`:8117`–`8129`）、`#questionnaire-room-review`（`:8131`））。`scene.html` 只有靜態骨架 `.rp-room-questionnaire-editor`（`scene.html:464`），**本文件一律以執行期 DOM 為準**。

---

## 目錄

- [1. 頁面目的 (Page Purpose)](#1-頁面目的-page-purpose)
- [2. 版面配置 (Layout)](#2-版面配置-layout)
- [3. 欄位與元件 (Fields / Components)](#3-欄位與元件-fields--components)
- [4. 使用者操作 (Actions)](#4-使用者操作-actions)
- [5. UI 狀態 (States)](#5-ui-狀態-states)
- [6. 互動規格 (Interaction Spec)](#6-互動規格-interaction-spec)
- [7. RAG 排序整合](#7-rag-排序整合)
- [8. 驗證規則 (Validation)](#8-驗證規則-validation)
- [9. 響應式與無障礙 (Responsive / A11y)](#9-響應式與無障礙-responsive--a11y)
- [10. 設計交付 (Design Handoff)](#10-設計交付-design-handoff)
- [11. 追溯](#11-追溯)

## 1. 頁面目的 (Page Purpose)

讓屋主用「全屋一次＋逐房各一次」的問卷，把用途、家具、面材、天花照明與（廚衛陽台）固定設備需求填成 `state.roomRequirementModel`，作為第 6 步選件與擺位、第 8 步生圖的唯一需求輸入。對應 User Flow 節點見 [ux-research](ux_research_and_journey.md) 第 5 步；面板在資訊架構中的位置見 [ia](information_architecture.md)。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 4 步 `#confirm-dimensioned-plan`「確認尺寸標註並進入需求問卷」（`scene.html:405`）；或還原專案時 `showStep("requirements")` |
| 出口 | 第 6 步（`layout_2d`）——`#confirm-requirements` 成功後由 `confirmRequirementsInternal()` 直接接續產生方案 A／B 與白模（`scene_v2.js:9093`–`9170`） |
| 面板 | `section#requirements-step[data-panel="requirements"]`（`scene.html:410`）；導覽列 `data-step="requirements"`（`scene.html:22`–`30`） |

## 2. 版面配置 (Layout)

```text
#requirements-step
└─ .rp-questionnaire-workspace > .rp-test2-questionnaire
   ├─ header.rp-questionnaire-heading   #randomize-requirements | #requirements-progress
   ├─ nav#questionnaire-stage-nav       [data-questionnaire-stage] = profile | rooms | summary
   ├─ #whole-house-questionnaire        [data-questionnaire-panel="profile"]
   │    #whole-house-fields | #whole-house-style-tabs | #whole-house-style-grid
   │    #whole-house-style-selection    → #confirm-basic-questionnaire
   ├─ #visual-questionnaire             [data-questionnaire-panel="rooms"]
   │  ├─ aside .rp-room-questionnaire-plan
   │  │    .rp-questionnaire-plan-stage(#questionnaire-plan-image + #questionnaire-plan-overlay)
   │  │    nav#visual-space-nav         逐房膠囊（狀態徽章）
   │  └─ .rp-room-questionnaire-editor
   │       [JS 注入] #questionnaire-room-section-nav / #questionnaire-active-room-title
   │                 #questionnaire-room-save-state / #questionnaire-room-action-bar
   │       #visual-question-card（現況空白，見 §3 註）
   │       #questionnaire-finishes：usage → generative-equipment → furniture
   │                                → material-grid → [JS 注入] #questionnaire-room-review
   │                                → #confirm-questionnaire-finishes
   ├─ #questionnaire-summary            [data-questionnaire-panel="summary"]
   │    #questionnaire-summary-content → #confirm-requirements
   └─ #requirements-error | #requirements-generation-help
```

三層 stage 與逐房五 section 是**兩層獨立的巡覽**：stage 由 `showQuestionnaireStage()` 切 `[data-questionnaire-panel]`（`scene_v2.js:7593`–`7625`）；section 由 `[data-questionnaire-room-section]` 切 `#questionnaire-finishes` 內的區塊，順序固定為 `QUESTIONNAIRE_ROOM_SECTIONS`（`scene_v2.js:8099`–`8105`）。

## 3. 欄位與元件 (Fields / Components)

### 3.1 stage `profile`（全屋）

| 欄位／元件 | 型態 | 寫入路徑 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#whole-house-fields` | 動態表單 | `state.basicAnswers` → `roomRequirementModel.globalProfile`（`scene_v2.js:9021`–`9028`） | 家庭成員、預算、生活偏好只填一次；`household`／`membersAndPets` 由 `occupantsFromBasicAnswers()` 推 `{adults, children, elderly, pets}`（`scene_questionnaire_test2.js:104`–`118`），第 6 步餐椅數量依此推 |
| `#whole-house-style-tabs` / `#whole-house-style-grid` | 風格分頁＋卡片 | `wholeHouseFinishDraft().stylePackId`（`STYLE_PACKS`，`scene_style_packs.js`） | 選定後逐房牆／地／天花／照明取該 pack 預設值，各房仍可覆寫 |

### 3.2 stage `rooms`（逐房五 section）

`QUESTIONNAIRE_ROOM_SECTIONS`＝`usage`／`furniture`／`surfaces`／`ceiling`／`review`，標籤依序「房間用途／家具配置／牆面與地板／天花與照明／檢查並確認」（`scene_v2.js:8099`–`8105`）。

| section | 主要元件 | 寫入 `roomRequirements[roomId]` |
| :--- | :--- | :--- |
| `usage` | `#questionnaire-room-usage-options`（可複選，依房型預設一項） | `usage[]` |
| `furniture` | `#questionnaire-furniture-options`、`#open-questionnaire-furniture-catalog`、`#questionnaire-furniture-preference`＋`#questionnaire-furniture-preference-tags` | `furniture.selected[]`、`furniture.preferenceText`、`furniture.preferenceTags[]` |
| `surfaces` | `#questionnaire-wall-options`／`#questionnaire-wall-color`／`#questionnaire-wall-preference`、`#questionnaire-floor-*`、`#selected-wall-surface`、`#questionnaire-material-pairs` | `surfaces.wallDefault{materialId,color}`、`surfaces.floor{materialId,color}`、`surfaces.wallPreference`／`floorPreference`、`surfaces.wallSurfaceIds[]`／`wallOverrides{}` |
| `ceiling` | `#questionnaire-ceiling-quick-choices`、`#questionnaire-ceiling-material`／`-style`／`#questionnaire-light-style`／`-color` | `surfaces.ceiling{materialId,styleId,lightingId,color}` |
| `review` | `#questionnaire-room-review`（JS 注入）、`#confirm-questionnaire-finishes` | `confirmed`、`feasibility[]` |

跨 section 的兩個附加區塊：`#questionnaire-air-conditioning`（五個選項，預設 `auto`）＋`#apply-air-conditioning-all` → `climate.airConditioning`；`#questionnaire-finish-scope`（`room`／`selected`／`same-type`／`all`）＋`#questionnaire-finish-room-targets` → `applyRoomFinishScope()` 複製 `surfaces` 與 `climate` 到目標房並把目標房 `confirmed` 歸 false（`scene_room_requirements.js:223`–`248`）。走道另有 `#circulation-style-notice`／`#enable-circulation-style-override`（預設沿用客廳風格）。

### 3.3 視覺題庫（FR-026）

`ensureVisualQuestionnaireLoaded()` 呼叫 `GET /api/questionnaire/visual-catalog`（`scene_v2.js:7627`–`7657`），回應含 `version`／`notice_zh`／`question_count`／`image_count`／`ready_image_count`／`questions[]`（`main.py:3195`–`3216`）。前端僅保留 `state.visualCatalog` 與 `state.visualCatalogVersion` 供 RAG 與版本比對使用；**`state.visualQuestions` 在現行程式中恆為 `[]`**（`scene_v2.js:7629`, `:7639`，全檔無其他賦值），因此 `#visual-question-card`、`#visual-question-progress`、`#visual-question-back/next` 這組逐題 UI 不會渲染任何內容（`scene.html:462`–`468` 已標 `hidden aria-hidden="true"` 保留為相容 DOM），第 5 步只問家具與材質（原始碼註解自陳，`scene_v2.js:7635`–`7637`）。`GET /api/questionnaire/visual-images/{image_id}` 存在且缺圖回 404 `questionnaire_image_not_found`（`main.py:3218`–`3226`），但**現行 `backend/server/static/` 無任何呼叫點**（見 §5 與 §11 待確認）。

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 切換 stage | `nav#questionnaire-stage-nav [data-questionnaire-stage]` | `showQuestionnaireStage()`；未解鎖的 stage 一律退回 `profile`（`scene_v2.js:7593`–`7597`） | 無角色控制（Pilot 全 app 無認證，NFR-019） |
| 確認全屋 | `#confirm-basic-questionnaire` | 寫 `globalProfile`／`globalConfirmed=true`、套全屋面材、`invalidateDownstreamFrom("requirements", …)`、跳 `rooms`（`scene_v2.js:9021`–`9035`） | 同上 |
| 選房 | `#visual-space-nav [data-visual-room]` 或 `#questionnaire-plan-overlay` 房間多邊形／牆線（`[data-questionnaire-wall]`） | 切 `activeRoomId`；點牆設定 `state.selectedQuestionnaireWallId`，確認時併入 `surfaces.wallSurfaceIds` | 同上 |
| 切 section | `#questionnaire-room-section-nav`、`#questionnaire-room-section-back`／`-next` | `moveQuestionnaireRoomSection(±1)`（`scene_v2.js:8117`–`8129`） | 同上 |
| 加家具 | `#open-questionnaire-furniture-catalog`（`[data-open-questionnaire-furniture-catalog]`） | 開 `#furniture-catalog-drawer`（`scene.html:1119`），資料來自 `GET /api/furniture` | 同上 |
| 選面材／天花 | `[data-open-material-catalog]` → `#questionnaire-material-catalog-dialog`（`scene.html:1159`）；天花 → `#questionnaire-ceiling-picker-dialog`（`scene.html:1187`） | 寫入對應 draft 欄位 | 同上 |
| 確認本房 | `#confirm-questionnaire-finishes` | 通過 `finishesGate` 後寫 `requirement.surfaces/climate/feasibility`、`confirmed=true`，並在 `rooms` stage 觸發 `startQuestionnaireRag(room)`（`scene_v2.js:8532`–`8605`） | 同上 |
| 完成需求 | `#confirm-requirements` | `settleQuestionnaireRagForLayout()` → `buildRoomRequirementsPayload()` → 型錄就緒檢查 → 產生方案 A／B → `workflow.complete("requirements", …)` → 白模生成（`scene_v2.js:9066`–`9170`） | 同上 |
| 一鍵填測試問卷 | `#randomize-requirements`／`#randomize-requirements-summary` | `randomizeRequirementsForTesting()` 帶入每房測試用途、材質與家具（`scene_v2.js:7448`）——**測試輔助，非正式交付流程**；是否於 Pilot 對外保留待 owner 決定 | 同上 |

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案（原文） |
| :--- | :--- | :--- |
| Loading（建立配置） | 全畫面遮罩 `#placement-busy` ＋ `#confirm-requirements` `aria-busy="true"`＋`disabled` | 「AI 正在為每間房挑選並擺放家具，請稍候…」；階段訊息「正在依每個房間的需求搜尋可配置家具…」「正在檢查空間規則並建立方案 A、B…」 |
| Empty（未選家具） | `#visual-space-nav` 膠囊副標 | 「需求填寫中・N 件家具」 |
| Error（問卷層） | `#requirements-error`（`aria-live="polite"`） | 例：「請完成本房材質：wall_material、floor_color」 |
| Error（型錄不可用） | `#requirements-generation-help` 展開，附 `#retry-configuration-catalog-check`、`#return-to-room-requirements` | 「目前無法連線 Kai 家具型錄，尚未取得所選家具的可用 GLB，因此不能建立可靠的 2D+3D 配置。」＋「系統回報：<reason>。」 |
| RAG 進行中 | `#visual-space-nav` 該房 `class` 含 `is-rag-pending`（`scene_v2.js:7798`–`7801`） | 「<房名> 的家具偏好已送交 RAG 排序，您可繼續填下一個空間。」 |
| RAG 降級 | 房狀態退回 `is-confirmed`，`state.roomRagJobs[roomId].status="unavailable"` | 「<房名> 目前保留原本的推薦順序；RAG 排序暫時無法完成，但不影響繼續填寫。」／「<房名> 目前使用基本推薦；RAG 服務尚未就緒，不影響繼續填寫。」 |
| 題庫版本更新 | 呼叫 `invalidateDownstreamFrom("requirements", …)`，stage 強制回 `rooms` | 「推薦題庫已更新，請重新確認家具與材質。」（`scene_v2.js:7643`–`7652`） |
| Permission Denied | 不適用（Pilot 全 app 無認證與角色，NFR-019；服務邊界待 DEC-014 核准） | — |
| Success | `#visual-space-nav` 副標「本房需求已確認」；stage 徽章 `is-complete`；`#requirements-progress` 顯示「逐房需求 N / M」 | — |

**題庫缺圖 404**：後端行為已定（`main.py:3218`–`3226`），但現行前端無呼叫點，**畫面文案尚未存在**——列為 TO-BE，不得在其他文件寫成已實作。

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover／選取 | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `[data-questionnaire-stage]` | `.is-active`／已過 stage `.is-complete` | `rooms` 需 `basicConfirmed`；`summary` 需 `roomQuestionnaireProgress().ready && basicConfirmed`（`scene_v2.js:7587`–`7591`），HTML 初始即 `disabled`（`scene.html:427`–`428`） | — | 點擊未解鎖 stage 靜默退回 `profile` |
| `#visual-space-nav button` | `aria-current="true"`＋`.is-active`；狀態 class `is-draft`／`is-ready`／`is-rag-pending`／`is-confirmed` | — | `is-rag-pending` 期間仍可切房 | — |
| `#confirm-questionnaire-finishes` | — | 不 disable | — | 未過 `finishesGate` 時寫 `#requirements-error` 並 `setStatus(..., "error")`，不寫入 `confirmed` |
| `#confirm-requirements` | — | 送出中 `disabled`＋`aria-busy`，`state.requirementsGenerationPending` 防重複點擊（`scene_v2.js:9066`–`9090`） | 遮罩＋分階段 `setStatus` | 例外一律寫 `#requirements-error` ＋ `#requirements-generation-help`，並在 `finally` 解除 busy |
| `#questionnaire-generation-notes` | — | — | — | 命中 `擴建|延伸|移牆|拆牆|加房間|隔間|改門|改窗|打掉牆` 時 `#questionnaire-generation-warning` 改寫為結構警語（`scene_v2.js:11116`–`11118`, `:11141`–`11143`） |
| `#questionnaire-plan-overlay` | 選中牆線 `stroke="#bd5c36"`，未選為 `transparent`、`stroke-width="16"` 命中區 | — | — | — |

疊層對位：`#questionnaire-plan-image` 與 `#questionnaire-plan-overlay` 由 `syncAllOverlays()` 依 `<img>` content rect 設 `viewBox`（`scene_v2.js:1962`–`1980`），與第 3／4／6 步同一套機制。座標一律公分（ADR-007）。

## 7. RAG 排序整合

| 項目 | 行為 | 證據 |
| :--- | :--- | :--- |
| 觸發時機 | 每房 `#confirm-questionnaire-finishes` 成功且 stage 為 `rooms` 時各發一次；`#confirm-requirements` 時對所有已確認房再跑一輪 | `scene_v2.js:8605`、`:920`–`935` |
| 請求 | `POST /api/rag/search/jobs`，body `{query, top_k: 6, fast: true}`；`query` 由房名、用途、已選家具、偏好文字、設備方向與生圖補充串成（`questionnaireRagQuery`） | `scene_v2.js:867`–`875`、`:818`–`854` |
| 輪詢 | 首次 500 ms、其後每 900 ms `GET /api/rag/search/jobs/{job_id}` | `scene_v2.js:908`, `:876` |
| 只重排不增刪 | `completed` 時把命中 `item_id` 集合排到 `state.roomFurnitureRecommendations[roomId]` 前面，候選集合本身不變（ACPT-042） | `scene_v2.js:881`–`891` |
| 失敗降級 | `failed` 或任何例外 → `status:"unavailable"`＋中文提示，問卷可繼續、可完成（SCN-015） | `scene_v2.js:894`–`915` |
| 整批逾時 | `#confirm-requirements` 以 `Promise.race` 等 12,000 ms，逾時只提示「RAG 尚在整理部分家具；本次先保留可用的推薦，完成後會同步更新。」不阻擋後續 | `scene_v2.js:920`–`935` |
| 樓梯間短路 | `room.type === "stair"` 且 `furniture.selected` 為空時**不送請求**，直接記 `{status:"no_furniture_rag_required", reason:"stair_has_no_movable_furniture"}` | `scene_v2.js:857`–`866` |
| 伺服器端失敗面 | 佇列滿 429 `rag_job_capacity_reached`（上限 24）、未就緒 503 `rag_dependency_unavailable`、job 逾 3600 秒 404；三者對前端都是「降級不阻塞」 | `rag_api.py:28`–`32`, `:186`–`191`；處置見 [runbook-rag-model](../06_ops/runbook-rag-model-cache-missing.md) |

RAG 只做檢索與排序，不新增候選、不決定幾何、不取代選件政策（ADR-008）。

## 8. 驗證規則 (Validation)

| 對象 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| 本房面材（`finishesGate`） | `stylePackId`／`wallMaterial`／`wallColor`／`floorMaterial`／`floorColor`／`ceilingMaterial`／`ceilingStyle`／`lightStyle` 八項皆需有值 | 「請完成本房材質：<missing 以、串接>」 | 按 `#confirm-questionnaire-finishes`（`scene_questionnaire_test2.js:189`–`203`；`scene_v2.js:8538`–`8546`） |
| 廚／衛／陽台設備（`generativeEquipmentGate`） | 需 `primaryUse` ＋至少一項 `equipmentDirection`；同一 id 不可同時在 `equipmentDirection` 與 `mustNotHave` | 「請選擇主要使用方式與至少一項設備方向，才能讓生圖遵守此房尺寸與動線。」／「同一設備同時被選擇與排除，請保留其中一種需求或改選依尺寸推薦。」 | 區塊互動與確認本房（`scene_v2.js:11189`–`11200`） |
| section 進度（`roomQuestionnaireSectionProgress`） | `usage.length>0`；`furniture`＝該房無必備家具或已選 ≥1；`surfaces`＝牆＋地 `materialId` 皆有；`ceiling`＝`styleId`＋`lightingId` 皆有 | 未完成的房在 `#visual-space-nav` 顯示「需求填寫中」 | 每次 render（`scene_v2.js:8070`–`8089`） |
| 逐房完成（`roomRequirementComplete`） | `confirmed===true` ＋ `climate.airConditioning` ＋ `surfaces.wallDefault.materialId` ＋ `surfaces.floor.materialId` ＋ `ceiling.materialId/styleId/lightingId` 皆為真 | 未作答的房不得被當成已完成（ACPT-025） | `buildRoomRequirementsPayload()`（`scene_room_requirements.js:352`–`381`） |
| 全屋就緒 | `readyForRag = allRoomsConfirmed && globalConfirmed` | 「請先完成所有房間需求與材質，再確認全屋資料。」 | 按 `#confirm-requirements`（`scene_v2.js:9106`–`9110`） |
| 型錄就緒 | `GET /api/catalog/status` 的 `catalog_provider.ready/available` 任一為 false 即中止 | 見 §5 型錄不可用文案 | `#confirm-requirements` 前置（`scene_v2.js:9050`–`9064`） |
| 前進閘門 | `validCompletion("requirements")` 要求 `basicConfirmed===true && roomsResolved===true`；`REQUIRED_COMPLETIONS.requirements` 要求前四步全部完成 | 未滿足即無法 `goTo("layout_2d")` | `scene_workflow.js:43`–`55`, `:136`–`138` |
| 條件式選項可行性 | 浴室檢 `bathtub`／`double_vanity`、廚房檢 `large_dining_table`：扣掉門扇迴轉面積後的有效面積、短邊、門寬與門位內深皆需達標 | 「目前尺寸可能無法配置；可保留為特殊需求，家具引擎不會強制擺入。」顯示於 `#room-feasibility-notices` | 確認本房時（`scene_room_requirements.js:250`–`350`） |

**問卷是需求宣告，不是幾何裁決**：`#questionnaire-furniture-status` 明示「第 5 步不會阻擋；第 6 步會驗證實際 GLB 與位置」。家具是否放得下由 `backend/engine/` 判定（ADR-002），第 5 步的可行性提示只是預警。

### 8.1 家電只影響效果圖（DEC-006／ACPT-026）

- 第 5 步的設備需求收在 `#questionnaire-generative-equipment`（僅 `kitchen`／`bathroom`／`balcony` 顯示，`GENERATIVE_EQUIPMENT_OPTIONS`，`scene_v2.js:11094`–`11112`），欄位為 `#questionnaire-generative-primary-use`、`#questionnaire-generative-directions`、`#questionnaire-generative-exclusions`、`#questionnaire-generation-notes`，寫入 `generativeEquipment{primaryUse, equipmentDirection[], mustNotHave[], priority, fitStatus, generationNotes, structuralIntentAcknowledged}`。
- **明示文案（已存在於畫面）**：「這些設備會依房間尺寸與固定結構送入 RAG 和生圖；第 6 步不會放入大型設備模型。」（`scene.html:504`）與「此說明會一起送入 RAG 與最終生圖；系統不會擴建空間或移動固定結構。」（`scene_v2.js:11143`）。
- 型錄中的家電型品項（`RETIRED_APPLIANCE_TYPES`：`refrigerator`／`washer`／`washing-machine`／`dishwasher`／`dryer`／`oven`／`microwave`／`range-hood`／`air-conditioner`／`ceiling-cassette`／`appliance`，`scene_v2.js:674`–`685`）在第 6 步送出前被抽出成 `render_context.appliance_requirements`（`applianceRequirementsForRendering()`，`scene_v2.js:762`–`775`；送出於 `:12710`、`:12765`；後端落點 `scene_service.py:2916`, `:3059`），同時以 `removeRetiredAppliancesFromFurniture()` 移出可擺放清單（`scene_v2.js:12635`）。還原舊專案時會清除並提示「已移除 N 件舊版家電項目；冰箱與洗衣機已改由一般家具與櫃體流程處理。」（`scene_v2.js:804`）。
- 結論：家電不進 `scene_objects`、不進 2D/3D 擺設，只進 `render_context` 供第 8 步生圖（ADR-006）。

## 9. 響應式與無障礙 (Responsive / A11y)

- **斷點行為：** 版面由 `site.css` 的 `.rp-room-questionnaire-layout` 控制（平面圖側欄＋編輯區雙欄）；本 repo 無獨立斷點規格文件，實際斷點值**待確認**（見 §11）。
- **鍵盤操作：** 所有 stage／section／房間膠囊皆為原生 `<button>`，Tab 可達、Enter/Space 觸發；材質與天花選擇使用原生 `<dialog>`（Esc 關閉為瀏覽器預設行為）。
- **ARIA 現況：** `nav#questionnaire-stage-nav[aria-label="需求問卷進度"]`、`#visual-space-nav[aria-label="逐房需求空間"]`、`#questionnaire-plan-overlay[aria-label="點選房間或牆面"]`；房間膠囊以 `aria-current` 標示當前房；`aria-live="polite"` 用於 `#whole-house-style-selection`、`#visual-question-card`、`#questionnaire-furniture-status`、`#questionnaire-generation-warning`、`#questionnaire-ceiling-quick-choices`、`#room-feasibility-notices`、`#requirements-error`、`#requirements-generation-help`。
- **未驗證項：** 對比度、focus ring、`is-rag-pending` 等狀態徽章是否有非色彩替代標示，repo 內無無障礙稽核紀錄；WCAG 等級未定，屬 TO-BE。

## 10. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | 無（repo 內查無 Figma 連結或設計稿）——**待確認** |
| Design Tokens | 無獨立 token 檔；樣式集中於 `backend/server/static/site.css`（單檔） |
| 元件對照 | 無元件庫；DOM id 與 `[data-*]` 選擇器即介面契約，斷言於 `tests/test_scene_v2_contract.py` |
| 快取鍵 | `scene.html` 對 `scene_v2.js`／`site.css` 的 `?v=sha256-<前 12 碼>` 必須等於實檔雜湊，由 `tests/test_scene_v2_contract.py:20`–`28` 強制 |
| 已知限制 | 逐題視覺問卷 UI 保留但不渲染（§3.3）；`#randomize-requirements` 為測試輔助按鈕仍對使用者可見 |

## 11. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-005（問卷收需求）、DEC-006（家電只影響效果圖）、DEC-016（AI 檢索只排序）——狀態皆為**待 owner 核准** |
| 對應功能需求 | FR-026（視覺題庫端點）、FR-027（逐房需求模型）、FR-028（家電只進 `render_context`）、FR-049（第 5 步 `fast:true` 呼叫 RAG 且失敗降級）；相關 FR-046、FR-048 |
| 對應非功能需求 | NFR-009（RAG 佇列 24／保留 3600 秒）、NFR-010（模型 offline-only）、NFR-017（公分制）、NFR-019（無認證，Pilot 現況） |
| 對應驗收條件 | ACPT-024、ACPT-025、ACPT-026、ACPT-042（另涉 ACPT-041、ACPT-043） |
| 對應情境 | SCN-014、SCN-015、SCN-016 |
| 對應架構決策 | [ADR-006](../03_architecture/adr/ADR-006-appliances-render-context-only.md)、[ADR-008](../03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md)、[ADR-007](../03_architecture/adr/ADR-007-centimeter-unit-contract.md)、[ADR-010](../03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md) |
| 對應模組 | MOD-WEB（`backend/server/static/`）、MOD-SRV-SCENE、MOD-RAG |
| 對應測試 | TC-024（題庫篩選與缺圖 404）、TC-025（逐房 schema 與完成判定）、TC-026（家電只進 `render_context`）、TC-042（RAG 只重排、不可用不阻塞） |
| 對應 Runbook | RB-004（[runbook-rag-model](../06_ops/runbook-rag-model-cache-missing.md)） |
| 相鄰步驟 | [ui-spec-step4](ui_spec-step4-space-confirmation.md) → 本步 → [ui-spec-step6](ui_spec-step6-layout-2d.md) |
| 需求規格 | [srs](../01_requirements/srs.md)；端點契約 [api-spec](../04_design/api_spec.md)、[openapi-scene](../04_design/openapi-scene-v1.yaml)、[openapi-agent-rag](../04_design/openapi-agent-rag-v1.yaml) |

### 待確認事項

1. **`room_requirements` schema 版本雙份不一致**：前端 `ROOM_REQUIREMENTS_SCHEMA_VERSION = 2`、欄位名 `schemaVersion`（`scene_room_requirements.js:1`, `:372`），而 `docs/contracts/FURNITURE_ENGINE_ROOM_REQUIREMENTS_CONTRACT.md:57` 寫「`schema_version` 固定為 `1.0`」。以原始碼為準時 ACPT-025 的「`schema_version:"1.0"`」需修正；由誰擁有此欄位待 owner 裁定。
2. **`room_requirements` 目前無伺服器端消費者**：`backend/server/scene_service.py` 全檔查無 `room_requirements`，前端只把它塞進 `/api/scene/generate` 與 `/api/agent/furniture/select` 的 payload。契約文件描述的引擎消費路徑是 TO-BE 還是既有落差，需 MOD-ENG／MOD-AGT owner 確認。
3. **逐題視覺問卷是否正式退役**：`state.visualQuestions` 恆為 `[]`，`/api/questionnaire/visual-images/{id}` 無前端呼叫點。題庫是保留給 RAG 的資料資產，還是待恢復的 UI？若退役，FR-026 的驗收面（ACPT-024 的缺圖 404）只能以 API 層測試涵蓋。
4. **`#randomize-requirements`（一鍵填寫測試問卷）是否對外保留**：屬產品範圍決策，待 owner 拍板。
5. **`appliance_requirements` 實際可否非空**：家電型品項需先在第 5 步被使用者從型錄加入，且在 `pruneRetiredAppliances()` 清掉之前完成第 6 步送出；此路徑是否仍可達成，需以端到端測試驗證（TC-026 目前缺 `scene_objects` 反向斷言）。
6. **響應式斷點與無障礙標準**：repo 內無斷點規格、無 a11y 稽核紀錄、無 Figma 來源。
