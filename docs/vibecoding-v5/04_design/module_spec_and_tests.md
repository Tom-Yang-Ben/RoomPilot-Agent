# 模組規格與測試案例 - backend/engine 碰撞與淨空檢查（含新子系統：工程文件 MVP、家具 RAG runtime）

> 本文件由 VibeCoding v5.0 模板 04_design/module_spec_and_tests.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04 | **狀態:** 已完成（規格對照現行工作樹；測試於本日實測，證據見文末「測試證據」）

**對應架構文件**: [`../03_architecture/architecture_and_design.md`](../03_architecture/architecture_and_design.md)；`docs/contracts/FURNITURE_ENGINEERING_RULES.md`（鐵律第 4 條：「家具座標、碰撞與淨空是否合法，只能由 `backend.engine` 判定」，FURNITURE_ENGINEERING_RULES.md:13）；工程文件 MVP 契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`；RAG runtime 契約 `docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md`
**對應 BDD Feature**: [`../01_requirements/bdd_guide.md`](../01_requirements/bdd_guide.md)

**與舊導入版的關係**：本文件取代 `docs/vibecoding/07_module_specification_and_tests.md`（2026-07-26 對舊分支填寫）。舊版聚焦 backend/engine 單一模組；本版對現行工作樹重查全部行號與測試數，並新增舊版完全沒有的兩個子系統規格——`backend/server/engineering/`（工程文件 MVP）與 `backend/spatial_data/rag/`（家具 RAG runtime），以及其他新增 server 模組的測試對照。

---

## 模組 A: backend/engine（碰撞/淨空檢查——核心規格）

**範圍界定**：聚焦三個檔案——`backend/engine/geometry.py`（本體碰撞，76 行）、`backend/engine/clearance.py`（開合淨空，113 行）、`backend/engine/models.py`（資料契約，76 行）。同套件的 `placement.py`（自動擺位，135 行）、`adjustment.py`（移動/旋轉，91 行）是這組檢查的消費者，只在文末簡列；`dxf_room.py`（127 行）、`schema.py`（99 行）不在本篇範圍。套件合計 717 行（`wc -l backend/engine/*.py`）。

### 單位與座標契約（models.py:1-13 docstring）

| 項目 | 約定 |
| :--- | :--- |
| 長度單位 | 一律公分（cm）（models.py:10；schema.py:9 同樣宣告） |
| 座標系 | 原點在平面圖左下角，X 向右、Y 向上 |
| position | 指物件中心點（`pos_x`, `pos_y`） |
| rotation | 逆時針角度（度）；0 度時家具正面朝 +Y |
| 尺寸軸向 | width 沿本地 X、depth 沿本地 Y、height 沿 Z |

### 資料結構（models.py，行號為現行工作樹實查）

| dataclass | 位置 | 欄位 | 說明 |
| :--- | :--- | :--- | :--- |
| `Wall` | models.py:18 | `x1, y1, x2, y2, thickness` | 一段有厚度的牆線段；碰撞時展開成旋轉矩形 |
| `Room` | models.py:28 | `width, depth, walls` | 房間矩形邊界 + 牆體清單；`walls` 可為空清單 |
| `ClearanceZone` | models.py:36 | `side, depth` | 開合淨空需求；`side` 以「未旋轉時家具自己的方向」為準，合法值 `front`/`back`/`left`/`right` |
| `FurnitureCatalogItem` | models.py:48 | `type, name, width, depth, height, style, price, glb_path, clearance` | 型錄屬性，不含座標；`clearance=None` 表示無開合淨空需求 |
| `PlacedFurniture` | models.py:62 | `id, catalog, pos_x, pos_y, rotation`；另有 `bounds()`（models.py:73） | 擺放結果；`id` 為唯一識別碼（如 `sofa_1`） |

### 公開介面總覽

| 函式 | 位置 | 角色 |
| :--- | :--- | :--- |
| `furniture_polygon(item)` | geometry.py:14 | 家具 → 旋轉後 Shapely 多邊形（以中心點旋轉） |
| `wall_polygon(wall)` | geometry.py:26 | 牆線段 → 有厚度的旋轉矩形；長度 < 1e-4 回傳空多邊形（geometry.py:30-31） |
| `room_polygon(room)` | geometry.py:39 | 房間邊界 `box(0, 0, width, depth)` |
| `hits_wall(item, room)` | geometry.py:44 | 本體是否與任一牆相交 |
| `hits_furniture(item, others)` | geometry.py:52 | 本體是否與其他家具相交；回傳撞到的那件或 `None`；同 `id` 跳過（geometry.py:55-56） |
| `out_of_bounds(item, room)` | geometry.py:62 | 本體是否超出房間邊界（`poly.within`） |
| `check_placement(item, room, others)` | geometry.py:67 | 本體檢查統一入口 |
| `clearance_polygon(item)` | clearance.py:29 | 家具的淨空範圍多邊形；無需求回傳 `None` |
| `clearance_conflict(item, room, others)` | clearance.py:56 | 淨空衝突檢查 |
| `check_placement_with_clearance(item, room, others)` | clearance.py:89 | 本體 + 淨空 + 反向檢查的總入口 |

### 消費端（逐一實查）

| 消費者 | 位置 | 用法 |
| :--- | :--- | :--- |
| `backend/engine/placement.py` | placement.py:7 | `import check_placement_with_clearance as check_placement`——自動擺位（placement.py:43）與鄰接軟裝擺位（`place_adjacent_to_furniture`，placement.py:109）走淨空版檢查；批次擺位 `place_furniture_batch`（placement.py:115）本身不直接呼叫檢查，逐件委派 `place_furniture` |
| `backend/engine/placement.py`（覆蓋物例外） | placement.py:8, 64 | 另 `import check_placement as check_body_placement`（本體版）——`place_overlay_on_furniture`（地毯類覆蓋物）只做本體檢查、不查淨空（舊導入版未記錄此分流；程式碼側自 2026-07-24 commit b04833ce 起即有，非後續新增） |
| `backend/engine/adjustment.py` | adjustment.py:9 | 淨空版檢查，供移動（軸分離）與旋轉的合法性判斷 |
| `backend/server/scene_service.py` | scene_service.py:19（import）；1856、1858、2007（`generate_layout` 本體候選驗證）與 1030（輔助函式 `_grid_place_in_boundary`，scene_service.py:992，僅由 `generate_layout` 於 1905、2023 呼叫）；1698 `validate_single_placement`（實際檢查在 1731、1742） | 2D 佈局與第 6 步拖曳驗證 |
| `POST /api/scene/validate` | backend/server/main.py:3492 → main.py:3500 呼叫 `validate_single_placement` | 前端拖曳落點的 HTTP 入口，回 `{ok, reason}` |

**拖曳驗證的前置過濾（scene_service.py:1698-1743）**：`validate_single_placement` 在進引擎前先做三層閘門——(1) 家具必須完整落在某一間房的聯集邊界內（1715-1717）；(2) 門弧與窗前禁區對所有型別一律適用，與 `generate_layout` 共用同一份 `placement_forbidden_zones`（1720-1727）；(3) 覆蓋物（地毯類）只查本體、免碰撞型別直接通過（1729-1734）。`others` 清單排除免碰撞型別與 `placement_failed` 物件（1735-1741）後才交給 `check_placement_with_clearance`（1742）。

### 淨空資料來源（業務規則）

`backend/catalog/style_db.py:185` 的 `CLEARANCE_BY_TYPE` 只對 4 種類型設定前方淨空：`bookcase` 40cm、`sideboard` 40cm、`wardrobe` 50cm、`desk` 50cm（均 `side="front"`，現行工作樹實查）。尺寸的合理性修補由上游 `style_db.sanitize_size_cm`（style_db.py:119，規則表 `_SIZE_RULES` 在 style_db.py:23）負責，引擎層不驗證尺寸。

---

### 規格: check_placement

**位置**: `backend/engine/geometry.py:67`
**簽名**: `check_placement(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`

**描述**: 本體碰撞統一檢查入口。依序檢查出界 → 穿牆 → 與其他家具重疊，回傳 `None` 表示合法，否則回傳繁體中文失敗原因字串。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `item.catalog.width` / `depth` 為正數公分——函式本身不驗證，由上游 `style_db.sanitize_size_cm` 修補 2. `room` 為角落原點座標系，`walls` 可為空 3. `others` 中每件的 `id` 應唯一；與 `item.id` 相同者會被跳過不檢查（geometry.py:55-56） |
| **後置條件** | 1. 回傳 `None` ⇔ `out_of_bounds`、`hits_wall`、`hits_furniture` 三項全部通過 2. 失敗時回傳固定詞彙字串，且只回報「第一個」失敗原因（短路）：`"物件超出空間範圍"`（geometry.py:70）→ `"與牆體穿透"`（:72）→ `"與「{家具名}」重疊"`（:75） 3. 不修改 `item` / `room` / `others` 任何欄位（純查詢） |
| **不變性** | 1. 碰撞以旋轉後的實際多邊形判斷（Shapely `intersects` / `within`），非包圍盒近似，支援任意角度 2. 檢查順序固定：出界 → 穿牆 → 重疊（TC-301 釘死本體優先的延伸） 3. 失敗字串是對外契約——`examples/demo_agent_flow.py:10-12` 列為詞彙表、`tests/test_placement.py:79` 與 `tests/test_clearance.py:119` 斷言完整字串，改字即破壞性變更 4. 家具邊緣與房間邊界恰好重合不判出界（Shapely `within` 容許邊界接觸）——但若邊界線上有牆體（如測試共用 fixture 的四面牆壓在邊界線上），同一位置仍會因穿牆失敗（見 TC-006） |

---

### 規格: clearance_polygon

**位置**: `backend/engine/clearance.py:29`
**簽名**: `clearance_polygon(item: PlacedFurniture) -> Polygon | None`

**描述**: 算出家具的開合淨空範圍（衣櫃門、抽屜等打開所需的額外矩形），不含本體。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `item.catalog.clearance` 為 `None` 或合法 `ClearanceZone` 2. `clearance.side` 必須在 `front`/`back`/`left`/`right` 四值內——超出即 `_SIDE_OFFSETS`（clearance.py:20）在 clearance.py:36 查表 `KeyError`，無防禦處理（見 TC-104） |
| **後置條件** | 1. 回傳 `None` ⇔ 家具無淨空需求（clearance.py:32-33） 2. 否則回傳一個「與本體只共邊、不重疊」的矩形：`front`/`back` 時與家具同寬、沿 ±Y 延伸 `clearance.depth`（clearance.py:38-43）；`left`/`right` 時與家具同深、沿 ±X 延伸（:44-49） 3. `item.rotation` 非 0 時，淨空矩形以家具中心為原點跟著旋轉（:51-52） |
| **不變性** | 1. 不修改輸入 2. 淨空矩形面積 = （家具該面邊長）×`clearance.depth`（`depth` ≤ 0 的行為未定義，無測試，見 TC-106） |

---

### 規格: clearance_conflict

**位置**: `backend/engine/clearance.py:56`
**簽名**: `clearance_conflict(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`

**描述**: 檢查「這件家具的淨空範圍」是否被牆、其他家具本體、或其他家具的淨空侵犯。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 同 `check_placement`；另 `item` 若無淨空需求則直接通過（clearance.py:66-68） |
| **後置條件** | 1. 回傳 `None` ⇔ 無淨空需求，或三段檢查全過 2. 檢查順序固定：淨空撞牆 → 淨空撞其他家具本體 → 淨空撞其他家具的淨空；失敗字串依序為 `"「{我}」的開合空間被牆體阻擋"`（clearance.py:73）、`"「{我}」的開合空間與「{他}」衝突"`（:80）、`"「{我}」與「{他}」的開合空間互相衝突"`（:84） 3. 同 `id` 的 other 跳過（:76-77）；不修改輸入 |
| **不變性** | 1. 只檢查「item 的淨空」被誰侵犯；「item 的本體」壓到別人淨空屬反向檢查，在 `check_placement_with_clearance` 補上 2. 淨空互撞為刻意從嚴設計（clearance.py:11 檔頭註解：「兩個門互相打架——較嚴格，可討論放寬」） |

---

### 規格: check_placement_with_clearance

**位置**: `backend/engine/clearance.py:89`
**簽名**: `check_placement_with_clearance(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`

**描述**: 本體碰撞 + 淨空檢查的總入口。正式流程（自動擺位 `placement.py`、微調 `adjustment.py`、2D 佈局與拖曳驗證 `scene_service.py`）一律經此函式判定合法性；唯一例外是覆蓋物擺位 `place_overlay_on_furniture` 只走本體版（placement.py:64）。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. 同 `check_placement` 2. `others` 應為與 `item` 同一房間座標系下的既有家具（呼叫端 `scene_service.py:1735-1741` 已先排除 `placement_failed` 與免碰撞型別的物件） |
| **後置條件** | 1. 回傳 `None` ⇔ 依序通過：`check_placement`（出界→穿牆→重疊，clearance.py:97）→ `clearance_conflict`（淨空撞牆→撞他人本體→淨空互撞，:101）→ 反向檢查（item 本體壓到他人淨空，字串 `"擋住了「{他}」的開合空間"`，:105-112） 2. 全序固定且短路，只回報第一個失敗原因 3. 不修改輸入 |
| **不變性** | 1. **增量合法性**：若既有佈局兩兩合法，且新加入件經本函式對全部既有件檢查通過，則整體佈局仍兩兩合法——因為新件與每一既有件之間「本體×本體、本體×淨空（雙向）、淨空×淨空」四種關係全數被查。`place_furniture_batch`（placement.py:115）的逐件放置正依賴此性質 2. 本體問題優先於淨空問題回報（TC-301 釘死） |

---

### 模組 A 測試案例

**現況**：直接單元測試在 `tests/test_clearance.py`（10 個）與 `tests/test_placement.py`（18 個，其中 5 個直接測 `check_placement`，其餘 13 個測消費端 `placement.py` / `adjustment.py` / `schema.py`）。本日實測：`.venv/bin/python -m pytest tests/test_placement.py tests/test_clearance.py -q` → **28 passed, 0.69s**。

共用測資：兩檔皆用 500cm × 400cm 四面圍牆的矩形房間 fixture；淨空案例用「150×60cm 衣櫃、front 60cm 淨空」與「200×90cm 沙發（無淨空）」。

#### check_placement（geometry.py）

##### TC-001: 正常路徑——房間正中央合法

- **Arrange**: 500×400 房間；200×90 沙發置於 (250, 200)
- **Act**: `check_placement(item, room, [])`
- **Assert**: 回傳 `None`
- **狀態**: 已有 —— `tests/test_placement.py::test_center_placement_is_valid`（test_placement.py:69）

##### TC-002: 無效位置——出界

- **Arrange**: 沙發置於 (1000, 1000)（房間外）
- **Act**: `check_placement`
- **Assert**: 回傳 `"物件超出空間範圍"`
- **狀態**: 已有 —— `tests/test_placement.py::test_out_of_bounds_detected`（test_placement.py:75）

##### TC-003: 無效位置——穿牆

- **Arrange**: 沙發本體壓進下牆
- **Act**: `check_placement`
- **Assert**: 回傳 `"與牆體穿透"`
- **狀態**: 已有 —— `tests/test_placement.py::test_wall_collision_detected`（test_placement.py:82）

##### TC-004: 無效位置——與家具重疊（含名稱回報）

- **Arrange**: 沙發與茶几同置一點
- **Act**: `check_placement(table, room, [sofa])`
- **Assert**: 回傳 `"與「沙發」重疊"`
- **狀態**: 已有 —— `tests/test_placement.py::test_furniture_overlap_detected`（test_placement.py:89）

##### TC-005: 正常路徑——距離足夠不誤判

- **狀態**: 已有 —— `tests/test_placement.py::test_furniture_no_false_positive_when_apart`（test_placement.py:97）

##### TC-006: 邊界情況——家具邊緣與房間邊界恰好重合 **(待補)**

- **Arrange**: 500×400 **無牆**房間（`walls=[]`）；200×90 沙發置於 (100, 45)，左、下兩邊貼齊房間邊界
- **Act**: `check_placement`
- **Assert**: 應釘死為不出界（`None`）——Shapely `within` 容許邊界接觸；注意若沿用共用 fixture 的四面圍牆房間，同一座標會因牆中心線壓在邊界線上回傳 `"與牆體穿透"`，測試必須用無牆房間隔離出界判定
- **狀態**: 現行工作樹仍無此測試（`grep def test_` 逐一核對，測試清單與 2026-07-26 相同）

##### TC-007: 無效輸入——零尺寸家具 **(待補)**

- **Arrange**: `width=0, depth=0` 的家具置於房間中央
- **Act**: `check_placement`
- **Assert**: 退化多邊形通過所有檢查、回傳 `None`（舊導入版 2026-07-26 實測記錄），屬未定義行為；需先裁決契約（防禦 vs 釘死現況）再寫測試
- **狀態**: 待補

##### TC-008: 邊界情況——退化牆（長度 < 1e-4）不影響判定 **(待補)**

- **Arrange**: 房間含一段起訖同點的牆 `Wall(10, 10, 10, 10)`；家具合法置於房內
- **Act**: `check_placement`
- **Assert**: `wall_polygon` 回傳空多邊形（geometry.py:30-31），不應誤報穿牆；無正式測試
- **狀態**: 待補

##### TC-009: 邊界情況——非 90 倍數旋轉的碰撞判定 **(待補)**

- **Arrange**: 家具 `rotation=45`，斜置於牆邊/另一家具旁
- **Act**: `check_placement`
- **Assert**: 以旋轉後多邊形判定（規格宣稱支援任意角度），現有測試僅覆蓋 0/90/180 度
- **狀態**: 待補

#### clearance_polygon（clearance.py）

##### TC-101: 正常路徑——無淨空需求回 None

- **狀態**: 已有 —— `tests/test_clearance.py::test_no_clearance_returns_none`（test_clearance.py:51）

##### TC-102: 正常路徑——front 淨空往 +Y 延伸、不含本體

- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_polygon_extends_front`（test_clearance.py:57）

##### TC-103: 邊界情況——旋轉 180 度後淨空改朝 -Y

- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_rotates_with_furniture`（test_clearance.py:71）

##### TC-104: 無效輸入——side 不在四值內 **(待補)**

- **Arrange**: `ClearanceZone(side="top", depth=50)`
- **Act**: `clearance_polygon`
- **Assert**: 現行實作在 clearance.py:36 查 `_SIDE_OFFSETS` 拋 `KeyError`，無防禦；測試應釘死此行為或改加防禦後測防禦
- **狀態**: 待補

##### TC-105: 邊界情況——side 為 back/left/right 的延伸方向 **(待補)**

- **Assert**: 依 `_SIDE_OFFSETS`（clearance.py:20-26）各朝 -Y/-X/+X 延伸、與該面同長；現有測試只覆蓋 `front`（含旋轉），另外三面零覆蓋——`CLEARANCE_BY_TYPE` 現行 4 類雖全為 `front`，引擎介面仍宣告支援四面
- **狀態**: 待補

##### TC-106: 無效輸入——clearance.depth ≤ 0 **(待補)**

- **Assert**: 行為未定義（退化矩形），無測試
- **狀態**: 待補

#### clearance_conflict（clearance.py）

##### TC-201: 正常路徑——門朝房內無阻礙

- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_clear_when_open_space`（test_clearance.py:83）

##### TC-202: 業務規則——淨空撞牆（門打不開）

- **Assert**: 回傳 `"「衣櫃」的開合空間被牆體阻擋"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_blocked_by_wall`（test_clearance.py:89）

##### TC-203: 業務規則——淨空撞其他家具本體

- **Assert**: 回傳 `"「衣櫃」的開合空間與「沙發」衝突"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_blocked_by_furniture_body`（test_clearance.py:96）

##### TC-204: 業務規則——兩件家具淨空互撞

- **Assert**: 回傳 `"「衣櫃」與「衣櫃」的開合空間互相衝突"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_two_clearances_conflict`（test_clearance.py:104）

##### TC-205: 業務規則——三段檢查次序釘死 **(待補)**

- **Assert**: 同時「淨空撞牆」且「淨空撞他人本體」時應回報撞牆訊息（次序：牆 → 他人本體 → 互撞，clearance.py:70-84）；現況次序只由實作保證，無測試
- **狀態**: 待補

##### TC-206: 邊界情況——others 內含同 id 物件被跳過 **(待補)**

- **Assert**: 同 `id` 不得自撞（geometry.py:55-56、clearance.py:76-77、clearance.py:108-109 皆有跳過邏輯）；無直接測試
- **狀態**: 待補

#### check_placement_with_clearance（clearance.py）

##### TC-301: 業務規則——本體檢查優先於淨空回報

- **Arrange**: 衣櫃置於 (1000, 1000)（同時出界又必有淨空問題）
- **Assert**: 回傳 `"物件超出空間範圍"` 而非淨空訊息
- **狀態**: 已有 —— `tests/test_clearance.py::test_body_check_runs_first`（test_clearance.py:115）

##### TC-302: 業務規則——反向檢查（本體壓到別人的淨空）

- **Assert**: 回傳 `"擋住了「衣櫃」的開合空間"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_reverse_check_body_blocks_others_clearance`（test_clearance.py:122）

##### TC-303: 正常路徑——完整合法佈局全數通過

- **狀態**: 已有 —— `tests/test_clearance.py::test_valid_layout_passes_all_checks`（test_clearance.py:134）

#### 消費端測試對照（placement.py / adjustment.py / schema.py，簡列）

以下 13 個測試不直接測檢查函式，但全數以檢查函式為合法性判準（`tests/test_placement.py`，本日均通過）：

| 對象 | 測試 |
| :--- | :--- |
| `placed_to_dict` 公分契約（schema.py:18） | `test_placed_furniture_payload_declares_centimeter_contract` |
| `place_furniture`（placement.py:10）找到合法位置/塞不下回報失敗 | `test_place_furniture_finds_valid_position`、`test_place_furniture_fails_when_room_too_small`（失敗字串 `"找不到合法擺放位置"`，見 demo_agent_flow.py:12 詞彙表） |
| `place_furniture_batch`（placement.py:115）後放避開先放 | `test_place_furniture_batch_avoids_overlap` |
| `place_overlay_on_furniture`（placement.py:50）地毯沿用目標座標 | `test_overlay_keeps_target_coordinates_in_centimeters` |
| `place_adjacent_to_furniture`（placement.py:72）12cm 間隙 | `test_adjacent_accessory_uses_twelve_centimeter_gap` |
| `move_furniture`（adjustment.py:11）軸分離 | `test_move_valid_direction_succeeds`、`test_move_axis_separation_blocks_only_bad_axis`、`test_move_both_axes_blocked_reports_failure`、`test_move_blocked_by_other_furniture` |
| `rotate_furniture`（adjustment.py:54）合法旋轉/穿牆還原 | `test_rotate_valid_angle_succeeds`、`test_rotate_into_wall_reverts` |
| `adjust_furniture`（adjustment.py:72）未知動作 | `test_unknown_action_returns_failure`（字串含 `"未知的動作"`） |

---

## 模組 B: backend/server/engineering（工程文件 MVP——舊導入版無此子系統）

**範圍界定**：14 個 .py 合計 3,111 行（`wc -l`），另有 Node adapter `workbook_builder.mjs`。流程為 **snapshot → lock → packages → jobs → documents**（契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`；OpenAPI `docs/contracts/engineering_openapi.yaml`；JSON Schema `docs/contracts/project_snapshot.schema.json`、`report_payload.schema.json`、`risk_results.schema.json`）。HTTP 入口 8 條路由掛在 `build_engineering_router`（api.py:47，`prefix="/api/v1"`，由 main.py:218-223 include）。本篇規格聚焦兩個守門函式與一條產出流程；QuantityService（quantity.py:25）、ExistingEngineRuleService（rules.py:70）、CostService（cost.py:13）、ScheduleService（schedule.py:21）、DocumentService（documents.py:19）、EngineeringOrchestrator（orchestrator.py:22）以測試對照簡列。

### 規格: EngineeringRepository.save_snapshot

**位置**: `backend/server/engineering/repository.py:127`
**簽名**: `save_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot`

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `snapshot` 為公分制 `ProjectSnapshot`（models.py 定義；公尺制 payload 在 API 層被拒，見 TC-403） 2. API 層要求 path 的 `project_id`/`revision` 與 payload 一致，否則 422 `PATH_PAYLOAD_MISMATCH`（api.py:120） 3. 來源專案 revision 未前進（否則 `SnapshotSourceConflict`，repository.py:22） |
| **後置條件** | 1. snapshot 持久化（SQLite 或 PostgreSQL 後端，repository.py:40/:173；持久層由 `project_store_getter` 決定） 2. 覆寫已鎖定 revision 時拋 `LockedRevisionError`（repository.py:18）→ API 409 `LOCKED_REVISION_CANNOT_BE_OVERWRITTEN`（api.py:130） 3. 來源已前進 → API 409 `SNAPSHOT_SOURCE_REVISION_STALE`（api.py:138） |
| **不變性** | 已鎖定（`approval_status == "designer_confirmed"`）的 revision 不可變——這是工程文件產出的信任基礎 |

### 規格: EngineeringRepository.lock_revision

**位置**: `backend/server/engineering/repository.py:247`；HTTP 入口 `POST /api/v1/projects/{project_id}/revisions/{revision}/lock`（api.py:325）

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. 對應 snapshot 存在（否則 API 404 `SNAPSHOT_NOT_FOUND`，api.py:340） 2. 來源專案 revision 未前進（否則 409 `SNAPSHOT_SOURCE_REVISION_STALE`，api.py:348） 3. body 帶 `confirmed_by` |
| **後置條件** | snapshot 的 `approval_status` 進入 `designer_confirmed`，成為 packages 產出的唯一合格狀態 |
| **不變性** | 鎖定後 snapshot 不可再被 `save_snapshot` 覆寫（TC-401） |

### 規格: 產出流程 POST engineering-packages → jobs → documents

**位置**: `backend/server/engineering/api.py:172`（202）→ `run_generation_job`（背景任務）→ `GET /api/v1/jobs/{job_id}`（api.py:271）→ `GET /api/v1/packages/{package_id}`（api.py:281）→ `GET /api/v1/documents/{document_id}/download`（api.py:294）

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. snapshot 存在（否則 404 `SNAPSHOT_NOT_FOUND`，api.py:187） 2. `snapshot.approval_status == "designer_confirmed"`（api.py:191），否則 409 `REVISION_NOT_LOCKED`（api.py:195） |
| **後置條件** | 1. 建立 `JobStatus`，`job_id = "job_" + uuid4().hex[:12]`（api.py:200），初始 `queued`，由 BackgroundTasks 執行 2. 成功時 job 寫入 `package_id` 與 documents；失敗分兩類 `error_code`：`XLSX_ADAPTER_UNAVAILABLE`（Node adapter 缺席，api.py:258）與 `ENGINEERING_PACKAGE_FAILED`（api.py:265） 3. `GET packages/{id}` 回 `ReportPayload`（404 `PACKAGE_NOT_FOUND`）；下載僅允許落在 `<PROJECT_DIR>/.runtime/engineering` 之下的實檔（`path.is_relative_to(root)` 防護，api.py:301），支援 .json/.html/.xlsx |
| **不變性** | 1. 幾何規則不重算——`ExistingEngineRuleService` 委派既有 `backend.engine` 判定（TC-405） 2. production 模式缺價不得編造總價（TC-406） 3. repository 掛在 `router.engineering_repository`（api.py:360）供測試共用同一持久層 |

### 模組 B 測試案例（7 檔 19 個測試函式；本日實測見文末證據）

##### TC-401: 業務規則——鎖定後 revision 不可覆寫

- **狀態**: 已有 —— `tests/test_engineering_snapshot_api.py::test_snapshot_save_lock_and_locked_revision_is_immutable`（test_engineering_snapshot_api.py:66）

##### TC-402: 業務規則——來源專案前進後不可再鎖定

- **狀態**: 已有 —— `test_snapshot_cannot_lock_after_source_project_revision_changes`（:93）

##### TC-403: 無效輸入——公尺制 payload 與 path 不一致被拒

- **狀態**: 已有 —— `test_snapshot_rejects_meter_contract_and_path_mismatch`（:119）

##### TC-404: 業務規則——未鎖定 revision 產包回 409

- **狀態**: 已有 —— `tests/test_engineering_documents_api.py::test_unlocked_revision_returns_required_409`（test_engineering_documents_api.py:114）

##### TC-405: 業務規則——工程量用多邊形公分而非包圍盒；重疊委派既有引擎

- **狀態**: 已有 —— `tests/test_engineering_quantity_rules.py::test_quantity_uses_polygon_cm_not_bounding_box`（:62）、`test_rule_service_delegates_overlap_to_existing_engine`（:73）、`test_existing_placement_failure_is_not_silently_accepted`（:93）

##### TC-406: 業務規則——production 模式缺價保持 unknown、不編造總價

- **狀態**: 已有 —— `tests/test_engineering_cost_schedule.py::test_production_mode_keeps_missing_prices_and_productivity_unknown`（:70）、`test_demo_mode_uses_only_demo_records_and_exact_cost_formula`（:92）；`tests/test_engineering_documents_api.py::test_production_report_has_pending_quotes_and_no_fake_total`（:204）

##### TC-407: 正常路徑——demo E2E 產出 HTML/JSON 與雙 sheet XLSX

- **狀態**: 已有但環境相依 —— `test_demo_e2e_generates_html_json_and_two_sheet_artifact_xlsx`（test_engineering_documents_api.py:130）；本日實測 **skipped**（`artifact-tool module path is not configured`，test_engineering_documents_api.py:134）——XLSX 產生走 Node adapter `workbook_builder.mjs`，node 路徑由環境變數 `ROOMPILOT_ARTIFACT_NODE` 指定

##### TC-408: 其他覆蓋（簡列）

- persistence 表結構：`test_postgres_schema_contains_engineering_persistence_tables`（test_engineering_snapshot_api.py:138）
- Advanced RAG 檢索：`tests/test_engineering_advanced_rag.py`（2 個）
- 契約匯出：`tests/test_engineering_contract_exports.py`（2 個，對照 export_contracts.py 113 行）
- 前端頁：`tests/test_engineering_frontend.py`（3 個，對照 static/engineering.html + engineering.js）

**待補（本篇識別）**：job 輪詢的失敗路徑（`XLSX_ADAPTER_UNAVAILABLE` vs `ENGINEERING_PACKAGE_FAILED` 的 error_code 分流，api.py:258/:265）無直接單元測試釘死；documents 下載的路徑逃逸防護（api.py:301）無負面測試。

---

## 模組 C: backend/spatial_data/rag（家具 RAG runtime——舊導入版無此子系統）

**範圍界定**：11 個 .py 合計 1,234 行（`wc -l backend/spatial_data/rag/*.py`，含一個 `__init__.py`），另有受控詞彙資料 `rag/data/taxonomy.json`（6 風格、24 氛圍詞、4 圖樣）與 `rag/data/category_groups.json`（19 家具群組、6 房型預設組）。核心是 `service.py`（496 行）：「End-to-end LLM parser → PostgreSQL pgvector → Django reranker service」（service.py:1）。HTTP 入口經 `backend/server/rag_api.py`（APIRouter 無 prefix，rag_api.py:26；main.py:217 include）：`GET /rag`（:136）、`GET /api/rag/status`（:141）、`POST /api/rag/search`（:146）、`POST /api/rag/search/jobs`（202，:155）、`GET /api/rag/search/jobs/{job_id}`（:187）。

### 輸入契約（models.py，Pydantic）

| 模型 | 關鍵欄位界線 |
| :--- | :--- |
| `RagSearchRequest`（models.py:80） | `query` 長度 1–1000（:83）；`top_k` 預設 8、範圍 1–8（:84） |
| `RagQueryPlan`（models.py:54） | `styles` ≤ 2、`moods` ≤ 3、`items` 1–6 件、`confidence` 0–1、`budget_total` > 0 |
| `RagQueryItem`（models.py:36） | `item_id` 正則 `^[a-z0-9][a-z0-9_-]*$`、`quantity` 1–8、`role` ∈ {anchor, accent}、`styles` ≤ 2 |

型別化失敗（errors.py）：`RagError` 基底（:4），子類 `RagDisabledError`（:8）、`RagDependencyError`（:12）、`RagDatabaseError`（:16）、`RagUpstreamError`（:20）。

### 規格: FurnitureRagService.status / _require_ready

**位置**: `backend/spatial_data/rag/service.py:61`（status）、:128（_require_ready）

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 無（status 為純診斷查詢） |
| **後置條件** | 回傳 `{ready, blockers, ...}`；blockers 逐項累積（service.py:71-102）：`feature_disabled`、`parser_provider_invalid`、`{provider}_api_key_missing`、`{provider}_package_missing`、`rag_model_packages_missing`、`embedding_model_cache_missing`、`reranker_model_cache_missing`、`furniture_embeddings_empty`（pgvector 表無資料即 blocker）、`filtered_search_function_missing`、`postgresql_unavailable`；`ready = not blockers`（:109） |
| **不變性** | `_require_ready` 在 blockers 非空時拋型別化例外：僅 `feature_disabled` → `RagDisabledError`，其餘 → `RagDependencyError`（:131-137）；服務不在半就緒狀態下執行檢索 |

### 規格: FurnitureRagService.search

**位置**: `backend/spatial_data/rag/service.py:351`
**簽名**: `search(self, request: RagSearchRequest, progress: ProgressReporter | None = None) -> dict[str, Any]`

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `request` 通過 Pydantic 驗證 2. 就緒守門通過（見上） |
| **後置條件** | 1. 依序執行：readiness（進度 3%）→ LLM parsing（8%）→ planning（20%，載入受控詞彙、依 pgvector 價格統計分配預算 `allocate_budget`）→ 分批向量檢索 `_search_items_batched`（anchor 先於 accent，service.py:369）→ hydration（型錄補水）與去重 2. PostgreSQL 失敗一律轉 `RagDatabaseError`（:151、:178、:252、:424），不外洩底層例外 3. 進度可經 `progress` 回報（202 job 模式用） |
| **不變性** | 1. 檢索只回受控詞彙界定的結果；LLM 只負責解析查詢（parser.py dispatch，OpenAI/Anthropic Structured Outputs adapter，無 fallback 降級）2. rerank 依 item role 取 top 20（anchor）/12（accent）再重排（TC-505） 3. 本服務不做幾何決策（CLAUDE.md 產品邊界：幾何只在 `backend/engine/`） |

### HTTP 層契約（rag_api.py）

- `POST /api/rag/search` 把型別化失敗映射為服務錯誤碼（rag_api.py:146；對照 TC-502）。
- `POST /api/rag/search/jobs`：active 上限 `RAG_JOB_MAX_ACTIVE = 1`（rag_api.py:30），超過回 429 `rag_job_capacity_reached`（:163-166）；以 daemon Thread 執行。
- `GET /api/rag/search/jobs/{job_id}`：不存在回 404 `rag_job_not_found`（:194）。

### 模組 C 測試案例（3 檔 16 個測試函式；本日實測見文末證據）

##### TC-501: 無效輸入——受控 schema 保留 null、拒絕未知值

- **狀態**: 已有 —— `tests/test_rag_domain.py::test_controlled_schema_preserves_nulls_and_rejects_unknown_values`（:93）

##### TC-502: 業務規則——HTTP 層把型別化失敗映射為對應狀態碼

- **狀態**: 已有 —— `tests/test_rag_api.py::test_rag_api_maps_failures`（:70，參數化）；另 `test_rag_page_status_success_and_validation`（:41）

##### TC-503: 正常路徑——202 job 回報進度與結果；上游失敗細節不外洩

- **狀態**: 已有 —— `test_rag_job_api_reports_progress_and_result`（:95）、`test_rag_job_api_hides_upstream_failure_detail`（:115）

##### TC-504: 業務規則——預算過濾與 Django score 公式

- **狀態**: 已有 —— `tests/test_rag_domain.py::test_budget_filters_and_django_score_formula`（:136）

##### TC-505: 業務規則——依 item role 取 top 20/12 重排；結果補水與去重

- **狀態**: 已有 —— `test_service_reranks_top_20_or_12_by_item_role`（:390）、`test_service_groups_hydrates_and_deduplicates_results`（:425）

##### TC-506: 無效輸入——parser provider 設定守門

- **狀態**: 已有 —— `test_settings_select_only_the_configured_rag_parser`（:118）、`test_configured_parser_rejects_unknown_provider`（:261）、`test_openai_parser_uses_structured_outputs_without_fallback`（:186）、`test_anthropic_parser_uses_structured_outputs_without_fallback`（:216）

##### TC-507: 前端測試台

- **狀態**: 已有 —— `tests/test_rag_frontend.py`（4 個，對照 static/rag.html + rag.js 的 202 輪詢流程）

**待補（本篇識別）**：`status()` 的 blockers 逐項單元覆蓋（現有測試走整條 search 路徑，個別 blocker 如 `reranker_model_cache_missing` 無獨立案例）(未查證：是否被 test_rag_domain 內部 fixture 間接覆蓋，未逐行核對)。

---

## 模組 D: 其他新增 server 模組測試對照（簡列）

以下模組均為 2026-07-26 舊導入版未收錄的 server 模組（其中 `catalog_admin.py`、`runtime_catalog_repository.py` 建於 2026-07-31 commit e1e22ddf、`render_providers.py` 建於 2026-07-30 commit 614ae3a4，確為舊版之後新增；`cost_estimation.py`、`style_cards.py`、`questionnaire_visuals.py` 建檔日為 2026-07-24，早於舊導入版，只是舊版未收錄），均無獨立 DbC 規格需求（或屬資料轉接層），以測試對照收錄；深入規格見 [`api_design.md`](./api_design.md) 與各 contracts：

| 模組 | 職責與關鍵介面 | 測試 |
| :--- | :--- | :--- |
| `backend/server/cost_estimation.py`（109 行） | 第 8 步費用概算：`estimate_project_cost`（:35）、`load_default_cost_catalog`（:17，載入 `taiwan_renovation_price_seed.json`） | `tests/test_cost_estimation.py`（2 個：低/基準/高三段可追溯估價、線上價格種子保留來源連結與明示排除項）、`tests/test_cost_estimation_api.py`（1 個：版本化來源、不打真網路） |
| `backend/server/catalog_admin.py` | 型錄管理 CRUD 4 路由（prefix `/api/admin/furniture`，catalog_admin.py:29），寫入走 `backend/catalog/postgres_admin_repository.py`（764 行：交易、參照驗證、activation gate、樂觀併發、audit record） | `tests/test_postgres_catalog_crud.py`（14 個，`ls tests` 實查唯一引用 `catalog_admin` 的測試檔；無 `test_catalog_admin_api.py`／`test_postgres_admin_repository.py`）、`tests/test_postgres_catalog_contract.py`（1 個） |
| `backend/catalog/runtime_catalog_repository.py`（431 行） | Phase 4 SQL runtime catalogs（styles/surfaces/costs/quarantine）；strict PostgreSQL 模式不靜默回退掃 JSON（檔頭 docstring）；消費端 cost_estimation.py:9、style_cards.py:6、main.py:111 | `tests/test_runtime_catalog_phase4.py`；契約 `docs/contracts/POSTGRESQL_RUNTIME_CATALOG_PHASE4.md` |
| `backend/server/render_providers.py` | 第 8 步遠端生圖 provider 抽象；契約 `docs/contracts/REMOTE_RENDER_CONTRACT.md`（只經 `POST /api/projects/{id}/render-jobs` 呼叫遠端） | `tests/test_remote_render_workflow.py`（6 個）、`tests/test_render_direct_provider.py`（13 個）（`ls tests` 實查；無 `test_render_service.py`） |
| `backend/server/questionnaire_visuals.py`、`style_cards.py` | 第 5 步問卷視覺目錄（main.py:2619、:2642 兩路由）與六風格色卡 | `tests/test_questionnaire_visual_catalog.py`（14 個）、`tests/test_taiwan_style_cards.py`（8 個）（`ls tests` 實查；無 `test_questionnaire_visuals.py`／`test_style_cards.py`） |

引擎消費鏈的整合行為（拖曳驗證、2D 佈局、門弧/窗前禁區）由 `tests/test_scene_*.py` 場景測試系列覆蓋（26 支檔案，`ls tests/test_scene_*.py | wc -l`），不在本篇單元規格範圍內重列。

---

## 測試證據（2026-08-04 本日實測，指令與結果照錄）

| 指令 | 結果 |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/test_placement.py tests/test_clearance.py -q` | **28 passed**, 4 warnings, 0.69s |
| `.venv/bin/python -m pytest tests/test_engineering_*.py tests/test_rag_*.py tests/test_cost_estimation*.py -q`（12 檔逐一列名執行） | **39 passed, 1 skipped**, 0.86s；唯一 skip 在 test_engineering_documents_api.py:134（`artifact-tool module path is not configured`，見 TC-407） |
| `.venv/bin/python -m pytest -q`（全量） | **916 passed, 3 failed, 9 skipped**, 69.26s |

全量 3 個失敗均與本篇規格模組無關：

1. `tests/test_scene_v2_contract.py::test_scene_entrypoint_cache_key_matches_bundle_content`——前端 cache-busting 雜湊守約紅燈（scene.html 引用的 `?v=sha256-` 與實檔內容不符，屬 static 前端待修）。
2. `training/tests/test_annotation_drafts.py::test_house_round_trip`、`training/tests/test_room_office_stair.py::test_gt_label_separates_office_and_stairwell`——訓練側測試樹（`training/tests/`，11 支，非主 `tests/`）缺模組依賴。

### 測試現況與待補彙整

| 項目 | 數字 |
| :--- | :--- |
| 模組 A 直接單元測試 | 28 個（test_clearance.py 10 + test_placement.py 18），本日全數通過；其中 15 個直接測四個規格函式（TC-001~005、TC-101~103、TC-201~204、TC-301~303） |
| 模組 A 待補 | 9 個：TC-006（邊界重合）、TC-007（零尺寸）、TC-008（退化牆）、TC-009（斜角旋轉）、TC-104（無效 side）、TC-105（back/left/right 淨空）、TC-106（depth ≤ 0）、TC-205（淨空檢查次序）、TC-206（同 id 跳過）——與 2026-07-26 舊導入版識別的清單相同，期間未補（測試名單逐一比對確認）；其中 TC-007、TC-104、TC-106 需先裁決契約（防禦 vs 釘死現況）再寫測試 |
| 模組 B 測試 | 19 個測試函式（7 檔），本日 1 skip（環境相依 Node adapter）；待補 2 項：job error_code 分流、下載路徑逃逸負面測試 |
| 模組 C 測試 | 16 個測試函式（3 檔），本日全數通過；待補 1 項：status blockers 逐項覆蓋 |
| 全 repo 測試檔 | `tests/` 99 支 test_*.py + `tests/static/` 3 支 .test.mjs + `training/tests/` 11 支 |
