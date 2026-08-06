# 前端架構規範 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 12_frontend_architecture_specification.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 已發布(依現行程式碼逐條核對整理)
> **相關文檔:** [API 設計規範 (06)](../04_design/api_spec.md)、[專案結構指南 (08)](../04_design/lld_project_structure.md)、[前端資訊架構 (17)](information_architecture.md)(已導入)
>
> **MECE 邊界**:本文件**只談技術視角**(stack / 分層 / 量化指標 / 工程化)。
> 使用者視角(頁面職責、旅程、導航、路由內容)依模板約定屬 17 號文件,已導入:[17_frontend_information_architecture_template.md](information_architecture.md)。
>
> | 你想找的 | 看這份 |
> |---|---|
> | 兩套前端是什麼、關係如何 | 12(本檔)§0 |
> | 用什麼框架、怎麼分層 | 12(本檔)§2 |
> | 3D 渲染架構(牆體擠出、X-ray、吸附) | 12(本檔)§2.3 |
> | 效能與快取現況 | 12(本檔)§4 |
> | 專案 file 組織、測試現況 | 12(本檔)§6 |
> | 與後端的資料流、API 呼叫點 | 12(本檔)§7 |
> | 全部 44 條 API 端點規格 | 06 |
> | 哪些**頁面**存在、頁面職責、旅程 | [17](information_architecture.md) |

---

## 第 0 部分: 現況總覽——兩套前端並存(先讀這節)

本專案同時存在兩套前端,模板其餘章節分別描述:

| | A. `frontend/`(**現行主要 UI**) | B. `frontend3d/`(R3F 子專案) |
| :--- | :--- | :--- |
| 型態 | 無建置步驟的靜態頁,由 FastAPI 直接供檔 | Vite + React 18 + React Three Fiber 的獨立子專案 |
| 規模 | 4 個 HTML + 33 支 JS + site.css(頂層實測) | git 追蹤 11 檔;`src/` 6 檔共 960 行 |
| 入口 | `GET /`、`/styles`、`/library`、`/scene`(main.py:1432-1452) | `npm run dev` 起 Vite dev server,`/api` 代理到 8002 |
| 職責 | 十步驟主流程(建立專案→上傳→…→AI 渲染)、風格庫、家具庫 | DXF 上傳→3D 白模檢視、GLB 家具手動擺放試驗 |
| 負責人 | Bella(README.md:16) | Bella(README.md:16;README.md:170 稱「React Three Fiber 3D 編輯器」) |

### frontend3d 與後端的關係(照實描述)

- `backend/server/main.py:2072` 的 `_legacy_viewer_models()` docstring 寫明 **"Feed the retired R3F viewer"**(退役的 R3F 檢視器),但供它使用的路由**全部存活**:main.py:2657 起有註解「以下路由自原 app/backend/main.py 移植,供 frontend3d(React Three Fiber)使用」,含 `GET /api/plans`、`GET /api/plan`、`POST /api/upload`、`GET /api/furniture/{name}`;`GET /api/furniture` 回應也保留 legacy 鍵 `furniture` 餵它(main.py:2066)。
- `tests/test_cloud_catalog_bridge.py:133` 的 `test_frontend3d_accepts_cloudfront_model_urls` 仍直接讀 `frontend3d/src/Furniture.jsx` 原始碼驗證它能吃 CloudFront URL——CI 層面 frontend3d 仍被當作受保護的消費端。
- `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md:17` 把 `frontend/` 與 `frontend3d/` 並列為前端職責範圍(蒐集需求、呼叫 API、呈現結果;禁止在瀏覽器自行推算合法家具座標)。
- `frontend3d/README.md` 內容已過時:寫後端 port 8000、路徑 `app/backend/`/`app/frontend/`,與 `vite.config.js` 實際代理的 8002 及倉庫根 README 的啟動指令(`uv run uvicorn backend.server.main:app --port 8002`,README.md:185)矛盾。git 實測:該檔自 2026-07-06 重構 commit 85b4a92 後未再更動,內容沿用重組前 `app/` 佈局——屬未同步更新,非刻意標記。
- `frontend3d/node_modules` 不存在(實測),依賴未安裝;`npm install --dry-run` 實測(2026-07-26)以 **ERESOLVE 失敗**:鎖定的 `@vitejs/plugin-react` 4.7.0 peer 只支援 vite ^4–^7,與宣告的 vite ^8.1.0 衝突,預設安裝直接中止(npm 提示需 `--legacy-peer-deps`/`--force`);`npm run dev`/`npm run build` 因依賴裝不起來仍無法驗證(未查證)。

> **裁決事項(待本顥/團隊決定):** frontend3d 的定位——(a) 正式除役:移除 main.py:2657 起的移植路由、`_legacy_viewer_models`、legacy `furniture` 鍵與對應測試,封存目錄;或 (b) 保留為 DXF 除錯工具:更新 frontend3d/README.md(port、路徑)、解決 `npm install` 的 ERESOLVE 衝突(vite 8 vs plugin-react peer,實測失敗)。現況「docstring 說退役、路由與測試都活著」是半吊子狀態,文件與程式碼互相矛盾。

---

## 第 1 部分: 架構目標(量化)

模板要求的量化指標(LCP/INP/CLS/TTI、a11y 通過率、覆蓋率、錯誤率)**本專案均未建立量測**,無任何 web-vitals 收集或監控程式碼(§8)。以下為現況實際成立的架構目標,依據為程式碼註解與實作:

| 維度 | 現況目標 | 依據 |
| :--- | :--- | :--- |
| 正確性優先於快取 | `/scene` 頁回應帶 `Cache-Control: no-store`(main.py:1449-1452);JS 以內容雜湊查詢參數載入(`scene_v2.js?v=sha256-2ff7e164ea1b`,scene.html:792)防舊快取——注意本分支該雜湊已與 scene_v2.js 現內容不符,守約測試紅燈(§6) | 記憶檔:曾因舊頁快取造成組員驗收問題 |
| 3D 即時互動 | 牆體 X-ray shader、拖曳吸附即時計算(§2.3);幾何重算 250ms debounce(App.jsx:42-68) | 程式碼 |
| 免 CORS 設定 | frontend3d 以 Vite proxy 把 `/api` 轉到 8002(vite.config.js);static 頁與 API 同源——後端**沒有任何 CORS middleware**(全 backend/ grep 無 `add_middleware`/`cors`) | 程式碼 |
| 座標紀律 | 前端不得自行推算合法家具座標,一律問後端引擎(contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md:17) | 契約 |

量化效能預算:**待補**(見 §9 檢查清單)。

---

## 第 2 部分: 系統化分層

### 2.1 現行主要 UI(frontend/)分層

```
用戶感知層    -- 4 個 HTML(index/styles/library/scene)+ site.css + scene.html 內部樣式
互動邏輯層    -- 33 支原生 ES module JS(其中 scene_*.js 26 支;scene_v2.js 8,544 行為主檔)
狀態管理層    -- 模組內變數 + localStorage(workflow v2 契約 + 待重放的 pending save)
資料通訊層    -- 原生 fetch,無封裝 client;保存失敗 3 次退避重試 + pending save 版本檢查重放(§7.2)
基礎設施層    -- 無建置工具、無打包、無前端測試框架;由 FastAPI StaticFiles 直接供檔
```

| 層級 | 技術選型(現況) | 依據 |
| :--- | :--- | :--- |
| 感知層 | 無框架 vanilla JS + 手寫 CSS;three.js **0.165.0** 經 `<script type="importmap">` 從 unpkg CDN 載入(scene.html:784-791) | 實測 |
| 互動層 | 原生 DOM 事件;`scene.html` 頂部導覽 10 顆步驟按鈕(`data-step`,scene.html:22-32) | 實測 |
| 狀態層 | `scene_workflow.js` 匯出 `WORKFLOW_SCHEMA_VERSION = 2`、`WORKFLOW_STORAGE_KEY = "roompilot.workflow.v2"`、`createWorkflow({projectId, storage = globalThis.localStorage})`;`scene_v2.js` 另以 localStorage 存斷線期間的 pending save 供重放(scene_v2.js:510-582) | 實測 |
| 通訊層 | `scene_v2.js` 內 16 種 `/api/*` 端點字串(§7.2);`common.js` 負責 `/api/home-data`、`/api/scene/bootstrap`、`/api/site-data`、`/api/styles`、`/api/furniture` | grep 實測 |
| 基礎設施 | `app.mount("/static", ...)` 與 `app.mount("/docs-assets", ...)`(main.py:163-164);JS 相互 import 也帶雜湊查詢參數(如 `scene_viewer.js?v=sha256-aee068a25df9`) | 實測 |

主流程步驟順序以程式碼為準:`static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS` 共 11 個內部步驟(`project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render`);`recognition` 與 `calibration` 共用同一 "scale" 面板,故 UI 只顯示 10 顆按鈕。伺服器端 main.py 的同名集合只驗步驟名不驗順序,前置依賴僅由前端強制。

### 2.2 frontend3d 分層

```
用戶感知層    -- React 18 JSX + styles.css(68 行,深色主題,#root 固定 grid 320px|1fr)
互動邏輯層    -- R3F pointer events + window 原生鍵盤/指標事件(Furniture.jsx)
狀態管理層    -- 純 React useState/useRef,全部集中 App.jsx 頂層(15 個 useState)
資料通訊層    -- 原生 fetch ×4 + drei useGLTF 載 GLB
基礎設施層    -- Vite 8.1.0 + @vitejs/plugin-react;無測試、無 lint、無 TypeScript
```

| 層級 | 技術選型(現況) | 依據 |
| :--- | :--- | :--- |
| 感知層 | React 18.3.1 + @react-three/fiber + @react-three/drei(OrbitControls/Bounds/Grid/useGLTF);樣式為手寫 class 級 CSS,無 CSS Modules/Tailwind | package.json、src 實測 |
| 互動層 | 無表單庫;控制項為原生 `<select>`/`<input type="range">`/checkbox(App.jsx) | 實測 |
| 狀態層 | **無** redux/zustand/jotai/context(package.json 無此類依賴,src 無 import);15 個 useState:plans/name/upload/scaleM/thickness/height/data/loading/error/show/furn/items/placing/selectedId/snapOn,以 props 下傳 | 實測 |
| 通訊層 | 原生 fetch(§7.1);錯誤處理讀後端 `detail` 欄位(App.jsx:58) | 實測 |
| 基礎設施 | `vite.config.js` 僅 2 項設定:`plugins:[react()]` 與 `server.proxy {'/api': 'http://localhost:8002'}`;scripts 只有 dev/build/preview | 實測 |
| 路由器 | **無**(單頁,`main.jsx` 直接 `createRoot(...).render(<App />)`,無 Router、無 Provider) | 實測 |

**依賴清單(package.json 宣告 vs package-lock.json 鎖定)**:

| 套件 | 宣告 | 鎖定 |
| :--- | :--- | :--- |
| react / react-dom | ^18.3.1 | 18.3.1 |
| three | ^0.160.1 | 0.160.1 |
| @react-three/fiber | ^8.17.10 | 8.18.0 |
| @react-three/drei | ^9.114.0 | 9.122.0 |
| vite(dev) | ^8.1.0 | 8.1.0 |
| @vitejs/plugin-react(dev) | ^4.3.4 | 4.7.0 |

注意:frontend3d 用 three **0.160.1**、static UI 用 CDN three **0.165.0**——兩套前端的 three 版本不一致(照實記錄,無同步機制)。另:鎖定的 plugin-react 4.7.0 peer range 不含 vite 8,`npm install` 實測 ERESOLVE 失敗(§0)。

### 2.3 frontend3d 3D 渲染架構(src/ 各檔職責)

| 檔案 | 行數 | 職責 |
| :--- | :--- | :--- |
| `main.jsx` | 6 | createRoot 掛載 `<App />` |
| `App.jsx` | 209 | 全部狀態 + 4 個 fetch + 左側控制面板(平面圖選擇、比例/牆厚/樓高滑桿、圖層開關、家具庫) |
| `Scene.jsx` | 236 | `<Canvas shadows>`;牆=`THREE.ExtrudeGeometry` 從 `wall_polys`(exterior+holes)擠出;**X-ray 透牆**=`onBeforeCompile` 注入 fragment shader(uniforms: uCamPos/uViewDir/uCamDist/uFade/uMargin/uBand/uMinAlpha),鏡頭拉近時逐 fragment 淡化鏡頭與焦點之間的牆面(因後端把所有牆 union 成單一 mesh,近牆遠牆共用 mesh,只能逐 fragment 判斷);窗/門=`SegBoxes` 沿線段擺 boxGeometry;座標約定 **plan(x,z)→world(x,−z)**,Y 為高 |
| `Furniture.jsx` | 304 | 家具擺放層:`useGLTF` 載 GLB 後 clone、`rotation.x = -PI/2` 立正(trimesh 匯出為 Z-up)、置中貼地;互動:點擊放置(ghost 跟隨游標)、Shift+點擊連續放置、拖曳移動、R 旋轉 90°、Del/Backspace 刪除、Esc 取消;游標→地面用手動 Raycaster 對 y=0 平面求交;隱形 pick plane(`colorWrite:false`)接放置點擊 |
| `snap.js` | 137 | 純 2D 吸附幾何,**刻意不 import three 以便 node 單測**(檔頭註解);常數 GRID=0.1m、WALL_SNAP=0.45m、EDGE_SNAP=0.18m、GAP=0.005m;優先序:牆面(含轉角雙牆 corner)→家具邊緣 AABB 對齊→0.1m 格點 |
| `styles.css` | 68 | 深色主題全域樣式 |

---

## 第 3 部分: 設計系統

**本專案不適用(未建立)**——兩套前端均無 Design Tokens 定義檔、無 Atomic Design 元件分層、無元件庫;樣式為手寫 CSS(static: site.css + scene.html 內部樣式;frontend3d: styles.css 內以 hex 色碼硬編碼)。

與「設計系統」概念最接近的現況資產是**設計內容資料**而非技術令牌:6 風格 × 3 色系 = 18 張色卡(`backend/catalog/data/taiwan_style_cards.json`,實測 6 風格各 3 卡,每卡 `palette_hex` 三色)。注意色票實際存在**兩份平行資料**:該 JSON 由後端 `style_cards.py` 載入、經 API 供前端;`static/scene_style_packs.js` 則以同一組 card_id **另行硬編碼**每卡 4 色 palette 與 PBR/燈光參數,數值與 JSON 不一致(如 `scandinavian_1`:JSON `#F3EBDD…` vs style_packs `#FAF4EE…`,實測)。`docs/contracts/STYLEPACK_RENDERING_CONTRACT.md:23-31` 把兩者並列為各自職責的執行來源。若未來要建 tokens,需先裁決以哪份為準——平行清單已是現況,不是風險預告。

---

## 第 4 部分: 效能策略(量化)

### Core Web Vitals 目標

**未建立**——無量測工具、無數字目標(待補,見 §9)。以下為現況**實際存在**的效能相關實作:

### 載入與快取(現況)

| 手段 | 位置 | 說明 |
| :--- | :--- | :--- |
| 內容雜湊防快取 | scene.html:792 及 scene_v2.js 內部 import | JS 以 `?v=sha256-...` 查詢參數載入,改版即失效舊快取 |
| `Cache-Control: no-store` | main.py:1449-1452 | 只對 `/scene` 頁;犧牲快取換部署正確性 |
| GLB 走 CDN | `/api/furniture/{furniture_id}/model` → 307 轉址 CloudFront(main.py:914-935) | 模型檔不經 FastAPI 傳輸;`ROOMPILOT_MODEL_DELIVERY_MODE` 預設 `cloudfront` |
| 型錄分頁 | `GET /api/furniture` page_size 1-80、預設 24 | 避免 9,350 件一次載入 |
| CDN importmap | scene.html:784-791、library.html:160-167 | three@0.165.0 由 unpkg 載入,不在 repo 內(`/scene` 與 `/library` 兩頁) |

### 執行時(現況,frontend3d)

- 幾何重抓 **250ms debounce**(App.jsx:42-68),滑桿連續調整不會每 tick 打 API。
- `useMemo` 快取牆體幾何與材質,且**分開的 dispose 節奏**:材質只在換色/卸載時 dispose,幾何在重建時 dispose——耦合會導致每次滑桿微調都重編譯 shader(Scene.jsx:71-77 註解)。
- `React.memo` 包家具 Item;GLB 以 `<Suspense>` 逐件懶載;drei `useGLTF` 內建以 URL 為鍵的快取。
- X-ray 淡化用 `THREE.MathUtils.damp` 緩動,並在近俯視角自動關閉(Scene.jsx:93-99)。

### SSR / SSG

**本專案不適用**——兩套前端皆為內部工具型介面,由 FastAPI 同源供檔或 Vite dev server 執行,無 SEO 與匿名首屏需求。

### Code Splitting / Service Worker / 圖片 WebP 化

**未實作**(static UI 無打包器故無 splitting 概念;無 Service Worker 註冊,grep 未見)。

---

## 第 5 部分: 技術可用性(量化標準)

### 響應式設計斷點

**無統一斷點系統。** 現況:

- `static/site.css` 含 47 條 `@media` 規則,但斷點為逐案取值(max-width 520/620/640/720/760/820/900/920/980/1120px 等,grep 實測),非模板式的 xs-xl 尺度。
- `scene.html` 內部樣式 0 條 `@media`;`frontend3d/styles.css` 的 `#root` 固定 `grid-template-columns: 320px 1fr`,不做響應式——兩者實質**桌面優先、未承諾行動裝置**。

### 無障礙 (A11y)

**無 WCAG 承諾與檢測。** 現況存在零星語意化屬性:scene.html 步驟導覽有 `aria-label="空間規劃流程"`,提示區與錯誤訊息有 `aria-live="polite"`(scene.html 實測)。鍵盤導航、對比度、螢幕閱讀器支援均未系統性驗證(未查證)。

### 國際化 (i18n)

**本專案不適用**——介面文案全為繁體中文硬編碼(`index.html`/`scene.html`、frontend3d `index.html` 均 `lang="zh-Hant"`),無 i18n 工具與多語需求。

---

## 第 6 部分: 工程化實踐

### 專案 file 組織(實況,非模板約定)

frontend3d 不採用模板的 `components/features/hooks/...` 目錄結構,src/ 為 6 檔扁平結構:

```
frontend3d/
├── index.html            # 掛載點 #root,載入 /src/main.jsx
├── package.json          # room-3d;scripts 僅 dev/build/preview
├── package-lock.json
├── vite.config.js        # react plugin + /api proxy → localhost:8002
├── README.md             # ⚠️ 內容過時(port 8000、app/backend/ 路徑),見 §0 裁決事項
└── src/
    ├── main.jsx          # 進入點
    ├── App.jsx           # 狀態 + 面板 + fetch
    ├── Scene.jsx         # Canvas、牆/窗/門/地板、X-ray shader
    ├── Furniture.jsx     # GLB 擺放層 + furnitureUrl()
    ├── snap.js           # 純 2D 吸附幾何(無 three 依賴)
    └── styles.css
```

static UI 的組織是**檔名前綴慣例**:`scene_*.js` 26 支(workflow/calibration/layout2d/viewer/style_packs/questionnaire...各管一個面板或契約)、`common.js` 共用資料載入、頁面各配一支同名 JS(home/styles/library)。無目錄分層。

### 程式碼品質

- Linter/Formatter:**無**(frontend3d 無任何 eslint/prettier 設定檔,實測)。
- 型別:**無 TypeScript**,全為 JS/JSX(無 tsconfig,實測)。
- 提交慣例:repo 混用 conventional commits(`fix(catalog): ...`)與中文前綴(`修正:`、`新增:`),git log 實測,無 commitlint 強制。
- 分支:團隊各自分支 + 整合分支模式(README「共同規則」;分支歸屬見記憶檔),非 Git Flow。

### 測試策略(現況)

| 類型 | 現況 | 依據 |
| :--- | :--- | :--- |
| 前端單元測試 | **零**。frontend3d 無測試框架;`snap.js` 檔頭寫明「不 import three 以便 node 單測」,但 repo 內**沒有**對應測試檔(tests/ 全為 Python,實測) | 實測 |
| 前端元件/E2E/視覺 | **無** Testing Library/Playwright/Storybook | 實測 |
| 跨層守約測試(Python) | `tests/test_cloud_catalog_bridge.py:133` `test_frontend3d_accepts_cloudfront_model_urls` 直接讀 `frontend3d/src/Furniture.jsx` 原始碼,驗證 `furnitureUrl()` 透傳 https URL | 實測 |
| 後端測試間接覆蓋 | static UI 的 API 契約由後端 pytest(tests/ 47 檔)覆蓋;前端 JS 邏輯本身無自動化測試 | 實測;2026-07-26 本分支 `uv run pytest`:**389 passed / 2 failed / 1 skipped**,敗的 2 條均為 `tests/test_scene_v2_contract.py` 快取鍵一致性(scene.html 的 `?v=sha256-2ff7e164ea1b` ≠ scene_v2.js 現內容雜湊 `6221aa80936c`) |

---

## 第 7 部分: 前後端協作(技術面)

### API 通訊規範(現況)

- **無統一 API Client**:兩套前端皆直接呼叫原生 `fetch`(與模板建議相反,照實記錄)。
- **無型別自動生成**:FastAPI 可產 `/openapi.json`,但前端未消費(無 codegen 設定,實測無相關檔案)。
- 錯誤處理:frontend3d 讀 `(await res.json()).detail || res.statusText`(App.jsx:58);static UI 保存失敗時重試 3 次(180ms 遞增退避,scene_v2.js:514-535);離線期間的 pending save 於載入時以 `replay_pending` + `base_updated_at` 重放,遇 409 直接捨棄 pending 並重新 GET 專案(scene_v2.js:8310-8333)。後端另支援 `expected_revision` 樂觀鎖與 409 `project_revision_conflict` 附回最新 project(main.py:1542-1592,契約詳見 06 號文件),但 grep 全 static/ 無 `expected_revision` 字串——**現行前端未使用該機制**。
- CORS:後端**無** CORS middleware。frontend3d 依賴 Vite proxy 同源化;若改為跨源直連後端,瀏覽器會攔截,屬已知限制。

### 7.1 frontend3d ↔ 後端資料流(4 個 fetch + 1 個 GLB URL)

| 呼叫點 | 端點 | 後端定義 | 用途 |
| :--- | :--- | :--- | :--- |
| App.jsx:26 | `GET /api/plans` | main.py:2661 | 列 `testdata/pic/temp/` 的 DXF(實測 7 個檔) |
| App.jsx:30 | `GET /api/furniture` | main.py:2018 | 只讀回應 legacy 鍵 `furniture`;CloudFront 模式回最多 24 條已驗證 https model_url,local 模式回 `testdata/sample_glb/` 檔名(main.py:2071-2085;該目錄現不存在,實測回空清單) |
| App.jsx:53 | `POST /api/upload?thickness&height[&scale_m]`(FormData `file`) | main.py:2682 | 上傳 DXF 直接解析,失敗 422 |
| App.jsx:56 | `GET /api/plan?name&thickness&height[&scale_m]` | main.py:2666 | 解析既有 DXF;`Path(name).name` basename 防路徑跳脫;404/422 |
| Furniture.jsx:7-11 | `GET /api/furniture/{name}` 或直接透傳 URL | main.py:2787 | `furnitureUrl()`:`http(s)://` 或 `/` 開頭直接透傳(可吃 CloudFront model_url),否則組本機端點;`.glb` 結尾在 CloudFront 模式回 410 |

回傳幾何契約(frontend3d 消費欄位):`wall_polys`(公尺,exterior+holes)、`windows`/`doors`(x1/z1/x2/z2)、`bbox`、`wall_height`、`wall_thickness`、`scale_m`、`scale_basis`、`fallback_all_walls`、`stats{width_m, depth_m, extent_area, wall_segments, wall_polys, windows, doors}`(App.jsx/Scene.jsx 實測)。此為 `backend/upgrade3d/dxf_parser.py` 的公尺制輸出——與主流程 static UI 的**公分制**契約(`coordinate_unit='cm'`)不同體系,照實記錄。

### 7.2 現行主要 UI ↔ 後端資料流(摘要)

`scene_v2.js`(8,544 行)呼叫的端點(grep 字串實測,16 種):

- 專案生命週期:`POST /api/projects`、`GET /api/projects/{id}`、`PUT /api/projects/{id}/workflow`(自動保存;帶 `base_updated_at`,重放時附 `replay_pending` 做版本檢查,**未用** `expected_revision`,見上)、`POST .../floorplan`、`GET .../floorplan/source`、`POST .../floorplan/analyze`、`POST .../render-jobs`
- 場景管線:`POST /api/scene/generate`、`/api/scene/layout`、`/api/scene/decorate`、`/api/scene/validate`(F6 拖曳落點驗證——前端不自算座標,符合契約)
- 其他:`POST /api/agent/furniture/select`、`POST /api/floorplan/analyze`、`GET /api/furniture?...`(4 種參數組合)、`GET /api/questionnaire/visual-catalog`、`GET /api/render-provider/status`

`common.js` 負責 `GET /api/home-data`、`/api/scene/bootstrap`、`/api/site-data`、`/api/styles`、`/api/furniture`。

3D 檢視由 `scene_viewer.js`(`scene_v2.js:1` import)以 three@0.165.0 實作,`preserveDrawingBuffer: true` + `toDataURL("image/png")` 支援瀏覽器端截圖(scene_viewer.js:51、2661);後端 `POST /api/projects/{id}/renders` 接受 `provider=browser_capture` 的 PNG 上傳,但全 repo grep:`browser_capture` 只出現在 main.py 與 tests/,static/ 與 frontend3d/ 均無對 `/renders` 的呼叫點——**上傳鏈路未接通(實測)**,該端點現階段只有測試在打;前端接的是 `POST .../render-jobs`(遠端渲染提交)。

### 認證與授權(Token 機制)

**本專案不適用**——後端 44 條路由全部無認證(06 號文件),前端自然無 Token 儲存/重整/路由守衛。唯一的 Bearer token 是伺服器對外呼叫遠端渲染供應商時附的 `ROOMPILOT_RENDER_PROVIDER_TOKEN`,不經過瀏覽器。

---

## 第 8 部分: 監控與安全

### 前端監控

**全部未建立**:無 web-vitals 收集、無 Sentry/錯誤邊界上報、無行為追蹤(兩套前端 grep 無相關依賴與程式碼)。錯誤呈現只到 UI 層(frontend3d 的 `.err` 區塊、scene 頁的 aria-live 錯誤欄位)。

### 前端安全(現況檢查表)

- [ ] XSS 防護:React 有自動跳脫(frontend3d);static UI 為手寫 DOM 操作,`innerHTML` 賦值共 109 處、集中 6 支 JS(scene_v2.js 51、scene.js 31、library.js 19、styles.js 6、home.js 1、scene_viewer.js 1,grep 實測),scene_v2.js 備有 `escapeHtml`(scene_v2.js:97)供插值跳脫;無 CSP header(main.py 無設定)——每一處是否都經跳脫未逐點審計,**未查證**
- [ ] CSRF 防護:無(也無 cookie-based 認證,攻擊面有限但未評估)
- [x] 敏感資料不存 localStorage:localStorage 只存 workflow 進度與 pending save(scene_workflow.js、scene_v2.js:510-582),不含個資;個資剝除在伺服器端做(render_service.py 送遠端前剝 name/phone/email)
- [ ] 依賴掃描:未執行(`npm audit` 需先 `npm install`,node_modules 不存在)
- [ ] Subresource Integrity:**缺**——scene.html 與 library.html 的 unpkg importmap 均無 `integrity` 屬性(grep 兩檔零命中,實測);three.js 由第三方 CDN 載入而無完整性驗證,是明確的供應鏈風險點(待辦)

---

## 第 9 部分: 技術上線檢查清單

模板原清單多數項目在本專案無對應建設,照實改寫為兩欄:

**現況可執行的檢查:**

- [ ] 後端 pytest 全綠(tests/ 47 檔;含 `test_cloud_catalog_bridge.py` 的 frontend3d 守約測試)——2026-07-26 實測**未全綠**:389 passed / 2 failed / 1 skipped,敗因=scene.html 快取雜湊未隨 scene_v2.js 內容更新(§6);修法=重算 `?v=sha256-…` 參數
- [ ] `/scene` 頁 no-store 與 JS 雜湊參數在部署後確實生效(改版後強制重新載入驗證)
- [ ] CloudFront 模式下家具 model_url 全為 https(`GET /api/catalog/status` 的 manifest_ready)

**未建立、列為待辦(需先裁決是否投資):**

- [ ] frontend3d 定位裁決(§0)→ 據此決定是否修 README、解 `npm install` ERESOLVE(已實測失敗,§0)並驗證 `npm run build`
- [ ] Core Web Vitals 量測與目標(§4)
- [ ] 前端 JS 測試(至少 `snap.js` 已為可測而設計,補 node 單測成本最低)
- [ ] ESLint/Prettier 導入(§6)
- [ ] unpkg CDN 資源 SRI 或改為 vendor 進 repo(§8)
- [ ] 響應式斷點整理與行動裝置支援範圍聲明(§5)
- [x] 17 號文件(前端資訊架構)已導入:`./17_frontend_information_architecture_template.md`,收納頁面職責/旅程/路由表

---

## 附:本文件未查證項清單

2026-07-26 逐項複查後,原列 5 項中 3 項已查證完畢並回寫正文:pytest 通過率(389/2/1,§6)、browser_capture 上傳鏈路(未接通,§7.2)、frontend3d README 過時原因(85b4a92 後未更動,§0)。仍未查證的剩:

| 項目 | 說明 |
| :--- | :--- |
| `npm run dev`/`npm run build` 可行性 | `npm install` 已實測 ERESOLVE 失敗(§0);dev/build 因依賴裝不起來,仍無法驗證 |
| static UI 的 XSS 逐點審計 | `innerHTML` 109 處已量測(§8),每處是否都經 `escapeHtml` 跳脫未逐點確認 |
| a11y 鍵盤導航/對比度/螢幕閱讀器 | 零星 aria 屬性存在(§5),系統性驗證未做 |
