# 工作流與產物路由

## 模式判斷

| 條件 | 模式 | 必要產物 |
|---|---|---|
| 單 owner、行為清楚、無 schema/persistence 影響 | Focused | module spec/tests、diff review |
| 跨 owner、API/schema、保存、SQL、production frontend | Full | brief/BDD、ADR/architecture、contract、work packets、雙端測試 |
| 使用者要求平行，且有兩個以上互不重疊 packet | Maximum parallel | 穩定 contract、WBS/work packets、單一 integrator、平行驗證 |
| 只診斷或 review | Evidence-only | findings、根因證據、風險；不寫修復除非另有授權 |

## 產物選擇

| 需求 | 使用模板 |
|---|---|
| 定義目標、範圍、KPI、story、非目標 | `assets/templates/02-task-brief-prd.md` |
| 業務可觀測 acceptance | `assets/templates/03-bdd-acceptance.md` |
| 需取捨且影響邊界/長期維護 | `assets/templates/04-adr.md` |
| C4/component/sequence/data/deployment 視圖 | `assets/templates/05-architecture-change.md` |
| API、schema、error、版本、相容 | `assets/templates/06-api-data-contract.md` |
| 函式/module precondition、invariant、tests | `assets/templates/07-module-spec-tests.md` |
| 新檔案位置、目錄責任 | `assets/templates/08-project-structure.md` |
| producer/consumer/import/call DAG | `assets/templates/09-dependency-map.md` |
| component/class/interface 關係 | `assets/templates/10-component-relationships.md` |
| 實作後 findings 與最小重構 | `assets/templates/11-code-review-refactor.md` |
| 正式 frontend 技術分層、效能、a11y | `assets/templates/12-frontend-technical.md` |
| secrets/auth/input/data/readiness | `assets/templates/13-security-readiness.md` |
| 真實部署、health、rollback、incident | `assets/templates/14-deployment-runbook.md` |
| 文件、連結、命令、維護責任 | `assets/templates/15-documentation-maintenance.md` |
| owner/file-bound work packets 與 waves | `assets/templates/16-wbs-work-packets.md` |
| 八步 journey、頁面、CTA、route/state | `assets/templates/17-frontend-ia.md` |

不要為小變更產生整套文件。選擇能降低決策、契約或驗證風險的最小集合。

## Full 模式 Gate

1. **Preflight Gate**：規範、owner、contract、status、輸入輸出與測試已盤點。
2. **Requirement Gate**：scope/non-goals/acceptance 已可測量，沒有重寫八步產品。
3. **Contract Gate**：schema、單位、版本、保存、錯誤與 producer/consumer 已固定。
4. **Plan Gate**：每個 packet 的檔案不重疊，shared files 有單一 writer。
5. **Implementation Gate**：只在現有 owner path 內加入最小相容行為。
6. **Review Gate**：diff、owner 邊界、安全、fallback 與維護性已審查。
7. **Validation Gate**：targeted、雙端、integration、full gates 已依風險執行。
8. **Delivery Gate**：changed/verified/unverified/risk 已清楚交付。

## 文件放置

- 正式跨模組 schema 只放 `docs/contracts/`，不要複製到 skill 形成第二來源。
- 一次性設計產物依使用者要求放入 `docs/` 或指定位置；模板本身留在 skill assets。
- Runtime、WBS 時間紀錄、prompt/response、session ID 與秘密不寫入 repository。
