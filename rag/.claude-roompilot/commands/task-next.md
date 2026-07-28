---
description: 從 RoomPilot WBS 取得下一個任務建議，分析優先級和依賴關係。
---

# 下個任務建議

## 功能

分析 WBS 任務清單，考慮依賴關係和優先級，建議最適合的下一個任務。

## 資料來源

**必須** 從 `.claude-roompilot/taskmaster-data/wbs.md` 讀取 WBS 資料。

如果檔案不存在，提示使用者先執行 `/task-init` 初始化專案。

## 分析內容

1. **依賴檢查** -- 前置任務是否完成
2. **優先級排序** -- 關鍵路徑、阻塞因素
3. **複雜度評估** -- 預估時間和難度
4. **Agent 建議** -- 建議搭配的專業 Agent
5. **管線位置** -- 該任務落在 Advanced RAG 的哪一段
   （Query Understanding → Query Rewriting → Metadata Filtering → Vector Retrieval
   → Re-ranking → Budget Allocation → Set Composition → Result Presenter）
6. **成本與耗時風險** -- 是否需要重建索引（全量 27 分鐘）或呼叫批次 LLM（全量約 US$7）

## 輸出格式

```
下個任務建議:

  任務: [任務名稱]
  描述: [簡述]
  優先級: [高/中/低]
  預估: [時間]
  依賴: [前置任務（已完成）]
  管線位置: [Advanced RAG 的哪一段]
  成本風險: [是否需重建索引／是否呼叫批次 LLM]
  建議 Agent: [agent-name]

請選擇:
  [Y] 開始此任務
  [S] 跳過，看下一個
  [D] 查看詳細資訊
  [L] 查看完整任務清單
```

實際範例：

```
下個任務建議:

  任務: 2.2 調整排序加權
  描述: 修改 rag_pipeline/retriever.py:47 的 final 權重，改善日式查詢被 cream 洗版
  優先級: 高
  預估: 2h
  依賴: 2.1 擴充六風格詞表（已完成）
  管線位置: Set Composition 前的加權排序
  成本風險: 不需重建索引；不呼叫批次 LLM
  建議 Agent: code-quality-specialist（改完審查）／architect（若要動公式結構）

請選擇:
  [Y] 開始此任務
  [S] 跳過，看下一個
  [D] 查看詳細資訊
  [L] 查看完整任務清單
```

## 使用方式

```
/task-next              # 取得建議
/task-next --detailed   # 含詳細分析
```

## 狀態同步

當使用者選擇開始任務時：
1. 讀取 `.claude-roompilot/taskmaster-data/wbs.md`
2. 將選中的任務狀態更新為 `🔄 進行中`
3. 更新「最後更新」日期
4. 寫回檔案
5. **時間追蹤**：將任務編號寫入 `.claude-roompilot/taskmaster-data/.current-task`（例如 `2.1`）

當任務完成（透過 `/verify` 或使用者確認）時：
1. 將任務狀態更新為 `✅ 完成`
2. 寫回檔案
3. **時間追蹤**：清除 `.claude-roompilot/taskmaster-data/.current-task`

## 搭配使用

```
/task-next    → 取得任務（自動更新 wbs.md）
/plan         → 規劃實作步驟
/tdd          → 開始開發（pytest 尚未建置，第一次需先建 tests/）
/verify       → 完成驗證（CLI 冒煙：query_parser.py → retriever.py → app.py）
/task-next    → 取得下一個（自動更新 wbs.md）
```

## 動到資料或索引的任務，額外提醒

若建議的任務會改動 `rag_dataset/`、`vlm_annotation/taxonomy_v2.json`
或 `rag_pipeline/category_groups.json`，開始前提示使用者：

```bash
PY=.venv-rag/bin/python
$PY rag_pipeline/embed_v3.py --limit 50      # 先冒煙
$PY rag_pipeline/embed_v3.py --only-changed  # 再增量（text_hash 比對）
```

並提醒同步 SSOT 文件（`docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`、
`json_adjustment/RAGSQL.md`）— **規格衝突以文件為準**。
