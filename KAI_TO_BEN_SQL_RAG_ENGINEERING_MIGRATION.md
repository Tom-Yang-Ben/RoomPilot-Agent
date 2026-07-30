# Kai → Ben：PostgreSQL、RAG 與工程功能移植清單

## 資料夾稱呼

| 文件稱呼       | 用途                                        |
| -------------- | ------------------------------------------- |
| Kai 分支資料夾 | 最新 PostgreSQL、家具 RAG、工程報告功能來源 |
| Ben 分支資料夾 | 要補入上述功能的整合目標                    |

## 整合原則

1. 正式家具、風格、材質、資產與 embeddings 統一使用 Kai 最新 PostgreSQL 資料。
2. 以 Kai 分支資料夾作為本清單所列功能的來源。
3. 不可整包覆蓋 Ben 分支資料夾；必須依下列清單逐項新增或合併。
4. Ben 分支現有 OCR、平面圖辨識、渲染與較新的前端程式必須保留。
5. 不提交或互相複製 `.env`、模型快取、`.runtime/`、`.tmp/` 或 API key。
6. 家具位置、碰撞與淨空仍只由 `backend/engine/` 判定；RAG 只負責檢索與排序。

## 一、直接新增到 Ben 分支的檔案

請將 Kai 最新分支的 `scripts/` 資料夾直接完整替換 Ben 分支的 `scripts/` 資料夾。

以下檔案在 Ben 分支缺少，可從 Kai 分支以相同相對路徑加入。

### PostgreSQL catalog repository

```text
backend/catalog/postgres_repository.py
backend/catalog/postgres_admin_repository.py
backend/catalog/runtime_catalog_repository.py
backend/catalog/rag_repository.py
```

用途：

- 正式家具 SQL 查詢、分頁與 facet。
- 家具管理 CRUD、啟用檢查、軟刪除與 audit。
- 風格卡、設計風格、表面材質、裝修費率與 quarantine runtime 查詢。
- BGE-M3／pgvector 家具候選搜尋。

### FastAPI adapter

```text
backend/server/catalog_admin.py
backend/server/rag_api.py
backend/server/postgres_project_store.py
```

用途：

- 家具管理 API。
- 家具 RAG 狀態、同步搜尋與背景工作 API。
- PostgreSQL `workflow_json`、render metadata 與工程資料保存。

### Django 家具 RAG runtime

加入整個目錄：

```text
backend/spatial_data/rag/
```

必須包含該目錄內的 Python 模組，以及：

```text
backend/spatial_data/rag/data/category_groups.json
backend/spatial_data/rag/data/taxonomy.json
```

### 工程報告服務

加入整個目錄：

```text
backend/server/engineering/
```

包含工程量、Structured Retrieval、規則、估價、排程、文件輸出與 API。

### 工程知識資料

加入整個目錄：

```text
backend/catalog/data/engineering/
```

這個目錄不能省略。工程報告目前仍由 `JsonEngineeringKnowledgeRepository` 直接讀取這些 JSON／JSONL，尚未改成從 PostgreSQL 讀取。

必須包含：

```text
work_items.json
material_catalog.json
material_work_mappings.json
equipment_mep_mappings.json
price_records.json
productivity_records.json
task_dependencies.json
construction_knowledge.jsonl
source_registry.json
source_registry.csv
production_templates/
```

其中 `price_records.json` 與 `productivity_records.json` 是 `DEMO_ONLY` 合成資料，不得當成正式市場報價或正式工期。

### 正式前端頁面

```text
backend/server/static/rag.html
backend/server/static/rag.css
backend/server/static/rag.js
backend/server/static/engineering.html
backend/server/static/engineering.js
backend/server/static/engineering_link.js
```

### RAG 套件清單

```text
requirements-rag.txt
```

安裝方式：

```powershell
Set-Location 'D:\新增資料夾'
.\.venv\Scripts\python.exe -m pip install -r requirements-rag.txt
```

模型權重與 cache 必須放在 repository 外，不得提交 Git。

## 二、Ben 分支既有檔案：只能合併修改

### `backend/server/main.py`

不可直接用 Kai 版整份覆蓋。只合併以下內容：

- 匯入並掛載 `catalog_admin_router`。
- 匯入並掛載 `rag_router`。
- 呼叫 `build_engineering_router(...)`。
- 使用 `build_project_store(...)` 建立 project store。
- 正式家具改用 `backend.catalog.postgres_repository`。
- style、surface、cost、quarantine 改用 `runtime_catalog_repository`。
- 加入 PostgreSQL／runtime catalog 的 503 exception handler。
- 加入 `/api/health` 與 `/engineering`。
- shutdown 時關閉 catalog connection pool 與 project store。

必須保留 Ben 分支現有的：

- OCR provider 與房型辨識。
- PNG／JPG／DXF 驗證。
- 目前的 render provider。
- 平面圖分析與校正流程。
- Ben 分支較新的八步前端 API。

### `backend/server/project_store.py`

合併：

- `ProjectStoreUnavailable`
- `provider = "sqlite"`
- `imports_legacy_on_startup`
- `_read_project_env(...)`
- `project_store_provider(...)`
- `build_project_store(...)`
- `close()` 相容介面

不得移除原有 SQLite 離線模式。

### `backend/server/style_cards.py`

改為透過：

```python
load_runtime_style_cards(...)
```

讀取正式 PostgreSQL runtime catalog；明確離線 JSON 模式仍由 repository 處理。

### `backend/server/cost_estimation.py`

改為透過：

```python
load_runtime_cost_catalog(...)
```

讀取裝修費率與來源。

### `backend/server/postgres_catalog.py`

建議替換成 Kai 分支的相容 shim，避免同時存在兩套 PostgreSQL catalog 邏輯。新程式應直接引用：

```python
backend.catalog.postgres_repository
```

### `backend/server/static/scene.html`

不可整份替換。只加入 `engineering_link.js` 的 script 引用，並保留 Ben 分支現有頁面結構與其他 script。

### `.env.example`

只合併 PostgreSQL、project store 與 RAG 的設定名稱；不得放入真實密碼或 API key。

建議欄位：

```dotenv
ROOMPILOT_CATALOG_PROVIDER=postgres
ROOMPILOT_RUNTIME_CATALOG_PROVIDER=postgres
ROOMPILOT_PROJECT_STORE_PROVIDER=postgres

DB_HOST=localhost
DB_PORT=5432
DB_NAME=roompilot_db
DB_USER=postgres
DB_PASSWORD=
DB_SSLMODE=disable
DB_CONNECT_TIMEOUT=10
DB_POOL_MIN=1
DB_POOL_MAX=8

ROOMPILOT_CATALOG_ADMIN_TOKEN=

ROOMPILOT_RAG_ENABLED=false
ROOMPILOT_RAG_PARSER_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
ROOMPILOT_RAG_DEVICE=auto
ROOMPILOT_RAG_MODEL_CACHE=

ROOMPILOT_DEMO_MODE=false
```

## 三、SQL 與 pgvector

### 目前正式資料筆數

```text
正式 catalog／GLB：8,675
三視角圖片：26,025
active／RAG-indexable／BGE-M3 向量：8,076
inactive 複核資料：599
```

不得再使用 8,557／7,958／25,671 的舊批次。完整重建時先執行 catalog dry-run，再用 `--replace-existing` 在同一個 transaction 內刪除並重建家具 tables／views／staging，最後重新匯入向量：

```powershell
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py --require-all --dry-run
.\.venv\Scripts\python.exe scripts\sql\import_official_catalog_to_postgres.py --replace-existing
.\.venv\Scripts\python.exe scripts\sql\import_furniture_embeddings_to_postgres.py --require-all
```

### 正式 catalog schema

Ben 分支的下列檔案是舊版，需要更新為 Kai 最新版本：

```text
scripts/sql/roompilot_postgresql_schema.sql
```

新版至少必須提供：

- `roompilot.furniture_catalog_api_current`
- `roompilot.furniture_admin_audit`
- 正式家具 current views 與必要 index

### Furniture embeddings

若組員要建立自己的 PostgreSQL，需要加入：

```text
scripts/sql/roompilot_furniture_embeddings_schema.sql
scripts/sql/import_furniture_embeddings_to_postgres.py
```

並確保 PostgreSQL 已安裝 `vector` extension。

若組員直接連線到 Kai 已完成匯入的 PostgreSQL，網站 runtime 不需要在 Ben 分支保存 91 MB embeddings JSONL；向量已由 PostgreSQL 提供。

### 組員匯入規則

- 使用 Kai 提供的最新 SQL schema 與正式資料批次。
- 不得再匯入舊的 9,350／10,550 catalog。
- 不得把 quarantine 或 appliance 資料匯入正式家具 API。
- 正式啟用的家具必須具有 GLB 與 front／side／angle-45 圖片。

## 四、不要替換的內容

以下內容應保留 Ben 分支版本：

```text
backend/server/static/scene_v2.js
requirements.txt
scripts/sql/import_official_catalog_to_postgres.py
JSON/furniture/furniture_official_catagory.json
JSON/manifests/glb_upload_manifest.csv
JSON/manifests/glb_upload_all_result.csv
JSON/manifests/image_upload_manifest.csv
JSON/manifests/image_upload_all_result.csv
frontend3d/
```

原因：

- Ben 分支的 `scene_v2.js`、OCR、平面圖與渲染內容較新，不能被 Kai 分支較舊整合版本覆蓋。
- `requirements.txt` 保留 Ben 分支既有 vision／OCR 依賴；RAG 另由 `requirements-rag.txt` 安裝。
- 官方家具 JSON、manifest 與正式 importer 已與 Kai 最新資料一致，不需重複替換。

## 五、可不放入的資料

共用 Kai 最新 PostgreSQL 後，下列內容不影響網站執行，可不移植：

- 舊 9,350／10,550 catalog 與舊 schema。
- PostgreSQL validation report。
- 舊 CSV review／mapping report。
- 本機 `.runtime/` 與 SQLite 檔案。
- 模型 cache、Torch／Hugging Face 權重。
- 大型 GLB、圖片壓縮包。
- 測試報告、驗證報告與暫存輸出。

## 六、建議整合順序

```text
1. 更新正式 catalog SQL schema
2. 加入四個 catalog repository
3. 合併 project_store 與 PostgreSQL project store
4. 加入 catalog admin API
5. 加入 Django furniture RAG runtime 與 rag_api
6. 加入 engineering knowledge 與 engineering services
7. 加入 RAG／Engineering 正式前端頁面
8. 最後小範圍合併 main.py 與 scene.html
9. 各組員自行建立 .env 並連線 Kai 最新 PostgreSQL
```

禁止直接把 Kai 分支的 `backend/server/` 或 `backend/server/static/` 整個覆蓋到 Ben 分支。
