---
name: 05-api-contract-spec
description: "內部介面契約規範 - JSON Schema、錯誤處理、版本控制、冪等性、金鑰保護"
stage: "Design"
template_ref: "06_api_design_specification.md"
---

# 指令 (你是介面契約設計專家)

以 Contract First 原則輸出 RoomPilot 的**內部介面契約**。

**本專案沒有 REST 服務**——沒有 HTTP 端點、沒有 Web 框架、沒有對外 API。
契約發生在三個交界面:

1. `rag_pipeline/query_parser.py` 的 **structured output schema**(claude-haiku-4-5 回傳的 JSON 形狀)
2. `rag_pipeline/retriever.py` 的**輸入／輸出契約**(吃 parser 的 payload,吐 blocks/hits)
3. `rag_pipeline/embed_v3.py` 對 `rag_export/` **四個交付檔的契約**(`json_adjustment/RAGSQL.md` 為 SSOT)

契約必須完整、精確、可版本化,並包含錯誤語意、冪等性、金鑰保護與合約測試指南。

## 交付結構

### 1. 契約設計原則

#### 1.1 介面導向準則
- **意圖導向 (Intent-Oriented)**: 函式名代表意圖,不是執行步驟
  - ✅ `parse_query("日式侘寂感的客廳沙發")`
  - ❌ `do_step1(text)` / `call_llm_then_cut(text)`

- **呼叫語意**:
  - `parse_query()`: 解析,唯讀,**非冪等**(LLM 有隨機性,同輸入可能微幅不同)
  - `retrieve()`: 檢索,唯讀,對同一份 `parsed` 與同一份索引**冪等**
  - `build_where()`: 純函式,無副作用,永遠冪等
  - `embed_v3.py`(全量): 重建索引,對同一份 v3 資料集**冪等**(同 `text_hash` → 同向量)
  - `embed_v3.py --only-changed`: 增量重算,以 `text_hash` 決定範圍,重複執行結果相同

- **失敗語意分類**:
  - `輸入契約違反`: 呼叫端給錯(空字串、詞表外的值)
  - `外部相依失敗`: Anthropic API、HF Hub、Chroma collection 出問題
  - `資料契約違反`: 產出不符交付規格(維度不符、空 `embedded_text`)

#### 1.2 命名規範
- **Python 識別字**: snake_case, 動詞-名詞
  - `parse_query()`、`build_where()`、`resolve_price_bounds()`
- **JSON 欄位**: **snake_case**(與 REST 常見的 camelCase 不同,本專案全線 snake_case)
  - `{ "category_group": "sofa", "price_max": 20000, "text_hash": "b4ecf0a1…" }`
- **CLI 參數**: kebab-case
  - `--only-changed --batch-size 16 --skip-chroma`

### 2. 契約索引規範

契約以 JSON Schema 描述資料形狀(`query_parser.build_schema()` 本身就是一份 JSON Schema),
以一份 YAML 索引檔統管介面清冊——建議落在 `docs/contracts/roompilot_contracts.yaml`。

#### 2.1 基本結構

```yaml
contract_version: 1.0.0
info:
  title: RoomPilot 內部介面契約
  description: |
    家具風格檢索系統的內部介面契約。純檢索(R 沒有 G),無 HTTP 服務、無對外 API。

    ## 金鑰載入方式
    需要 claude-haiku-4-5 的介面依序嘗試:
    ```
    ANTHROPIC_API_KEY 環境變數  →  專案根 .anthropic_key（純文字,已 .gitignore）
    ```

    ## 錯誤處理
    所有失敗遵循統一格式 (參見 `#/schemas/ErrorPayload`)

    ## 成本與限流
    - 需求解析: 每次約 US$0.005（system prompt 走 prompt caching）
    - 六風格全量判定: 約 US$7 —— 會燒額度的是批次工作
    - HF Hub: 已 `setdefault("HF_HUB_OFFLINE", "1")`,避免未登入被限流乾等數分鐘
  ssot:
    - docs/query_parser_spec.md
    - docs/RAG檢索系統說明.md
    - json_adjustment/RAGSQL.md

runtimes:
  - name: 本機 CLI
    entry: .venv-rag/bin/python rag_pipeline/retriever.py "<需求>"
  - name: 本機 UI
    entry: .venv-rag/bin/python rag_pipeline/app.py   # http://127.0.0.1:7860
  - name: 批次建索引
    entry: .venv-rag/bin/python rag_pipeline/embed_v3.py [--limit N|--only-changed]
  # 無測試環境、無生產環境:本專案無 CI、無 Docker,只在本機 macOS 執行

tags:
  - name: Query Understanding
    description: 需求解析與改寫（claude-haiku-4-5,一次呼叫兩用）
  - name: Retrieval
    description: 硬過濾 → 向量召回 → rerank → 加權 → 收斂
  - name: Indexing
    description: bge-m3 編碼與 ChromaDB furniture_v3 寫入
  - name: Export
    description: rag_export/ 四個交付檔（SQL 端消費）

interfaces:
  # 介面詳細定義...

schemas:
  # 資料模型定義...

failures:
  # 可重用失敗定義...

security:
  - anthropic_api_key: []
```

#### 2.2 介面定義範例

```yaml
interfaces:
  query_parser.parse_query:
    tags:
      - Query Understanding
    summary: 自然語言需求 → 受控詞彙的結構化檢索條件
    description: |
      使用者提交自然語言需求,單次 claude-haiku-4-5 呼叫同時完成:
      1. Query Understanding（抽出受控詞彙條件）
      2. Query Rewriting（HyDE:semantic_query 寫成與 embedded_text 相同句式）
      3. 詞表由 taxonomy_v2.json + category_groups.json 動態注入（改詞表不改 prompt）
      4. 回傳後程式端裁切 styles[:2] / moods[:3] / items[:6]（schema 不支援 maxItems）

    signature: "parse_query(text: str, client: anthropic.Anthropic | None = None) -> dict"
    security:
      - anthropic_api_key: []

    request:
      required: true
      content:
        text/plain:
          schema:
            type: string
            minLength: 1
          examples:
            simple:
              summary: 單一物件需求
              value: "日式侘寂感、預算兩萬內的客廳沙發"
            set:
              summary: 整組需求
              value: "六萬預算幫我配一整組北歐風客廳，沙發要淺色布面"

    responses:
      ok:
        description: 解析成功
        meta:
          _usage:
            description: 本次呼叫的 token 用量（cache_read > 0 代表 prompt caching 命中）
            schema:
              type: object
              example: { input_tokens: 2480, output_tokens: 612, cache_read: 2312 }
        content:
          application/json:
            schema:
              $ref: '#/schemas/QuerySpecPayload'
            example:
              room_type: "living_room"
              styles: ["japanese"]
              moods: ["寧靜", "自然"]
              price_level: null
              budget_total: null
              is_set: false
              items:
                - item_id: "main_sofa"
                  label_zh: "主沙發"
                  category_group: "sofa"
                  quantity: 1
                  priority: "must_have"
                  is_inferred: false
                  price_max: 20000
                  semantic_query: "名稱：…。類別：沙發。物件類型：三人座布沙發。…"
              confidence: 0.86
              needs_clarification: false

      invalid_input:
        $ref: '#/failures/InvalidInput'

      missing_key:
        $ref: '#/failures/MissingCredential'

      vocab_violation:
        description: 業務驗證失敗（模型回傳詞表外的值或空 items）
        content:
          application/json:
            schema:
              $ref: '#/schemas/ErrorPayload'
            examples:
              empty_items:
                summary: items 為空陣列
                value:
                  error:
                    code: "VOCAB_VIOLATION_EMPTY_ITEMS"
                    message: "無法從需求中判斷要找什麼家具，請再描述一下"
                    details:
                      raw_text: "幫我看看"
                      item_count: 0
                      needs_clarification: true

      upstream_error:
        $ref: '#/failures/UpstreamModelError'

  retriever.retrieve:
    tags:
      - Retrieval
    summary: 依需求規格檢索並收斂成一組家具
    description: |
      吃 parse_query 的 payload,對每個品項跑兩階段檢索,再做 set 層收斂。
      anchor 品項先跑,用它的 top-1 決定主導風格,其餘品項沿用同一個主導風格。
    signature: "retrieve(parsed: dict, top_k: int = FINAL_TOP_K) -> dict"
    security: []   # 純本機,不需金鑰

    parameters:
      - name: parsed
        in: argument
        required: true
        description: query_parser 的輸出（必須含非空 items）
        schema:
          $ref: '#/schemas/QuerySpecPayload'
      - name: top_k
        in: argument
        description: 每個品項最終回傳筆數
        schema:
          type: integer
          minimum: 1
          maximum: 20
          default: 8          # retriever.FINAL_TOP_K
      - name: VEC_TOP_K
        in: constant
        description: 向量召回筆數（硬過濾緩衝）
        schema: { type: integer, default: 50 }
      - name: RERANK_TOP_K
        in: constant
        description: 送進 cross-encoder 的候選數（配件品項降為 RERANK_TOP_K_LIGHT=12）
        schema: { type: integer, default: 20 }
      - name: BUDGET_SLACK
        in: constant
        description: 預算分配的檢索寬容係數
        schema: { type: number, default: 1.3 }

    responses:
      ok:
        description: 檢索成功
        content:
          application/json:
            schema:
              $ref: '#/schemas/RetrievalResult'

      empty_result:
        $ref: '#/failures/EmptyResult'

      collection_rebuilt:
        $ref: '#/failures/CollectionNotFound'

  retriever.build_where:
    tags:
      - Retrieval
    summary: 推導 Chroma metadata 硬過濾條件
    description: |
      純函式,無副作用。**只有**房型／類別／價格／尺寸進 where;
      風格與氛圍是軟加權(只影響排序);顏色與材質只進 semantic_query,不做過濾。
      ★ rag_indexable 絕對不可寫進 where —— 它是 v3 頂層欄位、不在 chroma_metadata 裡,
        寫了會命中 0 筆。
    signature: "build_where(item: dict, parsed: dict, allocated: dict, data: dict) -> dict | None"

    responses:
      ok:
        description: 成功（完全沒有硬條件時回傳 null,代表全庫語意檢索）
        content:
          application/json:
            schema:
              type: [object, "null"]
            example:
              $and:
                - room_living_room: { $eq: true }
                - category: { $in: ["沙發", "單人沙發", "沙發床"] }
                - price_twd: { $lte: 20000 }

  embed_v3.export:
    tags:
      - Indexing
      - Export
    summary: 建索引並產出 rag_export/ 四個交付檔
    description: |
      一次算向量、同時寫 ChromaDB 與 rag_export/,保證兩邊是同一批、同一個 text_hash,
      不會出現「demo 正常但 SQL 端結果不同」。
      --only-changed 會比對既有交付檔的 text_hash,只重算變動者(646 筆約 1.5 分鐘)。
    entry: ".venv-rag/bin/python rag_pipeline/embed_v3.py [--limit N] [--only-changed] [--device cpu]"

    parameters:
      - $ref: '#/parameters/OnlyChangedFlag'

    outputs:
      required: true
      description: RAGSQL.md 指定的四個交付檔,缺一不可
      content:
        application/x-ndjson:
          files:
            - path: rag_export/furniture_embeddings_bge_m3.jsonl
              schema:
                $ref: '#/schemas/EmbeddingRecord'
            - path: rag_export/embedding_metadata.json
              description: 整批規格檔（SQL 端據此決定 VECTOR(1024) 與 hnsw 索引）
            - path: rag_export/embedding_failures.jsonl
              description: 失敗清單（解釋筆數差異的唯一依據）
            - path: rag_export/embedding_validation_report.json
              description: 驗證報告（匯入前的 gate）

    responses:
      ok:
        description: 交付成功
        content:
          application/json:
            example:
              embedded_count: 9349
              reused_vector_count: 8703
              failed_count: 1
              coverage_percent: 99.99

      data_contract_violation:
        description: 產出不符交付規格（該筆不寫進 jsonl,改記入 failures）
        content:
          application/json:
            schema:
              $ref: '#/schemas/ErrorPayload'
            example:
              error:
                code: "DATA_CONTRACT_INVALID_DIMENSION"
                message: "向量維度不符交付規格"
                details:
                  item_id: "abo-example-001"
                  expected_dimension: 1024
                  actual_dimension: 768

      model_error:
        $ref: '#/failures/UpstreamModelError'
```

### 3. Schema 定義

> ★ 送進 claude-haiku-4-5 的 schema 有額外限制:所有 object 必須 `additionalProperties: false`,
> 不支援 `minLength` / `maxItems` 等數量約束(上限改在 prompt 講、程式端再裁切),
> **可為 null 的 enum 一定要用 `anyOf` 包**(直接寫 type 陣列會 400)。

```yaml
schemas:
  # 通用錯誤格式
  ErrorPayload:
    type: object
    required:
      - error
    properties:
      error:
        type: object
        required:
          - code
          - message
        properties:
          code:
            type: string
            description: 錯誤代碼 (機器可讀)
            example: "INVALID_INPUT"
          message:
            type: string
            description: 錯誤訊息 (人類可讀,可直接顯示在 Gradio 卡片區)
            example: "請再描述一下想找的家具"
          details:
            type: object
            description: 額外錯誤細節（伺服端／stderr 記錄用,不顯示給使用者）
            additionalProperties: true
          trace_id:
            type: string
            format: uuid
            description: 追蹤ID,用於日誌查詢
            example: "550e8400-e29b-41d4-a716-446655440000"

  # 需求解析輸出（query_parser.build_schema() 的頂層,SSOT: docs/query_parser_spec.md）
  QuerySpecPayload:
    type: object
    additionalProperties: false
    required:
      - room_type
      - styles
      - moods
      - items
      - confidence
      - needs_clarification
    properties:
      room_type:
        anyOf:                       # 可為 null 的 enum 必須這樣寫
          - type: string
            enum: [living_room, bedroom, dining_room, study, entryway,
                   kids_room, outdoor, bathroom, kitchen]
          - type: "null"
      styles:
        type: array                  # 上限 2,schema 無 maxItems,程式端 [:2]
        items:
          type: string
          enum: [scandinavian, japanese, modern_minimal, cream, industrial, american]
        example: ["japanese", "scandinavian"]
      moods:
        type: array                  # 上限 3,24 個受控氛圍詞
        items: { type: string }
        example: ["寧靜", "自然"]
      price_level:
        anyOf:
          - type: string
            enum: [budget, mid, premium]
          - type: "null"
        description: 與 budget_total／price_max 互斥（有具體金額就留 null）
      budget_total:
        anyOf: [{ type: integer }, { type: "null" }]
        example: 60000
      is_set:
        type: boolean
      items:
        type: array                  # 上限 6（MAX_ITEMS）,★ 絕對不可為空陣列
        items:
          $ref: '#/schemas/QueryItem'
      confidence:
        type: number
        minimum: 0
        maximum: 1
        example: 0.86
      needs_clarification:
        type: boolean
      clarify_question:
        type: [string, "null"]
      clarify_options:
        type: array                  # 上限 4（app.MAX_CLARIFY）
        items: { type: string }
      reasoning:
        type: string

  # 單一品項
  QueryItem:
    type: object
    additionalProperties: false
    required:
      - item_id
      - label_zh
      - category_group
      - quantity
      - semantic_query
    properties:
      item_id:
        type: string
        description: 英文 slug
        example: "main_sofa"
      label_zh:
        type: string
        example: "主沙發"
      category_group:
        anyOf:
          - type: string             # 19 個檢索群組之一（category_groups.json）
          - type: "null"             # null = 跨類別語意檢索
        example: "sofa"
      quantity:
        type: integer
        minimum: 1
        example: 1
      priority:
        type: string
        enum: [must_have, nice_to_have]
      is_inferred:
        type: boolean
        description: true = 使用者沒明講、系統推論的品項（rerank 額度降為 12）
      semantic_query:
        type: string
        description: 與 embedded_text 同句式的 HyDE 描述,每個品項獨立撰寫
      price_max:
        anyOf: [{ type: integer }, { type: "null" }]
      max_width_cm:
        anyOf: [{ type: number }, { type: "null" }]
        description: ★ 硬過濾;只有使用者明講尺寸才填,絕不可用常識推測
      role:
        anyOf: [{ type: string, enum: [anchor, accent] }, { type: "null" }]
      size_hint:
        anyOf: [{ type: string, enum: [S, M, L] }, { type: "null" }]

  # 檢索結果
  RetrievalResult:
    type: object
    required:
      - dominant_style
      - blocks
    properties:
      dominant_style:
        type: [string, "null"]
        example: "japanese"
      style_zh:
        type: string
        example: "日式"
      budget_total:
        type: [integer, "null"]
      estimated_total:
        type: integer
        description: 各品項首選 × quantity 的加總
        example: 48600
      blocks:
        type: array
        items:
          type: object
          required: [item_id, label_zh, quantity, hits]
          properties:
            item_id: { type: string }
            label_zh: { type: string }
            category_group: { type: [string, "null"] }
            quantity: { type: integer, minimum: 1 }
            is_inferred: { type: boolean }
            price_cap: { type: [integer, "null"] }
            where: { type: [object, "null"] }
            hits:
              type: array           # 最多 top_k 筆,已跨品項去重
              items:
                type: object
                required: [id, meta, score_final]
                properties:
                  id: { type: string }
                  meta:
                    type: object
                    description: chroma_metadata（含 name_zh / category / price_twd /
                      style_primary / duplicate_group / room_* 布林旗標）
                  score_final:
                    type: number
                    description: 0.60×rerank + 0.20×style_compat + 0.10×mood + 0.10×confidence
                    example: 0.7412
                  score_rerank: { type: number, minimum: 0, maximum: 1 }
                  score_style: { type: number, minimum: 0, maximum: 1 }
                  score_mood: { type: number, minimum: 0, maximum: 1 }

  # 交付檔單列（rag_export/furniture_embeddings_bge_m3.jsonl 一行一件）
  EmbeddingRecord:
    type: object
    required:
      - item_id
      - embedded_text
      - text_hash
      - embedding_model
      - embedding_dimension
      - embedding
    properties:
      item_id:
        type: string
        description: 對應家具主表的 id（舊規格 RAGSQL.md 稱 furniture_id）
        example: "abo-bed-frames-19-amazon-brand-rivet-a8910-dresser"
      embedded_text:
        type: string
        description: 實際送進 embedding model 的完整文字
      text_hash:
        type: string
        pattern: '^[a-f0-9]{64}$'
        description: 判斷文字有無修改;--only-changed 的冪等依據
      embedding_model:
        type: string
        enum: ["BAAI/bge-m3"]
      embedding_dimension:
        type: integer
        enum: [1024]
      embedding:
        type: array
        items: { type: number }
        description: 1024 個浮點數,已 normalized,寫出時 round 到小數 6 位
      embedded_at:
        type: string
        format: date-time
        example: "2026-07-28T12:00:00+08:00"
      text_format_version:
        type: string
        example: "v1"
      source_schema_version:
        type: string
      normalized:
        type: boolean
        enum: [true]

# 可重用參數
parameters:
  OnlyChangedFlag:
    name: --only-changed
    in: cli
    required: false
    description: 只重算 text_hash 與既有 rag_export 不同的品項,其餘沿用舊向量
    schema:
      type: boolean
      default: false
    example: --only-changed

  TopKParam:
    name: top_k
    in: argument
    required: false
    description: 每個品項最終回傳筆數
    schema:
      type: integer
      minimum: 1
      maximum: 20
      default: 8
    example: 8

# 可重用失敗定義
failures:
  InvalidInput:
    description: 輸入契約違反
    content:
      application/json:
        schema:
          $ref: '#/schemas/ErrorPayload'
        example:
          error:
            code: "INVALID_INPUT"
            message: "請輸入想找的家具或風格"
            details:
              field: "text"
              constraint: "不可為空字串"

  MissingCredential:
    description: 找不到金鑰或金鑰無效
    content:
      application/json:
        schema:
          $ref: '#/schemas/ErrorPayload'
        example:
          error:
            code: "MISSING_CREDENTIAL"
            message: "需求解析暫時無法使用，請稍後再試"
            details:
              checked: ["ANTHROPIC_API_KEY", ".anthropic_key"]
              # ★ 絕不可把金鑰內容寫進 details 或回顯到 UI

  EmptyResult:
    description: 硬過濾後命中 0 筆
    content:
      application/json:
        schema:
          $ref: '#/schemas/ErrorPayload'
        example:
          error:
            code: "EMPTY_RESULT"
            message: "這個條件下沒有合適的家具，試著放寬預算或尺寸"
            details:
              item_id: "main_sofa"
              where: { $and: [{ room_living_room: { $eq: true } },
                              { price_twd: { $lte: 3000 } }] }
              hint: "rag_indexable 不可寫進 where，寫了必定 0 筆"

  CollectionNotFound:
    description: collection 不存在（多半是索引正被重建,UUID 已換）
    content:
      application/json:
        schema:
          $ref: '#/schemas/ErrorPayload'
        example:
          error:
            code: "NOT_FOUND_COLLECTION"
            message: "索引更新中，正在重新連線"
            details:
              collection: "furniture_v3"
              recovery: "清 lru_cache 後重取 collection 並重試一次"

  UpstreamModelError:
    description: 外部相依失敗（Anthropic API／HF Hub／MPS 算子）
    content:
      application/json:
        schema:
          $ref: '#/schemas/ErrorPayload'
        example:
          error:
            code: "UPSTREAM_MODEL_ERROR"
            message: "服務暫時不可用,請稍後重試"
            details:
              stage: "encode"
              fallback: "device=cpu"
            trace_id: "550e8400-e29b-41d4-a716-446655440000"
```

### 4. 錯誤處理策略

#### 4.1 錯誤代碼分類

```markdown
| 失敗類別 | 錯誤代碼類別 | 範例 | 處理建議 |
|----------|--------------|------|----------|
| 輸入契約違反 | INVALID_INPUT_* | INVALID_INPUT_EMPTY_TEXT | 檢查傳入參數 |
| 金鑰缺失 | MISSING_CREDENTIAL_* | MISSING_CREDENTIAL_ANTHROPIC | 設 ANTHROPIC_API_KEY 或補 .anthropic_key |
| Schema 被拒 | SCHEMA_REJECTED_* | SCHEMA_REJECTED_NULLABLE_ENUM | 可為 null 的 enum 改用 anyOf |
| 詞表違反 | VOCAB_VIOLATION_* | VOCAB_VIOLATION_UNKNOWN_STYLE | 對映回六風格,或更新 taxonomy_v2.json |
| 索引不存在 | NOT_FOUND_* | NOT_FOUND_COLLECTION | 清快取重連;確認 furniture_v3 已建 |
| 命中 0 筆 | EMPTY_RESULT_* | EMPTY_RESULT_HARD_FILTER | 放寬預算/尺寸;檢查有無誤過濾 rag_indexable |
| 業務約束 | BUSINESS_ERROR_* | BUSINESS_ERROR_BUDGET_TOO_LOW | 提示使用者調整預算或件數 |
| 限流 | RATE_LIMIT_* | RATE_LIMIT_ANTHROPIC_429 | 指數退避;批次工作降速 |
| 模型/裝置錯誤 | UPSTREAM_MODEL_ERROR_* | UPSTREAM_MODEL_ERROR_MPS | 退回 --device cpu 重試 |
| 資料契約違反 | DATA_CONTRACT_* | DATA_CONTRACT_INVALID_DIMENSION | 記入 embedding_failures.jsonl,不入庫 |
```

#### 4.2 可重試與不可重試錯誤

```python
# 可重試錯誤 (呼叫端應自動重試)
RETRYABLE_ERROR_CODES = [
    "UPSTREAM_MODEL_ERROR_TIMEOUT",
    "UPSTREAM_MODEL_ERROR_MPS",        # 退回 device=cpu 再試
    "NOT_FOUND_COLLECTION",            # 索引重建中,清 lru_cache 後重取
    "RATE_LIMIT_ANTHROPIC_429",        # 需指數退避
]

# 不可重試錯誤 (應提示使用者或開發者修正)
NON_RETRYABLE_ERROR_CODES = [
    "INVALID_INPUT_EMPTY_TEXT",
    "MISSING_CREDENTIAL_ANTHROPIC",
    "SCHEMA_REJECTED_NULLABLE_ENUM",   # 程式 bug,重試一萬次也一樣
    "EMPTY_RESULT_HARD_FILTER",        # 條件本身太嚴,要改條件不是重試
]
```

### 5. 版本控制策略

#### 5.1 版本演進規則

- **版本載體**: 本專案沒有 URL 版本,版本寫在資料與索引名稱上
  - `schema_version` / `source_schema_version`(資料集)、`text_format_version`(組句規格)、
    `taxonomy_version`(詞表)、collection 名稱 `furniture_v3`(索引)
  - 用於重大不相容變更:改 collection 名稱(如 `furniture_v4`)並保留舊 collection 至少一輪 demo

- **向後相容變更** (無需升版本):
  - ✅ 新增 `chroma_metadata` 欄位(舊查詢不讀就不受影響)
  - ✅ 新增可為 null 的解析欄位(記得用 `anyOf`)
  - ✅ 放寬驗證規則 (如放大 `top_k` 上限、放寬價格區間)

- **不相容變更** (需升版本):
  - ❌ 刪除欄位(如把 `duplicate_group` 拿掉,去重會整組失效)
  - ❌ 修改欄位類型或改名(`furniture_id` → `item_id` 這類)
  - ❌ 改 `embedded_text` 句式 —— `text_hash` 會全部變動,等於全量重算 27 分鐘
  - ❌ 換 embedding 模型或維度(SQL 端的 `VECTOR(1024)` 與 hnsw 索引都要重建)

#### 5.2 棄用流程

```yaml
deprecations:
  rag_export/furniture_embeddings.jsonl:   # 舊檔名
    deprecated: true
    description: |
      ⚠️ 已棄用,改用 furniture_embeddings_bge_m3.jsonl（i_need_rag.md 指定的檔名）
      embed_v3.py --only-changed 仍會相容讀取舊檔,但不再寫出
    compatibility:
      read: true
      write: false
    sunset: "下一次全量重建後移除"

  field.furniture_id:                       # 舊欄位名（RAGSQL.md 初版規格）
    deprecated: true
    description: |
      ⚠️ 已改名為 item_id。增量模式讀入舊檔時會就地正規化,
      避免沿用的舊列把 furniture_id 殘留進新交付檔
    replaced_by: item_id
    note: "chroma_metadata 內仍保留 furniture_id 作為顯示用鍵,兩者不要混淆"
```

#### 5.3 冪等性契約（text_hash）

本專案沒有 HTTP,自然也沒有 `Idempotency-Key` header —— **`text_hash` 就是冪等鍵**。

```markdown
| 操作 | 冪等鍵 | 重複執行的結果 |
|------|--------|----------------|
| `embed_v3.py`（全量） | `text_hash` | 同一份 v3 資料集 → 同一批向量;collection 整批替換 |
| `embed_v3.py --only-changed` | `text_hash` | 未變動者沿用舊向量,只重算變動筆;可安全重跑 |
| `retrieve(parsed)` | `parsed` + collection 內容 | 同輸入同索引 → 同結果（純函式鏈） |
| `parse_query(text)` | 無 | **非冪等**:LLM 有隨機性,同一句可能得到略異的 payload |
```

規則:
- 交付檔與 Chroma **必須同一次執行產生**,否則兩邊 `text_hash` 可能不同源,
  會出現「demo 正常但 SQL 端結果不同」
- 沿用舊向量時,舊列**原樣寫回**(含 `embedded_at`),不重打時間戳,才能看出哪些真的重算過
- 想強制重算某筆:改它的 `embedded_text`（`text_hash` 自然變動),不要手改 hash

### 6. 安全設計

#### 6.1 金鑰方案

```yaml
securitySchemes:
  anthropic_api_key:
    type: apiKey
    in: env_or_file
    name: ANTHROPIC_API_KEY
    description: |
      載入順序（query_parser.get_client()）:
      ```
      1. os.environ["ANTHROPIC_API_KEY"]
      2. 專案根 .anthropic_key（純文字檔,已列入 .gitignore）
      3. anthropic.Anthropic() 預設查找
      ```
      ★ 絕不可提交、絕不可回顯內容、絕不可寫進錯誤 details 或日誌

  local_only:
    type: none
    in: process
    name: 本機執行
    description: |
      retriever／embed_v3／Gradio 全在本機跑,UI 綁 127.0.0.1:7860 不對外;
      本專案無 CI、無 Docker,沒有伺服器對伺服器的調用面
```

#### 6.2 權限與破壞性操作控制

```yaml
operations:
  embed_v3.rebuild:
    tags:
      - Indexing
    summary: 重建 furniture_v3（破壞性）
    security:
      - local_only: []
    x-destructive: true          # delete_collection + create_collection,無法回滾
    x-requires-confirmation: true
    x-cost-note: |
      會燒額度／耗時的是批次工作:
      全量建索引約 27 分鐘;六風格全量判定約 US$7。
      先用 --limit 50 冒煙,確認無誤再跑全量。
```

#### 6.3 輸入驗證

所有輸入必須在系統邊界驗證:
- **格式驗證**: 使用 JSON Schema 的 `enum`, `pattern`(如 `text_hash` 的 64 位 hex)
- **範圍驗證**: `minimum`, `maximum`;以及程式端裁切 `styles[:2]` / `moods[:3]` / `items[:6]`
- **業務驗證**: 在應用層執行(尺寸不得由 LLM 推測、`rag_indexable` 不進 `where`、
  `price_max` 與 `price_level` 互斥)

### 7. 合約測試

> 測試框架以 **pytest** 為預設建議,但本專案**尚未建置正式測試套件**;
> 執行方式為 `.venv-rag/bin/python -m pytest tests/`。
> 契約測試不必載入 bge-m3／reranker,只驗形狀,是最便宜也最該先補的一層。

#### 7.1 Provider 測試 (契約提供方:parser / retriever / embed_v3)

```python
"""驗證產出符合契約 schema（用 jsonschema 驗,不打真的 API 就用錄下來的 payload）。"""
import json
from pathlib import Path

import pytest
from jsonschema import validate

CONTRACT = Path("docs/contracts")
EXPORT = Path("rag_export")


class TestParserContract:
    def test_parse_query_應該符合_QuerySpecPayload(self, recorded_payload):
        schema = json.loads((CONTRACT / "query_spec_payload.json").read_text())

        validate(instance=recorded_payload, schema=schema)
        assert recorded_payload["items"], "items 絕對不可為空陣列"
        assert len(recorded_payload["styles"]) <= 2

    def test_受控詞彙必須全部落在_taxonomy_v2_內(self, recorded_payload, taxonomy):
        assert set(recorded_payload["styles"]) <= set(taxonomy["styles"])


class TestExportContract:
    def test_交付檔每一列都符合_EmbeddingRecord(self):
        schema = json.loads((CONTRACT / "embedding_record.json").read_text())
        path = EXPORT / "furniture_embeddings_bge_m3.jsonl"

        for line in path.read_text(encoding="utf-8").splitlines()[:200]:
            row = json.loads(line)
            validate(instance=row, schema=schema)
            assert row["embedding_dimension"] == len(row["embedding"]) == 1024

    def test_失敗清單應該符合標準錯誤欄位(self):
        for line in (EXPORT / "embedding_failures.jsonl").read_text().splitlines():
            row = json.loads(line)
            assert {"item_id", "error_type"} <= set(row)
            assert row["error_type"] in {
                "not_indexable", "model_error", "invalid_dimension", "empty_embedded_text",
            }
```

#### 7.2 Consumer 測試 (契約消費方:retriever / Gradio / SQL 端)

```python
"""消費方不打模型,用固定 fixture 假裝上游的輸出（等同 mock server 的角色）。"""


@pytest.fixture
def parsed_fixture() -> dict:
    """一份凍結的 parse_query 輸出,改契約時這份 fixture 必須同步更新。"""
    return {
        "room_type": "living_room",
        "styles": ["japanese"],
        "moods": ["寧靜"],
        "price_level": None,
        "budget_total": None,
        "is_set": False,
        "items": [{
            "item_id": "main_sofa",
            "label_zh": "主沙發",
            "category_group": "sofa",
            "quantity": 1,
            "priority": "must_have",
            "is_inferred": False,
            "semantic_query": "名稱：…。類別：沙發。…",
            "styles": ["japanese"],
            "price_max": 20000,
            "max_width_cm": None, "max_height_cm": None,
            "role": "anchor", "size_hint": None,
        }],
        "confidence": 0.86,
        "needs_clarification": False,
        "clarify_question": None, "clarify_options": [], "reasoning": "…",
    }


def test_build_where_只放硬過濾條件(parsed_fixture, data_fixture):
    where = build_where(parsed_fixture["items"][0], parsed_fixture, {}, data_fixture)

    flat = json.dumps(where, ensure_ascii=False)
    assert "room_living_room" in flat and "price_twd" in flat
    assert "rag_indexable" not in flat          # 寫了必定命中 0 筆
    assert "style_primary" not in flat          # 風格是軟加權,不進 where


def test_SQL_端匯入前的驗證報告_gate():
    report = json.loads((EXPORT / "embedding_validation_report.json").read_text())

    assert report["duplicate_furniture_ids"] == 0
    assert report["invalid_vector_count"] == 0
    assert report["null_vector_count"] == 0
    assert list(report["dimension_distribution"]) == ["1024"]
    assert list(report["model_distribution"]) == ["BAAI/bge-m3"]
```

## 蘇格拉底檢核

1. **一致性**:
   - 三個交界面(parser / retriever / rag_export)的錯誤格式是否一致?
   - 命名風格是否統一 snake_case?(`chroma_metadata`、交付檔、structured outputs 都是)

2. **完整性**:
   - 是否涵蓋所有失敗類別?(輸入違反／金鑰缺失／限流／模型錯誤／資料契約違反)
   - 每個錯誤是否有明確的處理建議與可否重試的判斷?

3. **版本演進**:
   - 新增欄位會不會讓 SQL 端匯入失敗?會不會讓 `text_hash` 全部變動?
   - 棄用流程是否給了相容讀取期?(`furniture_embeddings.jsonl` / `furniture_id` 就是範例)

4. **安全性**:
   - 金鑰是否只從環境變數或 `.anthropic_key` 取得,且從不回顯、不進錯誤 details?
   - 破壞性與燒額度的批次操作是否需要明確旗標與人工確認?

5. **可測試性**:
   - 是否提供契約測試範例(pytest,標明尚未建置)?
   - fixture 是否夠真實?(用真的跑一次錄下來的 payload,不要手捏假句子)

## 輸出格式

- 主文件: `docs/contracts/roompilot_contracts.yaml`（介面清冊）+ JSON Schema 檔
- 分模組: `docs/query_parser_spec.md`（解析契約）、`json_adjustment/RAGSQL.md`（交付契約）
- 遵循 VibeCoding_Workflow_Templates/06_api_design_specification.md

## 審查清單

- [ ] 三個交界面都有完整的輸入/輸出 Schema
- [ ] 失敗回傳遵循統一 `ErrorPayload` 格式
- [ ] 所有欄位有明確的驗證規則（含可為 null 的 enum 一律 `anyOf`）
- [ ] 金鑰載入順序與保護規則明確
- [ ] 版本控制與冪等性（`text_hash`）策略清晰
- [ ] 提供契約測試範例（pytest,尚未建置者列入待辦）
- [ ] Schema 可通過 `jsonschema` 驗證,且交付檔通過 `embedding_validation_report.json` 的 gate
- [ ] 契約變更已同步 `docs/query_parser_spec.md` 與 `json_adjustment/RAGSQL.md`

## 關聯文件

- **架構設計**: 03-architecture-design-doc.md (Container Diagram)
- **模組規格**: 07_module_specification_and_tests.md (實作細節)
- **安全檢查**: 13_security_and_readiness_checklists.md (安全審查)
- **DDD 聚合**: 04-ddd-aggregate-spec.md（`QuerySpec` 聚合與本契約的 `QuerySpecPayload` 對應）

---

**記住**: 契約是系統的接縫,好的契約設計讓 RAG 端與 SQL 端並行開發,讓驗證有明確依據,讓文檔永不過時。
**規格衝突時以文件為準** —— 程式改了契約,`docs/` 下的 SSOT 必須同一個 commit 一起改。
