# ADR-002: 對外資料契約全面採用公分（cm）

> **狀態:** 已接受 | **日期:** 2026-07-23～24 | **決策者:** 團隊（commit 作者 bellayang312-source；決議會議 repo 內查無記錄——未查證） | **Owner:** Ancai（engine 契約）／Bella（server 與前端落地）
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則對應舊 `docs/vibecoding/03_architecture/adr.md` 之 ADR-002
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 執行計畫（已完成）](#5-執行計畫已完成)
- [6. 追溯](#6-追溯)

## 1. 背景與問題

- **上下文**: DXF 解析器與平面圖視覺管線內部以公尺運算，家具型錄尺寸為公分（`*_cm`），前端 Three.js 另有自己的座標系。
- **問題**: 各模組單位不一，跨模組傳遞時的換算錯誤難以在測試中攔截；家具擺放與碰撞檢查對單位錯誤零容忍。
- **驅動因素/約束**:
  - 家具尺寸以公分表達最貼近型錄與台灣室內設計慣例。
  - 內部演算法（shapely、OpenCV）不必改單位，只需在邊界一次轉換。

## 2. 考量的選項

> 未被採納的選項是由 commit 前後狀態回推，未必是當時實際討論過的方案。

### 選項一: 全面統一公尺
- **描述**: 對外契約沿用 DXF／視覺管線的內部公尺表示。
- **優點**: 解析層免轉換。
- **缺點**: 家具型錄與 UI 顯示皆需小數；與型錄欄位命名（`*_cm`）矛盾。
- **成本/複雜度**: 中

### 選項二: 對外契約統一公分，內部各自保留、邊界單點轉換
- **描述**: 引擎、API、前端契約一律 cm；DXF 與視覺管線內部維持公尺，各設唯一轉換點。
- **優點**: 型錄、擺放、UI 全程公分；轉換點可測試。
- **缺點**: 內部／外部雙表示並存，新讀者需知道邊界在哪。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二。以四段 commit 鏈實施（2026-07-23，git log 於基準 `1268b2b4` 實證可達）：

1. `d97f95c4` refactor(engine): adopt centimeter contract
2. `1baf0277` refactor(server): use centimeters across layout workflow
3. `b7df3071` refactor(app): complete centimeter workflow
4. `714722fd` fix(app): harden centimeter migration boundaries

最終由 `b04833ce`（2026-07-24）整合收尾。決策已升格為 `AGENTS.md`「不可違反的契約」前兩條：跨模組幾何使用公分、新欄位 `_cm`／面積 `_m2`、舊欄位必須帶 `coordinate_unit: "cm"` 與 schema version（AGENTS.md，2026-08-07 實讀）。

**座標契約**（`backend/engine/models.py` 檔頭 docstring，2026-08-07 實讀）：長度一律公分；X 向右、Y 向上，原點在平面圖左下角；position 為物件中心；rotation 為逆時針度數，0 度時家具正面朝 +Y。序列化輸出 `schema_version: "2.0"`、`coordinate_unit: "cm"`（`backend/engine/schema.py:21-22`，實測）。

**單位邊界（唯一轉換點，2026-08-07 皆實測仍在）**:

- DXF 路徑：`backend/engine/dxf_room.py:38` 的 `_M_TO_CM = 100.0` 把公尺輸出 ×100 進引擎。
- 影像路徑：`backend/floorplan/vision/units.py:30` 的 `canonicalize_analysis_cm()` 是辨識結果公尺→公分的唯一轉換點。

## 4. 後果

- **正面**: 引擎、伺服器 API、前端契約單位一致；單位轉換集中兩個檔案，可被測試覆蓋；契約寫入 `AGENTS.md` 成為硬規範。
- **負面**:
  - 內部公尺表示仍存在，繞過邊界模組直接取用內部值會拿到公尺。
  - `backend/floorplan/vision/analysis.py:30-31` 的 `COORDINATE_SYSTEM` 常數仍宣告 `"unit": "metre"`（2026-08-07 實測），為中間態宣告，最終回傳前才經 `canonicalize_analysis_cm` 轉公分——直接引用該常數的文件會與對外契約矛盾。
  - DXF 自動比例本質是推測，公分數值精度受此上限（沿用 2026-07-26 版記載，本輪未複核 scale_basis 細節）。
- **影響範圍**: `backend/engine/`、`backend/server/`、`backend/floorplan/`、`frontend/` 全部；`layout_json` 與 `scene_json` 兩份輸出契約（邊界見 `docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`）。
- **重新評估觸發**: 與以 mm 為單位的外部系統整合時，在邊界另立轉換點，不回頭改本契約。

## 5. 執行計畫（已完成）

1. 引擎契約先行（`d97f95c4`）→ 伺服器（`1baf0277`）→ 應用層（`b7df3071`）→ 邊界加固（`714722fd`）。
2. `b04833ce` 整合收尾並統一 backend 目錄（見 [ADR-001](ADR-001-unified-backend-package.md)）。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥（回溯撰寫） | commit 鏈與邊界程式碼實測 |
| 2026-08-07 | VibeCoding Pilot 導入 | 邊界轉換點、schema 常數、metre 中間態於現行碼複核仍成立 |

## 6. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | FR-ENGINE-01／FR-LAYOUT-01、NFR-一致性-01（公分制；srs §1–§2 已定編）；`AGENTS.md` 不可違反契約第 1–2 條 |
| 影響範圍 | `backend/engine/`、`backend/server/`、`backend/floorplan/`、`frontend/`；db_design、api_spec 的單位欄位；`docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md` |
| 取代關係 | 無；舊編號對照：`docs/vibecoding/03_architecture/adr.md` ADR-002 |
