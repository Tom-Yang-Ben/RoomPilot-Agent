# Architecture Review Terminology Reference

> 100 條軟體工程行話分類索引。**預設不載入 context** — 由 reviewer 在 SKILL.md 三階段流程中按需查詢。
>
> **使用方式**：
> - Phase 1 (Detect Smells) → 查 §1 Smells & Anti-Patterns
> - Phase 2 (Map to Principles) → 查 §2 Principles
> - Phase 3 (Propose Fixes) → 查 §3 Patterns / §4 Reliability Patterns / §5 Practices
>
> 每條格式：**編號 / 中文 / English** — 類型 — 一行解釋 — 對策／使用要點。
>
> **本詞彙表刻意維持通用**（它是共通行話的標準索引，不隨專案改寫），
> RoomPilot 的落點另見文末〈RoomPilot 適用性對照〉：哪些詞在本專案有實際對應物、
> 哪些是**目前不適用**（單機、無訊息佇列、無 CI、無容器編排）而不該硬套。

---

## §1 Smells & Anti-Patterns（#1–#25）

審查時用來「命名病灶」。每個 finding 必須引用此節中的標準名稱，禁止自創。

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 1 | 壞味道 / Code Smell | Smell | 程式設計上可疑的結構信號 | 以小步重構消除 |
| 2 | 特性嫉妒 / Feature Envy | Smell | 某方法過度關心別的物件資料 | Move Method、引入服務 |
| 3 | 上帝物件 / God Object | Anti-Pattern | 單一類別知道／做太多 | 切分職責，套用 SRP |
| 4 | 巨型方法 / Long Method | Smell | 方法太長難理解 | Extract Method |
| 5 | 巨型類別 / Large Class | Smell | 類別承載過多職責 | 拆模組、引入聚合根 |
| 6 | 過長參數列 / Long Parameter List | Smell | 參數太多、可讀性差 | 引入參數物件 (Parameter Object) |
| 7 | 基本型別偏執 / Primitive Obsession | Smell | 用原始型別表達複雜概念 | Value Object |
| 8 | 重複程式碼 / Duplicated Code | Smell | 同樣邏輯散落多處 | 抽取共用元件／函式 (DRY) |
| 9 | 訊息鏈 / Message Chains | Smell | `a.b().c().d()` 連鎖 | 引入門面 (Facade)／包裝器 |
| 10 | 中間人 / Middle Man | Smell | 類別只轉呼叫沒價值 | 移除／直連協作者 |
| 11 | 註解味道 / Comments Smell | Smell | 用註解掩蓋糟設計 | 以程式表意、重命名 |
| 12 | 拒絕繼承 / Refused Bequest | Smell | 子類不想要父類行為 | 以組合代替繼承 |
| 13 | 不當親密 / Inappropriate Intimacy | Smell | 模組彼此過度耦合 | 介面隔離、界限上下文 |
| 14 | 過度一般化 / Speculative Generality | Smell | 為未來預留過多彈性 | YAGNI 清理、Inline 化 |
| 15 | 暫時欄位 / Temporary Field | Smell | 僅在部份情境才用的欄位 | 提取成特定物件 |
| 16 | 發散式變更 / Divergent Change | Smell | 一改動需改同模組多處 | 重構以單一變更原因 |
| 17 | 霰彈式修改 / Shotgun Surgery | Smell | 小改動波及多模組 | 聚合相關行為 |
| 18 | 過度使用 switch / Switch Statements | Smell | 以條件分支取代多型 | Strategy / 多型重構 |
| 19 | 平行繼承體系 / Parallel Inheritance | Smell | 兩樹狀繼承需同步改 | 以組合／介面整合 |
| 20 | 資料團塊 / Data Clumps | Smell | 總是成對／成組出現的資料 | 封裝為物件 |
| 21 | 循環相依 / Cyclic Dependency | Anti-Pattern | 模組互相依賴成圈 | 依賴反轉 (DIP)、分層 |
| 22 | 大泥球 / Big Ball of Mud | Anti-Pattern | 無明確架構的系統 | 建立界限、分割上下文 |
| 23 | 義大利麵碼 / Spaghetti Code | Anti-Pattern | 控制流程糾結難懂 | 重構流程、引入模式 |
| 24 | 熔岩流 / Lava Flow | Anti-Pattern | 難移除的遺留殘渣 | 清理／封存／Strangler Fig |
| 25 | 金錘子 / Golden Hammer | Anti-Pattern | 單一解法打天下 | 依脈絡選型 |

---

## §2 Principles（#26–#39）

審查 Phase 2 反向對應。每個 smell 必須關聯至少一條此節原則。

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 26 | 單一職責 / SRP | Principle | 一模組僅一變更理由 | 以職責切分 |
| 27 | 開放封閉 / OCP | Principle | 對擴展開放、對修改封閉 | 抽象化、外掛化 |
| 28 | 里氏替換 / LSP | Principle | 子類可替換父類 | 保持行為契約 |
| 29 | 介面隔離 / ISP | Principle | 小而專注的介面 | 拆分胖介面 |
| 30 | 依賴反轉 / DIP | Principle | 依賴抽象不依賴具體 | DI 容器／注入 |
| 31 | KISS | Principle | 保持簡單避免複雜 | 先解最小問題 |
| 32 | DRY | Principle | 不要重複你自己 | 抽共用、模板化 |
| 33 | YAGNI | Principle | 你不會需要它 | 延後到需求出現 |
| 34 | 得墨忒耳律 / LoD | Principle | 只與直接朋友說話 | 減少耦合 |
| 35 | Tell, Don't Ask | Principle | 告知物件做什麼別抽資料 | 封裝行為 |
| 36 | 童子軍法則 / Boy Scout Rule | Practice | 離開時讓程式比來時更好 | 小步持續改善 |
| 37 | 乾淨架構 / Clean Architecture | Principle | 內核與外界隔離、依賴向內 | 用邊界／用例分層 |
| 38 | 六角形（埠與配接器）/ Hexagonal | Architecture | 核心與外部以埠／配接器解耦 | 測試友好、替換介面 |
| 39 | 洋蔥架構 / Onion | Architecture | 同心層、依賴向中心 | 守護領域模型 |

---

## §3 Patterns（#40–#65）

審查 Phase 3 推薦修法的主要來源（GoF + 架構模式）。

### 架構級

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 40 | CQRS | Pattern | 讀寫責任分離 | 寫一致、讀擴展 |
| 41 | 事件溯源 / Event Sourcing | Pattern | 以事件為真相來源 | 重播還原狀態 |
| 42 | 交易邊界 / Transaction Boundary | Concept | 一致性所覆蓋的邊界 | 明確界定、縮小範圍 |
| 43 | 最終一致 / Eventual Consistency | Concept | 分散系統延遲一致 | 用補償／重試 |
| 44 | CAP 定理 | Concept | 一致性／可用性／分區容忍取二 | 依業務取捨 |
| 45 | 防腐層 / Anti-Corruption Layer | Pattern | 隔離舊系統語意污染 | 轉換／映射模型 |

### 建造型 (GoF Creational)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 46 | 工廠方法 / Factory Method | Pattern | 子類決定建立哪個實例 | 封裝建構細節 |
| 47 | 抽象工廠 / Abstract Factory | Pattern | 產出相關物件族群 | 一致性組合 |
| 48 | 生成器 / Builder | Pattern | 分步建立複雜物件 | 流式鏈式設定 |
| 49 | 原型 / Prototype | Pattern | 以複製建立新物件 | 複雜建構替代 |
| 50 | 單例 / Singleton | Pattern* | 全域唯一實例 | 謹慎使用，傾向 DI |

### 結構型 (GoF Structural)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 51 | 配接器 / Adapter | Pattern | 轉換介面相容 | 漸進整合老舊系統 |
| 52 | 外觀 / Facade | Pattern | 對外提供簡化入口 | 隱藏複雜度 |
| 53 | 裝飾者 / Decorator | Pattern | 動態增添行為 | 比繼承更彈性 |
| 54 | 組合 / Composite | Pattern | 樹狀結構統一處理 | 遞迴操作整體／部分 |
| 55 | 代理人 / Proxy | Pattern | 間接控制訪問 | 延遲載入、權限 |
| 56 | 橋接 / Bridge | Pattern | 抽象與實作分離 | 維度解耦 |
| 57 | 享元 / Flyweight | Pattern | 共用細粒度物件節省記憶體 | 快取／池化 |

### 行為型 (GoF Behavioral)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 58 | 觀察者 / Observer | Pattern | 狀態改變通知訂閱者 | 事件／回呼 |
| 59 | 中介者 / Mediator | Pattern | 集中協作溝通 | 降低對等耦合 |
| 60 | 命令 / Command | Pattern | 把請求封裝為物件 | 排程、復原 |
| 61 | 策略 / Strategy | Pattern | 可替換的演算法家族 | 以介面抽象 |
| 62 | 責任鏈 / Chain of Responsibility | Pattern | 串連處理直到被處理 | 可插拔處理器 |
| 63 | 狀態 / State | Pattern | 依狀態改變行為 | 移除分支 |
| 64 | 訪問者 / Visitor | Pattern | 對結構新增操作 | 開放演算法、封閉資料 |
| 65 | 迭代器 / Iterator | Pattern | 一致方式走訪集合 | 隱藏內部結構 |

---

## §4 Reliability Patterns（#66–#74）

分散式可靠性專用，Phase 1 維度 4 (Distributed reliability) 的核心檢查項。

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 66 | 斷路器 / Circuit Breaker | Pattern | 故障時短路避免連鎖 | 熔斷 → 半開 → 閉合 |
| 67 | 隔艙 / Bulkhead | Pattern | 把資源隔離防止擴散 | 配額、池分區 |
| 68 | 重試＋退避＋抖動 / Retry+Backoff+Jitter | Practice | 控制重試風暴 | 指數退避＋隨機化 |
| 69 | 背壓 / Backpressure | Concept | 下游忙時抑制上游速率 | 隊列、窗口控制 |
| 70 | SAGA（編排／編舞） | Pattern | 長交易以事件／步驟補償 | 失敗即補償 |
| 71 | Outbox Pattern | Pattern | 本地交易＋訊息可靠外送 | 避免雙寫不一致 |
| 72 | Idempotent Consumer | Pattern | 重複訊息不重做副作用 | 去重鍵／版本號 |
| 73 | 死信佇列 / DLQ | Pattern | 無法處理的訊息暫存 | 後續人工／離線補償 |
| 74 | 毒藥訊息 / Poison Pill | Concept | 刻意發送的結束／下線訊號 | 優雅關閉消費者 |

---

## §5 Practices & Concepts（#75–#100）

審查中常引用的效能、部署、領域、可觀測性概念。

### 資料層 (#75–#80)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 75 | N+1 查詢 / N+1 Query | Anti-Pattern | 迴圈中多次查 DB | 批量／預先載入、DataLoader |
| 76 | 讀寫分離 / Read-Write Split | Pattern | 寫主、讀從 | 注意最終一致 |
| 77 | 分片 / Sharding | Pattern | 按鍵切分資料庫水平擴展 | 注意跨片查詢成本 |
| 78 | 變更資料擷取 / CDC | Pattern | 從 DB log 抽出變更事件 | 解耦寫入路徑 |
| 79 | ACID | Concept | 原子／一致／隔離／持久 | 強一致情境 |
| 80 | BASE | Concept | 基本可用、軟狀態、最終一致 | 分散式情境 |

### 領域驅動設計 (#81–#88)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 81 | 領域驅動設計 / DDD | Practice | 以領域模型為核心的設計方法 | 與業務專家協作 |
| 82 | 限界上下文 / Bounded Context | Concept | 領域模型有效範圍邊界 | 切分微服務／模組邊界 |
| 83 | 聚合根 / Aggregate Root | Pattern | 一致性邊界的領域物件 | 保護不變性 |
| 84 | 值物件 / Value Object | Pattern | 由屬性定義、不可變 | 取代 Primitive Obsession |
| 85 | 實體 / Entity | Concept | 由 ID 識別、可變 | 與 Value Object 對比使用 |
| 86 | 領域事件 / Domain Event | Pattern | 領域內發生的重要事實 | 解耦、做為整合點 |
| 87 | 貧血模型 / Anemic Domain Model | Anti-Pattern | 領域物件只有資料無行為 | 移行為入領域層 |
| 88 | 富領域模型 / Rich Domain Model | Pattern | 領域物件封裝行為 | DDD 戰術設計目標 |

### 部署與發布 (#89–#94)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 89 | 絞殺者無花果 / Strangler Fig | Pattern | 漸進替換遺留系統 | 新舊並行、流量切換 |
| 90 | 抽象分支 / Branch by Abstraction | Pattern | 用抽象層支撐並行重構 | 不開長壽命分支 |
| 91 | 功能旗標 / Feature Toggle | Practice | 程式內開關控制功能可見性 | 解耦發布與部署 |
| 92 | 金絲雀部署 / Canary Release | Practice | 小流量先試新版本 | 自動化指標監控 |
| 93 | 藍綠部署 / Blue-Green Deployment | Practice | 兩組環境瞬時切換 | 快速回退 |
| 94 | 影子流量 / Shadow Traffic | Practice | 複製生產流量到新版本 | 無使用者影響的驗證 |

### 服務拓撲 (#95–#97)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 95 | 微服務 / Microservices | Architecture | 獨立部署的服務集合 | 與限界上下文對齊 |
| 96 | API Gateway / BFF | Pattern | 對外統一入口／前端專屬後端 | 鑑權、聚合、轉換 |
| 97 | Service Mesh / Sidecar | Pattern | 旁路代理處理服務間通信 | 解耦業務與基礎設施 |

### 可觀測性與韌性 (#98–#100)

| # | 名稱 | 類型 | 解釋 | 對策 |
|---:|---|---|---|---|
| 98 | 可觀測性 / Observability | Practice | 三支柱：logs / metrics / traces | 結構化日誌＋分散式追蹤 |
| 99 | SLI / SLO / SLA / Error Budget | Concept | 服務水準指標／目標／協定／錯誤預算 | 量化可靠性、決策依據 |
| 100 | 混沌工程 / Chaos Engineering | Practice | 主動注入故障驗證韌性 | 演習熔斷、降級、容災 |

---

## Cross-Reference: Smell → Fix Map

審查 Phase 3 快速查表。每個 smell 至少列出兩個候選 fix（強制 trade-off）。

| Smell (§1) | 違反原則 (§2) | 候選 Fix (§3/§4/§5) |
|---|---|---|
| #3 God Object | #26 SRP | Extract Class、#54 Composite、#61 Strategy |
| #4 Long Method | #31 KISS | Extract Method、#61 Strategy、#63 State |
| #6 Long Parameter List | #31 KISS, #35 Tell-Don't-Ask | Parameter Object、#48 Builder |
| #7 Primitive Obsession | #29 ISP | #84 Value Object |
| #8 Duplicated Code | #32 DRY | Extract Method、Extract Class、#61 Strategy |
| #9 Message Chains | #34 LoD | #52 Facade、#55 Proxy |
| #10 Middle Man | #34 LoD | 直連協作者、移除中介 |
| #14 Speculative Generality | #33 YAGNI | Inline 化、清理 |
| #18 Switch Statements | #27 OCP, #28 LSP | #61 Strategy、#63 State、多型 |
| #21 Cyclic Dependency | #30 DIP, #37 Clean | 依賴反轉、#45 ACL |
| #22 Big Ball of Mud | #37 Clean, #82 Bounded Context | #38 Hexagonal、#89 Strangler Fig |
| #24 Lava Flow | #36 Boy Scout | #89 Strangler Fig、#90 Branch by Abstraction |
| #75 N+1 Query | #31 KISS（效能版） | Eager Loading、Batch Fetch、DataLoader |
| 缺 Circuit Breaker | #66 (本身) | #66 Circuit Breaker、#67 Bulkhead、#68 Retry+Backoff |
| 缺 Idempotent | #72 (本身) | #72 Idempotent Consumer、Idempotency Key |
| 雙寫不一致 | #42 Transaction Boundary | #71 Outbox、#70 Saga |
| 缺 Backpressure | #69 (本身) | #69 Backpressure、Queue + Window |
| 貧血模型 | DDD #88 | #88 Rich Domain Model、Move Method |

---

## Cross-Reference: Dimension → Smells Lookup

審查 Phase 1 五維度掃描的快速索引。

| 維度 | 重點 smells / patterns 編號 |
|---|---|
| **Dependency** | #13, #21, #22, #45, #82 |
| **Modularity** | #2, #3, #4, #5, #16, #17, #19, #26 |
| **Performance** | #18, #75, #76, #77, #78 |
| **Distributed reliability** | #66, #67, #68, #69, #70, #71, #72, #73, #74 |
| **Technical debt** | #11, #12, #14, #15, #24, #87 |

---

## RoomPilot 適用性對照

審查本專案時的落點與禁區。**「不適用」的詞彙不得拿來湊 finding** —— 硬套即是主觀判斷，應剔除。

### 高適用（優先掃這些）

| 編號／名稱 | RoomPilot 的具體落點 |
|---|---|
| #3 God Object / #4 Long Method | `rag_pipeline/retriever.py`（369 行）的 `search_item()`、`embed_v3.py` 的 `main()` |
| #8 Duplicated Code | 房型中文對照在 `app.py` 與 `retriever.py` 各有一份；taxonomy 讀取散落三處 |
| #13 Inappropriate Intimacy | `app.py` 直接拆解 `retrieve()` 回傳的內部巢狀結構 |
| #16 Divergent Change / #17 Shotgun Surgery | 新增一個受控詞彙要同時改 `query_parser.py` + `retriever.py` + `taxonomy_v2.json` + `docs/` |
| #18 Switch Statements | 逐一 if/elif 比對六風格，而非查 `style_compat` 表 |
| #21 Cyclic Dependency | `query_parser.py` ↔ `retriever.py` 雙向 import（目前無，須守住） |
| #24 Lava Flow | `taxonomy_v1.json`、`furniture_enriched_v1/v2.json`、指向已不存在 `.venv/` 的腳本 |
| #26 SRP / #30 DIP / #32 DRY / #33 YAGNI | 三層邊界與詞表單一來源的主要依據 |
| #42 Transaction Boundary / #71 Outbox | `embed_v3.py` 同批寫 `chroma_db/` 與 `rag_export/`，需筆數對帳 |
| #45 Anti-Corruption Layer | SQL 端交付規格（`RAGSQL.md`）與內部 metadata 的轉換邊界 |
| #61 Strategy | 風格判定的 provider 切換（Ollama `qwen3:8b` ↔ Anthropic `claude-haiku-4-5`） |
| #66 Circuit Breaker / #68 Retry+Backoff | Anthropic API、本機 Ollama、HF Hub 三個外部依賴的降級與退避 |
| #72 Idempotent Consumer | 批次續跑：`text_hash` 比對（`--only-changed`）、標註的 `load_done()` |
| #73 DLQ | `rag_export/embedding_failures.jsonl` 失敗清單 |
| #75 N+1 Query | 迴圈中逐筆 `query_collection()` 或逐筆 `predict()`，應改批次 |
| #84 Value Object / #7 Primitive Obsession | 風格、氛圍、價格區間以裸 str/int 穿透整條管線 |
| #98 Observability | 目前只有 stdout print；「三支柱」在本專案降級為結構化日誌與階段耗時 |

### 條件適用（有對應物，但要換算）

| 編號／名稱 | 換算方式 |
|---|---|
| #40 CQRS | 讀（檢索）與寫（建索引）本來就分離；用來說明 `embed_v3` 與 `retriever` 不該互相耦合 |
| #70 SAGA | 沒有分散式交易；對應「多步驟批次的補償」——建索引失敗時的回滾與續跑策略 |
| #69 Backpressure | 對應 API 額度與記憶體：16 GB 機器上 UI 常駐 4.6 GB，批次不得與 UI 同跑 |
| #82 Bounded Context | 對應三層邊界：詞表／資料加工／線上檢索 |
| #89 Strangler Fig / #90 Branch by Abstraction | 用於 v1→v2→v3 資料集與 taxonomy 的漸進汰換 |
| #91 Feature Toggle | 對應 CLI 旗標（`--dry-run`、`--limit`、`--only-changed`、`--provider`） |

### 目前不適用（**不要**拿來當 finding）

| 編號／名稱 | 為什麼不適用 |
|---|---|
| #76 讀寫分離、#77 Sharding、#78 CDC | 沒有關聯式資料庫，向量庫為單機檔案式 ChromaDB |
| #92 Canary / #93 Blue-Green / #94 Shadow Traffic | **無 CI、無容器編排**，部署方式是本機 `.venv-rag/bin/python rag_pipeline/app.py` |
| #95 Microservices、#96 API Gateway/BFF、#97 Service Mesh | 單一 runtime（Gradio），沒有服務拓撲 |
| #99 SLI/SLO/SLA、#100 Chaos Engineering | 無線上流量、無值班制度；期末專題情境下屬過度工程 |
| #41 Event Sourcing、#58 Observer | 沒有事件流；資料流是離線批次的檔案產出 |

---

## How to Cite in a Review Report

Findings 中引用此 terminology 時，**必須**用 `#編號 標準名稱` 格式：

```
- Violates: #26 SRP
- Smell: #3 God Object
- Proposed fix: #61 Strategy + #54 Composite
```

RoomPilot 的完整 finding 範例：

```
- Smell: #21 Cyclic Dependency
- Evidence: rag_pipeline/query_parser.py:20 import retriever；retriever.py:24 import query_parser
- Violates: #30 DIP, #37 Clean Architecture
- Proposed fix: Option A 抽出唯讀詞彙模組（#45 ACL）／Option B 依賴反轉，由 app.py 注入（#30 DIP）
```

避免：
- "violates single responsibility" （沒有編號）
- "use strategy pattern" （沒有編號）
- "feels too coupled" （沒有引用標準名稱）
- "應該改成微服務／加 Canary 部署" （本專案不適用，見〈RoomPilot 適用性對照〉）
