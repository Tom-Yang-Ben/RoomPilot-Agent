# 程式碼審查與重構指南 — RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 05_qa/code_review_and_refactoring.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本:** v2.0 | **更新:** 2026-08-04 | **狀態:** 活躍

本指南保留模板章節架構，慣例段落全部換成本專案現實。所有數字、路徑、行號均於 2026-08-04 對現行工作樹（django-skill @ a2179f7e）逐項以工具實查；查不到的標「(未查證)」。先行素材為舊導入版 `docs/vibecoding/11_code_review_and_refactoring_guide.md`（2026-07-26，bella-local 分支年代），其事實（44 條路由、2,796 行 main.py、「2 failed, 389 passed」基準）已全部過期，本文件不沿用。

相關文件：`docs/vibecoding-v5/00_meta/workflow_manual.md`（流程）、`docs/vibecoding-v5/04_design/api_design.md`（API 變更審查依據）、`docs/vibecoding-v5/05_qa/security_and_readiness.md`（安全專項，若已導入）、根目錄 `AGENTS.md`（驗證矩陣的權威來源）。

---

## 審查前檢查

- [ ] **程式碼可運行、測試通過**：自 repo 根執行 `.\.venv\Scripts\python.exe -m pytest -q`（README.md:77 的驗證指令，Windows PowerShell 寫法；macOS/Linux 等價指令 `.venv/bin/python -m pytest tests/ -q`。README.md:46 亦提供 `uv run` 版本，但本機未必裝有 uv——2026-08-04 本機 `which uv` 查無，直接用 `.venv` 可跑通全套）
- [ ] **工作區乾淨**：`git diff --check` 與 `git status --short`（根目錄 AGENTS.md:76-80 的最終整合指令三條）
- [ ] **符合專案風格規範**：本專案**沒有** linter/formatter 設定——repo 無 `ruff.toml`、`.flake8`、`.pre-commit-config.yaml`、`setup.cfg`，`pyproject.toml` 僅有 `[tool.pytest.ini_options]`（pyproject.toml:64，`pythonpath = ["."]`）與 `[tool.setuptools]`（pyproject.toml:67），無 `[tool.ruff]`/`[tool.black]`（2026-08-04 實測）。風格審查靠人工，依據為 README 共同規則與本指南檢查點
- [ ] **文檔已更新**：欄位或行為變更須同步 `docs/contracts/` 對應契約（現有 22 個檔案：17 個 .md、1 個 .yaml、3 個 .schema.json、1 個 example.json）；使用者可見流程變更須同步 `README.md` 與 `docs/RoomPilot_現行版本總覽.md`
- [ ] **已完成自我審查**：diff 只落在自己的責任目錄與對應測試（責任表見「審查重點 2」；跨目錄修改須依根目錄 AGENTS.md:20-28 填 6 欄記錄：主要 owner／協作 owner／修改檔案／改變的資料契約或流程／為何不能只在單一目錄完成／兩端驗證測試）

### 測試基準現況（2026-08-04 實測，django-skill @ a2179f7e）

`.venv/bin/python -m pytest tests/ -q` → **1 failed, 811 passed, 9 skipped, 7 warnings**（68.53s）。

- 唯一紅燈：`tests/test_scene_v2_contract.py::test_scene_entrypoint_cache_key_matches_bundle_content`——`scene.html` 引用 `scene_v2.js?v=sha256-27f24b6bede3`、`site.css?v=sha256-5693fe5d95c5`，但實算 sha256 前 12 碼為 `7d938e1fdc28` / `e362900c8195`（shasum 實測）。審查時遇紅燈先對照這份基準：**新變更不得增加新紅燈**；修這條紅燈本身也是待辦（見技術債 D-02）。
- 7 條 warning 中含 `main.py:2821/2831` 的 FastAPI `on_event` DeprecationWarning（見 D-06），以及 `catalog_admin.py:290` 與 engineering snapshot 測試的 Starlette `HTTP_422_UNPROCESSABLE_ENTITY` 棄用警告（新增債務 D-13）。
- 測試規模：`tests/` 共 **99** 支 `test_*.py`（`ls tests/test_*.py | wc -l`），另有 `tests/static/` 下 **3** 支 jsdom 行為測試 `.test.mjs`（page_boot_failure / pending_actions / render_errors；跑法 `npm test` = `node --test`，devDependency jsdom ^26，tests/static/package.json）。訓練用另一測試樹 `training/tests/` 有 11 支，不在主套件內。

常用指令：

```bash
.venv/bin/python -m pytest tests/ -q                    # 全套（合併前必跑；README 寫法為 .\.venv\Scripts\python.exe -m pytest -q）
.venv/bin/python -m pytest tests/test_scene_workflow.py tests/test_project_workflow_api.py tests/test_scene_v2_contract.py -q   # 網頁流程與專案恢復（README.md:91）
.venv/bin/python -m pytest tests/test_floorplan_vision.py tests/test_floorplan_vision_api.py -q   # 平面圖辨識（README.md:85）
cd tests/static && npm test                             # 前端 jsdom 行為測試
uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload   # 啟動伺服器（README.md:30/46；8002 被占用時改 8023，README.md:35）
```

---

## 審查重點

### 1. 程式碼品質

- **可讀性**：程式碼是否容易理解？
- **可維護性**：是否容易修改？
- **一致性**：是否遵循專案慣例？
- **複雜度**：複雜部分是否有文檔？

RoomPilot 檢查點（逐項查證）：

- **繁中失敗字串是對外契約**：引擎失敗訊息詞彙表在 `examples/demo_agent_flow.py` 檔頭 docstring；`tests/test_placement.py`、`tests/test_clearance.py` 斷言「物件超出空間範圍」「與牆體穿透」等完整字串（grep 實測命中）——**改字視同破壞性 API 變更**，須同步契約與測試。
- **單位一致性**：跨模組幾何一律公分，新欄位以 `_cm` 命名、面積 `_m2`（根目錄 AGENTS.md:50 不可違反契約；`backend/engine/schema.py` docstring 明定全長度/座標公分）。審查 diff 時任何裸的長度數字都要問單位。
- **邊界文檔化的正例**：`backend/agent/__init__.py` 檔頭 docstring 明定「本套件不碰網路，也不依賴」server、LLM 呼叫器與擺放函式由呼叫端注入——新模組應比照在 `__init__.py` 或檔頭寫清楚職責邊界。同型正例：`backend/catalog/placement_surface.py`（「只做分類，不做任何幾何決策」）、`backend/catalog/postgres_repository.py`（「FastAPI 不得為了 filter/count/facet/paginate 而載入完整型錄」）。
- **修正意圖寫進註解**：近期修債時把「為什麼以前是壞的」留在原地（正例：`main.py:3297` 布簾 GLB 缺檔說明、`scene_service.py:888` 擺放面單一事實宣告）。審查時鼓勵此風格，但要求敘述與現行行為一致。

### 2. 架構與設計

- **SOLID 原則**：是否遵循？
- **設計模式**：是否使用適當模式？
- **關注點分離**：職責是否明確劃分？
- **API 設計**：介面是否乾淨直覺？

RoomPilot 的「關注點分離」有明文規則，審查時逐條對照（責任表出處 `docs/TEAM_AI_OWNERSHIP.md:19-34`；**Git author 不能單獨視為 owner**，TEAM_AI_OWNERSHIP.md:3）：

| Owner | 主要目錄 | 職責 | Python 行數（2026-08-04 wc -l） |
| :--- | :--- | :--- | :--- |
| Bella | `backend/server/`（含 static/、engineering/） | FastAPI、八步流程、保存、正式 UI 整合 | main.py 3,695；scene_service.py 2,445；engineering/ 3,111（14 檔） |
| Cody | `backend/floorplan/`、`backend/upgrade3d/` | PNG/JPG/DXF → 牆門窗房間辨識；DXF→3D 幾何 | 9,313；305 |
| Django | `backend/spatial_data/`（含 rag/） | 空間尺寸與家具 RAG runtime | 1,236 |
| Kai | `backend/catalog/` | 家具型錄、PostgreSQL、CloudFront、隔離資料 | 3,199 |
| Yen | `backend/agent/` | LLM 選件與擺位紀律（不輸出座標） | 1,045 |
| Ancai | `backend/engine/` | 擺放、碰撞、淨空——幾何與規則唯一裁決者 | 717 |
| Ben | 辨識 QA / evaluation | 驗收與品質 | — |

- **座標紀律**：家具合法位置只由 `backend/engine/` 判定（AGENTS.md:55）；`backend/agent/place.py` docstring 明言「本模組絕不計算或修改座標」，重擺經注入的 `engine_place_fn`。審查時看到 agent 層或前端出現座標運算即退回。Graph RAG 只補強關係與證據，「Ancai 仍是幾何與規則的唯一裁決者」（TEAM_AI_OWNERSHIP.md:53）。
- **路由現況與擺放位置**：全站 HTTP 路由 **63 條** = `main.py` 46 + `rag_api.py` 5 + `catalog_admin.py` 4 + `engineering/api.py` 8（grep `@(app|router).(get|post|put|delete|patch)` 逐條核對）。**新子系統已走 APIRouter**：RAG（`rag_api.py:26`，無 prefix）、型錄管理（`catalog_admin.py:29`，prefix `/api/admin/furniture`）、工程文件（`engineering/api.py:50`，prefix `/api/v1`）——審查新端點時，**優先要求放進獨立 router，不再往 main.py 疊**；main.py 46 條既有路由維持現狀（見 D-01）。
- **新端點對照契約**：API 變更對照 `docs/contracts/` 22 檔中的對應契約；工程文件 API 另有 OpenAPI schema（`docs/contracts/engineering_openapi.yaml`）與三份 JSON Schema（project_snapshot / report_payload / risk_results）。路徑匹配順序注意：`GET /api/furniture/{furniture_id}/model`（main.py:3508）與 `GET /api/furniture/{name}`（main.py:3686）並存，依定義順序匹配。
- **工程文件子系統（新增，必審）**：`backend/server/engineering/`（14 個 .py 共 3,111 行 + Node adapter `workbook_builder.mjs`）實作 snapshot→lock→packages→jobs→documents 五段流程（契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md`）。審查重點：錯誤碼契約（422 PATH_PAYLOAD_MISMATCH、409 LOCKED_REVISION_CANNOT_BE_OVERWRITTEN / SNAPSHOT_SOURCE_REVISION_STALE / REVISION_NOT_LOCKED、404 五類（PROJECT_NOT_FOUND / SNAPSHOT_NOT_FOUND / JOB_NOT_FOUND / PACKAGE_NOT_FOUND / DOCUMENT_NOT_FOUND），engineering/api.py:118-348）；文件下載僅允許落在 `.runtime/engineering` 之下的實檔（`path.is_relative_to(root)` 防護，api.py:295-303）——任何動到下載路徑的 diff 必須保住這道防線。
- **RAG 子系統（新增，必審）**：`backend/spatial_data/rag/`（11 個 .py 共 1,234 行）經 `backend/server/rag_api.py` 曝露 5 條路由（`/api/rag/*` 4 條，另 1 條為頁面 `GET /rag`，rag_api.py:136）；非同步 job 有 `RAG_JOB_MAX_ACTIVE` 上限、超過回 429（rag_api.py:155-185）。審查重點：受控詞彙版本化（`rag/vocab.py`、`rag/data/taxonomy.json`：6 風格、24 氛圍詞；`category_groups.json`：19 群組）、就緒守門（embedding 模型快取缺失與 pgvector 空表都是 blocker，service.py:82-90）、typed errors（`rag/errors.py`）不得被吞成裸 500。
- **PostgreSQL 五階段（新增，必審）**：契約 `docs/contracts/POSTGRESQL_*.md`（Phase1 Read／Phase2 CRUD／Phase3 專案保存／Phase4 runtime catalog／Phase5 單一來源）對應 `scripts/sql/`、`scripts/project_store/`、`scripts/runtime_catalog/`。審查重點：Phase2 管理寫入必須走交易 + activation gate + 樂觀併發 + audit record（`backend/catalog/postgres_admin_repository.py`）；Phase4 strict 模式下不得靜默回退掃 JSON（`runtime_catalog_repository.py` 檔頭）；第 6 步家具以 PostgreSQL view `roompilot.furniture_catalog_current` 優先（AGENTS.md:56）。
- **主流程步驟序以程式碼為準**：唯一有序來源是 `backend/server/static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS`（11 個內部 step，UI 為 8 顆按鈕，scene.html:25-32）；伺服器端 `main.py:183` 的 `WORKFLOW_STEPS` 是 set，只驗名稱不驗順序（main.py:2050-2051）。涉及流程的變更不要沿用任何舊文件的步驟數字。

### 3. 效能與安全

- **效能**：是否有明顯瓶頸？
- **安全**：是否遵循安全最佳實踐？
- **資源使用**：記憶體/CPU 使用是否合理？
- **錯誤處理**：是否覆蓋邊界情況？

RoomPilot 現行機制（審查時確認變更未繞過）：

- **效能已有實績可對照**：`0c531ee1 perf(scene): 第 6 步單次操作 21.5 秒降到 0.2 秒——資產快取取代整場重建`、`d1b32c37 perf(scene): 快取上限照實際 GLB 尺寸下修，避免記憶體無限成長`（git log 實查）。改動 3D 資產載入或型錄快取路徑時，要求 diff 說明對這兩項的影響。
- **回應壓縮**：`GZipMiddleware(minimum_size=1024)`（main.py:215）——全 backend/server/ 僅此一個 middleware，**無 CORS、無認證/授權 middleware**（grep 零命中）。現況同源部署故未爆 issue；`.claude/skills/roompilot-security/SKILL.md` 明言「全端點無認證/授權、外部抓取無 SSRF 防護、DB 預設明文連線」——涉及新端點、上傳、URL 抓取、DB 查詢的 diff，審查時載入 `roompilot-security` skill 跑其 `audit.sh` 靜態稽核。
- **上傳防護**：平面圖副檔名白名單 `FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")`（main.py:164，於 main.py:2106 生效）；渲染 PNG 上限 `MAX_RENDER_BYTES = 20MB`（main.py:177）；工作流草稿上限 2MB（413 workflow_too_large，main.py:2087-2093）。
- **併發與版本衝突**：`PUT /api/projects/{id}/workflow` 支援 `expected_revision` 樂觀併發，衝突回 409 `project_revision_conflict`（main.py:2077-2085；`project_store.py:30` ProjectVersionConflict）。動到保存路徑的 diff 不得弱化此檢查。
- **個資**：遠端渲染 payload 送出前剝除 `PRIVATE_KEYS`（姓名/電話/Email 等，`backend/server/render_service.py:12`）。
- **Secrets**：`.env` 不入版控；`.mcp.json` 因含 API key 忽略（.gitignore:91）；金鑰全走環境變數。
- **資料隔離**：`backend/catalog/data/quarantine/`（sf3d_legacy、unmatched_cloud_furniture）不得被網頁、Agent 與 3D 場景使用（CLAUDE.md 禁令；`tests/test_cloud_quarantine.py` 防守，斷言 quarantined 家具不在 web model set）。
- **錯誤處理契約**：全域例外處理器把 `ProjectStoreUnavailable`→503（busy 附 Retry-After:2）、`RuntimeCatalogUnavailable`→503（區分 catalog_pool_busy / runtime_catalog_unavailable）（main.py:226-266）。新增依賴 PostgreSQL 的路徑必須沿用這兩類 typed 例外，不得回裸 500。

---

## 專案慣例：分支與 Commit

### 分支與整合規則（出處：README.md:277-297「版本控制與整合」，該節為 README 末節）

整合落點為 `bella` 分支，必須先建整合分支確認差異：

```powershell
git fetch origin
git switch bella
git pull --ff-only origin bella
git switch -c integration/<owner>-<feature>
git diff --name-status bella...origin/<owner-branch>
git log --oneline bella..origin/<owner-branch>
```

只移植責任範圍內、符合現行契約的 commit。禁止以整份 ours/theirs 覆蓋衝突、建立第二套 FastAPI、搬入完整舊前端或提交大型模型。不得提交：`.env`、`.runtime/` 專案資料、`.tmp/` 與快取、大型 GLB/圖片包/模型權重、未驗證的 catalog 或自動標註結果（README 明文清單）。

分支現況（2026-08-04 `git branch -a`）：本機 3 條（ben、django-skill、main）、遠端 17 條。注意 `docs/TEAM_AI_OWNERSHIP.md` 分支對照寫 `origin/kai-with-bellatest1`，但遠端實際無此分支（現有 kai 系為 `origin/kai`、`origin/kai-new`）——文件與遠端現況不一致（見 D-14）。

審查形式：repo 無 `.github/`、無 CI（2026-08-04 實測），沒有 GitHub PR 自動化。現行 code review = 整合者在 `integration/<owner>-<feature>` 分支逐 commit 人工檢視，整合實績見 `merge:` 前綴 commit（如 `5316bef5 merge: 整合 bella-test1`、`620698b9 merge: 整合 cody-dev`）。

### Commit 訊息慣例（2026-08-04 自 git log 全史歸納）

全史共 **251** 條 commit；**162** 條符合 Conventional Commits 前綴（`type[(scope)]:` 嚴格比對，type 見於 log：feat/fix/docs/doc/chore/refactor/test/perf），僅 **9** 條為早期繁中「類別：」格式（新增/修正/功能/整合），另有 `merge:` 前綴整合 commit 與少量自由格式。

**現行主流＝「英文 type(scope) + 繁中摘要」**，最近 40 條幾乎全數如此。例：

- `a2179f7e fix(skills): 報告文件補完整 HTML 骨架修亂碼,並重排版面配色`
- `ffd38968 refactor(scene): 擺放面分類收斂到型錄層,不再維護第二份型別名單`
- `0c531ee1 perf(scene): 第 6 步單次操作 21.5 秒降到 0.2 秒——資產快取取代整場重建`
- `e1e22ddf feat: 整合 Kai 的 PostgreSQL、家具 RAG 與工程報告功能`

scope 慣用值（log 實查）：scene / catalog / floorplan / agent / render / static / skills / deps / test。最低要求：新 commit 沿用「type(scope): 繁中摘要」；摘要不加句號；subject 要讓人不看 diff 也能猜中大意（本專案的好例子普遍把「症狀＋修法」寫進一句）。

---

## 重構時機

模板四條觸發訊號，對應本專案已查證的實例：

- **偵測到 code smells** → 見下節技術債清單（3,695 行 main.py、雙軌 cache key 機制等）
- **效能問題浮現** → 已有前例可循：第 6 步 21.5s→0.2s（`0c531ee1`）證明「先量測、後快取」路徑可行；新瓶頸浮現時比照辦理並在 commit 寫明數字
- **新增功能變得困難** → main.py 46 條路由單檔（整合時 `backend/server/` 是衝突熱區）；新子系統已示範解法：RAG / catalog admin / engineering 全走獨立 APIRouter
- **技術債累積過多** → 下節清單即現況；新增債務時同步登記到 `docs/backlog/`（現有 1 筆 `FLOORPLAN_DATASET_TUNING.md`）

---

## 既有技術債清單（2026-08-04 逐項對現行樹複查；編號沿用舊導入版以利追溯）

| 編號 | 位置 | 2026-08-04 現況 | 狀態 |
| :--- | :--- | :--- | :--- |
| D-01 | `backend/server/main.py` | 3,695 行（較 7/26 的 2,796 行再增），46 條路由 + 型錄快取 + 工具函式仍在單檔；但新子系統（rag_api / catalog_admin / engineering）已走 APIRouter，拆分模式已確立 | 持續（範圍縮小為存量） |
| D-02 | `tests/test_scene_v2_contract.py` 紅燈 | 剩 1 條紅燈：scene.html 的 scene_v2.js 與 site.css cache key 與實算 sha256 不符（27f24b6bede3 vs 7d938e1fdc28、5693fe5d95c5 vs e362900c8195）；歷史上已三度整批重算（`5986f659` 21 個、`979ef806` 31 個、`29d7160e` 還原），仍會過期 | 持續 |
| D-03 | `backend/server/static/scene.js` 死碼 | 已刪除（`7a799770 fix: …scene.js 死碼`；ls 確認檔案不存在） | **已解** |
| D-05 | 布簾 GLB 缺檔 | 已解：`_curtain_catalog_item()` 改為檔案不存在即回 None、列進 decor_summary.skipped（main.py:3291-3305，`02eb0d68`） | **已解** |
| D-06 | `main.py:2821/2831` | `@app.on_event("startup"/"shutdown")` 仍為棄用 API，本日 pytest 實跑仍出 DeprecationWarning | 持續 |
| D-07 | `main.py:150` | `DATASET_DIR = PROJECT_DIR / "dataset"` 指向的目錄用途為本機 IKEA GLB 備援（README 開頭明言「尚未完成…請勿在 .env 啟用本機模式」）；`_dataset_glb_lookup()` 已有 `exists()` 守門（main.py:326），缺目錄不會炸 | 降級為守門後殘留 |
| D-08 | 步驟數文件腐化 | README 與總覽已統一為「八步流程」（README.md:94、總覽:5），與 UI 8 顆按鈕一致；殘留：`frontend3d/README.md:15,22` 仍寫 port 8000，實際 `vite.config.js:8` 代理 8002 | 大致已解，剩 frontend3d |
| D-09 | 「舊友：12種風格與JSON」雙目錄 | 現行樹只剩 git 追蹤的「舊友」一份（ls 實測），`EXTERNAL_IMPORT_PATH` 指向它（main.py:149） | **已解**（單一副本） |
| D-11 | 6 風格 vs 12 profile | `surface_catalog.json` 的 `style_surface_profiles` 仍為 12 個舊 key；現行 6 風格 ID 中 cream/japanese/modern_minimal 查無 profile、落到 scandinavian fallback（main.py:542-544，python json 實測）。Phase 4 已建 SQL 表 `roompilot.style_surface_profiles`（runtime_catalog_repository.py:192），DB 內是否補齊 6 風格 (未查證) | 持續 |
| D-12 | 伺服器端步驟順序 | `PUT /api/projects/{id}/workflow` 仍只驗步驟名（main.py:2050-2051 `current_step not in WORKFLOW_STEPS` → 422），順序依賴僅前端強制；但已補樂觀併發（409）與 2MB 上限（413） | 持續（縮小） |
| D-13 | `catalog_admin.py:290` 等 | Starlette `HTTP_422_UNPROCESSABLE_ENTITY` 棄用警告（本日 pytest 實錄，另見 engineering snapshot 測試）；改用 `HTTP_422_UNPROCESSABLE_CONTENT` | **新增** |
| D-14 | `docs/TEAM_AI_OWNERSHIP.md` | 分支對照含 `origin/kai-with-bellatest1`，遠端實際無此分支 | **新增**（文件修正） |
| D-15 | cache key 手動維護 | `?v=sha256-` 內容雜湊全站雙軌：scene 系用 sha256 前 12 碼、index/styles 仍用日期版本（`site.css?v=20260708s` 等），且 repo 內查無自動重算腳本（grep 實測）——每次改 JS/CSS 都要手算，D-02 反覆復發的根因；`library.html` 的 `library.js?v=sha256-d3c2bcee981f` 亦與實算 `1c9375c972ad` 不符但**無測試防守** | **新增** |

（舊 D-04 floorplan 死碼與 D-10 `__pycache__` 孤兒殘留：本次未逐項複查，狀態 (未查證)；處理前先以 grep/ls 現勘。）

---

## 重構策略

| 策略 | 適用場景 | RoomPilot 現況實例（2026-08-04 已查證） |
| :--- | :--- | :--- |
| Extract Method | 函式過長，有可複用邏輯 | `main.py`（3,695 行）內的路由處理函式；先從已自成區塊的段落下手 |
| Extract Variable | 條件表達式過複雜 | `main.py:1598-1600` 家具列表篩選：取值→`_normalize_furniture_facet_value()`→`casefold()`→比較連寫在單行 `if` 且逐 facet 重複；可先抽具名變數再抽共用函式 |
| Replace Conditional with Polymorphism | 多重 if/switch | **已完成的正例**：擺放面分類原在 scene_service 維護第二份型別名單，`ffd38968` 收斂到型錄層單一事實（`scene_service.py:888` 註解、`backend/catalog/placement_surface.py`）——新分類需求照此模式進型錄層，不再開新 if 鏈 |
| Introduce Parameter Object | 參數過多 | `backend/floorplan/vision/analysis.py:435` `analyze_floorplan_image` 已增至 6 個 keyword-only 參數（filename/calibration_hint/ocr_observations/ocr_provider/geometry_observations/evaluation_reference_rooms） |
| Move Method | 方法在錯誤的位置 | `main.py:3547` 起註解明標「以下路由自原 app/backend/main.py 移植,供 frontend3d(React Three Fiber)使用」的舊 R3F 路由區塊（/api/plans、/api/plan、/api/upload 等 8 條），邊界最清楚，是拆 APIRouter 的首選 |

重構的守門規則（本專案特有）：

1. 失敗字串、payload 欄位名、`coordinate_unit`/`schema_version`、engineering 錯誤碼（REVISION_NOT_LOCKED 等）是對外契約，重構不得改變；改了就是破壞性變更，走契約同步流程。
2. 重構不得跨目錄責任線——例如把 `scene_service.py` 的擺位邏輯搬進 `backend/engine/` 前，須先與 Ancai 協調並依 AGENTS.md 跨資料夾格式記錄。
3. 每步重構後全套 pytest 對照「**1 failed, 811 passed, 9 skipped**」基準，不得新增紅燈。
4. 改任何 `backend/server/static/` 的 JS/CSS，必須同步重算 `?v=sha256-` cache key（前 12 碼），否則 D-02 紅燈擴散（`.gitattributes` 已強制 static 為 LF，`29d7160e`，跨 OS 雜湊才會一致）。

---

## PR 模板（本專案為「整合說明」）

現實：無 GitHub PR 自動化（無 `.github/`、無 CI），本模板供整合者在 `integration/<owner>-<feature>` 分支完成後，寫入 `merge:` commit 訊息或整合紀錄使用：

```markdown
## 摘要
[一句話：整合了誰的哪個責任範圍、解決什麼]

## 變更類型
- [ ] Bug 修復（commit 用 fix(scope):）
- [ ] 新功能（feat(scope):）
- [ ] 效能（perf(scope): 並附量測前後數字）
- [ ] 破壞性變更（失敗字串/payload 欄位/契約/錯誤碼；須同步 docs/contracts/）
- [ ] 文檔更新（docs:）

## 測試
- [ ] `.venv/bin/python -m pytest tests/ -q` 對照基準（1 failed, 811 passed, 9 skipped），無新增紅燈
- [ ] 受影響模組的測試檔單獨跑過（前端行為改動加跑 tests/static 的 `npm test`）
- [ ] 涉及靜態資源時：cache key 已重算並通過 test_scene_v2_contract.py

## 檢查清單
- [ ] diff 只落在該 owner 責任目錄與對應測試；跨目錄已填 AGENTS.md 6 欄記錄
- [ ] 公分契約：新欄位 `_cm`/`_m2`、payload 帶 `coordinate_unit: "cm"` 與 `schema_version`
- [ ] `docs/contracts/` 對應契約已同步（22 檔中的受影響者）
- [ ] 未帶入第二套 FastAPI、重複前端或大型模型；未提交 .env/.runtime/.tmp
- [ ] 隔離區 quarantine/ 未被任何執行路徑載入（test_cloud_quarantine.py 綠燈）
- [ ] 涉及端點/上傳/URL 抓取/DB 的變更已跑 roompilot-security skill 的 audit.sh
```

---

## 品質關卡

### 合併前（對應 README「版本控制與整合」與根目錄 AGENTS.md）

- [ ] `.venv/bin/python -m pytest tests/ -q` 無新增紅燈（現行基準 1 failed, 811 passed, 9 skipped, 68.53s）
- [ ] `git diff --check`、`git status --short` 乾淨（AGENTS.md:76-80 最終整合指令）
- [ ] 整合者逐 commit 檢視（`git diff --name-status bella...origin/<owner-branch>`、`git log --oneline bella..origin/<owner-branch>`），只挑責任範圍內變更
- [ ] 依 AGENTS.md:64-72 驗證矩陣選對驗證方式：Python 領域模組→`pytest -q`；FastAPI/保存→API 測試 + `pytest -q`；靜態前端→JS 語法 + 契約測試 + 瀏覽器 QA；平面圖辨識→`testdata/` vision/evaluation 測試；Catalog/SQL→dry-run + 契約測試 + PostgreSQL view 檢查；React 原型→`npm ci && npm run build`；文件→連結與指令可用性
- [ ] 目錄責任、公分契約、隔離區、PostgreSQL view 優先四條規則逐項核對（AGENTS.md:50-60 的 11 條不可違反契約）
- [ ] 同儕審核：無工具強制，依賴整合分支上的人工檢視；安全專項載入 `roompilot-security` skill（`.claude/skills/` 四支專案 skill 已進版控，`3b2438dd`；.gitignore:43-46 唯一例外 `!.claude/skills/`）

### 合併後（本專案無雲端部署，對應現實 = 組員同步驗收）

- [ ] 組員同步：停舊 uvicorn → `git fetch origin` → 切換整合分支 → `git pull --ff-only` → `git rev-parse --short HEAD` 核對版本 → `uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload` → 開 `/scene` 走八步流程
- [ ] `project_id` 綁各機本地 `.runtime/`，不能拿別台電腦的專案網址驗版本
- [ ] 「監控」的現實對應＝健康與狀態端點人工巡檢：`GET /api/health`（main.py:2533）、`GET /api/catalog/status`（main.py:2528）、`GET /api/render-provider/status`（main.py:2262）、`GET /api/scene/provider-status`（main.py:2837）、`GET /api/rag/status`（rag_api.py:141）、`GET /api/v1/engineering/health`（engineering/api.py:77，回報 snapshot store、demo_mode、知識庫數量與 xlsx adapter 狀態）；無外部監控與告警（現況）
