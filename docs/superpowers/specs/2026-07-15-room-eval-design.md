# 路線圖 A：房型答案集評分工具（eval_rooms_cc.py）設計

- 日期：2026-07-15
- 目標：把 floorplan2room 的房型系統從「拍腦袋權重」變成可量測——解析 CubiCasa5k
  model.svg 的 Space 多邊形當 ground truth，對管線輸出算「分割 IoU＋房型混淆矩陣」。
  複製窗偵測 75%→99% 的答案集迭代方法論。

## 範圍

- 新增 `eval_rooms_cc.py`（單檔，與 eval_cc_masks.py / eval_color_walls.py 同風格）
- 不修改 floorplan2room.py / floorplan2dxf*.py 的任何偵測邏輯（只 import 調用）
- 不含路線 B（符號模板庫）與 C（微調）；不含 png/ 43 題的標注初稿功能

## 評分樣本

- 來源：`CubiCasa5k/data/cubicasa5k/{val,test}.txt` 中屬於 `high_quality_architectural/`
  的樣本（**不用 train**——路線 C 微調用 train，評分集必須永遠乾淨）
- 過濾：只取單層樓樣本（目錄內無 `F2_original.png`）——多層樣本的 SVG 含多個
  Floor group，對位模糊
- 數量：test 取前 40、val 取前 30（排序後取前 N，決定性可重跑）；不足則取全部並回報
- 影像：用 `F1_scaled.png`（model.svg 座標系與 scaled 圖同尺寸；實作時以 SVG
  viewBox == 圖片寬高做斷言驗證，不符者跳過並回報）

## Ground Truth 解析

- 用 `xml.dom.minidom` 讀 model.svg，取 `class="Space ..."` 的多邊形；
  頂點與房型映射重用 CubiCasa5k 程式庫：
  `floortrans.loaders.svg_utils.get_polygon` ＋ `floortrans.loaders.house` 的
  `rooms_selected` 映射表（SVG 房型字串 → 12 類語意 id，63 項；已驗證
  Dining→4 客廳、Sauna→6 浴廁、CarPort→10 車庫，與模型訓練歸類一致）
- 12 類 id → 管線房型的對照（與 floorplan2room.CC_ROOM_LABEL 同源）：
  3=廚房、4=客廳、5=臥室、6=浴廁、7=玄關、9=儲藏室、10=車庫、1=陽台/戶外、
  11(Undefined/Room 等)=空間；牆(2)/欄杆(8)/背景(0) 不算房間，排除
- GT 以「房間實例」保存：每間房一個多邊形遮罩＋房型標籤（不是壓扁的像素圖，
  因為要算逐房 IoU 與房間級混淆矩陣）

## 管線輸出取得

- 樣本圖先複製到 `eval_rooms/input/<樣本id>.png`（唯一檔名，避開
  cubicasa_room/ 快取以 basename 為 key 的撞名問題；樣本 id = 目錄名，如 `10074`）
- 語意快取：直接調用 floorplan2room.ensure_cc_masks()（缺快取自動 subprocess 跑
  infer_cubicasa.py，CPU 約 1 分/張，70 張約 70 分鐘，只算一次之後永久快取）
- 以 import 方式調用 floorplan2room 的單張處理路徑，取得記憶體中的
  `labels`（房間連通塊標籤圖）與 `rooms`（房型/面積清單）——不經 json bbox
  （bbox 算 IoU 太粗）

## 評分指標

1. **房間配對**：GT 房間 × 預測房間算 IoU 矩陣，貪婪一對一配對（IoU 由大到小），
   IoU ≥ 0.5 視為命中
2. **分割品質**：命中率（GT 房間被命中比例）、配對房間平均 IoU、
   過切率（預測房間數 / GT 房間數）、floor17 型整體失敗另計「分割失敗張數」
3. **房型混淆矩陣**：命中配對上 GT 房型 × 預測房型（9 類），
   輸出逐類 precision / recall；「空間」對「空間」= 誠實未定，單獨列不混入命名成績
4. **輸出**：
   - 終端逐張一行摘要 ＋ 總表（混淆矩陣、逐類 P/R、平均 IoU）
   - `eval_rooms/report.json`（機器可讀，供之後微調前後對比）
   - `eval_rooms/chk/<id>_gt.png` GT 疊圖 ＋ `<id>_pred.png` 預測疊圖（肉眼抽查對位）

## 錯誤處理

- SVG 解析失敗 / viewBox 與圖不符 / 管線例外：該張記為 error 跳過，總表回報張數與原因
- 分割失敗（切不出房間，如 floor17 型）：計入分割失敗，不進混淆矩陣
- GT 無有效房間（全 Undefined 且面積 0）：跳過並回報

## 驗證方式

- 先跑 3 張煙霧測試：肉眼比對 `_gt.png` 疊圖與原圖房型標注是否對位、
  混淆矩陣行列和 = 配對數
- 全量 70 張跑完，report.json 產出，與終端總表數字一致

## 依賴

- 既有 .venv ＋ 本日補裝：torch/torchvision（CPU 版）、lmdb、scikit-image、
  svgpathtools（floortrans.loaders 的連帶依賴）；CubiCasa5k/ 程式庫（已 clone）
- 這些推論/評分用依賴不進 requirements.txt（主管線不需要）；
  改記入 README 換機交接章節，避免下次換機再踩
