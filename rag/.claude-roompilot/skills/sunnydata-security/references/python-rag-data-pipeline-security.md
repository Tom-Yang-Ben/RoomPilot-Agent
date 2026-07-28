# RAG 資料管線（Python）安全規範（ChromaDB 1.5.9 / bge-m3, Python 3.11.15）

本文件是一份**安全規格**，支援兩種用途：
1) 為 `rag_pipeline/embed_v3.py`、`rag_pipeline/retriever.py`、`json_adjustment/*.py`
   等資料建置與檢索程式**產生預設安全的程式碼**。
2) 對既有管線程式碼做**安全審查／漏洞獵捕**（被動「順手發現問題」與主動「掃描整個 repo 並回報」）。

刻意寫成一組**規範性要求**（MUST／SHOULD／MAY）加上**稽核規則**
（不良模式長什麼樣、怎麼偵測、怎麼修或緩解）。

> **適用範圍**：本專案沒有資料庫連線、沒有 ORM、沒有對外服務。
> 資料流是 `rag_dataset/furniture_enriched_v3.json` → `bge-m3` → `chroma_db/` + `rag_export/`。
> 因此「注入」的 sink 不是 SQL 語句而是 **Chroma `where` 字典**；
> 「權限」不是使用者角色而是 **`rag_indexable` 與交付範圍**；
> 「完整性」不是傳輸加密而是 **`text_hash` 與驗證報告**。

--------------------------------------------------------------------

## 0) 安全邊界與反濫用限制（MUST FOLLOW）

- MUST NOT 索取、輸出、記錄或提交任何金鑰（`ANTHROPIC_API_KEY`、`.anthropic_key` 內容）。
- MUST NOT 用「關掉防護」來修問題（例如移除維度檢查、跳過驗證報告、關掉 `rag_indexable` 篩選）。
- MUST 提供**基於證據的發現**：引用檔案路徑、程式片段、實際的交付檔欄位值。
- MUST 誠實處理不確定性：若某項防護可能存在於資料產生的上游（爬蟲、VLM 標註），
  回報為「管線程式碼中看不到；請於上游確認」。
- MUST NOT 在未備份 `chroma_db/` 的情況下建議執行覆寫性重建。

--------------------------------------------------------------------

## 1) 運作模式

### 1.1 產生模式（預設）
被要求撰寫新的管線程式碼或修改既有程式碼時：
- MUST 遵守本規格中每一條 **MUST** 要求。
- SHOULD 遵守每一條 **SHOULD** 要求，除非使用者明確表示不要。
- MUST 優先使用預設安全的 API 與經驗證的函式庫，而非自製安全程式碼。
- MUST 避免引入新的危險 sink（pickle 反序列化、shell 執行、以資料決定檔案路徑、
  以資料決定查詢條件鍵名等）。

### 1.2 被動審查模式（編輯時恆開）
在管線程式碼中工作時（即使使用者沒有要求安全掃描）：
- MUST「注意到」所觸及與鄰近程式碼中違反本規格之處。
- SHOULD 順手指出問題，附上簡短說明與安全修法。

### 1.3 主動稽核模式（明確的掃描請求）
使用者要求「掃描」「稽核」「找漏洞」時：
- MUST 系統性地在程式碼庫中搜尋違反本規格之處。
- MUST 以結構化格式輸出發現（見 §2.3）。

建議稽核順序：
1) 批次腳本入口與參數（`--limit` / `--only-changed` / `--dry-run` / `--skip-chroma`）。
2) 路徑與模型常數（`PROJ`、`V3`、`EXPORT_DIR`、`COLLECTION`、`EMBED_MODEL`）。
3) 來源資料載入與 schema 驗證。
4) 寫入路徑與覆寫行為（`chroma_db/`、`rag_export/`）。
5) `embedded_text` 組句與 `text_hash` 計算。
6) Chroma `where` 條件組裝（`build_where`）。
7) 注入類別（shell、反序列化、動態匯入）。
8) 外部資產讀取（GLB／PNG／JSON）與路徑穿越。
9) 出站請求（HF Hub、Anthropic、Ollama）。
10) 日誌／進度輸出與交付檔內容。

--------------------------------------------------------------------

## 2) 定義與審查指引

### 2.1 不可信輸入（除非證明否則一律視為攻擊者可控）
包含但不限於：
- `rag_dataset/furniture_enriched_v*.json` 的所有字串欄位
  （`name_zh`、`description`、`features`、`search_keywords`、`rag_text`）
  ——來自外部爬取與 VLM 產生，**不是**你寫的常數
- `vlm_annotation/taxonomy_v2.json`、`rag_pipeline/category_groups.json`
  ——是設定檔，但若被竄改會直接改變過濾與加權行為
- LLM 輸出：`query_parser` 的 `parsed` dict、VLM 標註結果、Ollama 判定結果
- CLI 參數（`sys.argv`）與環境變數
- `rendering/output/` 底下的檔名與 PNG 內容
- 既有的 `rag_export/*.jsonl`（增量模式會讀回它們並沿用其中的向量）

### 2.2 狀態變更操作
在本專案，若一個操作會建立／覆寫／刪除 `chroma_db/`、`rag_export/`、`rag_dataset/`，
或觸發花錢的批次呼叫（Anthropic 全量標註／判定，約 US$7），
就算是狀態變更操作。**唯讀腳本（`retriever.py` CLI、`--dry-run`）不得有任何寫入副作用。**

### 2.3 稽核發現的必要格式
每個問題輸出：

- Rule ID：
- Severity：Critical / High / Medium / Low
- Location：檔案路徑 + 函式名稱 + 行號
- Evidence：確切的程式碼／設定／交付檔片段
- Impact：可能出什麼事、誰能利用、會不會污染索引
- Fix：安全的修改（優先最小 diff）
- Mitigation：若立即修復困難，縱深防禦做法
- False positive notes：不確定時要驗證什麼

--------------------------------------------------------------------

## 3) 安全基線：最低執行設定（MUST）

這是防止常見管線誤設的最小基線。

### 3.1 常數與設定管理（SHOULD）
SHOULD 把所有路徑、模型名、截斷參數集中在模組頂端的常數區，
讓「換版本」只需改一處，也讓稽核只需看一個區塊。

### 3.2 最低基線目標
- `PROJ` 由 `Path(__file__).resolve().parent.parent` 推導，**不從環境變數或參數取得**
- `COLLECTION = "furniture_v3"`、`EMBED_MODEL = "BAAI/bge-m3"`、`DIMENSION = 1024` 為常數
- `os.environ.setdefault("HF_HUB_OFFLINE", "1")` 與 `TRANSFORMERS_OFFLINE` 保留
- 寫入 `chroma_db/` 前已有備份，或走雙目錄切換
- 每次寫出交付檔都同時產生 `embedding_metadata.json` 與 `embedding_validation_report.json`
- 失敗逐筆寫入 `embedding_failures.jsonl`，不因單筆失敗中斷整批

--------------------------------------------------------------------

## 4) 規則（產生 + 稽核）

每條規則包含：必要實務、不安全模式、偵測提示、修復方式。

### PIPELINE-RUN-001: 批次工作不得未經小樣本驗證即全量執行
Severity: High（成本與資料污染）

必要：
- MUST 在改動 prompt、詞表、組句方式或判定模型後，先跑小樣本再全量：
  `--dry-run`（只印統計）→ `--limit 50`（冒煙）→ `--compare 30`（一致率比對）。
- MUST 在腳本 docstring 中標明成本量級（需求解析每次約 US$0.005；全量判定約 US$7）。
- SHOULD 讓所有批次腳本可續跑（checkpoint），中斷後不重跑已完成品項。

不安全模式：
- 沒有 `--limit` / `--dry-run` 參數的批次腳本
- 直接 `for item in all_items: call_llm(item)` 而無中途落檔
- 文件教人「直接跑就好」

偵測提示：
- 搜尋 `argparse`、`add_argument`、`--limit`、`--dry-run`、`--compare`。
- 檢查是否有 checkpoint／resume 機制（讀既有輸出、跳過已完成）。

修復：
- 補上參數與 checkpoint；在 README 寫明「先小樣本」的固定流程。

註：
- 這是 A04（Insecure Design）與 LLM10（Unbounded Consumption）的交集，
  在本專案是**最容易發生的實際損失**。

---

### PIPELINE-RUN-002: 破壞性寫入必須顯式並先備份
Severity: Critical（資料不可回復）

必要：
- MUST 讓覆寫 `chroma_db/` 或刪除 `rag_export/` 需要顯式旗標。
- MUST 在覆寫前自動備份（含時間戳），或採雙目錄切換。
- MUST NOT 讓 `--dry-run` 有任何寫入副作用。
- SHOULD 提供 `--skip-chroma`，允許只重算交付檔而不動索引。

不安全模式：
- 腳本一啟動就 `client.delete_collection(...)`
- `shutil.rmtree(CHROMA_DIR)` 沒有旗標也沒有備份
- `--dry-run` 仍會寫出 `rag_export/`

偵測提示：
- 搜尋 `rmtree`、`delete_collection`、`unlink`、`open(..., "w")`、`write_text(`。
- 檢查每個寫入點是否在旗標保護之下。

修復：
```python
if not args.dry_run:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    shutil.copytree(CHROMA_DIR, f"{CHROMA_DIR}.bak.{stamp}")
```

---

### PIPELINE-CONFIG-001: 路徑與模型常數不得由資料或參數決定
Severity: High

必要：
- MUST 讓 `PROJ`、`V3`、`EXPORT_DIR`、`CHROMA_DIR`、`COLLECTION`、`EMBED_MODEL`
  為模組層級常數，由 `__file__` 推導。
- MUST NOT 從資料集欄位、LLM 輸出或未驗證的 CLI 參數取得這些值。
- MAY 允許以 `DEVICE` 環境變數覆寫裝置（值必須在 `{"mps", "cpu"}` 白名單內）。

不安全模式：
- `EXPORT_DIR = Path(args.export_dir)` 而無白名單或範圍檢查
- `COLLECTION = src["collection_name"]`（從資料檔取得 collection 名）
- `EMBED_MODEL = os.environ["MODEL"]`（可被指向任意 HF repo）

偵測提示：
- 搜尋 `os.environ[`、`os.environ.get(` 靠近路徑／模型變數。
- 檢查 `argparse` 是否有接受路徑的參數，且是否驗證。

修復：
```python
PROJ = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJ / "chroma_db"
COLLECTION = "furniture_v3"
device = os.environ.get("DEVICE", "mps")
if device not in {"mps", "cpu"}:
    raise SystemExit(f"DEVICE 只能是 mps 或 cpu，收到：{device}")
```

---

### PIPELINE-SOURCE-001: 來源資料必須驗證 schema 與版本
Severity: High

必要：
- MUST 在載入 `furniture_enriched_v3.json` 後驗證頂層欄位存在
  （`schema_version`、`text_format_version`、`text_fields`、`items`）。
- MUST 驗證每個 item 的必要欄位與型別（`id` 為 str、`price_twd` 為數值、
  `embedded_text` 為非空 str、`chroma_metadata` 為 dict）。
- MUST 對不符者寫入失敗清單並跳過，MUST NOT 讓半殘資料進索引。
- SHOULD 驗證 `schema_version` 與程式期望的版本一致，不一致就中止並說明。

不安全模式：
- `items = json.load(f)["items"]` 之後直接使用
- 用 `item.get("price_twd", 0)` 掩蓋缺欄位問題
- 對 `chroma_metadata` 內容不做任何檢查就 `add(metadatas=[...])`

偵測提示：
- 搜尋 `json.loads(`、`json.load(`、`read_text(` 之後緊接的使用方式。
- 檢查是否有任何 schema 驗證函式，或僅靠 `.get()` 預設值。

修復：
```python
REQUIRED_TOP = {"schema_version", "text_format_version", "text_fields", "items"}
missing = REQUIRED_TOP - src.keys()
if missing:
    raise SystemExit(f"來源檔缺少欄位：{sorted(missing)}")

if not isinstance(item.get("embedded_text"), str) or not item["embedded_text"].strip():
    failures.append({"item_id": item.get("id", "<unknown>"),
                     "error_type": "empty_embedded_text",
                     "error_message": "embedded_text is empty"})
    continue
```

---

### PIPELINE-INTEGRITY-001: 向量與交付檔必須同批、同 text_hash
Severity: Critical（資料完整性）

必要：
- MUST 一次編碼、同時寫入 Chroma 與 `rag_export/` 的 jsonl，共用同一批向量與 `text_hash`。
- MUST 驗證每個向量維度等於 `DIMENSION`（1024），不符者進失敗清單而非寫入。
- MUST 在增量模式下把「沿用的舊向量」也一併寫回 jsonl 並用於重建 Chroma，
  確保兩邊永遠一致。
- MUST 在 `embedding_metadata.json` 記錄 `reused_vector_count`，讓變更範圍可稽核。

不安全模式：
- 先寫 Chroma、之後另外跑一支腳本產生 jsonl（兩批向量可能不同）
- 維度不符時只印警告卻仍寫入
- 增量模式只 upsert 變動者，但 jsonl 只寫變動者（造成交付檔不完整）

偵測提示：
- 搜尋 `DIMENSION`、`len(vec)`、`upsert(`、`add(`、`EMBEDDINGS_FILE`。
- 檢查 `embedding_metadata.json` 的 `embedded_count` 是否等於 Chroma 的 `count()`。

修復：
```python
if len(vec) != DIMENSION:
    failures.append({"item_id": item["id"], "error_type": "invalid_dimension",
                     "expected_dimension": DIMENSION, "actual_dimension": int(len(vec))})
    continue
```

註：
- 這對映 OWASP LLM08（Vector and Embedding Weaknesses）。
  「demo 正常但 SQL 端結果不同」幾乎都是這條沒守住。

---

### PIPELINE-DEVICE-001: 執行環境與離線設定必須明確
Severity: Medium

必要：
- MUST 保留 `os.environ.setdefault("HF_HUB_OFFLINE", "1")` 與 `TRANSFORMERS_OFFLINE`。
  移除後，未登入被 HF Hub 限流會讓每次載入乾等數分鐘，且開啟了非必要的出站通道。
- MUST 以白名單驗證 `DEVICE`（`mps` / `cpu`），並在輸出中印出實際使用的裝置。
- SHOULD 在 `embedding_metadata.json` 記錄 `device` 與 `encode_seconds`，便於重現與比對。

不安全模式：
- 為了「讓新機器能下載模型」直接刪掉 `setdefault`
- `device = os.environ["DEVICE"]` 無白名單
- 沒有記錄執行裝置，導致效能差異無法歸因

偵測提示：
- 搜尋 `HF_HUB_OFFLINE`、`TRANSFORMERS_OFFLINE`、`setdefault`、`DEVICE`。

修復：
- 首次下載模型時以**單次環境變數覆寫**（`HF_HUB_OFFLINE=0 python …`），
  而不是改程式碼預設值。

---

### PIPELINE-STATE-001: 共用資料結構不得就地修改
Severity: Medium

必要：
- MUST 遵循專案的不可變性規則：永遠建立新物件，不修改 `load_data()`／
  `load_vocab()` 回傳的共用結構。
- MUST NOT 在檢索流程中就地改寫 `data["items"]`、`taxonomy`、`groups`。
- SHOULD 對這些單例做淺層防禦（回傳前 `copy`，或以命名慣例標示唯讀）。

不安全模式：
- `data["items"][fid]["price_twd"] = adjusted`（污染後續所有查詢）
- `parsed["items"].sort(...)` 就地排序呼叫端傳入的 list
- `meta.update(extra)` 直接改 Chroma 回傳的 metadata dict

偵測提示：
- 搜尋 `[` … `] =`、`.update(`、`.append(`、`.sort(`、`.pop(` 作用在共用結構上。
- 檢查 `@lru_cache` 函式回傳值是否被呼叫端修改。

修復：
```python
adjusted = {**item, "price_twd": new_price}          # 新物件
ranked = sorted(rows, key=lambda r: -r["final"])     # 不就地排序
```

註：
- 這同時是安全與正確性問題：跨查詢污染會讓檢索結果無法重現，也讓稽核失去基準。

---

### PIPELINE-STATE-002: 增量狀態必須可稽核
Severity: Medium

必要：
- MUST 以 `text_hash` 作為唯一的增量判斷依據（本專案的冪等鍵）。
- MUST 在增量模式讀不到既有 `rag_export/` 時**退回全量並明確告知**，
  MUST NOT 靜默產生不完整的交付檔。
- MUST 相容讀取舊檔名（`furniture_embeddings.jsonl`），但輸出一律使用現行檔名。
- SHOULD 在輸出中印出「N 筆中 M 筆 text_hash 變動需重算」。

不安全模式：
- 用「檔案修改時間」或「item 數量」判斷是否需要重算
- 找不到舊檔時靜默當成「全部都沒變」（會產生空交付檔）
- 沿用舊向量卻不記錄 `reused_vector_count`

偵測提示：
- 搜尋 `only_changed`、`text_hash`、`reused`、`mtime`、`st_mtime`。

修復：
```python
if not old_path.exists():
    print("找不到既有 rag_export，改跑全量")
    args.only_changed = False
```

---

### PIPELINE-WRITE-001: 產出寫入必須可回滾
Severity: High

必要：
- MUST 在覆寫現役索引前備份，或先寫入 `chroma_db.new/` 再原子切換。
- MUST 保留舊版資料集（`furniture_enriched_v1/v2.json` 不覆寫）。
- SHOULD 讓交付檔寫入採「先寫暫存檔再 rename」，避免中途失敗留下半截檔案。
- MUST 在切換前先跑健康檢查（筆數、維度、覆蓋率）。

不安全模式：
- 直接對現役 `EMBEDDINGS_FILE` 開 `"w"`，中途失敗即毀損交付檔
- 覆寫 `furniture_enriched_v3.json` 而不保留前一版
- 切換索引後才發現筆數不對，已無舊索引可回

偵測提示：
- 搜尋 `open(..., "w")`、`write_text(`、`replace(`、`rename(`。
- 檢查是否存在備份或暫存檔機制。

修復：
```python
tmp = EXPORT_DIR / (EMBEDDINGS_FILE + ".tmp")
with tmp.open("w", encoding="utf-8") as fh:
    ...
tmp.replace(EXPORT_DIR / EMBEDDINGS_FILE)         # 原子替換
```

---

### PIPELINE-OUTPUT-001: 交付內容必須是中性資料
Severity: High

必要：
- MUST 讓交付給 SQL 端的檔案**只含資料，不含可被執行或渲染的內容**
  （不放 HTML 片段、不放 SQL 語句、不放 shell 指令）。
- MUST 以 `json.dumps(..., ensure_ascii=False)` 正確逃逸，MUST NOT 自行拼接 JSON 字串。
- MUST NOT 在交付檔中放入絕對路徑、金鑰、內部主機名。
- SHOULD 對長文字欄位設上限，避免單行 jsonl 過大導致下游解析失敗。

不安全模式：
- `fh.write('{"item_id":"' + fid + '",...}')`（自行拼 JSON，遇引號即毀）
- 把 `description` 中的原始 HTML 原樣交付而未標明
- 交付檔內出現 `/Users/xxx/...` 絕對路徑

偵測提示：
- 搜尋 `fh.write(`、`+ '"'`、`"{" +`、`% (`。
- 抽樣 `head -1 rag_export/furniture_embeddings_bge_m3.jsonl` 檢查欄位。

修復：
- 一律 `json.dumps(dict, ensure_ascii=False)`；路徑一律相對於專案根。

註：
- 這對映 A03。sink 不在本專案（我們不渲染 jsonl），而在**下游**——
  交付方有責任不把危險內容送出去。

---

### PIPELINE-TEMPLATE-001: `embedded_text` 組句結構不得由資料控制
Severity: High

必要：
- MUST 讓組句樣板是程式碼中的常數；資料只能出現在插值位置。
- MUST 對插入的欄位做長度截斷（`MAX_SEQ_LEN=512`，超過會被模型截掉，
  應在組句時就有意識地取捨而非放任截斷）。
- MUST NOT 對資料字串使用 `.format()`（`"{x.__class__}".format(x=obj)` 可讀出內部物件）。
- MUST 在改變組句方式時同步升 `text_format_version` 並**全量重建**
  （增量會混到舊句式的向量）。

不安全模式：
- `template = src["text_template"]; template.format(**item)`（樣板來自資料）
- 不截斷地把 `rag_text` + `description` + `features` 全串起來
- 改了組句卻沿用 `--only-changed`

偵測提示：
- 搜尋 `.format(`、`f"名稱：`、`text_format_version`、`MAX_SEQ_LEN`。
- 比對 `embedding_metadata.json` 的 `text_format_version` 與程式碼是否一致。

修復：
- 樣板寫成常數 f-string；欄位先 `str(...)[:N]` 截斷；改樣板就升版本並全量重建。

---

### PIPELINE-QUERY-001: 防止檢索條件注入
Severity: High

必要：
- MUST 讓 Chroma `where` 的**鍵名**永遠來自程式常數，不得由 LLM 輸出或資料決定。
- MUST 對值做白名單（`category_group` ∈ 19 群組、`style` ∈ 六風格、
  `room_type` ∈ 9 房型）與明確型別轉換。
- MUST NOT 把 `rag_indexable` 放進 `where`——它是頂層欄位、不在 `chroma_metadata` 裡，
  寫了會命中 0 筆。
- MUST NOT 用 `json.loads(llm_output)` 的結果直接當 `where`。

不安全模式：
- `where = {parsed["field"]: {"$eq": parsed["value"]}}`
- `{"price_twd": {"$lte": parsed["price_max"]}}` 而未 `int()` 與範圍檢查
- `{"rag_indexable": True}` 出現在任何 `where` 中

偵測提示：
- 搜尋 `where`、`$and`、`$in`、`$lte`、`$gte`、`rag_indexable`。
- 檢查 `build_where` 的每一個鍵是否為字面常數。

修復：
```python
ALLOWED_GROUPS = set(groups["groups"])
if item.get("category_group") not in ALLOWED_GROUPS:
    return None
clauses.append({"price_twd": {"$lte": max(0, int(item["price_max"]))}})
```

---

### PIPELINE-CMD-001: 防止作業系統指令注入
Severity: Critical to High

必要：
- MUST 避免以不可信輸入執行 shell 指令。
- 若必須使用 subprocess：
  - MUST 以 list 傳參（不是字串）
  - MUST NOT 對受影響的字串使用 `shell=True`
  - SHOULD 對任何可變部分使用嚴格白名單
- 能用純 Python 或函式庫達成時優先（PIL 取代 `sips`、`trimesh`/`pyrender` 取代外部轉檔工具）。
- 不要假設 `shell=False` 下參數必然安全——參數可能被誤判為命令列旗標；
  可行時把使用者值放在 `--` 之後。

不安全模式：
- `os.system(f"ollama run {model} '{prompt}'")`
- `subprocess.run(f"cp {src} {dst}", shell=True)`，其中路徑來自資料集
- 把家具檔名（來自資料）拼進轉檔指令

偵測提示：
- 搜尋 `os.system`、`subprocess`、`Popen`、`shell=True`、`os.popen`。
- 追蹤資料是否從 JSON／LLM 流入這些呼叫。

修復：
- 改用函式庫 API；不得已時硬編碼指令，參數以 list 傳入並白名單驗證。

---

### PIPELINE-ASSET-001: 外部資產讀取必須驗證
Severity: High

必要：
- MUST 對讀取的 GLB／PNG／JSON 設大小上限，避免單檔撐爆記憶體。
- MUST 以「副檔名白名單 + 實際解析成功」雙重驗證，不只看副檔名。
- MUST NOT 對來源不明的 `.pkl` / `.pt` / `.bin` 執行反序列化。
- SHOULD 讀取失敗採靜默降級（略過該筆、寫入失敗清單），不讓整批中斷。

不安全模式：
- `json.load(open(path))` 對任意大小的檔案（單檔數 GB 即 OOM）
- `pickle.load(open(path, "rb"))` 讀取外部產生的快取
- 只檢查 `.glb` 副檔名就交給解析器

偵測提示：
- 搜尋 `pickle`、`torch.load`、`joblib.load`、`np.load`（`allow_pickle=True` 尤其危險）。
- 搜尋 `open(`、`json.load(`、`Image.open(` 是否有大小檢查。

修復：
```python
if p.stat().st_size > MAX_ASSET_BYTES:
    failures.append({"item_id": fid, "error_type": "asset_too_large"})
    continue
np.load(path, allow_pickle=False)        # 絕不允許 pickle
```

---

### PIPELINE-PATH-001: 防止路徑穿越與輸出目錄外洩
Severity: High

必要：
- MUST 以 `Path.resolve()` + `is_relative_to(BASE)` 驗證所有由資料組成的路徑。
- MUST 把允許讀取的根目錄限制在 `rag_dataset/`、`rendering/output/`、`vlm_annotation/`。
- MUST 把允許寫入的根目錄限制在 `rag_export/`、`chroma_db/`、`rag_dataset/`。
- MUST NOT 讓輸出檔名包含來自資料的未清洗字串（可含 `../` 或 `/`）。

不安全模式：
- `out = EXPORT_DIR / item["id"]`，其中 `id` 來自資料且未驗證
- `Image.open(PROJ / meta["image_path"])`（`"../../.anthropic_key"` 即可讀到金鑰）
- 用 `os.path.join` 而不檢查結果是否仍在 base 之下

偵測提示：
- 搜尋 `os.path.join(`、`/` 路徑運算、`open(`、`write_text(`。
- 檢查每個路徑片段的來源。

修復：
```python
def safe_under(base: Path, rel: str) -> Path:
    p = (base / rel).resolve()
    if not p.is_relative_to(base.resolve()):
        raise ValueError(f"非法路徑：{rel}")
    return p
```

---

### PIPELINE-URL-001: 資料中的 URL 不得被自動請求
Severity: Medium（SSRF / 資料外洩）

必要：
- MUST NOT 對資料集中的 URL 欄位（商品連結、圖片來源）發出自動請求。
- MUST 讓所有出站目的地硬編碼：`https://api.anthropic.com`、
  `http://127.0.0.1:11434`（Ollama）、HuggingFace Hub（僅首次下載模型）。
- MUST 只允許 `http` / `https`（禁止 `file:` 等協定）。
- SHOULD 設定 timeout 與重導上限。

不安全模式：
- 補圖腳本 `requests.get(item["image_url"])` 掃過整個資料集
- 允許環境變數任意覆寫 `ANTHROPIC_BASE_URL` 而無白名單
- 移除 `HF_HUB_OFFLINE` 的 `setdefault`

偵測提示：
- 搜尋 `requests.`、`httpx`、`urllib`、`aiohttp`、`base_url`、`_BASE_URL`。
- 檢查資料集中是否有 URL 欄位被程式讀取。

修復：
- 外部素材改為離線預先下載並人工審核後入庫；執行期不對外抓取。

---

### PIPELINE-DESER-001: 禁止不安全的反序列化與遠端程式碼
Severity: Critical

必要：
- MUST NOT 使用 `pickle` / `joblib` 載入非本程式產生的檔案。
- MUST NOT 使用 `trust_remote_code=True` 載入 HF 模型。
- MUST 使用 `np.load(..., allow_pickle=False)`。
- MUST 以固定的模型 repo 名載入（`BAAI/bge-m3`、`BAAI/bge-reranker-v2-m3`），
  MUST NOT 從設定檔或 LLM 輸出取得模型名稱。
- SHOULD 優先使用 safetensors 格式的權重。

不安全模式：
- `SentenceTransformer(cfg["model_name"], trust_remote_code=True)`
- `pickle.load(open("cache.pkl", "rb"))`
- `torch.load(path)` 未指定 `weights_only=True`

偵測提示：
- 搜尋 `pickle`、`trust_remote_code`、`torch.load`、`allow_pickle`、`joblib`。

修復：
```python
SentenceTransformer("BAAI/bge-m3")                 # 常數，不 trust_remote_code
torch.load(path, weights_only=True)                # 若真的需要
```

註：
- 這對映 A08 與 LLM03（Supply Chain）。模型權重是可執行內容，
  「從 HF 抓一個看起來對的 repo」等同執行陌生程式碼。

---

### PIPELINE-VALIDATE-001: 交付前必須通過驗證報告
Severity: High

必要：
- MUST 每次寫出交付檔時同步產生 `embedding_validation_report.json`，
  含 `total_source_items`、`total_embedding_records`、`unique_furniture_ids`、
  `duplicate_furniture_ids`、`missing_furniture_ids`、`invalid_vector_count`、
  `null_vector_count`、`dimension_distribution`、`model_distribution`、`coverage_percent`。
- MUST 在交付前由人檢視 `coverage_percent` 與 `failed_count`。
- MUST 讓 `duplicate_furniture_ids` 為 0；不為 0 時 MUST 阻止交付。
- SHOULD 把驗證做成可獨立執行的檢查腳本，讓交付方也能自行驗。

不安全模式：
- 只產生 jsonl 而沒有驗證報告
- 報告產生了但沒人看
- 覆蓋率驟降卻照常交付

偵測提示：
- 檢查 `rag_export/embedding_validation_report.json` 是否存在、`generated_at` 是否為最新。
- 比對報告的 `total_embedding_records` 與 Chroma `count()`。

修復：
- 把驗證納入 §`scripts/verify.sh` 的最後一步，未通過就 `exit 1`。

---

### PIPELINE-KEY-001: 批次金鑰與成本控制
Severity: Critical

必要：
- MUST 從 `ANTHROPIC_API_KEY` 或 `.anthropic_key` 載入，兩者皆無則啟動即失敗。
- MUST NOT 記錄、列印或寫入任何金鑰片段（含進度輸出與失敗清單）。
- MUST 為所有 LLM 呼叫設重試上限（不得無限重試）。
- MUST 在 `--provider anthropic` 這類「會花錢」的切換上，於腳本輸出明確警示成本量級。
- SHOULD 使用本機 Ollama（`qwen3:8b`）作為預設 provider，Anthropic 為顯式選項。

不安全模式：
- `while True: try: call() except: continue`（無上限重試 → 無上限燒錢）
- 預設 provider 就是 Anthropic 且無成本提示
- 把金鑰當成參數傳進子行程的命令列（會出現在 `ps` 輸出）

偵測提示：
- 搜尋 `--provider`、`anthropic.`、`retry`、`while True`、`MAX_RETRIES`。
- 檢查金鑰是否曾經以 CLI 參數傳遞。

修復：
```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        return call()
    except Exception:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(2.0 ** attempt)
```

---

### PIPELINE-AUTHZ-001: 可索引性必須在寫入時決定
Severity: Medium

必要：
- MUST 在建索引時就用 `rag_indexable` 篩掉不可索引品項，並寫入失敗清單
  （`error_type: "not_indexable"`）。
- MUST NOT 依賴查詢時過濾來達成同樣效果（`rag_indexable` 不在 `chroma_metadata` 裡，
  寫進 `where` 只會命中 0 筆）。
- SHOULD 讓「不可索引」的原因可追溯（`is_active=False` 或無文本）。

不安全模式：
- 全部寫進索引，靠 `where` 排除
- 篩掉了但沒有記錄，導致覆蓋率下降無法解釋

偵測提示：
- 搜尋 `rag_indexable`、`not_indexable`、`skipped`。
- 比對 `source_item_count` − `embedded_count` 是否等於失敗清單長度。

修復：
```python
if not item.get("rag_indexable"):
    skipped.append(item)
    continue
# …最後統一寫入 failures，附上原因字串
```

---

### PIPELINE-EXPORT-001: 交付檔必須視為高價值目標
Severity: Medium

必要：
- MUST 把 `rag_export/` 視為對外交付物：內容一旦送出即無法收回。
- MUST 在交付前確認不含金鑰、絕對路徑、內部備註欄位。
- MUST 附上 `embedding_metadata.json` 說明 `id_key`、維度、距離度量、
  `text_format_version` 與 `source_schema_version`——讓下游不必猜。
- SHOULD 交付時附上檔案雜湊，供對方驗證完整性。

不安全模式：
- 交付 jsonl 但不附 metadata（下游只能猜 1024 維、猜 cosine）
- 交付檔中出現 `/Users/…` 路徑
- 交付後又本機改了資料卻沒通知對方

偵測提示：
- `grep -c "/Users/" rag_export/*.json*`
- 檢查 `embedding_metadata.json` 是否包含 `id_key`。

修復：
- 交付前跑一次「敏感字串掃描」；把 `id_key` 等契約欄位補齊。

註：
- `json_adjustment/RAGSQL.md` 的範例用 `furniture_id`，實作寫的是 `item_id`，
  靠 `"id_key": "item_id"` 宣告。改名必須兩份文件同時改。

---

### PIPELINE-LOG-001: 日誌與進度輸出不得外洩敏感資料
Severity: Medium

必要：
- MUST NOT 在進度輸出、失敗清單或例外訊息中包含金鑰、完整絕對路徑或完整 prompt。
- MUST 讓失敗清單只含 `item_id` 與結構化的錯誤欄位，不含原始資料全文。
- SHOULD 進度輸出包含可操作資訊：筆／秒、已用時間、ETA、失敗數。
- SHOULD 例外只記錄型別與簡短訊息（`f"{type(exc).__name__}: {exc}"`），不印完整堆疊到共享檔案。

不安全模式：
- `print(f"送出 prompt：{system_prompt}")`（洩漏內部 schema 與詞表）
- 失敗清單中放入整筆 item（含所有欄位）
- 把日誌寫到 `rag_export/` 內（會隨交付一起送出）

偵測提示：
- 搜尋 `print(`、`logging.`、`traceback`、`format_exc`。
- 檢查日誌輸出路徑是否位於交付目錄內。

修復：
- 日誌另存 `logs/`（並列入 `.gitignore`）；輸出前先過濾敏感欄位。

---

### PIPELINE-SUPPLY-001: 依賴、模型與資料來源衛生
Severity: Low（單一事件）／High（累積風險）

必要：
- SHOULD 固定並定期更新安全關鍵依賴：`chromadb`、`sentence-transformers`、
  `torch`、`numpy`、`pillow`、`anthropic`。
- MUST 建立 lock file（`requirements.lock.txt`）——**本專案目前沒有，屬待辦**。
- MUST 對已知安全公告及時回應。
- MUST 記錄資料來源與版本（`source_schema_version`），讓被污染的批次可以被追溯與撤回。
- SHOULD 定期執行 `pip audit`。

稽核重點範例：
- `numpy` 的 `allow_pickle` 預設行為、`torch.load` 的 `weights_only` 預設值變化。
- HF repo 名是否可能被搶註（typosquatting）——`BAAI/bge-m3` 必須逐字比對。
- Ollama 模型 `qwen3:8b` 的來源與版本是否記錄在文件。

偵測提示：
- `.venv-rag/bin/python -m pip list --outdated`
- 檢查是否存在 lock file；檢查模型名是否為字面常數。

修復：
- 升級到已修補版本；補上 lock file；升級後跑一次 `--limit 50` 冒煙確認無回歸。

--------------------------------------------------------------------

## 5) 實務掃描啟發式（怎麼「獵」）

主動掃描時，用這些高訊號模式：

- 批次與成本：
  - 缺少 `--limit` / `--dry-run` / `--compare`、`while True` 重試、無 checkpoint
- 破壞性寫入：
  - `rmtree`、`delete_collection`、`open(..., "w")`、`write_text(`、無備份
- 設定：
  - `os.environ[` 靠近路徑／模型變數、`COLLECTION` 來自資料、`DEVICE` 無白名單
- 完整性：
  - `len(vec)` 沒檢查、`upsert` 與 jsonl 寫入分屬不同執行、`reused` 未記錄
- 不可變性：
  - `[…] =`、`.update(`、`.sort(` 作用在 `load_data()` 回傳值上
- 組句：
  - `.format(`、樣板來自資料、`text_format_version` 與程式碼不一致
- 注入：
  - `where` 鍵名為變數、`json.loads(llm_output)` 直接使用、`rag_indexable` 出現在 `where`
  - `subprocess.*`、`shell=True`、`os.system`
- 反序列化／供應鏈：
  - `pickle`、`joblib`、`torch.load`、`allow_pickle=True`、`trust_remote_code=True`
  - 模型名來自設定檔而非常數
- 檔案：
  - `os.path.join(` 無 `is_relative_to`、無大小上限、輸出檔名含未清洗的 `id`
- 出站：
  - `requests.get/post` 讀資料集 URL、`HF_HUB_OFFLINE` 的 `setdefault` 被移除
- 日誌／交付：
  - `print(` 含 prompt 或金鑰、日誌寫在 `rag_export/` 內、交付檔含 `/Users/`

務必確認三件事：
- 資料來源（不可信 vs 可信——資料集與 LLM 輸出都算不可信）
- sink 型別（`where` 條件／檔案路徑／subprocess／反序列化／出站請求／交付檔）
- 現有防護（schema 驗證、白名單、型別轉換、維度檢查、備份）

--------------------------------------------------------------------

## 6) 來源（本專案版，2026-07-28 對照實際程式碼校訂）

專案內事實來源（SSOT，優先於任何外部文件）：
- `.claude-roompilot/PROJECT_BRIEF.md`（技術棧、六個坑、成本結構）
- `rag_pipeline/embed_v3.py`（交付檔欄位、失敗分類、增量邏輯）
- `rag_pipeline/retriever.py`（`build_where`、`lru_cache` 單例、排序權重）
- `json_adjustment/RAGSQL.md`、`json_adjustment/i_need_rag.md`（SQL 端交付規格）
- `docs/RAG檢索系統說明.md`、`rag_pipeline/README.md`

函式庫文件：
- ChromaDB Docs：Metadata filtering（`where` 運算子）— https://docs.trychroma.com/
- Sentence-Transformers Docs — https://www.sbert.net/
- Python Docs：`pathlib.Path.is_relative_to` — https://docs.python.org/3/library/pathlib.html
- Python Docs：`pickle` 安全警告 — https://docs.python.org/3/library/pickle.html
- NumPy Docs：`np.load` 的 `allow_pickle` — https://numpy.org/doc/stable/reference/generated/numpy.load.html

OWASP Cheat Sheet Series：
- Input Validation — https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- Injection Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html
- OS Command Injection Defense — https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- Deserialization — https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html
- SSRF Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- Logging — https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- Secrets Management — https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

LLM 相關：
- OWASP Top 10 for LLM Applications（LLM03 Supply Chain、LLM04 Data Poisoning、
  LLM08 Vector and Embedding Weaknesses）— https://owasp.org/www-project-top-10-for-large-language-model-applications/
