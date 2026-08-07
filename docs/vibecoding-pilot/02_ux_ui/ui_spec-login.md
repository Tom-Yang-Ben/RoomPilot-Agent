# UI 規格書 (UI Spec) - 登入／註冊（/login）

> **版本:** v1.0 | **更新:** 2026-08-07 | **狀態:** 草稿
> **Owner:** Bella（`frontend/` 目錄 owner，見 `AGENTS.md` 目錄責任表）
> **回答的問題:** `/login` 頁有哪些區塊、欄位、狀態、操作與文案？前端不用猜。
> **語域:** L3（工程）
> **實例:** 每頁面一份（`ui_spec-<page>.md`）；本份為登入／註冊頁
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

讓使用者登入既有帳號或註冊新帳號（設計師／屋主二擇一），成功後導向 `?next=` 指定頁或預設 `/projects`。旅程對應 `ux_research_and_journey.md` §5（同輪產出）。

| 導航 | 頁面 |
| :--- | :--- |
| 入口 | 受保護頁（`/projects`、`/scene`）未登入時的 `redirectToLogin()` 轉址（帶 `?next=原路徑`，`auth_client.js:147-152`）；改密碼後的 `/login?changed=1`（`projects.js:253`） |
| 出口 | 成功後 → `?next=` 或 `/projects`；topnav 可去 `/`（探索功能）、`/styles`、`/library` |

檔案組成：`login.html`（111 行）＋ `login.js`（88 行）＋ `auth_client.js`（241 行，token 保管與 fetch 攔截器）。頁面本身公開，授權由 API 端點負責（`backend/server/main.py:952-958` 註解）。

## 2. 版面配置 (Layout)

```text
topbar：logo ｜ topnav（探索功能 / 風格類型 / 家具資料庫）
auth-shell
└── auth-card
    ├── H1「登入 RoomPilot」＋導語
    ├── auth-tabs（登入 ｜ 註冊，role=tablist）
    └── form#auth-form
        ├── 顯示名稱（僅註冊模式顯示，.auth-register-only）
        ├── Email ／ 密碼
        ├── 身分 radio（僅註冊模式）
        ├── #auth-error（role=alert）
        └── submit（登入 ／ 建立帳號）
```

登入／註冊共用同一表單，模式由 `body.is-registering` class 切換註冊限定欄位的顯示（`login.js:31-43`）。

## 3. 欄位與元件 (Fields / Components)

| 欄位 | 型態 | 來源（API 欄位） | 顯示規則 |
| :--- | :--- | :--- | :--- |
| 顯示名稱 `#display-name` | text，maxlength 100 | `display_name`（register） | 僅註冊模式；留空時以 email `@` 前段代入（`login.js:70`） |
| Email `#email` | email，required | `email` | autocomplete=email |
| 密碼 `#password` | password，required，minlength 8 | `password` | autocomplete 隨模式切 `current-password`／`new-password` |
| 身分 `role` | radio：`designer`（預設）／`client` | `role`（register） | 文案：「設計師 — 建立專案、鎖定版本、產生成果報告」／「屋主 — 檢視被分享的專案與報告」 |
| 錯誤列 `#auth-error` | p，role=alert | — | 預設 hidden，有錯誤才顯示 |

## 4. 使用者操作 (Actions)

| 操作 | 觸發 | 結果 | 權限 |
| :--- | :--- | :--- | :--- |
| 切換登入／註冊 | tab click | 切模式、清錯誤、submit 文案改「登入」／「建立帳號」 | 公開 |
| 登入 | submit（login 模式） | `POST /api/auth/login` → 存 session（localStorage）→ 導向 `safeNextTarget()` | 公開 |
| 註冊 | submit（register 模式） | `POST /api/auth/register`（含 display_name、role）→ 同上 | 公開 |
| 已登入直接進入 | 頁面載入時 `isSignedIn()` | `location.replace(safeNextTarget())`，不顯示表單內容（`login.js:84-85`） | — |

Session 儲存：`roompilot.access_token`／`roompilot.refresh_token`／`roompilot.user` 三鍵存 localStorage（`auth_client.js:13-15`）；XSS 外洩風險為已知取捨，以短效 access（預設 30 分鐘）＋ refresh 輪替縮小窗口（`auth_client.js:7-10` 註解）。

## 5. UI 狀態 (States)

| 狀態 | 呈現 | 文案 |
| :--- | :--- | :--- |
| 預設 | login 模式，註冊限定欄位隱藏 | submit＝「登入」 |
| 送出中 | submit disabled | 「登入中…」／「建立中…」（`login.js:63-64`） |
| 錯誤 | `#auth-error` 顯示，submit 恢復可按 | 伺服器 `detail` 訊息；fallback「登入失敗，請稍後再試。」 |
| 已登入 | 立即轉址（無畫面停留） | — |
| Empty／Loading skeleton | 不適用（無列表資料） | — |

## 6. 互動規格 (Interaction Spec)

| 元素 | Hover | Disabled | Loading | 錯誤反應 |
| :--- | :--- | :--- | :--- | :--- |
| submit `#auth-submit` | site.css 樣式 | 送出期間 disabled 防重複（`login.js:63`） | 文案切「…中…」 | 失敗後還原文案並 re-enable |
| `?next=` 轉址 | — | — | — | 只接受同源相對路徑：非 `/` 開頭或 `//` 開頭一律回退 `/projects`，防開放轉址（`login.js:13-19`） |
| 401 續期（登入後全站） | — | — | 多請求同時 401 只跑一次 refresh，其餘等同一 promise（`auth_client.js:117-145`） | refresh 失敗清 session 轉 `/login?next=` |

## 7. 驗證規則 (Validation)

表單掛 `novalidate`，驗證在 JS submit handler：

| 欄位 | 規則 | 錯誤訊息 | 觸發時機 |
| :--- | :--- | :--- | :--- |
| email＋password | 皆非空 | 「請填寫 email 與密碼。」 | submit |
| password（註冊） | 長度 ≥ 8 | 「密碼至少需要 8 個字元。」 | submit |
| 伺服器端驗證 | email 格式／重複註冊／帳密錯誤等 | 回傳 `detail` 原文顯示 | submit 後 |

## 8. 響應式與無障礙 (Responsive / A11y)

- **斷點行為:** 依 `site.css` 逐案 `@media`；無統一斷點系統（沿用 2026-07-26 版結論）。
- **鍵盤操作:** 原生 form submit（Enter 可送出）；tab 鍵順序依 DOM。未系統性驗證（未查證）。
- **ARIA:** tabs 有 `role=tablist/tab`＋`aria-selected`＋`aria-controls`；錯誤列 `role=alert`；`lang="zh-Hant"`。對比未驗證（未查證）。

## 9. 設計交付 (Design Handoff)

| 項目 | 連結／位置 |
| :--- | :--- |
| Figma | **無**（repo 內 `rg -i figma` 零命中，2026-08-07 實測） |
| Design Tokens | 無；樣式為手寫 `site.css`（`.auth-*` class 群） |
| 元件對照 | 無元件庫 |
| 已知限制 | 無「忘記密碼」UI——重設走 admin API 口頭告知流程（`README.md:107-109`），頁面上無入口與說明 |

## 10. 追溯

| 項目 | ID |
| :--- | :--- |
| 對應需求 | FR-AUTH-*（註冊／登入／登出／token 續期／角色）——編號以本輪 `../01_requirements/srs.md` 為準（撰寫中，待對齊） |
| 對應情境 | SCN-AUTH-*（同上，待對齊） |
| 上游文件 | `information_architecture.md`（頁面清單與路由，同輪產出）；帳戶行為權威描述見 `README.md` §帳戶端 |
| 對應元件規格 | 無獨立元件庫；`auth_client.js` 為全站身分附掛的共用層（`/scene`、`/projects`、`/engineering`、`/rag` 皆 import） |
