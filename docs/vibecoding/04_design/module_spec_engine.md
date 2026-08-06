# 模組規格與測試案例 - backend/engine 碰撞與淨空檢查

> 本文件由 VibeCoding 模板 07_module_specification_and_tests.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 已完成(規格對照現行程式碼;測試於本日實測 28 passed)

**對應架構文件**: `docs/contracts/FURNITURE_ENGINEERING_RULES.md`(鐵律第 4 條:「家具座標、碰撞與淨空是否合法，只能由 `backend.engine` 判定。」);`docs/vibecoding/03_architecture/sad.md`
**對應 BDD Feature**: `docs/vibecoding/01_requirements/bdd_guide.md`(其測試對照表已引用 `tests/test_placement.py` 18 個測試與 `tests/test_clearance.py` 10 個測試)

---

## 模組: backend/engine(碰撞/淨空檢查)

**範圍界定**:本篇規格聚焦三個檔案——`backend/engine/geometry.py`(本體碰撞)、`backend/engine/clearance.py`(開合淨空)、`backend/engine/models.py`(資料契約)。同套件內的 `placement.py`(自動擺位)、`adjustment.py`(移動/旋轉)是這組檢查的消費者,只在文末簡列;`dxf_room.py`、`schema.py` 不在本篇範圍。

### 單位與座標契約(models.py 檔頭 docstring)

| 項目 | 約定 |
| :--- | :--- |
| 長度單位 | 一律公分(cm) |
| 座標系 | 原點在平面圖左下角,X 向右、Y 向上 |
| position | 指物件中心點(`pos_x`, `pos_y`) |
| rotation | 逆時針角度(度);0 度時家具正面朝 +Y |
| 尺寸軸向 | width 沿本地 X、depth 沿本地 Y、height 沿 Z |

### 資料結構(models.py)

| dataclass | 欄位 | 說明 |
| :--- | :--- | :--- |
| `Wall`(models.py:17) | `x1, y1, x2, y2, thickness=10.0` | 一段有厚度的牆線段;碰撞時展開成旋轉矩形。`dxf_room.py:36` 的環邊薄牆改用 `DEFAULT_WALL_SEG_THICKNESS = 6.0` |
| `Room`(models.py:27) | `width, depth, walls` | 房間矩形邊界 + 牆體清單;`walls` 可為空清單 |
| `ClearanceZone`(models.py:35) | `side, depth` | 開合淨空需求;`side` 以「未旋轉時家具自己的方向」為準,合法值 `front`/`back`/`left`/`right` |
| `FurnitureCatalogItem`(models.py:47) | `type, name, width, depth, height=80.0, style, price, glb_path, clearance` | 型錄屬性,不含座標;`clearance=None` 表示無開合淨空需求 |
| `PlacedFurniture`(models.py:61) | `id, catalog, pos_x=0.0, pos_y=0.0, rotation=0.0` | 擺放結果;`id` 為唯一識別碼(如 `sofa_1`) |

### 公開介面總覽

| 函式 | 位置 | 角色 |
| :--- | :--- | :--- |
| `furniture_polygon(item)` | geometry.py:14 | 家具 → 旋轉後 Shapely 多邊形(以中心點旋轉) |
| `wall_polygon(wall)` | geometry.py:26 | 牆線段 → 有厚度的旋轉矩形;長度 < 1e-4 回傳空多邊形 |
| `room_polygon(room)` | geometry.py:39 | 房間邊界 `box(0, 0, width, depth)` |
| `hits_wall(item, room)` | geometry.py:44 | 本體是否與任一牆相交 |
| `hits_furniture(item, others)` | geometry.py:52 | 本體是否與其他家具相交;回傳撞到的那件或 `None`;同 `id` 跳過 |
| `out_of_bounds(item, room)` | geometry.py:62 | 本體是否超出房間邊界(`poly.within`) |
| `check_placement(item, room, others)` | geometry.py:67 | 本體檢查統一入口 |
| `clearance_polygon(item)` | clearance.py:29 | 家具的淨空範圍多邊形;無需求回傳 `None` |
| `clearance_conflict(item, room, others)` | clearance.py:56 | 淨空衝突檢查 |
| `check_placement_with_clearance(item, room, others)` | clearance.py:89 | 本體 + 淨空 + 反向檢查的總入口 |

### 消費端(逐一查證)

| 消費者 | 位置 | 用法 |
| :--- | :--- | :--- |
| `backend/engine/placement.py` | placement.py:7 | `import check_placement_with_clearance as check_placement`——自動擺位一律走淨空版檢查 |
| `backend/engine/adjustment.py` | adjustment.py:9 | 同上,移動(軸分離)與旋轉的合法性判斷 |
| `backend/server/scene_service.py` | scene_service.py:17(import);1307、1309、1453(`generate_layout` 候選驗證)與 913(輔助函式 `_grid_place_in_boundary`,僅由 `generate_layout` 呼叫);1202、1212(`validate_single_placement`) | 2D 佈局與 F6 拖曳驗證 |
| `POST /api/scene/validate` | backend/server/main.py:2607 → scene_service.py:1185 `validate_single_placement` | 前端拖曳落點的 HTTP 入口,回 `{ok, reason}` |

### 淨空資料來源(業務規則)

`backend/catalog/style_db.py:185` 的 `CLEARANCE_BY_TYPE` 只對 4 種類型設定前方淨空:`bookcase` 40cm、`sideboard` 40cm、`wardrobe` 50cm、`desk` 50cm。沙發/床/電視櫃刻意不設(style_db.py 註解:設了會把茶几貼沙發、床頭櫃貼床誤判違規)。尺寸的合理性修補由上游 `style_db.sanitize_size_cm`(style_db.py:119,`_SIZE_RULES` 規則表)負責,引擎層不驗證尺寸。

---

### 規格: check_placement

**位置**: `backend/engine/geometry.py:67`
**簽名**: `check_placement(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`

**描述**: 本體碰撞統一檢查入口。依序檢查出界 → 穿牆 → 與其他家具重疊,回傳 `None` 表示合法,否則回傳繁體中文失敗原因字串。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `item.catalog.width` / `depth` 為正數公分——函式本身不驗證,由上游 `style_db.sanitize_size_cm` 修補(本日實測:寬深皆 0 時三項檢查全通過、回傳 `None`,屬未定義行為,見 TC-007) 2. `room` 為角落原點座標系,`walls` 可為空 3. `others` 中每件的 `id` 應唯一;與 `item.id` 相同者會被跳過不檢查 |
| **後置條件** | 1. 回傳 `None` ⇔ `out_of_bounds`、`hits_wall`、`hits_furniture` 三項全部通過 2. 失敗時回傳固定詞彙字串,且只回報「第一個」失敗原因(短路):`"物件超出空間範圍"` → `"與牆體穿透"` → `"與「{家具名}」重疊"` 3. 不修改 `item` / `room` / `others` 任何欄位(純查詢) |
| **不變性** | 1. 碰撞以旋轉後的實際多邊形判斷(Shapely `intersects` / `within`),非包圍盒近似,支援任意角度 2. 檢查順序固定:出界 → 穿牆 → 重疊,測試已釘死此順序(見 TC-301 對本體優先的延伸) 3. 失敗字串是對外契約——`examples/demo_agent_flow.py:11-12` 列為詞彙表、多個測試斷言完整字串,改字即破壞性變更 4. 家具邊緣與房間邊界恰好重合不判出界(Shapely `within` 容許邊界接觸;本日以無牆房間引擎實測驗證,尚無正式測試,見 TC-006)——但若邊界線上有牆體(如測試共用 fixture 的四面牆壓在邊界線上),同一位置仍會因穿牆失敗 |

---

### 規格: clearance_polygon

**位置**: `backend/engine/clearance.py:29`
**簽名**: `clearance_polygon(item: PlacedFurniture) -> Polygon | None`

**描述**: 算出家具的開合淨空範圍(衣櫃門、抽屜等打開所需的額外矩形),不含本體。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. `item.catalog.clearance` 為 `None` 或合法 `ClearanceZone` 2. `clearance.side` 必須在 `front`/`back`/`left`/`right` 四值內——超出即 `_SIDE_OFFSETS`(clearance.py:20)查表 `KeyError`,無防禦處理(見 TC-104) |
| **後置條件** | 1. 回傳 `None` ⇔ 家具無淨空需求 2. 否則回傳一個「與本體只共邊、不重疊」的矩形:`front`/`back` 時與家具同寬、沿 ±Y 延伸 `clearance.depth`;`left`/`right` 時與家具同深、沿 ±X 延伸 3. `item.rotation` 非 0 時,淨空矩形以家具中心為原點跟著旋轉 |
| **不變性** | 1. 不修改輸入 2. 淨空矩形面積 = (家具該面邊長) × `clearance.depth`(`depth` ≤ 0 的行為未定義,無測試,見 TC-106) |

---

### 規格: clearance_conflict

**位置**: `backend/engine/clearance.py:56`
**簽名**: `clearance_conflict(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`

**描述**: 檢查「這件家具的淨空範圍」是否被牆、其他家具本體、或其他家具的淨空侵犯。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 同 `check_placement`;另 `item` 若無淨空需求則直接通過 |
| **後置條件** | 1. 回傳 `None` ⇔ 無淨空需求,或三段檢查全過 2. 檢查順序固定:淨空撞牆 → 淨空撞其他家具本體 → 淨空撞其他家具的淨空;失敗字串依序為 `"「{我}」的開合空間被牆體阻擋"`、`"「{我}」的開合空間與「{他}」衝突"`、`"「{我}」與「{他}」的開合空間互相衝突"` 3. 同 `id` 的 other 跳過;不修改輸入 |
| **不變性** | 1. 只檢查「item 的淨空」被誰侵犯;「item 的本體」壓到別人淨空屬反向檢查,在 `check_placement_with_clearance` 補上 2. 淨空互撞為刻意從嚴設計(clearance.py 檔頭註解:「兩個門互相打架——較嚴格,可討論放寬」) |

---

### 規格: check_placement_with_clearance

**位置**: `backend/engine/clearance.py:89`
**簽名**: `check_placement_with_clearance(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None`

**描述**: 本體碰撞 + 淨空檢查的總入口。正式流程(自動擺位 `placement.py`、微調 `adjustment.py`、2D 佈局與拖曳驗證 `scene_service.py`)一律經此函式判定合法性。

**契約式設計 (DbC)**:

| 類型 | 條件 |
| :--- | :--- |
| **前置條件** | 1. 同 `check_placement` 2. `others` 應為與 `item` 同一房間座標系下的既有家具(呼叫端 `scene_service.py:1207-1211` 已先排除 `placement_failed` 與忽略碰撞類型的物件) |
| **後置條件** | 1. 回傳 `None` ⇔ 依序通過:`check_placement`(出界→穿牆→重疊)→ `clearance_conflict`(淨空撞牆→撞他人本體→淨空互撞)→ 反向檢查(item 本體壓到他人淨空,字串 `"擋住了「{他}」的開合空間"`) 2. 全序固定且短路,只回報第一個失敗原因 3. 不修改輸入 |
| **不變性** | 1. **增量合法性**:若既有佈局兩兩合法,且新加入件經本函式對全部既有件檢查通過,則整體佈局仍兩兩合法——因為新件與每一既有件之間「本體×本體、本體×淨空(雙向)、淨空×淨空」四種關係全數被查。`place_furniture_batch`(placement.py:115)的逐件放置正依賴此性質 2. 本體問題優先於淨空問題回報(測試 TC-301 釘死) |

---

## 測試案例

**現況**:本模組的直接單元測試在 `tests/test_clearance.py`(10 個)與 `tests/test_placement.py`(18 個,其中 5 個直接測 `check_placement`,其餘 13 個測消費端 `placement.py` / `adjustment.py` / `schema.py`)。本日實測:`.venv/bin/python -m pytest tests/test_placement.py tests/test_clearance.py -q` → **28 passed, 0.14s**。

共用測資:兩檔皆用 500cm × 400cm 四面圍牆的矩形房間 fixture;淨空案例用「150×60cm 衣櫃、front 60cm 淨空」與「200×90cm 沙發(無淨空)」。

### check_placement(geometry.py)

#### TC-001: 正常路徑——房間正中央合法

- **Arrange**: 500×400 房間;200×90 沙發置於 (250, 200)
- **Act**: `check_placement(item, room, [])`
- **Assert**: 回傳 `None`
- **狀態**: 已有 —— `tests/test_placement.py::test_center_placement_is_valid`

#### TC-002: 無效位置——出界

- **Arrange**: 沙發置於 (1000, 1000)(房間外)
- **Act**: `check_placement`
- **Assert**: 回傳 `"物件超出空間範圍"`
- **狀態**: 已有 —— `tests/test_placement.py::test_out_of_bounds_detected`

#### TC-003: 無效位置——穿牆

- **Arrange**: 沙發置於 (250, 47),本體壓進下牆(牆厚 10cm)
- **Act**: `check_placement`
- **Assert**: 回傳 `"與牆體穿透"`
- **狀態**: 已有 —— `tests/test_placement.py::test_wall_collision_detected`

#### TC-004: 無效位置——與家具重疊(含名稱回報)

- **Arrange**: 沙發與茶几同置於 (250, 200)
- **Act**: `check_placement(table, room, [sofa])`
- **Assert**: 回傳 `"與「沙發」重疊"`
- **狀態**: 已有 —— `tests/test_placement.py::test_furniture_overlap_detected`

#### TC-005: 正常路徑——距離足夠不誤判

- **Arrange**: 沙發 (250, 200)、茶几 (250, 350)
- **Act**: `check_placement(table, room, [sofa])`
- **Assert**: 回傳 `None`
- **狀態**: 已有 —— `tests/test_placement.py::test_furniture_no_false_positive_when_apart`

#### TC-006: 邊界情況——家具邊緣與房間邊界恰好重合 **(待補)**

- **Arrange**: 500×400 **無牆**房間(`walls=[]`);200×90 沙發置於 (100, 45),左、下兩邊貼齊房間邊界(min_x=0, min_y=0)
- **Act**: `check_placement`
- **Assert**: 應釘死為不出界(`None`);本日以無牆房間引擎實測確認現行為合法(Shapely `within` 容許邊界接觸),但無正式測試防守此行為。注意:若沿用共用 fixture 的四面圍牆房間,同一座標實測回傳 `"與牆體穿透"`(牆中心線壓在邊界線上),測試必須用無牆房間隔離出界判定

#### TC-007: 無效輸入——零尺寸家具 **(待補)**

- **Arrange**: `width=0, depth=0` 的家具置於房間中央
- **Act**: `check_placement`
- **Assert**: 目前實測回傳 `None`(退化多邊形通過所有檢查),屬未定義行為;測試應與團隊裁決一致——釘死現況或改為前置條件防禦(拋例外/回失敗原因)

#### TC-008: 邊界情況——退化牆(長度 < 1e-4)不影響判定 **(待補)**

- **Arrange**: 房間含一段起訖同點的牆 `Wall(10, 10, 10, 10)`;家具合法置於房內
- **Act**: `check_placement`
- **Assert**: `wall_polygon` 回傳空多邊形(本日實測確認),不應誤報穿牆;無正式測試

#### TC-009: 邊界情況——非 90 倍數旋轉的碰撞判定 **(待補)**

- **Arrange**: 家具 `rotation=45`,斜置於牆邊/另一家具旁
- **Act**: `check_placement`
- **Assert**: 以旋轉後多邊形判定(規格宣稱支援任意角度),現有測試僅覆蓋 0/90/180 度

### clearance_polygon(clearance.py)

#### TC-101: 正常路徑——無淨空需求回 None

- **狀態**: 已有 —— `tests/test_clearance.py::test_no_clearance_returns_none`

#### TC-102: 正常路徑——front 淨空往 +Y 延伸、不含本體

- **Arrange**: 衣櫃 (250, 50),本體 front 邊 y=80
- **Act**: `clearance_polygon`
- **Assert**: 淨空 bounds 為 y∈[80, 140]、x∈[175, 325](與家具同寬)
- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_polygon_extends_front`

#### TC-103: 邊界情況——旋轉 180 度後淨空改朝 -Y

- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_rotates_with_furniture`

#### TC-104: 無效輸入——side 不在四值內 **(待補)**

- **Arrange**: `ClearanceZone(side="top", depth=50)`
- **Act**: `clearance_polygon`
- **Assert**: 現行實作會拋 `KeyError`(clearance.py:36 查 `_SIDE_OFFSETS`,無防禦);測試應釘死此行為或改加防禦後測防禦

#### TC-105: 邊界情況——side 為 back/left/right 的延伸方向 **(待補)**

- **Arrange**: 分別以 `back`/`left`/`right` 建 ClearanceZone
- **Act**: `clearance_polygon`
- **Assert**: 依 `_SIDE_OFFSETS` 各朝 -Y/-X/+X 延伸、與該面同長;現有測試只覆蓋 `front`(含旋轉),另外三面零覆蓋——而 `CLEARANCE_BY_TYPE` 現行 4 類雖全為 `front`,引擎介面仍宣告支援四面

#### TC-106: 無效輸入——clearance.depth ≤ 0 **(待補)**

- **Arrange**: `ClearanceZone(side="front", depth=0)` 與負值
- **Act**: `clearance_polygon` / `clearance_conflict`
- **Assert**: 行為未定義(退化矩形),無測試

### clearance_conflict(clearance.py)

#### TC-201: 正常路徑——門朝房內無阻礙

- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_clear_when_open_space`

#### TC-202: 業務規則——淨空撞牆(門打不開)

- **Arrange**: 衣櫃旋轉 180 度背對房間,淨空朝牆
- **Assert**: 回傳 `"「衣櫃」的開合空間被牆體阻擋"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_blocked_by_wall`

#### TC-203: 業務規則——淨空撞其他家具本體

- **Arrange**: 沙發後緣 y=85 壓進衣櫃淨空區 [80, 140]
- **Assert**: 回傳 `"「衣櫃」的開合空間與「沙發」衝突"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_clearance_blocked_by_furniture_body`

#### TC-204: 業務規則——兩件家具淨空互撞

- **Arrange**: 兩衣櫃面對面,淨空區重疊
- **Assert**: 回傳 `"「衣櫃」與「衣櫃」的開合空間互相衝突"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_two_clearances_conflict`

#### TC-205: 業務規則——三段檢查次序釘死 **(待補)**

- **Arrange**: 建構同時「淨空撞牆」且「淨空撞他人本體」的佈局
- **Act**: `clearance_conflict`
- **Assert**: 應回報撞牆訊息(次序:牆 → 他人本體 → 互撞);現況次序只由實作保證,無測試

#### TC-206: 邊界情況——others 內含同 id 物件被跳過 **(待補)**

- **Arrange**: `others` 清單含 `item` 自己(拖曳驗證時前端可能把自身一併送入)
- **Act**: `clearance_conflict` / `check_placement_with_clearance`
- **Assert**: 同 `id` 不得自撞(geometry.py:55、clearance.py:76-77 皆有跳過邏輯);無直接測試

### check_placement_with_clearance(clearance.py)

#### TC-301: 業務規則——本體檢查優先於淨空回報

- **Arrange**: 衣櫃置於 (1000, 1000)(同時出界又必有淨空問題)
- **Assert**: 回傳 `"物件超出空間範圍"` 而非淨空訊息
- **狀態**: 已有 —— `tests/test_clearance.py::test_body_check_runs_first`

#### TC-302: 業務規則——反向檢查(本體壓到別人的淨空)

- **Arrange**: 床前緣 y=110 壓進已放置衣櫃的淨空區 [80, 140]
- **Act**: `check_placement_with_clearance(bed, room, [wardrobe])`
- **Assert**: 回傳 `"擋住了「衣櫃」的開合空間"`
- **狀態**: 已有 —— `tests/test_clearance.py::test_reverse_check_body_blocks_others_clearance`

#### TC-303: 正常路徑——完整合法佈局全數通過

- **Arrange**: 衣櫃靠牆門朝內 + 床離淨空上緣有餘裕
- **Assert**: 回傳 `None`
- **狀態**: 已有 —— `tests/test_clearance.py::test_valid_layout_passes_all_checks`

---

### 消費端測試對照(placement.py / adjustment.py,簡列)

以下 13 個測試不直接測檢查函式,但全數以檢查函式為合法性判準(`tests/test_placement.py`,均通過):

| 對象 | 測試 |
| :--- | :--- |
| `placed_to_dict` 公分契約(schema.py) | `test_placed_furniture_payload_declares_centimeter_contract` |
| `place_furniture` 找到合法位置/塞不下回報失敗 | `test_place_furniture_finds_valid_position`、`test_place_furniture_fails_when_room_too_small`(失敗字串 `"找不到合法擺放位置"`) |
| `place_furniture_batch` 後放避開先放 | `test_place_furniture_batch_avoids_overlap` |
| `place_overlay_on_furniture` 地毯沿用目標座標 | `test_overlay_keeps_target_coordinates_in_centimeters` |
| `place_adjacent_to_furniture` 12cm 間隙 | `test_adjacent_accessory_uses_twelve_centimeter_gap` |
| `move_furniture` 軸分離(合法移動/單軸被擋/雙軸被擋/撞家具) | `test_move_valid_direction_succeeds`、`test_move_axis_separation_blocks_only_bad_axis`、`test_move_both_axes_blocked_reports_failure`、`test_move_blocked_by_other_furniture` |
| `rotate_furniture` 合法旋轉/穿牆還原 | `test_rotate_valid_angle_succeeds`、`test_rotate_into_wall_reverts` |
| `adjust_furniture` 未知動作 | `test_unknown_action_returns_failure`(字串含 `"未知的動作"`) |

---

### 測試現況與待補彙整

| 項目 | 數字 |
| :--- | :--- |
| 現有測試 | 28 個(`test_clearance.py` 10 + `test_placement.py` 18),本日實測全數通過(0.14s) |
| 其中直接測本篇四個規格函式 | 15 個(TC-001~005、TC-101~103、TC-201~204、TC-301~303) |
| 待補測試 | 9 個:TC-006(邊界重合)、TC-007(零尺寸)、TC-008(退化牆)、TC-009(斜角旋轉)、TC-104(無效 side)、TC-105(back/left/right 淨空)、TC-106(depth ≤ 0)、TC-205(淨空檢查次序)、TC-206(同 id 跳過)——其中 TC-007、TC-104、TC-106 需先裁決契約(防禦 vs 釘死現況)再寫測試 |

另註:`check_placement_with_clearance` 在 `backend/server/scene_service.py` 的整合行為(拖曳驗證、2D 佈局)由 `tests/test_project_workflow_api.py` 與 `tests/test_scene_layout_regions.py` 等場景測試覆蓋(見 `docs/vibecoding/01_requirements/bdd_guide.md` 測試對照表),不在本篇單元規格範圍內重列;該批測試已於 2026-07-26 全量 pytest(389 通過/2 失敗/1 跳過,失敗均為快取鍵紅燈)中通過。
