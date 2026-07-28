---
description: 分析當前 session 並擷取 RoomPilot 檢索管線值得保存的可重用模式作為知識。
---

# 學習指令

分析當前 session 並擷取任何值得保存為技能的模式（RoomPilot 家具風格檢索系統）。

## 觸發時機

在 session 中解決非平凡問題的任何時刻執行 `/learn`。
本專案典型觸發點：檢索命中 0 筆、rerank 分數異常、Haiku structured outputs 回 400、
bge-m3 模型載入卡住、Gradio 卡片沒吃到渲染圖、`embed_v3.py --only-changed` 沒偵測到變更。

## 擷取目標

尋找以下內容：

### 1. 錯誤解決模式
- 發生了什麼錯誤？
- 根因是什麼？
- 什麼修復了它？
- 這對類似錯誤是否可重用？

> 範例：檢索結果 0 筆 → 根因是把頂層欄位 `rag_indexable` 寫進 Chroma `where`
> → 改為只用 `chroma_metadata` 內的欄位過濾 → 可重用於任何新增硬過濾條件的場合。

### 2. 除錯技巧
- 不明顯的除錯步驟
- 有效的工具組合
- 診斷模式

> 範例：先用 `.venv-rag/bin/python rag_pipeline/query_parser.py "<需求>"` 單測解析結果，
> 再用 `.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` 跑 CLI 完整檢索，
> 分段確認是「解析錯」還是「檢索錯」，最後才開 `app.py` 看 UI。

### 3. 變通方案
- 套件的特殊行為
- API 限制
- 版本特定的修復

> 範例：Gradio 6.20.0 的 theme 必須在 `launch()` 傳而非建構子；
> `HF_HUB_OFFLINE=1` 用來避開 HF Hub 未登入限流卡數分鐘；
> Anthropic structured outputs 中可為 null 的 enum 要寫 `anyOf` 而非 type 陣列。

### 4. 專案特定模式
- 發現的程式碼庫慣例
- 做出的架構決策
- 整合模式

> 範例：硬過濾（房型／類別／價格／尺寸）與軟加權（風格／氛圍）的界線；
> 顏色／材質只進 `semantic_query` 不做過濾；
> 排序公式 `0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence`
> 的權重調整必須同步 `docs/RAG檢索系統說明.md`。

## 輸出格式

建立技能檔案於 `.claude-roompilot/skills/learned/[模式名稱].md`:

```markdown
# [描述性模式名稱]

**擷取日期:** [日期]
**情境:** [簡述此模式何時適用]

## 問題
[此模式解決什麼問題 - 要具體]

## 解決方案
[模式/技巧/變通方案]

## 範例
[適用時附上程式碼範例，一律 Python 3.11，執行方式 .venv-rag/bin/python]

## 使用時機
[觸發條件 - 什麼情況應啟動此技能]
```

範例檔名：`chroma-where-只能用-chroma_metadata-欄位.md`、
`bge-reranker-輸出已是-0-1-勿再套-sigmoid.md`、
`embed_v3-only-changed-的-text_hash-比對規則.md`

## 流程

1. 審查 session 中可擷取的模式
2. 識別最有價值/可重用的洞察
3. 撰寫技能檔案草稿
4. 請使用者確認後再儲存
5. 儲存至 `.claude-roompilot/skills/learned/`

## 注意事項

- 不擷取瑣碎修復（打字錯誤、簡單語法錯誤）
- 不擷取一次性問題（特定 API 中斷等）
- 專注於能在未來 session 節省時間的模式
- 保持技能聚焦 -- 一個模式一個技能
- **絕不把 `.anthropic_key` 內容或任何金鑰寫進技能檔案**
- 已列在 `.claude-roompilot/CLAUDE.md`「六個坑」的內容不需重複擷取，改為補充新發現的坑
