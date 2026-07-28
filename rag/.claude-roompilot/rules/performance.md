# 效能優化

## Claude 模型（agent 層）選擇

本節講的是**開發工具側**的模型，與下一節「RoomPilot 管線用的模型」是兩回事，勿混淆。

**現況（如實記錄）**：`settings.json` 為 `"model": "opus"`，
`agents/*.md` 的 13 個 agent frontmatter **全部**為 `model: opus`。
`README.md` 的 Agents 表與 `WORKFLOW.md` 的「Agent 使用時機」皆以此為準。

為何一律 opus：

- 本專案的高頻工作是**檢索品質推理**（解析 → `where` 條件 → 召回 → rerank → 排序公式的逐層因果），
  以及**六個坑的合規判斷**（`rag_indexable`、sigmoid、`anyOf`、尺寸硬過濾……）。
  這些踩錯的代價是「結果看起來正常但其實錯」，比多花 token 貴得多。
- 專案規模小（單一 `rag_pipeline/` 應用、無 CI、無多團隊併發），
  subagent 呼叫量低，**開發工具側的 token 不是本專案的成本大宗**。
- 真正會燒額度的是**批次工作**（六風格全量判定約 US$7、VLM 標註），
  與 agent 模型無關 —— 控成本要控批次，不是控 agent。

要降級時（例如只做跨檔搜尋、死碼清理這類低推理量任務）：

1. 改該 agent 檔 frontmatter 的 `model:`（**不要動 `settings.json` 的主模型**）
2. **同步**更新 `README.md` 的 Agents 表 Model 欄與 `WORKFLOW.md` 的說明
3. 驗證未漂移：`grep -H '^model:' .claude-roompilot/agents/*.md`

> 沒同步兩份文件 = 使用者照文件估成本會估錯，等同本規則失效。

## 模型選擇策略（RoomPilot 管線用的模型）

| 模型 | 適用場景 | 取捨與實測 |
| :--- | :--- | :--- |
| **`BAAI/bge-m3`**（embedding） | 全量／增量建索引、查詢向量化 | 1024 維 normalized、`MAX_SEQ_LEN=512`；全量 9,349 筆約 27 分鐘。多語佳，別換小模型省時間，召回會塌 |
| **`BAAI/bge-reranker-v2-m3`**（rerank） | 向量召回後的精排 | 中文 cross-encoder，每 50 筆約 10 秒 —— **是端到端延遲主因**。輸出已是 0–1，不可再套 sigmoid；勿換 ms-marco MiniLM（英文模型，中文劣化） |
| **`claude-haiku-4-5`**（需求解析／VLM 標註） | 線上單次解析、批次標註 | structured outputs + prompt caching，每次約 US$0.005，延遲遠低於 rerank，不是瓶頸 |
| **本機 Ollama `qwen3:8b`** | 批次六風格判定（`reclassify_styles.py`） | 免額度但慢；全量改用 `--provider anthropic` 走 Haiku 約 US$7。全量批次前先 `--compare 30` 看一致率 |

**會燒額度的是批次工作**，不是線上查詢。跑全量前先小批驗證。

## 執行資源與瓶頸

- **device 優先 MPS，出問題退 CPU**：`embed_v3.py --device cpu`（`pick_device()` 預設 `auto`）
- **記憶體頻寬才是瓶頸，不是核心數** —— Apple Silicon 16 GB 上開多進程併發建索引無效甚至更慢，
  一次跑一條管線就好
- **UI 常駐約 4.6 GB**（bge-m3 + reranker 同時載入），跑 UI 時不要同時開批次任務
- **rerank 是延遲主因**：要壓延遲先動 `RERANK_TOP_K`（20）／`RERANK_TOP_K_LIGHT`（12），
  而不是砍 `VEC_TOP_K`（50，砍了直接傷召回）
- **增量優先**：`embed_v3.py --only-changed` 以 `text_hash` 比對，646 筆約 1.5 分鐘 vs 全量 27 分鐘；
  `--limit 50` 用於冒煙
- **HF Hub 已設 `HF_HUB_OFFLINE=1`**，勿移除——未登入被限流會卡數分鐘

## Context Window 管理

避免在最後 20% context 中進行：
- 大規模重構（例如重排檢索管線分層）
- 跨多檔案的功能實作（`query_parser.py` + `retriever.py` + `app.py` 連動改動）
- 複雜互動除錯（解析結果 → `where` 條件 → 命中筆數的逐層追查）

低 context 敏感任務：
- 單檔案編輯
- 獨立工具函式（`style_score` / `mood_score` 這類純函式）
- 文檔更新（`docs/`、`rag_pipeline/README.md`）
- 簡單 bug 修復

## 執行疑難排解

建索引／檢索失敗時（本專案無建置步驟，Python 直接執行）：
1. 載入 sunnydata-debugging skill
2. 分析錯誤訊息（先看是模型載入、Chroma `where`、還是 API 金鑰問題）
3. 增量修復
4. 每次修復後驗證：`.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` 看命中筆數與排序

## 平行任務處理

面對 2+ 個獨立任務時，載入 sunnydata-parallel-agents skill 進行平行派發。
注意：平行的是**代理工作**，不是模型推論——建索引／rerank 仍維持單一進程。
