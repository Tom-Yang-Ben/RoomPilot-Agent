---
name: sunnydata-deep-research
description: 使用 firecrawl 與 exa MCP 的多來源深度研究。搜尋網路、綜整發現，交出附來源標註的引用式報告。當使用者需要對某主題（如替代 reranker 評估、六風格詞表擴充依據、Chroma 過濾語法）做有憑有據的徹底研究時使用。
origin: ECC
---

# 深度研究（RoomPilot 版）

使用 firecrawl 與 exa MCP 工具，從多個網路來源產出徹底、附引用的研究報告。

## 何時啟動

- 使用者要求對任一主題做深入研究
- 競品分析、技術選型評估、模型／套件比較
- 對模型、資料集、授權條款做盡職調查（例如 ABO / IKEA 資料來源、模型授權）
- 任何需要綜整多個來源才能回答的問題
- 使用者說「研究一下」「深入查」「調查」「現在的做法是什麼」

## MCP 需求

至少要有其中之一：
- **firecrawl** — `firecrawl_search`、`firecrawl_scrape`、`firecrawl_crawl`
- **exa** — `web_search_exa`、`web_search_advanced_exa`、`crawling_exa`

兩者一起用涵蓋度最好。設定於 `~/.claude.json` 或 `~/.codex/config.toml`。

## 工作流程

### Step 1：釐清目標

問 1-2 個快速澄清問題：
- 「你的目標是什麼 — 學習、做決策，還是要寫成文件？」
- 「有沒有特定角度或深度要求？」

如果使用者說「就查一查」— 用合理預設直接往下。

### Step 2：規劃研究

把主題拆成 3-5 個研究子問題。範例：
- 主題：「評估是否要把 `bge-reranker-v2-m3` 換成其他 reranker」
  - 目前有哪些支援中文的 cross-encoder reranker？
  - 它們在中文檢索基準（如 C-MTEB reranking）上的表現如何？
  - 在 Apple Silicon（MPS）上的延遲與記憶體佔用如何？
  - 授權條款是否允許本專案使用？
  - 換掉後，`retriever.py` 的 `final = 0.60×rerank + …` 權重是否需要重新校正？

> RoomPilot 的既有結論：**勿換成 ms-marco MiniLM**（英文模型，中文查詢會劣化）。
> 研究若要推翻既有結論，必須提出可比較的中文基準證據。

### Step 3：執行多來源搜尋

對**每一個**子問題，用可用的 MCP 工具搜尋：

**用 firecrawl：**
```
firecrawl_search(query: "<子問題關鍵字>", limit: 8)
```

**用 exa：**
```
web_search_exa(query: "<子問題關鍵字>", numResults: 8)
web_search_advanced_exa(query: "<關鍵字>", numResults: 5, startPublishedDate: "2025-01-01")
```

**搜尋策略：**
- 每個子問題用 2-3 種不同的關鍵字變化（中英文各試，模型名建議用英文）
- 混用一般搜尋與新聞導向查詢
- 目標 15-30 個不重複來源
- 優先序：學術論文、官方文件（Hugging Face model card、Chroma / Gradio docs）、可信媒體 > 部落格 > 論壇

### Step 4：深讀關鍵來源

對最有價值的 URL 抓取完整內容：

**用 firecrawl：**
```
firecrawl_scrape(url: "<url>")
```

**用 exa：**
```
crawling_exa(url: "<url>", tokensNum: 5000)
```

完整讀 3-5 個關鍵來源以求深度。不要只靠搜尋摘要片段。

### Step 5：綜整並撰寫報告

報告結構：

```markdown
# [主題]：研究報告
*產出日期：[date] | 來源數：[N] | 信心度：[高/中/低]*

## 執行摘要
[3-5 句話概述關鍵發現]

## 1. [第一個主要主題]
[附行內引用的發現]
- 關鍵論點（[來源名稱](url)）
- 佐證數據（[來源名稱](url)）

## 2. [第二個主要主題]
...

## 3. [第三個主要主題]
...

## 關鍵結論
- [可行動的洞察 1]
- [可行動的洞察 2]
- [可行動的洞察 3]

## 來源
1. [標題](url) — [一行摘要]
2. ...

## 方法論
共執行 [N] 次查詢（網頁 + 新聞），分析 [M] 個來源。
調查的子問題：[列表]
```

### Step 6：交付

- **短主題**：把完整報告直接貼在對話裡
- **長報告**：貼執行摘要 + 關鍵結論，完整報告存成檔案
  （放 `.claude-roompilot/context/decisions/`，命名依 `rules/subagent-context.md`）

## 用 Subagent 平行研究

主題很廣時，用 Claude Code 的 Task 工具平行化：

```
平行啟動 3 個研究 agent：
1. Agent 1：研究子問題 1-2（候選 reranker 清單與中文基準表現）
2. Agent 2：研究子問題 3-4（MPS 延遲／記憶體、授權條款）
3. Agent 3：研究子問題 5 + 跨面向主題（換模型後的權重重新校正方法）
```

每個 agent 各自搜尋、讀來源、回傳發現。主 session 綜整成最終報告。

## 品質規則

1. **每個論述都要有來源。** 不允許無來源的斷言。
2. **交叉比對。** 只有單一來源說的，標記為「未經驗證」。
3. **時效重要。** 優先採用近 12 個月的來源（模型與框架版本變動快）。
4. **承認缺口。** 某個子問題找不到好資料，就明講。
5. **不許幻覺。** 不知道就說「查無足夠資料」。
6. **事實與推論分開。** 明確標示估計值、預測與意見。

## 範例

```
「研究可替代 bge-reranker-v2-m3 的中文 cross-encoder reranker，含中文基準與授權」
「深入查 bge-m3 以外的中文長文 embedding 模型，1024 維、normalized、MAX_SEQ_LEN 512 的取捨」
「研究六風格 taxonomy 擴充的依據 — 業界（IKEA/Houzz/Pinterest）如何定義風格分類與相容度」
「調查 ChromaDB 1.5.x 的 where 過濾語法與多條件 $and/$in 的效能特性」
「研究 Gradio 6 的 theme 與卡片式結果呈現的常見做法」
```
