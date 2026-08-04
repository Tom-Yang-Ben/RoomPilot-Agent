# 架構決策紀錄（ADR）— RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 03_architecture/adr.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

本文件分三部分：

1. **空白模板**：新增 ADR 時複製使用，章節結構不可刪減（v5.0 模板原文）。
2. **既有 ADR 承接（ADR-001～005）**：舊導入版（`docs/vibecoding/04_architecture_decision_record_template.md`，2026-07-26 對舊分支撰寫）的 5 則決策，逐則對現行工作樹再查證，只記「決策要旨＋現況差異」，過期數字一律以本次實查為準。
3. **新 ADR（ADR-006～010）**：2026-07-26 之後成立、舊導入版完全沒有的決策，涵蓋 APIRouter 分檔、PostgreSQL 五階段、家具 RAG runtime、工程文件 MVP 與專案原生 skills。

範例中的「決策者」欄依 commit 作者與 `docs/TEAM_AI_OWNERSHIP.md` 歸屬填寫；實際口頭決策過程未必留痕，標註「(未查證)」處待團隊補認。`docs/TEAM_AI_OWNERSHIP.md:3` 明示 Git author 不能單獨視為 owner。

## ADR 索引

| 編號 | 標題 | 狀態 | 日期 | 主要依據 |
| :--- | :--- | :--- | :--- | :--- |
| ADR-001 | 統一 `backend/` 單層套件與一人一目錄 | 已接受（部分後果由 ADR-006 解除） | 2026-07-24 | commit `b04833c`、`README.md` |
| ADR-002 | 對外資料契約全面採用公分（cm） | 已接受 | 2026-07-23~24 | commits `d97f95c`→`714722f`、`backend/engine/schema.py` |
| ADR-003 | GLB 模型改由 CloudFront 供應（預設 `cloudfront`） | 已接受 | 2026-07-23 | commit `3260497`、`backend/server/services/cloud_models.py` |
| ADR-004 | 官方雲端家具型錄 9,350 件為唯一母集合 | **已取代**（由 ADR-007 的 8,557 件 official JSON v3 取代） | 2026-07-26 | commit `83b3c8a`、現行 `cloud_catalog.py:15` |
| ADR-005 | 型錄匯入硬化：狀態白名單＋非破壞性預設 | 已接受 | 2026-07-26 | commit `e48cd67`、`cloud_catalog.py:16-23` |
| ADR-006 | 新子系統以 APIRouter 分檔掛載，不再擴張單檔 main.py | 已接受 | 2026-07-31 | commit `e1e22ddf`、`main.py:216-223` |
| ADR-007 | 型錄與專案保存以 PostgreSQL 五階段遷移為事實來源 | 已接受 | 2026-07-31 | `docs/contracts/POSTGRESQL_*.md`、`postgres_repository.py:199` |
| ADR-008 | 家具 RAG runtime 落在 `backend/spatial_data/rag/`，預設停用 | 已接受 | 2026-07-31 | `rag/settings.py:65`、`rag_api.py` |
| ADR-009 | 工程文件 MVP：snapshot→lock→packages→jobs→documents | 已接受 | 2026-07-31 | `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`、`engineering/api.py` |
| ADR-010 | 專案原生 Claude skills 進版控（`.claude/skills/` 白名單） | 已接受 | 2026-08-04 | commit `3b2438dd`、`.gitignore:43-46` |

---

# 第一部分：ADR 空白模板

# ADR-XXX: [簡短的決策標題]

> **狀態:** 提議中/已接受/已取代/已棄用 | **日期:** YYYY-MM-DD | **決策者:** [人員/團隊]

---

## 1. 背景與問題

- **上下文**: [需要做出此決策的背景]
- **問題**: [具體問題，盡量量化嚴重性]
- **驅動因素/約束**:
  - [驅動 1]
  - [約束 1]

## 2. 考量的選項

### 選項一: [名稱]
- **描述**: [實現方式]
- **優點**: [列舉]
- **缺點**: [列舉]
- **成本/複雜度**: 高/中/低

### 選項二: [名稱]
- **描述**: [實現方式]
- **優點**: [列舉]
- **缺點**: [列舉]
- **成本/複雜度**: 高/中/低

## 3. 決策

**選擇**: [明確指出選項]

**理由**: [為何此選項最符合需求，與其他選項的權衡比較]

## 4. 後果

- **正面**: [預期收益，盡量可衡量]
- **負面**: [引入的風險或技術債]
- **影響範圍**: [對其他元件/團隊的影響]
- **重新評估觸發**: [何時需重新審視此決策]

## 5. 執行計畫 (選填)

1. [步驟 1]
2. [步驟 2]

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| YYYY-MM-DD | [姓名] | [意見] |

---

# 第二部分：既有 ADR 承接與 2026-08-04 現況再查證（ADR-001～005）

以下每則只記決策要旨與現況差異；完整原文見舊導入版 `docs/vibecoding/04_architecture_decision_record_template.md`（其中「44 條路由」「9,350 件」等數字已過期，不可再引用）。

## ADR-001：統一 `backend/` 單層套件與一人一目錄

- **決策要旨**：commit `b04833c`（2026-07-24）將 `roompilot/` 全套件 rename 為 `backend/`，README 明定一人唯一主要目錄。
- **2026-08-04 再查證**：
  - 目錄責任表現在權威來源是 `docs/TEAM_AI_OWNERSHIP.md:19-34`（共 14 個路徑列）：`backend/server/`＝Bella、`backend/floorplan/`＝Cody、`backend/spatial_data/`＝Django、`backend/catalog/`＝Kai、`backend/agent/`＝Yen、`backend/engine/`＝Ancai、`docs/contracts/`＝Bella 整合。
  - 啟動指令仍為 `uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload`（`README.md:30,46`；`README.md:35` 註明 8002 被占用時改 8023）。
  - 舊 ADR 負面後果「路由全集中在 main.py、無 APIRouter」**已解除**：現行 `main.py` 3,695 行、46 條路由，另有 3 個 router 檔共 17 條（見 ADR-006），全站 63 條。
  - 舊 ADR 負面後果「`backend/spatial_data/` 僅有 `.gitkeep`」**已解除**：現有 rag/ 子套件 11 個 .py 共 1,234 行，連同 `spatial_data/__init__.py` 全套件 12 檔 1,236 行（見 ADR-008）。
  - 六個領域模組 Python 行數合計 15,815：floorplan 9,313＋catalog 3,199＋spatial_data 1,236＋agent 1,045＋engine 717＋upgrade3d 305（各以 `wc -l` 排除 `__pycache__` 實測）。
- **狀態**：已接受；「main.py 持續成長需拆 APIRouter」的重新評估觸發已由 ADR-006 兌現。

## ADR-002：對外資料契約全面採用公分（cm）

- **決策要旨**：引擎、API、前端契約一律公分；DXF 與視覺管線內部維持公尺，各設唯一轉換點（commit 鏈 `d97f95c`→`1baf027`→`b7df307`→`714722f`，2026-07-23）。
- **2026-08-04 再查證**：
  - `backend/engine/schema.py` docstring 第 9 行仍明文「單位契約:所有長度/座標一律公分(cm)」。
  - 根目錄 `AGENTS.md:50` 將其列為不可違反契約：「跨模組幾何用公分、新欄位 `_cm`/`_m2`」。
  - 專案 `CLAUDE.md` 明定「未更新兩端測試就改動公分制 payload」為禁止事項。
- **狀態**：已接受，仍為現行契約。

## ADR-003：GLB 模型改由 CloudFront 供應（預設 `cloudfront` 模式）

- **決策要旨**：模型交付與 repo 解耦，只信任 manifest 驗證過的 URL；commit `3260497`（2026-07-23）引入 `services/cloud_models.py`。
- **2026-08-04 再查證**：
  - `ROOMPILOT_MODEL_DELIVERY_MODE` 預設仍為 `"cloudfront"`（`backend/server/services/cloud_models.py:47`），合法值仍僅 local/cloudfront（同檔 :34）。
  - CloudFront base 預設仍為 `https://ddgsm1yg3xikc.cloudfront.net`（同檔 :32）。
  - 模型端點行號已位移：`GET /api/furniture/{furniture_id}/model` 現在 `main.py:3508`，`/model.gltf`:3517、`/buffer.bin`:3526、`/images/{image_index}`:3536。
  - 交付契約仍為 `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`（owner：Kai）。
- **狀態**：已接受。

## ADR-004：官方雲端家具型錄 9,350 件為唯一母集合

- **決策要旨**：commit `83b3c8a`（2026-07-26）以 cloud catalog JSON＋manifest CSV 定義 9,350 件母集合，載入期硬驗證。
- **2026-08-04 再查證（已取代）**：
  - 現行 `backend/catalog/cloud_catalog.py:15` 為 `OFFICIAL_CATALOG_COUNT = 8_557`，docstring 第 1 行明言「Build the official 8,557-item catalog from Kai's versioned JSON source」；件數不符仍 raise（同檔 :96-98）、ID 必須齊全且唯一（:103）。
  - schema_version 為 `official-json-8557-v3`（同檔 :221）；`docs/TEAM_AI_OWNERSHIP.md:57` 同步記載 Kai 官方 JSON catalog 目前 8,557 筆。
  - 舊 9,350 件資料檔 `backend/catalog/data/furniture_catalog_cloud_9350.json`（count=9350）仍在 repo，但已非母集合定義來源（`docs/owners/KAI.md:19` 定位為 PostgreSQL 不可用時的唯讀 fallback）；母集合來源檔改為 `JSON/furniture/furniture_official_catagory.json`（count=8557，`main.py:137-139`），兩檔不是同一份資料的前後版本，換檔原因與差異清單（未查證）。
  - 「載入期硬驗證、每件必有已驗證 GLB」的設計原則由後繼實作沿用。
- **狀態**：**已取代**——母集合定義移至 8,557 件 official JSON v3，並由 ADR-007 的 PostgreSQL 五階段接手事實來源。

## ADR-005：型錄匯入硬化：狀態白名單＋非破壞性預設

- **決策要旨**：commit `e48cd67`（2026-07-26）加入 `READY_UPLOAD_STATUSES` 白名單、匯入器預設非破壞（`--prune-extra` 才清除）、刪除重複 manifest。
- **2026-08-04 再查證**：
  - `READY_UPLOAD_STATUSES = {uploaded, already_exists, complete, completed, success, skipped_existing}` 仍在 `cloud_catalog.py:16-23`。
  - 匯入工具現分三組：`scripts/sql/`（Phase 1/2/5：schema、official catalog 與 embeddings 匯入）、`scripts/project_store/`（Phase 3）、`scripts/runtime_catalog/`（Phase 4）——見 ADR-007。
  - manifest 目錄現況：`backend/catalog/data/manifests/` 有 glb_upload_manifest.csv、glb_upload_all_result.csv、image_upload_manifest.csv、image_upload_all_result.csv 四檔（`ls` 實查；e48cd67 當時刪除的重複檔名 `glb_upload_manifest.csv` 已以新內容回歸，與當時刪除版本的關係未查證）。
- **狀態**：已接受。

---

# 第三部分：新 ADR（ADR-006～010）

以下 5 則為回溯撰寫的既成決策紀錄，2026-08-04 於分支 django-skill @ a2179f7e 以 git/grep/讀檔查證；「考量的選項」段中未被採納的選項是依 commit 前後狀態回推，未必是當時實際討論過的方案。

---

# ADR-006: 新子系統以 APIRouter 分檔掛載，不再擴張單檔 main.py

> **狀態:** 已接受 | **日期:** 2026-07-31 | **決策者:** Bella（`backend/server/` owner）＋各子系統 owner（Kai/Django）；整合 commit `e1e22ddf` 的 git author 為 Ben，依 `docs/TEAM_AI_OWNERSHIP.md:3` 不單獨視為 owner；討論過程(未查證)

---

## 1. 背景與問題

- **上下文**: ADR-001 時代所有路由集中在單檔 `main.py`（舊導入版記錄為 44 條、2,796 行，該數字屬 2026-07-26 舊分支）。2026-07 下旬同時要接入三個新子系統：型錄管理 CRUD、家具 RAG、工程文件 MVP。
- **問題**: 若三個子系統都寫進 main.py，單檔將逼近 5,000 行以上，且三個子系統分屬不同 owner（Kai/Django/Bella），單檔會讓跨 owner 修改的衝突面最大化。
- **驅動因素/約束**:
  - `docs/TEAM_AI_OWNERSHIP.md` 的一人一目錄責任制：路由檔應可對應到 owner。
  - 專案 `CLAUDE.md` 禁止「新建第二套 FastAPI」——只能在同一個 app 內分層，不能另起服務。

## 2. 考量的選項

### 選項一: 繼續寫進 main.py
- **描述**: 新端點全部追加在單檔。
- **優點**: 無結構變更。
- **缺點**: 單檔膨脹、owner 邊界消失、合併衝突集中。
- **成本/複雜度**: 低（短期）/高（長期）

### 選項二: 每個新子系統一個 APIRouter 檔，main.py 只負責 include
- **描述**: 見決策段。
- **優點**: 路由檔與 owner 目錄對齊；工程 router 可注入依賴（project store、project dir）便於測試。
- **缺點**: main.py 既有 46 條路由未回頭遷移，形成新舊並存。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二，由 commit `e1e22ddf`（2026-07-31「feat: 整合 Kai 的 PostgreSQL、家具 RAG 與工程報告功能」，125 檔、+28,110/−7,238，`git show --stat` 實測）引入三個 router，main.py 掛載於 :216-223：

- `app.include_router(catalog_admin_router)`（`catalog_admin.py`，316 行，prefix=`/api/admin/furniture`，catalog_admin.py:29；4 條路由：POST :234、GET :252、PATCH :274、DELETE :294）。
- `app.include_router(rag_router)`（`rag_api.py`，197 行，無 prefix，rag_api.py:26；5 條路由，見 ADR-008）。
- `app.include_router(build_engineering_router(project_store_getter=..., project_dir=PROJECT_DIR))`（`engineering/api.py`，361 行，prefix=`/api/v1`，api.py:50；8 條路由，見 ADR-009）。

**現行全站路由 63 條**＝main.py 46＋rag_api.py 5＋catalog_admin.py 4＋engineering/api.py 8（`grep -rn -E '@(app|router)\.(get|post|put|delete|patch|head|options|websocket)\(' backend/server/ --include='*.py'` 逐條核對；無 websocket/head/options）。另有 2 個 StaticFiles 掛載（`/static`、`/docs-assets`，main.py:285-286）。

**理由**: 一個 FastAPI app、多個 owner 對齊的 router，是「不建第二套 FastAPI」約束下唯一能維持責任邊界的切法；工程 router 以工廠函式注入依賴，`router.engineering_repository` 供測試共用同一持久層。

## 4. 後果

- **正面**: 新子系統路由檔各自對應 owner；跨子系統例外處理集中在 app 層（`ProjectStoreUnavailable`→503、`RuntimeCatalogUnavailable`→503 且區分 busy/未匯入，main.py:226-266，busy 時附 `Retry-After: 2`）。
- **負面**: main.py 仍有 46 條路由、3,695 行未拆；新舊兩種掛載風格並存，新讀者需知道「有路由的檔只有 4 個」（全目錄 grep 證明，其餘 service 檔如 intake_service.py、scene_service.py、render_service.py、render_providers.py、cost_estimation.py、questionnaire_visuals.py、style_cards.py 均無路由）。
- **影響範圍**: `backend/server/` 全部；前端 engineering.js/rag.js 依 router prefix 呼叫。
- **重新評估觸發**: main.py 既有 46 條路由是否回頭拆分為 router 時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-04 | 本次導入（回溯撰寫） | 路由數、行號、commit stat 皆於 a2179f7e 實測 |

---

# ADR-007: 型錄與專案保存以 PostgreSQL 五階段遷移為事實來源

> **狀態:** 已接受 | **日期:** 2026-07-31（Phase 契約陸續成立，整合入主線於 commit `e1e22ddf`） | **決策者:** Kai（Phase 1/2/4/5 owner）＋Bella（Phase 3 owner）；分工依 docs/contracts/ 各契約 owner 欄，拍板過程(未查證)

---

## 1. 背景與問題

- **上下文**: ADR-004/005 時代 PostgreSQL 只是匯入工具，執行期一律從 JSON+CSV 載入記憶體。型錄成長到 8,557 件正式家具＋表面材質/色卡/價格等多份 runtime JSON，每次請求或啟動都全量掃 JSON。
- **問題**: FastAPI 為了 filter/count/facet/paginate 而載入完整型錄，記憶體與延遲成本高；專案保存用 SQLite 單機檔案，無法多人共用；型錄維護（新增/下架）沒有交易與稽核。
- **驅動因素/約束**:
  - 專案 `CLAUDE.md`：第 6 步家具資料以 Kai PostgreSQL view `roompilot.furniture_catalog_current` 優先，只有資料庫暫時不可用才使用已驗證 JSON。
  - 根目錄 `AGENTS.md:56` 將此列為不可違反契約。
  - 版本化 JSON 仍是 import/review 來源，不因上 DB 而消失。

## 2. 考量的選項

### 選項一: 維持 JSON 載入記憶體
- **描述**: 不動，DB 僅作備份。
- **優點**: 零遷移成本、離線可用。
- **缺點**: 全量載入的記憶體/延遲成本隨型錄成長；無交易式管理；專案資料仍鎖單機。
- **成本/複雜度**: 低

### 選項二: 一次全面切換 PostgreSQL
- **描述**: 移除 JSON 路徑，執行期只讀 DB。
- **優點**: 單一事實來源最乾淨。
- **缺點**: DB 不可用即全站停擺；六人團隊各機器須同時就緒；無法漸進驗證。
- **成本/複雜度**: 高

### 選項三: 五階段契約化遷移，每階段各有環境變數開關與 dry-run
- **描述**: 見決策段。
- **優點**: 每階段獨立可驗證；JSON 保留為 import/review 來源與明確 fallback。
- **缺點**: 過渡期兩套來源並存，需明確禁止靜默回退。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項三。五階段契約（`ls docs/contracts/` 實查）與對應實作：

| Phase | 契約 | 實作 | 工具 |
| :--- | :--- | :--- | :--- |
| 1 Read | POSTGRESQL_CATALOG_READ_PHASE1.md（owner: Kai） | `backend/catalog/postgres_repository.py`（891 行） | `scripts/sql/` |
| 2 CRUD | POSTGRESQL_CATALOG_CRUD_PHASE2.md（owner: Kai） | `backend/catalog/postgres_admin_repository.py`（764 行）＋`backend/server/catalog_admin.py` | `scripts/sql/` |
| 3 專案保存 | POSTGRESQL_PROJECT_STORE_PHASE3.md（owner: Bella） | `backend/server/postgres_project_store.py`＋`project_store.py` | `scripts/project_store/` |
| 4 Runtime catalog | POSTGRESQL_RUNTIME_CATALOG_PHASE4.md（Kai↔Bella） | `backend/catalog/runtime_catalog_repository.py`（431 行） | `scripts/runtime_catalog/` |
| 5 單一事實來源 | POSTGRESQL_SINGLE_SOURCE_PHASE5.md（owner: Kai） | 上述整體收斂 | `scripts/sql/` |

另有兩份向量side契約：POSTGRESQL_FURNITURE_EMBEDDINGS.md 與 POSTGRESQL_FURNITURE_RAG_RUNTIME.md（見 ADR-008）。

關鍵預設值（實測）：

- 型錄讀取預設 **postgres**：`ROOMPILOT_CATALOG_PROVIDER` 預設 `"postgres"`（`postgres_repository.py:199`）；`postgres_repository.py:1-5` 明文「FastAPI 不得為了 filter/count/facet/paginate 而載入完整型錄」。
- 讀取端實際查詢的是 view `roompilot.furniture_catalog_api_current`（`postgres_repository.py:18`），它疊在 `CLAUDE.md` 所述的 `roompilot.furniture_catalog_current` 之上——兩層 view 均由契約定義（POSTGRESQL_CATALOG_READ_PHASE1.md:57-58：前者管 API taxonomy 與安全預設，後者是正規化表與資產的目前版聚合；DDL 見 `scripts/sql/roompilot_postgresql_schema.sql:386,475`）。
- Runtime catalog（styles/surfaces/costs/quarantine）預設 **strict postgres**：`ROOMPILOT_RUNTIME_CATALOG_PROVIDER` 預設 strict，明確設 `json/local/fallback` 才走 JSON（`runtime_catalog_repository.py:49-60`）；strict 模式不靜默回退掃 JSON（同檔 docstring）。
- 專案保存預設 **sqlite**：`ROOMPILOT_PROJECT_STORE_PROVIDER` 預設 `"sqlite"`，設 `postgres/postgresql/sql/database` 才切 DB（`project_store.py:604-607`）——Phase 3 為 opt-in，與 Phase 1/4 的預設方向不同。
- 管理寫入走交易＋參照驗證＋activation gate＋樂觀併發＋audit record，公開型錄維持唯讀（`postgres_admin_repository.py:1-6`）。
- 不可用時不猜測：`RuntimeCatalogUnavailable` 分 `catalog_pool_busy`（瞬時滿載，附 Retry-After）與 `runtime_catalog_unavailable`（未匯入，導向匯入流程）兩種 503（main.py:246-266）。

**理由**: 「JSON 是 import/review 來源、PostgreSQL 是執行期事實來源」把資料維護與服務讀取解耦；分階段各設開關讓六人團隊能在不同就緒度下工作。

## 4. 後果

- **正面**: 型錄查詢下推 DB（filter/count/facet/paginate）；型錄維護有交易與稽核；`GET /api/catalog/status`（main.py:2528）與 `GET /api/health`（main.py:2533，欄位 :2550）回報 `source_of_truth: postgresql|versioned_files`（值產生於 `catalog_status()`，main.py:2494）可觀測。
- **負面**: 執行期新增 PostgreSQL 依賴（psycopg2-binary==2.9.12、SQLAlchemy==2.0.51，requirements.txt Kai 組）；DB 未就緒時型錄相關端點回 503；`roompilot.furniture_catalog_current` view 的實際列數本次未連線查證(未查證)。
- **影響範圍**: `backend/catalog/`、`backend/server/`（main.py 型錄路徑、catalog_admin、cost_estimation.py 與 style_cards.py 均改讀 runtime catalog）、部署環境變數、`tests/` 的 postgres/catalog 系列 12 支（`ls tests/ | grep -iE 'postgres|catalog'` 實測）。
- **重新評估觸發**: Phase 3 預設是否翻轉為 postgres；Phase 5 收斂後 JSON fallback 是否退場。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-04 | 本次導入（回溯撰寫） | 預設值行號、契約清單、503 分類皆實測；DB 內實際資料未連線查證 |

---

# ADR-008: 家具 RAG runtime 落在 `backend/spatial_data/rag/`，經 rag_api 掛載且預設停用

> **狀態:** 已接受 | **日期:** 2026-07-31（commit `e1e22ddf` 入主線；契約 POSTGRESQL_FURNITURE_RAG_RUNTIME.md 記更新 2026-07-29） | **決策者:** Django（RAG owner）＋Kai（pgvector adapter）＋Bella（伺服器掛載）；分工依契約 owner 欄，拍板過程(未查證)

---

## 1. 背景與問題

- **上下文**: 屋主用口語描述需求，家具型錄需要語意檢索（RAG 向量索引為獨立管線的 9,349 筆，`POSTGRESQL_FURNITURE_RAG_RUNTIME.md:55,96`；與 ADR-004 的 8,557 件官方 JSON 型錄不是同一個集合）；`docs/TEAM_AI_OWNERSHIP.md:53` 同時限定「Graph RAG 只補強關係與證據，Ancai 仍是幾何與規則的唯一裁決者」，專案 `CLAUDE.md` 禁止把幾何決策移到 Graph RAG/瀏覽器/LLM。
- **問題**: 語意檢索要 LLM 解析查詢＋向量檢索＋重排，依賴外部 API key、離線模型快取與 pgvector 表——不能讓未配置的機器啟動失敗，也不能讓長查詢卡死同步請求。
- **驅動因素/約束**:
  - RAG 標註與空間資料同屬 Django 的責任（`docs/TEAM_AI_OWNERSHIP.md:11` 記「空間資料與 RAG 標註」，`:24` 記 `backend/spatial_data/` 目錄 owner）。
  - pgvector adapter 屬 Kai 的 catalog 目錄（`backend/catalog/rag_repository.py:1` 自述「Kai-owned PostgreSQL adapter for Django's furniture RAG runtime」）。

## 2. 考量的選項

### 選項一: RAG 邏輯直接寫進 backend/server/
- **描述**: 檢索、重排、LLM 解析都放伺服器層。
- **優點**: 檔案少。
- **缺點**: 違反一人一目錄；Django 的領域邏輯混進 Bella 的伺服器目錄。
- **成本/複雜度**: 低

### 選項二: 領域套件在 spatial_data/rag/，伺服器只留薄 router，功能預設關閉
- **描述**: 見決策段。
- **優點**: owner 邊界乾淨；未配置機器不受影響；錯誤型別化。
- **缺點**: 跨三個 owner 目錄（spatial_data/catalog/server），修改需跨資料夾記錄。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二。架構（全部實測）：

- **領域套件** `backend/spatial_data/rag/`：11 個 .py 共 1,234 行（`backend/spatial_data/` 全套件含 `__init__.py` 為 12 檔 1,236 行）。service.py 496 行自述「End-to-end LLM parser -> PostgreSQL pgvector -> Django reranker service」（service.py:1）；parser.py 分派 openai_parser.py/anthropic_parser.py 兩家 Structured Outputs adapter；model_runtime.py 為 thread-safe lazy **offline-only** BGE-M3 runtime；ranking.py 重排；vocab.py 版本化受控詞彙；errors.py 型別化失敗（RagError/RagDisabledError 等）。受控詞彙資料 `rag/data/taxonomy.json`（styles=6、moods=24、patterns=4）與 `rag/data/category_groups.json`（groups=19、room_default_sets=6）。
- **向量層**：`backend/catalog/rag_repository.py`（164 行，`EMBEDDING_MODEL = "BAAI/bge-m3"`，rag_repository.py:12）；契約 POSTGRESQL_FURNITURE_EMBEDDINGS.md、POSTGRESQL_FURNITURE_RAG_RUNTIME.md。
- **HTTP 層** `backend/server/rag_api.py`（197 行，APIRouter 無 prefix）：GET /rag（測試台頁，no-store，:136-138）、GET /api/rag/status（:141）、POST /api/rag/search（:146）、POST /api/rag/search/jobs（202，:155）、GET /api/rag/search/jobs/{job_id}（:187，404 rag_job_not_found）。
- **預設停用**：`ROOMPILOT_RAG_ENABLED` 預設 `"false"`（`rag/settings.py:65`）；parser provider 預設 openai（settings.py:55，模型預設 `gpt-5.6-sol`，anthropic 選項預設 `claude-sonnet-4-6`，settings.py:57-59）。
- **就緒守門**：service.py:82-90 檢查 embedding model cache 缺失與 pgvector 表無資料（furniture_embeddings_empty）為 blocker。
- **背壓**：非同步 jobs 以 daemon Thread 執行，`RAG_JOB_MAX_ACTIVE = 1`（rag_api.py:30），超額回 429 rag_job_capacity_reached（:163）。

**理由**: 檢索只產生「候選與證據」，家具合法位置仍由 `backend/engine/` 判定（AGENTS.md:55）；預設停用＋型別化錯誤讓 RAG 是可插拔強化而非硬依賴。

## 4. 後果

- **正面**: 未配置機器照常啟動；前端 rag.js 走 202 輪詢不卡同步請求；受控詞彙與 `.claude/skills/roompilot-furniture-query` skill 的六風格/24 氛圍詞/19 群組一致。
- **負面**: 啟用需同時就緒 API key、離線 BGE-M3 快取與 pgvector 匯入，三缺一即 blocker；`RAG_JOB_MAX_ACTIVE = 1` 使併發查詢常撞 429。
- **影響範圍**: `backend/spatial_data/`、`backend/catalog/`、`backend/server/`、tests/test_rag_{api,domain,frontend}.py。
- **重新評估觸發**: RAG 從測試台走向正式第 6 步選件流程時；job 容量上限需要提高時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-04 | 本次導入（回溯撰寫） | 模組行數、路由行號、預設值、詞彙數皆實測 |

---

# ADR-009: 工程文件 MVP：snapshot→lock→packages→jobs→documents 五段流程

> **狀態:** 已接受 | **日期:** 2026-07-31（commit `e1e22ddf` 入主線） | **決策者:** Bella（契約 ENGINEERING_DOCUMENT_MVP.md owner）；討論過程(未查證)

---

## 1. 背景與問題

- **上下文**: 八步工作流第 7 步「方案鎖定」之後，需要把場景方案轉成可交付的工程文件（工程量、估價、排程、報告 HTML/XLSX）。
- **問題**: 文件產生耗時（多階段：數量→規則→成本→排程→敘事→輸出），不能同步阻塞；且必須保證「產包的輸入是設計師確認過的版本」，否則報告與場景會漂移。
- **驅動因素/約束**:
  - 契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`＋`engineering_openapi.yaml`＋三份 JSON Schema（project_snapshot/report_payload/risk_results）。
  - 知識資料屬 catalog 資料層：`backend/catalog/data/engineering/`（14 項：work_items.json、material_catalog.json、price_records.json、productivity_records.json、task_dependencies.json、construction_knowledge.jsonl 等）。

## 2. 考量的選項

### 選項一: 同步端點直接生成文件
- **描述**: 一支 POST 進去、文件出來。
- **優點**: 簡單。
- **缺點**: 長請求逾時；無進度可觀測；輸入版本無鎖定保證。
- **成本/複雜度**: 低

### 選項二: 版本鎖定＋非同步 job＋文件下載分離的五段流程
- **描述**: 見決策段。
- **優點**: 鎖定前禁止產包；job 可輪詢；文件路徑受限。
- **缺點**: 前端要管理五段狀態機（engineering.js 465 行）。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二。`backend/server/engineering/`（api.py 361 行＋orchestrator/quantity/rules/cost/schedule/narrative/documents/repository 等，共 14 個 .py 合計 3,111 行，另有 Node adapter `workbook_builder.mjs`，全套件 15 檔）以 prefix=`/api/v1` 掛 8 條路由（api.py 行號實測）：

1. **Snapshot**：`PUT /api/v1/projects/{project_id}/revisions/{revision}/snapshot`（:107）——path 與 payload 不一致回 422 PATH_PAYLOAD_MISMATCH（:114-122）；鎖定版本覆寫回 409 LOCKED_REVISION_CANNOT_BE_OVERWRITTEN；專案已前進回 409 SNAPSHOT_SOURCE_REVISION_STALE。
2. **Lock**：`POST .../revisions/{revision}/lock`（:325）以 body.confirmed_by 呼叫 repository.lock_revision。
3. **Packages**：`POST .../engineering-packages`（202，:172）——先取 snapshot（404 SNAPSHOT_NOT_FOUND），再檢查 `snapshot.approval_status == "designer_confirmed"`，否則 409 REVISION_NOT_LOCKED（:191-195）；建 JobStatus（job_id=`job_<uuid4 hex 12 碼>`）後交 BackgroundTasks 執行。
4. **Jobs**：`GET /api/v1/jobs/{job_id}`（:271）輪詢 progress/stage；失敗分 XLSX_ADAPTER_UNAVAILABLE 與 ENGINEERING_PACKAGE_FAILED 兩類 error_code（:216-268）。
5. **Documents**：`GET /api/v1/packages/{package_id}`（:281）回 ReportPayload；`GET /api/v1/documents/{document_id}/download`（:294）只允許落在 `<PROJECT_DIR>/.runtime/engineering` 之下的實檔（`path.is_relative_to(root)` 防護，:297-301），支援 .json/.html/.xlsx。

配套：`GET /api/v1/engineering/health`（:77）回報 snapshot_store provider、demo_mode（`ROOMPILOT_DEMO_MODE`，:58）、knowledge counts 與 xlsx adapter；XLSX 走 Node adapter `engineering/workbook_builder.mjs`（documents.py:30），node 執行檔由 `ROOMPILOT_ARTIFACT_NODE` 指定（documents.py:142）；知識庫 JsonEngineeringKnowledgeRepository 指向 `backend/catalog/data/engineering`（api.py:52-54）。

**理由**: 「鎖定才可產包」把報告輸入凍結成可稽核版本；非同步 job＋型別化 error_code 讓耗時流程可觀測；下載路徑白名單防任意檔案讀取。

## 4. 後果

- **正面**: ReportPayload 成為下游 `.claude/skills/roompilot-proposal`（提案）與 `roompilot-budget`（估價排程）兩支 skill 的唯一數字來源；tests/ 有 engineering_* 系列 7 支守約。
- **負面**: XLSX 依賴外部 Node runtime，缺 node 時該格式降級失敗（XLSX_ADAPTER_UNAVAILABLE）；job 狀態存於行程內，重啟後輪詢中的 job 遺失(未查證：持久化行為未逐行確認)。
- **影響範圍**: `backend/server/engineering/`、`backend/catalog/data/engineering/`、前端 engineering.html/engineering.js、`/engineering` 頁（main.py:2565）。
- **重新評估觸發**: 工程文件從 MVP 走向正式交付（多專案併發產包、job 持久化）時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-04 | 本次導入（回溯撰寫） | 路由行號、錯誤碼、路徑防護、Node adapter 皆實測 |

---

# ADR-010: 專案原生 Claude skills 進版控（`.claude/skills/` 白名單）

> **狀態:** 已接受 | **日期:** 2026-08-04 | **決策者:** Django（commit `3b2438dd`、`a2179f7e` 所在分支 django-skill）；團隊共識過程(未查證)

---

## 1. 背景與問題

- **上下文**: `.gitignore` 原本整段忽略 `.claude/*`（因含個人設定與含 API key 的 `.mcp.json`）。團隊逐步累積了四支 RoomPilot 專屬的 agent skill（資安稽核、RAG 查詢轉譯、提案文件、預算報告），散在各人本機。
- **問題**: skill 是團隊共用工作方法，不進版控就無法共享、審查與演進；但 `.claude/` 其餘內容（個人 settings、社群 skill、含密鑰檔）不可入庫。
- **驅動因素/約束**:
  - `.mcp.json` 因含 API key 必須維持忽略（.gitignore:91）。
  - skill 內含可執行腳本（audit.sh、verify_numbers.py 等），需要 code review。

## 2. 考量的選項

### 選項一: skill 放 docs/ 或 scripts/
- **描述**: 內容當一般文件/腳本入庫。
- **優點**: 不動 .gitignore。
- **缺點**: Claude Code 不會從 docs/ 載入 skill，失去自動觸發能力。
- **成本/複雜度**: 低

### 選項二: `.gitignore` 對 `.claude/skills/` 開唯一白名單
- **描述**: `.claude/*` 維持忽略，僅 `!.claude/skills/` 負向收回。
- **優點**: skill 就地生效又可版控；個人設定與密鑰仍被擋。
- **缺點**: `.claude/skills/` 下混入的未追蹤社群 skill 需人工分辨。
- **成本/複雜度**: 低

## 3. 決策

**選擇**: 選項二。`.gitignore:43-46`：`.claude/*` 忽略、唯一例外 `!.claude/skills/`（註解明言 skills 是共用專案 skill 要進版控）。追蹤檔案共 **14 個**（`git ls-files .claude/skills/` 實測），全部屬四支 roompilot-* skill，各 SKILL.md front matter 標 `origin: RoomPilot-Agent 專案原生`：

| skill | 檔案 | 用途 |
| :--- | :--- | :--- |
| roompilot-security | SKILL.md、audit.sh、references/remediation.md | 掃描實際攻擊面（FastAPI 八步工作流、專案保存、SSRF、模型交付、PostgreSQL catalog）；SKILL.md 明言 repo 現況「全端點無認證/授權、外部抓取無 SSRF 防護、DB 預設明文連線」 |
| roompilot-furniture-query | SKILL.md、lint_query.py、references/{vocabulary,translation-patterns}.md | 口語需求→`POST /api/rag/search` 受控詞彙檢索句（六風格十八色卡、24 氛圍詞、19 家具群組），只轉譯不碰幾何 |
| roompilot-proposal | SKILL.md、build_proposal.py、verify_numbers.py、references/style-voice.md | ReportPayload→屋主提案；文案由 agent 寫、數字由腳本取，verify_numbers.py 擋編造數字 |
| roompilot-budget | SKILL.md、build_budget.py、verify_budget.py | ReportPayload→工程估價與排程文件，零 LLM 文字、附列印樣式 |

入庫節點：commit `3b2438dd`「feat(skills): 新增三支 RoomPilot 專用 skill,並讓 .claude/skills 進版控」；HEAD `a2179f7e`（2026-08-04）修 skill 報告 HTML 骨架與版面。

**理由**: skill 的腳本把「數字必須來自 payload」「查詢必須是受控詞彙」等紀律做成可執行檢查，與 repo 的契約文化一致；白名單切法讓密鑰檔零外洩風險不變。

## 4. 後果

- **正面**: 四支 skill 隨 repo 分發，任何成員 clone 即得；skill 腳本可被 PR review。
- **負面**: `.claude/skills/` 下同時存在未追蹤的社群 skill 目錄（`git status` 顯示多個 `??`），已追蹤/未追蹤並存易混淆；skill 內容與程式碼演進需人工同步（如 catalog 件數變動時 furniture-query 的詞彙表）。
- **影響範圍**: `.gitignore`、`.claude/skills/`、所有使用 Claude Code 的成員工作流。
- **重新評估觸發**: 社群 skill 是否也要入庫的裁決；skill 與 docs/contracts/ 內容重複到需要指定單一權威時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-04 | 本次導入（回溯撰寫） | git ls-files、.gitignore 行段、commit 訊息皆實測 |

---

## 待補事項

- 各 ADR 的「決策者」僅依 commit 作者、分支名與 `docs/TEAM_AI_OWNERSHIP.md` 責任歸屬回推，實際討論與拍板過程待團隊補認（標註「(未查證)」處）。
- ADR-004 取代案：母集合來源檔由 `furniture_catalog_cloud_9350.json` 換成 `JSON/furniture/furniture_official_catagory.json`（9,350 與 8,557 是兩份不同來源檔的 count，非同一份的削減）的原因、差異清單與時點 commit 未逐一追查(未查證)；`furniture_catalog_cloud_9350.json` 舊資料檔的去留待裁決。
- ADR-007：PostgreSQL `roompilot.furniture_catalog_current` view 的實際列數需連線 DB 查證(未查證)。
- ADR-009：job 狀態在伺服器重啟後的行為（是否持久化於 repository）未逐行確認(未查證)。
- 模板 INDEX.md 指向的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/` (未查證：來源不在 repo)。
