# RAG 家具資料集與風格檢索系統

把 9,350 件家具（IKEA + ABO）的渲染圖，經 VLM 加值成結構化資料集，再建成
**「輸入家具風格／設計 → 找出合適物件」** 的語意檢索系統。

```
渲染圖 ──VLM標註──▶ v2 資料集 ──加工──▶ v3（RAG-ready）──bge-m3──▶ ChromaDB ──▶ Gradio UI
                                            └──────────────────────▶ rag_export/（交接 SQL）
```

| 階段 | 產出 | 狀態 |
| :-- | :-- | :-- |
| ① 資料加值 | `rag_dataset/furniture_enriched_v2.json`（9,350 筆） | ✅ |
| ② RAG 加工 | `rag_dataset/furniture_enriched_v3.json`（**9,349 筆**，49.9 MB） | ✅ |
| ③ 建索引 | `chroma_db/`（9,349 筆向量） | ✅ **覆蓋率 100%** |
| ④ 檢索與 UI | `rag_pipeline/`（解析 → 檢索 → Gradio `:7860`） | ✅ |
| ⑤ 交接 SQL | `rag_export/` 四個檔（規格見 `json_adjustment/RAGSQL.md`） | ✅ |

> **風格分類**：使用 **6 風格 × 3 色卡**（北歐風／日式／現代簡約／奶油風／工業風／美式），
> 全數由 LLM 依色卡定義重新判定；舊的 12 風格值保留在 `style_primary_v1`。
>
> **LLM 混合方案**：互動的需求解析用 `claude-haiku-4-5`（延遲 1–2 秒）；
> 批次的風格判定預設用本機 `qwen3:8b`（零 API 成本）。詳見第七節。

詳細說明：**`docs/RAG檢索系統說明.md`**（架構、模型、排序公式、實測數據、六風格改版、已知限制）
與 **`docs/query_parser_spec.md`**（需求解析器規格）。

---

## 一、資料夾功能一覽

| 資料夾 | 大小 | 功能 | 動到它的時機 |
| :-- | --: | :-- | :-- |
| **`rendering/`** | 2.0 GB | **影像來源**。9,350 張預渲染 PNG（**只剩正面視角**）＋ 由 GLB 產圖的工具。VLM 標註與 UI 卡片縮圖都取自這裡 | 新增 GLB 商品時 |
| **`vlm_annotation/`** | 16 MB | **標註與詞表**。VLM 看圖標註的全套腳本、風格／氛圍／類別詞表（taxonomy）、標註進度檔 | 重跑標註、改風格詞表 |
| **`json_adjustment/`** | 20 MB | **資料加工層**。v2→v3 加工、色卡→taxonomy、風格重新判定、SQL 交付規格書 | 改欄位、改風格分類 |
| **`rag_dataset/`** | 79 MB | **三代資料集**。v1 原始 → v2 標註完成 → v3 RAG-ready | 每次加工後 |
| **`rag_pipeline/`** | 148 KB | **檢索系統本體**。需求解析 → 兩階段檢索 → Gradio UI | 調權重、改介面 |
| **`chroma_db/`** | 366 MB | **向量庫**。9,349 筆 1024 維向量 + 攤平後的過濾用 metadata | 由 `embed_v3.py` 自動重建 |
| **`rag_export/`** | 146 MB | **交接 SQL 的交付檔**。向量 jsonl + 規格 + 失敗清單 + 驗證報告（＋官方分類版） | 交付給 SQL 負責人 |
| **`docs/`** | 28 KB | **系統文件**。架構說明、解析器規格、標註 pipeline 執行說明 | 隨開發同步 |
| **`.venv-rag/`** | 1.5 GB | **唯一的執行環境**（Python 3.11.15） | 跑 `rag_pipeline/`、`json_adjustment/` |

> ⚠️ **`.venv/`（Python 3.9，渲染與 VLM 標註環境）已不存在**，`rendering/` 與 `vlm_annotation/`
> 的腳本目前沒有可用環境；要重跑標註需先重建（見第八節）。現行檢索流程不受影響。
>
> ⚠️ **45 度視角的渲染圖已刪除**，只保留正面圖。`render_meta_full.jsonl` 每筆的第二個
> `images` 路徑（`45度(abo)` / `45度(ikea)`）目前**指向不存在的檔案**——重跑
> `annotate_full.py annotate` 前必須先重新產圖，或改為單視角標註。

**專案外的相依**（不在此資料夾但必要）：

| 位置 | 大小 | 內容 |
| :-- | --: | :-- |
| `~/.cache/huggingface` | ~9 GB | `bge-m3`（嵌入）、`bge-reranker-v2-m3`（重排） |
| `~/.ollama/models` | ~7.7 GB | `qwen3:8b`（5.2 GB）、`qwen3:4b`（2.5 GB） |

### 各資料夾內的關鍵檔案

```
rendering/
├── render_abo.py                 由 GLB 渲染正面/45 度兩視角（未來新增 GLB 用）
└── output/ikea & abo/            預渲染 PNG 9,350 張，只剩正面（IKEA 2,612＋ABO 6,738）

vlm_annotation/
├── glb_annotation_pipeline.py    VLM 標註共用函式庫（build_prompt / call_vlm）
├── build_render_meta_full.py     掃描 PNG → id 對照表
├── annotate_full.py              全量 VLM 標註 + merge 進 v2（可續跑）
├── supplement_from_export.py     從既有匯出補 RAG 欄位進 v2
├── taxonomy_v2.json          ★  6 風格 × 3 色卡 + 6×6 相容矩陣 + 24 氛圍 + 64 類別對照
├── taxonomy_v1.json              舊 12 風格（保留供回溯）
├── style_v2_annotations.jsonl ★  六風格判定結果 9,350 筆（可續跑）
├── render_meta_full.jsonl        id → [正面, 45度] 圖檔路徑（★45 度那筆已失效，見上方警告）
└── annotations_full.jsonl        VLM 標註進度檔

json_adjustment/
├── RAGSQL.md                     SQL 負責人給的交付規格（四個交付檔的定義）
├── build_taxonomy_v2.py          色卡 → taxonomy_v2（★風格定義與相容度在此維護）
├── reclassify_styles.py      ★  六風格判定器（Qwen3／Haiku 雙供應商、可續跑、可比對）
├── build_rag_v3.py           ★  v2 → v3 加工（embedded_text / text_hash / chroma_metadata）
└── furniture_official_catagory.json   官方分類版（內容與 v2 相同，僅供對照）

rag_dataset/
├── furniture_enriched_v1.json    原始 items（未標註）
├── furniture_enriched_v2.json    VLM 標註完成（9,350 筆）— 標註血統的主檔
└── furniture_enriched_v3.json ★  RAG-ready（9,349 筆，49.9 MB）— 索引與交付的唯一來源

rag_pipeline/
├── category_groups.json          64 細類 → 19 檢索群組 + 各房型典型組合
├── embed_v3.py                   v3 → bge-m3 向量 → Chroma + rag_export（支援 --only-changed）
├── query_parser.py               需求解析（Haiku + structured outputs）
├── retriever.py                  硬過濾 → 向量 → rerank → 風格加權 → 去重
├── app.py                        Gradio UI
└── README.md                     管線操作手冊

rag_export/                       ★ 交接 SQL（規格見 RAGSQL.md）
├── furniture_embeddings_bge_m3.jsonl   9,349 筆向量（106 MB）
├── embedding_metadata.json       批次規格（模型／維度／distance_metric／normalized）
├── embedding_failures.jsonl      失敗清單（目前 0 筆，檔案為空）
├── embedding_validation_report.json  覆蓋率 100%、重複 ID 0、空向量 0
└── furniture_official_catagory.json   官方分類版（34 MB，非 RAGSQL 交付規格內的檔）

docs/
├── RAG檢索系統說明.md         ★  系統總說明（架構、模型、實測、六風格改版、限制）
├── query_parser_spec.md      ★  需求解析器規格（schema、prompt、實測案例）
└── GLB標註pipeline執行說明.md    VLM 標註流程說明
```

> ⚠️ **兩個來源檔已不在專案內**：`taiwan_style_cards.json`（色卡定義）與
> `all_furniture_vlm_responses_.json`（VLM 匯出）。內容已分別固化進
> `taxonomy_v2.json` 與 `furniture_enriched_v2.json`，**現行流程不受影響**，
> 但 `build_taxonomy_v2.py` 與 `supplement_from_export.py` 若要重跑需先放回來源檔。

---

## 二、資料加值（階段 ①）

1. **補充缺少的資訊** — 原始 v1 有 906 筆缺 `colors`、且絕大多數缺外觀標註。
2. **增加資訊欄位** — 讓檢索能依風格、氛圍、材質、關鍵字命中，而非只靠名稱。
3. **透過 VLM 辨識樣式** — Claude 視覺模型「看」預渲染圖，判斷風格、圖樣、顏色、材質，產出 80–120 字中文描述。
4. **渲染（技術前提）** — VLM 看不到 3D 模型，需先有渲染圖。

```
rendering/output/ikea & abo/  (9,350 張 PNG，標註當時尚有 45 度圖)
        │ build_render_meta_full.py   建 id→[正面,45度] 對照表
        ▼
render_meta_full.jsonl
        │ annotate_full.py annotate   VLM 受控標註
        ▼
annotations_full.jsonl
        │ annotate_full.py merge      併入主資料集
        ▼
furniture_enriched_v2.json  ◀── supplement_from_export.py  補 RAG 欄位
```

---

## 三、RAG 加工：v2 → v3（階段 ②）

`json_adjustment/build_rag_v3.py` 依 `RAGSQL.md` 的交付規格加工。**只增不覆寫**：
v2 既有欄位原封不動，v3 只新增衍生欄位。

| 新增欄位 | 內容 | 為什麼需要 |
| :-- | :-- | :-- |
| `embedded_text` | 固定欄位順序組出的中文文本（中位 334 字） | embedding 的唯一輸入來源 |
| `text_hash` | `sha256(embedded_text)` | 判斷要不要重算向量（9,349 筆零碰撞） |
| `chroma_metadata` | 純量化的過濾欄位 + 9 個 `room_*` 布林 | Chroma metadata 只吃 str/int/float/bool，list 必須攤平 |
| `category_final` / `category_conflict` | 865 筆 `name_category_conflict` 改用 `suggested_category` | 例：id 是 bed-frames、分類寫「抽屜櫃」的已修正為「床」 |
| `style_primary` / `style_card` / `style_palette_hex` | 六風格判定結果與對應色卡 | 色卡名也是檢索訊號（可直接搜「奶茶木質」） |
| `style_primary_v1` / `style_source` | 舊 12 風格值與判定來源 | 判定出錯可回溯，不損失既有標註成本 |
| `rag_text` 補漏 | 150 筆原本為空者以既有欄位組回 | 不補就會少掉檢索文本 |

**排除規則**：`rag_indexable = false` 者直接不進 v3（目前 1 筆——被誤分類成「扶手椅」的
UNDERLÄTTA 保溫瓶）。明細記在 v3 header 的 `excluded_items`，v1/v2 仍保留該筆供回溯。

⚠️ **`rag_indexable` 不在 `chroma_metadata` 裡**（它是頂層欄位）。寫進 Chroma 的 `where`
會命中 0 筆——collection 本來就只收可索引的品項。

---

## 四、檢索系統（階段 ③④）

```
使用者輸入「奶油風的沙發，預算三萬內」
   │
   │ query_parser.py    claude-haiku-4-5 + structured outputs
   ▼                    自然語言 → 受控詞彙條件 + HyDE 查詢文本（一次呼叫兩用）
{ room_type, styles, moods, items[], budget… }
   │
   │ retriever.py
   ├─ Chroma where 硬過濾（房型 / 類別 / 價格 / 尺寸）
   ├─ bge-m3 向量檢索 top 50
   ├─ bge-reranker-v2-m3 重排
   ├─ style_compat 風格加權 + mood 命中加權
   └─ 跨品項去重（duplicate_group）
   ▼
每品項 top 8 → app.py（Gradio，卡片帶預渲染圖）
```

**風格是軟加權不是硬過濾**：單一風格硬過濾後，疊上房型與類別可能只剩個位數；
`taxonomy_v2.json` 的 6×6 `style_compat`（japanese↔scandinavian 0.9、cream↔american 0.7）
讓相容風格也進得來。

排序公式（權重在 `retriever.py` 頂部）：
```
final = 0.60 × rerank + 0.20 × style_compat + 0.10 × mood 命中率 + 0.10 × confidence
```

---

## 五、執行流程

### A. 資料集（已完成，除非要重跑標註）

> ⚠️ **這段目前跑不動**：`.venv/`（Python 3.9）已不存在、45 度渲染圖已刪除。
> 要重跑標註得先補齊兩者（重建 venv：見第八節；補圖：`rendering/render_abo.py`），
> 或改為單視角標註。**現行檢索流程與此無關，不受影響。**

```bash
PY=.venv/bin/python                                 # ← 此環境已不存在，需先重建
export ANTHROPIC_API_KEY="$(tr -d '\n' < .anthropic_key)"

$PY vlm_annotation/build_render_meta_full.py        # 掃描 PNG → 對照表
$PY vlm_annotation/annotate_full.py annotate        # 全量 VLM 標註（可續跑）
$PY vlm_annotation/annotate_full.py merge           # → v2
$PY vlm_annotation/supplement_from_export.py        # → v2 補 RAG 欄位
```

### B. 風格分類（只在改風格定義時才需要）

```bash
python3 json_adjustment/build_taxonomy_v2.py                     # 色卡 → taxonomy_v2
PY=.venv-rag/bin/python
$PY json_adjustment/reclassify_styles.py --compare 30            # 先比對一致率
$PY json_adjustment/reclassify_styles.py                         # 本機 Qwen3（零成本）
$PY json_adjustment/reclassify_styles.py --provider anthropic    # 或用 Haiku（快 60 倍）
```

### C. 加工與建索引

```bash
python3 json_adjustment/build_rag_v3.py             # v2 → v3（--dry-run 只看統計）

PY=.venv-rag/bin/python
$PY rag_pipeline/embed_v3.py --limit 50             # 冒煙測試
$PY rag_pipeline/embed_v3.py                        # 全量（27 分鐘）
$PY rag_pipeline/embed_v3.py --only-changed         # 增量（只重算 text_hash 變動者）
```

### D. 檢索與 UI

```bash
PY=.venv-rag/bin/python
$PY rag_pipeline/query_parser.py "奶油風的沙發，預算三萬內"    # 只看解析
$PY rag_pipeline/retriever.py   "侘寂自然色卡的收納櫃"        # 命令列檢索
$PY rag_pipeline/app.py                                     # UI → http://127.0.0.1:7860
```

---

## 六、資料欄位字典

### 風格與標註欄位（taxonomy 受控）

| 欄位 | 說明 | 取值 |
| :-- | :-- | :-- |
| `style_primary` / `style_secondary` | 主/次風格 | **6 選 1**（scandinavian / japanese / modern_minimal / cream / industrial / american） |
| `style_card` / `style_card_id` | 對應色卡 | 18 張色卡之一（如「侘寂自然」） |
| `style_palette_hex` | 色卡色票 | 3 個 hex |
| `style_primary_v1` | 舊 12 風格值 | 保留供回溯 |
| `style_source` | 判定來源 | `text_reclassify_v2` |
| `pattern` | 表面圖樣 | 素色 / 木紋 / 幾何 / 花紋 |
| `mood_tags` | 氛圍標籤 | 24 詞選最多 3 |
| `description` | 外觀描述 | 80–120 字繁中 |
| `confidence` / `desc_source` | 把握度 / 描述來源 | 0–1 / `glb_render` |

### RAG 檢索欄位

| 欄位 | 說明 |
| :-- | :-- |
| `rag_text` | 檢索文本（描述句 / 特徵句 / 關鍵字） |
| `search_keywords` / `features` / `shape_tags` / `object_type_zh` | 關鍵字、細部特徵、造型、物件類型 |
| `embedded_text` / `text_hash` | 送進 embedding 的正規文本與指紋 |

### 被「補齊」的既有欄位

`colors` / `materials`：原本為空或佔位符時填入 VLM 實際看到的值。
尺寸 / 價格 / 房型 / `name_zh` 等既有可信欄位**不被覆寫**。

---

## 七、LLM 與模型配置（混合方案）

| 用途 | 模型 | 位置 | 理由 |
| :-- | :-- | :-- | :-- |
| **需求解析**（每次查詢） | `claude-haiku-4-5` | 雲端 API | 延遲是關鍵；1–2 秒 vs 本機 20 秒 |
| **風格判定**（批次） | `qwen3:8b` | 本機 Ollama | 零成本、不會跑到一半額度用盡 |
| **VLM 標註**（批次） | `claude-haiku-4-5` | 雲端 API | 需要視覺能力 |
| 嵌入 | `BAAI/bge-m3` | 本機 | 1024 維、cosine、normalized |
| 重排 | `BAAI/bge-reranker-v2-m3` | 本機 | 中文 cross-encoder |

**成本結構**：需求解析每次約 US$0.005（1,000 次查詢 ≈ US$5）；風格判定全量約 US$7。
真正會燒額度的是批次工作，所以批次端才改本機。

**實測（M1 16 GB，以既有 Haiku 判定為基準）**：

| 模型 | 風格一致率 | 速度 | 全量 9,350 筆 |
| :-- | --: | --: | --: |
| Qwen3 8B | 75% | 19.5 秒/筆 | 50 小時 |
| Qwen3 4B | 60% | ~14 秒/筆 | 37 小時 |
| Haiku | 基準 | 0.2 秒/筆（併發 12） | 30 分鐘 |

**結論：本機模型適合增量批次（50–200 筆＝16–65 分鐘），不適合全量重跑。**
併發沒有幫助——M1 的瓶頸是記憶體頻寬，多開執行緒只會互相搶。

---

## 八、環境需求

| 環境 | Python | 狀態 | 用途 | 主要套件 |
| :-- | :-- | :-- | :-- | :-- |
| `.venv-rag/` | 3.11.15 | ✅ 現役 | 檢索系統與資料加工 | torch、sentence-transformers、chromadb 1.5.9、gradio 6.20.0、anthropic、requests |
| `.venv/` | 3.9 | ❌ **已不存在** | 渲染與 VLM 標註 | 需重建：trimesh、pyrender、pillow、numpy、anthropic |

重建渲染／標註環境（僅在要重跑 `rendering/`、`vlm_annotation/` 時才需要）：

```bash
python3.9 -m venv .venv     # macOS 上 pyrender 須用預設 pyglet 後端，見第九節
.venv/bin/pip install trimesh pyrender pillow numpy anthropic
```

- **Ollama**：`brew install ollama` → `ollama serve` → `ollama pull qwen3:8b`
- **金鑰**：`.anthropic_key`（純文字）。已列入 `.gitignore`，**務必勿提交**
- **硬體**：本機為 Apple M1 / 16 GB；UI 執行時 bge-m3 + reranker 常駐約 4.6 GB

---

## 九、設計要點

- **成本控制**：標註與判定都用 Haiku（非 Opus）；批次工作可改本機 Qwen3
- **enum 正規化**：VLM 有時把風格附中文註（如 `minimalist(極簡風)`），比對前先去括號
- **只補不覆寫**：合併標註時既有可信欄位一律保留；就地寫入前先備份
- **灰模判定**：預渲染是灰底真實貼圖，無法用色度區分「無貼圖灰模」與「本來就是灰的家具」，故一律送圖由 VLM 判斷
- **macOS 渲染**：`pyrender` 用預設 pyglet 後端（勿設 `PYOPENGL_PLATFORM=egl/osmesa`，會 ImportError）
- **向量與交付檔同批產出**：`embed_v3.py` 一次算向量、同時寫 Chroma 與 `rag_export/`，
  保證 demo 與 SQL 端是同一批向量、同一個 `text_hash`
- **增量重嵌**：`--only-changed` 比對 `text_hash`，實測 646 筆變動只花 1.5 分鐘（全量 27 分鐘）

> 完整的「GLB → VLM 標註」技術要點另見個人 skill：`annotating-glb-furniture-with-vlm`。
