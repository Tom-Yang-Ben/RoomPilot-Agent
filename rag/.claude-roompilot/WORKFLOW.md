# 開發工作流指南 — RoomPilot 家具風格檢索系統

> 專案事實見 `PROJECT_BRIEF.md`，入口見 `CLAUDE.md`。
> **所有 Python 指令一律 `.venv-rag/bin/python`**；本專案無 CI、無 Docker、尚未 git init。

```bash
PY=.venv-rag/bin/python    # 本檔所有指令的前提
```

## 完整開發流程

```
專案初始化 → 任務管理循環 → 結束保存
```

### Phase 0: 專案初始化

```bash
/task-init          # 建立 WBS、分析複雜度、配置 Hub 策略
```

產出：WBS 任務清單、專案配置、里程碑規劃

### Phase 1: 任務循環（每個任務重複）

```
/task-next          # 從 WBS 取下一個任務（自動開始時間追蹤）
    |
/plan               # 規劃該任務的實作步驟（等待確認）
    |
/tdd                # 測試驅動開發（Red → Green → Refactor；pytest 尚未建置）
    |
/build-fix          # 修復執行錯誤（import、模型載入、Chroma 連線）
    |
/review-code        # 程式碼審查（對照 CLAUDE.md 六個坑）
    |
/e2e                # 端到端驗證（起 Gradio UI，送代表性查詢看卡片）
    |
/verify full        # 全面驗證（語法 + 冒煙檢索 + 索引一致性 + 秘密掃描）
    |
/task-status        # 確認進度（含預估 vs 實際時間），回到 /task-next
```

### Phase 2: 收尾

```bash
/time-log             # 查看今日/累計開發時間
/verify pre-delivery  # 交付前完整檢查（含 .anthropic_key 秘密掃描、索引覆蓋率、rag_export/ 完整性）
/save-session         # 儲存 session 狀態供下次恢復
```

> **參數口徑**：`/verify` 只認 `quick` / `full` / `pre-commit` / `pre-delivery` 四個參數
> （定義在 `commands/verify.md` 的「參數」節）。**本專案沒有 `pre-pr`** —— 尚未 git init、無 PR 流程，
> 交付前一律用 `pre-delivery`。
>
> **git 說明**：commit／PR 步驟目前無法執行——**專案尚未 git init**。
> 流程照走（自我 review 變更、檢查殘留 debug code），但以人工檢查取代 `git diff`。

---

## 快速模式（小功能/Bug 修復）

```
/plan [描述]  →  /tdd  →  /verify quick
```

最小驗證（不重建索引、不起 UI）：

```bash
$PY rag_pipeline/query_parser.py "北歐風的小坪數客廳沙發，預算兩萬"
$PY rag_pipeline/retriever.py   "北歐風的小坪數客廳沙發，預算兩萬"
```

---

## 四條開發主線

RoomPilot 的改動幾乎都落在這四條主線上。**先辨識自己在哪條線，再進 Phase 1 循環。**

| 主線 | 主要檔案 | 是否需重建索引 | 是否需重啟 UI |
| :--- | :--- | :--- | :--- |
| A. 改檢索邏輯 | `rag_pipeline/retriever.py` | 否 | 是（模型常駐） |
| B. 改詞表／受控詞彙 | `vlm_annotation/taxonomy_v2.json`、`rag_pipeline/category_groups.json`、`query_parser.py` | 視情況 | 是 |
| C. 重建索引 | `rag_pipeline/embed_v3.py`、`rag_dataset/furniture_enriched_v3.json` | 是 | 是 |
| D. 改 UI | `rag_pipeline/app.py` | 否 | 是 |

### 主線 A：改檢索邏輯（`retriever.py`）

**典型任務**：調整排序權重、改 `VEC_TOP_K` / `RERANK_TOP_K`、改預算分配、改去重收斂策略。

```bash
# 1. 改前先看基準（同一組查詢跑三次，記下 top-8 的 id 與分數）
$PY rag_pipeline/retriever.py "工業風的餐廳吊燈，預算五千內"
$PY rag_pipeline/retriever.py "奶油風臥室，想要溫暖柔和的氛圍"
$PY rag_pipeline/retriever.py "日式侘寂感、預算兩萬內的客廳沙發"

# 2. 改權重（W_RERANK / W_STYLE / W_MOOD / W_CONF 在 retriever.py:47）
# 3. 用同一組查詢重跑，逐條比對排序變化
```

| 檢查點 | 內容 |
| :--- | :--- |
| 權重總和 | `W_RERANK + W_STYLE + W_MOOD + W_CONF` 必須 = 1.0 |
| 六個坑 #1 | 新增 `where` 條件時，欄位必須存在於 `chroma_metadata`（`rag_indexable` 不行） |
| 六個坑 #2 | 不要對 rerank 分數再套 sigmoid |
| 六個坑 #6 | 不要把 reranker 換成英文 ms-marco MiniLM |
| 硬／軟界線 | 房型／類別／價格／尺寸 = 硬過濾；風格／氛圍 = 軟加權；顏色／材質只進 `semantic_query` |
| SSOT 同步 | `docs/RAG檢索系統說明.md`、`rag_pipeline/README.md` |

### 主線 B：改詞表／受控詞彙

**典型任務**：新增／調整六風格、改 `style_compat` 相容矩陣、改 19 檢索群組、改氛圍詞或色卡。

```bash
# 1. 先確認詞表改動範圍
$PY -c "import json; t=json.load(open('vlm_annotation/taxonomy_v2.json')); print(list(t['styles']), len(t['style_compat']))"

# 2. 需求解析端單測（受控詞彙來自 taxonomy_v2 + category_groups）
$PY rag_pipeline/query_parser.py "美式鄉村風的餐桌"

# 3. 若改動影響批次風格判定，先比一致率再全量
$PY json_adjustment/reclassify_styles.py --compare 30
```

| 檢查點 | 內容 |
| :--- | :--- |
| 相容矩陣 | 6×6 必須對稱且完整；新增風格 = 矩陣擴為 7×7，**全部格子都要填** |
| 六個坑 #3 | structured outputs 可為 null 的 enum 要用 `anyOf`，直接寫 type 陣列會 400 |
| 六個坑 #5 | 尺寸是硬過濾，不可讓 LLM 用常識推測 |
| 影響索引 | 若詞表改動改變了 `text_hash` 的輸入，需走主線 C 的 `--only-changed` |
| 成本 | 全量六風格判定約 US$7；**先 `--compare 30` 再決定是否全量** |
| SSOT 同步 | `docs/query_parser_spec.md`、`taxonomy_v2.json`、`category_groups.json` |

### 主線 C：重建索引（`embed_v3.py`）

**典型任務**：資料集更新（v2→v3 加工）、embedding 文本組法變更、`rag_export/` 交付檔重出。

```bash
# 1. 資料加工先 dry-run 看統計
python3 json_adjustment/build_rag_v3.py --dry-run

# 2. 先冒煙，確認流程與欄位無誤
$PY rag_pipeline/embed_v3.py --limit 50

# 3. 增量（text_hash 比對；646 筆約 1.5 分鐘）
$PY rag_pipeline/embed_v3.py --only-changed

# 4. 只有在文本組法整體變更時才全量（約 27 分鐘）
$PY rag_pipeline/embed_v3.py
```

| 檢查點 | 內容 |
| :--- | :--- |
| 筆數 | 完成後 `furniture_v3` 應為 9,349 筆（有增刪則以資料集為準） |
| 交付檔 | `rag_export/` 四個檔案：向量 jsonl、metadata、失敗清單、驗證報告 |
| 失敗清單 | `embedding_failures.jsonl` 必須為空或逐筆有解釋 |
| 六個坑 #4 | `HF_HUB_OFFLINE=1` 的 `setdefault` 勿移除；新機器首次下載才設 0 |
| 資源 | bge-m3 常駐約 4.6 GB —— **建索引期間不要同時開 UI** |
| SSOT 同步 | `json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md` |

### 主線 D：改 UI（`app.py`）

**典型任務**：卡片版型、條件摘要區塊、追問（clarify）按鈕、範例查詢、縮圖處理。

```bash
$PY rag_pipeline/app.py        # → http://127.0.0.1:7860
```

| 檢查點 | 內容 |
| :--- | :--- |
| Gradio 6 | `theme` 必須在 `launch()` 傳，**不能**傳進 `gr.Blocks()` |
| 圖片 | PIL 縮圖 + base64 內嵌；來源在 `rendering/output/…/正面(abo\|ikea)/` |
| 純檢索 | 本系統無 LLM 生成端，UI **不得**加入「生成文案」類功能 |
| 預熱 | 首次查詢會載入 bge-m3 + reranker，屬預期延遲，勿誤判為當機 |
| 追問按鈕 | 上限由 `MAX_CLARIFY` 控制，超出要收斂而非展開 |
| SSOT 同步 | `rag_pipeline/README.md`、專案根 `README.md` |

### 跨主線收尾（四條都適用）

```bash
/review-code rag_pipeline/       # 對照六個坑
/verify full                     # 語法 + 冒煙檢索 + 索引一致性 + 秘密掃描
```

- 確認 `.anthropic_key` **未被讀出、未被寫進任何檔案**
- 確認 SSOT 文件已同步（規格衝突時以文件為準）
- Subagent 產出摘要寫入 `.claude-roompilot/context/` 對應子目錄

---

## 指令速查

### 核心工作流（按使用順序）

| 指令 | 用途 | 常用參數 |
| :--- | :--- | :--- |
| `/task-init` | 專案初始化 | |
| `/task-next` | 取下一個任務（自動追蹤時間） | |
| `/task-status` | 查看專案進度（含時間追蹤） | `--detailed`, `--metrics` |
| `/time-log` | 開發時間報表 | `--today`, `--by-task`, `--week`, `--month` |
| `/plan` | 規劃實作步驟 | [功能描述]，如「新增第七種風格」 |
| `/tdd` | 測試驅動開發（pytest 尚未建置） | [功能描述] |
| `/build-fix` | 修復執行錯誤（import／模型載入／Chroma） | |
| `/review-code` | 程式碼審查 | [路徑]，如 `rag_pipeline/retriever.py` |
| `/e2e` | 端到端驗證（Gradio UI 送查詢） | [流程描述] |
| `/verify` | 全面驗證 | `quick`, `full`, `pre-commit`, `pre-delivery` |

### 輔助指令

| 指令 | 用途 |
| :--- | :--- |
| `/hub-delegate` | 委派 agent 執行任務 |
| `/check-quality` | 品質評估 |
| `/refactor-clean` | 死碼清理 |
| `/template-check` | 模板合規檢查 |
| `/time-log` | 開發時間報表（每日/每任務） |
| `/suggest-mode` | 調整建議密度 |
| `/learn` | 擷取可重用模式 |
| `/save-session` | 儲存 session |

---

## Agent 使用時機

> **13 個 agent 一律 `model: opus`**（`agents/*.md` frontmatter 與 `settings.json` 皆為 opus）。
> 本表不再逐列標模型，以免與檔案漂移；完整對照見 `README.md` 的「Agents」表，
> 成本考量與降級方式見 `rules/performance.md` 的「Claude 模型（agent 層）選擇」。

| 場景 | 自動使用的 Agent | 對應主線 |
| :--- | :--- | :--- |
| 複雜功能需求（新增第七種風格） | planner | B |
| 架構決策（硬過濾／軟加權界線變更） | architect | A / B |
| 寫完程式碼後 | code-quality-specialist | 全部 |
| Bug 修復/新功能 | tdd-guide | 全部 |
| 執行失敗（import、模型載入、Chroma） | build-error-resolver | 全部 |
| 安全敏感程式碼（`.anthropic_key`、查詢輸入） | security-infrastructure-auditor | B / D |
| 端到端驗證（CLI 端到端檢索 + Gradio 冒煙） | e2e-validation-specialist | D |
| 死碼清理（v1/v2 遺留分支） | refactor-cleaner | 全部 |
| 更新文檔（同步 SSOT） | documentation-specialist | 全部 |
| 本機執行運維（啟動 runbook、索引重建） | deployment-expert | C |
| 模板整合（VibeCoding 19 份模板） | workflow-template-manager | — |

---

## Rules 自動載入

`.claude-roompilot/rules/` 下的規則在每次對話中自動生效（啟用改名後為 `.claude/rules/`）：

| 規則 | 強制內容 |
| :--- | :--- |
| coding-style | 不可變性、檔案大小限制、錯誤處理、Python 命名慣例 |
| development-workflow | 研究先行、Plan-TDD-Review 流程 |
| git-workflow | Conventional Commits、PR 流程（**專案尚未 git init**） |
| security | 提交前安全檢查清單（`.anthropic_key` 絕不外流） |
| testing | 80%+ 覆蓋率、TDD 強制（pytest **尚未建置**） |
| performance | 模型選擇、context 管理、批次成本控管 |
| patterns | 既有實作優先、檢索管線分層、硬過濾/軟加權界線、資料存取封裝、統一回傳格式、只增不覆寫加工、text_hash 增量、受控詞彙 SSOT |
| subagent-context | Subagent 產出寫入 `context/` 對應子目錄 |

---

## Skills 參考

`.claude-roompilot/skills/` 下的 12 個 skill 提供特定領域的深度知識
（**前端類 skill 已捨棄**；索引見 `skills/INDEX.md`）：

| Skill | 搭配指令／時機 |
| :--- | :--- |
| sunnydata-design | `/plan`、任一主線開工前 |
| sunnydata-testing | `/tdd`（pytest 尚未建置） |
| sunnydata-code-review | `/review-code` |
| sunnydata-debugging | 檢索命中 0 筆、排序異常、模型載入失敗 |
| sunnydata-security | `/verify pre-delivery` 的秘密掃描 |
| sunnydata-api-design | 主線 B：`query_parser.py` structured outputs schema |
| sunnydata-architecture-review | 主線 A：檢索管線邊界與依賴 |
| sunnydata-branch-lifecycle | 分支收尾（專案尚未 git init，流程備用） |
| sunnydata-deep-research | 模型／套件選型調查（是否換 reranker） |
| sunnydata-infrastructure | 主線 C：本機執行 runbook（**無 CI／無 Docker**） |
| sunnydata-parallel-agents | 兩條互不相干的主線同時推進 |
| sunnydata-skill-authoring | 新增／修改 skill |

---

## MCP Server

> **本專案目前沒有任何專案層級 MCP server**（專案根無 `.mcp.json`、`settings.json` 無
> `enabledMcpjsonServers`）。下表是「**若要加裝**，什麼對本專案有用」的評估，
> **不代表已安裝**；口徑以 `.claude-roompilot/mcp-configs/README.md` 為準。
> 所有工作目前一律以內建工具（Read / Edit / Write / Grep / Glob / Bash）與 `.venv-rag/bin/python` 完成。

| Server | 用途（RoomPilot 情境） |
| :--- | :--- |
| brave-search | 網路搜尋（風格關鍵字、家具詞彙調查）（**未安裝**） |
| context7 | 即時文檔查詢（Gradio 6、ChromaDB、sentence-transformers API）（**未安裝**） |
| github | 上游模型／套件 repo 的 issue 查證（**未安裝**；**本專案尚未 git init**，建 repo 後才有意義） |
| sequential-thinking | 鏈式推理（排序公式調權的因果推導）（**未安裝**） |
| memory | 跨 session 記憶（六個坑、已試過的權重組合）（**未安裝**） |

**瀏覽器自動化（playwright 等）不在本專案採用範圍**：本專案**無 Playwright、無瀏覽器自動化、無 CI**，
E2E 一律走 **CLI 端到端檢索 + Gradio 冒煙**——見 `commands/e2e.md`、`agents/e2e-validation-specialist.md`。
`127.0.0.1:7860` 的卡片呈現以**人工開瀏覽器目視**確認，不透過 MCP 工具驅動。

更多可用 server 見 `.claude-roompilot/mcp-configs/README.md`。

---

## 配置啟用指南

1. 確認事實來源：先讀 `PROJECT_BRIEF.md`，再讀 `CLAUDE.md`
2. 啟用配置（Claude Code 只讀 `.claude/`）：

   ```bash
   mv .claude .claude-template-backup
   mv .claude-roompilot .claude
   ```

3. **改 `settings.json` 的 7 條路徑**（`statusLine` 1 + hook 6）—— 這是**唯一**需要手動改的檔案：

   ```bash
   sed -i '' 's|\.claude-roompilot/|.claude/|g' .claude/settings.json
   python3 -m json.tool .claude/settings.json > /dev/null && echo "settings.json OK"
   ```

   > `hooks/*.sh` 與 `statusline.sh` **不需要改** —— 已改為由腳本自身位置推導配置目錄
   > （`CLAUDE_CONFIG_DIR` / `CLAUDE_DIR_NAME`），改名後自動跟著走。詳見 `README.md` 的「如何啟用」。

4. 確認 Python 環境可用：`.venv-rag/bin/python -c "import chromadb, gradio; print('ok')"`
5. 確認金鑰就位：`.anthropic_key` 存在或已設 `ANTHROPIC_API_KEY`（**不可回顯內容**）
6. 啟動 Claude Code，執行 `/task-init`，並辨識自己在哪條主線
