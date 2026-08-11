# ADR-001: 平面圖辨識止於 layout_json，設計方案用 scene_json，兩者是唯一模組邊界產物

> **狀態:** 已接受（AI 衍生，待人工核准） | **日期:** 2026-08-11 | **決策者:** Bella（`docs/contracts/` owner，AGENTS.md:46）＋ Cody（`layout_json` 生產端）、Yen／Ancai（`scene_json` 消費／生產端）——依 docs/TEAM_AI_OWNERSHIP.md:21-34，AI 補記，人工核准前為 TO-BE
> **Owner:** Bella（`docs/contracts/` 整合 owner，AGENTS.md:46）
> **語域:** L2（橋接）
> **定位:** 本 ADR 只回答「為什麼辨識與方案之間用 layout_json／scene_json 兩個產物切界」；系統全貌見 [../sad.md](../sad.md)，端點契約見 [../../04_design/api_spec.md](../../04_design/api_spec.md)，幾何權威歸屬見 [ADR-002](./ADR-002-geometry-legality-engine-only.md)。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **生成:** AI 由程式碼與文件衍生（既成決策補記）｜來源版本 git yen@8863a36c

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 八步工作流橫跨多位 owner——Cody 的平面圖辨識（`backend/floorplan/`）、Yen 的需求結構化（`backend/agent/`）、Ancai 的幾何引擎（`backend/engine/`）、Bella 的 FastAPI 與正式 UI（`backend/server/`）。辨識結果與設計方案若共用同一份不斷長大的 payload，任何一端加欄位都會把其他 owner 的模組拖下水。
- **問題**: 需要一條讓「空間事實」與「設計決策」不互相汙染的資料邊界：辨識端不得夾帶家具／材質決策，方案端不得反過來改寫建築結構。歷史上 `/api/floorplan/analyze` 只回 `analysis`（相容欄位至今保留，LAYOUT_SCENE_BOUNDARY_CONTRACT.md:36-44），邊界只存在於慣例。
- **驅動因素/約束**:
  - 跨 owner 契約必須由 `docs/contracts/` 統一版本化，受影響 owner 共同確認（AGENTS.md:46）。
  - Graph RAG 只能提供關係證據，不得成為幾何最終權威（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:73-92；NFR-004）。
  - 前端既有讀取路徑不能一次斷裂，需保留 legacy 欄位並存期。

## 2. 考量的選項

### 選項一: 單一 analysis payload 一路長大（歷史基線）
- **描述**: 沿用 `/api/floorplan/analyze` 的 `analysis` 頂層物件，設計階段直接在同一物件上疊家具、材質、render 欄位。相容欄位證據：analyze 至今同時回 `analysis` 與 `layout_json`（main.py:4140-4146），`/api/scene/generate` 回 legacy 頂層 payload 並附 `scene_json` deepcopy（main.py:3641-3644），前端讀 `response.scene_json || response`（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:70-71）。
- **優點**: 無遷移成本；前端一個物件讀到底。
- **缺點**: 辨識與設計欄位混雜，無法界定「改結構須回第 4 步重新驗證家具」的重算範圍（REQ-004）；owner 責任無法對齊資料 owner；schema 演進互相踩踏。
- **成本/複雜度**: 低（短期）／高（長期維護）

### 選項二: layout_json 與 scene_json 兩個顯名邊界產物（採用）
- **描述**: 辨識路徑輸出止於 `layout_json`（牆／門／窗／樑柱／房間／尺度／信心度，白名單與黑名單見 LAYOUT_SCENE_BOUNDARY_CONTRACT.md:22-35）；方案生成以 `layout_json` 為正典輸入（`/api/scene/generate` 收 `layout_json`，main.py:3622；契約列為 required input，LAYOUT_SCENE_BOUNDARY_CONTRACT.md:58-64；並存管線 start 缺 `layout_json` 即 422，main.py:3522-3527），加上需求、catalog 與規則後產出 `scene_json`（家具、材質、render_context；LAYOUT_SCENE_BOUNDARY_CONTRACT.md:51-65）。
- **優點**: 邊界即 owner 邊界（Cody 產 layout、Yen/Ancai/Bella 產 scene，TEAM_AI_OWNERSHIP.md:21-29）；黑名單條款可測（ACPT-002）；部署期可直接沿產物切 worker（floorplan-vision-worker → proposal-agent-worker，LAYOUT_SCENE_BOUNDARY_CONTRACT.md:94-100）。
- **缺點**: 相容期需雙欄位並存（`analysis`＋`layout_json`、legacy 頂層＋`scene_json`），回應體積加倍（deepcopy）。
- **成本/複雜度**: 中

### 選項三: 依 worker 階段切更多中間產物（推測）
- **描述**: **推測**——契約的 Deployment Boundary 已規劃三個 worker（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:94-100），可再細分出「Graph RAG 候選產物」「render 設定產物」等多份中間契約。
- **優點**: 每階段獨立演進。
- **缺點**: Pilot 階段契約數量爆炸；Graph RAG 產物一旦顯名化，容易被誤當幾何權威，違反 NFR-004。
- **成本/複雜度**: 高

## 3. 決策

**選擇**: 選項二——`layout_json`／`scene_json` 為模組邊界的唯二顯名產物。

**理由**: 邊界寫進不可違反契約「平面圖辨識輸出是 `layout_json`；方案生成與編輯輸出是 `scene_json`」（AGENTS.md:52），並以 `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md` 明文列允許／禁止內容。相對選項一，它讓「空間事實 vs 設計決策」可驗收（layout_json 不含家具/材質欄位，ACPT-002）；相對選項三，兩個產物已足以支撐 worker 切分規劃，Graph RAG 維持「候選證據、非最終決定」的支援層定位（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:14、90-92），不需第三份權威產物。

## 4. 後果

- **正面**: 辨識、需求、引擎、UI 四方可獨立演進，只要各自守住產物 schema；第 4 步「確認即鎖定 layout_json」有明確重算語意（REQ-004／ACPT-004）；新架構圖與 worker 契約有統一名詞（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:43-44）。
- **負面**: 相容欄位長期並存——analyze 回 `analysis`＋`layout_json`（main.py:4140-4146）、confirm 回 `floorplan`＋`layout_json`（LAYOUT_SCENE_BOUNDARY_CONTRACT.md:40）、generate 回 legacy 頂層＋`scene_json` deepcopy（main.py:3641-3644）；何時移除 legacy 欄位無明文排程（待確認）。
- **影響範圍**: `/api/floorplan/analyze|confirm`（main.py:4106-4159）、`/api/scene/generate`（main.py:3591-3644）、前端讀取分支、`docs/contracts/` 全部下游契約；ADR-002（幾何權威）與 ADR-004（家電只進 `scene_json.render_context`）皆以本邊界為前提。
- **重新評估觸發**: (1) worker 化實際落地（floorplan-vision／proposal-agent 拆進程）時檢視產物是否需再切；(2) legacy 欄位（`analysis`、頂層 scene payload）確定可下線時；(3) 若出現必須跨界的欄位（例如辨識端要輸出風格建議），先修契約再動 code。

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | REQ-002、REQ-004、REQ-006；FR-002、FR-004、FR-006；NFR-004 |
| 影響範圍 | [api_spec.md](../../04_design/api_spec.md) §5 floorplan/scene 端點、[sad.md](../sad.md) 資料流視圖、[lld.md](../../04_design/lld.md)、ACPT-002／ACPT-004 |
| 取代關係 | 無 |
