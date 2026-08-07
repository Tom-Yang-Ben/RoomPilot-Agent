# UI 規格書 (UI Spec) - 我的專案（/projects）

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** Bella（`frontend/` 目錄 owner，見 `AGENTS.md` 目錄責任表）
> **回答的問題:** `/projects` 頁有哪些區塊、欄位、狀態、操作與文案？前端不用猜。
> **語域:** L3（工程）
> **實例:** 每頁面一份（`ui_spec-<page>.md`）；本份為專案列表頁
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/02_ux_ui/ui_spec.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

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

登入後的中樞頁：檢視可存取的專案（自有＋被分享）、建立新專案、分享專案給屋主、修改密碼、登出。旅程對應 `ux_research_and_journey.md` §5（同輪產出）。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | `/login` 成功後預設導向；首頁 topnav「我的專案」與「開始設計」CTA（`index.html:22,24`）；未登入由 `requireSignedIn()` 轉 `/login?next=/projects`（`projects.js:260`） |
| 出口 | 專案卡「繼續設計」→ `/scene?project_id=`；登出 → `/login`；改密碼成功 → `/login?changed=1`；topnav → `/styles`、`/library`、`/` |

檔案組成：`projects.html`（91 行）＋ `projects.js`（265 行）＋ `auth_client.js`（共用身分層）。

## 2. 版面配置 (Layout)

```text
topbar：logo ｜ topnav（我的專案* / 風格類型 / 家具資料庫 / 登出）
projects-shell
├── projects-intro：H1 + 身分列 #projects-identity ｜「建立新專案」#new-project
├── form#create-form（預設 hidden：名稱 + 備註 + 建立並開始 / 取消）
├── #projects-error（role=alert）
├── details#account-settings：帳號設定：修改密碼（目前密碼 / 新密碼 / 更新密碼）
└── section#projects-list（aria-live=polite）：project-card × N
```

## 3. 欄位與元件 (Fields / Components)

| 欄位 | 型態 | 來源（API 欄位） | 顯示規則 |
| :--- | :--- | :--- | :--- |
| 身分列 `#projects-identity` | text | `roompilot.user`（localStorage） | 「{display_name}（{角色}） · {email}」；角色譯為 管理者／屋主／設計師（`projects.js:68-77`） |
| 專案名（卡片標題） | link | `GET /api/projects` → `name`、`project_id` | 連到 `/scene?project_id=` |
| 角色徽章 | span | `project_role` | owner→擁有者、editor→可編輯、viewer→唯讀（`ROLE_LABELS`） |
| 步驟徽章 | span | `current_step` | 依 `STEP_LABELS` 映射（`projects.js:7-19`）：內部 11 步收斂為 8 步顯示，`layout_2d`/`white_model_3d`/`realistic_3d` 都顯示「6 家具配置」；未知值原樣顯示 |
| 更新時間 | text | `updated_at` | `toLocaleString("zh-TW")` 年月日時分；無法解析時原樣顯示 |
| 備註 | text | `notes` | 有值才渲染 |
| 建立表單：專案名稱 `#project-name` | text，required，maxlength 120 | `POST /api/projects` `name` | placeholder「例如：大安區三房兩廳」 |
| 建立表單：備註 `#project-notes` | textarea，maxlength 2000 | `notes` | placeholder「屋主需求、預算範圍、時程限制…」 |
| 改密碼：目前／新密碼 | password；新密碼 minlength 8 | `POST /api/auth/password` | 收在 `<details>` 內，預設收合 |

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 建立新專案 | `#new-project` → 表單展開 → submit | `POST /api/projects` 成功即整頁導向 `/scene?project_id=`（`projects.js:211-221`） | designer／admin（client 隱藏入口） |
| 繼續設計 | 卡片連結／按鈕 | 導向 `/scene?project_id=` | 所有可見成員 |
| 分享給屋主 | 卡片「分享給屋主」→ `window.prompt` 輸入 email | `POST /api/projects/{id}/members`（`project_role: "viewer"` 固定）→ `window.alert` 顯示成員數（`projects.js:135-155`） | 僅 `project_role === "owner"` 顯示按鈕 |
| 登出 | topnav `#sign-out` | 清 localStorage session ＋ `POST /api/auth/logout` → `/login`（`projects.js:228-231`） | 已登入 |
| 修改密碼 | `#change-password-form` submit | 成功後主動 `logout()` 導向 `/login?changed=1`——改密碼撤銷所有 refresh token，要求重登以確認新密碼可用（`projects.js:250-253` 註解） | 已登入 |

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案（程式碼實值） |
| :--- | :--- | :--- |
| Loading | 身分列與列表 | 「載入中…」（`projects.html:27,85`；無 skeleton） |
| Empty（designer） | `.projects-empty`＋內嵌「建立第一個專案」按鈕 | 「還沒有專案。點右上角『建立新專案』開始第一個設計。」 |
| Empty（client） | `.projects-empty`，無建立按鈕 | 「還沒有設計師把專案分享給你。」（`projects.js:170-183`） |
| Error | `#projects-error`（role=alert） | 伺服器 `detail` 或 `HTTP {status}`；載入失敗 fallback「無法載入專案列表。」 |
| Permission Denied | client 角色：`#new-project` hidden（`projects.js:79`）；非成員專案不出現在列表（伺服器端過濾） | — |
| Success（分享） | `window.alert` | 「已分享。目前成員 {N} 人。」 |
| 建立中 | `#create-submit` disabled | 「建立中…」，結束後還原「建立並開始」 |

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| `#create-submit` | site.css | 送出期間 disabled（finally 還原，`projects.js:208-224`） | 「建立中…」 | `#projects-error` 顯示 `readError()` 結果 |
| 建立表單開闔 | — | — | — | 「取消」收合表單、還原「建立新專案」鈕並清錯誤 |
| 分享 prompt | — | — | — | prompt 取消（空值）即中止；API 失敗寫 `#projects-error` |
| 改密碼 submit | — | 無 disabled 防重複（原始碼無此處理） | — | `#change-password-error` 顯示；fallback「密碼更新失敗。」 |
| 所有 `/api/*` 請求 | — | — | — | `auth_client.js` 攔截器附 Bearer；401 自動 refresh 一次，失敗轉登入頁 |

## 7. 驗證規則 (Validation)

| 欄位 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| 專案名稱 | trim 後非空（另有 HTML required、maxlength 120） | 「請輸入專案名稱。」 | submit |
| 分享 email | 前端只 trim，不驗格式；對方須已註冊 | 伺服器 `detail` 原文 | API 回應後 |
| 新密碼 | HTML minlength 8（無 JS 前置驗證） | 伺服器 `detail.message` 或「密碼更新失敗。」 | submit（原生驗證）＋ API |

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** 依 `site.css` 逐案 `@media`；無統一斷點系統（沿用 2026-07-26 版結論）。
- **鍵盤操作:** 原生 form／details 行為；未系統性驗證（未查證）。
- **ARIA:** 列表 `aria-live="polite"`；兩個錯誤列 `role="alert"`；topnav `aria-label="主要導覽"`。分享流程用 `window.prompt`/`alert` 原生對話框——樣式不可控但鍵盤可及。對比未驗證（未查證）。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | **無**（repo 內 `rg -i figma` 零命中，2026-08-07 實測） |
| Design Tokens | 無；樣式為手寫 `site.css`（`.projects-*`、`.project-card` class 群） |
| 元件對照 | 無元件庫；卡片由 `projects.js` `projectCard()` 以 DOM API 組裝 |
| 已知限制 | 分享 UI 只能加 viewer（editor 需走 API）；無移除成員、無成員列表 UI；改密碼鈕無防重複點擊 |

## 10. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應需求 | FR-PROJ-*（列表／建立／分享／角色）、FR-AUTH-*（登出／改密碼）——編號以本輪 `../01_requirements/srs.md` 為準（撰寫中，待對齊） |
| 對應情境 | SCN-PROJ-*（同上，待對齊） |
| 上游文件 | `information_architecture.md`（頁面清單與路由，同輪產出）；角色與分享語意權威描述見 `README.md` §帳戶端 |
| 對應元件規格 | 無獨立元件規格；步驟徽章的步驟語意以 `ui_spec-scene.md` §2 的 8/11 步對映為準 |
