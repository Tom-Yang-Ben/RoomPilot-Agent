# 文檔與維護指南 - RoomPilot-Agent

> 本文件由 VibeCoding v5.0 模板 07_governance/documentation_and_maintenance.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **版本：** v2.0（v5 導入版）| **更新：** 2026-08-04 | **狀態：** 活躍

**衝突優先序（全 repo 文件通用）**：文件與實際行為衝突時，依序以「自動化測試 > 可執行程式 > 正式契約（`docs/contracts/`）> 總覽文件」為準（出處：`docs/RoomPilot_現行版本總覽.md` 開頭：「若文件和程式衝突，依序以自動化測試、可執行程式、正式契約、本文件為準」）。本指南描述文件本身的角色、更新時機與版控規則，不覆寫上述優先序。

repo 現行入庫 Markdown 共 **103 個**（`git ls-files '*.md' | wc -l`），其中 `AGENTS.md` 12 個（根目錄 + backend 七模組 + frontend3d/scripts/testdata/tests；`git ls-files 'AGENTS.md' '*/AGENTS.md' | wc -l` = 12）。

---

## 1. 文檔類型

| 類型 | RoomPilot 實際載體 | 格式 |
| :--- | :--- | :--- |
| **API 文檔** | `docs/vibecoding-v5/04_design/api_design.md`；API 實體為 `backend/server/` 63 條路由（main.py 46 + rag_api.py 5 + catalog_admin.py 4 + engineering/api.py 8，grep 逐條核對）。工程文件 API 另有靜態 schema：`docs/contracts/engineering_openapi.yaml` 與 3 份 `*.schema.json`（project_snapshot / report_payload / risk_results）。`main.py:214` 建立 `FastAPI(title=...)` 未覆寫 `docs_url`，依 FastAPI 預設於執行期提供 `/docs` 與 `/openapi.json`（本次未啟動伺服器實測） | Markdown + OpenAPI YAML + JSON Schema |
| **架構文檔** | `docs/RoomPilot_現行版本總覽.md`（83 行，跨模組協作導航）、`docs/使用者流程與系統架構圖.md`（最後更新 2026-07-29）、`docs/vibecoding-v5/03_architecture/`（architecture_and_design / adr / project_structure）、`docs/vibecoding-v5/04_design/`（file_dependencies / class_relationships） | Markdown + Mermaid |
| **契約文檔** | `docs/contracts/` 共 **22 個檔案**（17 個 .md + 1 個 .yaml + 3 個 .schema.json + 1 個 example.json；`ls | wc -l` 實測）——模板原無此類型，RoomPilot 以契約取代零散介面說明。含新一代子系統契約：`ENGINEERING_DOCUMENT_MVP.md`（工程文件 MVP：snapshot→lock→packages→jobs→documents）、`POSTGRESQL_*` 七份（五階段 Phase1–5 + embeddings + RAG runtime） | Markdown / YAML / JSON Schema |
| **使用者/操作文檔** | `README.md`（297 行）：快速啟動（`uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload`，README.md:30、:46；8002 被占用改 8023，README.md:35）、驗證指令、八步流程、團隊責任、版本控制與整合 | Markdown |
| **開發者文檔** | 根 `AGENTS.md`（閱讀順序、跨資料夾修改格式、驗證矩陣 7 類——含「文件→連結與指令可用性」）、各目錄近端 `AGENTS.md`（12 個）、`docs/TEAM_AI_OWNERSHIP.md` + `docs/owners/` 7 份 owner profile、各模組 `README.md`（`backend/engine/`、`backend/catalog/data/`、`scripts/sql/` 等） | Markdown |
| **資料字典/政策** | `backend/catalog/data/engineering/DATA_DICTIONARY.md`、`PRICE_AND_PRODUCTIVITY_POLICY.md`、`README.md`（工程文件 MVP 的資料層文件，與 work_items/material_catalog/price_records 等 JSON 同目錄共版控） | Markdown |
| **Skill 文檔** | `.claude/skills/roompilot-*` 四支專案 skill 共 **14 個追蹤檔**（`git ls-files .claude/skills/` = 14）：security/furniture-query/proposal 各含 `SKILL.md` 與 references/ 說明檔，budget 只有 `SKILL.md` 與兩支腳本（`build_budget.py`／`verify_budget.py`），無 references/ | Markdown + 腳本 |

模板建議的「使用者教學（getting-started/tutorials）」獨立目錄現況無；操作說明集中在 README 與各頁 UI 本身。

---

## 2. 文檔即程式碼

### 目錄結構（2026-08-04 實測）

模板的 `docs/{api,architecture,guides,developer}/` 通用結構在本 repo 對應為：

```
docs/
├── RoomPilot_現行版本總覽.md      # 跨模組架構導航（README 管安裝啟動，本檔管協作與資料邊界）
├── TEAM_AI_OWNERSHIP.md           # 7 人團隊、遠端分支對照、14 列目錄責任表
├── 使用者流程與系統架構圖.md       # 使用者流程 + 系統架構圖（2026-07-29）
├── 2D3D座標鏡像_根因與修復方案.md  # 提案文件，自標「尚未動工」
├── BELLA_6_8_CONDENSED_FLOW_SPEC.md   # 第 6–8 步濃縮流程規格（自標「已定稿，尚未實作」）
├── BELLA_TEST1_INTEGRATION_LOG.md     # 整合紀錄（2026-07-27）
├── CODY_MAIN_SYNC_TODO.md / CODY_PIPELINE_README.md  # 自 origin/cody 收編，檔頭帶收編說明
├── contracts/                     # 22 檔正式契約（17 md + yaml + 3 schema.json + example.json）
├── backlog/                       # 已確認未完成工作（現 1 檔：FLOORPLAN_DATASET_TUNING.md）
├── owners/                        # 7 份 owner profile（ANCAI/BELLA/BEN/CODY/DJANGO/KAI/YEN）
├── moodboard_assets/              # 舊風格 moodboard 圖
├── vibecoding/                    # 舊一代模板導入（01–17 + INDEX + output_style，19 檔）
│                                  #   ⚠ 事實基準為 2026-07-26 舊分支（44 條路由年代），數字已過期
└── vibecoding-v5/                 # 本套件：v5.0 階段式模板導入（00_meta～07_governance）
```

模組層文件（docs/ 之外，`git ls-files '*.md'` 實列）：根 `README.md`、`MAIN_SYNC_TODO.md`、`design-qa.md`、`JSON/README.md`；`backend/` 各模組 README 與 AGENTS.md；`rag/`（Django 的 GLB 標註與 RAG 管線工作區）自帶 `README.md`、`SETUP.md`、`docs/`（GLB標註pipeline執行說明、RAG檢索系統說明、query_parser_spec）；`scripts/sql/` 含「PostgreSQL 17.10 安裝與資料匯入指南.md」。

### 各文件 SSOT 角色與更新時機（節錄重點）

| 文件 | SSOT 角色 | 更新時機 |
| :--- | :--- | :--- |
| `README.md` | 安裝、啟動（port 8002）、驗證指令（PowerShell 三連：pytest -q / git diff --check / git status --short，README.md:74-80）、整合流程與「不得提交」清單 | 啟動方式、依賴、整合規則變更時 |
| `docs/RoomPilot_現行版本總覽.md` | 跨模組協作、資料邊界、衝突優先序宣告 | 模組接入狀態或流程步驟變更時 |
| `docs/TEAM_AI_OWNERSHIP.md` | 目錄責任表（:19-34）、分支對照；明示「Git author 不能單獨視為 owner」（:3） | 分工或分支策略變更時 |
| `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md` | 八步工作流資料交換主契約（檔頭「最後更新：2026-08-02」） | 介面欄位或行為變更時，檔頭日期同步改 |
| `docs/contracts/ENGINEERING_DOCUMENT_MVP.md` | 工程文件 MVP（`backend/server/engineering/`：snapshot→lock→packages→jobs→documents）契約，owner Bella，配 `engineering_openapi.yaml` + 3 份 schema.json | 工程 API 或 payload 變更時，四類檔案一起動 |
| `docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1` ～ `SINGLE_SOURCE_PHASE5` | 家具/專案/runtime catalog 的 PostgreSQL 五階段契約；分別對應 `scripts/sql/`（Phase1/2/5）、`scripts/project_store/`（Phase3）、`scripts/runtime_catalog/`（Phase4） | 對應 schema/匯入器變更時，契約與 scripts 同 PR |
| `docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md`（+ `POSTGRESQL_FURNITURE_EMBEDDINGS.md`） | 家具 RAG runtime（`backend/spatial_data/rag/` 經 `rag_api.py` 掛 `/api/rag/*`）契約，owner Django | RAG 路由、詞彙表（taxonomy/category_groups）或 embeddings 變更時 |
| `docs/backlog/*.md` | 已確認要做但未完成的工作（現 1 筆） | 新債務確認時新增；完成時移除或併入契約 |
| `docs/vibecoding-v5/**` | 本套件：對現行工作樹逐條實查的流程/規格文件，檔頭固定帶基準分支、commit 與日期 | 對應主題重大變更時重新對齊 |
| `docs/vibecoding/01–17` | **歷史參考**：舊一代導入（基準 bella-local-20260726），路由數、步驟數等事實已過期，僅供章節結構參考，任何數字不可直接引用 | 不再更新；新事實一律寫入 vibecoding-v5 |
| `backend/catalog/data/README.md` | 正式家具集合邊界：「正式家具集合由以下兩個檔案一對一決定」；quarantine/ 兩子目錄（sf3d_legacy、unmatched_cloud_furniture）不得視為正式家具 | 型錄檔或映射規則變更時 |
| `backend/catalog/data/engineering/DATA_DICTIONARY.md` 等 | 工程文件 MVP 知識庫（work_items/材料/單價/工率/工序）的資料字典與單價政策 | 該目錄 JSON 資料變更時 |
| `.claude/skills/roompilot-*/SKILL.md` | 四支專案 skill 的觸發條件、邊界（如 proposal 不碰 `backend/server/engineering/`、budget 零 LLM 數字）與腳本用法 | skill 行為或腳本變更時（入庫起點：commit `3b2438dd`） |

### .gitignore 對文件的規則（.gitignore:26-39、:43-46 實測）

`docs/` 採「預設全忽略 + 白名單豁免」：

```gitignore
docs/*
!docs/*.md
!docs/backlog/          !docs/backlog/*.md
!docs/contracts/        !docs/contracts/*.md
!docs/moodboard_assets/ !docs/moodboard_assets/**
!docs/owners/           !docs/owners/*.md
!docs/vibecoding/       !docs/vibecoding/*.md
!docs/vibecoding-v5/    !docs/vibecoding-v5/**
```

- **地雷**：`docs/` 新子目錄若不在豁免清單內，git 會**默默忽略**（不出現在 `git status`）。新增文件類別必須同步加兩行豁免。注意 `vibecoding-v5` 用 `**` 全收（子資料夾與非 .md 都收），`vibecoding` 只收 `.md`。
- `docs/contracts/` 的 `.yaml`／`.schema.json`／`.json` **不在** `!docs/contracts/*.md` 豁免內，但已入庫（歷史上先 add 的檔不受 ignore 影響）；日後在 contracts/ 新增非 .md 檔需 `git add -f` 或補豁免規則（實測：`ls docs/contracts | wc -l` = 22 全數已追蹤）。
- `.claude/*` 忽略，唯一例外 `!.claude/skills/`（註解明言共用專案 skill 要進版控）；本機的 community-*/sunnydata-* skill 目錄與 `.claude/CLAUDE.md` 維持未追蹤（`git status` 實測）。
- AI 協作規則版本化：先 `AGENTS.md`（忽略）再負向收回 `!AGENTS.md`、`!CLAUDE.md`、`!backend/**/AGENTS.md`、`!frontend3d/AGENTS.md`、`!scripts/AGENTS.md`、`!testdata/AGENTS.md`、`!tests/AGENTS.md` 共 7 條路徑（.gitignore:62-69）。
- 個人生成文件不入庫：`PROJECT_CONTEXT.md`、`LOCAL_*/PRIVATE_*/PERSONAL_*` 各變體、`docs/MISSING_*_AUDIT_*.md`（:59）。
- `.mcp.json` 因含 API key 忽略；GLB/GLTF/HDR 等大型資產不入版控（`!backend/server/static/pbr_assets/**` 例外）。

### 文件命名慣例（自現況歸納）

| 位置 | 慣例 | 實例 |
| :--- | :--- | :--- |
| `docs/` 根層 | 中文描述性檔名，或「OWNER 大寫前綴 + 蛇形英文」的收編/規格檔 | `使用者流程與系統架構圖.md`、`BELLA_6_8_CONDENSED_FLOW_SPEC.md` |
| `docs/contracts/` | 全大寫蛇形英文 + 類型字尾（CONTRACT/RULES/SCHEMA/PHASE*）；schema 檔用小寫 `*.schema.json` | `POSTGRESQL_RUNTIME_CATALOG_PHASE4.md`、`report_payload.schema.json` |
| `docs/owners/` | 大寫人名 | `DJANGO.md` |
| `docs/vibecoding-v5/` | 兩位數階段資料夾 + 小寫蛇形英文，對齊 `VibeCoding_Workflow_Templates/` v5.0 目錄結構 | `07_governance/documentation_and_maintenance.md` |
| 模組目錄 | 一律 `README.md`／`AGENTS.md` 就地放在被說明的目錄內 | `backend/catalog/data/README.md` |
| vibecoding-v5 檔頭 | 首行 H1 + 固定引用註記「本文件由 VibeCoding v5.0 模板 … 導入 … | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04」+ 版本行 | 本檔與 `00_meta/workflow_manual.md` 第 1–5 行 |
| 收編文件 | 檔頭帶「收編說明（由主線整理者補充，非原文的一部分）」與原始來源分支 | `docs/CODY_MAIN_SYNC_TODO.md` 第 1–3 行 |

### 撰寫規範

- **簡潔明瞭**：直接切入重點；總覽只描述「可由程式、測試與正式資料庫核對的架構」（該檔開頭自述）。
- **主動語態**：「設定伺服器」而非「伺服器應被設定」。
- **包含範例**：指令必須可執行、數字必須可複測（如路由 63 條的 grep 數法、`docs/contracts/` 22 檔的 ls 數法）。
- **標示未接入/未動工**：提案文件自標狀態（`2D3D座標鏡像` 標「提案，尚未動工」；`BELLA_6_8` 標「已定稿，尚未實作」；`LAYOUT_EVALUATION_SCHEMA.md` 為目標契約），不得在 README 或總覽宣稱已完成。
- **版本控制**：契約檔頭維護「最後更新/更新日期」與 owner（如 AGENT_FRONTEND_BACKEND 2026-08-02、ENGINEERING_DOCUMENT_MVP 2026-07-29 owner Bella）；vibecoding-v5 檔頭維護基準分支 + commit + 日期。
- **查證紀律**：寫入路徑、路由、指令、數字前先用工具查證；查不到標「(未查證)」——本套件全數依此規則產出。

---

## 3. 維護排程

RoomPilot 是課程專題，無月/季營運節奏；模板的「每月/每季」對應為「每次合併節點/里程碑前」（事件驅動）。

### 每次合併前（對應模板「每月」）

- [ ] 欄位或行為變更是否同步 `docs/contracts/` 對應契約？檔頭「最後更新」是否更新？工程文件 API 變更是否同步 `engineering_openapi.yaml` 與 schema.json？
- [ ] 流程或接入狀態變更是否同步 `docs/RoomPilot_現行版本總覽.md` 與 `README.md`？
- [ ] 步驟描述以程式碼為準：唯一有序來源是 `backend/server/static/scene_workflow.js` 的 11 個內部 step（project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render，scene_workflow.js:4-16）；UI 顯示 8 顆步驟按鈕（scene.html:25-32）。
- [ ] 前端資產雜湊是否重算？`?v=sha256-<12 hex>` 為**手動維護**（無自動重算腳本，grep 實測），由 `tests/test_scene_v2_contract.py` 守約把關（見下表現行紅燈）。
- [ ] 新增文件是否落在 `.gitignore` 豁免範圍？（`git status` 看得到才算入庫）
- [ ] 文件內指令與數字是否仍可複測？（路由 63、契約檔 22、`tests/test_*.py` 99 支 + `tests/static/*.test.mjs` 3 支）
- [ ] 依根 `AGENTS.md` 驗證矩陣，文件類變更需檢查「連結與指令可用性」。

### 里程碑前（對應模板「每季」)

- [ ] 全面核對總覽與 `docs/TEAM_AI_OWNERSHIP.md` 的責任/分支表與實際 remote。
- [ ] 清理下表已知待修項。
- [ ] `docs/backlog/` 與各「尚未實作」自標文件逐檔確認狀態仍為真。
- [ ] `docs/vibecoding/`（舊一代）是否仍需保留或標記封存。

### 已知待修文件清單（2026-08-04 實測）

| 文件 | 問題 | 依據 |
| :--- | :--- | :--- |
| `backend/server/static/scene.html` | 引用 `scene_v2.js?v=sha256-27f24b6bede3`、`site.css?v=sha256-5693fe5d95c5`，實算前 12 碼為 `7d938e1fdc28`、`e362900c8195` → 守約測試 `tests/test_scene_v2_contract.py` 預期紅燈 | `shasum -a 256` 比對（本次未跑 pytest 確認，屬推算） |
| `docs/TEAM_AI_OWNERSHIP.md` | 分支對照寫 `origin/kai-with-bellatest1`，但 `git branch -a` 遠端無此分支（現有 `origin/kai`、`origin/kai-new`） | 兩者實測比對 |
| `backend/engine/README.md` | 第 6 行「對應 SSOT:第 4 節」所指 SSOT 文件不存在於 repo | grep 實測仍在；find 無 SSOT 檔 |
| `frontend3d/README.md` | 範例 port 8000 與 `vite.config.js:8` proxy 8002 不一致 | 兩檔實測比對 |
| `examples/demo_app/README.md` | 自述為「走通骨架 Demo」給老師看的最小可跑版，與正式產品邊界（`backend/server/` 唯一 FastAPI）並存，易誤導 | 該檔頭 3 行 |
| `docs/vibecoding/01–17` | 全套事實停在 2026-07-26 舊分支（44 條路由、無 engineering/RAG/PostgreSQL 五階段），未標示封存 | 各檔頭基準宣告 vs 現行 63 條路由 |
| `docs/contracts/` 非 .md 檔 | `.gitignore` 豁免只寫 `!docs/contracts/*.md`，yaml/schema.json 靠既有追蹤狀態存活；規則與現況不一致 | .gitignore:30-31 vs `git ls-files docs/contracts/` |

---

## 4. README 模板

repo 已有實際 README（297 行），以下為其現行章節骨架（`grep -n '^#' README.md` 實測），新增段落沿用此結構，不套用模板的通用骨架：

```markdown
# RoomPilot-Agent
## IKEA 地端 GLB 備援（尚未完成）   # 自標未完成的備援方案
## 快速啟動                          # venv+requirements / uv 兩種方式；port 8002（占用改 8023）
## 驗證指令                          # pytest -q / git diff --check / git status --short + 分域測試
## 現行八步流程
## 系統架構
## 團隊責任
## 主要資料夾
## 關鍵資料契約
## 家具資料與 PostgreSQL
## React/R3F 原型
## 套件版本
## 版本控制與整合                    # fetch→switch bella→integration 分支→逐 commit 移植 + 不得提交清單
```

分工邊界：README 負責安裝與啟動，總覽負責跨模組協作（兩檔開頭互相聲明）。模板建議的「貢獻（CONTRIBUTING.md）」與「授權」段落現況皆無：repo 無 `CONTRIBUTING.md`（ls 實測），合併規範直接寫在 README「版本控制與整合」段；根層有 `LICENSE` 檔（git ls-files 已入版控）但 README 無「授權」段指向它——是否補段落待裁決。

---

## 5. CHANGELOG 模板

現況：repo 無 `CHANGELOG.md`（ls 實測），變更紀錄實質上就是 git log。與舊導入版（2026-07-26）記錄的「兩種 commit 風格並存」不同，**現行已收斂為 Conventional Commits 型式 + 中文主旨**：最近 15 筆全為 `type(scope): 中文摘要` 或 `type: 中文摘要`（如 `feat(skills): 新增三支 RoomPilot 專用 skill,並讓 .claude/skills 進版控`、`refactor(scene): 擺放面分類收斂到型錄層,不再維護第二份型別名單`；`git log --oneline -15` 實測），但仍無書面規範——是否明文化、是否建立 CHANGELOG.md 均待裁決。若日後建立，沿用模板骨架：

```markdown
# 變更記錄

## [Unreleased]
### 新增
### 變更
### 修復

## [0.1.0] - YYYY-MM-DD    # 版號對齊 pyproject.toml（現為 version = "0.1.0"，pyproject.toml:3）
### 新增
- 初始版本
```

在此之前，查變更的實際入口是 `git log --oneline` 與總覽的接入狀態描述；跨分支收編歷史另見 `docs/CODY_PIPELINE_README.md`（cody 管線版本變更紀錄的收編版）與 `docs/BELLA_TEST1_INTEGRATION_LOG.md`。

---

## 6. 最佳實踐

1. **隨開發同步撰寫**：欄位或行為變更與契約更新在同一次合併內完成；根 `AGENTS.md` 要求動手前先讀最近的 AGENTS.md 與 contracts、修改前說明檔案與驗證指令。工程文件 API 是四件套（契約 md + openapi.yaml + schema.json + 程式），任一變更四者同動。
2. **文檔也要 Review**：整合進 bella 分支時逐 commit 檢視（README「版本控制與整合」段的 `git log --oneline bella..origin/<owner-branch>` 流程）；契約把「提案」寫成「已完成」即是缺陷。
3. **目錄負責人制，人人有責**：owner 依 `docs/TEAM_AI_OWNERSHIP.md` 目錄責任表（:19-34）而非 Git author（:3 明文）；每位成員維護自己目錄的 README/AGENTS.md 與對應契約，跨 owner 修改用根 `AGENTS.md` 的 6 欄記錄格式（:20-28）。
4. **文件聲明必須可複測**：寫入路徑、路由、指令、數字前先查證；查不到標「(未查證)」。守約測試把文件性契約變成紅綠燈（`tests/test_scene_v2_contract.py` 驗 cache 雜湊、`tests/test_env_example_contract.py` 驗環境變數表、`tests/test_team_ai_guidance.py` 驗 AI 協作規則檔）。
5. **入庫前檢查 .gitignore**：`docs/` 是白名單制、`.claude/` 只放行 `skills/`，新子目錄先加豁免再寫文件，避免默默漏交。
6. **歷史文件標示封存，不留雙權威**：舊一代 `docs/vibecoding/` 與新 `docs/vibecoding-v5/` 主題重疊時，事實一律以 v5 為準；同一概念不建立第二份現行文件（收編文件以「收編說明」檔頭標示非原文，保留來源分支可追溯）。
