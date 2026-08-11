# ADR-005: MasterAgent 管線以 ROOMPILOT_AGENT_PIPELINE flag 與 step6 並存，可隨時回退，不取代正式路徑

> **狀態:** 已接受（AI 衍生，待人工核准） | **日期:** 2026-08-11 | **Owner／決策者:** Yen（`backend/agent/` owner）＋ Bella（`backend/server/` owner），依 docs/TEAM_AI_OWNERSHIP.md:21、28
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **定位宣告:** 本文件回答「MasterAgent 端到端管線為什麼以 feature flag 與正式 step 6 並存，而不是取代它或只留測試」；不包含管線的端點細節（見 [../../04_design/api_spec.md](../../04_design/api_spec.md)）與系統全貌（見 [../sad.md](../sad.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c。本 ADR 為既成決策補記，背景由程式碼與契約重建。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 正式第 6 步的家具配置路徑是「LLM 選件 + engine 擺放 + `resolve_placements` 修復」（docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md:24-36），穩定運作且受契約測試保護。同時 `backend/agent/` 已有 Master + 四個 sub-agent（Furniture／Validation／Gen_Pic／Report）的 HITL state machine，但缺少能端到端真正呼叫它的線上入口（agent_pipeline_service.py:1-11）。
- **問題**: 如何讓 agent 管線在真實服務中被呼叫、驗證與正式路徑的一致性，同時不冒任何破壞正式 step 6 的風險？兩條路徑使用不同 document model（agent 端 SceneDoc/documents vs. scene_service 端 site_payload/engine objects），尚無輸入轉接與輸出對帳，不能宣稱等價（agent_pipeline_service.py:22-26）。
- **驅動因素/約束**:
  - 正式產品邊界固定：家具幾何合法性只由 `backend/engine/` 計算，不得移入 LLM（NFR-004；契約:19-20）。
  - workflow JSON 快照上限 2MB（NFR-002）；master 狀態含生圖 base64，放進去會撐爆上限並被 `project_store` 的顯示字串壓縮邏輯改壞（agent_pipeline_service.py:8-10）。
  - Pilot 階段需要可隨時回退、不影響既有使用者流程的驗證通道。

## 2. 考量的選項

### 選項一: 以 agent 管線直接取代 step 6 的 `scene_service` 路徑
- **描述**: 把第 6 步方案生成改由 MasterAgent 驅動，正式路徑下線。
- **優點**: 單一路徑，無雙軌維護成本。
- **缺點**: 兩條路徑 document model 不同、無對帳證據就切換，等於未驗證即上線；破壞受測試保護的正式流程；違反「不取代正式路徑」的產品邊界（CLAUDE.md 產品邊界節）。docstring 明示「不改動 `scene_service` 的正式 step 6」（agent_pipeline_service.py:3），此選項即其否定式對照。
- **成本/複雜度**: 高

### 選項二: 不建線上入口，MasterAgent 只以單元測試驗證（推測）
- **描述**: 管線僅存在於 `backend/agent/` 測試，不接 FastAPI 路由。
- **優點**: 零線上風險、零 server 端改動。
- **缺點**: 無法端到端驗證 gateway、狀態序列化與 HITL 決策點在真實服務下的行為；一致性對帳（reconcile）沒有掛載點。此選項為推測重建，程式碼中無被否決的直接證據。
- **成本/複雜度**: 低

### 選項三: 以環境變數 flag 掛出並存管線（採用）
- **描述**: `ROOMPILOT_AGENT_PIPELINE` 未設定或為 `""/0/false/no/off` 時管線關閉（agent_pipeline_service.py:32、42-43）；關閉時 start/submit/undo/get/reconcile 一律回 404 並附啟用指引（main.py:3510-3515），只有 `GET /api/agent/pipeline/status` 永遠可查（main.py:3504-3507）。狀態序列化到 `runtime_dir/agent_pipeline/<project_id>.json`，刻意不進 workflow blob（agent_pipeline_service.py:8-10）。
- **優點**: 正式路徑零改動、回退＝清掉環境變數重啟；兩條路徑可用 `POST /api/agent/pipeline/reconcile` 對同一批 step6 家具比對擺放覆蓋率與合法性（main.py:3569-3588）。
- **缺點**: 雙軌並存的維護成本；單一全域鎖序列化所有專案的管線操作，不適合並發吞吐（agent_pipeline_service.py:28-30）。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項三——feature flag 並存管線。

**理由**: 在「無對帳證據不得切換」與「管線必須被端到端真正呼叫才驗得動」之間，flag 並存是唯一同時滿足兩者的做法：對正式 step 6 零侵入（選項一的風險歸零）、又保留真實服務下的驗證與對帳掛載點（選項二做不到）。狀態放 runtime 檔而非 workflow blob，是為了不觸碰 2MB 上限與 `project_store` 壓縮邏輯，讓並存路徑連保存層都不影響正式資料（agent_pipeline_service.py:8-10）。

## 4. 後果

- **正面**: 正式流程風險為零，回退即時（unset flag + 重啟）；`backend.agent` 的 Master + 四 sub-agent 可被端到端呼叫驗證（agent_pipeline_service.py:4-6）；reconcile 端點提供兩路徑一致性的量化比對通道（SCN-010）。
- **負面**: 資料轉接與輸出對帳「未做」——尚不能宣稱與 step6 等價（agent_pipeline_service.py:22-26，標記 TO-BE）；全域鎖限制並發（agent_pipeline_service.py:28-30）；管線狀態不在 workflow 快照內，不受 revision 樂觀鎖保護，跨瀏覽器恢復語意與正式專案資料不同。
- **影響範圍**: `backend/server/agent_pipeline_service.py` 與 main.py:3504-3588 的六條路由；`backend/agent/`（被呼叫方）；部署設定（環境變數，見 [../../06_ops/deployment_and_operations.md](../../06_ops/deployment_and_operations.md)）；正式 step 6（`scene_service`）明確不受影響。
- **重新評估觸發**:
  - 完成 step6 輸入轉接＋逐件輸出對帳，且覆蓋率／合法性達到可接受門檻時——重新評估是否升級管線地位。
  - 對帳長期證明兩路徑不可能收斂時——評估退役管線入口。
  - 管線需要多使用者並發時——全域鎖須改 per-project 鎖（agent_pipeline_service.py:28-29）。

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | FR-015（MasterAgent 並存管線 start/submit/undo/status/reconcile）；約束來源 NFR-002（2MB 快照）、NFR-004（幾何唯一權威） |
| 驗收/情境 | ACPT-015（未設 flag 時 start 回錯誤、status 永遠可查）、SCN-010（並行對帳覆蓋率） |
| 影響範圍 | [../../04_design/api_spec.md](../../04_design/api_spec.md) §5 agent pipeline 端點群、[../sad.md](../sad.md)、相鄰決策 [./ADR-002-geometry-legality-engine-only.md](./ADR-002-geometry-legality-engine-only.md)、[./ADR-007-workflow-json-single-snapshot-store.md](./ADR-007-workflow-json-single-snapshot-store.md) |
| 取代關係 | 無 |

ID 真相源：[../../00-registry.md](../../00-registry.md)。
