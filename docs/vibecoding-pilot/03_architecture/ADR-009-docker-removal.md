# ADR-009: 整套移除 Docker 容器化，回歸本機 uvicorn

> **狀態:** 已接受 | **日期:** 2026-08-06 | **決策者:** Ben（commit `09891216` 作者，commit 訊息明言「Ben 裁定」） | **Owner:** Ben（裁決）／Bella（server 啟動路徑）
> **語域:** L2（橋接）
> **定位:** 一個重大決策一份；記 context、選項、決定與後果。系統全貌歸 [sad.md](sad.md)，本文件只回答「為什麼這樣選」。
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

- **上下文**: 2026-08-05 容器化曾實際落地：commit `0c53ad01`（feat(infra): 容器化落地，multi-stage 映像＋唯讀資產 volume）建成映像並跑通，隨後 `4b3320be`（fix(infra)）處理容器內 opencv 被 rapidocr 拉成 5.x 的依賴鏈問題並停用容器 RAG。
- **問題**: 容器化在專案未達目標狀態時帶來持續維運成本：改 repo 檔案要重 build 映像才生效（開發回饋變慢）、容器內 RAG 不可用、依賴鏈需額外鎖版與 assert、17.8GB build cache 佔用磁碟。
- **驅動因素/約束**:
  - 產品仍在快速迭代期（八步流程持續修改），本機 `--reload` 開發迴圈價值高於部署一致性。
  - 團隊部署目標尚未定案，容器化的收益（環境一致、可攜）當下無消費者。

## 2. 考量的選項

> 選項是由 commit 訊息與前後 commit 狀態回推，未必是當時逐一討論過的完整清單。

### 選項一: 保留容器化，與本機 uvicorn 並行維護
- **描述**: Dockerfile／compose 留在 repo，文件維持兩套啟動路徑。
- **優點**: 保留已跑通的建置成果，未來部署免重做。
- **缺點**: 兩套路徑都要隨程式碼演進維護；容器行為差異（RAG 停用、資料 bind-mount 範圍）持續產生「文件說的與跑起來的不同」；開發期沒人用容器。
- **成本/複雜度**: 中（持續）

### 選項二: 整套移除，達到目標狀態後再重建
- **描述**: 刪除全部容器化檔案；容器 runtime 資料先遷回本機；建置期教訓另存供重建時用。
- **優點**: 單一啟動路徑（本機 uvicorn port 8002）；不再維護無消費者的部署面。
- **缺點**: 未來重新容器化要重做檔案（教訓已留存，成本可控）；一段 git 歷史內的建置成果暫時閒置。
- **成本/複雜度**: 低

## 3. 決策

**選擇**: 選項二，由 commit `09891216`（2026-08-06 chore(infra): 移除 Docker 容器化，回歸本機 uvicorn 執行，author Ben）實施。commit 訊息明言：「**Ben 裁定：專案達到目標狀態前不容器化，屆時再重建**」。

commit stat 實證刪除：`Dockerfile`（104 行）、`docker-compose.yml`（60 行）、`.dockerignore`（44 行）、`requirements-container.txt`（53 行）、`docs/DOCKER.md`（129 行）、README 的 Docker 一節（12 行），共 402 行刪除、零新增。

資料遷移（commit 訊息記載）：容器 runtime volume 內三個專案的 floorplan.png 已搬回 `.runtime/uploads/`；auth_secret.key 維持本機原有那把；映像、volume、network 與 17.8GB build cache 均已清除。

**現況複核（2026-08-07 實測）**: repo 根無 `Dockerfile`、無 `docker-compose.yml`（ls 實測）；README 啟動路徑只有本機 venv／uv 兩式，`uvicorn backend.server.main:app --port 8002`（README.md:32、48）。

## 4. 後果

- **正面**: 啟動路徑單一，文件與實際行為一致；開發迭代不再受映像重 build 拖累；磁碟釋出 17.8GB build cache。
- **負面**:
  - 部署一致性回到「換機部署清單」人工流程（`docs/NEW_MACHINE_SETUP.md`，commit `b5fd267b` 2026-08-05 新增）。
  - 容器時期建立的專案殘留舊程式碼快照的資料（如待處理家具查無 3D 模型），需按「更換家具」或重新配置解掉（工作階段記錄，repo 外；本輪未複核）。
  - 建置期學到的坑（rapidocr→opencv 5.x 依賴鏈、容器 RAG 停用、bind-mount 邊界）只存在 git 歷史與 repo 外工作階段記錄，重新容器化時需回收。
- **影響範圍**: 啟動與部署文件（README、NEW_MACHINE_SETUP、deployment_and_operations）、`.runtime/` 資料、開發環境需求（不再需要 Docker Desktop）。
- **重新評估觸發**: 「專案達到目標狀態」（Ben 裁定原文；具體驗收條件——未查證）；或出現多節點／雲端部署的實際需求時。

---

| 日期 | 審核人 | 備註 |
| :--- | :--- | :--- |
| 2026-08-07 | VibeCoding Pilot 導入 | commit `09891216` 訊息與 stat、現況無容器檔案皆實測；容器時期殘留資料引自工作階段記錄未複核 |

## 5. 追溯

| 項目 | ID |
| :--- | :--- |
| 觸發來源 | 容器化維運成本 vs 迭代速度的取捨（`0c53ad01`→`4b3320be`→`09891216` commit 鏈）；NFR-維運-01（本機 uvicorn 部署形態，srs §2 已定編） |
| 影響範圍 | deployment_and_operations 全文、runbook 啟動類症狀、README 快速啟動節 |
| 取代關係 | Supersedes：`0c53ad01`（2026-08-05 容器化落地）所代表的容器化路線；無舊編號對應 |
