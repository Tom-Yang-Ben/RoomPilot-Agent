# ADR-002: 幾何合法性唯一裁決者是 backend/engine/ (Engine as Sole Geometry Authority) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** Ancai（`backend/engine/` owner，`AGENTS.md:41`）＋ Bella（`backend/server/` 消費端）；決策者名單由 ownership 文件推得（`docs/TEAM_AI_OWNERSHIP.md:14,29`），人工核准前本欄為待確認
> **語域:** L2（橋接）——業務詞「放得下、走得過去」與工程詞「七段檢查、遮罩、OBB」並列
> **實例:** 每決策一份（`ADR-002-engine-sole-geometry-authority.md`）
>
> **本文件回答**：為什麼碰撞、淨空、出界、移動與旋轉的裁決權只放在 `backend/engine/`（與其伺服器端呼叫層），不放到 LLM、Graph RAG 或瀏覽器；當初放棄了哪些替代方案；這個決策付出什麼代價、何時該重評。
> **本文件不含**：`layout_json`／`scene_json` 的資料邊界（見 [ADR-001](./ADR-001-layout-json-scene-json-boundary.md)）、Shapely 與柵格雙路徑的分工與分歧（見 [ADR-003](./ADR-003-dual-path-shapely-raster-engine.md)）、公分單位契約（見 [ADR-007](./ADR-007-centimeter-unit-contract.md)）、演算法逐段細節（見 [`lld.md`](../../04_design/lld.md)）、系統全貌（見 [`sad.md`](../sad.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、工作樹日期 2026-08-12。行號隨程式碼演進，衝突時以原始碼為準。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：DEC-008 承諾「家具必須真的放得下、走得過去，放不下要用看得懂的中文說明原因」（`brd.md:162`）；DEC-009 進一步要求 A／B 兩案過**同一套**檢查（`brd.md`；FR-031）。第 6 步同時存在四個有能力宣稱「這樣擺可以」的角色：瀏覽器 Three.js／2D 疊層、選件與場景規劃 LLM、Graph RAG 檢索、伺服器幾何引擎。
- **問題**：裁決權若不收斂到一處，同一份配置在「拖曳當下」「按重排」「進第 7 步整屋確認」三個入口會得到不同答案；失敗原因也會分裂成三套文案，使用者無從得知該移哪一件。NFR-016 的擺位決定性、ACPT-029 的「B 走完全相同驗證」都將無法宣告。
- **驅動因素**：DEC-008／DEC-009 需要**可重現**且**可解釋**的裁決；FR-037 要求擺不下必須回報結構化失敗清單而非靜默丟棄。
- **約束**：`AGENTS.md:53-54` 明文「Graph RAG 只檢索…不決定幾何、碰撞、淨空或結構合法性」「家具合法位置只由 `backend/engine/` 判定」；`docs/TEAM_AI_OWNERSHIP.md:28` 規定 `backend/agent/`「不輸出合法座標」、`:53`「Ancai 仍是幾何與規則的唯一裁決者」；`backend/engine/AGENTS.md:5-11` 要求引擎演算法不得依賴 UI 或 LLM 措辭、須保持既定驗證順序與公分契約。

## 2. 考量的選項

| # | 選項 | 描述 | 優點 | 缺點（為何不選） | 成本 | 結論 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 一 | **瀏覽器端判定** | 由 Three.js／2D 疊層在前端自算 `hitsWall`／`hitsFurniture`／`outOfBounds` | 零往返、拖曳手感最好 | 原型即以軸對齊包圍盒近似、不支援旋轉（`backend/engine/geometry.py:1-6` 記載引擎正是為取代 `2Dto3D.html` 的這三個函式而寫，該原型檔已不在本 repo）；規則會隨每個前端版本各長一套，A／B 與整屋確認無法保證同準 | 低 | **放棄** |
| 二 | **LLM／Graph RAG 直接產座標** | 讓場景規劃或檢索模型輸出 `position_cm` 與 `rotation_y_deg` | 一次呼叫得到「像設計師擺的」結果 | 不決定性、不可單元測試、失敗時給不出可轉述的固定原因；與 `AGENTS.md:53-54`、brd OUT-6「不讓 AI 決定家具擺在哪裡」（`brd.md:125`）直接衝突；NFR-016 無法成立 | 中 | **放棄** |
| 三 | **淨空全部由型錄宣告（declarative-only）** | 引擎不內建任何預設淨空，一律讀型錄的 `clearance_zones` | 規則即資料、改型錄就改規則，無硬編碼 | 正式型錄每件的 `clearance_zones` 恆為空陣列（`backend/catalog/postgres_repository.py:418`），採此案等同關閉全部淨空檢查，收納櫃會被緊貼擺放、門打不開（`backend/engine/clearance.py:20-23` 記錄此坑） | 低 | **放棄** |
| 四 | **伺服器引擎唯一裁決（本案）** | 幾何原語與檢查順序集中在 `backend/engine/`，前端與 agent 只送輸入、只呈現結果 | 單一規則來源、可測試、失敗原因為固定繁中字串、A／B 共用同一驗證 | 每次拖曳需一次網路往返；規則改動集中，engine owner 成為瓶頸 | 中 | **採用** |

## 3. 決策

**選擇**：選項四。碰撞、淨空、出界、移動與旋轉的合法性，一律由 `backend/engine/` 計算並經 `backend/server/` 的三個入口對外；LLM 只決定「選哪些家具」、Graph RAG 只決定「候選排序」、瀏覽器只負責呈現與送出待驗座標。

| 使用者動作 | 入口 | 實際裁決者 | 佐證 |
| :--- | :--- | :--- | :--- |
| 產生方案 A／B、重排、替換、新增後重算全場 | `POST /api/scene/layout` | `generate_layout` → `build_raster_context` 布林網格 | `main.py:3647-3709`；`scene_service.py:2228-2230` |
| 拖曳落點、換件試放、指定位置新增 | `POST /api/scene/validate` | `validate_single_placement` → `check_placement_with_clearance` | `main.py:3998-4009`；`scene_service.py:2111-2155` |
| 進第 7 步前的整屋確認 | `POST /api/scene/layout` 帶 `validate_only:true` | 只驗不排：座標照舊，只回報合法與否 | `scene_service.py:2338-2364` |
| 結構化移動／旋轉指令 | `adjust_furniture` | X／Y 軸分離試放；旋轉 `%360`，不合法即還原 | `backend/engine/adjustment.py:11-51,54-69,72-91` |

**七段固定順序、只回最先命中者**（FR-034）：①出界 →②穿牆 →③本體重疊（`backend/engine/geometry.py:67-76`）→④淨空撞牆 →⑤淨空撞他人本體 →⑥淨空互撞（`clearance.py:99-115`）→⑦反向：本體壓到他人淨空（`clearance.py:134-141`）；總入口與順序見 `backend/engine/clearance.py:118-143`，回傳值是可直接轉述的繁體中文字串。

**五個公分常數**（FR-035）：門前 75 cm、窗前 40 cm（僅家具高 ≥90 cm 受限）（`backend/engine/constraints.py:21-23,35-37`）、有櫃家具正面 50 cm（`backend/engine/clearance.py:24,33-37,55-62`）、背牆間距 5 cm（`backend/engine/rules.py:15`）。判定解析度為 5 cm 網格、單軸上限 1200 格、牆線描粗 12 cm（`backend/engine/raster.py:18-21`，NFR-015）。

**理由**：相對選項一，引擎用旋轉多邊形／OBB 而非包圍盒近似，且所有入口共用同一函式，使 ACPT-029「B 走完全相同驗證」可被斷言；相對選項二，`backend/agent/place.py:16` 明載「全程不呼叫 LLM、不產生座標；重擺一律經注入的 `place_fn`（＝引擎）」，LLM 的產出被限縮為選件（`main.py:3440-3501` 未通過本地白名單即整批降級 `local_rules`）與不含座標的計畫欄位（`scene_service.py:315-338`）；相對選項三，型錄現況無淨空資料，引擎端預設是唯一能讓 DEC-008 成立的位置。

## 4. 後果

### 4.1 得到什麼

- 單一規則來源：`rg` 可窮舉全部裁決點，第 6 步 UI 的所有錯誤文案都源自 `clearance.py`／`geometry.py` 的固定字串（`scene_v2.js:11470-11477,12626,12747`）。
- 可測試：七段順序與反向檢查有直接單元測試（`tests/test_clearance.py:115-133`、`tests/test_placement.py:69-105`、`tests/test_layout_spec.py:139`）。
- 前端 fail-closed：驗證服務無回應時瀏覽器回 `{ok:false, reason:"驗證服務未回應"}` 而非自行放行（`backend/server/static/scene_viewer.js:4992-5010`；另見 `scene_v2.js:11761-11774`）。
- 決定性：候選邊排序有完整 tie-break（`backend/engine/rules.py:49-52`），同輸入同輸出（NFR-016）。

### 4.2 付出什麼

| 代價／技術債 | 事實 | 佐證／掛號 |
| :--- | :--- | :--- |
| 每次拖曳一次往返 | 落點驗證是同步 HTTP，離線或伺服器忙時使用者拖不動 | `scene_v2.js:11761-11774` |
| `validate_only` 是刻意的較寬檢查 | 整屋確認用 `check_placed=False`（不驗家具互撞）＋房界 12 cm 容差，僅檢查房間邊界與門窗淨空 | `scene_service.py:2338-2364` |
| 雙路徑正面朝向相反 | 柵格路徑定義正面為本地 **−y**（`f=(sin r, −cos r)`），Shapely 路徑 `_SIDE_OFFSETS["front"]=(0,1)` 為 **+y**；本體 OBB 對稱故不影響碰撞，但淨空外推方向會相反 | **OPEN-21**；`backend/engine/obb.py:3-5,30-36` vs `backend/engine/clearance.py:46-52` |
| 兩張淨空表鍵值與數值都不同 | `CLEARANCE_BY_TYPE`＝bookcase/sideboard/wardrobe/desk（40/40/50/50 cm）；`CLEARANCE_OF`＝wardrobe/cabinet_low/dressing_table/nightstand（60/45/45/35 cm）。僅 `wardrobe` 交集且深度不一致（50 vs 60） | **OPEN-22**；`backend/catalog/style_db.py:185-190` vs `backend/agent/clearance.py:20-25` |
| 領域知識與幾何原語分層 | 淨空「哪種家具會開門抽拉」放 agent 層，引擎不得反向 import；代價是同一概念有兩處定義 | `backend/agent/clearance.py:6-7` |
| 規則變更集中 | 任一新淨空規則都要動 engine owner 的檔案，跨 owner 協調成本固定存在 | `AGENTS.md:41`；`backend/engine/AGENTS.md:5-11` |

> 上表 OPEN-21／OPEN-22 為 [`srs.md`](../../01_requirements/srs.md) §8 已登記項目（承接處指向本 ADR 與 [ADR-003](./ADR-003-dual-path-shapely-raster-engine.md)）；哪一套為規格權威**待確認**，未收斂前兩者皆不得在下游文件寫成唯一規格。

### 4.3 何時重評（可觀測觸發條件）

| 觸發 | 判準 |
| :--- | :--- |
| 淨空語意分歧造成實際誤判 | OPEN-21 收斂後，若兩路徑對同一件收納櫃給出相反的合法性結論（可由同輸入分別走 `/api/scene/validate` 與 `/api/scene/layout` 比對複現） |
| 拖曳往返延遲影響可用性 | 第 6 步落點驗證 p95 往返時間超過可接受值（**目標值待確認**，NFR-025 目前無來源） |
| 型錄開始供應真實淨空資料 | `roompilot.furniture_catalog_current` 的 `clearance_zones` 不再恆為空（`postgres_repository.py:418`）→ 選項三重新成為可行案 |
| Agent 並存管線轉正 | `ROOMPILOT_AGENT_PIPELINE` 由旁路改為 live（FR-053、[ADR-011](./ADR-011-agent-pipeline-flag-isolation.md)），屆時須重新確認唯一裁決者仍是引擎 |
| 整屋確認出現漏網碰撞 | `validate_only` 的 `check_placed=False` 導致第 7 步接受了互相重疊的配置（UAT 或缺陷回報可觀測） |

## 5. 執行計畫

1. 維持現況邊界：新增或修改任何幾何規則一律進 `backend/engine/`（或其伺服器呼叫層），不得在 `static/` 或 agent／RAG 層另建判定；違反即視為缺陷。
2. 收斂 OPEN-21：由 engine owner 指定正面朝向的唯一慣例，並補一條跨兩路徑的一致性測試。**負責人與期限待確認。**
3. 收斂 OPEN-22：決定 `CLEARANCE_BY_TYPE` 與 `CLEARANCE_OF` 誰為權威（或合併為單一表），wardrobe 的 50／60 cm 擇一。**負責人與期限待確認。**
4. 補測 `validate_only` 的已知缺口：以「兩件明顯重疊但都在房內」的配置斷言目前行為（現況會通過），使該取捨成為顯式而非隱式。
5. 在 [`engineering_tracker.xlsx`](../engineering_tracker.xlsx) ①規格追溯登記本 ADR 與 OPEN-21／OPEN-22 的收斂狀態。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待簽核 | 本 ADR 為既成決策的補記；狀態「已接受」指程式碼與 `AGENTS.md` 契約已成立，非指 owner 已核准 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 上游業務決策 | DEC-008、DEC-009；邊界約束來自 DEC-016、DEC-017（[`brd.md`](../../01_requirements/brd.md)） |
| 上游需求 | FR-032、FR-033、FR-034、FR-035、FR-036、FR-037；NFR-015、NFR-016（[`srs.md`](../../01_requirements/srs.md) §2.4、§3） |
| 驗收對應 | ACPT-030、ACPT-031、ACPT-032、ACPT-033、ACPT-034（內文在 [`prd.md`](../../01_requirements/prd.md)）；UC-002 |
| 受本決策約束的元件 | MOD-ENG（Ancai）為唯一實作者；MOD-SRV-SCENE（Bella）為唯一對外入口；MOD-AGT（Yen）與 MOD-RAG（Django）明文不得產出座標；MOD-WEB（Bella）只呈現裁決結果 |
| 相關 ADR | [ADR-001](./ADR-001-layout-json-scene-json-boundary.md)（資料邊界）、[ADR-003](./ADR-003-dual-path-shapely-raster-engine.md)（雙路徑分工與 OPEN-21／OPEN-22 的技術面）、[ADR-007](./ADR-007-centimeter-unit-contract.md)（公分契約）、[ADR-011](./ADR-011-agent-pipeline-flag-isolation.md)（並存管線隔離） |
| 取代關係 | 無 Supersedes／Superseded-by |
| 下游文件 | [`sad.md`](../sad.md)、[`lld.md`](../../04_design/lld.md)、[`api_spec.md`](../../04_design/api_spec.md) ＋ [`openapi-scene-v1.yaml`](../../04_design/openapi-scene-v1.yaml)、[`ui_spec-step6-layout-2d.md`](../../02_ux_ui/ui_spec-step6-layout-2d.md)、[`test_plan.md`](../../05_qa/test_plan.md)、[`runbook-placement-blocked.md`](../../06_ops/runbook-placement-blocked.md) |
| 待確認 | OPEN-21（雙路徑正面朝向 +y／−y 相反）、OPEN-22（`CLEARANCE_BY_TYPE` 與 `CLEARANCE_OF` 鍵值與深度不同）；另 §4.3 的延遲目標值依 NFR-025 仍無來源 |
