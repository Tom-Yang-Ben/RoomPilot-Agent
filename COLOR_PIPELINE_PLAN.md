# Color 管線調優計劃書

- **日期**: 2026-08-01
- **前置**: color 答案集 28 張已全數人工審定（own_dataset_color 19 張 152 間、
  own_eval_color 9 張 62 間，0 Undefined，parse_gt 全過）。
  重複已清：color_floor_11（同 floor_04）、灰階 floor19（與保留集 floor60 洩漏）。
- **相關**: 灰階調優歷程與失因分析見 `SEG_FAILURE_ANALYSIS.md`（v2.23/v2.24）。

## 目標

1. **Phase 0 — Baseline**：用乾淨 GT 對 color 集首次量測，建立基準數字。
2. **Phase 1 — Color 調優**：以 own_dataset_color 為開發集做失因歸類與修正，
   目標比照灰階：整體命中 ≥ 80%、核心五類（Kitchen/LivingRoom/Bedroom/
   Storage/Bath）命中 ≥ 85%。
3. **Phase 2 — 墨水層殘餘**（color 告一段落後）：
   - floor_02：圍籬線進 thin 層造成的切割問題
   - floor_13、floor_09：零符號圖的命名證據不足問題

## 量測方式（Phase 0）

```
# 開發集（19 張）
python training/scripts/eval_rooms_cc.py \
    --own-dir testdata/Identify_ans/own_dataset_color --report-suffix baseline

# 保留集（9 張）——只在循環收尾跑，平時不看
python training/scripts/eval_rooms_cc.py \
    --own-dir testdata/Identify_ans/own_eval_color --report-suffix baseline
```

- 報表落在 `temp/json/report_own_own_dataset_color_baseline.json`（保留集同理）。
- 指標：hit_rate（IoU≥0.5 配對率）、overseg、mean_iou、per-class P/R、
  seg_fail 數。核心五類命中另行從 confusion 算。

## 紀律（沿用灰階循環的鐵律）

- **開發只看 own_dataset_color**；own_eval_color 每循環收尾量一次，防過擬合。
- 疑似答案卷標錯 → 帶證據（疊圖）找使用者一起看，不硬調管線遷就。
- 房間切割一律軸對齊直角矩形系（0/90/180/270）。
- 改 `testdata/Identify_ans/` 任何檔案前先問使用者、先備份。
- 每個假設先寫測試（TDD），失敗假設誠實記錄並 revert。

## 待驗證進度（checklist）

### Phase 0 — Baseline
- [x] own_dataset_color 19 張跑通（18 ok＋1 seg_fail，無 error/svg_mismatch）
- [x] own_eval_color 9 張跑通（9 ok）
- [x] 基準數字記入本文件「Baseline 結果」節
- [ ] 失因初步歸類（seg 層 vs 命名層 vs 偵測層），逐張看疊圖加權重排序

### Phase 1 — Color 調優（依 baseline 失因決定攻擊順序，逐輪補記）
- [ ] 第一輪：攻擊最大失因（待 baseline 出爐後填）
- [ ] 每輪收尾：own_eval_color 量一次，記遷移數字
- [ ] 達標判定：dev 命中 ≥ 80% 且核心五類 ≥ 85%，holdout 無明顯落差（< 5pp）
- [ ] Readme changelog 補版本節

### Phase 2 — 墨水層殘餘（灰階）
- [ ] floor_02 圍籬線：thin 層誤收圍籬 → 切割誤合，先寫重現測試再修
- [ ] floor_13 / floor_09 零符號：symbol_match 在這兩張一個符號都沒中，
      查模板覆蓋與 CH_THR 距離分佈，決定補模板或調門檻
- [ ] 灰階開發集重量測：**分母已變**（own_dataset 25→24，floor19 已刪），
      舊報表 157 房基準不可比，需重跑 baseline 後才能比較
- [ ] own_eval 保留集收尾量測

## Baseline 結果（2026-08-01）

| 指標 | 開發集（19 張） | 保留集（9 張） |
| :--- | :--- | :--- |
| 命中率（IoU≥0.5） | **59.2%**（84/142） | **67.7%**（42/62） |
| 核心五類命中 | **56.7%**（38/67） | **72.2%**（26/36） |
| 過切率 | 1.08 | 1.39 |
| 配對平均 IoU | 0.857 | 0.789 |
| seg_fail | 1（floor_07） | 0 |

報表：`temp/json/eval_rooms/report_own_own_{dataset,eval}_color_baseline.json`

### 逐張命中（開發集）

| 張 | 命中 | 張 | 命中 |
| :- | :--- | :- | :--- |
| 01 | 4/7 | 12 | 10/12 |
| 02 | 5/9 | 13 | 5/9 |
| 03 | 3/6 | 14 | 6/9 |
| 04 | 8/10 | 15 | 3/5 |
| 05 | 5/10 | 16 | 3/5 |
| 06 | 6/9 | 17 | 9/10 |
| 07 | **seg_fail** | 18 | 5/7 |
| 08 | **1/7** | 19 | 3/5 |
| 09 | **1/7** | 20 | **2/5** |
| 10 | 5/10 | | |

保留集低分張：floor_25（2/6）、floor_21/29（3/6）。

### 初步觀察（待逐張疊圖確認）

1. **分割層是最大失因**：floor_07 seg_fail、floor_08/09 只配 1/7、floor_20
   2/5——配上的 IoU 都 0.95+，代表其餘房間沒被切出（黏成大塊或漏切），
   不是切歪。這一項至少吃掉開發集 ~25 間。
2. **命名層系統性弱點**（兩集一致）：
   - **Balcony R=0.0（兩集全滅）**，開發集 6 個被叫成 Stair——陽台磚紋
     疑似觸發樓梯特徵。
   - **Bath R 低**（dev 0.22 / holdout 0.46），常被叫 Bedroom/Storage。
   - **Kitchen R=0.33**（兩集同數字）。
3. **比例尺**：color 圖開口樣本常為 0（floor_30 量出 0.46 cm/px、開口樣本
   0、退回 wall_mid），門寬鐵律在 color 線稿上偵測不到門弧，比例尺品質
   待查。
