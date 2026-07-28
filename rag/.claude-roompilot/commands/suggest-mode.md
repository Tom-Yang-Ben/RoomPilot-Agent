---
description: 調整 RoomPilot 開發中 Agent 建議的頻率和密度，控制人機協作模式。
---

# 建議模式控制

## 模式說明

| 模式 | 說明 | 適用場景 |
| :--- | :--- | :--- |
| `high` | 每個任務節點都建議 Agent | 新手、學習中、初次接觸檢索管線 |
| `medium` | 僅在關鍵決策點建議（預設） | 日常開發（調權重、擴詞表） |
| `low` | 僅在必要時建議 | 熟練開發者 |
| `off` | 關閉自動建議 | 心流模式、快速試 query 調參 |

## 使用方式

```
/suggest-mode high      # 每步都建議
/suggest-mode medium    # 關鍵點建議（預設）
/suggest-mode low       # 最少建議
/suggest-mode off       # 關閉建議
```

## 模式行為

### high
- 每完成一個函式（如 `retriever.py` 的加權函式）→ 建議 code-quality-specialist
- 每次交付／提交前（**專案尚未 git init**，指「收尾一段工作」時）→ 建議 security-infrastructure-auditor
- 每個新功能 → 建議 tdd-guide（pytest **尚未建置**，第一次會先建 `tests/`）
- 每次改完 `taxonomy_v2.json` 或 `category_groups.json` → 提醒跑 `embed_v3.py --limit 50` 冒煙

### medium（預設）
- 完成整個功能後 → 建議 code-quality-specialist
- 準備交付／同步 SSOT 文件時 → 建議安全檢查與 documentation-specialist
- 動到排序公式（`retriever.py:47`）時 → 建議 architect 覆核

### low
- 僅在偵測到風險時建議（金鑰外洩風險、測試缺失、
  把 `rag_indexable` 寫進 Chroma `where`、對 rerank 分數再套 sigmoid）

### off
- 完全不主動建議，只在你呼叫 `/hub-delegate` 時才啟動

## 不受模式影響的硬提醒

無論設為哪個模式，以下情況一律提醒（屬於 CLAUDE.md「六個坑」與成本紅線）：

- 即將提交或回顯 `.anthropic_key` 內容
- 即將跑全量建索引（約 27 分鐘）或六風格全量判定（約 US$7）
- 即將移除 `HF_HUB_OFFLINE` 設定
- 即將把 reranker 換成英文模型（ms-marco MiniLM）
