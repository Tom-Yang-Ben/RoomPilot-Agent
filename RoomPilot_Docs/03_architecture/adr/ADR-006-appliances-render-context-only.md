# ADR-006: 家電只寫入 render_context，不進 2D/3D 擺設 (Appliances as Render Context Only) - RoomPilot

> **狀態:** 已接受（現況追認，待 owner 核准）｜ **日期:** 2026-08-12 ｜ **決策者:** MOD-SRV-SCENE／MOD-WEB owner（Bella）＋ MOD-AGT owner（Yen）；業務面待產品 owner 於 [`requirements_tracker.xlsx`](../../../VibeCoding_Workflow_Templates/01_requirements/requirements_tracker.xlsx) ①需求決策核准 DEC-006
> **語域:** L2（橋接）——業務詞與工程詞並列，跨層一律用穩定 ID
> **實例:** 每決策一份（`ADR-006-appliances-render-context-only.md`）
>
> **本文件回答**：為什麼冰箱、洗衣機這類家電被排除在 2D 平面、3D 場景與正式家具 API 之外，只以 `scene_json.render_context.appliance_requirements` 進入第 8 步生圖；放棄了哪些替代做法；這個決策什麼時候該重評。
> **本文件不含**：`layout_json` 與 `scene_json` 的邊界（去 [`ADR-001`](./ADR-001-layout-json-scene-json-boundary.md)）、幾何合法性唯一權威（去 [`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)）、生圖服務的失敗政策（去 [`ADR-009`](./ADR-009-server-governed-ai-generation.md)）、需求條文本身（去 [`srs.md`](../../01_requirements/srs.md) FR-028／FR-059）、第 5 步畫面規格（去 [`ui_spec-step5-requirements.md`](../../02_ux_ui/ui_spec-step5-requirements.md)）、第 8 步畫面規格（去 [`ui_spec-step8-ai-render.md`](../../02_ux_ui/ui_spec-step8-ai-render.md)）。
> **佐證基準**：分支 `yen`、HEAD `8f378b24`、2026-08-12 工作樹。行號隨程式碼演進，衝突時以原始碼為準。

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫](#5-執行計畫)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**：第 5 步問卷會收到「要冰箱、要洗衣機」這類需求（DEC-005），第 8 步要生出像真實住家的效果圖（DEC-011）。系統早期把家電當一般家具處理過：曾有 `/api/appliances` 端點、前端曾以 `endpoint: "/api/appliances"` 對映、IKEA 家電 GLB 以 `/models/ikea/appliance/` 進場景；該路徑已於 commit `aeecf841`「清理第六步舊版家電殘留」退役。
- **問題**：家電的可行位置由給排水、排煙、電源迴路決定，而 `backend/engine/` 只有幾何規則——出界、穿牆、本體重疊、淨空五類（`backend/engine/clearance.py:118-143`）與五個公分常數（`backend/engine/constraints.py:21-23`）。引擎能算出「幾何合法」的冰箱位置，卻無法保證可施作；把它畫進平面與 3D，等於對使用者做出系統無力背書的承諾。
- **驅動因素／約束**：
  - AGENTS.md 已把此事列為不可違反的契約：「冰箱、洗衣機等家電保留為問卷與 AI 生圖上下文，不能進入 2D/3D 自動配置或正式家具 API」（[`AGENTS.md`](../../../AGENTS.md):56），同段亦規定家具合法位置只由 `backend/engine/` 判定（`AGENTS.md:53`）。
  - 生圖契約同步要求家電只作為畫面 context（`docs/contracts/AI_RENDER_OPENROUTER_CONTRACT.md:15`）。
  - 問卷已經收了這筆資訊，直接丟棄會讓效果圖缺少廚房與陽台的關鍵物件。

## 2. 考量的選項

### 選項一: 家電視為一般家具，走型錄＋引擎擺位（曾實作，已退役）

- **描述**：家電列入正式家具 API 與型錄候選，取得 GLB 後與沙發、床同樣交由引擎判定座標，進 `scene_objects`、進 2D 疊層、進 3D。
- **優點**：所見即所得；家電佔位參與碰撞與淨空計算；平面圖可直接標示家電位置。
- **缺點**：引擎沒有管線約束，算出的「合法」位置不等於可施作；家電 GLB 與三軸尺寸品質不足以支撐白模比例；使用者會把系統自動擺的冰箱位置誤認為設計建議。
- **成本／複雜度**：高——需把引擎的規則面從幾何擴張到水電管線。已放棄並以測試釘死回不去：`/api/appliances` 現回 404、前端原始碼不得再出現該端點字串（`tests/test_scene_furniture_retrieval.py:145-158`）。

### 選項二: 家電只進 2D 平面圖示，不進 3D、不經引擎

- **描述**：在 2D 疊層畫家電圖示供溝通，3D 與 `scene_objects` 維持不含家電。
- **優點**：實作量小；平面圖仍能標示大致位置。
- **缺點**：同一份 `scene_json` 出現兩種真相（2D 有、3D 沒有），與 ADR-002「幾何唯一權威」直接衝突；圖示位置未經任何驗證，卻長得像經過驗證；還原舊專案時 2D／3D 一致性無法自動檢查。
- **成本／複雜度**：中。

### 選項三: 問卷不收家電需求

- **描述**：把家電整段移出問卷，效果圖也不提家電。
- **優點**：最省，沒有第二條資料通道。
- **缺點**：違背 DEC-006 的業務承諾（家電是「只影響效果圖」，不是「不存在」）；廚房與陽台的效果圖會少掉最顯眼的物件，第 8 步交付物說服力下降。
- **成本／複雜度**：低，但不滿足需求。

### 選項四: 家電只寫入 `scene_json.render_context.appliance_requirements`（採用）

- **描述**：問卷收到的家電需求以獨立欄位帶到伺服器，經 `scene_service` 原樣寫進 `scene_json` 的 `render_context`，只在第 8 步組提示詞時取用；擺位、型錄、引擎三條路徑全部拒收。
- **優點**：引擎責任面不擴張；效果圖仍有家電；資料通道單一且可字串比對稽核。
- **缺點**：`render_context` 成為 `scene_json` 內唯一不受引擎管轄的欄位，需要人工守住不被濫用（見 §4）。
- **成本／複雜度**：低。

## 3. 決策

**選擇**：選項四——家電只寫入 `scene_json.render_context.appliance_requirements`，並以四層防線確保它進不了擺設。

**理由**：只有選項四同時滿足「引擎是幾何唯一權威」與「效果圖要像真實住家」兩個約束。選項一要求引擎背書它算不出來的東西；選項二製造 2D 與 3D 互相打臉的第二真相；選項三丟掉已收到的需求。選項四付出的代價（一條旁路欄位）可以用單一寫入點與測試字串斷言控制住。

| 層 | 落地位置 | 實際行為 | 佐證 |
| :--- | :--- | :--- | :--- |
| 型錄層 | `_appliance_payload_cache()` 首行即 `return ()`；`/api/appliances` 路由不存在 | 正式家具 API 取不到任何家電 | `main.py:930-931`；`tests/test_scene_furniture_retrieval.py:145-151` |
| 前端層 | 11 個 `RETIRED_APPLIANCE_TYPES` 型別 ＋ 3 個 `model_url` 標記；`pruneRetiredAppliances()` 在存檔（`workflowPayload()`）、第 6 步平面重繪、專案還原三處清除，並含方案 A／B 的 `furniture` 與 `sceneData` | 家電不進 `state.furniture2d`、不進 `scene_objects`、不進任一方案 | `scene_v2.js:674-691,693-712,775-806,1173,11410,19450`；`tests/test_scene_v2_contract.py:2488-2500` |
| 伺服器層 | `selected_furniture_items_from_questionnaire()` 以同一組型別集合與同一個 `/models/ikea/appliance/` 標記直接 `continue` | 前端被繞過時伺服器仍不生成家電 `scene_objects` | `scene_service.py:697,715-727,738-740` |
| 生圖層 | 全 repo 唯一寫入點 `scene_service.py:3058`（來源 `questionnaire.appliance_requirements`，`scene_service.py:2916`）與唯一讀取點 `ai_render_service.py:200-220`；最終落成提示詞的「家電：…」片段 | 家電只出現在畫面描述，不含尺寸數字（FR-059） | `scene_service.py:2916,3058-3062`；`ai_render_service.py:14,200-220`；`backend/agent/tools/genpic_info.py:231-235` |

## 4. 後果

### 4.1 得到什麼

- 引擎責任面收斂：`backend/engine/` 永遠看不到家電，七段檢查與五個淨空常數不必模擬管線約束（FR-034、FR-035）。
- 四層防線互為備援，且三層有字串級測試護欄（`tests/test_scene_v2_contract.py:2488-2500`、`tests/test_scene_furniture_retrieval.py:145-158`、`tests/test_ai_render_openrouter.py:68-76`），退化會在 `pytest` 紅燈；舊專案還原時自動清除殘留家電並以中文告知，不靜默改變畫面（`scene_v2.js:803-805,19450`）。
- 第 8 步仍能在提示詞列出家電，滿足 ACPT-051（`backend/agent/tools/genpic_info.py:231-235`）。

### 4.2 付出什麼

- 平面與 3D 不呈現家電位置，家電定位須靠圖面外的溝通；**本 repo 無此溝通機制**（交付物章節中無家電位置頁）。
- `render_context` 是 `scene_json` 內唯一不由引擎產生、也不被引擎驗證的欄位，靠「單一寫入點」的紀律維持，無 schema 或測試阻止未來加入其他旁路子欄位。
- 已知落差（程式碼可證，但「是缺陷或取捨」須 owner 判定，**待確認**，無既有 OPEN-* 承接）：

| # | 落差 | 佐證 | 可觀察後果 |
| :--- | :--- | :--- | :--- |
| A | 欄位名不對接：前端輸出 `name_zh`，adapter 讀 `name_zh_raw` | `scene_v2.js:762-773`；`ai_render_service.py:206` | 提示詞退回英文 slug（如 `refrigerator`）而非「雙門冰箱」 |
| B | `room_id` 在 adapter 被硬寫 `None`，而 genpic 以 `room_id in (None, room.room_id)` 過濾 | `ai_render_service.py:216`；`backend/agent/tools/genpic_info.py:232` | 每一房的提示詞都帶到全部家電（臥室也出現冰箱） |
| C | `quantity` 前端從不輸出，`×N` 分支為死碼 | `scene_v2.js:765-772`；`ai_render_service.py:207-211` | 多台同型家電無法表達 |
| D | `applianceRequirementsForRendering()` 的輸入是 `state.furniture2d`，但 `workflowPayload()` 每次存檔都先把家電從該陣列清掉 | `scene_v2.js:1173,12634` | 跨 session 還原後 `appliance_requirements` 恆為空；家電需求實際上不一定進得了生圖 |
| E | 家電不進 `locked_furniture` 鎖定清單 | `backend/agent/tools/genpic_info.py:243` | 第 8 步改圖時家電不受「其餘不動」約束 |
| F | 使用者提示文案寫「冰箱與洗衣機已改由一般家具與櫃體流程處理」，與本決策語意不同 | `scene_v2.js:804` | 對外說法與 DEC-006 不一致，須擇一 |
| G | `main.py:932-965` 為 `return ()` 之後的不可達程式碼，且呼叫未定義的 `_appliance_manifest_index()` | `main.py:930-936`（全 repo 無該函式定義） | 若有人移除守衛行，模組會在該路徑 `NameError` |

### 4.3 什麼時候該重評

任一條成立即重開本 ADR：

1. `roompilot.furniture_catalog_current` 出現 `role_code = "appliance"` 且同時具備 GLB 與三軸 `size_cm` 的資料列（家電資料品質已足以支撐白模）。
2. `backend/engine/constraints.py` 出現非幾何約束常數（給排水、排煙、插座迴路），代表引擎已能背書家電位置。
3. 產品 owner 在 `requirements_tracker.xlsx` ①需求決策把 DEC-006 改為「家電需標示於平面」。
4. UAT 或 Pilot 回饋出現 ≥1 件「效果圖有家電、平面沒有，客戶認為圖面不實」的缺陷（承接 [`UAT_RoomPilot_Pilot_內部_2026-08-12.md`](../../05_qa/UAT_RoomPilot_Pilot_內部_2026-08-12.md)）。
5. `scene_json.render_context` 新增第二個非家電子欄位——代表它已變成通用旁路通道，須升格為正式契約而非例外。

## 5. 執行計畫

本 ADR 為**現況追認**：四層防線已在 `yen`／`8f378b24` 全數落地並有測試護欄。尚未完成者：

1. 產品 owner 核准 DEC-006（`requirements_tracker.xlsx` ①需求決策），本 ADR 狀態才由「現況追認」轉為「已核准」。
2. MOD-SRV-RENDER 與 MOD-WEB owner 對 §4.2 的 A–G 逐條判定缺陷或取捨，判為缺陷者補 TC-051 對應測試後修正；G 為不可達程式碼，刪除或明確註記即可。
3. 補一條端到端測試覆蓋「問卷勾家電 → 第 6 步 `scene_objects` 無家電 → 第 8 步提示詞有家電」；現有 `tests/test_ai_render_openrouter.py:68-76` 以手寫 fixture 直接餵 `render_context`，不經前端，涵蓋不到落差 A、B、D。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-12 | 待指派（產品 owner） | 待核准 DEC-006 與 §4.2 落差判定 |

## 6. 追溯

| 項目 | ID／文件 |
| :--- | :--- |
| 觸發來源 | DEC-006（[`brd.md`](../../01_requirements/brd.md)）；FR-028、FR-059（[`srs.md`](../../01_requirements/srs.md) §2.4、§2.8）；[`AGENTS.md`](../../../AGENTS.md) §不可違反的契約 |
| 受約束的需求 | FR-028、FR-029、FR-034、FR-035、FR-058、FR-059；NFR-017（公分單位契約，家電欄位不含座標）；ACPT-026、ACPT-051 |
| 影響範圍（MOD） | MOD-WEB（前端四處清除與需求收集）、MOD-SRV-SCENE（唯一寫入點）、MOD-SRV-RENDER（唯一讀取點）、MOD-AGT（提示詞組裝）、MOD-CAT（家電退出正式型錄）、MOD-ENG（不受影響即為本決策目的） |
| 相關 ADR | [`ADR-001`](./ADR-001-layout-json-scene-json-boundary.md)（`scene_json` 邊界）、[`ADR-002`](./ADR-002-engine-sole-geometry-authority.md)（幾何唯一權威）、[`ADR-005`](./ADR-005-postgres-catalog-source-of-truth.md)（型錄來源）、[`ADR-009`](./ADR-009-server-governed-ai-generation.md)（生圖伺服器治理） |
| 系統全貌 | [`sad.md`](../sad.md)（MOD-* 定義與模組邊界）；設計細節 [`lld.md`](../../04_design/lld.md)、端點契約 [`api_spec.md`](../../04_design/api_spec.md) 與 [`openapi-render-delivery-v1.yaml`](../../04_design/openapi-render-delivery-v1.yaml) |
| 取代關係 | Supersedes: 無（首版）；Superseded-by: 無 |
| 驗證承接 | [`test_plan.md`](../../05_qa/test_plan.md) TC-026、TC-051；[`qa_tracker.xlsx`](../../05_qa/qa_tracker.xlsx)；[`engineering_tracker.xlsx`](../engineering_tracker.xlsx) ①規格追溯 |
