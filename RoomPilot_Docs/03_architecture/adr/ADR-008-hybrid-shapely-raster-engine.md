# ADR-008: 兩套幾何引擎並存：Shapely 提議候選、5cm 柵格為碰撞判定唯一權威

> **狀態:** 已接受（AI 衍生，待人工核准）| **日期:** 2026-08-11 | **決策者:** Ancai（`backend/engine/` owner）＋ Bella（`backend/server/` 整合），依 docs/TEAM_AI_OWNERSHIP.md:29、21
> **Owner:** Ancai（`backend/engine/`）＋ Bella（`backend/server/` 整合）
> **語域:** L2（橋接）
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）
> **定位宣告:** 本文件回答「為什麼引擎裡同時存在 Shapely 解析幾何與布林柵格兩套機制、裁決權為何歸柵格」；不包含引擎全貌（見 [../sad.md](../sad.md)）、幾何權威歸屬引擎的決策（見 [ADR-002-geometry-legality-engine-only.md](ADR-002-geometry-legality-engine-only.md)）與擺位演算法細節（見 [../../04_design/lld.md](../../04_design/lld.md)）。
> **生成:** AI 由程式碼與文件衍生｜來源版本 git yen@8863a36c。本 ADR 為既成決策補記，背景由程式碼註解與 `docs/擺位計算邏輯.md` 重建。

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 引擎 v0.1 是純 Shapely 解析幾何：家具/牆轉成旋轉多邊形做交集判斷（geometry.py:1-9、engine/README.md:14），檢查順序固定七段（出界→穿牆→重疊→淨空…，engine/README.md:40-52）。後續依 `docs/擺位計算邏輯.md` §3 新增柵格引擎：房間環掃描線填充、牆/門窗線段描粗成布林佔用網格，格徑 5cm（`DEFAULT_CELL_CM = 5.0`，raster.py:18-20），此後碰撞判定全在布林網格上做（raster.py:1-8）。兩套的資料模型明文並存：`models.py` 是型錄/payload 契約，`layout_model.py` 是柵格引擎的內部工作型別（layout_model.py:3-5）。
- **問題**: 兩套引擎對同一擺位可能給出不同合法性答案。若無單一裁決權威，房間環、門前動線（75cm）與窗前採光帶（40cm）的檢查分散在 Shapely 三段各自為政（scene_service.py:2228-2229 註解所述的前身狀態），跨房/斜擺/成組家具的判定會互相打臉，違反 NFR-004「幾何合法性單一權威」。
- **驅動因素/約束**:
  - Shapely 引擎累積了大量提議能力：first-fit 靠牆掃描、貼附主家具（`place_adjacent_to_furniture`）、地毯 overlay 等，整組重寫成本高（engine/README.md:16-17、scene_service.py:2417-2462）。
  - 柵格把房間環、門窗淨空、視聽走廊等禁放規則一次烘進遮罩，之後每次判定只是布林查表，且天然支援多房 MultiPolygon 聯集（scene_service.py:1391-1394）。
  - AGENTS.md:53-54：幾何合法性只由 `backend/engine/` 判定，不得移往 RAG/LLM/前端。

## 2. 考量的選項

### 選項一: 全面沿用並擴充純 Shapely 解析幾何
- **描述**: 在 v0.1 的多邊形交集引擎上疊加門前動線、採光帶、多房聯集等規則，維持單一解析幾何實作。
- **優點**: 單一套機制；判定精確到浮點，無格徑量化誤差。
- **缺點**: 淨空規則逐條寫成多邊形運算，三段分散檢查已被證實難以維持一致（scene_service.py:2228-2229）；非矩形房與走道連通性本來就是 v0.1 未實作項（engine/README.md:75-82）。
- **成本/複雜度**: 高

### 選項二: 整組改寫為純柵格引擎、淘汰 Shapely（推測）
- **描述**: 依 `docs/擺位計算邏輯.md` 全規格實作柵格擺位，Shapely 提議路徑（place_furniture 等）棄用。
- **優點**: 只有一個事實源；判定與提議同一套資料結構。
- **缺點**: 丟掉已驗證的提議能力（成組貼附、overlay、first-fit 掃描共 25 案測試，engine/README.md:24）；柵格格徑 5cm 的量化對「提議最佳位置」的搜尋策略是重寫不是移植。此選項未見於文件，屬由 layout_model.py:3-5「並存」措辭反推的落選路線，標記**推測**。
- **成本/複雜度**: 高

### 選項三: 並存分工——Shapely 提議、柵格裁決（現況）
- **描述**: Shapely 引擎產生候選擺位，每個候選必須通過布林網格 `_raster_accepts` 才算合法（scene_service.py:2269-2286）；被否決時改走柵格參與的掃描（`_grid_place_in_boundary` 帶 `accepts` 回呼，scene_service.py:2631-2640）。
- **優點**: 保留提議資產；裁決收斂到單一布林網格；禁放規則（門 75cm、窗 40cm、視聽走廊）一次烘進遮罩。
- **缺點**: 兩套型別與座標約定並存，維護者必須理解轉換（`pos_x/pos_y` 中心制 ↔ 角落原點相對座標、旋轉取負，scene_service.py:2273-2275）。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項三——兩套並存，柵格是碰撞判定唯一權威。

**理由**: `build_raster_context` 把房間環、門前動線與窗前採光帶全部烘進布林網格，「取代原本 Shapely 的三段分散檢查」（scene_service.py:2228-2230）；Shapely 引擎回傳的每個候選仍須通過 `_raster_accepts` 的柵格裁決（scene_service.py:2269-2270 docstring：「Shapely 提議、柵格裁決」）。相對選項一，柵格把規則判定統一成查表；相對選項二，保留了 Shapely 提議能力而不必重寫。唯一例外：取不到房間環（手動矩形極端案例）時 `build_raster_context` 回 `None`，呼叫端退回舊 Shapely 路徑（scene_service.py:1378-1382）。

## 4. 後果

- **正面**: 合法性答案唯一（ACPT-007/008 的拒絕與 validate_only 行為都以柵格為準）；多房聯集驗證可行（scene_service.py:1391-1394）；視聽走廊等新紀律只需疊一張遮罩（scene_service.py:2233-2242）。
- **負面**: 5cm 格徑引入量化誤差，貼邊擺位可能與解析幾何結論差一格；`MAX_CELLS_PER_AXIS = 1200` 超限時放大格徑、解析度變粗（raster.py:19）；兩套座標/旋轉約定的轉換是常態 bug 面（旋轉取負 `(-rotation) % 360`）。
- **影響範圍**: `backend/engine/`（raster.py、obb.py、layout_model.py、constraints.py 與舊 geometry.py、placement.py 並存）與 `backend/server/scene_service.py` 的擺位管線；前端與 RAG 不受影響（依 ADR-002 本就不判幾何）。
- **重新評估觸發**: 柵格量化誤差造成可觀察的擺位缺陷（貼牆縫隙、誤殺合法拖曳）；Shapely 提議路徑的維護成本超過重寫；或 `docs/擺位計算邏輯.md` 規格演進到柵格可完全承接提議（屆時走選項二收斂單套）。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-11 | （待人工核准） | AI 衍生補記，待 Ancai/Bella 確認選項二的重建是否符合當時考量 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | NFR-004（幾何合法性單一權威）、REQ-006/FR-006（方案生成）、REQ-007/FR-007（拖曳與重排裁決）、ACPT-007、ACPT-008 |
| 影響範圍 | `backend/engine/`、`backend/server/scene_service.py` 擺位管線；[../sad.md](../sad.md)、[../../04_design/lld.md](../../04_design/lld.md)、[ADR-002-geometry-legality-engine-only.md](ADR-002-geometry-legality-engine-only.md) |
| 取代關係 | 無 |
