# Kai：資料庫與目錄資料架構

## 角色與範圍

Kai 負責 RoomPilot 的正式目錄資料來源、PostgreSQL 匯入、CloudFront/S3 模型與圖片交付資訊，以及可供 RAG 檢索的家具中繼資料。

主要責任目錄：

- `backend/catalog/`
- `backend/catalog/data/`
- `scripts/sql/`
- PostgreSQL `roompilot` schema 與其 view

Bella 可以讀取並呈現資料；Yen 可以排序與推薦；但三者都不可直接改寫 Kai 的正式目錄資料。

## 正式資料來源與優先順序

1. PostgreSQL view `roompilot.furniture_catalog_current`：第 6 步與 API 的正式來源。
2. `backend/catalog/data/furniture_catalog_cloud_9350.json`：PostgreSQL 尚未可用時的唯讀 fallback。
3. `backend/catalog/data/manifests/glb_upload_all_result.csv` 與 `image_upload_all_result.csv`：模型、三視角圖片的交付憑據。
4. `furniture_catalog_6styles_zh.json`：舊的風格與中文 enrichment，不能覆蓋正式 ID、尺寸、模型 URL 或圖片 URL。

禁止再把舊的 10,550 筆資料、測試 CSV 或未驗證的本機 GLB 當成正式來源。

## 燈具、天花板與冷氣資料模型

### 家具燈具

正式燈具仍是 `furniture_catalog_current` 的家具子集。清洗完成後，每一筆需至少具有：

```json
{
  "item_id": "stable-id",
  "asset_kind": "lighting_fixture",
  "lighting_type": "pendant|track|downlight|wall|table|floor",
  "glb_url": "https://...",
  "thumbnail_url": "https://...",
  "dimensions_cm": {"width": 0, "depth": 0, "height": 0},
  "verification_status": "verified|quarantine",
  "license": "catalog-origin|CC0"
}
```

不得只靠名稱中的 `lamp` 或 `light` 直接上架；需先檢查 GLB 是否能載入、尺寸是否合理、預覽是否真的是燈具。

### 天花板與照明配置

天花板不是家具 catalog item，而是每個房間的 `surface_overrides` / `scene_json` 結構資料。可選結構：

- `exposed`：裸頂。
- `flat`：平釘天花，下吊 12 cm。
- `cove`：四周燈槽，下吊 18 cm。
- `floating`：中央懸浮板，下吊 20 cm。
- `linear`：平頂加線型燈槽，下吊 14 cm。
- `wood-grid`：木格柵，下吊 16 cm。
- `no-main-light`：無主燈平頂，下吊 12 cm。

天花板表面材質可引用 `surface_catalog`；燈具則以 `lighting_fixture` 引用正式家具 catalog。兩者不得混為同一張資料表。

### 冷氣

冷氣目前是結構與設備需求，不進第 6 步家具配置。第一階段資料只需保存：

```json
{
  "system": "wall-split|ceiling-cassette|ducted|none",
  "placement": "wall|ceiling_void|linear_supply",
  "room_id": "...",
  "status": "placeholder"
}
```

日後取得可商用模型後，才建立獨立 HVAC catalog；不可把空氣清淨機誤當冷氣模型。

## 燈具清洗與隔離流程

```text
Kai catalog 候選 GLB / 外部 CC0 GLB
  -> 讀取 GLB bounding box、材質數、面數與載入結果
  -> 產生只含模型的 PNG 預覽
  -> 分類 lighting_type、校驗實體尺寸
  -> verified：寫入 staging，再 UPSERT 正式 catalog
  -> 不確定、壞檔、非燈具：寫入 quarantine，不影響正式資料
```

外部資產僅接受 CC0 或可商業使用且可追溯授權的來源。原始下載檔、Blender 暫存檔、批次 PNG 不進 Git；Git 只保存 manifest、來源 URL、授權、checksum 與產生規則。

### 燈具資產存放與使用位置

| 項目 | 位置／用途 |
|---|---|
| 正式 GLB 與三視角 PNG | Kai 管理的 S3 bucket，經 CloudFront 對外提供 HTTPS URL。 |
| 正式 catalog | PostgreSQL `roompilot.furniture_catalog_current`，提供 `glb_url`、`thumbnail_url`、尺寸、類型、授權與驗證狀態。 |
| Git 內 manifest | `backend/catalog/data/manifests/lighting_assets_manifest.csv`，只保存 item ID、CloudFront URL、checksum、授權、分類與驗證結果。 |
| 原始下載、Blender 暫存、批次渲染 | 本機或物件儲存 staging；不得提交 Git。 |
| PBR 紋理 | `backend/server/static/pbr_assets/`；這是網站執行期資產，必須提交版本控制。 |

執行期使用流程：Bella 的 `/api/furniture` 讀取 verified catalog item，前端以 `thumbnail_url` 顯示純物件 PNG、以 `glb_url` 載入 3D 模型；Yen RAG 與 Ancai 擺放器只可使用 `verification_status=verified` 的項目。

CloudFront 基底 URL 與 manifest 路徑由下列環境設定指定，不可寫死到前端：

```dotenv
ROOMPILOT_CLOUDFRONT_BASE_URL=https://ddgsm1yg3xikc.cloudfront.net
ROOMPILOT_GLB_MANIFEST_PATH=backend/catalog/data/manifests/glb_upload_all_result.csv
ROOMPILOT_LIGHTING_MANIFEST_PATH=backend/catalog/data/manifests/lighting_assets_manifest.csv
```

本機 IKEA GLB 備援尚未實作。後續由 Kai 與 Django 共同定義固定備份位置、正式 JSON 對照表、完整性驗證與 API 模式後，才能加入環境變數；在此之前 CloudFront 仍是唯一正式交付來源。

## 新增資料到資料庫：Kai 作業手冊

新增或修正正式 catalog 時，必須依下列順序進行，不能跳過 staging 或直接手改 `furniture_catalog_current` view。

1. 將候選資料寫入匯入 JSON/CSV，保留 `item_id`、供應來源、GLB URL、圖片 URL、尺寸、授權與 checksum。
2. 匯入 staging table，先做 duplicate ID、空 URL、尺寸範圍與授權檢查。
3. 對燈具執行 GLB 載入、bounding box、純物件 PNG 預覽、類型分類檢查。
4. 合格資料以 transaction UPSERT 寫入正式 catalog；失敗資料寫入 quarantine 並填寫 `reason_code`。
5. 重新整理 `roompilot.furniture_catalog_current`，確認 API 可讀到 `verification_status=verified` 的資料。
6. 以 dry-run、SQL contract 與 manifest 測試驗證後，才讓 Bella／Yen 使用。

新外部 CC0 燈具的上傳順序：下載到本機 staging → 驗證與產生 PNG → 上傳 S3/CloudFront → 寫入 `lighting_assets_manifest.csv` → staging/UPSERT PostgreSQL → API contract 測試。任何一步失敗均留在 quarantine，不發布 URL。

建議欄位責任如下：

| 欄位群組 | 必填 | 說明 |
|---|---:|---|
| `item_id`、來源、授權、checksum | 是 | 穩定 ID 與可追溯性；不可由前端生成。 |
| `glb_url`、`thumbnail_url`、三視角 URL | 是 | 交付給第 6 步與家具選擇器。 |
| `dimensions_cm`、`asset_kind`、`lighting_type` | 是 | 供空間驗證、RAG 與 UI 篩選。 |
| `verification_status`、`reason_code` | 是 | 決定是否可被自動推薦與配置。 |
| 風格、材質、房型標籤 | 建議 | 可由 Yen/RAG 使用，但不得取代正式尺寸。 |

```powershell
# 先確認匯入內容與 schema，不寫入資料庫
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run

# 寫入前後都必須跑的契約測試
.\.venv\Scripts\python.exe -m pytest -q tests/test_official_cloud_catalog.py tests/test_official_catalog_sql.py tests/test_image_manifest_contract.py
```

## 跨資料夾改動規則

- 修改 `backend/catalog/`、`scripts/sql/`、資料 schema：先更新 `docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md`，並告知 Django、Bella。
- Django 若需新的房間或開口關係欄位，只提出 schema 需求，不能直接修改 catalog 資料。
- Bella 若需新篩選或圖片欄位，只經由 API adapter 消費，不能在前端生成新的正式 item ID。
- Yen 的 RAG 可讀取 `lighting_type`、風格、尺寸與房間適配性，但不可變更 `verification_status`。

## 驗證

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe -m pytest -q tests/test_official_cloud_catalog.py tests/test_official_catalog_sql.py tests/test_image_manifest_contract.py
```
