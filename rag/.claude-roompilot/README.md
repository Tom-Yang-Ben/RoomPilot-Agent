# .claude-roompilot 配置目錄

> **版本:** v5.0（RoomPilot 專用） | **更新:** 2026-07-28
> **專案:** RoomPilot 家具風格檢索系統（Python 3.11 / Gradio 6 / ChromaDB `furniture_v3`）

本目錄是通用開發模板 `.claude/` 針對 RoomPilot 改寫後的專用配置。
事實來源為 `PROJECT_BRIEF.md`，入口說明為 `CLAUDE.md`。

---

## 如何啟用

Claude Code 只讀取專案根目錄下的 `.claude/`。啟用本配置＝**把目錄改名**：

```bash
cd /Users/django_cheng/Public/AIPE_03/final_term/Demo2/RAG

mv .claude .claude-template-backup     # 1. 先備份原本的通用模板
mv .claude-roompilot .claude           # 2. 啟用 RoomPilot 配置
```

啟用後注意：

| 項目 | 是否需手動改 | 說明 |
| :--- | :--- | :--- |
| `settings.json` 路徑 | **要** | 內含 `statusLine` 與 6 個 hook 註冊，字串寫死為 `bash .claude-roompilot/…`，**啟用後必須全部改為 `bash .claude/…`**（見下方一鍵指令） |
| `hooks/*.sh`、`statusline.sh` | **不用** | 已改為由腳本自身位置推導配置目錄（`CLAUDE_CONFIG_DIR` / `CLAUDE_DIR_NAME`），改名後自動跟著走，**不需批次替換** |
| Subagent context | 不用 | 寫入路徑由 `.claude-roompilot/context/` 自動變為 `.claude/context/`（文件敘述請自行理解為新目錄名） |
| 各 `.md` 內的路徑字樣 | 不用 | 純文件敘述，不影響執行 |
| 還原 | — | `mv .claude .claude-roompilot && mv .claude-template-backup .claude` |

啟用後的 `settings.json` 路徑一次改完並驗證：

```bash
sed -i '' 's|\.claude-roompilot/|.claude/|g' .claude/settings.json
python3 -m json.tool .claude/settings.json > /dev/null && echo "settings.json OK"
grep -c 'bash .claude/' .claude/settings.json     # 應為 7（statusLine 1 + hook 6）
```

> **為什麼只有 `settings.json` 要改**：它是 Claude Code 在**讀取腳本之前**就解析的註冊表，
> 路徑由 Claude Code 以 cwd 為基準展開，腳本無從自我推導；
> `hooks/*.sh` 與 `statusline.sh` 則是執行時才解析路徑，因此能用 `${BASH_SOURCE[0]}` 自我定位。

> 本專案**尚未 git init**，改名不會產生任何版本控制副作用；備份請自行保留。

---

## 目錄結構（實際檔案）

```
.claude-roompilot/
├── settings.json              # 專案設定（權限、StatusLine、Model=opus、6 個 hook 註冊）
├── CLAUDE.md                  # 配置入口：專案事實、執行指令、SSOT、六個坑
├── PROJECT_BRIEF.md           # 事實來源（SSOT），與 CLAUDE.md 衝突時以本檔為準
├── README.md                  # 本檔：目錄結構與元件說明
├── WORKFLOW.md                # RAG 專案開發流程（四條主線）
├── STATUSLINE_GUIDE.md        # StatusLine 設定與排錯指南
├── statusline.sh              # StatusLine bash 腳本（macOS，唯一版本）
├── statusline-debug.sh        # StatusLine 除錯腳本
│
├── agents/        (13 個)     # 專業 Agent 定義
├── commands/      (17 個)     # Slash Command
├── rules/         (8 個)      # 自動載入規則
├── skills/        (12 個)     # 領域知識 Skill + INDEX.md + SUPERPOWERS-EXTRAS-USAGE-zh-TW.md
├── output-styles/ (15 個)     # 輸出樣式模板 + README.md
├── mcp-configs/               # MCP 推薦清單（README.md）
├── hooks/                     # Hook 腳本庫（7 個 .sh + README.md）
├── logs/                      # Agent 活動記錄（僅 .gitignore，執行後才產生 log）
├── taskmaster-data/           # 持久化資料（WBS、時間日誌）— 無資料，`timelog.jsonl` 為 0 bytes 空檔
├── context/                   # 跨 Agent 上下文共享（8 個子目錄 + README.md）
└── coordination/              # Agent 協調配置（human_ai_collaboration_config.md + README.md）
```

**與原通用模板 `.claude/` 的差異（2026-07-28 逐目錄比對，如實記錄）**：

| 項目 | 原模板 `.claude/` | 本配置 `.claude-roompilot/` | 差異說明 |
| :--- | :--- | :--- | :--- |
| `PROJECT_BRIEF.md` | 無 | **新增** | 本配置唯一事實來源（SSOT），改寫時的裁決依據 |
| `skills/` | **22 個**（13 個 sunnydata + 9 個 community） | **12 個** | **精簡 10 個**：9 個 community 前端類（a11y、frontend-design、react-*、ui-design-system、ux-*、web-guidelines）＋ `sunnydata-shadcn-ui`，全數捨棄 |
| `rules/` | 8 個（**已含** `subagent-context.md`） | **維持 8 個** | 數量不變，**內容全數改寫為 RoomPilot 事實**（Python 3.11／`.venv-rag/`／無 CI／尚未 git init） |
| StatusLine 變體 | `statusline.sh`、`statusline-debug.sh`、`statusline-linux.sh`、`statusline-go.exe` | 僅前兩者 | **捨棄跨平台變體** — 本專案只跑 macOS |
| `agents/` `commands/` `output-styles/` `hooks/` | 13／17／15＋README／7 支 `.sh` | 同數量 | 數量不變，內容全數改寫為 RoomPilot 情境 |
| `logs/` `context/` `coordination/` `mcp-configs/` | 已存在 | 已存在 | **非新增**；`logs/` 僅保留 `.gitignore`，實際 log 於首次觸發 hook 後產生 |
| `taskmaster-data/` 的 runtime 狀態檔 | `timelog.jsonl`（1,296 bytes）、`.session-snapshot`、`.session-start` | 僅 `timelog.jsonl`（**0 bytes 空檔**） | **已捨棄** — 原模板那些是**另一個專案的實際 session 遙測**，與 RoomPilot 無關，不得沿用或補寫假記錄。首次 session 結束後由 `statusline.sh` → `hooks/session-start.sh` 自動累積 |

> 原模板 `.claude/` 本來就**沒有** `settings.local.json` 與 `SOP.md`，
> 本配置同樣沒有 —— 兩者皆**不構成差異**，本表不再列出。
> 本配置的入口職責由 `CLAUDE.md` + `PROJECT_BRIEF.md` 承擔。

---

## 各元件說明

### Agents（13 個）

自動註冊，可透過 Agent tool 或 `/hub-delegate` 呼叫。

> **Model 欄如實反映 `agents/*.md` 的 frontmatter**：13 個 agent **全部**是 `model: opus`，
> 與 `settings.json` 的 `"model": "opus"` 一致。理由與降級方式見 `rules/performance.md`
> 的「Claude 模型（agent 層）選擇」。改 agent 的 model 時，**必須同步本表與
> `WORKFLOW.md` 的「Agent 使用時機」**，否則兩處會再度漂移。

| Agent | Model | 用途（RoomPilot 情境） |
| :--- | :--- | :--- |
| general-purpose | opus | 通用問題解決、跨檔案搜尋（如「哪裡定義 `style_compat`」） |
| planner | opus | 功能規劃（如新增第七種風格、加房型欄位的落地步驟） |
| architect | opus | 架構設計（檢索管線分層、硬過濾／軟加權界線變更） |
| code-quality-specialist | opus | 程式碼審查（`retriever.py`／`query_parser.py` 品質與可讀性） |
| security-infrastructure-auditor | opus | 安全稽核（`.anthropic_key` 外洩、查詢輸入驗證） |
| test-automation-engineer | opus | 測試自動化（pytest 套件建置——**尚未建置**，由此 agent 起頭） |
| tdd-guide | opus | TDD 引導（先寫 `test_query_parser.py` 再改 schema） |
| e2e-validation-specialist | opus | 端到端驗證（`app.py` 起 UI → 送 8 條代表性查詢 → 檢查卡片） |
| build-error-resolver | opus | 執行錯誤修復（import 失敗、模型載入、Chroma 連線） |
| refactor-cleaner | opus | 死碼清理（v1/v2 遺留分支、已固化的上游來源檔引用） |
| documentation-specialist | opus | 文檔生成（同步 `docs/` 與 `rag_pipeline/README.md` 等 SSOT） |
| deployment-expert | opus | 本機執行運維（啟動 runbook、索引重建流程；**無 CI／無 Docker**） |
| workflow-template-manager | opus | 模板管理（VibeCoding 19 份模板的合規與同步） |

驗證本表未漂移：

```bash
grep -H '^model:' .claude-roompilot/agents/*.md    # 應全為 model: opus
```

### Commands（17 個）

在 Claude Code 中輸入 `/` 即可使用。

| 指令 | 用途（RoomPilot 情境） |
| :--- | :--- |
| /plan | 規劃實作步驟（改權重、改詞表前先出計畫） |
| /tdd | 測試驅動開發（pytest 為預設建議，**尚未建置**） |
| /build-fix | 修復執行錯誤（`.venv-rag` import、HF 模型載入、Chroma） |
| /e2e | 端到端驗證（Gradio UI 實際送查詢） |
| /verify | 全面驗證（語法 + 冒煙檢索 + 索引一致性 + 秘密掃描） |
| /refactor-clean | 死碼清理 |
| /review-code | 程式碼審查 |
| /check-quality | 品質評估 |
| /learn | 擷取模式（把踩過的坑寫回 CLAUDE.md 六個坑） |
| /save-session | 儲存 session |
| /task-init | 專案初始化（建 WBS） |
| /task-next | 下個任務（自動追蹤時間） |
| /task-status | 專案狀態（含時間追蹤） |
| /time-log | 開發時間報表（每日/每任務） |
| /hub-delegate | Agent 委派 |
| /suggest-mode | 建議密度 |
| /template-check | 模板合規 |

### Rules（8 個，自動載入）

放在 `rules/` 下，**每次對話自動注入 context**，無需手動觸發。

| 規則 | 內容 |
| :--- | :--- |
| coding-style | 不可變性、檔案大小、錯誤處理、Python 命名慣例 |
| development-workflow | 研究先行 → Plan → TDD → Review |
| git-workflow | Conventional Commits、PR 流程（**專案尚未 git init**） |
| security | 提交前安全檢查（`.anthropic_key` 絕不外流） |
| testing | 80%+ 覆蓋率、TDD（pytest 尚未建置） |
| performance | 模型選擇、Context 管理、批次成本控管 |
| patterns | 既有實作優先、檢索管線分層、硬過濾/軟加權界線、資料存取封裝、統一回傳格式、只增不覆寫加工、text_hash 增量、受控詞彙 SSOT |
| subagent-context | Subagent 產出寫入 `context/` 對應子目錄 |

### Skills（12 個精選）

放在 `skills/` 下，按需載入；索引見 `skills/INDEX.md`，延伸用法見
`skills/SUPERPOWERS-EXTRAS-USAGE-zh-TW.md`。
**前端框架類 skill（UI 元件庫、前端效能、無障礙稽核等）已捨棄** —— 本專案 UI 由 Gradio 產生，
不手寫前端框架程式碼；UI 相關改動一律走 `rag_pipeline/app.py`。

| Skill | 搭配 |
| :--- | :--- |
| sunnydata-design | 新功能／多步驟實作前，`/plan` |
| sunnydata-testing | `/tdd`（pytest，尚未建置） |
| sunnydata-code-review | `/review-code`、交付前自我審查 |
| sunnydata-debugging | 檢索結果異常、模型載入失敗、命中 0 筆 |
| sunnydata-security | `.anthropic_key` 稽核、查詢輸入驗證 |
| sunnydata-api-design | `query_parser.py` structured outputs schema、`rag_export/` 交付契約 |
| sunnydata-architecture-review | 兩階段檢索管線邊界、模組依賴審查 |
| sunnydata-branch-lifecycle | 分支收尾（**專案尚未 git init**，流程備用） |
| sunnydata-deep-research | 模型／套件選型調查（如是否換 reranker） |
| sunnydata-infrastructure | 本機執行 runbook 與環境重建（**無 CI／無 Docker**） |
| sunnydata-parallel-agents | 2+ 支互不相干的腳本同時處理 |
| sunnydata-skill-authoring | 新增／修改 skill |

### Output Styles（15 個）

使用 `/output-style <name>` 切換，詳見 `output-styles/README.md`。

| 樣式 | 對應產出 |
| :--- | :--- |
| 01-prd-product-spec | 檢索需求 PRD（User Story + 允收標準） |
| 02-bdd-scenario-spec | Gherkin 場景（「輸入日式侘寂客廳沙發，應回 8 張卡片」） |
| 03-architecture-design-doc | C4 + Advanced RAG 管線架構文件 |
| 04-ddd-aggregate-spec | 領域模型（家具物件、風格、檢索群組） |
| 05-api-contract-spec | `parse_query` / `retrieve` 函式契約 |
| 06-tdd-unit-spec | 單元測試規格（pytest，尚未建置） |
| 07-code-review-checklist | 審查清單（含六個坑） |
| 08-security-checklist | 金鑰與輸入驗證清單 |
| 09-database-schema-spec | ChromaDB `furniture_v3` metadata 與 `rag_export/` schema |
| 10-backend-python-impl | Python 3.11 實作輸出格式 |
| 11-frontend-component-bdd | Gradio 卡片／追問按鈕的行為規格 |
| 12-integration-contract-suite | 管線串接契約（parser → retriever → app） |
| 13-data-contract-evolution | `furniture_enriched_v1→v2→v3` 資料契約演進 |
| 14-ci-quality-gates | 本機品質關卡（**本專案無 CI**，以人工 checklist 取代） |
| 15-Vision-output | 專題願景與成果簡報 |

### Hooks（已註冊於 settings.json）

```
hooks/
├── README.md              # Hook 說明文件（非 hook）
├── hook-utils.sh          # 共用工具函數庫（非 hook）
├── session-start.sh       # 會話啟動：偵測模板、提示初始化
├── user-prompt-submit.sh  # 用戶輸入：攔截 /task-* 命令
├── pre-tool-use.sh        # 工具前置：TaskMaster 狀態提示
├── post-write.sh          # 寫入後置：文檔審查通知
├── agent-monitor.sh       # Agent 監控：記錄 subagent 活動
└── watch-agents.sh        # 監控工具：即時追蹤 agent log
```

所有腳本皆為 **bash（macOS）**；本專案 shell 為 zsh，hook 由 Claude Code 以 `bash` 呼叫。

#### Hook 註冊對照表

| 事件 | 腳本 | Matcher | 用途 |
| :--- | :--- | :--- | :--- |
| SessionStart | session-start.sh | 全部 | 偵測 `CLAUDE_TEMPLATE.md`，提示 `/task-init` |
| UserPromptSubmit | user-prompt-submit.sh | 全部 | 攔截 `/task-*` 命令，準備 TaskMaster 環境 |
| PreToolUse | agent-monitor.sh | `Agent` | 記錄 subagent 啟動（類型、prompt、model） |
| PreToolUse | pre-tool-use.sh | `Write\|Edit\|Read` | 提供 TaskMaster 狀態上下文 |
| PostToolUse | agent-monitor.sh | `Agent` | 記錄 subagent 完成結果 |
| PostToolUse | post-write.sh | `Write` | 文檔寫入後觸發駕駛員審查通知 |

#### Agent 活動監控

所有 subagent 的啟動和完成會自動記錄到 `.claude-roompilot/logs/`：

- `agent-activity.log` — 人類可讀格式（prompt、結果、時間戳）
- `agent-activity.jsonl` — 結構化 JSON（適合程式分析）

目前 `logs/` 只有 `.gitignore`，實際 log 於第一次觸發 hook 後產生。

即時監控（開另一個終端機，zsh 亦可直接執行）：

```bash
bash .claude-roompilot/hooks/watch-agents.sh           # 即時追蹤
bash .claude-roompilot/hooks/watch-agents.sh --json    # JSON 格式
bash .claude-roompilot/hooks/watch-agents.sh --last 30 # 最近 30 行
bash .claude-roompilot/hooks/watch-agents.sh --summary # 統計摘要
bash .claude-roompilot/hooks/watch-agents.sh --clear   # 清除 log
```

#### 複製到其他專案

```bash
# 1. 複製 hooks 腳本
mkdir -p .claude-roompilot/hooks .claude-roompilot/logs
cp <模板路徑>/hooks/*.sh .claude-roompilot/hooks/
cp <模板路徑>/logs/.gitignore .claude-roompilot/logs/

# 2. 在目標專案 settings.json 加入 hooks 區段（見本目錄 settings.json）
#    注意：settings.json 內的 hook 路徑必須與實際目錄名一致
#    —— 啟用（改名為 .claude/）後應為 bash .claude/hooks/xxx.sh
```

#### 自訂 Hook

所有 hook 透過 **stdin** 接收 JSON 資料，使用 `jq` 解析：

```bash
#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
# 處理邏輯...
exit 0  # 0=放行, 2=阻擋
```

---

## 自訂指南

### 新增 Agent

在 `agents/` 新增 `.md` 檔案：

```yaml
---
name: my-agent
description: 繁體中文描述
tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob"]
model: opus
---

Agent 的指示內容...
```

新增後必須同步「Agents」表與 `WORKFLOW.md` 的「Agent 使用時機」；
本配置目前 13 個 agent 一律 `model: opus`，若刻意用別的模型請在該 agent 檔內寫明理由。

### 新增 Command

在 `commands/` 新增 `.md` 檔案：

```yaml
---
description: 繁體中文描述
---

# 指令標題

指令的執行邏輯...
```

### 新增 Rule

在 `rules/` 新增 `.md` 檔案（自動載入，無需 frontmatter）。

### 新增語言特定規則

本專案語言唯一：**Python 3.11**（`.venv-rag/`）。要補 Python 專屬規則時：

```bash
cp <模板路徑>/rules/python/*.md .claude-roompilot/rules/
```

規則內的所有指令必須寫成 `.venv-rag/bin/python …`，不得引用其他虛擬環境。

### 新增 Skill

```bash
cp -r <來源路徑>/skill-folder .claude-roompilot/skills/sunnydata-<name>/
```

新增後同步更新 `skills/INDEX.md` 的生命週期表格，否則等同不存在。

### 驗證配置可用

```bash
PY=.venv-rag/bin/python

$PY -c "import json,sys; json.load(open('.claude-roompilot/settings.json')); print('settings.json OK')"
bash -n .claude-roompilot/statusline.sh && echo "statusline.sh OK"
for f in .claude-roompilot/hooks/*.sh; do bash -n "$f" || echo "FAIL $f"; done
```
