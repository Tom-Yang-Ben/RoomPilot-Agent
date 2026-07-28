---
description: RoomPilot 迭代初始化，建立 WBS 任務清單、分析複雜度、選擇開發模式。
---

# 專案初始化

## 功能

分析本次迭代需求，建立工作分解結構 (WBS)，配置開發策略。

RoomPilot 是**既有專案**（9,349 件家具、`furniture_v3` 索引已建置），
因此本指令實務上是「**本輪迭代的 WBS 初始化**」，不是從零開專案。

## 初始化流程

### 步驟 1: 基礎資訊收集

```
1. 迭代名稱？（預設：RoomPilot 檢索優化 - <主題>）
2. 迭代簡述？
3. 主要語言？ Python 3.11.15（唯一環境 .venv-rag/，固定值，僅確認）
4. 版本控制？ 專案尚未 git init — (現在 init / 跳過)
```

### 步驟 2: 需求澄清

```
1. 核心問題：本輪要改善檢索的哪個環節？
   （需求解析 / 硬過濾 / 向量召回 / rerank / 加權排序 / 去重收斂 / Gradio 呈現）
2. 核心功能：3-5 個最重要的工作項？
3. 技術約束：不得換 reranker、不得動 HF_HUB_OFFLINE、金鑰不得外洩
4. 規模需求：9,349 筆索引；UI 常駐約 4.6 GB；單次檢索目標回應時間？
5. 時程資源：全量重建索引約 27 分鐘、六風格全量判定約 US$7 — 額度與時間夠嗎？
```

### 步驟 3: 確認設定

```
專案結構：AI-ML（rag_pipeline / rag_dataset / rag_export / json_adjustment / vlm_annotation）
建議密度：[high/medium/low]
複雜度：[依分析結果]
開發模式：[完整流程/MVP]

確認？(y/N)
```

### 步驟 4: 自動執行

1. 確認既有專案結構（不重建 `rag_pipeline/` 等既有目錄）
2. 更新 `.claude-roompilot/CLAUDE.md` 的迭代重點（不覆寫專案事實）
3. 載入相關 VibeCoding 模板（見 `VibeCoding_Workflow_Templates/INDEX.md`，共 19 份 .md）
4. 建立 WBS 任務清單
5. 版本控制初始化（**專案尚未 git init**；如選擇 init，先確認 `.anthropic_key` 已在 `.gitignore`）
6. 配置 Agent 協調策略（13 個 Agent，見 `/hub-delegate`）

### 步驟 5: 持久化 WBS（關鍵步驟）

**必須** 將 WBS 寫入檔案以跨 session 保存：

1. 建立目錄 `.claude-roompilot/taskmaster-data/`（若不存在）
2. 將完整 WBS 寫入 `.claude-roompilot/taskmaster-data/wbs.md`，格式如下：

```markdown
# WBS - RoomPilot 家具風格檢索系統

**建立日期:** YYYY-MM-DD
**最後更新:** YYYY-MM-DD
**開發模式:** [完整流程/MVP]
**專案描述:** 自然語言家具風格需求 → 從 9,349 件家具檢索最合適物件（純檢索，無 LLM 生成端）

---

## 任務清單

| # | 任務 | 狀態 | 優先級 | 依賴 | 預估 | 備註 |
|---|------|------|--------|------|------|------|
| 1.1 | 迭代初始化 | ✅ 完成 | 高 | - | 0.5h | 自動完成 |
| 1.2 | 需求分析（檢索痛點盤點） | ✅ 完成 | 高 | - | 1h | 自動完成 |
| 2.1 | 擴充六風格詞表（`taxonomy_v2.json` 色卡／氛圍詞） | ⏳ 待處理 | 高 | 1.2 | 2h | 需同步 6×6 相容矩陣 |
| 2.2 | 調整排序加權（`retriever.py:47`） | ⏳ 待處理 | 高 | 2.1 | 2h | 改完須人工比對 12 組查詢 |
| 3.1 | 重建索引（`embed_v3.py --only-changed`） | ⏳ 待處理 | 高 | 2.1 | 0.5h | 646 筆約 1.5 分鐘；全量 27 分鐘 |
| 3.2 | 補 pytest 測試（**尚未建置**測試套件） | ⏳ 待處理 | 中 | 2.2 | 3h | 先建 `tests/` 與 query_parser 契約測試 |
| 4.1 | SQL 交付驗證（`rag_export/` 四個交付檔） | ⏳ 待處理 | 中 | 3.1 | 1.5h | 對照 `json_adjustment/RAGSQL.md` |
| 4.2 | 同步 SSOT 文件（`docs/RAG檢索系統說明.md` 等） | ⏳ 待處理 | 高 | 2.2 | 1h | 規格衝突以文件為準 |
| ... | ... | ... | ... | ... | ... | |

### 狀態說明
- ✅ 完成
- 🔄 進行中
- ⏳ 待處理
- 🚫 阻塞
- ⏭️ 跳過

---

## 里程碑

| 里程碑 | 目標日期 | 包含任務 | 狀態 |
|--------|----------|----------|------|
| M1: 詞表與加權調校完成 | YYYY-MM-DD | 2.x | 進行中 |
| M2: 索引重建 + 測試補齊 | YYYY-MM-DD | 3.x | 待處理 |
| M3: SQL 交付驗收 | YYYY-MM-DD | 4.x | 待處理 |

---

## 風險與阻塞

| 風險 | 影響 | 緩解策略 |
|------|------|----------|
| 全量重建索引耗時 27 分鐘 | 阻塞後續驗證 | 優先用 `--only-changed`；改詞表先跑 `--limit 50` 冒煙 |
| 批次風格判定燒額度（全量約 US$7） | 成本 | 先 `--compare 30` 看一致率再決定是否全量 |
| `rendering/`／`vlm_annotation/` 無可用環境（舊 `.venv/` 已不存在） | 無法重跑標註 | 需求出現時才重建環境 |
| 16 GB 機器 UI 常駐約 4.6 GB | 批次與 UI 搶記憶體 | 不同時跑 UI 與批次 |
```

3. 同時建立 `.claude-roompilot/taskmaster-data/project.json`：

```json
{
  "name": "RoomPilot 家具風格檢索系統",
  "created": "YYYY-MM-DD",
  "mode": "[完整流程/MVP]",
  "language": "Python 3.11.15",
  "python": ".venv-rag/bin/python",
  "collection": "furniture_v3",
  "wbsFile": ".claude-roompilot/taskmaster-data/wbs.md"
}
```

## 使用方式

```
/task-init                       # 互動式初始化
/task-init 檢索加權調校           # 指定本輪迭代名稱
```

## 初始化完成後

```
迭代初始化成功！
WBS 已儲存至 .claude-roompilot/taskmaster-data/wbs.md

下一步:
  /task-next    取得第一個任務
  /plan         規劃實作步驟
  /task-status  查看 WBS 狀態
```
