# Context 目錄說明

此目錄用於儲存各個 Subagent 的工作成果和主 Claude Code Agent 的決策記錄，實現跨 agent 的上下文共享。

本專案為 **RoomPilot 家具風格檢索系統**（Python 3.11.15 / Gradio 6 UI / ChromaDB `furniture_v3` /
bge-m3 embedding / bge-reranker-v2-m3 / claude-haiku-4-5 需求解析，9,349 件家具、六風格 taxonomy）。
所有報告與決策一律以此技術棧為背景撰寫，執行指令一律 `.venv-rag/bin/python`。

## 目錄結構

```
.claude-roompilot/context/
├── decisions/     # 主 Agent 技術決策記錄（檢索權重、taxonomy、模型選型）
├── quality/       # code-quality-specialist 報告（rag_pipeline/、json_adjustment/）
├── testing/       # test-automation-engineer 報告（pytest 為預設建議，尚未建置）
├── e2e/           # e2e-validation-specialist 報告（Gradio UI 127.0.0.1:7860 檢索流程）
├── security/      # security-infrastructure-auditor 報告（.anthropic_key、批次成本）
├── deployment/    # deployment-expert 報告（本機執行 runbook；本專案無 CI／無 Docker）
├── docs/          # documentation-specialist 報告（docs/、rag_pipeline/README.md）
└── workflow/      # workflow-template-manager 報告與 VibeCoding 範本合規記錄
```

## 檔案命名規範

### 決策記錄 (decisions/)
格式: `ADR-{YYYY-MM-DD}-{序號}-{簡要標題}.md`
範例: `ADR-2026-07-28-001-reranker-selection.md`
（為何採用中文 cross-encoder `bge-reranker-v2-m3`，而非英文 ms-marco MiniLM）

### Agent 報告
格式: `{agent-name}-report-{YYYY-MM-DD-HHMM}.md`
範例: `code-quality-specialist-report-2026-07-28-1530.md`

### 主 Agent 摘要寫入（見 `rules/subagent-context.md`）
格式: `{agent-type}-{YYYY-MM-DD-HHmm}-{簡要主題}.md`
範例: `architect-2026-07-28-1500-retriever-weight-redesign.md`
（重新設計 `final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence` 權重）

## 各目錄職責

### decisions/
- **負責 Agent**: 主 Claude Code Agent
- **內容**: 系統架構決策、技術選型、跨領域決策
  （例：硬過濾 vs 軟加權界線、`retriever.py:47` 排序權重調整、embedding／reranker 模型選型、
  `VEC_TOP_K` / `RERANK_TOP_K` / `FINAL_TOP_K` 參數變更）
- **格式**: ADR (Architecture Decision Record)
- **更新頻率**: 按需要，重大決策時

### quality/
- **負責 Agent**: code-quality-specialist
- **內容**: `rag_pipeline/`（`app.py`／`query_parser.py`／`retriever.py`／`embed_v3.py`）與
  `json_adjustment/`、`vlm_annotation/` 的程式碼品質檢查、重構建議、技術債務評估
- **格式**: 標準化品質報告
- **更新頻率**: 程式碼變更後、定期檢查

### testing/
- **負責 Agent**: test-automation-engineer
- **內容**: 測試執行結果、覆蓋率報告、測試基礎設施狀態
  （本專案**尚未建置正式測試套件**，預設建議 pytest；現行驗證手段為
  `.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50` 冒煙測試與
  `.venv-rag/bin/python rag_pipeline/query_parser.py "<需求>"` 單測）
- **格式**: 標準化測試報告
- **更新頻率**: 測試執行後、每次索引重建或解析 schema 變更後（本專案無 CI，皆為本機手動執行）

### e2e/
- **負責 Agent**: e2e-validation-specialist
- **內容**: 端到端檢索流程驗證、使用者流程驗證、Gradio UI 測試
  （輸入自然語言需求 → 卡片呈現 → 追問按鈕；服務位址 `http://127.0.0.1:7860`）
- **格式**: 標準化 E2E 報告
- **更新頻率**: 交付前、Demo 前、UI 或檢索邏輯調整後

### security/
- **負責 Agent**: security-infrastructure-auditor
- **內容**: 安全稽核報告、金鑰外洩掃描、合規檢查
  （重點：`.anthropic_key` 純文字金鑰不得提交或回顯、`ANTHROPIC_API_KEY` 注入方式、
  批次工作成本控管——風格判定全量約 US$7、需求解析每次約 US$0.005）
- **格式**: 標準化安全報告
- **更新頻率**: 定期安全檢查、交付前

### deployment/
- **負責 Agent**: deployment-expert
- **內容**: 本機執行 runbook、啟動與預熱記錄、效能分析
  （bge-m3 + reranker 常駐約 4.6 GB、device 優先 MPS 退 CPU、全量建索引約 27 分鐘；
  **本專案無 CI、無 Docker**，「部署」即本機 macOS 啟動 `rag_pipeline/app.py`）
- **格式**: 標準化執行記錄報告
- **更新頻率**: 每次重建索引或重啟 UI 後、出現記憶體／延遲異常時

### docs/
- **負責 Agent**: documentation-specialist
- **內容**: 文檔更新記錄、知識庫維護報告、SSOT 文件同步狀態
  （`docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`、`docs/GLB標註pipeline執行說明.md`、
  `rag_pipeline/README.md`、`json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md`）
- **格式**: 標準化文檔報告
- **更新頻率**: 文檔變更後、程式與規格不一致時立即補正

### workflow/
- **負責 Agent**: workflow-template-manager
- **內容**: VibeCoding 範本合規檢查、WBS 任務狀態、開發時間追蹤
- **格式**: 標準化流程報告
- **更新頻率**: 階段啟動與收尾時

## 使用原則

### 寫入原則
1. **所有權**: 每個目錄只由對應的 Agent 寫入（主 Agent 代寫摘要時亦寫入對應子目錄）
2. **標準格式**: 必須使用標準化的報告範本（見 `rules/subagent-context.md` 的報告範本）
3. **及時更新**: 完成工作後立即產出報告，只留最終結論與可操作建議，不留思考過程
4. **版本控制**: 保留歷史版本，便於追溯（**專案尚未 git init**，現階段以檔名時間戳區分版本；
   同一任務多次呼叫同型 agent 時只保留最終版本）

### 讀取原則
1. **開放讀取**: 所有 Agent 都可以讀取所有目錄
2. **上下文注入**: 主 Agent 負責整合相關上下文
3. **依賴關係**: Agent 間可以引用其他 Agent 的報告
   （例：quality 報告指出 `retriever.py` 去重邏輯過長 → testing 針對該函式補 pytest 案例）
4. **決策依據**: 使用共享上下文做出更好的決策，並與 SSOT 文件（`docs/`）交叉核對；規格衝突時以文件為準

### 維護原則
1. **定期清理**: 清理過期的臨時報告（如單次索引冒煙測試記錄）
2. **重要保留**: 保留重要的決策記錄和里程碑報告（如 v2→v3 資料加工、六風格 taxonomy 定版）
3. **索引管理**: 維護報告索引，便於查找
4. **備份機制**: 重要決策記錄需要備份；金鑰、`.anthropic_key` 內容一律不得寫入任何報告

## 協作流程

### 新任務啟動
1. 主 Agent 檢查相關的歷史決策和報告（`ls -t .claude-roompilot/context/decisions/ | head -5`）
2. 根據上下文制定任務策略，並確認是否踩到「六個坑」（如 `rag_indexable` 不可寫進 Chroma `where`）
3. 分派任務給對應的專業 Agent

### 任務執行中
1. Agent 讀取相關的上下文資訊
2. 執行專業工作並產出中間報告
3. 必要時與其他 Agent 協作（交接記錄寫入 `.claude-roompilot/coordination/handoffs/`）

### 任務完成後
1. 產出標準化的最終報告
2. 更新相關的決策記錄
3. 為後續任務提供上下文

## 品質保證

### 報告品質
- 使用標準範本確保格式一致
- 包含必要的技術細節和建議（指令一律寫成 `.venv-rag/bin/python <script>` 可直接複製執行）
- 提供可操作的行動項目

### 一致性檢查
- 主 Agent 負責檢查報告間的一致性
- 識別並解決潛在的衝突（衝突記錄寫入 `.claude-roompilot/coordination/conflicts/`）
- 確保技術決策的連貫性，並與 `taxonomy_v2.json`、`category_groups.json` 等 SSOT 保持一致

### 追溯性
- 所有重要決策都有明確的記錄
- 可以追溯決策的背景和理由
- 支援決策的檢討和修正

---

此上下文管理機制確保所有 Agent 都能在充分的資訊基礎上做出專業決策，同時保持整體系統的一致性和品質。