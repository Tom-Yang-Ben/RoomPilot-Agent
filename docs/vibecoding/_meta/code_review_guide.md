# 程式碼審查與重構指南 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 11_code_review_and_refactoring_guide.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 活躍

本指南保留模板的審查方法論,慣例段落全部換成本專案現實(指令、分支規則、commit 慣例、技術債均逐項以工具查證;查不到的標「(未查證)」或「待補」)。相關文件:`docs/vibecoding/_meta/workflow_manual.md`(Gate 與合併流程)、`docs/vibecoding/04_design/api_spec.md`(API 變更審查依據)、`docs/vibecoding/04_design/module_spec_engine.md`(契約式審查範例)。

---

## 審查前檢查

- [ ] **程式碼可運行、測試通過**: 自 repo 根執行 `uv run pytest tests/ -q`(README「合併前必須執行」;pytest 由 `pyproject.toml` `[dependency-groups] dev` 提供,`[tool.pytest.ini_options]` 設 `pythonpath = ["."]`,必須在 repo 根跑)
- [ ] **工作區乾淨**: `git diff --check` 與 `git status --short`(README 合併前指令)
- [ ] **符合專案風格規範**: 本專案**沒有** linter/formatter 設定——repo 無 `ruff.toml`、`.flake8`、`.pre-commit-config.yaml`、`setup.cfg`,`pyproject.toml` 亦無 `[tool.ruff]`/`[tool.black]`(2026-07-26 實測);風格審查靠人工,依據為 README 共同規則與本指南的檢查點
- [ ] **文檔已更新**: 欄位或行為變更須同步 `docs/contracts/` 對應契約(6 份);使用者可見流程變更須同步 `README.md` 與 `docs/RoomPilot_現行版本總覽.md`
- [ ] **已完成自我審查**: diff 只落在自己的責任目錄與對應測試(README 共同規則 1;目錄責任表見下節)

### 測試基準現況(2026-07-26 實測,bella-local-20260726;程式基準 e48cd67,其後 d88b707 僅導入 docs/vibecoding 文件,同日複測結果相同)

`uv run pytest tests/ -q` → **2 failed, 389 passed, 1 skipped**(13.53s,共收集 392 條)。

- 兩條既有紅燈都在 `tests/test_scene_v2_contract.py`:`scene.html` 對 `scene_v2.js` 的 sha256 內容雜湊快取鍵、以及 `scene_v2.js` 對 `scene_viewer.js` 的快取鍵,與現行檔案內容不符(JS 改過但雜湊查詢參數未重生)。審查時遇到紅燈先對照這份基準:**新變更不得增加新紅燈**;修復這兩條紅燈本身也是待辦。
- 2 條 warning 之一是 FastAPI `on_event` 的 `DeprecationWarning`(見技術債 D-06)。
- 本日在既有 `.venv` 直接跑通全套;該環境查無 `ocr`/`catalog` extras 套件(`uv pip list` 無 paddleocr/paddlepaddle/selenium/sqlalchemy/psycopg2,2026-07-26 實測)而全套仍綠,故 **全套測試的最低需求組合 = `dev` 群組(`uv sync` 預設安裝)+ `server` + `vision` 兩個 extras**;`ocr`/`catalog` 非測試必需。逐檔掃描 47 個測試檔的第三方 import:14 檔直接用到 extras 套件——11 檔僅涉 `server`,2 檔僅涉 `vision`(`test_floorplan_room_icons.py`、`test_floorplan_vision.py`),1 檔兩者皆涉(`test_floorplan_vision_api.py`);其餘 33 檔無直接第三方 import(可能經 `backend.server` 間接依賴 `server`)。新環境安裝指令:`uv sync --extra server --extra vision`(README 安裝指令為 `uv sync --extra server`,跑平面辨識測試須再加 `vision`)。

常用指令:

```bash
uv run pytest tests/ -q                      # 全套(合併前必跑)
uv run pytest tests/test_placement.py -q     # 單檔
uv run pytest tests/ --collect-only -q       # 只收集不執行
uv run uvicorn backend.server.main:app --port 8002   # 啟動伺服器(README)
```

---

## 審查重點

### 1. 程式碼品質

- **可讀性**: 程式碼是否容易理解?
- **可維護性**: 是否容易修改?
- **一致性**: 是否遵循專案慣例?
- **複雜度**: 複雜部分是否有文檔?

RoomPilot 檢查點(逐項查證):

- **繁中失敗字串是對外契約**:引擎的失敗訊息詞彙表定義在 `examples/demo_agent_flow.py` 檔頭 docstring(「物件超出空間範圍」「與牆體穿透」「與「X」重疊」「找不到合法擺放位置」等),`tests/test_placement.py`、`tests/test_clearance.py` 斷言完整字串——**改字視同破壞性 API 變更**,審查時要求同步契約與測試。
- **單位一致性**:跨模組幾何一律公分,新欄位以 `_cm` 命名,payload 帶 `coordinate_unit: "cm"` 與 `schema_version`;面積維持 `_m2`(README 共同規則 4)。審查 diff 時任何裸的長度數字都要問單位。
- **邊界文檔化的正例**:`backend/agent/__init__.py` 檔頭 docstring 明定「本套件不碰網路、不依賴 backend.server、不計算座標」——新模組應比照在 `__init__.py` 或檔頭寫清楚職責邊界。

### 2. 架構與設計

- **SOLID 原則**: 是否遵循?
- **設計模式**: 是否使用適當模式?
- **關注點分離**: 職責是否明確劃分?
- **API 設計**: 介面是否乾淨直覺?

RoomPilot 的「關注點分離」有明文規則(README 團隊目錄表與共同規則),審查時逐條對照:

| 負責人 | 唯一主要目錄 | 功能 |
| :--- | :--- | :--- |
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | PNG、DXF、牆與門窗辨識 |
| Kai | `backend/catalog/` | 家具型錄、AWS Manifest、CloudFront 與隔離資料 |
| Django | `backend/spatial_data/` | 房間長寬、面積、比例及尺寸標註 |
| Yen | `backend/agent/` | 家具選件與擺放失敗修復策略 |
| AN | `backend/engine/` | 家具座標、碰撞與淨空檢查 |
| Bella | `backend/server/`、`frontend3d/` | FastAPI、1–10 流程、2D/3D UI |

- **座標紀律**:家具座標只能由 `backend/engine/` 計算(README 共同規則 3);`backend/agent/` 只決定選品、順序與失敗修復策略(`backend/agent/__init__.py` docstring)。審查時看到 agent 層或前端出現座標運算即退回。
- **串接不複製**:Bella 可在 `backend/server/` 串接模組,但不複製其他人的演算法(README 共同規則 2)。
- **API 變更**:新端點對照 `docs/vibecoding/04_design/api_spec.md` 與 `docs/contracts/`。現況 44 條路由全部定義在 `backend/server/main.py`(45 個 `@app.` 裝飾器 = 44 路由 + 1 個 `on_event`,無 APIRouter 拆分,grep 實測);新增路由要注意路徑匹配順序,例如 `GET /api/furniture/{name}`(main.py:2787)與 `GET /api/furniture/{furniture_id}/model` 並存,依定義順序匹配。
- **主流程步驟序以程式碼為準**:唯一有序來源是 `frontend/scene_workflow.js` 的 `WORKFLOW_STEPS`(11 個內部步驟,UI 顯示 10 顆按鈕);伺服器端 `backend/server/main.py:113` 的 `WORKFLOW_STEPS` 是 set,只驗名稱不驗順序。審查涉及流程的變更時,不要沿用任何舊文件的步驟順序(舊文件有「八個步驟」殘留,見 D-08)。

### 3. 效能與安全

- **效能**: 是否有明顯瓶頸?
- **安全**: 是否遵循安全最佳實踐?
- **資源使用**: 記憶體/CPU 使用是否合理?
- **錯誤處理**: 是否覆蓋邊界情況?

RoomPilot 現行機制(審查時確認變更未繞過):

- **效能**:家具 catalog 在伺服器端建立記憶體快取,API 從快取搜尋、篩選與分頁(README;`main.py:2102` 的 startup 事件預熱 `_furniture_payload_cache()` 與 `build_site_payload()`)。改動型錄載入路徑時確認快取仍生效。
- **上傳防護**:平面圖副檔名白名單 `FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")`(main.py:111);渲染 PNG 上傳上限 `MAX_RENDER_BYTES = 20MB`(main.py:112)。
- **個資**:遠端渲染 payload 送出前剝除 `PRIVATE_KEYS`(姓名/電話/Email 等,`backend/server/render_service.py:12`)。
- **Secrets**:`.env` 不入版控(`.gitignore` 第 1 行);金鑰全走環境變數(`OPENROUTER_API_KEY`、`ROOMPILOT_RENDER_PROVIDER_URL/TOKEN` 等)。
- **資料隔離**:`backend/catalog/data/quarantine/unmatched_cloud_furniture/` 不得被網頁、Agent 與 3D 場景使用(README 共同規則 5;`tests/test_cloud_quarantine.py` 防守)。
- **已知空白**:全 `backend/` 無任何 CORS 或 middleware(grep `cors|add_middleware` 零命中,2026-07-26 實測)。現況同源部署(靜態頁由 FastAPI 直接掛載)故未爆issue;若未來前後端分離部署,此為必補項。

---

## 專案慣例:分支與 Commit

### 分支與合併規則(出處:README「團隊目錄與合併規則」)

整合落點為 `bella` 分支。不得把舊分支整支 merge 進 Bella,必須先建整合分支確認差異:

```powershell
git fetch origin
git switch bella
git switch -c integration/<name>-into-bella
git diff --name-status bella...origin/<member-branch>
git log --oneline bella..origin/<member-branch>
```

整合者只挑組員責任範圍內的 commit 或變更,再依正式契約修正 import、路徑與欄位。衝突時不能以整份 ours/theirs 覆蓋另一方,也不要帶入第二套 FastAPI、重複前端或整包大型模型。

路徑規則表(來源 → 合併落點,README 原表):

| 來源 | 合併落點 |
| :--- | :--- |
| `backend/floorplan/` | `backend/floorplan/` |
| `backend/upgrade3d/` | `backend/upgrade3d/` |
| `backend/catalog/` | `backend/catalog/` |
| `backend/agent/` | `backend/agent/` |
| `backend/engine/` | `backend/engine/` |
| `backend/server/` | `backend/server/` |
| `frontend/` | 第一階段不覆蓋正式網頁;靜態網站維持 `frontend/` |
| `data/dataset/` | 不搬大型 GLB;型錄 metadata 放 `backend/catalog/data/` |
| `data/testdata/` | `testdata/` |
| `Final-Project_Version3/` | 只移植空間邏輯到 `backend/spatial_data/` |

審查形式:repo 無 `.github/`、無 CI(2026-07-26 實測),沒有 GitHub PR 自動化;歷史上僅少量 GitHub PR(git log 有 `Merge pull request #1`–`#4`)。現行 code review = 整合者在 `integration/<name>-into-bella` 分支逐 commit 人工檢視。

### Commit 訊息慣例(2026-07-26 自 git log 全史歸納)

全史共 121 條 commit(含 7/26 導入本套文件的 `d88b707`),兩種風格並存:

1. **英文 Conventional Commits**:59 條(嚴格比對 `type[(scope)]: ` 前綴),type 見於 log:`feat`(20)/`fix`(19)/`docs`(9)/`chore`(5)/`refactor`(3)/`test`(2),另有 `doc` 單數變體(`04a1fbe`、`c2ece59`)。例:`e48cd67 fix(catalog): harden cloud database import`、`d97f95c refactor(engine): adopt centimeter contract`。
2. **繁中「類別:一句話」**:近期主要格式,全形冒號,類別詞見於 log:**新增/修正/功能/整合**,摘要不加句號。例:
   - `7fb3753 新增:依已確認房間預選共通問卷`
   - `6978f07 修正:需求問卷特殊選項卡住`
   - `6cf188b 功能:支援跨電腦匯入匯出專案`
   - `9aef367 整合:同步遠端 Bella 並保留 Codex 功能`
   - 更早也有無冒號直述句(`87b1876 修正房間輪廓異常岔出節點`)與自由格式,早期歷史不必回溯統一。

歸納(現況描述,非既有明文規定):同一週內兩種風格並存(7/26 的 `e48cd67` 英文 conventional 與 7/25 的 `7fb3753` 繁中);模組級/工程面變更偏英文 conventional,流程與 UI 面向團隊溝通的變更偏繁中「類別:摘要」。最低要求:單一整合批次內風格一致,繁中格式沿用上列四個類別詞。

---

## 重構時機

模板四條觸發訊號,對應本專案已查證的實例:

- **偵測到 code smells** → 見下節技術債清單(單檔 2,796 行的 `main.py`、無人引用的 `scene.js` 等)
- **效能問題浮現** → repo 文件內查無任何效能瓶頸紀錄(grep「效能瓶頸」/profiling 於 `docs/` 僅本檔自身命中,2026-07-26 實測);浮現時再登記
- **新增功能變得困難** → 44 條路由全擠在 `main.py`,任何路由變更都在同一檔案衝突(整合時 `backend/server/` 是衝突熱區)
- **技術債累積過多** → 下節清單即現況;新增債務時應同步登記到 `docs/backlog/`(現有 1 筆 `FLOORPLAN_DATASET_TUNING.md`)

---

## 既有技術債清單(全部逐項以工具查證,2026-07-26)

| 編號 | 位置 | 現況 | 處理方向 |
| :--- | :--- | :--- | :--- |
| D-01 | `backend/server/main.py` | 2,796 行單檔,44 條路由 + 型錄快取 + 工具函式全在其中,無 APIRouter 拆分 | 按資源拆 APIRouter(見重構策略) |
| D-02 | `tests/test_scene_v2_contract.py` 兩條紅燈 | `scene.html`/`scene_v2.js` 的 sha256 快取鍵與現行 JS 內容不符 | 重生內容雜湊查詢參數,恢復全綠 |
| D-03 | `frontend/scene.js` | 3,128 行舊版場景程式,`static/` 內無任何 HTML/JS 引用(grep 實測);現役入口為 `scene_v2.js`(8,544 行) | 確認無外部引用後刪除 |
| D-04 | `backend/floorplan/vision/geometry.py` 的 `detect_geometry`、`backend/floorplan/vision/ocr.py` 的 `default_ocr_provider` | `backend/` 與 `tests/` 皆無呼叫者(grep 實測),判定死碼;無法排除 repo 外系統使用 | 團隊確認後刪除或標記 deprecated |
| D-05 | `backend/server/main.py:2446` | 軟裝布簾引用 `/static/models/roompilot-curtain.glb`,但 `frontend/` 下找不到任何 `.glb`(find 實測 0 個) | 補檔或改走 CloudFront/移除假想品項 |
| D-06 | `backend/server/main.py:2102` | `@app.on_event("startup")` 為 FastAPI 已棄用 API,pytest 實跑出現 `DeprecationWarning`(本日實錄) | 改用 lifespan 事件 |
| D-07 | `backend/server/main.py:101` | `DATASET_DIR = PROJECT_DIR / "dataset"` 指向不存在的目錄(實際 GLB 在 `data/dataset/`,且 cloudfront 模式不走本機路徑) | 修正路徑或移除 local 模式殘留 |
| D-08 | `docs/RoomPilot_現行版本總覽.md:12`、`README.md:5-7`、`frontend3d/README.md:15,22` | 文件腐化:總覽寫「目前固定為八個步驟」但同檔表格與程式碼為 10 顆按鈕/11 內部步驟;README 開頭有殘缺句(「不再建立/不再保留舊版巢狀後端命名」接不上);frontend3d README 寫 port 8000,實際 `vite.config.js:8` 代理到 8002 | 逐處修正(文件變更,不影響程式) |
| ~~D-09~~ | ~~`backend/catalog/data/舊友：12種風格與JSON/` 與 `舊有：12種風格與JSON/`~~ | **已結案(2026-08-04 實測)**:「舊有：」目錄已不存在,磁碟上只剩「舊友：」一份 | 無需裁決。另注意 `quarantine/sf3d_legacy/` 與「舊友：」的同名檔案**不是**重複(3,055 對 1,509 筆,各有消費者),兩份 README 已互相註記 |
| D-10 | `backend/floorplan/__pycache__/`、`backend/upgrade3d/__pycache__/`、`backend/server/storage/` | 孤兒編譯殘留:`opening_classifier`/`room_analysis`/`seg_infer`/`vlm_judge`/`wall_openings` 的 `.pyc` 無對應 `.py`(ls 實測);`storage/` 目錄只剩 `__pycache__` | 清除 `__pycache__` 與空目錄 |
| D-11 | `backend/catalog/data/surface_catalog.json` + `backend/server/main.py:426-428` | `style_surface_profiles` 有 12 個舊風格 key;現行 6 風格 ID(`taiwan_style_cards.json`:american/cream/industrial/japanese/modern_minimal/scandinavian)中 3 個恰同名命中(american/industrial/scandinavian),另 3 個(cream/japanese/modern_minimal)查無 profile、落到 `scandinavian` fallback;repo 內無任何 6→12 映射程式(`_style_surface_profile` 直接以 ID 查 dict) | 補齊 cream/japanese/modern_minimal 的 profile 或建立映射;此不一致是否有意設計無法自 repo 斷定(`surface_catalog.json` 係整合 commit `b04833c` 整檔新增 21,876 行帶入,未查證) |
| D-12 | `backend/server/main.py:113` vs `frontend/scene_workflow.js:4` | 伺服器端 `WORKFLOW_STEPS` 是 set 只驗步驟名,步驟前置依賴僅前端強制——伺服器無法阻止跳步驟寫入 | 評估是否在 `PUT /api/projects/{id}/workflow` 補伺服器端順序驗證 |

---

## 重構策略

| 策略 | 適用場景 | RoomPilot 現況實例(已查證) |
| :--- | :--- | :--- |
| Extract Method | 函式過長,有可複用邏輯 | `backend/server/main.py`(2,796 行)內的路由處理函式;先從已自成區塊的段落下手 |
| Extract Variable | 條件表達式過複雜 | `backend/server/main.py:1184`/`:1186` 家具列表篩選的 color/material 條件:取值→`_normalize_furniture_facet_value()`→`casefold()`→比較全連寫在單行 `if`,且同型條件逐 facet 重複;可先抽出具名變數再考慮抽共用函式 |
| Replace Conditional with Polymorphism | 多重 if/switch | `backend/server/scene_service.py` 以類型集合分支決定擺放路徑:`_OVERLAY_TYPES`(:793)、`_IGNORE_COLLISION_TYPES`(:794),分支散在 :1201/:1204/:1210/:1304 |
| Introduce Parameter Object | 參數過多 | `backend/floorplan/vision/analysis.py:223` `analyze_floorplan_image` 有 5 個 keyword-only 參數(calibration_hint/ocr_observations/ocr_provider/geometry_observations/filename) |
| Move Method | 方法在錯誤的類別中 | `main.py` 拆 APIRouter;首選 `main.py:2656` 起註解明標「以下路由自原 app/backend/main.py 移植,供 frontend3d(React Three Fiber)使用」的舊 R3F 路由區塊,邊界最清楚 |

重構的守門規則(本專案特有):

1. 失敗字串、payload 欄位名、`coordinate_unit`/`schema_version` 是對外契約,重構不得改變(改了就是破壞性變更,走契約同步流程)。
2. 重構不得跨目錄責任線——例如把 `scene_service.py` 的擺位候選邏輯搬進 `backend/engine/` 前,須先與 AN 協調(座標計算本來就該在 engine,但搬移屬範圍變更)。
3. 每步重構後全套 pytest 對照「2 failed, 389 passed」基準,不得新增紅燈。

---

## PR 模板(本專案為「整合說明」)

現實:無 GitHub PR 自動化(無 `.github/`、無 CI),本模板供整合者在 `integration/<name>-into-bella` 分支完成後,寫入 merge commit 訊息或整合紀錄使用:

```markdown
## 摘要
[一句話:整合了誰的哪個責任範圍、解決什麼]

## 變更類型
- [ ] Bug 修復(commit 用「修正:」或 fix)
- [ ] 新功能(commit 用「新增:」「功能:」或 feat)
- [ ] 破壞性變更(失敗字串/payload 欄位/契約;須同步 docs/contracts/)
- [ ] 文檔更新(commit 用 docs 或直述)

## 測試
- [ ] `uv run pytest tests/ -q` 對照基準(2 failed, 389 passed),無新增紅燈
- [ ] 受影響模組的測試檔單獨跑過
- [ ] 涉及辨識/流程時手動驗收:上傳 floor04.png 應得 19 面牆、5 扇門、5 扇窗、7 個房間(README 驗收基準)

## 檢查清單
- [ ] diff 只落在該組員責任目錄與對應測試
- [ ] 公分契約:新欄位 `_cm`、payload 帶 `coordinate_unit: "cm"` 與 `schema_version`
- [ ] `docs/contracts/` 對應契約已同步
- [ ] 未帶入第二套 FastAPI、重複前端或整包大型模型
- [ ] 隔離區 `quarantine/unmatched_cloud_furniture/` 未被任何執行路徑載入
```

---

## 品質關卡

### 合併前(對應 README「合併方式」與共同規則)

- [ ] `uv run pytest tests/ -q` 無新增紅燈(現行基準 2 failed, 389 passed, 1 skipped)
- [ ] `git diff --check`、`git status --short` 乾淨
- [ ] 整合者逐 commit 檢視(`git diff --name-status bella...origin/<member-branch>`、`git log --oneline bella..origin/<member-branch>`),只挑責任範圍內變更
- [ ] 目錄責任、公分契約、隔離區三條規則逐項核對(見審查重點第 2、3 節)
- [ ] 同儕審核:無工具強制,依賴整合分支上的人工檢視;安全/生產準備專項檢查依 `docs/vibecoding/05_qa/security_and_readiness.md`(2026-07-26 與本檔同批導入,基於程式碼實查);效能專項審查仍無既定流程(待補)

### 合併後(本專案無部署,對應現實 = 組員驗收)

- [ ] 組員同步驗收(README「組員同步 Bella」):停舊 uvicorn → `git fetch origin` → `git switch bella` → `git pull --ff-only origin bella` → `git rev-parse --short HEAD` 核對版本 → `uv run uvicorn backend.server.main:app --port 8014` → 開 `/scene`
- [ ] 辨識基準:同版程式上傳 `floor04.png` 應為 19 面牆、5 扇門、5 扇窗、7 個房間;`project_id` 綁各機本地 `.runtime/`,不能拿別台電腦的專案網址驗版本(README 明文)
- [ ] 「監控」的現實對應:三個狀態端點 `GET /api/render-provider/status`(main.py:1751)、`GET /api/catalog/status`(main.py:1933)、`GET /api/scene/provider-status`(main.py:2111);無外部監控與告警(現況)
