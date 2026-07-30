# RAG 家具風格檢索系統 — 系統說明

> 版本：v2（2026-07-27，六風格色卡改版）
> 對應實作：`rag_pipeline/`、`json_adjustment/build_rag_v3.py`
> 相關文件：`docs/query_parser_spec.md`（需求解析器規格）、`json_adjustment/RAGSQL.md`（SQL 交付規格）

---

## 1. 系統定位

**輸入家具風格或設計需求 → 從 9,349 件家具中找出最合適的物件。**

不做「能不能擺得下」的空間判斷——那是幾何與規則計算，不是檢索問題（若日後要做，
應寫成獨立的 `check_fit()` 函式由程式計算，不要讓 LLM 憑感覺算公分數）。

---

## 2. 架構

```
使用者輸入
   │
   │ ① query_parser.py ── claude-haiku-4-5 + structured outputs
   ▼                      自然語言 → 受控詞彙條件 ＋ HyDE 查詢文本（一次呼叫兩用）
{ room_type, styles, moods, items[], budget_total, needs_clarification… }
   │
   │ ② retriever.py
   ├── Chroma where 硬過濾   房型 / 類別群組 / 價格 / 尺寸 / role / size_class
   ├── bge-m3 向量檢索       top 50
   ├── bge-reranker-v2-m3    中文 cross-encoder 重排 top 20（配件品項 12）
   ├── 加權排序              style_compat + mood 命中 + confidence
   ├── set 層收斂            主導風格統一、跨品項 duplicate_group 去重
   └── 每品項 top 8
   ▼
   ③ app.py（Gradio）── 條件面板 + 追問按鈕 + 結果卡片（內嵌預渲染圖）
```

### 硬過濾 vs 軟加權的界線

| 條件 | 處理方式 | 理由 |
| :-- | :-- | :-- |
| `room_type` | **硬過濾** `room_<type> = true` | 客廳沙發不該回浴室物件 |
| `category_group` | **硬過濾** `category $in [...]` | 要沙發就不該回椅子 |
| 價格 / 尺寸 / role / size | **硬過濾** | 真實約束 |
| `styles` | **軟加權**（style_compat 6×6 矩陣） | 單一風格硬過濾後疊上房型與類別幾乎撈不到 |
| `moods` | **軟加權**（moods_flat 交集） | 24 詞是 VLM 主觀標的，硬過濾會誤殺 |
| 顏色 / 材質 / 圖樣 | **只進 semantic_query** | 顏色 317 種、材質 700+ 種（「木質腳架」「木製腳」是不同值），字串比對必敗 |

### 排序公式

```
final = 0.60 × rerank(0-1)
      + 0.20 × style_compat[主導風格][物件 style_primary]
      + 0.10 × (mood 命中數 / 使用者 mood 數)
      + 0.10 × item.confidence
```

權重定義在 `retriever.py` 的 `W_RERANK / W_STYLE / W_MOOD / W_CONF`。

---

## 3. 模型

| 用途 | 模型 | 設定 |
| :-- | :-- | :-- |
| 需求解析 | `claude-haiku-4-5` | structured outputs 強制 JSON schema；系統提示走 prompt caching |
| Embedding | `BAAI/bge-m3` | 1024 維、cosine、normalized、`max_seq_length=512` |
| Rerank | `BAAI/bge-reranker-v2-m3` | 中文 cross-encoder，**輸出已內建 sigmoid（0-1），不可再套一次** |

⚠️ **不要換成 `ms-marco-MiniLM`**（06-advanced-rag notebook 用的那顆）——那是英文模型，
套在中文資料上會比不 rerank 還糟。

---

## 3.5 LLM 供應商：混合方案

兩種工作的性質相反，所以分開配置：

| 工作 | 特性 | 供應商 | 理由 |
| :-- | :-- | :-- | :-- |
| **需求解析**（每次查詢 1 次） | 要即時、輸出長（~600 token）、規則細膩 | `claude-haiku-4-5` | 延遲是關鍵；每次僅 US$0.005 |
| **風格判定**（批次 9,350 次） | 不趕時間、輸出短（~80 token）、任務單純 | `qwen3:8b`（本機 Ollama） | 零 API 成本、不會跑到一半額度用盡 |

`reclassify_styles.py` 兩條路徑**共用同一份 prompt 與 JSON schema**，只有呼叫層不同：

```bash
python3 json_adjustment/reclassify_styles.py                      # 本機 Qwen3（預設）
python3 json_adjustment/reclassify_styles.py --provider anthropic # 切回 Haiku
python3 json_adjustment/reclassify_styles.py --compare 30         # 量一致率與速度
```

實作要點：
- Ollama 用 `format` 傳 JSON schema → llama.cpp 語法約束解碼，**JSON 保證合法**
- **`think: False` 是關鍵**——Qwen3 預設會先產一大段推理，token 量多 2–3 倍
- 併發自動調整（ollama 2／anthropic 12），每筆判定記錄 `provider` 供追溯

### 實測（M1 16 GB，以既有 9,350 筆 Haiku 判定為基準）

| 模型 | 風格一致率 | 色卡一致率 | 速度 | 全量 9,350 筆 |
| :-- | --: | --: | --: | --: |
| Qwen3 8B | **75%** | 60% | 19.5 秒/筆 | **50 小時** |
| Qwen3 4B | 60% | 47% | ~14 秒/筆 | 37 小時 |
| Haiku（基準） | — | — | 0.2 秒/筆 | 30 分鐘 |

**併發沒有幫助**：實測併發 4 反而更慢——M1 的瓶頸是記憶體頻寬，多執行緒只會互相搶。

### Qwen3 的系統性偏差

不一致的樣本不是隨機雜訊，有明確方向：

```
床架 Stone & Beam        modern_minimal → industrial
ZEN 手工編織黃麻地毯        scandinavian   → japanese
Rivet Woven Sisal 地毯    scandinavian   → japanese
```

Qwen3 傾向把**天然纖維（黃麻、劍麻、藤編）判成日式**、**深色木質判成工業風**。
若要提高一致率，可在 `reclassify_styles.py` 的「常見判別要點」補一條：
「天然纖維地毯（黃麻、劍麻、藤編）若色調偏米白仍屬 scandinavian」。

### 該怎麼用

| 場景 | 筆數 | Qwen3 耗時 | 建議 |
| :-- | --: | --: | :-- |
| 新增商品上架後補判 | 50–200 | 16–65 分鐘 | ✅ 本機，零成本 |
| 調風格定義前試水溫 | 30–50 | 10–16 分鐘 | ✅ 本機，免費試錯 |
| API 額度用完的備援 | 任意 | — | ✅ 本機，工作不中斷 |
| **全量重新判定** | 9,350 | 50 小時 | ❌ 用 Haiku（30 分鐘 / US$7） |

**不要用 Qwen3 重跑全量**——50 小時換來 25% 的標籤變動，且會改變已校準的風格分布。

---

## 4. 索引實測數據（2026-07-27）

| 項目 | 數值 |
| :-- | :-- |
| 來源 | `rag_dataset/furniture_enriched_v3.json`（**9,349 筆**，已排除 1 筆非家具） |
| 向量筆數 | **9,349（覆蓋率 100.00%）** |
| 唯一 ID / 重複 ID | 9,349 / **0** |
| 維度分布 | `{"1024": 9349}`（單一） |
| 模型分布 | `{"BAAI/bge-m3": 9349}`（單一） |
| 空向量 / 錯誤維度 / 失敗 | 0 / 0 / **0** |
| 編碼耗時 | **1,621 秒（27.0 分鐘）**，device = mps，5.8 筆/秒（六風格重建） |
| `chroma_db/` | 137 MB（該次建置；目錄現為 366 MB，含歷次 collection 殘留） |
| `rag_export/furniture_embeddings_bge_m3.jsonl` | 106 MB |

**已刪除的 1 筆**：`jp-armchairs-01-underl-tta-vacuum-flask-black-1-2-l`
（UNDERLÄTTA 保溫瓶 1.2 L，12.9×17.5×22.5 cm，被誤分類成「扶手椅」，`is_active=False`）。
排除邏輯寫在 `build_rag_v3.py`，每次重建都會印出被排除的品項；
v3 header 的 `excluded_items` 記錄明細，v1/v2 仍保留該筆供回溯。

**SQL 端驗收條件全數通過**：重複 ID = 0、空向量 = 0、維度單一、模型單一。

---

## 4.5 六風格色卡改版（2026-07-27）

風格詞表從舊的 12 風格改為 `taiwan_style_cards.json` 定義的 **6 風格 × 3 色卡**。

| 新風格 | 色卡 | 筆數 | 佔比 |
| :-- | :-- | --: | --: |
| modern_minimal 現代簡約 | 黑白俐落／暖灰質感／自然留白 | 4,113 | 44.0% |
| scandinavian 北歐風 | 自然木質／清新明亮／低彩度質感 | 2,178 | 23.3% |
| american 美式 | 鄉村溫馨／經典優雅／現代輕奢 | 1,868 | 20.0% |
| cream 奶油風 | 奶油米白／法式柔霧／奶茶木質 | 560 | 6.0% |
| industrial 工業風 | 黑鐵水泥／復古工坊／極簡冷調 | 450 | 4.8% |
| japanese 日式 | 侘寂自然／茶室禪意／現代和風 | 181 | 1.9% |

### 為什麼不能用映射表

舊 12 風格中有 6 個（mid_century 1,387、contemporary 869、scandi_luxe 428、rustic、boho、
french_country）在新分類找不到對應，佔全庫 **33.6%**；且**奶油風在舊資料完全不存在**，
純映射最多只能從 french_country 硬塞 127 筆（1.4%）。實際重新判定後奶油風有 560 筆。

### 判定方式：文字重判

`json_adjustment/reclassify_styles.py` 用 Haiku 讀每件既有的 80–120 字 VLM 描述
（本來就是看圖寫的，已含顏色材質線索）＋顏色＋材質，對照六風格定義與色票重新判定，
不重看渲染圖。判定同時回傳最接近的色卡。

- 已判定 **8,704 筆**（`style_source = text_reclassify_v2`），把握度中位 **0.85**，零筆低於 0.5
- 判定理由可見色票確實被使用：「米色香檳黃麻…色票接近清新明亮」「暖灰質感色票最佳匹配」
- 剩 **646 筆**因 API 額度耗盡未判定，暫用多數決映射（`style_source = legacy_majority_map`）

### 舊值保留與回溯

`style_primary_v1` / `style_secondary_v1` 保留舊的 12 風格值，`style_source` 標示判定來源。
判定出錯時可回溯比對，也不損失已付出的標註成本。

### 補完那 646 筆（儲值後）

```bash
.venv-rag/bin/python json_adjustment/reclassify_styles.py      # 續跑，約 2 分鐘
python3 json_adjustment/build_rag_v3.py
.venv-rag/bin/python rag_pipeline/embed_v3.py --only-changed   # 只重嵌變動的，約 2 分鐘
```

`--only-changed` 比對 v3 與 `rag_export` 的 `text_hash`，只重算變動者、其餘沿用舊向量——
不必再等 28 分鐘全量。

### 這次改版動到的檔案

| 檔案 | 變更 |
| :-- | :-- |
| `vlm_annotation/taxonomy_v2.json` | 新增：6 風格 + 18 色卡 + 6×6 相容矩陣 |
| `json_adjustment/build_taxonomy_v2.py` | 新增：由色卡生成 taxonomy（定義文字與相容度在此維護） |
| `json_adjustment/reclassify_styles.py` | 新增：六風格判定器（可續跑、併發、含成本統計） |
| `json_adjustment/build_rag_v3.py` | 併入新判定、舊值搬 `_v1`、色卡進 `embedded_text` |
| `rag_pipeline/embed_v3.py` | 新增 `--only-changed` 增量模式 |
| `query_parser.py` / `retriever.py` | 指向 taxonomy_v2；口語對映改六風格 + 色卡名 |
| `glb_annotation_pipeline.py` / `annotate_full.py` | 指向 taxonomy_v2；fallback 改 modern_minimal |

---

## 5. 建置過程實測抓到的五個問題

留下來當回歸清單——這些都是「看起來會動、實際結果錯」的類型。

| # | 問題 | 症狀 | 修法 |
| :-- | :-- | :-- | :-- |
| 1 | `rag_indexable` 寫進 Chroma `where` | 端到端查詢回 **0 筆** | 它是 v3 頂層欄位、不在 `chroma_metadata`；移除該條件（collection 本來就只收可索引的） |
| 2 | rerank 分數被 sigmoid 兩次 | 判別力歸零（0.984→0.728、0.0001→0.5） | CrossEncoder 已內建 sigmoid，輸出在 0-1 時直接使用 |
| 3 | 解析器憑空編造尺寸 | 只說「客廳沙發」卻填 `max_width_cm: 220`，硬過濾砍掉正確結果 | prompt 明令禁止推測尺寸，只有使用者明講才填 |
| 4 | `items` 回空陣列 | 只給風格不給類別時檢索端沒東西可跑 | 允許 `category_group = null`（跨類別檢索），並強制至少 1 個品項 |
| 5 | 可為 null 的 enum schema | API 回 400「Enum value does not match declared type」 | 不能用 `{"type":["string","null"],"enum":[...]}`，要用 `anyOf` 包一層 |

另有兩個 Gradio 6 API 變更：`theme` 從 `Blocks()` 移到 `launch()`、`show_api` 參數已移除。

---

## 6. 檢索品質抽驗（六風格版）

**輸入**：`奶油風的沙發`　→ 主導風格 cream

```
0.907  Stone & Beam Andover 沙發套座椅   cream  色卡:奶油米白  st=1.00  20,000
0.906  Stone & Beam Andover 沙發套座椅   cream  色卡:奶油米白  st=1.00  20,000
0.901  Movian 沙發                      cream  色卡:奶油米白  st=1.00  20,000
```

**輸入**：`侘寂自然色卡的櫃體`　→ 主導風格 japanese

```
0.918  LEDAMOT 收納櫃，淺灰米色           japanese      色卡:侘寂自然  st=1.00   5,000
0.917  FRYKSÅS 收納櫃，藤                japanese      色卡:侘寂自然  st=1.00   5,000
0.860  BESTÅ Shelf unit 附門，白色       scandinavian  色卡:自然木質  st=0.90   9,000
```

相同風格拿滿分排最前、相容風格（日式↔北歐 0.90）跟上——`style_compat` 加權如預期運作。

**多物件**：`北歐風溫馨感的客廳，幫我配一整組，預算十萬`
→ 6 個品項，預算依各群組中位價分配（合計 130,000 = 10 萬 × 1.3 寬容係數）：
主沙發 57,706／單椅 28,212（建議加入）／淺木茶几 14,426／淺色地毯 13,785／
床邊桌 9,778（建議加入）／落地燈 6,091

---

## 7. UI（Gradio）

- 網址：`http://127.0.0.1:7860`
- 啟動時預熱 bge-m3 / reranker / Chroma，避免第一次查詢乾等一分鐘
- 結果卡片的預渲染圖轉成 240px 縮圖再 base64 內嵌，不必設定 Gradio 靜態檔授權路徑
- `needs_clarification` 時**照樣先給結果**，追問以提示條 + 快速選項按鈕呈現，點按鈕併入原句重跑
- 卡片標示：`分類已修正`（865 筆 category_conflict）、`建議加入`（系統推論的品項）

單次查詢延遲約 3–6 秒（Haiku 解析 1–2 秒 + 向量檢索與 rerank）。

---

## 8. 已知限制

1. **多物件推論偶爾夾帶不合適品項**——例如客廳組合推出「床邊桌」。已標「建議加入」且仍受房型過濾，
   要更準需在 prompt 的房型典型組合表加負面約束。
2. **ABO 來源的 `name_zh` 有法文/義大利文殘留**（「Canapé convertible」）——v1 就有的來源資料問題，
   不影響檢索（檢索靠 VLM 寫的中文描述），只影響卡片顯示。
3. **重複商品只靠 `duplicate_group` 去重**（177 筆有標）——同款不同色若沒被標到群組仍可能並列。
4. **rerank 在 CPU 上較慢**——目前走 MPS；若換機器沒有 GPU/MPS，可先關掉 rerank 只用加權排序。
5. **尚未做擺設可行性判斷**——本系統只解決「找到合適物件」。

---

## 9. 維運

```bash
PY=.venv-rag/bin/python

# 重建索引（資料集有更新時）
python3 json_adjustment/build_rag_v3.py && $PY rag_pipeline/embed_v3.py

# 只重跑向量、不動 Chroma（例如只想更新交付檔）
$PY rag_pipeline/embed_v3.py --skip-chroma

# 換裝置（MPS 出問題時）
$PY rag_pipeline/embed_v3.py --device cpu

# 啟動 / 重啟 UI
$PY rag_pipeline/app.py
```

**判斷要不要重算向量**：比對 v3 的 `text_hash` 與 `rag_export/furniture_embeddings_bge_m3.jsonl`
同一 `furniture_id` 的 `text_hash`，不一致者才需重算——這正是 `text_hash` 存在的理由。

調權重不需重建索引，改 `retriever.py` 頂部的 `W_*` 常數即可；
改分類群組改 `rag_pipeline/category_groups.json`，不用動 prompt。
