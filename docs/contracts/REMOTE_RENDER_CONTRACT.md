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
