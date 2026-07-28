---
description: 安全識別並移除 RoomPilot 的死碼與過時資料欄位，每步都有驗證。
---

# 重構清理指令

呼叫 **refactor-cleaner** agent 安全地識別並移除死碼。

> ⚠️ **pytest 尚未建置**：本專案目前沒有測試套件，
> 因此原本「每步跑測試」改為「每步跑 `/verify quick`（語法 + 匯入 + 契約）」，
> 動到檢索邏輯時再加跑一次檢索冒煙 `$PY rag_pipeline/retriever.py "<需求>"`。
> **專案亦尚未 git init**，刪除前必須自行留備份，不能靠 `git checkout` 回復。

## 步驟 1: 偵測死碼

RoomPilot 是純 Python 3.11 專案，一律 `PY=.venv-rag/bin/python`：

| 工具 | 偵測內容 | 指令 |
|------|----------|------|
| vulture | 未使用的 Python 函式、變數、類別 | `$PY -m pip install vulture && $PY -m vulture rag_pipeline json_adjustment vlm_annotation` |
| ruff | 未使用的 import 與區域變數（F401／F841） | `$PY -m pip install ruff && $PY -m ruff check --select F401,F841 rag_pipeline` |
| pipdeptree | 未被任何模組 import 的第三方依賴 | `$PY -m pip install pipdeptree && $PY -m pipdeptree --warn silence` |
| grep 交叉引用 | 定義了但全庫零呼叫的函式（不裝套件的 stdlib 版） | `for fn in $(grep -rhoE "^def [a-z_]+" rag_pipeline/*.py \| sed 's/def //'); do n=$(grep -rho "\b$fn\b" rag_pipeline/*.py \| wc -l); [ "$n" -le 1 ] && echo "只定義未使用: $fn"; done`（目前輸出應為空） |
| 資料欄位稽核 | `furniture_enriched_v3.json` 中沒進 `embedded_text` 也沒進 `chroma_metadata` 的欄位 | `$PY -c "import json;d=json.load(open('rag_dataset/furniture_enriched_v3.json'));i=d['items'][0];print(sorted(set(i)-set(i['chroma_metadata'])))"` |
| 舊版資料檔 | 已被 v3 取代的 v1／v2 中間產物 | `ls -la rag_dataset/ vlm_annotation/taxonomy_v1.json` |

## 步驟 2: 分類發現

| 層級 | 範例 | 行動 |
|------|------|------|
| **安全** | 未使用的工具函式、除錯輔助、模組內部私有函式 | 可放心刪除 |
| **小心** | `retriever.py` 的評分函式、`app.py` 的事件 handler、`embed_v3.py` 的 CLI 旗標 | 驗證無字串引用或 Gradio 綁定 |
| **危險** | `taxonomy_v2.json`／`category_groups.json` 的詞彙欄位、`chroma_metadata` 欄位、`rag_export/` 交付欄位、模組進入點 | 調查後再處理；動到就要重建索引並同步 SSOT 文件 |

## 步驟 3: 安全刪除迴圈

對每個安全項目：
1. **執行驗證基準** -- 跑 `/verify quick`（pytest **尚未建置**，暫以匯入檢查 + 契約檢查為基準）
2. **刪除死碼** -- 精確移除
3. **重新驗證** -- 重跑 `/verify quick`，必要時加跑檢索冒煙
4. **驗證失敗則** -- 立即回復並跳過（**專案尚未 git init**，`git checkout -- <file>` 目前不可用，
   刪除前請先把原檔複製到暫存目錄，或改用編輯器的復原）
5. **驗證通過則** -- 繼續下一個

## 步驟 4: 處理小心項目

刪除前：
- 搜尋動態載入：`importlib`、`getattr()`、`globals()[...]`
- 搜尋字串引用：受控詞彙 key、檢索群組名、`chroma_metadata` 欄位名、Gradio 元件 label
- 檢查是否被 `rag_export/` 交付規格（`json_adjustment/RAGSQL.md`、`i_need_rag.md`）依賴
- 驗證 `docs/` 底下無任何 SSOT 文件仍在描述它 —— **文件還寫著就不算死碼**

## 步驟 5: 合併重複

移除死碼後，尋找：
- 近似重複函式（>80% 相似）-- 合併為一（例如多處各自重算中位價）
- 冗餘常數定義 -- 合併（`COLLECTION`、`CHROMA_DIR`、TOP_K 系列只能有一份來源）
- 無附加值的包裝函式 -- 內聯
- 無用途的 re-export 與轉手 dict 複製 -- 移除間接層（同時遵守不可變性：建新物件，勿就地改）

## 步驟 6: 摘要

```
死碼清理
──────────────────────────────
已刪除:   12 個未使用函式
          3 個未使用檔案
          5 個未使用依賴
已跳過:   2 個項目（驗證失敗）
節省:     約 450 行已移除
──────────────────────────────
/verify quick 通過
索引覆蓋率 9349/9349 未受影響
```

## 規則

- **絕不在未執行驗證的情況下刪除**（pytest 尚未建置 → 以 `/verify quick` + 檢索冒煙為最低門檻）
- **一次一個刪除** -- 原子變更使回復容易
- **不確定就跳過** -- 保留死碼好過破壞檢索品質
- **清理時不重構** -- 分開關注（先清理，再重構）
- **絕不動六個坑相關程式碼**：`HF_HUB_OFFLINE` 的 `setdefault`、rerank 不套 sigmoid、
  schema 的 `anyOf`、reranker 型號常數 —— 它們看起來像冗餘，其實都是防坑用的
- **刪除欄位前先確認索引無需重建**；若必須重建，用 `--only-changed` 增量，別無腦跑 27 分鐘全量
