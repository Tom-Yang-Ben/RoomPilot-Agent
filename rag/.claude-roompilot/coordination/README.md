# Coordination 協調機制目錄

此目錄管理 Subagent 之間的協調機制，包括任務交接和衝突解決記錄。

本專案為 **RoomPilot 家具風格檢索系統**（Python 3.11.15 / Gradio 6 / ChromaDB `furniture_v3` /
bge-m3 / bge-reranker-v2-m3 / claude-haiku-4-5 需求解析），交接場景一律以
**VLM 標註批次 → 資料加工 → 索引重建 → 檢索調校 → UI 驗收** 這條流水線為背景。

## 目錄結構

```
.claude-roompilot/coordination/
├── handoffs/     # Agent 間任務交接記錄
└── conflicts/    # 衝突解決與決策記錄
```

## handoffs/ 目錄

### 用途
記錄 Agent 間的任務交接過程，確保工作的連續性和完整性。
本專案的批次工作（VLM 標註、六風格判定、全量建索引）耗時且會燒 API 額度，
**交接記錄必須寫明「已跑到哪一批、是否可續跑、重跑成本」**，避免重複執行。

### 檔案命名
格式: `handoff-{from-agent}-to-{to-agent}-{YYYY-MM-DD-HHMM}.md`
範例: `handoff-code-quality-specialist-to-test-automation-engineer-2026-07-28-1530.md`

### 常見交接場景

#### 1. 品質檢查 → 測試執行
- **觸發**: code-quality-specialist 發現需要補強測試的程式碼
  （例：`retriever.py` 的去重收斂與預算分配缺少邊界驗證）
- **交接內容**: 問題程式碼位置（`rag_pipeline/retriever.py:47` 權重區塊等）、建議測試案例、測試策略
- **期望結果**: test-automation-engineer 補強相關測試
  （本專案**測試套件尚未建置**，預設以 pytest 起步，先補純函式層級案例）

#### 2. 測試完成 → E2E 驗證
- **觸發**: test-automation-engineer 完成單元測試 / CLI 單測
  （`.venv-rag/bin/python rag_pipeline/query_parser.py "<需求>"`）
- **交接內容**: 測試覆蓋範圍、需要 E2E 驗證的功能（卡片排序、追問按鈕、圖片載入）
- **期望結果**: e2e-validation-specialist 於 `http://127.0.0.1:7860` 執行端到端驗證

#### 3. 安全檢查 → 執行準備
- **觸發**: security-infrastructure-auditor 完成安全檢查
  （`.anthropic_key` 未入庫、報告未回顯金鑰、批次額度上限確認）
- **交接內容**: 安全檢查結果、批次腳本執行前的金鑰與成本配置要求
- **期望結果**: deployment-expert 依要求啟動本機服務／批次工作（**本專案無 CI、無 Docker**）

#### 4. 執行完成 → 文檔更新
- **觸發**: deployment-expert 完成索引重建與 UI 啟動
- **交接內容**: 索引筆數與耗時（全量 9,349 筆約 27 分鐘）、參數變更、`rag_export/` 交付檔異動
- **期望結果**: documentation-specialist 更新 `docs/RAG檢索系統說明.md` 與 `rag_pipeline/README.md`

#### 5. VLM 標註批次 → 資料加工
- **觸發**: `vlm_annotation/` 批次標註完成或中斷（可續跑）
- **交接內容**: 已完成／待補的 item 清單、失敗原因、續跑指令
- **期望結果**: 後手執行 `python3 json_adjustment/build_rag_v3.py --dry-run` 先看統計再正式加工

#### 6. 索引重建 → 檢索調校
- **觸發**: `.venv-rag/bin/python rag_pipeline/embed_v3.py`（或 `--only-changed`）完成
- **交接內容**: 索引版本（collection `furniture_v3`）、變更欄位、`rag_export/` 四個交付檔驗證報告
- **期望結果**: 後手以 `retriever.py "<需求>"` 抽驗前 8 名，確認硬過濾未誤殺

#### 7. 檢索調校 → UI 調整
- **觸發**: 排序權重或 `FINAL_TOP_K` 變更
- **交接內容**: 新舊權重對照、受影響的風格類型（如 japanese↔scandinavian 相容度 0.9）
- **期望結果**: 後手調整 `rag_pipeline/app.py` 卡片呈現與追問按鈕文案並截圖驗收

### 交接流程
1. **發起交接**: 來源 Agent 建立交接記錄
2. **資訊傳遞**: 提供完整的背景和期望結果
3. **接收確認**: 目標 Agent 確認接收和理解
4. **執行工作**: 目標 Agent 執行相關工作
5. **結果回報**: 記錄執行結果和後續建議

## conflicts/ 目錄

### 用途
記錄 Agent 間的意見衝突和主 Agent 的決策過程。

### 檔案命名
格式: `conflict-{YYYY-MM-DD-HHMM}-{簡要描述}.md`
範例: `conflict-2026-07-28-1530-rerank-model-disagreement.md`

### 衝突類型

#### 1. 技術選型衝突
- **場景**: 不同 Agent 對技術選擇有不同建議
  （例：有 agent 主張換成較輕的 ms-marco MiniLM reranker，但那是英文模型、中文查詢會劣化）
- **處理**: 主 Agent 基於架構考量做最終決策，並以 `PROJECT_BRIEF.md` 的「六個坑」為否決依據
- **記錄**: 各方觀點、決策理由、實施計劃

#### 2. 優先級衝突
- **場景**: 多個 Agent 都認為自己的任務最重要
  （例：重建索引 vs 先修 UI 卡片；全量重建約 27 分鐘且期間不宜同時跑批次）
- **處理**: 主 Agent 基於業務價值和風險評估
- **記錄**: 優先級排序理由、資源分配決策

#### 3. 標準衝突
- **場景**: 不同領域的最佳實踐產生衝突
  （例：檢索端想把顏色／材質也做成硬過濾，但規格明訂顏色／材質只進 `semantic_query`）
- **處理**: 主 Agent 制定統一標準或例外處理；規格衝突時**以 SSOT 文件為準**
- **記錄**: 標準制定過程、例外情況處理

#### 4. 資源衝突
- **場景**: 多個 Agent 需要相同的資源或工具
  （例：16 GB 機器上 UI 常駐 bge-m3 + reranker 約 4.6 GB，與批次建索引搶記憶體／MPS；
  或多方同時呼叫 Haiku 造成額度競用）
- **處理**: 主 Agent 協調資源分配和使用時程（批次與 UI 錯開執行）
- **記錄**: 資源分配方案、協調結果

### 衝突解決流程
1. **衝突識別**: Agent 發現意見不一致時上報
2. **資訊收集**: 主 Agent 收集各方觀點和論據
3. **影響評估**: 分析不同選擇的業務和技術影響
4. **決策制定**: 基於整體考量做出決策
5. **執行監控**: 監控決策執行效果
6. **後續檢討**: 定期檢討決策是否需要調整

## 協調原則

### 透明度原則
- 所有交接和衝突都要有明確記錄
- 決策過程和理由都要公開透明
- 相關 Agent 都能查閱相關記錄

### 效率原則
- 簡化不必要的交接流程
- 建立標準化的協調機制
- 避免過度的官僚程序

### 學習原則
- 從協調過程中學習改善點
- 建立協調最佳實踐
- 持續優化協調機制

## 監控與改善

### 協調效率指標
- 交接完成時間
- 衝突解決時間
- Agent 協作滿意度
- 重複衝突頻率
- 批次重跑次數與額度耗用（需求解析每次約 US$0.005、六風格全量判定約 US$7）

### 定期檢討
- 月度協調效率檢討
- 季度協調機制優化
- 年度協調策略調整

### 持續改善
- 基於指標數據優化流程
- 收集 Agent 協作回饋
- 引入新的協調工具和方法（MCP server 現況見 `.claude-roompilot/mcp-configs/README.md`）

---

良好的協調機制是 Subagent 系統成功的關鍵，確保各個專業 Agent 能夠有效協作，產生最佳的整體效果。