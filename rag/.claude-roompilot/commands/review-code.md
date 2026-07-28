---
description: 根據 VibeCoding 模板審查 RoomPilot Python 程式碼，涵蓋品質、安全、檢索正確性與架構合規。
---

# 程式碼審查

## 分析目標

分析路徑: $ARGUMENTS（預設為當前目錄）

本專案唯一的應用程式是 `rag_pipeline/`；資料建置在 `json_adjustment/`、
詞表在 `vlm_annotation/`、SSOT 文件在 `docs/`。一律以 `.venv-rag/bin/python` 驗證。

## 審查項目

### 階段 0: 流程合規
- `01_workflow_manual.md` → 開發流程合規性（本專案採 MVP 快速迭代模式）

### 階段 1: 規劃
- `02_project_brief_and_prd.md` → 需求對齊（對照 `.claude-roompilot/PROJECT_BRIEF.md`）
- `03_behavior_driven_development_guide.md` → BDD 覆蓋率（檢索旅程的 Given/When/Then）

### 階段 2: 架構設計
- `04_architecture_decision_record_template.md` → ADR 記錄（換模型／改權重必須留 ADR）
- `05_architecture_and_design_document.md` → 系統架構（Advanced RAG 七段管線是否仍成立）
- `06_api_design_specification.md` → 契約合規（`query_parser.py` structured outputs schema、
  `rag_export/` 交付欄位對照 `json_adjustment/RAGSQL.md`）

### 階段 3: 詳細設計
- `07_module_specification_and_tests.md` → 模組規格與測試（pytest **尚未建置**，以 docstring 契約代之）
- `08_project_structure_guide.md` → 專案結構（`rag_pipeline/` 為唯一應用層，不得散落腳本）
- `09_file_dependencies_template.md` → 依賴分析（`query_parser` → `retriever` → `app` 單向，無循環）
- `10_class_relationships_template.md` → 模組/函式關係設計（本專案以函式為主，檢核單一職責）

### 階段 4: 開發品質
- `11_code_review_and_refactoring_guide.md` → 審查清單
- `12_frontend_architecture_specification.md` → **Gradio 呈現層架構**（`app.py` 的卡片 HTML 組裝、
  縮圖 base64 內嵌、Gradio 6 的 theme 必須在 `launch()` 傳）
- `17_frontend_information_architecture_template.md` → **UI 資訊架構**（單頁：查詢輸入 → 條件摘要 →
  結果卡片 → 追問按鈕；`FINAL_TOP_K=8` 的版面承載量）

### 階段 5: 安全部署
- `13_security_and_readiness_checklists.md` → 安全評估（`.anthropic_key` 不得回顯／提交、查詢輸入驗證）
- `14_deployment_and_operations_guide.md` → **本機執行 runbook**（本專案無 CI、無 Docker；
  檢核索引重建、模型預熱、`127.0.0.1:7860` 啟動步驟是否可重現）

### 階段 6: 維護管理
- `15_documentation_and_maintenance_guide.md` → 文檔品質（SSOT 文件是否與程式同步）
- `16_wbs_development_plan_template.md` → WBS 追蹤

## RoomPilot 專屬審查清單（必查）

### A. 六個坑 — 逐項確認

- [ ] **坑 1**：`rag_indexable` 沒有出現在任何 Chroma `where` 條件裡（它是頂層欄位、不在 `chroma_metadata`，寫了命中 0 筆）
- [ ] **坑 2**：rerank 分數沒有再套 sigmoid（`bge-reranker-v2-m3` 經 CrossEncoder 已輸出 0–1）
- [ ] **坑 3**：structured outputs 中可為 null 的 enum 使用 `anyOf`，不是 type 陣列（否則 400）
- [ ] **坑 4**：`setdefault("HF_HUB_OFFLINE", "1")` 未被移除（否則 HF Hub 限流會卡數分鐘）
- [ ] **坑 5**：尺寸為硬過濾，LLM 未被允許用常識推測（猜錯會直接濾掉正確結果）
- [ ] **坑 6**：reranker 仍是 `BAAI/bge-reranker-v2-m3`，未被換成 ms-marco MiniLM（英文模型會劣化中文查詢）

### B. 硬過濾 / 軟加權界線 — 不得越界

| 欄位類別 | 正確處理 | 審查要點 |
| :--- | :--- | :--- |
| 房型／類別／價格／尺寸 | **硬過濾**（進 Chroma `where`） | 條件缺值時應放行，不可組出必然落空的條件 |
| 風格／氛圍 | **軟加權**（進排序公式） | 絕不可寫進 `where`，否則相容風格會被整批濾掉 |
| 顏色／材質 | **只進 `semantic_query`** | 既不過濾也不加權，錯放會嚴重壓縮召回 |

- [ ] 排序公式仍為 `final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence`
      （權重定義在 `rag_pipeline/retriever.py:47`，改動需附 ADR 與前後檢索比對）
- [ ] `VEC_TOP_K=50` → `RERANK_TOP_K=20`（配件 `RERANK_TOP_K_LIGHT=12`）→ `FINAL_TOP_K=8` 的漏斗未被破壞
- [ ] 六風格值域仍限於 `taxonomy_v2.json` 的 `scandinavian` / `japanese` / `modern_minimal` /
      `cream` / `industrial` / `american`，未在程式中硬編碼自創風格

### C. 一般品質

- [ ] 不可變：建立新 dict／list，未就地修改傳入的 `parsed`、`item`、`chroma_metadata`
- [ ] 函式 < 50 行、檔案 < 800 行、巢狀 ≤ 4 層
- [ ] 錯誤明確處理，不靜默吞噬；使用者可見訊息友善，伺服器端記錄完整上下文
- [ ] 無硬編碼金鑰、無硬編碼絕對路徑（一律以 `PROJ` 為基準組路徑）
- [ ] 改動已同步對應 SSOT 文件（`docs/`、`rag_pipeline/README.md`、`taxonomy_v2.json`、`category_groups.json`）

## 建議 Agent

根據審查結果建議適合的 Agent：

```
審查結果:

建議的 Agent:
  [1] code-quality-specialist -- 程式碼品質深度分析
  [2] security-infrastructure-auditor -- 安全稽核
  [3] test-automation-engineer -- 測試覆蓋補強

請選擇 (1-3) 或 N 跳過:
```

## 使用方式

```
/review-code                      # 審查整個專案
/review-code rag_pipeline/        # 審查檢索管線
/review-code rag_pipeline/retriever.py   # 只審過濾與排序
/review-code json_adjustment/     # 審資料建置腳本與交付規格
```
