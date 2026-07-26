# 專案結構指南 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 08_project_structure_guide.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26(HEAD e48cd67)

> **版本:** v1.0 | **更新:** 2026-07-26

---

## 設計原則

- **按負責人目錄組織**:每位組員只修改自己的主要目錄與對應測試(README「共同規則」第 1 條);`backend/` 下一個子目錄對應一位負責人。
- **明確職責分層**:家具座標只能由 `backend/engine/` 計算;`backend/agent/` 只做選件與修復策略、不碰座標;`backend/server/` 負責串接但不複製其他人的演算法。
- **一致命名**:Python 模組 `snake_case.py`、測試 `test_` 開頭、跨模組長度欄位 `_cm` 後綴(詳見下方「命名慣例」)。
- **配置外部化**:環境變數統一 `ROOMPILOT_` 前綴(LLM 相關為 `OPENROUTER_` 前綴),`.env` 自 repo 根或 `backend/server/.env` 載入;平面辨識參數在 `backend/floorplan/config.ini`。
- **與模板的偏差**:本專案**不採用** `src/[app_name]/` 佈局,`backend/` 本身就是 Python 套件(`pyproject.toml` 設 `pythonpath = ["."]`);也不採用 Clean Architecture 的 domains/application/infrastructure 分層,改以「負責人模組 + 引擎/策略分離」組織,理由見 README 團隊合併規則。

---

## 頂層結構

以下為實際目錄樹(2026-07-26 實測,略去 `__pycache__`、`node_modules`、`.venv`、`.runtime`、gitignore 的大型資料內容):

```plaintext
RoomPilot-Agent/
├── backend/                      # Python 套件(唯一後端,無巢狀命名)
│   ├── agent/                    # 家具選件與擺放失敗修復策略(不算座標)
│   │   └── prompts/              # 版本化 LLM 提示參考(runtime 不載入)
│   ├── catalog/                  # 家具型錄:雲端 9,350 件母集合 + 風格 enrichment
│   │   └── data/                 # 型錄 JSON、manifests/、quarantine/(隔離區)
│   ├── engine/                   # 幾何擺放引擎:座標、碰撞、淨空(公分制)
│   ├── floorplan/                # PNG 平面圖辨識(Cody 管線)
│   │   └── vision/               # 分析管線 15 模組 + icon_templates/(6 類家具圖示)
│   ├── server/                   # FastAPI 應用:44 條路由全在 main.py
│   │   ├── data/                 # questionnaire_visual_catalog.json(問卷版本來源)
│   │   ├── services/             # cloud_models.py(CloudFront GLB 信任邊界)
│   │   ├── static/               # 4 頁 HTML + 33 支 JS + 圖片資產(共 468 檔)
│   │   ├── routes/               # ⚠️ 空目錄,僅剩 __pycache__ 殘留,勿引用
│   │   └── storage/              # ⚠️ 空目錄,僅剩 __pycache__ 殘留,勿引用
│   ├── spatial_data/             # 預留目錄,現況僅 .gitkeep,無任何程式碼
│   └── upgrade3d/                # DXF → 3D JSON 解析器(dxf_parser.py 單檔)
├── data/
│   └── dataset/                  # 1.3GB 本機資料集(gitignore,不進版控)
│                                 #   catalog_json/、floor_materials_pack_1+2/、
│                                 #   ikea_glb_db/(1,517 GLB)、style_rag/
├── docs/                         # 文件(docs/* 預設 gitignore,白名單豁免)
│   ├── backlog/                  # 待辦文件(現有 1 檔)
│   ├── contracts/                # 6 份正式契約
│   ├── moodboard_assets/         # 文件用圖片資產
│   ├── vibecoding/               # VibeCoding 模板導入文件(本檔所在)
│   └── RoomPilot_現行版本總覽.md  # 跨模組協作總覽
├── examples/                     # demo_agent_flow.py + demo_app/(已退役示範)
├── frontend3d/                   # React Three Fiber DXF 檢視器(Vite 子專案,11 檔)
│   └── src/                      # App/Scene/Furniture.jsx、snap.js 等 6 檔
├── scripts/                      # 型錄管線腳本(git 追蹤 8 檔;scripts/* 預設 gitignore)
│   └── sql/                      # PostgreSQL schema + 9,350 件匯入器 + README
├── testdata/                     # 平面圖測試素材:chk(21)/door(19)/dxf(30)/
│                                 #   pic(8)/png(23)/pngans(21)
├── tests/                        # 47 個 test_*.py,扁平結構,無 conftest.py
├── tmp/                          # 暫存(gitignore)
├── .gitignore                    # 注意 docs/*、scripts/* 全忽略+白名單豁免的陷阱
├── LICENSE
├── README.md                     # 安裝啟動 + 團隊合併規則 + 責任目錄表
├── pyproject.toml                # uv 專案定義(extras: server/vision/ocr/catalog)
└── uv.lock                       # uv 鎖定檔
```

另有未入版控的工作區殘留:`VibeCoding_Workflow_Templates/`(模板原稿)與 `backend/catalog/data/舊有：12種風格與JSON/`(untracked;git 內已有內容幾乎相同的「舊友：12種風格與JSON」目錄,兩者僅 README.md 不同,去留待裁決)。

---

## 目錄用途與負責人

負責人分工表抄錄自 `README.md`(團隊目錄與合併規則一節),用途欄依實際程式碼補述:

| 目錄 | 負責人 | 一句話用途 |
|---|---|---|
| `backend/floorplan/` | Cody | PNG 平面圖 → 牆/門/窗辨識與尺度推定(cody_adapter + vision/ 管線) |
| `backend/upgrade3d/` | Cody | DXF 解析為 3D JSON(圖層分類、牆體多邊形、公尺→公分輸出) |
| `backend/catalog/` | Kai | 家具型錄、AWS Manifest、CloudFront 交付與隔離資料(9,350 件正式集合) |
| `backend/spatial_data/` | Django | 房間長寬、面積、比例及尺寸標註(預留,現況僅 `.gitkeep`) |
| `backend/agent/` | Yen | 家具選件驗證(LLM 白名單閘)與擺放失敗修復策略 |
| `backend/engine/` | AN | 家具座標、碰撞與淨空檢查(Shapely 幾何,全公分制) |
| `backend/server/` | Bella | FastAPI 應用:44 條路由、十步流程、專案持久化(SQLite)、靜態四頁 |
| `frontend3d/` | Bella | React Three Fiber DXF 3D 白模檢視器(Vite,經 proxy 打 8002 後端) |
| `tests/` | 各自負責 | 每位成員維護自己模組的測試(README 共同規則第 1 條) |
| `scripts/` | Kai(型錄管線) | IKEA 下載、JSON 清洗、離線備援驗證、PostgreSQL 匯入(sql/) |
| `docs/` | 共同 | 總覽、6 份契約、backlog、VibeCoding 導入文件 |
| `testdata/` | 共同 | 平面圖辨識測試素材與標準答案 |
| `data/dataset/` | 各自下載 | 本機大型資料集(gitignore,各機器內容可能不同) |

---

## 原始碼結構

本專案不用 Clean Architecture 分層,實際分層邏輯如下(依 import 方向,由下而上):

```plaintext
backend/
├── engine/          # 最底層:純幾何。models.py 座標契約(公分、左下原點、
│   │                #   position=中心、rotation 逆時針度)、geometry.py 碰撞、
│   │                #   clearance.py 淨空、placement.py 擺放、dxf_room.py 單位邊界
│   │                #   (刻意不依賴 ezdxf/shapely 以外的重依賴,dxf_room 零依賴)
├── agent/           # 策略層:select.py(LLM 選件信任邊界)、place.py(失敗修復
│   │                #   迴圈,座標一律經注入的 engine_place_fn)、knowledge.py
│   │                #   (族系/副件/房型適配的宣告式知識,單一事實來源)
├── catalog/         # 資料層:cloud_catalog.py(9,350 件強制驗證)、style_db.py
│   │                #   (型錄 → 引擎 FurnitureCatalogItem 轉接、尺寸修補)
├── floorplan/       # 辨識層:floorplan2dxf.py(Cody 核心 PNG→DXF)、
│   │                #   cody_adapter.py、vision/(分析、確認閘、空間報告)
├── upgrade3d/       # 解析層:dxf_parser.py(DXF→3D,內部公尺、輸出附公分欄位)
└── server/          # 組裝層:main.py(全部 44 條路由,無 APIRouter 拆分)、
                     #   scene_service.py(場景生成與擺位編排)、project_store.py
                     #   (SQLite 持久化)、intake_service.py、render_service.py、
                     #   services/cloud_models.py、static/(前端)
```

### 主流程步驟(以程式碼為準)

步驟順序的唯一有序權威是 `backend/server/static/scene_workflow.js` 的 `WORKFLOW_STEPS`(第 4-16 行),共 11 個內部步驟;`backend/server/main.py` 的同名常數(第 113-125 行)是無序 set,只驗步驟名:

```plaintext
project → upload → recognition → calibration → space_confirmation
→ requirements → layout_2d → white_model_3d → realistic_3d
→ proposal_review → ai_render
```

UI 只顯示 10 顆步驟按鈕,因 `recognition` 與 `calibration` 共用同一個 scale 面板(`WORKFLOW_PANEL_BY_STEP`,scene_workflow.js 第 18-30 行)。任何文件寫「問卷在最前面」都是舊版錯誤:上傳與尺度確認在問卷(requirements)之前。

### 規模參考(2026-07-26 實測)

| 檔案 | 行數 | 說明 |
|---|---|---|
| `backend/server/main.py` | 2,796 | 全部路由(27 GET + 16 POST + 1 PUT)與型錄載入 |
| `backend/server/scene_service.py` | 1,872 | 場景生成、擺位編排、OpenRouter 場景規劃 |
| `backend/server/static/scene_v2.js` | 8,544 | `/scene` 十步驟頁面主程式(module,內容雜湊防快取) |

---

## pyproject.toml 與 uv 工作流

`pyproject.toml` 定義(實際檔案內容):

- 專案:`roompilot-agent` 0.1.0,`requires-python >= 3.12`,核心依賴只有 `shapely>=2.1.2`。
- optional extras 四組:
  - `server`:fastapi、uvicorn、pillow、ezdxf、python-multipart、httpx — 網站後端。
  - `vision`:numpy、opencv-python、ezdxf — PNG → DXF 平面辨識。
  - `ocr`:paddleocr、paddlepaddle(3.x)— 尺度文字 OCR,模型大、按需安裝。
  - `catalog`:requests、selenium、webdriver-manager、tqdm、beautifulsoup4、sqlalchemy、psycopg2-binary、python-dotenv — 型錄管線與 PostgreSQL 匯入。
- `[dependency-groups] dev`:httpx + pytest>=9.1.1。
- `[tool.pytest.ini_options] pythonpath = ["."]` — 因此測試直接 `import backend.…`,不需安裝套件本身。
- 鎖定檔為 repo 根 `uv.lock`。

常用指令(來源:README 與 pyproject):

```bash
# 安裝(網站後端)
uv sync --extra server

# 啟動伺服器(port 未寫死在程式碼;README 慣用 8002,被占用改 8010/8014)
uv run uvicorn backend.server.main:app --port 8002

# 跑測試(合併前必跑)
uv run pytest tests/ -q

# 離線備援包驗證(不需解壓)
uv run python scripts/verify_ikea_offline_backup.py <zip 路徑>
```

注意:`main.py` 無 `__main__` 區塊,必須經 uvicorn 啟動;執行期資料寫入 repo 根 `.runtime/`(projects.sqlite3、uploads/、renders/、indexes/),位置可用 `ROOMPILOT_RUNTIME_DIR` 覆寫(`backend/server/runtime_paths.py`)。

---

## 命名慣例(自現有程式碼歸納)

| 範疇 | 慣例 | 實例(repo 實測) |
|---|---|---|
| Python 模組 | `snake_case.py` | `scene_service.py`、`cloud_catalog.py`、`dxf_parser.py` |
| 測試檔 | `test_*.py`,扁平放 `tests/` | `test_agent_select.py`、`test_floorplan_vision.py`(共 47 檔,無 unit/integration 子目錄、無 conftest.py) |
| 前端 JS | `snake_case.js`,場景模組加 `scene_` 前綴 | `scene_workflow.js`、`scene_style_packs.js`(static 頂層 33 支 JS 多數屬此) |
| 目錄 | 小寫,必要時 `snake_case` | `spatial_data/`、`upgrade3d/`、`frontend3d/` |
| API 路徑 | `/api/` 前綴;多字段用 kebab-case;資源 ID 用 `{snake_case}` 路徑參數 | `/api/render-provider/status`、`/api/questionnaire/visual-catalog`、`/api/projects/{project_id}/render-jobs` |
| JSON 欄位 | `snake_case` | `expected_revision`、`style_card_id`、`placement_variant` |
| 長度/座標欄位 | 一律公分、`_cm` 後綴;面積維持 `_m2`(README 共同規則第 4 條) | `width_cm`、`room_depth_cm`、`net_area_m2`;`scene_service.py` 內 `_cm` 命中 163 處 |
| 既有例外 | AN/Yen 舊契約的 `width`、`depth`、`pos_x`、`pos_y` 暫不改名,但 payload 必帶 `coordinate_unit: "cm"` 與 `schema_version` | `backend/engine/schema.py`(`placed_to_dict`,schema_version 2.0) |
| 環境變數 | 專案自有的用 `ROOMPILOT_` 前綴;LLM 用 `OPENROUTER_` 前綴 | `ROOMPILOT_MODEL_DELIVERY_MODE`、`ROOMPILOT_RENDER_PROVIDER_URL`、`OPENROUTER_API_KEY`、`OPENROUTER_INTAKE_ENABLED`(grep 實測共 9 個 ROOMPILOT_* 與 7 個 OPENROUTER_*) |
| 錯誤碼字串 | `snake_case` 語意碼 | `project_revision_conflict`(409)、`unsupported_floorplan_type`(415)、`workflow_too_large`(413) |

---

## 測試結構

與模板的 unit/integration/features 分層不同,本專案採**扁平單層**:

```plaintext
tests/
└── test_*.py        # 47 檔,無子目錄、無 conftest.py
                     # pytest --collect-only 收集 392 個測試(2026-07-26 實測)
```

- 命名即分域:`test_agent_*`(選件/擺放/知識)、`test_floorplan_*`(辨識)、`test_scene_*`(場景系列)、`test_cloud_*` / `test_official_*`(型錄)、`test_placement` / `test_clearance`(引擎)等。
- 其中 23 檔 import `backend.server`,即近半測試直接打 FastAPI 層。
- 執行:`uv run pytest tests/ -q`(README 規定合併前必跑)。本文件撰寫時只實跑過 agent+engine 相關 6 檔共 62 個測試(62 passed);全量通過率(未查證,記憶口徑 7/24 曾 330 過/4 敗)。

---

## 文檔結構

與模板的 adrs/design/images 不同,實際結構:

```plaintext
docs/
├── RoomPilot_現行版本總覽.md   # 跨模組協作總覽;衝突優先序:測試 > 程式 > 契約 > 總覽
├── contracts/                  # 6 份正式契約(agent 前後端、型錄交付、家具工程規則、
│                               #   佈局評估 schema、遠端渲染、StylePack 渲染)
├── backlog/                    # 待辦(現有 FLOORPLAN_DATASET_TUNING.md 1 檔)
├── moodboard_assets/           # 文件圖片資產(伺服器掛載為 /docs-assets)
└── vibecoding/                 # VibeCoding 模板導入文件(01/02/03/04/06/08…)
```

⚠️ `.gitignore` 陷阱:`docs/*` 與 `scripts/*` 預設全忽略,僅白名單豁免(`docs/*.md`、`docs/backlog/*.md`、`docs/contracts/*.md`、`docs/moodboard_assets/**`、`docs/vibecoding/` 與 `docs/vibecoding/*.md`、`scripts/verify_ikea_offline_backup.py`、`scripts/sql/**`)。在 docs/ 或 scripts/ 下新增子目錄或非 .md 檔前,先確認 `.gitignore` 有對應豁免,否則檔案不會進版控。

---

## 演進原則

- 本結構以 README 團隊合併規則為準:每人只動自己的主要目錄;整合分支從 Bella 建立,不整支 merge 舊分支。
- 頂層結構或負責人目錄的變更,必須同步更新 `README.md` 責任目錄表與本文件;正式契約變更走 `docs/contracts/`。
- 已知待清理項(現況事實,裁決待定):
  - `backend/server/routes/`、`backend/server/storage/` 只剩 `__pycache__`,原始 `.py` 已刪,屬結構搬移殘留。
  - `backend/catalog/data/` 的「舊有：」「舊友：」近重複目錄(僅 README.md 不同,前者 untracked)。
  - `backend/server/main.py` 的 `DATASET_DIR` 指向 repo 根 `dataset/`(不存在),實際資料在 `data/dataset/`;cloudfront 模式下不影響執行。
  - `frontend3d/README.md` 內容過時(寫 port 8000 與舊路徑,與 vite.config.js 實際 proxy 8002 矛盾)。
  - `examples/demo_app/` 自述已退役,README 仍引用已廢除的 ControlNet 計畫。
- 一致性比嚴格遵守特定模式重要:新程式碼跟隨上方「命名慣例」表,而非引入第二套慣例。
