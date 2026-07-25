# 交接：微調 v5 訓練（2026-07-25 凌晨，Cody 機 → GPU 機）

## TL;DR

own_dataset 25 題＋own_eval 12 題標注**全面修復並逐張人工驗收完畢**，House 解析 37/37 通過。
`training/finetune_data.zip`（416MB）已重新打包，帶去 GPU 機即可直接訓練。
**本輪資料品質大幅優於 v1~v4**：修復了「牆窗門 id 失配導致九成手畫標注在訓練時隱形」的重大 bug（見下方陷阱清單），歷屆微調都是在殘缺資料上訓的。

---

## 一、GPU 機立即執行步驟

### 1. 同步程式碼與資料

```bash
git pull origin cody          # 本次 commit 含所有修復腳本與標注
# finetune_data.zip 不進版控——用 Google Drive / 隨身碟帶過去，放到 training/
```

### 2. 環境確認（machine A 跑過 v4 的話大多已備）

```bash
pip install lmdb scikit-image svgpathtools   # SVG 標注解析新增依賴（requirements.txt 已列）
# 既有：torch(GPU)、opencv、matplotlib、shapely、tensorboardX、pandas 2.x
```

### 3. CubiCasa5k 程式庫補丁（**必跑，含新增的 WashRoom 補丁**）

```bash
python scripts/apply_cubicasa_patches.py --dir training/CubiCasa5k
# 冪等腳本；若 GPU 機是 fresh clone 也是這一條
# 不跑的後果：WashRoom class 標注會退回 Undefined（floor01/06/08/47 中招）
```

### 4. 解壓訓練資料

```bash
# zip 內部路徑已帶 training/finetune_data/ 前綴，須在專案根目錄解壓
python -m zipfile -e training/finetune_data.zip .
# （機器沒裝 unzip 時 python -m zipfile 是現成替代；勿再 -d finetune_data，會雙層巢套）
# 內容：own/ 25 題 ×3 過採樣 + high_quality_architectural/ 300 題
# train.txt 375 行、val.txt 3 行（floor01/10/20——僅訓練監控用）
```

### 5. 訓練（v4 同配方，RTX 3060 約 33 分鐘）

```bash
cd training/CubiCasa5k
python train.py --data-path ../finetune_data/ \
  --weights ../model_best_val_loss_var.pkl --new-hyperparams true \
  --n-epoch 20 --batch-size 8 --l-rate 5e-5 --l-rate-var 5e-5 \
  --log-path runs_cubi/ft_v5/
# 產出 checkpoint 更名為 training/model_finetuned_v5.pkl 帶回
# 註（2026-07-25 實跑修正）：官方 model_best_val_loss_var.pkl 是 44 類權重，
# 必須用 --weights 載入；--furukawa-weights 是給原始 51 類 Furukawa 權重用的，
# 誤用會 size mismatch（conv4_/upsample 44 vs 51）。--new-hyperparams 必加，
# 否則會沿用 checkpoint 內舊 optimizer 狀態、蓋掉 lr 5e-5。
```

### 6. 驗收（回 Cody 機或就地）

```bash
# 換權重重算快取，對比基線（不動基線快取目錄）
CC_WEIGHTS=training/model_finetuned_v5.pkl CC_CACHE_DIR=training/cubicasa_room_ft5 \
  python scripts/eval_rooms_cc.py --gt-seg
```

**驗收門檻（歷屆同一標準）：具名房型 recall 不得倒退**（基線具名 macro-F1 0.838）。
v1~v4 全部未過門檻、預設權重維持基線；本輪資料痊癒後值得重新期待。

### 2026-07-25 v5 實測結果（雙尺分歧，換權重待裁決）

- 訓練順跑：val loss 6.57→1.75（v4 終點 2.19），最佳 checkpoint 在最後 epoch
- **own 尺（現行主尺）史上首勝基線**：新 GT 同尺重評，具名 macro-F1 基線 0.215 → **v5 0.473**，
  八類 recall 無一倒退（kitchen 0.4→0.9、living 0.083→1.0、bed 0.35→0.8、bath 0.43→0.86、entry 0→0.43）
- **CubiCasa 尺未過門檻**：具名 macro-F1 0.797（v4 0.814、基線 0.838），storage R -10pp、garage R -18pp；
  kitchen P 0.537→0.681、space→kitchen 誤名 51→24
- 結論：own 域大贏、CubiCasa 域小輸。預設權重是否切到 v5＝產品取向決策（目標域是 own 風格則值得切）
- **使用者已裁決（2026-07-25）：目標域＝own 風格，v5 接管預設**。權重移至專案根 `model_finetuned_v5.pkl`，
  **不進版控**（200M 超 GitHub 100MB 限制；gitignore 已加 `/model_finetuned_*.pkl`）
- **權重發佈與自動下載（2026-07-25，供前端整合部署）**：權重掛在 GitHub Release
  [`weights-v5`](https://github.com/Tom-Yang-Ben/RoomPilot-Agent/releases/tag/weights-v5)
  （asset id 489011637，SHA-256 `b7a280d2…f4cf`）。floorplan2room.py 在權重缺失時自動下載
  （`_ensure_cc_weights`，含 SHA-256 校驗；`CC_WEIGHTS` 環境變數指定的自訂權重不代抓）。
  **repo 目前 private**：部署端須設 `GITHUB_TOKEN`/`GH_TOKEN`（clone 私有 repo 本就需要，同一顆即可），
  程式會經 asset API 換 S3 簽名鏈下載；repo 若轉 public 則零設定直鏈生效。
  換機亦可繼續用 Drive/隨身碟帶（放專案根即跳過下載）
  （floorplan2room.py CC_WEIGHTS 預設已改）；`cubicasa/room/` 語意快取全數以 v5 重算
  （含 9 個來源圖已刪的死快取移除：hq17/19/33、floor17/24/30/34/46/49）；四份評分報表＋
  recognition_report.html 已重算同步（own 端對端 76.4%、IoU 0.875；具名命中 0.788）
- 註：CubiCasa 尺驗收需要資料集，7/23 清理時已刪；本輪已從 Zenodo record 2613548 重下
  （`python -m zipfile -e cubicasa5k.zip training/CubiCasa5k/data/`）

---

## 二、本次人工審批流程規則（已驗證有效，日後標注審查照此執行）

今晚 37 題逐張走完的 SOP，**一張一張來，不批次**（使用者要求；批次會漏掉語意錯標）：

1. **腳本先跑自動修復**：`python scripts/fix_own_floor.py Identify_ans/own_dataset/floorXX --backup-dir <備份> --render-dir <輸出>`
   - 修檔前必備份；產出 House 視角渲染圖
2. **AI 檢視渲染圖自我把關**：房型 vs 家具是否矛盾（沙發房標 Kitchen、浴缸間標 Kitchen 等）、
   「需人工」旗標逐條判讀、房間數 vs 圖面比對
3. **回報使用者**：修改摘要＋渲染圖＋疑點清單（只提問題，不擅自改語意）
4. **使用者裁決**：口頭回覆或貼 Inkscape 參考截圖（「照這個」）；AI 依座標精準改 class
5. **使用者 Inkscape 開檔驗收** → 說 OK 才進下一張

### 裁決原則（與使用者確認的鐵律）

- **使用者的英文 class 為主**（DEPOSIT 標 Bedroom 就是 Bedroom）
- **class 與填色衝突時，填色通常是真實意圖**（複製群組忘改 class 是最常見錯誤）——
  但要列出證據（家具、原填色）給使用者裁決，連續命中案例：floor19/20/52/55/73/74/78/79
- **Undefined＋標準色填色 = class 沒設好**，腳本自動改回（報告中列明）
- 名稱轉換：Terrace→Outdoor、Study→Office、Entrance→Entry、**WashRoom 獨立 class**（不併 Bath）
- own_eval 12 題永不進訓練（鐵律不變）

### 統一色表（Inkscape 1.4.4 HSL：H 0-360 / S 0-100 / L 0-100）

| class | Hex | HSL | 備註 |
|---|---|---|---|
| Bedroom | #4a90d9 | 211,65,57 | |
| Bath | #3dbdbd | 180,51,49 | |
| WashRoom | #d97a8f | 347,56,66 | 獨立 class，訓練 id 歸 6=Bath |
| Kitchen | #e8843c | 25,79,57 | Dining 併入 Kitchen |
| LivingRoom | #7dc37d | 120,37,63 | |
| Outdoor | #b5368f | 318,54,46 | Terrace/Balcony |
| Storage | #b8a06a | 42,35,57 | |
| Office | #c9b458 | 49,51,57 | Study |
| StairWell | #a89cc8 | 256,29,70 | |
| Entry | #8f5fc6 | 268,47,57 | Entrance |
| HallWay | #c9a0dc | 281,46,75 | |
| Garage | #909090 | 0,0,56 | |
| Undefined | #d9d9d9 | 0,0,85 | 未定類別用 |
| Wall / Window / Door | #cc2222 / #22aa22 / #ddaa00 | — | 透明度 45/60/60% |

房間填充透明度 35%。標籤＝class 名、22px 黑字、房內最深點置中、集中在 SVG 末端 `Labels` 群組（最上層）。

---

## 三、已知陷阱（fix_own_floor.py 已全部防禦，新標注必過此腳本）

1. **【最重大】House 用 `id` 而非 class 比對 Wall/Railing/Window/Door**（house.py:394/404/419/461）。
   Inkscape 複製元素必改 id → 手畫牆窗門對訓練隱形（floor09 牆 132px→修後 10031px；全 26 題 id 失配 264 處）
2. polygon points **尾空格**：House `split(' ')[:-1]` 會砍最後一項，無尾空格＝丟頂點
3. Inkscape 存檔會把 polygon 變 **path/rect**、位移存成 **transform**——House 不認 path/rect、忽略 transform
4. 複製群組**掉 class**（無 class 群組 House 直接跳過）
5. 替換元素時要**複製全部非幾何屬性**（只複製 style → 屬性式配色變黑塊）
6. 貝茲曲線指令（q/c/a）需人工處理，腳本會擋下報「需人工」
7. Space 群組空殼（無任何圖形）會讓 House 直接 crash

---

## 四、後續待辦（優先序）

1. **微調 v5 訓練＋驗收**（本交接主任務）
2. 彩色 30 題草稿人工修正：`Identify_ans/own_dataset_color/`（20 題）＋`own_eval_color/`（10 題）
   ——目前是管線草稿**未經人工修正、未進訓練**；修完跑 `fix_own_floor.py`（支援 `*floor*` 目錄）再擴充 pack_finetune_data.py
3. v5 若過門檻：換預設權重、重算全評分報表
4. 辨識素材庫已備妥可接符號匹配開發：`Asset/door/` 71 張、`Asset/kitchen/` 73 張、
   `Asset/bathroom/` 69 張、`Asset/pieces/` 543 張（10 類 DWG 切割，含馬桶/水槽/浴缸/淋浴/小便斗）

## 附：本機（Cody）狀態

- venv 新增：lmdb、scikit-image、svgpathtools（已寫入 requirements.txt）
- `training/finetune_data.zip` = 2026-07-25 02:00 打包版（對應本 commit 的標注）
- 標注修復備份：scratchpad（session 結束即失效）；真正的還原點＝本 commit
