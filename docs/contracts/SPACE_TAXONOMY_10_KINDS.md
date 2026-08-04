# RoomPilot 十種空間分類契約

## 唯一正規分類

RoomPilot 從平面辨識、逐房問卷、RAG 搜尋、家具配置到第 6 步場景，均只使用下列十種空間代碼：

| 前端辨識分類 | API `room_type` | 問卷顯示名稱 |
| --- | --- | --- |
| `Hallway` | `hallway` | 走道／動線 |
| `Bath` | `bathroom` | 浴室 |
| `Bedroom` | `bedroom` | 臥室 |
| `Kitchen` | `kitchen` | 廚房 |
| `LivingRoom` | `living_room` | 客廳 |
| `Balcony` | `balcony` | 陽台 |
| `Entry` | `entryway` | 玄關 |
| `Storage` | `storage` | 書房／儲藏室 |
| `Stair` | `stair` | 樓梯 |
| `Garage` | `garage` | 車庫 |

## 臥室規則

- 系統只有 `bedroom` 一種臥室分類，不建立主臥、次臥、兒童房等額外空間類型。
- 當有多個臥室時，介面以「臥室（一）」、「臥室（二）」區分實例；每個實例可各自選用途、家具、牆地與照明。
- 睡眠、工作、更衣收納、兒童使用等差異是逐房用途與尺寸偏好，不是 `room_type`。

## 正規化規則

- 餐廳與廚房都正規化為 `kitchen`。
- 書房、工作區與儲藏室都正規化為 `storage`。
- 所有走道／動線都正規化為 `hallway`。
- 不支援多功能室；辨識與選單不得產生該分類。

## 資料交接

第 4 步輸出的 `room_type` 是第 5、6、7、8 步的唯一空間分類來源。RAG 可以為 `stair`、`hallway` 等空間回傳不配置家具的結果，但不得把它們改成其他房型。
