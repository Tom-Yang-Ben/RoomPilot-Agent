# RoomPilot Agent 架構圖

最後更新：2026-08-01
適用分支：`bella-test1`
權威來源：`backend/agent/AGENTS.md`、`backend/agent/IMPLEMENTATION_REPORT.md` 與 `backend/agent/` 程式碼

> 本文件只畫 **`backend/agent/`（owner: Yen）** 的內部架構。整個產品的系統架構見
> [系統架構圖](系統架構圖.md)；使用者八步操作流程見
> [使用者流程與系統架構圖](使用者流程與系統架構圖.md)。

---

## 0. 一句話定位

Master 是**程式寫死的 state machine**（不呼叫 LLM），負責流程、迴圈上限與人為決策點；
LLM 只在 skill 內做**語意決策**；座標與合法性只由 `backend/engine/` 決定；
所有共享狀態走 `DocStore`（blackboard），可 checkpoint／undo／整包序列化保存。

---

## 1. 分層架構

```mermaid
flowchart TB
    subgraph CALLER["呼叫端（backend/server/）"]
        SRV["FastAPI orchestrator<br/>build_master() → start() → submit() → undo()<br/>【※ 目前尚未接線】"]
    end

    subgraph L1["Master 層 — master.py（程式流程，不呼叫 LLM）"]
        M["MasterAgent<br/>state machine ＋ HITL 暫停點"]
        CFG["MasterConfig<br/>修復迴圈 ≤3 · 改圖 ≤1 · 色卡 ≤3"]
        CK["checkpoint stack<br/>每次 submit 前快照，undo 可還原上一動"]
    end

    subgraph L2["Sub-agent 層 — subagents/（skills ＋ tools 的組裝）"]
        FA["Furniture Agent<br/>任務 1–3 ＋ 修復"]
        VA["Validation Agent<br/>任務 4 雙軌驗證"]
        GA["Gen_Pic Agent<br/>任務 5–6 ＋ 失敗政策"]
        RA["Report Agent<br/>任務 7 設計手冊"]
    end

    subgraph L3["Skill 層 — skills/&lt;name&gt;/（語意決策；每個都有 deterministic fallback）"]
        SREQ["requirements<br/>三分流＋家電防線"]
        SFUR["furniture<br/>A/B 策略選件"]
        SVAL["validation<br/>軟規則與需求滿足度"]
        SGEN["genpic<br/>兩階段生圖 prompt"]
        SEDIT["editpic<br/>鎖定清單改圖"]
        SREP["report<br/>手冊章節"]
    end

    subgraph L4["Tool 層 — tools/（deterministic，不呼叫 LLM）"]
        T1["read_layout · read_rules"]
        T2["rag_furniture"]
        T3["pick_furniture · place_furniture"]
        T4["engine_validate"]
        T5["genpic_info · fetch_image"]
        T6["read_docs · render_pdf"]
    end

    subgraph L5["Docs 層 — documents.py"]
        DS["DocStore（blackboard）<br/>plain dict · JSONB-ready · checkpoint/undo"]
    end

    subgraph GW["Gateway — llm.py"]
        LLM["OpenRouterGateway<br/>文字＋生圖單一入口<br/>stdlib urllib＋certifi，業務碼禁 httpx"]
    end

    subgraph EXT["外部邊界（不屬於 agent）"]
        ENG["backend/engine/（Ancai）<br/>placement · clearance<br/>【唯一座標與合法性來源】"]
        RAG["backend/spatial_data/rag（Django）<br/>FurnitureRagService<br/>【只檢索與排序】"]
        ORT["OpenRouter API<br/>文字模型＋nano banana / nano banana 2"]
    end

    SRV --> M
    M --- CFG
    M --- CK
    M --> FA
    M --> VA
    M --> GA
    M --> RA
    M --> T1
    M <--> DS

    FA --> SREQ
    FA --> SFUR
    VA --> SVAL
    GA --> SGEN
    GA --> SEDIT
    GA --> T5
    RA --> SREP

    SFUR --> T2
    SFUR --> T3
    SVAL --> T4
    SGEN --> T5
    SREP --> T6

    SREQ -.-> LLM
    SFUR -.-> LLM
    SVAL -.-> LLM
    SGEN -.-> LLM
    SEDIT -.-> LLM
    SREP -.-> LLM

    T3 --> ENG
    T4 --> ENG
    T2 --> RAG
    LLM --> ORT
```

**讀圖重點**

- 實線＝流程依賴；虛線＝LLM 呼叫（沒有 `OPENROUTER_API_KEY` 時整條虛線斷開，skills 走 deterministic fallback，流程仍可跑完，只有生圖階段會以可讀原因暫停）。
- 只有 `place_furniture` 與 `engine_validate` 兩個 tool 碰得到 engine；skill 與 LLM 一律不產生座標。
- Master 直接持有 `ReadLayoutTool` / `ReadRulesTool`，其餘 tool 都由 skill 呼叫。

---

## 2. Master state machine

```mermaid
stateDiagram-v2
    [*] --> AWAIT_QUESTIONNAIRE : start(layout_json, rules_json)

    AWAIT_QUESTIONNAIRE --> AWAIT_QUESTIONNAIRE : RAG 檢索失敗，以 retry 重試
    AWAIT_QUESTIONNAIRE --> AWAIT_PLAN_CHOICE : S1 需求整理 → S2 RAG → S3 挑擺 A/B → S4 驗證（修復迴圈 ≤3）

    AWAIT_PLAN_CHOICE --> AWAIT_PALETTE_CHOICE : 擇一方案＋視角 → S5a 單房色卡生圖
    AWAIT_PLAN_CHOICE --> AWAIT_FEEDBACK : 無色卡選項時直接 S5b

    AWAIT_PALETTE_CHOICE --> AWAIT_FEEDBACK : 擇一色卡 → S5b 全房生圖＋鎖定清單

    AWAIT_FEEDBACK --> AWAIT_FEEDBACK : S6 改圖成功（額度 -1）
    AWAIT_FEEDBACK --> DONE : skip 或無意見 → S7 設計手冊 PDF

    AWAIT_PALETTE_CHOICE --> AWAIT_RENDER_RETRY : 生圖主模型與備援皆失敗
    AWAIT_FEEDBACK --> AWAIT_RENDER_RETRY : 生圖主模型與備援皆失敗
    AWAIT_RENDER_RETRY --> AWAIT_PALETTE_CHOICE : retry
    AWAIT_RENDER_RETRY --> AWAIT_FEEDBACK : retry 或 skip
    DONE --> [*]
```

**計數器全部在 Master，不交給 LLM 自律**

| 限制 | 數值 | 位置 | 備註 |
|---|---|---|---|
| 驗證失敗修復迴圈 | ≤ 3 輪 | `MasterConfig.repair_max_rounds` | A/B 各自獨立計數 |
| 改圖 | ≤ 1 次 | `MasterConfig.edit_max` | **只有成功才扣額度**，失敗重試不扣 |
| 色卡比對張數 | ≤ 3 組 | `MasterConfig.palette_limit` | 取需求文件的 `palette_options` 前 N 組 |
| 單一模型生圖重試 | 3 次 | `ImagePolicy.max_attempts_per_model` | 達上限 → 記錄原因 → 換備援模型再試 3 次 |
| undo | 無上限 | `checkpoint stack` | 每次 `submit()` 前自動快照 |

輸入不合法（`ValueError`）**不算一動**：Master 會自動 `undo()` 並要求重新提交。

---

## 3. 一次完整流程

```mermaid
sequenceDiagram
    autonumber
    participant U as 使用者／Server
    participant M as MasterAgent
    participant D as DocStore
    participant F as Furniture Agent
    participant V as Validation Agent
    participant E as backend/engine
    participant G as Gen_Pic Agent
    participant R as Report Agent

    U->>M: start(layout_json, rules_json)
    M->>D: LAYOUT / RULES / USER_CHOICES
    M-->>U: 暫停 AWAIT_QUESTIONNAIRE

    U->>M: submit({questionnaire})
    M->>F: S1 organize_requirements
    F-->>D: REQUIREMENTS（硬／軟／家電三分流）
    M->>F: S2 retrieve_candidates（RAG）
    F-->>D: CANDIDATES

    loop 方案 A 與 B
        M->>F: S3 propose（A 動線優先／B 收納優先）
        F->>E: place_furniture（唯一座標來源）
        E-->>F: placed / failed
        M->>V: S4 validate
        V->>E: check_placement_with_clearance
        E-->>V: 硬違規清單
        V-->>M: ValidationReport（軟警告不擋）
        loop 未通過且 < 3 輪
            M->>F: repair（換小／移除／重排）→ 重新 place → 重新 validate
        end
        M->>D: FURNITURE_LIST:X / SCENE:X / VALIDATION:X
    end
    M-->>U: 暫停 AWAIT_PLAN_CHOICE（附 A/B 摘要）

    U->>M: submit({variant, viewpoints, scene_override?})
    M->>G: S5a 單房 × N 組色卡生圖
    G-->>D: IMAGES
    M-->>U: 暫停 AWAIT_PALETTE_CHOICE

    U->>M: submit({palette_id})
    M->>G: S5b 逐房全房生圖 ＋ 產生鎖定清單
    G-->>D: IMAGES / LOCK_MANIFEST
    M-->>U: 暫停 AWAIT_FEEDBACK（改圖剩餘 1 次）

    U->>M: submit({feedback, room_id}) 或 {skip:true}
    opt 有意見且額度未用完
        M->>G: S6 改圖（依鎖定清單，只改允許項）
        G-->>D: IMAGES
    end
    U->>M: submit({skip:true})
    M->>R: S7 build_manual
    R-->>D: MANUAL（PDF 已輸出）
    M-->>U: DONE
```

---

## 4. Skills 與 Tools

### Skill 層（`skills/<name>/`）

每個 skill 一個資料夾，**兩檔分層**：

- `SKILL.md`＝**宣告層**：frontmatter ＋ 提示詞 ＋ 輸出 schema ＋ 流程說明。**提示詞的唯一來源**，`load_skill_doc()` 於匯入期解析驗證。改提示詞不需動 Python，但要跑 skills 測試。
- `__init__.py`＝**流程層**：呼叫 gateway、驗證輸出、**deterministic fallback**。

| Skill | 職責 | 關鍵約束 |
|---|---|---|
| `requirements` | 問卷 → 硬約束／軟偏好／家電三分流 | `_enforce_contracts()` 是家電防線：冰箱、洗衣機、冷氣、電視只能進 `appliances` |
| `furniture` | A/B 兩套策略選件（白名單＝RAG 候選） | 只輸出語意 `PlacementHint`（free／adjacent／overlay），**不含座標** |
| `validation` | 軟潛規則與需求滿足度（advisory 軌） | 硬規則走 `engine_validate`，LLM 不參與 |
| `genpic` | 兩階段生圖 prompt ＋ 鎖定清單 | 家電只在此進 context |
| `editpic` | 依鎖定清單產生改圖指令 | 明列不可變動元素 |
| `report` | 設計手冊章節統整 | 缺價一律保留待確認，不補猜 |

### Tool 層（`tools/`）

deterministic 函式，**不呼叫 LLM**；每個 tool 的 `contract` 可直接餵給 function calling。

| Tool | 輸出 | 外部依賴 |
|---|---|---|
| `read_layout` | `LayoutDoc` | — |
| `read_rules` | `RulesDoc`（軟潛規則） | — |
| `rag_furniture` | `CandidateListDoc` | `backend/spatial_data/rag`（可注入替換）|
| `pick_furniture` | 白名單過濾與擺放排序 | — |
| `place_furniture` | `SceneDoc`（placed／failed） | **`backend/engine/placement`** |
| `engine_validate` | `HardViolation[]` | **`backend/engine/clearance`** |
| `genpic_info` | 生圖 context 整理 | — |
| `fetch_image` | 取回舊圖供改圖 | — |
| `read_docs` | 讀 DocStore 供出報告 | — |
| `render_pdf` | 設計手冊 PDF | Pillow（點陣排版，文字不可選取） |

> `place_furniture` 採 **engine 能力偵測**：本分支引擎只有 `place_furniture` /
> `place_furniture_batch`，`adjacent` / `overlay` 意圖自動降級為 free 自由擺放並在
> hint note 註記——agent 層**不自行實作幾何補位**。

---

## 5. Docs 層（DocStore blackboard）

```mermaid
flowchart LR
    subgraph IN["輸入"]
        Q["questionnaire"]
        L["layout"]
        RU["rules"]
    end
    subgraph MID["流程產出"]
        RQ["requirements"]
        CA["candidates"]
        FL["furniture_list:A / :B"]
        SC["scene:A / :B / :chosen"]
        VD["validation:A / :B"]
    end
    subgraph OUT["交付產出"]
        LK["lock_manifest"]
        IM["images"]
        MA["manual"]
    end
    UC["user_choices<br/>方案／色卡／視角／意見歷程"]

    Q --> RQ
    L --> RQ
    RQ --> CA --> FL --> SC --> VD
    VD -. "未通過 → 修復" .-> FL
    RU --> VD
    SC --> LK --> IM --> MA
    UC -.-> SC
    UC -.-> IM
```

- 內部一律存 **plain dict**，dataclass 只是建構／讀取時的型別化外殼。
- 每份文件帶 `schema_version`（`roompilot.agent.*.v1`），以「可直接存進 PostgreSQL JSONB」為設計原則。
- `master.to_dict()` / `restore()` 也是 plain dict，可整包存進專案 storage。

---

## 6. 不可違反的邊界

| 邊界 | 規則 |
|---|---|
| **幾何** | 座標與合法性只由 `backend/engine/` 判定；LLM 與 skills 不得產生或修改座標 |
| **RAG** | 家具向量 RAG 只解析需求、檢索與排序；不可用時回報可讀錯誤，**不得改用未驗證資料** |
| **家電** | 冰箱、洗衣機、冷氣、電視只進需求文件 `appliances` 與生圖 context，**不進 2D/3D 配置** |
| **fallback** | 所有 LLM skill 必須有 deterministic fallback（無金鑰可跑完流程，生圖除外） |
| **提示詞** | 只能寫在各 skill 的 `SKILL.md`；改提示詞不動 Python，但要跑 skills 測試 |
| **迴圈與額度** | 由 Master 程式控制，不交給 LLM 自律 |
| **單位** | 公分制；場景 placed 條目沿用 `backend.engine.schema.placed_to_dict`，由擺家具 tool 附加 `coordinate_unit: "cm"` |
| **re-export** | 套件 `__init__` 的 room_pilot2 re-export 被 `backend/server/` 依賴，**不可移除** |

---

## 7. 現況與缺口（2026-08-01 實測）

### 已接線 vs 未接線

```mermaid
flowchart LR
    subgraph WIRED["✅ 目前線上會執行"]
        K["agent/knowledge.py<br/>family_of · prompt_rules"]
        S["agent/select.py<br/>parse_selections · request_selections"]
        P["agent/place.py<br/>placement_hints · resolve_placements"]
    end
    subgraph PENDING["⏸ 已實作但尚未接線"]
        MST["master.py ＋ subagents/<br/>skills/ ＋ tools/ ＋ documents.py ＋ llm.py"]
    end
    SRV["backend/server/main.py<br/>backend/server/scene_service.py"]

    K --> SRV
    S --> SRV
    P --> SRV
    MST -. "待建立 orchestrator" .-> SRV
```

- `main.py:23-24` 與 `scene_service.py:15` 只 import room_pilot2 三模組；`build_master` / `MasterAgent` 在 `backend/agent/` 之外**尚無任何呼叫端**。
- 接線方式已定義：`from backend.agent import build_master` → `master.start(layout_json)` → `master.submit(payload)` → `master.undo()`；`master.to_dict()` 可直接存進 `.runtime/projects.sqlite3` 的專案狀態。

### 範圍註記

Gen_Pic（nano banana 生圖／改圖）與設計手冊 PDF 屬**提案功能**，超出現行五階段 Demo
範圍（現行 Demo 終點是 3D 白模取景＋提案 PNG）。未設 `OPENROUTER_API_KEY` 時 Master
會在生圖階段以可讀原因暫停並可 skip，不影響主線。

### 已知限制

- PDF 為 Pillow 點陣排版（文字不可選取）；換向量排版時替換 `tools/render_pdf.py` 即可，介面不變。
- 生圖「未報錯但品質不佳」的判定尚未定義。
- `FurnitureRagService.search` 的實際回傳欄位需在有 DB 環境實測對齊。

### 驗證指令

```bash
uv run pytest backend/agent/tests -q   # 2026-08-01: 24 passed
uv run pytest tests/ -q                # 2026-08-01: 122 passed, 1 skipped
```

---

## 8. 相關文件

- [系統架構圖](系統架構圖.md)
- [使用者流程與系統架構圖](使用者流程與系統架構圖.md)
- [`backend/agent/AGENTS.md`](../backend/agent/AGENTS.md)
- [`backend/agent/IMPLEMENTATION_REPORT.md`](../backend/agent/IMPLEMENTATION_REPORT.md)
- [Agent 前後端契約](contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md)
