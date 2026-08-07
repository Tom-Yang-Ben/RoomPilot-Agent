# ADR-003: GLB 模型由 CloudFront 供應（預設 `cloudfront` 模式）

> **狀態:** 已接受 | **日期:** 2026-07-23 | **決策者:** Kai（型錄／AWS 歸屬）＋Bella（commit `3260497e` 作者 bellayang312-source）；分工細節（未查證） | **Owner:** Kai（資產）／Bella（交付端點）
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則對應舊 `docs/vibecoding/03_architecture/adr.md` 之 ADR-003
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 家具 GLB 模型體積大，模型不進 git（`.gitignore` 排除；AGENTS.md 不可違反契約亦禁止提交大型 GLB）；本機 GLB 依賴各成員自行下載，跨機器不一致。
- **問題**: 網站要能穩定載入數千件家具模型，不能依賴每台開發機的本機檔案。
- **驅動因素/約束**:
  - GLB 已上傳 S3 並經 CloudFront 發佈，manifest 記錄每件的 delivery URL。
  - 前端 Three.js 的 GLTF loader 可直接載入 HTTPS URL。

## 2. 考量的選項

> 未被採納的選項是由 commit 前後狀態回推，未必是當時實際討論過的方案。

### 選項一: 本機 GLB + repo 外資料目錄
- **描述**: 維持本機檔案，由後端以 FileResponse 供應。
- **優點**: 離線可用。
- **缺點**: 大量資料每台機器都要放對位置；git 不管理，一致性無保證。
- **成本/複雜度**: 低（程式）／高（維運）

### 選項二: CloudFront 供應 + manifest 驗證，本機模式保留為 fallback
- **描述**: 預設由 CloudFront 轉址供應；只信任 manifest 驗證過的 URL；以環境變數切換 local 模式。
- **優點**: 跨機器一致；URL 經 manifest 白名單，不猜測拼接。
- **缺點**: 執行期需要網路；離線開發需另備方案。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二，由 commit `3260497e`（2026-07-23 feat(catalog): adopt verified CloudFront furniture manifest）引入 `backend/server/services/cloud_models.py` 實施。現行碼複核（2026-08-07 實測）：

- `ROOMPILOT_MODEL_DELIVERY_MODE` 預設 `"cloudfront"`（`cloud_models.py:47`）。
- CloudFront base 預設 `https://ddgsm1yg3xikc.cloudfront.net`（`cloud_models.py:32`），可用 `ROOMPILOT_CLOUDFRONT_BASE_URL` 覆寫；manifest 路徑可用 `ROOMPILOT_GLB_MANIFEST_PATH` 覆寫。
- `GET /api/furniture/{furniture_id}/model`（`backend/server/main.py:1518`）有雲端 URL 時回 **307 RedirectResponse**（main.py:1523、634）。
- cloudfront 模式下，本機 glTF 拆解端點一律回 **410**（main.py:1530、1539、1549、1619）。
- 只回 manifest 驗證過的 URL，manifest 缺列即回 None，不拼 URL 猜測。

**理由**: 模型交付與 repo 解耦；manifest 是唯一信任來源。契約全文見 `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`（本文件不重抄）。

## 4. 後果

- **正面**: 模型跨機器一致；前端可直接載 CloudFront URL。
- **後續演變**:
  - 母集合已於 2026-07-30 由 9,350 件雲端集切換為 Kai 官方 8,557 件（commit `f5fc0995`，見 [ADR-004](ADR-004-official-catalog-master-set.md)）；CloudFront 交付機制不變，manifest 集合隨之更新。
  - PostgreSQL Phase 1 之後，`/api/furniture/{item_id}/model` 優先由 PostgreSQL 取得 CloudFront GLB URL（`docs/contracts/POSTGRESQL_CATALOG_READ_PHASE1.md`，見 [ADR-006](ADR-006-postgres-single-source-five-phases.md)）；CloudFront 仍是實際資產載體。
  - README 首節（2026-08-07 實讀）：本機 IKEA GLB 備援**尚未完成**，完成前不得在 `.env` 啟用本機模式——CloudFront 目前是唯一正式模型來源。
- **負面**:
  - 執行期依賴外部網路與 CloudFront 存活；離線時 3D 模型無法載入。
  - local 模式的本機解析路徑缺陷（DATASET_DIR 指向不存在目錄、模型端點 404）為 2026-07-26 舊版實測記載，本輪未複核；README 已明文禁止啟用本機模式，實害受限。
- **影響範圍**: `backend/server/`、`frontend/` 的模型載入、部署環境變數。
- **重新評估觸發**: CloudFront 費用或供應商變更；完全離線 demo 需求；IKEA 本機備援完成（README 首節載明 Django＋Kai 待辦）。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥（回溯撰寫） | 程式行號與 commit 實測；AWS 帳務不在本 ADR 範圍 |
| 2026-08-07 | VibeCoding Pilot 導入 | 預設模式、307/410 行號於現行碼複核更新；補 PostgreSQL Phase 1 與母集合切換的演變 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | FR-CATALOG-01（正式家具與模型交付）、NFR-可用性-01（srs §1.4／§2 已定編）；跨機器模型交付動機另見 srs §4 外部介面 CloudFront 列 |
| 影響範圍 | `docs/contracts/CATALOG_MODEL_DELIVERY_CONTRACT.md`、api_spec 家具模型端點、deployment_and_operations 環境變數表 |
| 取代關係 | 無；舊編號對照：`docs/vibecoding/03_architecture/adr.md` ADR-003 |
