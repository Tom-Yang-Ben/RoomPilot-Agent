# RoomPilot 現行版本總覽(單一事實來源 / SSOT)

> **這份文件是 RoomPilot 專案的唯一事實來源(Single Source of Truth)。**
> 老師版、組內版、簡報、PRD、Demo 腳本,都從這份拆出去。有衝突時,以本文件為準。
>
> 版本:v1.9 ・ 更新日期:2026-07-04 ・ 維護者:組長(楊本顥)・ Demo 死線:**2026-08-20**
>
> 本文件已吸收並取代過去散落的提案、開發包與進度文件(原檔已打包歸檔)。
> **主軸 = Python / FastAPI 專案 repo `RoomPilot-Agent`。** 早期純前端原型 `2Dto3D.html`(AI Interior Copilot)保留為「3D 直接操作 UX 的靈感來源」,存於 docs 資料夾,**非 code 主線**。

---

## ✅ 0. 核心決策

### 0.1 AI 核心 = A 風格生成(已定案 2026-07-01)

**AI 核心 = A 風格生成(`render_style`)。** 全隊已定案:以 depth/ControlNet 即時換風格為專案主軸與對外定位;B 風險檢查降為 **P1/P2 加分**;C 的「風格預覽」作為 P0 保底(見下)。

| 選項 | 狀態 | AI 核心 | 定位 |
|---|---|---|---|
| **A 風格生成** | ✅ **主軸(已定案)** | `render_style`(depth/ControlNet 即時換風格) | 最炫、最符合原始定位;最高風險,楊舒媁主責(★ 建議兩人 pair,見 11.2) |
| **B 風險檢查** | ⬇ **降 P1/P2 加分** | 規則引擎檢查(擋門/碰撞/動線)+ Agent tool use | 引擎已有碰撞/門牆判斷可接,包裝成本低;A 不穩時可撐場面(見 5.2) |
| **C 折衷** | 🛟 **併入 A 作為 P0 保底** | 配置 + 即時**風格預覽** + 基本風險檢查 + Agent 編排 | 對外主打 A,但 P0 底線=示意預覽+預生成備援,確保 Demo 不垮 |

> **風險擺法(重要):** A 是「最高風險、原本沒做」,配置/微調引擎反而「已做、穩」。因此對外主打 A,但 **P0 一定交得出來的地板=風格示意預覽(demo_app 已有 stub 保底)+ 預生成備援圖**;live ControlNet 生成當 W5 攻堅目標(成了最好,沒成有地板撐 Demo)。詳見 5.1 F4 與 6.3。

### 0.2 輸入格式與兩個 P0 邊界(已定案 2026-07-04)

- **輸入格式:先支援乾淨的 DXF 向量檔(最小可行)。** PNG / PDF 掃描圖辨識列「這條路跑通、時間允許再加」——不在第一版必做。
- **「輸出提案檔案」進 P0(新增 F9)。** 使用者調整完後,能匯出一個檔案(建議 `.glb` 3D 場景 / 也可 DXF / 提案 PDF)拿給室內設計師或屋主。原本只列 P1,現升為 P0。
- **「3D 直接拖曳搬家具」進 P0(併入 F6)。** 除了自然語言微調,3D 場景要能用滑鼠直接拖曳搬動家具(Blender 式直接操作),含碰撞檢查。

---

## 1. 專案基本資料

| 項目 | 內容 |
|---|---|
| 專案名稱 | RoomPilot — 室內設計即時提案溝通 Agent |
| 班級 / 組別 | 資展國際 Python AI 應用工程師就業養成班 ・ AIPE03 第四組 |
| 組長 | 楊本顥 |
| 組員 | 蘇立凱、蔡承安、林柏彥、陳峙宏、楊舒媁、鄭典 |
| 專案期間 | 2026/06/23 → 2026/08/20(8 週) |
| **主軸 code repo** | **`RoomPilot-Agent`(Python / FastAPI 多模組)** — 見第 10 節模組地圖 |
| 早期原型(靈感來源) | `2Dto3D.html`(純前端 three.js 0.149)—— 貢獻「3D 直接操作」UX,存 docs 資料夾,非 code 主線 |
| 規劃技術棧(目標態) | three.js(前端 3D)、FastAPI + Python + Shapely、LLM function-calling Agent、影像生成(ControlNet/depth)、RAG + 向量庫、PostgreSQL |
| 現況技術 | FastAPI 後端骨架已存在(`web_fastapi`、`demo_app`)、Shapely 家具引擎已完成並測試、three.js 3D viewer 有殼;**尚未整合成單一端到端流程**(見 7.2、10) |

---

## 2. 定位與不做的事

**一句話定位:** 即時提案溝通平台。把使用者的平面圖與需求,在幾分鐘內變成可即時換風格、調軟裝、可匯出的 3D 提案畫面,讓設計師與客戶快速對齊想像。

**明確不是(Out of Scope):**

- 不取代 AutoCAD / 3D Max 施工圖。
- 不做純炫技、無法驗證的 AI 生圖(避免視角幻覺、空間不一致)。
- 不做硬裝(天花板/管線/結構)、不做水電消防法規。
- 不做任意 CAD/PDF 全自動解析(**第一版只吃乾淨 DXF**;PNG/PDF 辨識列後續)。
- 不追求寫實渲染與任意角度生圖。

---

## 3. 目標使用者與痛點

| 使用者 | 痛點 / 價值 |
|---|---|
| 室內設計師 | 快速生成提案草圖、取代繁瑣建模、提升提案效率 |
| 一般客戶 / 屋主 / 租客 | 把「講不清楚想要什麼」具象化,降低溝通障礙 |
| 專題評審 / 老師 | 看到 AI Agent 如何解決真實設計流程問題 |

**關鍵痛點:** ① 看平面圖想像不出實際空間;② 設計師建草圖耗時、案前常漏問需求;③ 客戶難用文字精準表達;④ 一般 AI 生圖有視角幻覺、保不住空間結構,不能當提案依據。

---

## 4. 核心流程(主線)

```
Agent 對話(先問清需求 → 收成 client_brief JSON;訪談式追問為 P1)
  → 上傳平面圖(先 DXF)→ 空間升維 3D 白模(可旋轉縮放)
  → 配置軟裝(真實尺寸)
  → 自然語言換風格 / 微調家具(同一個 Agent 規劃並呼叫工具)
      ┌ 微調兩種方式:自然語言指令 或 3D 直接拖曳搬家具(含碰撞檢查)
  → 風格化提案畫面
  → 多輪迭代
  → 輸出提案檔案(.glb / DXF / PDF)給設計師 / 屋主
  → Demo Mode fallback(任一步失敗不中斷)
```

**兩個關鍵設計:** ① 用**同一個 Agent 對話**統一收集需求與接指令(取代單獨的靜態問卷)——因為「填需求」和「下指令」的使用者輸入幾乎一樣,合成一個對話介面:先問清人數/預算/風格/材質/機能/禁忌收成 `client_brief`,再驅動生成(解掉「使用者不會下 prompt」);② 資料關聯簡化(家具直接掛 project,免中間表,另存一張 `CLIENT_BRIEF`)。

---

## 5. 功能範圍

### 5.1 P0 必做(逐功能 + 驗收)

> **F0 案前需求問卷已併入 F3(Agent 對話編排)**——因為「填需求」與「下指令」的使用者輸入幾乎一樣,合成同一個 Agent 對話介面。

| 代號 | 功能 | 驗收標準 | 主責 | 現況 |
|---|---|---|---|---|
| F1 | 上傳平面圖(**先 DXF**) | 預覽、辨識牆線(+門/窗)、綁 project;重開仍在 | 平面辨識(陳峙宏) | 🟢 `floorplan2dxf.py` 牆+門窗偵測已實作;窗 精準89%/召回91%、門 過濾~100% |
| F2 | 空間升維 `upgrade_to_3d` | 解析牆/開口 → 白模;與平面圖大致一致;可旋轉縮放 | 平面辨識+升維 | 🟠 **已有但未整合**:柏彥(yen 分支)`dxf_parser.py` 已做 DXF→3D;待 merge 進來並和 `Room` 對齊 |
| F3 | Agent 對話編排(含案前需求問卷 → `client_brief`) | ① 對話收集需求 → 產生合法 `client_brief` JSON(缺漏會追問);② 一句多動作指令能拆解依序執行;失敗 fallback | Agent 核心(林柏彥) | 🔴 未做(僅 `demo_app/agent_stub.py` 規則式佔位) |
| F4 | 空間風格生成 `render_style` 🔥 | **P0 地板:**風格示意預覽 + 預生成備援圖可即時套用。**W5 攻堅:**depth/ControlNet 條件生成,風格可辨、結構一致、單一視角、1~2 風格(成了最好,沒成有地板撐 Demo) | render_style ★(楊舒媁) | 🔴 未做(僅 `demo_app/render_style_stub.py` PIL 示意佔位) |
| F5 | 基礎配置 `place_furniture` | 依需求放真實尺寸軟裝;尺寸正確、不超出空間、不重疊 | 家具邏輯(蔡承安) | 🟢 **已完成 & 25 測試通過**(`furniture_engine`) |
| F6 | 軟裝微調 `adjust_furniture`(**自然語言 + 3D 直接拖曳**) | 對應指令**或滑鼠拖曳**正確調整位置/角度;含碰撞檢查;可多輪 | 家具邏輯(蔡承安)+ 前端(拖曳) | 🟡 幾何/自然語言側**已完成**(軸分離 move);**3D 直接拖曳前端待做** |
| F7 | 提案畫面 + 多輪迭代 | before/after + 對話;可繼續追問即時看到變化 | 前端(楊本顥) | 🟡 `web_fastapi` 有 compare(before/after)頁雛形,未接引擎 |
| F8 | Demo Mode fallback | AI/生成/網路任一失敗主線不中斷 | 後端(蘇立凱)+前端(組長統籌) | 🔴 未做(demo_app 的 stub 可視為雛形保底) |
| **F9** | **輸出提案檔案**(新,P0) | 調整完的 3D 場景可**匯出檔案**:建議 `.glb`(three.js GLTFExporter,設計師可直接開)/ 也可 DXF / 提案 PDF | 前端(楊本顥)+ 後端(蘇立凱) | 🔴 未做 |

### 5.2 P1 加分

- **B 風險檢查(擋門/碰撞/動線)+ Agent tool use** —— 引擎已有碰撞/門牆判斷,包裝成本低;A 當天不穩時可撐場面(對應第 0 節 B 降級)。
- **PNG / PDF 平面圖辨識**(第一版只吃 DXF,這條列「DXF 跑通後、時間允許再加」)。
- 訪談 Agent(會追問)、更多風格/家具、多方案配置、**更多匯出格式**、eval harness(風格符合度/結構保真度/收斂步數)。

### 5.3 Out of Scope

見第 2 節。另:照片多模態輸入、9 步工作流、12,000+ 家具、一鍵下單導購、多視角/漫遊 = **未來展望,不在 8/20 P0**。

---

## 6. AI Agent 與四大引擎

### 6.1 Agent 與工具分離(為什麼算 Agent)

四大引擎是 **Agent 呼叫的工具,不是 Agent 本身**。一句含多動作的指令(例:「換成日式無印風,沙發往窗邊移」)會被 Agent 拆成多次工具呼叫並迭代——這才是 agent 編排,不是單次生圖。

### 6.2 四大引擎(= Agent 的工具)+ 現況

| 引擎 | 工具名 | 做什麼 | 現況 |
|---|---|---|---|
| 空間升維 | `upgrade_to_3d` | 2D 平面圖 → 簡化 3D 白模(牆/地板/開口) | 🟠 柏彥已做 `dxf_parser`(DXF→3D,ezdxf+shapely),**未整合進 ben** |
| 基礎配置 | `place_furniture` | 依需求放真實尺寸軟裝家具 | 🟢 已完成 & 測過 |
| 空間風格生成 🔥 | `render_style` | 固定 3D 結構下換風格(depth → ControlNet 條件生成 → 一致性後處理) | 🔴 未做(stub 保底) |
| 軟裝微調 | `adjust_furniture` | 自然語言/拖曳調家具位置/數量,重繪 | 🟢 幾何已完成(軸分離 move + 碰撞) |

> 介面契約已部分落地:`furniture_engine/schema.py` 定義了 `PLACE_FURNITURE_TOOL` / `ADJUST_FURNITURE_TOOL`(給 LLM function-calling 用);`demo_agent_flow.py` 已草擬 id 規則(`{type}_{流水號}`)與失敗訊息詞彙表,供 Agent(柏彥)對介面。

### 6.3 風格生成管線(最高風險,先想清楚)

`固定視角渲染 → 取 depth/輪廓 → ControlNet 條件式生成 → 一致性後處理`。
此管線維持空間結構、避免視角幻覺。**先鎖定:單一視角 + 1~2 風格 + 1~2 範例空間跑穩。**

> **⚠️ 落地方式待定(W2 spike 前決定,影響成本/延遲/可行性):** ControlNet 生成要跑在哪?
> - **選項一:託管 API(Replicate / HuggingFace Inference / fal.ai)** —— 免自架 GPU、上手快,但**逐張生成有成本、有延遲**,需估算 Demo 呼叫量。
> - **選項二:本地 / Colab GPU** —— 無 per-call 費用,但需 GPU 環境、模型下載與環境維護。
> 未決前,F4 的 P0 地板(示意預覽 + 預生成圖)不受影響;live 生成的路線在 W2 spike 拍板。此項的成本風險已列入第 13 節。

---

## 7. 技術架構與選型

### 7.1 規劃架構(目標態)

- **前端:** three.js(上傳、3D 白模、可旋轉縮放、直接拖曳搬家具、提案畫面、匯出)
- **後端:** FastAPI + Python + Shapely(API、2D 幾何升維、配置引擎、非同步任務)
- **AI:** LLM function-calling Agent + 四工具引擎;影像生成服務(ControlNet/depth);RAG + 向量庫
  - **API 金鑰 / 成本 / rate limit 管理:** LLM 由 Agent 核心 owner 統一控管;影像生成(ControlNet)成本視 6.3 落地方式而定。兩者的成本風險見第 13 節。
- **資料:** PostgreSQL + 檔案儲存;Redis 快取(後期);OCR(後期)
- **自己做:** Agent 編排與 tool routing、2D 幾何升維、配置邏輯、結構約束生成整合管線、RAG、會話與迭代、eval、前後端、API、DB schema、Demo 可靠性、檔案匯出。
- **用模型/API:** LLM、影像生成模型、向量庫。

### 7.2 現況(目標態 vs 實際 repo,務必誠實)

> 主軸已是 Python/FastAPI。下表比對「規劃目標態」與「`RoomPilot-Agent` repo 實際狀態」。

| 面向 | 規劃(目標態) | 現況(實際 repo) |
|---|---|---|
| 前端 | three.js 完整編輯器 | **兩個 3D 前端**:舒媁 `web_fastapi/viewer.js`(載 GLB 家具)、柏彥 `app/` React Three Fiber(擠出 DXF 牆、X-ray,**未整合**);皆未接引擎;`demo_app` 有 2D 骨架 |
| 後端 | FastAPI + DB,完整整合 | FastAPI **骨架已存在**(舒媁 `web_fastapi`、柏彥 `app/backend`、`demo_app`);**尚未整合成單一持久化流程**;`web_fastapi` 有匯入 bug(缺 moodboard_assets 等) |
| 升維 | Shapely 後端 `upgrade_to_3d` | 🟠 柏彥(yen 分支)`dxf_parser` **已做**(ezdxf+shapely,DXF→3D、牆體聯集、房間=孔洞),**未 merge**;demo 暫時寫死 5×4 |
| 平面辨識 | 牆/門/窗 | 🟢 `floorplan2dxf.py`:牆(強)+ 門/窗偵測 + `eval_doors/windows`(pass rate 待確認) |
| 配置 | 後端工具 | 🟢 `furniture_engine.place_furniture` **真實 & 25 測試通過** |
| 微調 | 自然語言 + 直接拖曳 | 🟡 `adjust_furniture` 幾何**已完成**;3D 直接拖曳前端待做 |
| 風格 | `render_style`(AI 生成) | 🔴 未做(`demo_app/render_style_stub.py` 示意佔位) |
| Agent | LLM function-calling | 🔴 未做(`demo_app/agent_stub.py` 規則式佔位);tool schema 已在 `schema.py` |
| 輸出 | .glb / DXF / PDF 匯出 | 🔴 未做 |
| 型錄/素材 | GLB + 風格標籤 → Postgres | 🟡 `scripts/`(GLB 下載、型錄合併、Postgres 匯入)已有;風格化選家具未接 |

> **走通骨架 `demo_app`**:已把「一句話 → Agent(stub)→ `place_furniture`(真)→ `render_style`(stub)」串成端到端可跑的 Demo,用來對老師展示架構與真進度。正式版把 stub 換真、把 demo 寫死的房間換成 DXF→Room 即可。

---

## 8. 資料結構

- **`client_brief`(需求檔,JSON):** 人數、孩童/長者/寵物、預算、風格偏好、色系、材質、機能(收納/在家工作/招待)、禁忌。問卷產出,驅動後續生成。
- **平面圖辨識輸出:** 牆段線段(座標)。DXF(第一版)收斂成「牆段」格式,餵進升維管線;PNG/PDF 之後也收斂到同一格式。
- **資料庫(現行設計):** `PROJECT 1—N FURNITURE`(已放置家具實例直接掛 project_id,免中間表)+ `CLIENT_BRIEF`(1—1 PROJECT)。等做採購型錄再考慮加中間表。
- **Furniture 屬性(已放置實例):**
  - **型錄屬性:** type / name / size(w·d·h)/ color / style / price /(glb 路徑),細節存 json。
  - **⚠️ 擺放屬性(必要):** `pos_x` / `pos_y` / `rotation`(+ 需要時 `pos_z`)—— F5/F6 算出的座標與朝向。**沒有這幾欄,配置算得出來卻無處存,重開就回不到原狀。**(對應 `schema.py` 的 `placed_to_dict` 輸出格式。)
- **型錄 vs 實例(P1 做採購型錄時分家):** MVP 一張表兼「型錄描述 + 擺放座標」;做採購型錄再拆 `furniture_catalog` 與 `furniture_instance`。

---

## 9. 平面圖辨識(現行真實能力)

離線、不需 LLM。第一版主吃 **DXF**;`floorplan2dxf.py` 亦支援 PNG(影像)→ DXF。

> **⚠️ 目前狀態(2026-07-04 由 code 確認):牆體辨識完整;門、窗偵測已實作(`detect_doors` / `detect_windows` / `_has_door_swing`)並有評測腳本(`eval_doors.py` / `eval_windows.py`,TP/FP 對答案)。** 實際 pass rate(cody 分支):**窗 精準 89% / 召回 91%**(78 對 / 6 誤 / 8 漏)、**門 過濾 ~100%**;牆:門:窗 權重 5:4:3。(SSOT 舊版誤記「門窗未完成」,已更正。)

- **DXF:** 解析 LINE / LWPOLYLINE / POLYLINE / ARC / CIRCLE / MLINE,容忍多種圖層命名 → 生**牆體**;門用 L 形+弧偵測,窗用開口覆蓋率偵測。
- **影像(PNG,列 P1):** 灰階二值化 → 形態學 → 牆遮罩向量化 → 抽中線 → 強制正交輸出 DXF,再走同一建牆管線。
- **驗證資料:** `png/`(20 張測試圖)、`pngans/`(答案)、`chk/`(輸出)、`door/`(19 門樣式)、`dxf/`(29 個 DXF)。

**限制:** 圖片無真實單位,房間以名目比例生成,需用「實際尺寸 → 重建」校正;牆以軸向(水平/垂直)為主,斜/弧牆會掉。**升維(DXF→Room)這條把牆段變成引擎能吃的 `Room` 尚未接上(F2 缺口)。**

---

## 10. 實際 repo 現況快照(`RoomPilot-Agent`,2026-07-04)

> 主軸 = Python/FastAPI code repo。以下是各模組真實狀態。

### ✅ 已完成(真實產出)

- **`furniture_engine`(蔡承安 / ancai)** 🟢:`place_furniture` / `adjust_furniture` / 碰撞 / 淨空,**25 個 pytest 全過**;`schema.py` 有 LLM tool schema;`demo_agent_flow.py` 有介面範例。
- **`floorplan2dxf.py`(陳峙宏 / cody)** 🟢:DXF/PNG → 牆體(強)、**門/窗偵測 + eval**(窗 精準89%/召回91%、門 過濾~100%)。
- **升維 `dxf_parser.py` + 3D 場景(林柏彥 / yen)** 🟠 **未整合**:DXF→3D 樓面 JSON(ezdxf+shapely、牆體聯集、房間=孔洞、單位處理)+ FastAPI 可上傳解析 + React Three Fiber(擠出牆、X-ray)。**孤立在 yen 分支,沒 merge 進 ben。**
- **Web 前端 + GLB 3D 檢視(楊舒媁 / bella)** 🟢:`web_fastapi` + `viewer.js`(three.js + OrbitControls + GLTFLoader 載 GLB);styles / library / compare / scene 頁。
- **型錄管線 `scripts`(蘇立凱 / 鄭典)** 🟢:IKEA GLB 下載、JSON 合併/清洗/驗證、**匯入 PostgreSQL**。
- **走通骨架 `demo_app`(本次工作階段,⚪ 未 commit)**:一句話 → stub Agent → 真引擎配置 → stub 風格,**端到端可跑**;展示架構用,非組員模組。

### 🟡 做一半 / 有殼未接

- **`web_fastapi`** viewer **未接 `furniture_engine`**(只是家具/模型檢視器),且有匯入 bug(缺 moodboard_assets、metadata json)。
- **3D 直接拖曳搬家具**:`viewer.js` 目前只有 OrbitControls(轉視角),**無直接拖曳編輯**(直接操作 UX 只存在 docs 的 `2Dto3D.html`,待移植到 three.js 前端)。
- **持久化 / DB 串接**:script 能匯入 Postgres,但 app 尚未真正讀寫、儲存配置結果。

### 🔴 尚未存在(全分支 0 命中,真的沒開始)

- **F3 自然語言 Agent**(LLM function-calling / tool routing / 指涉解析)+ 案前問卷 → `client_brief`。
- **F4 AI 風格生成 `render_style`**(ControlNet/depth;最高風險)。
- **F9 檔案匯出**(.glb / DXF / PDF)。
- **F8 一鍵 Demo Mode**、正式 API/DB 整合、RAG。

> ⚠️ **多數不是「缺口」而是「沒接起來」**:升維(柏彥)、辨識(峙宏)、引擎(承安)、3D 前端(舒媁+柏彥)都存在,只是各自孤島。**最該做的是整合**——尤其把柏彥的 `app/`(升維+3D)撈進來、和 `Room` 對齊。詳見《完整現況盤點》。

### 🔁 早期 `2Dto3D.html`(docs)可移植的優點

| 優點 | 狀態 |
|---|---|
| 3D **直接拖曳搬家具** + 碰撞沿牆滑動 | ⏳ 待移植到 three.js 前端(F6/F2) |
| DXF/影像牆體辨識 | ✅ 已由 `floorplan2dxf.py`(Python)取代並強化 |
| 手動放門窗、材質風格預覽 | ⏳ 概念可參考,重點放在 F4 AI 生成 |

---

## 11. 團隊分工

### 11.1 現行工作分組

- **平面辨識 + 升維:** 陳峙宏 —— 牆體+門窗辨識(已可,pass rate 待確認);**下一棒:DXF→Room 升維(F2 缺口)**,建議與後端(蘇立凱)協作。
- **家具引擎:** 蔡承安 —— `place_furniture` / `adjust_furniture` 已完成;下一步支援更多家具類型與間距規則。
- **家具素材/型錄:** 鄭典 —— 家具 GLB + 尺寸 + 風格標籤,餵 viewer 與風格配置。

### 11.2 工作分工(8 區塊)

> ★ `render_style` 最關鍵,務必兩人 pair;8 區塊 7 人,部分需身兼。

| 區塊 | 主責 | 關鍵交付 | 副手 |
|---|---|---|---|
| 組長 / 整合 | **楊本顥** | 每週可跑版、W6 凍結檢查、5 分鐘連跑統籌、Demo 可靠性、走通骨架 | ＿＿ |
| Agent 核心 + 編排 | **林柏彥** | F3:對話編排(含案前需求問卷)→ 收 `client_brief` + 多動作指令拆解;用 `schema.py` tool schema | 陳峙宏 |
| 風格生成 `render_style` ★ | **楊舒媁** | F4:depth/ControlNet 條件生成、一致性後處理(接 `render_style_stub` 的介面) | 蔡承安 |
| 平面辨識 + 升維 | **陳峙宏** | F1 牆/門/窗辨識(已可)+ **F2 `upgrade_to_3d`:DXF→Room 白模** | 蘇立凱 |
| 家具邏輯(引擎) | **蔡承安** | F5/F6:`place_furniture`、`adjust_furniture`、碰撞/淨空(✅ 已完成,持續擴充) | 林柏彥 |
| 家具素材(餵 DB) | **鄭典** | 找家具、2D 圖轉 GLB、匯入型錄、家具尺寸表、風格標籤 | 蘇立凱 |
| 後端 / API / DB / RAG | **蘇立凱** | API、DB(型錄 + `client_brief` + 配置結果)、Demo Mode fallback、**F9 匯出**、RAG(P1) | 鄭典 |
| 前端 / 對話 UI / 3D | **楊本顥** | 對話 UI、提案畫面、多輪迭代、**3D 直接拖曳(F6)**、**F9 匯出前端**、merge 整合、QA | ＿＿ |

**配置原則:**

- ★ `render_style` 最高風險,務必兩人 pair、優先敲定。
- 配置屬引擎「算」、家具素材屬「餵」、DB 屬「存」——三者分開。
- `client_brief` 三方接力:Agent 定 schema + 對話收集 → 前端做對話 UI → 後端存,組長對齊介面。
- **⚠️ 組長負載提醒:** 組長同時兼整合+前端+3D 拖曳+匯出+merge+QA,W6/W8 衝刺期會搶時間。必要時把前端某塊(如提案畫面/多輪迭代)下放副手,讓組長專注整合與可靠性。

---

## 12. 開發時程(8 週)

| 週 | 期間 | 里程碑 |
|---|---|---|
| W1 | 6/23–6/29 | 合約對齊 + 骨架:`client_brief` schema、四工具 stub、API mock、前端路由 |
| W2 | 6/30–7/6 | 引擎(配置/微調)已完成;走通骨架 `demo_app` 端到端可跑;**🔥 `render_style` 可行性 spike + 落地方式拍板(6.3)** |
| W3 | 7/7–7/13 | **F2 升維:DXF→Room 接上**(取代寫死房間);真實 DB + API + 會話;前端串真 API |
| W4 | 7/14–7/20 | Agent 編排串通 + `client_brief` 餵入 prompt;一句指令可拆步驟;**3D 直接拖曳(F6)** |
| W5 | 7/21–7/27 | 🔥 **風格生成攻堅**:`render_style` 單一視角穩定出圖(1~2 風格) |
| W6 | 7/28–8/3 | 微調 + 迭代 + **F9 匯出**;**端到端主線跑通 + 凍結檢查(7/31~8/3)**,未過砍加分項 |
| W7 | 8/4–8/10 | 整合測試 + Demo Mode(三種 fallback)+ 基本 eval |
| W8 | 8/11–8/20 | 簡報/講稿/QA/備援;連跑 ≥5 次 5 分鐘內無誤;**8/20 發表** |

---

## 13. 風險與對策

| 風險 | 影響 | 對策 | 負責 |
|---|---|---|---|
| 風格生成一致性(最高) | 提案畫面不可信 | 收斂單一視角+1~2 風格;P0 保底=示意預覽+預生成圖;W2 spike 早驗證 | render_style ★ |
| **生成算力 / 成本(ControlNet)** | 做不起來 / 燒錢 | W2 spike 決定託管 API vs 本地 GPU;估 Demo 呼叫量;P0 用預生成圖不依賴 live 算力 | render_style ★ |
| **LLM API 成本 / 金鑰 / rate limit** | 超支 / 中斷 | Agent 核心 owner 統一控管 key 與用量;設呼叫上限;Demo Mode 用固定回應 | Agent 核心 |
| **F2 升維(DXF→Room)沒接上** | 只能用寫死房間、辨識與引擎串不起來 | W3 優先做;先用 1~2 個乾淨 DXF 跑通 | 平面辨識+後端 |
| 2D→3D 升維品質參差 | Demo 卡 | 用乾淨 DXF 範例 / 半自動(人工確認牆線);任意 CAD 不做 | 平面辨識+升維 |
| 範圍蔓延 | 做不完 | 照片/多視角/12000 家具/導購 = 未來展望,不在 P0;PNG/PDF 辨識列 P1 | 組長 |
| 組員進度不一、整合困難 | W6 爆 | P0 優先、每週整合驗收、W6 凍結檢查 | 組長 |
| 模組輸出接不起來 | 整合失敗 | 先定介面 schema(辨識輸出、`Room`、家具 DB entry、`client_brief`、匯出格式) | 組長 |
| Demo 當天失敗 | 展示中斷 | 固定範例資料、Demo Mode、錄影備援 | 後端+前端(組長統籌) |

---

## 14. 現行待辦(活的清單)

**🎯 最高優先**

- [ ] **F2 升維 = 整合,不是重寫**:把柏彥(yen 分支)的 `app/`(`dxf_parser` + 3D)merge 進來,並和 `furniture_engine` 的 `Room` 對齊介面(取代 demo 寫死的 5×4)
- [ ] **收斂 3D 前端**:舒媁 `web_fastapi/viewer.js`(載 GLB)與 柏彥 R3F Scene(擠出牆)二選一或分工,並接上引擎座標
- [ ] **分工對齊待談**:Agent(柏彥)、render_style(舒媁)兩核心 owner 目前產出在別的分支;是否調整待組長與兩人討論
- [ ] **W2 spike:`render_style` 可行性 + ControlNet 落地方式拍板**(見 6.3、12)
- [ ] 三份介面 schema 收尾:辨識輸出/`Room`、家具 DB entry、`client_brief`(配置/微調 tool schema 已在 `schema.py`)
- [ ] **F9 匯出**:先做 three.js GLTFExporter 匯出 `.glb`,再視情況加 DXF / PDF
- [ ] **F6 3D 直接拖曳搬家具**:在柏彥的 R3F 場景上加拖曳(接 `adjust_furniture` 碰撞)

**🔧 進行中**

- [x] **門、窗辨識 pass rate 已知**:窗 精準89%/召回91%、門 過濾~100%(見 §9)
- [ ] `web_fastapi` 修匯入 bug(補 moodboard_assets 等)並接上 `furniture_engine`

**✅ 已完成**

- [x] `git` / GitHub:repo 已上、多分支(ancai/bella/ben/cody/kai/yen…)
- [x] `furniture_engine`:`place_furniture` / `adjust_furniture` + 25 測試通過
- [x] 牆體 + 門/窗偵測(`floorplan2dxf.py`)+ eval 腳本
- [x] 走通骨架 `demo_app`:一句話 → stub Agent → 真引擎 → stub 風格,端到端可跑
- [x] 型錄:GLB 下載 / 合併 / Postgres 匯入 script

---

## 15. Demo 設計

**Demo A — 正常案例(完整主流程):** 填案前問卷 → 上傳客廳 **DXF** 辨識 → 升維 3D 白模(旋轉縮放)→ 自動配置(沙發/茶几/電視櫃)→ 自然語言換風格 → **直接拖曳微調** → 3D 提案畫面 → **匯出 .glb / PDF**。重點:需求 → 配置 → 風格 → 可交付檔案 的因果。

**Demo B — 強化案例(主打 Agent 編排):** 現場用自然語言連續微調(換風格 + 移家具 + 加家具),展示 Agent 多步編排——核心 A 的招牌演出。

**Demo B' — 備援 / 加分(P1 風險檢查):** 載入有問題的配置 → 系統檢查出擋門/動線不足 → 給改善建議(引擎已有碰撞/門牆判斷,接得上)。

**現場失敗備援:** AI/網路失敗 → 一鍵 Demo Mode 載入預備資料;3D 壞 → 播放錄影;上傳失敗 → 直接載入 demo 資料。

---

## 16. 驗收標準(8/20)

**功能驗收**

| 項目 | 通過標準 |
|---|---|
| Agent 對話(含需求問卷) | 對話能收出合法 `client_brief`,生成有引用需求檔 |
| 平面圖 → 3D | DXF 白模與平面圖大致一致,可旋轉縮放 |
| 配置 | 家具真實尺寸、不超出空間、不重疊 |
| 微調 | 自然語言**或直接拖曳**皆可調整,含碰撞檢查 |
| 風格 | 1~2 風格可辨、空間結構維持一致(單一視角) |
| 提案畫面 | 可多輪迭代、即時看到變化 |
| **輸出檔案** | **能匯出 .glb / DXF / PDF,檔案可被外部工具開啟** |
| Demo Mode | 任一步失敗主線不中斷 |

**AI / eval 指標:** 風格符合度、空間結構保真度、迭代收斂步數、5 分鐘連跑成功率(目標 ≥5/5)。

**協作驗收:** GitHub 有清楚 README、分支與提交紀錄;每位組員能說清自己負責的模組與技術難點。

---

## 17. 名詞 / 參考資料

**名詞:** `client_brief`(案前需求檔 JSON)・ `upgrade_to_3d`(升維:平面圖→Room 白模)・ `render_style`(風格生成工具)・ Agent 編排(LLM 規劃 + tool routing)・ ControlNet/depth(結構約束生成)・ Demo Mode(失敗備援固定資料)・ GLTFExporter(three.js 匯出 .glb)。

**參考方向:** 競品 — HomeByMe / Planner 5D / SketchUp / RoomGPT;技術 — three.js / FastAPI / OpenCV / Shapely / ezdxf / LLM function-calling / RAG;格式 — JSON / glTF / GLB / DXF / PDF;室內設計規則 — 家具尺寸、動線寬度、門窗避讓。

---

## 變更紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| v1.0 | 2026-06-29 | 建立 SSOT,吸收既有提案與進度文件,標註原型現況與 AI 核心待決策 |
| v1.1 | 2026-06-29 | 主軸改為 `2Dto3D.html`;併入其已做/做一半/未做與 HomeByMe 併入進度 |
| v1.2 | 2026-07-01 | 併入 8 工作區塊分工表;加「存/算/餵」對齊心法 |
| v1.3 | 2026-07-01 | 更正辨識狀態(當時回報只到牆體) |
| v1.4 | 2026-07-01 | 依能力填入分工建議 |
| v1.5 | 2026-07-01 | **核心決策定案 A**;補家具擺放座標欄位、ControlNet 落地/成本風險、W2 spike |
| v1.6 | 2026-07-01 | 清除 11.2 主責/副手人名待填 |
| v1.7 | 2026-07-01 | 5.1 功能重排、F0 併入 F3、全篇 F 代號對齊 |
| **v1.8** | **2026-07-04** | **重大改寫:主軸原型由 `2Dto3D.html` 改為 Python/FastAPI repo `RoomPilot-Agent`**,§1/§7.2/§10 依實際檔案改寫(後端骨架/引擎已測/viewer.js 有殼);**輸入格式定案 DXF 先**(PNG/PDF 降 P1);**新增 P0 功能 F9 輸出提案檔案**、**F6 併入 3D 直接拖曳搬家具**;更正門窗辨識為「已實作+eval」;F 表加現況欄;§6.2 加現況+介面契約註記;§11 填回主責並加 DXF→Room/F9/拖曳交付;§12/§13/§14/§15/§16 同步對齊(升維、匯出、拖曳);git 待辦打勾 |
| **v1.9** | **2026-07-04** | **git 全分支對照更正**:升維(`dxf_parser`)+3D 其實**柏彥(yen 分支)已做、但未整合**——F2/§6.2/§7.2/§10/§14 從「缺口」改為「已有待整合」;`demo_app` 標記為本次工作階段產物(未 commit),非組員模組;3D 前端標為舒媁(`web_fastapi`)+ 柏彥(R3F);門窗填入實際 pass 率(窗89%/91%、門~100%);待辦改「升維=整合非重寫、收斂兩個 3D 前端」;記錄分工提醒(柏彥實作升維、舒媁實作 web 前端,兩核心 Agent/render_style 未動,分工是否調整待討論,**本次不改分派**) |
