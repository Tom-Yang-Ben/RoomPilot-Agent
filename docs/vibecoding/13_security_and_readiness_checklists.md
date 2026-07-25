# 安全與生產準備檢查清單 - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿 | **審查人員:** 待確認（建議：專案負責人＋一位未參與實作的協作者）

> **專案性質先說清楚**：RoomPilot-Agent 是純 Python CLI 管線（平面圖 PNG → DXF／房型辨識），**無 Web 後端、無資料庫、無 REST API、無對外服務**，使用者是內部團隊（多機多分支：main/cody/bella/ben/ancai/django/kai-dev）。因此傳統 Web 安全項目多為 N/A——本清單逐項標明 N/A 理由與「本專案的對應物」，並把重心放在真正的兩大風險：**授權合規（CubiCasa CC BY-NC 禁商用）**與 **GITHUB_TOKEN 秘密管理**。
>
> 圖例：✅ 已達成 ｜ ❌ 未達成（列入行動項）｜ ⚠ 部分達成 ｜ N/A 不適用（附理由）

---

## A. 核心安全原則

- [x] ✅ **最小權限**：`floorplan2room.py` 的 `_gh_token()`（第 289 行）只在權重缺檔且直鏈失敗時才讀 token（`GITHUB_TOKEN`／`GH_TOKEN` 環境變數，其次 `git credential fill`），且僅用於單一 asset API 呼叫換取 S3 簽名鏈，不長期持有。建議部署機的 PAT 使用 fine-grained token、僅授 `contents: read`（現行 PAT 權限範圍**待確認**）。
- [x] ✅ **縱深防禦**：權重供應鏈有三層——(1) 私有 repo 需認證才能下載；(2) 下載後強制 SHA-256 校驗（`CC_WEIGHTS_SHA256`，第 265 行），不符即刪除 `.part` 暫存檔；(3) `tests/test_cc_weights_download.py` 以 7 個測試鎖住此行為。
- [x] ✅ **預設安全**：使用者以 `CC_WEIGHTS` 環境變數指定自訂權重時**不代抓**（缺檔就報錯，不默默換檔，見 `_ensure_cc_weights()` 第 341 行）；權重下載失敗時管線降級為「面積規則」而非崩潰或跳過校驗。
- [x] ✅ **攻擊面最小化**：無監聽埠、無網路服務；唯二對外連線是 GitHub Release 權重下載（HTTPS）與 pip 安裝。`subprocess.run` 全部使用 list 參數形式，**全專案無 `shell=True`**（已 grep 確認），無命令注入面。

## B. 資料安全與隱私

### 資料分類與收集

- [x] ✅ 資料已可分類：
  - **內部/機密**：`png/`、`color_png/` 考卷平面圖與 `Identify_ans/` 人工答案（客戶/內部平面圖，隨私有 repo 保護）
  - **秘密**：GITHUB_TOKEN（PAT，密碼等級）
  - **大型產物**：`model_finetuned_v5.pkl`（200MB，不進版控，走 GitHub Release `weights-v5`）
- [x] N/A **PII 收集同意**——本專案不收集任何個人資料；輸入是建築平面圖圖片。本專案對應物：平面圖本身可能屬客戶機密，比照「內部/機密」等級處理（私有 repo、不對外分享）。

### 傳輸安全

- [x] ✅ 權重下載走 HTTPS（`CC_WEIGHTS_URL` → github.com；私有 repo 情境用 `Authorization: Bearer` 向 asset API 換 S3 簽名鏈，簽名鏈本身免認證，**避免 Authorization 標頭被轉送到 S3**——`_resolve_weights_url()` 第 312-333 行的 `_NoRedirect` 設計即為此）。
- [x] N/A **TLS 憑證管理／內部傳輸加密**——無自營伺服器、無憑證可管。本專案對應物：跨機資料搬運用 `training.zip`（Drive/隨身碟）＋git push 私有 repo，兩者傳輸層均由 GitHub/Google 託管。

### 儲存安全

- [ ] ⚠ **敏感資料加密儲存**——本機 WSL2 檔案系統未加密（**待確認**各協作機是否啟用 BitLocker/LUKS）。風險有限：本機只有平面圖與權重，無憑證檔落地（token 走環境變數或 git credential helper）。
- [x] ✅ **金鑰管理**：無硬編碼秘密（已 grep `ghp_`/`github_pat_` 全案無命中）；`.gitignore` 明確排除 `.mcp.json`（含 API keys，僅允許 `.mcp.json.*.example`）。
- [x] N/A **備份加密**——無資料庫備份。本專案對應物：`Identify_ans/`、`cubicasa/room/*.npz` 進版控即異地備份；`training/` 由 `training.zip` 本機自管（`.gitignore` 註明換機流程）。

### 資料生命週期

- [x] ✅ 管線輸出（stdout、`recognition_report.html`、`json/eval_rooms/*.json`）只含幾何/評分資料，不含秘密；`_ensure_cc_weights()` 的錯誤訊息只提示「需 GITHUB_TOKEN」而不印出 token 值。
- [x] N/A **資料保留期限／安全銷毀**——無使用者資料庫。本專案對應物：`temp/`（除錯產物）與 `chk/` 為可重生工作區，已列 `.gitignore`；權重舊版（v1~v4）留存於 GitHub Release 供回滾。

## C. 應用程式安全

### 認證

- [x] N/A **密碼 hash／Session／帳戶鎖定**——CLI 工具無使用者帳號體系。本專案對應物：唯一認證行為是 GitHub PAT，管理規則見上方「金鑰管理」與 F 節行動項。

### 授權

- [x] N/A **物件級／功能級授權**——單機單使用者 CLI。本專案對應物：GitHub 私有 repo 的協作者權限即授權邊界（各機一分支、透過 main PR 匯流，見 `.claude/rules/git-workflow.md`）。

### 輸入驗證與輸出編碼

- [x] N/A **防注入／XSS／CSRF**——無資料庫、無瀏覽器互動式服務。本專案對應物與殘餘風險：
  - 輸入邊界是 **PNG 解碼（OpenCV）與 SVG 標注解析（svgpathtools）**——只處理內部信任來源的考卷圖與 CubiCasa 資料集，非不信任輸入；若未來接收外部使用者上傳圖片，需補「圖片格式/尺寸上限驗證」再評估。
  - `recognition_report.html` 為本機靜態產出報表，內容來自管線自身數據，無外部輸入注入面；House 解析陷阱（get_polygon 尾空格、Inkscape transform 未烘焙）已修（Readme v2.15、`scripts/fix_annotation_paths.py`）。

### API 安全

- [x] N/A **端點認證／速率限制／參數白名單**——無 REST API。本專案對應物：CLI 介面與環境變數契約（`CC_WEIGHTS`、`GITHUB_TOKEN`/`GH_TOKEN`），詳見 [./06_api_design_specification.md](./06_api_design_specification.md)。

### 依賴安全

- [x] ✅ **破壞版本已上界封鎖**：`requirements.txt` 同時鎖 `opencv-python>=4.10,<5` 與 `opencv-python-headless<5`（5.0 改 HoughLinesP 回傳 shape 會弄壞門偵測；headless 版會被 torch 生態拉進來蓋掉 cv2，兩個都要擋）。
- [ ] ❌ **無 lock file**：`requirements.txt` 只有範圍約束（numpy≥2、ezdxf≥1.3、lmdb≥1.4、scikit-image≥0.24、svgpathtools≥1.6），未提交 `pip freeze` 快照——多機協作（7 個分支機器）易發生「同 repo 不同依賴版本」的隱性偏差。→ 行動項 #2
- [ ] ❌ **無定期漏洞掃描**：未設 `pip audit` 例行檢查、無 Dependabot（無 `.github/` 目錄、無 CI）。→ 行動項 #3
- [x] ⚠ **torch 未列入 requirements.txt**：推論/訓練依賴 PyTorch，但因 CPU/GPU 版本因機而異（Cody 機 CPU 版、GPU 機 CUDA 版）未鎖版，屬有意為之；建議在 lock file 中分環境註記。→ 併入行動項 #2

## D. 基礎設施安全

- [x] N/A **防火牆／DDoS／容器非 root**——無部署基礎設施、無容器化生產環境（`training/CubiCasa5k/Dockerfile` 僅為上游訓練環境遺留，未用於部署）。本專案對應物：各協作機為開發機，由 WSL2/OS 層自保。
- [x] ✅ **Secrets 專用管理**：GITHUB_TOKEN 只存在於環境變數或 git credential helper，程式碼與版控中零落地（`.claude/rules/security.md` 明文禁止硬編碼秘密；本次審查 grep 驗證通過）。
- [ ] ⚠ **安全事件日誌/告警**——無集中日誌。以專案規模屬合理省略；折衷對應物：權重 SHA-256 校驗失敗會在 stdout 明確告警（「權重下載 SHA-256 校驗失敗，已捨棄」），且不會留下半成品檔案。

## E. 合規性（本專案最大風險區）

- [ ] ❌ **CubiCasa5k 授權繼承——禁止商用**，這是全專案最重要的合規事實，且是**雙重繼承**：
  1. **程式庫**：`training/CubiCasa5k/`（含推論必經的 `floortrans/` 模型定義，`scripts/infer_cubicasa.py` 載入權重時依賴它）授權為 **CC BY-NC 4.0**（`training/CubiCasa5k/LICENSE` 開頭即載明，Copyright 2019）——非商業限制及於**執行推論的程式碼路徑**，不只訓練。
  2. **權重**：官方權重 `model_best_val_loss_var.pkl` 由 CC BY-NC-SA 4.0 資料集訓練而來，微調 v1~v5（含現行預設 `model_finetuned_v5.pkl`）全部繼承**禁商用**——微調不能洗掉上游授權。
  - **結論：現行管線（含 v5 權重）僅限研究/內部評估使用；任何商用部署前，必須完成「去 CubiCasa」替換**。這正是 DINOv2 分類探針路線（`scripts/probe_room_classifier.py`，具名正確率 0.730）與「floortrans 解析自寫替換」（v2.16 待辦 #7）的動機。DINOv2 骨幹授權為 Apache-2.0（**待確認**所用權重版本的最終授權條款與資料集端限制）。→ 行動項 #1
- [ ] ❌ **repo 根目錄無 LICENSE 檔**：私有內部 repo 現階段可接受，但建議加入 NOTICE 檔明文標注「本 repo 含 CC BY-NC 衍生元件（training/CubiCasa5k、model_finetuned_*.pkl），整體暫禁商用」，防止協作者或未來接手者誤用。→ 行動項 #4
- [x] N/A **GDPR/CCPA/HIPAA**——不處理個資、醫療、加州消費者資料。本專案對應物：唯一合規軸線就是上述著作權授權。
- [x] ✅ **其餘依賴授權相容**：numpy（BSD）、opencv-python（Apache-2.0）、ezdxf（MIT）、PyTorch（BSD）、scikit-image（BSD）、svgpathtools（MIT）、lmdb（OLDAP）——均為寬鬆授權，無額外商用障礙（以套件官方宣告為準，發布前建議跑一次授權盤點複核）。

## F. 審查結論

| # | 行動項 | 對應物/證據 | 建議負責人 | 預計完成 | 狀態 | 嚴重度 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **商用前完成去 CubiCasa 替換**：DINOv2 分類器接進融合層＋floortrans 解析自寫（v2.16 待辦 #1、#7）；在此之前所有對外交付明文標注「僅限非商業評估」 | `training/CubiCasa5k/LICENSE`、`scripts/probe_room_classifier.py` | 專案負責人 | 商用部署前（硬闸） | 待辦 | CRITICAL |
| 2 | 提交依賴 lock file（`pip freeze > requirements.lock.txt`，CPU/GPU 機分檔或註記 torch 差異），納入換機 SOP | `requirements.txt` 現況僅範圍約束 | 各機分支負責人 | 2026-08-01 | 待辦 | HIGH |
| 3 | 建立 `pip audit` 例行檢查（至少每月一次或併入 eval 前置步驟），高危漏洞即時升版 | 無 CI、無 `.github/` | 待確認 | 2026-08-08 | 待辦 | MEDIUM |
| 4 | repo 根目錄加 NOTICE/LICENSE 說明檔，標注 CC BY-NC 衍生範圍與內部使用限制 | repo 根目前無 LICENSE | 專案負責人 | 2026-08-01 | 待辦 | HIGH |
| 5 | 盤點各部署機 PAT：改用 fine-grained token（僅 `contents: read`）、記錄核發日期、設定到期輪換；確認無人把 token 寫進 shell 設定檔後進了 dotfiles repo | `_gh_token()`（floorplan2room.py:289） | 各機分支負責人 | 2026-08-08 | 待辦 | MEDIUM |
| 6 | 確認各協作機磁碟加密狀態（BitLocker/LUKS），未加密者評估平面圖機密等級後決定 | B 節儲存安全 | 各機分支負責人 | 待確認 | 待辦 | LOW |
| 7 | 發布新權重版本時同步更新 `CC_WEIGHTS_SHA256` 常數並跑 `tests/test_cc_weights_download.py`（7 測試）——寫入交接文件成為固定 SOP | `floorplan2room.py:265`、`docs/HANDOVER_finetune_v5.md` | 權重發布者 | 持續 | 進行中 | MEDIUM |

**整體評估：** **內部研究/評估用途——可繼續使用**（秘密管理、權重校驗、依賴上界封鎖均已到位）；**商用部署——不可上線**，硬性前提是行動項 #1（授權替換）完成，#2/#4 亦須在對外交付前完成。

---

## G. 生產準備就緒

> 本節多數項目以「對外服務」為前提。RoomPilot-Agent 的「生產」是**內部團隊在各自機器上執行 CLI**，故對應物是評測守門 harness 與交接文件，而非監控/部署設施。

### 可觀測性

- [x] N/A **監控儀表板／SLI／中央日誌／OpenTelemetry**——無長駐服務可監控。本專案對應物（品質可觀測性）：
  - **評測守門 harness**：`scripts/eval_windows.py`、`eval_rooms_cc.py`、`eval_color_walls.py`、`eval_doors.py` 等，改動前後跑分防退化（鐵律：改 chk/dxf 邏輯前必先對 `Identify_ans/pngans/` 評分，不得退化後覆蓋）
  - **報表落地**：`json/eval_rooms/*.json`（report.json、report_own*.json、report_gtseg_ft_v5.json）＋`chk/*_chk.png` 檢核圖＋`recognition_report.html`
  - **現況基準（2026-07-25，v2.16）**：灰牆 F1 0.99、灰窗 96%/96%、彩牆 87.7/94.9、彩窗 P62/R38（最低）、切割 72.6%、own 具名命中 0.788
- [x] ✅ **關鍵故障告警**（CLI 語意）：權重校驗失敗、下載無管道、語意快取缺失皆有明確 stdout 警告與降級路徑（退回面積規則），不靜默吞錯。

### 可靠性

- [x] N/A **`/health` 端點／優雅停機／故障轉移**——無服務行程。本專案對應物：CLI 以例外中止＋`subprocess.run(check=True)` 讓子程序失敗立即浮出；權重下載用 `.part` 暫存＋`os.replace` 原子換名，中斷不會留下損壞的權重檔。
- [x] ✅ **外部呼叫有超時**：權重 URL 探測 HEAD 15 秒、asset API 30 秒、git credential 15 秒（`_resolve_weights_url()`／`_gh_token()`）；無自動重試（失敗即降級，符合 CLI 情境）。
- [x] ⚠ **備份與恢復**：程式碼與 GT 靠 git 多機分散；`training/`（含資料集與訓練產物）僅 `training.zip` 本機自管——單點在持有 zip 的機器。**待確認**是否已有 Drive 副本。

### 效能與擴展

- [x] N/A **負載測試／水平擴展**——批次 CLI 無並發流量。本專案對應物（容量事實）：CubiCasa 推論 CPU 約 1 分/張（`ensure_cc_masks()` 註記）；訓練必須換 GPU 機（RTX 3060 / GTX 1650，Cody 機 WSL2 無 GPU）；語意快取 `cubicasa/room/*.npz`（137 檔）避免重複推論。

### 可維護性

- [x] ✅ **Runbook 對應物**：`Readme.md`（管線總覽與版本沿革至 v2.16）＋`docs/HANDOVER_finetune_v5.md`（GPU 機即刻執行步驟＋人工審批 SOP）＋`scripts/README.md`。
- [ ] ❌ **CI/CD 流水線**：無（無 `.github/workflows`）；測試（`tests/` 6 檔）靠各機手動 `pytest`。以專案規模屬可接受債務，若行動項 #3 落地可一併掛最小 CI（pytest＋pip audit）。
- [x] ✅ **配置集中管理**：`config.ini`（灰階管線，凍結）＋`config_color.ini`（彩色管線）＋環境變數契約（`CC_WEIGHTS` 等），無散落硬編碼配置。
- [x] N/A **Feature Flag**——無漸進發布需求。本專案對應物：`CC_WEIGHTS` 環境變數即權重 A/B 驗收開關（换權重不改碼）；灰階管線整檔凍結（`scripts/floorplan2dxf.py` 不再修改）是最強的變更隔離。

---

### 相關文件

- 開發流程與分支鐵律：`.claude/rules/development-workflow.md`、`.claude/rules/git-workflow.md`
- 安全規範原文：`.claude/rules/security.md`
- CLI/環境變數契約：[./06_api_design_specification.md](./06_api_design_specification.md)
- 專案結構：[./08_project_structure_guide.md](./08_project_structure_guide.md)
