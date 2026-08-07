# ADR-007: 燈具獨立資料表（lighting lane），不進家具母集合

> **狀態:** 已接受（分表偏離契約原文，待 Kai／Django／Bella／Ancai 四人確認） | **日期:** 2026-08-02 | **決策者:** commit `cb2637af` 作者 Ben；型錄 owner 為 Kai，拍板過程（未查證） | **Owner:** Kai
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，資料語意歸 `docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md`，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則為新增，舊 `docs/vibecoding/03_architecture/adr.md` 無對應
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 2026-07-30 型錄切換（commit `f5fc0995`，見 [ADR-004](ADR-004-official-catalog-master-set.md)）把 793 筆燈具記錄以 `removed_lighting_*` 從家具 items 移除，但沒有補上契約說好的 lighting manifest，那批資產一度無家可歸（`scripts/sql/build_lighting_manifest.py:1-6` docstring 明言，2026-08-07 實讀）。
- **問題**: 燈具有 GLB 資產與渲染價值，但語意上不是第 6 步自動擺放的家具——混在家具母集合會污染擺放候選；整批丟棄則損失 793 筆可用資產。
- **驅動因素/約束**:
  - `docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md`（草案，需 Kai／Django／Bella／Ancai 共同遵守）要求燈具、天花板、材質、冷氣各有明確 owner，不混在一起。
  - 家具母集合有載入期件數硬驗證（[ADR-004](ADR-004-official-catalog-master-set.md)），燈具進出都會打破 8,557 契約。

## 2. 考量的選項

> 未被採納的選項是由 commit 前後狀態與契約文本回推，未必是當時實際討論過的方案。

### 選項一: 燈具留在家具母集合，以 role／type 欄位區分
- **描述**: 793 筆保留在 items，前端與引擎依欄位過濾。
- **優點**: 單一資料表；與契約原文「燈具屬 Kai catalog（`asset_kind: lighting_fixture`）」字面較接近。
- **缺點**: 母集合件數契約失真；第 6 步自動配置需處處排除燈具；擺放語意（吊燈掛天花板）與落地家具不同。
- **成本/複雜度**: 中

### 選項二: 燈具獨立表與獨立 manifest（lighting lane）
- **描述**: 專屬 `roompilot.lighting_assets` 表、`lighting_assets_manifest.csv`、分類器與匯入器；燈具由 `scene_json` 的 lighting 欄位引用，不參與第 6 步家具自動配置。
- **優點**: 家具母集合契約不受影響；燈具型別（pendant/track/downlight…）有專屬 CHECK 約束；待分流資產可標 `needs_review` 而不擋整批。
- **缺點**: 多一套 manifest／匯入／測試要維護；與契約原文的「單一 catalog」敘述有偏離，需四人補確認。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二，由 commit `cb2637af`（2026-08-02 feat(catalog): 燈具接回 lighting lane，793 筆資產重新入庫）實施，commit stat 實證交付：

- `backend/catalog/data/manifests/lighting_assets_manifest.csv`（793 資料列，2026-08-07 csv.DictReader 實測）
- `backend/catalog/lighting_classification.py`（燈具型別分類器）
- `scripts/sql/roompilot_postgresql_schema.sql`：`roompilot.lighting_assets` 表＋`lighting_type` CHECK（pendant/track/downlight/wall/table/floor/shade_base/unclassified_lighting/not_lighting）＋`lighting_assets_current` view（schema.sql:281-439 區段，實讀）
- `scripts/sql/import_lighting_assets_to_postgres.py`、`tests/test_lighting_assets_catalog.py`

schema 注釋明訂邊界：「燈具透過 `scene_json.surface_overrides.lighting_ids` 引用，不參與第 6 步家具自動（配置）」（schema.sql:279-280，實讀）。後續 commit `099fbb2d`（2026-08-05）把自動裝飾的燈具角色接上燈具表。

**現況數字（2026-08-07 manifest 實測）**: 793 筆中 `verification_status=verified` 637 筆、`needs_review` 156 筆；型別分布 table 311、floor 128、pendant 97、unclassified_lighting 83、wall 52、downlight 48、shade_base 48、not_lighting 25、track 1。

**理由**: 燈具的擺放語意與落地家具不同，且母集合件數是硬契約；獨立 lane 讓 793 筆資產回到可用狀態，同時不動 [ADR-004](ADR-004-official-catalog-master-set.md) 的 8,557 驗證。

## 4. 後果

- **正面**: 793 筆資產從「切換後無家可歸」恢復為可用（verified 637 筆即用、156 筆待 Kai 分流）；燈具型別有 DB 層 CHECK；渲染與自動裝飾有正式燈具來源。
- **負面**:
  - 分表做法與 `LIGHTING_CEILING_CATALOG_CONTRACT.md` 原文（燈具以 `asset_kind` 存在於 Kai catalog）有偏離，**待四人確認**（工作階段記錄 2026-08-02，repo 外；契約檔至今仍標草案）。
  - `unclassified_lighting` 83 筆與 `not_lighting` 25 筆混在 manifest，依賴 `verification_status` 過濾，分流完成前查詢端要記得帶條件。
  - 多一套 manifest／匯入器／測試的維護面。
- **影響範圍**: `backend/catalog/`、`scripts/sql/`、第 8 步渲染與自動裝飾、db_design 燈具表。
- **重新評估觸發**: 四人契約確認時（結論應回寫本 ADR 狀態）；156 筆分流完成時；燈具若需進入第 6 步自動配置（現契約明文禁止）。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-07 | VibeCoding Pilot 導入 | commit stat、schema DDL、manifest 793/637/156 皆實測；契約偏離待確認如實標註 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | `f5fc0995` 型錄切換的燈具移除（[ADR-004](ADR-004-official-catalog-master-set.md)）；FR-CATALOG-04（燈具獨立 lane，srs §1.4 已定編）；渲染呈現另涉 FR-RENDER-01／FR-SCENE-01 |
| 影響範圍 | `docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md`、db_design 燈具表、`scene_json.surface_overrides.lighting_ids` 契約 |
| 取代關係 | 無；舊編號無對應 |
