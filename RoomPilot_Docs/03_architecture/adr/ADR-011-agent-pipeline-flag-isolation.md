# ADR-011: Agent 並存管線以環境旗標隔離，不動 live 路徑 (Agent Pipeline Flag Isolation) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准） ｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-AGT owner（Yen）；架構審閱與 Gate 簽核待產品 owner
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
>
> **本文件回答**：為什麼 `backend/agent/` 的 MasterAgent 管線是「與第 6 步並存、由環境旗標關閉」而不是取代 live 路徑、也不是另開一個服務，以及這個選擇換來什麼、欠下什麼。
> **本文件不含**：管線內部的 sub-agent 與 skill 結構（去 [`../../04_design/lld.md`](../../04_design/lld.md)）、端點欄位級契約（去 [`../../04_design/api_spec.md`](../../04_design/api_spec.md) 與 [`openapi-agent-rag-v1.yaml`](../../04_design/openapi-agent-rag-v1.yaml)）、系統全貌與模組邊界（去 [`../sad.md`](../sad.md)）、幾何權威歸屬（去 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：`backend/agent/` 有一套 MasterAgent ＋ 四個 sub-agent（Furniture／Validation／Gen_Pic／Report）的管線，帶五個 HITL 暫停點（`master.py:47-52`）。第 6 步 live 路徑則是「LLM 選件 ＋ engine 擺放 ＋ `resolve_placements` 修復」，由 `scene_service` 承載。兩者要在同一個 FastAPI app 內共存，但 DEC-001 明文不允許第二條交付路徑。
- **問題**：兩條路徑的 document model 不同——agent 側是 `SceneDoc`／`documents`，server 側是 `site_payload`／engine objects（`agent_pipeline_service.py:17-22`）。在轉接層與輸出對帳都還沒做之前，管線**不能宣稱與 step 6 等價**；但不合併進主 app 就無法在同一 runtime 拿同一批家具跑兩條路徑做比對。
- **驅動因素／約束**：

| 類型 | 內容 | 佐證 |
| :--- | :--- | :--- |
| 約束 | 不另開第二條交付路徑（DEC-001）、不建第二套正式前端 | `AGENTS.md:58`；[`ADR-010`](./ADR-010-static-frontend-and-eight-step-collapse.md) |
| 約束 | 家具合法位置只由 `backend/engine/` 判定 | `AGENTS.md:54`；[`ADR-002`](./ADR-002-engine-sole-geometry-authority.md) |
| 約束 | 專案進度快照有 2 MB 上限，且會被顯示字串壓縮邏輯改寫 | `project_store.py:11,224` |
| 驅動 | 需要一條可隨時回退、且能被真正呼叫的第二路徑來驗證一致性 | `agent_pipeline_service.py:1-11` |

## 2. 考量的選項

### 2.1 選項 A：直接以 agent 管線取代第 6 步 live 路徑

- **描述**：把 `scene_service` 的選件與擺放換成 MasterAgent 流程，八步前端直接改打 agent 端點。
- **優點**：一次消滅雙路徑與雙套選件規則，不需要對帳機制。
- **缺點**：**被放棄的直接原因**——(1) 轉接層未實作，agent 側的 `FurnitureListDoc` 與 server 側選件 dict／engine objects 之間沒有雙向映射（`agent_pipeline_service.py:17-22`）；(2) 管線的選件入口 `skills/furniture/__init__.py:76-108` 只做候選白名單驗證與 `fallback_pick`，`tools/pick_furniture.py:8-20` 完全沒有 import `knowledge`，因此 FR-051 的房型基礎家具、客廳三件、房型白／黑名單、每房上限 8 件等潛規則在這條路徑上**不存在**（OPEN-39），直接換會讓選件品質退化且無測試可證。
- **成本／複雜度**：高（且在轉接與規則補齊前無法驗收）。

### 2.2 選項 B：agent 管線另立第二個服務或掛到 `frontend3d/`

- **描述**：獨立 FastAPI app／獨立部署承載 agent 管線，或用次要原型前端當它的 UI。
- **優點**：與 live 完全物理隔離，改壞不影響正式產品。
- **缺點**：直接違反 DEC-001（不另開第二條交付路徑）與 `AGENTS.md:58`（不得以 `frontend3d/` 取代正式前端）；且兩個 process 無法共用同一份 runtime 狀態，對帳要再造跨服務資料搬運，成本高於它避開的風險。
- **成本／複雜度**：高。

### 2.3 選項 C：長期 feature branch，不合併

- **描述**：管線留在未合併分支，需要驗證時才手動切分支跑。
- **優點**：main 上零程式碼、零風險。
- **缺點**：無法在同一 runtime 內以同一批 step 6 選定家具跑兩條路徑對帳（對帳正是本管線目前唯一有訊號的產出，見 `agent_reconcile_service.py:77-141`）；且與 live 的 merge 債隨時間單調上升，與既有多分支整合痛點同源。
- **成本／複雜度**：中（風險延後而非消除）。

### 2.4 選項 D（採用）：合併進同一 app，但以環境旗標預設關閉

- **描述**：路由與服務層進主 app，`ROOMPILOT_AGENT_PIPELINE` 未設即等同關閉，受閘門的路由一律 404。
- **優點**：live 零改動、預設零暴露、可在同一 runtime 對帳、回退成本＝移除環境變數。
- **缺點／成本**：程式碼與並存的選件規則仍在 repo 內累積（OPEN-39）、旗標開啟後無鑑權；成本／複雜度低。

## 3. 決策

**選擇**：選項 D。

**理由**：旗標是這四個選項裡唯一同時滿足「不動 live」與「能對帳」的作法。落地形式：

| 面向 | 實作 | 佐證 |
| :--- | :--- | :--- |
| 旗標語意 | `ROOMPILOT_AGENT_PIPELINE`；`{"", "0", "false", "no", "off"}` 皆為關閉，**未設＝空字串＝關閉** | `agent_pipeline_service.py:32,42-43` |
| 閘門 | `_require_pipeline_enabled()` 未啟用時回 404，訊息含可照做的啟用指引 | `main.py:3510-3516` |
| 受閘門路由 | 四支專案範圍（start／submit／undo／get）＋ 對帳共五處呼叫閘門 | `main.py:3518,3537,3549,3559,3569`；`main.py:3521,3540,3552,3562,3572` |
| 永遠可查 | `GET /api/agent/pipeline/status` 不受閘門，回 `enabled`／`gateway_configured`／`flag` | `agent_pipeline_service.py:46-51`；`main.py:3504-3508` |
| 狀態不污染 live | 序列化到 `runtime_dir/agent_pipeline/<project_id>.json`，刻意不進 workflow blob | `agent_pipeline_service.py:8-11,54-60,78-81` |
| live 零耦合 | 靜態前端 `scene_v2.js`／`index.html` 對 `agent/pipeline` 零命中 | `scene_v2.js`、`index.html`（grep 0） |
| 對帳範圍 | 同一批件跑 Path A（`scene_service.generate_layout`）與 Path B（`PlaceFurnitureTool` → `EngineValidateTool`），只比家族覆蓋＋合法性，**不比座標** | `agent_reconcile_service.py:11-19,96-141` |

不比座標是刻意取捨：兩條路徑座標系不同（step 6 房中心原點、旋轉與引擎反向；引擎角原點），而合法性兩邊都呼叫同一支 `backend.engine.clearance.check_placement_with_clearance`，比座標既脆弱又多半是恆等式（`agent_reconcile_service.py:11-19`）。這與 ADR-002「幾何唯一權威在 engine」一致。

## 4. 後果

### 4.1 得到什麼

- 第 6 步 live 路徑零改動；旗標未設時並存管線在外部完全不可達（404），Pilot 預設暴露面為零，回退＝移除環境變數並重啟，不需 revert 程式碼。
- 對帳有可執行證據：寬敞房兩件家具兩條路徑家族覆蓋一致且 agent 側 0 硬違規（`test_agent_reconcile_service.py:33-43`）；旗標解析與跨請求狀態往返有煙霧測試（`test_agent_pipeline_service.py:17-38`）。
- 管線狀態含生圖 base64，放獨立檔避開 2 MB 快照上限與顯示字串壓縮（`project_store.py:11,224`）。

### 4.2 付出什麼

| 代價 | 內容 | 佐證／登記 |
| :--- | :--- | :--- |
| 選件規則三套並存 | live 多房 `select.parse_selections` 有同族一款去重（`select.py:245-248`）；live 單房 `choose_furniture_items` 只以 `furniture_id` 去重、僅床有特例（`scene_service.py:510,631,778-790`）；並存管線 `skills/furniture.choose()` 兩者皆無 | **OPEN-39**（FR-051、FR-052、FR-053） |
| 餐椅張數兩套 | 單房 `min(max(2, 入住人數 or 2), dining_chair_target(桌寬))`（`scene_service.py:225-256`）vs 多房直接用 `dining_chair_target`（`select.py:303-349`；`knowledge.py:103-113`） | **OPEN-39**；ACPT-045 目前只覆蓋多房路徑 |
| 等價性未證 | 資料轉接與輸出對帳兩層未做；hint 成組邏輯不對齊；選件階段（RAG／LLM）不在對帳範圍 | `agent_pipeline_service.py:17-22`；`agent_reconcile_service.py:21-25` |
| 併發受限 | 單一全域鎖序列化**所有專案**的管線操作 | `agent_pipeline_service.py:28-30,84,95,105,115`（NFR-018） |
| 無鑑權、無保留期 | 旗標開啟後五支路由無帳號／權限控制；`.runtime/agent_pipeline/*.json` 無清理或保留期機制（repo 內查無） | 待確認：DEC-014／OPEN-02（服務邊界）、DEC-015（保留期，承接 [`../../06_ops/runbook-runtime-storage-growth.md`](../../06_ops/runbook-runtime-storage-growth.md)、RB-009） |

### 4.3 什麼時候該重評這個決策

任一條成立即重開本 ADR（不是「有空再看」）：

1. `/api/agent/pipeline/reconcile` 在真實 step 6 選件（非煙霧測試資料）上出現 `consistent: false`，或 `divergence.families_only_in_*` 非空——代表兩條路徑已實質分歧，旗標隔離不再只是延後合併。
2. OPEN-39 由 owner 拍板為「單一規則來源」——此時三套選件規則必須收斂，本 ADR 的「並存」前提消失。
3. 有任何 live 程式碼（`scene_v2.js`、`index.html` 或第 6 步 server 路徑）開始呼叫 `agent/pipeline` 端點——目前 grep 為 0，一旦非 0 即代表隔離被打破。
4. 旗標預計在非 Pilot 環境開啟——此時 DEC-014 的鑑權與 DEC-015 的資料保留期必須先核准（OPEN-02）。
5. 全域鎖成為量測到的瓶頸（多專案同時操作管線出現排隊）——改 per-project 鎖需重審 NFR-018 的敘述。

## 5. 執行計畫

1. 現況已落地（本 ADR 為追認）：旗標、五支受閘門路由、狀態檔、對帳端點與兩份煙霧測試皆在 HEAD `8f378b24`。
2. 把 `ROOMPILOT_AGENT_PIPELINE` 的預設關閉語意寫入 [`../../06_ops/deployment_and_operations.md`](../../06_ops/deployment_and_operations.md) 的環境變數清單。
3. OPEN-39 提交 owner 裁決；裁決前不得把任一套選件規則宣告為規格（承接 [`../../04_design/lld.md`](../../04_design/lld.md)），並由 TC-046 覆蓋「旗標未設時四支專案路由 404 且 `/status` 仍回 200」（承接 [`../../05_qa/test_plan.md`](../../05_qa/test_plan.md)）。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待具名（產品 owner） | 待核准：本 ADR 的「已接受」為現況追認，非業務拍板 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 上游決策 | DEC-001（不另開第二條交付路徑）、DEC-007（家具只來自已驗證型錄）；業務論述見 [`../../01_requirements/brd.md`](../../01_requirements/brd.md) §7 |
| 觸發需求 | FR-050、FR-051、FR-052、FR-053、FR-054；NFR-018（`../../01_requirements/srs.md` §2.7、§3） |
| 驗收 | ACPT-044、ACPT-045、ACPT-046（ACPT-046 屬非使用者可觀察面，由 TC-046 承接） |
| 影響模組 | MOD-AGT（owner：Yen）；讀取但不改寫 MOD-SRV-SCENE、MOD-ENG、MOD-RAG |
| 相依 ADR ／取代關係 | [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)（對帳只比合法性的前提）、[`ADR-010`](./ADR-010-static-frontend-and-eight-step-collapse.md)（單一正式前端）、[`ADR-004`](./ADR-004-single-workflow-snapshot-sqlite.md)（狀態為何不進 workflow blob）、[`ADR-012`](./ADR-012-pilot-loopback-deployment.md)（旗標的部署面）；Supersedes：無、Superseded-by：無 |
| 待確認 | OPEN-39（選件規則並存，主承接處為本 ADR 與 [`../../04_design/lld.md`](../../04_design/lld.md)）、OPEN-02／DEC-014（鑑權）、DEC-015（`.runtime/agent_pipeline/` 保留期） |
| 上下文文件 | [`../sad.md`](../sad.md)、[`../../01_requirements/srs.md`](../../01_requirements/srs.md)、[`../../04_design/api_spec.md`](../../04_design/api_spec.md)、[`../../06_ops/deployment_and_operations.md`](../../06_ops/deployment_and_operations.md) |
