# AI Agent JSON Schema v1

最後更新：2026-07-08

## 目的

這份文件定義一套給 AI Agent 使用的標準化 JSON 規格，讓不同人都能用一致格式提供：

`平面圖結構 + 使用者需求 + 候選家具 + 規則 -> AI Agent 自動擺位 -> 可驗證的配置結果`

這份規格的定位是「多人協作的資料交換格式」。
它不是目前 `/scene` 頁面直接暴露給終端使用者的前端格式，也不是 `furniture_engine` 目前 v0.1 的最小輸入格式。

## 為什麼需要這份 Schema

- 沒有統一格式時，每個人會用自己的 JSON 命名與結構，Agent 很難穩定接資料。
- 沒有幾何欄位時，AI 只能講概念，不能可靠避障。
- 沒有需求欄位時，AI 只能「放得下」，不能保證「符合風格與功能」。
- 沒有規則欄位時，AI 可能排出漂亮畫面，但不一定能走、不一定安全。
- 沒有結果欄位時，前端與驗證器很難知道哪些家具有放進去、哪些失敗、失敗原因是什麼。

## 與現況差異

目前專案內實際運作的流程偏向：

`問卷 -> 後端整理 plan_json -> 從資料庫挑家具 -> furniture_engine 擺位 -> scene_objects`

目前 `furniture_engine` 真正吃的幾何欄位仍偏精簡，核心以：

- 房間尺寸
- 牆線
- 家具尺寸
- 家具位置
- 家具旋轉
- 少量淨空

為主。

本文件提出的 v1 規格，比現況多出三類重要資訊：

1. 風格與功能需求的結構化欄位
2. 家具之間的語意關係與擺放提示
3. 可驗證、可追蹤的輸出結果格式

## 建議檔案拆分

建議 AI Agent 的輸入輸出拆成 5 份 JSON：

1. `architecture.json`
2. `requirement.json`
3. `furniture_candidates.json`
4. `rules.json`
5. `layout_result.json`

---

## 1. architecture.json

### 用途

描述房間幾何、牆、窗、門與可用空間，讓 Agent 能做避障、靠牆、保留門窗操作區。

### 為什麼必要

- 這份檔案是所有擺位計算的空間基底。
- 沒有它，家具只能做抽象排列，無法知道是否出界、是否卡門、是否堵窗。
- 後續規則驗證幾乎都依賴這份資料，例如 `within_room`、`door_swing`、`window_access`。

### 建議欄位

```json
{
  "schema_version": "1.0",
  "units": "cm",
  "coordinate_system": {
    "origin": "room_min_corner",
    "x_positive": "right",
    "y_positive": "up_on_plan",
    "z_positive": "up_in_3d"
  },
  "room": {
    "room_type": "客廳",
    "room_polygon": [[0, 0], [400, 0], [400, 300], [0, 300]],
    "usable_floor_polygon": [[15, 15], [385, 15], [385, 285], [15, 285]],
    "ceiling_height": 280
  },
  "walls": [
    {
      "id": "wall_bottom",
      "position": {"x": 200, "y": 0},
      "rotation": 0,
      "width": 400,
      "thickness": 15,
      "height": 280,
      "normal": {"x": 0, "y": 1}
    }
  ],
  "windows": [
    {
      "id": "win_1",
      "position": {"x": 200, "y": 300},
      "rotation": 0,
      "width": 120,
      "height": 120,
      "sill_height": 90,
      "host_wall": "wall_top",
      "access_clearance_cm": 40
    }
  ],
  "doors": [
    {
      "id": "door_1",
      "position": {"x": 60, "y": 0},
      "rotation": 0,
      "width": 90,
      "host_wall": "wall_bottom",
      "hinge": "left",
      "swing_in": true,
      "open_angle_deg": 90
    }
  ]
}
```

### 中文欄位註解

- `schema_version`
  - 這份資料規格的版本號，避免未來欄位變動後彼此誤用。
- `units`
  - 單位定義，這裡示範是 `cm`。如果沒有這欄，尺寸與座標容易解讀錯誤。
- `coordinate_system`
  - 座標系定義，說明原點與正方向，避免前後端或 Agent 對旋轉與位置理解不一致。
- `room.room_type`
  - 房間類型，例如客廳、臥室。會影響候選家具與配置策略。
- `room.room_polygon`
  - 房間外框多邊形，是最基本的可放置邊界。
- `room.usable_floor_polygon`
  - 可用地坪範圍，扣除牆厚、包柱、保留區後更準。
  - 註：暫不考慮，可先視為未來升級功能，v1 可先只用 `room_polygon`。
- `room.ceiling_height`
  - 天花高度，可影響高家具與窗簾、燈具等限制。
  - 註：暫不考慮，先保留欄位給未來升級功能；目前平面擺位通常不需要它。
- `walls`
  - 牆的集合。很多靠牆家具、電視牆、收納櫃都需要參考它。
- `wall.normal`
  - 牆的正面方向參考向量，用來幫助系統判斷家具應該面向室內哪一側。
  - 它不是「另一邊的牆不能貼」，而是告訴系統：如果家具要貼這面牆，家具的正面通常應該朝哪個方向。沒有這欄也能貼牆，但有這欄時，朝向推算會更穩定。
- `windows`
  - 窗的位置與尺寸，用來保留採光與操作空間。
- `access_clearance_cm`
  - 窗前建議保留淨空，方便開窗與清潔。
- `doors`
  - 門的位置與尺寸，用來保留進出動線與門扇開啟區。
- `hinge`
  - 鉸鏈方向，會影響門扇開啟的掃掠區。
- `swing_in`
  - 門是往內開還是往外開。
- `open_angle_deg`
  - 開門角度，讓 door swing 的驗證更具體。

### 最低必要欄位

- `units`
- `room.room_polygon`
- `walls`
- `windows`
- `doors`

### 建議補強欄位

- `coordinate_system`
- `usable_floor_polygon`
- `ceiling_height`
- `wall.normal`
- `doors.open_angle_deg`
- `windows.access_clearance_cm`

---

## 2. requirement.json

### 用途

描述使用者需求、風格方向、禁忌條件與優先順序，讓 Agent 不只是「塞得下」，而是「符合需求」。

### 為什麼必要

- 幾何資料只能回答「能不能放」，不能回答「該不該放」。
- 同一個客廳，可以是日式、北歐、奶油風，配置策略完全不同。
- 若沒有明確約束，Agent 很可能選出功能合理但風格不對、或風格對但違反需求的方案。

### 建議欄位

```json
{
  "schema_version": "1.0",
  "room_type": "客廳",
  "style": "日式風格",
  "prefer_color": ["米白色", "淺木色"],
  "requirements": [
    "日式風格客廳",
    "主色調米白色",
    "不要沙發",
    "以坐墊替代沙發",
    "保留會客功能"
  ],
  "constraints": {
    "exclude_categories": ["沙發"],
    "include_categories": ["坐墊", "茶几", "電視櫃", "地毯", "落地燈"],
    "must_keep": ["以坐墊承接沙發的座位功能", "圍繞茶几成組"],
    "priority_order": [
      "安全與可通行",
      "功能完整",
      "風格一致",
      "視覺平衡"
    ],
    "preferred_layout_pattern": "central_conversation",
    "style_strictness": "high",
    "notes": [
      "避免大型西式沙發",
      "保持低矮、留白、自然材質感"
    ]
  }
}
```

### 中文欄位註解

- `room_type`
  - 房型類別，通常要與 `architecture.json` 對齊。
- `style`
  - 主要風格方向，是選家具與排構圖的重要依據。
- `prefer_color`
  - 偏好色系，方便後續選家具或做 style scoring。
- `requirements`
  - 使用者用自然語句表達的核心要求，可保留原始需求語意。
- `constraints.exclude_categories`
  - 明確禁止的家具類型，例如不要沙發。
- `constraints.include_categories`
  - 希望優先納入的家具類型。
- `constraints.must_keep`
  - 某些功能或關係必須成立，例如「保留會客功能」。
- `constraints.priority_order`
  - 當條件互相衝突時，Agent 要依什麼順序取捨。
- `constraints.preferred_layout_pattern`
  - 偏好的空間構圖方式，例如 central conversation。
- `constraints.style_strictness`
  - 風格嚴格度，決定 Agent 是偏保守還是可混搭。
- `constraints.notes`
  - 額外文字補充，適合放暫時難以結構化的偏好。

### 最低必要欄位

- `room_type`
- `style`
- `requirements`

### 建議補強欄位

- `prefer_color`
- `constraints.priority_order`
- `constraints.preferred_layout_pattern`
- `constraints.style_strictness`

---

## 3. furniture_candidates.json

### 用途

提供可被選用的家具候選池。
這份資料不只要能挑款式，還要能支援 AI 做合理擺位。

### 為什麼必要

- 沒有候選池，Agent 不知道有哪些家具可以選。
- 只有尺寸不夠，還需要知道家具的角色、數量範圍、與其他家具的關係。
- 這份檔案是「風格需求」與「空間幾何」之間的橋樑。

### 建議欄位

```json
{
  "schema_version": "1.0",
  "room_type": "客廳",
  "style": "日式風格",
  "candidates": [
    {
      "catalog_id": "cushion_001",
      "name": "亞麻和室坐墊",
      "category": "坐墊",
      "style": "日式",
      "color": "米白",
      "dimensions": {"width": 60, "depth": 60, "height": 12},
      "glb_path": "assets/cushion_001.glb",
      "role": "主要座位",
      "match_reason": "以坐墊承接沙發座位功能，亞麻米白貼合日式與主色調",
      "quantity": {"min": 2, "max": 4, "recommended": 3},
      "placement_hints": {
        "anchor_preference": "around_focal_table",
        "prefer_near_wall": false,
        "can_float": true,
        "prefer_facing": ["table_low_004", "cabinet_low_007"]
      }
    },
    {
      "catalog_id": "table_low_004",
      "name": "橡木和室矮桌",
      "category": "茶几",
      "style": "日式",
      "color": "淺木色",
      "dimensions": {"width": 100, "depth": 60, "height": 35},
      "glb_path": "assets/table_low_004.glb",
      "role": "中心矮桌",
      "match_reason": "低矮桌面符合和室席地而坐，淺木色協調米白",
      "quantity": {"min": 1, "max": 1, "recommended": 1},
      "placement_hints": {
        "anchor_preference": "room_center",
        "prefer_near_wall": false,
        "can_float": true
      }
    },
    {
      "catalog_id": "cabinet_low_007",
      "name": "橡木電視矮櫃",
      "category": "電視櫃",
      "style": "日式",
      "color": "淺木色",
      "dimensions": {"width": 120, "depth": 40, "height": 45},
      "glb_path": "assets/cabinet_low_007.glb",
      "role": "收納 / 電視擺放",
      "match_reason": "低矮線條呼應和室，淺木色一致",
      "quantity": {"min": 1, "max": 1, "recommended": 1},
      "placement_hints": {
        "anchor_preference": "against_wall",
        "preferred_wall_types": ["solid_wall"],
        "avoid_blocking": ["window", "door_swing"]
      },
      "clearance_zones": [
        {
          "anchor": "front",
          "depth": 30
        }
      ]
    }
  ],
  "layout_relations": [
    {
      "type": "surround",
      "subject": ["cushion_001"],
      "target": "table_low_004",
      "min_count": 2,
      "preferred_count": 3
    },
    {
      "type": "co_locate",
      "subject": ["table_low_004"],
      "target": "rug_natural_002"
    },
    {
      "type": "face_toward",
      "subject": ["cushion_001"],
      "target": "table_low_004"
    }
  ]
}
```

### 中文欄位註解

- `catalog_id`
  - 家具在型錄或資料庫中的唯一 ID。
- `name`
  - 給人看的家具名稱。
- `category`
  - 家具類別，例如茶几、坐墊、電視櫃。
- `style`
  - 家具本身的風格標籤。
- `color`
  - 家具主色，方便和需求中的偏好色系比對。
- `dimensions`
  - 家具實際尺寸，是幾何擺位的必要資料。
- `glb_path`
  - 3D 模型檔位置，讓前端能實際載入。
- `role`
  - 這件家具在空間中的角色，例如主座位、焦點桌、收納。
- `match_reason`
  - 為什麼這件家具符合本案需求，方便除錯與審核。
- `quantity`
  - 數量彈性範圍，避免 Agent 只會「每件都放一個」。
- `placement_hints`
  - 單件家具的擺放偏好，例如靠牆、置中、朝向目標。
- `clearance_zones`
  - 使用淨空，例如櫃體前方抽拉區。
- `layout_relations`
  - 家具與家具之間的組合關係，是形成完整空間構圖的關鍵。

### 最低必要欄位

每件候選家具至少要有：

- `catalog_id`
- `name`
- `category`
- `dimensions`
- `glb_path`

### 建議補強欄位

- `role`
- `match_reason`
- `quantity`
- `placement_hints`
- `clearance_zones`
- `layout_relations`

### `quantity` 為什麼必要

- 很多家具不是固定 1 件，例如餐椅、坐墊、邊几。
- 沒有 `quantity`，Agent 不知道 2 到 4 個坐墊與 1 個坐墊在語意上差很多。
- `recommended` 可以讓 Agent 在多解中優先選出最像設計意圖的方案。

### `placement_hints` 欄位說明

`placement_hints` 是給 AI Agent 的擺放提示。
它不是硬性規則，但會強烈影響 Agent 如何決定位置、朝向、是否靠牆、是否成組。

### `placement_hints` 為什麼必要

- 同一件家具通常不只一種合法擺法。
- 只靠幾何可行性，Agent 常會擺出「能放但不好看」的結果。
- 這些提示可把設計語意轉成半結構化資訊，幫 Agent 更接近設計師直覺。

### `placement_hints` 建議格式

```json
{
  "placement_hints": {
    "anchor_preference": "around_focal_table",
    "prefer_near_wall": false,
    "preferred_wall_types": ["solid_wall"],
    "can_float": true,
    "prefer_facing": ["table_low_004", "cabinet_low_007"],
    "avoid_blocking": ["window", "door_swing", "walkway"],
    "preferred_zone": "conversation_area",
    "distance_preferences": {
      "min_to_wall_cm": 10,
      "preferred_to_target_cm": 45,
      "max_to_target_cm": 120
    }
  }
}
```

### `placement_hints` 欄位定義

- `anchor_preference`
  - 用途：告訴 Agent 這件家具優先依附什麼來放。
  - 常用值：`room_center`、`against_wall`、`around_focal_table`、`near_window`、`corner`、`entry_side`
- `prefer_near_wall`
  - 用途：是否偏好靠牆。
  - 型別：`boolean`
- `preferred_wall_types`
  - 用途：指定偏好的牆種類。
  - 常用值：`solid_wall`、`tv_wall`、`window_wall`
- `can_float`
  - 用途：能否離牆獨立擺放在空間中間。
  - 型別：`boolean`
- `prefer_facing`
  - 用途：優先朝向哪些家具或空間焦點。
  - 型別：ID 陣列
- `avoid_blocking`
  - 用途：避免阻擋哪些元素。
  - 常用值：`window`、`door_swing`、`walkway`、`switch_panel`
- `preferred_zone`
  - 用途：指定這件家具優先屬於哪個空間區域。
  - 常用值：`conversation_area`、`storage_edge`、`display_edge`、`reading_corner`
- `distance_preferences`
  - 用途：提供與牆或目標物件的偏好距離。
  - 常用值：
    - `min_to_wall_cm`
    - `preferred_to_target_cm`
    - `max_to_target_cm`

### 這個案子的 `placement_hints` 怎麼填

- 坐墊：
  - `anchor_preference = around_focal_table`
  - `can_float = true`
  - `prefer_facing = ["table_low_004"]`
- 矮桌：
  - `anchor_preference = room_center`
  - `can_float = true`
- 電視櫃：
  - `anchor_preference = against_wall`
  - `prefer_near_wall = true`
  - `avoid_blocking = ["window", "door_swing"]`
- 落地燈：
  - `anchor_preference = corner`
  - `prefer_near_wall = true`

### 什麼情況一定要加 `placement_hints`

- 同一類家具可能有多種擺法
- 家具不是單純靠牆就好
- 家具需要朝向某個目標
- 空間強調風格構圖而不只是塞進去

### `layout_relations` 欄位說明

`layout_relations` 是描述家具與家具之間的關係。
如果 `placement_hints` 是單件家具的偏好，`layout_relations` 就是整體組合的規則。

### `layout_relations` 為什麼必要

- 設計不是把單件家具各自合法放下就結束。
- 很多空間重點在「成組關係」，例如沙發圍茶几、餐椅圍餐桌、地毯對齊會客區。
- 沒有這層資訊，AI 容易產生零散、缺乏中心的配置。

### `layout_relations` 建議格式

```json
{
  "layout_relations": [
    {
      "id": "rel_1",
      "type": "surround",
      "subject": ["cushion_001"],
      "target": "table_low_004",
      "min_count": 2,
      "preferred_count": 3,
      "distance_range_cm": [25, 70],
      "priority": "high"
    },
    {
      "id": "rel_2",
      "type": "co_locate",
      "subject": ["table_low_004"],
      "target": "rug_natural_002",
      "priority": "high"
    },
    {
      "id": "rel_3",
      "type": "face_toward",
      "subject": ["cushion_001"],
      "target": "table_low_004",
      "priority": "medium"
    }
  ]
}
```

### `layout_relations` 欄位定義

- `id`
  - 用途：每條關係規則的唯一識別碼。
- `type`
  - 用途：關係類型。
  - 常用值：
    - `surround`
    - `co_locate`
    - `face_toward`
    - `align_with`
    - `near`
    - `against_same_wall`
    - `center_on`
    - `keep_apart`
- `subject`
  - 用途：發起關係的家具，可以是一類家具或一組家具。
- `target`
  - 用途：關係的目標家具或空間錨點。
- `min_count`
  - 用途：至少要幾件 `subject` 參與。
- `preferred_count`
  - 用途：理想參與數量。
- `distance_range_cm`
  - 用途：主體與目標的距離範圍。
- `priority`
  - 用途：衝突時這條關係的優先權。
  - 常用值：`high`、`medium`、`low`

### 這個案子的 `layout_relations` 怎麼填

- 坐墊圍繞矮桌：`surround`
- 矮桌與地毯重疊成組：`co_locate` 或 `center_on`
- 坐墊朝向矮桌：`face_toward`
- 電視櫃與坐墊區保持視覺對向：`align_with` 或 `face_toward`

### 什麼情況一定要加 `layout_relations`

- 你希望 AI 不只擺單件，而是擺出一整組空間關係
- 同一套家具彼此有中心與陪襯
- 會客區、餐區、閱讀角等需要被明確定義

### 你目前版本已經有的優點

- 已有 `role`
- 已有 `match_reason`
- 已有 `dimensions`
- 已有 `glb_path`
- 已開始加入 `clearance_zones`

### 你目前版本還缺的關鍵點

- 沒有 `quantity`
- 沒有 `placement_hints`
- 沒有 `layout_relations`
- 沒有明確描述哪些候選家具應該成組出現

---

## 4. rules.json

### 用途

定義硬性規則、警告規則與驗證條件。
這份資料的目標不是讓 LLM 自由理解，而是讓規則引擎與 validator 可直接執行。

### 為什麼必要

- 這份檔案定義什麼叫「合格」。
- 沒有規則，Agent 只能靠偏好與機率決策，難以保證安全與可用性。
- 規則與幾何分離後，未來比較容易調整驗證標準，不必重寫整個擺位流程。

### 建議欄位

```json
{
  "schema_version": "1.0",
  "rules": [
    {
      "id": "no_overlap",
      "type": "no_overlap",
      "description": "任兩件家具不可重疊",
      "severity": "error",
      "params": {"tolerance_cm": 1},
      "applies_to": ["*"]
    },
    {
      "id": "within_room",
      "type": "within_room",
      "description": "家具必須完全落在房間可用範圍內",
      "severity": "error",
      "params": {},
      "applies_to": ["*"]
    },
    {
      "id": "walkway_60",
      "type": "min_walkway",
      "description": "家具之間及家具與牆之間的通行間隙至少 60cm",
      "severity": "error",
      "params": {"min_distance_cm": 60},
      "applies_to": ["*"]
    },
    {
      "id": "clearance_zones",
      "type": "clearance_zone",
      "description": "家具宣告的使用淨空區不可被其他家具侵占，也不可超出房間",
      "severity": "error",
      "params": {},
      "applies_to": ["*"]
    },
    {
      "id": "door_swing",
      "type": "door_swing",
      "description": "門的開合範圍內不可放家具",
      "severity": "error",
      "params": {},
      "applies_to": ["*"]
    },
    {
      "id": "window_access",
      "type": "window_access",
      "description": "窗前保留 40cm 操作淨空",
      "severity": "warning",
      "params": {"clearance_cm": 40},
      "applies_to": ["*"]
    }
  ]
}
```

### 中文欄位註解

- `id`
  - 規則唯一 ID，方便在結果中引用。
- `type`
  - 規則種類，供 validator 決定用哪種邏輯檢查。
- `description`
  - 給人讀的規則說明。
- `severity`
  - 違反後是 `error` 還是 `warning`。
- `params`
  - 規則參數，例如最小走道寬度、容許誤差。
- `applies_to`
  - 規則適用對象，可指定全部或某些類別。

### 重疊規則的例外要先講清楚

- 「不可重疊」不一定代表所有物件都完全不能上下或平面共存。
- 例如地毯通常可視為可承載或可共置物件，所以茶几、坐墊可以放在地毯上。
- 但沙發通常不是承載平台，因此不應允許其他家具「放在沙發上」或與沙發本體重疊。
- 這表示未來規則最好不是只有單一 `no_overlap`，而是再加一層「哪些類別可作為 base / support surface，哪些不行」的例外表。

### 建議補一個例外規則欄位

如果未來要做得更完整，可以在 `rules.json` 或家具資料內增加類似：

- `allow_overlap_with = ["rug"]`：例如茶几可和地毯重疊。
- `support_surface = true`：例如地毯可視為可承載層。
- `support_surface = false`：例如沙發不可作為別的家具承載面。
- `overlap_mode = "floor_only" | "support_allowed" | "forbidden"`：讓驗證器更容易判斷。

### 評價

你現在這份 `rules.json` 已經很接近正式版，可直接當 v1 基礎。

### 與現況差異

目前專案已有部分碰撞與淨空檢查，但還沒有完整做到：

- 外部規則檔驅動
- 所有 `rule type` 通用解譯
- 規則驗證報告標準化輸出

換句話說，這份 `rules.json` 很適合當目標格式，但還不是目前 `furniture_engine` 已完全原生吃進去的格式。

---

## 5. layout_result.json

### 用途

定義 AI Agent 的標準輸出，讓前端、驗證器、後端後處理都能穩定接資料。

### 為什麼必要

- 單純回傳家具座標不夠，因為協作者還需要知道成功與否、缺件原因、違規內容。
- 統一輸出格式後，前端顯示、除錯、評分與比方案才會容易。
- 這份檔案是把「AI 做了什麼」轉成「系統可接、可追蹤、可比較」的結果。

### 建議欄位

```json
{
  "schema_version": "1.0",
  "status": "success",
  "summary": "已生成日式客廳配置，保留會客功能並以坐墊取代沙發。",
  "placed_furniture": [
    {
      "id": "f_1",
      "catalog_id": "cushion_001",
      "name": "亞麻和室坐墊",
      "position": {"x": 200, "y": 95},
      "rotation": 0,
      "dimensions": {"width": 60, "depth": 60, "height": 12},
      "glb_path": "assets/cushion_001.glb"
    }
  ],
  "unplaced_items": [],
  "violations": [],
  "warnings": [],
  "score": {
    "total": 91,
    "style_consistency": 95,
    "functionality": 90,
    "rule_compliance": 100,
    "layout_balance": 80
  },
  "reasoning": [
    "以矮桌作為座位區中心。",
    "三個坐墊圍繞矮桌形成會客關係。",
    "電視櫃靠實牆放置，避開門扇開啟區。"
  ]
}
```

### 中文欄位註解

- `status`
  - 這次配置是否成功。
- `summary`
  - 一句話摘要，方便快速看懂結果。
- `placed_furniture`
  - 成功放入場景的家具清單。
- `unplaced_items`
  - 未能放入的家具與失敗原因。
- `violations`
  - 規則違反紀錄，適合機器與人一起看。
- `warnings`
  - 給前端或使用者看的簡短提醒。
- `score`
  - 多面向評分，方便候選方案比較。
- `reasoning`
  - Agent 為何這樣擺的說明，用於審查與除錯。
- `validation_summary`
  - 把規則檢查結果快速整理成通過、警告、失敗。

### 最低必要欄位

- `status`
- `placed_furniture`
- `violations`
- `warnings`

### 建議補強欄位

- `summary`
- `unplaced_items`
- `score`
- `reasoning`

### `layout_result` 欄位說明

`layout_result` 是 AI Agent 的正式輸出格式。
重點不是只回傳家具座標，而是要能回答：

1. 有沒有成功擺完
2. 哪些家具放進去了
3. 哪些家具沒放進去
4. 哪些規則通過或失敗
5. 為什麼這樣擺

### `layout_result` 建議完整格式

```json
{
  "schema_version": "1.0",
  "status": "success",
  "summary": "已生成日式客廳配置，保留會客功能並以坐墊取代沙發。",
  "placed_furniture": [
    {
      "id": "f_1",
      "catalog_id": "cushion_001",
      "name": "亞麻和室坐墊",
      "category": "坐墊",
      "position": {"x": 200, "y": 95},
      "rotation": 0,
      "dimensions": {"width": 60, "depth": 60, "height": 12},
      "glb_path": "assets/cushion_001.glb"
    }
  ],
  "unplaced_items": [
    {
      "catalog_id": "side_table_002",
      "reason": "與主要走道衝突，無法通過 min_walkway 規則"
    }
  ],
  "violations": [
    {
      "rule_id": "window_access",
      "severity": "warning",
      "message": "落地燈接近窗前操作區",
      "objects": ["floorlamp_003"],
      "value": 28,
      "expected": 40
    }
  ],
  "warnings": [
    "落地燈與窗前淨空接近臨界值"
  ],
  "score": {
    "total": 91,
    "style_consistency": 95,
    "functionality": 90,
    "rule_compliance": 100,
    "layout_balance": 80
  },
  "reasoning": [
    "以矮桌作為座位區中心。",
    "三個坐墊圍繞矮桌形成會客關係。",
    "電視櫃靠實牆放置，避開門扇開啟區。"
  ],
  "validation_summary": {
    "passed_rules": ["no_overlap", "within_room", "door_swing"],
    "warning_rules": ["window_access"],
    "failed_rules": []
  }
}
```

### `layout_result` 欄位定義

- `status`
  - 用途：配置是否成功
  - 常用值：`success`、`partial_success`、`failed`
- `summary`
  - 用途：一句話說明整體結果
- `placed_furniture`
  - 用途：成功放入場景的家具清單
- `unplaced_items`
  - 用途：沒放進去的家具與原因
- `violations`
  - 用途：正式的規則違反紀錄
- `warnings`
  - 用途：給人看的簡短提醒
- `score`
  - 用途：多面向評分，方便排序或比較候選方案
- `reasoning`
  - 用途：保留 AI 的擺位理由，方便除錯與審查
- `validation_summary`
  - 用途：快速整理哪些規則通過、警告、失敗

### `violations` 建議格式

每筆 `violation` 建議包含：

- `rule_id`
- `severity`
- `message`
- `objects`
- `value`
- `expected`

這樣前端可以直接標示是哪條規則、哪件家具、實際值多少、預期多少。

### 什麼情況要輸出 `partial_success`

- 主要家具有放進去，但次要家具因規則衝突被捨棄
- 有 `warning`，但沒有 `error`
- 空間功能成立，但不是滿配方案

### 這個案子的 `layout_result` 應該長什麼樣

- `status` 多半是 `success` 或 `partial_success`
- `placed_furniture` 至少包含坐墊、矮桌、地毯、電視櫃
- `unplaced_items` 可用來記錄因走道不足而被捨棄的次要家具
- `validation_summary` 應讓你們一眼看出是否通過 `door_swing`、`window_access`、`walkway_60`

---

## 日式客廳完整範例

### 這個範例要達成什麼

- 客廳
- 日式風格
- 主色米白與淺木色
- 不要沙發
- 以坐墊承接沙發的座位功能
- 以茶几和地毯形成會客核心

### 架構上如何拆

1. `architecture.json` 提供房間、牆、門、窗
2. `requirement.json` 提供風格與功能需求
3. `furniture_candidates.json` 提供候選家具與成組關係
4. `rules.json` 提供硬性規則
5. `layout_result.json` 輸出最終擺位與驗證結果

### 這組資料是否夠做 demo

夠。

### 這組資料是否夠做多人協作、穩定交給 AI Agent

補上 `placement_hints`、`layout_relations`、`layout_result` 後，就已經接近可用的 v1。

---

## 建議的最小落地版本

如果你們要先做 v1，而不是一次做太大，建議先把下列欄位定成必填：

### architecture

- `units`
- `room.room_polygon`
- `walls`
- `windows`
- `doors`

### requirement

- `room_type`
- `style`
- `requirements`
- `constraints.exclude_categories`
- `constraints.include_categories`

### furniture_candidates

- `catalog_id`
- `name`
- `category`
- `dimensions`
- `glb_path`
- `role`
- `quantity`

### rules

- `id`
- `type`
- `severity`
- `params`

### layout_result

- `status`
- `placed_furniture`
- `violations`
- `warnings`

---

## 每個檔案的必要性總結

### `architecture.json`

負責描述空間幾何。沒有這份資料，AI 只能做概念配置，不能可靠避障。

### `requirement.json`

負責描述人想要什麼。沒有這份資料，AI 只能做幾何上可行，不能保證風格與功能對。

### `furniture_candidates.json`

負責描述有哪些家具可選，以及每件家具在風格與功能上的角色。沒有這份資料，AI 不知道要選什麼，也不知道哪些家具該成組出現。

### `rules.json`

負責定義什麼叫合格。沒有這份資料，AI 即使排出漂亮畫面，也可能不符合走道、安全與使用性。

### `layout_result.json`

負責輸出最終答案。沒有這份資料，前端與驗證流程很難知道 AI 是否真的成功、哪些家具沒放進去、哪些規則被違反。

---

## 結論

你目前提出的 JSON 範例方向是正確的，而且比專案現況更接近正式的 AI Agent 規格。

如果只是做展示，現在已經夠。

如果目標是讓很多人都能把 JSON 丟給 AI Agent，並穩定得到「有風格、可驗證、可落地」的家具配置，那 v1 至少要完整包含：

1. 家具擺放提示 `placement_hints`
2. 家具之間的關係 `layout_relations`
3. 標準化的結果輸出格式 `layout_result`

這三項補齊後，整套資料就會從「範例 JSON」升級成真正可協作的 Agent schema。

