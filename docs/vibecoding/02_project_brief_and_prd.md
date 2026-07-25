# 專案簡報與產品需求文件 (PRD) - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

---

## 1. 專案總覽

| 項目 | 內容 |
| :--- | :--- |
| **專案名稱** | RoomPilot-Agent — 建築平面圖（PNG）自動向量化與房型辨識管線 |
| **狀態** | 開發中（現行版本 v2.16，2026-07-25） |
| **目標發布日期** | 無對外發布日（內部工具，滾動式版本：Readme.md 版本日誌即發布紀錄）；商用部署前提是完成「去 CubiCasa」授權替換（見 §5 Q-001） |
| **核心團隊** | 內部團隊多機多分支協作（main/cody/bella/ben/ancai/django/kai-dev，一機一分支經 main PR 匯流）。PM/UX 角色 N/A——內部 CLI 工具，由開發者兼任需求把關；標注品質由「VLM 盲標＋人工把關」流程中的人工覆核者負責 |

**一句話定位**：輸入一張建築平面圖 PNG，自動輸出 (1) 公分單位的 DXF 向量圖（牆/窗/門，AutoCAD 可開）、(2) 房間切割與房型命名（kitchen/living/bed/bath/entry/storage/garage/office/stair 等）、(3) 品質檢核圖（`training/chk/*_chk.png`）與 HTML 辨識報表（`recognition_report.html`）。下游消費者是櫃體設計流程（`cabinet_designer.py` 為早期入口）——房型與樓梯區辨識直接決定「哪些空間可以擺櫃、擺什麼櫃」。

**形態**：純 Python 3.10+ CLI 專案，**無 Web 後端、無資料庫、無 REST API**。核心元件：

- 灰階向量化管線 `scripts/floorplan2dxf.py`＋`config.ini`（**已凍結，不再修改**）
- 彩色向量化管線 `scripts/floorplan2dxf_color.py`＋`config_color.ini`（現行開發重點）
- 房型辨識管線 `floorplan2room.py`（專案根；flood fill 切割＋CNN 語意投票命名；權重缺檔自動自 GitHub Release 下載＋SHA-256 校驗）
- 評測守門 harness `scripts/eval_*.py`（改動前後跑分防退化）
- 訓練管線 `training/CubiCasa5k/`（微調 v1~v5）與 DINOv2 分類探針（`scripts/probe_room_classifier.py`）

---

## 2. 商業目標

| 項目 | 內容 |
| :--- | :--- |
| **背景與痛點** | 平面圖以 PNG 點陣圖流通，人工重繪成 CAD 向量圖與逐房標房型費時且不可規模化；櫃體設計自動化的前置條件是「機器讀得懂平面圖」——牆在哪、窗門在哪、每個房間是什麼房型（尤其樓梯區不可擺設，屬硬需求）。 |
| **策略契合度** | 本管線是「平面圖 → 櫃體設計」自動化鏈路的上游基礎設施：DXF＋房型輸出直接餵給 `cabinet_designer.py` 與未來前端整合（丟任意新 PNG 即得房型判斷）。權重掛 GitHub Release、部署機 clone 即用，支撐多機協作與前端接入。 |
| **成功指標** | 主要 KPI：房型具名命中率（own 尺）與彩色窗召回。次要 KPI：牆/窗 F1、切割命中率、門位精準率。現況與目標值見下表。 |

### KPI 現況與目標（2026-07-25，v2.16 實測）

| 指標 | 現況 | 目標 | 備註 |
| :--- | :--- | :--- | :--- |
| 灰階牆 F1 | 0.99 | 維持不退化 | 灰階管線已凍結，評測守門即目標 |
| 灰階窗 P/R | 96% / 96% | 維持不退化 | 同上 |
| 彩色牆 P/R (IoU) | 87.7 / 94.9 (83.8) | 維持不退化 | v2.13 起穩定 |
| **彩色窗 P/R** | **62% / 38%** | 召回大幅拉升（具體目標值待確認） | **全系統最低，v2.16 定案為最大真實破口**；調參方向：牆段配對 gap 與 covered 門檻的線寬適配 |
| 房間切割命中 | 72.6%（53/73，配對 IoU 0.829） | 提升（floor60 GT 牆補封＋開放空間語意分界後重評） | 端對端 76.4%、IoU 0.875 |
| **房型具名命中（own 尺，主尺）** | **0.788**（52/66，v5 權重） | 持續提升（own_dataset 擴充後次輪微調） | 基線 0.273 → v5 0.788，史上首勝基線；具名 macro-F1 0.215 → 0.473 |
| 房型具名命中（CubiCasa 尺） | 0.797 | 參考尺，不設過門硬指標 | 未過 0.838 門檻，但使用者裁決目標域＝own，v5 仍接管預設（見 D-001） |
| DINOv2 探針具名正確率 | 0.730 | 新 GT 重評後再議是否接融合層 | 131 張訓練樣本即勝語意投票基線 0.270 |
| 門過濾 | 100% | 維持 | — |
| 門位 fused P/R | 0.576 / 0.868 | 精準率提升（118 候選中 50 誤報待清） | 待辦第 6 位 |

---

## 3. 使用者故事與允收標準

使用者＝內部團隊成員（管線操作者、標注者、部署者、下游櫃體設計開發者）。

### Epic A：平面圖向量化（PNG → DXF）

| ID | 描述 (As a / I want to / So that) | 允收標準 | BDD 連結 |
| :--- | :--- | :--- | :--- |
| US-001 | As a 管線操作者, I want to 丟一張灰階平面圖 PNG 給 `scripts/floorplan2dxf.py`, so that 我拿到公分單位、AutoCAD 可開的 DXF（牆/窗/門）與 `training/chk/gray/` 檢核圖。 | 1. DXF 輸出至 `dxf_scale/`，單位公分 2. 牆厚自動偵測、正交線重建（不描輪廓）3. 對 `Identify_ans/pngans/` 評分：牆 F1 0.99、窗 96%/96% 不退化 | N/A（見注） |
| US-002 | As a 管線操作者, I want to 丟彩色渲染平面圖給 `scripts/floorplan2dxf_color.py`, so that 彩色考卷也能得到同規格 DXF。 | 1. 彩牆 P 87.7/R 94.9 不退化 2. 窗偵測走獨立二值層（淺灰描邊白條不被牆二值化濾掉）3. 彩窗召回現況 38%，改動須經 `scripts/eval_windows.py` 評分且不得退化後覆蓋 | N/A（見注） |

### Epic B：房型辨識（DXF/PNG → 房間切割＋命名）

| ID | 描述 (As a / I want to / So that) | 允收標準 | BDD 連結 |
| :--- | :--- | :--- | :--- |
| US-003 | As a 下游櫃體設計開發者, I want to 用 `floorplan2room.py` 取得每個房間的輪廓與房型（含 stair）, so that 櫃體設計知道哪些空間可擺設、該擺什麼櫃。 | 1. flood fill＋門洞封口切割，命中 72.6% 以上 2. own 尺具名命中 0.788 以上（v5 權重）3. 樓梯（stair）必須可辨識——樓梯區不可擺設為硬需求 4. 報表輸出 `json/eval_rooms/*.json` 與 `recognition_report.html` | N/A（見注） |
| US-004 | As a 標注者, I want to 用標注工具鏈（`scripts/fix_own_floor.py`、`fix_annotation_paths.py`、`rebuild_room_gt.py`、review.html 流程）走「VLM 盲標＋人工把關」, so that own 資料集能以低成本擴充且品質可靠。 | 1. transform 已烘焙（Inkscape matrix 陷阱）2. get_polygon 尾空格陷阱有防回歸測試 3. own_eval 12 題永不進訓練 4. 人工覆核為必經步驟（VLM 標注不得直接採信） | N/A（見注） |

### Epic C：權重發佈與部署

| ID | 描述 (As a / I want to / So that) | 允收標準 | BDD 連結 |
| :--- | :--- | :--- | :--- |
| US-005 | As a 部署者, I want to 在新機器 clone repo 後設一個 `GITHUB_TOKEN` 環境變數就能跑, so that 不必手動搬 200MB 權重檔。 | 1. `model_finetuned_v5.pkl` 缺檔時 `_ensure_cc_weights` 自動從 Release tag `weights-v5` 下載 2. SHA-256 校驗（b7a280d2…f4cf）不符即失敗 3. `CC_WEIGHTS` 指定自訂權重時缺檔不代抓 4. 既有考卷走版控快取（`cubicasa/room/`）不觸發下載 5. tests/ 中 `test_cc_weights_download` 7 例單元測試通過 | N/A（見注） |
| US-006 | As a 訓練者, I want to 用 `scripts/pack_finetune_data.py` 打包 `training/finetune_data.zip` 帶去 GPU 機（RTX 3060 / GTX 1650）微調, so that 無 GPU 的本機（Cody 機，WSL2、torch CPU 版）也能參與訓練迭代。 | 1. 打包內容可在 GPU 機依 `docs/HANDOVER_finetune_v5.md` 步驟復現訓練 2. 官方 44 類權重須 `--weights ＋ --new-hyperparams`（誤用 `--furukawa-weights` 即 size mismatch，已勘誤）3. 新權重須經 `scripts/eval_rooms_cc.py` own 尺評分，經人工審批才接管預設 | N/A（見注） |

> **BDD 連結欄注**：N/A——本專案無 `.feature` 檔與 BDD 框架。對應物是**評測守門 harness**（`scripts/eval_windows.py`、`eval_rooms_cc.py`、`eval_color_walls.py`、`eval_doors.py`、`eval_door_match.py`、`eval_cc_masks.py`、`score_compare.py`）＋ pytest 單元測試（`tests/` 現有 6 檔）：每條允收標準以「對 GT 跑分不退化」與測試綠燈驗收，而非 Gherkin 場景。

---

## 4. 範圍與限制

| 項目 | 內容 |
| :--- | :--- |
| **功能範圍** | - 灰階向量化管線（凍結維護）<br>- 彩色向量化管線（現行開發重點，彩窗召回為首要缺口）<br>- 房型辨識管線（切割＋命名，v5 微調權重為預設）<br>- 評測守門 harness 與 HTML 辨識報表<br>- 標注工具鏈與 own 資料集（`Identify_ans/`：pngans gray 38＋color 29、own_dataset 25 題、own_eval 12 題）<br>- 訓練管線（CubiCasa5k 微調）與 DINOv2 分類探針（去 CubiCasa 路線）<br>- 權重 Release 發佈與自動下載部署 |
| **非功能需求** | **正確性**：改 chk/dxf 邏輯前必先跑 `scripts/eval_windows.py` 對 `Identify_ans/pngans/` 評分，不得退化後覆蓋（評測鐵律）。**可重現性**：權重 SHA-256 校驗；opencv 鎖 `>=4.10,<5`（HoughLinesP shape 破壞性變更）、numpy≥2、ezdxf≥1.3。**安全**：GITHUB_TOKEN 為 PAT 密碼等級秘密，只走環境變數、勿進版控（`.claude/rules/security.md`）。**可攜性**：部署機 clone＋設 token 即用；訓練可搬 zip 換 GPU 機。性能無明訂 SLA（批次離線處理，N/A——非線上服務）。 |
| **不做什麼** | - 不提供 Web 後端、資料庫、REST API（純 CLI；前端整合為未來事項，目前僅 `recognition_report.html` 靜態報表）<br>- 不再修改灰階管線 `scripts/floorplan2dxf.py`（已凍結）<br>- 不做家具擺設/櫃體設計本體（那是下游 `cabinet_designer.py` 及其後續的事，本專案只交付 DXF＋房型）<br>- 不以面積規則猜房型（禁面積規則，房型一律走辨識式）<br>- own_eval 12 題永不進訓練集（保留評分集鐵律）<br>- 在完成授權替換前，不做任何商用部署（CubiCasa5k 禁商用，見下） |
| **假設與依賴** | **假設**：目標域＝own 風格平面圖（使用者裁決，見 D-001）；輸入為單層平面圖 PNG（灰階或彩色渲染）。**依賴**：CubiCasa5k repo（CC BY-NC 4.0）與資料集（CC BY-NC-SA 4.0）——官方權重與微調 v1~v5 **全繼承禁商用**，`floortrans/` 解析程式碼亦同，長期須自寫替換；GitHub Release 承載 200MB 權重（GitHub 100MB 硬限）；私有 repo 下載依賴 GITHUB_TOKEN；訓練依賴外部 GPU 機（本機 Cody 無 GPU）；訓練另依賴 lmdb、scikit-image、svgpathtools。 |

---

## 5. 待辦問題與決策

（優先序依 v2.16 定案；詳細脈絡見 `Readme.md` 版本日誌與 `docs/HANDOVER_finetune_v5.md`）

| ID | 描述 | 狀態 | 負責人 |
| :--- | :--- | :--- | :--- |
| Q-001 | 彩色窗召回 38%（P62/R38，全系統最低）——最大真實破口；方向：牆段配對 gap 與 covered 門檻的線寬適配 | 待處理（優先序 1，原第 1 位 DINOv2 已降級） | 待確認 |
| Q-002 | 切割收尾：floor60 GT 牆補封、開放空間語意分界（家具聚落切縫） | 待處理 | 待確認 |
| Q-003 | own_dataset 擴充 50~100 題（VLM 盲標＋人工把關）；彩色 30 題標注草稿人工修正（次輪訓練素材） | 進行中（color 30 題草稿已產出，commit 95b0778） | 待確認 |
| Q-004 | 彩色管線門位/切割/命名三層 GT 建集（現僅牆窗有答案） | 待處理 | 待確認 |
| Q-005 | 門位精準率 0.576（118 候選 50 誤報） | 待處理 | 待確認 |
| Q-006 | 長期：floortrans 解析自寫替換（程式碼授權 CC BY-NC，商用前必辦） | 待處理（長期） | 待確認 |
| Q-007 | DINOv2 裁切分類器是否接進 floorplan2room 融合層（含 10 類對齊——office/stair 未進評分與訓練） | 已降級為「新 GT 重評後再議」——v5 預設 0.788 已超 DINOv2 0.730 舊快照 | 待確認 |
| D-001 | **目標域＝own 風格；v5 權重接管預設**（`floorplan2room.py` CC_WEIGHTS）——CubiCasa 尺 0.797 未過 0.838 門檻，但 own 尺 0.788 史上首勝基線，使用者裁決以 own 為主尺 | 已決定（v2.16） | 使用者裁決 |
| D-002 | 房型類別定案 **10 類**：既有 8 類＋office＋stair（stair 為硬需求）；走道標 Undefined 併 space（與 CubiCasa 的 HallWay→entry 慣例不同） | 已決定（v2.14） | 使用者裁決 |
| D-003 | 灰階管線凍結，開發重點集中彩色管線（`floorplan2dxf_color.py`） | 已決定 | 使用者裁決 |
| D-004 | own_eval 12 題永為保留評分集、永不進訓練 | 已決定（v2.14 審定） | 使用者裁決 |
| D-005 | 200MB 權重不進版控，走 GitHub Release（tag `weights-v5`）＋缺檔自動下載＋SHA-256 校驗；部署機僅需 GITHUB_TOKEN | 已決定（v2.16） | — |
| D-006 | 確立「去 CubiCasa」路線動機：授權禁商用實錘（repo CC BY-NC 4.0、資料集 CC BY-NC-SA 4.0），商用部署前必須替換權重與解析程式碼 | 已決定（v2.15） | — |
| D-007 | 訓練資產 `training/` 本機自管不 push（gitignore），換機以 zip 搬運；v2.15 大清理 17GB 後備份需重新打包 | 已決定（v2.14/v2.15） | — |

---

### 相關文件

- 專案簡報總覽與規則：見本目錄其他 VibeCoding 文件（`docs/vibecoding/`）
- 版本日誌與各輪決策全文：`Readme.md`
- 微調 v5 交接與訓練 SOP：`docs/HANDOVER_finetune_v5.md`
- 腳本說明：`scripts/README.md`
- 開發流程規範：`.claude/rules/`（development-workflow、git-workflow、testing、security 等）
