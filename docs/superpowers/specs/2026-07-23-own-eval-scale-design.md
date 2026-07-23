# own_eval 量尺：eval_rooms_cc.py 增加 --own-eval 模式

- 日期：2026-07-23
- 狀態：已核准（使用者於對話中確認「就做吧」，交付物定義見下）

## 目的

把房型命名評分的量尺從 CubiCasa 風格（芬蘭向量圖）遷移到 own 風格（產品實際的
實心牆掃描圖）。微調路線 C 的驗收自此能回答「own 風格有沒有變好」，而不是只看
「CubiCasa 分數有沒有倒退」。

## 需求

1. `eval_rooms_cc.py` 增加 `--own-eval` 旗標：
   - 樣本來源改為 `Identify_ans/own_eval/eval_list.txt`（12 題，floor55~79）
   - GT 改讀 `Identify_ans/own_eval/<id>/model.svg`（人工審定）
   - 輸入圖改 stage `Identify_ans/own_eval/<id>/F1_scaled.png`
     （已驗證與 `png/<id>.png` 逐位元相同；語意快取以 basename 為 key，同名同內容安全）
   - 報表輸出 `json/eval_rooms/report_own[_gtseg].json`
2. 與既有 `--gt-seg` 正交組合；評分邏輯（IoU 配對、混淆矩陣、9 類 P/R）完全共用。
3. `CC_WEIGHTS`/`CC_CACHE_DIR` 環境變數覆寫照舊生效（A/B 驗收隔離快取）。

## 非目標

- 不動既有 CubiCasa 評分路徑與報表格式。
- 不做端到端分割評分的風格補強（v2.12 已決策退役；own 量尺只跑 gt-seg 命名層）。

## 設計

最小侵入：`pick_samples()` 旁增 `pick_own_samples()`；`eval_one()` 的 GT svg 路徑
與 staging 來源依模式切換（傳參，不引全域分支）；報表檔名由旗標組合導出。
`parse_gt()` 不變——own model.svg 與 CubiCasa 同格式（make_annotation_drafts 產出、
House round-trip 已驗證），Undefined 房自然落入 space 類。

## 驗收

- 單元測試：own 樣本清單解析（12 題、目錄與 F1_scaled.png 齊全）、報表路徑導出。
- 實跑：基線與 model_finetuned_v4.pkl 各跑一次 `--own-eval --gt-seg`，
  產出兩份報表可對比（12 題全數 status=ok）。
