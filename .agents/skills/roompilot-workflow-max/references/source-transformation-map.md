# 來源轉換地圖

本 skill 以安全重寫方式吸收 `.claude/` 與 `VibeCoding_Workflow_Templates/`，
不原封複製 Claude runtime、第三方 prompt、權限、hooks、秘密處理、二進位或破壞性
recipes。逐檔 path、size、SHA-256、類型與 disposition 位於
`source-inventory.json`；本檔說明每組來源轉到何處與原因。

## 轉換優先序

```text
使用者明確範圍
→ 最近的 AGENTS.md
→ docs/contracts/ 與 owner profiles
→ 現行程式、測試與可執行命令
→ 本 skill 的重寫流程與模板
```

處置詞：

- **重寫納入**：保留方法，改成 Codex 工具、RoomPilot owner/contract 與安全模型。
- **僅參考**：只吸收經驗法則，不把原文件或執行碼放入 runtime。
- **排除**：不複製、不執行，只在稽核證據說明理由。
- **runtime 排除**：session、log、prompt/response、token、cache、binary 不進 skill。

## VibeCoding 01–17

| 來源 | 轉換位置 | RoomPilot 化重點 |
|---|---|---|
| `INDEX.md` | `SKILL.md`、`workflow-routing.md`、本檔 | 以 preflight/owner/contract Gate 重排階段 |
| `output_style.md` | `output-recipes.md` 與下列模板 | 移除 Claude `/output-style`、hooks 與泛用技術假設 |
| `01_workflow_manual.md` | `SKILL.md`、`workflow-routing.md` | Focused/Full/Maximum parallel，加入 stop conditions |
| `02_project_brief_and_prd.md` | `assets/templates/02-task-brief-prd.md` | 對齊八步、owner、scope/non-goals、可驗收結果 |
| `03_behavior_driven_development_guide.md` | `assets/templates/03-bdd-acceptance.md` | 業務可觀測結果、保存/reload/失敗路徑 |
| `04_architecture_decision_record_template.md` | `assets/templates/04-adr.md` | Producer/consumer 共決、狀態與 supersede |
| `05_architecture_and_design_document.md` | `assets/templates/05-architecture-change.md` | FastAPI 模組化單體、真實 component/sequence/deployment |
| `06_api_design_specification.md` | `assets/templates/06-api-data-contract.md` | 現行 FastAPI/Pydantic、cm/schema/409/503/soft delete |
| `07_module_specification_and_tests.md` | `assets/templates/07-module-spec-tests.md` | Owner invariant、pre/post、targeted tests |
| `08_project_structure_guide.md` | `assets/templates/08-project-structure.md` | 保留現有 owner paths，不建立泛用 `src/` 樹 |
| `09_file_dependencies_template.md` | `assets/templates/09-dependency-map.md` | Producer/consumer DAG、fallback 與 persistence |
| `10_class_relationships_template.md` | `assets/templates/10-component-relationships.md` | Component/function 優先，不強迫 class 化 |
| `11_code_review_and_refactoring_guide.md` | `assets/templates/11-code-review-refactor.md` | Evidence/severity/minimal fix，保留 dirty worktree |
| `12_frontend_architecture_specification.md` | `assets/templates/12-frontend-technical.md` | 正式原生 JS/Three.js；React 僅限 `frontend3d/` |
| `13_security_and_readiness_checklists.md` | `assets/templates/13-security-readiness.md` | Secret/auth/input/raw_data/quarantine/approval |
| `14_deployment_and_operations_guide.md` | `assets/templates/14-deployment-runbook.md` | 只寫真實 runtime/health/rollback，不虛構 K8s/HA |
| `15_documentation_and_maintenance_guide.md` | `assets/templates/15-documentation-maintenance.md` | 連結、命令、contract、現行 scripts baseline |
| `16_wbs_development_plan_template.md` | `assets/templates/16-wbs-work-packets.md`、`parallel-execution.md` | Owner/file-bound packets，設計穩定後才平行寫入 |
| `17_frontend_information_architecture_template.md` | `assets/templates/17-frontend-ia.md` | 八步 journey、正式 routes/state、與技術架構 MECE |

## `.claude` 核心 87 檔

詳細風險與檔案證據見 `claude-core-conversion.md`。

| 來源群組 | 處置 | 轉換位置／理由 |
|---|---|---|
| `CLAUDE.md`、`README.md`、`WORKFLOW.md` | 重寫納入 | `SKILL.md`、workflow/parallel references；repository 規範優先 |
| `agents/` 13 角色 | 重寫納入 | 合併為分析、架構、測試、review、安全、文件、部署 packets；移除 model/tools frontmatter |
| `commands/` 17 recipes | 重寫納入 | 轉為工作流 Gate，不保留 slash command 或 TaskMaster 依賴 |
| `rules/` | 重寫納入 | 只保留與 root `AGENTS.md` 相容的安全、測試、diff、context 原則 |
| `output-styles/` 15 份 | 重寫納入 | `output-recipes.md` 與 templates；移除範例架構假設 |
| `coordination/`、空 `context/` | 重寫納入 | `parallel-execution.md` 與 work-packet 模板；不靜默寫 repository |
| `mcp-configs/` | 排除 | 不複製 API key 位置、未 pin `npx` 或 Claude MCP 設定 |
| `settings.json` | 排除 | 過度寬鬆的 rm/sudo/write/network 權限不適用 Codex sandbox/approval |
| `hooks/` | 排除 | Claude hook JSON、jq/Node、prompt/response logging 與缺失 TaskMaster 依賴 |
| `statusline*`、`STATUSLINE_GUIDE.md` | 排除 | 讀取 OAuth/credentials、呼叫外部 usage endpoint、未驗證 EXE |
| `taskmaster-data/`、`logs/` | runtime 排除 | session、time log、prompt/response 與可變狀態不進版本化 skill |

## `.claude/skills` 22 組／258 檔

詳細逐項理由、授權與安全證據見 `claude-skills-conversion.md`。

| Skill | 處置 | 吸收或排除 |
|---|---|---|
| `community-a11y-audit` | 重寫納入 | 正式 UI 的 a11y/browser/DOM 稽核；移除 Claude/MCP 假設 |
| `community-frontend-design` | 重寫納入 | 條件式視覺品質；服從八步流程與 a11y |
| `community-react-composition` | 僅參考 | 只限明確 `frontend3d/` React 18 工作 |
| `community-react-native` | 排除 | 專案沒有 React Native/Expo app |
| `community-react-performance` | 僅參考 | Next/React 19 大多不適用；只限原型且需核對版本 |
| `community-ui-design-system` | 僅參考 | 不搬 CSV/寫檔工具；含 embedded prompts、來源/路徑安全問題 |
| `community-ux-bencium-controlled` | 僅參考 | 僅保留通用 UX/a11y/motion 概念 |
| `community-ux-bencium-innovative` | 排除 | 與 controlled 衝突且技術假設不符 |
| `community-web-guidelines` | 排除 | 會抓取並服從未固定 GitHub main prompt |
| `sunnydata-api-design` | 重寫納入 | Contract-first，但不強加 `/v1`、envelope 或欄位改名 |
| `sunnydata-architecture-review` | 重寫納入 | 依賴/模組/效能/債務檢查，不強制製造 findings |
| `sunnydata-branch-lifecycle` | 排除 | 自動 pull/push/merge/delete/worktree cleanup 超出授權 |
| `sunnydata-code-review` | 重寫納入 | Evidence-before-claims、severity、驗證；移除自動 GitHub 操作 |
| `sunnydata-debugging` | 重寫納入 | 重現→根因→單一假設→最小修復；排除壓力 prompt/腳本 |
| `sunnydata-deep-research` | 重寫納入 | 僅在需最新/外部證據時用現有 web 與一手來源 |
| `sunnydata-design` | 重寫納入 | Frame→contract→plan→implement，不自動 branch/commit |
| `sunnydata-infrastructure` | 僅參考 | 不搬 destructive Docker 或泛用部署命令 |
| `sunnydata-parallel-agents` | 重寫納入 | `parallel-execution.md` 的 owner/file isolation waves |
| `sunnydata-security` | 重寫納入 | FastAPI/vanilla JS 安全，React 僅限原型 |
| `sunnydata-shadcn-ui` | 排除 | 正式前端不是 shadcn；含 remote latest/force overwrite |
| `sunnydata-skill-authoring` | 僅參考 | 由 Codex `skill-creator` 取代，不納入 runtime |
| `sunnydata-testing` | 重寫納入 | 以 repository pytest/AGENTS matrix 取代通用 Jest/80% 規則 |

## 完整性與更新流程

1. 執行 `python .agents/skills/roompilot-workflow-max/scripts/audit_sources.py check`
   檢查新增、移除與 stable hash drift。
2. 先完整閱讀所有 drift，判斷安全、授權、RoomPilot 適用性與新 disposition。
3. 更新本檔、兩份 Claude conversion 文件、workflow/templates（若行為改變）。
4. 只在審查完成後執行
   `python .agents/skills/roompilot-workflow-max/scripts/audit_sources.py write` 更新 inventory。
5. 執行 `validate_workflow.py` 與 Codex `quick_validate.py`。

Inventory 涵蓋來源內的每一個檔案，包括被排除的 binary、data、runtime 與 logs；
「涵蓋」不代表執行、載入或複製其內容。
