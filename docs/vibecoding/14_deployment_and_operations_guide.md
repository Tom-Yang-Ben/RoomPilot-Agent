# 部署與運維指南 - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

> 本專案是純 Python CLI 管線（平面圖 PNG → DXF 向量圖＋房型辨識），**無 Web 服務、無資料庫、無 K8s**。
> 「部署」在本專案的實際意義是：**多台開發/推論機器的安裝與同步**（clone → pip install → 權重自動下載），
> 以及 **GPU 機訓練換機流程**。「運維監控」的實際意義是：**eval 守門報表**與 **recognition_report.html** 辨識成功率儀表板。
> 傳統伺服器運維段落一律標 N/A 並給出本專案對應物。

---

## 1. 部署架構

### 1.1 實際拓撲：分支即機器

```
GitHub (private repo: Tom-Yang-Ben/RoomPilot-Agent)
   │  ├─ 程式碼與標注（Identify_ans/）走 git
   │  └─ 權重走 Release（tag: weights-v5，200MB 超過 GitHub 100MB 硬限）
   │
   ├── Cody 機（WSL2，無 GPU，torch CPU 版）── 分支 cody ── 主開發＋標注＋評測
   ├── Machine A（RTX 3060）──────────────────── GPU 訓練機（v4/v5 實跑，約 33 分/輪）
   ├── Machine B（GTX 1650 4GB）───────────────── 備用 GPU 訓練機（有 WSL pin_memory OOM 陷阱）
   └── 其他協作機 ── 分支 bella / ben / ancai / django / kai-dev ── 透過 PR 匯流 main
```

- **沒有 Development → Staging → Production 環境鏈**。每台機器同時是開發與執行環境；「上線」＝merge 進 main。
- 大型檔案搬運：`training/finetune_data.zip`（416MB 訓練資料）與 `training.zip`（本機自管總目錄備份）**不進版控**，用 Google Drive / 隨身碟換機。
- `training/` 目錄整體 gitignore、各機自管；`cubicasa/room/` 語意快取（npz，137 檔）進版控，是雙機同步推論結果的依據。

### 1.2 基礎設施元件

| 元件 | 本專案狀態 | 對應物 |
| :--- | :--- | :--- |
| 負載均衡 | **N/A**——無網路服務、無流量 | 無；批次 CLI 逐張處理 |
| 應用伺服器 | **N/A**——無常駐程序 | 各機器本地 Python 3.10+ venv 直接執行 CLI |
| 資料庫叢集 | **N/A**——無資料庫 | 檔案系統即資料層：`Identify_ans/`（GT）、`json/`（報表）、`dxf_scale/`（輸出） |
| 快取層 | N/A（無 Redis 類服務） | `cubicasa/room/*_mask.npz` CNN 語意快取（進版控，避免每機重推論，CPU 約 1 分/張） |
| CDN | **N/A**——無靜態資源交付 | GitHub Release 承擔權重分發（`weights-v5`，經 asset API 換 S3 簽名鏈下載） |
| 監控 | N/A（無 Prometheus/Grafana） | `scripts/eval_*.py` 守門報表＋根目錄 `recognition_report.html`（詳見第 5 節） |

### 1.3 執行環境需求

| 項目 | 要求 | 依據 |
| :--- | :--- | :--- |
| Python | 3.10+ | 專案簡報 |
| numpy | ≥ 2.0 | requirements.txt |
| opencv-python / opencv-python-headless | ≥ 4.10，**< 5**（兩者都要鎖） | 5.0 把 HoughLinesP 回傳 shape (N,1,4) 改成 (N,4)，門偵測會掛；torch 生態會拉 headless 版蓋掉 cv2，同樣要擋 |
| ezdxf | ≥ 1.3 | requirements.txt |
| lmdb / scikit-image / svgpathtools | ≥1.4 / ≥0.24 / ≥1.6 | CubiCasa 標注解析與訓練資料打包依賴 |
| PyTorch | 推論機 CPU 版即可；訓練機須 GPU 版 | Cody 機為 CPU 版；訓練走 GPU 機 |
| 磁碟 | 權重 200MB＋CubiCasa5k 資料集 5.6GB（僅訓練機需要，可從 Zenodo record 2613548 重下） | HANDOVER_finetune_v5.md |

---

## 2. CI/CD 流水線

**N/A（無 GitHub Actions / Jenkins 等自動化流水線）**——本專案的「建置→測試→部署」由人工執行的守門流程取代，鐵律寫在 `.claude/rules/`：

| 傳統階段 | 本專案對應流程 |
| :--- | :--- |
| **建置** | 無編譯產物。`git pull` 即最新版；權重缺檔時由 `floorplan2room.py` 的 `_ensure_cc_weights()` 自動下載＋SHA-256 校驗 |
| **測試** | `pytest`（tests/ 6 檔：conftest、test_cc_weights_download、test_eval_rooms_cc、test_eval_rooms_own、test_annotation_drafts、test_symbol_match）；上次遷移驗證 13/13 全綠 |
| **品質守門** | **評測鐵律：改 chk/dxf 邏輯前必先跑 `scripts/eval_windows.py` 對 `Identify_ans/pngans/` 評分，不得退化後覆蓋**（現行基準：灰窗 96%/96%（38 題灰階集，v2.16）） |
| **部署** | 功能分支 → PR → main；各機 `git pull` 即完成「部署」。commit 遵循 WHY/WHAT/IMPACT（`.claude/rules/git-workflow.md`） |

守門腳本清單（`scripts/`，任何管線改動前後跑分對比）：

| 腳本 | 守什麼 | 現行基準（2026-07-25，v2.16） |
| :--- | :--- | :--- |
| `eval_windows.py` | 灰階窗偵測（chk 覆蓋前必跑） | 96% / 96%（38 題灰階集） |
| `eval_color_walls.py` | 彩色牆體像素級 P/R/IoU | 87.7 / 94.9 / IoU 83.8（無融合基準） |
| `eval_doors.py` | 門不被誤判成窗（過濾率） | 100%（目標 ≥ 95%） |
| `eval_door_match.py` | 門位候選重評分 A/B | fused P 0.576 / R 0.868 |
| `eval_rooms_cc.py` | 房型切割＋命名（`--own-eval [--gt-seg]` 為現行主尺） | 切割 72.6%（53/73）、具名命中 0.788（52/66） |
| `eval_cc_masks.py` | DL 原始 wall mask 實力 | 灰 F1 0.89（供融合決策） |
| `score_compare.py` | 前後跑分對比 | — |

---

## 3. 部署檢查清單

### 3.1 新機安裝流程（推論機，clone 即可用）

```bash
# 1. clone（private repo，需 PAT）
git clone https://github.com/Tom-Yang-Ben/RoomPilot-Agent.git
cd RoomPilot-Agent

# 2. venv ＋依賴
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu   # 推論機 CPU 版即可

# 3. 設定權重下載 token（repo 目前 private；轉 public 後此步可省）
export GITHUB_TOKEN=<clone 私有 repo 用的同一顆 PAT>

# 4. 首跑——權重缺檔會自動從 Release 下載（約 200MB，僅首次）＋ SHA-256 校驗
python floorplan2room.py            # 批次 png/ → training/chk/room/、json/room/
```

安裝驗收清單：

- [ ] `pytest tests/` 全綠（含 `test_cc_weights_download.py` 的 7 例下載單元測試）
- [ ] 專案根出現 `model_finetuned_v5.pkl`（SHA-256 `b7a280d2…f4cf`），或已用 Drive/隨身碟放入（放專案根即跳過下載）
- [ ] `python scripts/eval_windows.py` 跑分與基準一致（灰窗 96%/96%，38 題灰階集）
- [ ] `cv2.__version__` < 5.0（兩個 opencv 套件都確認）

### 3.2 GITHUB_TOKEN 設定要點（部署機唯一的秘密）

- `floorplan2room.py` 讀 `GITHUB_TOKEN` 或 `GH_TOKEN` 環境變數，經 GitHub asset API（asset id 489011637）換 S3 簽名鏈下載；**clone 私有 repo 用的那顆 PAT 同一顆即可**，程式其餘全自動。
- token 是**密碼等級秘密**：只放環境變數（如 `~/.bashrc` 或 secret manager），**勿寫進任何進版控的檔案**（`.claude/rules/security.md`）。
- 無 token 且無 git 憑證時，程式印出「權重下載無可用管道」並**降級運行**：跳過語意辨識、房型退回面積規則——不會 crash，但命名品質大幅下降，屬異常狀態須處理。
- `CC_WEIGHTS` 環境變數指定自訂權重時**缺檔不代抓**（缺了就該報錯而非默默換檔）。
- repo 若轉 public：零設定直鏈自動生效，token 可移除。

### 3.3 主要 CLI 入口（「部署」後實際跑什麼）

| 指令 | 功能 | 輸出 |
| :--- | :--- | :--- |
| `python floorplan2room.py [圖檔或目錄]` | 房間切割＋房型命名（自動判黑白/彩色） | `training/chk/room/` 疊圖、`json/room/<名>_room.json` |
| `python3 scripts/floorplan2dxf.py [--config 設定檔.ini]` | 灰階 PNG → DXF（**已凍結，不再修改**） | `dxf_scale/gray/`、`training/chk/gray/` |
| `python3 scripts/floorplan2dxf_color.py` | 彩色 PNG → DXF（開發主力） | `dxf_scale/color/`、`training/chk/color/` |
| `python cabinet_designer.py` | 櫃體設計入口（早期） | — |

### 3.4 變更部署前（= merge 前）檢查

- [ ] 在功能分支上（禁止 main 直接 commit——`.claude/rules/development-workflow.md`）
- [ ] `pytest` 全綠
- [ ] 相關 `eval_*.py` 前後跑分，無退化（退化不得覆蓋 chk/dxf）
- [ ] `json/eval_rooms/` 報表已重算（若動到房型層）
- [ ] commit message 含 WHY/WHAT/IMPACT
- [ ] 無硬編碼秘密（PAT 尤其）

---

## 4. 部署策略

**Blue-Green / Rolling / Canary 均 N/A**——無流量可切、無多實例可滾動。本專案真正需要策略管理的是**模型權重版本切換**：

| 場景 | 做法 | 「回滾時間」 |
| :--- | :--- | :--- |
| 權重 A/B 驗收（不動預設） | `CC_WEIGHTS=<候選.pkl> CC_CACHE_DIR=<獨立快取目錄> python scripts/eval_rooms_cc.py --gt-seg`——環境變數與基線快取正交，互不污染 | 即時（改環境變數） |
| 換預設權重（如 v4→v5） | 需過驗收門檻＋使用者裁決 → 改 `floorplan2room.py` 的 `CC_WEIGHTS` 預設值＋發新 Release tag＋`cubicasa/room/` 快取全量重算＋四份評分報表與 recognition_report.html 同步重算 | 一個 commit revert |
| 程式碼變更 | git 分支 → PR → main，各機 pull | `git revert` |

歷史案例（權重驗收制度實績）：v1~v4 四輪全部未過「具名房型 recall 不得倒退」門檻，預設權重維持基線；v5 在 own 尺首勝（macro-F1 0.215→0.473），CubiCasa 尺 0.797 未過 0.838 門檻，由**使用者裁決目標域＝own 風格後才接管預設**——換預設權重永遠是「數據＋人工裁決」雙關卡，不自動切換。

---

## 5. 監控與告警

**無即時監控系統（N/A：Prometheus/Grafana/Datadog）**——本專案是批次管線，品質監控靠**離線評測報表**，於每次改動前後與定期全批次重跑時產生。

### 5.1 關鍵指標（現行儀表，2026-07-25，v2.16）

| 層級 | 指標 | 現值 | 判讀 |
| :--- | :--- | :--- | :--- |
| 灰階牆/窗 | 牆 F1 / 窗 P/R | 0.99 / 96%/96% | 健康（凍結管線） |
| 彩色牆 | P/R/IoU | 87.7 / 94.9 / 83.8 | 健康（無融合基準） |
| **彩色窗** | P/R | **62 / 38** | **全系統最低，最大真實破口** |
| 門 | 過濾率 / 門位 fused P/R | 100% / 0.576/0.868 | 精準率待改善（118 候選 50 誤報） |
| 房間切割 | 命中率 / 配對 IoU | 72.6%（53/73）/ 0.829（端對端 76.4% / 0.875） | 漏接集中 floor60、floor55 類開放式黏房 |
| 房型命名 | own 尺具名命中 / macro-F1 | 0.788（52/66）/ 0.473 | v5 權重；基線 0.215 |
| 分類探針 | DINOv2 具名正確率 | 0.730 | 備選路線（去 CubiCasa 授權） |

### 5.2 報表產出物（＝儀表板）

| 產出物 | 位置 | 內容 |
| :--- | :--- | :--- |
| **recognition_report.html** | 專案根 | 四層級（牆窗/門/切割/命名）辨識成功率總覽，支援深色模式；每次權重或管線大改後全批次重算 |
| 房型評分 JSON | `json/eval_rooms/`（report.json、report_own.json、report_own_gtseg.json、report_gtseg_ft_v5.json…） | `eval_rooms_cc.py` 輸出，A/B 對比依據 |
| 品質檢核圖 | `training/chk/gray/`、`training/chk/color/`、`training/chk/room/` | 逐張疊圖（紅牆、綠窗、房型色塊），人眼抽查用 |
| 差異視覺化 | `eval_color_walls.py --vis` | 白=TP、紅=FP、綠=FN 像素圖 |

### 5.3 告警規則

**N/A（無 on-call / Slack 告警）**——對應物是**評測鐵律的硬性門檻**，違反即停止合入：

| 「告警」 | 條件 | 處置 |
| :--- | :--- | :--- |
| 評分退化 | 任一 eval 指標低於改動前 | 禁止覆蓋 chk/dxf，回頭修或放棄改動 |
| 權重驗收未過 | 具名房型 recall 倒退（歷屆門檻） | 預設權重不切換（v1~v4 皆如此處理） |
| 權重校驗失敗 | 下載 SHA-256 不符 | 程式自動捨棄暫存檔並告警 |
| 權重下載無管道 | 無 token 且無憑證 | 程式印警告、降級為面積規則——視為部署設定錯誤，補設 GITHUB_TOKEN |

---

## 6. 回滾流程

### 自動回滾觸發

**N/A（無自動回滾機制）**——對應防線是：eval 守門在「覆蓋輸出之前」擋下退化（事前防範，而非事後回滾），加上權重下載的 SHA-256 校驗失敗自動捨棄。

### 手動回滾步驟

| 對象 | 步驟 |
| :--- | :--- |
| 程式碼 | `git log` 找最後穩定 commit → `git revert <sha>`（或 PR revert）→ 重跑相關 `eval_*.py` 確認數字回到基準 |
| 預設權重 | 改 `floorplan2room.py` CC_WEIGHTS 預設回前版 → 以對應權重重算 `cubicasa/room/` 語意快取 → 重算 `json/eval_rooms/` 四報表與 recognition_report.html。注意：舊版官方基線權重在 `training/model_best_val_loss_var.pkl`（本機自管，不進版控） |
| 語意快取 | 快取進版控，`git checkout <sha> -- cubicasa/room/` 即可回檔；換權重驗收時一律用 `CC_CACHE_DIR` 指到獨立目錄，**不動基線快取**，天然免回滾 |
| 標注（GT） | `Identify_ans/` 進版控，git 即還原點；`fix_own_floor.py` 修檔前強制 `--backup-dir` 備份 |

---

## 7. Runbook：GPU 機微調訓練（濃縮自 [docs/HANDOVER_finetune_v5.md](../HANDOVER_finetune_v5.md)，完整陷阱清單以該文件為準）

### 服務概覽

- **用途**：CubiCasa5k hourglass CNN（44 類）微調，產出 `model_finetuned_vN.pkl` 供 `floorplan2room.py` 房型命名。
- **依賴**：`training/CubiCasa5k/` 程式庫（不進版控，clone 後須打補丁）、官方權重 `training/model_best_val_loss_var.pkl`、`training/finetune_data.zip`（416MB，Drive/隨身碟帶機）。
- **機器**：Machine A（RTX 3060，v5 約 33 分鐘）或 Machine B（GTX 1650 4GB，見陷阱）。

### 訓練步驟（v5 實跑驗證版）

```bash
# 1. 同步程式碼；資料 zip 放到 training/
git pull origin cody

# 2. 依賴（v4 跑過的機器大多已備）
pip install lmdb scikit-image svgpathtools

# 3. CubiCasa5k 補丁（必跑；冪等，fresh clone 同一條）
python scripts/apply_cubicasa_patches.py --dir training/CubiCasa5k
#    不跑的後果：WashRoom class 退回 Undefined（floor01/06/08/47 中招）

# 4. 解壓——zip 內部已帶 training/finetune_data/ 前綴，須在專案根解壓
python -m zipfile -e training/finetune_data.zip .
#    勿再加 -d finetune_data（會雙層巢套）；無 unzip 時 python -m zipfile 是現成替代

# 5. 訓練（RTX 3060 約 33 分鐘）
cd training/CubiCasa5k
python train.py --data-path ../finetune_data/ \
  --weights ../model_best_val_loss_var.pkl --new-hyperparams true \
  --n-epoch 20 --batch-size 8 --l-rate 5e-5 --l-rate-var 5e-5 \
  --log-path runs_cubi/ft_vN/
# 產出 checkpoint 更名 training/model_finetuned_vN.pkl 帶回

# 6. 驗收（回 Cody 機或就地；環境變數正交，不動基線快取）
CC_WEIGHTS=training/model_finetuned_vN.pkl CC_CACHE_DIR=training/cubicasa_room_ftN \
  python scripts/eval_rooms_cc.py --gt-seg
```

### 陷阱（實跑血淚，逐條防禦）

1. **`--weights` vs `--furukawa-weights`**：官方 `model_best_val_loss_var.pkl` 是 44 類權重，必須用 `--weights` 載入；`--furukawa-weights` 是 51 類原始 Furukawa 權重入口，誤用即 size mismatch（conv4_/upsample 44 vs 51）。
2. **`--new-hyperparams` 必加**：否則沿用 checkpoint 內舊 optimizer 狀態、蓋掉 lr 5e-5。
3. **Machine B（4GB 卡）**：WSL 鎖頁記憶體與 GPU 位址空間共用，VRAM 吃滿後 dataloader pin 執行緒 CUDA OOM——兩個 loader 都關 `pin_memory` 解，否則訓練中途陣亡。
4. **標注 id 失配是 v1~v4 全敗根因**：House 解析用 `id` 而非 class 比對 Wall/Window/Door，Inkscape 複製元素必改 id → 手畫標注對訓練隱形。新標注**必過 `scripts/fix_own_floor.py`**（已防禦全部七項陷阱，含 polygon 尾空格、transform 未烘焙、空殼 Space 群組等）。
5. **own_eval 12 題永不進訓練**（鐵律）；驗收門檻＝具名房型 recall 不得倒退，過檻後仍須使用者裁決才換預設權重。
6. CubiCasa 尺驗收需要資料集（5.6GB），已清理的機器從 Zenodo record 2613548 重下：`python -m zipfile -e cubicasa5k.zip training/CubiCasa5k/data/`。

### 監控

- 訓練中：`--log-path runs_cubi/ft_vN/` 的 tensorboardX 記錄，看 val loss（v5：6.57→1.75；v4 終點 2.19）。
- 驗收：`json/eval_rooms/` 報表對比基線（第 5 節）。

### 故障排除與升級

- 訓練/評測異常：先載入 sunnydata-debugging skill（`.claude/rules/performance.md` 規範）；標注疑義走 HANDOVER 第二節的逐張人工審批 SOP（AI 只提問題、使用者裁決語意）。
- 緊急聯絡人：內部團隊（repo owner Tom-Yang-Ben）；無 on-call 制度。

---

## 8. 授權與商用部署限制（本專案特有的部署風險）

- CubiCasa5k **repo 程式碼 CC BY-NC 4.0、資料集 CC BY-NC-SA 4.0**——官方權重與微調 v1~v5 全繼承**禁商用**。
- **商用部署前必須替換整條命名路線**：DINOv2 裁切分類探針（`scripts/extract_room_crops.py`＋`probe_room_classifier.py`，具名正確率 0.730）即為此準備；長期並須自寫替換 floortrans 解析層。
- 在此之前，任何「部署」僅限內部研發用途。

---

## 相關文件

- 訓練交接完整版：[docs/HANDOVER_finetune_v5.md](../HANDOVER_finetune_v5.md)
- 腳本逐支說明：`scripts/README.md`
- 專案結構：[./08_project_structure_guide.md](./08_project_structure_guide.md)
- 模組規格與測試：[./07_module_specification_and_tests.md](./07_module_specification_and_tests.md)
