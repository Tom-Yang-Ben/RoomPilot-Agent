# Furniture Engineer Rules

本文件定義 `furniture_candidates` 中與「家具工程判斷」有關的欄位怎麼寫。它是 AI agent 中間資料層，不取代目前 `roompilot.engine.schema` 的 tool schema；tool schema 仍是執行介面，這份資料要在轉換層整理後再送進擺放引擎。

## 使用原則

1. 只根據目前資料集、風格標註、尺寸、類型與使用者需求填寫；沒有來源就保持空值或空陣列，不要腦補。
2. `requirement` 代表使用者輸入需求，`furniture_candidates` 代表被挑出的候選家具。
3. `role`、`match_reason` 可以由家具類型、風格、材質、顏色、尺寸推導。
4. `placement_hints`、`clearance_zones`、`layout_relations` 只有在資料或規則能支撐時才填。
5. 未來要由轉換層把本文件欄位轉成 `roompilot.engine` 需要的 `CatalogItem`、尺寸、靠牆需求、淨空與關係約束。

## 欄位模板

```json
{
  "catalog_id": "",
  "name": "",
  "category": "",
  "style": "",
  "color": "",
  "material": "",
  "dimensions": {
    "width": null,
    "depth": null,
    "height": null
  },
  "glb_path": "",
  "role": "",
  "quantity": {
    "min": null,
    "max": null,
    "recommended": null
  },
  "placement_hints": {},
  "clearance_zones": [],
  "layout_relations": [],
  "match_reason": "",
  "rule": {}
}
```

## 欄位說明與範例

`role`

用途：說明家具在空間中的功能角色。可由 `normalized_type` 推導，例如 sofa 是主要座位、coffee-table 是中心互動桌、tv-bench 是影音牆收納。

範例：

```json
"role": "主要座位"
```

`quantity`

用途：描述此類家具需要幾件。若使用者沒有指定數量，目前先保留 `null`，不要自行假設。

範例：

```json
"quantity": {"min": 1, "max": 1, "recommended": 1}
```

空白模板：

```json
"quantity": {"min": null, "max": null, "recommended": null}
```

`placement_hints`

用途：提供擺放偏好，不直接保證合法。未來轉換層會把它變成 engine 的候選排序或約束。

範例：

```json
"placement_hints": {
  "anchor_preference": "against_wall",
  "prefer_near_wall": true,
  "can_float": false,
  "avoid_blocking": ["door", "window"]
}
```

空白模板：

```json
"placement_hints": {}
```

`clearance_zones`

用途：描述家具前方、側邊、抽屜或門片需要保留的使用空間。只有收納、門片、抽屜類較適合填；沙發、茶几不要亂加，避免誤殺合理配置。

範例：

```json
"clearance_zones": [
  {"anchor": "front", "depth": 45, "reason": "抽屜與門片開啟"}
]
```

空白模板：

```json
"clearance_zones": []
```

`layout_relations`

用途：描述家具之間的關係，例如沙發面向電視櫃、茶几靠近沙發、床頭櫃靠近床。若候選資料尚未成組，先留空。

範例：

```json
"layout_relations": [
  {
    "relation": "face",
    "target_category": "tv-bench",
    "priority": "medium"
  }
]
```

空白模板：

```json
"layout_relations": []
```

`match_reason`

用途：說明為什麼此家具符合 `requirement`。目前可根據 style、type、color、material、GLB 是否存在、尺寸是否可用產生。

範例：

```json
"match_reason": "符合 scandinavian 風格，類型為 sofa，已有 GLB 模型，尺寸資料可供 3D viewer 與擺放引擎使用。"
```

`rule`

用途：保留給未來家具工程規則，例如特定品牌系列、施工限制、門片方向。目前沒有來源就維持空物件。

空白模板：

```json
"rule": {}
```

## 未來銜接

1. `requirement` 由使用者表單、自然語言與風格選擇整理出來。
2. `furniture_candidates` 由 catalog/style DB 選出家具，補上本文件欄位。
3. 轉換層把候選家具轉成 engine 可執行格式。
4. `roompilot.engine` 回傳擺放結果。
5. `eval.MD` 定義的 evaluation schema 接收結果，產生可解釋的成功、失敗、警告與分數。
