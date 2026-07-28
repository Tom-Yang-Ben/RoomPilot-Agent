# TODO：房型辨識加入 OCR 文字證據層（第 5 層）

> 2026-07-28 於 cody 機調查後立項。目標機器：任一台（OCR 走 CPU，免 GPU、免重訓）。
> 起因：floor04.png 七間房被判成 客廳×5／玄關×2，使用者質疑辨識品質。
>
> **✅ 2026-07-28 已完成**（feat/room-ocr-evidence，同機當日實作）。結果：
> own_dataset 25 層 gt-seg 具名 106/164=64.6% → **117/164=71.3%，零倒退**
> （floor04 1/6→6/6；floor01/02/03/07/08 連帶提升）；端對端切割前後
> 完全一致（68.3%／IoU 0.893），配對房型正確 60.2%→65.7%；
> 窗 P98/R96、門 84/86 不動。實作備註見文末「實作結果」。

## 調查結論（已驗證，換機不必重查）

1. **不是回歸**：18:36 的輸出與 7/26 的 `training/json/room/floor04_room.json` 逐字節相同，
   本次 pull（語意快取來源驗證等）沒有改變任何結果。
2. **不是快取汙染**：以 v5 權重現推重比對，新舊遮罩一致度 99.99%——快取確實出自這張圖。
3. **根因**：floor04 是美式極簡線稿——**無任何家具符號**（`icons_cm2`、`symbols` 全空），
   正解以英文字印在圖上（DORMITORY／KITCHEN／CIRCULATION／DEPOSIT／BATHROOM／LIVING ROOM）。
   CubiCasa 靠家具/格局特徵訓練，沒家具可看就把大房間全押 living：
   - DORMITORY→living 0.925、DEPOSIT→living **1.0**、LIVING ROOM→living 0.817（僅此間對）
   - KITCHEN 只有 living 0.275 弱票，被 `floorplan2room.py` `classify_rooms_cc` 的
     「相對多數加成」（`typed >= 0.05` 段）放大後仍判客廳
   - BATHROOM 無任何 bath 票（bed 0.115／entry 0.203）→ 判玄關
4. **為何不走繼續 finetune**：DORMITORY／DEPOSIT／LIVING ROOM 在像素層是完全相同的
   空白矩形，區分資訊只存在於文字。own_dataset 僅 25 張，分割網路學不到、只會過擬合，
   還可能拉壞 v5 在渲染圖上 0.9+ 的既有表現。與 MAIN_SYNC_TODO.md 裁定 3
   「模型在美式線稿上會自信地錯」相互印證。

## 決策：加 OCR 文字證據層，不再往 finetune 方向追

### 實作項目

- [x] **環境**：裝 OCR。首選 `apt install tesseract-ocr` + `pip pytesseract`
      （乾淨印刷英文足夠、最輕）；不想動系統套件則 `rapidocr-onnxruntime`（純 pip、
      CPU、順便吃中文標注）。裝哪套記得進 requirements.txt 註明（semantic extra 同級）。
      → **採 rapidocr-onnxruntime**（cody 機 sudo 需密碼，apt 不可用；floor04 六字全中 conf 0.99+）
- [x] **OCR 證據函式**（`backend/floorplan/floorplan2room.py` 新增，與 `detect_symbols` 平行）：
  - 對原灰階圖（或細線層）做 word-level OCR，取字框＋信心值，信心門檻過濾。
  - 字典映射（含模糊比對容 OCR 錯字）：
    `DORMITORY/BEDROOM→bed`、`KITCHEN→kitchen`、`BATH/BATHROOM/WC/TOILET→bath`、
    `LIVING/LOUNGE→living`、`DEPOSIT/STORAGE/CLOSET→storage`、
    `CIRCULATION/HALL/HALLWAY/ENTRY→entry`、`BALCONY/TERRACE→outdoor`、`GARAGE→garage`。
  - **注意**：floor04 的 ground truth 把 DEPOSIT 標成 `Space Bedroom`（model.svg 內
    Bedroom×2）——DEPOSIT 的映射要跟標注慣例對齊，動手前先跟標注者確認一次。
    → **已確認（2026-07-28）：DEPOSIT→storage，GT 誤植一併修正**（model.svg g33）
- [x] **計分整合**（`classify_rooms_cc`）：字框中心落在哪個房間（`labels` 查表）就給
      該房型加分；權重設在圖示證據之上（文字是作者親口說的答案，建議 +0.6~0.7 級）。
      圖上沒字＝零貢獻，行為與現行完全相同，不影響其他評測集。
      → **權重定 1.3 而非 0.6~0.7**：floor04 實測 DEPOSIT→living 語意滿票 1.0
      「自信地錯」，0.65 壓不過語意+加成 1.12；語意+圖示鐵證聯手(≥1.7)仍可反壓 OCR 誤讀
- [x] **順手修弱票放大器**：top 票 < 0.35 不加成；own_dataset 25 層評測零倒退確認
- [x] **JSON/疊圖透明化**：`_room.json` 每房加 `ocr_text` 欄（{房型: [原文字]}，
      無命中時為 null——main 端若有嚴格 schema 需知悉此 additive 欄位）

### 驗證（收工條件）

- [x] own_dataset 25 層前後對照：gt-seg 具名 64.6%→71.3% 零倒退
      （報表 training/json/eval_rooms/report_own_gtseg_own_dataset_{baseline,after}.json，
      評測入口 `eval_rooms_cc.py --own-dir testdata/Identify_ans/own_dataset [--gt-seg]` 本輪新增）；
      floor04 端對端 6/7（唯一錯的是被切成上下兩半的走道上半、無文字可救；gt-seg 6/6）
- [x] 無文字的圖成績零退步：25 層中僅含文字層變動且全為改善；端對端切割前後逐字節一致
- [x] 窗/門基準不動：gray 45 張 P98/R96、door 84/86（chk 重生後實測）

### 已知限制（follow-up）

- `deskew=true` 時 OCR 座標對不上分析圖 → 已加防護自動停用（預設 false 不受影響）
- OCR 單例非執行緒安全：批次/腳本單執行緒沒問題，伺服器端多執行緒 import 需加鎖或 warm-up
- 退回面積規則路徑（無語意快取）不採 OCR 證據；中文標注詞彙未進字典（rapidocr 可讀，待需求）

### 流程約定

- 依開發工作流：**從 cody 開 feature 分支**（建議 `feat/room-ocr-evidence`），
  不直接動 cody；完成後 PR。
- `floorplan2room.py` 是 main 橋接契約檔（`build_rooms(det)` 介面，見 MAIN_SYNC_TODO.md
  裁定 1），只在 `classify_rooms_cc` 內加證據層、不動 `process()`／`build_rooms` 形狀。
- main 端「語意只填空」（裁定 3）不受影響：OCR 是 cody 管線內部計分，出口仍是
  `rooms[].label`。

### 相關檔案速查

| 用途 | 路徑 |
| :--- | :--- |
| 房型分類主體 | `backend/floorplan/floorplan2room.py`（`classify_rooms_cc`） |
| 語意推論 | `backend/floorplan/infer_cubicasa.py`（快取已帶 `src_sha256`） |
| 語意快取 | `cubicasa/room/*_mask.npz`（契約路徑；**切分支後同名不同圖要刪快取重推**，舊快取無 sha 只擋尺寸） |
| Ground truth | `testdata/Identify_ans/own_dataset/<floor>/model.svg`（`Space <Class>` polygon） |
| 已知案例 | floor04：cody 與 ben-dev 是**不同圖但同尺寸** 1173×1079（cody RGBA / ben-dev RGB） |
