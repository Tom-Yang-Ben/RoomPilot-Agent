---
description: 驗證 RoomPilot 專案是否符合指定的 VibeCoding 工作流模板規範。
---

# 模板合規檢查

## 選擇模板: $ARGUMENTS

## 模板來源

模板位於**專案根**的 `VibeCoding_Workflow_Templates/`，共 **19 份 .md**：
17 份編號模板 + `INDEX.md`（索引，先讀它確認模板清單）+ `output_style.md`（輸出風格）。

## 可用模板

### 階段 0: 流程
1. **workflow-manual** → `01_workflow_manual.md`
   （選完整流程或 MVP；RoomPilot 為單人專題 → 預設 MVP 快速迭代）

### 階段 1: 規劃 (02-03)
2. **project-brief** → `02_project_brief_and_prd.md`
   （對照 `.claude-roompilot/PROJECT_BRIEF.md` 與專案根 `README.md`）
3. **bdd** → `03_behavior_driven_development_guide.md`
   （檢索行為的 Given/When/Then：給定「北歐風小坪數客廳」→ 回 8 張卡片）

### 階段 2: 架構設計 (04-06)
4. **adr** → `04_architecture_decision_record_template.md`
   （如：為何選 bge-m3 而非其他 embedding、為何 rerank 不再套 sigmoid）
5. **architecture** → `05_architecture_and_design_document.md`
   （Advanced RAG 八段管線、C4 邊界；`rag_pipeline` 是唯一應用程式 Container）
6. **api** → `06_api_design_specification.md`
   （本專案無對外 HTTP API；檢核對象為 `query_parser.py` 的 structured outputs schema
   與 `json_adjustment/RAGSQL.md` 的 SQL 端交付契約）

### 階段 3: 詳細設計 (07-10)
7. **tests** → `07_module_specification_and_tests.md`
   （四類測試：正常／邊界／無效輸入／業務規則；**pytest 尚未建置**）
8. **structure** → `08_project_structure_guide.md`
   （`rag_pipeline/`、`rag_dataset/`、`rag_export/`、`json_adjustment/`、`vlm_annotation/`）
9. **dependencies** → `09_file_dependencies_template.md`
   （`app.py` → `retriever.py` → `query_parser.py` + Chroma，需為 DAG、無循環）
10. **classes** → `10_class_relationships_template.md`
    （檢索器／解析器／索引建置的類別與資料結構關係）

### 階段 4: 開發品質 (11-12, 17)
11. **code-review** → `11_code_review_and_refactoring_guide.md`
12. **frontend-arch** → `12_frontend_architecture_specification.md`
    （呈現層＝Gradio 6.20.0 卡片；theme 在 `launch()` 傳）
13. **frontend-ia** → `17_frontend_information_architecture_template.md`
    （單頁 UI：查詢輸入 → 8 張結果卡片 → 追問按鈕的資訊架構）

### 階段 5: 安全部署 (13-14)
14. **security** → `13_security_and_readiness_checklists.md`
    （`.anthropic_key` 不得提交或回顯、使用者查詢輸入驗證）
15. **deployment** → `14_deployment_and_operations_guide.md`
    （**本專案無 CI、無 Docker**；改為本機 macOS 執行 runbook 與環境重建步驟）

### 階段 6: 維護管理 (15-16)
16. **documentation** → `15_documentation_and_maintenance_guide.md`
    （SSOT：`docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`、
    `docs/GLB標註pipeline執行說明.md`、`rag_pipeline/README.md`）
17. **wbs** → `16_wbs_development_plan_template.md`
    （對照 `.claude-roompilot/taskmaster-data/wbs.md`）

### 附屬檔（不編號，但屬於那 19 份）
- **index** → `INDEX.md`（模板總索引）
- **output-style** → `output_style.md`（輸出風格規範）

## 合規分析

針對選定的模板檢查專案合規性：

```
模板: $ARGUMENTS
合規分析:

  符合: [項目列表]
  需改善: [項目列表]
  缺失: [項目列表]
  不適用: [本專案沒有的項目，需寫明理由，如「無 CI／無 Docker」「無對外 HTTP API」]

  整體合規: [X]%

建議:
  [Y] 啟動對應 Agent 改善（通常是 workflow-template-manager 或 documentation-specialist）
  [R] 產生詳細報告（寫入 .claude-roompilot/context/ 對應子目錄）
  [C] 交叉檢查其他模板
  [N] 稍後處理
```

## 使用方式

```
/template-check security       # 檢查安全合規（金鑰、輸入驗證）
/template-check architecture   # 檢查架構合規（八段管線是否都出現在架構文件）
/template-check api            # 檢查契約合規（structured outputs schema／SQL 交付）
/template-check tests          # 檢查測試合規（會標出 pytest 尚未建置）
/template-check deployment     # 檢查本機 runbook（會標出無 CI／無 Docker）
```

## 檢查原則

- **模組沒出現在 05 架構文件 = 不存在**；架構變更需同步 08／09／10／14
- 規格與程式衝突時**以 SSOT 文件為準**（見 `.claude-roompilot/CLAUDE.md` 文件清單）
- 本專案不存在的技術（CI、容器、對外 API）標為「不適用」並寫理由，**不得偽造合規**
