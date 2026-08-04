# SETUP — clone 之後怎麼跑起來

從零到能查詢，四步。全程約 40 分鐘（大部分在等模型下載與建索引）。

環境需求：**Python 3.11**、macOS 或 Linux、約 **12 GB** 可用磁碟（模型 9 GB ＋ 索引 1.5 GB）。
執行時 bge-m3 ＋ reranker 常駐約 **4.6 GB** 記憶體。

---

## 步驟一：建立環境

```bash
cd rag
python3.11 -m venv .venv-rag
.venv-rag/bin/pip install -r requirements.txt
```

本專案**所有指令一律用 `.venv-rag/bin/python`**，不要用系統 python。

## 步驟二：下載模型（約 9 GB，只需一次）

程式碼在 `retriever.py:29` 與 `embed_v3.py` 都設了 `HF_HUB_OFFLINE=1`
（避免 HF Hub 未登入被限流時乾等數分鐘）。**新環境第一次跑必須先關掉它**，
否則會因為本機沒有快取而直接失敗：

```bash
HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 .venv-rag/bin/python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-m3')
CrossEncoder('BAAI/bge-reranker-v2-m3')
print('模型已快取到 ~/.cache/huggingface')"
```

下載完之後就不用再管這兩個環境變數了。

## 步驟三：設定 API 金鑰

需求解析用 `claude-haiku-4-5`，每次查詢約 US$0.005。

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

或在 `rag/` 底下放一個純文字檔 `.anthropic_key`（已列入 `.gitignore`，**絕不可提交**）。

## 步驟四：建立向量索引（約 27 分鐘）

`chroma_db/` 不在版控內（365 MB，且每次重建都是全新的二進位 blob），需要自己建。
來源 `rag_dataset/furniture_enriched_v3.json` 已在 repo 內，可直接跑：

```bash
.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50    # 先冒煙測試（約 1 分鐘）
.venv-rag/bin/python rag_pipeline/embed_v3.py               # 全量 9,349 筆（約 27 分鐘）
```

跑完會同時產出 `chroma_db/` 與 `rag_export/` 的交付檔。驗證：

```bash
.venv-rag/bin/python -c "
import chromadb; c = chromadb.PersistentClient('chroma_db').get_collection('furniture_v3')
print('索引筆數:', c.count(), '（應為 9349）')"
```

---

## 開始使用

```bash
PY=.venv-rag/bin/python
$PY rag_pipeline/query_parser.py "奶油風的沙發，預算三萬內"   # 只看需求解析
$PY rag_pipeline/retriever.py   "日式侘寂感的收納櫃"          # CLI 完整檢索
$PY rag_pipeline/app.py                                      # UI → http://127.0.0.1:7860
```

---

## 沒有隨 repo 散布的東西

這些是資料產物或本機專屬，刻意不進版控：

| 項目 | 大小 | 影響 | 怎麼取得 |
| :--- | ---: | :--- | :--- |
| `chroma_db/` | 365 MB | **不建就無法檢索** | 步驟四自建，或向維護者要 |
| `rag_export/furniture_embeddings_bge_m3.jsonl` | 106.5 MB | 只影響 SQL 端交付 | 步驟四會一併產出（**超過 GitHub 100 MB 上限，無法入庫**） |
| `rendering/output/`（9,350 張 PNG） | 2.0 GB | **卡片沒有縮圖**，其餘功能正常 | 向維護者要 |
| `vlm_annotation/render_meta_full.jsonl` | 5.6 MB | 同上（缺檔已優雅降級，不會崩） | `build_render_meta_full.py` 重建，需先有 PNG |
| HF 模型快取 | ~9 GB | 不下載就無法啟動 | 步驟二 |
| `.venv-rag/` | 1.4 GB | — | 步驟一（內含絕對路徑，本來就不可攜） |
| `.anthropic_key` | — | 沒有就無法解析需求 | 步驟三，自備 |

**沒有縮圖不影響檢索**：`render_index()` 與 `thumb_data_uri()` 都對缺檔做了防護，
卡片會照常顯示名稱、價格、風格標籤，只是沒有圖。

## 選用：本機批次風格判定

只有要重跑六風格分類（`json_adjustment/reclassify_styles.py`）時才需要 Ollama：

```bash
brew install ollama && ollama serve
ollama pull qwen3:8b
```

全量 9,349 筆本機約 50 小時；改用 `--provider anthropic`（Haiku）約 30 分鐘、成本約 US$7。
**建議只在增量（50–200 筆）時用本機模型。**

---

## 常見問題

**`OSError: We couldn't connect to huggingface.co`** — 沒做步驟二。模型沒快取而
`HF_HUB_OFFLINE=1` 又擋住連線，用步驟二的指令先下載。

**`NotFoundError: Collection [furniture_v3] does not exist`** — 沒做步驟四。

**查詢回傳 0 筆** — 硬過濾條件疊太多。房型／類別／價格／尺寸是硬過濾，
風格與氛圍只是加權；把尺寸或價格條件放寬再試。

**重建索引時 UI 查不到東西** — `embed_v3.py` 是 `delete_collection` 後重建，
灌資料的期間 collection 是空的。**重建前先關掉 UI。**

**`ModuleNotFoundError`** — 用到系統 python 了，指令前面要加 `.venv-rag/bin/`。

---

更完整的架構、模型選擇與實測數據見 `docs/RAG檢索系統說明.md`；
需求解析器的 schema 與 prompt 見 `docs/query_parser_spec.md`。
