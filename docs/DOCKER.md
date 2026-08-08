# 容器化執行指南

正式 web app（`backend/server/` + `frontend/` 八步流程）的容器化。辨識、選件、
幾何合法性都在同一個行程內，所以只有一個 app 服務，不拆微服務。

## 快速開始

前置：`.env` 已存在且 `DB_PASSWORD` 已填（`Copy-Item .env.example .env`）。

```powershell
.\scripts\docker\roompilot.ps1 up
.\scripts\docker\roompilot.ps1 smoke
```

開 <http://127.0.0.1:8002>。

不想用包裝腳本就直接下 compose：

```powershell
docker compose up -d --build
```

停止與清除：

```powershell
.\scripts\docker\roompilot.ps1 down            # 保留 volume
.\scripts\docker\roompilot.ps1 down -Volumes   # ⚠ 連 volume 一起刪
```

## 兩種模式

| | 預設模式 | 自足模式（`-FullStack`）|
|---|---|---|
| 資料庫 | 本機那套 PostgreSQL 17.10（`host.docker.internal`）| 容器內 `pgvector/pgvector:pg17` |
| 資料 | 直接用現有的家具 8,557／向量 7,958／29 筆專案 | 空的，要先 `seed-db` 灌 |
| 可攜性 | 換機要另外裝 PostgreSQL 並重跑匯入 | 一個指令端起整套 |
| 風險 | 無（就是現在在用的那份資料）| **是第二份資料庫**，與本機不同步 |
| 指令 | `roompilot.ps1 up` | `roompilot.ps1 up -FullStack` |

自足模式第一次啟動：

```powershell
.\scripts\docker\roompilot.ps1 up -FullStack
.\scripts\docker\roompilot.ps1 seed-db -FullStack   # 從本機 5432 匯出再灌進容器
```

沒灌資料前 `/api/health` 回 503 是**正確行為**（型錄與專案表都是空的），
不是容器壞掉。

## 五個決策

| 決策 | 選擇 | 代價 |
|---|---|---|
| torch | CPU 版（官方 CPU index）| 省下約 2.5GB CUDA runtime；房型辨識 90.3% 準確度保住 |
| 家具 RAG | 權重烘進映像 | 映像大很多，換來容器內語意檢索真的能用、且完全離線 |
| PostgreSQL | 兩種模式並存 | 多一套設定要維護，換來零資料搬遷 + 可攜兩者都有 |
| `frontend/` 422M 圖片 | 唯讀掛載 | 映像小 422MB；部署時素材必須另外送達 |
| Node | 裝 binary + `npm ci` 裝 exceljs | 多約 90MB；換來第 9 步 XLSX 匯出在容器內真的會產出 |

## 映像組成

多階段建置，六個 stage：

| Stage | 做什麼 | 為什麼分開 |
|---|---|---|
| `builder` | 裝 Python 套件、修 opencv、建置期 assert | — |
| `hf-fetch` | 只裝 huggingface-hub，下載 4.5GB 權重 | 快取鍵最穩：改 requirements 不會害你重抓權重 |
| `models` | 驗證權重載得起來、預抓 DINOv2 | 需要 torch 與 sentence-transformers |
| `nodedeps` | `npm ci` 裝 exceljs | 不搬 Windows 上裝的 node_modules |
| `nodetest` | `npm ci` 裝 jsdom | 只給 test stage |
| `runtime` | 最終映像：非 root、tini、healthcheck | — |
| `test` | 加 tests/、testdata/、docs/、pytest | 這些不進正式映像 |

## 實測數字（2026-08-09，Docker Desktop 4.85.0 / 8GB VM）

| 項目 | 實測 |
|---|---|
| 映像實際佔用磁碟 | **10.5 GB**（`docker images` 顯示的 3.5GB 是壓縮後的，不是佔用量）|
| ├ BGE-M3 + reranker 權重 | 4.3 GB（各 2,166 MB）|
| ├ torch CPU + sentence-transformers 等套件 | 約 4 GB |
| ├ DINOv2 骨幹快取 | 89 MB |
| └ `backend/` + `frontend/` 程式與型錄資料 | 約 120 MB |
| 首次建置（含下載權重）| 約 25 分鐘 |
| 重建（只改程式碼）| 約 1 分鐘 |
| 容器啟動到 `/api/health` 回 200 | 數秒 |
| RAG 權重載入完成（背景）| **43.0 秒** |
| 穩定後記憶體 | 1.78 GB / 7.63 GB（reranker 首次檢索才載，會再上升）|
| `seed-db` 匯出檔 | 58.8 MB（來源 DB 470 MB）|
| 容器內全套 pytest | 約 15 分（1047 passed / 10 skipped / 1 既有紅燈）|

⚠ 上一版 `docs/DOCKER.md` 宣稱映像約 1.8GB、實測 2.64GB，兩個數字都對不上。
這次的 10.5 GB 是 `docker system df -v` 的 UNIQUE SIZE，會隨權重與套件版本變動，
改動 Dockerfile 後請重新量，不要沿用。

## 三份 requirements 的分工

| 檔案 | 用途 | 誰讀 |
|---|---|---|
| `requirements.txt` | 團隊 Windows 開發機 baseline | 人 |
| `requirements-container.txt` | 容器核心執行期 | Dockerfile `builder` |
| `requirements-container-rag.txt` | 容器的 RAG 相依 | Dockerfile `builder`（`WITH_RAG=1` 時）|

容器版與 baseline 的兩個差異：

1. **拿掉 `opencv-python`，只留 `opencv-python-headless`。** 前者在 slim 容器缺
   `libGL.so.1` 與 `libxcb.so.1`，`import cv2` 會直接崩。headless 提供同一個
   `cv2` 模組。
2. **拿掉 `selenium` / `webdriver-manager` / `tqdm` / `beautifulsoup4` /
   `requests`。** 這些是 Kai 的型錄爬蟲與 AWS metadata 工具，`backend/` 沒有
   任何 import（2026-08-09 重新全域 grep 確認），selenium 還會在執行期找 chrome。

**改任一份的版本 pin 時，三份都要一起看。**

## 會咬人的地方（都已在設定裡處理，但改動時要知道）

### 1. `.env` 會蓋掉映像的 ENV

`env_file` 讀進來的值優先序高於 Dockerfile 的 `ENV`。所以 `.env` 裡任何一個
Windows 路徑（例如 `ROOMPILOT_ARTIFACT_TOOL_MODULES=C:\Users\...`）都會蓋掉
映像裡設好的 Linux 路徑，**而且不會報錯**，只在用到時安靜失效。

`docker-compose.yml` 的 `environment:` 區塊就是為此存在：凡是「容器內必須
不一樣」的變數一律在那裡顯式覆寫。加新變數時記得同步。

### 2. 第 9 步工程文件的路徑寫死了

`backend/server/engineering/api.py:77`：

```python
generated_dir = project_dir / ".runtime" / "engineering"
```

它**不吃** `ROOMPILOT_RUNTIME_DIR`。所以容器的 runtime volume 掛在
`/app/.runtime`（不是 `/data/runtime`），讓兩條路徑指向同一個地方。
掛錯的話——網站起得來、健康檢查是綠的、第 9 步下載 404，因為
`api.py:391` 會檢查檔案是否落在 `generated_dir` 底下。

這是繞法不是修法。正解是讓它也走 `runtime_paths.project_runtime_dir()`，
但那是 Bella 的程式碼，且會改變本機既有 219 個 package 的路徑，
不在容器化的範圍內。

### 3. 專案保存 provider 的程式預設是 SQLite

`backend/server/project_store.py:655` 的預設值是 `sqlite`。不在 compose 明寫
`ROOMPILOT_PROJECT_STORE_PROVIDER=postgres`，容器會安靜地把專案寫進 volume
裡的 SQLite——網站完全正常，資料卻存錯地方。三個 provider 都明寫。

### 4. RAG 快取路徑差一層

`ROOMPILOT_RAG_MODEL_CACHE` 被 `model_runtime.py:113` 直接當
`SentenceTransformer(cache_folder=...)` 用，也就是「**直接**含
`models--BAAI--bge-m3` 的那一層」。而 `HF_HOME=/x` 的語意是快取在 `/x/hub`。

兩者差一層。更糟的是 `model_runtime.py:23` 的 `_repo_is_cached` 同時接受
`<cache>/models--*` 與 `<cache>/hub/models--*` 兩種佈局——所以設錯時
**狀態端點會說「已快取」，實際載入卻失敗**。

映像用 `HF_HUB_CACHE`（語意上就是 hub 目錄本身），不用 `HF_HOME`。

### 5. opencv 會被 rapidocr 偷換成 5.x

`rapidocr-onnxruntime` 1.4.4 的 metadata 依賴未鎖版本的 `opencv-python`，
pip 會裝進 5.0.0.93 並蓋掉 headless 的 `cv2/`。後果有兩層：

1. GUI build 連結 `libGL`/`libxcb`，slim 映像沒有，容器啟動即 `ImportError`；
2. **就算補上那些 X 函式庫讓它開得起來，跑的也是 OpenCV 5.0**——
   `requirements.txt:22` 已寫明 5.0 改了 `HoughLinesP` 回傳 shape，
   門偵測會當場失效。第 2 層不會報錯，比第 1 層危險。

Dockerfile 的處置是三步：裝完後拔掉 GUI build、強制還原 headless、
加一道建置期 assert 擋主版本 >=5。**改 rapidocr 版本時要重驗這條依賴鏈。**

### 6. 改了程式為什麼沒生效

`backend/` 與 `frontend/` 都是 `COPY` 進映像的，不是掛載。改 repo 檔案後
瀏覽器怎麼硬刷新都不會變。要：

```powershell
.\scripts\docker\roompilot.ps1 up      # 會帶 --build
```

layer 快取下約 1 分鐘。專案資料在資料庫與 volume，重建不掉資料。

另：改任何 `frontend/*.js` 要同步更新 import 端的 `?v=sha256-` cache key
（`scene_v2.js` → 依賴、`scene.html` → `scene_v2.js`），有
`test_changed_scene_module_cache_keys_match_dependency_content` 擋。

### 7. 容器資料庫的排序規則與 pgvector 版本都與本機不同

本機 `roompilot_db` 的 collation 是 `Chinese (Traditional)_Taiwan.950`——
Windows 專有的 locale 名稱，Linux 容器建不出來。所以 `seed-db` 的匯出
刻意不帶 `--create`，讓容器用映像預設的 `en_US.utf8` 建庫。

實務影響只有一項：純中文字串的 `ORDER BY` 排序結果會與本機不同。
已確認 `roompilot` 與 `staging` 兩個 schema 沒有任何欄位寫死 `COLLATE`
（查 `pg_attribute.attcollation`，0 筆），資料、索引與 pgvector 相似度
查詢都不受影響。

2026-08-09 實測的容器 DB 實況：

| | 本機 | 容器（`pgvector/pgvector:pg17`）|
|---|---|---|
| PostgreSQL | 17.10（Windows）| 17.10（Debian）|
| collation | `Chinese (Traditional)_Taiwan.950` | `en_US.utf8` |
| pgvector | 0.8.2（自行編譯）| **0.8.6** |

pgvector 兩個版本的差異未逐條比對；實測 7,958 筆 1024 維向量匯入與
`<=>` 查詢都正常。

## 容器與本機的行為差異

### 必須掛 volume 的執行資料

`/app/.runtime` 是唯一需要寫入的位置。裡面有：

- `auth_secret.key` — 重生等於所有已簽發的 access/refresh token 立即失效。
  想避免這件事，在 `.env` 明確設 `ROOMPILOT_AUTH_SECRET`。
- `uploads/`、`renders/` — **即使專案存在 PostgreSQL，平面圖與生成的成果圖
  仍然落在檔案系統。** 沒有 volume 就是重啟即失圖。
- `indexes/`、`doc-report/`、`engineering/`
- `projects.sqlite3` — 只有離線模式才會用到

把本機既有的搬進去：

```powershell
.\scripts\docker\roompilot.ps1 seed-runtime
```

### 沒掛 `testdata/` 時

`main.py` 的 `PLAN_DIR`、`SAMPLE_GLB_DIR` 都有 `is_dir()` 守衛，缺目錄時
sample 清單回空陣列，正式八步流程不受影響。需要範例平面圖時打開
`docker-compose.yml` 裡註解掉的那行掛載。

### 未納入的東西

- **PaddleOCR**（`requirements-ocr.txt`）：體積大且平台相依，且首次執行會
  嘗試下載模型到家目錄。缺它時印刷房名／尺寸 OCR 安靜停用、比例尺回到手拉。
- **家具型錄爬蟲**（selenium 那一組）：執行期會找 chrome，容器不需要。

## 資源需求

| 項目 | 需求 | 為什麼 |
|---|---|---|
| 記憶體 | 8GB 配額（實測用到 1.78GB）| 只載 BGE-M3 時 1.78GB；reranker 在第一次檢索才載入，還會再上升。契約文件寫「約 4.6GB 常駐」是兩個模型都載滿的情況 |
| 磁碟 | 25GB | 映像 10.5GB，加上 build cache 與 volume |
| CPU | 不限 | `OMP_NUM_THREADS` 預設限 4，避免 torch 與 uvicorn 搶 |

記憶體不足時的表現**不是明顯錯誤**：預載會 `failed`，第 6 步檢索安靜退成
純結構化過濾。用 `roompilot.ps1 smoke` 看 `/api/rag/embedding-status` 的
`status` 欄位確認。

`uvicorn` 只能開 1 個 worker：每個 worker 各載一份 4.5GB 模型，且 RAG 的
job 狀態是行程內的，多 worker 會讓輪詢查不到自己的工作。

## 在容器內跑測試

```powershell
.\scripts\docker\roompilot.ps1 test
```

`test` stage 在 runtime 之上加了 `tests/`、`scripts/`、`testdata/`、`docs/`、
`tools/`、`.env.example` 與 jsdom，這些都不在正式映像裡。

2026-08-09 基準線：**1047 passed / 10 skipped / 1 failed**，耗時約 15 分。

唯一的紅燈是
`tests/test_scene_pbr_realism.py::test_orthographic_dollhouse_avoids_gtao_projection_artifacts`
——**本機執行同樣是紅的**（同日以 `.venv` 實測比對確認），與容器無關，
屬 `chore/docker-containerization` 分出來之前就存在的問題。

容器測試若出現「素材不存在」類的失敗，先確認 `roompilot.ps1 test` 的四個唯讀
掛載都在：`JSON/`、`frontend/surface_assets`、`frontend/style_cards`、
`frontend/style_images`。這些走掛載不進映像，少掛任何一個，紅的會是資產缺失
而不是邏輯錯誤。

`AGENTS.md` 的最終整合指令有三條，容器只承擔第一條：

```powershell
.\.venv\Scripts\python.exe -m pytest -q   # ← 容器可以跑
git diff --check                          # ← 映像內沒有 .git，留在宿主
git status --short                        # ← 同上
```

## 建置精簡映像（不含 RAG）

CI 或只跑八步流程時：

```powershell
.\scripts\docker\roompilot.ps1 build -NoRag
```

等同 `--build-arg WITH_RAG=0`。少了 sentence-transformers 與 4.5GB 權重。
此時容器內 `/api/rag/*` 會回 `RagDependencyError`，第 6 步候選集退成純結構化
過濾——服務不中斷，但語意排序是死的。

## 從零建一個容器資料庫（不從本機匯出）

`seed-db` 走的是 `pg_dump` → `pg_restore`，前提是本機那套還在。若要真正
從零建（例如全新機器、沒有本機 PostgreSQL），流程是：

1. `docker compose -f docker-compose.yml -f docker-compose.full-stack.yml up -d db`
2. 依序套用 DDL：
   `scripts/sql/roompilot_postgresql_schema.sql` →
   `scripts/sql/roompilot_furniture_embeddings_schema.sql` →
   `scripts/project_store/roompilot_project_store_schema.sql`
3. 依序跑匯入：`scripts/sql/import_official_catalog_to_postgres.py` →
   `import_furniture_embeddings_to_postgres.py` →
   `scripts/runtime_catalog/` → `import_lighting_assets_to_postgres.py`

⚠ 第 2 步的向量匯入需要 `JSON/RAG/furniture_embeddings_bge_m3.jsonl`，
那是 **git-lfs 檔（91MB）**。沒跑過 `git lfs pull` 的 clone 拿到的是
132 bytes 的指標檔，匯入會在驗證階段失敗。

這條路徑尚未在容器內端到端實跑驗證過（`seed-db` 那條有）。

## 未在容器化範圍內的既有問題

- **連線池**：`.env.example` 的 `DB_POOL_MAX=24`，單一 app 行程最多
  2×24＝48 條。容器內 PostgreSQL 預設 `max_connections=100`，單副本安全，
  兩副本就會逼近上限。
- **多副本不可行**：`uploads/`、`renders/` 綁本機檔案系統，SQLite WAL 是
  單寫者。兩個模式都維持單一實例。
- **第 9 步工程文件的絕對路徑存進資料庫**（`documents.py:139-145`）。
  在本機產生的舊 package，其路徑是 `C:\...\.runtime\engineering\...`，
  到容器裡下載會被 `api.py:391` 的路徑檢查擋下。新產生的不受影響。
