---
name: sunnydata-architecture-review
description: RoomPilot 檢索系統的架構級審查，採 smells → principles → fixes 三階段流程。審查既有架構、盤點設計債、評估重構候選、稽核 rag_pipeline / json_adjustment / vlm_annotation 三層模組邊界與依賴方向時使用。補足 sunnydata-code-review（行級）與 architect agent（全新設計）之間的空缺。
---

> **繁體中文說明**：此技能提供「架構級」code review 的結構化流程 — 先掃壞味道 (smells) → 反向對應違反的原則 (principles) → 推薦具體修法 (fixes)。三階段順序固定，不可跳過。本 skill 補充 `sunnydata-code-review`（行級實作審查）與 `architect` agent（全新設計）之間的空缺：**對既有系統做結構性、有證據的、可決策的架構審查**。

# Architecture Review

## Overview

Three phases, fixed order. Skipping a phase invalidates the review.

```
Detect Smells → Map to Principles → Propose Fixes → Output Report
```

**Why this order is mandatory:**

- 沒有 smells = 沒有要修的東西，不要硬找。
- 找到 smells 卻對應不上原則 = 主觀判斷，必須剔除。
- 對應上原則卻沒有具體 fix = 抱怨而非審查。

**Core principles across all phases:**

- **Evidence before claims** — 每個 finding 必須有檔案路徑＋行號或可驗證的指標。
- **Severity over sentiment** — 用 Critical/High/Medium/Low 分級，不用「好/不好」。
- **Vocabulary over vibes** — 必須使用業界共通行話（見 `terminology.md`），不接受自創詞。

**When to invoke:**

- 變更定案交付前的架構守門（本專案尚未 git init，「合併到 main」＝視為定案）
- 技術債盤點與重構優先級排序
- 新人 onboarding 走讀既有系統（`rag_pipeline` → `json_adjustment` → `vlm_annotation` 三層）
- 評估「要重寫還是要修」的決策依據（例如「retriever 要不要拆成 filter/rank/compose 三個模組」）
- 變更觸及 3+ 檔案或新增 100+ 行時的結構性審查
- 更換模型、改動排序公式、調整硬過濾／軟加權界線時

**When NOT to invoke:**

- 行級實作審查 → 用 `sunnydata-code-review`
- 全新系統的架構設計 → 用 `architect` agent
- 模板合規檢查 → 用 `template-check` command
- Bug 修復、typo、單檔小改 → 直接審查不需此流程

---

## 本專案的三層模組邊界（審查依賴方向的基準）

RoomPilot 是**純檢索系統（R 沒有 G）**，只有一個 runtime：`rag_pipeline/app.py`（Gradio，`127.0.0.1:7860`）。
另外兩層是**離線資料建置**，不在請求路徑上。

```
[離線層 A] vlm_annotation/     詞表與標註產出
             taxonomy_v2.json（六風格 + 6×6 相容矩陣）、render_meta_full.jsonl
                    │  產出檔（資料依賴）
                    ▼
[離線層 B] json_adjustment/    資料加工與交付規格
             build_rag_v3.py（v2→v3）、reclassify_styles.py（六風格判定）
                    │  產出 rag_dataset/furniture_enriched_v3.json
                    ▼
[線上層 C] rag_pipeline/       檢索管線（唯一應用程式）
             embed_v3.py → chroma_db/ + rag_export/
             query_parser.py → retriever.py → app.py
```

**允許的依賴方向（單向，DAG）：**

| 從 | 到 | 形式 | 判定 |
| :--- | :--- | :--- | :--- |
| `rag_pipeline/app.py` | `query_parser.py`、`retriever.py` | Python import（同層） | 允許 |
| `rag_pipeline/*` | `vlm_annotation/taxonomy_v2.json`、`render_meta_full.jsonl` | **只讀 JSON／JSONL 檔** | 允許（資料依賴） |
| `rag_pipeline/*` | `rag_pipeline/category_groups.json` | 只讀 JSON | 允許 |
| `rag_pipeline/embed_v3.py` | `rag_dataset/furniture_enriched_v3.json` | 只讀 | 允許 |
| `json_adjustment/*` | `rag_dataset/`、`vlm_annotation/taxonomy_v2.json` | 只讀 | 允許 |

**禁止的依賴（出現即 Critical 或 High）：**

| 反向依賴 | 為什麼禁止 | 嚴重度 |
| :--- | :--- | :--- |
| `json_adjustment/*` 或 `vlm_annotation/*` `import` `rag_pipeline` | 離線層依賴線上層＝依賴倒錯，資料重建會被檢索實作綁死 | Critical |
| `rag_pipeline/*` `import` `vlm_annotation` 或 `json_adjustment` 的 Python 模組 | 線上路徑被離線腳本的重依賴（VLM、Ollama）污染，UI 啟動時間與記憶體失控 | Critical |
| `query_parser.py` `import` `retriever.py`（或反向雙向 import） | 解析與檢索互相依賴＝循環依賴，兩者都無法單獨測試 | Critical |
| 任一層繞過 `taxonomy_v2.json` 自行硬編碼六風格清單 | 詞表分裂，`style_compat` 查表失準 | High |
| `json_adjustment/reclassify_styles.py` 直接寫入 `vlm_annotation/`（現況：`OUT = vlm_annotation/style_v2_annotations.jsonl`） | 加工層回寫詞表層目錄＝跨層寫入，產出物歸屬不明 | Medium（已知技術債，需 ADR 決定歸屬） |

**驗證指令（審查時實跑）：**

```bash
# 有沒有反向 import
rg -n "^\s*(from|import)\s+(rag_pipeline|json_adjustment|vlm_annotation)" \
   rag_pipeline json_adjustment vlm_annotation

# 有沒有繞過 taxonomy 硬編碼六風格
rg -n "scandinavian.*japanese.*modern_minimal" --glob '!*.json'

# 模組規模（判斷 God Object / Long Method 的起點）
wc -l rag_pipeline/*.py json_adjustment/*.py vlm_annotation/*.py
```

---

## Phase 1: Detect Smells

### Iron Rule

```
NO SMELL WITHOUT EVIDENCE
```

「感覺有問題」「好像不對」不算證據。每個 smell 必須附：

1. **檔案路徑＋行號** 或
2. **可量化指標**（方法行數、圈複雜度、依賴數量、N+1 查詢次數、p99 延遲等）

### Five-Dimension Scan Matrix

掃描必須覆蓋全部 5 個維度。即使某維度無 finding，也要在報告中明確聲明 "no findings"。

| 維度 | 對應 smell（節錄自 terminology.md） | 證據蒐集指令範例（本專案） |
| :--- | :--- | :--- |
| **Dependency 依賴** | Cyclic Dependency、Big Ball of Mud、Inappropriate Intimacy、Parallel Inheritance | `rg -n "^\s*(from\|import)\s+(rag_pipeline\|json_adjustment\|vlm_annotation)"` ／ 上節三層依賴表 ／ 產出檔流向圖 |
| **Modularity 模組化** | God Object、Long Method、Large Class、Feature Envy、Divergent Change、Shotgun Surgery | `wc -l rag_pipeline/*.py` ／ `rg -n "^def " rag_pipeline/retriever.py` 看函式行數分布 ／ 同一改動波及幾個檔 |
| **Performance 效能** | N+1 查詢、Switch Statements、Primitive Obsession（在熱路徑上） | `rg -n "for .*query_collection\|for .*\.predict"` 找迴圈內查 Chroma／打 reranker ／ `time .venv-rag/bin/python rag_pipeline/retriever.py "<需求>"` |
| **Distributed reliability 分散式可靠性** | 缺 Circuit Breaker、缺 Idempotent Consumer、缺 Outbox、缺 DLQ、雙寫不一致、Backpressure 缺失 | 本專案為**單機、無訊息佇列**；對應物是「外部依賴與批次可靠性」：`rg -n "retry\|timeout\|except"` 檢查 Anthropic／Ollama／HF Hub 呼叫；`rg -n "text_hash\|load_done"` 檢查批次續跑冪等；比對 `chroma_db/` 與 `rag_export/` 筆數檢查雙寫一致 |
| **Technical debt 技術債** | Lava Flow、Speculative Generality、Refused Bequest、Comments Smell、Middle Man、Temporary Field | `rg -n "TODO\|FIXME\|HACK"` ／ 死碼掃描（`taxonomy_v1.json`、`furniture_enriched_v1/v2.json`、已不存在的 `.venv/`） ／ 註解與程式是否矛盾（**專案尚未 git init，`git blame` 不可用**） |

### 維度 4 在本專案的對照（不可略過此維度）

| 通用檢查項 | RoomPilot 的對應物 |
| :--- | :--- |
| Circuit Breaker（外部依賴熔斷） | Anthropic API／本機 Ollama 失敗時的降級路徑：解析失敗是否有可用的最小 `parsed`，或至少給使用者可讀訊息？ |
| Idempotent Consumer（重複訊息不重做） | 批次續跑冪等：`reclassify_styles.py` 的 `load_done()`、`embed_v3.py --only-changed` 的 `text_hash` 比對；重跑不得產生重複列 |
| Outbox（避免雙寫不一致） | `embed_v3.py` 一次算向量、同時寫 `chroma_db/` 與 `rag_export/*.jsonl`；兩邊筆數／`text_hash` 必須一致 |
| DLQ（失敗訊息暫存） | `rag_export/embedding_failures.jsonl`（失敗清單）與標註流程的續跑檔 |
| Backpressure（抑制上游速率） | 批次併發與 API 額度：全量風格判定約 US$7；16 GB 機器上 UI 常駐 4.6 GB，批次不得與 UI 同跑 |
| Bulkhead（隔離故障） | 離線層故障不得影響線上檢索 —— 這正是禁止 `rag_pipeline` import 離線模組的理由 |

### Severity Definitions

| 等級 | 定義 | 範例（本專案） |
| :--- | :--- | :--- |
| **Critical** | 立即危害正確性或可用性，或會導致資料遺失 | `where` 混入 `rag_indexable` 導致全域 0 筆、`chroma_db/` 與 `rag_export/` 雙寫不一致、離線層與線上層反向 import |
| **High** | 6 個月內必修，否則阻礙可擴展性／團隊速度 | `retriever.py` 的 `search_item()` 同時做過濾＋排序＋去重（職責過載）、外部 LLM 呼叫完全無退路 |
| **Medium** | 影響可維護性，但可規劃 1-2 季處理 | 房型中文對照在 `app.py` 與 `retriever.py` 各一份、加工層回寫詞表層目錄、非熱路徑的重複讀檔 |
| **Low** | 風格或可讀性問題 | 命名不一致（`groups` / `category_group` 混用）、過度註解、Temporary Field |

### Smell Output Template

每個 finding 在 Phase 1 結束時必須能填完此表：

```
Smell:    <terminology.md 中的標準名稱>
Location: <絕對或專案相對路徑:行號>
Evidence: <一行可驗證的事實或指標>
Severity: Critical | High | Medium | Low
```

**找不到 5 個以上 smell 的審查通常不可信** — 不是系統完美，是審查太淺。挑戰自己再掃一次。

---

## Phase 2: Map to Principles

### Iron Rule

```
EVERY SMELL MUST VIOLATE A NAMED PRINCIPLE
```

對應不上原則的 smell 一律剔除。可選原則必須來自 `terminology.md` 的 Principles 區段（SOLID / KISS / DRY / YAGNI / LoD / Tell-Don't-Ask / Boy Scout Rule / Clean Architecture / Hexagonal / Onion）。

### Mapping Cheat Sheet（節錄）

| Smell | 違反原則 | 為什麼 |
| :--- | :--- | :--- |
| God Object | SRP | 一個類承擔多個變更理由 |
| Feature Envy | LoD | 過度與「非直接朋友」對話 |
| Long Parameter List | KISS / Tell-Don't-Ask | 暴露內部細節給呼叫方 |
| Duplicated Code | DRY | 同邏輯多處複製 |
| Speculative Generality | YAGNI | 為不存在的需求預留彈性 |
| Cyclic Dependency | DIP / Hexagonal | 內層依賴外層或彼此糾纏（如 `query_parser` ↔ `retriever` 互相 import） |
| Switch Statements | OCP / LSP | 新增類型必須改現有程式碼（如新增風格要動一長串 if/elif） |
| Refused Bequest | LSP | 子類無法替換父類 |
| 雙寫不一致 | Outbox（缺）/ Transaction Boundary | 跨資源無一致性保證（`chroma_db/` 與 `rag_export/` 分開寫） |
| 缺 Circuit Breaker | Bulkhead 隔艙原則 | 單點失敗會擴散（Anthropic 掛掉整個 UI 不可用） |
| 硬編碼六風格清單 | DRY / Single Source of Truth | 詞表分裂於 `taxonomy_v2.json` 之外 |

### Principle Match Output Template

```
Smell:        <Phase 1 finding>
Violates:     <原則名稱（terminology.md 編號）>
Why:          <一句話說明違反在哪>
Counter-evidence: <若反駁此原則違反，需提供什麼證據？>
```

`Counter-evidence` 欄位是防呆 — 強迫審查者預想反駁，避免主觀套用原則。

---

## Phase 3: Propose Fixes

### Iron Rule

```
EVERY FIX MUST CITE A PATTERN OR PRACTICE FROM terminology.md
```

不接受「重寫一下」「優化一下」這種無詞彙的建議。每個 fix 必須命名一個或多個 Pattern / Practice。

### Fix Proposal Template

```
For Smell:    <Phase 1 finding>
Violates:     <Phase 2 principle>

Option A (recommended):
  Pattern:    <terminology.md Pattern/Practice 名稱>
  Steps:      <3-5 條具體執行步驟>
  Effort:     S (< 1 day) | M (1-5 days) | L (> 1 week)
  Risk:       <破壞性 / 回歸風險 / 團隊熟悉度評估>
  ADR needed: Yes | No

Option B (alternative):
  ...同上格式...

Trade-off: <為何選 A 而非 B 的一句話>
```

**至少兩個方案**是強制要求 — 單一方案 = 沒做取捨。Trade-off 欄位必填。

### Common Smell-to-Fix Map（節錄）

| Smell | 候選 Pattern / Practice | 本專案的落點範例 |
| :--- | :--- | :--- |
| God Object | Extract Class、Compound Pattern (Composite/Strategy) | 把 `retriever.py` 拆成 filter／rank／compose 三個職責 |
| Long Method | Extract Method、Replace Conditional with Polymorphism | `search_item()`（約 60 行）抽出 `build_where` 後的評分段 |
| Feature Envy | Move Method、Introduce Service | `app.py` 直接翻找 `parsed` 內部結構 → 移到 `retriever` 的展示 DTO |
| Switch Statements | Strategy、State、Polymorphism | 每加一種風格就多一段 if → 改查 `taxonomy_v2.json` 的表 |
| Cyclic Dependency | Dependency Inversion、Anti-Corruption Layer | 解析與檢索共用的詞彙抽成第三個唯讀模組 |
| N+1 Query | Eager Loading、Batch Fetch、DataLoader Pattern | 迴圈內逐筆 `query_collection()` → 合併成一次批次查詢 |
| 缺 Idempotent | Idempotent Consumer、Idempotency Key | `text_hash` 作為冪等鍵（`--only-changed`）、標註流程的 `load_done()` |
| 雙寫不一致 | Outbox Pattern、Saga | `embed_v3.py` 同批寫 Chroma 與 `rag_export/`，寫完做筆數對帳 |
| 缺 Circuit Breaker | Circuit Breaker、Bulkhead、Retry+Backoff+Jitter | Anthropic／Ollama 失敗時的降級與退避 |
| Lava Flow | Strangler Fig、Branch by Abstraction | `taxonomy_v1.json`、`furniture_enriched_v1/v2.json` 的封存決策 |
| Speculative Generality | YAGNI Cleanup、Inline 化 | 只有一個實作卻抽了介面的參數（如未使用的 provider 分支） |

### ADR Trigger

任何 **Critical** 或 **High** 的 fix 必須建議寫入 `.claude-roompilot/context/decisions/architecture-review-{YYYY-MM-DD}-{topic}.md`，依 `subagent-context.md` 規則執行。

本專案務必寫 ADR 的變更類型：更換 embedding／rerank 模型、改動排序公式權重、
改動硬過濾與軟加權的界線、Chroma collection 改名或重建、三層模組邊界調整。

---

## Output Format

審查最終報告必須使用此骨架，**不可省略任何區段**。

```markdown
# Architecture Review: <Scope>

- **Date**: <YYYY-MM-DD>
- **Reviewer**: <agent / human>
- **Scope**: <模組路徑 / 服務名 / PR 範圍>
- **Commit range**: <git SHA range, 若適用；**專案尚未 git init** 時填 `N/A — 檔案清單：<...>`>

## Summary

- **Smells found**: <總數> (Critical: <n>, High: <n>, Medium: <n>, Low: <n>)
- **Dimensions covered**: Dependency / Modularity / Performance / Distributed / TechDebt
- **Recommended next action**: <一句話, 例如「先修 Critical 的 Outbox 缺失再合併」>
- **ADR candidates**: <數量>

## Findings

### [Critical] Smell: <名稱>

- **Evidence**: `path/to/file.py:123` — <一行事實>
- **Violates**: <原則名稱>
- **Why it matters**: <一句話>
- **Proposed fix**:
  - Option A: <Pattern> — <Effort: S/M/L> — <Risk>
  - Option B: <Pattern> — <Effort: S/M/L> — <Risk>
  - Trade-off: <一句話>
- **ADR needed**: Yes

### [High] Smell: <名稱>
...

### [Medium] Smell: <名稱>
...

## Dimension Coverage

| 維度 | Findings | Status |
| :--- | :--- | :--- |
| Dependency | <n> | covered / no findings |
| Modularity | <n> | covered / no findings |
| Performance | <n> | covered / no findings |
| Distributed reliability | <n> | covered / no findings |
| Technical debt | <n> | covered / no findings |

## ADR Candidates

- [ ] `architecture-review-<date>-<topic>.md` — <一句話標題>

## Open Questions

- <無法在審查中決定、需要 stakeholder 回答的問題>
```

---

## Forbidden Phrases

仿 `sunnydata-code-review` 規則，以下表述在審查報告中**禁止出現**：

| 禁止 | 必須 |
| :--- | :--- |
| "looks good" | "passes dimensions X, Y, Z with no findings" |
| "seems fine" | "no Critical/High findings; <n> Medium documented" |
| "should be ok" | "verified by <evidence>; pass" |
| "could be better" | "<smell name> at <location>; severity <level>" |
| "maybe consider" | "Option A: <pattern>; Option B: <pattern>; recommend A because <reason>" |
| "in my opinion" | "<principle> requires <X>; current code shows <Y>" |
| "perhaps refactor" | "Apply <Pattern> with effort <S/M/L> and risk <X>" |

---

## Integration with Other Skills

| 場景 | 流程 |
| :--- | :--- |
| 交付定案前（專案尚未 git init，無 PR） | `sunnydata-architecture-review` → 若無 Critical → `sunnydata-code-review`（行級，含六個坑與資料契約） |
| 新模組設計 | `architect` agent（設計）→ 實作 → `sunnydata-architecture-review`（驗收） |
| 技術債盤點 | `sunnydata-architecture-review`（找出所有 High+）→ 排序 → ADR 寫入 `.claude-roompilot/context/decisions/` |
| Onboarding 走讀 | `sunnydata-architecture-review`（產出系統地圖）→ 補入 `docs/RAG檢索系統說明.md` |
| 大型重構決策 | `sunnydata-architecture-review` → `architect` agent（重新設計受影響部分） |
| 換模型／改排序權重 | `sunnydata-architecture-review`（評估影響面）→ ADR → 實作 → CLI 實跑比對前後結果 |

---

## How to Invoke

### Direct invocation（主 agent 直接執行）

主 agent 載入此 skill，依三階段流程執行，產出報告。適合單次、範圍明確的審查。

### Via subagent（dispatch architecture-reviewer.md）

使用 `architecture-reviewer.md` 作為 subagent 模板，dispatch 給專責 agent 執行，回傳結構化報告。適合：

- 範圍大（三層全掃：`rag_pipeline` + `json_adjustment` + `vlm_annotation`）
- 需要與其他 subagent 平行執行
- 主 agent 想保留 context window

dispatch 後的結論依 `subagent-context.md` 規則寫入 `.claude-roompilot/context/decisions/`。

### Reference loading

`terminology.md` 預設**不**載入 context — 由 reviewer 在需要查特定詞彙時主動 Read。這降低 skill 啟動成本。

---

## Quick Reference

| 我想… | 用什麼 |
| :--- | :--- |
| 找出系統有哪些壞味道 | Phase 1 + 五維度矩陣 |
| 知道某 smell 的標準名稱 | `terminology.md` Smells 區段 |
| 為某 smell 找修復模式 | `terminology.md` Patterns 區段 + Smell-to-Fix Map |
| 評估重構優先級 | Severity 表 + Effort 評估 |
| 確認某個 import 合不合法 | 本檔〈本專案的三層模組邊界〉的允許／禁止依賴表 |
| 把審查報告寫成 ADR | `.claude-roompilot/context/decisions/` + `subagent-context.md` 範本 |
| 大型範圍／平行審查 | `architecture-reviewer.md` subagent |
