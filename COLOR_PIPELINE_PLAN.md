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
- [ ] own_dataset_color 19 張跑通（無 error/svg_mismatch）
- [ ] own_eval_color 9 張跑通
- [ ] 基準數字記入本文件「Baseline 結果」節
- [ ] 失因初步歸類（seg 層 vs 命名層 vs 偵測層），加權重排序

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

## Baseline 結果（Phase 0 跑完回填）

（待填）
