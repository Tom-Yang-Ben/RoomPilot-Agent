# Skills 索引（RoomPilot 家具風格檢索系統）

MECE 架構：**實際保留 12 個 skill**，對齊開發生命週期，統一 `sunnydata-` 前綴。
所有前端類 skill（react-*、shadcn、ui-design-system、ux-bencium-*、a11y-audit、
frontend-design、web-guidelines）**已全數捨棄** — 本專案 UI 是 Gradio 6，無前端框架。

## 命名原則

```
sunnydata-{lifecycle-phase}
```

| 前綴 | 意義 |
| :--- | :--- |
| `sunnydata-` | SunnyData 團隊標準 skill |

## 開發生命週期（保留的 12 個）

| 階段 | Skill | 用途 | 何時載入（觸發時機） |
| :--- | :---- | :--- | :------- |
| THINK+PLAN+DO | **sunnydata-design** | 探索意圖 → 撰寫計畫 → 依檢查點執行 | 改檢索邏輯、調排序權重、換模型等多步驟實作前 |
| ARCHITECT | **sunnydata-architecture-review** | 架構級審查：異味 → 原則 → 修法三階段 | 檢視 Advanced RAG 八個模組的邊界、評估重構、稽核模組相依 |
| BUILD (契約) | **sunnydata-api-design** | 介面／資料契約設計最佳實踐 | 改 `query_parser.py` 的 structured outputs schema、`rag_export/` 交付格式、Chroma metadata 欄位 |
| BUILD+TEST | **sunnydata-testing** | TDD 流程 + 單元／整合／端到端測試模式 | 寫功能、修 bug、補測試（本專案 **pytest 尚未建置**，先以 CLI 冒煙為驗證基準） |
| VERIFY (安全) | **sunnydata-security** | OWASP 分類 + 實作 checklist + 語言特定實踐 | 金鑰處理（`.anthropic_key`）、使用者查詢輸入驗證、批次腳本外部資料信任邊界 |
| VERIFY (審查) | **sunnydata-code-review** | 驗證 → 發起 review → 消化回饋 | 完成任務、交付前自我審查 |
| SHIP (執行環境) | **sunnydata-infrastructure** | 本機執行環境、runbook、資料交付與回復流程 | 建索引／批次跑批前後（**本專案無 CI、無 Docker**，一律本機 macOS 執行） |
| SHIP (分支) | **sunnydata-branch-lifecycle** | 建立 worktree → 收尾分支（merge/PR/cleanup） | 功能隔離、分支收尾（**專案尚未 git init**，流程照走但指令暫不可執行） |
| DEBUG | **sunnydata-debugging** | 四階段結構化除錯 | 檢索結果不對、rerank 分數異常、模型載入失敗、Gradio 卡片沒圖 |
| RESEARCH | **sunnydata-deep-research** | 多來源深度研究（firecrawl/exa MCP） | 評估替代 reranker、風格詞表擴充依據、Chroma／Gradio 版本行為調查 |
| ORCHESTRATE | **sunnydata-parallel-agents** | 獨立任務平行派發 | 2+ 條互不相干的線同時處理（批次標註／索引重建／文件同步） |
| META | **sunnydata-skill-authoring** | 撰寫／驗證 SKILL.md | 新增或修改本目錄下的 skill |

## 已捨棄（不再列於本索引）

| 捨棄的 skill | 原因 |
| :--- | :--- |
| `community-react-*`（composition/native/performance） | 本專案無 React／無 Node 生態 |
| `sunnydata-shadcn-ui`、`community-ui-design-system` | UI 為 Gradio 6 卡片，無元件庫 |
| `community-ux-bencium-*`、`community-frontend-design` | 無前端設計工作 |
| `community-a11y-audit`、`community-web-guidelines` | 無網頁前端可稽核（Gradio 由框架產生 DOM） |

## 永遠生效的規則（非 skill）

以下在 `.claude-roompilot/rules/` 目錄，每次對話自動載入：

| 檔案 | 涵蓋 |
| :--- | :--- |
| `coding-style.md` | 不可變性、檔案組織、Python 命名慣例、品質清單 |
| `security.md` | 交付前安全檢查、`.anthropic_key` 秘密管理 |
| `testing.md` | 測試策略與覆蓋率目標（pytest 尚未建置，先以冒煙為準） |
| `git-workflow.md` | Conventional Commits、PR 流程（專案尚未 git init） |
| `patterns.md` | 既有實作優先、檢索管線分層、硬過濾/軟加權界線、資料存取封裝（Chroma／JSON 集中在一致介面後）、統一回傳格式（扁平回傳 vs `rag_export/` 完整信封）、只增不覆寫加工、text_hash 增量、受控詞彙 SSOT |
| `development-workflow.md` | 研究 → 規劃 → TDD → 審查 → 交付 |
| `performance.md` | 模型選擇、Context Window 管理、批次成本控制 |
| `subagent-context.md` | Subagent 產出寫入 `.claude-roompilot/context/` 的規則 |

## 擴充方式

```bash
cp -r /path/to/skill-folder .claude-roompilot/skills/sunnydata-<name>/
```

| 情境 | 建議來源 |
| :--- | :------- |
| 深度安全審計 | `trailofbits/skills` 依 plugin 挑選 |
| 更多 Superpowers | [obra/superpowers](https://github.com/obra/superpowers) |
| 檢索／向量庫專題 | ChromaDB 與 BAAI/bge 官方文件，整理成本地 reference skill |

> 新增 skill 前先載入 **sunnydata-skill-authoring**：本專案要求「先有失敗測試，才有 skill」。
