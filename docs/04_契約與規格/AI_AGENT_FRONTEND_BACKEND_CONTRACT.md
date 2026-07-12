# RoomPilot 前後端與未來 AI Agent 連接操作說明

最後更新：2026-07-10

## 目的

目前先完成前端與後端的穩定連接，**不啟用真正的 LLM 或 AI Agent**。前端聊天框呼叫後端 guided intake，後端回傳下一個問題與累積的 `client_brief` JSON。未來接入 Agent 時，只替換後端的 conversation adapter，不改變前端與 3D 場景 API。

## 目前資料流

```text
scene.html / scene.js
  -> POST /api/agent/intake/start
  -> POST /api/agent/intake/answer
  <- next question + client_brief JSON
  -> user confirmation
  -> POST /api/scene/generate { client_brief, ... }
  <- scene payload
  -> scene_viewer.js
```

目前 `intake_service.py` 是 deterministic fallback，只依固定欄位與關鍵字整理答案。它不是 AI Agent，也不會自行操作家具。

## API 1：開始需求訪談

### Request

```http
POST /api/agent/intake/start
Content-Type: application/json
```

```json
{"session_id": "roompilot-demo-001"}
```

### Response

```json
{
  "session_id": "roompilot-demo-001",
  "mode": "guided_fallback",
  "step": "space_type",
  "question": "你想先規劃哪一個空間？例如客廳、臥室、書房或餐廳。",
  "client_brief": {},
  "ready_for_confirmation": false
}
```

## API 2：送出一個回答

### Request

```http
POST /api/agent/intake/answer
Content-Type: application/json
```

```json
{
  "session_id": "roompilot-demo-001",
  "step": "space_type",
  "answer": "客廳，想要明亮一點",
  "client_brief": {"schema_version": "1.0"}
}
```

前端必須把上一個 response 的完整 `client_brief` 原樣帶回。後端目前是無狀態設計，不依賴記憶體 session，因此之後可以改成 Redis、資料庫或 Agent runtime，而不改 API。原始 JSON 只作為前後端資料契約，不直接顯示在使用者畫面；前端顯示的是可讀的需求摘要卡。

### Response

```json
{
  "session_id": "roompilot-demo-001",
  "mode": "guided_fallback",
  "step": "occupants",
  "question": "這個空間主要會由哪些人使用？請告訴我成人、小孩、長輩與寵物的大約數量。",
  "reply": "收到，我先記下來。",
  "client_brief": {},
  "ready_for_confirmation": false
}
```

完成最後一題後，`ready_for_confirmation` 會變成 `true`。前端顯示 JSON 摘要，使用者確認前不能呼叫正式場景生成。

## API 3：生成 3D 場景

`POST /api/scene/generate` 現在接受 `client_brief`。舊欄位仍保留相容性，但新前端應把 `client_brief` 視為主要來源。

```json
{
  "client_brief": {
    "schema_version": "1.0",
    "space": {"type": "living_room", "width_cm": 420, "depth_cm": 360},
    "occupants": {"adults": 2, "children": 0, "elderly": 0, "pets": 0},
    "needs": ["storage", "entertaining"],
    "style": {
      "preferred": ["japanese"],
      "colors": ["warm_neutral"],
      "materials": ["wood", "fabric"],
      "selected_card_id": "japanese-card-01"
    },
    "constraints": ["keep_window_clear", "keep_door_clear"],
    "confirmation": {"status": "confirmed"}
  },
  "floorplan_filename": "sample.dxf",
  "floorplan_dxf_text": null,
  "wall_option": "auto",
  "floor_option": "auto",
  "furniture_random_seed": 123
}
```

## 未來 AI Agent 的接線方式

未來 Agent 只負責「理解使用者語句、決定下一步與呼叫工具」，不能直接修改 Three.js 物件。建議保留以下邊界：

```text
LLM / Agent
  -> client_brief JSON
  -> place_furniture tool
  -> adjust_furniture tool
  -> validate_scene tool
  -> render_style / apply_surface tool
  -> scene payload
```

Agent 不應直接呼叫瀏覽器 DOM，也不應直接寫入 `scene_viewer.js` 的內部狀態。所有空間修改必須經過後端 API 與規則引擎驗證。

### 建議 Agent adapter 介面

```python
class ConversationAdapter(Protocol):
    def start(self, session_id: str) -> dict: ...

    def answer(
        self,
        *,
        session_id: str,
        step: str,
        answer: str,
        client_brief: dict,
    ) -> dict: ...
```

目前 `intake_service.start_intake` 與 `intake_service.advance_intake` 就是 fallback adapter。未來可以建立 `llm_intake_adapter.py`，使用 OpenManus 或其他 LLM runtime，但 response 必須維持相同欄位：

- `session_id`
- `step`
- `question`
- `reply`
- `client_brief`
- `ready_for_confirmation`

## 與外部專案的整合原則

- OpenManus：可參考 Agent runtime、工具調度與 LLM 設定；不要直接把其主程式嵌入 RoomPilot server。
- agentic-design-patterns：可參考 planner、reflection、tool-use 等模式；RoomPilot 第一版只需要 guided intake 與受限工具呼叫。
- kittycad/modeling-app：可參考建模/場景編輯概念；RoomPilot 的現有 Three.js viewer 與家具引擎仍是主線。

參考連結：

- https://github.com/FoundationAgents/OpenManus
- https://github.com/xindoo/agentic-design-patterns
- https://github.com/kittycad/modeling-app

## 本階段驗收

- [ ] 開啟 `/scene` 可看到聊天式需求訪談。
- [ ] 每次回答會呼叫 `/api/agent/intake/answer`。
- [ ] 回應中的 `client_brief` 可在前端 JSON 預覽。
- [ ] 可下載需求 JSON。
- [ ] 最後確認前，生成按鈕維持 disabled。
- [ ] 確認後呼叫 `/api/scene/generate`，payload 包含完整 `client_brief`。
- [ ] 沒有安裝或啟動 OpenManus，也不會阻塞目前的 fallback 流程。
