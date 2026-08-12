# UI 規格：第 2 步 上傳平面圖 (UI Spec - Step 2 Upload) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** MOD-WEB（Bella）；驗收條件與 owner 核准欄位屬產品 owner
> **回答的問題:** 第 2 步畫面有哪些區塊、欄位、狀態、操作與確切中文文案？前端不用猜。
> **語域:** L3（工程）
> **實例:** 每頁面一份（`ui_spec-<page>.md`）；本份只涵蓋 `#upload-step`（`backend/server/static/scene.html:75`–`109`）
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。DOM id 與 UI 文案逐字取自 `scene.html`／`scene_v2.js` 實檔；行號隨程式碼演進，衝突時以原始碼為準。

本文件回答：第 2 步的 DOM 結構、可操作元素、狀態與錯誤文案、以及「上傳成功 → 自動辨識 → 跳第 3 步」這條接續行為。
本文件**不含**：`POST /api/projects/{id}/floorplan` 的 multipart 欄位與 schema（見 [openapi-project-workflow](../04_design/openapi-project-workflow-v1.yaml) 與 [api_spec](../04_design/api_spec.md)）、辨識演算法與比例尺（見 [ui_spec-step3](./ui_spec-step3-recognition.md)）、跨步旅程（見 [ux_research_and_journey](./ux_research_and_journey.md)）、導覽與面板總表（見 [information_architecture](./information_architecture.md)）。

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

讓使用者把手上的平面圖（DXF／PNG／JPG／JPEG）交給系統，並親自確認「這張就是要辨識的圖」——這個勾選是第 3 步辨識的硬前置（FR-011）。對應 SCN-004、SCN-005。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 第 1 步建立專案（`REQUIRED_COMPLETIONS.upload = ["project"]`，`scene_workflow.js:44`）；或還原既有專案後由 `showStep()` 直接進入 |
| 出口 | 第 3 步確定尺寸——**無獨立「下一步」按鈕**，`confirmUpload()` 成功後直接 `showStep("recognition")`（`scene_v2.js:1863`） |

面板為單頁 `scene.html` 的 `section#upload-step.rp-step-panel[data-panel="upload"]`；導覽第 2 顆按鈕 `[data-step="upload"]`（`scene.html:23`）。膠囊文案：`步驟 2 / 選擇 DXF、PNG 或 JPG，並確認圖檔內容`（`scene_v2.js:299`）。

## 2. 版面配置 (Layout)

```text
.rp-split-workspace.rp-upload-workspace
├─ .rp-plan-pane                     左：圖檔投放與預覽
│  ├─ .rp-pane-heading   「上傳平面圖」＋ #upload-file-state（右上狀態字）
│  └─ label.rp-drop-zone[for=floorplan-file]
│     ├─ input#floorplan-file        （CSS 1×1、opacity 0，site.css:6475）
│     ├─ img#upload-floorplan-preview[hidden]
│     └─ span#upload-floorplan-placeholder 「DXF · PNG · JPG／將平面圖放在這裡…」
└─ aside.rp-control-pane             右：確認與送出
   ├─ #project-floorplan-confirmation-notice（checkbox ＋ label）
   ├─ p#upload-error[aria-live=polite]
   └─ button#confirm-upload[disabled] 「確認並開始辨識」
```

## 3. 欄位與元件 (Fields / Components)

| 欄位／元件 | 型態 | 來源／繫結 | 顯示規則 |
| :--- | :--- | :--- | :--- |
| `#floorplan-file` | file input | `accept=".dxf,.png,.jpg,.jpeg,image/png,image/jpeg,application/dxf"`（`scene.html:86`） | 視覺上不可見（1×1、opacity 0），點擊區由包住它的 `label.rp-drop-zone` 提供 |
| `#upload-file-state` | text | `state.pendingFile`；還原時取 `analysis.filename` 或 `workflow.data.upload.filename`（`scene_v2.js:19333`） | 初始「尚未選擇」；選檔後 `檔名 · N.N KB`；副檔名不符時「格式不支援」 |
| `#upload-floorplan-preview` | img | 選檔中：`URL.createObjectURL(file)`；已上傳：`/api/projects/{id}/floorplan/source?v=<ts>` | `object-fit: contain`、高 336px（`site.css:6463`）；**`.dxf` 不產生預覽**（`showPendingPreview` 直接 return，`scene_v2.js:1748`），此時只保留 placeholder |
| `#upload-floorplan-placeholder` | text block | 靜態 | 有預覽時由 `.rp-drop-zone.has-preview` 隱藏（`site.css:6459`） |
| `#project-floorplan-confirmation` | checkbox | 送出時寫入 `workflow.floorplan_confirmation.confirmed = true`（`scene_v2.js:1815`–`1827`） | 未持久化勾選狀態到本地；重新進入本步一律未勾 |
| `#upload-error` | text（`aria-live="polite"`） | 前端驗證訊息或 `errorMessage(error)`（`scene_v2.js:642`） | 每次送出先清空 |
| `#confirm-upload` | button | `updateUploadConfirmationState()`（`scene_v2.js:1763`） | `disabled` 直到「已選檔 ∧ 已勾選」同時成立 |
| `#global-status` | text（區塊 `aria-live="polite"`，`scene.html:32`） | `setStatus(message, kind)` | 承載等待與成功訊息；錯誤時另設 `data-kind="error"` |

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 選擇檔案 | 點擊 `label.rp-drop-zone`（含「選擇平面圖」字樣）→ 系統檔案對話框 → `change` | `selectFloorplanFile(file)`（`scene_v2.js:17749`）：檢副檔名、建預覽、更新狀態字與按鈕可用性 | 無角色控制（Pilot 全 app 無認證，NFR-019／DEC-014 待核准） |
| 拖放檔案到投放區 | — | **目前不生效**：`.rp-drop-zone` 未綁 `dragover`／`drop`（全檔僅 `#space-plan-stage` 有，`scene_v2.js:18058`），且 `input` 被縮成 1×1；投放區文案「將平面圖放在這裡」屬視覺承諾，實作缺席（待確認 U2-01） | — |
| 勾選「我已確認圖檔內容正確」 | `change` | `updateUploadConfirmationState()`（`scene_v2.js:17750`）重算 `#confirm-upload` 的 disabled | — |
| 確認並開始辨識 | 點擊 `#confirm-upload` | `confirmUpload()`：`POST /floorplan` → `PUT /workflow`（`floorplan_confirmation.confirmed`）→ `POST /floorplan/analyze` → `showStep("recognition")` ＋ `scheduleSave("recognition")` | — |

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案 |
| :--- | :--- | :--- |
| Empty（未選檔） | 虛線投放框＋placeholder；`#confirm-upload` disabled | `#upload-file-state`：「尚未選擇」；投放區：「將平面圖放在這裡／或從電腦中選擇檔案，系統會先替您檢查格式」 |
| 已選檔（影像） | 預覽圖填滿投放框，框線轉實線白底 | `#global-status`：「平面圖已顯示。請確認圖檔內容正確並勾選後繼續。」 |
| 已選檔（DXF） | 無預覽，維持 placeholder | `#global-status`：「已選擇 DXF。確認檔案正確並勾選後，系統會產生圖面預覽。」 |
| Loading（上傳＋辨識中） | **無全畫面遮罩**（`#placement-busy` 不用於本步），僅狀態列文字；按鈕保持可點（待確認 U2-02） | `#global-status`：「正在保存原圖並辨識牆、門、窗…」 |
| Error（415 不支援格式） | `#upload-error` 顯示；不改變既有預覽 | 前端攔截：「只支援 DXF、PNG、JPG 或 JPEG。PDF、WEBP、HEIC 等格式不會上傳。」／伺服器 `unsupported_floorplan_type`：「只支援 DXF、PNG、JPG 或 JPEG 平面圖。」 |
| Error（422 空檔／壞圖） | 同上 | `empty_floorplan`：「檔案沒有內容，請重新選擇平面圖。」／`invalid_floorplan_image`：「檔案副檔名正確，但內容不是可讀取的 PNG 或 JPG 圖片。」 |
| Error（409 未勾選） | 同上（正常流程由前端先擋，此為直接呼叫 API 的防線） | `floorplan_confirmation_required`：「請先確認圖檔內容正確，才能開始辨識。」 |
| Error（辨識失敗） | 停在第 2 步，`#upload-error` ＋狀態列同時顯示 | `dxf_parse_failed`／`cody_recognition_failed` 的伺服器訊息原樣呈現（處置見 [runbook-recognition](../06_ops/runbook-recognition-failed-or-review-blocked.md)，RB-006） |
| Success | 自動切換到第 3 步；本步預覽改指向伺服器原圖 | 第 3 步狀態列接手（「已標出建議端點…」或「辨識完成。…」） |
| Permission Denied | 不適用（Pilot 無認證與角色，`main.py:195`–`197`） | — |

還原既有專案時：若 `upload` 已完成，預覽以 `/floorplan/source` 重建（`scene_v2.js:19489`–`19491`），但 `state.pendingFile` 為空，故 `#confirm-upload` 仍為 disabled——要重跑辨識必須重新選檔。

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `label.rp-drop-zone` | `cursor: pointer`（`site.css:6444`）；無 hover 樣式變化 | 不會 disabled | 無變化 | 副檔名不符：清空 `state.pendingFile` 與預覽，狀態字改「格式不支援」 |
| `#confirm-upload` | 沿用 `.primary-action` | 「未選檔 ∨ 未勾選」時 disabled | **不 disable、無 spinner**（待確認 U2-02） | 訊息寫入 `#upload-error`，焦點移至缺少的欄位：未選檔 → `#floorplan-file`、未勾選 → `#project-floorplan-confirmation` |
| `#project-floorplan-confirmation` | 原生 | 不會 disabled | 無變化 | — |

- 接續行為（本步的核心）：上傳成功並不停留讓使用者按「下一步」，而是同一個 handler 內連續完成上傳 → 寫入確認旗標 → 辨識 → 換頁。任何一環丟錯都停在第 2 步，畫面不前進。
- 重新上傳會再次觸發辨識，伺服器隨即把 `confirmed_floorplan`／`calibration`／`space_confirmation`／`requirements`／`layout_2d`／`white_model_3d`／`realistic_3d` 全部重設為 null（FR-016，`main.py:3036`–`3063`）——等同下游七步作廢，UI 需視為「重做」而非「補上傳」。
- 伺服器錯誤 payload 帶 `focus` 欄位（如 `"focus": "project-floorplan-confirmation"`），但前端 `errorMessage()` 只取 `message`，**未消費 `focus`**（`scene_v2.js:642`–`653`）。

## 7. 驗證規則 (Validation)

| 欄位 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| `#floorplan-file` | 副檔名 ∈ `.dxf/.png/.jpg/.jpeg`（`floorplanExtension()`，`scene_v2.js:1733`） | 「只支援 DXF、PNG、JPG 或 JPEG。PDF、WEBP、HEIC 等格式不會上傳。」 | `change`（選檔當下） |
| `#floorplan-file` | 必選 | 「請先選擇 DXF、PNG、JPG 或 JPEG 平面圖。」 | 點 `#confirm-upload`（防呆，正常情況按鈕為 disabled） |
| `#project-floorplan-confirmation` | 必勾 | 「請先勾選確認圖檔內容正確，才能進入下一步。」 | 點 `#confirm-upload` |
| 伺服器：副檔名 | `FLOORPLAN_EXTENSIONS`（`main.py:153`），不符回 **415** | 見 §5 | `POST /floorplan` |
| 伺服器：檔案內容 | 空 bytes 回 **422** `empty_floorplan`；影像以 `Image.verify()` 檢查，失敗回 **422** `invalid_floorplan_image`；`.dxf` 不做內容檢查（直接視為 `application/dxf`） | 見 §5 | `POST /floorplan` |
| 伺服器：版本 | `expected_revision` 不符回 **409** `project_revision_conflict`（前端目前不送此欄位） | 「專案已在另一個分頁更新，請載入最新版本後再上傳。」 | `POST /floorplan` |
| 伺服器：原圖取用 | 未上傳 **409** `floorplan_missing`、實體檔遺失 **410** `floorplan_source_missing`（ACPT-005） | 「尚未上傳平面圖，請先選擇 DXF、PNG、JPG 或 JPEG 檔案。」／「原始平面圖已遺失，請重新上傳。」 | `GET /floorplan/source`、`POST /floorplan/analyze` |

上傳成功後 `revision` 遞增且 `floorplan/source` 可取回同一檔案（ACPT-004；契約測試 TC-004：`tests/test_project_workflow_api.py:251`）。

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** `.rp-split-workspace` 為兩欄（左圖右控制）；投放區 `min-height: 360px`、預覽固定高 336px。行動裝置斷點行為未在 `site.css` 針對本步另行定義（待確認 U2-03）。
- **鍵盤操作:** `#floorplan-file` 雖被縮為 1×1 但未 `display:none`，仍在 Tab 序列上；Tab 順序＝檔案輸入 → 確認勾選框 → 「確認並開始辨識」。錯誤時以 `.focus()` 主動移動焦點（§6）。**缺口：** 1×1／opacity 0 的 input 取得焦點時沒有可見的 focus 指示（`site.css:6475`–`6480`），鍵盤使用者看不出焦點落在投放區。
- **ARIA / 對比 / Focus:** `#upload-error` 具 `aria-live="polite"`，`.rp-guidance-band`（含 `#global-status`）亦為 `aria-live="polite"`；預覽 `img` 有 `alt="剛選擇的平面圖預覽"`；「DXF · PNG · JPG」格式提示標 `aria-hidden="true"`。全站未做 WCAG 對比實測（待確認 U2-04）。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | 無（repo 內無設計檔或 frame 連結；正式前端即 SSOT，見 ADR-010） |
| Design Tokens | `backend/server/static/site.css`（`.rp-drop-zone` 起於 `site.css:6433`；色票變數如 `--rp-green`） |
| 元件對照 | 本文件 §3 的 DOM id 即程式元件名；面板總表見 [information_architecture](./information_architecture.md) |
| 已知限制 | ① 投放區文案承諾拖放但無 drop handler（U2-01）；② 送出中不鎖按鈕、無遮罩（U2-02）；③ DXF 在本步無預覽，圖面要到第 3 步才由 `configureDxfPreview()` 產生 |

## 10. 追溯

| 項目 | ID |
| :--- | :--- |
| 上游需求決策 | DEC-003（用既有照片或 DXF 就能開案，**待 owner 核准**）、DEC-004（人必須確認過才算數，**待 owner 核准**） |
| 對應功能需求 | FR-005（上傳白名單與內容檢查）、FR-006（原圖取回）、FR-011（未勾選 → 409 辨識閘門）、FR-010（辨識接續，主體規格在 [ui_spec-step3](./ui_spec-step3-recognition.md)）、FR-016（重跑辨識作廢下游） |
| 對應驗收條件 | ACPT-004、ACPT-005（本步主綁）；ACPT-009（勾選閘門，與第 3 步共用） |
| 對應情境 | SCN-004（擋下不支援格式與壞圖）、SCN-005（JPG 上傳成功並預覽）；SCN-006 落在第 3 步 |
| 對應架構決策 | ADR-010（正式前端＝`backend/server/static/` 單頁、八步導覽）、ADR-001（辨識輸出止於 `layout_json`） |
| 對應模組 | MOD-WEB（`scene.html:75`–`109`、`scene_v2.js:1733`–`1869`）、MOD-SRV-STORE（`main.py:1870`–`1926`） |
| 對應測試／維運 | TC-004、TC-005；RB-006（辨識失敗）——見 [test_plan](../05_qa/test_plan.md)、[runbook-recognition](../06_ops/runbook-recognition-failed-or-review-blocked.md) |
| 本文件登記的待確認 | U2-01 拖放上傳是否為承諾功能；U2-02 送出中是否需鎖按鈕／遮罩；U2-03 行動裝置斷點；U2-04 對比與 focus 指示是否納入 Pilot 範圍 |
