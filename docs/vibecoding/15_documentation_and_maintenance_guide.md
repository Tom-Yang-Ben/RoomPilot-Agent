# 文檔與維護指南 - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

> 本文件盤點 RoomPilot-Agent 的全部文檔資產、各自的維護節奏與單一事實來源（SSOT）分工，並對照通用模板的 README / CHANGELOG 體例說明本專案的實際做法。相關文件：專案結構見 [./08_project_structure_guide.md](./08_project_structure_guide.md)、部署與權重發佈見 [./14_deployment_and_operations_guide.md](./14_deployment_and_operations_guide.md)。

---

## 1. 文檔類型

模板的四分類對映到本專案的實際資產如下（本專案為純 Python CLI 管線，無 Web 後端、無資料庫、無 REST API）：

| 類型 | 模板定義 | 本專案對應物 | 格式 |
| :--- | :--- | :--- | :--- |
| **API 文檔** | OpenAPI 規範、端點、認證、錯誤碼 | **N/A（無 REST API）**。對應物是「CLI 介面與環境變數契約」：各腳本的 argparse 用法寫在 `scripts/README.md`；環境變數契約（`CC_WEIGHTS`、`CC_CACHE_DIR`、`GITHUB_TOKEN`/`GH_TOKEN`）散見 `Readme.md` v2.11/v2.16 與 `docs/HANDOVER_finetune_v5.md`；JSON 輸出 schema（json/、arch/）記錄在 `Readme.md` v1.4/v1.6/v1.9 各版章節。詳見 [./06_api_design_specification.md](./06_api_design_specification.md) | Markdown |
| **架構文檔** | 系統概覽、元件圖、資料流 | `docs/vibecoding/` 本套（05 架構文件、09 檔案相依、10 類別關係）；歷史設計文件在 `docs/superpowers/plans/`（4 份）與 `docs/superpowers/specs/`（4 份，2026-07-15～07-23 的 finetune-prep / room-eval / symbol-lib / own-eval-scale） | Markdown |
| **使用者文檔** | 快速開始、教學、操作指南 | `Readme.md`（版本誌兼交接紀錄，v1.0～v2.16）＋ `scripts/README.md`（逐腳本用法與指令範例）＋ `recognition_report.html`（四層級辨識成功率 HTML 報表，支援深色模式，本身也是「成果文件」） | Markdown / HTML |
| **開發者文檔** | 環境設置、風格指南、貢獻規範 | 環境設置：`Readme.md` v2.6「〇、換機交接」章節（.venv 重建順序、opencv `<5` 鎖版、GPU 兩機基準）＋ `requirements.txt`；風格與流程規範：`.claude/rules/` 八檔；訓練換機交接：`docs/HANDOVER_finetune_v5.md` | Markdown |

---

## 2. 文檔即程式碼（現有資產盤點）

### 實際目錄結構

模板建議的 `docs/api|architecture|guides|developer` 四分法在本專案未採用；實際結構是「歷史累積 + 三代文件體系並存」：

```
RoomPilot-Agent/
├── Readme.md                          # 版本誌主文件（461 行，v1.0~v2.16 反時序）— 專案 SSOT
├── recognition_report.html            # 四層級成功率 HTML 報表（每輪全批次重跑後重算）
├── scripts/README.md                  # scripts/ 腳本說明（174 行；文件涵蓋 20 支，實際已 25 支）
├── docs/
│   ├── HANDOVER_finetune_v5.md        # 微調 v5 換機交接（166 行；訓練指令、審批 SOP、陷阱清單、統一色表）
│   ├── superpowers/
│   │   ├── plans/                     # 歷史實作計畫 4 份（2026-07-15~07-23）
│   │   └── specs/                     # 歷史設計文件 4 份（同名 -design.md）
│   └── vibecoding/                    # 本套結構化文件（01~17，2026-07-25 依模板實例化）
├── VibeCoding_Workflow_Templates/     # 模板原文（17 份＋INDEX），唯讀參照，不在此改內容
├── .claude/
│   ├── CLAUDE.md                      # AI 協作總則（skill 優先序、subagent context 持久化）
│   ├── rules/                         # 開發規範 8 檔（development-workflow / git-workflow / testing /
│   │                                  #   security / coding-style / performance / patterns / subagent-context）
│   └── context/                       # subagent 產出留存（decisions/quality/testing/e2e/security/deployment/docs）
└── json/eval_rooms/                   # 評測報表 13 份 JSON（report.json、report_own*.json、report_gtseg_ft_v1~v5.json）
                                       #   ——「機器可讀的文檔」，A/B 對比與退化偵測的依據
```

### SSOT 分工表（哪類事實以哪份文件為準）

| 事實類別 | SSOT | 說明 |
| :--- | :--- | :--- |
| 現況指標數字（牆/窗/門/切割/命名） | `Readme.md` 最新版本章節（現為 v2.16）＋ `json/eval_rooms/*.json` | Readme 記人讀的結論，JSON 報表是機器可讀原始值；`recognition_report.html` 是兩者的視覺化，不是來源 |
| 待辦優先序 | `Readme.md` 最新版本章節的「待辦」節 | 每版重排定序（如 v2.16 把 DINOv2 接線降級、彩窗召回升為首位）；舊版章節的待辦一律視為過期 |
| 腳本用法與 CLI 參數 | `scripts/README.md` | 程式碼本身（argparse `--help`）為最終依據；README 落後時以程式碼為準並回頭補文件 |
| 訓練流程與換機步驟 | `docs/HANDOVER_finetune_v5.md` | 含 2026-07-25 實跑勘誤（`--weights`＋`--new-hyperparams`，誤用 `--furukawa-weights` 即 size mismatch）；下輪微調（v6）時應另立 HANDOVER_finetune_v6.md，舊檔保留為歷史 |
| 標注規範（色表/命名/審批 SOP） | `docs/HANDOVER_finetune_v5.md` 第二、三節 | 統一色表（13 類 HSL）、裁決鐵律（class 與填色衝突時填色通常是真實意圖）、fix_own_floor.py 七大陷阱防禦 |
| 開發流程規範（分支/commit/測試/安全） | `.claude/rules/` 八檔 | 先開分支鐵律、WHY/WHAT/IMPACT commit、TDD 80%、評測守門；文件間引用勿另發明 |
| 環境重建（依賴/鎖版/GPU） | `Readme.md` v2.6「〇、換機交接」＋ `requirements.txt` | opencv-python 與 headless **兩顆都必須 <5**（HoughLinesP shape 破壞性變更）；torch cu126 裝法、兩機 VRAM 基準 |
| 架構與模組劃分詞彙 | `docs/vibecoding/` 本套（05/08/09/10） | C4 Container 級詞彙以本套為準，避免各文件自創名詞 |
| 歷史設計決策 | `Readme.md` 對應版本章節＋ `docs/superpowers/specs/` | 例：MitUNet 移除（v2.13）、CubiCasa 端到端評分退役（v2.12）、去 CubiCasa 路線授權動機（v2.15） |

### 撰寫規範（沿用專案既有實踐）

- **一律繁體中文**（`.claude/CLAUDE.md` 與 memory 規則）。
- **數字必須可追溯**：任何指標寫進文件前，對應的 `json/eval_rooms/` 報表或 eval 腳本輸出必須存在；不確定寫「待確認」，不編造。
- **誠實記錄失敗**：Readme 體例包含「未達標維持基線」（v2.11/v2.12 微調）、「命中歸零的誠實記錄」（v2.8 符號比對）——負面結果與根因分析是本專案文檔的核心價值，不可省略。
- **陷阱要落地成防禦**：文檔記錄的陷阱（get_polygon 尾空格、Inkscape transform 未烘焙、np.matrix numpy 2.x）都應同步落成腳本防禦（`scripts/fix_own_floor.py`、`scripts/apply_cubicasa_patches.py`）＋防回歸測試，文件只是索引。
- **版本控制**：所有 Markdown 文件進 git；`recognition_report.html` 與 `json/eval_rooms/*.json` 亦進版控（作為跨機同步的評分基準）。

---

## 3. 維護排程

本專案是內部多機協作（main/cody/bella/ben/ancai/django/kai-dev 分支即機器），文檔維護節奏綁定「版本事件」而非日曆月／季；模板的月／季排程改造如下：

### 每個版本號（v2.x）發佈時——必做

- [ ] `Readme.md` 頂部新增 `YYYY/M/D v.2.x 變更` 章節（反時序，最新在最上）
- [ ] 指標數字全部重跑後填入（評測鐵律：改 chk/dxf 邏輯前必先跑 `scripts/eval_windows.py` 對 `Identify_ans/pngans/` 評分，不得退化後覆蓋）
- [ ] 待辦清單重排定序（前版待辦逐項確認：完成／降級／升級，並註明原因，如 v2.16 的「待辦定序衝擊」節）
- [ ] 涉及快取/報表的變更同步重算 `json/eval_rooms/*.json` 與 `recognition_report.html`
- [ ] commit message 遵循 `.claude/rules/git-workflow.md` 的 WHY/WHAT/IMPACT 三段體

### 每輪微調訓練（v1~v5 已五輪）——必做

- [ ] 更新或新立 `docs/HANDOVER_finetune_*.md`（訓練指令實跑勘誤、驗收數字、雙尺結論、裁決紀錄）
- [ ] 評分報表快照留檔 `json/eval_rooms/report_gtseg_ft_v*.json`（歷屆 v1~v5 全數留存，供跨版 A/B）
- [ ] 權重發佈資訊（Release tag、SHA-256）同步寫進 Readme 與 HANDOVER（現行：tag `weights-v5`、SHA-256 `b7a280d2…f4cf`）

### 新增／改動 scripts/ 腳本時——必做

- [ ] `scripts/README.md` 同步補該腳本的用途、指令範例與依賴
- [ ] **現況缺口（本次盤點發現）**：`scripts/README.md` 開頭寫「本目錄共 20 個 Python 腳本」，實際已有 25 支；`dxf2png_pieces.py`、`extract_room_crops.py`、`probe_room_classifier.py`、`rebuild_room_gt.py`、`fix_own_floor.py` 五支（v2.15 之後新增）尚未入冊——應於下次改動 scripts/ 時一併補齊

### 每次 subagent 任務完成時——必做（AI 協作層）

- [ ] 依 `.claude/rules/subagent-context.md` 將最終產出總結寫入 `.claude/context/` 對應子目錄（檔名 `{agent-type}-{YYYY-MM-DD-HHmm}-{主題}.md`），靜默執行

### 季度級（低頻，可併入大版本時順手做）

- [ ] 檢查 `docs/superpowers/` 歷史計畫是否已全數落地或作廢，過期者在檔內標註結案狀態
- [ ] 檢查 `docs/vibecoding/` 本套與現況的漂移（指標數字、模組清單、待辦定序），漂移大的文件更新版號重發
- [ ] 外部連結有效性（GitHub Release `weights-v5`、Zenodo record 2613548）與 `.gitignore` 註記的重建方式是否仍可行
- [ ] 截圖/UI 參考更新：N/A（無 UI 截圖類文件；`recognition_report.html` 由腳本重算，不需人工更新截圖）

---

## 4. README 對映現況

模板的標準 README 結構（描述/安裝/使用/API 參考/貢獻/授權）與本專案 `Readme.md` 的實際體例對照：

| 模板區段 | 本專案現況 |
| :--- | :--- |
| 描述 | **無獨立描述區**——`Readme.md` 第 1 行即最新版本章節（v2.16）。專案概述由 `docs/vibecoding/02_project_brief_and_prd.md` 承擔 |
| 安裝 | 埋在 v2.6「〇、換機交接」章節：`pip install -r requirements.txt` → torch cu126 → lmdb/scikit-image/svgpathtools/pytest → clone CubiCasa5k 並跑 `scripts/apply_cubicasa_patches.py` → `pytest tests/` 應全綠 |
| 使用方式 | 分散於各版本章節與 `scripts/README.md`：批次 `python3 floorplan2room.py`（png/ → room_chk/ + json/）、`python3 scripts/floorplan2dxf_color.py` 等 |
| API 參考 | N/A（無 REST API）；CLI 用法見 `scripts/README.md`，JSON schema 見 Readme v1.4/v1.6/v1.9 章節 |
| 貢獻 | **無 CONTRIBUTING.md**——內部團隊專案，貢獻規範由 `.claude/rules/`（分支鐵律、commit 三段體、TDD、PR 前置條件）承擔 |
| 授權 | **無 LICENSE 檔（待確認）**——但授權約束是本專案重大風險項並已入文件：CubiCasa5k repo CC BY-NC 4.0、資料集 CC BY-NC-SA 4.0，官方權重與微調 v1~v5 **全繼承禁商用**（Readme v2.15、簡報風險節）；商用部署前必須替換（去 CubiCasa 路線動機） |

**體例定位**：本專案的 `Readme.md` 實質是「版本誌＋工程日誌」而非門面型 README——每章含變更動機、實測數字、失敗歸因與下輪待辦，是團隊的主要交接載體。此體例已運轉 16 個版本（v1.0 2026/7/2 → v2.16 2026/7/25），**維持現狀，不建議改造成模板體例**；門面型內容（快速開始、專案簡介）由 `docs/vibecoding/` 本套補位。若未來開源或轉交外部團隊，再另立標準 README。

---

## 5. CHANGELOG 對映現況

**本專案沒有獨立的 CHANGELOG.md——`Readme.md` 就是 CHANGELOG**，且比 Keep a Changelog 格式承載更多內容。對照：

| Keep a Changelog 要素 | 本專案對應 |
| :--- | :--- |
| `[Unreleased]` 區段 | 無；未發佈事項寫在最新版章節的「待辦（優先序）」節 |
| 版號＋日期標題 | 有：`2026/7/25 v.2.16 變更（一句話摘要）`，反時序排列 |
| 新增/變更/修復 分類 | 不採分類制，改採「編號主題節」（一、二、三…），每節含動機→做法→實測數字→判定；破壞性變更以粗體標記（如 v2.2「json/ 的 "dxf" 欄位移除（前端請改讀 "dxf_scale"）」） |
| 語義化版本 | 部分遵循：MINOR 每輪迭代遞增（v2.6→v2.16），無 PATCH 位；`.claude/rules/git-workflow.md` 要求語義化版本與 git tag——**tag 現況待確認**，若未打 tag，建議自 v2.16 起對每版 Readme 章節補打對應 tag |

**維持現狀的理由**：版本章節同時是變更記錄、實驗報告與交接文件，拆成標準 CHANGELOG 會失去歸因脈絡（如 v2.16 記錄「v1~v4 全敗於牆窗門 id 失配」的翻案過程，這在三分類格式中無處安放）。**改進建議**（不強制）：Readme 已 461 行且逐版增長，超過約 800 行時可把 v2.9 以前的章節搬到 `docs/CHANGELOG_archive.md`，Readme 留最近 6~8 版＋歸檔連結。

---

## 6. 最佳實踐（本專案實證版）

1. **隨開發同步撰寫，版本事件驅動**：每個 v2.x 章節在該輪工作收尾時寫成，不事後補——16 版無斷檔即為實證。
2. **文檔也要 Review**：文件變更與程式碼同 PR 走 `.claude/rules/git-workflow.md` 流程；commit 一律含 WHY/WHAT/IMPACT。
3. **量測先於結論**：文件裡的每個判定（「未達標維持基線」「牆偵測是最大瓶頸」）都附評分腳本輸出；「三個根因全部是量出來的而非猜的」（v2.8）是本專案文檔的品質標竿。
4. **陷阱清單制**：跨版反覆咬人的問題（House 用 id 比對、尾空格、transform 未烘焙等七項）集中列在 `docs/HANDOVER_finetune_v5.md` 第三節並全數落成 `scripts/fix_own_floor.py` 自動防禦——新標注必過此腳本，文件負責解釋為什麼。
5. **交接優先**：文檔的第一讀者是「下一台機器上的下一個 session」（含 AI agent）——換機步驟寫到可照抄執行的指令級（HANDOVER 的六步 SOP），秘密（`GITHUB_TOKEN`）只寫「如何設定」絕不寫值。
6. **已知債務（本次盤點）**：
   - [ ] `scripts/README.md` 補 5 支未入冊腳本、更正腳本總數（20→25）
   - [ ] LICENSE 檔與 git tag 現況待確認，決定是否補建
   - [ ] `docs/vibecoding/` 本套為 2026-07-25 快照，指標引用 v2.16；下個大版本發佈時檢查漂移
