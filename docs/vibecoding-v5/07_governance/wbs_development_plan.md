# WBS 開發計劃 - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 07_governance/wbs_development_plan.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04 | **狀態:** 進行中

工作項推導依據：`docs/backlog/`（現存 1 檔）、repo 根 `MAIN_SYNC_TODO.md` 的必做/建議清單、`docs/contracts/`（22 檔）明文標註的邊界，以及對現行工作樹（a2179f7e）的逐項實測。程式碼內 `TODO`/`FIXME` 全 backend 僅 5 處命中，且全部是 `backend/floorplan/` 內引用 `MAIN_SYNC_TODO`／草案值的說明性註解（grep 實測），非未完成標記。工時與日期凡 repo 無證據者一律留空或標「(未查證)」，不推估。前一代導入版 `docs/vibecoding/16_wbs_development_plan_template.md`（2026-07-26 基準）的事實已過期，本文件對每一項重查；已結案項在第 3 節明確標示。

---

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot-Agent（`backend/server/main.py:214` FastAPI title：「AI 室內風格與家具配置展示系統」） |
| **專案經理** | (未查證；repo 無 PM 職稱，`docs/TEAM_AI_OWNERSHIP.md` 僅定義目錄負責人制，Bella 為整合窗口) |
| **技術主導** | 無單一技術主導；採 7 人目錄負責人制（`docs/TEAM_AI_OWNERSHIP.md:19-34`），見下表 |
| **總工期** | (未查證；repo 無時程文件。成果發表日 2026-08-20 依團隊口述，repo 無記載) |
| **目前進度** | 整體百分比無權威來源；可量測現況：pytest 821 collected → **811 passed / 1 failed / 9 skipped**（2026-08-04 `.venv/bin/python -m pytest tests/ -q` 實測，69.87s，見第 4 節） |

### 角色與職責

本專案不採模板的 PM/TL/PO/ARCH/QA 分工，改用 `docs/TEAM_AI_OWNERSHIP.md` 的目錄負責人制（7 人；`:3` 明示 Git author 不能單獨視為 owner）：

| 角色 | 負責人 | 職責（出處：`docs/TEAM_AI_OWNERSHIP.md:19-34` 目錄責任表） |
| :--- | :--- | :--- |
| 伺服器與正式 UI | Bella | `backend/server/`（含 `static/`、`engineering/`）：FastAPI、八步工作流、工程文件 MVP；`docs/contracts/` 整合 |
| 平面圖辨識 | Cody | `backend/floorplan/`、`backend/upgrade3d/`：PNG/DXF、牆門窗與房間辨識、layout_json |
| 空間資料與家具 RAG | Django | `backend/spatial_data/`（含 `rag/`）：空間尺寸與相鄰、家具 RAG runtime |
| 家具型錄與 PostgreSQL | Kai | `backend/catalog/`：官方型錄、AWS/CloudFront 交付、PostgreSQL 五階段、隔離資料 |
| Agent 選件 | Yen | `backend/agent/`：LLM 選件與擺放失敗修復策略，不輸出座標 |
| 擺放引擎 | Ancai | `backend/engine/`：座標、碰撞、淨空；幾何與規則的唯一裁決者（`:53`） |
| 辨識 QA / evaluation | Ben | 辨識品質驗證與 `MAIN_SYNC_TODO.md` 合併裁決（`docs/TEAM_AI_OWNERSHIP.md:7-15` 分支對照） |

---

## 2. WBS 結構

```
1.0 專案管理與規劃
├── 1.1 分支與合併治理（AGENTS.md + TEAM_AI_OWNERSHIP，現行；遠端分支 17 條）
├── 1.2 里程碑與時程管理（時程文件仍缺）
└── 1.3 cody-dev 合併收尾（MAIN_SYNC_TODO.md §4 必做與建議，待 Ben 裁決）

2.0 系統架構與設計
├── 2.1 正式契約維護（docs/contracts/ 22 檔，現行）
├── 2.2 LAYOUT_EVALUATION_SCHEMA 正式 API 化（契約仍為提案）
└── 2.3 PostgreSQL 五階段（Phase 1–5 契約＋scripts 已在庫，執行期環境變數 opt-in）

3.0 後端開發（按目錄負責人分組）
├── 3.1 Cody：平面圖辨識（backend/floorplan/ 9,313 行 + backend/upgrade3d/ 305 行）
├── 3.2 Kai：家具型錄與 PostgreSQL（backend/catalog/ 3,199 行）
├── 3.3 Django：空間資料與家具 RAG runtime（backend/spatial_data/ 1,236 行）★新子系統
├── 3.4 Yen：Agent 選件（backend/agent/ 1,045 行）
├── 3.5 Ancai：擺放引擎（backend/engine/ 717 行）
├── 3.6 Bella：FastAPI 伺服器（backend/server/，main.py 3,695 行、全站 63 條路由）
└── 3.7 Bella：工程文件 MVP（backend/server/engineering/，snapshot→lock→packages→jobs→documents）★新子系統

4.0 前端開發
├── 4.1 主前端靜態頁（backend/server/static/ 1,031 檔、6 個 HTML 頁）
├── 4.2 frontend3d（React Three Fiber）去留裁決（仍開放）
└── 4.3 cache-busting 雜湊一致性（現行唯一紅燈）

5.0 測試與品質保證
├── 5.1 紅燈修復（現 1 failed）
├── 5.2 平面圖辨識評估測試（docs/backlog/FLOORPLAN_DATASET_TUNING.md，待執行）
└── 5.3 覆蓋率量測（repo 仍無 coverage 設定）

6.0 部署與上線
├── 6.1 遠端渲染供應商（render_providers.py 雙路徑，未設定時維持 502/503 契約）
├── 6.2 CloudFront GLB 交付（現行，官方 catalog 8,557 筆）
└── 6.3 PostgreSQL 匯入與執行期啟用（scripts/sql、project_store、runtime_catalog）

7.0 文檔、Skill 與培訓
├── 7.1 專案 Skill 維護（.claude/skills/ 四支 roompilot-*，已進版控）★新子系統
├── 7.2 文件與現況不一致修正（分支對照表、frontend3d README port）
└── 7.3 VibeCoding v5 文件導入（docs/vibecoding-v5/，本文件所屬批次）
```

### 工作包統計

工時 repo 無證據，全部留空；狀態依 2026-08-04 實測。

| WBS 模組 | 總工時 | 已完成 | 進度 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| 1.0 專案管理 | | | 待補 | 合併規則已運作；MAIN_SYNC_TODO §4.1 三項必做未結 |
| 2.0 系統架構 | | | 待補 | 22 份契約在庫；2.2 未動工、2.3 程式已接線待啟用 |
| 3.0 後端開發 | | | 待補 | 主流程可運作（811 綠）；六模組合計 15,815 行 Python |
| 4.0 前端開發 | | | 待補 | 主前端現行；1 個雜湊紅燈；frontend3d 去留待議 |
| 5.0 測試品保 | | | 待補 | 811 passed / 1 failed / 9 skipped（實測） |
| 6.0 部署上線 | | | 待補 | CloudFront 現行；PostgreSQL 執行期為 opt-in |
| 7.0 文檔培訓 | | | 待補 | 四支 skill 已入庫；已知文件矛盾列 7.2 |
| **合計** | | | **待補** | |

---

## 3. 詳細任務分解

每項「依據」欄為 2026-08-04 於現行工作樹（a2179f7e）實測的證據。狀態僅用：待辦／進行中／現行維護／待議（需跨模組裁決）／已結案（相對前一代 WBS）。

### 模組 3.1：Cody — 平面圖辨識（`backend/floorplan/`、`backend/upgrade3d/`）

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.1.1 | 平面圖辨識資料集調校：合法授權圖蒐集、固定切分、比例尺誤差／牆體拓樸／門窗／房名評估 | Cody | | 待辦 | | - | `docs/backlog/FLOORPLAN_DATASET_TUNING.md:5` 狀態明標「待執行」（承接舊 FV-07） |
| 3.1.2 | 房型語意層依賴裁決：torch（DINOv2）在 HTTP 辨識路徑上，缺它房型準確度由 90.3% 退回幾何猜測；是否移入 requirements baseline 待 Ben 拍板 | Cody（Ben 裁決） | | 待議 | | - | `MAIN_SYNC_TODO.md` §4.2 建議 1（呼叫鏈 `vision/analysis.py:530` → `room_classifier.py`）；`requirements.txt:46-57` 註解 |
| 3.1.3 | OCR 引擎收斂：短期保留 rapidocr＋paddleocr 兩引擎，中期收斂到 rapidocr | Cody | | 待辦 | | - | `MAIN_SYNC_TODO.md` §4.2 建議 2；`default_ocr_provider` 已接線（`main.py:45,176`，前一代 WBS 3.1.5「無呼叫者」已結案） |
| 3.1.4 | 前端 `stair` 契約鍵：語意層已新增 stair 房類，前端比照 circulation 零家具處理 | Cody（與 Bella 協作） | | 待辦 | | - | `MAIN_SYNC_TODO.md` §4.2 建議 3；`vision/analysis.py:75` 註解 |
| 3.1.5 | 辨識管線維護：floorplan2dxf_color 1,966／floorplan2dxf 1,588／floorplan2room 1,046／cody_adapter 1,036 行與 vision/ 15 檔 | Cody | | 現行維護 | | - | `wc -l` 實測（模組共 24 檔 9,313 行）；tests/ 內 floorplan/cody 系測試約 10 支（`ls tests`） |
| 3.1.6 | DXF 比例尺限制標註：無 `$INSUNITS` 且無手動比例時正規化長邊，非真實尺寸，對外需明示 | Cody | | 待辦 | | - | `backend/upgrade3d/dxf_parser.py`（305 行，`parse_dxf_file:271`；正規化行為承前一代 WBS 3.1.7，2026-08-04 重查行號：`:30` `DEFAULT_SPAN = 12.0`、`:139-147` `$INSUNITS` 缺漏時 basis 標 `"normalized"`） |

**模組小計**：工時待補 | 進度：待補

### 模組 3.2：Kai — 家具型錄與 PostgreSQL（`backend/catalog/`）

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.2.1 | 官方雲端型錄維運：8,557 筆官方 JSON catalog（載入來源檔 `JSON/furniture/furniture_official_catagory.json` count=8557；另一份 `backend/catalog/data/furniture_catalog_cloud_9350.json` count=9350 為舊 fallback 來源，非 8,557 的前身） | Kai | | 現行維護 | | - | `docs/TEAM_AI_OWNERSHIP.md:57`、`backend/catalog/cloud_catalog.py:1`（270 行）；兩檔 count 皆 python json 實測；載入路徑 `main.py:137-146` |
| 3.2.2 | PostgreSQL 唯讀 read 層（Phase 1）：`postgres_repository.py` 891 行，「FastAPI 不得為 filter/count/facet 載入完整型錄」 | Kai | | 現行維護 | | - | `postgres_repository.py:1-5`；`docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md`；`main.py:1122` `catalog_provider_mode == "postgres"` 分流 |
| 3.2.3 | PostgreSQL 管理 CRUD（Phase 2）：`postgres_admin_repository.py` 764 行（交易寫入、activation gate、樂觀併發、audit），經 `catalog_admin.py` 曝露 4 條 `/api/admin/furniture` 路由 | Kai（與 Bella 協作） | | 現行維護 | | - | `postgres_admin_repository.py:1-6`；`backend/server/catalog_admin.py:29,234-294`；`POSTGRESQL_CATALOG_CRUD_PHASE2.md` |
| 3.2.4 | Runtime catalog（Phase 4）：styles/surfaces/costs/quarantine 由逐次掃 JSON 改為 PostgreSQL，strict 模式不靜默回退 | Kai（與 Bella 協作） | | 現行維護 | | - | `runtime_catalog_repository.py:1-6`（431 行）；消費端 `cost_estimation.py:9`、`style_cards.py:6`、`main.py:111`；`POSTGRESQL_RUNTIME_CATALOG_PHASE4.md` |
| 3.2.5 | 單一事實來源（Phase 5）收斂：JSON 與 DB 之間的最終權威切換 | Kai | | 待辦 | | 3.2.2-3.2.4, 6.3.1 | `docs/contracts/POSTGRESQL_SINGLE_SOURCE_PHASE5.md` 在庫；實際 DB 啟用狀態=(未查證) |
| 3.2.6 | 家具向量與 RAG 資料層：`rag_repository.py` 164 行（pgvector adapter，EMBEDDING_MODEL=BAAI/bge-m3） | Kai（供 Django 消費） | | 現行維護 | | - | `rag_repository.py:1,12`；`POSTGRESQL_FURNITURE_EMBEDDINGS.md`、`POSTGRESQL_FURNITURE_RAG_RUNTIME.md` |
| 3.2.7 | 隔離區治理：`quarantine/`（sf3d_legacy、unmatched_cloud_furniture）不得進入正式家具 | Kai | | 現行維護 | | - | `backend/catalog/data/quarantine/` 兩子目錄（ls 實測）；CLAUDE.md 禁令 |

**模組小計**：工時待補 | 進度：待補

### 模組 3.3：Django — 空間資料與家具 RAG runtime（`backend/spatial_data/`）★前一代 WBS 3.3.1「目錄僅 .gitkeep」已結案

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.3.1 | 家具 RAG runtime 維護：`rag/` 11 檔 1,234 行（含模組根 `__init__.py` 則 12 檔 1,236 行；service.py 496 行「LLM parser → pgvector → reranker」），經 `backend/server/rag_api.py` 曝露 5 條路由（`/rag`、`/api/rag/status`、`/api/rag/search`、`/api/rag/search/jobs{,/{job_id}}`） | Django（與 Kai、Bella 協作） | | 現行維護 | | 3.2.6 | `rag/service.py:1`；`rag_api.py:26,136-187`（`main.py:217` 掛載）；tests：test_rag_api／domain／frontend |
| 3.3.2 | 受控詞彙與分類資料維護：taxonomy.json（6 風格／24 氛圍詞／4 pattern）、category_groups.json（19 群組／6 房型預設集） | Django | | 現行維護 | | - | `rag/data/*.json` python json 實測；與 roompilot-furniture-query skill 詞彙一致 |
| 3.3.3 | RAG 就緒守門與容量治理：embedding 模型快取缺失／pgvector 空表為 blocker；jobs 並發上限 `RAG_JOB_MAX_ACTIVE` 超過回 429 | Django | | 現行維護 | | - | `rag/service.py:82-90`；`rag_api.py:155`（202 非同步、429 rag_job_capacity_reached） |
| 3.3.4 | 空間尺寸／相鄰／evaluation 記錄模組：目錄責任表定義的空間資料職責，`rag/` 以外仍只有 `__init__.py`（2 行）＋AGENTS.md | Django | | 待辦 | | - | `ls backend/spatial_data/` 實測；`docs/TEAM_AI_OWNERSHIP.md:24` |

**模組小計**：工時待補 | 進度：待補

### 模組 3.4：Yen — Agent 選件（`backend/agent/`）

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.4.1 | 選件與失敗修復迴圈維護：select.py 617 行（LLM 只選件不捏造、不出座標）、place.py 285 行（主件先行、副件成組、放不下寧缺勿亂）、knowledge.py 132 行 | Yen | | 現行維護 | | - | 各檔 docstring 與 `wc -l` 實測；消費端 `main.py:23-24`、`scene_service.py:16`；agent 系測試 5 支 |
| 3.4.2 | 問卷需求接進選件規則層：選件 agent 已由伺服器實際觸發 | Yen（與 Bella 協作） | | 已結案 | 2026-08-02 | - | commit `a867d53d`「問卷需求接進選件規則層，選件 agent 由伺服器實際觸發」（`git show -s --date=short` 實測 commit 日期 2026-08-02） |
| 3.4.3 | `placement_hints()` 接線裁決：函式呼叫者仍僅 `tests/test_agent_place.py`；`main.py:864`／`postgres_repository.py:447` 的 `"placement_hints": {}` 為資料欄位非函式呼叫 | Yen | | 待議 | | - | grep 全 backend/＋tests/ 實測（2026-08-04） |

**模組小計**：工時待補 | 進度：待補

### 模組 3.5：Ancai — 擺放引擎（`backend/engine/`）

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.5.1 | 幾何／碰撞／淨空引擎維護（公分制、Shapely）：8 檔 717 行，placement/clearance/geometry/dxf_room/adjustment/models/schema | Ancai | | 現行維護 | | - | `wc -l` 實測；單位契約 `schema.py` docstring「一律公分」；消費端 `scene_service.py:19-27` |
| 3.5.2 | 佈局評估正式 API 化：`LAYOUT_EVALUATION_SCHEMA.md` 仍為目標評估格式，未成為正式 API | Ancai（與 Bella 協作） | | 待辦 | | - | `docs/contracts/LAYOUT_EVALUATION_SCHEMA.md`（22 檔清單內，「擺放完成後的目標評估資料格式」）；現行驗證入口為 `POST /api/scene/validate`（`main.py:3492`） |
| 3.5.3 | `adjustment.py` 接線裁決：`move_furniture`/`rotate_furniture`/`adjust_furniture` 在 `backend/server/` 仍無呼叫點 | Ancai（與 Bella 協作） | | 待議 | | - | grep `backend/server/` 零命中（2026-08-04 實測）；`scene_service.py:19-27` 匯入清單無 adjustment |
| 3.5.4 | 門弧淨空與窗種分流：拖曳驗證與自動擺放共用同一份禁區 | Ancai（與 Bella 協作） | | 已結案 | 2026-08-02 | - | commit `6e9ace0c`「門弧淨空與窗種分流，拖曳驗證改用同一份禁區」（`git show -s --date=short` 實測 commit 日期 2026-08-02） |

**模組小計**：工時待補 | 進度：待補

### 模組 3.6：Bella — FastAPI 伺服器（`backend/server/`）

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.6.1 | 修復 1 個紅燈：`scene.html` 引 `scene_v2.js?v=sha256-27f24b6bede3`／`site.css?v=sha256-5693fe5d95c5`，實算前 12 碼為 `7d938e1fdc28`／`e362900c8195` | Bella | | 待辦 | | - | pytest 實測 1 failed：`tests/test_scene_v2_contract.py::test_scene_entrypoint_cache_key_matches_bundle_content`；`shasum -a 256` 比對 |
| 3.6.2 | 窗簾 GLB 缺檔：已改為檔案不存在即回 `None`、列入 `decor_summary.skipped`，不再必觸發 404（static/ 下 .glb 仍為 0 個） | Bella | | 已結案 | | - | `main.py:3294-3303` docstring 自述修法；`find backend/server/static -name '*.glb'` = 0（前一代 WBS 3.6.2 對應項） |
| 3.6.3 | 伺服器端步驟順序防護：`WORKFLOW_STEPS` 仍為無序 set 只驗步驟名（11 步），前置依賴僅前端強制，伺服器無法阻止跳步驟寫入 | Bella | | 待辦 | | - | `main.py:183-195`（set）與 `main.py:2050`（僅 membership 檢查）實測 |
| 3.6.4 | `DATASET_DIR` 路徑：仍指向 repo 根 `dataset/`（不存在），用於外部 GLB zip 搜尋目錄清單 | Bella | | 待辦 | | - | `main.py:150,197`；`ls dataset` → No such file（實測） |
| 3.6.5 | 問卷選項圖片補齊：110 個選項圖中 8 個 `ready`、102 個 `planned` | Bella（圖片來源負責人未查證） | | 進行中 | | - | `backend/server/data/questionnaire_visual_catalog.json` python 實測（"ready" 8、"planned" 102）；服務層 `questionnaire_visuals.py` 250 行 |
| 3.6.6 | `main.py` 拆分裁決：單檔 3,695 行、46 條路由；rag/catalog_admin/engineering 已拆出 APIRouter（各 5/4/8 條），全站合計 63 條 | Bella | | 待議 | | - | `wc -l`；路由數法見 vibemap/server-api.md（grep 逐條核對＋`grep -c` 交叉驗證，2026-08-04） |
| 3.6.7 | 專案持久化與樂觀鎖維護：SQLite 預設，`project_store_provider` 可切 postgres（Phase 3） | Bella | | 現行維護 | | - | `project_store.py:607-617`；`scripts/project_store/`；`POSTGRESQL_PROJECT_STORE_PHASE3.md` |
| 3.6.8 | 遠端渲染雙路徑維護：`render_providers.py` 444 行，`ROOMPILOT_RENDER_PROVIDER_URL` 有值優先走原轉送路徑，502/503 錯誤碼契約保留；批次生圖單房失敗不中止整批（該房記為 `status: "failed"` 可重試），全部房間都失敗才原樣拋回最後一個錯誤 | Bella | | 現行維護 | | - | `render_providers.py:16,55,378-395,434-437` 實測（`:380` 註解所述「遇首個 502 即整批中止」是 2026-08-01 QA 已修正的舊行為）；`REMOTE_RENDER_CONTRACT.md` |
| 3.6.9 | 成本估算與風格卡服務：`cost_estimation.py` 109 行（`POST /api/cost/estimate`，`main.py:3658`）、`style_cards.py` 27 行，資料來源走 Phase 4 runtime catalog | Bella（與 Kai 協作） | | 現行維護 | | 3.2.4 | `wc -l`；`cost_estimation.py:9`、`style_cards.py:6` 匯入 runtime_catalog_repository |

**模組小計**：工時待補 | 進度：待補

### 模組 3.7：Bella — 工程文件 MVP（`backend/server/engineering/`）★新子系統，前一代 WBS 無此項

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.7.1 | snapshot→lock→packages→jobs→documents 五段工作流維護：8 條 `/api/v1` 路由（`engineering/api.py` 361 行；PUT/GET snapshot、POST lock、POST engineering-packages(202)、GET jobs/packages/documents、GET health） | Bella | | 現行維護 | | - | `api.py:50,77-334`；`docs/contracts/ENGINEERING_DOCUMENT_MVP.md`、`engineering_openapi.yaml`＋3 個 schema.json；掛載 `main.py:218-223` |
| 3.7.2 | 鎖定與狀態機守門：PATH_PAYLOAD_MISMATCH(422)、LOCKED_REVISION_CANNOT_BE_OVERWRITTEN／SNAPSHOT_SOURCE_REVISION_STALE／REVISION_NOT_LOCKED(409) 等錯誤碼契約 | Bella | | 現行維護 | | - | `api.py:120`（PATH_PAYLOAD_MISMATCH）、`:130`、`:138`、`:195`（三個 409 錯誤碼）實測 |
| 3.7.3 | XLSX Node adapter：`workbook_builder.mjs`，node 執行檔由 `ROOMPILOT_ARTIFACT_NODE` 指定；不可用時 job 以 `XLSX_ADAPTER_UNAVAILABLE` 失敗 | Bella | | 現行維護 | | - | `api.py:98-104,216-268`；`ls backend/server/engineering/` 實測 |
| 3.7.4 | 工程知識庫資料層：`backend/catalog/data/engineering/`（14 項：work_items、material_catalog、price_records、construction_knowledge.jsonl 等） | Bella（資料 owner 與 Kai 交界=(未查證)） | | 現行維護 | | - | `ls backend/catalog/data/engineering/`；`api.py:52-54` JsonEngineeringKnowledgeRepository 指向該目錄 |
| 3.7.5 | 文件下載路徑防護維護：僅允許 `<PROJECT_DIR>/.runtime/engineering` 下實檔（`is_relative_to` 防護） | Bella | | 現行維護 | | - | `api.py:295-303` |

**模組小計**：工時待補 | 進度：待補

### 模組 4.0：前端開發

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 4.1.1 | 主前端八步工作流維護：UI 8 顆步驟按鈕（`scene.html:25-32`）、內部狀態機 11 步（`scene_workflow.js:4-16`）；入口 bundle `scene_v2.js` 13,803 行＋`scene_viewer.js` 5,555 行；6 個 HTML 頁（index/styles/library/scene/rag/engineering） | Bella | | 現行維護 | | - | vibemap/frontend.md 實測（static 共 1,031 檔；Three.js vendored 無 CDN） |
| 4.1.2 | 未引用 JS 清理裁決：scene_delivery.js、scene_guidance.js、scene_space_change_report.js、scene_texture_uv.js 未被任何 html/js 引用，僅由 tests/ 以 Node 方式測試 | Bella | | 待議 | | - | grep import 圖實測（vibemap/frontend.md §C） |
| 4.1.3 | cache-busting 全站一致化：sha256 前 12 碼機制僅部分頁面採用，index/styles 仍用日期版本，scene_v2.js 內部混用日期 token；雜湊為手動維護、無自動重算腳本 | Bella | | 待辦 | | 3.6.1 | vibemap/frontend.md §D（grep `?v=` 實測；library.html 雜湊亦不符但無守約測試涵蓋） |
| 4.2.1 | frontend3d 去留裁決：Vite+R3F 原型（src 共約 960 行），AGENTS.md 明定 secondary prototype；4 條移植路由（`/api/plans`、`/api/plan`、`/api/upload`、`/api/furniture/{name}`）仍存活於 main.py | Bella（協作 Ancai） | | 待議 | | - | `frontend3d/AGENTS.md`；`main.py:3551-3686` 路由實測 |

**模組小計**：工時待補 | 進度：待補

### 模組 5.0：測試與品質保證

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 5.1.1 | 紅燈歸零（現 1 failed，同 3.6.1） | Bella | | 待辦 | | 3.6.1 | 2026-08-04 全套 pytest 實測 |
| 5.1.2 | skipped 盤點：9 skipped 的原因分類（外部依賴／環境缺件） | 整合者(未查證) | | 待辦 | | - | pytest 摘要實測；逐項原因未查證 |
| 5.2.1 | 平面圖評估自動化測試（backlog 驗收產物） | Cody | | 待辦 | | 3.1.1 | `docs/backlog/FLOORPLAN_DATASET_TUNING.md` |
| 5.2.2 | node 環境重跑全套 pytest：MAIN_SYNC_TODO 要求在有 node 的環境確認前端契約測試恢復 | Ben | | 待辦 | | - | `MAIN_SYNC_TODO.md` §4.1；tests/static/ 3 支 .test.mjs |
| 5.3.1 | 覆蓋率量測導入：repo 仍無 coverage 設定（無 pytest-cov、無 .coveragerc） | 整合者(未查證) | | 待辦 | | - | grep pyproject.toml/requirements.txt 與 `ls .coveragerc` 實測 |
| 5.4.1 | 測試資產維護：tests/ 99 支 test_*.py＋conftest；tests/static/ 3 支 mjs＋4 支 harness；training/tests/ 另 11 支 | 各 owner | | 現行維護 | | - | `find`／`ls \| wc -l` 實測（vibemap/data-contracts-tests.md） |

**模組小計**：工時待補 | 進度：待補

### 模組 6.0：部署與上線

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 6.1.1 | 遠端渲染供應商設定：環境變數未設定時第 8 步生圖依 502/503 契約回報，不假成功 | Bella（供應商窗口未查證） | | 待辦 | | 3.6.8 | `render_providers.py:16,55,436`；`REMOTE_RENDER_CONTRACT.md` |
| 6.2.1 | CloudFront GLB 交付維運：官方 catalog 8,557 筆；模型交付 4 條路由 `/api/furniture/{furniture_id}/model`、`/model.gltf`、`/buffer.bin`、`/images/{image_index}` | Kai | | 現行維護 | | - | `docs/TEAM_AI_OWNERSHIP.md:57`；`main.py:3508,3517,3526,3536`；manifests/（glb/image 上傳清單 CSV） |
| 6.3.1 | PostgreSQL 執行期啟用：五階段程式與 scripts 均在庫（`scripts/sql/`、`scripts/project_store/`、`scripts/runtime_catalog/`），執行期由環境變數 opt-in；正式環境是否已切換=(未查證) | Kai（與 Bella 協作） | | 進行中 | | 3.2.x | `main.py:1122`、`project_store.py:607-617`、`runtime_catalog_repository.py`；scripts 三子目錄 ls 實測 |
| 6.4.1 | 部署端 DINOv2 骨幹快取：88MB torch.hub 快取需預放或設 `TORCH_HOME`，離線可載入 | Ben（與 Cody 協作） | | 待辦 | | 3.1.2 | `MAIN_SYNC_TODO.md` §4.1 第三項 |
| 6.5.1 | `uv.lock` 重生：pyproject 的 vision extra 已增補 svgpathtools/rapidocr，lock 未同步 | Ben | | 待辦 | | - | `MAIN_SYNC_TODO.md` §4.1 第一項 |

**模組小計**：工時待補 | 進度：待補

### 模組 7.0：文檔、Skill 與培訓

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 7.1.1 | 四支專案 skill 維護：roompilot-security（攻擊面稽核 audit.sh）、roompilot-furniture-query（口語→RAG 受控詞彙）、roompilot-proposal（ReportPayload→屋主提案，verify_numbers.py 擋編造數字）、roompilot-budget（ReportPayload→估價排程，零 LLM 數字）；共 14 個追蹤檔 | Django（commit 提交者；skill owner=(未查證)） | | 現行維護 | | - | `git ls-files .claude/skills/` = 14；commit `3b2438dd`、`a2179f7e`；各 SKILL.md front matter 標 RoomPilot 原生 |
| 7.1.2 | roompilot-security 基線落地：SKILL.md 自述 repo「全端點無認證/授權、外部抓取無 SSRF 防護、DB 預設明文連線」，補強項需轉入開發任務 | Bella（依 skill 掃描結果） | | 待辦 | | - | `.claude/skills/roompilot-security/SKILL.md`（vibemap/team-git-skills.md §4） |
| 7.2.1 | TEAM_AI_OWNERSHIP 分支對照修正：文件寫 `origin/kai-with-bellatest1`，遠端實際無此分支（現有 kai 系為 `origin/kai`、`origin/kai-new`） | Bella（文件整合） | | 待辦 | | - | `git branch -a` 與 `docs/TEAM_AI_OWNERSHIP.md:7-15` 比對實測 |
| 7.2.2 | frontend3d README port 修正：README 範例 port 8000，`vite.config.js:8` 實際代理 8002 | Bella | | 待辦 | | 4.2.1 | `frontend3d/README.md:15` vs `vite.config.js:8` 實測 |
| 7.3.1 | VibeCoding v5 文件導入：`docs/vibecoding-v5/` 依 00–07 分層逐份導入（本文件屬 07_governance 批次） | Django | | 進行中 | | - | `find docs/vibecoding-v5 -type f` 現有 23 檔（19 份 md＋3 份 xlsx＋INDEX.md，含本文件）；`.gitignore:39` `!docs/vibecoding-v5/**` 白名單 |

**模組小計**：工時待補 | 進度：待補

---

## 4. 進度摘要

| 項目 | 當前值 | 目標值 |
| :--- | :--- | :--- |
| 整體進度 | 待補（repo 無進度追蹤文件） | 100% |
| 測試通過 | 811 passed / 1 failed / 9 skipped，共 821（2026-08-04 `.venv/bin/python -m pytest tests/ -q` 實測，69.87s） | 全綠 |
| 程式碼覆蓋率 | 未量測（無 coverage 設定） | 待訂（模板預設 80%+，本專案未採納此門檻） |
| 開放 Bug | 已知 1 項紅燈（3.6.1 雜湊守約）；另 library.html 雜湊不符但無測試涵蓋（4.1.3） | 0 |
| 技術債／待議項 | 本文件標「待議」共 6 項（3.1.2、3.4.3、3.5.3、3.6.6、4.1.2、4.2.1；另 3.1.3 OCR 收斂屬中期，狀態為待辦）；前一代 10 項待議中 1 項已結案（3.1.5 OCR 接線），另 2 項前一代標「待辦」者亦已結案（3.6.2 窗簾 GLB、3.3.1 spatial_data 空目錄） | 逐項裁決歸零 |
| 路由規模 | 全站 63 條 HTTP 路由（main.py 46＋rag_api 5＋catalog_admin 4＋engineering 8；grep 逐條核對） | -（規模指標，非目標值） |

---

## 5. 風險管理

| 風險 | 可能性 | 影響 | 緩解策略 | 負責人 |
| :--- | :--- | :--- | :--- | :--- |
| 59/63 條路由無認證/授權（僅 `/api/admin/furniture` 4 條有 Bearer token）、SSRF 與明文 DB 連線（roompilot-security 基線自述，範圍已縮小），公開部署即暴露 | 高（若對外部署） | 高 | 7.1.2：依 skill 掃描產出補強項；上線前過安全清單 | Bella |
| 伺服器不驗步驟順序（`WORKFLOW_STEPS` set 只驗名稱），客戶端可跳步驟寫入 | 中 | 中 | 3.6.3：伺服器端補前置依賴驗證 | Bella |
| cache-busting 雜湊手動維護且僅部分頁面有守約測試，改前端檔即紅燈或靜默舊快取 | 高（每次前端改動） | 中 | 4.1.3：自動重算腳本或 pre-commit；先修 3.6.1 | Bella |
| torch 依賴未定案：缺 torch 房型準確度由 90.3% 退回幾何猜測，部署環境不一致造成品質不一致 | 中 | 高 | 3.1.2＋6.4.1：Ben 拍板 baseline 化並備妥離線快取 | Ben/Cody |
| PostgreSQL 五階段為 opt-in，JSON 與 DB 雙來源並存期間可能漂移 | 中 | 中 | 3.2.5 Phase 5 收斂單一事實來源；strict 模式已禁止靜默回退 | Kai |
| CloudFront 為 GLB 唯一交付來源；local 備援又因 `DATASET_DIR` 指向不存在目錄而落空 | 低 | 高 | 3.6.4 修路徑；離線備援包維持可驗證 | Bella/Kai |
| 工程文件 XLSX 依賴 Node adapter（`ROOMPILOT_ARTIFACT_NODE`），環境缺 node 時 job 以 XLSX_ADAPTER_UNAVAILABLE 失敗 | 中 | 中 | 3.7.3：部署清單納入 node；health 端點已回報 adapter 狀態 | Bella |
| RAG runtime 依賴 pgvector 資料與本機 BGE-M3 快取，缺任一即 blocker | 中 | 中 | 3.3.3 就緒守門已回報 blocker；部署前跑 `/api/rag/status` | Django/Kai |
| 文件與現況不一致（分支對照、frontend3d port）誤導新成員 | 中 | 低-中 | 7.2.x 逐項修正 | Bella |
| `main.py` 單檔 3,695 行 46 路由，多人改動衝突面大 | 中 | 中 | 3.6.6 拆分裁決；rag/admin/engineering 已示範 APIRouter 拆出模式 | Bella |

---

## 6. 里程碑

repo 內無時程文件，日期欄除已發生事實外一律(未查證)或留空。

| 里程碑 | 預計日期 | 交付物 | 狀態 |
| :--- | :--- | :--- | :--- |
| M1: 官方雲端型錄與 PostgreSQL 五階段程式在庫 | (已發生) | 8,557 筆 catalog、Phase 1–5 契約＋repository＋scripts | 完成（程式與契約實測在庫；DB 正式啟用=(未查證)） |
| M2: 工程文件 MVP 與家具 RAG runtime 上線主流程 | (已發生) | `/api/v1` 8 條路由＋`/api/rag/*` 5 條路由、engineering/rag 兩頁 UI、對應測試綠燈 | 完成（2026-08-04 pytest 811 綠含 engineering 7 支、rag 3 支） |
| M3: 紅燈歸零＋MAIN_SYNC_TODO §4.1 必做結案 | 待補 | 全綠 pytest、uv.lock 同步、node 環境驗證、DINOv2 快取部署方案 | 待辦 |
| M4: 待議項逐項裁決 | 待補 | 6 項待議的去留決議紀錄（建議以 ADR 落地） | 待辦 |
| M5: 成果發表 | 2026-08-20(未查證，依團隊口述，repo 無記載) | 可展示完整八步工作流＋工程文件與 RAG 加值功能 | 待辦 |
