# Gradio（Python）本機應用安全規範（Gradio 6.20.0, Python 3.11.15）

本文件是一份**安全規格**，支援兩種用途：
1) 為 `rag_pipeline/app.py` 等 Gradio 介面**產生預設安全的程式碼**。
2) 對既有 Gradio 程式碼做**安全審查／漏洞獵捕**（被動「順手發現問題」與主動「掃描整個 repo 並回報」）。

刻意寫成一組**規範性要求**（MUST／SHOULD／MAY）加上**稽核規則**
（不良模式長什麼樣、怎麼偵測、怎麼修或緩解）。

> **適用範圍**：RoomPilot 的 Gradio UI 是**本機單機**應用——只綁 `127.0.0.1:7860`、
> 無帳號、無 cookie 認證、無資料庫連線、無檔案上傳。傳統 Web 的 session／CSRF 風險大幅降低，
> 但 **HTML 注入、路徑穿越、金鑰外洩、對外暴露**這四類仍然完全成立。

--------------------------------------------------------------------

## 0) 安全邊界與反濫用限制（MUST FOLLOW）

- MUST NOT 索取、輸出、記錄或提交任何金鑰（`ANTHROPIC_API_KEY`、`.anthropic_key` 內容）。
- MUST NOT 用「關掉防護」來修安全問題（例如移除 `html.escape`、放寬路徑檢查、關掉輸入驗證）。
- MUST 提供**基於證據的發現**：稽核時要引用檔案路徑、程式片段與設定值來佐證主張。
- MUST 誠實處理不確定性：若某項防護可能在別處（作業系統防火牆、macOS 本機權限），
  回報為「應用程式碼中看不到；請於執行時／設定端確認」。
- MUST NOT 為了 demo 方便而建議 `share=True` 或綁 `0.0.0.0`。

--------------------------------------------------------------------

## 1) 運作模式

### 1.1 產生模式（預設）
被要求撰寫新的 Gradio 程式碼或修改既有程式碼時：
- MUST 遵守本規格中每一條 **MUST** 要求。
- SHOULD 遵守每一條 **SHOULD** 要求，除非使用者明確表示不要。
- MUST 優先使用預設安全的 API 與經驗證的函式庫，而非自製安全程式碼。
- MUST 避免引入新的危險 sink（以字串組裝 HTML、shell 執行、動態匯入、
  以使用者輸入決定檔案路徑、把外部內容當成 active HTML 呈現等）。

### 1.2 被動審查模式（編輯時恆開）
在 Gradio 相關程式碼中工作時（即使使用者沒有要求安全掃描）：
- MUST「注意到」所觸及與鄰近程式碼中違反本規格之處。
- SHOULD 順手指出問題，附上簡短說明與安全修法。

### 1.3 主動稽核模式（明確的掃描請求）
使用者要求「掃描」「稽核」「找漏洞」時：
- MUST 系統性地在程式碼庫中搜尋違反本規格之處。
- MUST 以結構化格式輸出發現（見 §2.3）。

建議稽核順序：
1) 應用入口與啟動腳本（`app.py` 的 `__main__` 段、`launch()` 參數）。
2) 設定與環境變數處理（`HF_HUB_OFFLINE`、`DEVICE`、金鑰載入）。
3) 金鑰與憑證流向。
4) 狀態變更操作（重建索引、寫檔、刪檔）與其確認機制。
5) HTML 產生與 XSS（`card_html`、`condition_markdown`、`results_html`）。
6) 檔案處理（`rendering/output/` PNG 讀取、base64 內嵌）與路徑穿越。
7) 注入類別（Chroma `where` 條件、shell 執行、不安全的反序列化）。
8) 出站請求（Anthropic API、HF Hub、Ollama —— SSRF 面）。
9) 對外連結與 URL 輸出（卡片上的商品連結）。
10) 跨來源存取與安全標頭。

--------------------------------------------------------------------

## 2) 定義與審查指引

### 2.1 不可信輸入（除非證明否則一律視為攻擊者可控）
包含但不限於：
- Gradio 元件的值：`gr.Textbox` 查詢字串、`gr.Button` 追問選項的 label、`gr.Examples` 被改寫後的值
- CLI 參數：`sys.argv`（`retriever.py "<需求>"`、`query_parser.py "<需求>"`）
- 環境變數（可被啟動者任意設定）
- **資料集內容**：`furniture_enriched_v3.json` 的 `name_zh` / `description` / `features`
  ——它們來自外部爬取與 VLM 產生，**不是**你寫的常數
- **LLM 輸出**：`query_parser` 回傳的 `semantic_query` / `label_zh` / `clarify_question`
- 檔案系統上的既有檔案（`rendering/output/` 下的 PNG 檔名）

### 2.2 狀態變更操作
在本專案，若一個操作會建立／覆寫／刪除資料（`chroma_db/`、`rag_export/`、`rag_dataset/`）、
觸發花錢的副作用（Anthropic 批次呼叫）、或改變後續檢索行為（改權重、改詞表），
就算是狀態變更操作。**Gradio 事件處理器原則上應全部是唯讀的。**

### 2.3 稽核發現的必要格式
每個問題輸出：

- Rule ID：
- Severity：Critical / High / Medium / Low
- Location：檔案路徑 + 函式／事件處理器名稱 + 行號
- Evidence：確切的程式碼／設定片段
- Impact：可能出什麼事、誰能利用
- Fix：安全的修改（優先最小 diff）
- Mitigation：若立即修復困難，縱深防禦做法
- False positive notes：不確定時要驗證什麼

--------------------------------------------------------------------

## 3) 安全基線：最低本機執行設定（MUST）

這是防止常見 Gradio 誤設的最小基線。**本專案無正式環境**，
所謂「production」在此指「任何會被別人看到或操作的執行」（例如專題展示）。

### 3.1 應用啟動模式（SHOULD）
SHOULD 使用「工廠函式 + `__main__` 啟動段」，讓設定不寫死在模組層級：
- 從環境變數／金鑰檔載入設定。
- 缺少關鍵設定時**快速失敗**（`sys.exit`），不要帶著半殘設定啟動。

關鍵基線設定目標：
- `server_name="127.0.0.1"`（絕不 `0.0.0.0`）
- `server_port=7860`（固定埠，衝突時明確報錯而非隨機換埠）
- `share=False`（預設值；**絕不**顯式設為 `True`）
- `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` 的 `setdefault` 保留
- 啟動前完成模型與索引預熱，並印出就緒筆數（9,349）
- 金鑰在啟動時驗證存在，訊息中不含金鑰片段

--------------------------------------------------------------------

## 4) 規則（產生 + 稽核）

每條規則包含：必要實務、不安全模式、偵測提示、修復方式。

### GRADIO-DEPLOY-001: 本機 demo 不得對外暴露
Severity: High

必要：
- MUST 以 `server_name="127.0.0.1"` 啟動；MUST NOT 使用 `"0.0.0.0"` 或空字串。
- MUST NOT 使用 `share=True`（會產生對外可存取的臨時公開網址，繞過所有本機防護）。
- MUST NOT 把 Gradio 直接掛在對外的反向代理後而不加認證。

不安全模式：
- `demo.launch(share=True)`
- `demo.launch(server_name="0.0.0.0")`
- 文件或腳本教人「用 share 連結給同學看」

偵測提示：
- 搜尋 `launch(`、`share=`、`server_name=`、`0.0.0.0`、`GRADIO_SERVER_NAME`。
- 檢查 README、`rag_pipeline/README.md`、任何啟動腳本。

修復：
- 固定 `server_name="127.0.0.1"`，需要遠端展示時走 SSH port forwarding
  （`ssh -L 7860:127.0.0.1:7860 …`），而不是 `share`。

註：
- 本機開發使用 `127.0.0.1` 是正常且必要的，不需回報為發現。
  只有綁 `0.0.0.0` 或開 `share` 才是問題。

---

### GRADIO-DEPLOY-002: 除錯輸出不得暴露內部細節
Severity: Critical（若堆疊追蹤進入 UI）

必要：
- MUST NOT 把 `traceback.format_exc()` 或例外訊息原文輸出到 `gr.HTML` / `gr.Markdown`。
- MUST 把詳細錯誤記在終端輸出（含例外型別與上下文），UI 只顯示通用友善訊息。
- MUST NOT 開啟會回顯內部狀態的除錯開關給非開發者使用。

不安全模式：
- `return f"<pre>{traceback.format_exc()}</pre>"`
- `except Exception as e: return str(e)` 直接接到 UI 元件
- 把 `vars(args)` 或整個設定 dict 印進 UI

偵測提示：
- 搜尋 `traceback`、`format_exc`、`str(e)`、`repr(exc)` 是否流向回傳值。
- 檢查所有 `def search(...)` / `def refine(...)` 事件處理器的 except 區塊。

修復：
```python
except Exception as exc:
    print(f"[search] 失敗：{type(exc).__name__}: {exc}", flush=True)   # 終端
    return "<p>檢索暫時無法完成，請稍後再試。</p>"                      # UI
```

註：
- 開發階段在終端看到完整堆疊是正確做法，只有「進入 UI」才是問題。

---

### GRADIO-CONFIG-001: 金鑰必須外部化、不得回顯、不得提交
Severity: Critical

必要：
- MUST 從 `ANTHROPIC_API_KEY` 環境變數或 `.anthropic_key` 檔案載入，**依此優先序**。
- MUST 把 `.anthropic_key` 保持在版控之外（專案**尚未 git init**；init 後第一件事
  就是確認 `.gitignore` 內含 `.anthropic_key`）。
- MUST NOT 記錄、列印、或在 UI 顯示金鑰的任何片段。
- SHOULD 收緊檔案權限（`chmod 600 .anthropic_key`）。
- MAY 定期輪替金鑰；若懷疑外洩，MUST 立即輪替。

不安全模式：
- 原始碼中出現 `sk-ant-` 字面值
- `print(open(".anthropic_key").read())`
- 把金鑰放進 Gradio `gr.Textbox` 的預設值或 `gr.Examples`
- 錯誤訊息包含金鑰前綴

偵測提示：
- 搜尋 `sk-ant`、`api_key =`、`ANTHROPIC_API_KEY`、`.anthropic_key`。
- 檢查 `.claude-roompilot/context/` 的既有報告是否誤抄金鑰。

修復：
```python
key = os.environ.get("ANTHROPIC_API_KEY") or (
    KEY_FILE.read_text(encoding="utf-8").strip() if KEY_FILE.exists() else "")
if not key:
    raise SystemExit("缺少 ANTHROPIC_API_KEY 或 .anthropic_key")
print(f"金鑰已載入（長度 {len(key)}）")     # 只印長度
```

註：
- 本專案的金鑰直接關聯到金錢成本（批次全量約 US$7），外洩即等同財務損失。

---

### GRADIO-STATE-001: 元件狀態不得存放敏感資料
Severity: Medium

必要（等價於「session cookie 安全屬性」）：
- MUST NOT 把金鑰、絕對路徑、內部 schema 放進 `gr.State` 或元件的 `value`。
- MUST 假設任何 Gradio 元件的值都會被序列化送到瀏覽器端，並可被檢視。
- SHOULD 只在狀態中保存識別碼（`item_id`、查詢字串），需要細節時回查後端資料。

不安全模式：
- `gr.State(value={"api_key": key})`
- 把完整的 `parsed` dict（含 `reasoning`、內部 prompt 片段）塞進隱藏元件
- 把伺服器絕對路徑放進 `gr.HTML` 的 `data-*` 屬性

偵測提示：
- 搜尋 `gr.State(`、`visible=False`、`elem_id=`、`data-` 屬性。
- 追蹤哪些後端 dict 被整包丟進元件。

修復：
- 只傳遞必要欄位；敏感或冗長內容留在後端，用 ID 對應。

註：
- 本專案的 `parsed["reasoning"]` 是模型的思考說明，展示無妨，但不應含系統 prompt 原文。

---

### GRADIO-STATE-002: 全域狀態必須有界且不跨查詢污染
Severity: Medium

必要：
- MUST 確保 `@lru_cache` 的單例（`load_data`、`load_models`、`load_collection`）
  只快取**不可變的共用資源**，不得快取「某次查詢的結果」。
- MUST NOT 就地修改共用資料結構（`data["items"]`、`taxonomy`、`groups`）——
  遵循專案的不可變性規則：永遠建立新物件。
- SHOULD 為任何跨查詢累積的容器（歷史紀錄、快取）設定上限。

不安全模式：
- `data["items"][fid]["price_twd"] = new_price`（就地改共用資料 → 影響後續所有查詢）
- 用模組層級的 `list` 累積查詢歷史且無上限（記憶體無限成長）
- `@lru_cache` 套在吃 `dict` 參數的查詢函式上（不可雜湊，或快取爆量）

偵測提示：
- 搜尋 `lru_cache`、模組層級的可變全域變數（`CACHE = {}`、`HISTORY = []`）。
- 檢查是否有 `something[key] = value` 作用在 `load_data()` 的回傳值上。

修復：
- 需要修改時建立新 dict：`{**item, "price_twd": new_price}`。
- 為累積容器加上 `collections.deque(maxlen=N)`。

註：
- 這同時是安全問題與正確性問題：跨查詢污染會讓檢索結果無法重現。

---

### GRADIO-CSRF-001: 狀態變更操作必須顯式且不可由 UI 事件觸發
Severity: High

- **重要說明**：本專案**不使用 cookie 認證，因此沒有傳統 CSRF 風險**。
  等價議題是「破壞性操作是否可能被意外或間接觸發」。

必要：
- MUST 讓所有 Gradio 事件處理器保持唯讀（查詢、排序、呈現）。
- MUST NOT 在事件處理器中重建索引、寫入 `chroma_db/`、覆寫 `rag_export/` 或刪除檔案。
- MUST 讓破壞性操作只存在於 CLI 腳本，並需要顯式旗標（如 `--force-rebuild`）。
- MUST 在覆寫前自動備份（含時間戳）。

不安全模式：
- UI 上有「重建索引」按鈕直接呼叫 `embed_v3.main()`
- 事件處理器中出現 `shutil.rmtree`、`open(..., "w")`、`collection.delete`
- 批次腳本預設就覆寫現役索引，沒有旗標也沒有備份

偵測提示：
- 列舉所有 `.click(`、`.submit(`、`.change(` 綁定的函式，檢查是否寫檔。
- 搜尋 `rmtree`、`unlink`、`"w"`、`delete(`、`upsert(` 出現在 UI 模組中。

修復：
- 把破壞性動作移出 UI；CLI 加旗標與備份：
```python
if args.force_rebuild:
    shutil.copytree("chroma_db", f"chroma_db.bak.{datetime.now():%Y%m%d_%H%M}")
```

註：
- XSS 可以繞過所有「需要點按確認」的防護；本規則不能取代 GRADIO-XSS-001。

---

### GRADIO-XSS-001: 防止反射型／儲存型 XSS
Severity: High

必要：
- MUST 對所有進入 `gr.HTML` / `gr.Markdown` 的字串使用 `html.escape()`——
  **包含資料集欄位**（`name_zh`、`description`）與 LLM 輸出（`label_zh`、`clarify_question`），
  不是只有使用者輸入。
- MUST 為含變數的 HTML 屬性加上引號（`src="{uri}"`，不是 `src={uri}`）。
- MUST 只接受自產的 `data:image/...;base64,` URI 作為圖片來源；MUST NOT 接受
  資料集中的任意 URL 直接放進 `src`。
- MUST NOT 把外部 HTML 片段當成 active HTML 呈現。
- SHOULD 對 `href` 做協定白名單（只允許 `https:`），避免 `javascript:`。

不安全模式：
- `f'<h4>{row["meta"]["name_zh"]}</h4>'`（資料集欄位未跳脫）
- `f'<img src={uri}>'`（屬性未加引號）
- `gr.Markdown(f"**你的需求**：{raw_query}")`（Markdown 允許內嵌 HTML）
- `f'<a href="{meta["product_url"]}">'`（協定未驗證）

偵測提示：
- 搜尋 `gr.HTML`、`gr.Markdown`、`f'<`、`f"<`、`.format(` 產生 HTML 的位置。
- 檢查 `card_html`、`results_html`、`condition_markdown` 三個函式的每一個插值點。
- 檢查是否有任何插值點沒有經過 `html.escape`。

修復：
```python
import html

name = html.escape(str(meta.get("name_zh", "")))
uri = images.get(row["id"], "")
if not uri.startswith("data:image/"):
    uri = ""
url = meta.get("product_url", "")
url = html.escape(url) if url.startswith("https://") else ""
return f'<div class="card"><img src="{uri}" alt="{name}"><h4>{name}</h4></div>'
```

註：
- 本專案的 XSS 觸發路徑是「被污染的資料集 → 卡片 HTML → 瀏覽器」，
  即使沒有外部使用者，被污染的爬取資料也足以觸發。

---

### GRADIO-TMPL-001: 不得以使用者內容組裝模板或格式字串
Severity: Critical（若模板內容可被控制）

必要（等價 SSTI）：
- MUST NOT 對不可信字串呼叫 `.format()`——`"{a.__class__}".format(a=obj)` 可讀出內部物件。
- MUST NOT 用 `eval` / `exec` / `__import__` 處理任何來自輸入或資料集的字串。
- MUST NOT 讓資料集或 LLM 輸出決定 f-string 的**結構**（只能是被跳脫的值）。
- 若真的需要使用者自訂樣板，MUST 使用 `string.Template` 加嚴格白名單，並隔離執行。

不安全模式：
- `template.format(**parsed)`，其中 `template` 來自資料或設定檔
- `eval(parsed["expr"])`
- 用 `exec` 動態組出過濾條件

偵測提示：
- 搜尋 `.format(`、`eval(`、`exec(`、`__import__`、`compile(`。
- 追蹤格式字串本身的來源（常數？設定檔？資料集？）。

修復：
- 格式字串一律是程式碼中的常數；變數只能出現在插值位置且已跳脫。
- 需要可設定樣板時改用 `string.Template` 的 `safe_substitute`。

---

### GRADIO-HEADERS-001: 安全標頭（本機的適用範圍）
Severity: Low（本機 loopback）／Medium（若曾對外暴露）

必要：
- SHOULD 理解 Gradio 自帶的回應標頭有限，且本專案綁 loopback，
  瀏覽器同源政策已提供主要隔離。
- MUST NOT 因為「本機所以沒差」而放棄 §GRADIO-XSS-001 的跳脫——
  CSP 在此不存在，跳脫是**唯一**的防線。
- SHOULD 若未來要對外提供，先在前置代理設定 CSP、`X-Content-Type-Options: nosniff`、
  `X-Frame-Options: SAMEORIGIN`，並加上認證。

不安全模式：
- 以「有 CSP 就好」為由略過輸出跳脫（本專案根本沒有 CSP）
- 把 Gradio 用 iframe 嵌入其他頁面而不設限

偵測提示：
- 檢查是否有任何反向代理設定檔或 `app.py` 中的自訂中介層。
- 若都沒有，記錄為「本機執行，標頭由 Gradio 預設決定；對外提供前需補」。

修復：
- 維持本機執行；若必須對外，前置代理補齊標頭與認證後再開放。

註：
- 本專案**沒有**反向代理、CDN 或 WAF。不要假設有隱形防護。

---

### GRADIO-LIMITS-001: 輸入長度與併發必須設限
Severity: Medium

必要：
- MUST 限制查詢字串長度（建議 `MAX_QUERY_CHARS = 500`）。
- MUST 限制解析出的品項數（`MAX_ITEMS = 6`，在程式端裁切，schema 不支援 `maxItems`）。
- SHOULD 設定 Gradio queue 的併發上限——單機 16 GB、模型常駐 4.6 GB，
  併發查詢會直接把記憶體吃爆。
- SHOULD 對 rerank 候選數設上限（`RERANK_TOP_K=20`；cross-encoder 每 50 筆約 10 秒）。

不安全模式：
- 直接把任意長度的 `gr.Textbox` 值送進 LLM（token 成本無上限）
- 未設 queue 併發，多人同時操作導致 OOM
- 讓 LLM 回傳的 `items` 數量不裁切就全部拿去檢索

偵測提示：
- 搜尋 `Textbox(`、`max_lines`、`.queue(`、`concurrency_limit`。
- 檢查 `MAX_ITEMS`、`RERANK_TOP_K`、`VEC_TOP_K` 是否有實際套用。

修復：
```python
demo.queue(default_concurrency_limit=1)          # 單機模型常駐，序列化處理
text = text.strip()[:MAX_QUERY_CHARS]
items = parsed["items"][:MAX_ITEMS]
```

---

### GRADIO-HOST-001: 監聽位址必須明確且受限
Severity: High

必要：
- MUST 顯式指定 `server_name="127.0.0.1"`，不依賴預設值。
- MUST NOT 依賴環境變數 `GRADIO_SERVER_NAME` 決定監聽位址（可被誤設為 `0.0.0.0`）。
- MUST 在啟動輸出中明示實際監聽位址，方便人工確認。

不安全模式：
- `demo.launch()` 不帶參數（預設值可能隨版本改變）
- 監聽位址來自設定檔或環境變數而無白名單

偵測提示：
- 搜尋 `GRADIO_SERVER_NAME`、`server_name`、`launch()`。
- 執行時用 `lsof -nP -iTCP:7860 -sTCP:LISTEN` 確認實際綁定的介面。

修復：
```python
demo.launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())
```

---

### GRADIO-PROXY-001: 反向代理與轉送必須明確設定
Severity: Medium

必要：
- 本專案**沒有**反向代理。MUST 在報告中如實陳述，不要假裝有 X-Forwarded-* 處理。
- 若未來要透過 SSH port forwarding 或代理提供給他人，MUST 同時加上認證層
  （Gradio 的 `auth=` 參數或前置代理的 basic auth），且 MUST NOT 依賴「網址難猜」。
- MUST NOT 依據來源 IP 做任何授權判斷（本機應用沒有可信的 IP 資訊）。

不安全模式：
- 用 `share=True` 當成「臨時代理」提供給他人
- 假設 `127.0.0.1` 的請求一定來自本人（同機的其他行程也算）

偵測提示：
- 搜尋 `auth=`、`share=`、任何 nginx／caddy 設定檔。
- 檢查文件中是否教人把埠曝露到區網。

修復：
- 需要他人存取時：SSH tunnel + `auth=("user", "強密碼")`，密碼從環境變數讀。

---

### GRADIO-PATH-001: 防止路徑穿越與不安全的檔案讀取
Severity: High

必要：
- MUST NOT 把來自資料集或 LLM 的字串直接接到檔案路徑上。
- MUST 以 `Path.resolve()` + `is_relative_to(BASE)` 驗證最終路徑落在允許的根目錄內。
- MUST 對允許的根目錄採白名單（`rendering/output/`、`rag_dataset/`），不允許其他位置。
- SHOULD 一併驗證副檔名與檔案大小。

不安全模式：
- `Image.open(PROJ / meta["image_path"])`，其中 `image_path` 來自資料集
  （`"../../.anthropic_key"` 即可讀到金鑰）
- `open(os.path.join(base, user_path))` 未經正規化檢查
- 用 `os.path.join` 而不檢查結果是否仍在 base 之下

偵測提示：
- 搜尋 `Image.open(`、`open(`、`os.path.join(`、`Path(` 與 `/` 運算子。
- 追蹤路徑片段的來源：資料集欄位？LLM 輸出？CLI 參數？

修復：
```python
RENDER_ROOT = (PROJ / "rendering" / "output").resolve()


def safe_render_path(rel: str) -> Path:
    p = (RENDER_ROOT / rel).resolve()
    if not p.is_relative_to(RENDER_ROOT):
        raise ValueError("非法圖片路徑")
    if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("非法圖片格式")
    return p
```

註：
- `Path.is_relative_to` 需 Python 3.9+；本專案為 3.11.15，可直接使用。

---

### GRADIO-ASSET-001: 本機資產讀取與內嵌必須驗證
Severity: High

本專案沒有檔案上傳，但有「讀取外部產生的 PNG／GLB 並內嵌到 UI」，風險等價。

必要：
- MUST 限制單檔大小（建議 8 MB），避免單張圖把記憶體與回應撐爆。
- MUST 以副檔名白名單 + 實際解碼成功與否雙重驗證（不只看副檔名）。
- MUST 產生縮圖後再 base64 內嵌（`thumb_data_uri` 已做 240px 縮圖），不內嵌原圖。
- MUST NOT 內嵌任何非圖片的檔案內容到 `data:` URI。
- SHOULD 對讀取失敗採「靜默降級為無圖」，而非讓整個查詢失敗。

不安全模式：
- 直接 `base64.b64encode(open(path,'rb').read())` 而不看大小
- 只檢查 `.png` 副檔名就當成圖片內嵌
- 讀檔失敗直接讓例外冒泡到 UI（含絕對路徑）

偵測提示：
- 搜尋 `b64encode`、`data:image`、`Image.open`、`thumbnail(`。
- 檢查是否有大小與格式檢查、是否有 try/except 降級。

修復：
```python
def thumb_data_uri(path: str) -> str:
    p = safe_render_path(path)
    if p.stat().st_size > MAX_IMAGE_BYTES:
        return ""
    try:
        img = Image.open(p).convert("RGB")          # 解碼成功才算是圖片
        img.thumbnail((240, 240))
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        print(f"[thumb] 略過 {p.name}：{type(exc).__name__}", flush=True)
        return ""
```

---

### GRADIO-INJECT-001: 防止檢索條件注入（SQL injection 的等價物）
Severity: High

本專案沒有 SQL 連線；等價 sink 是 **ChromaDB `where` 字典**。

必要：
- MUST 讓 `where` 的**鍵名**永遠來自程式常數，不得由 LLM 輸出或使用者字串決定。
- MUST 對值做白名單（`category_group` 必須在 19 個群組內、`style` 在六風格內）
  與型別轉換（`int()` / `float()`）。
- MUST NOT 把 `rag_indexable` 放進 `where`（頂層欄位，不在 `chroma_metadata` → 命中 0 筆）。
- MUST NOT 用字串拼接組出任何查詢條件。

不安全模式：
- `where = {parsed["field"]: {"$eq": parsed["value"]}}`
- `where = json.loads(llm_output)` 直接使用
- `{"price_twd": {"$lte": parsed["price_max"]}}` 而 `price_max` 未經 `int()` 與範圍檢查

偵測提示：
- 搜尋 `where`、`$and`、`$in`、`$lte`、`query_collection(`、`collection.query(`。
- 檢查每個鍵名是否為字面常數；每個值是否經白名單／型別轉換。

修復：
```python
ALLOWED_GROUPS = set(groups["groups"])
if item.get("category_group") not in ALLOWED_GROUPS:
    return None                                  # 不在白名單就不過濾，而非照用
clauses.append({"price_twd": {"$lte": max(0, int(item["price_max"]))}})
```

---

### GRADIO-INJECT-002: 防止作業系統指令注入
Severity: Critical to High（視暴露程度）

必要：
- MUST 避免以不可信輸入執行 shell 指令。
- 若必須使用 subprocess：
  - MUST 以 list 傳參（不是字串）
  - MUST NOT 對受影響的字串使用 `shell=True`
  - SHOULD 對任何可變部分使用嚴格白名單
- 能用純 Python 或函式庫達成時，優先於 subprocess／系統指令
  （例如用 PIL 而非呼叫 `sips`／`convert`）。
- 不要假設 `shell=False` 下參數就必然安全——參數可能被誤判為命令列旗標。

不安全模式：
- `os.system(f"open {path}")`
- `subprocess.run(f"ollama run {model}", shell=True)`
- 把資料集中的檔名拼進指令字串

偵測提示：
- 搜尋 `os.system`、`subprocess`、`Popen`、`shell=True`、`os.popen`。
- 追蹤資料是否從 UI／資料集／LLM 流入這些呼叫。

修復：
- 改用函式庫 API；不得已時硬編碼指令並白名單驗證參數，
  並盡量把使用者值放在 `--` 之後以免被當成旗標。

---

### GRADIO-SSRF-001: 防止伺服器端請求偽造
Severity: Medium

- 說明：本專案為單機、無區網服務，SSRF 影響有限；但**出站位址由資料決定**
  仍會導致資料外洩（把查詢內容送去攻擊者的伺服器）。

必要：
- MUST 讓所有出站目的地硬編碼或來自環境變數白名單：
  `https://api.anthropic.com`、`http://127.0.0.1:11434`（Ollama）、HuggingFace Hub（僅首次下載）。
- MUST NOT 從資料集欄位、LLM 輸出或使用者輸入取得 URL 再去請求。
- MUST 只允許 `http` / `https`（禁止 `file:` 等協定）。
- SHOULD 設定 timeout 並限制重導。
- SHOULD 保留 `HF_HUB_OFFLINE=1` 的預設，讓平時完全不對 HF 發請求。

不安全模式：
- `requests.get(meta["product_url"])` 抓商品圖
- 允許以環境變數任意覆寫 `ANTHROPIC_BASE_URL` 而無白名單
- 移除 `HF_HUB_OFFLINE` 的 `setdefault`

偵測提示：
- 搜尋 `requests.`、`httpx`、`urllib`、`base_url`、`_BASE_URL`。
- 檢查 `os.environ.setdefault("HF_HUB_OFFLINE", "1")` 是否仍在。

修復：
- 需要外部圖片時，改為**離線預先下載並人工審核**後放進 `rendering/output/`，
  執行期不對外抓圖。

---

### GRADIO-REDIRECT-001: 對外連結必須驗證（開放重導的等價物）
Severity: Low

必要：
- MUST 驗證卡片上任何 `href` 的協定為 `https:`；其餘一律不輸出連結。
- SHOULD 對外部連結加上 `rel="noopener noreferrer"` 與 `target="_blank"`。
- SHOULD 對網域採白名單（如僅允許已知的商品來源網域）。

不安全模式：
- `f'<a href="{meta["url"]}">看商品</a>'`（協定與網域皆未驗證，`javascript:` 可注入）
- 直接把 LLM 產生的 URL 放上頁面

偵測提示：
- 搜尋 `href=`、`<a `、`target=`、`product_url`、`url`。

修復：
```python
url = str(meta.get("product_url", ""))
link = (f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">看商品</a>'
        if url.startswith("https://") else "")
```

---

### GRADIO-EVENT-001: 事件語意必須安全；敏感值不得進入可見通道
Severity: Medium

必要：
- MUST NOT 在唯讀事件（查詢、追問）中改變持久狀態。
- MUST NOT 把金鑰或內部路徑放進元件值、`elem_id`、檔名或日誌檔名。
- SHOULD 讓每個事件處理器的回傳 shape 固定（元件數與順序一致），避免以例外流控。

不安全模式：
- `search()` 內部順手寫入查詢紀錄檔到專案根目錄
- `elem_id=f"card-{abs_path}"`（洩漏絕對路徑）
- 用 `raise` 控制 UI 分支，讓 Gradio 顯示原始例外

偵測提示：
- 列舉 `.click(` / `.submit(` 綁定函式，檢查副作用與回傳 shape。
- 搜尋 `elem_id=`、`open(`、`logging.` 在事件處理器內。

修復：
- 副作用移出事件處理器；回傳 shape 固定；錯誤以文字回傳而非例外。

---

### GRADIO-CORS-001: 跨來源存取必須明確且最小權限
Severity: Medium

必要：
- Gradio 會在同一個埠上暴露 API 端點（`/gradio_api/…`）。MUST 意識到
  **只要瀏覽器能存取，本機其他網頁就可能對它發請求**。
- 若不需要跨來源，MUST 保持預設（不自行加寬 CORS）。
- MUST NOT 反射任意 `Origin`；MUST NOT 把 `Access-Control-Allow-Origin: *`
  與任何憑證性資訊組合。
- SHOULD 在不需要程式化存取時關閉 API 說明頁（`show_api=False`）。

不安全模式：
- 自行加中介層設定 `Access-Control-Allow-Origin: *`
- 開啟 `share=True` 使端點對整個網際網路開放

偵測提示：
- 搜尋 `Access-Control`、`CORSMiddleware`、`show_api`、`launch(`。

修復：
```python
demo.launch(server_name="127.0.0.1", server_port=7860, show_api=False)
```

---

### GRADIO-SUPPLY-001: 依賴與版本衛生（聚焦安全相關依賴）
Severity: Low

必要：
- SHOULD 固定並定期更新安全關鍵依賴：`gradio`、`chromadb`、`pillow`、
  `sentence-transformers`、`anthropic`。
- MUST 對已知安全公告及時回應（特別是 Pillow 的影像解碼漏洞——本專案會解碼外部 PNG）。
- MUST 建立 lock file（`requirements.lock.txt`）——**本專案目前沒有，屬待辦**。

稽核重點範例：
- Pillow 版本是否含已知的影像解碼 RCE 修補（本專案對 `rendering/output/` 的 PNG 做解碼）。
- Gradio 主版本升級（5 → 6）造成的 API 變動：**Gradio 6 的 theme 在 `launch()` 傳**，
  誤用舊寫法會在啟動時失敗而非安全問題，但仍需記錄。

偵測提示：
- 檢查 `.venv-rag/bin/pip list`、是否存在 lock file。
- `.venv-rag/bin/python -m pip list --outdated`。

修復：
- 升級到已修補版本，並在升級後跑一次檢索冒煙確認無回歸。

--------------------------------------------------------------------

## 5) 實務掃描啟發式（怎麼「獵」）

主動掃描時，用這些高訊號模式：

- 對外暴露：
  - `share=True`、`server_name="0.0.0.0"`、`GRADIO_SERVER_NAME`
- 金鑰：
  - `sk-ant`、`api_key =`、`.anthropic_key`、`print(` 靠近金鑰變數
- 狀態：
  - `gr.State(`、模組層級可變全域、`lru_cache` 套在吃 dict 的函式上
- 破壞性操作：
  - 事件處理器中的 `rmtree`、`unlink`、`open(..., "w")`、`upsert(`、`delete(`
- XSS：
  - `gr.HTML`、`gr.Markdown`、`f'<`、`f"<`、缺少 `html.escape`、未加引號的屬性
- 模板／執行：
  - `.format(`、`eval(`、`exec(`、`compile(`、`__import__`
- 檔案：
  - `Image.open(`、`open(`、`os.path.join(`、缺少 `is_relative_to`
  - `b64encode` 沒有大小上限
- 注入：
  - `where` 的鍵名為變數、`json.loads(llm_output)` 直接使用
  - `subprocess.*`、`shell=True`、`os.system`
- SSRF：
  - `requests.get/post`、`httpx`、URL 來自資料集或 LLM
  - `HF_HUB_OFFLINE` 的 `setdefault` 被移除
- 連結：
  - `href=` 未驗證協定、缺少 `rel="noopener"`
- CORS／API：
  - `Access-Control-Allow-Origin`、`show_api=True`

務必確認三件事：
- 資料來源（不可信 vs 可信——記得資料集與 LLM 輸出都算不可信）
- sink 型別（HTML／檔案路徑／`where` 條件／subprocess／出站請求）
- 現有防護（跳脫、白名單、路徑檢查、型別轉換）

--------------------------------------------------------------------

## 6) 來源（本專案版，2026-07-28 對照實際程式碼校訂）

專案內事實來源（SSOT，優先於任何外部文件）：
- `.claude-roompilot/PROJECT_BRIEF.md`（技術棧與六個坑）
- `rag_pipeline/app.py`（`launch()` 參數、`card_html` / `thumb_data_uri` 實作）
- `rag_pipeline/retriever.py`（`where` 組裝、`lru_cache` 單例）
- `docs/RAG檢索系統說明.md`、`rag_pipeline/README.md`

框架文件：
- Gradio Docs：Sharing Your App — https://www.gradio.app/guides/sharing-your-app
- Gradio Docs：Queuing — https://www.gradio.app/guides/queuing
- Python Docs：`html.escape` — https://docs.python.org/3/library/html.html
- Python Docs：`pathlib.Path.is_relative_to` — https://docs.python.org/3/library/pathlib.html
- Pillow Docs：Security considerations — https://pillow.readthedocs.io/en/stable/

OWASP Cheat Sheet Series：
- XSS Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- Input Validation — https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- Injection Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html
- OS Command Injection Defense — https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- SSRF Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- File Upload — https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- Unvalidated Redirects — https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
- HTTP Headers — https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html

LLM 相關：
- OWASP Top 10 for LLM Applications — https://owasp.org/www-project-top-10-for-large-language-model-applications/
