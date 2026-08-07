# ADR-005: 型錄匯入硬化——狀態白名單＋非破壞性預設

> **狀態:** 已接受 | **日期:** 2026-07-26 | **決策者:** Bella（commit `e48cd672` 作者 bellayang312-source）；Kai 為匯入工具 owner，拍板過程（未查證） | **Owner:** Kai
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則對應舊 `docs/vibecoding/03_architecture/adr.md` 之 ADR-005
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: [ADR-004](ADR-004-official-catalog-master-set.md) 初版實作（`83b3c8a5`）有三個弱點：(1) manifest 只驗 URL 是 HTTPS，不驗 `upload_status` 是否為可發布狀態；(2) PostgreSQL 匯入器預設**清除**官方集合以外的資料列——破壞性行為是預設值；(3) repo 內同時存在兩份 manifest，來源二義。
- **問題**: 上傳失敗的列可能混入正式型錄；誤跑匯入指令會刪掉資料庫既有資料。
- **驅動因素/約束**:
  - 匯入工具會被不同成員在不同機器執行，預設值必須安全。
  - manifest 是模型存在性的唯一信任來源，狀態欄位必須參與驗證。

## 2. 考量的選項

> 未被採納的選項是由 commit 前後狀態回推，未必是當時實際討論過的方案。

### 選項一: 維持首版（不驗狀態、預設清除、雙 manifest 並存）
- **描述**: 不動。
- **優點**: 無工作量。
- **缺點**: 三個弱點持續存在；誤操作即資料損失。
- **成本/複雜度**: 低

### 選項二: 白名單驗證＋反轉預設為非破壞＋收斂 manifest 來源
- **描述**: 見決策段。
- **優點**: 壞列在載入期就 fail；預設安全；manifest 來源明確。
- **缺點**: 需要清除多餘列時要記得加旗標。
- **成本/複雜度**: 低

## 3. 決策

**選擇**: 選項二，由 commit `e48cd672`（2026-07-26 fix(catalog): harden cloud database import）實施：

1. **狀態白名單**: `READY_UPLOAD_STATUSES = {uploaded, already_exists, complete, completed, success, skipped_existing}`（現行 `backend/catalog/cloud_catalog.py:16-23`，2026-08-07 實測仍在）；manifest 列的 `upload_status` 不在白名單即 raise（`cloud_catalog.py:131` 分支）。
2. **非破壞性預設**: 匯入器旗標由「預設清除」反轉為 `--prune-extra`（預設保留，明確要求才清除）。現行 README.md:265-266（2026-08-07 實讀）：「匯入採 transaction 與 UPSERT，預設不刪除其他資料。只有經過人工確認才可使用 `--prune-extra`」。
3. **單一 manifest**: 刪除當時重複的 `glb_upload_manifest.csv`。
4. **路徑可覆寫**: manifest 路徑改由 `ROOMPILOT_GLB_MANIFEST_PATH` 注入，測試與部署可用替代 manifest。

**理由**: 資料工程工具的預設值應該是「不動既有資料」；破壞性操作必須是明確選擇。狀態白名單把「上傳成功與否」納入契約驗證，與 ADR-004 的載入期硬驗證一致。

## 4. 後果

- **正面**: 誤跑匯入不再刪資料；壞列在載入期 fail；同 commit 補測試（`tests/test_official_catalog_sql.py`、`tests/test_official_cloud_catalog.py`）。
- **後續演變**:
  - 決策第 3 點「刪除重複 manifest」已被後續發展部分還原：`glb_upload_manifest.csv` 是上傳前快照、`*_all_result.csv` 是上傳結果，兩者為分工而非矛盾來源；雙份目錄的分工已由 commit `546be2c9`（2026-08-05 docs(catalog): 釐清 manifest 雙份目錄的分工）文件化。
  - 母集合切換（`f5fc0995`，2026-07-30）同步改寫匯入器與其測試（commit stat 實證）；白名單與非破壞預設兩機制沿用至今（2026-08-07 實測常數仍在、README 敘述仍在）。
- **負面**: 需要清理資料庫多餘列時，忘了 `--prune-extra` 會殘留舊資料；匯入後件數驗證把關（沿用 2026-07-26 版記載，本輪未複核驗證行號）。
- **影響範圍**: `backend/catalog/cloud_catalog.py` 的所有載入方（伺服器啟動、測試）、`scripts/sql/` PostgreSQL 匯入流程。
- **重新評估觸發**: manifest 出現白名單以外的新狀態值時；匯入流程隨 [ADR-006](ADR-006-postgres-single-source-five-phases.md) Phase 演進而改動預設值時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥（回溯撰寫） | 依 `git show e48cd672` diff 實測 |
| 2026-08-07 | VibeCoding Pilot 導入 | 白名單常數與 README 非破壞敘述於現行複核仍在；manifest 雙份分工補 `546be2c9` |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | [ADR-004](ADR-004-official-catalog-master-set.md) 首版弱點（事故預防，無 postmortem——未查證）；NFR-資料安全-*（待 srs 定編） |
| 影響範圍 | `backend/catalog/cloud_catalog.py`、`scripts/sql/import_official_catalog_to_postgres.py`、db_design 匯入流程段 |
| 取代關係 | 無；舊編號對照：`docs/vibecoding/03_architecture/adr.md` ADR-005 |
