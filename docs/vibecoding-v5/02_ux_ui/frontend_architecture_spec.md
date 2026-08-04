# 前端架構規範 - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 02_ux_ui/frontend_architecture_spec.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0（v5.0 模板重導入，取代舊 `docs/vibecoding/12_frontend_architecture_specification.md`，該版事實基準為 2026-07-26 舊分支，數字已過期） | **更新:** 2026-08-04 | **狀態:** 已發布（依現行工作樹逐條實查）
> **相關文檔:** [前端資訊架構](./frontend_information_architecture.md)（同資料夾 v5 導入版；若尚未導入，先行素材見 `docs/vibecoding/17_frontend_information_architecture_template.md`）
>
> **MECE 邊界**：本文件**只談技術視角**（stack / 分層 / 量化指標 / 工程化）。
> 使用者視角（頁面職責、旅程、導航、路由內容）全部在 **frontend_information_architecture**。
>
> | 你想找的 | 看這份 |
> |---|---|
> | 兩套前端是什麼、關係如何 | 本檔 §0 |
> | 用什麼框架、怎麼分層 | 本檔 §2 |
> | 設計令牌、樣式資料的雙來源 | 本檔 §3 |
> | 效能與快取現況（sha256 快取參數、no-store） | 本檔 §4 |
> | 響應式、a11y 現況 | 本檔 §5 |
> | 檔案組織、前端測試現況 | 本檔 §6 |
> | API 呼叫點、樂觀鎖、pending save | 本檔 §7 |
> | 哪些**頁面**存在、頁面職責、旅程、路由表 | frontend_information_architecture |
> | 全站 63 條 API 端點規格 | `docs/vibecoding-v5/04_design/api_design.md`（若尚未導入，見 `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md`） |

---

## 第 0 部分: 現況總覽——兩套前端並存（先讀這節）

| | A. `backend/server/static/`（**現行主要 UI**） | B. `frontend3d/`（次要原型） |
| :--- | :--- | :--- |
| 型態 | 無建置步驟的靜態頁，由 FastAPI 直接供檔 | Vite + React 18 + React Three Fiber 獨立子專案 |
| 規模 | 6 個 HTML + 頂層 42 支 JS（其中 `scene_*.js` 33 支）+ `site.css` 15,407 行 + `vendor/` 24 檔（自帶 three.js + draco）；static 全目錄共 1,031 檔（多為圖片資產） | `src/` 6 檔共 960 行（App.jsx 209、Furniture.jsx 304、Scene.jsx 236、snap.js 137、main.jsx 6、styles.css 68） |
| 入口 | `GET /`、`/styles`、`/library`、`/scene`、`/engineering`（main.py:1883-1902、2565-2570）、`/rag`（rag_api.py:136-138） | `npm run dev` 起 Vite dev server，`/api` 代理到 `http://localhost:8002`（vite.config.js:8） |
| 職責 | 八步主工作流（scene）、行銷首頁（index）、風格色卡（styles）、家具庫（library）、家具 RAG 測試台（rag）、工程估算與文件生成（engineering） | DXF 上傳→3D 白模檢視、GLB 家具手動擺放試驗 |
| 定位依據 | 專案 CLAUDE.md：「正式產品是 `backend/server/` 與 `backend/server/static/` 的八步 FastAPI/Three.js 工作流」 | `frontend3d/AGENTS.md`：secondary prototype（Owner: Bella、協作 Ancai），驗證門檻 `npm ci && npm run build` |

相較舊導入版（2026-07-26，4 頁 HTML 年代）的重大變化，本版已全部實查更新：

1. **新增 2 頁**：`/rag`（rag.html 130 行 + rag.js 367 行 + rag.css 571 行，掛在 `backend/server/rag_api.py`，背後是 `backend/spatial_data/rag/` 家具 RAG runtime）與 `/engineering`（engineering.html 113 行 + engineering.js 465 行，背後是 `backend/server/engineering/` 工程文件 MVP，契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`）。
2. **three.js 已 vendor 進 repo**：scene.html:1061-1062 與 library.html:164-165 的 importmap 均指向 `/static/vendor/three/`（three.module.js 內 `REVISION = '165'`，vendor/three/build/three.module.js:6）；全 static 目錄 grep `src="https`/`href="https`/`@import url` **零命中**——舊版的 unpkg CDN 供應鏈風險與 SRI 待辦已因自帶而消滅。
3. **前端 JS 自動化測試從零到有**：`tests/static/` 3 支 `.test.mjs`（node --test + jsdom，見 §6）。
4. **樂觀鎖已接線**：scene_v2.js 現以 `expected_revision` 送出平面圖保存（§7.2），舊版「前端未使用該機制」的記述已失效。
5. UI 步驟列從 10 顆按鈕改為 **8 顆**（內部狀態機仍 11 步，§2.1）。

---

## 第 1 部分: 架構目標（量化）

模板要求的量化指標（LCP/INP/CLS/TTI、a11y 通過率、覆蓋率、錯誤率）**本專案均未建立量測**——無 web-vitals 收集、無監控程式碼（§8）。以下為程式碼實際成立的架構目標：

| 維度 | 現況目標 | 依據 |
| :--- | :--- | :--- |
| 正確性優先於快取 | `/scene`、`/engineering`、`/rag` 回應帶 `Cache-Control: no-store`（main.py:1898-1902、2565-2570；rag_api.py:136-138）；JS/CSS 以內容雜湊查詢參數 `?v=sha256-…` 載入並有 pytest 守約（§4） | 程式碼 + tests/test_scene_v2_contract.py |
| 3D 即時互動 | scene_viewer.js（5,555 行）以 vendored three r165 做白模/寫實預覽；frontend3d 另有 X-ray 透牆 shader 與 250ms debounce 幾何重算 | 程式碼 |
| 同源免 CORS | static 頁與 API 同源；後端唯一 middleware 是 `GZipMiddleware(minimum_size=1024)`（main.py:215），**無 CORSMiddleware**（grep backend/server/*.py 僅命中 GZip）；frontend3d 靠 Vite proxy 同源化 | 實測 grep |
| 座標紀律 | 前端不得自行推算合法家具座標，一律問後端引擎；拖曳落點以 `POST /api/scene/validate` 驗證 | `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md` |

量化效能預算：**待補**（§9）。

---

## 第 2 部分: 系統化分層

### 2.1 現行主要 UI（backend/server/static/）分層

```
用戶感知層    -- 6 個 HTML（index/styles/library/scene/rag/engineering）+ site.css 15,407 行 + rag.css 571 行
互動邏輯層    -- 頂層 42 支原生 ES module JS（scene_*.js 33 支；入口 scene_v2.js 13,803 行）
狀態管理層    -- 模組內變數 + localStorage（workflow v2 契約 + 斷線 pending save）
資料通訊層    -- 原生 fetch，無封裝 client；expected_revision 樂觀鎖 + pending save 重放（§7.2）
基礎設施層    -- 無建置工具、無打包；FastAPI StaticFiles 供檔 + GZip；JS 測試用 node --test + jsdom
```

| 層級 | 技術選型（現況） | 依據 |
| :--- | :--- | :--- |
| 感知層 | 無框架 vanilla JS + 手寫 CSS；three.js **r165 自帶於 repo**，經 `<script type="importmap">` 指向 `/static/vendor/three/`（scene.html:1058-1065、library.html:161-165），無任何外部 CDN 資源 | 實測 |
| 互動層 | 原生 DOM 事件；scene.html 頂部 8 顆步驟按鈕（`data-step`，scene.html:25-32）：1 建立專案、2 上傳平面圖、3 確定尺寸、4 空間與結構、5 需求問卷、6 配置與預覽、7 方案鎖定與視角、8 AI 渲染與成果包 | 實測 |
| 狀態層 | `scene_workflow.js` 匯出 `WORKFLOW_SCHEMA_VERSION = 2`、storage key `roompilot.workflow.v2`（:1-2）；內部狀態機 **11 步**（project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render，:4-16）；calibration 與 recognition 共用 "scale" 面板、white_model_3d/realistic_3d 有面板無獨立按鈕（`WORKFLOW_PANEL_BY_STEP`，:18-30）；每步完成條件 `validCompletion()`（:159-193），上游變更把下游標 stale（`markDownstreamStale`，:207-219）；scene_v2.js 另以 localStorage 存斷線 pending save（`pendingSaveStorageKey` / `capturePendingSave` / `scheduleSave`，scene_v2.js:916-987） | 實測 |
| 通訊層 | 原生 fetch；scene_v2.js 直呼 `/api/*`（清單見 §7.2）；`common.js`（486 行）共用 `/api/site-data` 等載入與格式化工具 | 實測 grep |
| 基礎設施 | `app.mount("/static", …)` 與 `app.mount("/docs-assets", …)`（main.py:285-286）；JS 相互 import 也帶雜湊查詢參數（如 scene_v2.js:1 `./scene_viewer.js?v=sha256-ffc625d8b24f`） | 實測 |

入口 bundle 組成：scene.html:1066 載入 `engineering_link.js`（15 行，依 project_id 顯示 `/engineering` 入口）、:1067 載入 `scene_v2.js`（module）；`scene_viewer.js` 由 scene_v2.js:1 import（非 HTML 直接載入）。scene_v2.js 共 import **23 支** `scene_*` 模組（grep `from "` 去重）；`scene_delivery.js`、`scene_guidance.js`、`scene_space_change_report.js`、`scene_texture_uv.js` 4 支未被任何 html/js 引用，僅由 tests/ 以 Node 方式測試（死碼候選，照實記錄）。

伺服器端只驗步驟名不驗順序，前置依賴由前端狀態機強制。

### 2.2 frontend3d 分層

```
用戶感知層    -- React 18 JSX + styles.css（68 行，深色主題）
互動邏輯層    -- R3F pointer events + window 原生鍵盤/指標事件（Furniture.jsx）
狀態管理層    -- 純 React useState/useRef，集中 App.jsx 頂層
資料通訊層    -- 原生 fetch + drei useGLTF 載 GLB
基礎設施層    -- Vite；無測試、無 lint、無 TypeScript
```

| 項目 | 現況 | 依據 |
| :--- | :--- | :--- |
| 依賴宣告 | react/react-dom ^18.3.1、three **^0.160.1**、@react-three/fiber ^8.17.10、@react-three/drei ^9.114.0、vite ^8.1.0（dev）、@vitejs/plugin-react ^4.3.4（dev） | frontend3d/package.json |
| 安裝狀態 | `node_modules` 不存在（實測）；舊導入版曾實測 `npm install` 因 plugin-react 4.7.0 peer 不含 vite 8 而 ERESOLVE 失敗，本次未重測（未查證） | 實測 ls |
| dev 代理 | `/api` → `http://localhost:8002`（vite.config.js:8）；README 範例卻寫 port 8000（README.md:15）——文件與設定不一致，照實記錄 | 實測 |
| three 版本 | frontend3d 用 0.160.1、static UI 用 vendored r165——兩套前端 three 版本不一致，無同步機制 | 實測 |

### 2.3 3D 渲染架構摘要

- **static UI**：`scene_viewer.js`（5,555 行）為 Three.js viewer，服務第 6-8 步的白模、寫實 PBR 與渲染視角面板；`library_thumbnails.js`（187 行）產 GLB 縮圖；`viewer.js`（256 行）為 library 頁 GLB 預覽器（library.js:10 import）。vendor/ 內含 GLTFLoader/DRACOLoader/OrbitControls/EffectComposer/GTAOPass 等 postprocessing 鏈與 draco wasm。
- **frontend3d**：Scene.jsx 以 `THREE.ExtrudeGeometry` 從 `wall_polys` 擠牆 + `onBeforeCompile` 注入 X-ray 透牆 fragment shader；Furniture.jsx 管 GLB 擺放互動；snap.js 為純 2D 吸附幾何（刻意不 import three 以便 node 單測，但 repo 內無對應測試檔）。座標約定 plan(x,z)→world(x,−z)，此為 `backend/upgrade3d/dxf_parser.py` 的公尺制輸出，與主流程公分制契約不同體系，照實記錄。

---

## 第 3 部分: 設計系統

### 設計令牌（Design Tokens）

無獨立 tokens 檔／tokens 目錄，但 `site.css` 已有**單檔級 CSS 自訂屬性**：`:root` 區塊（site.css:674-693，`color-scheme: dark`）定義 `--bg`、`--panel`、`--panel-soft`、`--line`、`--line-strong`、`--text`、`--text-soft`、`--muted`、`--danger`、`--success`、`--warning`、`--radius`、`--radius-sm`、`--shadow`、`--mono`、`--sans`、`--display`；另一 `:root`（site.css:3080，`color-scheme: light`）供淺色頁面段。全檔含 `--` 變數的行共 253 行（定義+使用，grep 計）。`rag.css`（571 行）自身無 `:root` 定義，但 rag.html 先載 site.css 再載 rag.css（rag.html:8-9），因此 rag.css 實際**有消費** site.css 的字型令牌 `var(--sans)`／`var(--mono)`／`var(--display)`（共 9 行，grep `--` 實測：rag.css:71,78,90,166,263,356,387,480,537），色彩／半徑／陰影令牌則未使用——tokens 僅部分跨檔統一，照實記錄。

### 元件分層（Atomic Design）

**未建立**——無元件庫、無 Atoms→Templates 分層；static UI 以 class 前綴慣例（`rp-*`）手寫；frontend3d 以 hex 色碼硬編碼。

### 設計內容資料的雙來源（既存事實，非風險預告）

與「設計系統」最接近的資產是**設計內容資料**：6 風格 × 3 色系 = 18 張色卡存於 `backend/catalog/data/taiwan_style_cards.json`（經後端 `style_cards.py` 供 API；Phase 4 後優先走 PostgreSQL runtime catalog，`style_cards.py:6` 消費 `load_runtime_style_cards`）；`static/scene_style_packs.js` 則以同一組 card_id **另行硬編碼** palette 與 PBR/燈光參數。`docs/contracts/STYLEPACK_RENDERING_CONTRACT.md` 把兩者並列為各自職責的執行來源（色碼/材質參數以程式資料為準）。若未來建 tokens，需先裁決以哪份為準。靜態資產面另有 `static/style_cards/` 19 檔（六風格子目錄 01_北歐…06_美式）與 `moodboard_assets/` 67 檔。

---

## 第 4 部分: 效能策略（量化）

### Core Web Vitals 目標

**未建立**——無量測工具、無數字目標（待補，§9）。以下為現況實際存在的效能／快取實作：

### 載入與快取（現況）

| 手段 | 位置 | 說明 |
| :--- | :--- | :--- |
| 內容雜湊防快取 | scene.html:7,1066-1067 及各 JS 相互 import | sha256 全文雜湊取前 12 hex 放進 `?v=sha256-<hash>`；守約測試 tests/test_scene_v2_contract.py:20-28 以 `hashlib.sha256(...).hexdigest()[:12]` 驗證 |
| `Cache-Control: no-store` | main.py:1898-1902（/scene）、2565-2570（/engineering）、rag_api.py:136-138（/rag） | 工作流頁犧牲快取換部署正確性 |
| GZip 壓縮 | main.py:215 | `GZipMiddleware(minimum_size=1024)` |
| GLB 走 CDN | `GET /api/furniture/{furniture_id}/model`（main.py:3508）307 轉址 CloudFront | 模型檔不經 FastAPI 傳輸 |
| 型錄分頁 | `GET /api/furniture`（main.py:2707） | 避免 8,557 件官方雲端型錄一次載入（`OFFICIAL_CATALOG_COUNT`，backend/catalog/cloud_catalog.py:15，載入期硬驗證；來源檔 `furniture_catalog_cloud_9350.json` 頂層 count 9,350 是母檔筆數，非載入後件數） |
| RAG 非同步 job | rag.js 走 `POST /api/rag/search/jobs`（202）+ `GET .../jobs/{job_id}` 輪詢 | 檢索長請求不佔住頁面；active 上限超過回 429 |
| 自帶 three | `/static/vendor/`（24 檔＝`three/` 20 檔＋`draco/` 4 檔） | 免外部 CDN 首跳延遲與供應鏈風險 |

**快取雜湊現況（2026-08-04 實算，紅燈中）**：scene.html 引 `scene_v2.js?v=sha256-27f24b6bede3` 但實算 `7d938e1fdc28`、`site.css?v=sha256-5693fe5d95c5` 但實算 `e362900c8195`；library.html 引 `library.js?v=sha256-d3c2bcee981f` 但實算 `1c9375c972ad`——守約測試 test_scene_v2_contract 預期紅燈（本機未裝 pytest 相依，未能實跑確認，屬推算）。其餘頁面相符：engineering.js=`b5f0b28e2de2`、scene_viewer.js=`ffc625d8b24f`、rag.js/rag.css 用 64 碼全雜湊且相符。機制**未全站統一**：index/styles 仍用日期版本（`site.css?v=20260708s` 等），scene_v2.js 內部亦混用日期 token（如 `scene_style_packs.js?v=20260719-actual-palettes`，非真 sha256）；查無自動重算雜湊的腳本，雜湊為手動維護、由 pytest 把關。

### 執行時（frontend3d）

- 幾何重抓 250ms debounce（App.jsx:42-68）；`useMemo` 快取牆體幾何與材質並分開 dispose；`React.memo` 包家具 Item；GLB 以 `<Suspense>` 懶載，drei `useGLTF` 以 URL 為鍵快取。

### SSR / SSG / Code Splitting / Service Worker

**不適用或未實作**——內部工具型介面、同源供檔，無 SEO 需求；static UI 無打包器故無 splitting；無 Service Worker（grep 未見）。

---

## 第 5 部分: 技術可用性（量化標準）

### 響應式設計斷點

**無統一斷點系統。** `site.css` 含 66 條 `@media` 規則（grep -c 實測），斷點逐案取值（max-width 760px×9、520px×8、900px×7、1180px×7、980px×6、820px×6……非模板 xs-xl 尺度）；`scene.html` 內部樣式 0 條 `@media`；frontend3d `#root` 固定 `grid-template-columns: 320px 1fr`——實質**桌面優先、未承諾行動裝置**。

### 無障礙（A11y）

**無 WCAG 承諾與系統性檢測。** 現況存在零星語意化屬性：scene.html 含 `aria-*` 96 行（grep 實測），含步驟導覽 `aria-label`、3D viewer `aria-label`（如 scene.html:774「3D 資料庫家具配置」）、多處 `aria-live="polite"` 錯誤/提示欄位（scene.html:35,71,107,137 等）。鍵盤導航、對比度、螢幕閱讀器支援未系統性驗證（未查證）。

### 國際化（i18n）

**本專案不適用**——介面文案全為繁體中文硬編碼（`lang="zh-Hant"`），無 i18n 工具與多語需求。

---

## 第 6 部分: 工程化實踐

### 專案 file 組織（實況，非模板約定）

static UI 的組織是**檔名前綴慣例**，無目錄分層：

```
backend/server/static/
├── index.html / styles.html / library.html / scene.html / rag.html / engineering.html
├── site.css (15,407 行全站樣式) / rag.css (571 行 RAG 頁專用)
├── common.js            # 共用資料載入、背景特效、格式化
├── home.js / styles.js / library.js（+ viewer.js, library_thumbnails.js）
├── scene_v2.js          # 八步主流程入口（13,803 行）
├── scene_viewer.js      # Three.js viewer（5,555 行，由 scene_v2.js import）
├── scene_*.js           # 共 33 支，各管一個面板或契約（workflow/calibration/layout2d/style_packs/…）
├── engineering.js / engineering_link.js   # 工程文件頁與入口連結
├── rag.js               # RAG 測試台
├── vendor/              # three r165 + addons（vendor/three/ 20 檔）+ draco（vendor/draco/ 4 檔），共 24 檔
└── surface_assets/ questionnaire_images/ moodboard_assets/ style_cards/ style_images/ …（圖片資產）
```

frontend3d 為 6 檔扁平 `src/`（main/App/Scene/Furniture/snap/styles），不採模板的 components/features/hooks 結構。

### 程式碼品質

- Linter/Formatter：**無**（兩套前端均無 eslint/prettier 設定）。
- 型別：**無 TypeScript**，全為 JS/JSX。
- 提交慣例：repo 混用 conventional commits（`fix(catalog): …`）與中文描述，無 commitlint 強制。
- 分支：團隊 7 人各自分支 + 整合分支模式（遠端 17 條分支），非 Git Flow；責任歸屬以 `docs/TEAM_AI_OWNERSHIP.md` 為準，不可只依 Git author 推論。

### 測試策略（現況）

| 類型 | 現況 | 依據 |
| :--- | :--- | :--- |
| 前端 JS 行為測試 | `tests/static/` **3 支** `.test.mjs`（page_boot_failure / pending_actions / render_errors）+ 4 支 harness/stub（module_stub_hooks / scene_page_harness / scene_structure_preview_stub / scene_viewer_stub）；runner 為 `node --test`、devDependency 僅 jsdom ^26（tests/static/package.json，自述「jsdom 行為測試：第 6 步待處理清單的修復動作不得靜默失敗」）——舊導入版年代此項為零，已從零到有 | 實測 ls + package.json |
| 未接線模組的 Node 測試 | scene_delivery / scene_guidance / scene_space_change_report / scene_texture_uv 由 tests/ 內 Python 測試以 Node 方式驅動 | 實測 |
| 跨層守約測試（Python） | `tests/test_scene_v2_contract.py:20-28` 驗 scene.html 快取雜湊與 bundle 內容一致（現行工作樹預期紅燈，§4）；`tests/test_cloud_catalog_bridge.py` 直讀 `frontend3d/src/Furniture.jsx` 驗 CloudFront URL 透傳 | 實測 |
| 後端測試間接覆蓋 | tests/ 共 **99 支** test_*.py；static UI 的 API 契約由其覆蓋（`test_scene_*.py` 26 支、rag 3 支、engineering 7 支等）；2026-08-04 實跑 `pytest -q tests` = 811 passed / 1 failed / 9 skipped（共 821），唯一紅燈為 `test_scene_v2_contract.py` 的 cache-busting 雜湊守約 | 實測 ls + pytest |
| 元件/E2E/視覺測試 | **無** Testing Library / Playwright / Storybook | 實測 |
| frontend3d | 無任何測試框架；snap.js 為可測而設計但無測試檔 | 實測 |

---

## 第 7 部分: 前後端協作（技術面）

### API 通訊規範（現況）

- **無統一 API Client**：兩套前端皆直接呼叫原生 `fetch`（與模板建議相反，照實記錄）。
- **無型別自動生成**：FastAPI 可產 `/openapi.json`，工程文件另有 `docs/contracts/engineering_openapi.yaml`，但前端未做 codegen 消費。
- 全站 HTTP 路由 **63 條**（main.py 46 + rag_api.py 5 + catalog_admin.py 4 + engineering/api.py 8），前端消費其中主要子集如下。

### 7.1 主要 UI ↔ 後端資料流

`scene_v2.js` 呼叫（grep 實測）：

- 專案生命週期：`POST /api/projects`、`GET /api/projects/{id}`、`PUT /api/projects/{id}/workflow`、`POST/GET .../floorplan*`、`POST .../floorplan/analyze`、`POST .../render-jobs`、`GET .../renders`
- 場景管線：`POST /api/scene/{generate,layout,decorate,validate}`（validate＝第 6 步拖曳落點驗證，前端不自算座標，符合契約）
- 其他：`POST /api/agent/furniture/select`、`POST /api/floorplan/analyze`、`GET /api/furniture`、`GET /api/questionnaire/visual-catalog`（後端 `questionnaire_visuals.py` 供應）、`GET /api/render-provider/status`（後端 `render_providers.py` 供應）

其他頁面：`common.js` → `/api/site-data` 等站台資料；`engineering.js` → `/api/v1/{projects,jobs,packages}`、`/api/v1/engineering/health`（工程文件 MVP 的 snapshot→lock→packages→jobs→documents 前端端，202 建 job 後輪詢 `GET /api/v1/jobs/{job_id}`）；`rag.js` → `/api/rag/status` 與 202 非同步 `/api/rag/search/jobs{,/id}` 輪詢；`library.js` → `/api/furniture`。

### 7.2 保存一致性：樂觀鎖與 pending save

- **expected_revision 樂觀鎖（已接線）**：平面圖保存 POST 附 `expected_revision`（scene_v2.js:11752，`form.append("expected_revision", String(Number(state.project?.revision ?? 0)))`），衝突回 409 後前端以最新 project 重試（scene_v2.js:11746-11763 註解明言「409 幾乎都是 expected_revision 落後」）。舊導入版「現行前端未使用該機制」的記述已失效。
- **pending save 重放**：保存失敗時以 localStorage 暫存（`pendingSaveStorageKey()` 定義於 scene_v2.js:916，捕捉與排程在 :916-987），載入時重放（scene_v2.js:13482-13509）；重放帶版本檢查，遇衝突捨棄 pending 並重新 GET 專案。
- 後端配套：`ProjectStoreUnavailable` → 503（busy 時附 `Retry-After: 2`，main.py:226-243）。

### 認證與授權（Token 機制）

**本專案不適用**——前端消費的後端路由皆無認證/授權（`.claude/skills/roompilot-security` SKILL.md 明言「全端點無認證/授權」；2026-08-04 實測唯一例外是 `/api/admin/furniture` CRUD 4 條已有 Bearer token 驗證，`catalog_admin.py:170-195`，其餘 59 條仍無認證，且該 4 條不由瀏覽器前端呼叫），前端自然無 Token 儲存/重整/路由守衛。唯一 Bearer token 是伺服器對遠端渲染供應商的 `ROOMPILOT_RENDER_PROVIDER_TOKEN`，不經瀏覽器。

### 相關專案 skill（開發輔助，非 runtime）

`.claude/skills/roompilot-furniture-query` 把口語需求轉成 `POST /api/rag/search` 的受控詞彙檢索句（對應 `/rag` 頁測試台）；`roompilot-proposal` / `roompilot-budget` 消費 `/api/v1` ReportPayload 產出交付文件。皆為 agent 工具鏈，不屬前端程式碼。

---

## 第 8 部分: 監控與安全

### 前端監控

**全部未建立**：無 web-vitals 收集、無 Sentry/錯誤上報、無行為追蹤。錯誤呈現只到 UI 層（scene 頁 `aria-live` 錯誤欄位、rag/engineering 頁狀態區塊）。

### 前端安全（現況檢查表）

- [ ] XSS 防護：static UI 手寫 DOM，`innerHTML` 賦值共 **108 處、6 檔**（scene_v2.js 78、library.js 19、styles.js 6、engineering.js 3、home.js 1、scene_viewer.js 1，grep `\.innerHTML *=` 實測；另 scene_v2.js:8707、13065 兩行僅為註解提及，故 grep -c `innerHTML` 得 110 行）；scene_v2.js 備有 `escapeHtml`（scene_v2.js:130）供插值跳脫，模板字面量普遍套用（如 scene_v2.js:2384-2387），但每處是否都經跳脫未逐點審計（未查證）；無 CSP header
- [ ] CSRF 防護：無（也無 cookie-based 認證，攻擊面有限但未評估）
- [x] 敏感資料不存 localStorage：只存 workflow 進度與 pending save，不含個資；個資剝除在伺服器端做（送遠端渲染前剝 name/phone/email）
- [ ] 依賴掃描：未執行（tests/static 僅 jsdom 一個 devDependency；frontend3d node_modules 不存在無從 audit）
- [x] Subresource Integrity：**已不適用**——全 static 無外部 CDN 資源（three 已 vendor 進 repo，grep `https` 零命中），舊版 SRI 待辦就此關閉

全面的攻擊面盤點（SSRF、上傳、模型交付、PostgreSQL）由 `.claude/skills/roompilot-security` 的 audit.sh 承接，不在本文件範圍。

---

## 第 9 部分: 技術上線檢查清單

> IA / 可用性檢查清單在 frontend_information_architecture。本清單只有技術項。

**現況可執行的檢查：**

- [ ] 快取雜湊守約綠燈——2026-08-04 實算**紅燈**：scene.html 的 scene_v2.js/site.css 與 library.html 的 library.js 三處雜湊與內容不符（§4）；修法＝重算 `?v=sha256-…` 前 12 hex 回填
- [ ] 後端 pytest 全綠（tests/ 99 支，含 test_scene_v2_contract 與 frontend3d 守約）——2026-08-04 實跑 811 passed / 1 failed / 9 skipped，尚未全綠（紅燈 = test_scene_v2_contract 雜湊守約）
- [ ] `tests/static/` 的 `node --test` 全綠（需先 `npm install` 裝 jsdom）
- [ ] `/scene`、`/engineering`、`/rag` 的 no-store 部署後生效驗證
- [ ] CloudFront 模式下家具 model_url 全為 https（`GET /api/catalog/status`）

**未建立、列為待辦（需先裁決是否投資）：**

- [ ] Core Web Vitals 量測與目標（§4）
- [ ] 快取雜湊自動重算腳本（現為手動維護，§4；紅燈即其成本證據）
- [ ] ESLint/Prettier 導入（§6）
- [ ] static UI innerHTML 108 處 XSS 逐點審計 + CSP（§8）
- [ ] 響應式斷點整理與行動裝置支援範圍聲明（§5）
- [ ] frontend3d 定位裁決：README port/路徑過時、npm 依賴衝突（舊版實測 ERESOLVE），除役或修復擇一（§2.2）
- [ ] tokens 統一：rag.css 目前只沿用 site.css 的字型令牌，色彩／半徑／陰影仍硬編碼，需一併收斂（§3）；色卡雙來源（JSON vs scene_style_packs.js）裁決權威（§3）

---

## 附:本文件未查證項清單

| 項目 | 說明 |
| :--- | :--- |
| pytest 實跑結果 | 本機缺 pytest 相依未能執行；快取雜湊紅燈為 shasum 實算推得，非測試輸出 |
| frontend3d `npm install`/`build` | node_modules 不存在；舊導入版（2026-07-26）實測 ERESOLVE 失敗，本次未重測 |
| static UI XSS 逐點審計 | innerHTML 賦值 108 處已量測，每處是否都經 `escapeHtml` 未逐點確認 |
| a11y 鍵盤導航/對比度/螢幕閱讀器 | aria-* 96 行存在，系統性驗證未做 |
| 模板指向的包外來源 | 模板參照的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/` 不在 repo 內（未查證：來源不在 repo） |
