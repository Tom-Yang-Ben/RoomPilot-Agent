# RoomPilot 專案事實簡報（配置改寫的唯一事實來源 / SSOT）

> 本檔是把通用模板 `.claude/` 改寫為本專案專用配置 `.claude-roompilot/` 時的**唯一事實來源**。
> 改寫鐵律：所有範例、指令、路徑、技術棧引用都必須符合本檔；
> **不得保留 npm / Node / React / TypeScript / Go / Rust / Docker / Kubernetes** 等本專案沒有的技術。
> 本檔事實已於 2026-07-28 對照實際程式碼與環境驗證（含修正 README 的過時敘述）。

## 專案定位

**RoomPilot 家具風格檢索系統**——輸入自然語言的家具風格／設計需求，
從 9,349 件家具中檢索最合適的物件。純檢索系統（R 沒有 G），
結果直接呈現於 Gradio UI 卡片，**無 LLM 生成端**。

## 技術棧（唯一允許引用的）

| 項目 | 值（已驗證） |
| :--- | :--- |
| 語言 | Python **3.11.15**（唯一環境 `.venv-rag/`，執行方式 `.venv-rag/bin/python`） |
| UI | **Gradio 6.20.0**（`rag_pipeline/app.py`，`127.0.0.1:7860`；Gradio 6 的 theme 在 `launch()` 傳） |
| 向量庫 | **ChromaDB 1.5.9**（`chroma_db/`，collection **`furniture_v3`**，cosine，9,349 筆） |
| Embedding | `BAAI/bge-m3`（1024 維、normalized、`MAX_SEQ_LEN=512`） |
| Rerank | `BAAI/bge-reranker-v2-m3`（中文 cross-encoder，經 CrossEncoder 已內建 sigmoid，輸出即 0–1） |
| 需求解析 LLM | `claude-haiku-4-5`（structured outputs + prompt caching；金鑰於 `.anthropic_key` 或 `ANTHROPIC_API_KEY`） |
| 批次風格判定 | 本機 Ollama `qwen3:8b`（`json_adjustment/reclassify_styles.py`，可 `--provider anthropic` 切 Haiku） |
| VLM 標註 | `claude-haiku-4-5`（`vlm_annotation/`，批次、可續跑） |
| 圖片 | PIL 縮圖 + base64 內嵌；渲染圖在 `rendering/output/…/正面(abo\|ikea)/` |
| 測試框架 | **目前無正式測試套件**（改寫測試/TDD 配置時，以 **pytest** 為預設建議，並標明「尚未建置」） |
| CI／部署 | **無 CI、無 Docker**；本機 macOS（Apple Silicon，MPS 優先退 CPU）執行 |
| 版本控制 | **目前不是 git repo**（改寫 git 相關配置時保留流程，但標明「專案尚未 git init」） |
| Shell | zsh（hook / statusline 腳本用 bash，僅需 macOS 版） |

### ⚠️ 與根 README 不符、以本檔為準的事實

1. **`.venv/`（Python 3.9，渲染與 VLM 標註環境）目前不存在**，專案內只有 `.venv-rag/`。
   `rendering/` 與 `vlm_annotation/` 的腳本現階段沒有可用環境，重跑前需先重建。
   → 任何配置檔**不得**再寫 `PY=.venv/bin/python`，一律用 `.venv-rag/bin/python`。
2. 兩個上游來源檔已不在專案內：`taiwan_style_cards.json`、`all_furniture_vlm_responses_.json`。
   內容已固化進 `taxonomy_v2.json` 與 `furniture_enriched_v2.json`，現行流程不受影響。
3. **45 度渲染圖已刪除**：`rendering/` 只剩正面圖 9,350 張（IKEA 2,612＋ABO 6,738）。
   `render_meta_full.jsonl` 每筆 `images` 的第二個路徑（`45度(abo)` / `45度(ikea)`）指向不存在的檔案，
   重跑 VLM 標註前必須先補產圖或改單視角。檢索流程不受影響。
4. **交付檔名與契約不符**：`json_adjustment/RAGSQL.md`（SQL 端契約）要求 `furniture_embeddings.jsonl`，
   `embed_v3.py:37` 實際輸出 `furniture_embeddings_bge_m3.jsonl`。交付前需與 SQL 端確認，勿逕自改名。

## 目錄結構（實際）

```
RAG/
├── rag_pipeline/          # 核心管線（唯一的「應用程式」）
│   ├── app.py             # Gradio UI（預熱模型、卡片呈現、追問按鈕）
│   ├── query_parser.py    # Haiku 需求解析（受控詞彙 + HyDE，一次呼叫兩用）
│   ├── retriever.py       # 兩階段檢索（硬過濾→向量→rerank→加權→去重收斂）
│   ├── embed_v3.py        # 索引建置（bge-m3 → Chroma + rag_export/ 四個交付檔）
│   ├── category_groups.json  # 64 細類 → 19 檢索群組 + 房型典型組合
│   └── README.md          # 管線操作手冊
├── rag_dataset/           # furniture_enriched_v1/v2/v3.json（v3 為現役，9,349 筆）
├── rag_export/            # SQL 端交付檔（向量 jsonl、metadata、失敗清單、驗證報告）
├── json_adjustment/       # 資料建置腳本 + 交付規格（RAGSQL.md、i_need_rag.md）
├── vlm_annotation/        # taxonomy_v2.json（六風格詞表 + 6×6 相容矩陣）、標註腳本
├── rendering/             # 預渲染 PNG（正面圖為 UI 卡片用）
├── chroma_db/             # 向量索引
├── docs/                  # RAG檢索系統說明.md、query_parser_spec.md、GLB標註說明
└── README.md
```

## 常用指令（改寫 commands / rules / agents 時一律引用這些）

```bash
PY=.venv-rag/bin/python
$PY rag_pipeline/embed_v3.py                 # 全量建索引（約 27 分鐘）
$PY rag_pipeline/embed_v3.py --limit 50      # 冒煙測試
$PY rag_pipeline/embed_v3.py --only-changed  # 增量（text_hash 比對，646 筆約 1.5 分鐘）
$PY rag_pipeline/query_parser.py "<需求>"    # 單測需求解析
$PY rag_pipeline/retriever.py   "<需求>"     # CLI 完整檢索
$PY rag_pipeline/app.py                      # 啟動 UI → http://127.0.0.1:7860

python3 json_adjustment/build_rag_v3.py --dry-run   # v2→v3 加工（先看統計）
$PY json_adjustment/reclassify_styles.py --compare 30   # 六風格判定一致率比對
```

## 架構模組（專題架構圖命名）

Advanced RAG：
Query Understanding → Query Rewriting（與前者同一次 Haiku 呼叫）→
Metadata Filtering（Chroma `where` 硬過濾）→ Vector Retrieval（bge-m3，`VEC_TOP_K=50`）→
Re-ranking（cross-encoder，`RERANK_TOP_K=20`／配件 `RERANK_TOP_K_LIGHT=12`）→
Budget Allocation（中位價比例分配）→ Set Composition（主導風格收斂、去重）→
Result Presenter（Gradio，`FINAL_TOP_K=8`）

排序公式（權重定義在 `rag_pipeline/retriever.py:47`）：
```
final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence
```

## 領域詞彙

- **六風格**：`scandinavian` / `japanese` / `modern_minimal` / `cream` / `industrial` / `american`
  （`taxonomy_v2.json` 內含 6×6 `style_compat` 相容矩陣，如 japanese↔scandinavian 0.9、cream↔american 0.7）
- 18 張色卡（如「侘寂自然」）、24 個氛圍詞、9 種房型、64 細類 → 19 檢索群組
- **群組數／細類數一律以 `rag_pipeline/category_groups.json` 為準**，任何文件不得自行記憶數字。
  改動後用下列指令重新確認，並同步全部引用處：

  ```bash
  .venv-rag/bin/python -c "import json; g=json.load(open('rag_pipeline/category_groups.json'))['groups']; print(len(g))"   # → 19
  .venv-rag/bin/python -c "import json; print(len(json.load(open('vlm_annotation/taxonomy_v2.json'))['category_map']))"     # → 64
  ```

- **硬過濾 vs 軟加權界線**：房型／類別／價格／尺寸 = **硬過濾**；風格／氛圍 = **軟加權**；
  顏色／材質 = **只進 `semantic_query`**，不做過濾

## SSOT 文件（文件為契約）

程式改動必須同步以下文件；規格衝突時**以文件為準**：

- `docs/RAG檢索系統說明.md`、`docs/query_parser_spec.md`、`docs/GLB標註pipeline執行說明.md`
- `rag_pipeline/README.md`、專案根 `README.md`
- `vlm_annotation/taxonomy_v2.json`（六風格詞表 + 相容矩陣）
- `rag_pipeline/category_groups.json`（64 細類 → 19 檢索群組 + 房型典型組合）
- `json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md`（SQL 端交付規格）

## 六個坑（改動相關程式前必須確認）

1. **`rag_indexable` 不能寫進 Chroma `where`** — 它是頂層欄位、不在 `chroma_metadata` 裡，寫了會命中 0 筆
2. **rerank 分數不可再套 sigmoid** — `bge-reranker-v2-m3` 經 CrossEncoder 已輸出 0–1
3. **structured outputs 可為 null 的 enum 要用 `anyOf`** — 直接寫 type 陣列會 400
4. **HF Hub 未登入被限流會卡數分鐘** → 程式已 `setdefault("HF_HUB_OFFLINE", "1")`，勿移除
5. **尺寸是硬過濾，LLM 不得用常識推測** — 猜錯會直接濾掉正確結果
6. **勿把 reranker 換成 ms-marco MiniLM** — 英文模型，中文查詢會劣化

## 環境事實

- macOS（Darwin 24.5）、Apple Silicon 16 GB；device 優先 MPS 退 CPU
- UI 執行時 bge-m3 + reranker 常駐約 4.6 GB
- 沒有 Windows／Linux 需求：statusline 只需 macOS bash 版（`statusline-linux.sh`、`statusline-go.exe` 已捨棄）
- 金鑰 `.anthropic_key` 為純文字檔、已列入 `.gitignore`，**絕不可提交或回顯內容**
- 成本結構：需求解析每次約 US$0.005；風格判定全量約 US$7。會燒額度的是批次工作
