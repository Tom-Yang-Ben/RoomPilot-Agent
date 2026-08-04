# 專案結構指南 - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 03_architecture/project_structure.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04
>
> 先行素材：`docs/vibecoding/08_project_structure_guide.md`（2026-07-26 對舊分支 bella-local-20260726 撰寫）。該版事實已過期（44 條路由、47 支測試、無 engineering/、無 RAG），本文所有數字均對現行工作樹重查。

---

## 設計原則

- **按負責人目錄組織**：每位組員只修改自己的主要目錄與對應測試；`backend/` 下一個子目錄對應一位 owner，責任表以 `docs/TEAM_AI_OWNERSHIP.md:19-34` 為準（Git author 不可單獨視為 owner，同檔 :3）。
- **明確職責分層**：家具座標與合法性只由 `backend/engine/` 裁決（`AGENTS.md` 契約第 :55 行；`docs/TEAM_AI_OWNERSHIP.md:53`「Ancai 仍是幾何與規則的唯一裁決者」）；`backend/agent/` 只做選件與修復策略、不碰座標（`backend/agent/place.py` docstring）；`backend/server/` 負責串接。
- **一致命名**：Python 模組 `snake_case.py`、測試 `test_` 開頭、跨模組長度欄位一律公分制 `_cm` 後綴、面積 `_m2`（根目錄 `AGENTS.md:50`）。
- **配置外部化**：專案環境變數 `ROOMPILOT_` 前綴（如 `ROOMPILOT_DEMO_MODE`、`ROOMPILOT_ARTIFACT_NODE`、`ROOMPILOT_RUNTIME_DIR`），LLM 用 `OPENROUTER_` 前綴；根目錄有 `.env.example` 範本，且有守約測試 `tests/test_env_example_contract.py`。
- **與模板的偏差**：本專案**不採用** `src/[app_name]/` 佈局——`backend/` 本身就是 Python 套件（`pyproject.toml` 設 `[tool.setuptools] packages = ["backend"]`、pytest `pythonpath = ["."]`）；也不採用 Clean Architecture 的 domains/application/infrastructure 分層，改以「負責人模組 + 引擎/策略分離」組織。理由見 `README.md` 團隊合併規則與 `docs/TEAM_AI_OWNERSHIP.md`。

---

## 頂層結構

實測目錄樹（2026-08-04，`ls` 實查；略去 `__pycache__`、`.venv`、`.git`、`node_modules`）：

```plaintext
RoomPilot-Agent/
├── backend/                      # Python 套件（唯一後端）
│   ├── agent/                    # Yen：LLM 選件與擺放失敗修復策略（不算座標）
│   ├── catalog/                  # Kai：家具型錄 + PostgreSQL repository 五階段
│   │   └── data/                 # 型錄 JSON、engineering/（工程知識庫 14 項）、
│   │                             #   manifests/、quarantine/（隔離區，不得視為正式家具）
│   ├── engine/                   # Ancai：幾何擺放引擎（座標/碰撞/淨空，全公分制）
│   ├── floorplan/                # Cody：PNG/JPG/DXF 平面圖辨識
│   │   └── vision/               # 分析管線 15 支 .py
│   ├── server/                   # Bella：FastAPI 應用（63 條路由，8 步工作流）
│   │   ├── engineering/          # 工程文件 MVP：snapshot→lock→packages→jobs→documents
│   │   ├── data/                 # questionnaire_visual_catalog.json 等
│   │   ├── services/             # cloud_models.py、cloud_images.py（CloudFront 信任邊界）
│   │   └── static/               # 6 頁 HTML + 64 支 JS + vendor Three.js（共 1,031 檔）
│   ├── spatial_data/             # Django：空間資料
│   │   └── rag/                  # 家具 RAG runtime（11 支 .py，經 rag_api.py 掛 /api/rag/*）
│   └── upgrade3d/                # Cody：DXF → 3D JSON（dxf_parser.py 單檔）
├── JSON/                         # Kai 官方 8,557 件型錄與向量交接包（git 追蹤 9 檔：
│                                 #   furniture/ 2 JSON、RAG/ bge-m3 embeddings jsonl、manifests/）
├── rag/                          # 離線 RAG 資料集管線（git 追蹤 28 檔：vlm_annotation/、
│                                 #   rag_pipeline/、rendering/、json_adjustment/、docs/）
├── training/                     # 辨識訓練/評估素材（git 追蹤 68 檔：scripts/、tests/ 11 支、
│                                 #   json/eval_rooms、door_lib.npz）
├── docs/                         # 契約 22 檔、owners 7 檔、vibecoding、vibecoding-v5 等
├── examples/                     # demo_agent_flow.py + demo_app/（已退役示範）
├── frontend3d/                   # Bella：React Three Fiber DXF 檢視器（次要原型，Vite）
├── scripts/                      # Kai：型錄管線 + PostgreSQL 匯入
│   ├── sql/                      # Phase 1/2/5 schema 與匯入器
│   ├── project_store/            # Phase 3 專案保存 schema 與 SQLite 遷移器
│   └── runtime_catalog/          # Phase 4 runtime catalog schema 與匯入器
├── testdata/                     # 平面圖測試素材，6 子目錄（括號為頂層項目數，非遞迴檔數）：
│                                 #   Asset(5)/color_png(28)/dxf(78)/Identify_ans(6)/pic(8)/png(38)
├── tests/                        # 99 支 test_*.py（扁平）+ conftest.py + static/（JS 測試）
├── .claude/skills/               # 4 支專案原生 skill（git 追蹤 14 檔）：roompilot-security/
│                                 #   furniture-query/proposal/budget
├── .runtime/                     # 執行期資料（gitignore）：projects.sqlite3、uploads/、
│                                 #   renders/、engineering/、auth_secret.key、
│                                 #   indexes/questionnaire_visuals.sqlite3（問卷視覺索引，
│                                 #   可重建；建立點 main.py:276-279）
├── .env.example                  # 環境變數範本（有守約測試）
├── AGENTS.md                     # AI 協作規則：閱讀順序、跨資料夾格式、驗證矩陣
├── CLAUDE.md / MAIN_SYNC_TODO.md / design-qa.md
├── README.md                     # 安裝啟動 + 團隊合併規則 + 責任目錄表
├── LICENSE
├── pyproject.toml                # uv 專案定義（extras: server/vision/ocr/semantic/catalog）
├── requirements.txt              # 團隊 baseline（5 組 owner 分組、21 個 pin）
├── requirements-ocr.txt / requirements-rag.txt
└── uv.lock
```

另有未入版控的工作區殘留（`git ls-files` 為 0）：`VibeCoding_Workflow_Templates/`（本模板包原稿）、根目錄 `skills/`（skills CLI 的 node 專案）、`.claude_skills/`（skill 鏡像）、`.claude/` 下的社群 skill 目錄。舊導入版記載的 `backend/server/routes/`、`backend/server/storage/` 殘留目錄**已清除**（`ls` 回 No such file or directory）。

---

## 目錄用途與負責人

抄錄自 `docs/TEAM_AI_OWNERSHIP.md:19-34`（用途欄依現行程式碼補述）：

| 目錄 | 負責人 | 一句話用途 |
|---|---|---|
| `backend/server/` | Bella | FastAPI 應用：63 條路由、八步工作流、專案持久化、工程文件 MVP、靜態六頁 |
| `backend/floorplan/` | Cody | PNG/JPG/DXF → 牆/門/窗/房間辨識與 layout_json（24 支 .py，9,313 行） |
| `backend/upgrade3d/` | Cody | DXF 解析為 3D 幾何（305 行） |
| `backend/spatial_data/` | Django | 空間尺寸/相鄰/evaluation；現行主體為 `rag/` 家具 RAG runtime |
| `backend/catalog/` | Kai | 家具型錄、PostgreSQL 唯讀/管理/runtime repository、RAG adapter、擺放面分類 |
| `backend/agent/` | Yen | LLM 選件白名單閘與擺放失敗修復策略（不輸出座標） |
| `backend/engine/` | Ancai | 家具座標、碰撞與淨空（Shapely，全公分制，717 行） |
| `frontend3d/` | Bella（協作 Ancai） | React Three Fiber DXF 白模原型（次要原型，經 proxy 打 8002） |
| `tests/` | 各自負責 | 每位成員維護自己模組的測試 |
| `scripts/` | Kai | 型錄下載/清洗/上傳 + PostgreSQL 五階段 schema 與匯入 |
| `docs/contracts/` | Bella 整合 | 22 份契約檔（17 md + 1 yaml + 3 schema.json + 1 example.json） |
| `JSON/`、`rag/`、`training/` | Kai／Django／Cody+Ben | 型錄交接包／離線 RAG 資料集管線／辨識訓練評估 |

團隊 7 人（Bella、Cody、Django、Kai、Yen、Ancai、Ben），遠端分支對照見 `docs/TEAM_AI_OWNERSHIP.md:7-15`；owner 個人檔在 `docs/owners/{ANCAI,BELLA,BEN,CODY,DJANGO,KAI,YEN}.md` 共 7 份。

---

## 原始碼結構

不用 Clean Architecture 分層，實際依 import 方向由下而上（行數為 2026-08-04 `wc -l` 合計，排除 `__pycache__`）：

```plaintext
backend/
├── engine/          # 最底層純幾何，8 檔 717 行：models.py（Wall/Room/ClearanceZone/
│   │                #   FurnitureCatalogItem/PlacedFurniture）、geometry.py、clearance.py、
│   │                #   placement.py、adjustment.py、dxf_room.py、schema.py（介面 v0.1，
│   │                #   長度/座標一律 cm）
├── agent/           # 策略層，4 檔 1,045 行：select.py 617（LLM 只選件不捏造座標）、
│   │                #   place.py 285（重擺經注入的 engine_place_fn）、knowledge.py 132
├── catalog/         # 資料層，9 檔 3,199 行：postgres_repository.py 891（唯讀）、
│   │                #   postgres_admin_repository.py 764（交易式 CRUD + audit）、
│   │                #   runtime_catalog_repository.py 431（Phase 4 styles/surfaces/costs/
│   │                #   quarantine）、cloud_catalog.py 270、rag_repository.py 164
│   │                #   （pgvector adapter，BGE-M3）、style_db.py 208、
│   │                #   surface_material_processing.py 357、placement_surface.py 114
├── floorplan/       # 辨識層，24 檔 9,313 行：floorplan2dxf_color.py 1,966、
│   │                #   floorplan2dxf.py 1,588、floorplan2room.py 1,046、
│   │                #   cody_adapter.py 1,036、vision/ 15 檔 3,089 行、
│   │                #   symbol_match.py 277、room_classifier.py 138（DINOv2）
├── upgrade3d/       # 解析層，dxf_parser.py 305 行（classify/parse_dxf_file/
│   │                #   parse_dxf_bytes/list_plans）
├── spatial_data/    # 空間層，12 檔 1,236 行，主體 rag/：service.py 496（LLM parser →
│   │                #   pgvector → reranker）、model_runtime.py 163、ranking.py 154、
│   │                #   openai_parser.py 108 + anthropic_parser.py 64、settings.py 86、
│   │                #   models.py 84、vocab.py 26、data/{taxonomy,category_groups}.json
│   │                #   （6 風格、24 氛圍詞、19 家具群組）
└── server/          # 組裝層：main.py 3,695 行（46 條路由）+ 3 個 router（見下），
                     #   scene_service.py 2,445、project_store.py 620（SQLite）、
                     #   postgres_project_store.py 475（Phase 3）、render_providers.py 444、
                     #   catalog_admin.py 316、questionnaire_visuals.py 250、rag_api.py 197、
                     #   intake_service.py 171、render_service.py 158、cost_estimation.py 109、
                     #   runtime_paths.py 53、postgres_catalog.py 33、style_cards.py 27、
                     #   services/{cloud_models,cloud_images}.py、static/（前端）
```

### 路由組成（共 63 條）

數法見 `grep -rn '@(app|router)\.(get|post|…)' backend/server/ --include='*.py'` 逐條核對：

| 檔案 | 條數 | 掛載方式 |
|---|---|---|
| `main.py` | 46 | `@app.*`（無 APIRouter 拆分；另 2 個 StaticFiles mount：`/static`、`/docs-assets`，main.py:285-286） |
| `rag_api.py` | 5 | `include_router`（main.py:217），無 prefix：`GET /rag`、`GET /api/rag/status`、`POST /api/rag/search`、`POST /api/rag/search/jobs`（202）、`GET /api/rag/search/jobs/{job_id}` |
| `catalog_admin.py` | 4 | prefix=`/api/admin/furniture`（catalog_admin.py:29）：POST/GET/PATCH/DELETE |
| `engineering/api.py` | 8 | prefix=`/api/v1`（api.py:50）：health、snapshot PUT/GET、lock、engineering-packages（202）、jobs、packages、documents download |

### backend/server/engineering/ — 工程文件 MVP（舊導入版完全沒有的子系統）

契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`；14 支 .py 合計 3,111 行 + `workbook_builder.mjs`（Node XLSX adapter，node 路徑由 `ROOMPILOT_ARTIFACT_NODE` 指定）：

- `api.py` 361（8 條路由與 snapshot→lock→packages→jobs→documents 流程）、`repository.py` 515、`models.py` 421、`advanced_rag.py` 408、`rules.py` 281、`documents.py` 268、`schedule.py` 178、`knowledge.py` 176、`cost.py` 132、`orchestrator.py` 127、`export_contracts.py` 113、`quantity.py` 74、`narrative.py` 55、`__init__.py` 2。
- 知識庫在 `backend/catalog/data/engineering/`（work_items、material_catalog、price_records 等 14 項）；產出文件落在 `.runtime/engineering/`，下載端點有 `path.is_relative_to(root)` 路徑防護（api.py:295-303）。

### 主流程步驟（以程式碼為準）

- UI 進度列 **8 顆步驟按鈕**（`scene.html:25-32`）：1 建立專案 → 2 上傳平面圖 → 3 確定尺寸 → 4 空間與結構 → 5 需求問卷 → 6 配置與預覽 → 7 方案鎖定與視角 → 8 AI 渲染與成果包。
- 內部狀態機 **11 個 step**（`scene_workflow.js:4-16`，`WORKFLOW_SCHEMA_VERSION=2`）：`project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render`；calibration 與 recognition 共用 scale 面板（`WORKFLOW_PANEL_BY_STEP`，scene_workflow.js:18-30）。舊導入版寫「十步/11 步 UI」為過期事實。

### 規模參考（2026-08-04 `wc -l` 實測）

| 檔案 | 行數 | 說明 |
|---|---|---|
| `backend/server/static/scene_v2.js` | 13,803 | `/scene` 八步頁面主 bundle（匯入 23 支 scene_* 模組） |
| `backend/server/static/scene_viewer.js` | 5,555 | Three.js viewer（由 scene_v2.js import） |
| `backend/server/static/site.css` | 15,407 | 全站單一樣式表 |
| `backend/server/main.py` | 3,695 | 46 條路由與型錄載入 |
| `backend/server/scene_service.py` | 2,445 | 場景生成與擺位編排 |

static/ 共 1,031 檔（png 886、jpg 69、js 64、html 6、css 2、wasm 1 等）；HTML 六頁：index、styles、library、scene、rag（RAG 測試台）、engineering（工程估算與文件生成）——後兩頁為舊導入版沒有的新頁。vendor/ 自帶 Three.js 與 draco，無 CDN 依賴。

---

## pyproject.toml 與 uv 工作流

`pyproject.toml` 實際內容（2026-08-04）：

- 專案 `roompilot-agent` 0.1.0，`requires-python >= 3.12`，核心依賴只有 `shapely>=2.1.2`。
- optional extras **五組**（舊導入版只有四組，`semantic` 為新增）：
  - `server`：fastapi、uvicorn、pillow、ezdxf、python-multipart、httpx。
  - `vision`：numpy、opencv-python(<5)、ezdxf、svgpathtools、rapidocr-onnxruntime。
  - `ocr`：paddleocr、paddlepaddle（3.x，模型大、按需安裝）。
  - `semantic`：torch>=2.0、opencv-python-headless(<5)——房型 DINOv2 語意層；註解明言 OpenCV 5 改 HoughLinesP 回傳 shape 會壞門偵測，必須鎖 <5。
  - `catalog`：requests、selenium、webdriver-manager、tqdm、beautifulsoup4、sqlalchemy、psycopg2-binary、python-dotenv。
- `[dependency-groups] dev`：httpx + pytest>=9.1.1；`[tool.pytest.ini_options] pythonpath = ["."]`；`[tool.setuptools] packages = ["backend"]`。
- 另有 pin 死版本的團隊 baseline `requirements.txt`（5 組 owner 分組、21 個 `==` pin，2026-07-27 於 Windows + Python 3.12.13 驗證）與 `requirements-ocr.txt`、`requirements-rag.txt`。

常用指令（`README.md:30,35,44,46,77` 實查）：

```bash
# 安裝（網站後端；README.md:44 的日常開發組合）
uv sync --extra server --extra vision --extra catalog --group dev

# 啟動伺服器（port 不寫死在程式碼；README 基準 8002，被占用改 8023）
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload

# 跑測試（README.md:74-79「驗證指令」段實寫 .\.venv\Scripts\python.exe -m pytest -q；
# 下列 uv 等價寫法 README 未載明）
uv run pytest tests/ -q
```

`main.py` 無 `__main__` 區塊，必須經 uvicorn 啟動；執行期資料寫入 repo 根 `.runtime/`（projects.sqlite3、uploads/、renders/、engineering/、indexes/questionnaire_visuals.sqlite3、auth_secret.key），位置可用 `ROOMPILOT_RUNTIME_DIR` 覆寫（`backend/server/runtime_paths.py`）。

---

## 命名慣例（自現行程式碼與 AGENTS.md 歸納）

| 範疇 | 慣例 | 實例（repo 實測） |
|---|---|---|
| Python 模組 | `snake_case.py` | `scene_service.py`、`postgres_repository.py`、`workbook_builder.mjs`（唯一 Node 例外） |
| 測試檔 | `test_*.py`，扁平放 `tests/` | `test_rag_api.py`、`test_engineering_*.py`（共 99 檔） |
| 前端 JS | `snake_case.js`，場景模組加 `scene_` 前綴 | `scene_workflow.js` 等 scene_*.js 共 33 支 |
| API 路徑 | `/api/` 前綴；工程文件 API 另帶版次 `/api/v1` | `/api/rag/search`、`/api/admin/furniture`、`/api/v1/engineering/health` |
| JSON 欄位 | `snake_case` | `snapshot_completeness`、`approval_status`、`style_card_id` |
| 長度/座標欄位 | 一律公分、`_cm` 後綴；面積 `_m2`（AGENTS.md:50） | `width_cm`、`net_area_m2`；`backend/engine/schema.py` docstring 明定 cm |
| 錯誤碼字串 | 大小寫兩系並存：工程 API 用 SCREAMING_SNAKE、其餘用 snake_case | `SNAPSHOT_NOT_FOUND`、`REVISION_NOT_LOCKED`（engineering/api.py）；`rag_job_not_found`、`rag_job_capacity_reached`（rag_api.py） |
| 環境變數 | `ROOMPILOT_` 前綴；LLM 用 `OPENROUTER_` 前綴 | `ROOMPILOT_DEMO_MODE`、`ROOMPILOT_ARTIFACT_NODE`、`OPENROUTER_API_KEY`（.env.example 有守約測試） |
| Job ID | `job_` + uuid4 hex 12 碼 | engineering/api.py:199-215 |

---

## 測試結構

與模板的 unit/integration/features 分層不同，主測試樹採**扁平單層**，但已比舊導入版多出 conftest 與 JS 測試（2026-08-04 實查）：

```plaintext
tests/
├── conftest.py               # 全局 fixtures（舊導入版寫「無 conftest」已過期）
├── AGENTS.md                 # 測試目錄協作規則
├── test_*.py                 # 99 檔（find -maxdepth 1 實數）
└── static/                   # 前端 JS 測試：3 支 .test.mjs（page_boot_failure/
                              #   pending_actions/render_errors）+ 4 支 harness/stub
                              #   + package.json

training/tests/               # 另一測試樹：11 支 test_*.py + conftest.py（辨識訓練用）
```

- 命名即分域（依前綴粗分）：`test_scene_*` 26 支、postgres/catalog/cloud 資料層 15 支、floorplan/cody 辨識 10 支、`test_engineering_*` 7 支、`test_agent_*` 5 支、rag 3 支（`test_rag_api`/`test_rag_domain`/`test_rag_frontend`，`test_engineering_advanced_rag` 已計入 engineering）、cost_estimation 2 支、幾何 6 支（未查證：無穩定前綴可機械計數），其餘為契約守門（`test_env_example_contract`、`test_team_ai_guidance` 等）。
- 執行：`uv run pytest tests/ -q`（README.md:74-79「驗證指令」段實寫 `.\.venv\Scripts\python.exe -m pytest -q`，README 無「合併前必跑」字樣；跨類型最低驗證見 `AGENTS.md:64-72` 驗證矩陣）。本文撰寫時未全量實跑（未查證：現行全量綠燈數）；已知既有紅燈風險：`test_scene_v2_contract.py` 的內容雜湊守約——scene.html 引用 `scene_v2.js?v=sha256-27f24b6bede3` 但實算前 12 碼為 `7d938e1fdc28`，library.html 亦不符（`shasum -a 256` 實比）。
- 驗證矩陣 7 類見根目錄 `AGENTS.md:64-72`（Python 模組→`pytest -q`；靜態前端→JS 語法+契約測試+瀏覽器 QA；Catalog/SQL→dry-run+PostgreSQL view 檢查；React 原型→`npm ci && npm run build` 等）。

---

## 文檔結構

與模板的 adrs/design/images 不同，實際結構（2026-08-04 `ls docs/`）：

```plaintext
docs/
├── TEAM_AI_OWNERSHIP.md            # 負責人/分支/資料流 SSOT（Git author 不可單獨視為 owner）
├── RoomPilot_現行版本總覽.md        # 跨模組協作總覽
├── contracts/                      # 22 檔：17 .md + engineering_openapi.yaml +
│   │                               #   3 .schema.json + 1 example.json；含
│   │                               #   ENGINEERING_DOCUMENT_MVP、POSTGRESQL_* 五階段、
│   │                               #   POSTGRESQL_FURNITURE_RAG_RUNTIME、REMOTE_RENDER 等
├── owners/                         # 7 份 owner 個人檔（ANCAI/BELLA/BEN/CODY/DJANGO/KAI/YEN）
├── backlog/                        # 待辦文件
├── moodboard_assets/               # 文件用圖片資產
├── vibecoding/                     # 舊一代導入文件（01–17 平面結構，事實已過期）
├── vibecoding-v5/                  # 本文件所在：v5.0 階段式導入（00_meta～07_governance）
└── （其餘頂層 .md：使用者流程與系統架構圖、2D3D座標鏡像根因、BELLA_*、CODY_* 等）
```

`.gitignore` 陷阱（.gitignore:25-39 實查）：`docs/*` 預設全忽略，僅白名單豁免——`!docs/*.md`、`!docs/backlog/`+`*.md`、`!docs/contracts/`+`*.md`、`!docs/moodboard_assets/**`、`!docs/owners/`+`*.md`、`!docs/vibecoding/`+`*.md`、**`!docs/vibecoding-v5/**`（全收，含非 .md）**。`.claude/*` 忽略但 `!.claude/skills/` 例外（四支 roompilot-* skill 共 14 檔進版控）；`.mcp.json` 因含 API key 忽略；GLB/權重不進版控（AGENTS.md:60）。

模板 INDEX.md 指向的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/`：(未查證：來源不在 repo)。

---

## 演進原則

- 本結構以 `README.md` 團隊合併規則與根目錄 `AGENTS.md` 為準：每人只動自己的主要目錄；跨資料夾修改需填 6 欄記錄格式（AGENTS.md:20-28）；動手前 6 步閱讀順序（AGENTS.md:5-12）。
- 頂層結構或負責人目錄變更，必須同步更新 `README.md` 責任目錄表、`docs/TEAM_AI_OWNERSHIP.md` 與本文件；重大結構決策記入 `docs/vibecoding-v5/03_architecture/adr.md`（模板 03_architecture/adr）；正式契約變更走 `docs/contracts/`。
- 自舊導入版以來已修復：`backend/server/routes/`、`backend/server/storage/` 殘留目錄已清除；`main.py` 已拆出 rag_api/catalog_admin/engineering 三個 router。
- 已知待清理項（2026-08-04 現況事實，裁決待定）：
  - `scene.html`、`library.html` 的 `?v=sha256-` 內容雜湊與實檔不符（守約測試預期紅燈）；且雜湊機制不是全站統一——index/styles 仍用日期版本 token。
  - `backend/catalog/data/舊友：12種風格與JSON/` 歷史素材目錄仍在。
  - `frontend3d/README.md` 範例 port 8000 與 `vite.config.js` proxy 8002 不一致。
  - `docs/TEAM_AI_OWNERSHIP.md` 分支對照寫 `origin/kai-with-bellatest1`，但遠端實際無此分支（現有 `origin/kai`、`origin/kai-new`）。
  - 根目錄 `skills/`、`.claude_skills/`、`VibeCoding_Workflow_Templates/` 為未追蹤工作區殘留，去留待裁決。
  - `examples/demo_app/` 自述已退役。
- 一致性比嚴格遵守特定模式重要：新程式碼跟隨上方「命名慣例」表，而非引入第二套慣例。
