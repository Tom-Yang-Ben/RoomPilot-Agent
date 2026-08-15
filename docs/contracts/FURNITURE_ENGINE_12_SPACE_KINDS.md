# 家具引擎 12 種空間標準

## 目的

第 4 步確認的空間名稱是家具引擎判斷用途、推薦家具、尺寸限制與動線規則的唯一來源。
每個房間都必須同時提供：

- `space_kind`：12 種精確空間識別碼，保留使用者確認的房型。
- `room_type`：較粗的配置規則分類，用來共用家具與淨空規則。

家具引擎不得自行猜測或覆寫 `space_kind`。未知空間一律標記為 `multi_purpose`，
由第 6 步提示使用者處理。

## 標準對照表

| `space_kind` | 顯示名稱 | `room_type` | 配置重點 |
| --- | --- | --- | --- |
| `entryway` | 玄關 | `entry` | 鞋櫃、穿鞋椅、掛衣與進出淨空 |
| `living_room` | 客廳 | `living_room` | 沙發、茶几、影音與休息家具 |
| `dining_room` | 餐廳 | `dining_room` | 餐桌、餐椅、餐邊櫃與拉椅淨空 |
| `kitchen` | 廚房 | `kitchen` | 機能區；一般不配置活動家具 |
| `primary_bedroom` | 主臥 | `bedroom` | 床、衣櫃、床邊桌、梳妝或工作家具 |
| `secondary_bedroom` | 次臥 | `bedroom` | 單人或小雙人床、衣櫃、書桌與彈性家具 |
| `bathroom` | 浴室 | `bathroom` | 機能區；一般不配置活動家具 |
| `study` | 書房／工作區 | `workspace` | 書桌、工作椅、書櫃與閱讀家具 |
| `balcony` | 陽台 | `balcony` | 戶外小桌椅、植栽；保留排水與出入口 |
| `storage` | 儲藏室 | `storage` | 層架、收納櫃與取物通道 |
| `circulation` | 走道／動線 | `circulation` | 不配置家具；材質預設繼承客廳 |
| `multi_purpose` | 多功能室 | `default` | 依使用者選擇配置睡眠、工作、收納或休息家具 |

## JSON 範例

```json
{
  "room_id": "room-01",
  "space_kind": "primary_bedroom",
  "room_type": "bedroom",
  "usage": ["sleep", "read_work"]
}
```

## 引擎規則

1. 使用 `space_kind` 決定房型預設家具、使用者可選尺寸與第 6 步說明文字。
2. 使用 `room_type` 套用共用的碰撞、門窗淨空、走道與朝向規則。
3. 主臥與次臥皆可使用床與衣櫃規則，但候選家具尺寸與預設數量可以不同。
4. 走道不得放置家具，且預設沿用客廳的牆面、地板、天花和照明。
5. 廚房、浴室與陽台可使用機能材質；其餘室內空間預設繼承全屋風格。
