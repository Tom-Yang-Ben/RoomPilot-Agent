# ADR-002: 家具幾何合法性只在 backend/engine 計算

> **狀態:** 已接受（AI 衍生，待人工核准） | **日期:** 2026-08-11 | **決策者:** Ancai（`backend/engine/` owner，AGENTS.md:41、docs/TEAM_AI_OWNERSHIP.md:29）；Bella（`backend/server/` 消費端）共同確認——決策者名單為 AI 由 ownership 文件推得，人工核准前為 TO-BE
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-002-geometry-legality-engine-only.md`）
> **定位宣告:** 本文件回答「為什麼家具座標、碰撞、淨空、超界的裁決權只放在 `backend/engine/`，不放 Graph RAG、瀏覽器或 LLM」；不包含 layout_json/scene_json 資料邊界（見 [ADR-001](./ADR-001-layout-json-scene-json-boundary.md)）、Shapely/柵格雙引擎分工（見 [ADR-008](./ADR-008-hybrid-shapely-raster-engine.md)）與系統全貌（見 [../sad.md](../sad.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c。本 ADR 為既成決策的補記：決策已在程式碼與 AGENTS.md 契約中成立，此處重建其脈絡。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: RoomPilot 八步工作流中，第 6 步的方案生成（REQ-006）與 2D/3D 拖曳編輯（REQ-007）都要回答「這件家具放這裡合不合法」。系統裡至少有四個元件在技術上都「碰得到」幾何：`backend/engine/`（Shapely＋柵格）、Graph RAG／`backend/spatial_data/`（關係檢索）、瀏覽器端 Three.js 編輯器（`backend/server/static/`）、LLM agent（`backend/agent/`）。
- **問題**: 合法性規則是可量化的硬規則——門前通行淨空 75cm、窗前採光帶 40cm（僅高 ≥90cm 家具受限）、有櫃家具正面 50cm 開合空間（constraints.py:21-23、clearance.py:24）。若多個元件各自判定，同一件家具會在生成、拖曳、確認三個時點得到不一致的答案，且 LLM／RAG 的判定不可重現、無法寫成回歸測試。
- **驅動因素/約束**:
  - 團隊契約明文：「Graph RAG 只檢索……不決定幾何、碰撞、淨空或結構合法性」「家具合法位置只由 `backend/engine/` 判定」（AGENTS.md:53-54）。
  - 專案邊界禁令：「將幾何決策移到 Graph RAG、瀏覽器或 LLM」列在 CLAUDE.md 禁止清單。
  - 責任分工：`backend/agent/`（Yen）「不輸出合法座標」；`backend/spatial_data/`（Django/Kai）「不負責渲染或幾何合法性」（docs/TEAM_AI_OWNERSHIP.md:24、28）。
  - 淨空與碰撞需要決定論與公分精度（NFR-001），才能支撐 ACPT-007/ACPT-008 的可驗收行為。

## 2. 考量的選項

### 選項一: `backend/engine/` 為幾何合法性單一權威（現況）
- **描述**: 所有合法性運算集中在 `backend/engine/`：淨空多邊形與衝突（clearance.py:55-115）、兩層禁放遮罩 low/band（constraints.py:54-72）、OBB 柵格判定。`scene_service.py` 只作編排，直接 import `..engine.clearance`/`..engine.obb`/`..engine.placement` 等（scene_service.py:27-41）；前端拖曳落點回傳伺服器由 `POST /api/scene/validate` 裁決（main.py:3998-4009），重排走 `POST /api/scene/layout`（main.py:3647）。
- **優點**: 決定論、可單元測試；規則常數（75/40/90/50cm）單點維護；生成／拖曳／確認三個時點答案一致。
- **缺點**: 拖曳驗證多一次 API round-trip；前端只能顯示結果，無法離線即時預判。
- **成本/複雜度**: 低（沿用既有 Python 幾何棧）。

### 選項二: Graph RAG／spatial_data 兼管幾何規則
- **描述**: 既然 RAG 已索引家具、房間、限制的關係，讓它一併回答「可不可以放」。
- **優點**: 語意限制（風格、搭配）與幾何限制單一查詢入口。
- **缺點**: 檢索結果非決定論、依賴模型快取可用性（RAG 離線即整條失效，見 runbook-rag-model-cache-missing）；公分級碰撞不是關係檢索問題。契約已明文否決（AGENTS.md:53；docs/TEAM_AI_OWNERSHIP.md:53「Ancai 仍是幾何與規則的唯一裁決者」）。
- **成本/複雜度**: 高。

### 選項三: 瀏覽器端（Three.js）就地判定
- **描述**: 拖曳時由前端以 bounding box 即時判碰撞，不回伺服器。`frontend3d/` 原型的存在使此路線技術上可行。
- **優點**: 零延遲回饋、離線可用。
- **缺點**: 規則要在 JS 重寫一份，與 Python 引擎必然漂移；柵格遮罩（¬room_mask、門窗描粗）在前端重算成本高；驗收測試無法只跑 Python 覆蓋。現況前端僅呈現 `/api/scene/validate` 的裁決與分流訊息（ACPT-007）。
- **成本/複雜度**: 高（雙份實作＋同步成本）。

### 選項四: LLM agent 直接產出座標（推測——由 `backend/agent/` 舊 LLM 路徑推得，未見完整實作曾上線）
- **描述**: 讓 agent 依需求直接生成家具座標，引擎只做事後微調。
- **優點**: 生成與「擺得好看」的語意判斷合一。
- **缺點**: 不可重現、無法保證 75cm 淨空等硬規則；記憶（room-pilot2 整合紀錄）顯示舊 Agent LLM 擺位路徑本來就是死碼。分工上 agent 只給 hints/priority，最終座標仍由引擎裁決（scene_service.py:2288-2299）。
- **成本/複雜度**: 高。

## 3. 決策

**選擇**: 選項一——`backend/engine/` 是家具座標、碰撞、淨空、超界合法性的唯一權威（NFR-004）。

**理由**: 幾何合法性是公分級、可量化、必須決定論的硬規則，天然屬於純函式幾何庫，不屬於機率性元件（RAG/LLM）或不可測試的前端複本。Graph RAG 保留關係檢索與證據、agent 保留選件與 hints、前端保留呈現與互動——三者都「建議」，只有引擎「裁決」（Shapely 提議、柵格裁決，scene_service.py:2269-2286）。此分工同時滿足責任邊界（Ancai 單一 owner）與驗收可測性（ACPT-007/008 可用 pytest 覆蓋）。

## 4. 後果

- **正面**: 同一輸入必得同一裁決，SCN-004（拖進門前淨空被拒）與 SCN-005（validate_only 不重排）可寫成穩定回歸測試；淨空常數改動只動 `backend/engine/`＋對應測試。
- **負面**: 拖曳合法性依賴伺服器可用（無離線編輯）；agent 想要的擺位若不合法只能被引擎否決，需靠 hints 協商而非直接下座標。
- **影響範圍**: `backend/server/`（`/api/scene/layout`、`/api/scene/validate` 必須轉呼叫引擎，FR-007）、`backend/agent/`（僅輸出 hints）、`backend/spatial_data/`（禁碰幾何）、`backend/server/static/`（只呈現裁決結果）。契約端點見 [../../04_design/api_spec.md](../../04_design/api_spec.md) §5。
- **重新評估觸發**: (1) 前端需要離線／低延遲即時判定且 round-trip 成為實測瓶頸；(2) 引擎規則需搬進資料庫或外部服務共用；(3) agent pipeline（ADR-005）轉正並要求擺位語意與合法性合一時。

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | NFR-004（AGENTS.md:53-54、scene_service.py:2228-2230）；REQ-006、REQ-007 |
| 影響範圍 | FR-006、FR-007、NFR-001；ACPT-006、ACPT-007、ACPT-008；SCN-003、SCN-004、SCN-005；[api_spec](../../04_design/api_spec.md)、[lld](../../04_design/lld.md) |
| 相關 ADR | [ADR-001](./ADR-001-layout-json-scene-json-boundary.md)（資料邊界）、[ADR-008](./ADR-008-hybrid-shapely-raster-engine.md)（引擎內部分工） |
| 取代關係 | 無 |
