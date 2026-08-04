# 交付 manifest：兩個目錄的分工

本目錄與 `JSON/manifests/` **不是同一份資料的重複備份**，兩邊都要保留。

## 為什麼有兩份

2026-07-30 的型錄切換把 793 筆燈具從家具母集合剝離（9,350 → 8,557），
只重新產出到 `JSON/manifests/`，本目錄留在剝離前的狀態。

| | `JSON/manifests/` | 本目錄 |
|---|---|---|
| GLB 資料列 | 8,557 | 9,350 |
| 圖片資料列 | 25,671 | 28,050 |
| 內容關係 | 本目錄的**子集** | 子集 + 793 筆燈具 |
| 欄位 | 完全相同 | 完全相同 |
| 共有列的 `delivery_url` | 逐列相同，零衝突 | 逐列相同，零衝突 |

兩份沒有互相矛盾的資料列。差額嚴格等於那 793 筆燈具。

## 各自的消費者

`JSON/manifests/`（8,557，家具 lane）

- `backend/server/services/cloud_models.py` — GLB 交付網址
- `scripts/sql/import_official_catalog_to_postgres.py` — PostgreSQL 匯入
- `tests/test_official_catalog_sql.py`、`tests/test_image_manifest_contract.py`

本目錄（9,350，燈具重建套件）

- `backend/server/services/cloud_images.py` — 三視角圖片交付網址
- `scripts/sql/build_lighting_manifest.py` — **主要用途**：以「本目錄減去
  `JSON/manifests/`」的差集重建 `lighting_assets_manifest.csv`，燈具的品名、
  分類與尺寸取自 `../furniture_catalog_cloud_9350.json`
- `tests/test_cloud_image_previews.py`（`CATALOG_COUNT = 9_350`）

`lighting_assets_manifest.csv` 是本目錄唯一在剝離後才產生的檔案，
由 `build_lighting_manifest.py` 產出、`scripts/sql/import_lighting_assets_to_postgres.py`
匯入 `roompilot.lighting_assets`。

## 刪除前必讀

刪掉本目錄的 9,350 兩份 CSV 或 `../furniture_catalog_cloud_9350.json`，
就再也無法重建燈具 manifest——那 793 筆燈具的交付網址、品名與尺寸只存在這裡。
`JSON/manifests/` 沒有它們。

`origin/kai` 上有一版 8,675 筆的 manifest（兩個目錄已統一），那是**部分**剝離
（留下 118 筆燈具混在家具 lane）。採用它會與燈具獨立表的邊界衝突，也會與
`roompilot.furniture_items` 的 8,557 筆脫鉤。

## 環境變數

`ROOMPILOT_GLB_MANIFEST_PATH` 必須指向 `JSON/manifests/glb_upload_all_result.csv`。
指向本目錄會把 793 筆燈具灌回家具 lane。
