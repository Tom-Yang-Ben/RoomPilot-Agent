# BDD 行為驅動情境指南 — RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

> 本文件保留 Gherkin 教學骨架，但所有範例均取自 RoomPilot-Agent 的真實場景：
> 灰階 PNG→DXF 轉檔、彩色窗偵測、權重缺檔自動下載＋SHA-256 校驗、eval 守門不得退化。
> 引用數字以《專案事實簡報》v2.16（2026-07-25）與原始碼實測為準。

---

## Gherkin 語法速查

| 關鍵字 | 用途 |
| :--- | :--- |
| `Feature` | 高層次功能，對應本專案的 Container（如「彩色向量化管線」） |
| `Scenario` | 具體業務場景/測試案例 |
| `Given` | 初始狀態 (Arrange)：輸入圖檔、GT 目錄、環境變數 |
| `When` | 操作 (Act)：執行 CLI 指令（本專案無 UI，操作＝跑腳本） |
| `Then` | 預期結果 (Assert)：輸出檔存在、指標不退化、錯誤訊息正確 |
| `And/But` | 連接多個步驟 |
| `Background` | 所有 Scenario 共用的前置步驟 |
| `Scenario Outline` + `Examples` | 參數化多組資料測試 |

### 本專案的 BDD 落地方式（重要前提）

本專案是**純 Python CLI 管線**，未安裝 `behave`/`pytest-bdd` 等 Gherkin 執行框架。
`.feature` 檔在本專案定位為**規格溝通文件**（人讀），實際自動化驗證由兩層承接：

1. **pytest 單元/整合測試**（`tests/`，現有 6 檔）：如 `tests/test_cc_weights_download.py`
   的 7 個測試即是本文「權重自動下載」Feature 的逐條 Scenario 對應。
2. **評測守門 harness**（`scripts/eval_*.py`）：`eval_windows.py`、`eval_rooms_cc.py`、
   `eval_color_walls.py`、`eval_doors.py` 等，對 `Identify_ans/` 人工 GT 跑分，
   承接「不得退化」類的 Then 斷言，報表落在 `json/eval_rooms/*.json`。

寫新功能時的建議流程：先用 Gherkin 把場景講清楚（給人審） → 再依
`.claude/rules/testing.md` 的 TDD 流程把每個 Scenario 翻成 pytest 測試或 eval 守門項。

---

## 範本

**檔案名稱**: `[feature_name].feature`（若要落檔，建議放 `docs/vibecoding/features/`；目前僅內嵌於本文件）

```gherkin
Feature: [功能名稱]
  # 對應 Container: [系統分解表中的容器名]
  # 對應驗證: [tests/ 測試檔 或 scripts/eval_*.py]

  Background:
    Given [共用前置條件]

  @happy-path @smoke-test
  Scenario: [正常流程描述]
    Given [前置狀態]
    When [執行 CLI 指令]
    Then [預期輸出/指標]

  @sad-path
  Scenario: [異常流程描述]
    Given [前置狀態]
    When [錯誤情境觸發]
    Then [錯誤處理結果]

  @edge-case
  Scenario Outline: [邊界情況描述]
    When [以 "<參數>" 執行]
    Then [應得到 "<結果>"]

    Examples:
      | 參數 | 結果 |
      | ...  | ...  |
```

---

## 真實範例 1：灰階 PNG→DXF 轉檔

對應 Container：**灰階向量化管線**（`scripts/floorplan2dxf.py`，約 1400 行，**已凍結不再修改**）。
現況指標：灰牆 F1 0.99、灰窗 96%/96%（P/R）。

```gherkin
Feature: 灰階平面圖 PNG 轉 DXF 向量圖
  # 對應 Container: 灰階向量化管線（scripts/floorplan2dxf.py + config.ini）
  # 對應驗證: scripts/eval_windows.py（對 Identify_ans/pngans/gray/ 評分）
  # 注意: 此管線已凍結，Scenario 僅作回歸驗收，不作為新功能開發依據

  Background:
    Given 專案根目錄下存在 png/ 灰階考卷圖檔
    And config.ini 設定檔存在且可讀

  @happy-path @smoke-test
  Scenario: 批次轉檔產出正交 DXF 與檢核圖
    Given png/ 目錄內有黑白線稿平面圖
    When 我執行 "python3 scripts/floorplan2dxf.py"
    Then dxf_scale/ 應產出對應的 .dxf 檔（公分單位，AutoCAD 可開）
    And 每條輸出線段應為純水平或純垂直（H 線兩端同 y、V 線兩端同 x）
    And training/chk/gray/ 應產出對應的 *_chk.png 品質檢核圖

  @happy-path
  Scenario: 指定替代設定檔
    Given 存在一份自訂的 ini 設定檔
    When 我執行 "python3 scripts/floorplan2dxf.py --config 別的.ini"
    Then 管線應以該設定檔的參數執行而非 config.ini

  @sad-path
  Scenario: opencv 版本越界
    Given 環境安裝了 opencv-python 5.x（HoughLinesP 回傳 shape 破壞性變更）
    When 依賴安裝階段檢查版本約束
    Then 安裝應被 "opencv-python>=4.10,<5" 約束擋下
    # 理由: 專案事實簡報「重大約束」——opencv 5.0 破壞性變更須鎖版本

  @edge-case
  Scenario: 凍結管線的回歸底線
    Given 任何人試圖修改 scripts/floorplan2dxf.py
    When 變更提交前
    Then 必須先執行 eval_windows.py 確認灰窗指標不低於 96%/96%
    But 依專案共識，此檔已凍結——新需求一律改 scripts/floorplan2dxf_color.py
```

---

## 真實範例 2：彩色窗偵測

對應 Container：**彩色向量化管線**（`scripts/floorplan2dxf_color.py` + `config_color.ini`）。
現況指標：彩牆 87.7/94.9（IoU 83.8）；**彩窗 P62/R38 是全系統最低分**，為 v2.16 待辦第 2 位。

```gherkin
Feature: 彩色平面圖窗戶偵測
  # 對應 Container: 彩色向量化管線（scripts/floorplan2dxf_color.py + config_color.ini）
  # 對應驗證: scripts/eval_windows.py（答案目錄改指 Identify_ans/pngans/color/）
  # 現況: 彩窗 Precision 62% / Recall 38%——召回 38% 是最大真實破口

  Background:
    Given color_png/ 目錄內有 29 題彩色渲染平面圖
    And Identify_ans/pngans/ 內有 color 29 張牆窗像素 GT

  @happy-path @smoke-test
  Scenario: 批次彩色轉檔
    When 我執行 "python3 scripts/floorplan2dxf_color.py"
    Then dxf_scale/color/ 應產出對應 DXF
    And training/chk/ 應產出可供 eval 抽綠框評分的檢核疊圖

  @edge-case
  Scenario: chk 疊圖與答案圖尺寸不同時仍可評分
    Given 彩色管線可能以 2 倍圖處理，chk 疊圖與 GT 尺寸不一致
    When eval_windows.py 抽取兩邊綠框
    Then 評分器應先將圖縮放到同尺寸再配對（green_boxes 的 size 參數）
    # 灰階管線兩邊同尺寸，縮放係數=1 不受影響

  @sad-path
  Scenario: 調參改善召回但精度崩盤
    Given 目前彩窗基線為 P62/R38
    When 我調整「牆段配對 gap 與 covered 門檻的線寬適配」參數後重跑評分
    Then 若 Recall 上升但 Precision 明顯下滑（誤抓暴增），該組參數不得合入
    # 理由: MEMORY 記載 density-based window rewrite 曾因大量誤報被 revert，
    #       窗偵測策略以保守為原則

  @edge-case
  Scenario Outline: 綠框配對判定標準
    When 一個預測框與一個答案框的關係為 "<關係>"
    Then 配對結果應為 "<結果>"

    Examples:
      | 關係                                   | 結果            |
      | 交集面積/較小框面積 >= 0.3             | 配對成功 (TP)   |
      | 一框中心落在另一框內                   | 配對成功 (TP)   |
      | 多個預測框共同覆蓋同一答案框           | 只計 1 個 TP    |
      | 預測框無任何答案框對應                 | 誤抓 (FP)       |
      | 答案框無任何預測框對應                 | 漏抓 (FN)       |
```

---

## 真實範例 3：權重缺檔自動下載＋SHA-256 校驗

對應 Container：**房型辨識管線**（`floorplan2room.py`，專案根，663 行）中的
`_ensure_cc_weights()`。已由 `tests/test_cc_weights_download.py` 的 7 個 pytest
測試逐條自動化——這是本專案 BDD Scenario ↔ pytest 對應最完整的示範。

```gherkin
Feature: CubiCasa 微調權重缺檔自動下載
  # 對應程式: floorplan2room.py 的 _ensure_cc_weights()
  # 對應驗證: tests/test_cc_weights_download.py（7 個測試）
  # 權重: model_finetuned_v5.pkl（約 200MB，不進版控，GitHub Release tag weights-v5）
  # SHA-256: b7a280d2d7cf2dde580a947e1ebc7b4d12e53135c05581babb3b5797a166f4cf

  Background:
    Given 預設權重檔名由環境變數 CC_WEIGHTS 決定，未設定時為 "model_finetuned_v5.pkl"

  @happy-path
  Scenario: 權重已存在則直接使用
    Given 專案根已存在 model_finetuned_v5.pkl
    When floorplan2room.py 啟動並呼叫 _ensure_cc_weights()
    Then 不應發起任何網路請求
    # 對應測試: test_existing_file_short_circuits

  @happy-path @smoke-test
  Scenario: 缺檔時自動下載並通過校驗
    Given 專案根不存在權重檔
    And 下載管道可用（repo 為 public 直鏈，或已設 GITHUB_TOKEN / GH_TOKEN）
    When _ensure_cc_weights() 執行
    Then 應從 GitHub Release weights-v5 下載至暫存檔 "model_finetuned_v5.pkl.part"
    And 下載內容的 SHA-256 應等於 b7a280d2…f4cf
    And 校驗通過後以 os.replace 原子改名為正式檔名
    # 對應測試: test_download_success

  @sad-path
  Scenario: SHA-256 校驗不符即拒收
    Given 下載內容被竄改或不完整
    When 計算出的 SHA-256 與 CC_WEIGHTS_SHA256 不一致
    Then 下載結果應被拒絕且不得產生正式權重檔
    # 對應測試: test_checksum_mismatch_rejected

  @sad-path
  Scenario: 下載中斷須清理殘檔
    Given 下載過程拋出網路錯誤
    When _ensure_cc_weights() 處理該例外
    Then .part 暫存檔應被清除，不得留下半截檔案
    # 對應測試: test_download_error_cleans_up

  @sad-path
  Scenario: 使用者自訂權重缺檔時報錯而非代抓
    Given 使用者以環境變數 CC_WEIGHTS 指定了自訂權重路徑
    And 該檔案不存在
    When _ensure_cc_weights() 執行
    Then 不應自動下載任何檔案（使用者指定的權重缺了就該報錯，而非默默換檔）
    # 對應測試: test_user_override_never_downloads

  @sad-path
  Scenario: 無任何下載管道時優雅降級
    Given repo 為私有且未設 GITHUB_TOKEN / GH_TOKEN，亦無 git 憑證
    When _ensure_cc_weights() 回傳 False
    Then 主流程應印出「⚠ 找不到 model_finetuned_v5.pkl，跳過語意辨識（房型退回面積規則）」
    And 管線其餘輸出（房間切割、門位）不受影響
    # 對應測試: test_no_channel_returns_false

  @edge-case
  Scenario: token 讀取優先序
    Given 同時設定 GITHUB_TOKEN 與 GH_TOKEN
    When 組裝 GitHub API 請求標頭
    Then 應優先採用 GITHUB_TOKEN
    # 對應測試: test_gh_token_env_priority
    # 安全: PAT 屬密碼等級秘密，依 .claude/rules/security.md 絕不進版控
```

---

## 真實範例 4：eval 守門不得退化

對應 Container：**評測守門 harness**（`scripts/eval_windows.py`、`eval_rooms_cc.py`、
`eval_color_walls.py`、`eval_doors.py`、`eval_door_match.py`、`eval_cc_masks.py`、
`score_compare.py`）。這是全專案的品質鐵律：**改 chk/dxf 邏輯前必先對
`Identify_ans/pngans/` 評分，不得退化後覆蓋。**

```gherkin
Feature: 評測守門——任何管線改動不得造成指標退化
  # 對應 Container: 評測守門 harness（scripts/eval_*.py）
  # GT 資產: Identify_ans/pngans/（gray 38 + color 29 牆窗像素 GT）、
  #          Identify_ans/own_eval/（12 題房型保留評分集，永不進訓練）
  # 報表: json/eval_rooms/*.json（report.json、report_own*.json、report_gtseg_ft_v5.json…）

  Background:
    Given 我準備修改 chk 或 dxf 的產出邏輯

  @happy-path @smoke-test
  Scenario: 改動前先建立基線分數
    When 我執行 "python3 scripts/eval_windows.py"
    Then 應以預設 GT 目錄 Identify_ans/pngans/gray 對 chk 產出評分
    And 我記下改動前的 P/R 基線（灰窗現行基線 96%/96%）

  @happy-path
  Scenario: 改動後重評且不退化才可合入
    Given 已有改動前基線分數
    When 我重跑對應的 eval 腳本並比對前後分數（可用 scripts/score_compare.py）
    Then 每項指標皆不得低於基線
    And 通過後才允許覆蓋 chk/ 與 dxf_scale/ 產出

  @sad-path
  Scenario: 指標退化即擋下合入
    Given 改動後灰窗 Recall 從 96% 掉到 90%
    When 我比對評分報表
    Then 該改動不得提交，必須回頭修正或 revert
    # 前例: density-based 窗偵測重寫因誤報過多整組 revert（MEMORY 記載）

  @edge-case
  Scenario: 房型評分集的資料隔離
    Given Identify_ans/own_eval/ 是 12 題房型保留評分集
    When 準備微調訓練資料（scripts/pack_finetune_data.py）
    Then own_eval 的任何一題都不得混入訓練集
    # 理由: 保留集一旦污染，0.788 具名命中等數字全部失效

  @edge-case
  Scenario Outline: 各管線對應的守門腳本
    When 我修改 "<管線/邏輯>"
    Then 合入前必跑 "<守門腳本>"

    Examples:
      | 管線/邏輯                     | 守門腳本                        |
      | 灰階/彩色窗偵測               | scripts/eval_windows.py         |
      | 彩色牆偵測                    | scripts/eval_color_walls.py     |
      | 房間切割與房型命名            | scripts/eval_rooms_cc.py        |
      | 門位偵測                      | scripts/eval_doors.py           |
      | 門符號比對                    | scripts/eval_door_match.py      |
      | CNN 語意快取 (cubicasa/room/) | scripts/eval_cc_masks.py        |
      | 前後分數比對                  | scripts/score_compare.py        |
```

---

## 最佳實踐

1. **一個 Scenario 只測一件事** — 如上例把「校驗不符拒收」與「中斷清殘檔」拆成兩個
   Scenario，各自對應一個 pytest 測試。
2. **使用陳述式、從結果寫** — `Then dxf_scale/ 應產出對應的 .dxf 檔`，而非
   `Then 系統會去產生 DXF`。
3. **避免實作細節，但保留可驗證的契約** — 本專案無 UI，「避免 UI 細節」轉譯為
   「避免綁死內部函式流程」：寫 `When 我執行 "python3 scripts/floorplan2dxf_color.py"`
   （CLI 契約），不寫 `When detect_walls 的第三個迴圈…`（內部實作）。
4. **從使用者角度編寫** — 本專案的「使用者」是內部團隊成員與部署機操作者；
   Scenario 應讓沒讀過原始碼的隊友（bella/ben/ancai 各分支機器的操作者）也能照做驗收。
5. **每條 Scenario 標註對應的自動化驗證** — 以註解寫明對應的 pytest 測試名或
   eval 腳本；沒有對應驗證的 Scenario 視為未完成（TDD 的 RED 階段）。
6. **數字寫進 Then 就要可查證** — 指標引用《事實簡報》v2.16 或 `json/eval_rooms/`
   報表；拿不準的寫「待確認」，不編造。

---

## N/A 段落聲明

| 模板慣用場景 | 本專案適用性 | 對應物 |
| :--- | :--- | :--- |
| Web 表單填寫類 Scenario（`When I fill in "<field>"…`） | **N/A** — 無 Web 前端、無表單 | CLI 參數與環境變數契約（`CC_WEIGHTS`、`GITHUB_TOKEN`、ini 設定檔）；報表面為 `recognition_report.html` 靜態頁 |
| 對應 PRD Epic 的 `# 對應 PRD: [Link]` | 對應 [./02_project_brief_and_prd.md](./02_project_brief_and_prd.md) 的 Epic A~C／US-001~US-006 | Feature 註解可寫 `# 對應 PRD: US-00x`，並輔以 `# 對應 Container:` |
| Cucumber/behave 自動執行 `.feature` | **N/A** — 未安裝 Gherkin runner，避免為 6 檔測試引入額外依賴 | pytest（`tests/`）＋ eval 守門 harness（`scripts/eval_*.py`）雙層承接；若日後測試規模成長可再評估 pytest-bdd |
| API 端點行為場景 | **N/A** — 無 REST API、無資料庫 | 檔案系統契約：輸入 `png/`、`color_png/`，輸出 `dxf_scale/`、`training/chk/`、`json/` |

---

## 相關文件

- 開發流程與分支鐵律：`.claude/rules/development-workflow.md`、`.claude/rules/git-workflow.md`
- TDD 與覆蓋率要求：`.claude/rules/testing.md`
- 其他 VibeCoding 文件：見 `docs/vibecoding/` 同層（如 [./07_module_specification_and_tests.md](./07_module_specification_and_tests.md)）
