# Superpowers 系列繁體中文說明（RoomPilot 保留版）

原始來源：[obra/superpowers](https://github.com/obra/superpowers)。經 MECE 重構後，`sp-*` 系列已合併至 `sunnydata-` 前綴 skill；
本專案（RoomPilot 家具風格檢索系統）在此基礎上再篩選，**最終保留 12 個 skill**，完整清單見 [INDEX.md](INDEX.md)。

## 合併對照表

| 原 `sp-*` Skill | 合併至 | 對應章節 |
| :-------------- | :----- | :------- |
| `sp-brainstorming` | **sunnydata-design** | Phase 1: Brainstorm |
| `sp-writing-plans` | **sunnydata-design** | Phase 2: Write Plan |
| `sp-executing-plans` | **sunnydata-design** | Phase 3: Execute Plan |
| `sp-verification-before-completion` | **sunnydata-code-review** | Phase 1: Verify Before Completion |
| `sp-requesting-code-review` | **sunnydata-code-review** | Phase 2: Request Review |
| `sp-receiving-code-review` | **sunnydata-code-review** | Phase 3: Receive & Respond |
| `sp-using-git-worktrees` | **sunnydata-branch-lifecycle** | Phase 1: Create Worktree（專案尚未 git init） |
| `sp-finishing-a-development-branch` | **sunnydata-branch-lifecycle** | Phase 2: Finish Branch（專案尚未 git init） |
| `sp-using-superpowers` | **`.claude-roompilot/CLAUDE.md`** | Skill 使用規則（3 行） |

## 維持獨立（已改名）

| 原名 | 新名 | 用途 |
| :--- | :--- | :--- |
| `sp-systematic-debugging` | **sunnydata-debugging** | 四階段結構化除錯 |
| `sp-dispatching-parallel-agents` | **sunnydata-parallel-agents** | 平行子代理派發（批次／索引／文件三條線） |
| `sp-writing-skills` | **sunnydata-skill-authoring** | 撰寫/驗證 SKILL.md |

## 未導入

| Skill | 原因 |
| :---- | :--- |
| `sp-test-driven-development` | 與 **sunnydata-testing** 的 TDD 流程重疊 |

## 本專案額外捨棄（前端類，使用說明一併移除）

RoomPilot 的 UI 是 `rag_pipeline/app.py` 的 **Gradio 6.20.0** 卡片介面，
沒有前端框架、沒有元件庫、沒有自建 DOM，因此下列 skill 全數移除，不再提供使用說明：

| 捨棄的 Skill | 原因 |
| :---- | :--- |
| `community-react-composition` / `community-react-native` / `community-react-performance` | 本專案無 React、無 Node 生態 |
| `sunnydata-shadcn-ui` | 無元件註冊表；卡片樣式由 Gradio 主題與內嵌 HTML 決定 |
| `community-ui-design-system` | 無設計系統與多前端技術棧需求 |
| `community-ux-bencium-controlled` / `community-ux-bencium-innovative` | 無自訂前端介面設計工作 |
| `community-frontend-design` | 同上 |
| `community-a11y-audit` / `community-web-guidelines` | 無可稽核的自寫前端；Gradio DOM 由框架產生 |

## 保留的 12 個 skill 快速用法

| Skill | 一句話用法 |
| :---- | :--- |
| **sunnydata-design** | 動 `retriever.py` 排序權重或換模型前，先跑探索 → 計畫 → 檢查點 |
| **sunnydata-architecture-review** | 檢視 Query Understanding → … → Result Presenter 八個模組的邊界與相依 |
| **sunnydata-api-design** | 改 `query_parser.py` structured outputs schema 或 `rag_export/` 交付格式時 |
| **sunnydata-testing** | 補 pytest（尚未建置）；在那之前以 CLI 冒煙查詢當允收條件 |
| **sunnydata-security** | 檢查 `.anthropic_key`、使用者查詢輸入驗證、批次腳本的外部資料信任邊界 |
| **sunnydata-code-review** | 交付前自我審查（無 CI，人工把關就是最後一道） |
| **sunnydata-infrastructure** | 本機 runbook：建索引、跑批次、回復索引（無 CI／無 Docker） |
| **sunnydata-branch-lifecycle** | 分支開立與收尾（專案尚未 git init，先照流程規劃） |
| **sunnydata-debugging** | 檢索結果不對、rerank 分數異常、模型載入卡住時的四階段除錯 |
| **sunnydata-deep-research** | 評估替代 reranker、風格詞表擴充依據等需引用來源的調查 |
| **sunnydata-parallel-agents** | 批次標註／索引重建／文件同步三條線同時開工 |
| **sunnydata-skill-authoring** | 新增或修改本目錄下的 skill（先有失敗測試才有 skill） |
