# TRAINING.MD — cody 分支研發工具指南（2026-08-03 收尾定版）

`training/` 是 cody 辨識管線的研發自用目錄：**量測、答案卷製作、模型頭重訓、
符號素材入庫、回歸測試**。產品推論鏈（`backend/floorplan/`）對本目錄零依賴，
終版交付（cody-dev → ben）不含本目錄——重啟任務或新增 testdata 後的訓練，
一律回 cody 分支操作。

本檔為唯一入口說明（原 `training/scripts/README.md` 已併入並刪除）。

## 0. 環境

```bash
pip install -r requirements.txt   # 版本已釘實際開發環境（2026-08-03 對齊）
```

- 產物一律落 `temp/`（gitignore，隨時可全刪重生）。
- 本機可再生的中間產物：`training/room_crops/`（裁切資料集）、
  `training/asset_ckpt/`（素材輪快取）——都不進版控，缺了就重跑對應腳本。

## 1. 量測（改任何共用碼前後必跑）

| 量尺 | 指令 | 現行基準（v2.33） |
| :--- | :--- | :--- |
| 灰 dev 房間 | `python training/scripts/eval_rooms_cc.py --own-dir testdata/Identify_ans/own_dataset` | 88.9%（136/153） |
| 灰 holdout | `... --own-dir testdata/Identify_ans/own_eval` | 83.3%（60/72） |
| 彩 dev | `... --own-dir testdata/Identify_ans/own_dataset_color` | 76.3%（116/152） |
| 彩 holdout | `... --own-dir testdata/Identify_ans/own_eval_color` | 69.3%（43/62） |
| 門（端到端 json） | `python training/scripts/eval_door_json.py` | P 0.83／R 0.81 |
| 門（zones 層內診斷） | `python training/scripts/eval_door_zones.py` | 同上口徑的層內版 |
| 門過濾 | `python backend/floorplan/eval_doors.py` | 98%（84/86） |
| 窗 | `python backend/floorplan/floorplan2dxf.py && python backend/floorplan/eval_windows.py` | P 98／R 92 |
| 彩牆像素 | `python training/scripts/eval_color_walls.py` | P 87.7／R 94.9 |

鐵律：開發只看 dev；holdout（own_eval*）只在循環收尾量一次。逐輪 A/B
淨正向才收；報表落 `temp/json/`。

## 2. 新增 testdata 的答案卷工序（Inkscape 手修鏈）

1. 圖入 `testdata/png/`（灰）或 `testdata/color_png/`（彩）。
2. `python training/scripts/make_annotation_drafts.py` — 管線輸出組成
   CubiCasa model.svg 格式初稿，落 `testdata/Identify_ans/own_dataset*/<名>/`。
3. Inkscape 人工修正（房間多邊形、房型文字）。
4. 手修後必跑三件套：
   - `python training/scripts/fix_annotation_paths.py`（path/rect → polygon）
   - `python training/scripts/sync_room_labels.py`（文字標籤 → class 屬性）
   - `python training/scripts/fix_own_floor.py`（掉 class／transform 烘焙／統一色）
5. 彩色集另跑 `python training/scripts/normalize_answer_svg.py`（歸一收尾）。
6. 楔形粗畫導致量尺失真時：`python training/scripts/rebuild_room_gt.py`
   （用 GT 牆重建 Space 輪廓）。
7. `training/scripts/svg_poly.py` 是評分鏈讀 GT 的唯一入口（被 eval_rooms_cc
   等 import，不直接執行）；改動答案卷慣例前先看它與
   `training/tests/test_svg_poly_parity.py`。

**紀律**：改 `testdata/Identify_ans/` 任何檔案前先問使用者、先備份
（人工審定資產）。

## 3. 模型頭重訓（新增答案卷後）

| 頭 | 指令 | 輸出 |
| :--- | :--- | :--- |
| 房型灰階頭 | `python training/scripts/extract_room_crops.py` → `python training/scripts/probe_room_classifier.py --domain gray`（依提示以 train split 訓練） | `backend/floorplan/room_head.npz` |
| 房型彩色頭 | 同上改 `--domain color`（分域雙頭：混訓實測傷灰階 -5.5pp，勿混） | `backend/floorplan/room_head_color.npz` |
| 分割頭（語意牆帶） | `python training/scripts/probe_seg_head.py`（LOIO 標定）；驗證可分性後帶 `--full` 全訓出貨 | `backend/floorplan/seg_head.npz` |

重訓後必跑第 1 節四量尺＋`training/tests/`（回歸 232+ 項），
holdout 只收尾看一次。

## 4. 符號素材輪（新畫風模板入庫）

1. 素材來源是 DXF 時：`python training/scripts/dxf2png_pieces.py` 切成單件
   線稿 PNG；人工裁切歸類進 `testdata/Asset/<類>/`。
2. `python training/scripts/extract_asset_lib.py` — 併入模板庫
   `backend/floorplan/symbol_lib.npz`（48×48 正規化、近重複去重）。
3. `python training/scripts/probe_symbol_quality.py` — 弱標籤全掃逐模板
   TP/FP，據此**量測驅動**決定啟用範圍（逐類門檻 `CH_THR_BY_KIND`、
   逐模板 `TPL_THR`、白/黑名單——見 `docs/CODY_PIPELINE_README.md` v2.24/v2.33）。
4. 驗收：既有量尺逐位元不動才算零波及（比對 dev 全集）。

## 5. CubiCasa5k（6.6G 大檔，不進版控——需要時另外下載）

**何時需要**：只有「答案卷 House 回讀驗證」用到它的 `floortrans` 程式庫
（make_annotation_drafts 產稿後驗證、sync_room_labels `--no-validate` 以外
的驗證路、`training/tests/test_annotation_drafts.py` 的 House 案——缺庫時
importorskip 明確跳過）。**日常量測鏈完全不需要**（GT 解析走自寫的
svg_poly，2026-08 已與 CubiCasa loader 脫鉤，lmdb 依賴同步移除）。

需要時的安裝步驟：

```bash
git clone https://github.com/CubiCasa/CubiCasa5k training/CubiCasa5k
python training/scripts/apply_cubicasa_patches.py   # numpy 2.x 相容補丁，冪等可重跑
```

（dataset 圖集非必要，驗證只用程式庫；clone 後 6.6G 主要是資料集，
磁碟緊張可只保留 `floortrans/` 目錄。）

## 6. 本次收尾刪除紀錄（2026-08-03，要復活找 git 歷史）

| 已刪 | 原因 |
| :--- | :--- |
| `door_match.py`／`door_propose.py`／`eval_door_match.py`／`extract_door_lib.py`／`training/door_lib.npz` | 門「弧候選×模板融合」線整條退役——產品門位已改源 build_rooms zones（P 0.83/R 0.81），融合線的 score_fused 量尺不再是任何交付口徑 |
| `probe_band_semantics.py`＋`test_band_semantics.py` | 白牆帶語意判別線負結果收案（AUC 天花板 0.66，原理極限）；結論記於 changelog v2.33 |
| `extract_symbol_lib.py` | 自宣退役（2026-07-29）：CubiCasa 向量模板 3516 條 A/B 零貢獻已清出庫 |
| `training/scripts/README.md` | 內容過時（仍寫 18 支腳本/infer_cubicasa/scripts 舊路徑），併入本檔 |

留下的每一支都有現役用途：量測 6 支（eval_rooms_cc/eval_door_json/
eval_door_zones/eval_color_walls＋backend 兩支）、GT 工序 7 支
（make_annotation_drafts/fix_annotation_paths/sync_room_labels/fix_own_floor/
normalize_answer_svg/rebuild_room_gt/svg_poly）、重訓 3 支
（extract_room_crops/probe_room_classifier/probe_seg_head）、素材 3 支
（dxf2png_pieces/extract_asset_lib/probe_symbol_quality）、CubiCasa 補丁 1 支
（apply_cubicasa_patches）；`training/tests/` 32 支為管線回歸與工具測試。
