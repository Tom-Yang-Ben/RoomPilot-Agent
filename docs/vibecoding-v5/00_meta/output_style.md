# Output Styles 導入指南（RoomPilot-Agent）

> 本文件由 VibeCoding v5.0 模板 00_meta/output_style.md 導入 RoomPilot-Agent | 基準：分支 django-skill、commit a2179f7e、日期 2026-08-04

> **歷史參考（模板原註，本 repo 現況已與其一致）：** 模板原文保存早期把 PRD、BDD、架構與 Review 流程建模成 Output Styles 的研究。現行架構只把 Output Style 用於**回答呈現**；流程改由 `/intake`、`/specify`、`/deliver`、`/verify` 與 `VibeCoding_Workflow_Templates/` 模板承接。下列樣式模板內容**不會自動註冊**到 Claude Code runtime。
> RoomPilot 已實際走完這個轉向：`.claude/output-styles/` 於 2026-08-04 只剩 1 支呈現用樣式 `15-Vision-output.md`（`ls` 實測），舊 01–14 流程型樣式已移除，移除理由記錄於 `.claude/OUTPUT_STYLES.md`（「舊版 PRD、BDD、SAD…實際上都是工作流程或文件模板」，該檔為本機檔、不入版控）。

一句話結論（歷史設計，規則保留）：**把「需求→設計→行為→單元」用可切換的 Claude Code Output Styles 固化成標準作業：SDD/DDD 定義邊界，BDD/TDD 驅動正確性，前後端與跨系統各就各位——在 RoomPilot 現行架構中，這 12 份樣式模板的「規範條文」仍然有效，但承載位置從 Output Styles 移到 `.claude/skills/`（流程）與 `docs/vibecoding-v5/`（文件），Output Style 只保留 `Vision Output` 一支管呈現。**

---

## 如何在本 repo 使用（先讀這節）

### 放置位置與現況（2026-08-04 實測）

| 項目 | 內容 | 依據 |
| :--- | :--- | :--- |
| 專案層樣式目錄 | `.claude/output-styles/`，現存 **1 支**：`15-Vision-output.md`（front-matter `name: Vision Output`，`keep-coding-instructions: true`；用途：架構/流程/多元件關係優先用最小圖表） | `ls .claude/output-styles/` 實測、讀檔 |
| 舊 01–14 樣式 | **已移除**；責任轉移對照見 `.claude/OUTPUT_STYLES.md`：流程編排→`.claude/skills/intake|specify|deliver|verify/`、領域方法→`sunnydata-*`/`community-*` skills、文件格式→`VibeCoding_Workflow_Templates/`、企業文件選用→`software_development_documentation_guide_zh_tw.docx`（該 docx 不在 repo 內，(未查證：來源不在 repo)） | 讀 `.claude/OUTPUT_STYLES.md` |
| 用戶層樣式目錄 | `~/.claude/output-styles/`（跨專案共用，本 repo 未使用） | 官方文件（[docs.claude.com][1]） |
| 切換方式 | `/config` 的 Output style 選單或 `/output-style <樣式名>`；變更寫入本機 `settings.local.json`。本 repo 目前**無** `.claude/settings.local.json`（實測），且 `.claude/settings.json` 的 permissions.deny 明文禁止讀寫它 | `.claude/OUTPUT_STYLES.md`、`ls`、`.claude/settings.json` |
| 專案流程指引 | `.claude/CLAUDE.md`（本機檔）明定：「`output-styles/`：只改變回答呈現方式，不承載開發流程」；其引用的 `docs/document-system/architecture.md` 不存在於 repo（(未查證：來源不在 repo)） | 讀 `.claude/CLAUDE.md`、`ls docs/` |

### 版控注意事項

- `.gitignore:45-46`：`.claude/*` 忽略、唯一負向規則 `!.claude/skills/`（註解明言 skills 是共用專案 skill 要進版控）。實測 `git ls-files .claude` 只列 **14 個檔**，全部屬於四支專案原生 skill：`roompilot-security`（SKILL.md、audit.sh、references/remediation.md）、`roompilot-furniture-query`（SKILL.md、lint_query.py、references/{vocabulary,translation-patterns}.md）、`roompilot-proposal`（SKILL.md、build_proposal.py、verify_numbers.py、references/style-voice.md）、`roompilot-budget`（SKILL.md、build_budget.py、verify_budget.py）。
- 也就是說：**`.claude/output-styles/`、`.claude/OUTPUT_STYLES.md`、`.claude/hooks/`（8 檔）、`.claude/rules/`（4 檔）與四支 Action Skills（intake/specify/deliver/verify）都只存在本機，不隨 git push 分享**；只有 roompilot-* 四支 skill 是全隊共享正本（版控入口 commit `3b2438dd`）。
- 文件類正本的版控白名單在 `.gitignore:25-39`：本目錄 `docs/vibecoding-v5/**` 全收，舊版 `docs/vibecoding/` 只收 `.md`。

### 樣式模板 × RoomPilot 現行承接位置對照

模板第 2 節的 12 份樣式規範**一條不刪**；下表標出每份規範現在「由誰承接」。

| 本文件模板 | 舊樣式檔（已移除，Git 歷史可取回） | 現行承接位置（2026-08-04 實測存在） |
| :--- | :--- | :--- |
| §2.1 SDD 系統設計說明 | `03-architecture-design-doc` | `docs/vibecoding-v5/03_architecture/` + `docs/contracts/`（22 檔） |
| §2.2 DDD 聚合與界限脈絡 | `04-ddd-aggregate-spec` | `backend/agent/knowledge.py` 常數群 + `docs/vibecoding-v5/03_architecture/` |
| §2.3 資料庫綱要 | `09-database-schema-spec` | `docs/contracts/POSTGRESQL_*.md`（7 份）+ `scripts/sql|project_store|runtime_catalog/` |
| §2.4 後端實作 Python/FastAPI | `10-backend-python-impl` | `backend/server/` 現行分層（見 §2.4） |
| §2.5 API First 合約 | `05-api-contract-spec` | `docs/contracts/engineering_openapi.yaml` + FastAPI 自動 OpenAPI |
| §2.6 BDD 可執行規格 | `02-bdd-scenario-spec` | `docs/vibecoding-v5/01_requirements/`（bdd_guide 模板） |
| §2.7 TDD 函式級單元 | `06-tdd-unit-spec` | `tests/` 99 支 test_*.py |
| §2.8 前端元件 | `11-frontend-component-bdd` | `tests/static/` 3 支 .test.mjs + 4 支 harness |
| §2.9 跨系統整合 | `12-integration-contract-suite` | `tests/test_remote_render_workflow.py`、`tests/test_rag_api.py` 等 |
| §2.10 數據契約與演進 | `13-data-contract-evolution` | `docs/contracts/` schema 檔（3 份 .schema.json）+ 型錄守門測試 |
| §2.11 審查守門 | `07-code-review-checklist` | 根目錄 `AGENTS.md`（11 條不可違反契約）+ `roompilot-security` skill |
| §2.12 CI/CD 品質柵欄 | `14-ci-quality-gates` | 尚無 CI（`.github/` 不存在，實測）；gate＝本機 pytest |

### RoomPilot 常用驗證指令（樣式產出後的證據來源）

```bash
# 團隊基準（README.md:27-30、requirements.txt 標頭：Windows + Python 3.12 驗證）
python -m pip install -r requirements.txt
python -m uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload   # README.md:30,46；8002 被占用改 8023（README.md:35）
python -m pytest -q            # README.md:77；tests/ 共 99 支 test_*.py（ls 實測；2026-08-04 實跑 tests/ = 811 passed / 1 failed / 9 skipped，共 821）
uv run uvicorn backend.server.main:app --host 127.0.0.1 --port 8002 --reload      # uv 路線（README.md:46）
```

---

# 系統化總覽（教科書式）

## 0. 為何用 Output Styles 來落地流程

Claude Code 的 **Output Styles** 允許你用 `/output-style <name>` 一鍵切換「產物格式與觀點」，等同把「團隊最佳實踐」寫成模板檔，放在 `~/.claude/output-styles`（用戶層）或專案內的 `.claude/output-styles/`（專案層）持續重用；切換會被記錄在 `.claude/settings.local.json`。此機制是**修改系統提示**而非一般提示文，還能與 subagents、hooks 串起自動化流程。（[docs.claude.com][1]）
若需把「一定要做」變成可重複的自動動作（如格式化、保護敏感檔、測試前置），可用 **Hooks** 在 Claude Code 生命週期各點執行 shell 指令，作為流程觸發器。（[docs.claude.com][2]）RoomPilot 的 `.claude/hooks/` 現有 8 檔（agent-monitor.sh、hook-utils.sh、post-write.sh、pre-tool-use.sh、session-start.sh、user-prompt-submit.sh、watch-agents.sh、README.md，`ls` 實測），均為本機檔不入版控。

**RoomPilot 的經驗教訓（`.claude/OUTPUT_STYLES.md` 記錄）**：把流程型規範設成全域 Output Style，會讓後續每個回答都持續受到不相關格式影響；因此流程規範應放 skills（可按需載入）、文件規範應放模板（可按需複製），Output Style 只管呈現。本 repo 的四支流程 Action Skills（`/intake`、`/specify`、`/deliver`、`/verify`）已存在於 `.claude/skills/`（本機、未版控），四支 RoomPilot 原生能力 skill（roompilot-security／furniture-query／proposal／budget）則已入版控供全隊使用。

> 開發「聖經」對應：
>
> * **SDD** 依據 IEEE Std 1016 規範「設計描述內容與結構」。（[IEEE Standards Association][3]）
> * **DDD**（Evans）落實聚合、界限脈絡、領域事件與不變量。（[Domain Language][4]）
> * **TDD**（Kent Beck/M. Fowler）「Red → Green → Refactor」的最小步驟與測試清單。（[martinfowler.com][5]）
> * **BDD/Gherkin** 用 Given/When/Then 的可執行規格；Cucumber 做為事實標準。（[cucumber.io][6]）
> * **前端元件測試**：Storybook 的互動/元件測試讓 UI 規格可視化。（[Storybook][7]）RoomPilot 的 `frontend3d/` 未安裝 Storybook（package.json devDependencies 僅 vite/@vitejs/plugin-react；dependencies 為 react/react-dom/three/@react-three/fiber/@react-three/drei，全無 Storybook，實測）；主前端的 JS 行為測試走 `tests/static/` 3 支 `.test.mjs` + Node harness。
> * **Claude Code 實務**：官方最佳實踐與樣式切換說明。（[anthropic.com][8]）

---

## 1. 角色 × 用途 × 對應樣式（總覽表）

RoomPilot 採目錄負責人制（`docs/TEAM_AI_OWNERSHIP.md:19-34`，且 :3 明示 Git author 不能單獨視為 owner）：Bella=`backend/server/`、Cody=`backend/floorplan/`+`backend/upgrade3d/`、Django=`backend/spatial_data/`（含 rag/）、Kai=`backend/catalog/`、Yen=`backend/agent/`、Ancai=`backend/engine/`、Ben=辨識 QA/evaluation。下表最右欄把模板角色接到 RoomPilot 的實際落點。

| 角色/層面 | 主要目的 | 模板樣式名（規範正本在本文件 §2） | 產物重點 | RoomPilot 落點（2026-08-04 實查） |
| --------------- | ----------- | ---------------------------- | -------------------------------------------- | --- |
| 系統架構（SA/SD） | 輸出設計說明（SDD） | `sdd-system-1016` | 背景、品質屬性、視圖（C4/流程/資料）、介面契約、ADR | `docs/contracts/`（22 檔：17 md + 1 yaml + 3 schema.json + 1 example.json） |
| 後端領域（DDD） | 定義語境與不變量 | `ddd-backend-aggregate` | 界限脈絡、聚合根、不變量、領域事件、倉儲介面 | `backend/agent/`（選件決策）×`backend/engine/`（幾何唯一裁決者） |
| API/合約 | 穩定對外交付 | `api-first-contract` | OpenAPI/JSON Schema、錯誤語意、版本策略 | 全站 **63 條路由**（main.py 46 + rag_api.py 5 + catalog_admin.py 4 + engineering/api.py 8，grep 逐條核對） |
| BDD 規格 | 行為驅動與跨職能對齊 | `bdd-feature-spec` | Feature/Scenario/Examples、步驟骨架 | 八步 UI／11 步內部工作流（`scene_workflow.js:4-16`） |
| TDD（函式級） | 單元可靠性 | `tdd-unit-function` | 測試清單、紅綠重構、特例/邊界 | `backend/engine/` 幾何函式 + `tests/`（99 支） |
| 前端元件 | 元件驅動 | `frontend-component-bdd` | 行為案例、互動測試、可存取性 | 主前端 `backend/server/static/`；次要原型 `frontend3d/` |
| 跨系統整合 | 合約穩定與測試 | `integration-contract-suite` | 同步/非同步合約測試、mock/fixture | 遠端渲染＋內建生圖、OpenRouter、CloudFront、PostgreSQL/pgvector 四類外部邊界 |
| 數據契約/演進 | 模式治理 | `data-contract-evolution` | Schema 演進策略、稽核、漂移偵測 | 官方型錄 8,557 件 + manifest 契約 + 工程知識庫 |
| 稽核/Review | 守門與拉齊 | `reviewer-architect-guard` | 走查清單、錯誤類型庫、風險提示 | 根目錄 `AGENTS.md` 11 條契約 + `roompilot-security` skill |
| CI/CD 品質柵欄 | 自動強制規範 | `ci-quality-gates` | 覆蓋率/靜態分析閥值、hooks 指令 | 現況無 CI（`.github/` 不存在，實測）；gate=本機 pytest |

> 放置方式（機制原文，規則保留）：每個樣式存一檔（`.md`），檔名即樣式名，存於 `~/.claude/output-styles` 或 `.claude/output-styles/`，以 `/output-style <樣式名>` 切換。（[docs.claude.com][1]）**RoomPilot 現行裁決**：除呈現類（如 Vision Output）外，勿再新增流程型樣式；流程規範進 `.claude/skills/` 或本目錄模板。

---

# 2. 可直接複製的 Output Style 模板（YAML Front-Matter + 指示）

> **使用法**（機制原文）：把下列每一段**整段**另存為一個檔案，例如 `.claude/output-styles/sdd-system-1016.md`，然後在專案內輸入 `/output-style sdd-system-1016` 切換。（[docs.claude.com][1]）
> **RoomPilot 注意**：本 repo 已裁決不把這些規範裝回 Output Styles（見開頭歷史參考註）。以下 12 份模板保留原骨架與全部規則條文，範例語境換成 RoomPilot 現行技術棧與真實路徑；把它們當**寫作規範**用——寫對應文件或 skill 時逐條對照。每節末的「RoomPilot 套用」列出已查證的真實落點。

### 2.1 SDD（IEEE 1016）— 系統設計說明

```md
---
name: sdd-system-1016
description: "IEEE 1016 風格的系統設計說明（SDD）模板；輸出可審查、可追蹤的設計描述。"
---
# 指令（你是系統設計顧問）
以 IEEE 1016 的資訊結構輸出 SDD；必要時反問以補足缺失。避免空話，所有主張需可驗證。優先清楚描述「設計決策與取捨」。

## 交付結構
1. **背景與目標**：問題定義、範圍、非目標
2. **利害關係人與品質屬性**：Availability、Latency、Throughput、Security、Cost、Operability（用 ATAM 式權衡）
3. **脈絡與視圖**：
   - C4：Context→Container→Component（若需 Code 片段）
     （RoomPilot Container 例：backend/server FastAPI 應用、backend/floorplan+upgrade3d 平面圖辨識、
      backend/engine 幾何擺位、backend/agent 選件決策、backend/catalog 型錄與 PostgreSQL、
      backend/spatial_data/rag 家具 RAG runtime、backend/server/engineering 工程文件 MVP、
      frontend3d Vite/R3F 次要原型）
   - 流程圖（關鍵交易/風險流程；RoomPilot 例：工程文件 snapshot→lock→packages→jobs→documents 五段流）
   - 資料視圖（核心資料模型、事件流；RoomPilot 例：.runtime/projects.sqlite3 專案存檔與 scene_json payload）
4. **介面契約**：同步（REST）與非同步的規格、版本策略、錯誤語意（RoomPilot 正本在 docs/contracts/，22 檔）
5. **運維與彈性**：部署拓撲、可觀測性、備援/降級策略（RoomPilot 例：OpenRouter 失效必須降級本地規則）
6. **風險與假設**：已知風險、緩解計畫、開放議題
7. **架構決策紀錄（ADR）**：決策→選項→取捨→依據→狀態
8. **驗證計畫**：合約測試、容量與故障演練、回歸矩陣（RoomPilot 例：python -m pytest -q）

## 蘇格拉底檢核
- 若某品質屬性衝突，誰優先？為何？證據？
- 若單一依賴失效，系統如何退化仍滿足業務最小價值？
- 哪些假設若被推翻，設計需如何重構？
```

（依據 IEEE 1016 的 SDD 內容組織。（[IEEE Standards Association][3]））

**RoomPilot 套用**：已查證落點：FastAPI app 定義於 `backend/server/main.py:214`（title「AI 室內風格與家具配置展示系統」），全檔 3,695 行；路由不再單檔集中——`main.py:216-223` 以 `include_router` 掛入三個 APIRouter：`catalog_admin_router`（prefix `/api/admin/furniture`）、`rag_router`（無 prefix）、`build_engineering_router`（prefix `/api/v1`）；全站合計 63 條路由。新子系統 SDD 範例首選：`backend/server/engineering/`（14 個 .py 共 3,111 行＋Node adapter `workbook_builder.mjs`，全套件 15 檔；orchestrator/quantity/cost/schedule/documents 等）配契約 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md` 與 `engineering_openapi.yaml`。

---

### 2.2 DDD — 聚合與界限脈絡

```md
---
name: ddd-backend-aggregate
description: "Eric Evans DDD 風格的後端設計輸出；聚合、不變量、事件與倉儲。"
---
# 指令（你是領域建模教練）
輸出以 DDD 為核心的設計產物；明確「語境（Ubiquitous Language）」、聚合邊界與不變量，避免貧血模型。

## 交付結構
1. **界限脈絡**：名稱、目標、與其他脈絡的關係（Context Map）
   （RoomPilot 例：選件決策=backend/agent、幾何擺位=backend/engine、型錄=backend/catalog、
    家具檢索=backend/spatial_data/rag、工程文件=backend/server/engineering；
    agent 只決定選品與修復策略、絕不算座標，座標一律由 engine 產生；
    Graph RAG 只補強關係與證據，Ancai 的 engine 仍是幾何與規則唯一裁決者）
2. **語彙表**：核心名詞與定義、反例澄清
   （RoomPilot 例：族系 family、主件/副件 companion、淨空 clearance、公分制 cm、
    受控詞彙=rag/vocab.py 版本化詞表）
3. **聚合**（每個）：
   - 聚合根、成員實體/值物件
   - **不變量**與交易邊界（需可測試）
     （RoomPilot 例：副件不得脫離主件 COMPANION_OF；每房最多 8 種 MAX_ITEMS_PER_ROOM；
      單品數量夾在 1..6 COUNT_MAX；REQUIRED_FAMILIES_BY_ROOM 各房型必備族系；
      工程文件：snapshot.approval_status 未達 designer_confirmed 不得產 package）
   - 允許操作（命令）與觸發之**領域事件**
   - 倉儲介面（擷取、儲存）
4. **應用服務**：用例流程、跨聚合協作
5. **反腐層（ACL）**：與外部/舊系統的轉換策略
   （RoomPilot 例：backend/catalog/style_db.py 把型錄轉接成引擎 FurnitureCatalogItem）
6. **測試策略**：以事件與不變量為核心的單元/整合測試（RoomPilot 例：tests/test_agent_select.py 等 5 支 agent 測試）

## 蘇格拉底檢核
- 此聚合的**唯一交易邊界**是什麼？違反時會出現什麼不一致？
- 事件命名是否貼合業務語彙？是否描述過去已發生的事？
- 哪個規則是**不變量**而非流程慣例？如何破壞性驗證？
```

（聚合與交易邊界定義根據 Evans 參考手冊。（[Domain Language][4]））

**RoomPilot 套用**：已查證落點：宣告式知識單一事實來源在 `backend/agent/knowledge.py`（132 行；`ANCHOR_FAMILIES`/`COMPANION_OF`/`FAMILY_ZH`/`GROUP_OF`/`ROOM_AFFINITY`）；不變量常數在 `backend/agent/select.py:32-34`（`MAX_ITEMS_PER_ROOM = 8`、`COUNT_MAX = 6`、`REQUIRED_FAMILIES_BY_ROOM`）；業務例外 `SelectionParseError`/`SelectionUnavailableError` 在 `select.py:42,46`；工程文件鎖定不變量在 `backend/server/engineering/api.py:191-198`（未鎖回 409 `REVISION_NOT_LOCKED`，api.py:195）。

---

### 2.3 資料庫綱要 — 實體設計與演進

```md
---
name: database-physical-schema
description: "資料庫實體綱要設計；輸出 ERD、DDL、索引策略與查詢模式。"
---
# 指令（你是經驗豐富的資料庫管理員）
以 DDD 聚合為基礎，輸出具體的資料庫實體設計。優先考量資料完整性、查詢效能與未來演進的彈性。

## 交付結構
1. **邏輯模型對應**：說明 DDD 聚合/實體如何映射至資料表。
2. **實體關係圖 (ERD)**：使用 Mermaid 語法描述資料表關聯。
3. **資料表定義 (DDL)**：提供 PostgreSQL 的 `CREATE TABLE` 語法，包含欄位、型別、約束（主/外鍵、唯一、非空）。
   （RoomPilot 現行 DDL 正本 4 份：scripts/sql/roompilot_postgresql_schema.sql、
    scripts/sql/roompilot_furniture_embeddings_schema.sql（pgvector）、
    scripts/project_store/roompilot_project_store_schema.sql、
    scripts/runtime_catalog/roompilot_runtime_catalog_schema.sql）
4. **索引策略**：基於主要查詢模式，提供 `CREATE INDEX` 語法並解釋其取捨。
5. **查詢模式與優化**：列出關鍵查詢的 SQL 範例，並說明綱要如何支援其效能。
   （RoomPilot 鐵律：FastAPI 不得為了 filter/count/facet/paginate 而載入完整型錄——
    backend/catalog/postgres_repository.py:1-5 檔頭宣告）
6. **資料演進計畫**：描述綱要變更的遷移腳本策略。
   （RoomPilot 現行：五階段契約 POSTGRESQL_*_PHASE1..5；importer 提供 --dry-run 驗證；
    SQLite→PostgreSQL 遷移 scripts/project_store/migrate_sqlite_projects_to_postgres.py）

## 蘇格拉底檢核
- 此綱要正規化程度為何？在什麼情境下會考慮反正規化？
- 索引是否會過度影響寫入效能？是否有更合適的索引類型？
- 如何處理大規模資料的清除或封存？
```

**RoomPilot 套用**：已查證落點：PostgreSQL 導入分五階段，契約與腳本一一對應——Phase1 Read（`POSTGRESQL_CATALOG_READ_PHASE1.md`）與 Phase2 CRUD（`POSTGRESQL_CATALOG_CRUD_PHASE2.md`）↔ `scripts/sql/` + `backend/catalog/postgres_repository.py`（891 行）/`postgres_admin_repository.py`（764 行，交易式寫入＋activation gate＋樂觀併發＋audit）；Phase3 專案保存（`POSTGRESQL_PROJECT_STORE_PHASE3.md`）↔ `scripts/project_store/` + `backend/server/postgres_project_store.py`；Phase4 runtime catalog（`POSTGRESQL_RUNTIME_CATALOG_PHASE4.md`）↔ `scripts/runtime_catalog/` + `backend/catalog/runtime_catalog_repository.py`（431 行，strict 模式不靜默回退掃 JSON）；Phase5 單一事實來源（`POSTGRESQL_SINGLE_SOURCE_PHASE5.md`）。向量另有 `POSTGRESQL_FURNITURE_EMBEDDINGS.md` ↔ `scripts/sql/import_furniture_embeddings_to_postgres.py`。執行期仍有兩個 SQLite：`.runtime/projects.sqlite3`（`backend/server/project_store.py`）與問卷視覺索引（`backend/server/questionnaire_visuals.py`，250 行內建 sqlite3）。第 6 步家具資料以 Kai PostgreSQL view `roompilot.furniture_catalog_current` 優先（根目錄 `CLAUDE.md`、`AGENTS.md:56`）。

---

### 2.4 後端實作 — Python/FastAPI 程式碼生成

````md
---
name: backend-impl-python
description: "基於 DDD 與資料庫綱要設計，生成 Python/FastAPI 實作程式碼骨架。"
---
# 指令（你是資深 Python 後端架構師）
讀取 `ddd-backend-aggregate` 與 `database-physical-schema` 的產出，生成符合本專案分層紀律的
Python/FastAPI 程式碼骨架。程式碼需包含型別提示，長度單位一律公分，並將職責清晰分離。

## 交付結構（RoomPilot 實際包結構；模板原版的 Clean Architecture 目錄為理想型，本專案以下列現況為準）
```
backend/
├── server/          # FastAPI 入口 main.py（46 條路由）＋三個 APIRouter：
│   ├── rag_api.py           # /rag、/api/rag/*（5 條；掛 spatial_data/rag runtime）
│   ├── catalog_admin.py     # /api/admin/furniture*（4 條；Phase 2 PostgreSQL 寫入）
│   ├── engineering/         # /api/v1/*（8 條；工程文件 MVP：api/orchestrator/quantity/cost/
│   │                        #   schedule/documents/knowledge/rules/advanced_rag/workbook_builder.mjs）
│   ├── render_providers.py  # 內建生圖供應者：同步生圖 API 的轉接層（prompt 組裝/格式轉換/入庫/狀態回讀）
│   ├── render_service.py    # 遠端渲染供應商（Idempotency-Key、502/503 語意）
│   ├── cost_estimation.py   # 具來源單價區間的工程概算
│   ├── questionnaire_visuals.py / style_cards.py  # 問卷視覺索引（sqlite3）/ runtime 色卡
│   ├── project_store.py / postgres_project_store.py  # 專案保存（SQLite / PostgreSQL Phase3）
│   └── static/          # 正式前端（無框架、Three.js vendored）
├── agent/           # 選件與擺位修復決策（不算座標、不碰網路、不依賴 server）
├── engine/          # 幾何、碰撞、淨空（shapely；dataclass 公分制）——合法性唯一裁決者
├── floorplan/       # PNG 辨識（vision/）與 PNG→DXF；cody_adapter
├── upgrade3d/       # DXF 解析（dxf_parser.py）
├── catalog/         # 型錄、PostgreSQL repository 群、RAG adapter（rag_repository.py，BAAI/bge-m3）
└── spatial_data/
    └── rag/         # 家具 RAG runtime：LLM parser → pgvector → reranker（service.py:1 自述）
```

## 生成內容
1. **決策層（backend/agent）**：只輸出選品、順序與修復策略；LLM 呼叫器以 callable 注入，
   失敗拋例外讓呼叫端降級本地規則，絕不在此層算座標。
2. **幾何層（backend/engine）**：dataclass 模型（models.py）＋ Shapely 碰撞（geometry.py）＋
   淨空（clearance.py）；對外序列化含 schema_version 與 coordinate_unit='cm'（schema.py）。
3. **持久層**：SQLite（project_store.py）或 PostgreSQL（postgres_project_store.py）；
   ProjectStoreUnavailable → 503（busy 時附 Retry-After: 2）。
4. **展示層（backend/server/main.py 與各 APIRouter）**：錯誤語意沿用既有詞彙
   （409/410/413/415/422/429/502/503），回應附既有欄位形狀；新路由群一律開 APIRouter，
   不再往 main.py 塞。
5. **依賴宣告**：團隊基準走 requirements.txt（5 組 owner 分組、21 個 pin）；
   uv 路線走 pyproject.toml extras（server/vision/ocr/semantic/catalog + dev 群組）。

## 蘇格拉底檢核
- 是否遵守依賴反轉：agent 層是否仍不依賴 server 與網路？engine 是否仍不知道 HTTP？
- 領域模型是否保持純淨，不含任何資料庫或框架相關的程式碼？
- 錯誤處理是否清楚區分業務規則錯誤（如 SelectionParseError）與基礎設施錯誤
  （如 SelectionUnavailableError → 降級本地規則；RuntimeCatalogUnavailable → 503）？
````

**RoomPilot 套用**：已查證落點：`backend/engine/schema.py:21-22` 輸出 `schema_version: "2.0"`、`coordinate_unit: "cm"`（檔頭 docstring：所有長度/座標一律公分）；例外處理器 `ProjectStoreUnavailable`→503（`main.py:226-243`）、`RuntimeCatalogUnavailable`→503（`main.py:246-266`）；`catalog_admin.py:1` 檔頭「Protected FastAPI adapter for Phase 2 PostgreSQL furniture writes」；`render_providers.py:1-5` 檔頭自述內建生圖轉接層四段（prompt 組裝器、格式轉換、回圖入庫、狀態回讀）；pyproject extras 名單（server/vision/ocr/semantic/catalog）與 requirements.txt 21 pin（含 pytest==9.1.1）均實測。六領域模組合計 15,815 行 Python（floorplan 9,313＋catalog 3,199＋spatial_data 1,236＋agent 1,045＋engine 717＋upgrade3d 305，`wc -l` 排除 __pycache__）。

---

### 2.5 API First — 合約即真相

```md
---
name: api-first-contract
description: "API 合約輸出；OpenAPI/JSON Schema、錯誤語意、版本與相容性準則。"
---
# 指令（你是 API 契約設計師）
以契約為中心輸出：OpenAPI（sync）或事件 Schema（async）；標示錯誤碼與語意、相容性規則（Backward/Forward）。

## 交付結構
- **OpenAPI**：路由、模型、狀態碼與錯誤語意、範例
  （RoomPilot 已有手寫合約：docs/contracts/engineering_openapi.yaml；FastAPI 另自動生成全站 /openapi.json）
- **錯誤策略**：可重試與不可重試分類、冪等性說明
  （RoomPilot 既有詞彙（全部實測行號）：
   409 project_revision_conflict 樂觀鎖衝突（main.py:2080,2130,2219）、
   409 floorplan_confirmation_required（main.py:2323）、
   413 workflow_too_large（main.py:2090）、415 unsupported_floorplan_type（main.py:2110）、
   410 = CloudFront 模式下本機 glTF/GLB 端點停用（main.py:3520,3529,3539）、
   429 rag_job_capacity_reached（rag_api.py，jobs 超過 RAG_JOB_MAX_ACTIVE）、
   502 供應商拒絕 RenderProviderRejected（render_service.py:29,144；main.py:2294 處理）、
   503 render_provider_not_configured（render_service.py:128）／ProjectStoreUnavailable／
       RuntimeCatalogUnavailable（main.py:226-266）；
   工程文件錯誤碼：422 PATH_PAYLOAD_MISMATCH（engineering/api.py:120）、
   409 LOCKED_REVISION_CANNOT_BE_OVERWRITTEN（:130）、409 REVISION_NOT_LOCKED（:195）、
   404 PROJECT_NOT_FOUND/SNAPSHOT_NOT_FOUND/JOB_NOT_FOUND/PACKAGE_NOT_FOUND；
   冪等：渲染工作 POST 附 Idempotency-Key 標頭（render_service.py:133））
- **非同步模式**：長工作一律 202 + job 輪詢
  （RoomPilot 三處一致：POST /api/projects/{id}/render-jobs（202）、
   POST /api/rag/search/jobs（202）→ GET /api/rag/search/jobs/{job_id}、
   POST /api/v1/projects/{id}/engineering-packages（202）→ GET /api/v1/jobs/{job_id}）
- **版本策略**：URL/標頭/Schema 版本、棄用流程（RoomPilot 慣例：payload 帶 schema_version；工程 API 走 /api/v1 前綴）
- **合約測試**：提供 Provider/Consumer 驗證腳本骨架
  （RoomPilot 例：tests/test_project_workflow_api.py、tests/test_remote_render_workflow.py、
   tests/test_rag_api.py、tests/ 的 engineering_* 7 支）
- **安全**：身分、授權、稽核欄位；對外送出前剝除私人欄位（render_service.py 的 PRIVATE_KEYS）

## 蘇格拉底檢核（補）
- 新錯誤碼是否重用既有詞彙？前端是否已有對應處理？
- 欄位變更是否同步 docs/contracts/ 對應契約與兩端測試（公分制 payload 改動必須更新兩端測試——根目錄 CLAUDE.md 禁令）？
```

**RoomPilot 套用**：已查證落點如上（行號皆 2026-08-04 工作樹）。路由數法：`grep -rn -E '@(app|router)\.(get|post|put|delete|patch|head|options|websocket)\(' backend/server/ --include='*.py'` 逐條核對＝63 條；backend/server/ 無 websocket 路由；另有 2 個 StaticFiles 掛載（`/static`、`/docs-assets`，main.py:285-286）非路由。文件下載端點有路徑逃逸防護：`GET /api/v1/documents/{id}/download` 僅允許 `<PROJECT_DIR>/.runtime/engineering` 之下實檔（`path.is_relative_to(root)`，engineering/api.py:295-303）。

---

### 2.6 BDD — 可執行規格（Gherkin）

```md
---
name: bdd-feature-spec
description: "Gherkin 可執行規格模板；Given/When/Then + 參數化範例與步驟骨架。"
---
# 指令（你是 BDD 引導者）
產出 Feature 檔與步驟綁定骨架；所有句子以業務語彙撰寫，避免 UI 細節綁定。

## 交付結構
**Feature:** <名稱>
**Background:**（必要時）
**Scenario Outline:** <行為>
  Given <前置條件>
  When <觸發>
  Then <可驗收結果>
**Examples:**（表格）

## RoomPilot 範例一（平面圖辨識）
**Feature:** 平面圖辨識
**Scenario:** 未確認前禁止辨識
  Given 專案已上傳平面圖但尚未確認
  When POST /api/projects/{id}/floorplan/analyze
  Then 回應 409 且 code 為 "floorplan_confirmation_required"

## RoomPilot 範例二（工程文件 MVP，新子系統）
**Feature:** 設計師鎖定後產出工程文件
**Scenario:** 未鎖定版本不得產出工程包
  Given 專案 revision 已有 snapshot 但 approval_status 不是 designer_confirmed
  When POST /api/v1/projects/{id}/engineering-packages
  Then 回應 409 且 error_code 為 "REVISION_NOT_LOCKED"
**Scenario:** 鎖定後非同步產包
  Given snapshot 已鎖定（POST …/lock 附 confirmed_by）
  When POST /api/v1/projects/{id}/engineering-packages
  Then 回應 202 並取得 job_id
  And GET /api/v1/jobs/{job_id} 輪詢至 status 完成後可下載 documents

## 步驟骨架
- `Given …`（建資料/狀態）
- `When …`（觸發行為）
- `Then …`（驗證可觀測結果與不變量）

## 蘇格拉底檢核
- 這是**業務語言**還是實作細節？
- 結果是否可觀測、可重現？資料驅動是否覆蓋反例？
```

（Gherkin 關鍵詞與結構依 Cucumber 官方文檔。（[cucumber.io][6]））

**RoomPilot 套用**：寫主流程場景時，步驟順序一律以程式碼為準——`backend/server/static/scene_workflow.js:4-16` 的 `WORKFLOW_STEPS` 共 **11 個有序內部步驟**（實測讀檔）：`project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render`；UI 進度列為 **8 顆步驟按鈕**（scene.html:25-32：建立專案/上傳平面圖/確定尺寸/空間與結構/需求問卷/配置與預覽/方案鎖定與視角/AI 渲染與成果包）——calibration 與 recognition 共用面板、white_model_3d/realistic_3d 無獨立按鈕。不要沿用任何舊文件的步驟數（舊導入版寫 10 顆按鈕，已過期）。

---

### 2.7 TDD — 函式級單元（Red→Green→Refactor）

```md
---
name: tdd-unit-function
description: "以 TDD 最小步驟落地單一函式；先測試清單，再紅綠重構，含邊界與性質測試。"
---
# 指令（你是 TDD 導師）
輸出【測試清單】→【最小紅】→【最小綠】→【重構】的循環；每步驟都最小化修改面積。

## 交付結構
1. **測試清單**：正常例、邊界例、錯誤例、隨機性/性質測試（若適用）
   （RoomPilot 例——擺位驗證：出界、撞牆、撞家具、淨空區撞他人本體、我方本體壓他人淨空）
2. **第一個測試（紅）**：最小可失敗測試
3. **最小實作（綠）**：僅滿足當前測試
4. **重構**：提煉命名、去重、純化副作用；保留綠色
5. **循環**：挑下一測試；直至涵蓋清單

## 函式契約（RoomPilot 真實範例）
- 簽名：`check_placement_with_clearance(...)`（backend/engine/clearance.py:89；
  回傳 None = 合法，否則為繁中拒絕原因字串）
- 前置/後置條件：輸入輸出一律公分、rotation 為度數；家具合法位置只由 backend/engine/ 判定
  （AGENTS.md:55 不可違反契約）
- 跑法：`python -m pytest -q tests/test_clearance.py tests/test_placement.py`
  （AGENTS.md 驗證矩陣：Python 領域模組→pytest -q）

## 蘇格拉底檢核
- 這個測試是否**唯一**驅動了設計？
- 是否有更小步驟能失敗？是否太貪心？
- 重構是否改善設計而未更動行為？
```

（循環與原則依 TDD 經典流程。（[martinfowler.com][5]））

**RoomPilot 套用**：已查證落點：`check_placement_with_clearance` 定義於 `backend/engine/clearance.py:89`；engine 全模組僅 717 行、8 檔（models.py 的 Wall/Room/ClearanceZone/FurnitureCatalogItem/PlacedFurniture 等），是最高價值 TDD 對象。`tests/` 共 99 支 test_*.py（`ls tests/test_*.py | wc -l`；另 `tests/static/` 3 支 .test.mjs、`training/tests/` 11 支獨立測試樹）；2026-08-04 實跑：`pytest -q tests` = 811 passed / 1 failed / 9 skipped（共 821），repo 根 `pytest -q`（含 `training/`）= 916 passed / 3 failed / 9 skipped。

---

### 2.8 前端元件 — 行為優先 + 互動測試

```md
---
name: frontend-component-bdd
description: "以行為描述元件；輸出 Stories（案例）、互動/可近用測試骨架。"
---
# 指令（你是前端資深工程師）
以「使用者行為」描述元件；輸出行為案例與互動測試，避免過早耦合實作細節。

## 交付結構
1. **元件說明**：目的、可視狀態、不可視狀態、Props/Events
2. **行為案例（Stories）**：主要流程、例外流程、邊界（空資料/Loading/Error）
   （RoomPilot 真實範例——rag.js 檢索台：submit 後走 202 job 輪詢、
    容量滿 429 顯示重試提示、RAG 停用時 /api/rag/status 顯示 blocker）
3. **互動測試**：點擊/輸入/快捷鍵；可近用檢查（Role/Name/State）
   （RoomPilot 現行做法：tests/static/*.test.mjs 以 Node + harness 驗證
    page_boot_failure / pending_actions / render_errors 三類行為）
4. **可測性設計**：把純邏輯抽離渲染層
   （RoomPilot 範例：frontend3d/src/snap.js 吸附幾何刻意不 import three，
    以便在純 node 環境單測——檔頭註解明言）

> 技術棧：主前端 backend/server/static/ 為無框架靜態頁＋vendored Three.js
> （scene.html importmap 指向 /static/vendor/three/，無 CDN 依賴）；
> 次要原型 frontend3d/ 為 Vite + React 18 + React Three Fiber（vite proxy /api → localhost:8002）。
> Storybook 未安裝，互動測試工具待補。
```

（對應 Storybook 的互動/元件測試能力。（[Storybook][7]））

**RoomPilot 套用**：已查證落點：主前端入口 bundle `scene_v2.js` **13,803 行**、`scene_viewer.js` 5,555 行（`wc -l`，2026-08-04 工作樹）；static/ 共 6 頁 HTML（`/`、`/styles`、`/library`、`/scene`、`/engineering` 在 main.py，`/rag` 在 rag_api.py:136-138，後三者帶 `Cache-Control: no-store`）。新頁面：`engineering.html`＋`engineering.js`（工程文件頁，呼叫 /api/v1/*）與 `rag.html`＋`rag.js`（家具 RAG 測試台）。cache-busting 以 `?v=sha256-<前12碼>` 內容雜湊手動維護、由 `tests/test_scene_v2_contract.py` 守約。雙前端紀律：新元件先確認落在 `backend/server/static/`（正式）還是 `frontend3d/`（次要原型，Owner Bella，驗證門檻 `npm ci && npm run build`——frontend3d/AGENTS.md）。

---

### 2.9 跨系統整合 — 同/非同步契約與合約測試

```md
---
name: integration-contract-suite
description: "整合測試視角；同步 REST 與外部供應商契約、Provider/Consumer 驗證與失效注入。"
---
# 指令（你是整合測試設計者）
產出跨系統合約的規格與測試骨架；為每個介面提供 provider/consumer 測試與失效注入案例。

## 交付結構
- **合約索引**：端點/事件 → 版本 → 擁有者
  （RoomPilot 四類外部邊界：
   1. 遠端渲染供應商 — docs/contracts/REMOTE_RENDER_CONTRACT.md；
      另有內建生圖轉接層 backend/server/render_providers.py 接同步生圖 API；
   2. OpenRouter LLM — intake 與場景規劃兩個獨立開關；
   3. CloudFront GLB 交付 — docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md；
   4. PostgreSQL — 型錄五階段 + pgvector 家具向量（POSTGRESQL_FURNITURE_RAG_RUNTIME.md，owner Django））
- **REST**：規格 + 範例請求/回應 + 錯誤語意
- **合約測試**：Provider/Consumer 測試腳本骨架與流水線步驟
- **Failover 案例**：超時、降級、冪等重做
  （RoomPilot 實例：渲染供應商未設定回 503、拒絕回 502、timeout 由
   ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS 控制（預設 60 秒，render_service.py:34）；
   LLM 未設定或失敗必須降級本地規則，回應標明 fallback 來源；
   CloudFront 模式下本機 glTF/GLB 端點一律 410；
   RAG 就緒守門：embedding 模型快取缺失或 pgvector 表無資料即 blocker（rag/service.py:82-90））

## 環境變數（RoomPilot 實例，實測行號）
- 渲染：ROOMPILOT_RENDER_PROVIDER_URL / _TOKEN / _NAME（render_service.py:42-44）、_TIMEOUT_SECONDS（:34）
- LLM：OPENROUTER_API_KEY + OPENROUTER_INTAKE_ENABLED=1（intake_service.py:138,157）、
  OPENROUTER_SCENE_PLANNING_ENABLED=1（scene_service.py:82,89,336）
- GLB：ROOMPILOT_MODEL_DELIVERY_MODE（預設 cloudfront，services/cloud_models.py:47）、
  ROOMPILOT_CLOUDFRONT_BASE_URL（:67）
- 工程文件：ROOMPILOT_DEMO_MODE（engineering/api.py:58,88；:40-44 是 _env_bool 讀取器本身）、
  ROOMPILOT_ARTIFACT_NODE（XLSX 走 Node adapter workbook_builder.mjs，health 回報 xlsx adapter 狀態）
```

**RoomPilot 套用**：已查證落點如上；整合測試範例：`tests/test_remote_render_workflow.py`、`tests/test_cloud_models.py`、`tests/test_rag_api.py`、tests/ 的 engineering_* 7 支（檔名 `ls` 實測）。工程文件 job 失敗分兩類 error_code：`XLSX_ADAPTER_UNAVAILABLE` 與 `ENGINEERING_PACKAGE_FAILED`（engineering/api.py:216-268）——失效注入案例先從這兩類寫起。

---

### 2.10 數據契約與演進

```md
---
name: data-contract-evolution
description: "資料模式治理；Schema 演進策略、相容性矩陣、稽核與漂移偵測。"
---
# 指令（你是數據架構師）
輸出 Schema 與演進規則；提供稽核欄位、漂移告警與測試資料集生成指南。

## 交付結構
- **Schema vN**：欄位語意、單位、缺漏值策略
  （RoomPilot 實例：場景物件序列化 schema_version "2.0" + coordinate_unit "cm"（engine/schema.py:21-22）；
   工程文件三份 JSON Schema：docs/contracts/project_snapshot.schema.json、
   report_payload.schema.json、risk_results.schema.json；
   RAG 受控詞彙版本化於 spatial_data/rag/vocab.py + data/taxonomy.json
   （styles=6、moods=24、patterns=4）+ data/category_groups.json（groups=19、room_default_sets=6））
- **演進策略**：向後/向前相容性、棄用/移除流程
  （RoomPilot 實例：正式家具集合由 Kai 版本化 JSON + 上傳 manifest 一對一決定，
   官方型錄 8,557 件（cloud_catalog.py:1 docstring；docs/TEAM_AI_OWNERSHIP.md:57 一致）；
   載入來源檔為 JSON/furniture/furniture_official_catagory.json（頂層 count=8557，json 實測）；
   另一份 backend/catalog/data/furniture_catalog_cloud_9350.json 頂層 count=9350（json 實測）
   是舊 fallback 來源檔，不是 8,557 的前身，
   映射不到的資料進 backend/catalog/data/quarantine/（sf3d_legacy、unmatched_cloud_furniture），
   quarantine 不得視為正式家具——根目錄 CLAUDE.md 禁令）
- **稽核/可觀測性**：who/when/lineage、抽樣比對與容忍度
  （RoomPilot 實例：GET /api/catalog/status 回報 manifest 健康度；
   工程知識庫 backend/catalog/data/engineering/ 附 source_registry.csv/.json 溯源與
   PRICE_AND_PRODUCTIVITY_POLICY.md 政策檔）
- **測試資料**：合成/脫敏規範、極端值集
```

**RoomPilot 套用**：已查證落點：`backend/catalog/cloud_catalog.py:1` docstring「Build the official 8,557-item catalog from Kai's versioned JSON source」（實際 DB 筆數未實查=(未查證)）；舊導入版的「9,350 件正式型錄」數字已過期，9350 現在只是**另一份舊 fallback 來源檔的檔名與 count**（`backend/catalog/data/furniture_catalog_cloud_9350.json`，非 8,557 的前身），正式集合以 8,557 為準、來源檔為 `JSON/furniture/furniture_official_catagory.json`。工程文件 MVP 資料層 `backend/catalog/data/engineering/` 共 14 項（work_items.json、material_catalog.json、material_work_mappings.json、equipment_mep_mappings.json、price_records.json、productivity_records.json、task_dependencies.json、construction_knowledge.jsonl、source_registry、production_templates/、DATA_DICTIONARY.md 等，`ls` 實測）。守門測試：`tests/test_cloud_quarantine.py`、`tests/test_official_*`、`tests/test_furniture_embeddings_sql.py`（檔名實測）。

---

### 2.11 架構/程式碼審查守門

```md
---
name: reviewer-architect-guard
description: "架構與程式碼走查清單；聚焦複雜度、邊界、回歸風險與安全。"
---
# 指令（你是嚴格但友善的 Reviewer）
逐條產出結論/風險/修正建議，鏈接到 SDD/DDD/合約或測試證據。

## 走查清單（RoomPilot 化節錄；正本=根目錄 AGENTS.md 11 條不可違反契約 :50-60）
- 邊界是否清晰？agent 層是否越界計算座標（紀律：座標一律 backend.engine；
  幾何決策不得移到 Graph RAG、瀏覽器或 LLM——根目錄 CLAUDE.md 禁令）？
- 單位是否公分？跨模組幾何新欄位是否帶 _cm/_m2 後綴（AGENTS.md:50）？
- 不變量是否由測試守護？例外是否可觀測？
- 合約是否可版本化？欄位/行為變更是否同步 docs/contracts/ 與兩端測試？
- 錯誤語意是否沿用既有詞彙（409/410/413/415/422/429/502/503 與工程文件大寫 error_code）而非自創？
- 測試證據：python -m pytest -q 是否綠燈？新行為有無對應測試？
- LLM 相關：失敗是否降級本地規則而非硬失敗？回應是否標明來源
  （selection_source = openrouter / local_rules / local_rules_unvalidated）？
- 跨 owner 目錄修改是否填了 AGENTS.md 的 6 欄跨資料夾記錄
  （主要/協作 owner、修改檔案、契約變更、為何跨目錄、兩端驗證測試）？
- 安全走查：觸碰 backend/server、新端點、上傳/URL 抓取/DB 查詢/秘密時，
  載入 roompilot-security skill 跑 audit.sh（該 skill 風險基線寫
  「全端點無認證/授權、外部抓取無 SSRF 防護、DB 預設明文連線」，SKILL.md:17；
  2026-08-04 實測例外：`/api/admin/furniture*` 4 條已有 Bearer token 授權，
  無效或缺憑證回 401——catalog_admin.py:171-197）。
```

**RoomPilot 套用**：已查證落點：選件來源標記在 `backend/server/main.py:2888,2995,3007,3012,3022`（`openrouter`/`local_rules`/`local_rules_unvalidated`）；審查正本＝根目錄 `AGENTS.md`（動手前 6 步 :5-12、跨資料夾 6 欄格式 :20-28、11 條契約 :50-60、驗證矩陣 7 類 :64-72、最終整合 3 指令 :76-80）；`roompilot-security` skill 已入版控（`.claude/skills/roompilot-security/`，SKILL.md＋audit.sh＋references/remediation.md）。

---

### 2.12 CI/CD 品質柵欄（搭配 Hooks）

```md
---
name: ci-quality-gates
description: "把品質門檻寫進流水線；覆蓋率、靜態分析、合約與 E2E 必通。"
---
# 指令（你是 DevEx 工程師）
輸出 CI 階段與條件；對未達標的情境提供自動化修正建議/指令。

## 交付結構
- **Stages**：Lint → Unit → Contract → Integration → E2E → Perf/Chaos
- **門檻**：Coverage、Lint/Type Check、Contract Tests 全通、金路徑 E2E
- **Artifacts**：合約報告、基準數據、回歸矩陣
- **Hook 範例**：提交後自動格式化/阻擋敏感檔變更/通知

## RoomPilot 現況（2026-08-04 實測）
- repo 無 .github/、無任何 CI 流水線；品質柵欄 = 本機測試三件套（AGENTS.md:76-80）：
  `python -m pytest -q`、`git diff --check`、`git status --short`（不覆蓋他人未提交變更）。
- tests/ 99 支 test_*.py + tests/static/ 3 支 .test.mjs + training/tests/ 11 支。
- .claude/hooks/ 有 8 檔（post-write.sh、pre-tool-use.sh、session-start.sh 等），本機檔不入版控；
  .claude/settings.json 以 permissions.deny 阻擋 .env/secrets/credentials 讀寫（實測讀檔）。
- Lint/型別檢查工具（ruff/mypy）未列於 pyproject.toml（grep 無命中），未導入。
- 待補：CI 平台選型、覆蓋率門檻數值、合約測試在流水線的強制點。
```

（將不可或缺的動作用 hooks 自動化以「保證」執行。（[docs.claude.com][2]））

**RoomPilot 套用**：已查證落點：`.github/` 不存在（`ls` 實測）；`pyproject.toml` 有 `[tool.pytest.ini_options] pythonpath=["."]`；依賴基準 `requirements.txt`（2026-07-27 Windows + Python 3.12.13 驗證，21 個 pin、5 組 owner 分組；opencv 註解明言需鎖 <5 否則門偵測會壞）；torch 為選配（約 2GB，房型語意層必要性待 Ben 端拍板——requirements.txt 註解）。

---

## 3. 前/後端與跨系統的「風格建議」（RoomPilot 版）

* **設計與實作流程**：建議採 §2.1 SDD → §2.2 DDD → §2.3 資料庫綱要 → §2.4 後端實作 → §2.5 API 合約的順序，由宏觀到微觀；RoomPilot 的既有邊界（agent 決策/engine 幾何/公分制/quarantine 隔離）是每一步的硬約束，不因文件形式而放寬。現行入口是 Action Skills（`/intake → /specify → /deliver → /verify`，`.claude/skills/`，本機檔）而非 `/output-style` 切換。
* **前端開發**：以 §2.8 為核心，用行為案例描述元件；先分清目標是 `backend/server/static/`（正式，含 scene/engineering/rag 三個工作頁）還是 `frontend3d/`（次要原型）。互動測試工具（Storybook 等）待補。（[Storybook][7]）
* **後端開發**：以 §2.7 實踐紅綠重構；幾何與擺位函式（`backend/engine/`）與工程文件五段流（`backend/server/engineering/`）是最高價值的 TDD 對象，證據一律 pytest。
* **整合與演進**：使用 §2.9 與 §2.10 守護四類外部邊界（遠端渲染＋內建生圖/OpenRouter/CloudFront/PostgreSQL-pgvector）與 8,557 件型錄契約。
* **品質保證**：透過 §2.11 進行人工審查（正本＝根目錄 `AGENTS.md`），資安面用 `roompilot-security` skill；§2.12 目前只能描述目標狀態，因 repo 尚無 CI（實測）。
* **交付物產出**：工程報告下游有兩支版控 skill 承接——`roompilot-proposal`（ReportPayload→屋主提案，verify_numbers.py 擋編造數字）與 `roompilot-budget`（ReportPayload→估價排程文件，零 LLM 文字）；檢索語句撰寫用 `roompilot-furniture-query`（口語→受控詞彙，餵 POST /api/rag/search）。
* **Claude Code 操作**：`/output-style` 僅用於呈現類樣式（現存 `Vision Output` 一支）；`/hooks` 建立格式化/檔案保護/通知。（[docs.claude.com][1]）

---

## 4. 最小可行落地（RoomPilot 版）

1. **樣式極簡化已完成，不要回退**：`.claude/output-styles/` 只留 `15-Vision-output.md`；需要流程規範時載入對應 skill 或複製本目錄模板，不要再把流程做成全域樣式（`.claude/OUTPUT_STYLES.md` 的裁決）。
2. 先用 §2.1 SDD 把一條新管線「說清楚」——首選 `backend/server/engineering/` 五段流（snapshot→lock→packages→jobs→documents），契約對照 `docs/contracts/ENGINEERING_DOCUMENT_MVP.md` 與 `engineering_openapi.yaml`。
3. 用 §2.2 DDD 對照 `backend/agent/knowledge.py` 與 `select.py:32-34` 的既有不變量，把選件聚合拉齊；新增規則先問「這是不變量還是流程慣例」。
4. 用 §2.3 對照 PostgreSQL 五階段契約與四份 DDL 正本，檢視 Phase4 runtime catalog 與 Phase5 單一事實來源的推進狀態。
5. 用 §2.4 生成骨架時遵守 agent/engine 分界與公分制；新路由群一律開 APIRouter（比照 rag_api.py/catalog_admin.py/engineering/api.py），不往 main.py 塞。
6. 用 §2.7 挑一個高風險函式（例：`check_placement_with_clearance`，clearance.py:89），紅綠重構把不變量守起來。（[martinfowler.com][5]）
7. Hooks 與 skills 的版控邊界維持現狀：`.claude/skills/` 的 roompilot-* 四支入版控全隊共享；hooks 與 Action Skills 仍為本機檔——是否納入版控屬團隊裁決事項，待補。（[docs.claude.com][2]）

---

## 5. 參考來源（精選）

* Claude Code 官方：**Output Styles** 說明與檔案位置、`/output-style` 指令。（[docs.claude.com][1]）
* Claude 工程部落格：**最佳實務與工作流**。（[anthropic.com][8]）
* IEEE Std 1016：**SDD 結構與資訊內容**。（[IEEE Standards Association][3]）
* DDD：Evans **Reference**（聚合、不變量、界限脈絡）。（[Domain Language][4]）
* TDD：Fowler **Red-Green-Refactor**。（[martinfowler.com][5]）
* BDD/Gherkin：Cucumber 官方文件。（[cucumber.io][6]）
* 前端測試：Storybook 元件/互動測試。（[Storybook][7]）
* RoomPilot 內部正本：`docs/contracts/`（22 檔）、根目錄 `AGENTS.md`、`docs/TEAM_AI_OWNERSHIP.md`、`.claude/OUTPUT_STYLES.md`（樣式極簡化裁決，本機檔）、`.claude/skills/roompilot-*`（4 支版控 skill）。
* 模板包內連結 `docs/document-system/architecture.md`、`software_development_documentation_guide_zh_tw.docx`：(未查證：來源不在 repo)。

---

# 心法內化（像 5 歲小孩也懂）

把蓋房子想成三件事：**先畫藍圖（SDD）**，**再決定每個房間的規則（DDD）**，**最後拿尺量一量做對了沒（BDD/TDD）**。以前我們每次動工都「換一頂帽子」（切 Output Style）；現在發現帽子戴著不摘會影響後面每句話，所以改成**把工具收進工具箱（skills 與模板）**，要用哪個拿哪個，頭上只留一頂「畫圖說話」的帽子（Vision Output）。RoomPilot 剛好就是在幫使用者「蓋房間」——平面圖→規則→驗證，同一套思路。

# 口訣記憶（3 點）

1. **先邊界，後行為，再函式**（SDD/DDD → BDD → TDD）
2. **樣式管呈現，流程進 skill**（`/output-style` 只剩 Vision Output；流程走 `/intake → /specify → /deliver → /verify` 與 roompilot-* skills）
3. **證據說話**（合約在 `docs/contracts/`、測試用 `python -m pytest -q`，避免口號）

[1]: https://docs.claude.com/en/docs/claude-code/output-styles "Output styles - Claude Docs"
[2]: https://docs.claude.com/en/docs/claude-code/hooks-guide "Get started with Claude Code hooks - Claude Docs"
[3]: https://standards.ieee.org/ieee/1016/4502/ "IEEE 1016-2009 - Systems Design"
[4]: https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf "Domain-Driven Design Reference"
[5]: https://martinfowler.com/bliki/TestDrivenDevelopment.html "Test Driven Development"
[6]: https://cucumber.io/docs/gherkin/reference/ "Reference"
[7]: https://storybook.js.org/docs/8/writing-tests/component-testing "Component tests | Storybook docs - JS.ORG"
[8]: https://www.anthropic.com/engineering/claude-code-best-practices "Claude Code: Best practices for agentic coding"
