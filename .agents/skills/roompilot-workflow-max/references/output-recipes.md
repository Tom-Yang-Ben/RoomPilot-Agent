# 輸出 Recipes

`.claude/output-styles/` 的角色視角已轉為下列可選 recipes；Codex 不依賴 Claude
`/output-style` 或 hooks。只選與任務相關的輸出。

| Recipe | 必要內容 | RoomPilot 化要求 |
|---|---|---|
| Product/PRD | 問題、目標、KPI、story、scope/non-goals | 對齊現行八步與 owner，不重寫產品現況 |
| BDD | Given/When/Then、happy/sad/edge、observable result | 覆蓋保存、reload、409/503、placement failure 等真實行為 |
| Architecture | 現況/目標、component、sequence、data、decision | FastAPI 模組化單體；owner folder 通常是 component 非 service |
| DDD/domain | 語彙、boundary、invariant、command/event | 尊重 owner 邊界；不強迫 class/aggregate 化現有函式 |
| API contract | endpoint、schema、error、auth、version、compatibility | snake_case、`_cm`/`_m2`、schema version、現行 FastAPI/Pydantic |
| TDD/module | test list、red/green/refactor、pre/post/invariant | 使用 repository pytest 與現有 module paths |
| Review | findings、severity、evidence、minimal fix、tests | 先找 correctness/security/regression；不自動改未授權內容 |
| Security | threat/data/secret/auth/input/dependency/readiness | 不複製 OAuth token、Claude settings 或未 pin remote recipes |
| Database | table/view/query/migration/rollback | Kai/Bella 邊界；不宣稱缺失的 Phase 3/4 tools 可重建 |
| Python backend | domain/service/repository/API/test changes | 落在現有 `backend/<owner>/`，不得新增泛用 `src/` 第二套 app |
| Frontend | state、DOM/Three.js、API、a11y、performance、browser QA | 預設 `backend/server/static/`；React/Storybook 僅限明確原型 |
| Integration | producer/consumer、fixture、failure injection、E2E | 以 owner contract 與兩側 tests 為核心 |
| Data evolution | schema version、compatibility、lineage、drift | cm、layout/scene、confidence/evidence、persistence |
| CI/readiness | stages、commands、artifacts、thresholds | 只列現行可執行命令；不自動更新依賴或安裝 hooks |
| Visualization | C4、sequence、ERD、dependency map | 圖需反映真實 process/DB/deployment，不套示例架構 |

## 建議輸出順序

```text
需求/BDD
→ ADR/Architecture
→ API/Data/Module contract
→ WBS work packets
→ Implementation
→ Review/Security
→ Validation/Delivery
```

小任務可直接從 module contract 進入 implementation；診斷或 review 任務不應產生
未獲授權的 implementation。
