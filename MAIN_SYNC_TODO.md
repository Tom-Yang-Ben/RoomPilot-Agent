# main 分支配合修改清單（cody 結構調整對接）

> 2026-07-27 由 cody 分支發起。cody 已將管線移入 `backend/floorplan/`（與 main 同路徑），
> 以下是 main（含 bella，目前同 commit）需要配合修改的項目，完成後兩邊即可直接 diff 同步。

## 1. `cody_semantic.py` 權重預設路徑改指 backend/floorplan/ 的 v5

**檔案**：`backend/floorplan/vision/cody_semantic.py`

```python
# 現況
DEFAULT_WEIGHTS = Path("training/model_best_val_loss_var.pkl")   # CubiCasa5k 底模，非現役權重

# 改成
DEFAULT_WEIGHTS = Path("backend/floorplan/model_finetuned_v5.pkl")   # cody v5 微調權重（2026-07-25 起現役）
```

- `model_best_val_loss_var.pkl` 只是訓練起點的底模；cody 這邊 7/25 已把預設切到
  own 域驗收勝出的 **v5 微調權重**，main 的可用性檢查還停在舊檔名，會造成
  「檔在卻報 missing」或「用舊底模推論」兩種脫節。
- `DEFAULT_CACHE_DIR = Path("cubicasa/room")` **維持不變**（跨分支契約路徑）。
- `CC_WEIGHTS` 環境變數覆蓋機制維持不變。

## 2. 預設入口從 floorplan2dxf 改為 floorplan2room

**檔案**：`backend/floorplan/cody_adapter.py`（`from . import floorplan2dxf as cody`）
與 `backend/floorplan/vision/analysis.py:294`（`recognize_cody_geometry(...)`）

- 現況：main 只呼叫 `floorplan2dxf`（牆/窗/門幾何），房型另靠 icon/zone 規則 fallback。
- 改成：預設走 **`floorplan2room`** —— 它內部串好完整鏈路
  （灰階/彩色自動判別 → `floorplan2dxf`／`floorplan2dxf_color` → 房間切割 → CubiCasa 語意投票），
  一次拿到幾何＋房型（`rooms[]`：`label`／`label_zh`／`area_m2`／`bbox`／`cc_share`／`icons_cm2`，
  以及 `adjacency`），等同 cody 端 `json/room/*_room.json` 的內容改為記憶體回傳。
- 權重／快取缺失時 `floorplan2room` 會自動下載（見第 3 點）；完全離線時再退回
  現有 `django_icon_zone_rules` fallback，行為向下相容。

## 3. 權重自動下載：預設抓 v5、放到 backend/floorplan/

- cody 端 `backend/floorplan/floorplan2room.py` 已有 `_ensure_cc_weights()`：
  缺檔時從本 repo GitHub Release 自動下載＋SHA-256 校驗
  （`releases/download/weights-v5/model_finetuned_v5.pkl`，200MB 超過 100MB 限制故不進版控）。
- main 需把這套機制帶過去，並將**下載目的地與預設讀取路徑統一為
  `backend/floorplan/model_finetuned_v5.pkl`**（與第 1 點的 `DEFAULT_WEIGHTS` 一致）。
- cody 端配合項（**已完成 2026-07-27**）：`floorplan2room.py` 的 `CC_WEIGHTS` 預設
  已改為 `backend/floorplan/model_finetuned_v5.pkl`（權重檔已就位、.gitignore 已涵蓋），
  兩邊路徑約定一致。

## 4. 更新 `tests/test_cody_semantic_status.py`

**檔案**：`tests/test_cody_semantic_status.py`（main 自己的測試，斷言寫死了舊預設）

- 現況：以 `training/model_best_val_loss_var.pkl` 為預設權重路徑做斷言
  （含 `status["reason"] == "missing_cody_cubicasa_weights_or_cache"` 的缺檔情境、
  `tmp_path / "cubicasa" / "room"` 的快取情境）。
- 第 1 點把 `DEFAULT_WEIGHTS` 改成 `backend/floorplan/model_finetuned_v5.pkl` 後，
  這支測試會直接失敗，需同步更新：
  - 缺檔情境的預期 `weights_path` 改指新預設路徑
  - 有權重情境的假檔改放 `tmp_path / "backend" / "floorplan" / "model_finetuned_v5.pkl"`
  - 快取情境（`cubicasa/room`）**維持不變**——該路徑是不動契約
- 若依第 3 點引入自動下載，測試中須 mock 下載（斷網情境不可觸發真實下載）。

## 5. 環境與依賴（pyproject / uv.lock 需新增）

語意路徑的完整執行鏈：`floorplan2room` → `ensure_cc_masks()` → **subprocess 呼叫
`scripts/infer_cubicasa.py`** → torch 載入 floortrans 模型定義＋v5 權重推論。
main 的環境要補齊這條鏈：

| 需求 | 版本/來源 | 備註 |
| :--- | :--- | :--- |
| `torch` | CPU 版即可（cody 機以 2.13.0+cpu 實跑） | 只推論不訓練，無需 GPU |
| `opencv-python` | `>=4.10,<5` **必須鎖 <5** | 5.0 把 HoughLinesP 回傳 shape 改了，門偵測會掛 |
| `opencv-python-headless` | `<5` 同樣要鎖 | torch 生態會拉 headless 版蓋掉 cv2，同須擋 5.0 |
| `numpy` | `>=2.0` | main 應已有 |
| `ezdxf` | `>=1.3` | DXF 輸出 |
| `scripts/infer_cubicasa.py` | 隨管線帶過去 | `ensure_cc_masks` 以 subprocess 呼叫，路徑基準 `_SCRIPTS_DIR` |
| `scripts/symbol_match.py` | 隨管線帶過去（**硬依賴**） | `floorplan2room` 頂層 `import symbol_match`，缺檔直接 ImportError；模板庫 `training/symbol_lib.npz` 缺失時自動停用、不影響運作 |
| `scripts/apply_cubicasa_patches.py` | 部署時跑一次 | CubiCasa5k 程式庫的 numpy 2.x 相容補丁，checkout 後執行 |
| floortrans 模型定義 | `training/CubiCasa5k/` 原始碼 checkout | 只用模型定義、不用其 loader；**CC BY-NC** |

**不需要**帶去的：`lmdb`、`scikit-image`、`svgpathtools`——那是 CubiCasa loader／
訓練資料打包才用的，推論不碰。

已知樓層可靠 `cubicasa/room/*_mask.npz` 快取直接出結果（免權重、免 torch）；
只有遇到**新圖**要現推語意時才走上面整條鏈。

## 6. door 樣式評測集改讀 `testdata/Asset/door/`

**檔案**：`backend/floorplan/eval_doors.py`（main 版預設 `testdata/door`）

- main 目前的 `testdata/door/` 是 19 張舊快照（`door_typeXX` 命名，已過時）。
- cody 端評測集已重整為 **`testdata/Asset/door/` 共 86 張**（`door_001–086`，
  含舊 19 張＋DXF 切圖新素材），門過濾現行基準 **84/86 = 98%**；
  2 張已知困難樣本 `door_001`、`door_007`（多線門扇板與窗符號幾何同構，勿硬擋）。
- main 需把 `eval_doors.py` 預設 door 目錄改為 `testdata/Asset/door`，
  並以 cody 的 86 張集取代舊 `testdata/door/`。
- 週邊素材同層搬遷：`testdata/Asset/` 下另有 `bathroom/{Tub,WC,Washbasin}`、
  `kitchen/dinner_table`（皆為「目錄名_三位數序號」命名），main 若引用照此路徑。

## 不變的契約（提醒，勿動）

| 項目 | 路徑/約定 |
| :--- | :--- |
| 語意快取 | `cubicasa/room/*_mask.npz` |
| 前端交接座標 | cm、原點左下、y 向上（`"dxf_scale"` 鍵名保留） |
| 權重覆蓋 | `CC_WEIGHTS` 環境變數 |
| 授權硬閘 | CubiCasa5k 權重 CC BY-NC **禁商用**——v5 是其微調衍生物，隨權重供給一併適用 |

## 驗收

- [ ] clone main 後首跑自動下載 v5 到 `backend/floorplan/`，`cody_semantic_room_labeler_status()` 回報 available
- [ ] 上傳平面圖 API 回傳含房型（`rooms[].label` 非 fallback 來源）
- [ ] 離線環境（無權重、無快取）仍能以 `django_icon_zone_rules` 完成分析
- [ ] `tests/test_cody_semantic_status.py` 更新後全綠（見第 4 點）
