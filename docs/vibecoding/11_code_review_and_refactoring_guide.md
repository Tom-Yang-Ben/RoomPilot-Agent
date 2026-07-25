# RoomPilot-Agent 程式碼審查與重構指南

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

> 本文件把通用模板（`VibeCoding_Workflow_Templates/11_code_review_and_refactoring_guide.md`）實例化為 RoomPilot-Agent 的實際審查與重構規範。本專案是**研究型純 Python CLI 管線**（平面圖 PNG → DXF 向量化＋房型辨識），沒有 Web 前端、資料庫或 REST API；審查的核心不是「介面契約」，而是「**評測指標不退化**」與「**CubiCasa House 解析器相容性不被破壞**」。既有規範一律引用 `.claude/rules/`，本文件不另發明流程。

---

## 1. 審查前檢查（前置條件 = eval 守門通過）

通用模板的「可編譯、測試通過」在本專案具體化為以下清單，**全數通過才進入人工審查**：

- [ ] **分支正確**：`git branch --show-current` 不在 `main` 上（`.claude/rules/development-workflow.md` 鐵律：先開分支再動程式碼；本專案分支即機器——cody/bella/ben/ancai/django/kai-dev 各機一分支，經 main PR 匯流）
- [ ] **凍結清單未被觸碰**（見 §2）
- [ ] **eval 守門通過**：任何影響 `training/chk/`、`dxf_scale/` 輸出的邏輯改動，改動**前**必先跑對應 eval 腳本對 `Identify_ans/pngans/` 建立基線，改動**後**分數不得退化才可覆蓋輸出（見 §3 的腳本對照表）
- [ ] **pytest 通過**：`tests/` 現有 6 檔（`conftest.py`、`test_cc_weights_download.py`、`test_eval_rooms_cc.py`、`test_eval_rooms_own.py`、`test_annotation_drafts.py`、`test_symbol_match.py`）；覆蓋率目標 80%（`.claude/rules/testing.md`），現況以評測守門補足單元測試缺口，實際覆蓋率「待確認」
- [ ] **標注/訓練資料改動**：新增或修改 `Identify_ans/` 下的 model.svg 標注，必先過 `scripts/fix_own_floor.py`（House 相容陷阱防禦，見 §4）並完成人工驗收
- [ ] **無硬編碼秘密**：特別是 `GITHUB_TOKEN`（權重 Release 下載用的 PAT，密碼等級秘密，只走環境變數；`.claude/rules/security.md`）
- [ ] **文檔已更新**：版本級改動在 `Readme.md` 留決策紀錄（現行 v2.16，等同輕量 ADR）；腳本增刪同步 `scripts/README.md`
- [ ] **已完成自我審查**：`git diff main...HEAD` 全篇讀過，無殘留 debug print、註解掉的程式碼

## 2. 凍結清單（審查時見到即打回）

| 檔案 | 狀態 | 理由 | 例外 |
| :--- | :--- | :--- | :--- |
| `scripts/floorplan2dxf.py`（約 1400 行，灰階管線） | **已凍結，不再修改** | 灰牆 F1 0.99、灰窗 96%/96% 已達標；歷史上 density-based 窗偵測重寫曾造成大量誤報而回退，教訓是對高分模組保守 | 使用者明確指示解凍 |
| `Identify_ans/own_eval/`（12 題房型保留評分集） | **永不進訓練** | 評分集衛生鐵律；混入訓練即失去泛化度量 | 無 |
| CubiCasa5k val/test 樣本 | 不得用於建模板庫或微調 | 同上（`scripts/extract_symbol_lib.py` 只走 train.txt 的原因） | 無 |

現行開發主力是 `scripts/floorplan2dxf_color.py`（彩色管線）——審查彩色相關 PR 時，若 diff 波及 `floorplan2dxf.py`，一律要求拆出或移除。

## 3. 審查重點

### 3.1 評測指標（本專案的第一審查維度，模板所無）

審查者對照下表確認 PR 描述附有**改動前後**的守門數字；退化即打回，不接受「肉眼看起來沒差」：

| 改動範圍 | 必跑守門腳本 | 基線（2026-07-25，v2.16） |
| :--- | :--- | :--- |
| 灰階窗偵測（chk/dxf 輸出） | `python3 scripts/eval_windows.py`（對 `Identify_ans/pngans/gray/`） | 灰窗 96%/96% |
| 彩色牆體 | `python3 scripts/eval_color_walls.py [--vis]` | 彩牆 P 87.7 / R 94.9（IoU 83.8） |
| 彩色窗 | 同管線 chk 比對＋`eval_windows.py` 對 `pngans/color/` | **彩窗 P62/R38（全系統最低，改動最歡迎、退化最不允許）** |
| 門過濾 | `python3 scripts/eval_doors.py` | 過濾率 100%（目標 ≥ 95%） |
| 門位融合 | `python scripts/eval_door_match.py` | fused P 0.576 / R 0.868 |
| 房間切割/房型命名 | `python scripts/eval_rooms_cc.py [--gt-seg]` → `json/eval_rooms/*.json` | 切割命中 72.6%（端對端 76.4%、IoU 0.875）；own 尺具名命中 0.788、macro-F1 0.473 |
| DL 遮罩本身 | `python3 scripts/eval_cc_masks.py` | 依 `cubicasa/` 快取版本 |
| CV vs CC 對決 | `python scripts/score_compare.py` | 21 張 pngans 人工答案 |

評分報表 JSON（`json/eval_rooms/report*.json`）**進版控留痕**，讓審查者可以 diff 數字而非只信文字描述。

### 3.2 程式碼品質（對應 `.claude/rules/coding-style.md`）

- **可讀性**：函式 < 50 行、檔案 < 800 行、巢狀 ≤ 4 層。注意 `floorplan2dxf_color.py` 約 1900 行已超上限——新增功能優先抽到 `scripts/` 獨立模組（如 `door_match.py`、`symbol_match.py` 的既有先例），不再往主檔堆
- **不可變性**：numpy 陣列避免就地修改共享輸入（`mask[...] = 0` 前先 `copy()`）；遮罩快取（`cubicasa/room/*_mask.npz`）讀出後視為唯讀
- **無魔法數字**：管線參數進 `config.ini` / `config_color.ini`，不硬編碼在程式裡（例：牆段配對 gap、covered 門檻是彩窗召回的調參對象，必須可設定）
- **命名**：動詞-名詞函式名（`detect_walls`、`_ensure_cc_weights`）；避免 `any` 等含糊型別（Python 對應：避免無註記的 dict 巢狀傳遞）
- **錯誤處理**：絕不靜默吞錯；標注工具遇不支援情況（rotate/skew transform、貝茲 q/c/a 指令）應**報錯擋下**而非猜測修改——`fix_annotation_paths.py` 的「上層群組帶 transform 只能報錯」是標準範例

### 3.3 架構與設計

- **關注點分離**：灰階/彩色管線輸出目錄完全隔離（`training/chk/gray/` vs `training/chk/color/`、`dxf_scale/gray/` vs `dxf_scale/color/`、`json/gray|arch/` vs `json/color|color_arch/`）——審查時確認新程式碼沒有跨目錄互寫
- **只借模型定義不借 loader**：對 CubiCasa5k 上游程式碼（CC BY-NC，禁商用）的依賴面越小越好；`infer_cubicasa.py` 只 import `floortrans` 的模型定義並以 `weights_only=True` 安全載入 checkpoint，是既定邊界。任何 PR **擴大** floortrans 依賴面都要說明理由（長期待辦第 7 項是自寫替換）
- **上游改動走補丁**：`training/CubiCasa5k/` 不進版控，對其修改一律寫進 `scripts/apply_cubicasa_patches.py`（冪等、可重複執行、PATCHES 清單目前 12 條補丁條目，docstring 歸納為 5 類，含 WashRoom），禁止手改 clone 目錄
- **SOLID / 設計模式**：本專案的實際對應是「eval 腳本共用同一套指標定義」（`eval_cc_masks.py` 重用 `eval_color_walls.py` 指標）與「工具函式跨腳本 import」（`fix_own_floor.py` import `fix_annotation_paths.py` 的 `parse_transform`/`mat_mul`）——審查時抓複製貼上的重複實作
- **API 設計**：N/A（無 REST API）。本專案的對應物是 **CLI 介面與環境變數契約**：腳本的位置參數/旗標須與 `scripts/README.md` 文件一致；`GITHUB_TOKEN` 是唯一的環境變數契約（部署機設好即全自動下載 `weights-v5` 權重＋SHA-256 校驗）

### 3.4 效能與安全

- **效能**：Cody 機（WSL2）**無 GPU**、torch 為 CPU 版——審查涉及推論的改動時，確認沒有假設 CUDA 存在（`torch.cuda.is_available()` 分支必備）；訓練程式碼須記得 B 機 4GB 卡陷阱（WSL 鎖頁記憶體與 GPU 位址空間共用，dataloader 需關 `pin_memory`，已進補丁）
- **依賴鎖版**：`opencv-python>=4.10,<5`（5.0 對 HoughLinesP 回傳 shape 是破壞性變更）、`numpy>=2`；審查 `requirements.txt` 改動時逐條確認鎖版理由未被移除
- **安全**：權重下載必附 SHA-256 校驗（`floorplan2room.py` 的 `_ensure_cc_weights`，v5 權重 `b7a280d2…f4cf`）；`torch.load` 一律 `weights_only=True`；token 不落 log
- **授權（本專案的安全等級議題）**：CubiCasa5k 官方權重與微調 v1~v5 全繼承 **CC BY-NC 禁商用**——任何把權重或 floortrans 衍生碼帶向「商用部署」方向的 PR，審查時直接標 CRITICAL 要求先解決授權（去 CubiCasa 路線：DINOv2 探針 0.730）

## 4. House 相容陷阱檢查（標注/訓練資料 PR 專屬清單）

commit `82e36e7` 稱「五大陷阱防禦」，`docs/HANDOVER_finetune_v5.md` §三 已擴充為 7 項。凡 PR 涉及 `Identify_ans/**/model.svg` 或標注工具鏈，審查者逐項核對（防禦均已內建於 `scripts/fix_own_floor.py`，故實務檢查是「**這批標注過了 fix_own_floor 沒有**」）：

1. **【最重大】House 用 `id` 而非 class 比對 Wall/Railing/Window/Door**（house.py:394/404/419/461）——Inkscape 複製元素必改 id，手畫牆窗門九成對訓練隱形（實證：floor09 牆像素 132 → 修復後 10031；全資料集 id 失配 264 處）
2. **get_polygon 尾空格陷阱**：House 解析 points 固定 `split(' ')[:-1]`，自產 polygon 若無尾隨空格會被砍掉最後一個頂點、遮罩剩半。emitter 已修＋110 處補救＋防回歸測試；所有寫 points 的程式碼必須輸出尾空格（見 `fix_annotation_paths.py` 內註記）
3. **transform 未烘焙**：Inkscape 縮放/位移存成 `transform="matrix(...)"`，House 完全忽略 → 座標錯位。必須把 matrix/translate/scale 烘焙進座標點後移除屬性；rotate/skew 與上層群組帶 transform 不支援自動烘焙，**報錯不動檔案**
4. **path/rect 非 polygon**：House 只認 `<polygon>` 子節點，Inkscape 存檔常把 polygon 變 path/rect——須轉回 polygon
5. **複製群組掉 class**：無 class 群組 House 直接跳過；依文字標籤/填色最近鄰補回
6. **替換元素須複製全部非幾何屬性**：只複製 style 會讓屬性式配色變黑塊
7. **Space 群組空殼會讓 House 直接 crash**；另貝茲曲線指令（q/c/a）需人工處理，腳本擋下報「需人工」

**標注 PR 的人工審批 SOP**（HANDOVER §二，已驗證有效）：一張一張來、不批次 → 腳本自動修復（先備份）→ AI 檢視 House 視角渲染圖自我把關（房型 vs 家具矛盾、房間數比對）→ 回報疑點清單（只提問題不擅改語意）→ 使用者裁決 → 使用者 Inkscape 開檔驗收說 OK 才進下一張。裁決鐵律：使用者的英文 class 為主；class 與填色衝突時填色通常是真實意圖（列證據交裁決）；統一色表見 HANDOVER §二（Bedroom #4a90d9 … Undefined #d9d9d9，與 `fix_own_floor.py` 的 `SPACE_FILL` 同步）。

## 5. 重構時機

| 訊號 | 本專案的實際案例 |
| :--- | :--- |
| Code smells 累積 | `floorplan2dxf_color.py` 約 1900 行超過 800 行上限，新偵測邏輯應抽獨立模組 |
| 新增功能變困難 | DINOv2 裁切分類器要接進 `floorplan2room.py`（663 行）融合層時，若投票融合邏輯難插拔，先重構融合介面再接（含 office/stair 10 類對齊） |
| 技術債＝授權債 | floortrans 解析自寫替換（待辦第 7 項）：程式碼授權 CC BY-NC，是計畫性重構而非隨手改 |
| 重複實作 | 多支 eval 腳本若各自複製指標計算，抽共用模組 |

**不重構的時機**：凍結清單（§2）；以及「指標在門檻邊緣」的模組——例如彩窗召回 38% 的當下，優先調參（牆段配對 gap、covered 門檻的線寬適配）拿到基線改善，而非同時重構＋調參讓 eval 數字無法歸因。**一次 PR 只做一件事**（`.claude/rules/git-workflow.md`）：重構 commit 與行為變更 commit 分開，讓 eval 差異可獨立歸因。

## 6. 重構策略

| 策略 | 適用場景（本專案語境） |
| :--- | :--- |
| Extract Method | 主管線內超過 50 行的偵測步驟（窗符號比對、牆段配對）抽成可單測函式 |
| Extract Variable | config 門檻值運算式命名化（如 covered 比例判斷），讓調參點一眼可見 |
| Move Method | 主檔中可獨立的比對邏輯移到 `scripts/` 模組（先例：`door_match.py`、`symbol_match.py`、`door_propose.py`） |
| Introduce Parameter Object | 偵測函式參數過多時，改傳 config 區段物件而非 8 個裸參數 |
| Replace Conditional with Polymorphism | N/A——本專案是程序式影像管線，房型分支用查表（如 `fix_own_floor.py` 的 `ALIAS`/`SPACE_FILL` 字典）已足夠，引入類別階層是過度設計 |

每一步重構後跑對應 eval（§3.1 表）確認數字位元級不動（純重構的定義），再進下一步。死碼清理可用 `refactor-clean` skill，逐步驗證。

## 7. PR 模板（整合 `.claude/rules/git-workflow.md`）

通用模板的簡易 PR 格式在本專案**以 `.claude/rules/git-workflow.md` 的四區段結構為準**，並加入評測守門區段：

標題：`<type>(<scope>): <subject>`（< 70 字元；type ∈ feat/fix/refactor/docs/test/chore/perf/ci）

```markdown
## Background
[為什麼做這個 PR — 問題、動機、關聯待辦（如「彩窗召回 38% 是全系統最低」）]

## Changes
[核心決策和取捨，不是 file list — 選了方案 A 而非 B 的原因]

## Impact
[受影響管線/目錄（gray 或 color、chk/dxf/json 哪些子目錄）；
 破壞性變更（config 參數改名、權重版本切換）明確標記；
 是否觸碰凍結清單（必須為否）]

## Test Plan（含評測守門）
- [ ] pytest 全綠（tests/ 6 檔）
- [ ] 對應 eval 腳本改動前後分數（貼上前後數字，如「彩窗 P62/R38 → P65/R44」）
- [ ] json/eval_rooms/ 報表已更新進版控（如適用）
- [ ] 標注改動：已過 fix_own_floor.py＋人工驗收（如適用，附渲染圖）
- [ ] chk/ 檢核圖抽查（列出看過的樓層）
```

Commit message 遵循 WHY/WHAT/IMPACT 三段式 body（同 rules 檔）；一個 commit 做一件事、可獨立 revert。PR 超過 400 行 diff 或 10+ 檔案考慮拆分。

## 8. 品質關卡

### 合併前

- [ ] eval 守門數字不退化（§3.1；這是本專案的「自動化檢查」，目前**無 CI，靠本機執行＋報表進版控**，CI 化為「待確認」的改善項）
- [ ] pytest 通過
- [ ] 至少一位同儕審核：多機多分支協作下，由**非提交機器的成員**在自己分支環境拉下來跑 eval 覆核；純文檔 PR 可自審
- [ ] 安全審查（如適用）：涉及權重下載、token、`torch.load` 的改動，載入 sunnydata-security skill 過 `.claude/rules/security.md` 清單
- [ ] 授權審查（如適用）：涉及 CubiCasa5k 衍生物（權重、floortrans 程式碼、資料集）的改動確認未擴大禁商用污染面
- [ ] 效能審查（如適用）：訓練/推論改動確認 CPU-only 機可跑、4GB 卡機不 OOM

### 合併後

- [ ] 部署 = 各機分支同步：其他機器（bella/ben/ancai/django/kai）rebase main 後重跑各自關心的 eval，確認跨機一致（權重缺檔會自動下載＋SHA-256 校驗）
- [ ] 監控 = 報表比對：`recognition_report.html` 與 `json/eval_rooms/*.json` 數字與 PR 宣稱一致；`Readme.md` 版本紀錄已補（v2.x 遞增）
- [ ] 遠端分支已刪（squash/merge 策略見 `.claude/rules/git-workflow.md` 的場景表）

---

## 相關文件

- `.claude/rules/git-workflow.md` — commit/PR/分支完整規範（本文件 §7 的上游）
- `.claude/rules/development-workflow.md` — 先開分支鐵律
- `.claude/rules/coding-style.md`、`.claude/rules/testing.md`、`.claude/rules/security.md`
- `docs/HANDOVER_finetune_v5.md` — House 陷阱完整清單＋標注審批 SOP
- `scripts/README.md` — 各 eval 腳本用法與守門定位
- `./01_workflow_manual.md` — 整體開發流程；`./13_security_and_readiness_checklists.md` — 安全清單細節
