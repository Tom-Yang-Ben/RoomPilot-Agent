# 第 8 步 AI 寫實生圖契約（OpenRouter nano banana）

第 8 步逐房視角寫實生圖只透過 FastAPI 呼叫 `backend/agent/` 的 Gen_Pic Agent
（OpenRouter nano banana）。瀏覽器不得自帶模型網址或金鑰。此路徑與泛用遠端
渲染商（`REMOTE_RENDER_CONTRACT.md`）並存，直接接內建 agent。

## 邊界

- Bella（`backend/server/ai_render_service.py`）是 adapter：把 `scene_json` 補充成
  agent 文件並編排呼叫；生圖流程、失敗政策（主模型 3 次 → fallback）由 Yen 的
  `GenPicAgent` 決定，不得重做。
- 家具、座標、格局一律沿用 engine 既有 `scene_objects`（公分、房間中心原點）；
  adapter 只把中心原點翻成提示詞的角落原點措辭，不產生新座標。
- 逐房把第 7 步鎖定視角的 3D 截圖當 img2img 參考，模型不得增減或移動任何擺設。
- 家電只作為畫面 context（`render_context.appliance_requirements`）。
- 固定設備不在白模也不在家具清單，靠房型補述進提示詞（`genpic_info._ROOM_TYPE_HINTS`）：
  浴室必須有衛浴設備、廚房必須有系統廚具、陽台白色部分為室外。房型以 `room_type`
  為準，中文房名為後援。
- 尺寸不進提示詞的定案只對廚房例外：廚房報自己的長寬與面積，取
  `floorplan.room_regions` 中同 `room_id` 的輪廓外接矩形（查不到才退回整體平面圖尺寸）。

## 端點

- `GET /api/ai-render/status` → `{configured, provider, model, fallback_model}`；不外洩 token。
- `POST /api/projects/{id}/ai-renders`
  - 請求：`{project_id, scene, rooms:[{room_id, room_label, room_type?, reference_png_data_url, note?, night_only?, day_image_data_url?}]}`
    - `reference_png_data_url` 為該房鎖定視角的 Three.js 截圖（`data:image/png;base64,...`）。
    - `room_type` 決定客廳夜間圖與浴室／廚房／陽台的房型補述。
  - 回應：`{results:[{room_id, room_label, status, image_id?, image_data_url?, model?, notices, night_image_data_url?, night_image_id?, night_model?}], edit_remaining, revision, updated_at}`
  - 客廳（`room_type=living_room` 或房名含「客廳」）額外回一張夜間燈光圖 `night_image_data_url`：**以剛生出來的日光圖重打光**（img2img 附日光圖，不是白模截圖），提示詞只給夜間光影一句，避免模型整張重畫；夜間失敗不影響日光初稿，附 `night_notices`。
  - 房間可帶 `night_only: true`：只生夜間那張、不重生日光初稿，結果標 `night_only: true` 且不含 `image_data_url`，該房也不進回應的 `rooms`（沒有伺服器端日光圖就沒有 lock_manifest，仍不可改圖）。用於第 7 步代表房沿用色卡圖當日光初稿的情形，以及夜景單獨失敗後的補生。這條路徑的日光圖只在前端，須以 `day_image_data_url` 一併送回當底圖；沒送則退回 3D 截圖。
  - 單房失敗只標記該房 `status:"failed"`，其餘照常回傳。
- `POST /api/projects/{id}/ai-renders/{room_id}/edit`
  - 請求：`{feedback, image_data_url}`（`image_data_url` 為要修改的當前圖）。
  - 回應：`{result:{room_id, status, image_id, image_data_url, model, notices}, edit_remaining, updated_at, revision}`

## 額度與狀態

- 整批共用一次改圖。`ai_render.edit_used` 存在 project workflow，由伺服器強制；
  用完回 `409 ai_edit_budget_exhausted`。每次重新生圖（`ai-renders`）視為新一批、`edit_used` 歸零。
- 每房鎖定清單（`lock_manifest`）由伺服器於生圖時產生並保存，供改圖鎖定「只改指定內容、其餘不動」。
- AI 生圖端點會 bump 專案 `updated_at`；回應帶回 `updated_at`/`revision`，前端須同步以免後續保存衝突。

## 設定

沿用 `OPENROUTER_API_KEY`；模型可用 `ROOMPILOT_GENPIC_MODEL`、
`ROOMPILOT_GENPIC_FALLBACK_MODEL` 覆蓋。未設定金鑰時回 `503`
`openrouter_api_key_not_configured`，明確顯示「尚未連接」，不得回假圖或假成功。
