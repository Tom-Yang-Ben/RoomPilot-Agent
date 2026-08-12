# 文件登錄簿 (Document Registry) - RoomPilot

> **版本:** v1.0 ｜ **更新:** 2026-08-12 ｜ **狀態:** 草稿（待 owner 核准）
> **Owner:** 文件系統維護者（架構師合成）；各 ID 家族的欄位權威見 §2 的「定義在哪」欄，本檔不覆寫任一家族的內文
> **語域:** L2（橋接）——業務詞與工程詞並列，跨層一律用穩定 ID
> **實例:** 單例（整套 RoomPilot_Docs 共用的唯一 ID 索引）
>
> **本文件回答**：這套文件由哪些檔案組成、每份的定位與 owner 是誰、十一個穩定 ID 家族各有幾個成員、定義在哪一份、被誰消費，以及目前有哪些 ID 缺口。
> **本文件不含**：任何 ID 的內文——業務論述去 [`01_requirements/brd.md`](01_requirements/brd.md)、產品承諾與允收去 [`01_requirements/prd.md`](01_requirements/prd.md)、可測需求與佐證去 [`01_requirements/srs.md`](01_requirements/srs.md)、架構取捨去 [`03_architecture/sad.md`](03_architecture/sad.md) 與 `03_architecture/adr/`、端點欄位去 [`04_design/api_spec.md`](04_design/api_spec.md)、測試對照去 [`05_qa/test_plan.md`](05_qa/test_plan.md)、處置動作去 `06_ops/runbook-*`。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 專案資訊](#1-專案資訊)
- [2. 穩定 ID 骨幹](#2-穩定-id-骨幹)
- [3. ADR 清單](#3-adr-清單)
- [4. Runbook 症狀清單](#4-runbook-症狀清單)
- [5. 術語表](#5-術語表)
- [6. 檔案索引](#6-檔案索引)
- [7. 追溯](#7-追溯)

---

## 1. 專案資訊

| 欄位 | 值 |
| :--- | :--- |
| **專案名稱** | RoomPilot ── 由一張既有平面圖走完八步、產出成套住宅設計成果的網頁工作流 |
| **階段** | Pilot（內部驗收前）；服務邊界屬 DEC-014，**待 owner 核准** |
| **來源版本** | git 分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹 |
| **生成日期** | 2026-08-12（全批 41 份文件同批重建） |
| **生成方式** | 由現行可執行程式碼、`AGENTS.md` 與 `docs/contracts/` 逐條反推，每條事實主張附 `file:line`；程式碼看不出答案者一律掛 OPEN-\* 標「待確認」，不寫成既成事實 |
| **核准狀態** | **全批草稿。** DEC-001..019 全部待產品 owner 核准；ADR-001..012 皆為「現況追認」；TC-001..060 的狀態為 2026-08-12 實跑結果，非核准後的驗收結論 |
| **前批關係** | 先前一套工程文件只存在於版本歷史（採 REQ-\* 舊 ID 體系），與本批 ID **無對映保證**；本批是重建同一套或另立新版，待 owner 拍板（OPEN-48，見 [`prd.md`](01_requirements/prd.md) §6） |

---

## 2. 穩定 ID 骨幹

主鏈：`DEC-* → FR-*／NFR-* → ACPT-* → SCN-*／TC-* → 證據`，橫向掛 `MOD-*`（誰做）、`ADR-*`（為何這樣做）、`RB-*`（壞掉怎麼辦）。八步 × owner × 失效模式的完整交叉矩陣**只維護在** [`srs.md`](01_requirements/srs.md) §9.2，本節不重抄。

### 2.1 ID 家族總表

| 家族 | 範圍與數量 | 內文定義在哪 | 主要消費者 |
| :--- | :--- | :--- | :--- |
| **DEC** | DEC-001..019（19，連續） | 業務論述在 [`brd.md`](01_requirements/brd.md)；翻譯成 FR／NFR 的對照在 [`srs.md`](01_requirements/srs.md) §1.1 | `prd.md` §3、全部 ADR 的「上游」欄、[`ux_research_and_journey.md`](02_ux_ui/ux_research_and_journey.md) |
| **FR** | FR-001..067（67，連續） | [`srs.md`](01_requirements/srs.md) §2，依 MOD-\* 分 9 節，每條附 `file:line` | [`sad.md`](03_architecture/sad.md) §1.3、[`lld.md`](04_design/lld.md)、[`api_spec.md`](04_design/api_spec.md)、[`test_plan.md`](05_qa/test_plan.md) §3 |
| **NFR** | NFR-001..025（25，連續） | [`srs.md`](01_requirements/srs.md) §3，每條有「數值來源」欄，無依據者標待確認 | [`sad.md`](03_architecture/sad.md) 非功能段、[`deployment_and_operations.md`](06_ops/deployment_and_operations.md)、`06_ops/runbook-*` |
| **ACPT** | ACPT-001..060（60，連續） | S1–S8 內文在 [`prd.md`](01_requirements/prd.md) §3；全體對照與狀態在 [`srs.md`](01_requirements/srs.md) §7 | `02_ux_ui/ui_spec-step*.md` §7、[`test_plan.md`](05_qa/test_plan.md)（TC 同號 1:1）、[`UAT 計畫`](05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md) |
| **SCN** | SCN-001..042（42，見 §2.2 缺口） | 逐步引用在 [`prd.md`](01_requirements/prd.md) §3；六個關鍵卡點展開在 [`ux_research_and_journey.md`](02_ux_ui/ux_research_and_journey.md) §5 | `ui_spec-step*.md`、[`UAT 計畫`](05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md)、`06_ops/runbook-*` §1 |
| **UC** | UC-001..003（3） | [`srs.md`](01_requirements/srs.md) §6（只展開「例外路徑會改變業務結果」的三條） | [`lld.md`](04_design/lld.md) §6 狀態機、[`test_plan.md`](05_qa/test_plan.md) 端到端案例 |
| **ADR** | ADR-001..012（12，連續） | `03_architecture/adr/` 每決策一份，清單見 §3 | [`sad.md`](03_architecture/sad.md) §3.2、`04_design/`、`06_ops/runbook-*` 的「不含」段 |
| **MOD** | 14 個（`MOD-SRV-API`／`-STORE`／`-SCENE`／`-RENDER`、`MOD-FP`、`MOD-U3D`、`MOD-WEB`、`MOD-ENG`、`MOD-CAT`、`MOD-SQL`、`MOD-RAG`、`MOD-AGT`、`MOD-OPS`、`MOD-TEST`） | [`sad.md`](03_architecture/sad.md) §1.3（含 owner 與 FR 對應） | [`srs.md`](01_requirements/srs.md) §2 分節、`03_architecture/diagrams/`、全部 ui_spec 與 runbook 的 Owner 欄 |
| **TC** | TC-001..060（60，與 ACPT 同號 1:1） | [`test_plan.md`](05_qa/test_plan.md) §3（層級、佐證測試檔、綠／紅／部分／缺口狀態） | [`qa_tracker.xlsx`](05_qa/qa_tracker.xlsx) ②執行證據（60 列已填）、[`UAT 計畫`](05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md) |
| **RB** | RB-001..009（9，連續） | `06_ops/runbook-*.md` 每症狀一份，清單見 §4 | [`prd.md`](01_requirements/prd.md) §4 邊界場景、[`srs.md`](01_requirements/srs.md) §9.2、[`deployment_and_operations.md`](06_ops/deployment_and_operations.md) |
| **OPEN** | 22 個，編號**兩位數且不連續**：02、03、04、06、09、10、13、14、16、17、18、21、22、25、28、29、32、39、43、46、48、50 | 無單一定義檔——各由主責文件的「待確認」段登記（見 §2.2） | 全批文件；決策沿革留在 [`requirements_tracker.xlsx`](01_requirements/requirements_tracker.xlsx) ②決策沿革（18 列已建，決策者／日期待 owner 拍板後回填） |

**文件內局部 ID（不進主鏈，不得跨文件引用）**：`GAP-01..06`（[`test_plan.md`](05_qa/test_plan.md) 的測試缺口）、`UAT-001..029`（[`UAT 計畫`](05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md) 的人工案例）。

### 2.2 已知 ID 缺口（誠實登記，非 TO-BE）

| 缺口 | 事實 | 影響 | 處置 |
| :--- | :--- | :--- | :--- |
| **SCN-018／019／020／041 無內文** | 這四個編號在全批文件中**只出現在範圍寫法內**（`SCN-017–025`、`SCN-040–042`），沒有任何一處給出情境敘述 | S6 的 UAT 對位不完整；[`UAT 計畫`](05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md) UAT-012 已自標「SCN-017–025 內（待對位）」 | 由 `prd.md` owner 補內文或明文註銷；在補齊前不得宣稱 SCN-001..042 全數可驗 |
| **ACPT 跨步段（SX）內文不在 prd** | ACPT-007、018–023、046、056–059 只在 [`srs.md`](01_requirements/srs.md) §7 與 [`test_plan.md`](05_qa/test_plan.md) §3 以對照列存在，`prd.md` §3 只覆蓋 S1–S8 | 這 12 條沒有 L1 允收敘述，僅有 L3 測試佐證 | srs §7 已註明其屬「非使用者可觀察面」，由 TC-\* 承接；是否補 L1 敘述待 owner 決定 |
| **OPEN-\* 編號不連續且無主檔** | 22 個實際使用的編號散落 02–50，缺號 28 個；無任一文件持有完整 OPEN 清單 | 無法從單點得知「還有幾件待核准」；新增待確認項時有撞號風險 | 本節即為現行唯一清單；新增 OPEN 前先比對本表，**不自創新號**由 owner 統一發號 |
| **三份 `*_tracker.xlsx` 的 owner 欄位未填** | 三簿已於 2026-08-12 實例化（骨架列齊備：①需求決策 19 列 DEC-001..019、②決策沿革 18 列 OPEN-\*、③Gate 9 列；①規格追溯 92 列 FR＋NFR、②模組BOM 14 列、③切片看板 17 列；①測試設計＋②執行證據各 60 列 TC-\*）。**但 owner 決策欄一律留白**：①需求決策的優先序／範圍／里程碑／核准／Owner 五欄、③Gate 的里程碑／決策／決策者／日期四欄 | `workflow_manual.md` §8 的 `/specify` 硬閘要求「核准 = 已核准」且優先序、範圍、里程碑非空——**目前逐項不成立，硬閘無法放行** | 五欄由產品 owner 於 Excel 直接填寫（分頁名與欄序不得更動，稽核腳本靠其對位）；AI 不得代填（`workflow_manual.md` §8「需求決策不可由規則或 AI 自動衍生」）。填妥前所有引用該簿的文件維持「待 owner 核准」表述 |
| **`room_requirements` 版本號不一致** | 程式碼為 `ROOM_REQUIREMENTS_SCHEMA_VERSION = 2`（`scene_room_requirements.js:1,214`），[`srs.md`](01_requirements/srs.md) FR-027 記為 `schema_version 1.0` | 第 5 步問卷產物的版本契約敘述與實作對不上 | 由 MOD-WEB owner（Bella）裁定；修正前以原始碼為準（srs 已聲明此原則） |

---

## 3. ADR 清單

全部 12 份狀態皆為 **已接受（現況追認，待 owner 核准）**，日期 2026-08-12；「現況追認」＝記錄既成實作的取捨理由，不是新提案。

| ID | 標題 | 主決策者（MOD owner） | 檔案 |
| :--- | :--- | :--- | :--- |
| ADR-001 | 辨識產物 `layout_json` 與方案產物 `scene_json` 的邊界 | Bella ＋ Cody／Ancai／Yen | [`ADR-001`](03_architecture/adr/ADR-001-layout-json-scene-json-boundary.md) |
| ADR-002 | 幾何合法性唯一裁決者是 `backend/engine/` | Ancai（MOD-ENG）＋ Bella | [`ADR-002`](03_architecture/adr/ADR-002-engine-sole-geometry-authority.md) |
| ADR-003 | Shapely 與 raster 雙路徑並存的碰撞引擎 | Ancai（MOD-ENG）＋ Bella（MOD-SRV-SCENE） | [`ADR-003`](03_architecture/adr/ADR-003-dual-path-shapely-raster-engine.md) |
| ADR-004 | 單一 `workflow_json` 快照存 SQLite，不做事件流 | Bella（MOD-SRV-STORE） | [`ADR-004`](03_architecture/adr/ADR-004-single-workflow-snapshot-sqlite.md) |
| ADR-005 | PostgreSQL view 為家具型錄唯一權威，JSON 只是降級路徑 | Kai（MOD-CAT／SQL）＋ Bella | [`ADR-005`](03_architecture/adr/ADR-005-postgres-catalog-source-of-truth.md) |
| ADR-006 | 家電只寫入 `render_context`，不進 2D/3D 擺設 | Bella（MOD-SRV-SCENE／WEB）＋ Yen（MOD-AGT） | [`ADR-006`](03_architecture/adr/ADR-006-appliances-render-context-only.md) |
| ADR-007 | 跨模組一律公分制的單位契約 | Bella（跨目錄公開契約）；Ancai／Cody／Yen 共同確認 | [`ADR-007`](03_architecture/adr/ADR-007-centimeter-unit-contract.md) |
| ADR-008 | 檢索只做排序、模型 offline-only | Django（MOD-RAG）＋ Bella（API 轉接） | [`ADR-008`](03_architecture/adr/ADR-008-rag-retrieval-only-offline-models.md) |
| ADR-009 | AI 生成一律由伺服器治理，前端不持金鑰 | Bella（MOD-SRV-RENDER）＋ Yen（MOD-AGT） | [`ADR-009`](03_architecture/adr/ADR-009-server-governed-ai-generation.md) |
| ADR-010 | 靜態單頁前端即正式產品，11 步內部狀態折疊為 8 步 | Bella（MOD-WEB） | [`ADR-010`](03_architecture/adr/ADR-010-static-frontend-and-eight-step-collapse.md) |
| ADR-011 | Agent 並存管線以環境旗標隔離，不動 live 路徑 | Yen（MOD-AGT） | [`ADR-011`](03_architecture/adr/ADR-011-agent-pipeline-flag-isolation.md) |
| ADR-012 | Pilot 階段只綁 `127.0.0.1`，不做認證與 CORS | Bella（MOD-OPS）；DEC-014 屬產品 owner | [`ADR-012`](03_architecture/adr/ADR-012-pilot-loopback-deployment.md) |

---

## 4. Runbook 症狀清單

九份皆記載同一前提：**本 repo 無監控、無 dashboard、無告警規則、無 on-call 輪值**，故障入口只有使用者回報、畫面錯誤文案與 uvicorn 主控台輸出。

| RB | 症狀（使用者或維運者實際看到的） | 主要 owner | 檔案 |
| :--- | :--- | :--- | :--- |
| RB-001 | 第 5 步按「確認全屋需求」後停住不進第 6 步，錯誤區顯示無法連線 Kai 家具型錄、無法建立可靠配置 | Kai ＋ Bella | [`runbook-catalog-db-unavailable`](06_ops/runbook-catalog-db-unavailable.md) |
| RB-002 | 第 8 步狀態列顯示「尚未設定生圖服務」，或逐房生圖／改圖回失敗且無影像 | Bella（MOD-SRV-RENDER）＋ Yen | [`runbook-genpic-provider-failure`](06_ops/runbook-genpic-provider-failure.md) |
| RB-003 | 右上狀態列卡在「正在保存…」後轉「保存失敗」；版本衝突或單筆快照撞 2 MB 上限 | Bella（MOD-SRV-STORE／WEB） | [`runbook-workflow-save-conflict-or-oversize`](06_ops/runbook-workflow-save-conflict-or-oversize.md) |
| RB-004 | `GET /api/rag/status` 回 `ready:false` ＋具名 blocker；檢索回 503，第 5 步排序未套用 | Django（MOD-RAG）＋ Bella | [`runbook-rag-model-cache-missing`](06_ops/runbook-rag-model-cache-missing.md) |
| RB-005 | 按「產出設計提案」立刻失敗，訊息含「尚未安裝交付提案排版引擎」與安裝指令 | Bella（MOD-SRV-RENDER）＋ Yen | [`runbook-delivery-pdf-engine-missing`](06_ops/runbook-delivery-pdf-engine-missing.md) |
| RB-006 | 第 3 步辨識出不來（前端自擋或 422），或第 4 步空間確認存不進去 | Cody ＋ Bella | [`runbook-recognition-failed-or-review-blocked`](06_ops/runbook-recognition-failed-or-review-blocked.md) |
| RB-007 | 第 6 步側欄待處理計數 > 0 清不掉，「確認家具配置」鈕反灰擋住第 7 步 | Ancai ＋ Yen ＋ Bella | [`runbook-placement-blocked`](06_ops/runbook-placement-blocked.md) |
| RB-008 | 3D 出現橘色半透明方塊替身取代真家具，或模型端點回 410 | Kai ＋ Bella | [`runbook-glb-asset-missing`](06_ops/runbook-glb-asset-missing.md) |
| RB-009 | `.runtime/` 只增不減、磁碟餘量持續下降，且無專案刪除途徑與容量端點 | Bella（MOD-SRV-STORE／OPS） | [`runbook-runtime-storage-growth`](06_ops/runbook-runtime-storage-growth.md) |

---

## 5. 術語表

業務詞（L1，訪談與 PRD 用語）↔ 工程詞（L3，程式碼中的實際識別字）。佐證為本批實讀，路徑相對 repo 根。

| 業務詞（L1） | 工程詞（L3） | 語意邊界與佐證 |
| :--- | :--- | :--- |
| 平面圖辨識結果 | `layout_json` | 只描述空間本身（牆／門／窗／樑／柱／房間），辨識責任的終點；不含任何設計決策（`AGENTS.md:52`、ADR-001） |
| 設計方案 | `scene_json` | 由 `layout_json` ＋問卷＋型錄產出，含家具座標、材質與 `render_context`；方案生成與編輯的唯一載體（`AGENTS.md:52`） |
| 進度快照 | `workflow_json` | 八步狀態全存 `projects` 表單一 TEXT 欄（`project_store.py:105`），深合併寫入、序列化上限 2 MB（`project_store.py:11`）；無版本歷史表、無事件流（ADR-004） |
| 使用者校正後的結構 | `floorplan_editor` | 第 4 步房間／牆／門／窗／樑／柱的確認結果，是下游共同幾何基準；由 `confirmedFloorplanEditor()` 產生（`scene_v2.js:2216`） |
| 逐房需求 | `room_requirements` | 第 5 步問卷的房層級產物（用途、家具、面材、天花、複核五段）；版本常數 `ROOM_REQUIREMENTS_SCHEMA_VERSION = 2`（`scene_room_requirements.js:1,214`，與 srs 記載不一致，見 §2.2） |
| 生圖用畫面說明 | `render_context` | 家電需求的**唯一**合法去處：`scene_json.render_context.appliance_requirements`（`scene_service.py:3058-3062`）；不進 `scene_objects`、不進家具 API（ADR-006） |
| 方案 A／B | `placement_variant` | B 只反轉類型錨點的嘗試順序，仍走完全相同的碰撞與淨空驗證（`scene_service.py:2539`、`main.py:3630-3632`）；不是兩套不同規則（ADR-002） |
| 隔離區 | quarantine | 未匹配或未驗證的家具資料，**不得進任何 API 或場景**，也不得替其猜測 `model_url`（`AGENTS.md:57`；`unmatched_cloud_furniture` 1,514 筆，`tests/test_cloud_quarantine.py:25`） |
| 色卡 | `STYLE_PACKS` ／ palette | 凍結的風格×色卡組合表（`scene_style_packs.js:301`）；第 7 步對代表房產出比較圖，每案只能成功一次（依據待追認，OPEN-17） |
| 鎖定視角 | `master_view` | 第 7 步逐房鎖定的相機三元組；`position_cm`／`target_cm` 各三元素且 `fov_deg > 0` 才算完成本步（`scene_workflow.js:150-157`、`scene_v2.js:16046`） |
| 走得過去 | clearance | 門前 75 cm、窗前 40 cm、窗台 90 cm 等公分常數（`backend/engine/constraints.py:21-23`）；由引擎裁決，非前端或 LLM |
| 正式家具型錄 | `roompilot.furniture_catalog_current` | PostgreSQL view，第 6 步優先來源（`postgres_repository.py:20`）；只有 `ROOMPILOT_CATALOG_PROVIDER ∈ {json,local,fallback}` 才走已驗證 JSON（`postgres_repository.py:199-204`、ADR-005） |
| 八步 | `WORKFLOW_STEPS` | 內部實為 11 個 step key（`main.py:164-176`），對外折疊為 8 顆導覽（ADR-010）；文件寫「第 N 步」一律指對外 8 步 |
| 只驗不排 | `validate_only` | 第 6→7 步整屋確認用：信任使用者配置、座標照舊，只回報合法性（FR-032） |
| 並存管線 | agent pipeline | 由 `ROOMPILOT_AGENT_PIPELINE` 旗標保護的 MasterAgent 路徑，未設＝關閉；與第 6 步 live 路徑並存、不取代（ADR-011） |

---

## 6. 檔案索引

實際存在 **54 份**（本檔在內）＝ 47 `.md` ＋ 4 `.yaml` ＋ 3 `.xlsx`。ADR 12 份的定位見 §3、runbook 9 份見 §4，此處不重複列。

另有 4 個**非文件**產物不列入計數：`03_architecture/diagrams/` 下的 `solution_overview.py`／`deployment_topology.py`（宣告式 spec）與其生成物 `solution_overview.drawio`／`deployment_topology.drawio`（**勿手改**，改 spec 重生；驗收 `analyze_layout.py` 目標 score=0）。

| 路徑 | 定位一句話 | Owner |
| :--- | :--- | :--- |
| [`00-registry.md`](00-registry.md) | 本檔：ID 家族索引、ADR／runbook 清單、術語對照與檔案索引 | 文件系統維護者 |
| [`01_requirements/brd.md`](01_requirements/brd.md) | 為誰解決什麼、Pilot 要達成什麼商業結果、DEC-\* 的業務論述 | 產品 owner |
| [`01_requirements/prd.md`](01_requirements/prd.md) | 八步旅程每步要達成什麼、系統承諾什麼、什麼算完成（ACPT／SCN） | 產品 owner |
| [`01_requirements/srs.md`](01_requirements/srs.md) | DEC-\* 翻成 FR-\*／NFR-\*，每條附 `file:line`；§9.2 為全域追溯矩陣 | 系統分析（架構師合成） |
| [`01_requirements/requirements_tracker.xlsx`](01_requirements/requirements_tracker.xlsx) | ①需求決策 DEC-001..019／②決策沿革 OPEN-\*／③Gate；**優先序、範圍、里程碑、核准、Owner 五欄留白待填**（見 §2.2） | 產品 owner |
| [`02_ux_ui/ux_research_and_journey.md`](02_ux_ui/ux_research_and_journey.md) | 八步旅程、六個關鍵卡點與復原路徑、可用性測試現況 | 產品 owner／Bella |
| [`02_ux_ui/information_architecture.md`](02_ux_ui/information_architecture.md) | 頁面組成、URL、11 步→8 步折疊、步驟間的資料載體 | 產品＋設計；Bella 審 DOM 契約 |
| [`02_ux_ui/ui_spec-step1-project.md`](02_ux_ui/ui_spec-step1-project.md) | 第 1 步建立專案的畫面元素、狀態與 DOM 契約 | MOD-WEB（Bella）＋ PM |
| [`02_ux_ui/ui_spec-step2-upload.md`](02_ux_ui/ui_spec-step2-upload.md) | 第 2 步上傳平面圖與格式擋下的畫面規格 | MOD-WEB（Bella） |
| [`02_ux_ui/ui_spec-step3-recognition.md`](02_ux_ui/ui_spec-step3-recognition.md) | 第 3 步辨識、比例標定與信心呈現 | MOD-WEB（Bella）；輸出契約屬 Cody |
| [`02_ux_ui/ui_spec-step4-space-confirmation.md`](02_ux_ui/ui_spec-step4-space-confirmation.md) | 第 4 步結構編輯與逐房複核閘門 | MOD-WEB（Bella）；QA 會簽 |
| [`02_ux_ui/ui_spec-step5-requirements.md`](02_ux_ui/ui_spec-step5-requirements.md) | 第 5 步問卷三 stage、逐房五段與檢索降級呈現 | Bella ＋ 產品 owner ＋ Django |
| [`02_ux_ui/ui_spec-step6-layout-2d.md`](02_ux_ui/ui_spec-step6-layout-2d.md) | 第 6 步 2D／3D 配置、待處理清單與型錄瀏覽 | Bella ＋ Ancai ＋ Kai |
| [`02_ux_ui/ui_spec-step7-proposal-review.md`](02_ux_ui/ui_spec-step7-proposal-review.md) | 第 7 步逐房鎖視角與色卡比較疊層 | Bella ＋ 產品 owner（OPEN-17） |
| [`02_ux_ui/ui_spec-step8-ai-render.md`](02_ux_ui/ui_spec-step8-ai-render.md) | 第 8 步逐房生圖、改圖額度與成果包下載 | Bella ＋ Yen ＋ 產品 owner |
| [`03_architecture/sad.md`](03_architecture/sad.md) | 系統全貌：MOD-\* 十四模組與 owner、Context Map、非功能落點、ADR 索引 | 架構師（合成） |
| `03_architecture/adr/`（12 份） | 每決策一份的取捨記錄，清單與狀態見 §3 | 各 MOD owner |
| [`03_architecture/diagrams/c4_context.md`](03_architecture/diagrams/c4_context.md) | 誰在用、對外依賴哪些外部系統、失效時的對外表現 | 架構師 |
| [`03_architecture/diagrams/c4_container.md`](03_architecture/diagrams/c4_container.md) | 哪些是可獨立執行的 runtime、哪些其實同屬一個 Python 行程 | 架構師；Bella 實作 |
| [`03_architecture/diagrams/solution_overview.md`](03_architecture/diagrams/solution_overview.md) | 八步之間流動什麼資料、每步產出存到哪、靠什麼條件放行 | 架構師 |
| [`03_architecture/diagrams/deployment_topology.md`](03_architecture/diagrams/deployment_topology.md) | 跑在哪台機器／行程／埠，執行資料落在哪，跨邊界協定與失敗語意 | 架構師；MOD-OPS 維護 |
| [`03_architecture/diagrams/ai_guardrails.md`](03_architecture/diagrams/ai_guardrails.md) | AI 能碰什麼、永不碰什麼（幾何裁決留在 `backend/engine/`）、哪些資料離開本機、七項護欄缺口 | 架構師；MOD-AGT（Yen）＋ MOD-RAG（Django）會簽 |
| [`03_architecture/engineering_tracker.xlsx`](03_architecture/engineering_tracker.xlsx) | ①規格追溯 FR-001..067＋NFR-001..025／②模組BOM 14 個 MOD-\*／③切片看板 17 個 OPEN-\*（認領者、認領時間待工程 owner 填） | 架構師 |
| [`04_design/api_spec.md`](04_design/api_spec.md) | 開了哪些路由、分屬哪個 MOD owner、關鍵失敗碼與狀態碼慣例 | MOD-SRV-API（Bella） |
| [`04_design/db_design.md`](04_design/db_design.md) | 三個持久化體的表／view／約束、原子性與樂觀鎖、匯入器條件 | Bella（SQLite）＋ Kai（PostgreSQL） |
| [`04_design/lld.md`](04_design/lld.md) | codebase 依賴圖與七條「看不懂就無法安全改動」的演算法 | 架構師（§6）＋各 MOD owner |
| [`04_design/openapi-project-workflow-v1.yaml`](04_design/openapi-project-workflow-v1.yaml) | `/api/projects` 家族欄位級契約（快照寫入、上傳、renders） | Bella |
| [`04_design/openapi-scene-v1.yaml`](04_design/openapi-scene-v1.yaml) | 第 5–6 步場景與型錄 API 契約 | Bella；型錄面 Kai、幾何面 Ancai |
| [`04_design/openapi-agent-rag-v1.yaml`](04_design/openapi-agent-rag-v1.yaml) | `/api/agent/*` 與 `/api/rag/*` 兩家族契約 | Yen ＋ Django ＋ Bella |
| [`04_design/openapi-render-delivery-v1.yaml`](04_design/openapi-render-delivery-v1.yaml) | 第 7／8 步生圖與交付家族契約 | Bella；Agent 側 Yen |
| [`05_qa/test_plan.md`](05_qa/test_plan.md) | TC-001..060 的層級、佐證測試檔與狀態；2026-08-12 可驗證性基準線 | QA |
| [`05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md`](05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md) | 本輪內部驗收的 UAT-001..029 人工案例與外部相依故障演練 | 產品 owner 主導；QA 支援 |
| [`05_qa/qa_tracker.xlsx`](05_qa/qa_tracker.xlsx) | ①測試設計 TC-001..060（層級、環境、Entry／Exit）／②執行證據（實跑結果、Pass／Fail、執行版本 `yen@8f378b24`）；兩頁皆已填 | QA |
| [`06_ops/deployment_and_operations.md`](06_ops/deployment_and_operations.md) | 怎麼裝、怎麼啟動、需要哪些環境變數、執行資料長在哪、缺哪些維運機制 | MOD-OPS（Bella 整合） |
| `06_ops/runbook-*.md`（9 份） | 每症狀一份的處置程序，症狀與 owner 見 §4 | 各 MOD owner |

---

## 7. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| **上游** | 現行程式碼（分支 `yen`、HEAD `8f378b24`）、[`AGENTS.md`](../AGENTS.md) §不可違反的契約（`AGENTS.md:48-59`）、`docs/contracts/`、[`docs/TEAM_AI_OWNERSHIP.md`](../docs/TEAM_AI_OWNERSHIP.md)；ID 家族的內文權威見 §2.1「定義在哪」欄 |
| **本文件產出** | ID 家族的數量、範圍與消費者對照（§2.1）；五項 ID 缺口登記（§2.2）；ADR-001..012 清單（§3）；RB-001..009 症狀對照（§4）；L1↔L3 術語對照（§5）；54 份檔案索引與 owner（§6） |
| **下游** | 全批文件的交叉引用皆以本檔的檔名與 ID 為準；`requirements_tracker.xlsx` ①需求決策（DEC-\*）、`engineering_tracker.xlsx` ①規格追溯（FR／NFR／MOD）、`qa_tracker.xlsx` ②執行證據（TC-\*）——三簿已實例化，owner 決策欄待填（見 §2.2） |
| **本檔不決定** | 任何 ID 的內文與狀態：DEC-\* 核准屬產品 owner；FR／NFR 佐證屬 [`srs.md`](01_requirements/srs.md)；ACPT／SCN 內文屬 [`prd.md`](01_requirements/prd.md)；TC 狀態屬 [`test_plan.md`](05_qa/test_plan.md)；ADR 決策屬各 MOD owner |
| **待確認** | OPEN-48（本批是重建先前那套文件或另立新版，影響 ID 連續性與舊 REQ-\* 註銷處理）；§2.2 的五項缺口在 owner 裁定前一律視為未收斂，不得在下游文件寫成既成事實 |
