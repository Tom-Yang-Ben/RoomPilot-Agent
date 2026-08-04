# 家具 VLM 標註 Pipeline — 執行說明（Runbook）

> 目錄結構、資料流、欄位字典、設計要點請見專案根的 [`README.md`](../README.md)。
> 本文聚焦「怎麼跑、怎麼續跑、怎麼驗收、成本與限制」。

## 一、環境準備

專案自帶 venv：`.venv/`（Python 3.9），已裝 `trimesh` `pyrender` `pillow` `numpy` `anthropic` `gdown`。

API key 放在專案根的 `.anthropic_key`。執行標註前以環境變數帶入：

```bash
export ANTHROPIC_API_KEY="$(tr -d '\n' < .anthropic_key)"   # macOS / Linux
```

> ⚠️ 勿把金鑰明文寫進任何文件或程式碼；`.anthropic_key` 已列入 `.gitignore`。

## 二、全量流程（9,350 件，現行）

> ⚠️ **本流程目前無法直接執行**，有兩個前提已不成立：
> 1. **`.venv/`（Python 3.9）已不存在** — 需先重建：
>    `python3.9 -m venv .venv && .venv/bin/pip install trimesh pyrender pillow numpy anthropic`
> 2. **45 度渲染圖已刪除**，`rendering/` 只剩正面圖（9,350 張）。
>    `render_meta_full.jsonl` 每筆 `images` 的第二個路徑指向不存在的檔案，
>    重跑步驟 2 會讀圖失敗 — 需先用 `rendering/render_abo.py` 補產 45 度圖，或改為單視角標註。
>
> 既有標註成果（`furniture_enriched_v2.json`、`style_v2_annotations.jsonl`）已固化，
> **檢索流程不受影響**。

在專案根執行，`PY=.venv/bin/python`：

```bash
# 1. 建對照表：掃描 rendering/output/ikea & abo/ 的預渲染 PNG → id→[正面,45度]
$PY vlm_annotation/build_render_meta_full.py

# 2. VLM 標註（先抽 20 件試跑看品質，再全量）
$PY vlm_annotation/annotate_full.py annotate --sample 20
$PY vlm_annotation/annotate_full.py annotate           # 全量（可續跑，建議背景執行）

# 3. 併入主資料集 → rag_dataset/furniture_enriched_v2.json（先備份）
$PY vlm_annotation/annotate_full.py merge

# 4. 從既有匯出補 RAG 欄位（rag_text / search_keywords / features / shape_tags / object_type）
$PY vlm_annotation/supplement_from_export.py
```

**試跑建議**：步驟 2 先 `--sample 20`（跨 IKEA/ABO 均衡抽樣）確認格式與品質，滿意再跑全量。
**續跑**：`annotate_full` 以 `annotations_full.jsonl` 記錄進度，**只把成功列視為完成**；暫時性 429 等錯誤列在重跑時自動重試，中斷不會重做。

## 三、渲染新 GLB（選用）

若有新的 `.glb` 要納入（非預渲染那批），用 `render_abo.py` 產兩視角 PNG：

```bash
$PY rendering/render_abo.py     # models/*.glb → rendering/output/
```

`glb_annotation_pipeline.py` 提供共用函式（`render_views` / `build_prompt` / `call_vlm`），供 `render_abo.py` 與 `annotate_full.py` 匯入。

## 四、產出檔案

| 檔案 | 內容 |
|---|---|
| `vlm_annotation/render_meta_full.jsonl` | id → [正面,45度] 對照表（9,350 件） |
| `vlm_annotation/annotations_full.jsonl` | 逐筆標註進度檔（續跑依據、provenance） |
| `rag_dataset/furniture_enriched_v2.json` | ★ 最終 RAG（VLM 標註 + RAG 欄位補充） |
| `rag_dataset/furniture_enriched_v2.bak_before_supplement.json` | 還原點（補充前） |
| `all_furniture_vlm_responses_.json` | 既有全量 VLM 匯出（RAG 欄位來源，保有 raw response） |

欄位說明見 README「四、資料欄位字典」。

## 五、驗收重點（人工看）

1. 抽 10 筆對照渲染圖與 `description` / `rag_text`，是否符合畫面
2. `style_primary` 分布是否合理（不應集中單一風格）
3. 平均 confidence；低於 0.5 的筆數比例
4. `rag_text` / `search_keywords` 是否適合做為 embedding / 檢索來源
5. 成本：Haiku 兩張圖 + 回覆約 NT$0.1–0.2/件，全量 9,350 件約 NT$1,000–2,000

## 六、已知限制

- **灰模判定**：預渲染這批為灰底真實貼圖渲染，色度無法區分「無貼圖灰模」與「本來就是黑/白/灰的家具」，故一律送圖由 VLM 判斷（`is_gray=False`）。
- **匯出補充覆蓋**：`all_furniture_vlm_responses_.json` 有 9,200 筆成功、150 筆 failed/blocked；後者不補（保留既有欄位）。
- **enum 正規化**：VLM 偶把風格附中文註（`minimalist(極簡風)`），比對前去括號以免誤降信心。
- **macOS 渲染後端**：`pyrender` 用預設 pyglet（勿設 `PYOPENGL_PLATFORM=egl/osmesa`，會 ImportError）。
