# RoomPilot-Agent Claude Code Output Styles 建議

> **版本**: v1.0
> **更新**: 2026-07-25
> **狀態**: 草稿
> **模板來源**: `VibeCoding_Workflow_Templates/output_style.md`
> **本專案定位**: 純 Python CLI 的 CV/DL 平面圖向量化與房型辨識管線——無 Web 後端、無資料庫、無 REST API、無前端框架。原模板的 Web 三層架構樣式在此改寫為「管線階段 / 評測守門 / 標注資料契約」情境。

一句話結論：**把「需求→設計→行為→單元」用可切換的 Claude Code Output Styles 固化成標準作業：SDD 定管線邊界（對映 [05 架構文件](./05_architecture_and_design_document.md)），BDD 用 eval 場景描述行為（對映 [03 BDD 指南](./03_behavior_driven_development_guide.md)），TDD 以 pytest＋eval 守門驅動正確性（對映 [07 模組規格與測試](./07_module_specification_and_tests.md)）。**

---

# 系統化總覽（教科書式）

## 0. 為何用 Output Styles 來落地流程

Claude Code 的 **Output Styles** 允許用 `/output-style <name>` 一鍵切換「產物格式與觀點」，等同把「團隊最佳實踐」寫成模板檔持續重用。本專案**已建置** `.claude/output-styles/`（專案層，共 15 個樣式檔＋README），切換紀錄存於 `.claude/settings.json`（若有本機覆寫則在 `settings.local.json`，該檔目前不存在）。此機制是**修改系統提示**而非一般提示文，還能與 `.claude/agents/`、`.claude/hooks/` 串起自動化流程。

本專案的「一定要做」已用規則與 harness 固化：

- **評測鐵律**（[MEMORY](../../.claude/rules/) 與專案慣例）：改 chk/dxf 邏輯前必先跑 `scripts/eval_windows.py` 對 `Identify_ans/pngans/` 評分，**不得退化後覆蓋**。
- **先開分支鐵律**：`.claude/rules/development-workflow.md`——任何改碼前先 `git branch --show-current`。
- **TDD＋80% 覆蓋率**：`.claude/rules/testing.md`。
- **凍結約束**：`scripts/floorplan2dxf.py`（灰階管線）已凍結不再修改，只動 `scripts/floorplan2dxf_color.py`。

> 開發「聖經」對應（本專案版）：
>
> * **SDD** 依 IEEE Std 1016 精神組織設計描述 → 本專案落地為 [05_architecture_and_design_document.md](./05_architecture_and_design_document.md)（C4 Container 級九大模組分解）。
> * **DDD 聚合/不變量** → 本專案改為「**管線階段契約**」：每個階段（牆偵測→窗/門→DXF→切割→命名）的輸入/輸出格式與不變量（正交線、公分單位、統一標注色表）。
> * **TDD**（Red→Green→Refactor）→ pytest（`tests/` 現有 6 檔）＋ **eval 守門雙層防線**。
> * **BDD/Gherkin** → 以「考卷（png/、color_png/）→ 指標門檻」寫可執行的 eval 場景。
> * **前端元件測試** → **N/A**（無前端框架）；對應物是 `recognition_report.html` 報表頁與 `chk/*_chk.png` 檢核圖的人工目視驗收。

---

## 1. 角色 × 用途 × 對應樣式（總覽表）

既有 `.claude/output-styles/` 15 個樣式中，通用型（01/02/03/06/07/08/14）直接可用；Web 專屬型（04-ddd、05-api、09-database、10-backend-python、11-frontend、12-integration）對本專案語境錯位，建議依下表新增/改寫為 CV/DL 專屬樣式：

| 角色/層面 | 主要目的 | 推薦 Output Style 名稱 | 產物重點 | 既有樣式對應 |
| :--- | :--- | :--- | :--- | :--- |
| 系統架構（管線全景） | 輸出設計說明（SDD） | `sdd-pipeline-1016` | C4 九模組、資料流（PNG→DXF→房型）、品質屬性（召回/精準/IoU）、ADR | 03-architecture-design-doc（可直用） |
| 管線階段邊界 | 定義階段契約與不變量 | `pipeline-stage-contract` | 階段輸入/輸出、不變量（正交線、公分單位）、快取格式（`*_mask.npz`） | 改寫 04-ddd-aggregate-spec |
| CLI/設定契約 | 穩定對外介面 | `cli-config-contract` | argparse 參數、config.ini 鍵值、環境變數（GITHUB_TOKEN）、輸出目錄佈局 | 改寫 05-api-contract-spec（REST→CLI） |
| BDD 規格 | 行為驅動與評測對齊 | `bdd-eval-scenario` | Given 考卷/When 跑管線/Then 指標門檻；反例（誤報窗） | 02-bdd-scenario-spec（微調） |
| TDD（函式級） | 單元可靠性＋防退化 | `tdd-pytest-evalgate` | pytest 紅綠重構 ＋ eval 前後跑分對比 | 06-tdd-unit-spec（加 eval 守門） |
| 前端元件 | — | **N/A**（無前端框架） | 對應物：`recognition_report.html`＋`chk/` 目視驗收，見 §2.8 | 11-frontend-component-bdd 不適用 |
| 跨機訓練交付 | 無 GPU 機↔GPU 機交接 | `training-handoff-contract` | `training/finetune_data.zip` 打包清單、權重 Release＋SHA-256、交接 SOP | 改寫 12-integration-contract-suite |
| 標注資料契約/演進 | GT 治理 | `annotation-data-contract` | 統一色表、`Identify_ans/` 目錄規範、own_eval 永不進訓練、VLM 盲標＋人工把關 | 改寫 13-data-contract-evolution |
| 稽核/Review | 守門與拉齊 | `reviewer-eval-guard` | 走查清單＋指標退化檢查＋授權（CC BY-NC）警戒 | 07-code-review-checklist（加 eval 項） |
| CI/品質柵欄 | 自動強制規範 | `ci-eval-gates` | pytest 全綠、eval 指標不退化、opencv<5 鎖版 | 14-ci-quality-gates（改指標門檻） |

> 放置方式：每個樣式存一檔（`.md`），檔名即樣式名，存於本專案 `.claude/output-styles/`，以 `/output-style <樣式名>` 切換。既有檔案的維護說明見 `.claude/output-styles/README.md`。

---

# 2. 可直接複製的 Output Style 模板（YAML Front-Matter + 指示）

> **使用法**：把下列每一段**整段**另存為一個檔案，例如 `.claude/output-styles/sdd-pipeline-1016.md`，然後在專案內輸入 `/output-style sdd-pipeline-1016` 切換。

### 2.1 SDD（IEEE 1016 精神）— 管線設計說明

```md
---
name: sdd-pipeline-1016
description: "RoomPilot-Agent 管線設計說明（SDD）；輸出可審查、可追蹤的 CV/DL 管線設計描述。"
---
# 指令（你是 CV 管線設計顧問）
以 IEEE 1016 的資訊結構輸出 SDD；所有主張需可用 eval 指標驗證。優先清楚描述「設計決策與取捨」（例：正交線重建 vs 描輪廓）。

## 交付結構
1. **背景與目標**：問題定義（PNG→DXF＋房型）、範圍、非目標（無 Web/DB/API）
2. **利害關係人與品質屬性**：召回/精準/F1/IoU 優先於延遲；離線批次可接受分鐘級
3. **脈絡與視圖**：
   - C4：Context→Container（九大模組，見 docs/vibecoding/05_architecture_and_design_document.md）→Component
   - 資料流：png|color_png → dxf_scale/ ＋ chk/ ＋ json/ → recognition_report.html
   - 快取視圖：cubicasa/room/*_mask.npz（CNN 語意快取，權重換版須全量重算）
4. **介面契約**：CLI 參數、config.ini/config_color.ini 鍵值、GITHUB_TOKEN 環境變數
5. **運維與彈性**：權重缺檔自動下載（_ensure_cc_weights，SHA-256 校驗）；無 GPU 機降級 CPU 推論
6. **風險與假設**：CubiCasa5k CC BY-NC 禁商用、opencv 5.0 破壞性變更、彩窗召回 38% 缺口
7. **架構決策紀錄（ADR）**：決策→選項→取捨→依據→狀態（例：v5 權重接管預設的裁決依據）
8. **驗證計畫**：scripts/eval_*.py 七支守門腳本＋pytest tests/ 六檔

## 蘇格拉底檢核
- 若召回與精準衝突（如彩窗 P62/R38），哪個優先？裁決證據是什麼？
- 若 GitHub Release 權重下載失效，管線如何退化仍可出 DXF？
- 「灰階管線凍結」假設若被推翻，需要哪些 eval 保護才能安全解凍？
```

（本專案 SDD 的完整實例即 [05_architecture_and_design_document.md](./05_architecture_and_design_document.md)。）

---

### 2.2 管線階段契約 — 取代 DDD 聚合（本專案無領域聚合/倉儲）

> 原模板的 `ddd-backend-aggregate`（聚合根、倉儲介面、領域事件）預設有業務領域模型與持久層，本專案為影像處理管線，**改寫**為「階段契約」：把「聚合不變量」換成「階段輸出不變量」，把「領域事件」換成「中間產物檔案」。

```md
---
name: pipeline-stage-contract
description: "RoomPilot-Agent 管線階段契約；每個處理階段的輸入/輸出格式、不變量與快取策略。"
---
# 指令（你是管線模組設計教練）
輸出以「階段」為單位的設計產物；明確每階段的輸入/輸出 shape 與 dtype、不變量，避免隱式耦合。

## 交付結構
1. **階段索引**：牆偵測→窗/門符號→DXF 輸出→房間切割（flood fill＋門洞封口）→房型命名（CNN 語意投票融合）
2. **語彙表**：牆段、正交線、門洞封口、語意投票、own 尺/CubiCasa 尺（兩套評分基準）
3. **每階段契約**：
   - 輸入/輸出：檔案格式（PNG/npz/DXF/json）、numpy shape 與 dtype、座標系（像素 vs 公分）
   - **不變量**（需可測試）：H 線兩端同 y、V 線兩端同 x；DXF 一律公分單位；標注統一色表（如 terrace→Outdoor #c77dbb）
   - 快取：cubicasa/room/<名>_mask.npz——權重版本變更即失效，須全量重算
4. **融合層**：floorplan2room.py 的多證據投票（CNN 語意＋幾何規則；禁面積規則）
5. **防腐層**：CubiCasa5k floortrans 只借模型定義不碰舊 loader；checkpoint 以 weights_only=True 安全載入
6. **測試策略**：以不變量為核心的 pytest 單元測試＋eval 腳本端對端驗證

## 蘇格拉底檢核
- 此階段的**唯一輸出契約**是什麼？下游若拿到違約輸出會怎麼壞？
- 快取失效條件是否完整列舉？權重換版、色表變更、GT 重建各觸發什麼？
- 哪個規則是**不變量**（如公分單位）而非現行慣例（如目錄名）？如何破壞性驗證？
```

---

### 2.3 資料資產綱要 — 取代資料庫綱要（本專案無資料庫）

> 原模板的 `database-physical-schema`（ERD/DDL/索引）**N/A**：本專案無任何資料庫。對應物是**檔案系統上的資料資產佈局與 GT 格式**，改寫如下。

```md
---
name: data-asset-schema
description: "RoomPilot-Agent 資料資產綱要；目錄佈局、GT 格式、快取與版控邊界。"
---
# 指令（你是資料資產管理員）
輸出檔案系統層級的資料設計。優先考量 GT 完整性、灰/彩隔離與版控邊界（GitHub 100MB 硬限）。

## 交付結構
1. **目錄佈局圖**：png/（灰階考卷）、color_png/（彩色 29 題）、Identify_ans/{pngans,own_dataset,own_eval}、cubicasa/room/、json/eval_rooms/、dxf_scale/、chk/
2. **GT 格式定義**：pngans/ 牆窗像素 GT（gray 38＋color 29）；own_dataset/ 25 題（訓練＋門位 GT）；own_eval/ 12 題（保留評分集，**永不進訓練**）
3. **隔離策略**：彩色管線輸出一律進 color 子目錄（training/chk/color/、dxf_scale/color/、json/color/），與灰階完全隔離不互相覆蓋
4. **版控邊界**：Identify_ans/ 進版控；model_finetuned_v5.pkl（200MB）不進版控，走 GitHub Release tag weights-v5＋SHA-256 校驗
5. **演進計畫**：own_dataset 擴充 50~100 題（VLM 盲標＋人工把關）；彩色管線門位/切割/命名 GT 建集

## 蘇格拉底檢核
- own_eval 若被混入訓練，哪個指標會失真？如何機制性防止？
- 快取 npz 與權重版本如何對齊？誰負責觸發全量重算？
- 新增一種 GT（如彩色門位）時，哪些 eval 腳本與標注工具要同步改？
```

---

### 2.4 管線實作 — Python/OpenCV/PyTorch 程式碼生成（取代 FastAPI 後端骨架）

> 原模板的 `backend-impl-python`（FastAPI＋SQLAlchemy＋Clean Architecture 目錄）**N/A**：無 Web 層與 ORM。改寫為本專案實際的腳本式管線實作樣式。

```md
---
name: cv-pipeline-impl-python
description: "基於階段契約生成 RoomPilot-Agent 管線實作；numpy/OpenCV/ezdxf/PyTorch，config 驅動。"
---
# 指令（你是資深 CV 管線工程師）
讀取 pipeline-stage-contract 的產出，生成符合本專案慣例的 Python 實作。鐵律：只改 scripts/floorplan2dxf_color.py 與 floorplan2room.py 系統；scripts/floorplan2dxf.py 已凍結禁改。

## 實作慣例
1. **相依鎖版**：numpy>=2、opencv-python>=4.10,<5（HoughLinesP shape 破壞性變更）、ezdxf>=1.3
2. **參數externalize**：可調參數全進 config_color.ini，不硬編碼；門檻命名清楚（如牆段配對 gap、covered 門檻）
3. **輸出隔離**：一律寫 color 子目錄；chk 檢核圖與 DXF 同步產出
4. **權重載入**：走 floorplan2room.py 的 _ensure_cc_weights 模式——缺檔自動從 GitHub Release 下載＋SHA-256 校驗，GITHUB_TOKEN 由環境變數提供，絕不硬編碼
5. **CPU 相容**：本機（Cody，WSL2）無 GPU，torch 推論必須 CPU 可跑
6. **錯誤處理**：不靜默吞錯；缺 GT/缺權重給出可操作的錯誤訊息
7. **檔案規模**：函式 <50 行、檔案上限 800 行（.claude/rules/coding-style.md）

## 生成內容
- 階段函式（純函式優先，輸入輸出皆 numpy/明確檔案路徑）
- config 鍵值與預設值表
- 對應 pytest 測試骨架（tests/）與 eval 驗證指令

## 蘇格拉底檢核
- 新參數是否進了 config？換一張線寬不同的考卷需要改碼還是改參數？
- 這段改動會影響哪些 eval 指標？改前基準分數存了嗎？
- 是否誤觸凍結檔或灰階輸出目錄？
```

---

### 2.5 CLI/設定契約 — 取代 API First（本專案無 REST API）

> 原模板的 `api-first-contract`（OpenAPI/版本策略）**N/A**：無 HTTP 介面。本專案的「對外契約」是 **CLI 呼叫慣例＋config 檔＋環境變數＋輸出目錄佈局**，這正是多機多分支協作（main/cody/bella/ben/ancai/django/kai-dev）間的穩定介面。

```md
---
name: cli-config-contract
description: "RoomPilot-Agent CLI 與設定契約；命令列介面、config 鍵值、環境變數與輸出佈局的相容性準則。"
---
# 指令（你是 CLI 契約設計師）
以契約為中心輸出：命令列用法、config 鍵值語意、環境變數、輸出檔案佈局；標示相容性規則。

## 交付結構
- **CLI 用法**：如 `python3 scripts/floorplan2dxf_color.py`（批次 color_png/ → dxf_scale/color/）、`python scripts/infer_cubicasa.py <weights.pkl> <out_dir> <img...>`
- **config 契約**：config.ini（凍結）/config_color.ini 鍵值表——語意、單位、預設值、調參影響的指標
- **環境變數**：GITHUB_TOKEN（PAT，密碼等級秘密，僅環境變數提供，勿進版控）
- **輸出佈局契約**：dxf_scale/{gray,color}/、chk/、json/eval_rooms/report*.json——下游腳本與報表依賴此佈局，變更視同破壞性變更
- **相容性準則**：新增 config 鍵須有預設值（向後相容）；改輸出檔名/目錄須同步改所有 eval 腳本並在 commit IMPACT 段標記
- **錯誤語意**：缺權重（自動下載 vs 明確失敗）、缺 GT、opencv 版本不符的行為定義

## 蘇格拉底檢核
- 另一台機器（另一分支）拉了這個變更後，不改任何本機設定能直接跑嗎？
- 哪些鍵值改動會使既有 chk/dxf 基準失效？
```

---

### 2.6 BDD — 可執行規格（Gherkin，eval 場景版）

```md
---
name: bdd-eval-scenario
description: "RoomPilot-Agent Gherkin 評測場景；Given 考卷/When 跑管線/Then 指標門檻。"
---
# 指令（你是 BDD 引導者）
產出 Feature 檔與對應的 eval 驗證指令；所有句子以管線業務語彙撰寫（考卷、牆段、召回），避免綁定實作細節。

## 交付結構（範例）
**Feature:** 彩色平面圖窗戶偵測
**Scenario Outline:** 彩色考卷窗召回不退化
  Given Identify_ans/pngans/ 內的彩色牆窗像素 GT（29 題）
  When 執行 python3 scripts/floorplan2dxf_color.py 後跑 scripts/eval_windows.py
  Then 窗召回不得低於現行基準 38%，精準不得低於 62%
  And chk/ 檢核圖與 DXF 同步更新且不覆蓋灰階輸出
**Examples:**（逐題列出高風險考卷，如粗線寬/細線寬代表題）

## 步驟骨架
- `Given …`（指定考卷集與 GT 目錄）
- `When …`（管線指令＋eval 指令，可直接複製執行）
- `Then …`（明確數字門檻＋輸出檔案存在性）

## 蘇格拉底檢核
- 門檻數字的出處是哪份報表（json/eval_rooms/report*.json）？
- 是否覆蓋反例場景（把家具格線誤判為窗）？window 偵測歷史教訓：激進改寫曾因誤報過多回退，須保守。
```

（本專案 BDD 完整指南見 [03_behavior_driven_development_guide.md](./03_behavior_driven_development_guide.md)。）

---

### 2.7 TDD — 函式級單元（Red→Green→Refactor ＋ eval 守門）

```md
---
name: tdd-pytest-evalgate
description: "RoomPilot-Agent TDD；pytest 紅綠重構 ＋ eval 前後跑分雙層守門。"
---
# 指令（你是 TDD 導師）
輸出【基準跑分】→【測試清單】→【最小紅】→【最小綠】→【重構】→【eval 對比】的循環；每步最小化修改面積。

## 本專案雙層守門
1. **單元層（pytest）**：tests/ 現有 6 檔（conftest.py、test_cc_weights_download.py、test_eval_rooms_cc.py、test_eval_rooms_own.py、test_symbol_match.py、test_annotation_drafts.py）；新函式先寫失敗測試再實作；覆蓋率目標 80%（.claude/rules/testing.md）
2. **端對端層（eval）**：改動 chk/dxf 邏輯前，先跑 scripts/eval_windows.py 對 Identify_ans/pngans/ 記錄基準；改完重跑，任何指標退化即回退或說明取捨——**不得退化後覆蓋**

## 交付結構
1. **基準快照**：改動前的指標數字與報表路徑
2. **測試清單**：正常例、邊界例（空遮罩、單像素牆、非正交線）、錯誤例（壞 PNG、缺權重）
3. **紅→綠→重構**：每步保持 pytest 全綠
4. **eval 對比表**：改動前後逐指標對比（P/R/F1/IoU），標記退化項

## 函式契約
- 簽名：明確 numpy shape/dtype 與座標系（像素 or 公分）
- 前置/後置條件：如「輸出線段皆正交」「遮罩與原圖同尺寸」
- 隨機性控制：涉及訓練/抽樣時固定 seed

## 蘇格拉底檢核
- 這個測試是否唯一驅動了設計？有沒有更小的失敗步驟？
- eval 退化了 0.5 個百分點——是雜訊還是真退化？用哪幾張考卷驗證？
- 重構是否改善設計而未更動任何指標？
```

---

### 2.8 前端元件 — N/A（無前端框架）

> **N/A 理由**：本專案無 React/Vue/Storybook，無任何前端建置鏈。既有 `.claude/output-styles/11-frontend-component-bdd.md` 對本專案不適用，保留供未來前端整合參考即可。
>
> **本專案對應物**：
> 1. `recognition_report.html`——房型辨識 HTML 報表頁（由管線生成的靜態頁），是唯一「面向人眼的 UI」。
> 2. `chk/*_chk.png` 檢核圖——每題的目視驗收介面。
> 3. `scripts/` 標注工具鏈的 review.html 流程——標注人工把關頁。
>
> 若要為報表頁建立樣式，建議最小化：定義「報表必含欄位（逐題指標、縮圖連結、與基準的差異標紅）」與「產生後人工驗收 checklist」，而非元件互動測試。未來若真的加前端（如 Web 上傳介面），屆時再啟用 11 號樣式並補 [12_frontend_architecture_specification.md](./12_frontend_architecture_specification.md) 的對應章節。

---

### 2.9 跨機訓練交付 — 取代跨系統整合（本專案無服務間整合）

> 原模板的 `integration-contract-suite`（REST/事件/合約測試）**N/A**：無跨服務通訊。本專案真正的「跨系統邊界」是**無 GPU 開發機 ↔ GPU 訓練機**的人工交接，以及**權重產物經 GitHub Release 的發佈契約**，改寫如下。

```md
---
name: training-handoff-contract
description: "RoomPilot-Agent 跨機訓練交付契約；打包、訓練、權重發佈與回程驗收。"
---
# 指令（你是訓練交付設計者）
產出跨機交接的完整契約；每個交付物列出產生指令、校驗方式與回程驗收步驟。

## 交付結構
- **背景約束**：本機（Cody，WSL2）無 NVIDIA 驅動、torch CPU 版；訓練須帶包去 GPU 機（RTX 3060 / GTX 1650）
- **去程包**：scripts/pack_finetune_data.py 產出 training/finetune_data.zip；內容清單（own_dataset 標注、色表、patch）須逐項列出
- **GPU 機步驟**：training/CubiCasa5k/（train.py、eval.py）＋ scripts/apply_cubicasa_patches.py；步驟 SOP 見 docs/HANDOVER_finetune_v5.md
- **回程交付**：微調權重（如 model_finetuned_v5.pkl，200MB）→ GitHub Release（tag weights-v5）＋ SHA-256（b7a280d2…f4cf）；私有 repo 下載需 GITHUB_TOKEN
- **回程驗收**：cubicasa/room/ 語意快取全量重算 → scripts/eval_rooms_cc.py 跑 own 尺與 CubiCasa 尺雙基準 → 與前版權重逐指標對比（v5 為例：own 具名命中 0.788 vs 門檻裁決紀錄）→ 人工審批後才接管預設
- **失效注入**：權重下載中斷、SHA-256 不符、快取未重算——各自的預期行為

## 蘇格拉底檢核
- 交接包缺了哪個檔會讓 GPU 機白跑一輪？清單有沒有機器可驗的 manifest？
- 新權重退化時的回退路徑是什麼？舊 Release tag 是否保留？
```

---

### 2.10 標注資料契約與演進

```md
---
name: annotation-data-contract
description: "RoomPilot-Agent 標注 GT 治理；色表契約、演進策略、盲標把關與漂移偵測。"
---
# 指令（你是標注資料架構師）
輸出 GT 契約與演進規則；提供人工把關流程與新舊 GT 的對比驗證指南。

## 交付結構
- **色表契約**：own 標注統一色表（如 terrace→Outdoor #c77dbb）；任何新增房型類別須先過色表，並確認是否進評分（office/stair 目前未進評分與訓練，10 類對齊為待辦）
- **演進策略**：GT 修復走 scripts/fix_own_floor.py（逐層人工驗收）；路徑修復走 scripts/fix_annotation_paths.py（get_polygon 尾空格、Inkscape transform 未烘焙等 House 解析陷阱，已修，見 Readme v2.15）；標籤同步走 scripts/sync_room_labels.py；GT 重建走 scripts/rebuild_room_gt.py
- **盲標把關**：VLM 盲標草稿（scripts/make_annotation_drafts.py）→ review.html 逐張人工把關 → 才可入 own_dataset；own_eval 12 題永不進訓練
- **漂移偵測**：GT 變更後必重跑 eval 基準並保存新舊報表（json/eval_rooms/report_own*.json）對比；「新 GT 重評後再議」是 DINOv2 融合決策的前置條件
- **稽核**：每批標注記錄來源（盲標/人工）、驗收人與日期

## 蘇格拉底檢核
- 這批新 GT 改變了哪些題的分數分母？跨版本指標還可比嗎？
- 色表新增類別後，訓練集、評分腳本、floorplan2room 融合層三處是否同步？
```

---

### 2.11 架構/程式碼審查守門

```md
---
name: reviewer-eval-guard
description: "RoomPilot-Agent 審查清單；聚焦指標退化、凍結邊界、授權與秘密。"
---
# 指令（你是嚴格但友善的 Reviewer）
逐條產出結論/風險/修正建議，鏈接到 SDD/階段契約/eval 報表證據。

## 走查清單（本專案版）
- **指標退化**：附上改動前後 eval 對比了嗎（eval_windows/eval_rooms_cc/eval_color_walls/eval_doors/eval_door_match/eval_cc_masks/score_compare）？
- **凍結邊界**：是否誤改 scripts/floorplan2dxf.py？彩色輸出是否誤寫灰階目錄？
- **授權**：是否引入 CubiCasa5k（CC BY-NC 4.0）衍生物到商用路徑？floortrans 程式碼授權亦 CC BY-NC
- **秘密**：GITHUB_TOKEN 是否只走環境變數？（.claude/rules/security.md 檢查表）
- **相依**：是否維持 opencv-python>=4.10,<5 鎖版？新依賴是否活躍維護？
- **測試**：pytest 全綠？新邏輯有對應單元測試？覆蓋率 80%？
- **commit 品質**：WHY/WHAT/IMPACT 三段齊全（.claude/rules/git-workflow.md）？一 commit 一件事？
- **不可變性/風格**：函式 <50 行、無硬編碼門檻、錯誤不靜默（.claude/rules/coding-style.md）
```

---

### 2.12 CI/品質柵欄（搭配 Hooks）

```md
---
name: ci-eval-gates
description: "RoomPilot-Agent 品質門檻；pytest 全綠＋eval 指標不退化＋鎖版檢查。"
---
# 指令（你是 DevEx 工程師）
輸出檢查階段與條件；對未達標情境提供自動化修正建議/指令。

## 交付結構
- **Stages**：Lint/Type → pytest（tests/ 全綠）→ eval 基準對比 → 人工目視 chk/ 抽查
- **門檻（現行基準，2026-07-25 v2.16，退化即擋）**：
  - 灰牆 F1 0.99、灰窗 P 96%/R 96%（38 題灰階集）
  - 彩牆 87.7/94.9（IoU 83.8）；彩窗 P 62/R 38（現行最低水位，只許升不許降）
  - 切割命中 72.6%（53/73，配對 IoU 0.829）
  - 房型命名 own 尺具名命中 0.788（52/66）、具名 macro-F1 0.473
  - 門過濾 100%、門位 fused P 0.576/R 0.868
- **鎖版檢查**：opencv-python <5；requirements 與 lock 一致
- **Artifacts**：json/eval_rooms/report*.json 報表快照、chk/ 檢核圖
- **Hook 範例**：PostToolUse Write 後跑格式化；阻擋對 scripts/floorplan2dxf.py 的任何寫入（凍結保護）；阻擋含 token 樣式字串的 commit
```

（本專案 hooks 位於 `.claude/hooks/`，設定見 `.claude/settings.json`；CI 平台化細節待確認——目前守門以本機腳本＋人工審批為主。）

---

## 3. 管線各層面的「風格建議」

* **設計與實作流程**：建議採 `sdd-pipeline-1016` → `pipeline-stage-contract` → `data-asset-schema` → `cv-pipeline-impl-python` → `cli-config-contract` 的順序，由宏觀到微觀，確立管線邊界、階段契約、資料資產、實作骨架與跨機介面。
* **行為規格**：以 `bdd-eval-scenario` 為核心，用考卷＋指標門檻寫可執行場景——每個待辦（如彩窗召回 38% 破口）先寫 Scenario 再動手調參。
* **函式開發**：以 `tdd-pytest-evalgate` 實踐紅綠重構＋雙層守門，確保階段不變量與端對端指標同時受保護。
* **訓練與資料演進**：使用 `training-handoff-contract` 與 `annotation-data-contract` 守護跨機交接與 GT 相容性。
* **品質保證**：透過 `reviewer-eval-guard` 進行人工審查（對映 [11 審查指南](./11_code_review_and_refactoring_guide.md)），並用 `ci-eval-gates` 將指標門檻固化。
* **Claude Code 操作**：`/output-style` 切換樣式；樣式檔放本專案 `.claude/output-styles/`（已進版控供多機共享）；用 `.claude/hooks/` 建立格式化/凍結檔保護/秘密掃描。

---

## 4. 最小可行落地（你可以這樣開始）

1. 在 `.claude/output-styles/` 新增五個 CV/DL 專屬樣式：`sdd-pipeline-1016.md`、`pipeline-stage-contract.md`、`bdd-eval-scenario.md`、`tdd-pytest-evalgate.md`、`ci-eval-gates.md`（§2 整段可直接複製；與既有 15 檔並存，Web 專屬的 04/05/09/10/11/12 號保留不用）。
2. `/output-style sdd-pipeline-1016`——把現有九模組管線「說清楚」，比對 [05 架構文件](./05_architecture_and_design_document.md) 補缺。
3. `/output-style bdd-eval-scenario`——為 v2.16 待辦第一優先「彩窗召回 38%」寫 Scenario（Given color_png 29 題 GT / When 調牆段配對 gap 與 covered 門檻 / Then R>38% 且 P 不低於 62%）。
4. `/output-style tdd-pytest-evalgate`——挑 `scripts/floorplan2dxf_color.py` 的窗偵測函式，先跑 `scripts/eval_windows.py` 存基準，再紅綠重構。
5. `/output-style reviewer-eval-guard`——提 PR 前自審，附 eval 前後對比表。
6. 加上 hooks：阻擋對凍結檔 `scripts/floorplan2dxf.py` 的寫入；commit 前掃描 GITHUB_TOKEN 樣式字串。

---

## 5. 參考來源（精選）

* Claude Code 官方：**Output Styles** 說明與檔案位置、`/output-style` 指令（docs.claude.com/en/docs/claude-code/output-styles）。
* Claude Code 官方：**Hooks** 指南（docs.claude.com/en/docs/claude-code/hooks-guide）。
* IEEE Std 1016：SDD 結構與資訊內容。
* TDD：Fowler《Test Driven Development》（Red-Green-Refactor）。
* BDD/Gherkin：Cucumber 官方文件。
* 本專案內部：`.claude/output-styles/README.md`（既有 15 樣式使用指南）、`.claude/rules/`（開發流程/測試/安全/風格等 8 檔規則）、`scripts/README.md`（腳本分組說明；README 自稱 20 支、目錄實有 25 支 .py，待更新）、`docs/HANDOVER_finetune_v5.md`（跨機訓練 SOP）、`Readme.md`（v2.15/v2.16 變更紀錄）。

---

# 心法內化（像 5 歲小孩也懂）

把管線想成三件事：**先畫地圖（SDD 說清楚 PNG 怎麼變成 DXF 和房名）**，**再定每一站的交貨規矩（階段契約：線要正交、單位要公分）**，**最後每次改東西都拿同一把尺量（pytest＋eval 跑分，分數掉了就不准過）**；每次動工前，**換一種帽子（Output Style）**，就會說出正確的話、做對的事。

# 口訣記憶（3 點）

1. **先邊界，後行為，再函式**（SDD/階段契約 → eval 場景 → pytest 紅綠）
2. **樣式即流程**（`/output-style` 固化觀點，hooks 保護凍結檔與秘密）
3. **分數說話**（改前存基準、改後對報表——不得退化後覆蓋）
