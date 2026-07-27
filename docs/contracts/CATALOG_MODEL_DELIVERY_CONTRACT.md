# RoomPilot 家具模型交付契約

最後更新：2026-07-23

本文件定義家具 metadata、雲端 GLB 與網站之間的模型交付規則。
正式家具 GLB 由已驗證的 CloudFront Manifest 提供。

## 資料來源

| 資料 | 來源 |
|---|---|
| 正式家具、尺寸、材質、顏色與 GLB ID | `backend/catalog/data/furniture_catalog_cloud_9350.json` |
| 六風格、RAG、分類與擺放提示 enrichment | `backend/catalog/data/furniture_catalog_6styles_zh.json` |
| 家具 GLB | AWS CloudFront |
| 未對應家具 | `backend/catalog/data/quarantine/unmatched_cloud_furniture/` |
| 離線備援 | README 指定並通過驗證的外部 zip |

Manifest 位於：

```text
backend/catalog/data/manifests/glb_upload_all_result.csv
```

正式集合必須是 cloud catalog 與 Manifest 完整共有的 9,350 個 ID。
六風格檔只能補資料，不能增加家具。目前 9,021 件可由 ID 或唯一英文
品名安全補上舊資料，329 件維持未分類；無法映射的 1,514 筆舊資料
排除於正式查詢。

隔離項目在確認家具 ID、唯一品名或 Manifest 前，不得進入網頁、
Agent 選件或 3D 場景，也不得猜測模型 URL。

## 交付規則

- 預設模式是 `cloudfront`。
- 網頁、Agent 與 3D 只能列出正式 9,350 件，不得先載入 10,550 件再
  於前端隱藏多餘資料。
- 只有 Manifest 中狀態已完成且具 HTTPS URL 的模型可被發布。
- 對應順序是家具 ID、合併後模型優先 ID、唯一標準化英文品名。
- 同名對應超過一筆時拒絕猜測。
- 雲端模式找不到模型時回報不可用，不回退本機 ZIP 或 GLB。
- 舊的 glTF 拆解、buffer、圖片與 sample GLB 端點在雲端模式回傳 `410`。

## 離線備援

雲端無法連線時，管理者可使用 README 指定的 IKEA 中文命名備援包。
啟用前必須執行 SHA-256 與型錄對應驗證。

只有驗證成功後才可明確設定：

```dotenv
ROOMPILOT_MODEL_DELIVERY_MODE=local
ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS=D:\RoomPilot-assets\ikea抓取家具glb_中文命名版-20260703T022419Z-3-001.zip
```

設定 `ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS` 後，伺服器只讀指定的 zip 或
目錄，不再掃描 Downloads 中其他壓縮包。這是人工災難切換，不是
自動 failover；雲端恢復後必須改回 `cloudfront` 並重新啟動。

## 部署覆寫

部署時可覆寫：

```dotenv
ROOMPILOT_CLOUDFRONT_BASE_URL=https://ddgsm1yg3xikc.cloudfront.net
ROOMPILOT_GLB_MANIFEST_PATH=backend/catalog/data/manifests/glb_upload_all_result.csv
```

## 驗證

```text
GET /api/catalog/status
GET /api/furniture?has_model=true&page_size=3&detail=scene
```

第一個端點應回傳 `provider = aws_cloudfront`、`manifest_ready = true`
且 `verified_model_count` 大於零。第二個端點只列出具有已驗證 HTTPS
模型 URL 的家具。

相關自動化測試：

```powershell
uv run pytest tests/test_cloud_models.py tests/test_cloud_catalog_bridge.py -q
uv run pytest tests/test_cloud_quarantine.py tests/test_external_glb_resolution.py -q
```
