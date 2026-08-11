# ADR-004: 家電只進問卷與 scene_json.render_context 供生圖，不進 2D/3D 擺設與正式家具 API

> **狀態:** 已接受（AI 衍生，待人工核准） | **日期:** 2026-08-11 | **決策者:** Bella（`backend/server/` owner，AGENTS.md:36）＋跨 owner 契約（AGENTS.md:56 為團隊不可違反契約；受影響 owner：Yen `backend/agent/`、Ancai `backend/engine/`、Kai `backend/catalog/`）
> **Owner:** Bella（`backend/server/`）
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **定位宣告:** 本文件回答「為什麼家電（冰箱、洗衣機等）不進 2D/3D 自動配置與正式家具 API，只以問卷需求與 `render_context` 供第 8 步生圖」；不包含 layout/scene 邊界全貌（見 [ADR-001](./ADR-001-layout-json-scene-json-boundary.md)）、幾何合法性歸屬（見 [ADR-002](./ADR-002-geometry-legality-engine-only.md)）與生圖 API 細節（見 [../../04_design/api_spec.md](../../04_design/api_spec.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 第 5 步問卷收集使用者的家電需求（REQ-005），第 6 步由 `backend/engine/` 依 catalog 自動產生並驗證家具擺設（REQ-006/007），第 8 步以 scene_json 逐房 AI 生圖（REQ-011）。家電資產確實存在於素材庫（`JSON/furniture/all_furniture_appliance_catalog.json` 含 `/models/ikea/appliance/` 模型路徑；scene_service.py:738 即依此 URL 樣式設防），使用者在 /library 選件時可能把家電選進 `selected_furniture`。
- **問題**: 家電（冰箱、洗衣機、洗碗機、烘衣機、烤箱、微波爐、抽油煙機、冷氣等）的合法位置取決於水電、排水、插座與管線配置——這些資訊不在 `layout_json` 裡（辨識只到牆/門/窗/樑/柱/房間，ADR-001）。若讓 engine 擺放家電，碰撞/淨空規則會產出「幾何合法但水電不可行」的配置，誤導使用者；但生圖若完全不知道家電需求，第 8 步寫實圖又會缺少廚房/陽台的關鍵畫面元素。
- **驅動因素/約束**:
  - AGENTS.md:56 團隊契約：「冰箱、洗衣機等家電保留為問卷與 AI 生圖上下文，不能進入 2D/3D 自動配置或正式家具 API」。
  - NFR-004：幾何合法性只由 `backend/engine/` 計算；engine 沒有水電/管線輸入，無法為家電裁決合法位置。
  - REQ-013：正式家具 API 限 8,675 件已驗證官方 catalog；家電不在此驗證範圍。
  - 第 8 步生圖需要家電資訊入 prompt context（ai_render_service.py:14-15）。

## 2. 考量的選項

### 選項一: 家電視同一般家具，進 engine 自動配置與 2D/3D 編輯
- **描述**: 把家電併入 catalog 選件與 `scene_objects`，由 engine 以碰撞/淨空規則擺放，使用者可在 2D/3D 拖曳。素材庫已有 appliance 模型（`JSON/furniture/all_furniture_appliance_catalog.json`），此路徑技術上可行。
- **優點**: 使用者所見即所得，白模與生圖一致；不需另設過濾邏輯。
- **缺點**: engine 無水電/排水/插座資訊，擺出的位置無法保證可施工（違反 NFR-004 的「合法性」語意）；家電未經 catalog 驗證流程，混入會稀釋 REQ-013 的資料品質保證。
- **成本/複雜度**: 高（需擴充 layout_json 承載水電資訊，牽動 ADR-001 邊界）

### 選項二: scene_json 另設獨立家電圖層，前端顯示但 engine 不驗證（推測）
- **描述**: 家電放進 scene_json 的獨立欄位（如 `appliance_objects`），3D 只做視覺呈現、不參與碰撞/淨空裁決。此選項未見於程式碼或 docs/contracts/，屬合理替代方案的**推測**重建。
- **優點**: 3D 畫面較完整；不污染 engine 的合法性裁決。
- **缺點**: 「顯示但不驗證」的物件會與家具重疊穿模，使用者無從分辨哪些位置可信；等於在前端偷渡幾何決策，違反「前端 fallback 不得悄悄取代後端演算法」（AGENTS.md:30）。
- **成本/複雜度**: 中

### 選項三: 家電止於問卷與 `render_context`，只供第 8 步生圖（現行）
- **描述**: 問卷的 `appliance_requirements` 原樣寫入 `scene_json.render_context.appliance_requirements`（scene_service.py:2916、3058-3062）；選件混入的家電在組 `scene_objects` 前以 type 集合＋模型 URL 樣式過濾掉（scene_service.py:715-740）；生圖 adapter 從 `render_context` 讀出家電進 prompt context（ai_render_service.py:200-214）。
- **優點**: engine 只裁決它有依據裁決的物件；家電需求不遺失，寫實圖仍能呈現；正式家具 API 維持 8,675 件驗證邊界。
- **缺點**: 2D/3D 白模看不到家電，與最終生圖畫面存在已知落差。
- **成本/複雜度**: 低

## 3. 決策

**選擇**: 選項三——家電保留為問卷與 AI 生圖上下文，唯一合法去處是 `scene_json.render_context.appliance_requirements`。

**理由**: engine 的裁決權威（NFR-004）建立在「輸入足以判定合法性」之上；家電合法性需要水電/管線資訊，而 layout_json 依 ADR-001 明確不承載設計與設備決策。選項一會產出不可施工的假合法配置，選項二把幾何呈現決策外溢到前端。選項三以最小代價守住兩條既有邊界（engine 唯一裁決、catalog 唯一正式家具來源），並用 `render_context` 這條旁路保全生圖需求。實作上三處閘門互相印證：組場景時過濾（scene_service.py:729-740，含註解「Appliances remain questionnaire/render context, never 2D/3D objects.」）、輸出時單獨落欄（scene_service.py:3058-3062）、消費端只從 `render_context` 讀取（ai_render_service.py:202）。

## 4. 後果

- **正面**: `scene_objects` 不含任何家電（ACPT-013 可自動驗證）；engine 不需理解水電領域即可維持裁決權威；第 8 步生圖 prompt 仍帶家電與數量（ai_render_service.py:209-211）。
- **負面**: 第 6 步白模與第 8 步寫實圖之間有已知內容落差（白模無冰箱、生圖有）；使用者若在 /library 選了家電，該選擇被靜默丟棄而非明示回饋（scene_service.py:738-740 直接 `continue`，無 UI 訊息——待確認是否需補提示）。
- **影響範圍**: `backend/server/scene_service.py`（過濾與 render_context 組裝）、`backend/server/ai_render_service.py`（消費）、前端問卷送出 payload（static/scene_v2.js:12710、12765）、`GET /api/furniture` 正式家具 API 的資料邊界（REQ-013）。
- **重新評估觸發**: (a) layout_json 開始承載水電/插座/排水資訊，使 engine 有依據裁決家電位置；(b) catalog 驗證流程納入家電並建立擺設規則；(c) 使用者研究顯示白模缺家電造成理解障礙，需要選項二式的純視覺圖層。

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | REQ-005、REQ-014、FR-014、NFR-004、REQ-013 |
| 影響範圍 | ACPT-005（client_brief 家電三分流）、ACPT-013、SCN-008；[api_spec](../../04_design/api_spec.md)、[lld](../../04_design/lld.md)、[sad](../sad.md)；契約檔 AGENTS.md:56 |
| 取代關係 | 無 |
