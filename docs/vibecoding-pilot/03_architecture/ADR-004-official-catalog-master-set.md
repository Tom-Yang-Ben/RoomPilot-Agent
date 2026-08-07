# ADR-004: 官方型錄為唯一母集合，載入期硬驗證件數（現行 8,557 件）

> **狀態:** 已接受 | **日期:** 2026-07-26 初版（9,350 件）／2026-07-30 現行（8,557 件） | **決策者:** Bella（commits `83b3c8a5`、`f5fc0995` 作者 bellayang312-source）＋Kai（型錄歸屬）；決策討論過程（未查證） | **Owner:** Kai
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則對應舊 `docs/vibecoding/03_architecture/adr.md` 之 ADR-004，並補記 2026-07-30 母集合切換
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: repo 曾同時存在舊六風格中文型錄（10,550 件）與已上雲的 GLB 集合，兩者數量與 ID 集合不一致。
- **問題**: 若以舊型錄為準，會有上千件家具沒有可用的 3D 模型；網站、Agent 選件與 3D 擺放需要單一且模型保證存在的家具集合。
- **驅動因素/約束**:
  - 每件對外家具必須有經驗證的 CloudFront GLB（[ADR-003](ADR-003-cloudfront-glb-delivery.md)）。
  - 舊型錄的風格標籤、分類與擺放提示仍有價值，不應直接丟棄。

## 2. 考量的選項

> 未被採納的選項是由 commit 前後狀態回推，未必是當時實際討論過的方案。

### 選項一: 沿用舊 10,550 件型錄，缺模型者標記不可 3D
- **描述**: 型錄照舊，前端依 `has_model` 過濾。
- **優點**: 不需資料工程。
- **缺點**: 母集合含千餘件無模型項目；「有沒有模型」變成執行期判斷，測試難以立契約。
- **成本/複雜度**: 低

### 選項二: 官方雲端集合為母集合，舊型錄降級為 enrichment，無法映射者隔離
- **描述**: 以官方 catalog JSON＋manifest 一對一決定母集合；舊型錄只能補風格／分類資訊，不能新增家具；映射不到的舊列進隔離區。
- **優點**: 母集合每件保證有已驗證的 GLB；數量成為可斷言的契約。
- **缺點**: 千餘筆舊資料退出對外集合；部分家具暫無風格標籤。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二，分兩個階段落地：

1. **初版（commit `83b3c8a5`，2026-07-26）**: 以雲端 9,350 件為母集合，`build_official_catalog()` 載入期硬驗證件數、ID 唯一性與每件 HTTPS GLB URL，不符即 raise；映射不到的 1,514 筆舊列進隔離區，`tests/test_cloud_quarantine.py` 斷言隔離 ID 不得出現在對外集合。
2. **現行（commit `f5fc0995`，2026-07-30「切換 Kai 官方家具資料與交付契約」）**: 母集合切換為 Kai 官方 JSON `JSON/furniture/furniture_official_catagory.json`。2026-08-07 實測：`OFFICIAL_CATALOG_COUNT = 8_557`（`backend/catalog/cloud_catalog.py:15`）、該 JSON items 恰 8,557 筆（csv/json 程式實數）、README.md:230「Kai 官方 JSON catalog：8,557 筆」一致；`cloud_catalog.py` 檔頭 docstring 明言「official 8,557-item catalog from Kai's versioned JSON source」。同 commit 燈具 793 筆自 items 移除（後續處置見 [ADR-007](ADR-007-lighting-separate-table.md)）。

**理由**: 「每件對外家具必有模型」從執行期判斷升級為載入期硬驗證，壞資料直接讓啟動失敗而不是靜默缺圖；母集合切換後此原則不變，只換集合來源。

隔離規則已升格為 `AGENTS.md` 不可違反契約：「隔離區或未匹配資料不得進 API 或場景」（2026-08-07 實讀）。

## 4. 後果

- **正面**: 型錄數量成為測試可斷言的契約（`tests/test_official_cloud_catalog.py` 等，隨 `f5fc0995` 同步改版）；ID 映射規則杜絕同名猜測。
- **負面／已知不一致（2026-08-07 盤點）**:
  - `docs/contracts/POSTGRESQL_FURNITURE_EMBEDDINGS.md` 仍寫「家具來源筆數 9,349」「已匯入 9,349 筆正式向量」；`docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md` 亦提及 9,349——與現行 8,557 不一致，**多來源數字待 Kai 對齊**。
  - 工作階段記錄（2026-08-05，repo 外）：PostgreSQL 第 6 步實際可選 7,958 件、599 筆被 `is_active` 擋掉（8,557−599=7,958，算術一致）；本輪 psql 不在 PATH，**未複核**。
  - 舊型錄資料僅存於隔離區供核對；隔離總量見 `docs/contracts/POSTGRESQL_RUNTIME_CATALOG_PHASE4.md` 的正式筆數表（本文件不重抄）。
- **影響範圍**: `GET /api/furniture` 全部查詢、Agent 選件候選、3D 模型載入、PostgreSQL 匯入（[ADR-005](ADR-005-catalog-import-hardening.md)、[ADR-006](ADR-006-postgres-single-source-five-phases.md)）。
- **重新評估觸發**: 母集合增補（件數變動時 `OFFICIAL_CATALOG_COUNT` 與測試需同步改）；契約文件 9,349 vs 8,557 對齊時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥（回溯撰寫） | 初版 9,350 件實測 |
| 2026-08-07 | VibeCoding Pilot 導入 | 補記 `f5fc0995` 切換；8,557 於常數、JSON 實數、README 三處複核一致；9,349 殘留與 DB 7,958 列入待對齊 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | FR-CATALOG-01／FR-CATALOG-02（正式型錄來源與隔離區邊界，srs §1.4 已定編）；[ADR-003](ADR-003-cloudfront-glb-delivery.md) |
| 影響範圍 | `backend/catalog/cloud_catalog.py`、`JSON/furniture/`、db_design 型錄表、api_spec 家具端點、`docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md` |
| 取代關係 | 本則內部：2026-07-30 集合切換取代 2026-07-26 的 9,350 母集合；舊編號對照：`docs/vibecoding/03_architecture/adr.md` ADR-004 |
