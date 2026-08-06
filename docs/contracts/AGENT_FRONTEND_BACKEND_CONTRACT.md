# RoomPilot Agent 前後端契約

最後更新：2026-08-06

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
  "context": {},
  "llm_selection": null
}
```

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
- 每個房間必須符合必要家具族系。
- 同族系不得產生不合理重複。
- 數量限制為 1 到 6。
- LLM 結果無效時改用本地規則，原因放入 `warnings`。

前端只使用 response 中的結果，不自行實作 Yen 選件規則。

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

## 成果報告（Report Agent，兩版比較）

第 8 步收尾由 Bella adapter（`backend/server/design_manual_service.py`）把
scene_json 與逐房生圖成果組成 Yen Report Agent 的 Docs 層文件，產出**兩版**
報告供比較：八章設計手冊（Pillow 排版），與品牌交付提案（`backend/agent/
skills/roompilot-delivery-pdf/` 打包 skill 的 build_pdf.py 以 Playwright
Chromium 排版；文案由 `skills/delivery/` 流程層產生——LLM 依 SKILL.md 寫作
規範改寫，離線走只寫既有事實的 deterministic 底稿）。組稿與排版都在
`backend/agent/`，adapter 不重做。

### `POST /api/projects/{project_id}/design-manual`

Request：`scene`（state.sceneData）＋逐房 `rooms`（`room_id`、`room_label`、
`width_cm`、`depth_cm`、目前最新生圖 `image_data_url`（可為 null）、`model`）。

Response（201）：`manual.sections`（八章標題）、`manual.download_url`、
`manual.rendered_rooms`、專案 `revision` 與 `updated_at`。workflow 增加
`design_manual` 中繼資料（含檔名；不存圖與 PDF 內容）。

- 未設定 `OPENROUTER_API_KEY` 照樣輸出：LLM 只潤飾前言與設計理念，離線走
  deterministic 底稿。
- `placement_failed` 家具不進手冊；未標價品項不猜價。
- 缺 `scene` 回 422 `scene_required`；缺房間回 422 `rooms_required`。

### `GET /api/projects/{project_id}/design-manual/pdf`

下載最近一次產出的 PDF。尚未產出回 404 `design_manual_not_found`；紀錄在但
檔案遺失回 410 `design_manual_file_missing`。

### `POST /api/projects/{project_id}/delivery-proposal`

品牌交付提案版：與設計手冊吃**同一份 payload**（scene＋rooms）。Response
（201）：`proposal.download_url`、`proposal.warnings`（排版腳本的殘頁／空圖
提醒）、`revision`、`updated_at`；workflow 增加 `delivery_proposal` 中繼資料。
文案規則：只寫資料裡有的數字與規格、無圖房間寫進已知限制、未標價不猜價
（規範全文見打包 skill 的 `references/writing-rules.md`）。

排版引擎（playwright Chromium）未安裝時回 503
`delivery_engine_not_configured` 並附安裝指引（`requirements-delivery.txt`＋
`playwright install chromium`）；`GET /api/delivery-proposal/status` 可預先查。
`GET /api/projects/{project_id}/delivery-proposal/pdf` 下載，404／410 語意同
設計手冊。PDF 旁會留存 `content.json` 供文案數字溯源。

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
uv run pytest tests/test_project_workflow_api.py tests/test_roompilot_quality_guardrails.py -q
uv run pytest tests/test_design_manual_api.py tests/test_delivery_proposal_api.py backend/agent/tests/test_agent_report.py -q
```
