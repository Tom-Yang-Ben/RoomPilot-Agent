# ADR-001: 統一 `backend/` 單層套件與一人一目錄

> **狀態:** 已接受 | **日期:** 2026-07-24 | **決策者:** Bella（整合 commit 作者 bellayang312-source）＋團隊合併規則；口頭決策過程（未查證） | **Owner:** Bella
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，本文件只回答「為什麼這樣選」。
> **實例:** 每決策一份（`ADR-NNN-<slug>.md`）；本則對應舊 `docs/vibecoding/03_architecture/adr.md` 之 ADR-001
> **生成:** 2026-08-07 由 VibeCoding_Workflow_Templates/03_architecture/adr.md 導入 | 基準 docs/vibecoding-restructure @ 1268b2b4

---

## 目錄

- [1. 背景與問題](#1-背景與問題)
- [2. 考量的選項](#2-考量的選項)
- [3. 決策](#3-決策)
- [4. 後果](#4-後果)
- [5. 追溯](#5-追溯)

## 1. 背景與問題

- **上下文**: 專案由多人分別開發平面圖辨識、型錄、空間資料、選件 Agent、擺放引擎、伺服器與前端，各自分支曾使用不同的套件結構。commit `3260497e`（2026-07-23）時伺服器程式仍在 `roompilot/server/` 路徑下。
- **問題**: 多套件命名並存造成 import 路徑不一致、分支合併時大量路徑衝突，且無法一眼判定每個目錄的負責人。
- **驅動因素/約束**:
  - 多人平行開發、合併頻繁，需要最小衝突面的目錄劃分。
  - 與團隊既有的 `backend/frontend/data` 結構對齊。

## 2. 考量的選項

> 未被採納的選項是由 commit 前後狀態回推，未必是當時實際討論過的方案。

### 選項一: 保留 `roompilot/` 套件名
- **描述**: 維持 commit `3260497e` 時期的 `roompilot/server/`、`roompilot/agent/` 等路徑。
- **優點**: 不需大規模 rename，既有分支免改 import。
- **缺點**: 與團隊其他分支的 `backend/` 結構不一致，合併衝突持續。
- **成本/複雜度**: 低（短期）／高（長期合併成本）

### 選項二: 統一為 `backend/` 單層套件，一人一個主要目錄
- **描述**: 全套件 rename 為 `backend/`，並在 README 與 `AGENTS.md` 明定每人唯一主要目錄。
- **優點**: import 路徑單一；責任邊界清楚，合併規則可執行。
- **缺點**: 一次性大規模 rename，所有分支需跟進。
- **成本/複雜度**: 中

## 3. 決策

**選擇**: 選項二。

**理由**: commit `b04833ce`（2026-07-24「整合：完成 Bella 公分制架構與十步空間規劃流程」）以 git rename（`{roompilot => backend}`）完成統一，commit 訊息明言「統一 backend 目錄與公分制資料契約」。

目錄責任的**單一權威是 `AGENTS.md` 的「目錄責任與資料邊界」表**（AGENTS.md §目錄責任與資料邊界），本文件不重抄；現行要點：Bella（`backend/server/`、`frontend/`）、Cody（`backend/floorplan/`、`backend/upgrade3d/`）、Django（`backend/spatial_data/`）、Kai（`backend/catalog/`、`JSON/`、`scripts/sql/`）、Yen（`backend/agent/`）、Ancai（`backend/engine/`）。責任認定以 `docs/TEAM_AI_OWNERSHIP.md` 為準，不可只依 git author 推論。

啟動指令為 `uvicorn backend.server.main:app --port 8002`（README.md:32、48，2026-08-07 實讀）。

## 4. 後果

- **正面**: import 路徑與啟動指令單一化；責任目錄成為合併規則與 `AGENTS.md` 跨資料夾修改流程的依據。
- **後續演變（2026-08-07 實測，與 2026-07-26 舊 ADR 記載相比）**:
  - 舊記載「全部路由集中在 `main.py`（2,796 行）、無 APIRouter」**已不成立**：`main.py` 現為 1,623 行、23 個路由裝飾子，其餘拆入 `auth/api.py`（12）、`projects_api.py`（14）、`scene_api.py`（8）、`engineering/api.py`（8）、`catalog_admin.py`（4）、`shortlist_api.py`（3）、`rag_api.py`（5；雙 router——1 條頁面 router＋4 條掛 `current_user` 的 api_router，rag_api.py:31-32），全 `backend/server/` 共 **77 個路由裝飾子**（grep 實測，與 sad／api_spec 的 77 條路由一致）。
  - 舊記載「`backend/spatial_data/` 僅有 `.gitkeep`」**已不成立**：現有 `rag/` 子套件（Django 的家具 RAG runtime，實測列目錄）。
  - 前端於 2026-08-02 由 `backend/server/static/` 搬到 repo 根 `frontend/`（commit `ca051dbc`）；前端磁碟位置由 `backend/paths.py` 的 `STATIC_DIR` 決定（AGENTS.md 不可違反契約）。
- **負面**: 一人一目錄的邊界使跨目錄整合必須走 `AGENTS.md` 的跨資料夾修改格式，流程成本較高（此為刻意設計）。
- **影響範圍**: 全體成員的分支與 import；`tests/` 的模組歸屬。
- **重新評估觸發**: 目錄責任表變動（成員異動）或第二套服務整合裁決時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-07-26 | 本顥（回溯撰寫） | 依 commit `b04833ce` 與當時 README 整理 |
| 2026-08-07 | VibeCoding Pilot 導入 | 路由拆分、spatial_data、frontend 搬遷三項已對現行碼複核更新 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | 多分支合併衝突（事故性背景，無正式 postmortem 紀錄——未查證）；NFR-維護性-*（待 srs 定編） |
| 影響範圍 | `backend/*` 全套件、`frontend/`、`tests/`；api_spec、lld 的模組結構段 |
| 取代關係 | 無；舊編號對照：`docs/vibecoding/03_architecture/adr.md` ADR-001 |
