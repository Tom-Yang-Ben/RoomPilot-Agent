# RAG 家具資料集 — 建置與加值流程

把 9,350 件家具（IKEA + ABO）的渲染圖，經 VLM 加值成可供 RAG 檢索的結構化資料集：**補齊缺漏欄位、以 taxonomy 受控標註外觀樣式、再補充 RAG 檢索欄位**。

最終成品：**`rag_dataset/furniture_enriched_v2.json`（9,351 筆，其中 9,350 件具 VLM 標註）**。

---

## 一、這個 RAG 在做什麼（資料加值視角）

1. **補充缺少的資訊** — 原始 `furniture_enriched_v1.json` 有 906 筆缺 `colors`、且絕大多數缺外觀標註。加值流程補起來。
2. **增加資訊欄位** — 每件新增外觀與檢索欄位（見欄位字典），讓檢索能依風格、氛圍、材質、關鍵字命中，而非只靠名稱。
3. **透過 VLM 辨識樣式** — Claude 視覺模型「看」預渲染圖，判斷風格、圖樣、顏色、材質，並產出 80–120 字中文描述。
4. **渲染（技術前提）** — VLM 看不到 3D 模型，需先有渲染圖。本專案的 9,350 件已備妥預渲染 PNG（見資料流）。

### 資料流

```
rendering/output/ikea & abo/  (預渲染 PNG，18,700 張 = 9,350 件 × 正面/45度)
        │
        │ build_render_meta_full.py   建 id→[正面,45度] 對照表
        ▼
render_meta_full.jsonl
        │ annotate_full.py annotate   VLM 受控標註（style/pattern/mood/description…）
        ▼
annotations_full.jsonl
        │ annotate_full.py merge      併入主資料集
        ▼
furniture_enriched_v2.json  ◀── supplement_from_export.py  補入既有匯出的 RAG 欄位
        ★ 最終 RAG              (rag_text / search_keywords / features / shape_tags / object_type)
                                來源：all_furniture_vlm_responses_.json
```

> PNG 統計：IKEA 5,224 張（2,613 件）＋ ABO 13,476 張（6,738 件）＝ 18,700 張。
> 這批是「灰色背景上的真實貼圖渲染」，全部送圖給 VLM 依實際外觀判斷。

---

## 二、目錄結構

所有腳本以專案根為 `PROJ` 定位跨資料夾檔案。

```
RAG/
├── rendering/
│   ├── render_abo.py            由 GLB 渲染兩視角的工具（未來新 GLB 用；需自行放入來源 GLB）
│   └── output/
│       └── ikea & abo/          預渲染 PNG（IKEA+ABO 全量 18,700 張，全量標註的影像來源）
├── vlm_annotation/          VLM 標註（全量流程）
│   ├── glb_annotation_pipeline.py   共用函式庫（build_prompt / call_vlm / render_views）
│   ├── build_render_meta_full.py    掃描 PNG → render_meta_full.jsonl
│   ├── annotate_full.py             全量 VLM 標註 + merge 進 v2
│   ├── supplement_from_export.py    從既有匯出補 RAG 欄位進 v2
│   ├── taxonomy_v1.json             控制詞彙：12 風格 / 4 圖樣 / 24 氛圍詞
│   ├── render_meta_full.jsonl       id → [正面,45度] 對照表（9,350 件）
│   └── annotations_full.jsonl       標註進度檔（可續跑，provenance）
├── rag_dataset/
│   ├── furniture_enriched_v1.json   來源 items（9,351 筆）
│   ├── furniture_enriched_v2.json   ★ 最終 RAG
│   └── furniture_enriched_v2.bak_before_supplement.json   還原點（補充前）
├── all_furniture_vlm_responses_.json   既有全量 VLM 匯出（RAG 欄位來源，含 raw response）
├── docs/                    GLB標註pipeline執行說明.md
└── README.md
```

---

## 三、執行流程（全量）

```bash
PY=.venv/bin/python
export ANTHROPIC_API_KEY="$(tr -d '\n' < .anthropic_key)"

# 1. 建對照表：掃描預渲染 PNG → id→[正面,45度]
$PY vlm_annotation/build_render_meta_full.py

# 2. 全量 VLM 標註（~9,350 件，可續跑；建議背景執行）
#    先試跑：--sample 20 跨品牌抽樣看品質
$PY vlm_annotation/annotate_full.py annotate --sample 20
$PY vlm_annotation/annotate_full.py annotate            # 全量

# 3. 併入主資料集
$PY vlm_annotation/annotate_full.py merge               # → furniture_enriched_v2.json

# 4. 從既有匯出補 RAG 欄位（rag_text / search_keywords / features …）
$PY vlm_annotation/supplement_from_export.py            # → furniture_enriched_v2.json
```

**可續跑**：`annotate_full` 只把「成功列」視為完成，暫時性 429 等錯誤列在重跑時自動重試。中斷不會重做已完成的。

---

## 四、資料欄位字典

### VLM 標註欄位（taxonomy 受控，本專案 annotate_full 產出）

| 欄位 | 說明 | 取值 |
| :-- | :-- | :-- |
| `style_primary` / `style_secondary` | 主/次風格 | taxonomy 12 選 1（nordic / japandi / minimalist / rustic …） |
| `pattern` | 表面圖樣 | 素色 / 木紋 / 幾何 / 花紋 |
| `mood_tags` | 氛圍標籤 | 24 詞選最多 3（溫馨 / 俐落 / 沉穩 …） |
| `description` | 外觀描述 | 80–120 字繁中 |
| `confidence` | 把握度 | 0–1 |
| `desc_source` | 描述來源 | `glb_render`（看圖）|

### RAG 檢索欄位（由 all_furniture_vlm_responses_.json 補入）

| 欄位 | 說明 |
| :-- | :-- |
| `rag_text` | 檢索文本（描述句 / 特徵句 / 關鍵字，最多 3 段）——**建議做為 embedding 來源** |
| `search_keywords` | 搜尋關鍵字（繁中） |
| `features` | 細部特徵列表 |
| `shape_tags` | 造型標籤 |
| `object_type_zh` | 物件類型 |

### 被「補齊」的既有欄位

`colors` / `materials`：原本為空或佔位符時，填入 VLM 實際看到的值。尺寸 / 價格 / 房型（`room_types`）/ `name_zh` 等既有可信欄位**不被覆寫**。

---

## 五、設計要點

- **成本控制**：標註用 Haiku（非 Opus）、每件 2 視角，適合上萬件規模（全量約 NT$1,000–2,000）。
- **enum 正規化**：VLM 有時把風格附中文註（如 `minimalist(極簡風)`），比對前先去括號，避免誤降信心。
- **只補不覆寫**：補入匯出欄位與合併標註時，既有可信欄位一律保留；就地寫入前先備份。
- **灰模判定**：預渲染這批是灰底真實貼圖渲染，無法用色度區分「無貼圖灰模」與「本來就是黑/白/灰的家具」，故一律送圖由 VLM 判斷。
- **macOS 渲染**（render_abo）：`pyrender` 用預設 pyglet 後端（勿設 `PYOPENGL_PLATFORM=egl/osmesa`，會 ImportError）。

> 完整的「GLB → VLM 標註」技術要點另見個人 skill：`annotating-glb-furniture-with-vlm`。

---

## 六、環境需求

- Python 3.9、專案自帶 venv：`.venv/`
- 套件：`trimesh`、`pyrender`、`pillow`、`numpy`、`anthropic`、`gdown`
- VLM 金鑰：`.anthropic_key`（純文字，內含 `sk-ant-...`）。已列入 `.gitignore`；惟本目錄目前不在 git 版控內，若日後納入版控該規則即生效，請務必勿提交金鑰。
