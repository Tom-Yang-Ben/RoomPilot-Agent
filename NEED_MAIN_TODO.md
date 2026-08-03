# ben 分支配合修改清單（cody-dev 2026-08-03 合併輪）

> 2026-08-03 由 `cody-dev` 分支發起。前一輪為 2026-07-30 的 `MAIN_SYNC_TODO.md`
> （其成果已由 ben 於 a8f8b1ea／620698b9 吸收）；本檔是新一輪，結構沿用前檔。
> 本輪為 **cody 側收尾輪**：彩色調優與灰門專攻已收案，工作計劃書
> （COLOR_PIPELINE_PLAN.md／SEG_FAILURE_ANALYSIS.md）已自 cody 移除，
> 歷程見 cody 分支 git 歷史與 `docs/CODY_PIPELINE_README.md` changelog。

## 這份文件怎麼用

`cody-dev` 是以 `ben`（ffd38968）為基底、疊上 cody v2.33 辨識管線的分支。
衝突 173 處逐處裁定，準則沿用上輪：**保留 ben 的產品能力、採用 cody 的管線
進展**。所有「已完成／已改」皆為 `cody-dev` 當前提交的實際狀態，可用
`git diff ben cody-dev` 逐項核對。

審查順序建議：

1. 第 1 節辨識率證據（指令可自行重跑）
2. 第 2 節本輪帶來什麼
3. 第 3 節衝突裁定與 ben 端程式碼的配套修改——**最需要 ben 覆核**
4. 第 4 節 ben 必做／建議／知悉
5. 第 5 節已知風險

## 1. 辨識率證據鏈（v2.33 標準口徑）

### 1.1 標準口徑定義（2026-08-02 使用者定案，v2.27 起沿用）

- **空間切割正確性** ＝ 切對的房間 / 全部 GT 房間（IoU≥0.5 配對率，不論命名）
- **核心5項判讀率** ＝ 切對**且**叫對的核心五類（Kitchen/LivingRoom/Bedroom/
  Storage/Bath）/ 核心五類 GT 總數——端到端口徑

### 1.2 房間指標（四量尺，v2.33 現況）

| 量尺 | 空間切割正確性 | 核心5項判讀率 |
| :--- | :--- | :--- |
| 灰階 dev（24 張 153 房） | **88.9%**（136/153） | **91.8%**（112/122） |
| 灰階 holdout（12 張 72 房） | **83.3%**（60/72） | **75.0%**（45/60） |
| 彩色 dev（19 張 152 房） | **76.3%**（116/152） | **74.5%**（82/110） |
| 彩色 holdout（9 張 62 房） | **69.3%**（43/62） | **66.7%**（34/51） |

**與 ben 現吸收版本（a8f8b1ea，2026-08-01 快照）的對照**——當時灰階 dev
82.2%（129/157）、保留集 80.6%（58/72）。其後答案卷經人工逐間審定修正
（分母 157→153），數字不能逐位元直比，但同尺趨勢為：

- 灰階 dev 82.2% → **88.9%**、holdout 80.6% → **83.3%**
- 彩色從無量尺 → 建立 28 張 214 間全人工審定答案集，dev baseline
  59.2% → **76.3%**（循環一 63.8%／二 67.8%／三 75.0%／分割頭 76.3%）
- 彩 holdout 端到端全對 26 間 → **39 間**（+50%）

逐輪演進數字與失敗假設（誠實負結果一併記錄）見
`docs/CODY_PIPELINE_README.md` changelog v2.25～v2.33，及
`docs/superpowers/plans/2026-08-01-seg-attribution.md`（灰階歸因）、
`docs/superpowers/specs/2026-08-03-seg-head-design.md`（分割頭設計）。

### 1.3 門/窗指標

| 門/窗 | 灰階 | 彩色 |
| :--- | :--- | :--- |
| 門（產品 json doors） | **P 0.83／R 0.81**（90/111，F1 0.82） | 輸出關閉（偵測 P 0.38/R 0.47） |
| 窗 | **P 98%／R 92%** | 輸出關閉（偵測 P 61%/R 42%） |

**門是本輪對 ben 產品端最大的單項提升**：ben 現行吸收版的 json doors 走
弧掃描路，實測 **P 0.38/R 0.17**；本輪改源牆縫門位（`fp_c.gap_door_zones`
共用核心）＋範圍擦邊收割放寬窗，**P 0.83/R 0.81**，灰彩兩條產品路口徑統一。

### 1.4 重跑指令（在 cody-dev 上，環境見 4.2-2）

```bash
# 房間四量尺（報表落 temp/json/）
python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_dataset          # 灰 dev
python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_eval             # 灰 holdout
python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_dataset_color    # 彩 dev
python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_eval_color       # 彩 holdout

# 門（端到端 json 門位量尺）與窗
python backend/floorplan/eval_doors.py
python backend/floorplan/floorplan2dxf.py          # 產 temp/chk/gray/
python backend/floorplan/eval_windows.py
python training/scripts/eval_door_json.py          # 門 json 路 P/R
```

**口徑註記（誠實揭露，ben 端審查請知悉）**：

- 彩 dev 76.3% 中，監督式分割頭的訓練見過 dev 圖（比照分域雙頭輪慣例）；
  無偏數字為 LOIO patch AUC 0.974/IoU 0.876。holdout 43/62 逐位元一致
  （語意牆帶未觸發、零風險曝露，泛化待新樣本回驗）。
- 灰階雙頭基準自 90.3% 移到 86.1% 是答案卷標籤修正所致（新舊頭同分、
  非退化）；本表 1.2 的端到端口徑與該命名口徑不同，不可互比。

## 2. cody-dev 帶來什麼（相對 ben 現況）

1. **分域雙頭房型分類**：灰階/彩圖各一顆 DINOv2 線性頭
   （`room_head.npz`＋新增 `room_head_color.npz`），依 fence 偵測選頭，
   color 頭缺檔退灰階頭（出聲不靜默）。
2. **監督式分割頭語意牆帶**：`seg_head.npz`（7KB）＋`seg_head.py`，
   彩色棄守畫風（近白暗示牆）救援；`SEG_BANDS=0` 可 A/B 停用，
   資產缺檔＝停用零行為。
3. **門偵測重建**：json doors 改源牆縫門位（1.3 節）；弧掃描保留供
   比例尺/窗抑制/arch 白模。
4. **彩色門窗輸出閘**：`emit_openings=false` 預設關（低於可用線交付
   停畫），json 帶 `openings_suppressed` 標記，偵測保留供封口/比例尺。
5. **符號模板庫 v225**：943→961 條（美式畫風衛浴/廚具素材輪、
   trashcan 新類、`TPL_THR` 逐模板門檻機制）。
6. **答案集**：28 張彩色 214 間全人工審定（0 Undefined）；灰階答案卷
   標籤修正；圖檔集收斂 44→37 張（無人工答案的圖退場，不參與計分）。
7. 房型詞彙統一 10 類 CamelCase（6300e9e0，見 3.2）。

## 3. 衝突裁定與 ben 端配套修改（本節全部需 ben 覆核）

### 3.1 backend/floorplan 六檔（取 cody＋回植 ben 產品修正）

`floorplan2room.py`／`floorplan2dxf_color.py`／`symbol_match.py`／
`config_color.ini` ben 端為 cody 歷史原樣快照，直接取 cody 最新（純前進）。
兩檔手工三方合併：

- **floorplan2dxf.py**：取 cody（含門重建），回植 ben 三處——
  (a) 非 ASCII 路徑讀圖（np.fromfile＋imdecode，產品上傳硬需求）；
  (b) HoughLinesP 回傳 shape 的 OpenCV 4/5 安全網；
  (c) `detect_door_swing_arcs` 後備偵測器（`cody_adapter.py:696` 在用）。
  另補 package 載入路徑修正（cody 新增頂層平名 `import floorplan2dxf_color`
  在 ben 的 package 結構會 ModuleNotFoundError，比照 floorplan2room.py
  作法先插 `_PKG_DIR`）。
- **room_classifier.py**：取 cody 雙頭版，回植 ben 的 `available()`
  （`cody_adapter.py:1025` 的 `room_label_source` 訊號用）。

### 3.2 房型詞彙契約對齊（跨資料夾修改，主要 owner：Cody；協作 owner：Ben）

cody 6300e9e0 起詞彙統一 10 類 CamelCase：`Kitchen/LivingRoom/Bedroom/
Bath/Entry/Storage/Garage/Hallway/Stair/Balcony`＋中性 `room`
（outdoor 併入 Balcony、新增 Hallway）。ben 端映射層同步修改：

- `backend/floorplan/vision/analysis.py`：`CODY_ROOM_TYPE_MAP` 鍵改
  CamelCase；新類 **Hallway→circulation**（沿用「走道跟隨客廳風格、
  刻意零家具」既有語意）；Garage/Stair 維持 None 的既有裁定。
- `backend/floorplan/vision/evaluation.py`：`ROOM_LABEL_ALIASES` 加
  CamelCase 別名（正常路徑先經 MAP 轉換，此為原字彙直達時的保險）。
- `tests/test_cody_room_recognition.py`：fixture 詞彙同步 CamelCase。
- 資料契約形狀不變：`rooms[].label/type/id` 欄位結構原樣，只有 label
  值域變更。**ben 請自查其他隱性吃小寫詞彙處**：
  `git grep -nE '"(living|bed|bath)"' backend/server/ backend/agent/`

### 3.3 testdata（owner Cody，取 cody）

- 答案卷 `Identify_ans/` 更新為 cody 2026-08-02/03 人工審定版（標籤修正
  ＋彩色 28 張入 GT）。**Django 端若對答案卷有本地標註修改，需重新提報**。
- 圖檔集收斂編號重用：cody 的 `floor04` 已是另一張圖。ben 的 swing 測試
  固定樣張改名 `testdata/png/ben_swing_case_04.png` 保存（測試同步改路徑），
  `builder_plan_630.*` 系列不受影響。
- 中文檔名兩張 dxf（`03-3 bedroom house design_*`）依 cody 圖檔集收斂移除，
  全 repo 無程式引用。

### 3.4 其他

- cody 根目錄 `Readme.md` → `docs/CODY_PIPELINE_README.md`（沿上輪裁定，
  更新至 v2.33；根目錄 README.md 維持 ben 版）。中繼 commit 18caabe3 為
  Windows 大小寫碰撞的機械性暫移，最終樹已恢復。
- `backend/cabinetdesign/`、`docs/HANDOVER_finetune_v5.md`、
  `docs/recognition_report.html`（v2.17 舊報告）沿上輪裁定不帶入。
- `docs/superpowers/` plans/specs **本輪帶入**（上輪未帶）：它們是 1.2
  證據鏈的歸因文件，且 v2.33 的 Readme 與 seg_head.py docstring 指向它們。
  若 ben 端 docs 政策不收，請告知，下輪改留 cody 分支。
- `docs/png2dxf_pipeline.html`：v2.33 管線架構總覽（2026-08-03 產出）。
- `.gitignore`／`requirements.txt`：ben 版為基底，附加 cody 段
  （lmdb/scikit-image 為 eval 鏈的 GT 解析依賴，產品推論不需要）。
- `training/tests/test_annotation_drafts.py` 的 CubiCasa 案加
  `pytest.importorskip`：`training/CubiCasa5k` 是本機自管 checkout
  （gitignore 排除），沒有它的機器（含 ben 端）明確 skip 不誤報紅。

## 4. 還要動手的事

### 4.1 ben 必做

- [ ] **彩色圖無門窗的產品 UI 對策**：彩圖 json `doors`/`windows` 空、帶
      `openings_suppressed` 標記（偵測品質低於可用線，裁定交付停畫）。
      前端第 2～4 步的顯示與後續流程需明確 fallback（提示使用者手動補門窗
      或沿用 ben 的 swing 後備偵測器補位——後備的優先序請 ben 裁定）。
- [ ] **灰階 doors 換源驗收**：json 門位從弧掃描（R 0.17）換成牆縫門位
      （R 0.81），但 zones 路**沒有鉸鏈/開向資訊**（hinge_px 由 ben 端
      swing 後備補）。`scene_service.py` 門渲染與 3D 白模請實測一輪。
- [ ] **在 ben 環境跑完整測試套件**：cody 環境缺 psycopg2 等產品依賴，
      本輪只驗了辨識相關 72 測試＋training 234 測試（全綠、2 skip）。
      catalog/server/engine 側請 ben 端自跑。
- [ ] **torch 依賴決策落地確認**：雙頭與分割頭都吃 torch；缺 torch 時
      房型退面積規則、分割頭停用（皆出聲）。requirements.txt 註記已更新，
      部署程序是否預裝 torch 請 ben 確認。

### 4.2 建議

- [ ] 評測環境補裝 `lmdb`、`scikit-image`（requirements.txt 已列），
      即可在 ben 機器自行重跑 1.4 全部量尺。
- [ ] `scene_v2.js:141` 的詞彙註解仍寫舊小寫詞彙（功能鍵是 ben 契約型別
      不受影響）——順手更新註解防誤導。
- [ ] 前端推薦表若新增 `stair` 契約鍵，`CODY_ROOM_TYPE_MAP` 的
      `Stair: None` 可改指過去（沿前輪待辦）。

### 4.3 知悉即可

- 彩門/彩窗偵測仍在跑（供封口與比例尺），只是不出貨。
- 灰門殘餘 FN 19 樘已逐樘分型收案（seamless 10／halfgap 6／deadzone 3），
  原理性瓶頸，工程手段實測淨負已 revert；arch 白模門弧幾何（鉸鏈/開向）
  另輪。
- floor_07/08/09 彩色棄守畫風維持棄守（留分母如實計分）。

## 5. 已知風險

1. **語意牆帶泛化未經 holdout 實測**：holdout 無災難張、救援未觸發。
   出現新的彩色災難張樣本時需回頭驗（`SEG_BANDS=0` 可即時停用）。
2. **詞彙變更的隱性消費者**：3.2 已改映射層與已知測試，但 ben 端若有
   繞過 `CODY_ROOM_TYPE_MAP` 直接吃 label 的路徑，會靜默不匹配——
   請跑 3.2 的 grep 自查。
3. **答案卷更新**：Django 端本地標註若與新答案卷衝突，以「帶證據找
   使用者一起看」流程處理，不硬調管線遷就（沿 cody 紀律）。
4. 中繼 commit 18caabe3（README 暫移）若 ben 端以 squash 方式吸收
   cody-dev 則自然消失；保留 merge 拓撲亦無害。
