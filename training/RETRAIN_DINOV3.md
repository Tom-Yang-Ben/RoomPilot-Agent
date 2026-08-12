# DINOv3 換機重訓清單

> 目的：把房型辨識管線的骨幹由 DINOv2 換成 DINOv3，於**有 GPU 的機器**重訓三顆頭並跑四量尺 A/B，供主管依增益幅度拍板（見根目錄 `DINOv3_決策簡報.pptx`）。
>
> 前置狀態（2026-08-12）：HF 權重門禁**已核准**（帳號 CodyCH）；離線探針顯示 DINOv3 特徵可分性小幅一致提升（NC 0.536→0.573、kNN 0.621→0.657），落點偏簡報「情境 B」，**真正拍板仍須重訓後的端到端四量尺**。本機 cody 無 GPU，故換機。

---

## A. 什麼靠 git、什麼要另外帶

分支 `cody-DINOv3` 已 push，**大部分東西 git 就帶過去了**；`training.zip` 只需補 git 帶不了的。

| 類別 | 內容 | 換機取得方式 |
| :--- | :--- | :--- |
| ✅ git 已涵蓋 | 全部訓練/評估腳本、tests、**答案卷 `testdata/Identify_ans`（261 檔 ~56MB）**、現有三顆頭 npz、`requirements.txt`、決策簡報 | `git clone/pull cody-DINOv3` |
| 📦 git 帶不了 ① | `training/room_crops/`（被 `.gitignore`） | 現場用 `extract_room_crops.py` **重生**，免入 zip |
| 📦 ② | **DINOv3 gated 權重** | 新機 `hf auth login` 下載（或預抓 `~/.cache/huggingface` 塞進 zip 省流量）|
| 📦 ③ | **臨時依賴**（未進 requirements）：`transformers==5.14.1`、`torchmetrics`、`termcolor`、`python-pptx`（後者僅產簡報用）| 見 B 步驟的 pip 行 |
| 📦 ④ | **GPU 版 torch** | `requirements.txt` 是 `torch==2.13.0` **CPU 版**（註明「只推論不訓練」）——換機**務必改裝對應 CUDA 的 GPU 版** |
| 🚫 絕不進 zip | HF token、任何祕密 | 新機 `hf auth login` 互動輸入；舊 token 已 revoke |

> 結論：`training.zip` 可以很薄——git 已包絕大多數，實務上只需（可選的）② HF 權重 cache。

---

## B. 換機執行步驟（GPU 機：A = RTX 3060 / B = GTX 1650）

```bash
# 0. 取碼 + 環境
git clone -b cody-DINOv3 https://github.com/Tom-Yang-Ben/RoomPilot-Agent.git
cd RoomPilot-Agent
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 換 GPU 版 torch（index-url 依機器 CUDA/驅動版本挑，例：cu124）
pip uninstall -y torch
pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cu124

# DINOv3 臨時依賴
pip install transformers==5.14.1 torchmetrics termcolor

# 1. HF 登入（新 token；隱藏輸入，勿貼進任何會進版控的檔）
hf auth login
```

### 2. ⚠ DINOv3 程式適配（尚未做，這是真正的工程活）

三支硬編 `facebookresearch/dinov2` 的檔要補 HF 骨幹路——否則無法用 DINOv3 特徵重訓：

| 檔案 | 現況 | 要改成 |
| :--- | :--- | :--- |
| `backend/floorplan/room_classifier.py` (~L93) | `torch.hub.load("facebookresearch/dinov2", …)` | 加 HF/transformers 路（庫 id 含 `/` 走 `AutoModel.from_pretrained`）＋ CLS 取 `last_hidden_state[:,0]`（DINOv3 序列＝CLS＋4 register＋patches，CLS 在 0）|
| `training/scripts/probe_room_classifier.py` (~L149) | 同上硬編 | 同上（灰/彩房型頭靠它重訓）|
| `training/scripts/probe_seg_head.py` (L26) | `PATCH = 14` | `PATCH = 16` ＋ 骨幹改 HF 路 |

> **直接照抄 `training/scripts/probe_dino_backbone.py` 已寫好的 `v3hf` 分支**（`backbone_spec` / `load_backbone` / `cls_features`）——它是目前唯一已支援 DINOv3 的參考實作。

### 3–8. 重生裁切 → 重訓三頭 → 四量尺 A/B

```bash
# 3. 重生裁切（讀答案卷 → training/room_crops）
python training/scripts/extract_room_crops.py

# 4. 訓灰階房型頭 → room_head.npz
python training/scripts/probe_room_classifier.py \
  --backbone facebook/dinov3-vits16-pretrain-lvd1689m \
  --save_head backend/floorplan/room_head.npz

# 5. 訓彩色房型頭（彩 crops）→ room_head_color.npz
#    （沿用產彩頭的既有流程/crops，只換 --backbone 與 --save_head）

# 6. 訓分割頭 → seg_head.npz
python training/scripts/probe_seg_head.py --fit-final

# 7. 四量尺逐張 A/B（灰/彩 × dev；holdout 只在收尾量一次）
python training/scripts/eval_rooms_cc.py --own-eval --gt-seg   # 參數依現況補齊
```

**8. 淨正向才收**：逐張確認非「拆東補西」，報表落 `temp/json/`。

---

## C. 驗收基準（拍板依據）

- **端到端基準**（簡報 slide 3，v2.33 口徑）：

  | 量尺 | 空間切割正確性 | 核心 5 類判讀率 |
  | :--- | :--- | :--- |
  | 灰階 dev | 88.9% | **91.8%** |
  | 灰階 holdout | 83.3% | 75.0% |
  | 彩色 dev | 76.3% | 74.5% |
  | 彩色 holdout | 69.3% | 66.7% |

- **特徵層錨點**（本次離線探針，非端到端）：DINOv3 NC 0.573 / kNN 0.657（vs DINOv2 0.536 / 0.621）。
- **判準**：四量尺淨正向且超收案門檻 → 簡報**情境 A**（進授權評估）；持平／倒退／增益 < 成本 → **情境 B**（留 DINOv2）。

---

## D. 執行結果（2026-08-12，A 機 RTX 3060 Laptop）

> **決議：分域混合——灰階留 DINOv2、彩色換 DINOv3**（兩域 crop 層 A/B 方向相反：灰 −8.3pp／彩 +8.1pp；雙頭架構本就分域）。
> **採用前提**：彩色端到端目前仍低於基準（缺口在幾何規則閾值調校於 v2 機率分佈，見下拆源）——須對 v3 分佈重調閾值與牆帶參數、彩色四量尺淨正向才收。**在此之前產品資產維持 v2**（已還原），程式適配保留（v2 行為實證不變）。報告簡報：根目錄 `DINOv3_重訓結果報告.pptx`。

- **環境**：torch 2.13.0+cu130（cu124 無 2.13 build，改 cu130）、transformers 5.14.1、HF 帳號 CodyCH。
- **程式適配**：`room_classifier.py`／`seg_head.py`／`probe_room_classifier.py`／`probe_seg_head.py` 四支加 HF 骨幹路（照 `probe_dino_backbone.py` v3hf；`seg_head.py` 因四量尺會走到，產品端適配一併完成）。training tests 226 全過。
- **crop 層 A/B**（同裁切、同腳本、SEED 42）：

  | 域 | DINOv2 | DINOv3 | Δ |
  | :--- | :--- | :--- | :--- |
  | 灰階（72 房） | 86.1% | 77.8% | **−8.3pp** |
  | 彩色（62 房） | 83.9% | 91.9% | **+8.1pp** |

  灰階倒退非尺度問題：L2 正規化僅回 80.6%，pooler／patch 平均／CLS‖patch 皆 ≤80.6%。分割頭 LOIO：v3 AUC 0.985/IoU 0.907 vs v2 AUC 0.974。
- **端到端四量尺**（候選＝灰保持 v2、彩頭＋牆帶換 v3）：

  | 量尺 | 基準（v2.33） | v3 候選 | Δ |
  | :--- | :--- | :--- | :--- |
  | 彩 dev | 76.3% / 74.5% | 73.0% / 69.1% | −3.3 / −5.4 |
  | 彩 holdout | 69.3% / 66.7% | 67.7% / 64.7% | −1.6 / −2.0 |
  | 灰 dev / holdout | — | 未跑（crop 層已 −8.3pp，依 D 節不白花力氣） | — |

  基準重現：v2 彩 dev 76.3/74.5、灰 holdout 83.3/75.0 皆**逐字重現** v2.33 表——環境與適配無虞，倒退是真的。
- **倒退拆源**（彩 dev，`SEG_BANDS=0` 對照）：v2 牆帶貢獻 +1.3/+2.7pp；v3 牆帶反而 −0.7/−0.9pp；同無牆帶條件 v3 頭仍 −1.3/−1.8pp。**crop 層 +8pp 不轉移至端到端**，疑因幾何規則閾值（如 Bedroom 0.70 門檻）調校於 v2 的機率分佈。
- **重現指令**：v3 資產可由 B 節步驟 4–6 精確重現（訓練 SEED 固定）；報表在 `temp/json/eval_rooms/report_own_*dinov3*.json`。

## E. 別白花力氣的提醒

- **backbone 攻不到的**：LivingRoom（開放式，探針 0.075 換 v3 仍 0.075）、空間切割失敗（幾何層）、Garage 零樣本、Entry↔Hallway 資訊下限——這些不會因換骨幹改善。
- `opencv` 鎖 `4.13.0.92` 不要動（5.0 把 `HoughLinesP` 回傳 shape 改掉，門偵測會掛）。
- **授權**：DINOv3 非 Apache 2.0（Meta 自訂授權，須「Built with DINOv3」標示＋法務審查）。即使數字漂亮，**出貨採用前仍須法務**；內部評測用途在授權內。
