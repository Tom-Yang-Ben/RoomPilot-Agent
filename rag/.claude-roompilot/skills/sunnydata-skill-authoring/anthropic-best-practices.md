# Skill 撰寫最佳實踐（Anthropic 官方指引，RoomPilot 版）

> 學習如何撰寫 Claude 能發現並成功使用的 Skill。

好的 Skill 精簡、結構良好，並經過真實使用測試。本指南提供實務上的撰寫決策，幫助你寫出 Claude 能有效發現與使用的 Skill。

> **本專案調整說明**：本文件為 Anthropic 官方指引的繁體中文版，範例已改寫為 RoomPilot 家具風格檢索系統的情境
> （Python 3.11／`.venv-rag/bin/python`、ChromaDB `furniture_v3`、bge-m3、bge-reranker-v2-m3、
> `claude-haiku-4-5` 需求解析、Gradio 卡片）。原文的技術棧假設若本專案沒有，一律替換為最接近的對應物。

關於 Skill 如何運作的概念背景，見 [Skills overview](/en/docs/agents-and-tools/agent-skills/overview)。

## 核心原則

### 精簡是關鍵

[Context window](https://platform.claude.com/docs/en/build-with-claude/context-windows) 是公共財。你的 Skill 與 Claude 需要知道的其他所有東西共用 context window，包括：

* 系統提示
* 對話歷史
* 其他 Skill 的 metadata
* 你真正的請求

不是 Skill 裡的每個 token 都會立刻產生成本。啟動時只有所有 Skill 的 metadata（name 與 description）會被預先載入。Claude 只在 Skill 變得相關時才讀 SKILL.md，也只在需要時才讀其他檔案。不過，SKILL.md 精簡仍然重要：一旦 Claude 載入它，每個 token 都在與對話歷史和其他 context 競爭。

**預設假設**：Claude 已經很聰明

只補充 Claude 還沒有的 context。對每一段資訊都要質疑：

* 「Claude 真的需要這段解釋嗎？」
* 「我能不能假設 Claude 已經知道這件事？」
* 「這一段值得它花掉的 token 嗎？」

**好範例：精簡**（約 50 tokens）：

````markdown  theme={null}
## 查詢 Chroma 集合

用 chromadb 讀取 furniture_v3：

```python
import chromadb

col = chromadb.PersistentClient("chroma_db").get_collection("furniture_v3")
hits = col.query(query_embeddings=[vec], n_results=50)
```
````

**壞範例：太囉唆**（約 150 tokens）：

```markdown  theme={null}
## 查詢 Chroma 集合

向量資料庫是一種把文字轉成高維向量後存起來、可以做相似度搜尋的資料庫。
要查詢它，你需要一個客戶端函式庫。市面上有很多向量資料庫可以選，
但我們推薦 ChromaDB，因為它容易使用、而且大部分情況都處理得不錯。
首先你要用 pip 安裝它。然後你可以用下面的程式碼…
```

精簡版假設 Claude 已經知道什麼是向量資料庫、函式庫怎麼用。

### 設定適當的自由度

依任務的脆弱程度與變異性，調整指令的具體程度。

**高自由度**（純文字指令）：

適用於：

* 有多種有效做法
* 決策取決於脈絡
* 用經驗法則引導方向

範例：

```markdown  theme={null}
## 程式碼審查流程

1. 分析程式碼的結構與組織
2. 檢查潛在 bug 或邊界情況
3. 提出可讀性與可維護性的改善建議
4. 確認符合專案慣例
```

**中自由度**（帶參數的虛擬碼或腳本）：

適用於：

* 已有偏好的模式
* 可以接受某些變化
* 設定會影響行為

範例：

````markdown  theme={null}
## 產生檢索報表

用這個模板並依需要調整：

```python
def generate_report(results, fmt="markdown", include_scores=True):
    # 處理檢索結果
    # 以指定格式輸出
    # 視需要附上 rerank / style_compat 分數
```
````

**低自由度**（具體腳本、少參數或無參數）：

適用於：

* 操作脆弱、容易出錯
* 一致性至關重要
* 必須照特定順序執行

範例：

````markdown  theme={null}
## 重建向量索引

完全照這個指令跑：

```bash
.venv-rag/bin/python rag_pipeline/embed_v3.py --only-changed
```

不要修改指令、也不要加其他旗標（全量重建要 27 分鐘，且會覆寫 rag_export/ 交付檔）。
````

**類比**：把 Claude 想成在路上前進的機器人：

* **兩側是懸崖的窄橋**：只有一條安全路徑。提供具體護欄與精確指令（低自由度）。例如必須照順序執行的索引重建與交付檔驗證。
* **沒有危險的開闊原野**：很多路都能到終點。給大方向、信任 Claude 找到最佳路線（高自由度）。例如程式碼審查，脈絡決定最佳做法。

### 用你打算使用的所有模型測試

Skill 是模型的補充，效果取決於底層模型。用你打算搭配的所有模型測試你的 Skill。

**依模型的測試考量**：

* **Claude Haiku**（快、便宜；本專案的需求解析與 VLM 標註都用 `claude-haiku-4-5`）：Skill 給的引導夠嗎？
* **Claude Sonnet**（均衡）：Skill 夠清楚、夠有效率嗎？
* **Claude Opus**（強推理）：Skill 是不是解釋過頭了？

對 Opus 完美的寫法，對 Haiku 可能需要更多細節。若你的 Skill 會跨多個模型使用，指令要寫到對所有模型都適用。

## Skill 結構

<Note>
  **YAML Frontmatter**：SKILL.md 的 frontmatter 需要兩個欄位：

  * `name` — Skill 的可讀名稱（上限 64 字元）
  * `description` — 一行描述 Skill 做什麼、何時使用（上限 1024 字元）

  完整結構細節見 [Skills overview](/en/docs/agents-and-tools/agent-skills/overview#skill-structure)。
</Note>

### 命名慣例

使用一致的命名模式，讓 Skill 更好引用與討論。我們建議 Skill 名稱用**動名詞形式**（動詞 + -ing），因為它清楚描述該 Skill 提供的活動或能力。

**好的命名範例（動名詞）**：

* 「Processing PDFs」
* 「Analyzing spreadsheets」
* 「Managing databases」
* 「Testing code」
* 「Writing documentation」

**可接受的替代**：

* 名詞片語：「PDF Processing」、「Spreadsheet Analysis」
* 動作導向：「Process PDFs」、「Analyze Spreadsheets」

**避免**：

* 含糊名稱：「Helper」、「Utils」、「Tools」
* 過度泛用：「Documents」、「Data」、「Files」
* 你的 skill 集合內命名不一致

一致的命名讓以下事情更容易：

* 在文件與對話中引用 Skill
* 一眼看懂 Skill 做什麼
* 組織與搜尋多個 Skill
* 維持專業、一致的技巧庫

### 撰寫有效的 description

`description` 欄位決定 Skill 能否被發現，應同時包含「做什麼」與「何時用」。

<Warning>
  **永遠用第三人稱寫**。description 會被注入系統提示，人稱不一致會造成發現問題。

  * **好：**「解析家具風格需求並產出受控詞彙的結構化輸出」
  * **避免：**「我可以幫你解析家具風格需求」
  * **避免：**「你可以用這個來解析家具風格需求」
</Warning>

**具體並包含關鍵詞**。同時寫清楚 Skill 做什麼，以及何時該用的具體觸發點／脈絡。

每個 Skill 只有一個 description 欄位。description 對 Skill 選擇至關重要：Claude 用它從可能上百個 Skill 中挑出正確的那一個。你的 description 必須提供足夠細節讓 Claude 知道何時選它，而 SKILL.md 其餘部分提供實作細節。

有效範例：

**需求解析 skill：**

```yaml  theme={null}
description: 用 claude-haiku-4-5 structured outputs 把自然語言家具需求解析成受控詞彙欄位。當要改 query_parser.py 的 schema、受控詞彙或 HyDE 產生方式時使用。
```

**索引建置 skill：**

```yaml  theme={null}
description: 用 bge-m3 建置並增量更新 ChromaDB furniture_v3 集合與 rag_export 交付檔。當要重建索引、驗證交付檔或處理 text_hash 比對時使用。
```

**Git commit 輔助 skill：**

```yaml  theme={null}
description: 分析 git diff 產生具描述性的 commit 訊息。當使用者請你協助撰寫 commit 訊息或審視 staged 變更時使用。
```

避免以下含糊的 description：

```yaml  theme={null}
description: 幫忙處理文件
```

```yaml  theme={null}
description: 處理資料
```

```yaml  theme={null}
description: 對檔案做一些事
```

### 漸進揭露（Progressive disclosure）模式

SKILL.md 是一份總覽，依需要把 Claude 導向細節資料，就像新人手冊的目錄。漸進揭露如何運作的說明見 overview 的 [How Skills work](/en/docs/agents-and-tools/agent-skills/overview#how-skills-work)。

**實務準則：**

* SKILL.md 本體控制在 500 行以內，效能最佳
* 接近上限時把內容拆到獨立檔案
* 用下列模式來組織指令、程式碼與資源

#### 視覺總覽：從簡單到複雜

最基本的 Skill 只有一個 SKILL.md，包含 metadata 與指令：

<img src="https://mintcdn.com/anthropic-claude-docs/4Bny2bjzuGBK7o00/images/agent-skills-simple-file.png?fit=max&auto=format&n=4Bny2bjzuGBK7o00&q=85&s=87782ff239b297d9a9e8e1b72ed72db9" alt="Simple SKILL.md file showing YAML frontmatter and markdown body" data-og-width="2048" width="2048" data-og-height="1153" height="1153" data-path="images/agent-skills-simple-file.png" data-optimize="true" data-opv="3" />

當 Skill 成長時，你可以附加只在需要時才載入的內容：

<img src="https://mintcdn.com/anthropic-claude-docs/4Bny2bjzuGBK7o00/images/agent-skills-bundling-content.png?fit=max&auto=format&n=4Bny2bjzuGBK7o00&q=85&s=a5e0aa41e3d53985a7e3e43668a33ea3" alt="Bundling additional reference files like reference.md and forms.md." data-og-width="2048" width="2048" data-og-height="1327" height="1327" data-path="images/agent-skills-bundling-content.png" data-optimize="true" data-opv="3" />

完整的 Skill 目錄結構可能像這樣：

```
retrieval/
├── SKILL.md              # 主要指令（觸發時載入）
├── FILTERS.md            # Chroma where 硬過濾指南（依需要載入）
├── reference.md          # bge-m3 / reranker 參數參考（依需要載入）
├── examples.md           # 查詢範例（依需要載入）
└── scripts/
    ├── inspect_index.py  # 工具腳本（執行，不載入）
    ├── smoke_query.py    # 冒煙查詢腳本
    └── validate_export.py # rag_export 交付檔驗證腳本
```

#### 模式 1：高層指南 + 參考連結

````markdown  theme={null}
---
name: Retrieval Tuning
description: 調整 RoomPilot 兩階段檢索（硬過濾 → 向量 → rerank → 加權）的參數與權重。當檢索結果不準、要調整排序權重或除錯 where 過濾時使用。
---

# Retrieval Tuning

## 快速開始

用 CLI 跑一次完整檢索：
```bash
.venv-rag/bin/python rag_pipeline/retriever.py "北歐風客廳沙發，預算三萬"
```

## 進階功能

**硬過濾規則**：完整指南見 [FILTERS.md](FILTERS.md)
**模型參數參考**：所有參數見 [REFERENCE.md](REFERENCE.md)
**查詢範例**：常見模式見 [EXAMPLES.md](EXAMPLES.md)
````

Claude 只在需要時才載入 FILTERS.md、REFERENCE.md 或 EXAMPLES.md。

#### 模式 2：依領域組織

當 Skill 涵蓋多個領域時，依領域組織內容，避免載入不相關的 context。使用者問風格相容度時，Claude 只需要讀風格相關的資料，不需要讀價格或渲染資料。這讓 token 用量低、context 聚焦。

```
furniture-data-skill/
├── SKILL.md（總覽與導覽）
└── reference/
    ├── styles.md（六風格詞表、6×6 相容矩陣）
    ├── categories.md（64 細類 → 19 檢索群組）
    ├── moods.md（24 個氛圍詞、18 張色卡）
    └── pricing.md（中位價、預算分配規則）
```

````markdown SKILL.md theme={null}
# RoomPilot 家具資料

## 可用資料集

**風格**：六風格詞表、style_compat 矩陣 → 見 [reference/styles.md](reference/styles.md)
**類別**：64 細類、19 檢索群組、房型典型組合 → 見 [reference/categories.md](reference/categories.md)
**氛圍／色卡**：24 氛圍詞、18 色卡 → 見 [reference/moods.md](reference/moods.md)
**價格**：中位價、預算分配 → 見 [reference/pricing.md](reference/pricing.md)

## 快速搜尋

用 grep 找特定欄位：

```bash
grep -i "scandinavian" reference/styles.md
grep -i "檢索群組" reference/categories.md
grep -i "侘寂自然" reference/moods.md
```
````

#### 模式 3：條件式細節

先呈現基本內容，把進階內容用連結帶出：

```markdown  theme={null}
# 家具資料集加工

## 建立新版本資料集

用 build_rag_v3.py 從 v2 產生 v3。見 [BUILD-V3.md](BUILD-V3.md)。

## 修改既有欄位

小幅修改可直接編輯 JSON。

**風格重新判定**：見 [RECLASSIFY.md](RECLASSIFY.md)
**SQL 端交付規格**：見 [RAGSQL.md](RAGSQL.md)
```

Claude 只在使用者需要那些功能時才讀 RECLASSIFY.md 或 RAGSQL.md。

### 避免多層巢狀引用

當檔案是從「另一個被引用的檔案」中被引用時，Claude 可能只讀部分內容。遇到巢狀引用時，Claude 可能用 `head -100` 之類的指令預覽，而不是完整讀取，導致資訊不完整。

**所有引用維持在距離 SKILL.md 一層之內**。所有參考檔案都應該直接從 SKILL.md 連出，確保 Claude 需要時能完整讀取。

**壞範例：層數太深**：

```markdown  theme={null}
# SKILL.md
見 [advanced.md](advanced.md)…

# advanced.md
見 [details.md](details.md)…

# details.md
真正的資訊在這裡…
```

**好範例：只有一層**：

```markdown  theme={null}
# SKILL.md

**基本用法**：[寫在 SKILL.md 裡]
**進階功能**：見 [advanced.md](advanced.md)
**API 參考**：見 [reference.md](reference.md)
**範例**：見 [examples.md](examples.md)
```

### 較長的參考檔要加目錄

超過 100 行的參考檔，在最上方加一份目錄。這樣即使 Claude 只是部分預覽，也能看到可用資訊的全貌。

**範例**：

```markdown  theme={null}
# 檢索參數參考

## 目錄
- 環境與模型載入（MPS/CPU、HF_HUB_OFFLINE）
- 核心參數（VEC_TOP_K、RERANK_TOP_K、FINAL_TOP_K）
- 進階功能（配件品項的 RERANK_TOP_K_LIGHT、預算分配）
- 錯誤處理模式
- 程式碼範例

## 環境與模型載入
...

...

## 核心參數
...
```

Claude 之後可以完整讀該檔，或直接跳到特定章節。

關於這種以檔案系統為基礎的架構如何支撐漸進揭露，見下方進階章節的 [Runtime environment](#runtime-environment)。

## 工作流與回饋迴圈

### 複雜任務用工作流

把複雜操作拆成清楚的循序步驟。特別複雜的工作流，提供一份 Claude 可以複製到回覆裡、逐項打勾的檢查清單。

**範例 1：研究綜整工作流**（不含程式碼的 Skill）：

````markdown  theme={null}
## 研究綜整工作流

複製這份檢查清單並追蹤進度：

```
研究進度：
- [ ] Step 1：讀完所有來源文件
- [ ] Step 2：找出關鍵主題
- [ ] Step 3：交叉比對論述
- [ ] Step 4：建立結構化摘要
- [ ] Step 5：驗證引用
```

**Step 1：讀完所有來源文件**

逐一檢視 `docs/` 目錄的文件，記下主要論點與佐證。

**Step 2：找出關鍵主題**

尋找跨來源的模式。哪些主題反覆出現？來源之間在哪裡一致或衝突？

**Step 3：交叉比對論述**

對每個主要論述，確認它確實出現在來源資料中。記下每個論點由哪個來源支持。

**Step 4：建立結構化摘要**

依主題組織發現，包含：
- 主要論述
- 來源中的佐證
- 衝突觀點（若有）

**Step 5：驗證引用**

檢查每個論述都引用了正確的來源文件。若引用不完整，回到 Step 3。
````

這個例子展示工作流也適用於不需要程式碼的分析任務。檢查清單模式適用於任何複雜的多步驟流程。

**範例 2：索引重建工作流**（含程式碼的 Skill）：

````markdown  theme={null}
## 索引重建工作流

複製這份檢查清單，完成一項打勾一項：

```
任務進度：
- [ ] Step 1：檢查資料集差異（跑 build_rag_v3.py --dry-run）
- [ ] Step 2：確認 text_hash 變更筆數
- [ ] Step 3：冒煙建索引（embed_v3.py --limit 50）
- [ ] Step 4：增量建索引（embed_v3.py --only-changed）
- [ ] Step 5：驗證輸出（檢查 rag_export/ 四個交付檔）
```

**Step 1：檢查資料集差異**

跑：`python3 json_adjustment/build_rag_v3.py --dry-run`

這會印出 v2→v3 的加工統計，不會寫檔。

**Step 2：確認 text_hash 變更筆數**

比對後預期只有變動項目需要重算向量（例如 646 筆約 1.5 分鐘）。

**Step 3：冒煙建索引**

跑：`.venv-rag/bin/python rag_pipeline/embed_v3.py --limit 50`

在繼續之前修掉所有錯誤。

**Step 4：增量建索引**

跑：`.venv-rag/bin/python rag_pipeline/embed_v3.py --only-changed`

**Step 5：驗證輸出**

檢查 `rag_export/` 的向量 jsonl、metadata、失敗清單、驗證報告四個檔一致。

若驗證失敗，回到 Step 2。
````

清楚的步驟能防止 Claude 跳過關鍵驗證。檢查清單也幫 Claude 與你一起追蹤多步驟工作流的進度。

### 建立回饋迴圈

**常見模式**：跑驗證器 → 修錯誤 → 重複

這個模式能大幅提升輸出品質。

**範例 1：規格一致性檢查**（不含程式碼的 Skill）：

```markdown  theme={null}
## 內容審查流程

1. 依 docs/query_parser_spec.md 的規範撰寫內容
2. 對照檢查清單審視：
   - 檢查術語一致性（受控詞彙是否與 taxonomy_v2.json 一致）
   - 確認範例符合標準格式
   - 確認所有必要章節都在
3. 若發現問題：
   - 逐項記錄問題並標出章節
   - 修訂內容
   - 再跑一次檢查清單
4. 只有全部符合才能繼續
5. 定稿並存檔
```

這展示了用參考文件（而非腳本）當「驗證器」的迴圈模式：驗證器是 `docs/query_parser_spec.md`，Claude 透過閱讀與比對執行檢查。

**範例 2：資料集加工流程**（含程式碼的 Skill）：

```markdown  theme={null}
## 資料集加工流程

1. 修改 `json_adjustment/build_rag_v3.py` 的加工規則
2. **立即驗證**：`python3 json_adjustment/build_rag_v3.py --dry-run`
3. 若統計不符預期：
   - 仔細看差異數字（分類分布、缺欄位筆數）
   - 修正加工規則
   - 再跑一次 --dry-run
4. **只有驗證通過才能繼續**
5. 正式產生：移除 --dry-run 重跑
6. 用 `.venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` 測試輸出
```

驗證迴圈能提早抓到錯誤。

## 內容準則

### 避免有時效性的資訊

不要寫入將來會過期的資訊：

**壞範例：有時效性**（將來會變錯）：

```markdown  theme={null}
如果你是在 2025 年 8 月之前做這件事，用舊的 API。
2025 年 8 月之後，用新的 API。
```

**好範例**（用「舊模式」章節）：

```markdown  theme={null}
## 目前做法

現役集合為 `furniture_v3`（9,349 筆、cosine、bge-m3 1024 維）

## 舊模式

<details>
<summary>furniture_v2 集合（已退役）</summary>

v2 使用不同的文字組裝方式，且沒有 text_hash 增量欄位。

此集合已不再維護。
</details>
```

「舊模式」章節保留歷史脈絡，又不會弄亂主要內容。

### 使用一致的術語

選定一個詞並全篇貫徹：

**好 — 一致**：

* 一律用「集合（collection）」
* 一律用「欄位（field）」
* 一律用「硬過濾」

**壞 — 不一致**：

* 混用「集合」、「資料表」、「索引」、「庫」
* 混用「欄位」、「屬性」、「鍵」、「參數」
* 混用「硬過濾」、「篩選」、「filter」、「排除」

一致性能幫 Claude 理解並遵循指令。

## 常見模式

### 模板模式

為輸出格式提供模板。嚴格程度依需求調整。

**嚴格要求時**（例如交付格式或資料格式）：

````markdown  theme={null}
## 報表結構

一律使用這個確切模板結構：

```markdown
# [分析標題]

## 執行摘要
[一段話概述關鍵發現]

## 關鍵發現
- 發現 1 與佐證數據
- 發現 2 與佐證數據
- 發現 3 與佐證數據

## 建議
1. 具體可執行的建議
2. 具體可執行的建議
```
````

**彈性指引時**（可以依情況調整）：

````markdown  theme={null}
## 報表結構

以下是合理的預設格式，但請依分析內容自行判斷：

```markdown
# [分析標題]

## 執行摘要
[概述]

## 關鍵發現
[依你的發現調整章節]

## 建議
[依具體脈絡量身撰寫]
```

依分析類型調整章節。
````

### 範例模式

當輸出品質取決於「看過範例」時，就像一般提示工程一樣提供輸入／輸出配對：

````markdown  theme={null}
## Commit 訊息格式

依這些範例產生 commit 訊息：

**範例 1：**
輸入：新增了以 Haiku structured outputs 解析需求的功能
輸出：
```
feat(query-parser): 以 structured outputs 解析家具需求

新增受控詞彙 schema 與 HyDE 語意查詢，一次呼叫兩用
```

**範例 2：**
輸入：修正 rerank 分數被重複套 sigmoid 導致排序失真
輸出：
```
fix(retriever): 移除 rerank 分數重複的 sigmoid

CrossEncoder 已輸出 0-1，再套一次會壓縮分數區間
```

**範例 3：**
輸入：更新相依套件並重構錯誤處理
輸出：
```
chore: 更新相依套件並重構錯誤處理

- 升級 chromadb 至 1.5.9
- 統一各腳本的錯誤訊息格式
```

遵循這個風格：type(scope): 簡短描述，接著詳細說明。
````

範例比純描述更能讓 Claude 理解期望的風格與細節程度。

### 條件式工作流模式

引導 Claude 通過決策點：

```markdown  theme={null}
## 資料集修改工作流

1. 判斷修改類型：

   **要新增項目？** → 走下方「新增流程」
   **要修改既有欄位？** → 走下方「修改流程」

2. 新增流程：
   - 用 build_rag_v3.py 重新產生
   - 從來源重建全部項目
   - 匯出成 furniture_enriched_v3.json

3. 修改流程：
   - 直接修改既有 JSON 欄位
   - 重算受影響項目的 text_hash
   - 每次改動後驗證
   - 用 embed_v3.py --only-changed 增量更新索引
```

<Tip>
  若工作流變得龐大或步驟很多，考慮把它們放到獨立檔案，並告訴 Claude 依當下任務讀取對應檔案。
</Tip>

## 評估與迭代

### 先建立評估

**在寫大量文件之前先建立評估。** 這確保你的 Skill 解決的是真實問題，而不是想像出來的問題。

**評估驅動的開發：**

1. **找出缺口**：在沒有 Skill 的情況下讓 Claude 跑代表性任務，記錄具體失敗或缺少的 context
2. **建立評估**：針對這些缺口做三個情境
3. **建立基準**：測量沒有 Skill 時 Claude 的表現
4. **寫最小指令**：只寫剛好足以填補缺口、通過評估的內容
5. **迭代**：執行評估、對比基準、持續修正

這個方法確保你在解決實際問題，而不是預期一些永遠不會發生的需求。

**評估結構**：

```json  theme={null}
{
  "skills": ["retrieval-tuning"],
  "query": "北歐風客廳沙發，預算三萬以內，要溫暖一點",
  "files": ["rag_dataset/furniture_enriched_v3.json"],
  "expected_behavior": [
    "正確解析出 style=scandinavian、room=living_room、budget_twd=30000、mood 含溫暖類詞",
    "把房型／類別／價格／尺寸放進 Chroma where 硬過濾，風格與氛圍只做軟加權",
    "回傳 8 筆結果、主導風格收斂且無重複品項"
  ]
}
```

<Note>
  這個例子展示以資料驅動、附簡單評分準則的評估。我們目前沒有提供內建的評估執行工具，使用者可自建評估系統。評估是衡量 Skill 效果的事實來源。
</Note>

### 與 Claude 一起迭代開發 Skill

最有效的 Skill 開發流程會把 Claude 本身納入。你與一個 Claude 實例（「Claude A」）合作建立 Skill，這個 Skill 會被其他實例（「Claude B」）使用。Claude A 幫你設計與精修指令，Claude B 在真實任務中測試它們。這有效是因為 Claude 模型同時理解「如何寫出有效的 agent 指令」與「agent 需要什麼資訊」。

**建立新 Skill：**

1. **先在沒有 Skill 的情況下完成一次任務**：用一般提示與 Claude A 一起解決問題。過程中你自然會提供 context、解釋偏好、分享程序性知識。留意你反覆提供了哪些資訊。

2. **找出可重用的模式**：任務完成後，找出你提供過、且對未來類似任務有用的 context。

   **範例**：如果你剛做完一次檢索調參，你可能提供了集合名稱、欄位定義、過濾規則（像「`rag_indexable` 不能寫進 `where`」）與常用查詢模式。

3. **請 Claude A 建立 Skill**：「幫我把剛剛這套檢索調參模式做成一個 Skill。包含集合欄位、命名慣例，以及 rag_indexable 不能進 where 的規則。」

   <Tip>
     Claude 模型原生就理解 Skill 的格式與結構。你不需要特殊系統提示或「撰寫 skill」的 skill 才能請 Claude 幫忙建立 Skill。直接請它建立，它就會產出結構正確、frontmatter 與內容齊備的 SKILL.md。
   </Tip>

4. **檢查是否精簡**：確認 Claude A 沒有加入不必要的解釋。可以說：「把『什麼是 cosine 相似度』那段刪掉——Claude 已經知道了。」

5. **改善資訊架構**：請 Claude A 更有效地組織內容。例如：「把六風格詞表整理到獨立參考檔，之後可能會加更多風格。」

6. **在類似任務上測試**：用 Claude B（載入該 Skill 的全新實例）處理相關案例。觀察 Claude B 是否找到正確資訊、正確套用規則、順利完成任務。

7. **依觀察迭代**：若 Claude B 卡住或漏掉東西，帶著具體情形回到 Claude A：「Claude 用這個 Skill 時，忘了把尺寸當硬過濾。要不要加一段講硬過濾與軟加權的界線？」

**迭代既有 Skill：**

同樣的階層模式也適用於改善 Skill。你在以下兩者之間輪替：

* **與 Claude A 合作**（幫你精修 Skill 的專家）
* **用 Claude B 測試**（使用 Skill 執行真實工作的 agent）
* **觀察 Claude B 的行為**，再把洞察帶回 Claude A

1. **在真實工作流中使用 Skill**：給 Claude B（已載入 Skill）真正的任務，而不是測試題

2. **觀察 Claude B 的行為**：記下它在哪裡卡住、成功，或做了意外的選擇

   **觀察範例**：「我請 Claude B 找一組日式臥室家具，它寫了查詢但忘了套用預算硬過濾，儘管 Skill 有提到這條規則。」

3. **回到 Claude A 求改進**：分享目前的 SKILL.md 並描述你觀察到的現象。問：「我發現 Claude B 在查臥室家具時忘了預算過濾。Skill 有提到過濾，但也許不夠醒目？」

4. **檢視 Claude A 的建議**：Claude A 可能建議重新排版讓規則更醒目、用更強的語氣（把「一律過濾」改成「必須過濾」），或重構工作流章節。

5. **套用並測試改動**：用 Claude A 的修正更新 Skill，再用類似請求測試 Claude B

6. **依實際使用重複**：遇到新情境就持續這個「觀察—精修—測試」循環。每次迭代都是依真實 agent 行為改善 Skill，而不是依假設。

**蒐集團隊回饋：**

1. 把 Skill 分享給隊友並觀察他們的使用情形
2. 詢問：Skill 有在預期時機啟動嗎？指令清楚嗎？缺了什麼？
3. 把回饋納入，補上你自己使用習慣的盲點

**為何這個方法有效**：Claude A 理解 agent 的需求、你提供領域專業、Claude B 透過真實使用暴露缺口，而迭代精修讓 Skill 建立在觀察到的行為上，而非假設上。

### 觀察 Claude 如何在 Skill 中導航

迭代 Skill 時，注意 Claude 實際上怎麼使用它們。留意：

* **意料之外的探索路徑**：Claude 是否用你沒預期的順序讀檔？這可能表示你的結構沒有你以為的直覺
* **錯過的連結**：Claude 是否沒有跟著引用去讀重要檔案？你的連結可能需要更明確或更醒目
* **過度依賴某些章節**：如果 Claude 反覆讀同一個檔案，考慮把那些內容搬進主 SKILL.md
* **被忽略的內容**：如果 Claude 從來不去讀某個附加檔案，它可能沒必要存在，或在主指令中的訊號不足

依這些觀察迭代，而不是依假設。Skill metadata 中的 `name` 與 `description` 特別關鍵——Claude 用它們決定是否要在當下任務啟動這個 Skill。務必讓它們清楚描述 Skill 做什麼、何時該用。

## 要避免的反模式

### 避免 Windows 風格路徑

檔案路徑一律用正斜線，即使在 Windows 上：

* ✓ **好**：`scripts/helper.py`、`reference/guide.md`
* ✗ **避免**：`scripts\helper.py`、`reference\guide.md`

Unix 風格路徑在所有平台都能用，Windows 風格路徑在 Unix 系統會出錯。（本專案只跑 macOS。）

### 避免提供太多選項

除非必要，不要同時提出多種做法：

````markdown  theme={null}
**壞範例：選項太多**（令人困惑）：
「你可以用 bge-reranker-v2-m3，或 ms-marco MiniLM，或 bge-reranker-base，或 cohere rerank，或…」

**好範例：給一個預設**（附逃生門）：
「重排一律用 bge-reranker-v2-m3：
```python
from sentence_transformers import CrossEncoder
reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
```

配件品項候選較少時，把 RERANK_TOP_K 降為 RERANK_TOP_K_LIGHT（12）以降低延遲。」
````

## 進階：含可執行程式碼的 Skill

以下章節聚焦於包含可執行腳本的 Skill。若你的 Skill 只有 markdown 指令，可直接跳到 [有效 Skill 檢查清單](#checklist-for-effective-skills)。

### 解決問題，不要把問題丟回給 Claude

為 Skill 撰寫腳本時，要處理錯誤狀況，而不是把問題丟回給 Claude。

**好範例：明確處理錯誤**：

```python  theme={null}
def load_taxonomy(path):
    """載入六風格詞表；檔案缺失或損毀時退回內建預設。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # 找不到就用內建的最小詞表，而不是直接失敗
        print(f"找不到 {path}，改用內建六風格預設")
        return {"styles": DEFAULT_STYLES, "style_compat": DEFAULT_COMPAT}
    except json.JSONDecodeError as err:
        # 提供替代方案而不是直接失敗
        print(f"{path} 解析失敗（{err}），改用內建六風格預設")
        return {"styles": DEFAULT_STYLES, "style_compat": DEFAULT_COMPAT}
```

**壞範例：丟回給 Claude**：

```python  theme={null}
def load_taxonomy(path):
    # 直接爆掉，讓 Claude 自己想辦法
    return json.load(open(path))
```

設定參數也應該有理由並寫明，避免「巫毒常數」（Ousterhout 法則）。如果你都不知道正確值是多少，Claude 怎麼會知道？

**好範例：自我說明**：

```python  theme={null}
# cross-encoder 每 50 筆約 10 秒，是延遲主因
# 20 筆在品質與延遲之間取得平衡，且去重後仍 > FINAL_TOP_K
RERANK_TOP_K = 20

# 最終呈現 8 張卡片，剛好填滿一個 Gradio 版面
# 去重與主導風格收斂後仍能穩定湊滿 8 筆
FINAL_TOP_K = 8
```

**壞範例：魔術數字**：

```python  theme={null}
TOP_K = 47   # 為什麼是 47？
SLACK = 5    # 為什麼是 5？
```

### 提供工具腳本

即使 Claude 有能力自己寫腳本，預先做好的腳本仍有優勢：

**工具腳本的好處**：

* 比生成的程式碼更可靠
* 省 token（不用把程式碼放進 context）
* 省時間（不用生成程式碼）
* 確保每次使用都一致

<img src="https://mintcdn.com/anthropic-claude-docs/4Bny2bjzuGBK7o00/images/agent-skills-executable-scripts.png?fit=max&auto=format&n=4Bny2bjzuGBK7o00&q=85&s=4bbc45f2c2e0bee9f2f0d5da669bad00" alt="Bundling executable scripts alongside instruction files" data-og-width="2048" width="2048" data-og-height="1154" height="1154" data-path="images/agent-skills-executable-scripts.png" data-optimize="true" data-opv="3" />

上圖顯示可執行腳本如何與指令檔搭配。指令檔（filters.md）引用腳本，Claude 可以直接執行它而不必把內容載入 context。

**重要區別**：在指令中講清楚 Claude 應該：

* **執行腳本**（最常見）：「跑 `inspect_index.py` 檢查集合筆數」
* **當參考來讀**（複雜邏輯時）：「見 `inspect_index.py` 了解 metadata 展平演算法」

多數工具腳本建議用執行的方式，因為更可靠也更省。腳本執行的細節見下方 [Runtime environment](#runtime-environment)。

**範例**：

````markdown  theme={null}
## 工具腳本

**inspect_index.py**：檢查 Chroma 集合的筆數與欄位

```bash
.venv-rag/bin/python scripts/inspect_index.py > index_stats.json
```

輸出格式：
```json
{
  "collection": "furniture_v3",
  "count": 9349,
  "metadata_fields": ["category_final", "room", "price_twd", "style_primary"]
}
```

**validate_export.py**：檢查 rag_export/ 四個交付檔是否一致

```bash
.venv-rag/bin/python scripts/validate_export.py rag_export/
# 回傳 "OK" 或列出不一致項
```

**smoke_query.py**：對集合跑一組固定查詢

```bash
.venv-rag/bin/python scripts/smoke_query.py "北歐風客廳沙發" --top-k 8
```
````

### 使用視覺分析

當輸入可以被渲染成圖片時，讓 Claude 直接分析圖片：

````markdown  theme={null}
## 家具外觀分析

1. 取出品項的正面渲染圖：
   ```bash
   .venv-rag/bin/python scripts/collect_front_renders.py <item_id>
   ```

2. 分析每張正面圖以判定材質、顏色與風格傾向
3. Claude 能以視覺理解外觀特徵（這正是 vlm_annotation/ 的標註流程）
````

<Note>
  在這個例子中，`collect_front_renders.py` 需要你自己撰寫（可參考 `vlm_annotation/build_render_meta_full.py`）。
</Note>

Claude 的視覺能力有助於理解版面與結構。

### 建立可驗證的中間產物

當 Claude 執行複雜、開放性的任務時可能犯錯。「計畫—驗證—執行」模式能提早抓錯：先讓 Claude 以結構化格式產出計畫，用腳本驗證計畫，再執行。

**範例**：想像你請 Claude 依一份試算表更新 500 個品項的風格標籤。沒有驗證的話，Claude 可能引用不存在的風格值、產生互相矛盾的標籤、漏掉必填欄位，或套錯項目。

**解法**：沿用上面的工作流模式（索引重建），但加入一個中間的 `changes.json`，在套用前先驗證。流程變成：分析 → **產出計畫檔** → **驗證計畫** → 執行 → 驗證結果。

**這個模式為何有效：**

* **提早抓錯**：驗證在改動套用之前就找出問題
* **可機器驗證**：腳本提供客觀檢查
* **計畫可回溯**：Claude 可以反覆修改計畫而不動到原始資料
* **除錯清楚**：錯誤訊息直指具體問題

**何時使用**：批次操作、破壞性改動、複雜驗證規則、高風險操作（例如全量重跑索引或全量風格判定，後者要燒約 US$7）。

**實作提示**：讓驗證腳本輸出詳細具體的錯誤訊息，例如「風格值 'nordic' 不存在。可用值：scandinavian, japanese, modern\_minimal, cream, industrial, american」，幫助 Claude 修正問題。

### 套件相依

Skill 在程式碼執行環境中運行，各平台有不同限制：

* **claude.ai**：可從 PyPI 安裝套件，並從 GitHub 儲存庫取得程式碼
* **Anthropic API**：無網路存取、無執行期套件安裝

在 SKILL.md 列出必要套件，並確認它們在 [code execution tool 文件](/en/docs/agents-and-tools/tool-use/code-execution-tool) 中可用。
（本專案的套件一律裝在 `.venv-rag/`；模型權重採離線模式，程式已 `setdefault("HF_HUB_OFFLINE", "1")`。）

### 執行環境（Runtime environment）

Skill 在具備檔案系統存取、bash 指令與程式碼執行能力的環境中運行。這個架構的概念說明見 overview 的 [The Skills architecture](/en/docs/agents-and-tools/agent-skills/overview#the-skills-architecture)。

**這對你的撰寫有什麼影響：**

**Claude 如何存取 Skill：**

1. **Metadata 預載**：啟動時，所有 Skill 的 YAML frontmatter 的 name 與 description 會載入系統提示
2. **檔案按需讀取**：Claude 需要時才用工具從檔案系統讀 SKILL.md 與其他檔案
3. **腳本高效執行**：工具腳本可透過 bash 執行而不必把內容載入 context，只有輸出會消耗 token
4. **大檔案沒有 context 代價**：參考檔、資料或文件在真正被讀取前不佔 context

* **檔案路徑很重要**：Claude 會像瀏覽檔案系統一樣導航你的 skill 目錄。用正斜線（`reference/guide.md`），不要用反斜線
* **檔名要有描述性**：用能表達內容的名稱：`chroma_where_rules.md`，不要用 `doc2.md`
* **為了被發現而組織**：依領域或功能安排目錄
  * 好：`reference/styles.md`、`reference/categories.md`
  * 壞：`docs/file1.md`、`docs/file2.md`
* **附上完整資源**：完整 API 文件、大量範例、大型資料集都可以放，未被讀取前不佔 context
* **確定性操作優先用腳本**：寫 `validate_export.py`，而不是每次請 Claude 生成驗證程式碼
* **講清楚執行意圖**：
  * 「跑 `inspect_index.py` 檢查集合」（執行）
  * 「見 `inspect_index.py` 了解展平演算法」（當參考讀）
* **測試檔案存取模式**：用真實請求測試 Claude 能否在你的目錄結構中導航

**範例：**

```
furniture-data-skill/
├── SKILL.md（總覽，指向各參考檔）
└── reference/
    ├── styles.md（六風格與相容矩陣）
    ├── categories.md（64 細類 → 19 群組）
    └── pricing.md（中位價與預算分配）
```

當使用者問風格相容度時，Claude 讀 SKILL.md、看到指向 `reference/styles.md` 的連結，再用 bash 只讀那一個檔。`categories.md` 與 `pricing.md` 留在檔案系統上，在需要之前消耗零 context。這種以檔案系統為基礎的模型正是漸進揭露的關鍵：Claude 能導航並選擇性載入每個任務真正需要的東西。

完整技術架構細節見 Skills overview 的 [How Skills work](/en/docs/agents-and-tools/agent-skills/overview#how-skills-work)。

### MCP 工具引用

若你的 Skill 使用 MCP（Model Context Protocol）工具，一律用完整限定的工具名稱，避免「找不到工具」的錯誤。

**格式**：`ServerName:tool_name`

**範例**：

```markdown  theme={null}
用 firecrawl:firecrawl_search 工具搜尋外部資料。
用 exa:crawling_exa 工具抓取指定頁面的完整內容。
```

其中：

* `firecrawl` 與 `exa` 是 MCP server 名稱
* `firecrawl_search` 與 `crawling_exa` 是該 server 內的工具名稱

沒有 server 前綴時，Claude 可能找不到工具，尤其在同時有多個 MCP server 時。

### 不要假設工具已安裝

不要假設套件一定可用：

````markdown  theme={null}
**壞範例：假設已安裝**：
「用 chromadb 讀取集合。」

**好範例：明確說明相依**：
「安裝必要套件：`.venv-rag/bin/pip install chromadb`

然後使用：
```python
import chromadb
client = chromadb.PersistentClient("chroma_db")
col = client.get_collection("furniture_v3")
```」
````

## 技術備註

### YAML frontmatter 需求

SKILL.md 的 frontmatter 需要 `name`（上限 64 字元）與 `description`（上限 1024 字元）。完整結構細節見 [Skills overview](/en/docs/agents-and-tools/agent-skills/overview#skill-structure)。

### Token 預算

SKILL.md 本體控制在 500 行以內效能最佳。內容超過時，用前述的漸進揭露模式拆成獨立檔案。架構細節見 [Skills overview](/en/docs/agents-and-tools/agent-skills/overview#how-skills-work)。

## 有效 Skill 檢查清單

分享 Skill 之前，確認：

### 核心品質

* [ ] description 具體且包含關鍵詞
* [ ] description 同時說明 Skill 做什麼與何時使用
* [ ] SKILL.md 本體在 500 行以內
* [ ] 額外細節放在獨立檔案（若有需要）
* [ ] 沒有時效性資訊（或已放進「舊模式」章節）
* [ ] 全篇術語一致
* [ ] 範例具體，不抽象
* [ ] 檔案引用只有一層深
* [ ] 適當使用漸進揭露
* [ ] 工作流步驟清楚

### 程式碼與腳本

* [ ] 腳本自己解決問題，不把問題丟回 Claude
* [ ] 錯誤處理明確且有幫助
* [ ] 沒有「巫毒常數」（所有數值都有理由）
* [ ] 必要套件已在指令中列出且確認可用（本專案裝於 `.venv-rag/`）
* [ ] 腳本有清楚文件
* [ ] 沒有 Windows 風格路徑（全用正斜線）
* [ ] 關鍵操作有驗證／確認步驟
* [ ] 品質關鍵的任務有回饋迴圈

### 測試

* [ ] 至少建立三個評估
* [ ] 已用 Haiku、Sonnet、Opus 測試
* [ ] 已用真實使用情境測試
* [ ] 已納入團隊回饋（若適用）

## 下一步

<CardGroup cols={2}>
  <Card title="Get started with Agent Skills" icon="rocket" href="/en/docs/agents-and-tools/agent-skills/quickstart">
    建立你的第一個 Skill
  </Card>

  <Card title="Use Skills in Claude Code" icon="terminal" href="/en/docs/claude-code/skills">
    在 Claude Code 中建立與管理 Skill
  </Card>

  <Card title="Use Skills with the API" icon="code" href="/en/api/skills-guide">
    以程式方式上傳與使用 Skill
  </Card>
</CardGroup>
