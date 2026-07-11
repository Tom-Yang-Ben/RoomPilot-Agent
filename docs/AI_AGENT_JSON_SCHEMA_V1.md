# AI Agent JSON Schema v1

最後更新：2026-07-07

## 目的

這份文件定義一套給 AI agent 使用的標準化 JSON 規格，讓不同人都能用一致格式提供：

`平面圖結構 + 使用者需求 + 候選家具 + 規則 -> AI agent 自動擺位 -> 可驗證的配置結果`

這份規格的定位是「多人協作的資料交換格式」。
它不是目前 `/scene` 頁面直接暴露給終端使用者的前端格式，也不是 `furniture_engine` 目前 v0.1 的最小輸入格式。

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

建議 AI agent 的輸入輸出拆成 5 份 JSON：

1. `architecture.json`
2. `requirement.json`
3. `furniture_candidates.json`
4. `rules.json`
5. `layout_result.json`

---

## 1. architecture.json

### 用途

描述房間幾何、牆、窗、門與可用空間，讓 agent 能做避障、靠牆、保留門窗操作區。

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

描述使用者需求、風格方向、禁忌條件與優先順序，讓 agent 不只是「塞得下」，而是「符合需求」。

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

### `placement_hints` 欄位說明

`placement_hints` 是給 AI agent 的擺放提示。
它不是硬性規則，但會強烈影響 agent 如何決定位置、朝向、是否靠牆、是否成組。

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
  - 用途：告訴 agent 這件家具優先依附什麼來放
  - 常用值：`room_center`、`against_wall`、`around_focal_table`、`near_window`、`corner`、`entry_side`
- `prefer_near_wall`
  - 用途：是否偏好靠牆
  - 型別：`boolean`
- `preferred_wall_types`
  - 用途：指定偏好的牆種類
  - 常用值：`solid_wall`、`tv_wall`、`window_wall`
- `can_float`
  - 用途：能否離牆獨立擺放在空間中間
  - 型別：`boolean`
- `prefer_facing`
  - 用途：優先朝向哪些家具或空間焦點
  - 型別：ID 陣列
- `avoid_blocking`
  - 用途：避免阻擋哪些元素
  - 常用值：`window`、`door_swing`、`walkway`、`switch_panel`
- `preferred_zone`
  - 用途：指定這件家具優先屬於哪個空間區域
  - 常用值：`conversation_area`、`storage_edge`、`display_edge`、`reading_corner`
- `distance_preferences`
  - 用途：提供與牆或目標物件的偏好距離
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
  - 用途：每條關係規則的唯一識別碼
- `type`
  - 用途：關係類型
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
  - 用途：發起關係的家具，可以是一類家具或一組家具
- `target`
  - 用途：關係的目標家具或空間錨點
- `min_count`
  - 用途：至少要幾件 subject 參與
- `preferred_count`
  - 用途：理想參與數量
- `distance_range_cm`
  - 用途：主體與目標的距離範圍
- `priority`
  - 用途：衝突時這條關係的優先權
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

### 評價

你現在這份 `rules.json` 已經很接近正式版，可直接當 v1 基礎。

### 與現況差異

目前專案已有部分碰撞與淨空檢查，但還沒有完整做到：

- 外部規則檔驅動
- 所有 rule type 通用解譯
- 規則驗證報告標準化輸出

換句話說，這份 `rules.json` 很適合當目標格式，但還不是目前 `furniture_engine` 已完全原生吃進去的格式。

---

## 5. layout_result.json

### 用途

定義 AI agent 的標準輸出，讓前端、驗證器、後端後處理都能穩定接資料。

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

`layout_result` 是 AI agent 的正式輸出格式。
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

每筆 violation 建議包含：

- `rule_id`
- `severity`
- `message`
- `objects`
- `value`
- `expected`

這樣前端可以直接標示是哪條規則、哪件家具、實際值多少、預期多少。

### 什麼情況要輸出 `partial_success`

- 主要家具有放進去，但次要家具因規則衝突被捨棄
- 有 warning，但沒有 error
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

### 這組資料是否夠做多人協作、穩定交給 AI agent

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

## 每個檔案的說明

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

你目前提出的 JSON 範例方向是正確的，而且比專案現況更接近正式的 AI agent 規格。

如果只是做展示，現在已經夠。

如果目標是讓很多人都能把 JSON 丟給 AI agent，並穩定得到「有風格、可驗證、可落地」的家具配置，那 v1 至少要完整包含：

1. 家具擺放提示 `placement_hints`
2. 家具之間的關係 `layout_relations`
3. 標準化的結果輸出格式 `layout_result`

這三項補齊後，整套資料就會從「範例 JSON」升級成真正可協作的 agent schema。
