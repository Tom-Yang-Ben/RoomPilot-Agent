# 文檔與維護指南 - RoomPilot-Agent

> 本文件由 VibeCoding 模板 15_documentation_and_maintenance_guide.md 導入 RoomPilot-Agent 生成 | 基準分支 bella-local-20260726 | 2026-07-26

> **版本:** v1.0 | **更新:** 2026-07-26 | **狀態:** 活躍

**衝突優先序(全 repo 文件通用)**:實際欄位與行為和文件衝突時,依序以「自動化測試 > 可執行程式 > 正式契約(`docs/contracts/`) > 總覽文件」為準(出處:`docs/RoomPilot_現行版本總覽.md` 開頭)。本指南描述文件本身的角色、更新時機與版控規則,不覆寫上述優先序。

---

## 1. 文檔類型

| 類型 | RoomPilot 實際載體 | 格式 |
| :--- | :--- | :--- |
| **API 文檔** | `docs/vibecoding/06_api_design_specification.md`(538 行);API 實體為 `backend/server/main.py` 44 條路由(grep `@app.get/post/put` 實數,無 APIRouter 拆分)。無手寫 OpenAPI YAML;`main.py:144` 建立 `FastAPI(title=...)` 時未覆寫 `docs_url`,依 FastAPI 預設應提供 `/docs` 與 `/openapi.json` 自動文件(未實測啟動驗證) | Markdown;OpenAPI 為執行期自動生成 |
| **架構文檔** | `docs/RoomPilot_現行版本總覽.md`(193 行,跨模組協作的導航)、`docs/vibecoding/05_architecture_and_design_document.md`(936 行)、`docs/vibecoding/09`/`10`(依賴與類別關係) | Markdown + Mermaid |
| **契約文檔** | `docs/contracts/` 6 份正式契約(見第 2 節表格)——模板原無此類型,RoomPilot 以契約取代零散的介面說明 | Markdown |
| **使用者/操作文檔** | `README.md`(270 行):安裝、啟動(`uv run uvicorn backend.server.main:app --port 8002`)、組員同步 Bella、驗收基準(`floor04.png` → 19 牆/5 門/5 窗/7 房)、離線備援驗證 | Markdown |
| **開發者文檔** | `README.md`「團隊目錄與合併規則」「版本控制規則」段、`docs/vibecoding/` 全套、各模組 `README.md`(`backend/engine/`、`backend/catalog/data/`、`scripts/sql/` 等) | Markdown |

---

## 2. 文檔即程式碼

### 目錄結構(2026-07-26 實測)

```
docs/
├── RoomPilot_現行版本總覽.md      # 跨模組架構導航(唯一根層文件)
├── contracts/                     # 6 份正式契約,不存個人進度
│   ├── AGENT_FRONTEND_BACKEND_CONTRACT.md   (213 行,最後更新 2026-07-23)
│   ├── CATALOG_MODEL_DELIVERY_CONTRACT.md   ( 84 行,最後更新 2026-07-23)
│   ├── FURNITURE_ENGINEERING_RULES.md       (187 行)
│   ├── LAYOUT_EVALUATION_SCHEMA.md          (173 行,自標「提案契約,尚未完整接入 API」)
│   ├── REMOTE_RENDER_CONTRACT.md            ( 71 行)
│   └── STYLEPACK_RENDERING_CONTRACT.md      (119 行)
├── backlog/                       # 已確認要追蹤但尚未完成的工作
│   └── FLOORPLAN_DATASET_TUNING.md          ( 41 行,狀態:待執行)
├── moodboard_assets/              # 12 張舊風格 moodboard PNG + representative_furniture/
└── vibecoding/                    # 本套件:VibeCoding 模板導入文件(01–10 已導入 + 本 15 號)
```

模組層文件(docs/ 之外):

- `README.md`(repo 根,唯一根層 Markdown,ls 實測)
- `backend/engine/README.md`、`backend/catalog/data/README.md`、`backend/catalog/data/quarantine/*/README.md`、`scripts/sql/README.md`、`frontend3d/README.md`、`examples/demo_app/README.md`、`backend/floorplan/vision/icon_templates/README.md`、`backend/server/static/vendor/draco/README.md`、`backend/agent/prompts/ROOMPILOT_LLM.md`(git ls-files `*.md` 實列)

### 各文件 SSOT 角色與更新時機

| 文件 | SSOT 角色(對什麼是唯一事實來源) | 更新時機 |
| :--- | :--- | :--- |
| `README.md` | 安裝、啟動、組員同步、驗收基準、團隊目錄負責人表、合併規則、版本控制規則 | 啟動方式/port/依賴 extras 變更時;團隊分工或合併規則變更時 |
| `docs/RoomPilot_現行版本總覽.md` | 跨模組協作:產品流程、責任分界、資料流、單位契約(公分制)、已接入/尚未接入清單 | 模組接入狀態變更、流程步驟增刪、責任目錄調整時。注意:它「只描述目前程式可核對的責任」,不記錄個人進度與歷史測試結果(該檔開頭自述) |
| `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md` | Yen Agent、AN 引擎與 Bella 前後端之間已接入的介面行為(LLM 開關、fallback、修復 action 詞彙) | Agent/引擎介面欄位或行為變更時;檔頭「最後更新」日期須同步改 |
| `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md` | 家具 metadata 與雲端 GLB 的交付規則(cloudfront 模式、Manifest 對應順序、410 行為) | Manifest 檔、delivery 模式或映射規則變更時 |
| `docs/contracts/FURNITURE_ENGINEERING_RULES.md` | `furniture_candidates` 家具工程欄位寫法(AI agent 中間資料層;不取代 `backend.engine.schema` 的 tool schema) | 候選欄位增刪時 |
| `docs/contracts/LAYOUT_EVALUATION_SCHEMA.md` | 擺放後評估資料格式的**目標**契約(自標尚未完整接入;現行 `/api/scene/validate` 只回 ok 與 reason) | 評估 API 真正接入時,同步移除「提案」標記 |
| `docs/contracts/REMOTE_RENDER_CONTRACT.md` | 第 10 步遠端渲染:mode 白名單、私人欄位剝除、503/502 行為、環境變數 | `render_service.py` 行為變更時 |
| `docs/contracts/STYLEPACK_RENDERING_CONTRACT.md` | 6 風格 × 3 色卡 = 18 張的 ID 體系與渲染資料來源清單;具體色碼以程式資料為準(該檔自述) | 風格/色卡/燈光 profile 增減時 |
| `docs/backlog/*.md` | 已確認要做但未完成的工作(現有 1 筆) | 新債務確認時新增一檔;完成時移除或併入契約 |
| `docs/vibecoding/01–10、15` | 模板導入的流程/規格/結構文件;每份檔頭帶基準分支與日期 | 對應主題有重大變更時重新對齊;新導入模板時新增(11–14、16、17 尚未導入,模板在 `VibeCoding_Workflow_Templates/`,未入版控) |
| `backend/catalog/data/README.md` | 正式家具集合規則:9,350 件由 cloud catalog + Manifest 一對一決定;quarantine 禁用規則 | 型錄檔或映射規則變更時(有 `tests/test_cloud_quarantine.py` 等測試背書) |
| `scripts/sql/README.md` | PostgreSQL 匯入器用法與 dry-run 期望診斷數字(9350/9021/329/1514) | 匯入器 CLI 或 schema 變更時 |
| `backend/engine/README.md` | engine 模組結構與職責表 | 引擎模組增刪時。注意:檔內「對應 SSOT:第 4 節」所指的 SSOT 文件不存在於本分支(find 實測無 SSOT 檔),屬過時引用,待修 |
| `backend/agent/prompts/ROOMPILOT_LLM.md` | 版本化提示參考;檔內自述 runtime 不載入,未實作項目不得視為已完成 | 提示策略變更時 |
| `frontend3d/README.md`、`examples/demo_app/README.md` | 無 SSOT 角色——內容已過時(前者寫 port 8000 與 `app/backend/` 舊路徑,與 `vite.config.js` proxy 8002 矛盾;後者自述已退役且仍引用已廢除的 ControlNet 計畫) | 待裁決:更新或標記淘汰(見第 3 節待修清單) |

### .gitignore 對 docs/ 的規則

`docs/` 採「預設全忽略 + 白名單豁免」(`.gitignore` 第 41–50 行,實測):

```gitignore
docs/*
!docs/*.md
!docs/backlog/
!docs/backlog/*.md
!docs/contracts/
!docs/contracts/*.md
!docs/moodboard_assets/
!docs/moodboard_assets/**
!docs/vibecoding/
!docs/vibecoding/*.md
```

- **地雷**:放進 `docs/` 新子目錄的文件若不在豁免清單內,git 會**默默忽略**,不會出現在 `git status`。新增文件類別時必須同步加 `!docs/<subdir>/` 與 `!docs/<subdir>/*.md` 兩行。
- `!docs/vibecoding/` + `!docs/vibecoding/*.md` 兩行於 2026-07-26 新增,**尚未 commit**(git diff 實測);`docs/vibecoding/` 目錄本身也尚未入版控(git status 顯示 untracked)。本套件文件的入庫依賴這筆 .gitignore 修改先行提交。
- 另忽略 `docs/MISSING_*_AUDIT_*.md`(第 67 行,稽核暫存檔不入庫)。
- 個人生成文件一律不入庫(第 52–69 行):`CLAUDE.md`、`AGENTS.md`、`.claude/`、`.codex/`、`PROJECT_CONTEXT.md`、`LOCAL_*/PRIVATE_*/PERSONAL_*` 與 `*_LOCAL/_PRIVATE/_PERSONAL.md` 各大小寫變體。
- 與文件相鄰的其他規則:`scripts/*` 全忽略但豁免 `verify_ikea_offline_backup.py` 與 `scripts/sql/**`(第 26–29 行);`*.glb`(第 72 行)、`dataset/`、`.runtime/`、`.env` 不入庫。

### 文件命名慣例(自現況歸納)

| 位置 | 慣例 | 實例 |
| :--- | :--- | :--- |
| `docs/` 根層 | 中文描述性檔名,唯一一份總覽 | `RoomPilot_現行版本總覽.md` |
| `docs/contracts/` | 全大寫蛇形英文 + `.md`,名稱含 CONTRACT/RULES/SCHEMA 類型字尾 | `REMOTE_RENDER_CONTRACT.md` |
| `docs/backlog/` | 全大寫蛇形英文,一項追蹤工作一檔 | `FLOORPLAN_DATASET_TUNING.md` |
| `docs/vibecoding/` | 兩位數編號 + 小寫蛇形英文,編號對齊 `VibeCoding_Workflow_Templates/` 模板序號 | `15_documentation_and_maintenance_guide.md` |
| 模組目錄 | 一律 `README.md` 就地放在被說明的目錄內 | `backend/catalog/data/README.md` |
| vibecoding 檔頭 | 首兩行固定:H1 標題 +「本文件由 VibeCoding 模板 … 導入 … 基準分支 … 日期」引用註記,再接版本行 | 見 `01_workflow_manual.md` 第 1–5 行 |

### 撰寫規範

- **簡潔明瞭**:直接切入重點;總覽自述「只描述目前程式可核對的責任」,不寫個人進度與歷史數字。
- **主動語態**:「設定伺服器」而非「伺服器應被設定」。
- **包含範例**:指令必須可執行(如 `uv run pytest tests/ -q`)、數字必須可複測(如 `floor04.png` 19 牆/5 門/5 窗/7 房)。
- **標示未接入**:契約描述「提案」或「尚未接入」時,不得在 UI、README 或總覽中宣稱已完成(出處:總覽「正式契約」段)。
- **版本控制**:契約檔頭維護「最後更新」日期;vibecoding 檔頭維護基準分支與 HEAD。

---

## 3. 維護排程

RoomPilot 是課程專題,無月/季營運節奏;模板的「每月/每季」對應為「每次合併節點/里程碑前」。

### 每次合併前(事件驅動,對應模板「每月」)

- [ ] 欄位或行為變更是否同步 `docs/contracts/` 對應契約?檔頭「最後更新」是否更新?
- [ ] 流程步驟或接入狀態變更是否同步 `docs/RoomPilot_現行版本總覽.md` 與 `README.md`?
- [ ] 步驟順序描述是否以程式碼為準?唯一有序來源是 `backend/server/static/scene_workflow.js` 的 `WORKFLOW_STEPS`(11 個內部步驟:project → upload → recognition → calibration → space_confirmation → requirements → layout_2d → white_model_3d → realistic_3d → proposal_review → ai_render;recognition 與 calibration 共用 scale 面板,UI 顯示 10 顆按鈕)。伺服器端 `main.py` 的 `WORKFLOW_STEPS` 是無序 set,只驗名稱。
- [ ] 新增的文件是否落在 `.gitignore` 豁免範圍?(`git status` 看得到才算入庫)
- [ ] 文件內的指令與數字是否仍可複測?(型錄 9,350、色卡 18、測試收集 392 等)

### 里程碑前(對應模板「每季」)

- [ ] 全面核對總覽的「已接入/尚未接入」清單與實際程式。
- [ ] 清理下表已知待修項。
- [ ] `docs/backlog/` 逐檔確認狀態仍為真。

### 已知待修文件清單(2026-07-26 實測)

| 文件 | 問題 | 依據 |
| :--- | :--- | :--- |
| `docs/RoomPilot_現行版本總覽.md` | 第 12 行寫「目前固定為八個步驟」,但同檔緊接的表格列 10 步、程式碼為 11 內部步驟/10 顆按鈕——以程式碼為準,「八」為舊殘留 | 該檔 L12 vs L14–25;`scene_workflow.js` |
| `README.md` 與總覽 | 各有一句編輯殘缺:「不再建立\n不再保留舊版巢狀後端命名」接不上 | README L5–7;總覽 L94–95 |
| `frontend3d/README.md` | port 寫 8000、路徑寫 `app/backend/`/`app/frontend/`、DXF 來源寫 `pic/temp/`,與 `vite.config.js`(proxy 8002)及根 README 啟動指令矛盾 | 兩檔實測比對 |
| `examples/demo_app/README.md` | 自述 demo 已退役,仍引用已廢除的 ControlNet 計畫 | 該檔與 `examples/demo_app/main.py` 註解 |
| `backend/engine/README.md` | 「對應 SSOT:第 4 節」所指 SSOT 文件不存在於本分支 | find 實測無 SSOT 檔(其他分支未查證) |
| `.gitignore` | `!docs/vibecoding/` 豁免兩行未 commit;`docs/vibecoding/` 整目錄 untracked | git diff / git status 實測 |
| `docs/vibecoding/` | 模板 11–14、16、17 尚未導入(模板目錄 `VibeCoding_Workflow_Templates/` 為 untracked,去留待裁決) | ls 實測 |

---

## 4. README 模板

repo 已有實際 README,以下為其現行章節骨架(grep `^#` 實測),新增段落沿用此結構,不套用模板的通用骨架:

```markdown
# RoomPilot-Agent
## 團隊目錄與合併規則      # 6 人目錄負責人表 + 路徑規則 + 合併方式
## 現行流程                # 十步驟流程摘要
## 主要功能                # 六種住宅風格 / Test2 需求問卷(題庫 55 組) / 家具資料庫 / 3D 場景
## 載入效能
## 專案結構
## 啟動方式                # uv / Windows 虛擬環境 / 組員同步 Bella(含 floor04.png 驗收基準)
## 家具模型來源與離線備援   # 9,350 件 CloudFront;離線 zip SHA-256 驗證
## 測試                    # uv run pytest tests/ -v 與重點測試檔
## 版本控制規則            # .env 不提交、.glb 不新增提交、離線備援包不入 repo
```

分工邊界:README 負責安裝與啟動,總覽負責跨模組協作(兩檔開頭互相聲明)。模板建議的「貢獻(CONTRIBUTING.md)」「授權」段落現況皆無:repo 無 `CONTRIBUTING.md`、無 LICENSE 檔(ls 實測),合併規範直接寫在 README「合併方式」段——是否補 LICENSE 待裁決。

---

## 5. CHANGELOG 模板

現況:repo 無 `CHANGELOG.md`(ls 實測),變更紀錄實質上就是 git log。現行 commit 訊息有兩種風格並存(git log 實測):

- Conventional Commits 英文:`fix(catalog): harden cloud database import`、`feat(catalog): integrate official cloud furniture catalog`
- 中文前綴:`新增:依已確認房間預選共通問卷`、`修正:需求問卷特殊選項卡住`、`功能:支援跨電腦匯入匯出專案`、`整合:同步遠端 Bella 並保留 Codex 功能`

兩種風格未統一,無書面規範——是否收斂為單一慣例、是否建立 CHANGELOG.md 均待裁決。若日後建立,沿用模板骨架:

```markdown
# 變更記錄

## [Unreleased]
### 新增
### 變更
### 修復

## [0.1.0] - YYYY-MM-DD    # 版號對齊 pyproject.toml(現為 roompilot-agent 0.1.0)
### 新增
- 初始版本
```

在此之前,查變更的實際入口是 `git log --oneline` 與總覽的「已接入/尚未接入」清單。

---

## 6. 最佳實踐

1. **隨開發同步撰寫**:欄位或行為變更與契約更新在同一次合併內完成(總覽「跨階段」規則);不要事後補文檔。
2. **文檔也要 Review**:合併進 Bella 整合分支時,整合者逐 commit 檢視的範圍包含文件;契約若把「提案」寫成「已完成」即是缺陷(總覽「正式契約」段明文禁止)。
3. **目錄負責人制,人人有責**:每位成員維護自己主要目錄的 README 與對應契約(README 目錄負責人表);Bella 維護 README 啟動段與總覽整合狀態。
4. **文件聲明必須可複測**:寫入路徑、路由、指令、數字前先用工具查證;查不到就標「(未查證)」或「待補」——本套件(vibecoding 01–15)全部依此規則產出。
5. **入庫前檢查 .gitignore**:`docs/` 是白名單制,新子目錄先加豁免再寫文件,避免默默漏交。
