# UI 規格書 (UI Spec) - RoomPilot 八步精靈主頁 `/scene`

> **版本:** 0.1 | **更新:** 2026-08-11 | **狀態:** 草稿
> **Owner:** Bella（`backend/server/` 含 static 八步 UI，AGENTS.md:36）
> **回答的問題:** `/scene` 頁面有哪些區塊、DOM id、狀態、操作與互動？前端不用猜。
> **語域:** L3（工程）
> **實例:** 每頁面一份（本份對應八步精靈主頁 `/scene`，即 `backend/server/static/scene.html`）
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

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
- [10. 待確認](#10-待確認)
- [11. 追溯](#11-追溯)

## 1. 頁面目的 (Page Purpose)

讓使用者（屋主／設計協作者）在單一頁面完成八步 AI 室內設計工作流：建專案 → 上傳平面圖 → 標定尺寸 → 確認結構 → 需求問卷 → 配置與預覽 → 方案鎖定與色卡 → AI 生圖與成果包（REQ-001～REQ-012）。對應旅程節點見 `ux_research_and_journey.md` §5（規劃中，登錄簿 §6）。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 首頁 `index.html`（home.js）；或直接開 `/scene` 恢復既有專案（FR-001） |
| 出口 | 無跳頁——八步全在本頁完成；成果為 PDF／JSON 下載（FR-012） |

## 2. 版面配置 (Layout)

```text
+------------------------------------------------------+
| 側欄：8 顆步驟導覽鈕 (scene.html:23-30, data-step)     |
+------------------+-----------------------------------+
| 主區：目前步驟的 panel（同時只顯示一個）                |
|  #project-step / #upload-step / #scale-step /         |
|  #space-step / #requirements-step / #layout-2d-step / |
|  #white-model-3d-step / #realistic-3d-step /          |
|  #proposal-review-step / #ai-render-step              |
+------------------------------------------------------+
```

單頁應用：`scene.html`（1219 行）只載入 `scene_v2.js`（module entrypoint，hash 釘死，scene.html:7、:1217）與 `site.css`。內部狀態機 11 步（`scene_workflow.js:4-16 WORKFLOW_STEPS`），UI 導覽鈕 8 顆，panel 對映 `WORKFLOW_PANEL_BY_STEP`（`scene_workflow.js:18-30`）。無 wireframe／Figma 來源（見 §9）。

## 3. 欄位與元件 (Fields / Components)

八步各一節；DOM id 證據：scene.html 與 `scene_v2.js`（事實檔 04-frontend §4-§8）。

### 3.1 步 1 建立專案（data-step=`project` → `#project-step`）

| 元件 | id | 來源／去向 |
| :--- | :--- | :--- |
| 專案表單 | `#project-form` | `POST /api/projects`（FR-001） |
| 建立按鈕 | `#create-project` | 建立後進入步 2 |

### 3.2 步 2 上傳平面圖（`upload` → `#upload-step`）

| 元件 | id | 來源／去向 |
| :--- | :--- | :--- |
| 檔案輸入（PNG/JPG/DXF） | `#floorplan-file` | 平面圖辨識 API（FR-002，main.py:2981） |
| 確認上傳 | `#confirm-upload` | 回應含 `analysis`＋`layout_json`（ACPT-002） |

### 3.3 步 3 確定尺寸（`recognition`＋`calibration` → `#scale-step`）

| 元件 | id | 說明 |
| :--- | :--- | :--- |
| 標定舞台／圖／疊層 | `#floorplan-calibration-stage/-image/-overlay` | 兩點標定（scene_calibration.js，FR-003） |
| 實際長度輸入（公分） | `#floorplan-scale-cm` | 換算公分尺度（NFR-001） |
| 套用標定 | `#apply-floorplan-calibration` | 結果隨 workflow JSON 保存 |

### 3.4 步 4 空間與結構（`space_confirmation` → `#space-step`）

| 元件 | id | 說明 |
| :--- | :--- | :--- |
| 平面編輯舞台 | `#space-plan-stage/-image/-overlay`、`#room-editor` | 人工校正牆/門/窗/房間（FR-004） |
| 結構確認面板＋3D 預覽 | `#structure-confirmation-panel`、`#structure-3d-preview` | scene_structure_*、createStructurePreview |
| 尺寸標註平面 | `#dimensioned-plan-stage` | scene_dimensioned_plan |
| 確認結構 | `#confirm-space` | `POST /api/floorplan/confirm` → 鎖定 layout_json（ACPT-004） |

### 3.5 步 5 需求問卷（`requirements` → `#requirements-step`）

| 元件 | id | 說明 |
| :--- | :--- | :--- |
| 全屋／視覺問卷 | `#whole-house-questionnaire`、`#visual-questionnaire` | FR-005；視覺題庫 `/api/questionnaire/visual-catalog` |
| 面材偏好 | `#questionnaire-finishes` | — |
| 家電／生圖需求 | `#questionnaire-generative-*` | 只進 `render_context.appliance_requirements`（FR-014、ACPT-013） |
| 確認問卷 | `#confirm-requirements` | 產出 client_brief（ACPT-005） |

### 3.6 步 6 配置與預覽（`layout_2d`＋`white_model_3d`＋`realistic_3d`，三個 panel）

| 元件 | id | 說明 |
| :--- | :--- | :--- |
| 2D 編輯舞台 | `#layout-plan-stage/-image`、`#layout-room-overlay`、`#layout-furniture-layer` | 公分↔像素換算 `scene_layout2d.js:293 planCmToLayerPixel` |
| 家具庫／選取工具 | `#furniture-icon-library`、`#selected-2d-furniture` | rotate/replace/delete；家具來源 `GET /api/furniture`（FR-013） |
| 自動配置／確認 2D | `#auto-layout-furniture`、`#confirm-layout-2d` | `/api/scene/generate`、`/api/scene/layout`（FR-006/007） |
| AB 方案比較 | `#design-scheme-compare`、`#scheme-a/b-plan-image/-overlay` | `scene_v2.js:364-367`；逐房選擇 `#open-room-scheme-selection` → `#room-scheme-selection-dialog`、`#room-scheme-gate` |
| 白模 viewer | `#white-model-viewer` | whiteViewer（`scene_v2.js:582-624`） |
| 牆/地材質面板 | `data-step-six-surface-panel="wall|floor"`（scene.html:769-818）、`#wall-material-grouped`、`#floor-material-grouped`、`#draw-material-boundary` | 套用走 `whiteViewer.updateRoomSurfaces`（`scene_v2.js:14049`，FR-008） |
| 確認材質／白模 | `#confirm-room-surfaces`、`#confirm-white-model` | confirmWhiteModel 必帶 `validate_only`（ACPT-008、SCN-005） |
| 擬真層 | `#realistic-viewer`、`#lighting-editor`（`#ceiling-style`、`#light-style`、`#ceiling-conflicts`） | 衝突偵測 `detectCeilingConflicts`（scene_style_packs.js:465） |

### 3.7 步 7 方案鎖定與視角（`proposal_review` → `#proposal-review-step`）

| 元件 | id | 說明 |
| :--- | :--- | :--- |
| 提案 viewer | `#proposal-review-viewer` | proposalViewer |
| 色卡格 | `#proposal-palette-grid` | 6 風格 × 3 色卡（登錄簿 §5） |
| 視角建議／鎖定 | `#suggest-master-view`、`#lock-master-view` | 鎖定相機供第 8 步 img2img（FR-009） |

### 3.8 步 8 AI 渲染與成果包（`ai_render` → `#ai-render-step`，scene.html:950）

註：口語「第 7 步＝色卡、第 8 步＝全房生圖」兩者都在本 panel（色卡是 `palette_comparison` 模式），與導覽鈕編號不同義（04-frontend §4 註）。

| 元件 | id | 說明 |
| :--- | :--- | :--- |
| 色卡選項／結果／確認 | `#palette-render-options`、`#palette-render-results`、`#confirm-render-palette` | `requestPaletteRenders`（`scene_v2.js:16700`）→ `POST .../palette-renders`（FR-010） |
| 生圖 viewer 與疊層 | `#ai-render-viewer`、`#ai-render-image-stage`（scene.html:958，role=button）、`#ai-render-image-toggle` | `showRenderImageEnlarged`/`closeRenderImageStage`（`scene_v2.js:17434-17470`） |
| 生圖狀態／房清單 | `#ai-render-status`、`#remote-render-jobs`、`#render-room-list`、`#save-room-view` | 逐房單線 `submitRoomRenders`（`scene_v2.js:16992`，FR-011） |
| 交付 dialog | `#design-delivery-dialog`、`#design-delivery-generate`、`#delivery-proposal-generate/-download/-status`、`#render-brief-dialog` | FR-012；PDF 用圖來自前端 payload（`scene_v2.js:17640-17667`） |

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 限制 |
| :--- | :--- | :--- | :--- |
| 拖曳家具（2D/3D） | 拖放 | `/api/scene/validate` 引擎裁決落點（FR-007） | 門前 75cm 淨空等違規被拒（ACPT-007） |
| 產生方案 B | AB 比較區 | `ensureSchemeB`（`scene_v2.js:3665-3688`）帶 `placement_variant: "B"` | 失敗標 `stale` |
| 逐房選 A/B | `selectSchemeForRoom`（`scene_v2.js:4115、4556`） | 合成回 scheme A（`:4583-4590`），座標鎖定不漂移（SCN-003） | — |
| 生色卡比較圖 | `#confirm-render-palette` | 代表房截圖＋`POST palette-renders` | 每專案一次，二次 409（ACPT-009） |
| 逐房生圖／一鍵全生 | 房卡按鈕／`submitAllRoomRenders`（`scene_v2.js:17075`） | `POST ai-renders`；全生才顯示全螢幕遮罩 | — |
| 改圖 | 房卡改圖 | `POST .../ai-renders/{roomId}/edit` | 每房一次，`revision_submitted_at` 擋重複（`scene_v2.js:17003-17009`，ACPT-010） |
| 走動預覽 | `setWalkRoom`/`setViewMode` | 第一人稱檢視（scene_viewer.js） | — |
| 下載成果 | 交付 dialog | 提案 PDF／`roompilot-design-delivery-{projectId}.json`（`scene_v2.js:17282`） | 缺 Chromium 回 503（ACPT-011） |

無登入／角色權限機制（頁面無權限欄位；待確認見 §10）。

## 5. UI 狀態 (States)

| 狀態 | 呈現（有證據者） | 證據 |
| :--- | :--- | :--- |
| Loading（全生圖） | 全螢幕等待遮罩，僅 `submitAllRoomRenders` 顯示；單張不顯示 | `scene_v2.js:17075` 之後（04-frontend §7） |
| 恢復（重開瀏覽器） | `GET /api/projects/{id}` 還原 `current_step`；localStorage key `roompilot.workflow.v2` | scene_workflow.js:2、ACPT-001 |
| 衝突（多分頁） | 保存回 409 `project_revision_conflict`，落後方需重載 | project_store.py:28-33、SCN-009 |
| 額度用盡 | 色卡二次／改圖二次回 409 | main.py:2135-2140、2224 |
| 材質衝突 | `#ceiling-conflicts` 顯示天花衝突 | scene_style_packs.js:465 |
| Empty／Error／Permission Denied 全域文案 | 未盤點統一規格 | 待確認（§10） |

## 6. 互動規格 (Interaction Spec)

| 元素 | 規格 | 證據 |
| :--- | :--- | :--- |
| 7 個 viewer 實例 | whiteViewer、realisticViewer、proposalViewer、aiRenderViewer、replacementViewer、glbThumbnailViewer、roomSchemePreviewViewer；隱藏容器（`offsetParent === null`）跳幀防 GPU 撐爆 | `scene_v2.js:582-624`、`scene_viewer.js:5794-5799` |
| 3D 載入 | `loadScene`（scene_viewer.js:4142）唯一整場景 API，無增量；材質改動也整殼重建 | `scene_viewer.js:5826-5829` 註解 |
| 生圖縮圖點擊 | 放大到 `#ai-render-image-stage` 疊層；點空白處關閉切回 3D；`#ai-render-image-toggle` 重開 | scene.html:958、`scene_v2.js:17434-17470` |
| 色卡結果 | base64 只放記憶體 `state.paletteRenderImages`，不持久化；重載後不可再看（一次性） | `scene_v2.js:16759` 註解 |
| 步驟導覽 | 8 顆 `data-step` 鈕切換 panel；改結構須回步 4 並重驗家具 | scene.html:23-30、ACPT-004 |

## 7. 驗證規則 (Validation)

前端不做幾何裁決——合法性唯一權威是 `backend/engine/`（NFR-004、ADR-002）；前端只呈現拒絕訊息。

| 欄位／操作 | 規則 | 觸發時機 | 證據 |
| :--- | :--- | :--- | :--- |
| 家具落點 | 門前 75cm、窗前採光帶（高 ≥90cm）、房外 → 拒絕＋分流訊息 | 拖曳結束呼叫 `/api/scene/validate` | ACPT-007 |
| 標定長度 | 幾何欄位一律公分 `_cm`，payload 帶 `coordinate_unit: "cm"` | 標定套用後全下游 | NFR-001、ACPT-003 |
| 保存 | `expected_revision` 樂觀鎖，落後 409 | 每次保存 | NFR-002 |
| 各輸入欄位前端即時驗證（必填/格式/錯誤文案） | 未盤點 | — | 待確認（§10） |

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** 未盤點到任何 RWD 規格；`site.css` 斷點設計待確認（§10）。
- **鍵盤操作:** 未盤點統一 Tab/Escape 規格；待確認（§10）。
- **ARIA:** 已知 `#ai-render-image-stage` 帶 `role=button`（scene.html:958）；其餘 ARIA／對比／Focus 標準未定義，待確認（§10）。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | **無 Figma 來源**——本頁 SSOT 即 `backend/server/static/scene.html`＋`site.css`（ADR-006） |
| Design Tokens | 無獨立 tokens 檔；樣式集中於 `site.css`（scene.html:1217 hash 釘死） |
| 元件對照 | DOM id ↔ 模組見 §3 各表與 04-frontend §2 模組表 |
| 已知限制 | ES import cache-key 雜湊鏈：改任何被 import 模組需 leaf-first 級聯重算 hash（`tests/test_scene_v2_contract.py:706` 強制）；CRLF 正規化陷阱見 04-frontend §10 |

## 10. 待確認

1. 全域 Loading／Empty／Error／Permission Denied 統一呈現與文案——scene_v2.js 19,583 行未逐一盤點。
2. 表單欄位級驗證規則（必填、格式、錯誤文案、blur/submit 時機）未盤點。
3. RWD 斷點、鍵盤操作順序、ARIA/對比標準——`site.css` 與 DOM 未做 a11y 稽核。
4. 頁面無登入／權限機制的假設：未在程式碼找到權限欄位，但未窮舉驗證。
5. `scene.js`（3128 行）與 `viewer.js` 為未被 scene.html 引用的遺留碼，是否仍有路由使用（04-frontend §1）。

## 11. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應需求 | REQ-001～REQ-012、REQ-014；FR-001～FR-014、NFR-001/002/004 |
| 對應情境 | SCN-001～SCN-005、SCN-007～SCN-009 |
| 對應決策 | ADR-002（引擎唯一裁決）、ADR-006（static 為正式前端）、ADR-007（workflow 快照） |
| 上游 | [`../00-registry.md`](../00-registry.md)、`ux_research_and_journey.md`／`information_architecture.md`（登錄簿 §6 規劃）、事實檔 04-frontend（git yen@8863a36c） |
| 下游 | `../04_design/api_spec.md`、`../05_qa/test_plan.md` |
