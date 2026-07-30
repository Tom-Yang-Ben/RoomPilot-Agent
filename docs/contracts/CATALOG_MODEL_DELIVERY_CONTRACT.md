# Kai 官方家具資料與模型交付契約

更新日期：2026-07-30
主要 owner：Kai（`JSON/`、`backend/catalog/`、`scripts/sql/`）
協作 owner：Django（RAG metadata／向量）、Bella（FastAPI／正式前端 adapter）

## 唯一資料來源

正式家具資料只讀取下列 Kai 交付檔案；不得再以
`backend/catalog/data/furniture_catalog_cloud_9350.json` 或其 manifest 複本做推薦、模型
可用性判斷或 SQL 匯入來源。

| 用途 | 正式路徑 | 說明 |
|---|---|---|
| 家具身分、尺寸、風格、房型、RAG metadata | `JSON/furniture/furniture_official_catagory.json` | 最新 8,557 筆官方家具 |
| GLB 可用性與 CloudFront URL | `JSON/manifests/glb_upload_all_result.csv` | 唯一模型交付憑據 |
| 三視角圖片可用性 | `JSON/manifests/image_upload_all_result.csv` | front、side、angle-45 圖片憑據 |
| Django 向量交付 | `JSON/RAG/furniture_embeddings_bge_m3.jsonl` | Git LFS 管理；7,958 筆 `rag_indexable` 家具，每筆為 BGE-M3 1024 維向量 |

`glb_upload_manifest.csv` 與 `image_upload_manifest.csv` 是上傳輸入；runtime 僅能信任
對應的 `_all_result.csv`。只有 `upload_status` 已完成且有 HTTPS `delivery_url` 的資料才能
出現在 `/api/furniture?has_model=true`。

## 跨資料夾修改

- 主要修改：Kai 的 `JSON/`、`backend/catalog/cloud_catalog.py`、`scripts/sql/`。
- 消費端修改：Bella 的 `backend/server/main.py` 與 `backend/server/services/cloud_models.py`。
- 資料契約：官方 JSON 提供家具 identity 與 RAG metadata；manifest 提供資產驗證；FastAPI
  不得以舊型錄覆寫 ID、尺寸、房型、風格、GLB 或圖片 URL。
- 為何跨資料夾：catalog、交付憑據、SQL 與 UI/API 是同一筆家具的 producer、persistence
  與 consumer，單改其中一處會造成第 5 步推薦和第 6 步模型不一致。
- 驗證：catalog ID 與 GLB result ID 一對一、模型 URL 為 HTTPS、API 僅輸出已驗證項目、
  SQL 僅先執行 `--dry-run`。

## RAG 與幾何邊界

Django 的 RAG 只負責解析、檢索、排序與證據；不決定家具座標、不修改 `layout_json` 或
`scene_json`。`backend/engine` 是碰撞、門窗淨空、走道與擺放合法性的唯一裁決者。

總 catalog 有 8,557 筆；其中 7,958 筆為 `active_count`／`indexable_count`，會出現在
RAG 向量檔。其餘 599 筆 `rag_indexable=false` 不得以缺向量視為下載失敗，也不應進入向量檢索。

## 本機與 PostgreSQL

FastAPI 預設使用同一份 `JSON/`；只有明確設定
`ROOMPILOT_CATALOG_PROVIDER=postgres`，才會使用 Kai 的 current catalog view。資料庫匯入必須先：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
```

乾跑成功不代表資料已寫入 PostgreSQL；實際匯入需由 Kai owner 或取得授權後另行執行。

## 環境設定

```dotenv
ROOMPILOT_MODEL_DELIVERY_MODE=cloudfront
ROOMPILOT_CLOUD_CATALOG_PATH=JSON/furniture/furniture_official_catagory.json
ROOMPILOT_GLB_MANIFEST_PATH=JSON/manifests/glb_upload_all_result.csv
```

不要提交大型 GLB、PNG 原圖、模型快取、LFS materialize cache、資料庫檔案或密碼。
