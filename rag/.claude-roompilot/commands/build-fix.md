---
description: 以最小、安全的變更漸進式修復 Python 語法、匯入與資料載入錯誤。
---

# 建置修復指令

呼叫 **build-error-resolver** agent 以最小差異修復錯誤。

> RoomPilot 是純 Python 3.11 專案，**沒有編譯步驟、沒有 CI、沒有容器**。
> 這裡的「建置」＝ 語法可編譯 + 模組可匯入 + 資料檔可載入 + 索引可開啟。
> 所有指令一律 `PY=.venv-rag/bin/python`。

## 步驟 1: 偵測建置系統

依「指標」判斷該跑哪個檢查，由淺到深逐層執行：

| 指標 | 建置指令 |
|------|----------|
| 任何 `rag_pipeline/*.py` 有改動 | `$PY -m py_compile rag_pipeline/*.py` |
| 改到 import 或新增第三方套件 | `$PY -c "import rag_pipeline.retriever, rag_pipeline.query_parser, rag_pipeline.embed_v3"` |
| 改到 `app.py` / Gradio 版面 | `$PY -c "import rag_pipeline.app as a; a.build_ui()"`（只建不 launch） |
| 改到 `query_parser.py` 的 schema | `$PY rag_pipeline/query_parser.py "北歐風客廳沙發 預算三萬"` |
| 改到 `retriever.py` 的過濾／排序 | `$PY rag_pipeline/retriever.py "日式臥室 木質衣櫃"` |
| 改到 `rag_dataset/*.json` / `category_groups.json` / `taxonomy_v2.json` | `$PY -c "import json;[json.load(open(p)) for p in ['rag_dataset/furniture_enriched_v3.json','rag_pipeline/category_groups.json','vlm_annotation/taxonomy_v2.json']]"` |
| 改到 `embed_v3.py` 的文字組裝 | `$PY rag_pipeline/embed_v3.py --limit 50 --skip-chroma`（冒煙，不寫索引） |
| 懷疑索引與資料不同步 | `$PY -c "import chromadb;print(chromadb.PersistentClient(path='chroma_db').get_collection('furniture_v3').count())"` → 應為 **9349** |

## 步驟 2: 解析並分組錯誤

1. 執行建置指令並擷取 stderr（Python traceback 讀**最後一行**的例外型別）
2. 依檔案路徑分組錯誤
3. 依依賴順序排序（先修 import／資料載入，再修邏輯錯誤）
4. 計算總錯誤數以追蹤進度

## 步驟 3: 修復迴圈（一次一個錯誤）

對每個錯誤：
1. **讀取檔案** -- 查看錯誤前後 10 行上下文
2. **診斷** -- 識別根因（缺少 import、欄位名打錯、JSON key 不存在、語法錯誤）
3. **最小修復** -- 用最小變更解決錯誤
4. **重新建置** -- 重跑步驟 1 對應的指令，驗證錯誤消失且無新錯誤
5. **繼續下一個** -- 處理剩餘錯誤

## 步驟 4: 安全護欄

遇到以下情況時停止並詢問使用者：
- 修復引入的錯誤**多於解決的**
- **同一錯誤嘗試 3 次後仍存在**
- 修復需要**架構變更**（例如要改 Chroma collection schema）
- 錯誤源於**缺少依賴**或**缺少環境**（`.venv/` Python 3.9 已不存在，`rendering/`、`vlm_annotation/` 腳本需先重建環境）
- 修復會**觸發全量重建索引**（27 分鐘）或**批次 API 呼叫**（約 US$7）

## 步驟 5: 摘要

顯示結果：
- 已修復的錯誤（含檔案路徑）
- 剩餘的錯誤（如有）
- 引入的新錯誤（應為零）
- 未解決問題的建議後續步驟

## 恢復策略

| 情況 | 行動 |
|------|------|
| 缺少模組/import（`ModuleNotFoundError`） | 確認用的是 `.venv-rag/bin/python` 而非系統 `python3`；必要時 `$PY -m pip install <pkg>` |
| 欄位/鍵不匹配（`KeyError`、`TypeError`） | 對照 `docs/query_parser_spec.md` 與 `chroma_metadata` 實際欄位，修較窄的那一端 |
| 循環依賴 | `query_parser` → `retriever` → `app` 必須單向；發現反向 import 就提取共用常數 |
| 版本衝突 | `$PY -m pip list` 比對 PROJECT_BRIEF 鎖定版本（Gradio 6.20.0、ChromaDB 1.5.9） |
| 配置/資料檔錯誤 | 讀 `category_groups.json`、`taxonomy_v2.json`；欄位以 SSOT 文件為準 |
| Chroma 查詢命中 0 筆 | 檢查是否把 `rag_indexable` 寫進了 `where`（**坑 1**）；它不在 `chroma_metadata` 裡 |
| 模型下載卡住數分鐘 | HF Hub 限流（**坑 4**）；確認 `HF_HUB_OFFLINE=1` 的 `setdefault` 沒被移除 |
| Anthropic API 回 400 | 可為 null 的 enum 要用 `anyOf`（**坑 3**），不可直接寫 type 陣列 |

一次修復一個錯誤以確保安全。優先最小差異而非重構。
