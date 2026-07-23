# AWS 家具型錄橋接

Bella 保留 `roompilot/` 架構、Yen 選件規則、engine 擺放與 SQLite 專案資料，只把家具 GLB 的主要交付來源改為 `origin/kai-aws` 已驗證的 CloudFront Manifest。

## 目前來源

| 資料 | 來源 |
|---|---|
| 家具搜尋、風格、尺寸與選件 metadata | `roompilot/catalog/data/furniture_catalog_6styles_zh.json` |
| 家具 GLB | AWS CloudFront |
| 專案與流程狀態 | 本機 SQLite |
| 牆面、地板與門片 | Bella 現有本機／程序化來源 |

Manifest 位於：

```text
roompilot/catalog/data/manifests/glb_upload_all_result.csv
```

它包含 9,350 個已上傳或已存在的 GLB。Bella 的 10,550 件型錄中，目前 1,774 件可直接以 ID 對應，另有 7,262 件可透過唯一英文品名對應，共 9,036 件能使用雲端模型；其餘項目不會猜測或退回本機模型。

## 交付規則

- 預設模式是 `cloudfront`。
- 只有 Manifest 中狀態已完成且具 HTTPS URL 的模型可被發布。
- 對應順序是家具 ID、合併後模型優先 ID、唯一標準化英文品名。
- 同名對應超過一筆時拒絕猜測。
- 雲端模式找不到模型時回報不可用，不回退本機 ZIP 或 GLB。
- 舊的 glTF 拆解、buffer、圖片與 sample GLB 端點在雲端模式回傳 `410`。

需要暫時測試舊本機資料時，可明確設定：

```dotenv
ROOMPILOT_MODEL_DELIVERY_MODE=local
```

部署時也可覆寫：

```dotenv
ROOMPILOT_CLOUDFRONT_BASE_URL=https://ddgsm1yg3xikc.cloudfront.net
ROOMPILOT_GLB_MANIFEST_PATH=roompilot/catalog/data/manifests/glb_upload_all_result.csv
```

## 驗證

```text
GET /api/catalog/status
GET /api/furniture?has_model=true&page_size=3&detail=scene
```

第一個端點應回傳 `provider = aws_cloudfront`、`manifest_ready = true` 與 `verified_model_count = 9350`。第二個端點只會列出具有已驗證 `https://ddgsm1yg3xikc.cloudfront.net/...` 模型 URL 的家具。
