---
name: sunnydata-infrastructure
description: 本機環境與執行 runbook — .venv-rag 管理、Ollama 服務、HF 模型快取與離線模式、索引重建與回滾（備份 chroma_db）、資源占用與監看、交付前準備檢查清單。本專案無 Docker、無 CI、無部署。
---

<!-- 繁體中文說明：此技能整合「本機環境建置」與「索引更新／交付」兩部分，涵蓋從環境準備到索引灰度更新的完整工作流程。 -->

# Infrastructure（本機環境與執行）

## Overview

單一技能回答「程式怎麼跑起來」——從本機環境準備到索引更新與交付。

> **本專案前提（PROJECT_BRIEF）**：**無 Docker、無 docker-compose、無 Kubernetes、無 CI、無正式部署**。
> 執行環境只有一個：macOS（Apple Silicon 16 GB）上的 `.venv-rag/`（Python 3.11.15），
> 一律以 `.venv-rag/bin/python` 執行。原技能的容器化與部署章節，在此改寫為
> **本機環境管理**與**索引／資料的灰度更新**等價概念。

Activate when：
- 建置或修復本機執行環境（`.venv-rag/`、套件、Python 版本）
- 設定本機服務（Ollama `qwen3:8b`、Gradio `127.0.0.1:7860`）
- 設計多來源資料流（`rag_dataset/` → `chroma_db/` → `rag_export/`）
- 建立「可重複執行」的驗證流水線（本專案為手動腳本，非 CI）
- 規劃索引更新策略（全量重建 / 增量 / 小樣本先行）
- 實作健康檢查（索引筆數、維度、模型可載入、預熱）
- 準備交付前檢查清單（專題展示 / SQL 端交付）

---

## Part 1: 本機環境

### 環境建置最佳實務

三塊 canonical 設定，各自對應一種執行依賴。**`dev` 與 `production` 不分家**——
本專案只有一個環境，差別只在環境變數。

#### Python 虛擬環境（唯一執行環境）

```bash
# 建立（僅在環境遺失時執行；平時不要重建，1.5 GB 且要重抓套件）
python3.11 -m venv .venv-rag
.venv-rag/bin/python -m pip install --upgrade pip

# 核心套件（版本以實際安裝為準，勿隨意升級）
.venv-rag/bin/pip install \
  "chromadb==1.5.9" \
  "gradio==6.20.0" \
  "sentence-transformers" \
  "anthropic" \
  "pillow"

# 驗證（三行都要過）
.venv-rag/bin/python -c "import sys; print(sys.version)"          # 3.11.15
.venv-rag/bin/python -c "import chromadb, gradio; print(chromadb.__version__, gradio.__version__)"
.venv-rag/bin/python -c "import torch; print(torch.backends.mps.is_available())"   # True
```

> **注意**：`.venv/`（Python 3.9，舊渲染／VLM 標註環境）**目前不存在**。
> `rendering/` 與 `vlm_annotation/` 的腳本重跑前需先重建環境。
> 任何腳本或文件**不得**再寫 `PY=.venv/bin/python`。

#### HuggingFace 模型快取與離線模式

```bash
# 模型快取位置（不在專案內，不會被誤刪，也不進版控）
ls ~/.cache/huggingface/hub
#   models--BAAI--bge-m3                 ← embedding，1024 維
#   models--BAAI--bge-reranker-v2-m3     ← 中文 cross-encoder

# 首次在新機器下載（唯一需要關掉離線模式的時機）
HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 \
  .venv-rag/bin/python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-m3')
CrossEncoder('BAAI/bge-reranker-v2-m3')
print('模型快取完成')"
```

```python
# 程式內已 setdefault，勿移除：未登入被 HF Hub 限流時每次載入會乾等數分鐘
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
```

#### 本機 Ollama 服務（批次風格判定用）

```bash
# 啟動服務（背景常駐，預設 127.0.0.1:11434）
ollama serve

# 模型就緒檢查
ollama list | grep qwen3:8b
ollama pull qwen3:8b            # 未安裝時

# 連通性檢查（不經過 Anthropic，不花錢）
curl -s http://127.0.0.1:11434/api/tags | head -c 200

# 用途：json_adjustment/reclassify_styles.py 的六風格判定
.venv-rag/bin/python json_adjustment/reclassify_styles.py --compare 30
#   加 --provider anthropic 可切成 claude-haiku-4-5（會花錢，全量約 US$7）
```

### .gitignore

定義一次，全專案適用（專案**尚未 git init**，此為 init 後應立即套用的內容）：

```
.anthropic_key
.venv-rag/
.venv/
__pycache__/
*.pyc
chroma_db/
rag_export/*.jsonl
rendering/output/
.DS_Store
*.log
.cache/
```

> `chroma_db/`（366 MB）、`rag_export/`（146 MB）、`rag_dataset/`（79 MB）都是**產物**，
> 應由 `embed_v3.py` 重建而非入庫。唯一必須入庫的產物是 `rag_export/embedding_metadata.json`
> 與 `embedding_validation_report.json`（體積小、是交付契約的一部分）。

### 本機服務組合

#### 標準本機堆疊

沒有 Compose 檔，改用一張「服務表 + 啟動順序」；ChromaDB 是**嵌入式**的，不是獨立服務。

| 服務 | 型態 | 位址 | 啟動方式 | 相依 |
| :--- | :--- | :--- | :--- | :--- |
| Gradio UI | 前景行程 | `127.0.0.1:7860` | `$PY rag_pipeline/app.py` | 模型快取、`chroma_db/` |
| ChromaDB | **嵌入式**（同行程） | `chroma_db/`（本機檔案） | 由 `retriever.py` 開啟 | 無 |
| bge-m3 / reranker | 同行程常駐 | 記憶體約 4.6 GB | `load_models()` 預熱 | HF 快取 |
| Anthropic API | 外部 HTTPS | `api.anthropic.com` | `query_parser.py` | `.anthropic_key` |
| Ollama | 背景服務 | `127.0.0.1:11434` | `ollama serve` | `qwen3:8b` |

```bash
# 啟動順序（依賴由淺入深）
PY=.venv-rag/bin/python

$PY -c "import chromadb; c=chromadb.PersistentClient('chroma_db'); \
        print(c.get_collection('furniture_v3').count())"   # 1. 索引在不在（應為 9349）
$PY rag_pipeline/query_parser.py "日式客廳沙發"             # 2. 金鑰與 LLM 通不通
$PY rag_pipeline/retriever.py   "日式客廳沙發"             # 3. 完整檢索通不通
$PY rag_pipeline/app.py                                    # 4. 起 UI（會先預熱模型）
```

#### 環境變數覆寫

沒有 override 檔，改用啟動時的環境變數；**預設值就是正式值**。

```bash
# 開發／除錯用覆寫（僅在該次執行生效）
HF_HUB_OFFLINE=0 $PY rag_pipeline/app.py          # 允許連 HF（僅首次下載模型）
DEVICE=cpu       $PY rag_pipeline/embed_v3.py     # MPS 出問題時退 CPU
ANTHROPIC_API_KEY=... $PY rag_pipeline/query_parser.py "測試"   # 覆蓋 .anthropic_key

# 正式（無覆寫，全部走預設）
$PY rag_pipeline/app.py
```

#### 服務位址與連線

本機服務靠**固定埠**而非服務發現；所有位址都只綁 loopback。

```
Gradio UI        → http://127.0.0.1:7860      # 只綁 loopback，不開 share
Ollama           → http://127.0.0.1:11434     # 只給 reclassify_styles.py 用
Anthropic API    → https://api.anthropic.com  # 唯一的對外出站
HuggingFace Hub  → 預設封鎖（HF_HUB_OFFLINE=1），僅首次下載模型時開啟
ChromaDB         → 無網路（嵌入式，直接讀 chroma_db/ 目錄）
```

埠被占用的診斷：

```bash
lsof -nP -iTCP:7860 -sTCP:LISTEN     # 誰占了 Gradio 的埠
lsof -nP -iTCP:11434 -sTCP:LISTEN    # Ollama 是否已在跑
```

#### 磁碟資料策略

```
chroma_db/                     # 產物・可重建・366 MB   → 更新前必須備份（見回滾）
rag_export/*.jsonl             # 產物・可重建・146 MB   → 交付前壓縮
rag_export/*.json              # 契約・小・必須保留     → metadata + validation report
rag_dataset/furniture_*.json   # 來源・v1/v2/v3 並存    → 舊版不覆寫
rendering/output/              # 產物・重建成本極高     → 視為半永久資產，勿刪
~/.cache/huggingface/hub       # 外部快取・約 5 GB      → 勿放進專案，勿隨專案刪除
```

### 本機執行安全

#### 執行環境強化

```bash
# 1. 版本固定（絕不隨手 pip install -U）
.venv-rag/bin/pip freeze > requirements.lock.txt      # 專案目前無 lock file，建議補上

# 2. 不以 root 或 sudo 執行任何腳本
#    所有路徑都在使用者家目錄下，不需要提權

# 3. 金鑰檔權限收緊
chmod 600 .anthropic_key
```

#### 執行選項

```bash
# 只綁 loopback，永不開公開分享
#   app.py: launch(server_name="127.0.0.1", server_port=7860)
#   禁止 share=True —— 會產生對外可存取的臨時網址

# 離線優先：預設封鎖模型下載通道
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# 批次工作限縮：先小樣本再全量
$PY rag_pipeline/embed_v3.py --limit 50
```

#### 金鑰管理

```bash
# GOOD：金鑰檔（已列入 .gitignore，權限 600）
cat .anthropic_key            # 僅人工檢視，禁止在腳本／日誌中回顯

# GOOD：環境變數（CI 不存在，但本機切換帳號時好用）
export ANTHROPIC_API_KEY=...
$PY rag_pipeline/query_parser.py "測試"

# BAD：
# MODEL_KEY = "sk-ant-xxxxx"          # 絕不硬編碼在原始碼
# print(open(".anthropic_key").read()) # 絕不回顯金鑰內容
# git add -f .anthropic_key            # 絕不提交
```

### 資源占用與監看

16 GB 機器的硬限制：**UI 執行時不要同時跑批次**。

| 工作 | 常駐記憶體 | 時間 | 備註 |
| :--- | :--- | :--- | :--- |
| Gradio UI（bge-m3 + reranker 預熱） | 約 4.6 GB | 常駐 | 第一次查詢前已預熱完 |
| `embed_v3.py` 全量 | 約 4 GB | 約 27 分鐘 | 9,349 筆 |
| `embed_v3.py --only-changed` | 約 4 GB | 約 1.5 分鐘 | 646 筆變動時 |
| `embed_v3.py --limit 50` | 約 4 GB | < 1 分鐘 | 冒煙測試 |
| `reclassify_styles.py`（Ollama） | 另加 6–8 GB | 依批量 | **不可與 UI 併行** |

```bash
# 即時監看
top -o MEM -n 10                       # 記憶體排序
ps aux | grep -E "python|ollama" | grep -v grep

# 磁碟
du -sh chroma_db rag_export rag_dataset .venv-rag
df -h /

# 模型快取
du -sh ~/.cache/huggingface/hub
```

### 除錯指令

```bash
PY=.venv-rag/bin/python

# 執行日誌（腳本輸出到 stdout，需要留存時自行導向）
$PY rag_pipeline/embed_v3.py 2>&1 | tee logs/embed_$(date +%Y%m%d_%H%M).log

# 進入互動環境檢查（等價於「shell 進容器」）
$PY -i -c "import sys; sys.path.insert(0,'rag_pipeline'); from retriever import *; d=load_data()"

# 索引檢查
$PY -c "import chromadb; c=chromadb.PersistentClient('chroma_db'); \
        col=c.get_collection('furniture_v3'); print(col.count()); print(col.peek(1)['metadatas'])"

# 行程與資源
ps aux | grep -E "python|ollama" | grep -v grep
top -o MEM -n 10
lsof -nP -iTCP:7860 -sTCP:LISTEN

# 重建
$PY rag_pipeline/embed_v3.py --only-changed        # 增量
$PY rag_pipeline/embed_v3.py                       # 全量（先備份 chroma_db/）

# 清理（DESTRUCTIVE —— 執行前務必先備份）
rm -rf chroma_db/                                  # 索引全刪，需 27 分鐘重建
rm -rf .venv-rag/                                  # 環境全刪，需重裝套件
$PY -c "import shutil; shutil.rmtree('rag_pipeline/__pycache__', ignore_errors=True)"

# 連線診斷
curl -s http://127.0.0.1:11434/api/tags | head -c 200      # Ollama 活著嗎
$PY -c "import anthropic, os, pathlib; \
        k=os.environ.get('ANTHROPIC_API_KEY') or pathlib.Path('.anthropic_key').read_text().strip(); \
        print('金鑰長度', len(k))"                          # 只印長度，不印內容
```

---

## Part 2: 索引更新與交付

> **本專案目前沒有部署**：沒有正式環境、沒有 CI、沒有容器映像、沒有流量切換基礎設施。
> 以下把部署策略對映到本專案真正會做的事——**資料與索引的灰度更新**。

### 驗證流水線（手動，無 CI）

#### 本機流水線腳本

沒有 GitHub Actions，改為一支可重複執行的 shell 腳本；每個階段失敗就中止。

```bash
#!/usr/bin/env bash
# scripts/verify.sh —— 本機驗證流水線（本專案無 CI，需人工執行）
set -euo pipefail
PY=.venv-rag/bin/python

echo "[1/6] 環境檢查"
$PY -c "import sys; assert sys.version_info[:2]==(3,11), sys.version; print(sys.version)"

echo "[2/6] 語法檢查（專案未導入 linter，先確保可編譯）"
$PY -m compileall -q rag_pipeline json_adjustment

echo "[3/6] 單元測試（pytest —— 尚未建置，補齊後解除註解）"
# $PY -m pytest tests/ -q --cov=rag_pipeline --cov-report=term-missing

echo "[4/6] 需求解析冒煙"
$PY rag_pipeline/query_parser.py "日式侘寂感、預算兩萬內的客廳沙發" > /dev/null

echo "[5/6] 檢索冒煙"
$PY rag_pipeline/retriever.py "日式侘寂感、預算兩萬內的客廳沙發" > /dev/null

echo "[6/6] 索引健康檢查"
$PY scripts/healthcheck.py

echo "驗證通過"
```

#### 流水線階段

```
改程式（尚未 git init，暫以人工把關）:
  compileall → 需求解析冒煙 → 檢索冒煙 → 索引健康檢查

改資料（rag_dataset / taxonomy / category_groups）:
  build_rag_v3.py --dry-run（看統計）→ embed_v3.py --limit 50（冒煙）
  → 備份 chroma_db → embed_v3.py --only-changed → 健康檢查 → 交付檔驗證
```

### 索引灰度更新策略

#### 增量重建（等價 Rolling）

只重算 `text_hash` 變動的品項，其餘沿用舊向量——新舊向量在同一個 collection 內並存。

```
9,349 筆:  8,703 筆沿用舊向量（reused）
            646 筆重新編碼（changed）
            ↓
        同一個 furniture_v3 collection，逐批 upsert
```

**優點**：零重建等待（1.5 分鐘 vs 27 分鐘）、成本與變動量成正比。
**缺點**：新舊向量共存——**只有在 embedding 模型與 `text_format_version` 都沒變時才安全**。
**使用時機**：標準資料更新（改描述、補標註、調價格）。

```bash
$PY rag_pipeline/embed_v3.py --only-changed
```

#### 雙目錄切換（等價 Blue-Green）

兩份完整索引目錄，驗證通過後原子切換。

```
chroma_db/      (v3 現役) ← retriever 讀取
chroma_db.new/  (v3 新版)   建置中，不對外

# 驗證通過後：
mv chroma_db chroma_db.old && mv chroma_db.new chroma_db
# 出問題時：
mv chroma_db chroma_db.bad && mv chroma_db.old chroma_db     # 秒級回滾
```

**優點**：秒級回滾、切換乾淨、UI 不會讀到半成品索引。
**缺點**：需要 2 倍磁碟（約 732 MB）；切換瞬間需停掉 UI（Chroma 檔案被行程持有）。
**使用時機**：換 embedding 模型、改 `text_format_version`、全量重建。

#### 小樣本先行（等價 Canary）

先跑一小批，看統計與抽樣結果，確認無誤才全量。

```bash
$PY json_adjustment/build_rag_v3.py --dry-run        # 只印統計，不落檔
$PY rag_pipeline/embed_v3.py --limit 50              # 50 筆冒煙，< 1 分鐘
$PY json_adjustment/reclassify_styles.py --compare 30 # 30 筆一致率比對

# 統計看起來合理 → 才全量
$PY rag_pipeline/embed_v3.py
```

**優點**：用極低成本抓出組句錯誤、詞表錯配、風格判定漂移。
**缺點**：小樣本可能沒涵蓋長尾類別；需要人看統計，不是自動化把關。
**使用時機**：改 prompt、改詞表、換判定模型、改 `embedded_text` 組句方式。

#### 決策矩陣

| 情境 | 策略 |
| :--- | :--- |
| 改少量家具描述／標註（相容變更） | 增量重建（`--only-changed`） |
| 換 embedding 模型或維度 | 雙目錄切換（並同步換 collection 名與檔名） |
| 改 prompt／詞表／判定模型（高風險） | 小樣本先行 → 再選增量或雙目錄 |
| 改 `text_format_version`（組句方式） | 雙目錄切換 + 全量重建（增量會混到舊句式） |

### 健康檢查與探針

#### 健康檢查腳本（每個環境定義一次）

```python
# scripts/healthcheck.py —— 索引與模型健康檢查
import json, os, pathlib, sys
import chromadb

PROJ = pathlib.Path(__file__).resolve().parent.parent
EXPECTED_COUNT, EXPECTED_DIM, COLLECTION = 9349, 1024, "furniture_v3"


def check_index() -> dict:
    try:
        col = chromadb.PersistentClient(str(PROJ / "chroma_db")).get_collection(COLLECTION)
        n = col.count()
        dim = len(col.peek(1)["embeddings"][0])
        ok = n == EXPECTED_COUNT and dim == EXPECTED_DIM
        return {"status": "ok" if ok else "degraded", "count": n, "dimension": dim}
    except Exception as exc:                       # 不吞錯，但也不外洩堆疊
        return {"status": "error", "message": f"索引無法開啟：{type(exc).__name__}"}


def check_export() -> dict:
    meta = PROJ / "rag_export" / "embedding_metadata.json"
    if not meta.exists():
        return {"status": "error", "message": "缺少 embedding_metadata.json"}
    m = json.loads(meta.read_text(encoding="utf-8"))
    ok = m["embedding_dimension"] == EXPECTED_DIM and m["failed_count"] == 0
    return {"status": "ok" if ok else "degraded",
            "embedded": m["embedded_count"], "failed": m["failed_count"],
            "model": m["embedding_model"], "generated_at": m["generated_at"]}


def check_key() -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY") or (
        (PROJ / ".anthropic_key").read_text().strip() if (PROJ / ".anthropic_key").exists() else "")
    return {"status": "ok" if key else "error", "length": len(key)}   # 只回長度


if __name__ == "__main__":
    checks = {"index": check_index(), "export": check_export(), "api_key": check_key()}
    healthy = all(c["status"] == "ok" for c in checks.values())
    print(json.dumps({"status": "ok" if healthy else "degraded", "checks": checks},
                     ensure_ascii=False, indent=2))
    sys.exit(0 if healthy else 1)
```

#### 啟動預熱檢查（等價存活／就緒探針）

Gradio 沒有探針機制，改為**啟動時預熱 + 印出就緒狀態**——第一次查詢不該等一分鐘。

```python
# rag_pipeline/app.py 啟動段
print("預熱模型與索引…", flush=True)
from retriever import load_collection, load_models

load_models()                                          # 啟動探針：模型可載入嗎（約 30–60 秒）
print(f"索引就緒：{load_collection().count()} 筆", flush=True)   # 就緒探針：索引筆數對嗎

build_ui().launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())
```

| 探針等價物 | 檢查內容 | 判準 | 失敗處置 |
| :--- | :--- | :--- | :--- |
| 啟動（startup） | `load_models()` 可完成 | 60 秒內回來 | 檢查 HF 快取與 `HF_HUB_OFFLINE` |
| 就緒（readiness） | `collection.count()` | == 9349 | 重跑 `embed_v3.py` |
| 存活（liveness） | 檢索冒煙查詢有結果 | results 非空 | 看 `where` 是否誤含 `rag_indexable` |

### 環境設定

```bash
# 所有設定走環境變數，程式內用 setdefault 給安全預設（不硬編碼）
HF_HUB_OFFLINE=1              # 預設封鎖 HF 連線（勿移除；未登入被限流會卡數分鐘）
TRANSFORMERS_OFFLINE=1        # 同上
ANTHROPIC_API_KEY=            # 未設時退回讀 .anthropic_key
DEVICE=mps                    # mps | cpu（Apple Silicon 優先 MPS，出問題退 CPU）
TOKENIZERS_PARALLELISM=false  # 避免 fork 警告洗版
```

```python
# 啟動即驗證，設定錯就快速失敗
import os, pathlib, sys

REQUIRED_PATHS = [
    "chroma_db", "rag_dataset/furniture_enriched_v3.json",
    "rag_pipeline/category_groups.json", "vlm_annotation/taxonomy_v2.json",
]


def validate_env(proj: pathlib.Path) -> None:
    missing = [p for p in REQUIRED_PATHS if not (proj / p).exists()]
    if missing:
        sys.exit(f"缺少必要檔案：{', '.join(missing)}")

    if not (os.environ.get("ANTHROPIC_API_KEY") or (proj / ".anthropic_key").exists()):
        sys.exit("缺少 ANTHROPIC_API_KEY 或 .anthropic_key")

    device = os.environ.get("DEVICE", "mps")
    if device not in {"mps", "cpu"}:
        sys.exit(f"DEVICE 只能是 mps 或 cpu，收到：{device}")
```

### 回滾策略

```bash
# 索引回滾（更新前務必先備份 —— 這是本專案最重要的回滾前提）
cp -R chroma_db "chroma_db.bak.$(date +%Y%m%d_%H%M)"       # 備份（366 MB）
rm -rf chroma_db && mv chroma_db.bak.20260728_1030 chroma_db  # 還原

# 交付檔回滾
cp -R rag_export "rag_export.bak.$(date +%Y%m%d_%H%M)"
rm -rf rag_export && mv rag_export.bak.20260728_1030 rag_export

# 資料集回滾（v1/v2/v3 並存，不覆寫；退版只需改常數）
#   rag_pipeline/embed_v3.py 與 retriever.py 的 V3 路徑常數指回 furniture_enriched_v2.json

# collection 回滾（雙目錄切換時）
mv chroma_db chroma_db.bad && mv chroma_db.old chroma_db

# 程式碼回滾：專案尚未 git init，目前只能靠手動備份目錄
#   → 建議儘早 git init；在那之前，改動前先 cp -R rag_pipeline rag_pipeline.bak.<日期>
```

**回滾前提**：
- [ ] 更新前已備份 `chroma_db/` 與 `rag_export/`（含日期戳）
- [ ] 資料集舊版本仍在（`furniture_enriched_v1/v2.json` 未被覆寫）
- [ ] 常數集中（`COLLECTION`、`V3`、`EMBED_MODEL`）——退版只需改一處
- [ ] `embedding_metadata.json` 有 `generated_at`，可判斷現役索引是哪一批
- [ ] 回滾流程在小樣本上實際演練過（不是只寫在文件裡）

### 交付前準備檢查清單

#### 應用
- [ ] 冒煙查詢全數通過（`query_parser.py` / `retriever.py` / `app.py` 各一次）
- [ ] 錯誤處理涵蓋邊界（金鑰缺失、索引缺失、0 筆結果、模型載入失敗）
- [ ] 輸出訊息不含金鑰、絕對路徑、堆疊追蹤
- [ ] 啟動預熱會印出索引筆數（9,349）與就緒訊息
- [ ] 環境變數啟動時驗證（缺檔／缺金鑰即 `sys.exit`，不進 UI）

#### 環境
- [ ] `.venv-rag/` 可重建（建議補上 `requirements.lock.txt`，目前尚未建立）
- [ ] 記憶體占用已量測（UI 常駐約 4.6 GB，16 GB 機器不併行批次）
- [ ] 模型快取完整（`bge-m3` + `bge-reranker-v2-m3` 皆在 `~/.cache/huggingface/hub`）
- [ ] 服務只綁 `127.0.0.1`，未開 `share=True`

#### 安全
> 完整清單見 `.claude-roompilot/rules/security.md` 與 `sunnydata-security` 技能
> （金鑰、輸入驗證、prompt injection、LLM 輸出當查詢條件、模型供應鏈）。

#### 監看
- [ ] 批次執行有進度輸出（筆／秒、已用時間、剩餘 ETA）
- [ ] 失敗逐筆寫入 `rag_export/embedding_failures.jsonl`，不中斷整批
- [ ] `embedding_validation_report.json` 的 `coverage_percent` 有人看過
- [ ] 記憶體與磁碟在批次前後各量一次（`top` / `du -sh`）

#### 操作
- [ ] 回滾流程已寫入 `rag_pipeline/README.md` 並實際演練
- [ ] 索引重建耗時已知（全量 27 分鐘 / 增量 1.5 分鐘），可安排時間
- [ ] 常見故障有 runbook（HF 限流、MPS OOM、`where` 命中 0 筆、schema 400）
- [ ] 專題展示前的責任人與備援機器已確認（單機系統，沒有備援就是風險）
