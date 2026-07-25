# 前端架構規範 - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿
> **相關文檔:** [API 設計規範 (06)](./06_api_design_specification.md)、[專案結構指南 (08)](./08_project_structure_guide.md)、[檔案相依性 (09)](./09_file_dependencies_template.md)
>
> **本專案的前端現實**：RoomPilot-Agent 是純 Python CLI 管線，**無 SPA 框架、無 Node.js 工具鏈、無前端建置流程**。現存的「前端」共三件實體：
>
> | 實體 | 位置 | 性質 |
> |---|---|---|
> | 四層級辨識成功率報表 | `recognition_report.html`（專案根，181 行） | **產出型靜態報表**：純 HTML＋CSS（0 行 JavaScript），含深色模式，隨每版評測手動/半自動同步數字 |
> | 標注覆核頁 | `review.html` | **臨時工作檔**（未進版控）：VLM 盲標分歧人工覆核用「看圖點選」頁，v2.16 曾以此覆核 47 筆分歧（36 補名／10 錯名修正／1 降回） |
> | 系統櫃設計器 | `cabinet_designer.py` 內嵌 `INDEX_HTML`（全檔 1599 行） | **內嵌單頁應用**：Python `ThreadingHTTPServer` 綁 `127.0.0.1:8765`，canvas 拖放設計＋`/api/dxf`、`/api/quote`、`/api/quote.csv` 三個本機端點 |
>
> 另有明確的「**未來前端整合**」路線（Readme v2.16 第二節）：外部前端 clone 本 repo、設 `GITHUB_TOKEN` 即可全自動下載 v5 權重，丟任意新 PNG 判斷房型；交接介面是 `json/` 每圖一份的前端交接 JSON（px＋cm 雙座標系）。本文件凡標 N/A 的模板段落，一律附「未來前端整合時的建議值」。
>
> 模板中「12/17 MECE 邊界」對照表：17 已實例化為 [./17_frontend_information_architecture_template.md](./17_frontend_information_architecture_template.md)。分工邊界：**本文件（12）談技術架構視角**（實體盤點、產生機制、渲染/伺服方式、未來前端整合技術建議）；**17 談使用者/內容視角**（頁面職責、閱讀順序、覆核旅程、跨產物資料流），主要涵蓋 `recognition_report.html` 與 `review.html` 兩個產出頁。

---

## 第 1 部分: 架構目標（量化）

| 維度 | 本專案目標 | 衡量指標 |
| :--- | :--- | :--- |
| **效能** | 報表頁開檔即讀（本機 `file://` 直開，無網路請求） | `recognition_report.html` 為單檔自足（0 外部資源、0 JS），LCP 實質等於檔案讀取時間 |
| **技術可用性** | 報表在明/暗兩種系統主題下皆可讀；行動裝置可讀 | `prefers-color-scheme: dark` 全變數覆蓋；`viewport` meta＋`auto-fit` grid＋表格 `overflow-x:auto` |
| **可維護性** | 報表數字與 `json/eval_rooms/*.json` 評測報表一致，每版（如 v2.16）全量同步 | 版本落差為 0（Readme 變更紀錄逐版核對） |
| **可靠性** | 櫃體設計器僅綁 `127.0.0.1`，單機自足，無外部依賴故障面 | 端點錯誤統一 500＋錯誤字串回傳（`Handler._send`） |

> **N/A 說明**：模板的 LCP/INP/CLS/TTI 針對「網路載入的互動式 Web 應用」；本專案報表是本機靜態檔、設計器是 localhost 內網頁，這些指標無網路變因可量。**未來前端整合建議值**：LCP < 2.5s、INP < 200ms、CLS < 0.1（沿用模板 §4 標準值即可）。

---

## 第 2 部分: 系統化分層

本專案沒有 SPA 分層，但三個實體可以對映到模板的五層，據實填寫：

| 層級 | 模板職責 | 本專案對應物 |
| :--- | :--- | :--- |
| 感知層 | 渲染 UI、視覺一致性 | 手寫 HTML＋CSS 變數令牌（見 §3）；設計器用原生 `<canvas>` 繪製櫃體 |
| 互動層 | 使用者輸入 | 報表頁：無（純閱讀）。設計器：原生 DOM 事件＋canvas `touch-action:none` 拖放；覆核頁：看圖點選後**批次純文字改 class**（改名寫回 SVG 標注檔） |
| 狀態層 | 全局/Server State | 報表頁：無狀態。設計器：單一 in-memory design 物件（JS const 常數表 `TYPES`/`PARTS`，板厚 `T=2` cm 等寫死於前端） |
| 通訊層 | API 呼叫 | 報表頁：無。設計器：原生 `fetch` POST JSON 至 `/api/dxf`（回 DXF 下載）、`/api/quote`（回 JSON 報價）、`/api/quote.csv`（回 CSV 下載）——詳見 [06 API 設計規範](./06_api_design_specification.md) |
| 基礎設施層 | 建置/測試/CI | **無前端建置工具**。HTML 內嵌於 Python 字串（`INDEX_HTML`）或手寫單檔；測試走 pytest（`tests/` 6 檔，涵蓋權重下載等後端邏輯，前端零覆蓋） |

> **路由器選型：N/A** —— 三個實體皆單頁無路由。**未來前端整合建議**：若採 React 則 React Router v7（或 Next.js App Router）；單一「上傳 PNG → 看房型結果」流程實際只需 1~2 條路由。

---

## 第 3 部分: 設計系統

### 設計令牌 (Design Tokens)

本專案沒有獨立 `tokens/` 目錄；令牌以 **CSS 自訂屬性**直接定義於 `recognition_report.html` 的 `:root`，深色模式在 `@media (prefers-color-scheme: dark)` 內整組覆蓋：

| 類別 | 定義位置 | 實際值（淺色 → 深色） |
| :--- | :--- | :--- |
| 表面/頁面色 | `recognition_report.html :root` | `--surface: #fcfcfb → #1a1a19`、`--page: #f9f9f7 → #0d0d0d` |
| 文字階層 | 同上 | `--ink: #0b0b0b → #ffffff`、`--ink2: #52514e → #c3c2b7`、`--muted: #898781`（兩主題共用） |
| 線條/邊框 | 同上 | `--grid: #e1e0d9 → #2c2c2a`、`--baseline: #c3c2b7 → #383835`、`--ring: rgba(11,11,11,.10) → rgba(255,255,255,.10)` |
| 序列色（圖表） | 同上 | `--s1: #2a78d6 → #3987e5`（我們的管線）、`--s2: #eb6834 → #d95926`（CubiCasa 對照） |
| 語意色（嚴重度） | 同上 | `--good: #0ca30c`、`--warning: #fab219`、`--serious: #ec835a`、`--critical: #d03b3b`、`--good-text: #006300 → #0ca30c` |
| 字體 | `body` 規則 | `system-ui, -apple-system, "Segoe UI", "Noto Sans TC", sans-serif`（系統字體，無字型檔載入） |
| 圓角/間距 | 各規則內 | tile/card 圓角 10px、badge 全圓 999px；間距為各處手寫 px 值（無 spacing scale） |

`cabinet_designer.py` 的內嵌 UI 有一套獨立樣式（`.pal`、`#stage`、canvas 佈局），與報表頁**未共用令牌**——兩者是各自自足的單檔。

### 元件分層 (Atomic Design)

**N/A（無元件系統）** —— 報表頁的可重用單位是 CSS class 慣例而非元件：`.tile`（KPI 磚，含 `.good`/`.warn` 變體）、`.card`（表格容器）、`.bar`（水平條圖，`i.ref` 對照色、`i.dim` 弱化）、`.badge`、`.flag`（`.crit`/`.good`）。這些 class 即本專案的「Atoms」。

**未來前端整合建議**：沿用報表頁既有令牌起步（色彩已通過明暗雙主題實測），元件庫可選 shadcn/ui；Atoms→Templates 分層待頁面數 ≥ 3 再引入，避免過度工程。

---

## 第 4 部分: 效能策略（量化）

### Core Web Vitals 目標

**N/A（本機靜態檔與 localhost 應用，無網路載入路徑）**。本專案對應的「效能」事實：

| 項目 | 現況 | 說明 |
| :--- | :--- | :--- |
| 報表頁重量 | 181 行單檔、0 外部請求、0 JS | 開檔即完成渲染；表格容器 `overflow-x: auto` 防版面位移 |
| 真正的效能瓶頸在後端 | CNN 推論（本機 Cody 為 torch CPU 版，無 GPU） | 前端整合時「丟 PNG→出房型」的等待時間由 `floorplan2room.py` 推論主導，非前端渲染 |
| 快取策略 | `cubicasa/room/*_mask.npz` 語意快取 137 檔 | 既有考卷走版控快取不觸發推論/下載——這是本專案的「API 快取」對應物 |

**未來前端整合建議值**：LCP < 2.5s、INP < 200ms、CLS < 0.1；推論屬長任務，建議前端以非同步任務＋進度回饋處理（先顯示 chk 疊圖縮圖，再補房型結果），並沿用 npz 快取避免重複推論。

---

## 第 5 部分: 技術可用性（量化標準）

### 響應式設計斷點

報表頁不採固定斷點，而是**內容驅動的流式佈局**（實際存在的機制）：

| 機制 | 位置 | 行為 |
| :--- | :--- | :--- |
| `viewport` meta | `recognition_report.html` head | `width=device-width, initial-scale=1` |
| KPI 磚流式換行 | `.tiles` | `grid-template-columns: repeat(auto-fit, minmax(190px, 1fr))`——寬度不足自動降欄 |
| 內容寬度上限 | `.wrap` | `max-width: 980px` 置中 |
| 寬表格橫向捲動 | `.card` | `overflow-x: auto`（條圖欄 `min-width: 220px`） |

**未來前端整合建議**：採模板五斷點（xs<576 / sm≥576 / md≥768 / lg≥992 / xl≥1200），平面圖檢視區在 md 以下改直向堆疊。

### 無障礙 (A11y)

現況（據實盤點，未跑過自動檢測）：

- 已具備：`lang="zh-Hant"`、語意化表格（`th`/`td`）、系統色偏好支援（`color-scheme` + `prefers-color-scheme`）、條圖附 `title` 文字值、數字欄 `tabular-nums`
- 未驗證：色彩對比度未以工具實測（`--muted #898781` 於兩主題的對比比值待確認）；條圖為純視覺、依賴同列數字欄作文字替代；無 ARIA 標籤（純靜態內容需求低）
- 設計器 canvas 介面**無鍵盤替代操作**——未來若對外提供需補

**未來前端整合建議**：WCAG 2.2 AA、axe-core 自動檢測進 CI、對比 ≥ 4.5:1（一般文字）/ 3:1（大字）。

### 國際化 (i18n)

**N/A（單語系）** —— 全專案 UI 與文件為繁體中文（`zh-Hant`），使用者為內部團隊，無 i18n 工具。**未來前端整合建議**：若需求出現再引入 next-intl / react-intl；日期數字用 Intl API。

---

## 第 6 部分: 工程化實踐

### 專案 file 組織

**N/A（無 `src/` 前端目錄樹）** —— 前端相關檔案的實際落點：

```
RoomPilot-Agent/
├── recognition_report.html   # 產出型報表（進版控，隨版更新）
├── cabinet_designer.py       # 內嵌 INDEX_HTML 的本機 Web 設計器
├── review.html               # 標注覆核臨時頁（工作檔，未進版控）
├── json/                     # 前端交接 JSON（每圖一份：scale 區塊＋walls/windows/doors px+cm 雙座標）
├── training/chk/{gray,color,room}/  # 檢核疊圖 PNG（前端可直接引用的視覺產物）
└── dxf_scale/                # 公分單位 DXF（前端請讀 json 的 "dxf_scale" 欄位，"dxf" 欄位已移除）
```

完整目錄規範見 [08 專案結構指南](./08_project_structure_guide.md)。

### 程式碼品質

- Linter/TypeScript：**N/A**（無 Node 工具鏈；HTML/CSS/內嵌 JS 為手寫，無 lint）。未來前端整合建議：ESLint + Prettier + TypeScript strict、禁 `any`（與 `.claude/rules/coding-style.md` 一致）
- 提交規範：沿用全專案 `.claude/rules/git-workflow.md`——`<type>(<scope>): <subject>`＋WHY/WHAT/IMPACT body（報表更新實例：`cubicasa/room/ 語意快取…四報表＋recognition_report.html 同步`）
- 分支：分支即機器（main/cody/bella/ben/ancai/django/kai-dev），經 main PR 匯流；先開分支鐵律見 `.claude/rules/development-workflow.md`

### 測試策略

| 類型 | 現況 | 說明 |
| :--- | :--- | :--- |
| 單元（後端） | pytest，`tests/` 6 檔 | 涵蓋 `_ensure_cc_weights` 權重下載（7 例）等；換機驗收標準「pytest 應 13 全綠」 |
| 前端單元/元件 | **無** | 報表頁 0 JS 無可測邏輯；設計器內嵌 JS 未測（早期入口，非現行重點） |
| E2E | **無**（前端） | 專案的「E2E」對應物是評測守門 harness：`scripts/eval_*.py` 對 `Identify_ans/pngans/` 跑分，改 chk/dxf 邏輯前必先評分、不得退化後覆蓋 |
| 視覺回歸 | **無** | 報表數字正確性靠與 `json/eval_rooms/*.json` 逐版核對 |

**未來前端整合建議**：Vitest（單元 80%+，依 `.claude/rules/testing.md`）＋ Playwright（關鍵旅程：上傳 PNG → 顯示房型結果）。

---

## 第 7 部分: 前後端協作（技術面）

### API 通訊規範

本專案無 REST 後端；前後端交接走**檔案契約**與**本機端點**兩條路（詳細契約見 [06 API 設計規範](./06_api_design_specification.md)）：

1. **檔案契約（主要）**：`json/` 每圖一份前端交接 JSON
   - `scale` 區塊：`cm_per_px`、`method`（wall_min/config）、`confidence`（high/medium/low——門寬交叉檢核 70~110cm）、`doors_used`、`outer_wall_px`、`outer_wall_cm`、`wall_min_cm`、`median_door_cm`
   - `walls`/`windows`/`doors`：**px（影像座標）與 cm（同 dxf_scale，原點左下、y 向上）兩套座標並列**——前端免自行換算
   - 破壞性變更前例：`"dxf"` 欄位已移除，前端一律改讀 `"dxf_scale"`
2. **本機端點（設計器）**：POST JSON → `/api/dxf`（`application/dxf` 附件下載）、`/api/quote`（JSON）、`/api/quote.csv`（CSV 附件）；404/500 純文字錯誤

- OpenAPI 型別自動生成：**N/A**（無 OpenAPI 定義）。未來前端整合建議：以 JSON Schema 固定 `json/` 交接格式後生成 TypeScript 型別

### 認證與授權

**N/A（無使用者系統、無 Token 機制、無路由守衛）** —— 本專案唯一的「認證」是部署面的 `GITHUB_TOKEN`（PAT，密碼等級秘密）：

- 用途：私有 repo 期間，`floorplan2room.py` 的 `_ensure_cc_weights` 自動從 GitHub Release `weights-v5` 下載 200MB 權重＋SHA-256 校驗（`b7a280d2…f4cf`）
- 規則：**只放環境變數，勿進版控、勿進前端程式碼**；repo 轉 public 後連 token 都不需要
- **未來前端整合鐵律**：權重下載屬伺服器端行為，`GITHUB_TOKEN` 絕不可打包進瀏覽器端 bundle 或存 localStorage

---

## 第 8 部分: 監控與安全

### 前端監控

**N/A（本機檔案與 localhost 應用，無遙測需求與管道）**。本專案對應物：品質監控走評測守門 harness（`scripts/eval_*.py` → `json/eval_rooms/report*.json`），報表頁即「監控儀表板」的人讀版。未來前端整合建議：web-vitals 收集＋Sentry 錯誤邊界。

### 前端安全

依 `.claude/rules/security.md` 逐項對現況盤點：

- [x] XSS：報表頁無使用者輸入、無 JS；設計器 `innerHTML` 組裝的內容來自前端自身常數表與後端報價計算，無跨使用者輸入面（僅本機單人使用）
- [x] 網路暴露面：設計器 server 明確綁 `127.0.0.1`（非 `0.0.0.0`），不對外
- [x] 秘密管理：`GITHUB_TOKEN` 只走環境變數；權重檔 SHA-256 校驗防供應鏈替換
- [x] 敏感資料不存 localStorage：現況無任何 localStorage 使用
- [ ] CSRF：N/A（無 cookie、無跨站狀態）
- [ ] 依賴掃描：無 npm 依賴可掃；Python 側依 security.md 定期 `pip audit`（opencv 鎖 `>=4.10,<5` 防 5.0 破壞性變更）
- [ ] SRI：N/A（零 CDN 資源，單檔自足——這本身就是最強的 SRI）

**未來前端整合追加**：上傳 PNG 需驗檔案類型/大小上限（系統邊界輸入驗證）；若設計器改對外服務，`innerHTML` 全面改參數化渲染＋CSP。

---

## 第 9 部分: 技術上線檢查清單

模板原清單多數項目（TypeScript strict、覆蓋率 80%、五斷點、Bundle 預算）對現況 N/A；以下是**本專案實際適用**的「報表/前端產物出貨清單」：

- [ ] 報表數字與 `json/eval_rooms/` 最新評測報表逐項一致（v2.16 基準：灰牆 F1 0.99、灰窗 96/96、彩牆 87.7/94.9、**彩窗 P62/R38**、切割 76.4%、命名 own 尺 0.788）
- [ ] 明/暗兩主題皆目視驗收（`prefers-color-scheme` 切換）
- [ ] 單檔自足：0 外部請求（無 CDN/字型/圖片外連）
- [ ] 窄螢幕驗收：KPI 磚降欄、寬表格容器內橫捲、頁面本身無橫向捲軸
- [ ] 評測鐵律已遵守：產生報表數字的管線改動前後皆跑過 `scripts/eval_windows.py` 等對 `Identify_ans/pngans/` 評分，無退化
- [ ] `json/` 交接格式若有欄位增刪，已在 Readme 變更紀錄標記（前端讀取端同步）
- [ ] Commit 符合 WHY/WHAT/IMPACT；Code Review 通過（`.claude/rules/git-workflow.md`）

**未來前端整合時**，再啟用模板完整清單：TypeScript strict 無錯誤、覆蓋率 ≥ 80%、五斷點覆蓋、axe-core WCAG 2.2 AA、Core Web Vitals 達標、Bundle 預算。
