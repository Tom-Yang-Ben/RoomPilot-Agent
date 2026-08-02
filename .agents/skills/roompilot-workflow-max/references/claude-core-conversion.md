# `.claude` 核心資料轉換稽核

## 目的與優先順序

本文件記錄 `D:/RoomPilot-Agent/.claude/` 中「不含 `skills/`」的 87 個檔案，作為 RoomPilot workflow 最大模式的轉換依據。這不是原檔搬移清單，也不授權直接執行 `.claude` 內的命令、hook 或自動化。

套用時的優先順序如下：

1. repository 根目錄及最近層級的 `AGENTS.md`。
2. `README.md`、`docs/TEAM_AI_OWNERSHIP.md`、`docs/owners/`。
3. `docs/contracts/` 的公開資料契約。
4. 本 skill 的工作流程與參考資料。
5. `.claude` 中經本文件判定可轉換的通用方法。

如內容衝突，必須遵循 RoomPilot 現行契約；不得以 `.claude` 的通用範例覆蓋專案既有架構。

## 稽核範圍

| 類型 | 數量 | 處置摘要 |
|---|---:|---|
| Markdown | 64 | 萃取流程、角色與輸出格式；逐項去除 Claude 專屬語法及過時假設 |
| Shell scripts | 10 | 僅稽核風險，不轉入、不執行 |
| JSON settings | 1 | 不轉入；權限與 hook 設定風險過高 |
| Windows executable | 1 | 不轉入；來源與版本不可驗證 |
| Runtime/session files | 3 | 不轉入；含工作階段資料 |
| `.gitignore` | 1 | 無需轉換 |
| 空白 `.gitkeep` | 7 | 無語意，不轉換 |
| **合計** | **87** | `skills/` 另行處理，不在本稽核範圍 |

已盤點但未讀取 runtime 內容：`.claude/logs/` 與 `.claude/taskmaster-data/`。狀態列執行檔 `statusline-go.exe` 的 SHA-256 為 `6ED22871CEBC39B47300446FAEFCB183135AECECF8032AC9FBB303B2765285C2`；此雜湊只供辨識，不代表可信或可移植。

## 功能分組與轉換決策

| 群組 | 原始能力 | 轉換決策 | RoomPilot 落點或限制 |
|---|---|---|---|
| `CLAUDE.md`、`README.md`、`WORKFLOW.md` | Claude Code 入口、TaskMaster、工作流程說明 | **部分轉換** | 只保留「先讀規範、拆解、驗證、交付」的流程；改以本 skill 為入口 |
| `agents/` | 規劃、架構、測試、審查、修復、部署等 13 種角色 | **轉換並合併** | 移除 `model: opus`、Claude tools 與自動委派假設；加入 owner、契約、測試責任 |
| `commands/` | plan、TDD、build、E2E、verify、review、quality、task 等 17 個命令 | **轉為 recipes** | 不保留 slash command 語法；保留明確輸入、輸出、停止條件與驗證指令 |
| `rules/` | 開發、程式、Git、安全、效能、測試、上下文等 8 組規則 | **部分轉換** | 通用檢查可保留；與 `AGENTS.md` 衝突者淘汰 |
| `context/`、`coordination/` | ADR、共享報告、handoff、衝突處理 | **可選模板** | 只能由工作需求明確觸發；不可靜默寫入或覆蓋現有文件 |
| `output-styles/` | PRD、BDD、架構、API、TDD、review、安全、資料、CI 等 15 種格式 | **選擇性轉換** | 改寫為 RoomPilot 契約導向模板；不把範例技術棧視為專案標準 |
| `mcp-configs/` | MCP server 設定示例 | **概念保留、設定排除** | 可列能力需求；不得複製 raw key、`@latest` 或未核准 server 設定 |
| `hooks/` | session、prompt、tool、agent 監控 | **排除** | 不轉入、不執行；涉及隱私、靜默寫入及刪檔 |
| `settings.json` | 權限、hook、statusline、model | **排除** | 不沿用 Claude Code 權限模型，尤其是廣泛 Bash/Write/Edit 權限 |
| `statusline*` | 狀態、費用、速率、憑證與工作階段資訊 | **排除** | 不轉入 shell、debug script 或 exe；不得讀取或轉送 OAuth 憑證 |
| `logs/`、`taskmaster-data/` | log、snapshot、session、timelog | **排除** | 視為本機 runtime；不得成為 skill 資產或範本 |

## 可轉換的核心能力

### 1. 契約導向工作流程

可將通用流程轉為以下順序：

1. 讀取根與最近層級 `AGENTS.md`、README、owner 文件及受影響 contracts。
2. 執行 `git status --short`，辨識並保留他人未提交變更。
3. 追查輸入、輸出、座標單位、schema version、保存邊界及生產端／消費端。
4. 提出預計修改檔案與驗證指令；跨 owner 時先記錄跨資料夾修改說明。
5. 以最小相容修改實作，執行目標測試、完整測試、`git diff --check` 與狀態檢查。

### 2. 角色能力

可保留 planner、architect、reviewer、security、testing、E2E、build-fix、refactor、documentation、deployment 等能力，但應視為工作階段中的職責，不是固定模型或必然啟動的 agent。角色產出必須包含：

- 主要 owner 與協作 owner。
- 受影響的公開契約與資料流。
- 目標檔案、風險、回復策略與驗證證據。
- 未解決問題與需要使用者決策的邊界。

`tdd-guide` 與 test automation 可合併；general-purpose 為冗餘角色；workflow-template-manager 應改為 skill 內的模板維護流程。

### 3. 命令 recipes

可轉換的 recipe 包括：規劃、測試先行、build-fix、驗證、程式審查、品質門檻、E2E 與模板一致性檢查。每個 recipe 應：

- 接收明確目標、範圍與 owner。
- 先做唯讀診斷，再進入已授權的修改。
- 不自動刪檔、回退使用者修改、建立遠端資源或安裝套件。
- 以 RoomPilot 驗證矩陣決定最低測試，不套用 npm-first 的通用假設。

### 4. 輸出模板

優先轉換：PRD、BDD、architecture、API contract、TDD、code review、security review、integration、data evolution、CI quality gates、visualization。

需要大幅改寫：DDD、database schema、backend Python implementation。這些模板不得建立第二套 `src/<bounded_context>`、獨立 FastAPI/Clean Architecture、service-owned database、RabbitMQ 或 Kubernetes 架構。

frontend component BDD 只能供 `frontend3d/` 原型參考；正式八步流程仍位於 `backend/server/static/`，不得以 React/Storybook 範例取代。

## 必須注入的 RoomPilot 契約

所有轉換後的 workflow、recipe、角色與模板均必須明確遵守：

- 跨模組幾何以公分為單位；新長度與座標欄位用 `_cm`，面積用 `_m2`。
- 舊欄位 `width`、`depth`、`pos_x`、`pos_y` 必須同時提供 `coordinate_unit: "cm"` 與 schema version。
- 平面圖辨識輸出為 `layout_json`；方案生成與編輯輸出為 `scene_json`，兩者不可混用。
- Graph RAG 只提供房間、家具、風格、材質、限制的關係與證據；不得決定幾何、碰撞、淨空或結構合法性。
- 家具合法位置只能由 `backend/engine/` 判定。
- 第 6 步正式家具優先使用 PostgreSQL `roompilot.furniture_catalog_current`；資料庫不可用時才回退已驗證 JSON。
- 冰箱、洗衣機等家電只保留在問卷與 AI 生圖上下文，不可進入 2D/3D 自動配置或正式家具 API。
- 隔離區與未匹配資料不得進 API 或場景。
- 正式網頁位於 `backend/server/static/`；`frontend3d/` 是次要原型。
- 跨資料夾修改必須記錄 owner、檔案、契約變化、跨域必要性及兩端測試。

## Claude 專屬內容與漂移

以下項目不能直接成為 Codex/RoomPilot 規範：

- Claude Code 的 frontmatter、`model: opus`、tool 名稱、slash command、hook matcher 與 statusline protocol。
- TaskMaster 相依檔不完整：缺少 `.claude/taskmaster.js`、`taskmaster-data/project.json` 與 `taskmaster-data/wbs.md`。
- 文件引用但不存在：`.claude/SOP.md`、`.claude/settings.local.json`、`.claude/hooks-config.json`、根目錄 `CLAUDE_TEMPLATE.md`、根目錄 `.mcp.json`。
- `.claude/README.md` 宣告 7 組 rules，實際為 8 組；output styles README 宣告 9 種，實際為 15 種。
- 13 個 agent 檔皆指定 `opus`，但 README 描述多數使用 `sonnet`。
- hooks README 與 script 對 log 路徑的描述不同；pre/post tool matcher 也沒有涵蓋 script 內宣告的所有分支。
- review checklist 權重合計為 110%，不可直接作為品質分數。
- 範例含已過時或非專案基準的日期、OWASP 2021、`actions/checkout@v3` 與 npm-first 假設，導入前必須重新驗證。

## 高風險項目

### 權限與破壞性操作

`.claude/settings.json` 允許廣泛的 Bash、`Write(*)`、`Edit(*)`，且 deny/ask 未形成有效防護；其中包含 `rm` 與 `sudo` 類權限。不得複製。

下列內容只作為禁止案例，不可轉成自動 recipe：

- `agents/build-error-resolver.md` 的 cache、`node_modules`、lockfile 刪除。
- `commands/refactor-clean.md` 的 `git checkout -- <file>` 回退。
- `rules/git-workflow.md` 的遠端 branch 刪除。
- `hooks/watch-agents.sh`、`hooks/session-start.sh` 的 log/snapshot 刪除。
- `output-styles/14-ci-quality-gates.md` 的自動套件更新。

### 隱私、憑證與外部傳輸

- `hooks/agent-monitor.sh` 會記錄完整 prompt/response。
- `hooks/user-prompt-submit.sh` 會記錄並傳遞使用者 prompt。
- `statusline.sh` 會探查環境變數、系統 keychain、`~/.claude/.credentials.json` 與 secret-tool，並以 bearer token 呼叫外部 endpoint。
- `statusline-debug.sh` 會將完整 session JSON 寫到暫存目錄。
- runtime log 可能含 session、成本、cwd 與 task 資訊。
- MCP 示例含 raw key 設定與未固定版本的 `npx -y ...@latest`。

以上內容均不得讀取、複製、轉送或包入新 skill。任何外部連線、憑證使用、安裝或設定變更都必須走目前工具的授權機制。

### 專案邊界衝突

- 通用 camelCase/API envelope 不能覆蓋 RoomPilot 的 exact endpoint schema、snake_case、`schema_version` 與 `_cm` 欄位。
- 通用 Python backend 模板不能在既有 owner 目錄之外建立第二套 backend。
- React/Storybook 模板不能被視為正式前端遷移許可。
- 微服務、每服務獨立 DB、RabbitMQ、Kubernetes 只可作架構選項評估，不能當成現況或預設方向。
- `rules/subagent-context.md` 的靜默自動寫入要求與 RoomPilot 的授權、dirty worktree 保護及跨 owner 流程衝突，應淘汰。

## 明確排除清單

轉換產物不得包含或重建：

1. `.claude/settings.json` 的權限、hook、model 或 statusline 設定。
2. `.claude/hooks/` 任何 script 或等價的自動 prompt/response 記錄。
3. `statusline.sh`、`statusline-debug.sh`、`statusline-go.exe` 或其憑證存取邏輯。
4. `.claude/logs/`、`.claude/taskmaster-data/` 的 session、snapshot、timelog 與其他 runtime 資料。
5. OAuth token、API key、credentials、keychain 讀取、bearer header 或 raw MCP secret。
6. `rm`、`sudo`、`git checkout --`、遠端 branch 刪除、自動套件更新等破壞性命令。
7. Claude 專屬 frontmatter、模型綁定、slash command 與 hook protocol。
8. 靜默寫入 context、未經同意的檔案生成、安裝、網路呼叫或外部資源建立。
9. 通用電商／微服務範例作為 RoomPilot 的規範性領域模型。
10. 將 React/Storybook 或 `frontend3d/` 宣告成正式產品前端。

## 轉換驗收條件

每份由本稽核衍生的文件應通過以下檢查：

- 能追溯到明確的 `.claude` 來源能力，但沒有逐檔整包複製。
- 已移除 Claude 專屬執行語法、模型假設、hook 與 runtime 相依。
- 已標示適用 owner、輸入／輸出、單位、schema、保存邊界及測試。
- 已注入 `layout_json`／`scene_json`、engine、RAG、catalog、appliance、正式前端等不可違反契約。
- 不含秘密、憑證、執行檔、log、snapshot 或破壞性命令。
- 修改前後均保留既有 dirty worktree，且只改動已宣告範圍。
- 文件變更至少執行目標內容檢查、`git diff --check` 與 `git status --short`；程式變更另依驗證矩陣測試。

## 主要證據來源

- `.claude/CLAUDE.md`、`.claude/README.md`、`.claude/WORKFLOW.md`
- `.claude/agents/`、`.claude/commands/`、`.claude/rules/`
- `.claude/context/`、`.claude/coordination/`、`.claude/output-styles/`
- `.claude/settings.json`
- `.claude/hooks/agent-monitor.sh`、`user-prompt-submit.sh`、`session-start.sh`
- `.claude/statusline.sh`、`.claude/statusline-debug.sh`
- `AGENTS.md`、`README.md`、`CLAUDE.md`
- `docs/TEAM_AI_OWNERSHIP.md`、`docs/owners/`
- `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`
- `docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md`
- `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`
- `docs/contracts/FURNITURE_ENGINE_ROOM_REQUIREMENTS_CONTRACT.md`
- `docs/contracts/STYLEPACK_RENDERING_CONTRACT.md`
