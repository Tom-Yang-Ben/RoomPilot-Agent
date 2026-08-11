# ADR-006: 正式前端是 backend/server/static 單頁八步精靈；frontend3d/ 與 frontend/ 為次要原型

> **狀態:** 已接受（AI 衍生，待人工核准）| **日期:** 2026-08-11 | **決策者:** Bella（`backend/server/` 與 `backend/server/static/` owner，docs/TEAM_AI_OWNERSHIP.md:21-22；AI 衍生，人工核准前為 TO-BE）
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **定位宣告:** 本文件回答「為什麼正式前端是 FastAPI 直接服務的香草 JS/Three.js 單頁精靈，而不是 React/R3F SPA」；不包含頁面互動細節（見 [../../02_ux_ui/ui_spec-scene.md](../../02_ux_ui/ui_spec-scene.md)）與系統全貌（見 [../sad.md](../sad.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

本 ADR 是**既成決策的補記**：決策已在程式碼與治理文件中成立，此處重建其脈絡。

- **上下文**: repo 內同時存在兩套前端——(a) `backend/server/static/` 的香草 HTML/CSS/JS + Three.js，由 FastAPI `GET /scene` 直接回傳 `scene.html`（單頁八步精靈，`data-workflow-count="8"`，scene.html:22）；(b) React/R3F 原型（歷史名 `frontend3d/`，2026-07 技術分層重組後磁碟目錄為 `frontend/`，Vite build 產物落在 `backend/server/static/frontend3d/`，frontend/AGENTS.md:5-8）。
- **問題**: 六人團隊各自分支並行，若沒有唯一正式前端，工作流狀態、保存契約與第 5–8 步實作會出現互相打臉的複本；原型僅涵蓋約第 1–6 步，沒有第 7 步視角鎖定與第 8 步生圖／成果包（frontend/AGENTS.md:9-10）。
- **驅動因素/約束**:
  - 八步狀態走單一 workflow JSON 快照＋revision 樂觀鎖（ADR-007），前端必須與這套保存契約一對一。
  - 幾何合法性只由 `backend/engine/` 判定（NFR-004），前端只呈現不裁決；兩套前端＝兩套 adapter 維護成本。
  - 治理鐵律：「正式網頁在 `backend/server/static/`；不得以 `frontend3d/` 取代，除非已明確核准遷移」（AGENTS.md:58）。

## 2. 考量的選項

### 選項一: FastAPI 直接服務 `backend/server/static/` 香草 JS/Three.js 單頁精靈（現行）
- **描述**: `GET /scene` 回傳 `scene.html`，載入 `scene_v2.js`（香草 JS + Three.js），八步導覽列在同一頁切換（scene.html:22-30）；不需要另開 frontend dev server（README.md:343）。
- **優點**: 單一部署面（同一個 FastAPI 行程）；第 5–8 步權威實作只有 `scene_v2.js` 一份（frontend/AGENTS.md:10）；API payload 契約由 Bella 一手驗證（docs/TEAM_AI_OWNERSHIP.md:22）。
- **缺點**: 香草 JS 大檔（`scene_v2.js`）缺乏元件化與型別，回歸靠契約測試與人工瀏覽器 QA（AGENTS.md:67）。
- **成本/複雜度**: 低（無 build pipeline、無第二套狀態管理）。

### 選項二: 以 React/R3F SPA（`frontend/`，Vite）為正式前端
- **描述**: 把現有原型升級為正式產品，`vite build` 產物由 FastAPI 靜態掛載服務。
- **優點**: 元件化、宣告式 3D（R3F）、npm 生態與 `npm ci && npm run build` 可重現建置（frontend/AGENTS.md:25）。
- **缺點**: 只涵蓋約第 1–6 步，第 7–8 步須重寫（frontend/AGENTS.md:9-10）；會複製工作流與保存層，違反「不得實作競爭的 workflow/persistence」（frontend/AGENTS.md:20）；遷移需明確計畫與 Bella 核准（frontend/AGENTS.md:23）。
- **成本/複雜度**: 高（重寫第 5–8 步＋雙前端過渡期）。

### 選項三（推測）: 兩套前端並列為正式產品
- **描述**: 香草版與 React 版同時對外，各服務不同使用情境。
- **優點**: 各分支成果都能上線。
- **缺點**: 同一 workflow JSON 契約兩份消費端實作，任何 payload 演進都要雙倍驗證；與專案禁令「新建第二套 FastAPI 或正式前端」直接衝突（CLAUDE.md 禁止清單）。
- **成本/複雜度**: 高。此選項未見於文件明文討論，屬本補記推測的對照組。

## 3. 決策

**選擇**: 選項一。正式前端唯一是 `backend/server/static/` 的單頁八步精靈；React/R3F 原型（文件慣稱 `frontend3d/`、磁碟目錄 `frontend/`）為次要原型，不是正式流程（AGENTS.md:43、README.md:265-266）。

**理由**: 第 5–8 步（問卷、配置、視角鎖定、生圖／成果包）的權威實作已完整存在於 `scene_v2.js`，而原型缺後半段；在 Pilot 階段，把整合驗證集中於一套前端（Bella 的整合門檻，docs/TEAM_AI_OWNERSHIP.md:9）比元件化收益更關鍵。原型保留為契約消費端的第二視角（share contracts, not copied business logic，frontend/AGENTS.md:21），遷移路徑保留但需明確核准（AGENTS.md:58）。

## 4. 後果

- **正面**: 八步工作流、保存契約（ADR-007）與 API adapter 只有一份消費端；`/scene` 不需 Node 執行環境即可上線（README.md:343）。
- **負面**: `scene_v2.js` 持續長大，無框架約束；原型與正式版功能漂移（原型止於第 6 步），跨前端的「假動線」曾被記錄為 UX 缺陷風險。
- **影響範圍**: `backend/server/static/`（Bella＋Yen/Ancai/Cody/Django 協作，docs/TEAM_AI_OWNERSHIP.md:22）；`frontend/` 原型任何改動不得實作競爭 workflow；靜態前端變更的最低驗證為 JS 語法＋契約測試＋實際瀏覽器 QA（AGENTS.md:67）。
- **重新評估觸發**:
  - 原型補齊第 7–8 步且通過端對端（含三房手測）驗收（frontend/AGENTS.md:11-12 引用之驗收條件）。
  - 提出正式遷移計畫並獲 Bella 明確核准（frontend/AGENTS.md:23、AGENTS.md:58）。
  - `scene_v2.js` 維護成本高到契約測試與瀏覽器 QA 無法守住回歸（ACPT-016 基線持續惡化）。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-11 | （待人工審核） | AI 補記，尚未經 owner 核准 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | REQ-007、REQ-008、REQ-009、REQ-011（八步 UI 全鏈由單一前端承載）；NFR-002（前端消費 workflow 快照契約）；NFR-004（前端不裁決幾何） |
| 影響範圍 | FR-008、FR-009、FR-011（`scene_v2.js`／`scene.html` 為唯一實作面）；[api_spec](../../04_design/api_spec.md)；[ui_spec-scene](../../02_ux_ui/ui_spec-scene.md)；相鄰決策 [ADR-007](./ADR-007-workflow-json-single-snapshot-store.md) |
| 取代關係 | 無 |
