---
name: roompilot-furniture-query
description: RoomPilot 專屬室內設計需求轉譯 skill — 把屋主的口語房間描述，轉成 RAG 檢索器聽得懂的受控詞彙檢索句，餵給 POST /api/rag/search 的 query。涵蓋六風格十八色卡、24 氛圍詞、19 家具群組的對映規則，以及硬過濾／軟加權界線與撈不到時的放寬順序。當使用者用日常語言描述想要的房間或家具、要挑家具、抱怨檢索結果不準或撈不到東西時使用。
origin: RoomPilot-Agent 專案原生
---

<!-- 繁中：本 skill 只負責「需求 → 檢索句」的轉譯。不做幾何可行性、不改後端 parser prompt、不繞過既有 API。 -->

# RoomPilot Furniture Query

> 檢索管線實作：`backend/spatial_data/rag/`（owner: Django）
> 對外入口：`POST /api/rag/search`（`backend/server/rag_api.py`，owner: Bella）
> 受控詞彙表：`references/vocabulary.md`
> 口語對映與範例：`references/translation-patterns.md`

## 這個 skill 存在的理由

屋主說的是「想弄成日本那種很空、有木頭的客廳，沙發不要太大」。
檢索器吃的是六個風格 enum、24 個氛圍詞、19 個家具群組，加上一段模仿索引文本句式的描述。

中間這段翻譯目前**沒有寫在任何地方**——`build_system_prompt()` 只約束解析器怎麼填欄位，
沒有人負責「屋主的話該怎麼說出口」。同一個需求換個講法，撈到的東西可以差很多。
本 skill 就是那份轉譯規則：**讓 agent 每次都用同一套受控詞彙把話說對，一次就命中。**

## 何時啟動

- 使用者用日常語言描述想要的房間、風格、氛圍，要系統幫忙挑家具
- 要呼叫 `POST /api/rag/search` 或第 6 步家具選配，需要決定 `query` 怎麼寫
- 檢索結果不準、太發散、或回傳 0 筆，要診斷是查詢寫法還是資料問題
- 要把問卷／`scene_json.render_context` 的需求轉成家具檢索條件

## 邊界：這個 skill 不做什麼

| 不做 | 誰做 |
| :--- | :--- |
| 判斷家具擺不擺得下、會不會擋門窗 | `backend/engine/`（Ancai）。檢索只解決「找到合適物件」 |
| 改 `openai_parser.py` 的 `build_system_prompt()` | Django 的後端變更，需走 owner 流程與兩端測試 |
| 直接寫 SQL 或繞過 `/api/rag/search` | `backend/catalog/rag_repository.py`（Kai） |
| 決定家電（冰箱、洗衣機、冷氣） | 家電留在問卷與 `render_context` 供第 8 步生圖，**不進家具型錄** |

轉譯錯了就重寫檢索句，**不要**改硬過濾以外的東西來遷就結果。

---

## 系統怎麼吃這句話

```
query 字串（本 skill 的產出，≤1000 字）
   │
   │ ① parser（LLM structured output）→ RagQueryPlan
   ▼
{room_type, styles[≤2], moods[≤3], pattern, color_hint, material_hint,
 price_level, budget_total, is_set, items[1-6]{category_group, semantic_query,
 price_max, max_width_cm, max_height_cm, role, size_hint}}
   │
   ├── 硬過濾 → pgvector search_furniture_embeddings_filtered()
   │   room_type / categories / price / max_width_cm / max_height_cm / role / size_class
   │
   ├── bge-m3 向量檢索 top 50 → bge-reranker-v2-m3 重排
   │
   └── 加權排序 final = 0.60×rerank + 0.20×style_compat + 0.10×mood命中率 + 0.10×confidence
                                                                （ranking.py:16）
```

**這條界線決定一切**：

| 條件 | 處理 | 寫錯的後果 |
| :--- | :--- | :--- |
| 房型、類別、價格、**尺寸**、role、size | **硬過濾** | 猜錯 → 正確結果直接被砍掉，永遠撈不回來 |
| 風格、色卡、氛圍 | **軟加權** | 寫偏 → 排序變差，但東西還在 |
| 顏色、材質、圖樣、造型 | **只進語意向量** | 顏色 317 種、材質 700+ 種，字串比對必敗 |

推論：**保守填硬過濾，大方寫軟條件。** 屋主沒說的尺寸和價格，一個字都不要寫。

---

## 轉譯工作流

### 步驟 1：聽出五件事

從屋主的話裡分離出這五類，缺的就是缺的，**不要腦補**：

| 要素 | 屋主可能怎麼說 | 對應 |
| :--- | :--- | :--- |
| 空間 | 「客廳」「主臥」「小孩房」 | `room_type`（硬過濾，只能一個） |
| 調性 | 「日本那種」「很空」「木頭感」 | 風格 + 色卡 + 氛圍（軟加權） |
| 品項 | 「沙發」「一組客廳」 | `category_group`（硬過濾） |
| 約束 | 「兩萬以內」「牆面只有 180 公分」 | 價格、尺寸（硬過濾，**只在明講時**） |
| 感受 | 「不要太大」「看起來舒服」 | 造型／量體描述，寫進語意句，**不轉成公分** |

### 步驟 2：對映到受控詞彙

查 `references/vocabulary.md`，把口語換成詞表裡**存在的**詞。
常見對映與陷阱在 `references/translation-patterns.md`，先讀那份再動手。

三個高頻錯誤：

1. **氛圍詞必須逐字命中。** `mood_score` 是集合交集（`ranking.py:98`），「溫暖」不等於「溫馨」，
   寫錯就是 0 分，不會模糊比對。
2. **風格只有 6 個。** 「中古世紀」「波希米亞」「法式鄉村」在現行分類**不存在**
   （舊 12 風格有 33.6% 找不到對應），要主動選最接近的並告訴使用者你換了詞。
3. **色卡名是強訊號。** 18 個色卡名有寫進索引文本（`embedded_text` 的「色卡：」欄），
   講「侘寂自然色卡」比講「日式」精準得多。

### 步驟 3：決定哪些進硬過濾

逐項自問「屋主真的講了嗎」：

- [ ] 房型 — 明確說了才寫。說「家裡」不算。
- [ ] 品項 — 說了「沙發」就寫 sofa；只給風格不給品項，就**不寫任何品項詞**，讓它跨類別檢索。
- [ ] 價格 — 具體金額（「兩萬以內」）與相對詞（「便宜一點」）**擇一**，不要同時出現。
- [ ] 尺寸 — ★ 只有屋主親口說了公分數才寫。**這是本系統踩過最貴的坑**：
      模型憑常識填「沙發應該 220 公分寬」，硬過濾當場砍掉所有正確結果。

### 步驟 4：組出檢索句

固定順序，用中文全形分隔，風格同時寫**英文 id + 中文名**（前者幫解析器命中 enum，後者幫向量檢索）：

```
[房型]，[風格 id 中文名]、[色卡名]色卡，[氛圍1／氛圍2／氛圍3]；
要[數量][品項]；[材質、顏色、造型、量體描述]；[價格]
```

實例：

```
屋主：「想弄成日本那種很空、有木頭的客廳，沙發不要太大」

query = "客廳，japanese 日式、侘寂自然色卡，寧靜／自然／溫潤；要一張沙發；
淺色實木框架搭配米白亞麻布，低矮貼地量體、線條乾淨、素色，留白感強"
```

注意這句**沒有公分數**——屋主說「不要太大」，那是量體感受，寫進語意描述，不是硬過濾。

語意描述那段請模仿索引文本的句式（名稱／類別／顏色／材質／風格／色卡／氛圍／造型／描述），
30–120 字，**不要放價格與尺寸**（解析器規則 7）。詳細句式在 `references/vocabulary.md`。

### 步驟 5：校驗

```bash
python3 .claude/skills/roompilot-furniture-query/lint_query.py "客廳，japanese 日式、侘寂自然色卡…"
python3 .claude/skills/roompilot-furniture-query/lint_query.py --file query.txt --strict
```

腳本讀 `backend/spatial_data/rag/data/` 的真實詞表比對，輸出 PASS / WARN / FAIL：

- **FAIL** → 送出前必修（空字串、超過 1000 字、出現未經屋主確認的尺寸數字）。退出碼 1。
  尺寸確實是屋主給的，加 `--sized-by-client` 放行。
- **WARN** → 逐項判讀：詞不在詞表、風格超過 2 個、氛圍近義詞沒對上、提到家電或非型錄品項。

### 步驟 6：送出與判讀

```bash
curl -s localhost:8000/api/rag/search -H 'content-type: application/json' \
  -d '{"query": "…", "top_k": 8}' | python3 -m json.tool
```

回傳每筆有 `scores.{final, rerank, style, mood, confidence}`。**看分數診斷，不要瞎改**：

| 症狀 | 讀哪個分數 | 修法 |
| :--- | :--- | :--- |
| 回 0 筆 | — | 硬過濾太緊。依序放寬：**尺寸 → 價格 → 品項 → 房型**（尺寸最常是元兇） |
| 東西對但風格不對 | `style` 偏低 | 補色卡名、把風格寫在句首、確認沒混入第二個相斥風格 |
| 風格對但品項亂 | 品項沒寫或寫太模糊 | 補明確的群組詞（見詞表 19 群組） |
| 結果太發散 | `rerank` 普遍低 | 語意描述太短或太抽象，補材質、顏色、造型 |
| 全部很像、缺變化 | — | 同款不同色只靠 `duplicate_group` 去重，177 筆有標，其餘仍可能並列 |

**放寬順序不能顛倒**：先拿掉尺寸，再拿掉價格。房型是最後才動的——
拿掉房型會讓客廳需求撈到浴室物件。

### 步驟 7：該追問就追問，但先給結果

解析器 `needs_clarification=true` 時**照樣有結果**，絕不給空畫面。
你也一樣：先把最合理的解讀送出去、把東西攤在屋主面前，再問那一個問題。
「想找便宜一點的椅子」→ 先撈平價單椅，同時問「餐椅、辦公椅，還是客廳扶手椅？」

---

## 鐵律

1. **屋主沒說的尺寸，一個數字都不要寫。** 硬過濾猜錯 = 正確答案永久消失。
2. **氛圍詞逐字照抄詞表 24 個。** 集合交集不做模糊比對。
3. **風格最多 2 個、氛圍最多 3 個。** 超過會被截掉，而且相斥風格互相稀釋
   （cream↔industrial 相容度 0.2）。
4. **只給風格不給品項時，不要硬塞品項。** 讓 `category_group=null` 跨類別檢索，
   比猜錯類別好。
5. **成套配置要說「一整組」並給總預算**，預算會依各群組中位價比例分配（不是平均分），
   再乘 1.3 寬容係數。
6. **家電不是家具。** 冰箱、洗衣機、冷氣、電視機不在型錄，屬問卷與 `render_context`。
7. **換過的詞要告訴使用者。** 把「波希米亞」換成 scandinavian 時要講，不要默默改。

## 運作模式

| 模式 | 時機 | 動作 |
| :--- | :--- | :--- |
| **轉譯** | 屋主給了口語需求 | 步驟 1–5 產出檢索句，跑 lint，說明換了哪些詞 |
| **診斷** | 結果不準或 0 筆 | 讀 `scores` → 對照上表 → 依放寬順序改寫，一次只動一個條件 |
| **成套** | 「幫我配一整組」 | 帶總預算與 `is_set` 語意，檢查推論品項是否合房型（已知會夾帶不合適品項） |

## 驗證與退出標準

```bash
python3 .claude/skills/roompilot-furniture-query/lint_query.py "<檢索句>"   # FAIL=0
curl -s localhost:8000/api/rag/search -d '{"query":"…","top_k":8}'  # 回傳 > 0 筆
```

- 改寫檢索句後要**實際重跑並比對**前後筆數與 `scores.final`，不要只憑感覺說變好了。
- 詞表若與 `backend/spatial_data/rag/data/*.json` 不符，**以檔案為準**並更新
  `references/vocabulary.md`（lint 腳本讀的是檔案，會先抓到）。
- 需求同時涉及擺放可行性時，檢索只給候選，可行性交 `backend/engine/`，不要在這裡下判斷。
