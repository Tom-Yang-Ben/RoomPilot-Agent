# WBS 開發計劃 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 16_wbs_development_plan_template.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 進行中

工作項推導依據:`docs/backlog/`(現有 1 檔)、六份正式契約(`docs/contracts/`)明文標註的「尚未接入」項、以及 repo 實測的未接線功能。程式碼內經 grep 全 repo 實測**沒有任何 `TODO`/`FIXME` 標記**(2026-07-26 實測),因此本計劃不含「程式內 TODO」來源的工作項。工時與日期凡 repo 無證據者一律留空或標(未查證),不推估。

---

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot-Agent(AI 室內風格與家具配置展示系統,`backend/server/main.py:144` FastAPI title) |
| **專案經理** | (未查證;README 僅定義目錄負責人制,無 PM 職稱。依團隊口述整合者為本顥,repo 內無此記載) |
| **技術主導** | 無單一技術主導;採目錄負責人制,見下表(出處:`README.md` 團隊目錄與合併規則) |
| **總工期** | (未查證;repo 無時程文件。成果發表日 8/20 依團隊口述,未查證) |
| **目前進度** | 整體百分比待補;可量測現況:pytest 392 collected → 389 passed / 2 failed / 1 skipped(2026-07-26 實測,見第 4 節) |

### 角色與職責

本專案不採模板的 PM/TL/PO/ARCH/QA 分工,改用 `README.md` 的六目錄負責人制(每人一個唯一主要目錄,合併時只挑責任範圍內 commit):

| 角色 | 負責人 | 職責(出處:`README.md` 負責人表) |
| :--- | :--- | :--- |
| 平面圖辨識 | Cody | `backend/floorplan/`、`backend/upgrade3d/`:PNG、DXF、牆與門窗辨識 |
| 家具型錄 | Kai | `backend/catalog/`:家具型錄、AWS Manifest、CloudFront 與隔離資料 |
| 空間資料 | Django | `backend/spatial_data/`:房間長寬、面積、比例及尺寸標註 |
| Agent 選件 | Yen | `backend/agent/`:家具選件與擺放失敗修復策略 |
| 擺放引擎 | AN | `backend/engine/`:家具座標、碰撞與淨空檢查 |
| 伺服器與前端 | Bella | `backend/server/`、`frontend3d/`:FastAPI、1–10 流程、2D/3D UI |

跨目錄整合、文件與里程碑追蹤:負責人(未查證,repo 無記載;下表以「整合者」代稱)。

---

## 2. WBS 結構

```
1.0 專案管理與規劃
├── 1.1 分支與合併治理(README 合併規則,現行)
├── 1.2 里程碑與時程管理(時程文件待補)
└── 1.3 跨模組裁決事項清單(見第 3 節標「待議」項)

2.0 系統架構與設計
├── 2.1 正式契約維護(docs/contracts/ 六份,現行)
├── 2.2 LAYOUT_EVALUATION_SCHEMA 正式 API 化設計(契約自標「尚未完整接入」)
└── 2.3 PostgreSQL 執行期接線設計(importer 已入庫,執行期未連線)

3.0 後端開發(按六模組負責人分組)
├── 3.1 Cody:平面圖辨識(backend/floorplan/ + backend/upgrade3d/)
├── 3.2 Kai:家具型錄(backend/catalog/)
├── 3.3 Django:空間資料(backend/spatial_data/)
├── 3.4 Yen:Agent 選件(backend/agent/)
├── 3.5 AN:擺放引擎(backend/engine/)
└── 3.6 Bella:FastAPI 伺服器(backend/server/)

4.0 前端開發
├── 4.1 主前端靜態頁(backend/server/static/,現行入口)
└── 4.2 frontend3d(React Three Fiber)去留裁決

5.0 測試與品質保證
├── 5.1 紅燈修復(現有 2 個 failed)
├── 5.2 平面圖辨識評估測試(docs/backlog/FLOORPLAN_DATASET_TUNING.md)
└── 5.3 覆蓋率量測(repo 尚無 coverage 設定)

6.0 部署與上線
├── 6.1 遠端渲染供應商設定(未設定時 API 回 503)
├── 6.2 CloudFront GLB 交付(現行,9,350 件)
└── 6.3 PostgreSQL 匯入與維運(scripts/sql/)

7.0 文檔與培訓
├── 7.1 既有文件矛盾修正(README 殘缺句、總覽步驟數矛盾)
└── 7.2 過時文件處置(frontend3d/README、examples/demo_app)
```

### 工作包統計

工時 repo 無證據,全部留空;狀態依 repo 實測。

| WBS 模組 | 總工時 | 已完成 | 進度 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| 1.0 專案管理 | | | 待補 | 合併規則已運作,時程文件缺 |
| 2.0 系統架構 | | | 待補 | 六份契約在庫;2.2、2.3 未動工 |
| 3.0 後端開發 | | | 待補 | 主流程可運作;各模組餘項見第 3 節 |
| 4.0 前端開發 | | | 待補 | 主前端現行;frontend3d 去留待議 |
| 5.0 測試品保 | | | 待補 | 389/392 綠,2 紅 1 略過(實測) |
| 6.0 部署上線 | | | 待補 | CloudFront 現行;渲染供應商未設定 |
| 7.0 文檔培訓 | | | 待補 | 已知矛盾點列於 7.1/7.2 |
| **合計** | | | **待補** | |

---

## 3. 詳細任務分解

依任務指引,以下按六模組負責人分組(對應 WBS 3.x),跨模組項列於其後。每項「依據」欄為 2026-07-26 於工作區實測的證據。狀態僅用:待辦/進行中/現行維護/待議(需跨模組裁決)。

### 模組 3.1:Cody — 平面圖辨識(`backend/floorplan/`、`backend/upgrade3d/`)

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.1.1 | 平面圖辨識資料集調校:蒐集合法授權平面圖、固定訓練/驗證/測試切分、建立基準結果與失敗案例分類 | Cody | | 待辦 | | - | `docs/backlog/FLOORPLAN_DATASET_TUNING.md` 狀態明標「待執行」,承接舊 FV-07 |
| 3.1.2 | 五項評估指標實作:比例尺誤差、牆體拓樸、門窗 precision/recall/F1、房間語意正確率、流程成功率 | Cody | | 待辦 | | 3.1.1 | 同上文件「評估項目」1–5 條 |
| 3.1.3 | 門開向判定:自動路徑產出的 `opening_direction` 一律 `manual_review`,無實際方向值 | Cody | | 待辦 | | - | `backend/floorplan/cody_adapter.py:208,646` 實測;僅 golden match 或手動幾何有方向 |
| 3.1.4 | 辨識通用化:移除或參數化針對特定圖面的硬編碼過濾帶(右側 76% 寬、35%–78% 高的註記帶排除) | Cody | | 待辦 | | 3.1.2 | `cody_adapter.py:282-287,370-377` 實測硬編碼常數 |
| 3.1.5 | PaddleOCR 接線裁決:`ocr.py` 的 `default_ocr_provider` 全 repo 無呼叫者,`/api/floorplan/analyze` 內 provider 硬寫 `None` | Cody | | 待議 | | - | grep 全 repo 無呼叫者;`backend/server/main.py:2724` 附近 `provider = None` 實測 |
| 3.1.6 | 死碼清理:`vision/geometry.py` 的 `detect_geometry`(opencv_geometry 路徑)無任何呼叫者 | Cody | | 待議 | | - | grep backend/ + tests/ 零命中(不排除 repo 外系統使用,故標待議) |
| 3.1.7 | DXF 比例尺限制標註:無 `$INSUNITS` 且無手動比例時長邊正規化為 12 公尺,非真實尺寸,對外需明示 | Cody | | 待辦 | | - | `backend/upgrade3d/dxf_parser.py:30` `DEFAULT_SPAN = 12.0` 與 `:147` `"normalized"` 實測 |

**模組小計**:工時待補 | 進度:待補

### 模組 3.2:Kai — 家具型錄(`backend/catalog/`)

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.2.1 | 官方雲端型錄整合與加固(9,350 件 + manifest 驗證) | Kai(目錄負責人;commit 提交者為 Bella,git log 實測) | | 已完成 | 2026-07-26 | - | commit 83b3c8a、e48cd67(`git log` 實測);`build_official_catalog` 強制 9,350 件驗證 |
| 3.2.2 | 重複目錄裁決:「舊有:12種風格與JSON」(untracked)與「舊友:12種風格與JSON」(git 追蹤)僅 README.md 不同,擇一保留 | Kai | | 待議 | | - | `diff -rq` 實測僅 README.md 差異;`main.py:100` `EXTERNAL_IMPORT_PATH` 指向「舊友」版 |
| 3.2.3 | 表面型錄風格對齊:`surface_catalog.json` 的 `style_surface_profiles` 為 12 個舊風格 key,與家具 6 風格 ID 不一致,查無 profile 時 fallback `scandinavian` | Kai | | 待辦 | | - | 實測 profiles 共 12 key;`main.py:424-428` `_style_surface_profile` fallback 實測 |
| 3.2.4 | 隔離區治理:1,514 件無法映射舊資料維持隔離,不得進入網頁/Agent/3D | Kai | | 現行維護 | | - | `quarantine/unmatched_cloud_furniture/` 實測 count=1514;`tests/test_cloud_quarantine.py` 守護 |
| 3.2.5 | AWS 端型錄補齊:`/api/catalog/status` 中 surfaces provider=`local_pending_aws_manifest`、doors provider=`procedural_pending_aws_catalog`(count=0) | Kai | | 待辦 | | - | `main.py:1918,1923` provider 字串實測 |
| 3.2.6 | 離線備援包維運:IKEA zip(1,517 GLB、1,508 件可用)驗證流程與 SHA-256 核對 | Kai | | 現行維護 | | - | `README.md:228-244` 與 `scripts/verify_ikea_offline_backup.py`(git 追蹤)實測 |

**模組小計**:工時待補 | 進度:待補

### 模組 3.3:Django — 空間資料(`backend/spatial_data/`)

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.3.1 | 空間計算模組落地:目錄現況僅 `.gitkeep`,無任何程式碼;尺寸標註與確認現由整合前端處理 | Django | | 待辦 | | - | `ls backend/spatial_data/` 實測僅 .gitkeep;`docs/RoomPilot_現行版本總覽.md:160-161` 明標「尚未放入獨立 Python 空間計算模組」 |
| 3.3.2 | 模組範圍界定:房間長寬、面積、比例及尺寸標註的職責與 `backend/floorplan/vision/spatial_report.py` 現有功能如何分工 | Django | | 待議 | | 3.3.1 | README 負責人表 vs `spatial_report.py` 已實作房間尺寸/面積計算(實測存在) |

**模組小計**:工時待補 | 進度:待補

### 模組 3.4:Yen — Agent 選件(`backend/agent/`)

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.4.1 | 風格推薦與材質編輯:提示規格已寫入版本化參考文件,但明標為目標行為,無對應程式與測試 | Yen | | 待辦 | | - | `backend/agent/prompts/ROOMPILOT_LLM.md:14`:「target behavior unless corresponding code and tests exist」實測 |
| 3.4.2 | `placement_hints()` 接線裁決:函式僅測試使用,正式流程(`backend/server/`)無呼叫點;`main.py:748` 的 `"placement_hints": {}` 為資料欄位名,非函式呼叫 | Yen | | 待議 | | - | grep 實測:呼叫者僅 `tests/test_agent_place.py` |
| 3.4.3 | 選件與失敗修復迴圈維護(`resolve_placements` 三輪修復、保護件 escalate) | Yen | | 現行維護 | | - | `backend/agent/place.py` 實作;agent 三測試檔(test_agent_place 11 項、test_agent_knowledge+test_agent_select 21 項)共 32 項通過(2026-07-26 collect 實測,含在 389 passed 內) |

**模組小計**:工時待補 | 進度:待補

### 模組 3.5:AN — 擺放引擎(`backend/engine/`)

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.5.1 | 佈局評估正式 API 化:`status`/`violations`/`warnings`/`score`/`validation_summary` 尚未成為正式 API,現行 `/api/scene/validate` 只回 `ok` 與 `reason` | AN(與 Bella 協作) | | 待辦 | | - | `docs/contracts/LAYOUT_EVALUATION_SCHEMA.md` 狀態節明標「提案契約,尚未完整接入 API」實測 |
| 3.5.2 | `adjustment.py` 接線裁決:`move_furniture`/`rotate_furniture`/`adjust_furniture` 在 `backend/server/` 無呼叫點,僅 `examples/demo_agent_flow.py` 使用;F6 拖曳驗證現走 `check_placement_with_clearance` | AN(與 Bella 協作) | | 待議 | | - | grep `backend/server/` 零命中實測 |
| 3.5.3 | LLM function-calling 工具定義去留:`schema.py` 的 `PLACE_FURNITURE_TOOL`/`ADJUST_FURNITURE_TOOL` 標註 v0.1 草案,`backend/server/` 無引用 | AN | | 待議 | | - | grep 實測引用者僅 `examples/demo_app/agent_stub.py` 註解 |
| 3.5.4 | 幾何/碰撞/淨空引擎維護(公分制、Shapely 多邊形) | AN | | 現行維護 | | - | `backend/engine/` 8 檔實作;`tests/test_placement.py`、`test_clearance.py` 通過(含在 389 passed 內) |

**模組小計**:工時待補 | 進度:待補

### 模組 3.6:Bella — FastAPI 伺服器(`backend/server/`)

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 3.6.1 | 修復 2 個紅燈測試:`scene.html` 的 cache-busting 雜湊與 `scene_v2.js` 現行內容 SHA-256 不一致 | Bella | | 待辦 | | - | 2026-07-26 實測 `pytest tests/test_scene_v2_contract.py` 2 failed(`test_scene_entrypoint_cache_key_matches_bundle_content` 等 2 項) |
| 3.6.2 | 窗簾 GLB 缺檔:`/api/scene/decorate` 引用 `/static/models/roompilot-curtain.glb`,static/ 下實測 0 個 .glb;窗簾為固定假想品項不經型錄查找、不會觸發 409,而是瀏覽器載入 404 後由前端以同尺寸白色替代物兜底(409 `decor_model_missing` 屬燈/地毯/植栽等型錄角色查無 GLB 的情形) | Bella | | 待辦 | | - | `main.py:2440-2450` `_curtain_catalog_item` 與 `main.py:2409-2416` 409 路徑實測;`find backend/server/static -name '*.glb'` 為 0;`scene_viewer.js:2955-2957` 兜底實測 |
| 3.6.3 | 伺服器端步驟順序防護:`main.py` 的 `WORKFLOW_STEPS` 是無序 set 只驗步驟名,前置依賴僅前端 `REQUIRED_COMPLETIONS` 強制,伺服器無法阻止跳步驟寫入 | Bella | | 待辦 | | - | `main.py:113-125`(set)與 `static/scene_workflow.js:43`(REQUIRED_COMPLETIONS)實測 |
| 3.6.4 | `DATASET_DIR` 路徑修正:指向 repo 根 `dataset/`(不存在),實際 GLB 在 `data/dataset/`;cloudfront 模式不受影響,local 模式本機解析落空 | Bella | | 待辦 | | - | `main.py:101` 與 `ls dataset` No such file 實測 |
| 3.6.5 | 問卷選項圖片補齊:110 個選項圖中 8 個 `ready`、102 個 `planned`;圖片未完成的題目以文字選項作答 | Bella(圖片來源負責人未查證) | | 進行中 | | - | `backend/server/data/questionnaire_visual_catalog.json` 實測統計(55 題/110 圖) |
| 3.6.6 | `main.py` 拆分:單檔 2,796 行、44 條路由全在一檔,無 APIRouter | Bella | | 待議 | | - | `wc -l` 2796、`grep -c` 44 條實測;是否拆分屬技術債裁決 |
| 3.6.7 | 專案持久化與樂觀鎖維護(SQLite `.runtime/projects.sqlite3`、revision 409 衝突) | Bella | | 現行維護 | | - | `project_store.py` 實作;相關測試含在 389 passed 內 |

**模組小計**:工時待補 | 進度:待補

### 模組 4.0:前端開發

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 4.1.1 | 主前端 10 步流程維護(`/scene` 入口,`scene_v2.js` 8,544 行;內部 11 步,recognition 與 calibration 共用面板故 UI 顯示 10 顆按鈕) | Bella | | 現行維護 | | - | `static/scene_workflow.js:4-16` 11 步實測;`scene.html` 10 顆步驟按鈕 |
| 4.2.1 | frontend3d 去留裁決:後端 docstring 稱其為 retired R3F viewer,但 4 條移植路由(`/api/plans`、`/api/plan`、`/api/upload`、`/api/furniture/{name}`)與 `/api/furniture` 的 legacy `furniture` 鍵仍存活;`node_modules` 未安裝且 `npm install` ERESOLVE 失敗 | Bella | | 待議 | | - | `main.py:2072` `"Feed the retired R3F viewer"` 實測;`frontend3d/` 11 個 git 追蹤檔;路由清單見 12 §0/09 |

**模組小計**:工時待補 | 進度:待補

### 模組 5.0:測試與品質保證

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 5.1.1 | 紅燈歸零(現 2 failed,同 3.6.1) | Bella | | 待辦 | | 3.6.1 | 2026-07-26 全套 pytest 實測 |
| 5.2.1 | 平面圖評估自動化測試:不通過信心門檻仍要求人工確認的測試(backlog 驗收產物之一) | Cody | | 待辦 | | 3.1.2 | `docs/backlog/FLOORPLAN_DATASET_TUNING.md` 驗收產物節 |
| 5.3.1 | 覆蓋率量測導入:repo 無 coverage 設定(pyproject 無 pytest-cov,無 .coveragerc) | 整合者(未查證) | | 待辦 | | - | `grep pyproject.toml` 與 `ls .coveragerc` 實測 |

**模組小計**:工時待補 | 進度:待補

### 模組 6.0:部署與上線

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 6.1.1 | 遠端渲染供應商設定:`ROOMPILOT_RENDER_PROVIDER_URL/TOKEN` 未設定時 `/api/projects/{project_id}/render-jobs` 回 503,不得假成功 | Bella(供應商窗口未查證) | | 待辦 | | - | `main.py:1773`(503)/`1778`(502)實測;`docs/contracts/REMOTE_RENDER_CONTRACT.md` |
| 6.2.1 | CloudFront GLB 交付維運:9,350 件 manifest 驗證,預設 `cloudfront` 模式 | Kai | | 現行維護 | | - | `services/cloud_models.py` 與 manifest CSV 實測(9,350 列全 uploaded) |
| 6.3.1 | PostgreSQL 執行期接線:importer 與 schema 僅在 `scripts/sql/`,伺服器執行期(`backend/server/`)grep 無 psycopg2/postgres,型錄仍由 JSON+CSV 記憶體載入 | Kai(與 Bella 協作) | | 待辦 | | 2.3 | grep `backend/server/` 零命中實測;`scripts/sql/` 3 檔在庫 |

**模組小計**:工時待補 | 進度:待補

### 模組 7.0:文檔與培訓

| 編號 | 任務 | 負責人 | 工時 | 狀態 | 完成日期 | 依賴 | 依據 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 7.1.1 | 修正 README 殘缺句:「…不再建立\n不再保留舊版巢狀後端命名」語句接不上;`docs/RoomPilot_現行版本總覽.md:94-95` 有同樣殘缺 | 整合者(未查證) | | 待辦 | | - | `README.md:5-7` 實測 |
| 7.1.2 | 修正總覽步驟數矛盾:`docs/RoomPilot_現行版本總覽.md:12` 寫「固定為八個步驟」,緊接表格列 10 步;程式碼權威為 `scene_workflow.js` 11 內部步驟/10 顆 UI 按鈕 | 整合者(未查證) | | 待辦 | | - | 該檔 L12 與 L14-25 實測;`scene_workflow.js:4-16` 實測 |
| 7.2.1 | frontend3d/README.md 更新:寫後端 port 8000,實際 `vite.config.js` 代理到 8002 | Bella | | 待辦 | | 4.2.1 | `frontend3d/README.md:15,22` 與 `vite.config.js:8` 實測 |
| 7.2.2 | examples/demo_app 處置:main.py 自註「此 demo 已退役,僅供參考」,README 仍引用已廢除的 ControlNet 計畫;標示淘汰或移除 | 整合者(未查證) | | 待議 | | - | `examples/demo_app/main.py:26`、`README.md:11,35` 實測 |

**模組小計**:工時待補 | 進度:待補

---

## 4. 進度摘要

| 項目 | 當前值 | 目標值 |
| :--- | :--- | :--- |
| 整體進度 | 待補(repo 無進度追蹤文件) | 100% |
| 測試通過 | 389 passed / 2 failed / 1 skipped,共 392 collected(2026-07-26 `uv run pytest tests/` 實測,16.28s) | 全綠 |
| 程式碼覆蓋率 | 未量測(無 coverage 設定) | 待訂(模板預設 80%+,本專案未採納此門檻) |
| 開放 Bug | 已知 2 項:紅燈測試(3.6.1)、窗簾 GLB 缺檔(3.6.2) | 0 |
| 技術債項目 | 本文件標「待議」共 10 項(3.1.5、3.1.6、3.2.2、3.3.2、3.4.2、3.5.2、3.5.3、3.6.6、4.2.1、7.2.2) | 逐項裁決歸零 |

---

## 5. 風險管理

| 風險 | 可能性 | 影響 | 緩解策略 | 負責人 |
| :--- | :--- | :--- | :--- | :--- |
| 伺服器端不驗步驟順序,客戶端可跳步驟寫入工作流(`WORKFLOW_STEPS` 為 set) | 中 | 中 | 3.6.3:伺服器端補前置依賴驗證 | Bella |
| `/api/scene/decorate` 的窗簾 GLB 缺檔:瀏覽器載入必 404,前端以白色替代物顯示(不中斷,但畫面非預期材質) | 高(該路徑必觸發) | 低-中 | 3.6.2:補檔或改用型錄內既有 GLB | Bella |
| CloudFront 為 GLB 唯一交付來源,單點失效時 local 模式又因 `DATASET_DIR` 錯路徑落空 | 低 | 高 | 3.6.4 修路徑;離線備援包驗證流程(3.2.6)保持可用 | Bella/Kai |
| 表面型錄 12 舊風格 profile 與 6 風格 ID 不一致,未知風格靜默 fallback `scandinavian`,使用者不易察覺 | 中 | 中 | 3.2.3:建立 6→12 映射或改寫 profiles | Kai |
| 文件與程式矛盾(步驟數、殘缺句、過時 README)誤導新成員與整合 | 高 | 中 | 7.1.x/7.2.x 逐項修正;衝突時依總覽優先序「測試 > 程式 > 契約 > 總覽」 | 整合者(未查證) |
| `data/dataset/`(1.3GB)被 gitignore,各機器檔案數可能不一致,local 模式行為機器相依 | 中 | 低 | 維持 cloudfront 預設模式;離線包以 SHA-256 驗證 | Kai |
| 自動比例尺為推測值(DXF normalized 12m、PNG 門偵測系統性不可靠),尺寸精度風險 | 中 | 高 | 保留人工確認關卡(`scale_confirmation_required`);3.1.1/3.1.2 建立誤差基準 | Cody |
| `main.py` 單檔 2,796 行 44 路由,多人改動衝突面大 | 中 | 中 | 3.6.6 拆分裁決;現行以目錄負責人制降低跨人改動 | Bella |

---

## 6. 里程碑

repo 內無時程文件,日期欄除已發生事實外一律(未查證)或留空。

| 里程碑 | 預計日期 | 交付物 | 狀態 |
| :--- | :--- | :--- | :--- |
| M1: 官方雲端型錄整合 | (已發生)2026-07-26 | 9,350 件 catalog + manifest + PostgreSQL importer(commit 83b3c8a、e48cd67) | 完成(git log 實測) |
| M2: 紅燈歸零 + 已知缺檔修復 | 待補 | 全綠 pytest、decorate 流程可完整執行 | 待辦 |
| M3: 待議項逐項裁決 | 待補 | 10 項技術債的去留決議紀錄 | 待辦 |
| M4: 成果發表 | 2026-08-20(未查證,依團隊口述,repo 無記載) | 可展示完整 1–10 流程 | 待辦 |
