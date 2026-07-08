# Layout Evaluation Schema

本文件定義擺放完成後的評估資料格式。它對齊 `AI_AGENT_JSON_SCHEMA_V1.md` 的 `layout_result` 方向，但目前先服務現有 `/api/scene/generate`、`/api/scene/layout`、`/api/scene/validate` 流程。

## 使用原則

1. 評估層只描述結果，不直接搬動家具。
2. `status` 要能讓 UI 快速判斷成功、部分成功或失敗。
3. `violations` 是明確違規，`warnings` 是可接受但要提醒的風險。
4. `score` 暫時可保留 `null`，等正式評分規則完成再計算。
5. 未來轉換層會把 engine 回傳、使用者規則與 agent reasoning 整合成這份格式。

## 欄位模板

```json
{
  "schema_version": "1.0",
  "status": "",
  "placed_furniture": [],
  "unplaced_items": [],
  "violations": [],
  "warnings": [],
  "score": null,
  "reasoning": "",
  "validation_summary": {
    "placed_count": 0,
    "unplaced_count": 0,
    "violation_count": 0,
    "warning_count": 0
  }
}
```

## 欄位說明與範例

`status`

用途：整體結果狀態。

建議值：

```json
"status": "success"
```

可用值：`success`、`partial_success`、`failed`、`needs_review`

`placed_furniture`

用途：已成功擺放的家具。未來應包含家具 ID、位置、旋轉、尺寸與對應候選來源。

範例：

```json
"placed_furniture": [
  {
    "catalog_id": "sofa_001",
    "position": {"x": 210, "y": 260},
    "rotation": 180,
    "reason": "靠近主牆且保留中央走道"
  }
]
```

`unplaced_items`

用途：無法擺放或缺模型、缺尺寸、違反淨空的家具。

範例：

```json
"unplaced_items": [
  {
    "catalog_id": "bookcase_009",
    "reason": "房間寬度不足，放置後會超出可用範圍"
  }
]
```

`violations`

用途：明確違反規則的項目，例如擋門、擋窗、碰撞、超出房間。

範例：

```json
"violations": [
  {
    "type": "door_clearance_blocked",
    "item_id": "cabinet_001",
    "message": "櫃體占用門口開啟範圍"
  }
]
```

`warnings`

用途：可接受但需要提醒的情況，例如風格匹配低、尺寸偏大、材質資料不足。

範例：

```json
"warnings": [
  {
    "type": "style_match_low",
    "item_id": "chair_003",
    "message": "此家具不是主要風格，只是候選風格相近"
  }
]
```

`score`

用途：未來總評分，可由合法性、風格匹配、動線、使用者需求滿足度組成。目前沒有正式權重時可留 `null`。

範例：

```json
"score": 86
```

`reasoning`

用途：用自然語言簡述配置為什麼成立，提供給 UI 或 agent 回答使用者。

範例：

```json
"reasoning": "沙發與茶几形成主要互動區，電視櫃靠主牆，門窗淨空未被占用。"
```

`validation_summary`

用途：給 UI 快速顯示統計。

範例：

```json
"validation_summary": {
  "placed_count": 4,
  "unplaced_count": 1,
  "violation_count": 0,
  "warning_count": 1
}
```

## 未來銜接

1. `/api/scene/layout` 回傳的 `scene_objects` 先轉成 `placed_furniture` 與 `unplaced_items`。
2. `/api/scene/validate` 回傳的碰撞、超界、淨空問題轉成 `violations`。
3. 風格資料、家具候選 `match_reason`、材質 pool 命中情況轉成 `warnings` 與 `reasoning`。
4. 正式評分規則確定後，再把 `score` 從 `null` 改成可計算分數。
