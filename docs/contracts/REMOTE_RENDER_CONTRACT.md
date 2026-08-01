# 遠端室內渲染契約

第 10 步只透過 FastAPI 的
`POST /api/projects/{project_id}/render-jobs` 呼叫遠端生圖服務。瀏覽器
不得自行指定遠端網址或攜帶供應商金鑰。

## 執行順序

1. 第 8 步完成家具、色卡、牆面、地板、天花與燈光。
2. 第 9 步確認方案，最後鎖定一個透視比較視角。
3. 第 10 步以相同場景、視角及 seed 比較色卡。
4. 使用者確認色卡後，逐房間保存視角並送出正式渲染。

## 請求

`mode` 只接受：

- `palette_comparison`：固定場景與主要視角，只比較色卡。
- `room_final`：使用已確認色卡與逐房間視角產生正式圖片。

必要欄位：

- `schema_version`
- `project_id`
- `scene_version`
- `style_card_ids`
- `style_packs`
- `scene`
- `locks`
- `requirements`
- `master_view`
- `room_views`，僅 `room_final` 必填
- `reference_png_data_url`

家具、牆、地板區域與相機都是鎖定條件。遠端可依 `style_packs` 改變
材質與光線，不得增加、刪除或移動結構及家具。

## 回應

遠端應回傳：

```json
{
  "jobs": [
    {
      "job_id": "opaque-id",
      "style_card_id": "style-card-id",
      "room_id": null,
      "status": "queued",
      "preview_url": null
    }
  ]
}
```

`palette_comparison` 每張色卡一個 job；`room_final` 每個房間一個 job。
`job_id` 視為不透明字串。

## 隱私與設定

FastAPI 送出前會移除姓名、電話、Email 與地址欄位，保留家庭組成、
使用限制及房間個人需求。供應商由伺服器環境變數設定：

```dotenv
ROOMPILOT_RENDER_PROVIDER_URL=
ROOMPILOT_RENDER_PROVIDER_NAME=remote_renderer
ROOMPILOT_RENDER_PROVIDER_TOKEN=
ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS=60
```

未設定或無法連線時回 `503`，不得回傳假圖片或假成功狀態。

## 內建生圖供應者（2026-07-30 增補）

未設定 `ROOMPILOT_RENDER_PROVIDER_URL`、但環境有 `OPENROUTER_API_KEY` 時，
FastAPI 以內建轉接層直接呼叫 OpenRouter 生圖模型（預設
`google/gemini-2.5-flash-image`，`ROOMPILOT_RENDER_IMAGE_MODEL` 可覆蓋）：
同步生成、回圖以 `provider="openrouter_image"` 入庫專案成果，回應仍為本契約
JSON 形狀，但 `status` 直接是 `completed` 且附 `preview_url`。鎖定條件由
prompt 明文表達（結構、家具、相機不得變動）。`ROOMPILOT_RENDER_IMAGE_DISABLED=1`
停用此路徑，回到 503 行為。

## 家具鎖定清單（2026-08-02 增補）

原本內建路徑只送出參考截圖加上一句「請保留家具」，`scene` 雖然是必填卻沒有
被 prompt 讀取，等於要求模型看圖自行辨認家具——實測會換型號、多補座椅或
移動沙發。現在 `build_render_prompt` 會從 `scene.scene_objects` 逐件展開：

- 身分：`catalog_furniture_id`（缺值退 `furniture_id`）、`name_zh_raw`、
  `normalized_type`、`material`、`primary_style`。
- 幾何：`size_cm`、`position_cm`、`rotation_y_deg`，另附由 `floorplan.room_regions`
  外框推得的貼牆描述。這只是把 `backend/engine/` 已定案的座標翻成文字，
  生圖端不得成為第二套幾何來源。
- `room_final` 依 `placement_room_id` / `auto_decor_room_id` 逐房過濾；
  `palette_comparison` 是全景視角，帶整個場景。

排除規則：

- `placement_failed` 的品項不列入——它們沒有進場景，參考截圖裡也看不到。
- 價格欄位（`price`、`price_twd`、`price_ntd`）不進 prompt。
- 家具身分一律取自 `scene`，不得改繞 `requirements`：後者會過
  `_strip_private_fields`，而 `name` 在 `PRIVATE_KEYS` 內，繞過去名稱會被剝掉。

單張上限 `MAX_LOCKED_FURNITURE`（40 件）。超過時 prompt 會明寫未列出的件數，
不做無聲截斷。
