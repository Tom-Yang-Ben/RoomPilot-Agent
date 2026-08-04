# VibeCoding v5.0 工程文件索引 — RoomPilot-Agent 導入版

> 本索引由 `VibeCoding_Workflow_Templates/INDEX.md`（v5.0）導入 RoomPilot-Agent 生成
> **基準：** 分支 `django-skill`、commit `a2179f7e`、日期 2026-08-04
> **版本：** v1.0 | **更新：** 2026-08-04

本資料夾是 `VibeCoding_Workflow_Templates/`（v5.0 階段式模板包，`00_meta`–`07_governance`）套用 RoomPilot-Agent 實況後的導入版，共 **19 份 Markdown + 3 份 xlsx tracker**。每份文件的路由、常數、數量、行號均以基準工作區程式碼實查填寫；查不到依據者標「(未查證)」。

目錄結構鏡射模板包，**資料夾本身就是分類**，不必再查對照表。

---

## 文件清單

### `00_meta/` — 流程指南

| 檔名 | 用途 |
| :--- | :--- |
| [output_style.md](./00_meta/output_style.md) | 回答呈現的寫作規範：引註 `檔案:行號`、未查證標記、交付結構與蘇格拉底檢核；含本 repo 具體範例 |
| [workflow_manual.md](./00_meta/workflow_manual.md) | 開發流程使用說明書：Profile 選擇（Fast／Product／Governed）、工作入口、跨 owner 修改與合併 Gate |

### `01_requirements/` — 需求與產品

| 檔名 | 用途 |
| :--- | :--- |
| [requirement_decision_record.md](./01_requirements/requirement_decision_record.md) | 需求決策紀錄：決策邊界、DEC 主表、Gate 紀錄、決策沿革與 `/specify` 硬閘檢查（**回溯導入，待 owner 逐列補簽**） |
| [project_brief_and_prd.md](./01_requirements/project_brief_and_prd.md) | 專案簡報與 PRD：商業目標、使用者故事與允收標準、範圍限制、待辦問題與決策 |
| [bdd_guide.md](./01_requirements/bdd_guide.md) | BDD 指南：Gherkin 速查、主流程情境集、**新子系統情境集**（工程文件／RAG）、與 `tests/` 的落地對照 |
| `requirements_tracker.xlsx` | 需求追蹤表（模板原檔，未填） |

### `02_ux_ui/` — UX／UI／前端

| 檔名 | 用途 |
| :--- | :--- |
| [frontend_information_architecture.md](./02_ux_ui/frontend_information_architecture.md) | 前端資訊架構：頁面職責、核心旅程、導航結構、路由表與跨頁資料模型 |
| [frontend_architecture_spec.md](./02_ux_ui/frontend_architecture_spec.md) | 前端架構規範：**兩套前端並存現況**、分層、Design Tokens、效能與可用性量化標準 |

### `03_architecture/` — 系統架構

| 檔名 | 用途 |
| :--- | :--- |
| [architecture_and_design.md](./03_architecture/architecture_and_design.md) | 架構與設計文件（本包最長，1,008 行）：C4 L1–L3、DDD 戰略／戰術、Sequence、資料架構、部署視圖 |
| [adr.md](./03_architecture/adr.md) | 架構決策紀錄：ADR 索引與既成決策（含 ADR-004 型錄母集合已被 ADR-007 取代的沿革） |
| [project_structure.md](./03_architecture/project_structure.md) | 專案結構指南：頂層結構、目錄用途與負責人、`pyproject.toml`／uv 工作流、命名慣例 |
| `engineering_tracker.xlsx` | 工程追蹤表（模板原檔，未填） |

### `04_design/` — 技術設計

| 檔名 | 用途 |
| :--- | :--- |
| [api_design.md](./04_design/api_design.md) | API 設計規範：**63 條路由逐條核對**、通用行為、錯誤處理、安全性、資料模型 |
| [module_spec_and_tests.md](./04_design/module_spec_and_tests.md) | 模組規格與測試（DbC）：`backend/engine` 幾何核心 + **工程文件 MVP** + **RAG runtime**，含本日實測證據 |
| [file_dependencies.md](./04_design/file_dependencies.md) | 模組依賴分析：分層依賴圖、關鍵依賴路徑、DAG 驗證與外部依賴清單 |
| [class_relationships.md](./04_design/class_relationships.md) | 類別／元件關係：核心類別圖、職責、設計模式、SOLID 檢核與介面契約 |

### `05_qa/` — QA／測試／安全

| 檔名 | 用途 |
| :--- | :--- |
| [code_review_and_refactoring.md](./05_qa/code_review_and_refactoring.md) | 審查與重構指南：審查前檢查、分支與 Commit 慣例、**既有技術債清單**（逐項複查） |
| [security_and_readiness.md](./05_qa/security_and_readiness.md) | 安全與生產準備：**資安基線 R1–R8**（源自 `roompilot-security` skill 並重查）＋ A–E 檢查清單 |
| `qa_tracker.xlsx` | QA 追蹤表（模板原檔，未填） |

### `06_ops/` — DevOps／維運

| 檔名 | 用途 |
| :--- | :--- |
| [deployment_and_operations.md](./06_ops/deployment_and_operations.md) | 部署與維運：部署架構、CI/CD、檢查清單、部署策略、監控告警與回滾流程 |

### `07_governance/` — 專案治理

| 檔名 | 用途 |
| :--- | :--- |
| [wbs_development_plan.md](./07_governance/wbs_development_plan.md) | WBS 開發計劃：任務分解、進度摘要、風險管理與里程碑 |
| [documentation_and_maintenance.md](./07_governance/documentation_and_maintenance.md) | 文檔與維護指南：文檔類型、文檔即程式碼、維護排程與 README 模板 |

---

## 相對 `docs/vibecoding/`（2026-07-26 舊導入版）的主要差異

舊導入版是 **01–17 平面編號結構**、對分支 `bella-local-20260726`（commit `e48cd67`）填寫；本版是 **v5.0 階段式資料夾結構**、對 `django-skill`（`a2179f7e`）重查。兩者不是改版關係，是**不同模板世代 × 不同事實基準**。

1. **結構換代**：01–17 平面編號 → `00_meta`–`07_governance` 依文件分層歸類；新增舊版沒有的 `requirement_decision_record`（需求決策硬閘）。
2. **路由數 44 → 63**：舊版 44 條為 `main.py` 單檔年代；現行為 `main.py` 46 + `rag_api.py` 5 + `catalog_admin.py` 4 + `engineering/api.py` 8。
3. **新增工程文件 MVP 子系統**：`backend/server/engineering/`（snapshot → lock → packages → jobs → documents），舊版完全未涵蓋；已寫入 03 架構、04 模組規格、06 部署。
4. **新增家具 RAG runtime**：`backend/spatial_data/rag/` 經 `backend/server/rag_api.py` 掛載 `/api/rag/*`，與工程側 Structured Retrieval 是**兩條獨立檢索路徑**。
5. **新增 PostgreSQL 五階段**：`docs/contracts/POSTGRESQL_*.md` 與 `scripts/sql/` 的型錄／embeddings／project store 遷移，舊版仍寫「伺服器執行期不連 Postgres」。
6. **型錄件數釐清為三個不同數字**：官方雲端母集合 **8,557 件**（`cloud_catalog.py:15` 載入期硬驗證，載入來源檔 `JSON/furniture/furniture_official_catagory.json`）／舊 fallback 來源檔 `backend/catalog/data/furniture_catalog_cloud_9350.json` 頂層 count **9,350**（非 8,557 的前身）／RAG 向量索引 **9,349** 筆。舊版只寫 9,350 且未區分。
7. **新增 `.claude/skills/` 四支專案 skill**：`roompilot-security`（資安基線 R1–R8，已成為 05 安全文件的來源）、`roompilot-furniture-query`、`roompilot-proposal`、`roompilot-budget`。
8. **測試基準更新**：舊版記錄「389 passed / 2 failed」；現行工作樹 2026-08-04 實測 `pytest -q tests` = **811 passed / 1 failed / 9 skipped**（共 821），repo 根 `pytest -q`（含 `training/`）= **916 passed / 3 failed / 9 skipped**，各文件均以此為準。

---

## 查核紀錄

本批 19 份文件已於 2026-08-04 完成逐檔對抗查核與跨文件一致性核對，所有數字、路由、常數與 `檔案:行號` 引註均回到基準工作區（分支 `django-skill`、commit `a2179f7e`）重新驗證。

**統計：** 查核 **19 份文件**、抽驗 **1,400 條斷言**、修正 **148 處事實錯誤**。

### 逐檔查核結論

| 文件 | 抽驗斷言 | 修正處 | 結論 |
| :--- | ---: | ---: | :--- |
| [00_meta/output_style.md](./00_meta/output_style.md) | 58 | 5 | minor_fixes |
| [00_meta/workflow_manual.md](./00_meta/workflow_manual.md) | 60 | 9 | minor_fixes |
| [01_requirements/project_brief_and_prd.md](./01_requirements/project_brief_and_prd.md) | 62 | 7 | minor_fixes |
| [01_requirements/bdd_guide.md](./01_requirements/bdd_guide.md) | 162 | 2 | minor_fixes |
| [01_requirements/requirement_decision_record.md](./01_requirements/requirement_decision_record.md) | 44 | 15 | minor_fixes |
| [02_ux_ui/frontend_architecture_spec.md](./02_ux_ui/frontend_architecture_spec.md) | 55 | 8 | minor_fixes |
| [02_ux_ui/frontend_information_architecture.md](./02_ux_ui/frontend_information_architecture.md) | 76 | 9 | minor_fixes |
| [03_architecture/adr.md](./03_architecture/adr.md) | 68 | 6 | minor_fixes |
| [03_architecture/architecture_and_design.md](./03_architecture/architecture_and_design.md) | 118 | 13 | minor_fixes |
| [03_architecture/project_structure.md](./03_architecture/project_structure.md) | 52 | 5 | minor_fixes |
| [04_design/api_design.md](./04_design/api_design.md) | 96 | 9 | minor_fixes |
| [04_design/class_relationships.md](./04_design/class_relationships.md) | 112 | 7 | minor_fixes |
| [04_design/file_dependencies.md](./04_design/file_dependencies.md) | 95 | 7 | minor_fixes |
| [04_design/module_spec_and_tests.md](./04_design/module_spec_and_tests.md) | 68 | 8 | minor_fixes |
| [05_qa/code_review_and_refactoring.md](./05_qa/code_review_and_refactoring.md) | 68 | 7 | minor_fixes |
| [05_qa/security_and_readiness.md](./05_qa/security_and_readiness.md) | 52 | 7 | minor_fixes |
| [06_ops/deployment_and_operations.md](./06_ops/deployment_and_operations.md) | 46 | 8 | minor_fixes |
| [07_governance/documentation_and_maintenance.md](./07_governance/documentation_and_maintenance.md) | 52 | 2 | minor_fixes |
| [07_governance/wbs_development_plan.md](./07_governance/wbs_development_plan.md) | 56 | 14 | minor_fixes |
| **合計** | **1,400** | **148** | 19 份全部 minor_fixes、0 份 clean、0 份 major_fixes |

### 跨文件一致性三維度

| 維度 | 發現 | 已修正 | 主要內容 |
| :--- | ---: | ---: | :--- |
| 一、跨文件共同事實統一 | 5 | 5 | 測試執行結果口徑不一（10 處）、認證範圍矛盾（11 處，正確值為 59/63 條無認證、`/api/admin/furniture` 4 條有 Bearer token）、型錄 8,557 來源檔張冠李戴（10 處）、`WORKFLOW_PANEL_BY_STEP` 行號（1 處，正解 `scene_workflow.js:18-30`）、`engineering/` 檔數表述（2 處，正解 14 支 `.py` 共 3,111 行＋Node adapter `workbook_builder.mjs`，全套件 15 檔）。路由 63 條、port 8002、8 顆按鈕 vs 11 個 step、6 風格 × 3 色卡 = 18、負責人表、基準 banner、測試檔數等經實測一致，未改動。 |
| 二、C4／DDD 鐵律與跨文件同步表 | 10 | 10 | L2 Current 與 Future State 漏畫 `Node 子行程 → 檔案儲存` 邊、Future State 與 Deployment Diagram 箭頭缺動詞、DDD Context Map 自環誤用 Shared Kernel、L3-A 圖混入他 Container 內容物、`api → 問卷視覺索引` 標成唯讀（實為 sync 重建）；並補齊 `project_structure`、`deployment_and_operations`、`file_dependencies` 三份下游文件缺席的 Container，新增 §L3-Y「Container 的跨文件同步狀態」表明示範圍界線。 |
| 三、API 逐條核對 | 2 | 2 | 以實際載入 `app` 遞迴展開 `include_router` 列舉，得 46＋4＋5＋8 = **63 條**，與 §5.0 清單 100% 吻合：漏列 0、多列 0、method／path 寫錯 0，63 個出處行號與另抽驗約 110 個非路由行號引註全數命中。修正 `api_design.md:16` 數法（補記 FastAPI 另自動掛 4 條文件路由、不計入）與 `frontend_information_architecture.md:289` frontend3d 對口路由的失效區間引註（正解 `main.py:3551/3556/3572/2707`）。 |

查核針對事實正確性與引註有效性，不含人工審閱與業務正確性。

---

## 使用規則

- **不按序填滿**：資料夾編號只為對齊文件分層，不代表 `00 → 07` 的強制流水線；只讀與當前範圍直接相關的章節。
- **事實以程式碼為準**：本包所有數字均為 2026-08-04 快照。程式碼演進後，以實際工作樹為準並更新本包；**不要**反向要求程式碼配合文件。
- **跨文件一致性**：架構文件（`03_architecture/architecture_and_design.md`）是模組存在與否的權威——模組沒出現在該文件即視為不存在；架構變更須同步 `project_structure`、`file_dependencies`、`class_relationships`、`deployment_and_operations`。
- **未查證標記**：標「(未查證)」者為 repo 內查無依據或本次未實際執行的項目，不得當作既成事實引用。
- 模板 `INDEX.md` 指向的 `software_development_documentation_guide_zh_tw.docx` 與 `docs/document-system/` 不在本 repo (未查證：來源不在 repo)。
