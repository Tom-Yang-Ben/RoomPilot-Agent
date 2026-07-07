# furniture_engine — 家具邏輯引擎

負責 RoomPilot F3/F6:`place_furniture`(基礎配置)、`adjust_furniture`(軟裝微調)、碰撞/淨空運算。

- Owner: 蔡承安(副手: 林柏彥)
- 狀態: v0.1, 已合入 `bella` 作為後續 `/scene` 整合基礎

## 模組結構

| 檔案 | 職責 |
|---|---|
| `models.py` | `Room` / `Wall` / `ClearanceZone` / `FurnitureCatalogItem` / `PlacedFurniture` |
| `geometry.py` | 本體碰撞判斷(Shapely): 出界 / 穿牆 / 家具重疊 |
| `clearance.py` | 淨空運算: 開合空間(衣櫃門、抽屜等)的衝突檢查 |
| `placement.py` | `place_furniture`: 自動找合法位置(單件 + 批次) |
| `adjustment.py` | `adjust_furniture`: `move` / `rotate`, 吃結構化指令 |
| `schema.py` | 對外介面 v0.1: JSON 序列化 + LLM function-calling tool 定義 |

## 目前用途

這次 merge 先帶入:

- 家具自動放置
- 家具移動 / 旋轉
- 牆體碰撞
- 家具重疊檢查
- 開合淨空檢查

目前尚未直接接進 `web_fastapi` 的 `/scene` 生成流程,下一步可把既有的簡化擺放邏輯逐步改接到這套引擎。

