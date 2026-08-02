> **非正式工作總帳**。正式規格見 `../README.md` 與 `../room_strategy/README.md`。
> 本檔用白話寫，術語一律附解釋。

# Engine 工作總帳（現在在哪、還沒做什麼）

> **這本放「會變的東西」**：進度、待辦、衝突、待拍板。
> 查淨空數字、資料庫事實、環境怎麼建，請看 [`engine參考手冊.md`](engine參考手冊.md)。
>
> 最後更新：**2026-08-02**。由 2026-07-29 ～ 08-01 的五份每日筆記彙整而成，
> 原始日記已刪除，內容全數併入本檔與參考手冊；需要原始脈絡時查 git 歷史。
> **不再新增日記檔。**

## 目錄

1. [三分鐘上手](#0-三分鐘上手)
2. [**明日接手指南**](#05-明日接手指南2026-08-02-凌晨收官給下一個-claude-code) ← 接班先讀這節
3. [已完成](#1-已完成有證據不要重做)
3. [你提過但還沒做](#2-你提過但還沒做本檔重點)
4. [擺不對的因果鏈](#3-擺不對的因果鏈)
5. [floor04 基準](#4-floor04-基準)
6. [接線現況與職責邊界](#5-接線現況與職責邊界)
7. [想法衝突](#6-想法衝突)
8. [一再重複的同一個病](#7-一再重複的同一個病)
9. [待拍板](#8-待你拍板)
10. [紅線與維護規則](#9-紅線不變)

---

## 0. 三分鐘上手

**現在的位置**：**全鏈已接通**——問卷風格 → RAG 語意快取選件 → Agent 補件/換小 → 引擎擺位 → 2D/3D，全程 4.6 秒。

- 2026-08-01 之前：家具擺得出來但擺不對——床浮在房間正中央、床頭櫃一個貼床頭一個貼床尾、沙發背對電視櫃、衣櫃直接放不下。
- 2026-08-01 之後：新增擺放策略層並**已接進第 6 步**（策略層優先、舊候選表 fallback、環境變數可關）。
- **2026-08-02 凌晨夜戰**：床消失案雙刀結案（使用者確認全鏈通）；RAG 快取選件上線（1.4s）；40 型圖示庫地雷拆除；餐廳/書房/玄關規則＋三新原語；換小改階梯式；五表對帳量尺出爐並修掉灌水 bug。
- **收官三發**：床頭櫃統一成對 ×2（主次臥同預設，拍板）；SPACE_DEFAULTS 對齊 v1（後端預設全對齊，剩前端兩張表）；**全部 push 上 origin/ancai**。接班細節見 [§0.5 明日接手指南](#05-明日接手指南2026-08-02-凌晨收官給下一個-claude-code)。
- 真實路徑實測改善：**主臥床頭櫃**從浮空亂放 → 左右對稱緊貼床頭；**儲藏室**三件從浮在房間中央 → 全部貼牆；**客廳刻意不變**（見 §4.3）。

**三方分工**（Ancai 親口定義，不要用別的說法覆蓋）：

| 角色 | 職責 |
|---|---|
| **引擎**（Ancai） | 家具規則：淨空、碰撞、合法性、座標 |
| **RAG**（Django） | 問卷內容 → 轉 JSON → 據以搜索正確家具 |
| **Agent**（Yen） | 拿 RAG 選出的家具做擺位紀律（選件、順序、換小） |

**12 房型是封閉集合**：玄關、客廳、餐廳、廚房、主臥、次臥、浴室、書房／工作區、陽台、儲藏室、走道／動線、多功能室。兒童房＝次臥開 `kids_room` 候選池，**不是第 13 個房型**。

**產品資料流**（Ancai 口述）：

```
確定尺寸＋空間結構＋問卷
   ↓ 產出 JSON（需求／約束；風格等非幾何欄位原封往後流）
RAG 選家具（可超供）
   ↓
Agent 在規則下呼叫引擎擺放
   ↓ 放不下 → 換小款（「放得下」優先）
剩餘／證據可當第 8 步生圖素材
```

---

## 0.5 明日接手指南（**2026-08-03 凌晨收官版**——先讀這段，0802 版在後面）

> Ancai 指示：寫紀錄、確認明天可自行交接。8/2 中午～8/3 凌晨連續作戰十四小時的完整收官。

### 倉庫與環境狀態

- 分支 `ancai`，本日 **12 個 commit**（`b16f880`…`5d3dff5`＋本交接 commit），收官時全部 push。
- 產品測試庫：`pytest -q tests/` → **784 passed / 12 skipped / 0 failed**。
- 8002 server 由本 session 以 `--reload` 拉起；重開機後要手動啟（指令見 0802 版）。
- **python playwright＋chromium headless（含系統 deps）已裝好可直接用**；實操腳本樣式見 skill `placement-spec-verify`。

### 專案 `b2b2c83f`（123）狀態

- rev 475、**16 件全型錄真身**、GLB 全可載；客廳四件組（電視/沙發/茶几/植栽）已 **locked**＋定版樣本 `room_strategy/samples/living_room_floor04_v1.md`。
- 反向 GLB 已標注五件式清單見 skill（FREDDE 桌/LÖPARBANA 椅/AmazonBasics 沙發/Movian Cinca 床＝180）。

### 本日拍板（全部已落地，不要重新討論）

1. **平面上只留有 GLB 真身的件**——種子死鍵拔除＋回歸鎖。
2. **隨機配套池**：預設最少＋隨機配套到 5 槽、成組佔一槽、單元跨房型（電競桌椅＝臥室/客廳皆可）、手動新增不限。
3. **擺放邏輯全比例、零絕對公分**（巨人屋免疫）；沙發＝貼電視對面牆（opposite）背有靠。
4. 模型視覺朝向走 `modelOrientationDeg` 渲染層欄位，**絕不動擺位 rotation**。
5. 旋轉微調：90° snap 禁入 15° 路徑；被拒自動「先離牆再轉」（retreat）。

### 明日優先序

| # | 事 | 誰 | 備註 |
|---|---|---|---|
| 1 | **VLM 朝向批次標注工具**（8,557 件） | 引擎/工具 | 四顆反向實錘，`library_thumbnails` 有縮圖管線可借；根治「每顆新模型都要人肉問」 |
| 2 | **分割線開口資料**（分割房間時生成門/開口進 structures） | 引擎+前端 | 陽台門盲區：電視曾坐門口；任何分割房都會重演 |
| 3 | **平面圖重定標** | Ancai（瀏覽器 2 分鐘） | 949.52cm/383.758px≈2.474；巨人屋一日不除、絕對尺寸一日失真 |
| 4 | validate/layout 房界演算法統一（牆邊 ~10cm 灰帶） | scene_service | 手擺全靠 margin 探測的根源 |
| 5 | ⚠️ OpenRouter API key 輪換 | Ancai | **7/31 曝光至今未換** |
| 6 | 問卷表死鍵＋對話框過濾＋5 槽裁剪 | Bella | 單在 0802 版交接段 |

### 自檢三板斧＋skill

```bash
.venv/bin/python -m pytest -q tests/
.venv/bin/python scripts/audit_room_programs.py
.venv/bin/python scripts/audit_furniture_vanish.py
```

家具消失→skill `furniture-vanish-audit`；改擺位規則/要畫面驗證→skill `placement-spec-verify`（本日新增，含 24 條陷阱速查與反向模型名冊）。細節戰記：§0.5 續發現 1–9、§3.6 五層旋轉案。

---

## 0.5-舊 明日接手指南（2026-08-02 凌晨收官，給下一個 Claude Code）

> Ancai 指示：記錄總結讓明天完美接上，同一個環境作業。本節就是交接單，讀完即可上工。

### 現在的倉庫狀態

- 分支 `ancai`，**夜戰全部 commit 已 push 到 origin/ancai**（08-02 凌晨解除 push 禁令）。
- 產品測試庫收官實測：`pytest -q tests/` → **758 passed / 12 skipped / 0 failed**（跑完 SPACE_DEFAULTS 對齊後量的）。從 repo 根目錄裸跑 `pytest` 會多收 `training/` 而出現 7 個 failed——全是缺 torch 生態第三方套件，與產品無關，不用修。
- 8002 是使用者常駐 server；重啟用 `pkill -f "[u]vicorn backend.server.main"`（**方括號防自殺**，直接寫 uvicorn 會殺到自己的 shell，exit 144）再 `.venv/bin/python -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002`。改過 server 端 code 一定要重啟；改過 static 要叫使用者硬重整（Ctrl+Shift+R）。

### 當晚兩項拍板（已寫進 code，不要重新討論）

1. **主／次臥共用同一套預設、床頭櫃統一成對 ×2**——測試階段只有一間臥室，不做「最大間＝主臥」推定。落點：`knowledge.ROOM_MINIMUM_FAMILY_COUNTS` + `required_family_count()`，RAG 快取與補件 offers 都帶 count，前端自動展開、引擎對稱貼床頭。
2. **SPACE_DEFAULTS 對齊 v1**（Bella 檔案，Ancai 授權）：只留必備、死鍵清光、廚浴陽台顯式空清單（鍵必須存在，防「表外退成客廳家具」）。它只在 `/api/scene/generate` 方案換算、且問卷家具全空時生效——瀏覽器正常流程輪不到。

### 對帳工具的已知假陽性（別當 bug 修）

`scripts/audit_room_programs.py` 跑出來的玄關兩條是**假的**：

- 「knowledge 缺 cabinet-cupboard/shelving-unit」——v1 原文是「鞋櫃**優先**；不足退櫃」，是一件含備援，不是三件必備。優先/備援語意機器表還表達不了（v1 待辦 #2）。
- 「SPACE_DEFAULTS 缺 3 件」——後端問卷詞彙（canonical 9 型，鎖在 `tests/test_room_type_vocabulary.py`）根本沒開放 entry，N/A 不是缺。

改後真實狀態：**11 房 8 偏離，且後端已全對齊；剩下的偏離全在 Bella 的前端兩張表**（見下方交接單）。

### 還沒做的（依優先序）

| # | 事 | 誰 | 備註 |
|---|---|---|---|
| 1 | **OpenRouter API key 輪換** | Ancai | 7/31 已在終端機曝光，安全項，拖越久越險 |
| 2 | 使用者的平面圖重定標 | Ancai（瀏覽器 2 分鐘） | 房子仍是 2.8 倍巨人屋（手動校準 949.52cm/383.758px≈2.474 cm/px） |
| 3 | v1 #2 玄關優先/備援語意機器化 | 引擎+Agent | 需要 knowledge 支援「同槽備援」結構 |
| 4 | v1 #5 kids_room 候選池、#6 多功能室路由 | Agent | |
| 5 | RAG 離線快取 rerank 升級 | 可選 | 現況 bge-m3 top-12 已可用（1.4s） |
| 6 | RAG role bug | Django | 已被快取路徑繞過，不擋路 |

### 給其他成員的交接單（不是你的活，開單即可）

- **Bella**：前端兩張表對齊 v1（床頭櫃種子缺席、玄關房型未登記、問卷表死鍵三型＋新增對話框過濾〔種子表側 08-02 已拔，見 §2.3〕、問卷客廳缺電視櫃、廚浴陽台塞件）；旋轉 A/D 的 UX；「產生配置」後自動重建 3D 或提示；換小 old→new id 協定。
- **Yen**：過目 knowledge 的 count 欄位與 outdoor 別名（commit 訊息都有知會段落）。
- **Kai**：21 件掛床分類的非床品項清單（audit 關卡 1 輸出）。

### 快速自檢三板斧

```bash
.venv/bin/python -m pytest -q tests/                       # 全庫
.venv/bin/python scripts/audit_room_programs.py            # 五表對帳
.venv/bin/python scripts/audit_furniture_vanish.py         # 消失風險掃描
```

家具又消失時：先跑 skill `furniture-vanish-audit`（本機 `.claude/skills/`，不進 git），照 SOP 讀 autosave 差集，**不要看截圖猜**。

---

## 1. 已完成（有證據，不要重做）

### 1.1 引擎能力

| 項目 | 完成日 | 驗證 |
|---|---|---|
| 雙層淨空（理想 `ideal_cm`／底線 `floor_cm`） | 07-29 v1.2 | `test_clearance.py` |
| 硬性／軟性分流（`operation` 擋下／`access` 只警告） | 07-29 v1.2 | 同上 |
| 結構化失敗原因（哪件、哪條、差幾公分） | 07-29 v1.2 | `PlacementIssue`／`PlacementValidation` |
| 配套家具可進舒適空間 | 07-29 v1.2 | `companion_pairs` |
| 搜尋改善：中心 → 四面牆 → 15cm 網格 | 07-29 v1.2 | `placement.py` |
| 床左右長側至少一側（75／60，床尾不算） | 07-29 v1.3 | `test_bed_foot_block_does_not_count_as_side_clearance_failure` |
| 餐桌有椅才留面（呼叫端宣告哪幾面） | 07-29 v1.3 | dining 相關測試 |
| `ClearanceSpec` 多面 + `all`／`any` 模式 | 07-29 v1.3 | `test_catalog_json_accepts_multiple_clearance_zones_with_mode` |
| 類型預設淨空表（17 單面 + 6 多面） | 07-29 | `clearance_defaults.py` |
| 第 6 步套用類型預設淨空（最小接線） | 07-30 | `scene_service` 呼叫 `catalog_with_default_clearance()` |
| 旋轉語意實測：front 跟著 rotation 轉 | 08-01 | 解掉 07-29 待驗證點 #2，見 §3.2 |
| **`Room` 支援門窗**（`Opening`，含開門扇形與窗台高） | **08-01** | `models.py`；預設空清單，往下相容 |
| **擺放策略層**（選牆、貼牆、正面朝內、貼床頭端、正前方、擺放順序） | **08-01** | `layout_strategy.py`＋37 個測試 |
| **`layout_json` → 引擎 Room 轉換** | **08-01** | `layout_room.py`（比照 `dxf_room.py`，純資料轉換） |
| **floor04 真實管線預覽工具** | **08-01** | `scripts/floor04_layout_preview.py`（不做快照） |

**基準線**：`test_layout_strategy` + `test_clearance` + `test_placement` + `test_agent_place` + `test_agent_select` + `test_scene_layout_regions` = **131 passed**

### 1.2 規格與拍板

| 項目 | 拍板日 | 位置 |
|---|---|---|
| 淨空八項白話確認 | 07-29 | 參考手冊 §3 |
| 房型策略表 v0 | 07-30 | 已升級 |
| **12 房型 v1 定版（寫死不再變動）** | 07-31 | `../room_strategy/README.md` |
| 通用砍件規則 G1–G5 | 07-31 | 同上 |

### 1.3 環境與整合

| 項目 | 完成日 |
|---|---|
| 家裡 WSL PostgreSQL 18.4 + pgvector（8,557 家具、7,958 向量） | 07-31 |
| 修 `cloud_catalog.py` 兩道舊資料量斷言（五支端點 500 → 200） | 07-31 |
| 合併 ben 分支（第 6 步三個阻斷點全解），commit `890a0c4` | 08-01 |
| 修 503（`.env` 補兩行，見參考手冊 §5.3） | 08-01 |
| `.gitignore` 排除 `.env.*`（備份檔含密鑰卻沒被擋） | 08-01 |
| **瀏覽器路徑啟用策略層**（`/api/scene/layout` 補 `room_type`＋逐件處理依錨點排序） | 08-01 |
| **Agent 補件權**（必備族系缺席→型錄補真品；假件→換真 GLB；20cm 錯件防呆） | 08-01 |
| **RAG 語意快取接進第 6 步**（315 組離線 top-12，選件 1.4s；`build_rag_offer_cache.py`） | 08-01 |
| **床消失案雙修**（語意關認中文描述＋型錄對 `catalog_furniture_id`；使用者確認全鏈通） | 08-02 |
| **家具消失稽核工具＋skill**（`audit_furniture_vanish.py`＋`furniture-vanish-audit`） | 08-02 |

備份分支 `backup/ancai-20260731` 指向合併前的 `e98c3a9`，**只在本機，沒推遠端**。

---

## 2. 你提過但還沒做（**本檔重點**）

依「你第一次提出的日期」排序。愈上面代表擱置愈久。

| 提出日 | 擱置 | 事項 | 邊界 | 現況 |
|---|---|---|---|---|
| ~~07-29~~ | — | ~~沿牆／找位置的搜尋收回引擎~~ | — | ✅ **08-01 已接線**，但拍板**不收回**——兩套並存，策略層優先、舊表 fallback。見 §5.4 |
| **07-29** | **3 天** | **美學／擺放評分**（first-fit → 評分選優） | ✅ engine 內 | 部分完成：策略層已能產生「有設計」的候選，但**還沒有評分排序**，仍是找到第一個合法解就停 |
| ~~07-29~~ | — | ~~窗前禁放帶從 `scene_service` 收回引擎~~ | — | ❌ **2026-08-01 拍板不收回**，見 §5.4。落地窗留距仍要做，但會被 70cm 平頭帶蓋掉 |
| **07-29** | **3 天** | 地毯可壓、壁架略過碰撞 → 引擎層級規則（＝**堆疊層**） | 🔴 **必須連 `scene_service` 一起改** | **未做**。只改引擎地毯吃不到，見 §5.4 |
| **07-29** | **3 天** | 走道連通檢查（人走不走得過） | ✅ engine 內 | 未做 |
| **07-29** | **3 天** | 清死鍵 `bed-frame`／`cabinets-cupboard` | 🔴 **必須連 `FURNITURE_ALIASES` 一起改** | 未做。只改引擎沒用，見 §5.4 |
| ~~07-30~~ | — | ~~第 6 步所有家具皆無法旋轉~~ | — | ✅ **08-01 已查證**，根因四層疊加，見 §3.6。按鈕有反應、被合法性擋下、訊息藏在小字裡 |
| ~~07-31~~ | — | ~~四（五）張清單對帳~~ | — | ✅ **08-02 工具完成** `scripts/audit_room_programs.py`：**11 房型 9 個偏離規格**——玄關前端整個未登記、廚浴陽台被三表齊塞死鍵、主臥四表四種答案。備註：v1 的「優先/備援」與「×2 數量」語意任何機器表都還表達不了（knowledge 升級時一併解） |
| ~~07-31~~ | — | ~~`.env` 改 `cuda` 實測 RAG 秒數~~ | — | ✅ **08-01 已實測，結論反直覺**：CUDA 更慢（熱查詢 73~106s vs CPU 40s；VRAM 5877/6144 塞爆、來回搬資料）。**拍板路線＝離線預算快取**（§5.6 方案 3）。附帶發現：role bug 是**不穩定**的——同一句查詢這次電視櫃回 4 件（LLM 每次猜不同），更證明紅線 |
| 07-31 | — | `knowledge.py` 對齊 v1 六項 | ⚠️ 跨 Yen | **08-02 完成 2.5 項**：#1 outdoor 別名 ✅、#3 提示詞半邊（count=2 教學）✅、3 個過期紅測試結案 ✅；#2/#5/#6 與數量機器欄位待結構升級 |
| **07-31** | **1 天** | ⚠️ **輪換 OpenRouter API key** | 安全 | **未做**（曾在終端機完整輸出） |
| **07-31** | **1 天** | 前端六個死鍵＋廚房自動加冰箱／陽台加洗衣機（違反 G5） | ⚠️ 跨 Bella | 未做，清單見 §2.3 |
| 08-01 | 今天 | 補 `bedside-table` 淨空規則（DB 54 件，引擎零規則） | ✅ engine 內 | 未做 |
| 08-01 | 今天 | 房型白名單 | ✅ engine 內 | 未做 |
| ~~08-01~~ | — | ~~餐廳／書房／玄關擺放規則~~ | — | ✅ **08-02 完成**：新增 center／around／face 三原語；floor04 --retype 實測 16 件全放（餐桌置中＋2+2 對坐、椅面桌、鞋櫃貼牆） |
| ~~08-02~~ | — | ~~前端 2D 圖示庫缺 40 型~~ | — | ✅ **08-02 已修**：未登記型別帶尺寸即用通用圖示建檔（3D 照載真 GLB），無尺寸仍拋錯。node 回歸測試三向鎖死 |
| **08-02** | 新 | 床語意關現擋 21 件（多為抽屜櫃冒充床的既知錯件）——清單交 Kai 覆核 | ⚠️ Kai 資料 | 稽核工具可重印清單 |
| 08-01 | 今天 | 給床頭櫃等家具貼 `placement_relation` 標籤 | ⚠️ 跨 Bella（`main.py`） | 未做 |
| 08-01 | 今天 | RAG `role` 硬過濾 | ⚠️ 跨 Django | 未修，但**已繞過**：第 6 步快取路線不經 role；僅 /rag 自由文字頁仍受影響（且實測猜測不穩定） |

### 2.1 四（五）大設計落地狀況

| 設計 | 首次提出 | 現況 |
|---|---|---|
| 理想／底線兩層退讓 | 07-23 | ✅ **已完成** |
| 落地窗留距 | 07-23 | ✅ **大半完成（08-01）**。窗前帶已看窗台高度（`scene_service` 接管第一步，保險開關 `ROOMPILOT_WINDOW_BAND_FLAT`）；剩落地窗帶深 30/60 分級待拍板 |
| 房型白名單 | 07-23 | ❌ **零** |
| 堆疊層（地毯／地面層 vs 家具層） | 07-23 | ❌ **零** |
| 電視定位 | 07-23 | ⚠️ **一半**。電視櫃已會貼沙發對面牆並朝向沙發；「該不該避開窗」待拍板 |
| **成組擺放**（建議升為第五項） | 08-01 | ✅ **已完成**（貼床頭端、正前方對齊中線） |

### 2.2 `knowledge.py` 對齊 v1 的六項（跨 Yen）

| # | v1 要求 | 程式現況 |
|---|---|---|
| 1 | 加 `outdoor` → `balcony` 別名 | `ROOM_TYPE_ALIASES` 七條，**無 `outdoor`** ← 最要命，陽台永遠零候選 |
| 2 | 玄關鞋櫃「優先＋備援」 | `"entry": ("shoe-cabinet",)` 硬必備 |
| 3 | 主臥床頭櫃 ×2、次臥 ×1 | 主次臥不分、無數量概念 |
| 4 | 陽台維持空白 | ✅ 巧合符合 |
| 5 | 次臥開 `kids_room` 池 | 全檔查無 `kids_room` |
| 6 | 多功能室四條路由 | `"multifunction": ()`，無路由 |

另有既有失敗 `test_room_affinity_uses_known_localized_room_types`：**`multifunction` 不在 `KNOWN_ROOM_TYPES`**，v1 十二房型之一接不上。

### 2.3 前端六個死鍵（跨 Bella）

`scene_layout2d.js` 的 `recommendedFurnitureForRoom` 使用這些類型，**DB 全部 0 件**：

| 類型 | 影響房型 |
|---|---|
| `appliance-cabinet` | 廚房 |
| `storage-cabinet` | 儲藏室 |
| `bathroom-vanity` | 浴室 |
| `flower-pots-planter` | 陽台 |
| `refrigerator` | 廚房（自動加）← **違反 G5** |
| `washer` | 陽台（自動加）← **違反 G5** |

**結論**：即使房型標對，廚房／儲藏室／浴室／陽台在前端那條路仍必然空白。

**08-02 live 實證（第一個真實案例）**：使用者專案 `b2b2c83f` 走 skill SOP 差集驗屍，2D 14 件 vs 3D 11 件，差集正好 3 件全是死鍵假件——`appliance-cabinet`（#4 電器櫃）、`storage-cabinet`（#10 高收納櫃）、`bathroom-vanity`（使用者手動新增也中招）。三件皆 model_url 無／catalogId 無／placementFailed=False，2D 側欄照標「合法」（合法＝引擎擺放判定，與有無型錄真身無關），3D 端 diagnostics 11 請求／11 可見／0 失敗——3D 無罪，件是在送 3D 前就被 generate 合併剔除。靜態掃描關卡 3 的預測與 live 個案 100% 吻合。

**08-02 已修（種子表側，Ancai 拍板「平面上只留有 GLB 真身的件」）**：`recommendedFurnitureForRoom` 三死鍵拔除——廚房清空（對齊 v1）、儲藏室換 `shelving-unit`（型錄 80 件真貨；新登記 2D 變體 80×40×120＝中位 83×37×122 圓整）、浴室拔 `bathroom-vanity` 留 `mirror-cabinet`（17 件真身，完整 v1 對齊仍歸 Bella）。專案 `b2b2c83f` 三假件已從 autosave 清除（rev 295→296，2D 11 件＝3D 11 件，備份在 scratchpad）。回歸鎖 `tests/test_scene_seed_dead_keys.py`（死鍵不得進種子表＋核心真身型不得被誤清）。另 `flower-pots-planter` 型錄已補貨 235 件、自死鍵除名。**仍留給 Bella**：問卷表（`scene_v2.js` defaults/required）三死鍵、「新增家具」對話框仍可選死鍵型。〔更正：浴櫃假件不是手動加件——`room-manual` 是**手動劃的房間**，浴櫃是房型種子自動生的。〕

**08-02 續發現（同日下午）**：
1. **方案快照復活閘門**：第一次清理只清 `layout_2d.furniture` 頂層，前端從 `schemes[A/B]` 快照恢復假件並以合法 revision 寫回（rev 296→297 假件全回魂）。二次清理三處全清（top＋scheme A＋B，rev 298）。教訓已入 skill 判讀表。
2. **門前淨空實際零生效**：引擎扇形 ✔、`scene_service.py:1729` 接線 ✔，但本專案 5 樘門 `opening_direction` 全是 `manual_review`、**無 `swing_end`** → `room_openings_from_floorplan` 只建門洞、不建扇形。要生效：第 4 步人工確認門開向；或（待拍板）引擎/服務端做「開向未確認 → 預設門前通行帶」fallback。另留疑點：該轉換器解析 `raw.get("z")`，而 `confirmed_floorplan.doors` 座標是 x/**y**——餵入來源格式需查證。
3. **無房間件**：ROCKSJÖN 扶手椅、BILLY 書櫃 `roomId=null`（id 為型錄樣式 `fi-…`/`jp-…`，selectionSource 空，來源待查），落點在廚房範圍，前端因「無房」判 invalid 紅框——與淨空無關。〔已依 Ancai 拍板移除；儲藏室兩件改走正規管線 `/api/agent/furniture/select`（RAG 快取選件）＋`/api/scene/layout`（逐房擺位）補齊，rev 301。〕
4. **validate 與 layout 房界判定分歧**（全屋體檢發現）：臥室床邊桌 bbox 四方向皆在 room polygon 內（超出 0cm），`/api/scene/validate`（F6 拖曳那套）仍判「超出房間範圍/跨牆」，`/api/scene/layout` 全局重擺卻原位認可（位移 0）。兩套房界演算法（polygon vs 牆段重建）在牆邊 ~10cm 級別意見不同→使用者拖到引擎自己擺的位置也可能被標紅。歸 scene_service，待開單。
5. **全屋擺位體檢（rev 301）**：11 件 10 合法；陽台／浴室／儲藏室現況＝引擎理想位（位移 0）；客廳沙發 36cm、茶几 85cm 偏離 08-01 新策略理想位（成組對齊 x=171＋貼牆），合法但未套新策略。臥室床頭櫃現況 1 只 vs 拍板必備 ×2（`required_family_count('bedroom','bedside-table')=2`），缺 1。另：客廳理想位把電視櫃與沙發擺到**同一面牆**（y 皆 -531，`attach="opposite"` 疑似 fallback）——TV-first 成組規格（Ancai 提案：先定 TV 牆→沙發按房深比例距離→茶几居中；LLM 只接管選牆意圖、座標留引擎）待拍板動工。
**08-02 傍晚戰果（TV-first 三項拍板全落地，pytest 771/12/0，playwright 實操驗畢）**：
1. **TV-first 客廳**：`layout_strategy` 規則表反轉（電視櫃 anchor＋`avoid_windows`；沙發 `front of` 電視 `face=target`、觀影距離＝房深×0.45 夾 250–700；茶几居中）；`opposite`「退任意牆」fallback 死刑。PlacementRule 新欄位 `gap_ratio_depth`／`gap_clamp_cm`／`avoid_windows`（高度視 None→窗段全擋，一個機制吃「電視避窗＋床頭不靠窗」兩拍板）。
2. **窗帶分級**：落地窗 60cm（§2.1 懸案 30/60 拍板取 60）、一般窗 70＋窗台豁免照舊（`scene_service._window_zones_with_sill`）。
3. **§5.4 雙寫陷阱應驗**：引擎改完、API 重演仍同牆——`_strategy_placement`（整合端複製品）逐參數補同步（gap 比例〔逐房基準＝boundary 深，非全屋 room.depth〕、face、avoid_windows）。回歸鎖 `test_generate_layout_adapter_honours_tv_first`。
4. **companion 全鏈補洞**：`scene_service` 原本零 companion——「確認 2D」鎖位重驗把引擎自擺的對稱床頭櫃判「侵入床側淨空」（一只進待處理、一只被重排到廚房，live 實案 rev 305）。鎖位驗證／網格後援／策略層／F6 單件驗證全帶 `companion_pairs`；**id 雙體系陷阱**：鎖位件＝furniture_id、重擺件＝`type_N` 流水號，pairs 兩套 alias 都建。回歸鎖 `test_locked_companion_pair_survives_confirm_revalidation`（確認流程不得自打臉）。
5. **實操驗證（playwright headless，chromium+deps 已裝）**：`/scene?project_id=` 入口→`#confirm-layout-2d`（hidden 子 section，JS click 即觸發真 handler）→3D 重建→sceneData 幾何覆核：客廳同軸 x=170.6 三件、面對面 0/180、中心距 310；床頭櫃 ×2 對稱中點＝床心（殘差 0）；12/13/0 全可見。專案 rev 307。註：headless 的「GLB 載入失敗 ×11」為環境網路所致，氣泡點名機制（1ad4a50）正常運作，真機瀏覽器無此況。小房（<330 深）TV-first 下茶几會誠實失敗→砍件歸 Agent（v1：茶几可選）。
7. **模型出廠朝向修正（08-02 深夜，全屋朝向體檢）**：使用者實測 FREDDE 電競桌／LÖPARBANA 椅 3D 視覺反 180°——引擎 rotation 數字正確（面對面），**GLB 出廠面向出廠不一、渲染層無校正**。落地 `model_orientation_deg` 分層機制：2D `modelOrientationDeg` → `toSceneFurniture` 透傳 → `scene_viewer` 三條 wrapper 旋轉路徑吃 offset；**擺位 rotation 的引擎「正面」語意不得被污染**，視覺修正獨立欄位。桌椅兩件標 180 後 playwright 特寫實錘轉正。守門：cache-bust 鍵兩層測試逼著同步（scene_v2 import 鍵＋scene.html 入口鍵）。**Backlog**：8,557 件 GLB 無朝向標注——長期需型錄層 orientation 欄（Kai）或前端「轉模型」鈕寫 offset 而非 rotation（Bella）。另實測：headless GLB 全載需 95s＋（CDN），confirm 後重建同樣要等 GLB，等待不足會誤判「沒生效」。
9. **客廳重規劃＋分割線開口盲區（08-02 夜末）**：使用者回報電視卡陽台門——實測電視 (821,185) 橫跨北牆「門(668-833)＋落地窗(880-1063)」之間且兩頭壓線。**根因＝新盲區**：陽台是從客廳分割出來的，分割線上的開口（陽台門）只存在於視覺，`structures.doors` 沒有記錄→引擎完全看不見（TV-first 避的是「有資料的門窗」）。重規劃（手動 TV-first＋validate 5/5）：電視→東牆（客廳唯一無窗無門實牆）置中面西、沙發面東 272cm（比例）、茶几居中、配套補槽 2（隨機抽 3 取 2：層架→西牆下段實牆、書櫃→南牆東段避浴室門；抽中的 desk 是分類錯置件 Movian Taro 30cm 高「茶几桌」，裁掉）。rev 315、3D 16/20/0。**v2（使用者複核「沙發漂房中」）**：死守「觀影距＝房深比例」會把沙發釘在半空——改「沙發背靠西牆下段實牆優先、觀影距取實牆間距（449，夾限內）」；探測教訓：沙發 180 長，南緣斜 polygon 差 3cm 判跨牆，兇手在 y 不在 x。終態 rev 317、16/16/0 GLB 全載零替身；桌椅朝向修正與儲藏室貼牆同幀視覺實錘。**Backlog**：分割房間時在分割線生成開口資料（門/落地窗）進 structures，或引擎把 split 邊界視為禁貼開口——否則任何分割房都會重演此案。另：配套池抽樣暴露型錄分類錯置件（desk 池含茶几），RAG 選件品質關卡待補。層架／收納櫃舊寫入漂房中；策略層逐房重擺仍回房中——**逐房模式 place_against_wall 的「牆」與房 polygon 差牆厚，貼全屋牆＝出 boundary 被拒→網格 fallback 落房中**（backlog：逐房牆語意）。兜底：手算貼北牆並排（西緣退 60 避落地窗帶＋跨牆灰帶、避東南門）、單件驗證通過後寫入（validate 房界灰帶再現：貼緣 8cm 判跨牆，margin 16＋西退 60 過）。終態 rev 312：14 件全真身、diagnostics 14/14/0。
6. **隨機配套池（08-02 夜間落地，pytest 779/12/0）**：Ancai 拍板「預設最少＋隨機配套達到設計效果」——`knowledge.ADDON_UNITS`／`ROOM_ADDON_POOLS`／`ROOM_SLOT_LIMIT=5`＋select 端點 `_addon_offers`：必備族系外隨機抽「配套單元」補到 5 槽（成組佔一槽），同單元跨房型（desk-set 帶 gaming 風味，臥室與客廳皆可⚡實測入場）；種子鋪整個型錄 item（缺 model_url 會炸 backfill 契約）；回應帶 `addons` 抽樣紀錄；`addon_offers(rng=)` 可注入 seed。**兩張表打架教訓**：池說可進、`ROOM_AFFINITY` 說不行＝抽中被選件驗證踢掉白佔槽（實測層架／桌椅組／扶手椅三連中招）——親和表補 living_room（desk／office-chair／shelving-unit）、bedroom（armchair 閱讀角）、storage（chests-of-drawer），守門測試 `test_addon_pool_families_are_affine_to_their_rooms` 鎖一致；`storage-solution-system` 族系折疊歸 shelving-unit＝死單元不可入池。客廳桌椅組擺位規則補齊（椅貼桌前 8cm 面向桌）。**未做**：問卷塞爆＞5 槽的裁剪（現行只補不裁），留問卷表對齊時一併。原提案細則（decor 豁免走 decorate）維持待做。使用者手動新增不受槽限。巧合：v1 主臥（床＋衣櫃＋床頭櫃×2＋五斗櫃）＝5、次臥（床＋衣櫃＋床頭櫃×1＋桌椅組）＝5，天然契合。待定義：companion 成組計件方式、decor（植栽／地毯／燈）是否豁免上限（建議走 `/api/scene/decorate` 不吃槽）。配套池＝v1「可選」欄 × 型錄有貨；電競桌椅＝desk 池 gaming 語意件（62 件）＋gaming-chair（11 件，族系歸屬待補 knowledge）。附帶發現：auto-decor 的燈類（floor-lamp/lamp）型錄 0 件＝裝飾死鍵。

---

## 3. 擺不對的因果鏈

### 3.1 根因零：擺放策略住在 `scene_service.py`，不在引擎

第 6 步的真實呼叫路徑：

接線**前**的呼叫路徑（策略層完全輪不到）：

```
POST /api/scene/generate
  → scene_service.generate_layout()
      → scene_service._placement_candidates()  ← 80 行寫死的候選位置＋角度表，17 種家具
      → 逐個候選丟 engine.check_placement_with_clearance() 驗證
      → 全部失敗才 → engine.place_furniture()  ← 引擎只是備援
```

接線**後**（2026-08-01）：

```
POST /api/scene/generate
  → scene_service.generate_layout(room_type=...)
      → _strategy_placement()                  ← 先問引擎的擺放策略層
      → 策略層放不出來 → _placement_candidates()  ← 舊表完全不動，當 fallback
      → 還是不行 → engine.place_furniture()      ← 舊備援完全不動
```

開關：`ROOMPILOT_LAYOUT_STRATEGY=0` 就 100% 退回接線前行為。
方案 B 刻意不走策略層（策略層是確定性的，否則兩個方案會一模一樣）。

👉 **07-29 就寫過**：「沿牆／網格找可放位置——大半 `scene_service`——『能不能放』的搜尋屬幾何」，並列為「適合收回 engine」。**2026-08-01 拍板不收回**，改為兩套並存，見 §5.4。

### 3.2 方向其實已經對了一半（好消息）

實測（房間 400×300，衣櫃 100×60，前方淨空 90，貼下牆）：

```
rotation=0   （正面朝房間內）→ legal = True
rotation=180 （正面朝牆）    → legal = False
```

正面朝牆時，90 公分的開門淨空會跑到牆外，引擎自己就擋掉了。

👉 **有前方淨空的 16 個類型只要貼牆，方向自動正確**：衣櫃、PAX 衣櫃、櫃體、收納系統、抽屜櫃、餐邊櫃、電視櫃、電視影音、展示櫃、鞋櫃、鏡櫃、泛用收納、書櫃、層架、書桌、衣帽架。

👉 **方向會亂轉的只有沒設前方淨空的**：沙發、床、床頭櫃、茶几、單椅、餐椅。

### 3.3 真正的洞：貼牆完全沒強制（08-01 已修）

```
衣櫃放在 400×300 房間正中央 → legal = True
引擎自己找位置             → 就放在正中央 (200,150)
```

`placement.py` 的搜尋順序是**先試房間正中央**，再掃四面牆，first-fit。
👉 08-01 新增 `layout_strategy.py` 解決；`placement.py` 保持不變，仍作為備援。

### 3.6 「旋轉沒反應」的因果鏈（07-30 回報，08-01 查證結案）

按鈕**其實有反應**：每按一下都跑「前端夾回房內 → 後端 `/api/scene/validate`」，
被拒後家具不動，唯一回饋是 3D 畫面下方 `#white-model-status` 那行灰色小字
（`scene_viewer.js setStatus`）——體感就是「沒反應」。實測四層原因疊加：

| # | 層 | 內容 | 證據 |
|---|---|---|---|
| 1 | 🐛 **邊距不一致** | 前端夾位用 `WALL_GAP=6`（`scene_viewer.js:4490`），後端邊界內縮 **8**（`_shrunk_boundary`）——**貼極限的旋轉永遠差 2 公分被拒**，回「超出房間範圍」 | 床夾回房內後轉 15° 仍被拒，實測 |
| 2 | 物理 | 家具幾乎都貼牆，轉 15° 角必掃出房間／進牆 | 床/衣櫃/床頭櫃原位轉 15° 全回「超出房間範圍」 |
| 3 | 規則 | 窗前 70cm 平頭帶不看家具高度——床 55cm 轉 90° 被「不可遮擋窗戶」擋（窗台 90，物理上根本擋不到） | 實測；又是 §5.4 那條平頭帶 |
| 4 | 幾何 | 前端夾回房內後常撞到鄰件 → 重疊被拒 | 床內移後與床頭櫃重疊 |

修法選單與進度：**B ✅ 08-01 已修**（6→**9**，非 8——後端 contains 是嚴格判定，8 會壓線失敗；hash 連鎖已更新）；
**C ✅ 08-01 已修**（窗帶看窗台高度，`ROOMPILOT_WINDOW_BAND_FLAT=1` 可退回；床 55cm 靠窗轉 90° live 實測 ok）；
**A**（回饋顯眼化）與 **D**（先離牆再轉）留給 Bella——貼牆家具原地轉 15° 仍會被物理擋下，訊息仍是小字。
👉 **第五層（真主兇）✅ 08-03 破案**：`normalizedRotationDeg` 是 90 度吸附（round(deg/90)×90）——15° 微調按鈕從加入起每一按都被 snap 回原角（status 實錘「已旋轉到 0 度」），四層全是從犯。七處改用 `normalizeSceneRotationDeg`（mod 360），90° 件不受影響；playwright 真按鈕實測 0→345→0 還原、每步寫庫。引擎任意角本來就放行（API 重演 0.0s ok）。
👉 **D ✅ 08-03 落地**（使用者再度回報實錘後）：`rotateSelectedFromControls` 被拒改走 `rotateWithRetreat`——朝屋心逐步內移（15cm×6 步）找第一個轉得動的合法位，成功明講「自動內移 N 公分」；全敗訊息加 ⚠️。契約測試鎖接線。A 的整體回饋改版仍歸 Bella。
另註：`scene_viewer.js` R 鍵 handler 內有 `return` 後的死碼（舊 90° 邏輯），僅記錄。

### 3.7 「更換家具」查證（08-01，機制正常、回饋誤導）

實測 `replaceSelectedLayoutFurniture` → `/api/scene/layout`（其他家具鎖定、新件解鎖）
→ **真引擎檢查，機制正常**：塞得下就換＋更新位置；塞不下誠實拒絕（181cm Mira 衣櫃
在標準臥室確實無位）。體感「無法更換」來自三處回饋，皆 Bella 前端：
① 成功後 `invalidateDownstreamFrom("layout_2d")` 把主 3D 標成待重產——看起來像沒反應；
② 對話框右側預覽是迷你 3D viewer，鏡頭會鑽進 207cm 高的衣櫃內只見木紋＋「正在生成 3D 場景…」；
③ 失敗理由只顯示在對話框下緣小字。

### 3.4 沒有人告訴引擎「誰要貼著誰」（引擎側已修，上游未接）

引擎的 `place_adjacent_to_furniture()` 要家具帶標籤：

```python
placement_relation = { "kind": "adjacent", "target_types": ["bed", ...] }
```

唯一會貼標籤的地方是 `main.py:3072`，且只貼給**地毯（under）／植栽（adjacent）／燈（adjacent）**。床頭櫃、餐椅、茶几、電視櫃一個都沒有。

👉 08-01 的策略層改用**房型規則表**決定貼附關係，不再依賴上游貼標籤——但那是走 `layout_strategy.place_room()` 這條新路，舊路仍需標籤。

### 3.5 沙發前方無約束（07-29 的設計債，08-01 補上）

07-29 拍板「沙發不設前方淨空，前方是茶几**關係**」，但關係約束一直沒做，所以沙發前方零約束——這是茶几跑到最遠那面牆的原因。
👉 08-01 以 `attach="front"` 規則補上：茶几對齊沙發中線、放在正前方、刻意不貼牆。

---

## 4. floor04 基準

`POST /api/floorplan/analyze` 餵 `testdata/png/floor04.png`。座標單位公分，原點在平面 bbox 左下角。

⚠️ **刻意不做快照**——`scripts/floor04_layout_preview.py` 每次都重跑辨識＋定標，辨識端改進時會直接反映。以下數字是 2026-08-01 的執行結果。

**成果發表固定用 floor04**，這幾個空間會**輪流定義成餐廳、書房等房型**，用同一張圖的幾何測所有房型。

### 4.1 房間

| id | 類型 | 尺寸 | 門 | 窗 |
|---|---|---|---|---|
| room-1 | bedroom | 338×310 | 南牆（往房內開） | 西牆 |
| room-2 | kitchen | 339×310 | 北牆 | 東牆 |
| room-3 | storage | 338×298 | 北牆 | 西牆 |
| room-4 | circulation | 87×121 | — | — |
| room-5 | bathroom | 230×121 | 南牆 | 東牆 |
| room-6 | living_room | 338×298 | 南牆（入戶門） | 南牆 |
| room-7 | balcony | 346×132 | — | — |

定標：0.88 cm/px（來源 `cody_config`，信心 0.9）。

⚠️ **room-7 陽台是誤判**——PNG 上那塊是建築外的白區。現行規格陽台留空所以看不出來，但若房型定義給陽台配家具，會憑空冒出家具在建築外面。屬辨識端（Cody），只追蹤。

⚠️ `doors[].room_ids` 與 `windows[].room_ids` 都是**空陣列**——門窗歸屬由 `layout_room.py` 用幾何自己算（容差 12 公分，因為門窗畫在牆中線、房間多邊形畫在牆內緣）。

### 4.2 現行策略層實跑結果（2026-08-01）

```
主臥 338×310
  床        x[ 94~244] y[110~310] rot=180  床頭貼北牆（唯一無門無窗的長牆）
  床頭櫃×2  x[ 49~ 89] 與 x[249~289]，y[270~310]  床的左右兩側、都貼床頭端
  衣櫃      x[  0~ 60] y[  2~102] rot=270  貼西牆，避開窗、避開開門扇形

儲藏室 338×298
  層架×2＋收納櫃  全部貼南牆，沿同一面牆排（門在北牆）

客廳 338×298
  沙發      貼北牆朝南
  電視櫃    貼南牆朝北  ← 與沙發面對面
  茶几      沙發正前方、共用中線、刻意不貼牆

擺放成功 10 件、失敗 0 件、不該浮空卻浮空 0 件
```

**關鍵證據**：改成貼牆之後，原本「找不到合法位置」的衣櫃**放得進來了**。
「衣櫃放不下」不是房間太小，是床霸占了中央——現行 `scene_service` 的行為會誤觸 v1 砍序，把必備的衣櫃砍掉。

### 4.3 已知的待議點

客廳電視櫃落在 x[125~305]，而客廳南牆的窗在 x[118~221]——**電視櫃在窗前面**。
引擎判它合法，因為電視櫃高 50 < 窗台 90，物理上沒擋到窗。規則沒錯，但實務上電視放窗前會逆光。
👉 這是 §8 第 1 題「沙發背窗」的具體版本。

---

## 5. 接線現況與職責邊界

### 5.1 三方接線（08-01 追碼確認）

| 元件 | 接上主流程了嗎 | 證據 |
|---|---|---|
| **AGENT 擺放** `agent/place.py` | ✅ **有** | `scene_service.py:16` import、`:1962` 呼叫 |
| **AGENT 選件** `agent/select.py`＋`knowledge.py` | ⚠️ **半接**（08-01） | 驗證＋**補件**已上線（`_backfill_required_offers`，讀 `ROOM_MINIMUM_FAMILIES` 從型錄補真品）；LLM 選件仍不可能執行 |
| **RAG** | ✅ **已接（08-01 快取版）** | 離線快取（`scripts/build_rag_offer_cache.py`＋`.runtime/rag_offer_cache.json`）由 select 端點讀取，語意第一名主導選件；線上 /rag 頁照舊 |
| **引擎擺放策略層**（08-01 新增） | ❌ **沒有** | `scene_service` 仍用自己的 `_placement_candidates` |

第 6 步實際選件是 `scene_service.py:498`：**類型字串硬比對 catalog → 風格／顏色／尺度四項評分 + 亂數 0~8 分 → 取第一名**。沒有語意理解、沒有向量、沒有 LLM。

`agent/select.py` 的 LLM 選件**結構上不可能被呼叫**：`main.py:2373` 的 `if isinstance(llm_selection, dict)` 前端從不送這個欄位，而且就算送了，注入的 `complete` 只是把呼叫端自己傳進來的答案原封回傳——**它不打 OpenRouter**。`select.py` 整個檔案沒有任何 HTTP 呼叫。

### 5.2 職責邊界分類（2026-07-29 拍板，仍有效）

**A. 適合收回／新建在 engine（動之前要問跨資料夾）**

| 項目 | 現在在哪 | 狀態 |
|---|---|---|
| 出界／撞牆／重疊／開合淨空 | 已在 engine | ✅ 本來就是 |
| 沿牆／網格找可放位置 | 大半 `scene_service` | ⚠️ 引擎側已寫好，**接線未做** |
| 窗前禁放帶 | `scene_service.window_clearance_zones` | ❌ 未收回 |
| 地毯可壓、壁架略過本體碰撞 | `scene_service` 白名單 | ❌ 未收回（＝堆疊層） |
| 結構化失敗（哪件、哪條、差幾 cm） | — | ✅ 已完成 |

**B. 留在別人那邊（不要搶）**

RAG 選件、風格／人數→幾人座（Yen／Kai）；問卷、八步 UI、專案保存（Bella）；catalog／GLB／DB 淨空欄位落地（Kai，你定契約）；「哪面牆比較美」類美感偏好（暫留 Bella／之後再議）。

**C. 邊界模糊**

| 項目 | 建議 |
|---|---|
| `_placement_candidates` | 合法性搜尋進引擎；**好看順序可暫留 server** ← ⚠️ 與 08-01 目標衝突，見 §6.2 |
| 換小款 | **Agent 做**；引擎只回放不下＋原因 |
| 門／窗進 `Room` | 應進引擎模型；資料仍來自 `layout_json` ← ✅ 08-01 完成 |

### 5.3 各房型「關係意圖」（2026-07-29 記錄，是擺放策略的原始來源）

| 房型 | 家具 | 關係意圖 |
|---|---|---|
| 客廳 | `sofa` | 靠牆優先；不設前方淨空 |
| 客廳 | `tv-bench` | **與沙發對望／對牆**；無獨立 TV |
| 客廳 | `coffee-table` | 沙發前方配套（access companion） |
| 客廳 | `bookcase`／`shelving-unit` | 靠牆收納；可砍 |
| 臥室 | `bed` | 左右長側至少一側可上下床；床尾不算側 |
| 臥室 | `wardrobe`／`pax-wardrobe` | **靠牆；門扇開啟空間** |
| 臥室 | `bedside-table` | **床側配套**；可進床側 access |
| 臥室 | `chests-of-drawer` | 靠牆收納；可砍 |
| 餐廳 | `dining-table` | 有椅才留面；呼叫端宣告有椅側 |
| 餐廳 | `dining-chair` ×N | 餐桌配套；可進 access zone |
| 餐廳 | `sideboard` | 靠牆；可砍 |

👉 這張表是 `layout_strategy.ROOM_RULES` 的來源。**餐廳、書房、玄關、次臥還沒寫進規則表**。

### 5.4 ⚠️ 決定留在 `scene_service.py` 的邏輯（2026-08-01 Ancai 拍板「不收回」）

7/29 曾列出「沿牆搜尋、窗前禁放帶、地毯可壓」三項適合收回引擎。
**2026-08-01 拍板：不收回，維持現狀。** 但下列邏輯留在 Bella 的檔案裡，
未來動引擎時必須記得它們會蓋過或繞過引擎的規則：

| 留在 `scene_service.py` | 行號 | 內容 |
|---|---|---|
| `SPACE_DEFAULTS` | :108 | 房型家具清單（四張打架清單之三） |
| `FURNITURE_ALIASES` | :125 | 中文→型別別名，**仍在用兩個死鍵** |
| `choose_furniture_items` | :409 | 選件評分＋亂數（不是 RAG） |
| `_WALL_ANCHORED_TYPES` | :706 | 貼牆清單 |
| `_placement_candidates` | :726 | 80 行寫死的位置＋角度表，17 種家具 |
| `_OVERLAY_TYPES` | :844 | 地毯：可壓在別人身上 |
| `_IGNORE_COLLISION_TYPES` | :845 | 壁架：完全跳過碰撞（偷吃步） |
| `window_clearance_zones` | :1002 | **窗前 70cm 禁放帶**，平頭硬擋 |

#### 引擎後續工作與它們的衝突

| 我要做的 | 衝突對象 | 後果 |
|---|---|---|
| **堆疊層（地毯）** | `_OVERLAY_TYPES` | 🔴 地毯走 overlay 分支，策略層刻意跳過它。**引擎做了堆疊層，第 6 步的地毯完全吃不到**，必須同步改那個分支 |
| **落地窗留距** | `window_clearance_zones` 70cm | 🔴 那條**不分窗型、不看家具高度**，兩者取嚴。引擎的「落地窗 30／60、一般窗看窗台」**會被 70cm 蓋掉** |
| **清死鍵** | `FURNITURE_ALIASES` | 🔴 別名表仍寫 `"床架": "bed-frame"`、`"收納櫃": "cabinets-cupboard"`。引擎清了，問卷打那兩個詞**照樣靜默回 0 件** |
| 補餐廳／書房／玄關／次臥規則 | `_placement_candidates` | ⚠️ 不會壞（策略層先跑、它當 fallback），但**同一件事兩個地方寫**，改一邊另一邊不會跟 |
| 房型白名單 | `SPACE_DEFAULTS` | ⚠️ 會變成**第五張**房型清單 |
| `bedside-table` 淨空規則 | 無 | ✅ 純引擎內，`scene_service` 會自動吃到（它呼叫 `catalog_with_default_clearance`） |

👉 **紅色三項：只改引擎沒有用，一定要連 `scene_service` 一起改，否則做了也看不到。**

### 5.5 RAG 已知 bug（Django 地盤，只追蹤）

查「客廳想要現代簡約風的沙發加茶几和電視櫃」→ 沙發 ✅4、茶几 ✅4、**電視櫃 ❌0**。

根因：LLM 每次自己猜的 `role`（`anchor`／`accent`）被當成 SQL 硬過濾。

```
全部電視櫃類        66 件
role='accent'        4 件
accent 且在價格帶內   0 件   ← 回 0 的直接原因
anchor 且在價格帶內  38 件   ← 全被丟掉，且不報錯
```

`backend/spatial_data/AGENTS.md` 明寫 RAG「**不得決定選件政策**」，`role` 正在實質決定候選——已超界。

三種修法（都在 Django 地盤）：① `role` 只用來排序不用來擋；② 過濾後為空時自動放寬再查一次並標記 `relaxed_filters`；③ 在 `category_groups.json` 為每個 group 寫死 role ← **最符合「LLM 不做決定性判斷」的紅線**。

**效能**：parse 5.6~7.4s + rerank 33.8~35.8s ≈ **40 秒**。第二次沒變快 → 不是冷啟動，是 CPU 跑 reranker 慢。

### 5.6 RAG 接進第 6 步的評估（07-31，仍有效）

接縫已經留好：`/api/agent/furniture/select` 的 `offers` 是 payload 欄位，後端照單全收。RAG 回傳結構與 offers **幾乎同構**（一次查詢回一整間房的所有槽位，欄位名也對得上）。

| # | 動作 | 成本 | 效果 |
|---|---|---|---|
| 1 | `.env` 改 `ROOMPILOT_RAG_DEVICE=cuda` | 1 行 | 40 秒大幅下降（**需實測**） |
| 2 | 新增 `POST /api/agent/furniture/offers`；前端改呼叫它，JS 路徑留 fallback | 1 新檔＋2 檔小改 | RAG 正式接進第 6 步 |
| 3 | 離線預算 offers 快取表 | 較大 | 線上查表，毫秒級 |

**關鍵洞察**：資料庫已定版不再增加，所以「槽位 × 風格 × 尺寸級距」的組合有限且不變，可離線把每組 top-8 算好存進 PostgreSQL——既拿到真 RAG 的語意品質，又完全沒有 40 秒代價。**資料定版反而讓最好的方案變可行。**

**決策點**：先做 1 並實測 GPU 後的秒數。若降到 10 秒內，第 2 步直接可行，不需要做第 3 步。

---

### 5.7 前端持有的決策點盤點（2026-08-01 確認，Ancai 拍板方向：agent＋RAG＋引擎主導 2D/3D）

三份正式文件都規定前端只做呈現：

1. `CLAUDE.md` 禁止事項：「將幾何決策移到 Graph RAG、**瀏覽器**或 LLM」
2. `backend/server/AGENTS.md`：「Adapt owner modules; **do not copy their algorithms into `main.py` or JS**」
3. `engine/README.md` 分工圖：前端只出現在最末端的「2D／3D **呈現**」

實際盤點，前端目前握有 **9 個決策點**：

| # | 位置 | 它在決定什麼 | 應歸誰 | 拆除時機 |
|---|---|---|---|---|
| 1 | `scene_layout2d.js:238` `recommendedFurnitureForRoom` | 各房放什麼＋型號 | Agent（knowledge.py ← 你的策略表） | Agent 補件後降為種子，之後刪 |
| 2 | `scene_v2.js:7261` `QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS` | 問卷預設／必選 | Agent | 同上 |
| 3 | `scene_layout2d.js:50-100` `FURNITURE_2D_LIBRARY` | 型號與尺寸（雙人床 152×200 等寫死規格） | catalog（Kai，真家具尺寸） | 選件全走 catalog 後只留圖示 |
| 4 | `scene_layout2d.js:187` `recommendCompanionFurniture` | 成組補件 | Agent `COMPANION_OF` | Agent 補件後刪 |
| 5 | `scene_furniture_retrieval.js` 整檔 188 行 | **選哪件**（關鍵字打分，假 RAG） | RAG（Django） | RAG offers 接上後刪 |
| 6 | `scene_v2.js:8279` `specFitsRoomDimensions` | **塞不塞得下（幾何！）** | 引擎 | ⚠️ **直接違反 CLAUDE.md 禁令**，引擎驗證已可信即拆 |
| 7 | `scene_v2.js:8029` `specsAllowedByRoomFeasibility` | 可行性硬規則（浴缸等） | Agent／引擎 | 同上 |
| 8 | `scene_layout2d.js:214` `roomTypeFromName` | 用名字 regex 猜房型 | 第 4 步資料（Cody） | 房型欄位可信後刪 |
| 9 | `scene_v2.js` `furnitureOfferFromSpec` | **捏造無 GLB 的假 offer**（灰方塊來源） | 不該存在 | Agent 補件後刪 |

註解自白：#5 的 catch 寫著 `"Catalog RAG retrieval fallback"`、#6 的註解自稱「2026-07 盤點修復的治本**半**」——**墊檔性質有據，但沒有一處寫時程**，不拆就是永久。

⚠️ 更正一條舊記錄：先前記「前端在廚房自動加冰箱／陽台加洗衣機，違反 G5」——合併 ben 後 `recommendCompanionFurniture:189` 已用 `retiredApplianceTypes` 擋掉，**行為已無違規**，僅殘留死碼。

## 6. 想法衝突

### 6.1 同一房型有四張清單（07-31 實測確認，仍未解）

以主臥為例：

| 來源 | 主臥放什麼 | 擁有者 |
|---|---|---|
| `room_strategy/README.md` **v1 正式規格** | `bed`、`wardrobe`／`pax-wardrobe`、`bedside-table`**×2** | **Ancai** |
| `agent/knowledge.py` | `bed`、`wardrobe`、`bedside-table`（不分主次臥、無數量） | Yen |
| `scene_service.py` `SPACE_DEFAULTS` | `bed`、`bedside-table`、`bookcase`、**地毯**（無衣櫃） | Bella |
| `scene_layout2d.js`（**第 6 步實際用這張**） | `bed`、`wardrobe`（無床頭櫃） | Bella |

**後果**：只改 `knowledge.py` 對齊 v1 **不會讓第 6 步生效**。任何對帳測試必須**同時涵蓋四張表**。

### 6.2 「好看順序暫留 server」vs「要看起來有設計」

| 時間 | 說法 |
|---|---|
| **07-29 決定** | `_placement_candidates`：「合法性搜尋進引擎；**好看順序可暫留 server**」 |
| **08-01 目標** | 「該貼牆的貼牆、方向至少要對、**看起來是有設計的**」 |

👉 **直接衝突**。「好看」的決定權留在 server，引擎再怎麼改都不會好看。要達成 08-01 的目標，07-29 那個「暫留」必須解除。

### 6.3 「美學評分最後做」vs「看起來有設計」

07-29 三度把「美學／擺放評分」標為「延後／最後做」，但那就是「看起來有設計」這件事本身。
👉 應從「延後」改為「當期」。08-01 已完成一半（會產生有設計的候選），**評分排序仍未做**。

### 6.4 地毯：G4 說不放，後端自動放

- **v1 規格 G4**：軟裝不進自動配置
- **`SPACE_DEFAULTS`**：把 `runner-small-rug` 當主臥必備自動放

👉 這是「地毯整片壓在床底下」的來源。且地毯目前靠 `_IGNORE_COLLISION_TYPES` 完全跳過碰撞檢查。

### 6.5 已作廢／已修正的舊結論（別再引用）

| 原結論 | 現況 |
|---|---|
| LLM 24～78 秒，卡頓來自免費層排隊 | ❌ **作廢**。換付費模型後 3.3 秒 |
| ancai 落後 ben 110 commit | ❌ **作廢**。08-01 已合併 |
| 2D/3D 空白根因 `roomType="default"` | ✅ **已修**（合併後改下拉選單） |
| 新增家具退回第 5 步 | ✅ **已修**（`allowPendingFurniture: true`） |
| 6 個 catalog 測試斷言舊資料量 9350 | ✅ **已解決**（合併後 17 passed） |
| clearance 覆蓋率 22.9% 是大缺口 | ❌ **同日自行推翻**。65% 是刻意不設 |
| 表格「AGENT 擺放 ✅ 已接」 | ⚠️ **誤導**。選件與擺放併在同一格；實際是**擺放通、選件不通** |
| ben 合併風險極低 | ⚠️ engine `.py` 確實零衝突（判斷正確），但全庫實際 **43 個衝突**，整體低估 |
| 「引擎做好畫面不會變，要等上游接手」 | ⚠️ **講法不精確**。真因是策略在 `scene_service`（§3.1），**不是要動前端** |

---

## 7. 一再重複的同一個病

07-31 盤點時發現，當時六個獨立問題的根因**完全相同**：

> **程式宣告的東西與資料庫實際存在的東西對不上，而且全部靜默失敗**——不噴錯，只回傳空的或錯的。

| 現象 | 程式宣告 | 執行現實 | 有報錯嗎 |
|---|---|---|---|
| 主臥沒衣櫃 | v1 說必備 | `SPACE_DEFAULTS` 沒寫 | ❌ |
| 問卷打「收納櫃」撈不到 | 別名表寫 `cabinets-cupboard` | DB 是 `cabinet-cupboard` | ❌ |
| Agent 沒選件 | 端點名為 `/api/agent/furniture/select` | 實走 `local_rules` | ❌ |
| 廚房／陽台永遠空白 | 前端表列 `refrigerator`／`washer` | DB 各 0 件 | ❌ |
| 房間無房型 | 前端表無 `default` 分支 | 直接回 `[]` | ❌ |
| RAG 電視櫃回 0 件 | `role` 是 LLM 猜的 | 38 件合格品被丟掉 | ❌ |
| 退回第 5 步 | 訊息說「請檢查問卷」 | 真因是缺 GLB | ⚠️ 訊息誤導 |

而 `tests/test_agent_knowledge.py` 的測試**沒有一個碰資料庫**，只檢查「表跟自己一致」，從未檢查「表跟現實一致」——這就是全部漏網的原因。

**因此順序是：先有量尺，再改東西。**

1. **【先做】房型表 × 資料庫對帳測試**（約 50 行）——必備槽位 DB 0 件 → 失敗；必備槽位件數 < 門檻（建議 20）→ 失敗，強迫改成「優先＋備援」；可選槽位 0 件 → 警告。**上表六個問題有四個會被這一個測試當場抓到。**
2. **【再做】`knowledge.py` 對齊 v1 六項**（§2.2）。
3. **【接著】失敗要分層說話**：`表→RAG 0 件` / `RAG 有件→引擎全判不合法` / `引擎給了位置→前端沒畫`，三者症狀相同但責任不同。
4. **【接著】詞彙只准一套 `category_code`**：加測試禁止從 `item_id` 推型別（錯誤率 73%）。
5. **【設計建議】表要記錄「資料厚度」**，不只必備／可選。`shoe-cabinet` 只有 5 件卻寫成硬必備＝規格說謊，程式就會照著謊做事。

---

## 8. 待你拍板

| # | 題目 | 擋到什麼 | 首次提出 |
|---|---|---|---|
| 1 | **沙發背窗**：牆不夠才背窗（備案 A）還是看到落地窗就主動背窗（優先 B）？具體版本見 §4.3 | 落地窗禁放帶、客廳擺法 | 08-01 |
| 2 | **堆疊要不要做「電視上櫃」**？（需引入高度概念，工程變大） | 堆疊層 | 08-01 |
| 3 | **窗要分兩類還是三類**？前端只有 `standard`／`floor_to_ceiling`，設計定案是三類——缺「可通行落地窗門」，底線 **30 vs 60 差一倍**，逃生等級不同 | 落地窗禁放帶的欄位設計 | 07-31 |
| 4 | **窗型要不要自動猜**？辨識端完全不產生窗的類型（只有寬度），目前一律預設一般窗、靠人在第 4 步手動切換 | 第 4 步 UI（跨 Bella） | 08-01 |
| 5 | 6 個 catalog 測試期望值要不要改成 8,557？（取決於資料是否定版） | catalog 測試 | 07-31 |
| ~~6~~ | ~~`test_project_workflow_api` 2 個失敗~~ | ✅ **08-01 已解**：第三條路——Agent 補件讓驗證通過，測試更新為新契約後轉綠（832→836 passed） | — |
| 7 | **接線走法**：要不要動 `scene_service.py` 讓第 6 步真的顯示策略層的結果？ | 所有 08-01 的成果 | 08-01 |

**浴室要不要留空**已由 v1 規格回答（**空白**），不再是待決項。

---

## 9. 紅線（不變）

- RAG／LLM／瀏覽器**永不**決定幾何；合法位置只由 `backend/engine/` 判定。
- 家電不進 2D/3D 自動配置；quarantine 不當正式家具。
- 未問過不得改 `backend/server/`／`backend/agent/`／`backend/spatial_data/`／catalog SQL。
- 公分制；結構化中文失敗原因。
- 白話討論、**一批一次拍板才動工**。
- 判斷進度以 `../README.md`、`../room_strategy/README.md` 等正式 README 為準，**不以 `notes/` 為準**。
- 不得把「規格寫了」說成「引擎做完」；不得把「引擎測過」說成「第 6 步已啟用」。

## 10. 維護規則

1. 每完成一項：把 §2 對應列改成完成，並在 §1 加一行「做了什麼／怎麼驗證」。
2. 新結論與舊內容衝突：更新本檔，並在 §6.5 記一行「哪個結論作廢」。
3. Ancai 問「做到哪了」：先貼 §0 + §2，再講細節。
4. 不得把測試中、半成品、只寫了註解的項目標成完成。
5. **只有兩本筆記**：本檔（會變的）與 [`engine參考手冊.md`](engine參考手冊.md)（不太會變的）。**不再新增每日日記。**
