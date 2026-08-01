# RoomPilot Agent 前後端契約

最後更新：2026-08-02

## 目的

本文件定義 Yen Agent、AN 家具引擎與 Bella 前後端之間的現行契約。
它描述已接入正式流程的功能，不是未來功能清單。

## 權責邊界

| 模組 | 負責 | 不負責 |
|---|---|---|
| `backend/agent/` | 需求理解、家具選件規則、擺放失敗後的換小／移除／升級人工處理策略 | 計算家具座標、直接修改前端狀態 |
| `backend/engine/` | 家具座標、旋轉、碰撞、淨空、貼牆與房間邊界驗證 | 決定使用者需求或挑選風格 |
| `backend/server/` | API、fallback、專案資料、模組調度與回傳報告 | 複製 Agent 或 engine 演算法 |
| `backend/server/static/`、`frontend3d/` | 蒐集需求、呼叫 API、呈現選件、配置與修復結果 | 在瀏覽器自行推算合法家具座標 |

所有跨模組長度與平面座標使用公分。家具合法座標只能由
`backend.engine` 產生；Agent 每次更換家具後都必須重新呼叫 engine。

## 正式資料流

```text
Bella 問卷／對話 UI
  -> /api/agent/intake/start、/answer
  -> client_brief
  -> /api/agent/furniture/select
  -> 已驗證家具清單
  -> /api/scene/generate
  -> AN engine 擺放
  -> 若 placement_failed，Yen resolve_placements()
  -> AN engine 重新擺放
  -> scene_objects + placement_resolution_report
  -> Bella 2D／3D UI
```

## 需求訪談

### `POST /api/agent/intake/start`

Request：

```json
{"session_id": "roompilot-project-001"}
```

Response 主要欄位：

```json
{
  "session_id": "roompilot-project-001",
  "mode": "guided_fallback",
  "step": "space_type",
  "question": "你想規劃哪一個空間？可以直接用一段話描述整體需求。",
  "client_brief": {
    "schema_version": "1.1",
    "space": {"type": null, "width_cm": 420, "depth_cm": 360},
    "occupants": {"adults": 0, "children": 0, "elderly": 0, "pets": 0},
    "needs": [],
    "style": {"preferred": [], "colors": [], "materials": []},
    "constraints": [],
    "confirmation": {"status": "draft"}
  },
  "ready_for_confirmation": false
}
```

### `POST /api/agent/intake/answer`

Request 必須包含 `step`、非空白 `answer`，並原樣帶回上一輪
`client_brief`：

```json
{
  "session_id": "roompilot-project-001",
  "step": "space_type",
  "answer": "兩位成人使用的明亮日式客廳，需要收納且不能擋門窗。",
  "client_brief": {"schema_version": "1.1"}
}
```

Response 固定包含：

- `session_id`
- `mode`
- `step`
- `question`
- `reply`
- `client_brief`
- `ready_for_confirmation`
- `llm_model`

只有同時設定有效的 `OPENROUTER_API_KEY` 與
`OPENROUTER_INTAKE_ENABLED=1` 才會嘗試 LLM。逾時、解析失敗或未啟用時，
同一輪自動使用 deterministic fallback，`mode` 回傳
`guided_fallback`。前端不可依賴伺服器記憶體保存上一輪 brief。

## 家具選件

### `POST /api/agent/furniture/select`

Request：

```json
{
  "rooms": [
    {"room_id": "living-1", "room_type": "living_room"}
  ],
  "offers": {
    "living-1": [
      {
        "furniture_id": "sofa-001",
        "normalized_type": "sofa",
        "variant_id": "standard",
        "size_cm": {"width": 180, "depth": 85, "height": 80}
      }
    ]
  },
  "style_id": "japanese",
  "context": {
    "room_requirements": {
      "living-1": {
        "roomId": "living-1",
        "usage": ["招待訪客"],
        "furniture": {
          "required": ["sofa"],
          "selected": [
            {"furniture_id": "sofa-001", "normalized_type": "sofa", "count": 1}
          ],
          "deferred": []
        },
        "specialRequests": []
      }
    }
  },
  "llm_selection": null
}
```

`context.room_requirements` 是第 4 步逐房問卷的結論，由
`requirements_from_context()` 收斂成每房一筆需求後同時餵給兩條路徑。
`context.questionnaire.roomRequirements`（陣列形狀）等價。它的作用是：

- `furniture.selected` 進入保護名單，數量沿用問卷填的 `count`。
- `furniture.required` 折成擺位族系後成為該房必備；候選白名單裡沒有該
  族系時自動略過，不讓型錄缺貨拖垮整間房。
- `furniture.deferred` 的家具兩條路徑都不得選入。
- `usage` 與 `specialRequests` 只進入 LLM 提示，不改變驗證結果。

Response：

```json
{
  "source": "local_rules",
  "model": null,
  "warnings": [],
  "rooms": [
    {
      "room_id": "living-1",
      "items": [
        {
          "furniture_id": "sofa-001",
          "normalized_type": "sofa",
          "count": 1,
          "selection_source": "local_rules"
        }
      ]
    }
  ]
}
```

`offers` 是允許選擇的白名單。任何 LLM 結果都必須通過
`request_selections()`／`parse_selections()` 驗證：

- 不得選擇白名單外的家具。
- 每個房間必須符合必要家具族系（房型必備 + 問卷指定且候選有貨的族系）。
- 同族系不得產生不合理重複。
- 數量限制為 1 到 6。
- 使用者暫緩的家具不得選入。
- LLM 結果無效時改用本地規則，原因放入 `warnings`。

前端只使用 response 中的結果，不自行實作 Yen 選件規則。

### 選件 agent 的觸發

伺服器自行注入 OpenRouter 呼叫器（`selection_complete_fn()`），前端不需要
也不應該持有 API 金鑰。判斷順序：

1. payload 帶 `llm_selection` 物件時視為外部已算好的結果，只做驗證。
2. 否則有 `OPENROUTER_API_KEY` 且 `OPENROUTER_SELECTION_ENABLED != 0`
   就實際呼叫 LLM，依 `OPENROUTER_MODELS` 順序重試。
3. 未啟用、呼叫失敗或驗證不過，一律退回 `local_rules`，
   原因寫入 `warnings`。

`source` 仍只有 `openrouter`、`local_rules`、`local_rules_unvalidated`
三種值。`GET /api/scene/llm-status` 增加 `selection_enabled` 欄位。

本地規則同樣讀得到問卷需求：`local_selection_raw()` 以「問卷勾選 →
問卷指定族系 → 同族一件補齊」的確定性順序挑選，再走與 LLM 相同的
`parse_selections()` 驗證，因此 LLM 關閉時選件品質不會退回忽略需求。

## 場景生成與擺放修復

### `POST /api/scene/generate`

場景生成接受 `client_brief`、逐房需求與已選家具。回傳的核心欄位為：

- `selected_furniture`
- `scene_objects`
- `placement_resolution_report`
- `placement.failed`
- `placement.unavailable_types`

AN engine 初次擺放後若出現 `placement_failed`，
`scene_service.py` 會呼叫 `resolve_placements()`，處理順序為：

1. 使用者指定、必要或鎖定家具不得自動刪除，回報 `escalate`。
2. 非必要 companion 放不下或失去主件時移除。
3. 一般家具優先更換成同類型且占地較小的模型。
4. 多次重試仍失敗才移除非必要家具。
5. 每次變更後重新呼叫 AN engine，不沿用或自行修改舊座標。

修復報告每筆至少包含：

```json
{
  "furniture_id": "sofa-001",
  "type": "sofa",
  "action": "replace",
  "from": "原沙發",
  "to": "較小沙發",
  "message_zh": "空間放不下，已換成較小的「較小沙發」。"
}
```

`action` 目前可能是 `replace`、`remove` 或 `escalate`。Bella 應顯示
`message_zh`，不可把 `escalate` 當作成功擺放。

## 失敗與安全規則

- LLM 不可用時，需求訪談與選件都必須有本地 fallback。
- LLM 只能選家具或提出修復策略，不能輸出最終座標。
- 使用者指定家具不可被 Agent 靜默刪除。
- `placement_failed` 不得在前端改成成功；必須顯示原因或人工處理提醒。
- 所有 API 錯誤與 UI 提示使用繁體中文。
- 新增欄位時維持既有 `schema_version`，長度與座標欄位以 `_cm` 命名。

## 驗證位置

修改本契約涉及的程式時，至少執行：

```powershell
uv run pytest tests/test_agent_select.py tests/test_agent_place.py -q
uv run pytest tests/test_agent_requirement_chain.py tests/test_agent_selection_api.py -q
uv run pytest tests/test_project_workflow_api.py tests/test_roompilot_quality_guardrails.py -q
```
