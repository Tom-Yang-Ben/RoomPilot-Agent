# 第 5～7 步改採 bella-test1：整合執行規格

**文件性質**：交付給執行整合的 AI 的作業規格。所有數字為實測，非估算。
**日期**：2026-08-05
**下達者**：Ben

---

## 1. 規則

> **第 1～4 步保留 `ben-local`。第 5～7 步一律採 `origin/bella-test1`。前端設計風格（CSS 視覺）維持 `ben-local`。**

這條規則優先於本文件其他一切判斷。凡歸屬第 5～7 步者，即使 `ben-local` 那側看似
較新、較完整、或有專屬測試，一律替換，不做個案討論。執行者不得因為「對方版本看
起來較舊」而保留我方實作。

規則的三個邊界，已逐項裁定於 §4，執行時直接照表操作，不要再回頭詢問。

---

## 2. 兩邊現況

分岔點：`08517cba`（「補充 RAG 向量可索引資料範圍」）。之後雙方各自大改同一批檔案。

| | `ben-local`（目標） | `origin/bella-test1`（來源） |
|---|---|---|
| 八步 UI 位置 | `frontend/` | `backend/server/static/` |
| `scene_v2.js` | 13,153 行 | 17,414 行（base 12,343） |
| `scene_viewer.js` | 5,793 行 | 5,763 行（base 5,235） |
| `scene.html` | 1,231 行 | 1,107 行（base 942） |
| `site.css` 自 base 起變動 | 23,152 行 | 10,979 行 |
| 帳號／授權 | `auth/`、`auth_client.js`、login、projects | **無** |
| 後端結構 | 已模組化為 18 個檔案 | 集中在 `main.py` |

**檔名對照**：來源端 `backend/server/static/X` 對應目標端 `frontend/X`。這是同一份
檔案被搬過目錄，不是兩份不同檔案。

`scene_v2.js` 函式盤點：兩邊共同 331 個、`ben-local` 獨有 66 個、`bella-test1`
獨有 **275 個**（絕大多數屬第 5～7 步）。函式**同名且同順序**，這是本次替換可行的
基礎。

三方合併（base → ours=`ben-local`, theirs=`bella-test1`）衝突實測：

| 檔案 | 衝突段 |
|---|---|
| `scene_v2.js` | 111 |
| `scene.html` | 22 |
| `scene_viewer.js` | 20 |
| `scene_questionnaire_test2.js` | 3 |
| `scene_style_packs.js`、`scene_layout2d.js` | 各 2 |
| `scene_design_schemes.js`、`scene_room_requirements.js` | 各 1 |
| **合計** | **162** |

零衝突可直接取用：`scene_calibration.js`、`scene_architecture.js`、
`scene_requirements.js`、`scene_material_pair_preview.js`。

---

## 3. 步別對照

UI 八步與內部 11 個 workflow step 不是一對一：

| UI 步 | 內部 slug | 面板 `data-panel` | 歸屬 |
|---|---|---|---|
| 1 建立專案 | `project` | `project` | 保留我方 |
| 2 上傳平面圖 | `upload` | `upload` | 保留我方 |
| 3 確定尺寸 | `recognition`、`calibration` | `scale` | 保留我方 |
| 4 空間與結構 | `space_confirmation` | `space` | 保留我方 |
| **5 需求問卷** | `requirements` | `requirements` | **採對方** |
| **6 配置與預覽** | `layout_2d`、`white_model_3d`、`realistic_3d` | 三個面板 | **採對方** |
| **7 方案鎖定與視角** | `proposal_review` | `proposal-review` | **採對方** |
| 8 AI 渲染與成果包 | `ai_render` | `ai-render` | 保留我方 |

---

## 4. 逐項裁定（依 §1 規則機械推導，不再討論）

### 4.1 歸第 5～7 步 → 採對方

| 項目 | 處置 |
|---|---|
| 第 5 步全部題目、題序、面板版面 | 採對方 |
| **初談問卷**（`scene_first_meeting.js` 207 行 + `tests/test_scene_first_meeting.py`） | **移除**。位於第 5 步面板內，依規則隨第 5 步一併替換。連同其模組與測試下架 |
| 第 5 步「專案進度」「想要的家具或樣式（選填）」區塊 | 移除，隨面板替換 |
| 第 6 步 2D 位置 | 採對方 `scene_layout2d.js` |
| 第 6 步牆體、門窗幾何 | 採對方 `scene_viewer.js` 路線（`openingAnchorOnWall`、`openingAnchorForWallTopology`、`openingIsManuallyLocked`），**放棄**我方 `wallSegmentsExtendedForOpenings`（`a24d5bac`） |
| 第 6 步家具帳 `state.furnitureLedger` / `configurationLedger*` | 移除，採對方的 `configurationPendingList` 等機制 |
| 第 7 步色卡風格按鈕與選項集合 | 採對方 |
| 第 5～7 步 11 個 state 欄位 | 併入（見 §6.2） |

**牆體路線替換的安全性已查證**：`scene_viewer.js`（`createSceneViewer`）只被第 6、7、8
步使用（`whiteViewer`、`realisticViewer`、`proposalViewer`、`aiRenderViewer`、
`replacementViewer`、`glbThumbnailViewer`、`roomSchemePreviewViewer`）。第 4 步走的是
`scene_structure_preview.js`（`createStructurePreview`），**該模組不含任何牆體幾何**。
因此替換 viewer 牆窗路線不會波及要保留的第 1～4 步。

### 4.2 不歸第 5～7 步 → 保留我方

| 項目 | 理由 |
|---|---|
| auth 接線（`requireSignedIn`、`authorizedObjectUrl`，我方 5 處） | 跨步橫切關注點，非第 5～7 步元件。`AGENTS.md` 列為不可違反契約。對方無此層，替換後新面板須補掛 |
| 第 8 步入口 `prepareAiRender()`（我方 `scene_v2.js:11182`） | 屬第 8 步。且對方 `scene_v2.js:1602` 呼叫此函式卻**全 branch 無定義**，照搬會 `ReferenceError` |
| `/engineering` 頁面與 `backend/server/engineering/`（`api.py`、`documents.py`、`/api/v1` router） | 獨立頁面與獨立 API 子系統，不屬第 5～7 步。對方的 `downloadEngineeringDelivery()`（前端組 JSON blob 下載）與 `POST /api/cost/estimate` **不移植**；第 7 步若需交付入口，接到我方 `/engineering` |
| `site.css` 全部 | 規則明列設計風格維持我方 |
| 第 7 步色卡「格子的視覺樣貌」 | 規則明列。行為採對方、外觀採我方 |
| 第 1～4 步面板 markup（`scene.html` 43–445 行） | 規則明列 |
| 第 8 步面板 markup（`scene.html` 995–1231 行） | 規則明列 |

### 4.3 兩邊皆為死碼 → 一律不移植

| 項目 | 實測依據 |
|---|---|
| 圖片式視覺問卷整條鏈 | 對方 `ensureVisualQuestionnaireLoaded()`（7,279–7,308 行）抓完型錄立刻 `state.visualQuestions = []`；全檔對該變數**賦值僅兩處、皆為空陣列**（7,281、7,291），其餘 20 餘處全是讀取端。與我方 `bc6a45eb`（2026-08-03「拆除圖片式視覺問卷整條死鏈」）下架者為同一條鏈 |
| ↳ 連帶不移植 | `questionnaire_visuals.py`（250 行）、`GET /api/questionnaire/visual-catalog`、`GET /api/questionnaire/visual-images/{id}`、23 張共 **28.1MB** 圖片、2,372 行 `questionnaire_visual_catalog.json` |
| ↳ 唯一保留的相容面 | `state.visualCatalogVersion`（送入 payload 的 `questionnaireVersion`／`catalog_version`），`bc6a45eb` 已保留，不需再動 |
| 35 個無呼叫點的 `legacy*` 函式 | 共 37 個 `legacy*`，其中 35 個全檔僅出現定義處一次。含 `legacyPrepareAiRender` 三代、`legacyConfirmProposalRoomViews` V1/V1b/V2、`legacySubmitRoomRenders` 三代等，集中在第 7／8 步區域 |
| ↳ 例外 | `legacyEnsureProposalRoomViewPanel`、`legacyRenderPaletteResultsV1` 各有一個呼叫點，移植後確認是否為現行路徑，非現行則一併下架 |

### 4.4 後端

**一個端點都不用補。** 對方第 5～7 步用到而我方沒有的兩個端點
（`/api/cost/estimate`、`/api/questionnaire/visual-catalog`）已分別依 §4.2、§4.3 排除。
其餘 `/api/catalog/status`、`/api/rag/search/jobs`、`/api/rag/search/jobs/{id}` 我方皆已具備。

`backend/server/intake_service.py`（對方有、我方無，171 行）：移植第 5～7 步時若出現
未定義引用才納入；預設不移植。

---

## 5. 精確替換座標

### 5.1 `scene.html`

| 區段 | 來源 |
|---|---|
| 1–42（`<head>`、頂部骨架、進度條） | 我方保留，但進度條按鈕文案需與新面板一致 |
| 43–445（`project`／`upload`／`scale`／`space` 四個面板） | **我方保留** |
| **446–994**（`requirements`／`layout-2d`／`white-model-3d`／`realistic-3d`／`proposal-review` 五個面板） | **換成對方 365–866** |
| 995–1231（`ai-render` 面板與其後） | **我方保留** |

對方面板起點：`project` 41、`upload` 73、`scale` 109、`space` 142、
**`requirements` 365、`layout-2d` 561、`white-model-3d` 616、`realistic-3d` 719、
`proposal-review` 822**、`ai-render` 867、EOF 1107。

替換後須逐一檢查：新 markup 引用的 `id` 是否與保留下來的第 1～4 步、第 8 步程式碼
衝突（我方 `scene.html` 歷史上出現過 7 組重複 `id`）。

### 5.2 `scene_v2.js`

第 5～7 步概略區間：我方 **5,876–11,181**（5,305 行，佔全檔 40%）；
對方 **7,198–15,619**（8,421 行，佔全檔 48%）。

錨點函式行號對照（用於定位，非精確切點）：

| 函式 | 我方 | 對方 |
|---|---|---|
| `prepareQuestionnaireStep` | 5,876 | 7,198 |
| `renderVisualQuestionnaire` | 6,045 | 7,500 |
| `renderQuestionnaireSummary` | 6,060 | 8,323 |
| `confirmRequirements` | 6,388 | 8,705 |
| `renderLayoutFurniture` | 7,174 | 10,436 |
| `renderConfigurationPlan` | 7,509 | 10,770 |
| `renderSelectedFurnitureEditor` | 7,969 | 11,094 |
| `prepareProposalReview` | 10,535 | 15,378 |
| `submitRoomRenders` | 11,325 | 15,480 |
| `renderProposalRoomViewPanel` | 10,747 | 15,540 |
| `confirmProposalRoomViews` | 10,843 | 15,565 |
| `prepareAiRender`（第 8 步，保留我方） | 11,182 | **未定義** |
| `bindEvents` | 11,374 | 15,620 |

### 5.3 `bindEvents` —— 唯一不按步驟分段之處

我方 1,353 行、對方 1,404 行，**兩邊亂序方式完全相同**（同源）：第 6 步的
`realistic_3d` 綁定排在第 7、8 步綁定**之後**。

相對於各自 `bindEvents` 起點的分界（實測）：

| 區段 | 我方（起點 11,374） | 對方（起點 15,620） |
|---|---|---|
| 步驟 1–4 | 1–325（止於 `#confirm-dimensioned-plan`） | 1–329（同一接縫） |
| **步驟 5** | 326–755 | **330–751** |
| **步驟 6 主段** | 756–1212 | **752–1239** |
| **步驟 7 + 8** | 1213–1258 | **1240–1306** |
| **步驟 6 realistic 續（亂序）** | 1259–1336 | **1307–1389** |
| 全域（`#reset-project`） | 1337–1354 | 1390–1404 |

第 7 步與第 8 步的綁定**混在同一段**，替換時須拆開：第 7 步（`#suggest-master-view`、
`#lock-master-view`、`#return-to-realistic`、`#save-room-view`、色卡相關）採對方；
第 8 步（`#request-palette-renders`、`confirmRenderPalette`、`aiRenderTabs`、
`renderRoomList`、`#submit-room-renders`、`remoteRenderJobs`）保留我方並確保接到我方
`prepareAiRender()`。

### 5.4 其餘檔案

| 檔案 | 處置 |
|---|---|
| `scene_layout2d.js`、`scene_viewer.js` | 採對方（第 6 步） |
| `scene_questionnaire_test2.js`、`scene_style_packs.js`、`scene_design_schemes.js`、`scene_room_requirements.js`、`scene_requirements.js`、`scene_material_pair_preview.js`、`scene_calibration.js`、`scene_architecture.js` | 採對方 |
| `scene_questionnaire_flow.js`、`scene_questionnaire_data.js`、`scene_furniture_offers.js`（我方獨有，共 2,740 行） | 隨第 5／6 步替換一併處置；對方為內聯實作，需決定落點後同步修正 6 個引用它們的測試檔 |
| `scene_first_meeting.js` | 下架（§4.1） |
| `site.css` | **不動**，另補 §7 的 39 個 class |
| `geometry_core.js`、`scene_camera.js`、`scene_plan_geometry.js`、`scene_recognition_review.js`、`scene_tabletop_hosts.js`、`scene_structure_preview.js` | 我方保留（服務第 1～4 步） |

### 5.5 state

對方多出、須併入的 11 個欄位：

```
confirmedStructureSnapshot   lastWhiteModelGenerationError   pendingWallDeleteId
requirementsGenerationPending  roomRagJobs                   structureLinePreviewEnd
surfaceCatalog               surfaceCatalogLoadError         surfaceCatalogProvider
visualCatalog                visualQuestionIndex
```

我方多出的 `furnitureLedger` 依 §4.1 移除。

`confirmedStructureSnapshot` 是第 4 步→第 5 步的新接縫，須確認由保留下來的第 4 步
程式碼產生，或在替換後補上生產端。

---

## 6. 執行順序

### Phase 0：拆分 `bindEvents`（前置重構，不引入對方程式碼）

在**兩側**依 §5.3 的分界，把 `bindEvents()` 對稱拆成
`bindStep1to4Events()` / `bindStep5Events()` / `bindStep6Events()` /
`bindStep7Events()` / `bindStep8Events()` / `bindGlobalEvents()`。

我方這側拆完須先跑一次全測試，確認純重構、零行為變化。拆完後第 5～7 步才有可整段
抽換的邊界。**不做此步，就只能在 1,353 行裡逐行手挑 18 個衝突。**

### Phase 1：（取消）

依 §4.3、§4.4，後端無須任何移植。

### Phase 2：state 併入

依 §5.5。

### Phase 3：第 5 步

`scene.html` 446–649 → 對方 365–560；約 50 個問卷函式；§5.4 列的問卷週邊模組；
下架初談問卷。auth 接線補回新面板。

### Phase 4：第 6 步

`scene.html` 650–913 → 對方 561–821；configuration／stepSix／catalog 函式群；
`scene_layout2d.js`、`scene_viewer.js` 整檔採對方。

### Phase 5：第 7 步

`scene.html` 914–994 → 對方 822–866；proposal／renderBrief／finalRoom 函式群；
剔除 35 個死 `legacy*`；丟棄 `downloadEngineeringDelivery`；第 8 步入口接回我方
`prepareAiRender()`，並補第 7→8 交棒契約測試（對方那側從未跑通此路徑）。

### Phase 6：設計收斂

依 §7。

### Phase 7：驗證

依 §8。

---

## 7. CSS：39 個待補 class

對方 `scene.html` 用到 224 個 class，其中 **45 個**不存在於我方 `site.css`。
扣除歸第 1～4 步、依規則不引入的 6 個（`rp-project-kicker`、
`rp-project-form-heading`、`rp-project-at-a-glance`、`rp-step-panel--upload`、
`rp-step-panel--scale`、`rp-step-panel--structure`），**實作 39 個**：

```
天花選擇器   rp-ceiling-picker-dialog  rp-ceiling-picker-options
             rp-questionnaire-ceiling-quick-choices
             rp-questionnaire-native-ceiling-control
材質型錄     rp-material-catalog-dialog  rp-material-catalog-filters
             rp-material-catalog-options rp-material-catalog-search
             rp-material-catalog-result-count
             rp-questionnaire-material-pairs  rp-filter-chip-row
逐房方案     rp-room-scheme-guide  rp-room-scheme-progress
             rp-room-scheme-preview-close
             rp-room-questionnaire-summary  rp-room-filter
第 6 步      rp-layout-workspace  rp-furniture-controls
             rp-step-six-editor-heading  rp-step-six-task-actions
             rp-interaction-mode  rp-task-control-origin
             rp-room-toolbar-editor
面板骨架     rp-step-panel--requirements  rp-step-panel--layout
             rp-step-panel--white-model  rp-step-panel--realistic
             rp-step-panel--proposal  rp-step-panel--render
其他         rp-boundary-guidance  rp-catalog-batch  rp-decision-divider
             rp-dialog-heading  rp-generation-help  rp-search-field
             rp-style-grid  rp-control-pane-intro
             rp-questionnaire-generative-equipment  is-wall
```

**全部使用 `ben-local/frontend/site.css` 既有的設計 token**（色彩、間距、圓角、字級、
陰影），不得從對方 `site.css` 複製樣式段落。`rp-style-grid` 屬第 7 步色卡格子，依
§4.2 外觀採我方既有格子樣式。

---

## 8. 驗證門檻

1. `.\.venv\Scripts\python.exe -m pytest -q` —— **基準線為 1015 passed / 3 failed /
   11 skipped**。那 3 個失敗（`test_floor04_visible_swing_arcs_produce_door_candidates`、
   `test_floor04_swing_detector_supplements_a_partial_legacy_result`、
   `test_rerunning_floorplan_analysis_invalidates_stale_structure_confirmation`）全部
   源於工作區缺少 `testdata/png/ben_swing_case_04.png`，與本整合無關。整合後除這 3 個
   外不得新增失敗。
2. `tests/` 113 個檔案中 **40 個**觸及第 5～7 步，須逐一檢視而非只看綠燈。含
   `test_scene_v2_contract.py`、`test_scene_6_8_wizard_contract.py`、
   `test_scene_workflow.py`、`test_scene_room_requirements.py`、`test_scene_first_meeting.py`
   （隨初談問卷下架）、Node 端 `tests/static/*.mjs`。
3. **前端 cache key 全部重算**。`scene_v2.js` 內嵌子模組的 `?v=sha256-` 只有部分列在
   `test_scene_v2_contract` 的 `dependency_edges`，不在清單內的改了不會紅，瀏覽器卻
   拿到舊檔。
4. 以 `testdata/png/floor01.png` 從第 1 步實走到第 8 步。**必須 headed Edge／Chrome
   加原始滑鼠事件**；Playwright `click()` 會因 rAF 太慢逾時。避開原生 `confirm`
   （`#exit-project`、`#reset-project`）。
5. `git diff --check`、`git status --short`。

---

## 9. 執行者須注意的既有陷阱

- **門的座標語意**：`start→end` 是「打開後的門片」，`start→swing_end` 才是牆洞；
  `host_wall_id` 用打開的門片算、不可信。量距離要量到牆的**延伸線**。
- **`door_openings` 只加在新產生的 `scene_json`**。舊專案存下的沒有這個鍵，走動視角
  的門洞豁免在舊專案上無效——這是資料版本問題，不是 bug。
- **公分制契約**：跨模組幾何用公分，新欄位用 `_cm`／`_m2`；舊欄位 `width`、`depth`、
  `pos_x`、`pos_y` 必須同時帶 `coordinate_unit: "cm"` 與 schema version。改動 payload
  須同時更新生產端與消費端測試。
- **家電邊界**：冰箱、洗衣機等留在問卷與 `scene_json.render_context` 供第 8 步生圖，
  **不得**進入 2D/3D 自動配置或正式家具 API。
- **第 6 步家具來源**：Kai PostgreSQL `roompilot.furniture_catalog_current` 優先，
  資料庫不可用才回退已驗證 JSON。`conftest` 預設跑 JSON，型錄詞彙相關的 bug 在預設
  測試組態下看不到。
- **靜態目錄路徑**：一律 `import backend/paths.py` 的 `STATIC_DIR`（現值 `frontend/`），
  Node 測試那側是 `tests/static/paths.mjs`。**不得**自行拼 `parents[n]`。對方程式碼
  中凡出現 `Path(__file__).resolve().parents[1] / "server" / "static"` 者必須改寫。
- **環境變數蓋過 `.env`**：終端機既有的 `ROOMPILOT_*_PROVIDER` 優先於 `.env`，驗證前
  先清掉。

---

## 10. 附錄：本報告數據的取得方式

全部以 `git` 對 `ben-local` 與 `origin/bella-test1` 實測：`git merge-file` 三方合併取
衝突數；`grep -E '^(async )?function'` 取函式盤點並以 `comm` 求差集；`grep -oE '"/api/...'`
取 API 呼叫集合並與後端路由定義比對；`class="..."` 展開後逐一在 `site.css` 查存在性取
CSS 覆蓋率。分岔點 `08517cba`。量測腳本輸出留在工作階段暫存目錄，未進版控。
