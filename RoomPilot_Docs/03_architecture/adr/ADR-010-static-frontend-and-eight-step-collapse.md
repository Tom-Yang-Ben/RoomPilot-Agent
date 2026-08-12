# ADR-010: 靜態單頁前端即正式產品，11 步內部狀態折疊為 8 步 (Static SPA as Production Frontend; 11-Step State Collapsed to 8) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-WEB owner（Bella，`docs/TEAM_AI_OWNERSHIP.md:22`）；退役與遷移屬產品 owner，於 [`requirements_tracker.xlsx`](../../01_requirements/requirements_tracker.xlsx) ③Gate 簽核
> **語域:** L2（橋接）——業務詞（「八步」）與工程詞（`WORKFLOW_STEPS` key）並列
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
>
> **本文件回答**：為什麼正式前端是 FastAPI 直接服務的原生 JS ＋ Three.js 單頁、而不是框架 SPA；以及為什麼內部 11 個 workflow step key 對外只顯示 8 顆導覽按鈕。
> **本文件不含**：折疊後每一步的 DOM／panel／stage 對照（去 [`information_architecture.md`](../../02_ux_ui/information_architecture.md) §4）、單頁逐步互動規格（去 [`ui_spec-step1-project.md`](../../02_ux_ui/ui_spec-step1-project.md)–[`ui_spec-step8-ai-render.md`](../../02_ux_ui/ui_spec-step8-ai-render.md)）、快照保存與樂觀鎖（去 [`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)）、系統全貌（去 [`sad.md`](../sad.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：`GET /scene` 直接回傳 `scene.html`（帶 `Cache-Control: no-store`，`main.py:1665-1668`），該頁以 importmap 從 unpkg 取 three@0.165.0、再載入單一 ES module `scene_v2.js`（`scene.html:1209-1217`）；`/static` 由 `StaticFiles` 掛載（`main.py:216`）。整個正式前端沒有 bundler、沒有 `package.json`、沒有建置步驟——`backend/server/static/` 下無任何建置設定檔（2026-08-12 目錄列舉）。
- **同時存在第二套前端**：`frontend/` 是 React 18 ＋ @react-three/fiber ＋ Vite 原型（`frontend/package.json:5-21`），自我宣告「次要原型、非正式產品，永遠不會被 `/scene` 服務」且「只涵蓋約第 1–6 步，沒有第 7 步視角鎖定與第 8 步生圖／成果包」（`frontend/AGENTS.md:3-12`）。其 `vite build` 產物已提交在 `backend/server/static/frontend3d/`（4 個受控檔），因此 `/static/frontend3d/index.html` 對外可達。
- **問題**：六人多分支並行下，若不指定唯一正式前端，同一份 workflow 快照契約會出現兩個消費端實作，任何 payload 演進都要雙倍驗證；治理面已明文禁止「不得以 `frontend3d/` 取代正式網頁」（`AGENTS.md:58`）。
- **第二個問題（步數）**：狀態機實際是 11 個 key——後端白名單 `main.py:164-176`、前端 `scene_workflow.js:4-16` 兩邊一致；但使用者只該看到 8 步（`scene.html:22-31`，`data-workflow-count="8"`）。`calibration` 是 `recognition` 的延續、`white_model_3d`／`realistic_3d` 是 `layout_2d` 的 3D 續作，對使用者不是獨立的「一步」。
- **驅動因素／約束**：
  - 八步狀態走單一 workflow JSON 快照（[`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)），前端必須與該保存契約一對一。
  - 幾何合法性只由 `backend/engine/` 裁決（[`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)），前端只呈現不判定；框架化的收益不落在本系統最難的部分。
  - 內部三個 3D 相關 step 各有**不同的完成條件**（`scene_workflow.js:140-149`：`layout_2d` 只看 `confirmed`、`white_model_3d` 另檢查可見家具數、`realistic_3d` 只看 `confirmed`），這三道 gate 有工程價值、不能為了對外好看而併掉。

## 2. 考量的選項

### 選項一: FastAPI 直接服務 `backend/server/static/` 原生 JS 單頁；顯示層折疊 11→8（現行）

- **描述**：`PUBLIC_WORKFLOW_STEPS` 固定 8 個對外步（`scene_v2.js:311-320`），`publicWorkflowStep()` 兩條映射把 `calibration → recognition`、`white_model_3d|realistic_3d → layout_2d`（`scene_v2.js:322-326`）；導覽高亮與完成態只吃折疊後索引（`scene_v2.js:1597-1606`），文案表同步對 11 個 key 各給「步驟 N」（`scene_v2.js:297-309`）。保存與 gate 仍用完整 11 步。
- **優點**：單一部署面（同一 FastAPI 行程，不需 Node runtime）；快取正確性可硬斷言（`scene.html` 的 `?v=sha256-<前 12 碼>` 必須等於實檔雜湊，`tests/test_scene_v2_contract.py:20-28`）；三道 3D gate 完整保留。
- **缺點**：`scene_v2.js` 已 19,583 行單檔、無元件化與型別，回歸只能靠契約測試＋人工瀏覽器 QA（`AGENTS.md:67`）；折疊規則是隱式約定，只寫在 JS 常數裡（OPEN-04）。
- **成本／複雜度**：低。

### 選項二: 把 `frontend/` React/R3F 原型升級為正式前端（**已放棄**）

- **描述**：以 Vite 建置產物取代 `scene.html`，由 FastAPI 靜態掛載服務；原型建置驗證已存在（`npm ci` ＋ `npm run build`，`frontend/AGENTS.md:25`；安裝腳本已裝其相依，`install.ps1:68-74`）。
- **為何不選**：原型元件只到第 6 步——`frontend/src/components/` 僅有 `FloorplanReview`／`RequirementsQuestionnaire`／`Layout2DReview`／`Furniture`／`Scene`，**沒有任何 proposal_review 或 ai_render 元件**（2026-08-12 `git ls-files frontend/src`），第 7–8 步（視角鎖定、逐房生圖、成果包）須從零重寫；其 AGENTS 自身禁止實作競爭的 workflow／persistence 層，遷移須有明確計畫並經 Bella 核准（`frontend/AGENTS.md:20-23`）。Pilot 階段把整合驗證集中在一套前端的價值高於元件化收益。
- **成本／複雜度**：高（重寫第 7–8 步＋雙前端過渡期）。

### 選項三: 對外導覽也攤成 11 步，不做折疊（**已放棄**）

- **描述**：導覽列直接列出 `WORKFLOW_STEPS` 的 11 個 key，前後端與 UI 三處編號完全一致。
- **為何不選**：`calibration` 與 `white_model_3d`／`realistic_3d` 對使用者不是可獨立決策的階段——`calibration` 是「確認尺度後才顯示房間」的續頁、`realistic_3d` 是同一個 3D 工作台的側欄 tab 切換（`scene_v2.js:301,305-306`）；攤成 11 步會把「步驟總數」從產品承諾（DEC-001 的八步路徑）變成實作細節的洩漏。**代價**：使用者看到的「第 6 步」實際要跨三道 gate 才能進第 7 步。
- **成本／複雜度**：低（但產品面不可接受）。

### 選項四: 後端 `WORKFLOW_STEPS` 直接縮成 8 個 key，在資料層折疊（**已放棄**）

- **描述**：把折疊做在持久化與 gate 層，讓 11 步從此消失，前端不需要映射函式。
- **為何不選**：會一次弄丟三件事——`white_model_3d` 的「可見家具數 > 0」完成條件（`scene_workflow.js:141-148`）、`REQUIRED_COMPLETIONS` 對三個 3D step 的分層前置（`scene_workflow.js:55-92`）、以及 `markDownstreamStale()` 以 11 步順序判定下游作廢的粒度（`scene_workflow.js:175-187`）。折疊在顯示層是可逆的；折疊在資料層不可逆，且會讓既有專案的 `workflow_json` 需要遷移。
- **成本／複雜度**：中（改動小，但破壞既有快照與 gate 語意）。

## 3. 決策

**選擇**：選項一。正式前端唯一是 `backend/server/static/` 的原生 JS ＋ Three.js 單頁；`frontend/` React/R3F 專案維持次要原型定位。折疊**只做在顯示層**（`PUBLIC_WORKFLOW_STEPS` ＋ `publicWorkflowStep()`），持久化、前進條件與下游作廢一律沿用內部 11 步 key。

**理由**：第 5–8 步的權威實作只有 `scene_v2.js` 一份（`frontend/AGENTS.md:10`），原型缺後半段；顯示層折疊以兩行映射換到「使用者看八步、工程保留十一道 gate」，是四個選項裡唯一同時滿足 DEC-001（單一交付路徑）與 `scene_workflow.js` 既有 gate 粒度的做法。前端資產一致性由雜湊快取鍵與契約測試守住（NFR-021、`tests/test_scene_v2_contract.py:20-28`），而非靠建置工具鏈。

## 4. 後果

**得到什麼**

- 部署面只有一個 FastAPI 行程，正式流程不需要 Node 執行環境（`README.md:343` 明示只有開發原型時才需另開 frontend server）。
- workflow 快照契約只有一個消費端；API payload 演進的驗證成本不翻倍。
- 資產快取正確性可自動化驗證：`scene_v2.js` 與 `site.css` 的 `?v=sha256-<前 12 碼>` 與實檔雜湊不符即測試紅燈（`tests/test_scene_v2_contract.py:20-28`）。
- 3D 資源可用頁面級 LRU 直接治理，不受框架生命週期干擾（GLB 快取上限 48，`scene_viewer.js:49-50,66-85`）。

**付出什麼**

- `scene_v2.js` 19,583 行、`scene.html` 1,219 行單檔成長，無型別與元件邊界；回歸只能靠契約測試與人工瀏覽器 QA（`AGENTS.md:67`）。
- 折疊規則是隱式契約：只存在於 `scene_v2.js:311-326` 的兩個常數，後端與 `scene_workflow.js` 都不知道它存在；**欄位 owner 與變更程序尚未拍板（OPEN-04）**。
- 步號三套並存（對外 8 步、內部 11 key、舊契約十步的殘留錯誤訊息），統一方案未定（OPEN-09）。
- 第二個可達前端入口：原型 build 產物已提交於 `backend/server/static/frontend3d/`，經 `/static` 掛載對外可達（`main.py:216`），是否退役未決。
- 死頁面殘留：`#realistic-3d-step` 永不被 `showStep()` 選中、`scene.js`（3,128 行）已無生產載入路徑，去留未決（OPEN-50）。
- 對外資產依賴公網 CDN（unpkg，`scene.html:1212-1213`），離網或內網部署會直接白畫面。

**什麼時候該重評這個決策**（觸發條件皆可觀測）

| # | 觸發條件 | 可觀測訊號 |
| :--- | :--- | :--- |
| T1 | 原型補齊第 7–8 步 | `frontend/src/components/` 出現 proposal_review／ai_render 對應元件，且端對端（含三房手測）驗收通過（`frontend/AGENTS.md:11-12`） |
| T2 | 折疊規則升格為正式契約 | owner 對 OPEN-04 拍板；此時本 ADR 須補「欄位 owner ＋ 變更程序」，且映射需有專屬測試 |
| T3 | 折疊規則變複雜 | `publicWorkflowStep()` 的映射條件從 2 條增至 3 條以上，或內部 step key 數不再是 11（`main.py:164-176` 與 `scene_workflow.js:4-16` 任一方變動） |
| T4 | 單檔維護成本失控 | `scene_v2.js` 契約測試無法攔到的前端回歸，在一個 Pilot 週期內出現 2 次以上；或該檔超過既有規模仍無模組切分 |
| T5 | 部署環境離網 | 需在無公網環境部署 → unpkg importmap 失效，須改本地供應 three.js（同時觸發快取鍵斷言更新） |
| T6 | 明確核准遷移 | 依 `AGENTS.md:58` 提出遷移計畫並取得 MOD-WEB owner 核准 |

## 5. 執行計畫

1. 維持不變量：任何 `scene_v2.js`／`site.css` 變更後必須同步更新 `scene.html` 的 `?v=sha256-` 前 12 碼，否則 `tests/test_scene_v2_contract.py:20-28` 紅燈（此為現行硬閘，非新增要求）。
2. 新增或改名內部 step key 時，同批檢查三處：`main.py:164-176` 白名單、`scene_workflow.js:4-16,43-105` gate 表、`scene_v2.js:297-326` 折疊與文案表；缺一即產生對外步數與內部狀態不一致。
3. 待 owner 就 OPEN-04／OPEN-09／OPEN-50 拍板後回填本 ADR §4 與 [`information_architecture.md`](../../02_ux_ui/information_architecture.md) §4；在拍板前，折疊規則一律記為 AS-IS 現況，不得在下游文件寫成已核准契約。
4. **待確認（無既有 OPEN 編號）**：治理文件與磁碟現況不符——`AGENTS.md:43,58`、`README.md:248,265-266,343-348`、`docs/TEAM_AI_OWNERSHIP.md:31` 皆指涉 `frontend3d/`，但本分支 HEAD 無此目錄（`git ls-files frontend3d` 為空），原型實際位於 `frontend/`，`frontend3d/` 只剩 build 產物路徑；`README.md:346` 的 `Set-Location frontend3d` 已無法執行。是否統一改名、以及提交 build 產物是否為預期，須由 owner 決定後同批修訂。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | （待 owner 核准） | 現況追認；本 ADR 未經人工核准前，§3 決策視為 AS-IS 記錄 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 上游業務決策 | DEC-001（單一八步交付路徑）、DEC-018（結構變更作廢下游）——見 [`brd.md`](../../01_requirements/brd.md) §7、[`prd.md`](../../01_requirements/prd.md) §3 |
| 上游需求 | FR-020（11→8 折疊）、FR-021（前進條件與下游作廢）、FR-024（`loadScene` 唯一場景入口）、FR-025（生圖／色卡疊層）、NFR-021（GLB LRU 48、雜湊快取鍵）——見 [`srs.md`](../../01_requirements/srs.md) §2.3、§3 |
| 驗收 | ACPT-018、ACPT-019、ACPT-020、ACPT-021、ACPT-022、ACPT-023（[`srs.md`](../../01_requirements/srs.md) §7 SX 跨步） |
| 影響範圍 | MOD-WEB（Bella，`backend/server/static/`）、MOD-SRV-API（`main.py` 的 `WORKFLOW_STEPS` 白名單與 `/static` 掛載） |
| 相鄰決策 | [`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)（快照與樂觀鎖）、[`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)（前端不裁決幾何）、[`ADR-009`](./ADR-009-server-governed-ai-generation.md)（生圖由伺服器治理）、[`ADR-011`](./ADR-011-agent-pipeline-flag-isolation.md)（旁路管線不改前端路徑） |
| 下游文件 | [`sad.md`](../sad.md)、[`information_architecture.md`](../../02_ux_ui/information_architecture.md) §4–§5、[`ui_spec-step6-layout-2d.md`](../../02_ux_ui/ui_spec-step6-layout-2d.md)、[`ui_spec-step7-proposal-review.md`](../../02_ux_ui/ui_spec-step7-proposal-review.md)、[`ui_spec-step8-ai-render.md`](../../02_ux_ui/ui_spec-step8-ai-render.md)、[`test_plan.md`](../../05_qa/test_plan.md)、[`deployment_and_operations.md`](../../06_ops/deployment_and_operations.md) |
| 待確認 | OPEN-04（折疊規則是否為正式契約、owner 是誰）、OPEN-09（步號三套並存）、OPEN-50（`#realistic-3d-step` 與 `scene.js` 是否退役）、OPEN-03（無生產前端呼叫的端點是否退役）；另見 §5.4 的 `frontend3d/` 命名不符 |
| 取代關係 | 無（本批 ID 體系與歷史文件同名編號不保證同義，見 [`prd.md`](../../01_requirements/prd.md) OPEN-48） |
