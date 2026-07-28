---
description: 對 RoomPilot 當前程式碼庫與索引狀態執行全面驗證檢查。
---

# 驗證指令

> 一律 `PY=.venv-rag/bin/python`。本專案**無 CI、無 Docker**，所有檢查在本機 macOS 執行。

## 說明

依以下確切順序執行驗證：

### 1. 建置檢查（語法 + 匯入）
- 執行 `$PY -m compileall -q rag_pipeline json_adjustment`
- 執行 `$PY -c "import rag_pipeline.query_parser, rag_pipeline.retriever, rag_pipeline.embed_v3, rag_pipeline.app"`
- 如失敗則報告錯誤並停止

### 2. 契約檢查（取代型別檢查）
- 本專案無 TypeScript／目前未安裝 mypy；改驗**輸出契約**
- 比對 `query_parser.py` 組出的 schema 與 `docs/query_parser_spec.md`
- 確認可為 null 的 enum 一律使用 `anyOf`（坑 3），schema 內不得出現 `{"type": ["string", "null"]}`
- 確認受控詞彙來源仍是 `taxonomy_v2.json` 與 `category_groups.json`，未硬編碼
- 報告所有不符含 `檔案:行號`

### 3. Lint 檢查
- **ruff／flake8 目前未安裝**（尚未建置）；先跑 stdlib 版：
  `$PY -W error::SyntaxWarning -m compileall -q rag_pipeline`
- 若已安裝則跑 `$PY -m ruff check rag_pipeline json_adjustment`
- 報告警告和錯誤

### 4. 解析冒煙（Query Understanding）
```bash
$PY rag_pipeline/query_parser.py "北歐風客廳想找一張淺色布沙發，預算三萬"
```
- 應輸出合法 JSON，且風格落在六風格之內
- 未提尺寸時**不得**出現尺寸欄位（坑 5：LLM 不得用常識推測）
- 注意：每次呼叫約 US$0.005

### 5. 檢索冒煙（全鏈路）
```bash
$PY rag_pipeline/retriever.py "日式侘寂風臥室，木質衣櫃"
```
- 應回傳 ≤ `FINAL_TOP_K=8` 筆、無重複 `id`、主導風格收斂
- 命中 0 筆時第一個要查的是：`where` 是否誤含 `rag_indexable`（坑 1）
- reranker 每 50 筆約 10 秒，屬正常延遲

### 6. 索引覆蓋率檢查（Chroma count 對照 v3 筆數）
```bash
$PY - <<'EOF'
import json, chromadb
items = json.load(open("rag_dataset/furniture_enriched_v3.json"))["items"]
idx = [i for i in items if i.get("rag_indexable")]
n = chromadb.PersistentClient(path="chroma_db").get_collection("furniture_v3").count()
print(f"v3 items      : {len(items)}")
print(f"rag_indexable : {len(idx)}")
print(f"chroma count  : {n}")
print("覆蓋率        : %.2f%%" % (100 * n / max(len(idx), 1)))
print("PASS" if n == len(idx) else "FAIL — 需 $PY rag_pipeline/embed_v3.py --only-changed")
EOF
```
- 基準值：**9349 / 9349 / 9349，覆蓋率 100.00%**
- 不足時用 `--only-changed` 增量補（約 1.5 分鐘），不要無腦跑 27 分鐘全量

### 7. 資料檔完整性
```bash
$PY - <<'EOF'
import json, pathlib
FILES = ["rag_dataset/furniture_enriched_v3.json", "rag_pipeline/category_groups.json",
         "vlm_annotation/taxonomy_v2.json", "rag_export/embedding_metadata.json",
         "rag_export/embedding_validation_report.json"]
for p in FILES:
    f = pathlib.Path(p); ok, n = f.exists(), "-"
    if ok:
        try: n = len(json.load(f.open()))
        except Exception as e: ok, n = False, str(e)[:40]
    print(f"{'OK  ' if ok else 'FAIL'} {p}  keys/len={n}")
jl = pathlib.Path("rag_export/furniture_embeddings_bge_m3.jsonl")
fl = pathlib.Path("rag_export/embedding_failures.jsonl")
print("向量 jsonl 行數:", sum(1 for _ in jl.open()) if jl.exists() else "MISSING")
print("失敗清單行數  :", sum(1 for _ in fl.open()) if fl.exists() else "MISSING")
tx = json.load(open("vlm_annotation/taxonomy_v2.json"))
print("六風格:", list(tx["styles"]))
print("相容矩陣維度:", len(tx["style_compat"]), "×", len(next(iter(tx["style_compat"].values()))))
EOF
```
- 基準值：五個 JSON 全 OK、向量 jsonl **9349** 行、失敗清單 **0** 行、
  `styles` 六個、`style_compat` **6×6**

### 8. 秘密稽核
- 確認 `.anthropic_key` 未被 `git add`、未被任何腳本 `print`
- 搜尋原始碼中的硬編碼金鑰：`grep -rn "sk-ant" rag_pipeline json_adjustment vlm_annotation`
- **絕不回顯金鑰內容**

### 9. Debug 輸出稽核
- 搜尋暫時性 `print()` 與 `breakpoint()`：
  `grep -rn "breakpoint()\|# TODO\|# FIXME\|print(\"DEBUG" rag_pipeline json_adjustment`
- 報告位置（`embed_v3.py` 的進度 `print` 是正式輸出，不算 debug 殘留）

### 10. 版本控制狀態
- **本專案尚未 git init**，`git status` 目前無法執行
- 替代做法：列出最近修改的檔案
  `find rag_pipeline json_adjustment vlm_annotation docs -name "*.py" -o -name "*.md" -newermt "-1 day"`
- 一旦 `git init` 後，恢復顯示未提交變更與自上次 commit 以來修改的檔案

## 輸出

產出簡潔的驗證報告：

```
VERIFICATION: [PASS/FAIL]

Build:      [OK/FAIL]              # 語法 + 匯入
Contract:   [OK/X errors]          # schema ↔ query_parser_spec.md
Lint:       [OK/X issues/SKIP]     # ruff 尚未安裝時填 SKIP
Parse:      [OK/FAIL]              # 解析冒煙
Retrieve:   [OK/X hits]            # 檢索冒煙，應 ≤ 8 且 > 0
IndexCov:   [9349/9349 = 100.00%]  # Chroma count 對照 v3
DataFiles:  [OK/X missing]         # 5 JSON + jsonl 9349 行 + 失敗 0
Secrets:    [OK/X found]
Logs:       [OK/X debug prints]
Tests:      [尚未建置 — pytest 未安裝]

Ready for delivery: [YES/NO]
```

如有任何關鍵問題，列出並附修復建議。

## 參數

$ARGUMENTS 可以是：
- `quick` - 僅建置檢查 + 契約檢查（不呼叫 API、不載模型，數秒完成）
- `full` - 所有檢查（預設）
- `pre-commit` - 建置 + 契約 + Lint + 秘密稽核 + Debug 稽核（不燒額度）
- `pre-delivery` - 完整檢查加索引覆蓋率與 `rag_export/` 交付檔完整性
