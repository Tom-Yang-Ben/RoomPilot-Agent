# bella-new 第 5–8 步前端排版與功能對照（vs 本分支）

- **產出日期**：2026-08-08
- **bella-new**：`origin/bella-new` @ `09ef2855`。本文 bella 行號以本地快照 `e97adfce` 為基準（兩者差 9 個修正 commit，總量約 +855 行；該增量完整列於[第 8 節](#8-遠端增量e97adfce--09ef2855)，行號位移對段落定位影響極小）
- **本分支**：`yen` ＝ `feat/scene3d-modeling-swap` @ `f367e837`（兩分支同一 tip）
- **範圍**：`backend/server/static/`（scene.html、scene_v2.js、scene_viewer.js 與輔助模組）；後端僅列前端實際呼叫的 endpoint
- **步驟對應**（兩邊相同）：導覽第 5 步＝`requirements-step`；第 6 步（配置與預覽）涵蓋 **6A** `layout-2d-step`、**6B** `white-model-3d-step`、**6C** `realistic-3d-step` 三個子面板；第 7 步＝`proposal-review-step`；第 8 步＝`ai-render-step`
- **外殼幾何前提**：`f367e837` 已把本分支 3D 房殼幾何改回 bella-new 內聯管線——兩邊 `scene_viewer.js` 開頭 import 完全相同，皆未載入 `scene_shell_geometry.js` / `scene_builders.js`，此前的管線分歧已消除，本文不再比較外殼幾何本身

## 0. 總覽

| 步驟 | 排版對齊度 | 功能主要差異 |
| :-- | :-- | :-- |
| 5 需求問卷 | 主結構相同 | 家具型錄瀏覽模型完全不同：bella＝空間/用途分類＋批次多選；本分支＝三下拉＋逐件加入 |
| 6A 2D 配置 | 逐行相同 | 無（同函式、同端點） |
| 6B 白模 3D | 骨架相同、側欄分歧 | bella 有「牆面與地面」分頁＋逐房材質草稿→鎖定→確認狀態機；本分支白模無任何材質功能，多「指定家具外觀」常駐面板 |
| 6C 擬真預覽 | 側欄分歧 | 本分支把材質/燈光做成任務對話框（＋undo＋顯式保存鈕）；bella 擬真側欄僅家具清單＋內聯燈光 |
| 7 方案鎖定與視角 | 逐字相同 | 無實質差異（bella 多一個 hidden 相容工具列） |
| 8 AI 渲染與成果包 | 骨架相同、本分支右欄多兩區 | 同名按鈕語意不同（bella「送出房間渲染」＝同步生圖＋每房修訂；本分支＝佇列提交）；本分支獨有 OpenRouter 一鍵生圖與設計提案 PDF 全鏈 |
| （遠端增量） | — | origin/bella-new 最新 9 個 commit 的功能**本分支全部沒有**（吸附貼完成面、牆厚推斷、跨房修復、草稿持久化、視角守衛、payload 硬化等），詳第 8 節 |

---

## 1. 第 5 步 需求問卷（`requirements-step`）

### 1.1 bella-new 排版

問卷分三階段（stage nav 切換）：

- **頂部 header**（scene.html:381-391）：eyebrow「5 需求問卷」＋標題＋說明；右側「一鍵填寫測試問卷」`#randomize-requirements` 與進度標籤 `#requirements-progress`。
- **階段導覽 nav**（:393-397）`#questionnaire-stage-nav`：三顆 `data-questionnaire-stage`（profile/rooms/summary），後兩顆 disabled。
- **階段 1 全屋設定 `#whole-house-questionnaire`**（:399-417）：動態全屋欄位 `#whole-house-fields`（預設 hidden）；全屋主風格編輯器 `#whole-house-style-editor`（:405-413，style tabs＋grid＋選取狀態）；動作列 `#confirm-basic-questionnaire`「確認全屋風格，開始逐房設定」。
- **階段 2 逐房需求 `#visual-questionnaire`**（:419-547）：
  - 左側 `aside.rp-room-questionnaire-plan`（:425-431）：平面圖＋SVG overlay＋空間導覽 `#visual-space-nav`。
  - 右側編輯區（:432-545）：隱藏的舊問答控件群；動態問答卡 `#visual-question-card`；完成編輯器 `#questionnaire-finishes`（:441-544）——房名標題、走道沿用客廳風格提示、隱藏冷氣快捷、本房用途區、生圖設備區（primary-use/directions/exclusions/notes/warning）、**本房家具區**（:482-499：「＋新增家具」`#open-questionnaire-furniture-catalog` **在標題內**、狀態列、偏好 textarea（**無更新推薦按鈕**）、偏好標籤、結果區）、隱藏風格/材質區塊群、套用範圍、可行性提示、`#confirm-questionnaire-finishes`。
- **階段 3 摘要 `#questionnaire-summary`**（:549-560）：摘要內容＋返回／重新一鍵填／`#confirm-requirements`「完成需求，建立配置方案」。
- **底部**：錯誤列；生圖協助區 `#requirements-generation-help`（重試型錄檢查／返回需求）。
- **家具型錄 dialog `#furniture-catalog-drawer`**（:1050-1089）：搜尋 `#glb-furniture-search`；篩選區含**範圍切換（目前房間/全部空間）`data-questionnaire-catalog-scope`**、**空間分類 `#questionnaire-catalog-space-groups`**、**用途分類 `#questionnaire-catalog-purpose-groups`**、隱藏 type select、顏色/材質 select、**批次區**（已選計數＋`#add-selected-questionnaire-furniture`「加入本房」）。
- **材質型錄 dialog**（:1091-1116，自訂關閉鈕）與**天花選擇 dialog**（:1118-1130）。

### 1.2 bella-new 功能流

- 確認全屋風格：`confirmBasicQuestionnaire()`（scene_v2.js:8820）→ 進階段 2，純前端。
- 確認本房：`confirmQuestionnaireFinishes()`（:8326），按鈕文字動態改為「確認{房}的用途、家具與材質」。
- 開家具型錄：`openQuestionnaireFurnitureCatalog()`（:13047）：重設 scope=room、渲染空間＋用途分類按鈕（:12875）與批次區（:13005）→ 搜尋。
- 型錄搜尋 `searchGlbFurniture()`（:13080）：未選空間/用途先顯示引導文（browsePrompt :12867）不打 API；否則 **`GET /api/furniture?has_model=true&detail=scene&page_size=48&[q]&[types=用途taxonomy|group=]&[type/color/material]`**；問卷模式結果**依 `normalized_type:label` 去重、slice 18**，渲染成 **checkbox 多選卡**。
- 批次加入：checkbox 維護已選集合 → `#add-selected-questionnaire-furniture` 一次加入多件（:17917）。
- 完成需求：`confirmRequirements()`（:8865）——**`requirementsGenerationPending` 重入鎖**＋aria-busy → `confirmRequirementsInternal()`（:8890）：`settleQuestionnaireRagForLayout()` → `GET /api/catalog/status` → `await switchDesignScheme("A")` → `autoLayoutFurniture()`（**`POST /api/scene/layout`**）→ B 方案 relayout → `generateWhiteModelFromRequirements()`（**`POST /api/scene/generate`**）。失敗顯示生圖協助區。

### 1.3 本分支排版與功能

排版主結構**同 bella-new**（三階段、全屋、逐房、摘要、協助區、材質/天花 dialog 皆同），差異：

- 「＋新增家具」移到家具結果下方獨立 action-row（scene.html:532）；偏好 textarea 旁**多「更新推薦」`#refresh-questionnaire-furniture`**（:524）——bella markup 無此鈕（JS 用 `?.` 監聽故靜默無效），**實際 UI 只有本分支有**。
- 家具型錄 dialog（:1092-1128）：雙搜尋輸入切換（`#standard-catalog-search` 內 `#glb-furniture-search-fallback`＋controls 內 `#glb-furniture-search`）；篩選**只有 type/color/material 三個 select**——無範圍切換、無空間/用途分類、無批次區。
- 材質 dialog 關閉鈕改原生 `form method="dialog"`（:1137）。
- 本分支獨有 markup：`#placement-busy` 擺放中遮罩（:1174-1180）。

功能流：

- `openQuestionnaireFurnitureCatalog()`（scene_v2.js:11568）直接開 dialog＋搜尋，無分類/批次渲染。
- `searchGlbFurniture()`（:11587）：`page_size=24`、僅 `group=` 收斂（無 `types=`）；結果**不去重、不 slice**，每件單顆「加入此房」即時加入（:15053），按後變「已加入本房」。
- 殘留死碼：`data-questionnaire-catalog-scope` 監聽（:15039）仍註冊但 markup 無按鈕，永不觸發。
- `confirmRequirements()`（:7960）：**無重入鎖、無 settleQuestionnaireRag**；改用 `beginPlacementBusy()/endPlacementBusy()` 驅動全屏遮罩；`switchDesignScheme("A")` 為同步呼叫。後端 endpoint 序列與 bella 相同。
- `scene_furniture_retrieval.js`：本分支**多 `outdoorPenalty()`**（:144-158,172，戶外家具在室內房型 -400），其餘與 bella 完全相同。

### 1.4 差異對照表

| 區塊/功能點 | bella-new | 本分支 | 分類 | 功能影響 |
| :-- | :-- | :-- | :-- | :-- |
| 問卷三階段主結構 | 有 scene.html:378-569 | 有 scene.html:410-604 | 相同 | 無 |
| 「＋新增家具」鈕位置 | 家具區標題內 :485 | 結果下方 action-row :532 | 已移植-實作不同 | 僅版面位置 |
| 「更新推薦」鈕 | 無（JS optional 監聽無效） | 有 :524 | 本分支獨有 | 本分支可手動重刷本房家具推薦 |
| 型錄範圍切換（目前房間/全部空間） | 有 :1067-1070 | 無 | bella 獨有 | bella 可跨房瀏覽 |
| 型錄空間分類 | 有 :1071 / sv2:12878 | 無 | bella 獨有 | 按空間類型收斂 |
| 型錄用途分類（`types=`） | 有 :1072 / sv2:12885 | 無 | bella 獨有 | 按用途 taxonomy 精準過濾 |
| 型錄批次多選 | 有 :1082-1085 / sv2:13005,17902 | 無 | bella 獨有 | 一次勾多件加入 |
| 型錄單件即時加入 | 無（走 checkbox） | 有 sv2:11631,15053 | 已移植-實作不同 | 逐件點加、標「已加入本房」 |
| 型錄 API 收斂參數 | `types=` 或 `group=` sv2:13102-13104 | 僅 `group=` sv2:11594-11596 | 已移植-實作不同 | bella 過濾更細 |
| 型錄結果去重/上限 | 去重＋slice 18 sv2:13118-13124 | 無（全列）sv2:11608 | bella 獨有 | bella 清單短且無重複型 |
| 未選分類引導文 browsePrompt | 有 sv2:12867,13094 | 無 | bella 獨有 | bella 有引導、不打空 API |
| catalog-scope 監聽 | 有效（有按鈕）sv2:17800 | 死碼（無按鈕）sv2:15039 | 已移植-實作不同 | 本分支永不觸發 |
| 材質 dialog 關閉鈕 | 自訂 button :1098 | `form method=dialog` :1137 | 已移植-實作不同 | 皆可關閉 |
| `#placement-busy` 遮罩 | 無 | 有 :1174-1180 | 本分支獨有 | 確認需求時顯示全屏擺放進度 |
| `confirmRequirements` 重入鎖＋settleRag | 有 sv2:8865-8894 | 無 sv2:7960 | 已移植-實作不同 | bella 防連點、先結算 RAG |
| `switchDesignScheme("A")` | `await` sv2:8920 | 同步 sv2:7989 | 已移植-實作不同 | bella 等待切換完成 |
| 確認需求 endpoint 序列 | catalog/status → scene/layout → scene/generate | 同 | 相同 | 無 |
| `outdoorPenalty` 家具評分 | 無 | 有 retrieval.js:144-158 | 本分支獨有 | 排除誤標室內的戶外家具 |

### 1.5 功能層面重點差異

1. **家具型錄瀏覽模型完全不同**：bella 是「空間→用途→checkbox 多選→批次加入」的分類瀏覽器（後端 `types=` 精準收斂、去重 slice 18）；本分支簡化為「三下拉＋逐件即時加入」（`group=` 粗收斂、結果全列）。
2. **「更新推薦」按鈕存在性與歷史認知相反**：markup 上 bella 沒有、本分支有——實際能手動重刷本房推薦的只有本分支。
3. **確認需求健壯性**：bella 有重入鎖＋RAG 結算＋await 切方案；本分支以 `#placement-busy` 全屏遮罩提供回饋但無重入鎖。endpoint 序列一致。
4. **戶外家具過濾為本分支獨有**（`outdoorPenalty` -400），bella 室內房可能混入誤標的戶外家具。
5. **範圍切換（全部空間）是 bella 獨有**；本分支殘留一段永不觸發的 scope 死碼。
6. **未選分類體驗**：bella 顯示引導文；本分支開型錄即直接列當房結果——上手更直接、bella 更結構化。

---

## 2. 第 6 步之 6A：2D 配置（`layout-2d-step`）

兩邊**逐行相同**（bella scene.html:574-627 / 本分支 :609-664；本分支僅多兩行註解說明 hidden 工具列保留 DOM 之由）：

- 方案工具列 `layout-scheme-bar`（hidden，恰 A/B 兩鈕，保留 DOM 給契約測試）。
- 左「平面窗格」：「依需求重新配置」`auto-layout-furniture`、逐房下拉、逐房材質摘要條、平面舞台（底圖＋房間 SVG＋家具層）、圖例（實線腳印/紅色碰撞/拖曳提示）。
- 右「控制窗格」：家具搜尋、「＋新增家具」、貼牆提示、家具清單、圖示庫、已選家具編輯框（名稱/理由/寬深/旋轉90°/更換/刪除）、錯誤列、主鈕 `confirm-layout-2d`「確認 2D 尺寸與家具」。

功能流共用同函式、同端點：進場自動排與「依需求重新配置」→ **`POST /api/scene/layout`**；拖曳/旋轉/刪除/尺寸改 → **`POST /api/scene/validate`** 合法性檢查（不合法標紅並列入待處理）；「更換家具」開替換抽屜；`confirm-layout-2d` → `confirmLayout2d` → **`POST /api/scene/generate`** 產 3D → 進白模（bella sv2:17418/17481；本分支 sv2:14746-14920）。

---

## 3. 第 6 步之 6B：白模 3D＋材質（`white-model-3d-step`）

### 3.1 bella-new 排版（scene.html:629-820）

- 方案工具列 `white-model-scheme-bar`（hidden，同 6A）。
- 左「檢視窗格」：工具列＝檢視段（自由旋轉/正俯視＋家具編號鈕 `toggle-furniture-numbers`，**預設關**＝顯示「顯示編號」）、操作段（走動/編輯家具）、走動空間下拉、「＋新增家具」`open-furniture-catalog`；`white-model-viewer`；狀態列。
- 右側欄 `rp-3d-sidebar`（`data-scene-sidebar-mode="plan"`），**頂部三分頁 tab bar**（:667-672）：**同步平面／待處理（含徽章）／牆面與地面**：
  - `configuration-plan-panel`（同步平面）：可收合、同步 2D 縮圖＋家具層＋同步清單；巢狀「待處理」區（計數＋清單）。
  - `room-scheme-gate`（hidden）：逐房確認方案 gate＋「逐房比較方案」`open-room-scheme-selection`。
  - 天花板樑編輯器（引導返回第 4 步改樑）。
  - **`white-model-surface-entry` 逐房材質面板**（`data-scene-sidebar-panel="surfaces"`，:718-808）：
    - header：eyebrow「逐房材質」＋房名＋**進度「已確認 0/N 間」`surface-room-progress`**＋**鎖定徽章「草稿」`surface-room-lock-state`**；問卷摘要；預覽狀態。
    - 牆/地 tab（`data-step-six-surface-kind`）；牆面 panel（推薦色卡＋自訂色＋隱藏材質 select＋**「瀏覽全部材質」`data-open-material-catalog="wall"`**＋材質格）；地面 panel（同構＋**進階「地面混搭」**界線方向/位置/次要地材/建立/移除）。
    - footer：**「重新修改此房間」`unlock-room-surfaces`（hidden）＋「確認此房間材質」`confirm-room-surfaces`；全部完成才顯示「確認全部材質，前往第 7 步」`save-realistic-scene`（hidden）**。
  - 隱藏區：指定家具外觀舊控件（bella **全隱藏**，改由 3D 浮動微調面板操作）。
  - 錯誤列；主鈕 `confirm-white-model`「確認家具配置並**調整材質**」。
- 相關 dialog：`room-scheme-selection-dialog`（:973-999）、**`room-scheme-3d-preview-dialog`（:1000-1013，bella 獨有）**、家具替換/型錄抽屜、材質型錄 dialog（被 `data-open-material-catalog` 開啟）、天花挑選。bella **無** `surface-adjustment-dialog`/`lighting-adjustment-dialog`。

### 3.2 bella-new 功能流：逐房材質草稿→鎖定→確認生命週期（bella 核心，本分支無）

狀態容器 `state.roomFinishDrafts[roomId]`，旗標 `stepSixSurfaceConfirmed`/`stepSixSurfaceConfirmedAt`：

1. **選材＝更新草稿＋即時預覽**：點色卡/材質格/自訂色 → `previewStepSixRoomSurfaces({userInitiated:true})` 寫入該房草稿並更新 `scene_objects.surface_overrides`，`whiteViewer.updateRoomSurfaces` 即時套用、**只影響當前房**（sv2:14092-14144）。
2. **地面混搭**：`toggleMaterialBoundary`/`removeMaterialBoundary` 建立/移除 `material_boundary` 並重置該房確認旗標（:14223,14287）。
3. **確認此房**：`confirmStepSixRoomSurfaces()`（:14173-14203）：草稿定案 → 標 `stepSixSurfaceConfirmed=true`＋時間戳，寫入 `roomRequirements[room].surfaces` → `scheduleSave("realistic_3d")` → **自動跳下一個未確認房**。
4. **鎖定後 UI**：`renderStepSixSurfaceProgress()`（:4238-4267）：徽章「草稿↔已鎖定」、面板 `is-room-locked` 並 **disable 該分頁所有控件**、隱藏確認鈕、顯示解鎖鈕、進度「已確認 n/N 間」。
5. **解鎖重改**：`unlockStepSixRoomSurfaces()`（:14205-14221）；若已進第 7 步（final lock）則拒絕。
6. **全部確認才放行**：`save-realistic-scene` 僅在 `allStepSixRoomSurfacesConfirmed()` 為真時可按；未確認房會被聚焦擋下；通過則 `workflow.complete("realistic_3d")` → `goTo("proposal_review")`（:18021-18035）。草稿隨 `realistic_3d.roomSurfaceDrafts` 持久化（`PUT /api/projects/{id}`）。

其他：sidebar 三分頁 `setSceneSidebarTab(plan|issues|surfaces)`（sv2:1078-1090）；「逐房比較方案」開選擇 dialog，A/B 逐房選定寫入 `designSchemes.room_selections`。

### 3.3 逐房方案比較（兩邊皆有，深度不同）

- **bella**：choice card 一格 2D 平面＋一格**可點的互動 3D 格**（`data-room-scheme-preview-3d`「3D 房間預覽 · 點擊旋轉查看」，sv2:4341）→ `openRoomScheme3dPreview`（:4089-4124）開 **`room-scheme-3d-preview-dialog` 全屏可拖曳旋轉/縮放預覽**（單房裁切場景；結構未確認時顯示「前往第 4 步確認結構」）。快照生成 `ensureRoomScheme3dPreviews`（:4361-4396）**借用前景 whiteViewer 臨時 loadScene 拍 PNG 再還原**。
- **本分支**：choice card 兩格皆**靜態 img**（sv2:3535-3554）；**無** 3d-preview-dialog、無互動格。快照生成（:3568-3617）改用**專屬離屏 `glbThumbnailViewer`＋序列佇列**，以 `setWalkRoom` 進房取景（失敗退回 orbit+corner），拍完 `unloadScene` 釋放 GPU——前景不受干擾、記憶體更省，但**可旋轉的即時預覽在本分支不存在**。

### 3.4 本分支排版與功能（scene.html:666-762）

- 檢視窗格**同 bella**，唯一差異：家具編號鈕**預設開**（aria-pressed=true、文案「隱藏編號」）——與 bella 相反。
- 右側欄：**無分頁 tab bar、無 `data-scene-sidebar-mode`**，單欄平鋪：同步平面＋待處理（同 bella）、`room-scheme-gate`（**不帶 hidden、常駐可見**）、天花板樑（同 bella）、**本分支獨有可見面板「指定家具外觀」`furniture-property-locks`**（:750-757：指定色/指定材質/鎖定模型/鎖定材質）。
- **白模面板完全沒有材質區塊**：`white-model-surface-entry`、牆/地 tab、色卡、`confirm/unlock-room-surfaces`、進度、鎖定徽章在本分支 scene.html 全數 0 命中；scene_v2.js 亦無 `confirmStepSixRoomSurfaces`/`unlockStepSixRoomSurfaces`/`renderStepSixSurfaceProgress`/`setSceneSidebarTab`/`previewStepSixRoomSurfaces`（全 0 命中）。材質功能整組移到 6C 擬真子面板的任務對話框（見第 4 節）。
- 主鈕文案「確認家具配置並**進入即時寫實**」→ 直接進 6C（bella 是「並調整材質」→ 留在 6B 材質分頁）。

### 3.5 差異對照表（6A＋6B）

| 區塊/功能點 | bella-new | 本分支 | 分類 | 功能影響 |
| :-- | :-- | :-- | :-- | :-- |
| 6A 2D 配置面板全部 | 有 :574-627 | 有 :609-664 | 相同 | 無 |
| 白模檢視/操作/走動/新增家具工具列 | 有 :639-665 | 有 :676-700 | 相同 | 無 |
| 家具編號預設值 | 預設關（顯示編號）:646-647 | 預設開（隱藏編號）:683-684 | 已移植-實作不同 | 進場第一眼有無編號 sprite 相反 |
| 側欄三分頁 tab | 有 :667-672 / sv2:1078 | 無 | bella 獨有 | 本分支單欄平鋪 |
| 同步平面＋待處理 | 有 :673-700 | 有 :705-732 | 相同 | 無 |
| `room-scheme-gate` | 有（hidden 條件顯示）:701-705 | 有（常駐可見）:733-737 | 已移植-實作不同 | 顯示時機不同 |
| 逐房方案選擇 dialog | 有 :973-999 | 有 :1029-1055 | 相同 | 無 |
| 方案 3D 預覽 dialog（可旋轉） | 有 :1000-1013 / sv2:4089 | 無 | bella 獨有 | 本分支選方案時只能看靜態快照 |
| 快照生成機制 | 前景 viewer 臨時載入還原 sv2:4361-4396 | 離屏佇列＋setWalkRoom＋拍完卸載 sv2:3568-3617 | 已移植-實作不同 | 本分支不干擾前景、省資源；取景為房內走位 |
| **逐房材質面板（色卡/材質格/混搭）** | 有 :718-808 | 無（移 6C dialog） | bella 獨有 | 本分支白模步不能改材質 |
| **草稿/鎖定/逐房確認狀態機** | 有 sv2:14173-14221,4238-4267 | 無（0 命中） | bella 獨有 | 無「確認 n/N、草稿/已鎖定、解鎖、final lock」機制 |
| 材質型錄入口（第 6 步） | 有 :756/:781 | 無 | bella 獨有 | 本分支第 6 步無法瀏覽材質型錄 |
| 地面混搭界線位置 | 6B 白模內 :784-797 | 6C surface-editor 內 :831-839 | 已移植-實作不同 | 操作時機延後 |
| 指定家具外觀可見面板 | 無（控件隱藏 :809-815） | 有 :750-757 | 本分支獨有 | 本分支側欄直接鎖指定色/材質 |
| `confirm-white-model` 文案與去向 | 「並調整材質」→ 6B 材質分頁 | 「並進入即時寫實」→ 6C | 已移植-實作不同 | 白模確認後動線不同 |

---

## 4. 第 6 步之 6C：擬真預覽（`realistic-3d-step`）

### 4.1 bella-new 排版與功能（scene.html:822-863）

- 隱藏 A/B 工具列 `realistic-scheme-bar`（:823）。
- 左檢視窗格：視角 orbit/topdown/walk（`data-real-view-mode`）＋`lock-real-view-for-edit`＋`render-performance`；`realistic-viewer`；狀態列。
- 右側欄（eyebrow「第 6 步｜配置與材質微調」）：**只有**「寫實家具」清單 `realistic-scene-object-list`＋刪除鈕 `delete-realistic-furniture`，以及**內聯** `lighting-editor`（hidden，:853-860：**房間選擇器 `lighting-room-selector`**、問卷摘要、天花/燈風格、**燈具下拉 `lighting-fixture-select`**、衝突提示）。
- **無**材質編輯（牆/地色、材質下拉、混搭界線、apply、undo 皆無 markup）——bella 的材質微調在 6B 分頁完成。
- 推進鈕 `save-realistic-scene` 為 **hidden**（位於 6B 材質 footer :805，「確認全部材質，前往第 7 步」），由 6B 全房確認流程觸發。

功能：切視角／鎖定視角編輯家具／刪除家具（改 scene_json 隨 `scheduleSave` 持久化）／燈光內聯編輯（寫 `render_context`）。

### 4.2 本分支排版與功能（scene.html:764-854）

- 檢視窗格與家具清單/刪除鈕**同 bella**（status 文案改提 PBR）。
- 側欄（eyebrow「第 6 步｜材質與燈光微調」）在家具清單之後為**本分支獨有**結構：
  - **任務啟動器**「材質與燈光」（:794-799）：`open-surface-adjustment`「調整牆面、地板與色卡」＋`open-lighting-adjustment`「調整天花與燈具」。
  - 三個 hidden origin 容器：`style-pack-dialog-origin`（StylePack tabs/grid）、`surface-editor-origin`（:805-841：套用範圍 房/全屋、牆/地色、牆/地材質（含 grouped 網格）、`apply-surface-colors`、**材質混搭界線**）、`lighting-editor-origin`（:842-849：僅天花/燈風格/衝突——**無** bella 的房間選擇器與燈具下拉）。
  - `undo-style-change`「復原上一次 StylePack」（:850）。
  - **顯示的** primary 鈕 `save-realistic-scene`「保存即時寫實方案」（:851）。
- **任務對話框機制**（本分支獨有）：`openStepSixTaskDialog(kind)`（sv2:3488-3506）把側欄編輯器 **DOM 節點搬進** `surface-adjustment-dialog`/`lighting-adjustment-dialog`（scene.html:1003-1027）；關閉時 `restoreStepSixTaskControls`（:3474-3486）搬回並 `renderStyleControls`＋`scheduleSave`。
- `save-realistic-scene` handler 兩邊語意一致（`workflow.complete("realistic_3d")` → `goTo("proposal_review")`），但 bella 是隱藏自動推進、本分支需使用者主動點擊。

### 4.3 差異對照表（6C）

| 區塊/功能點 | bella-new | 本分支 | 分類 | 功能影響 |
| :-- | :-- | :-- | :-- | :-- |
| 檢視窗格（視角列/viewer/status/鎖定編輯/性能標籤） | 有 :830-843 | 有 :772-785 | 相同 | 無（status 文案異） |
| 寫實家具清單＋刪除鈕 | 有 :848-852 | 有 :789-793 | 相同 | 無 |
| 材質編輯（牆/地色、材質、混搭、apply、undo） | 無 | 有 :804-850 / sv2:3474-3513 | 本分支獨有 | 本分支可在 6C 逐項改材質；bella 在 6B 分頁改 |
| 材質/燈光任務啟動器＋dialog | 無 | 有 :794-799,1003-1027 / sv2:3488 | 本分支獨有 | 彈窗集中調整（DOM 搬移進出） |
| lighting-editor 位置與內容 | 內聯側欄，含房間選擇器＋燈具下拉 :853-860 | origin 容器→dialog，僅天花/燈/衝突 :842-849 | 已移植-實作不同 | bella 可選房間與燈具；本分支簡化 |
| `save-realistic-scene` | hidden 自動推進（於 6B footer :805） | 顯示 primary「保存即時寫實方案」:851 / sv2:15216 | 已移植-實作不同 | 本分支需手動保存推進 |
| `undo-style-change` | 無 | 有 :850 | 本分支獨有 | 一鍵復原上次 StylePack |

---

## 5. 第 7 步 方案鎖定與視角（`proposal-review-step`）

兩邊**逐 element 相同**（bella :865-908 / 本分支 :856-895）：視角 orbit/walk 工具列、`locked-scheme-label`、`proposal-review-viewer`（`data-render-quality="realistic"`）、審閱摘要、「選擇同風格色卡」grid、內容確認 checkbox、`return-to-realistic`、「鎖定色卡比較視角」區（`suggest-master-view`／`lock-master-view`／`master-view-status`）。

**唯一排版差異**：bella 多一個 hidden 的 `proposal-scheme-bar` 舊 A/B 相容分段（:873-876），本分支已移除——對使用者無影響。

**功能流完全相同**（handler 逐字一致）：切視角（sv2 bella:17881／本分支:15096）；建議視角＝orbit＋corner preset；`lockMasterRenderView`（本分支 sv2:12807-12872）純前端多重 gate（內容勾選、scheme 非 stale、視覺問卷、finishes、色卡、逐房選擇、透視相機）→ 寫 `proposalReview.masterView`＋`locked_scheme_id` → `workflow.complete` → 進第 8 步。無專屬 endpoint，持久化走 `scheduleSave`＝`PUT /api/projects/{id}`。

（注意：遠端增量把第 8 步色卡確認 `confirmRenderPalette` 硬化為第 7 步完成關卡，見第 8 節第 10 條。）

---

## 6. 第 8 步 AI 渲染與成果包（`ai-render-step`）

### 6.1 bella-new 排版（scene.html:910-941）

- **左欄檢視區**：toolbar「色卡比較視角」＋服務狀態；`ai-render-viewer`；狀態列。**無**內嵌生圖影像層。
- **右欄「色卡比較與逐房渲染」**：
  1. **色卡比較**（:923-930）：色卡選項、`request-palette-renders`「建立色卡比較任務」、結果格、`confirm-render-palette`（隱藏）「確認選取色卡並開始逐房間視角」。
  2. **逐房間視角**（:931-937，hidden）：房間清單、`save-room-view`、`submit-room-renders`「送出已保存的房間渲染」。
  3. `remote-render-jobs` 任務狀態區。
- **無** OpenRouter 生圖區塊、無成果包常駐按鈕、無 PDF。

### 6.2 bella-new 功能流

視角來源：第 7 步逐房鎖定的 `proposalReview.roomViews[roomId]`，全程沿用。

- **色卡比較**：`request-palette-renders` → render-brief dialog（送出前確認＋`renderBriefHasSpatialConflict` 改格局字眼二次確認）→ **`POST /api/projects/{id}/render-jobs`**（mode=palette_comparison，sv2:15575）→ job 佇列顯示。
- **逐房生圖（bella 的 AI 生圖主線）**：`submit-room-renders` → render-brief("room_final") → `submitRoomRenders(brief)`（:16336）：
  - initial → **`POST /api/projects/{id}/ai-renders`**（:16373，body scene＋rooms[{room_id,camera,reference_png_data_url,note}]）**同步回圖**存 `finalRooms[roomId]`；
  - revision → **`POST /api/projects/{id}/ai-renders/{roomId}/edit`**（:16353，feedback＋image_data_url），**每房限一次**；
  - 每完成一房自動跳下一房；全部完成 `workflow.complete("ai_render")`。
  - 服務狀態：**`GET /api/ai-render/status`**（:16083）。
- **成果包**：全房生圖完成後**動態注入** `download-engineering-delivery`「建立並查看裝潢簡報與費用明細」（:16028）→ **`POST /api/projects/{id}/design-delivery`**（:16597）→ 開 `design-delivery-dialog`。
- **成果包聚合＝四章 01-04**（:16533-16543）：01 逐房設計與裝潢（問卷/用途/家具/材質＋生圖）→ 02 工程報告書（結構統計、完成 N/M 房）→ 03 資安工程審核 → 04 裝潢與家具預算報告書（budget.lines 表）。**無 05 章、無 PDF**；dialog footer 僅「下載成果包 JSON」。
- 註：bella scene_v2.js 含大量 `legacy*` 死碼與同名多重定義（legacySubmitRoomRendersV2 等），上述為 bindEvents 實際綁定的生效路徑。

### 6.3 本分支排版與功能（scene.html:897-948）

- 左欄多 **`ai-render-image-stage`**（:905，本分支獨有）：生圖完成後影像**覆蓋 3D 檢視器**，`role="button"` 點擊互切，另有「查看生圖」toggle。
- 右欄 1、2、jobs 區同 bella，另**多兩區（本分支獨有）**：
  3. **AI 寫實生圖 `ai-openrouter-section`**（:932-939）：eyebrow「OPENROUTER · NANO BANANA」、服務狀態、`ai-openrouter-generate`「對每個房間視角生成寫實圖」、結果格。
  4. **成果包與設計提案 `delivery-proposal-section`**（:940-945）：常駐 `design-delivery-generate`「產出成果包（設計・工程・預算）」。
- 功能流：
  - 色卡比較流**同 bella**（render-brief→render-jobs，sv2:13913/13837）。
  - **`submitRoomRenders`（:13944）同名不同義**：→ **`POST /api/projects/{id}/render-jobs`**（mode=room_final）**只推佇列**、`workflow.complete`——**無 ai-renders 同步生圖、無 finalRooms、無 revision**。
  - **OpenRouter 一鍵生圖（本分支主線）**：`runAiOpenrouterRender`（:13276）：`GET /api/ai-render/status` 確認服務 → 逐房 `setCameraState`＋`capturePng` 取參考圖 → **`POST /api/projects/{id}/ai-renders`**（:13300，body `{project_id, scene, rooms}`——**無 configuration_snapshot**，對照遠端增量第 10 條）同步回圖存 `openRouterRenders`；完成即生圖覆蓋左側。每張結果卡「修改這張（整批僅一次）」→ **`ai-openrouter-edit-dialog`**（:949-966，本分支獨有）→ **`POST /api/projects/{id}/ai-renders/{roomId}/edit`**（:13420），`editRemaining` 控制**整批一次**額度。測試期預設只生第一房控成本（ponytail 註記 :13283）。
  - **成果包（常駐、可先於生圖）**：`generateDesignDelivery`（:13702）→ **`POST /api/projects/{id}/design-delivery`**（:13761，rooms 的 render 取自 openRouterRenders，可為 null）→ **五章 01-05**（:13673-13684）＝bella 四章＋**05 設計提案 PDF**。
  - **設計提案 PDF 全鏈（本分支獨有）**：dialog footer `delivery-proposal-generate` → **`POST /api/projects/{id}/delivery-proposal`**（:13529）→ 下載連結 **`GET /api/projects/{id}/delivery-proposal/pdf`**（:13480）；`GET /api/delivery-proposal/status`（:13502）檢查排版引擎。

### 6.4 差異對照表

| 區塊/功能點 | bella-new | 本分支 | 分類 | 功能影響 |
| :-- | :-- | :-- | :-- | :-- |
| 面板雙欄骨架（色卡比較＋逐房視角＋jobs） | 有 :910-938 | 有 :897-931 | 相同 | 無 |
| 色卡比較流（render-brief→render-jobs） | 有 sv2:16126,17929 | 有 sv2:13913,15122 | 相同 | 無 |
| render-brief＋spatial conflict 二次確認 | 有 sv2:15348,15427 | 有 sv2:13837 | 相同 | 無 |
| 視角來源＝第 7 步 roomViews 快照 | 有 | 有 sv2:13076,13151 | 相同 | 無 |
| 「送出房間渲染」實際行為 | ai-renders **同步生圖＋每房 revision** sv2:16336 | render-jobs **佇列提交** sv2:13944 | 已移植-實作不同 | **同一按鈕：bella 直接出圖可改；本分支只丟背景任務** |
| AI 寫實生圖區塊（OpenRouter 一鍵） | 無 | 有 :932-939 / sv2:13276 | 本分支獨有 | 一鍵全屋生圖＋服務狀態 |
| 生圖影像覆蓋左側 3D（互切） | 無 | 有 :905-909 / sv2:13339 | 本分支獨有 | 生圖後左側直接看圖 |
| 逐張修訂 UX | 綁逐房流程（無專屬 dialog）sv2:16353 | 專屬 dialog＋每卡按鈕 :949 / sv2:13409 | 已移植-實作不同 | 本分支動線明確；額度改整批一次 |
| `GET /api/ai-render/status` | 有 sv2:16083 | 有 sv2:13260 | 相同 | 無 |
| 成果包 `POST design-delivery` | 有 sv2:16597 | 有 sv2:13761 | 相同 | 無 |
| 成果包觸發入口 | 動態注入、須全房生圖完成 sv2:16028 | 常駐按鈕 :944 | 已移植-實作不同 | 本分支隨時可產出（render 可 null） |
| 成果包章節 | 四章 01-04 sv2:16540-16543 | 五章 01-05 sv2:13680-13684 | 已移植-實作不同 | 本分支多 PDF 章節 |
| 設計提案 PDF（generate/download/status） | 無 | 有 :991-996 / sv2:13480,13517,13529 | 本分支獨有 | 完整 PDF 端點鏈 |
| 成果包 JSON 下載 | 有 sv2:16552 | 有 sv2:13693 | 相同 | 無 |

### 6.5 功能層面重點差異

1. **「送出房間渲染」語意完全不同（最關鍵）**：bella 該按鈕是生圖主線（同步出圖、逐房推進、每房一次修訂、末端長出成果包按鈕）；本分支同名函式退化為 render-jobs 佇列提交（不出圖、無修訂）。
2. **本分支把 AI 生圖獨立成常駐區塊**：OpenRouter nano-banana 一鍵對所有鎖定視角生圖；bella 無此區塊。
3. **生圖結果呈現**：本分支影像覆蓋左側 3D 並可互切；bella 只在右欄結果卡與成果包內。
4. **修訂 UX**：本分支專屬對話框＋整批一次額度；bella 綁逐房 render-brief、每房各一次、動線隱晦。
5. **成果包門檻**：本分支常駐、未生圖也能產出；bella 須全房生圖完成才出現按鈕。
6. **成果包內容**：本分支五章含設計提案 PDF 章節；bella 四章僅 JSON 下載。
7. **PDF 是本分支獨有完整功能鏈**（produce／download／engine status 三端點 bella 皆無）。

---

## 7. 檔尾 dialog 總對照

| dialog / 覆蓋層 | bella-new | 本分支 | 歸屬 |
| :-- | :-- | :-- | :-- |
| `ai-openrouter-edit-dialog`（單次生圖修改） | — | :949 | 第 8 步，本分支獨有 |
| `render-brief-dialog` | :943 | :968 | 第 8 步，相同 |
| `design-delivery-dialog` | :959（僅 JSON） | :984（＋PDF 控件） | 第 8 步，已移植-實作不同 |
| `surface-adjustment-dialog` | — | :1003 | 6C，本分支獨有 |
| `lighting-adjustment-dialog` | — | :1016 | 6C，本分支獨有 |
| `room-scheme-selection-dialog` | :973 | :1029 | 6B，相同 |
| `room-scheme-3d-preview-dialog`（全屏可旋轉） | :1000 | — | 6B，bella 獨有 |
| `furniture-replacement-drawer` | :1016 | :1058 | 6A/6B，相同 |
| `furniture-catalog-drawer` | :1050（scope/空間/用途/批次完整版） | :1092（三下拉簡化版） | 第 5/6 步，已移植-實作不同 |
| `questionnaire-material-catalog-dialog` | :1091 | :1130 | 第 5/6 步，相同（關閉鈕實作異） |
| `questionnaire-ceiling-picker-dialog` | :1118 | :1157 | 第 5 步，相同 |
| `placement-busy` 擺放遮罩 | — | :1174 | 第 5 步，本分支獨有 |

---

## 8. 遠端增量：e97adfce → 09ef2855

`origin/bella-new` 比本地快照多 9 個 commit（`6140f85d`…`09ef2855`），約 +855 行，集中在第 6 步材質/家具與視角品質。**以下功能經 grep 確認本分支全部沒有**（或本分支走自己的舊實作）：

1. **逐房材質草稿持久化＋隨時可解鎖**（`6140f85d`、`09ef2855`）：`restoreProject` 從 `serverState.realistic_3d.roomSurfaceDrafts` 載回 `roomFinishDrafts`；`confirmQuestionnaireFinishes` 不再清空草稿；`roomSurfaceAssignments` 增送 `step_six_surface_confirmed(_at)`；解鎖鈕移進 header（`rp-step-six-lock-control`）並新增 sticky 變體 `unlock-room-surfaces-sticky`（兩顆都綁解鎖）。→ 本分支：無生命週期，`roomFinishDrafts` 固定重設 `{}`（sv2:6502/7596）。
2. **材質推薦收緊**（`03280cdc`）：泳池面料全域排除、馬賽克僅限浴室（原濕區皆可）；第 6 步色卡/材質卡改用 `recommendedStepSixMaterialOptions`（風格相容排序）；自選 pair 置頂。→ 本分支材質流不同，無對應。
3. **家具跨房自動修復**（`ab93ae90`）：`misplacedAssignedRoomFurniture()`＋`repairFurnitureRoomPlacements()`——還原時偵測家具（或其 scene 物件）不在指定房多邊形內，以參數化 `relayoutFurnitureForScheme({roomIds, movableFurnitureIds})` 僅重排受影響房、僅移動出錯家具並鎖定，狀態列報告「修正 N 件跨房間家具」。→ 本分支無。
4. **家具 ID 一對一映射與生成後對帳**：`sceneObjectIndexMapByFurnitureId()`（全域一對一配對，防重複型號互相覆蓋）；`reconcileFurniture2dAfterGeneration()`（生成後移除已送出項再 upsert 回傳物件）。→ 本分支：舊 findIndex 邏輯。
5. **舊 8cm 靠牆縫修復**（`1f30607b`）：`repairLegacyWallFurnitureGaps()`（scene_unit_contracts.js，16 種靠牆型別、偵測 7.5-8.5cm 縫、貼齊完成面），還原時對每個 scheme 執行。→ 本分支無。
6. **拖曳吸附貼完成面**（`7f352acf`）：`snapFurnitureToRoomSurface()`（scene_visual_contracts.js）——房界即完成面、`WALL_GAP` 6→**0**、貼齊時轉正 0/90°、角落雙面貼；浮動面板旋轉鈕「旋轉 180°」→「**旋轉 90°**」。→ 本分支：`WALL_GAP=6`（scene_viewer.js:5049）、走舊 `snapDragPositionV2`、浮動面板為「左轉 15°／右轉 15°」（:4387-4388）。
7. **推斷牆厚**（`a7cd0c20`）：`inferredWallThicknessCm()`（房界與牆段中線距的中位數）取代硬編碼 12cm。→ 本分支：硬編碼 12。
8. **地板貼圖 UV 正規化**（`cd0ec104`）：房面 ShapeGeometry 套 `normalizedPlanarUvs`（scene_texture_uv.js）。→ 本分支 viewer 無此 import。
9. **房間視角對齊**（`18bdee5c`）：bella 自家 `roomScenePolygon`/`scenePointInsideRoom`/`roomSceneTarget` 系列的 Z 軸翻轉修正（`center.y - point.y`，因 viewer 翻轉來源 Z）＋新守衛 `roomCameraTargetsRoom()`——已存視角的 target 不在房內即作廢重建。→ 本分支：無這組函式（取景走自家 `roomWalkPayload` 路徑，歷史上有各自的 world-z 修正），**無等價的視角落點守衛**。
10. **第 7/8 步串接硬化**：`confirmRenderPalette` 寫入 `masterView{style_card_id, configuration_snapshot_id}` 並強制 `workflow.complete("proposal_review")` 通過才放行（未完成逐房視角會被擋下）；新 `lockedConfigurationSnapshot()`（無第 7 步鎖定快照即 throw）；生圖 payload `aiRenderSubmissionPayload` 附 `configuration_snapshot`；`downloadEngineeringDelivery` 改用鎖定快照；`selectRenderRoom` 無有效視角時 fallback `roomCameraSuggestion(room)`。→ 本分支：`confirmRenderPalette` 為無守衛簡版（sv2:13199-13211）、`ai-renders` payload 無 configuration_snapshot（:13303）、成果包用 `refreshConfigurationSnapshot`。
11. **零星 UX 修正**：`skipQuestionnaireWithDefaults` 連同確認鈕一起鎖定防連點；點第 6 步 nav 可直達 realistic（若已可進入）；plan 分頁切回時重繪並先清空編號層（修殘影）；`placementResolutionText` 改彙總文案（「替換 N 件、移除 N 件、N 件需手動處理」）。→ 本分支無。

---

## 9. 結論

**bella 獨有、本分支若要對齊需移植**：

- 第 5 步型錄分類瀏覽器（範圍/空間/用途/批次多選/去重/引導文）。
- 6B 逐房材質分頁＋「草稿→鎖定→逐房確認→全部確認放行」狀態機（遠端增量再加草稿持久化與隨時解鎖）。
- 第 6 步的材質型錄入口。
- 逐房方案比較的全屏可旋轉 3D 預覽 dialog。
- 第 8 步逐房同步生圖＋每房一次修訂的主線。
- 遠端 9 commit 全部：貼完成面吸附（WALL_GAP=0）、推斷牆厚、跨房/舊縫自動修復、家具 ID 一對一映射、視角落點守衛、色卡確認守衛、生圖 payload 帶鎖定快照、地板 UV。

**本分支獨有、bella 沒有**：

- 「更新推薦」鈕、`placement-busy` 遮罩、`outdoorPenalty` 戶外家具過濾。
- 6B「指定家具外觀」常駐面板；6C 材質/燈光任務對話框＋`undo-style-change`＋顯式「保存即時寫實方案」。
- 離屏快照佇列（不佔前景 viewer、拍完卸載）。
- 第 8 步 OpenRouter 一鍵生圖區塊、生圖覆蓋 3D 互切、單次修改對話框。
- 成果包常駐入口、第 05 章設計提案 PDF＋`delivery-proposal` 三端點全鏈。

**合併風險（同名不同義，整合時最容易踩雷）**：

- `submitRoomRenders`：bella＝同步生圖；本分支＝佇列提交。
- `save-realistic-scene`：bella＝6B 材質全確認後的 hidden 自動推進；本分支＝6C 可見保存鈕。
- `confirmRenderPalette`：遠端 bella＝第 7 步完成守衛；本分支＝無守衛簡版。
- `furniture-catalog-drawer`／`searchGlbFurniture`：同 id 同名，內部結構與參數（`types=` vs `group=`）不同。
- 材質功能的「步驟歸屬」整體不同（bella 6B 分頁 vs 本分支 6C 對話框），不能逐 element 對拷。
