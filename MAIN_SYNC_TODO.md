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
`infer_cubicasa.py`（同 package）** → torch 載入 `ccmodel` 模型定義＋v5 權重推論。
main 的環境要補齊這條鏈：

| 需求 | 版本/來源 | 備註 |
| :--- | :--- | :--- |
| `torch` | CPU 版即可（cody 機以 2.13.0+cpu 實跑） | 只推論不訓練，無需 GPU |
| `opencv-python` | `>=4.10,<5` **必須鎖 <5** | 5.0 把 HoughLinesP 回傳 shape 改了，門偵測會掛 |
| `opencv-python-headless` | `<5` 同樣要鎖 | torch 生態會拉 headless 版蓋掉 cv2，同須擋 5.0 |
| `numpy` | `>=2.0` | main 應已有 |
| `ezdxf` | `>=1.3` | DXF 輸出 |
| `backend/floorplan/infer_cubicasa.py` | 已隨管線同目錄（2026-07-27 移入） | `ensure_cc_masks` 以 subprocess 呼叫，同 package 內 |
| `backend/floorplan/symbol_match.py` | 已隨管線同目錄（**硬依賴**） | `floorplan2room` 頂層 `import symbol_match`；模板庫 `backend/floorplan/symbol_lib.npz`（943 條、143KB）缺失時自動停用、不影響運作 |
| `backend/floorplan/ccmodel/` | 隨 repo（2 支 .py，約 29KB） | **2026-07-29 新增**，見下方說明 |

**不需要**帶去的：`lmdb`、`scikit-image`、`svgpathtools`——那是 CubiCasa loader／
訓練資料打包才用的，推論不碰。

### 5.1 推論鏈已與 `training/` 完全脫鉤（2026-07-29）

以往這條鏈要求部署端 checkout `training/CubiCasa5k/`（6.6G 目錄），因為
`infer_cubicasa.py` 得 `sys.path` 掛它、再 `os.chdir` 進去才載得到模型定義
（上游 `init_weights()` 寫死相對路徑 `floortrans/models/model_1427.pth`）。
現已改為：

| 項目 | 舊 | 新 |
| :--- | :--- | :--- |
| 模型定義 | `training/CubiCasa5k/floortrans/models/` | **`backend/floorplan/ccmodel/`**（2 支 .py，進版控） |
| `sys.path` / `chdir` | 掛 + 切進 `training/CubiCasa5k` | 皆已移除 |
| `model_1427.pth`（70MB） | 部署端必備 | **不再需要** |
| `apply_cubicasa_patches.py` | 列為部署步驟 | **已移至 `training/scripts/`，main 不必再跑** |

`model_1427.pth` 是 MPII 姿態估計預訓練權重，屬訓練起點；推論建完架構後
`load_state_dict(v5, strict=True)` 會把**全部 740 個參數張量**覆蓋掉。
已實測驗證：跳過 `init_weights` 與載入後再覆蓋，兩者參數逐張量完全相同
（0 個相異）。故 `get_model(..., pretrained=False)` 為推論預設。

套件名不叫 `floortrans`：`training/scripts/eval_rooms_cc.py` 等研發工具仍需原版
`floortrans.loaders` 解析 GT，同名會在 `sys.path` 上互相遮蔽。

**授權不變**：`ccmodel` 是 CubiCasa5k 原始碼衍生，CC BY-NC **禁商用**，
與 v5 權重的授權閘門一致。

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

---

## 2026-07-28 增補（回應《CODY 對接清單執行結果》交付）

main 已完成六項並推上 `origin/ben`（`20cfd21`）。以下是 cody 端對交付中三個未決事項的裁定與配套，
以及 main 需要的最後一步。

### 裁定 1：第 2 點的實作偏離——認可，契約照實修訂

main 實測「直接換入口」會讓幾何倒退（`builder_plan_630` 牆 28→0），改為
**幾何保留主線、房型語意由 `build_rooms(det)` 記憶體橋接疊加**（`recognize_cody_rooms()`
＋ `apply_floorplan2room_labels()`）。此偏離成立，第 2 點字面要求作廢，
以 main 的橋接介面為正式契約。`floorplan2room.process()` 維持腳本形狀不動。

### 裁定 2：權重下載——repo 維持私有，token 是正式管道，不公開 Release

GitHub Release 可見性跟隨 repo，無法單獨公開。`_resolve_weights_url()` 的
token 管道已於 2026-07-28 在 Linux 部署環境實測通過：**未設環境變數時
`_gh_token()` 會自動從 git 憑證系統撈到 clone 用的 PAT**，成功換得 S3 簽名鏈。
部署約定：能 clone 本 repo 的環境即具備下載條件；git 憑證非 HTTPS PAT 者
（如 SSH clone）須另設 `GITHUB_TOKEN` / `GH_TOKEN`。驗收條件 1 以此收口。

### 新增第 7 點：語意快取接上 cache_key（main 一行）＋來源驗證（cody 已供）

交付指出快取在產品路徑命中率為零（`analysis.py` 呼叫 `recognize_cody_rooms(image_bytes)`
未傳 `cache_key`），且盲目 `cv2.resize` 會讓同名不同圖靜默套錯房型（`floor10` 已實證）。
cody 端已完成配套（2026-07-28）：

- `floorplan2room.cc_cache_valid(cc_file, img_w, img_h, src_sha256=None)`：
  遮罩尺寸 ≠ 分析圖尺寸（容許彩圖管線 2 倍）即視為快取失效；新版快取帶
  `src_sha256` 時再做內容嚴格比對。`build_rooms` 已內建此檢查——**main 重新
  同步本檔後自動獲得保護，無需自己再驗**。
- `ensure_cc_masks` 改以 `_cc_stale` 判斷：快取與來源圖對不上會自動重推。
- `infer_cubicasa.py` 新產快取寫入 `src_sha256`；既有 137 份舊快取靠尺寸檢查把關。

main 剩最後一步：`analysis.py` 呼叫處改為
`recognize_cody_rooms(image_bytes, cache_key=Path(filename).stem)`
（`analyze_floorplan_image` 本來就收 `filename`）。

### 裁定 3：語意房型一律只填空、不覆蓋主線判斷

快取接通後 floor04 現形：CubiCasa 把七間投成 living×5/entry×2、信心 0.9–1.0，
而圖面文字標籤（DORMITORY/KITCHEN/DEPOSIT/…）證明主線圖示推論全對——模型在
美式線稿上會「自信地錯」，信心值不能當覆蓋依據。`apply_floorplan2room_labels`
改為不分來源一律只填 `type` 為空/default 的房間；main 的兩條覆蓋測試
（`test_labels_override_icon_fallback_*`、`test_true_semantics_may_overwrite_*`）
依此裁定反轉。

### 新增第 8 點（選配）：`CODY_LIVE_SEMANTIC=1` 就地推論

真實流量的上傳圖不會命中既有快取，語意要生效得現推。設 `CODY_LIVE_SEMANTIC=1`
後 `recognize_cody_rooms` 在快取缺失／來源不符時就地跑 CubiCasa 推論補快取
（阻塞請求約一分鐘，CPU；同一張圖只推一次）。與契約鍵衝突（同名不同圖）時
自動改用內容雜湊鍵，契約檔不被覆寫。預設關閉，行為與現行完全相同。

### 其餘交付事項的回覆

- **detect_doors 元組欄位**：cody 端定名為 `(cx, cy, width, score, ux, vy)`（現狀），
  main 的 `detect_door_swing_arcs` 接 `_door_geometry`／`write_arch_json` 前請對齊此序。
- **detect_color 彩色圖無門窗**：已知限制，暫不處理（幾何走主線，無產品影響）。
- **`.DS_Store`**：`.gitignore` 已補（2026-07-28）。
- **torch 現推鏈**：cody 端已於 Linux 環境端到端實測通過（含 `uv sync --extra semantic`、
  CubiCasa5k checkout、v5 權重推論、快取重推）。註：`infer_cubicasa.py` 在 scripts/
  解散重構後 chdir 路徑少一層目錄（`backend/training/CubiCasa5k`），已修復——
  main 若已同步該檔請一併帶回。

---

## 2026-07-29 收斂（Asset 模板工程結案；併入原 TODO_ASSET_SYMBOLS.md／TODO_ROOM_OCR.md）

換機到 Windows 原生環境後跑完 Asset 模板工程的全部斷點。**階段 A 完成、驗收零倒退，
但功能實際未生效**——原因不在權重也不在模板品質，在比對閘門。兩份 TODO 已刪除，
結論收在這裡。

### 1. 執行結果

- 環境：Windows 原生 `.venv` Python 3.12.10，套件版本與舊機 WSL 逐項相同
  （numpy 2.5.1 / torch 2.13.0+cpu / opencv 4.14 鎖 <5 / rapidocr 1.4.4）。
- 基準複驗與舊機 **零差異**：gt-seg 具名 114/157＝72.6%、端對端命中 107（70.9%）
  IoU 0.8975、門過濾 84/86＝98%。
- 階段 A 合併完成：CubiCasa 3516 條保留＋Asset 新增 **943** 條＝4459 條
  （bed 283／basin 116／chair 112／wc 92／kstove 82／ksink 73／sofa 58／
  dtable 51／tub 47／wardrobe 29；來源 1490 張 PNG，chamfer<0.6 去重 547 張）。
- 合併後重跑評測：**兩份報表與合併前逐字節相同**，具名率一分未動。

### 2. 根因：`symbol_match.HU_THR` 讓整套模板比對失效

`HU_THR = 0.15` 是 chamfer 驗證前的 Hu 矩粗篩。實測 Asset 模板的最佳 Hu 距離落在
**0.56 ~ 837**，差一至三個數量級，943 條模板無一進得了 chamfer 那關。

**這不是 Asset 專屬問題**：106 張圖全庫掃描，現行門檻下含原有 CubiCasa 系在內
總共只命中 **2 次**（sinkicon/stove 皆 0）。路線 B 的模板比對早已是死碼，
房型計分實際全靠 `detect_symbols` 的手寫幾何規則在撐；灌入 943 條模板才把它照出來。

成因是渲染路徑不同：CubiCasa 模板與查詢圖同走 `render_polylines` 向量渲染，Hu 幾乎一致；
Asset 模板走 `extract_asset_lib.png_to_template` 點陣化，Hu 必然拉開。

### 3. 放寬門檻是淨負面（已實測，勿再嘗試）

gt-seg／157 房／`CH_THR` 固定 2.0，只改 `HU_THR`：

| HU_THR | 具名 | Δ | kitchen R | **bath P** | bed R |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 0.15（現值） | 114 (72.6%) | — | 0.773 | **0.920** | 0.889 |
| 0.5 | 115 | +1 | 0.818 | 0.920 | 0.889 |
| 1.0 | 113 | −1 | 0.773 | 0.920 | 0.861 |
| 2.0 | 116 | +2 | 0.818 | 0.920 | 0.917 |
| 5.0 | 114 | 0 | 0.818 | **0.767** | 0.861 |
| ∞ | 113 | −1 | 0.818 | **0.676** | 0.833 |

總分在 113~116 間震盪像雜訊，拆逐類才看得出真相：`kitchen` recall 0.773→0.818
是**唯一穩定的真實增益**（kstove/ksink 的四口爐與雙槽圖案夠獨特）；代價是
`bath` precision **單調崩壞** 0.920→0.676，recall 完全沒動——不是漏抓，是大量
非浴室房間被誤標成 bath，與 basin/wc 假陽性數量（0→60→366→463）完全同步。

### 4. 模板品質分級（目視 + chamfer 天花板量測）

繞過 Hu、只用尺寸閘門＋chamfer≤1.2，36 張考卷的命中分布：

| kind | 命中 | 判定 |
| :--- | ---: | :--- |
| wardrobe | 55 | ❌ **假陽性大戶**——平面圖衣櫃＝長方形＋內部分隔線，與牆體剖面線／樓梯踏步幾何同構，本質不可分辨 |
| tub / basin / chair / sofa | 46/20/15/25 | ⚠️ 混雜，basin 是 bath precision 崩壞元凶之一 |
| kstove / ksink | 28/25 | ✅ 圖案獨特，證據可信，唯一值得啟用的兩類 |
| bed | 3 | ✅ 準但量太少（整床輪廓極少被切成單一 contour） |
| wc / dtable | 5/2 | — 量太少 |

`wardrobe` 55 個而 `bed` 只有 3 個——床遠比衣櫃常見，數字反過來本身就是誤判的證據。

另有一類假陽性是**圖面文字**：floor06 的「LNDRY」「BALCONY」字樣 chamfer 1.58/1.68
會被判成 ksink/sofa。

### 5. 要讓它生效該做什麼（未動工）

1. **文字抑制**——[`floorplan2room.detect_text_boxes()`](backend/floorplan/floorplan2room.py) 已存在，
   註解寫明用途就是「把文字墨水從細線層扣掉」，目前只用在門扇迴轉區、**沒接到符號比對**。
   接上去即可消除文字類假陽性。投報比最高的一刀。
2. **只啟用廚房系**——`kstove`／`ksink` 進計分，`wardrobe`／`chair`／`dtable` 關閉。
3. Hu 粗篩本身要換成對渲染路徑不敏感的指標（長寬比／填充率／輪廓數），
   而非調整全域門檻——第 3 節已證實調門檻只能同時放行真假兩者。

### 6. 「書房」結構上答不出來（新發現，與模板無關）

own_dataset 答案含 `Office` **7 間**，但映射鏈是：

```
model.svg class="Space Office"
  → rooms_selected["Office"] = 11        (CubiCasa house.py)
  → CC_ROOM_LABEL.get(11) = None         (floorplan2room.py:390，只映射 1/3/4/5/6/7/9/10)
  → norm_label(None) = "space"
```

`StairWell` 同樣是 id 11。**評分的 `space` 類實際是「書房＋樓梯間」混合桶**
（GT 14 ＝ Office 7 ＋ StairWell 7，與報表數字吻合），recall 僅 0.286。
且 `ASSET_KINDS` 沒有書桌／書櫃素材，模板庫對此毫無幫助。

要支援書房需整條鏈路新增類別：GT 映射 → `CC_ROOM_LABEL` → 計分規則 → 證據素材。

### 7. main 尚未履行的交代（第 7 點，仍未完成）

2026-07-29 查證 `origin/ben:backend/floorplan/vision/analysis.py:431`：

```python
cody_room_semantics = recognize_cody_rooms(image_bytes)   # 仍缺 cache_key
```

依上方第 7 點，此處應為 `recognize_cody_rooms(image_bytes, cache_key=Path(filename).stem)`。
**未改前語意快取在產品路徑命中率為零**，`cubicasa/room/*_mask.npz` 那 137 份快取形同虛設。

### 8. 換機提醒：`training/asset_ckpt/` 不在版控

`.gitignore` 的 `training/*` 涵蓋它，且無負向規則救回（對照：`door_lib.npz` 靠
`!training/*.npz` 留在版控內；`symbol_lib.npz` 已於本日移到 repo 根，見第 9 節）。
那 10 個檢查點只存在於本機磁碟。
換機後若要重建需重跑 1490 張 PNG 的模板化＋O(n²) chamfer 去重——即 2026-07-28
舊機當機的那段工作。素材（`testdata/Asset/` 1576 張）本身有版控，clone 即得。

`extract_asset_lib.py` 的分批續跑機制（`--ckpt-dir`／`--batch`／`--redo`）即為此而生：
每算完一類存檔即停，重跑同指令續算，十類齊全那次才合併寫入。

### 9. `symbol_lib.npz` 已移入 `backend/floorplan/`（2026-07-29）——main 需同步

原本放在 `training/` 純屬歷史位置，但它是**推論期資產**不是訓練產物：
產品進入點 `floorplan2room.process()` → `detect_symbols()` → `symbol_match.match_symbols()`
→ `load_lib()` 讀取。放在 `training/` 容易讓部署誤判為可略過。

| 項目 | 舊 | 新（**同日二次修正，以此為準**） |
| :--- | :--- | :--- |
| 檔案位置 | `training/symbol_lib.npz` | **`backend/floorplan/symbol_lib.npz`** |
| `symbol_match.LIB_PATH` | `dirname×3 + "training/symbol_lib.npz"` | `dirname(__file__) + "symbol_lib.npz"` |
| `extract_asset_lib.py --out` 預設 | `training/symbol_lib.npz` | `symbol_match.LIB_PATH`（引用，不再各自寫死） |
| `extract_symbol_lib.py --out` 預設 | `training/symbol_lib.npz` | 同上 |

`door_lib.npz` **維持在 `training/`**：它只被 `training/scripts/door_match.py`
消費，是研發工具的材料而非推論期資產，位置正確。

**先移到 repo 根、當日再移入 `backend/floorplan/` 的原因**：舊寫法
`LIB_PATH` 由模組位置往上三層推導，只搬 `backend/floorplan/` 而不保持 repo
目錄結構就會解析到錯路徑，而**找不到檔不會報錯**——`load_lib()` 回 `None`、
`match_symbols()` 回空清單、靜默停用。改成與消費模組同目錄後，`backend/floorplan/`
自成一個可獨立搬運的單位，此失效模式消失。已加測試釘住
（`test_symbol_match.py::test_lib_path_resolves_to_real_file`）。

### 10. 房型新增 `stair` 一類（2026-07-29，**當日修訂：`office` 已撤回**）

原本 `Office` 與 `StairWell` 在 CubiCasa 的 `rooms_selected` 都是 11(Undefined)，
評分的 `space` 是「書房＋樓梯間＋真未定義」混合桶（recall 0.286）。
本次拆解該混合桶，但**只新增 `stair` 一個 label**：

> **⚠ 給 main 的重點**：`rooms[].label` 只多出 `"stair"` 一個值。
> 曾短暫存在的 `"office"`（commit 7ca3b1dd）已於同日撤回併入 `storage`，
> 若已依舊版接了 office 請移除。

| 層 | 變更 |
| :--- | :--- |
| `ROOM_ZH_EX` / `ROOM_BGR_EX` | `stair`→「樓梯」＋疊圖色 |
| `EXTRA_LABELS` | 新常數 `("stair",)`：模型盲區類，score 以 0 分播種 |
| `OCR_WORD2LABEL` | STAIR(S)/STAIRWELL/STAIRCASE→stair；OFFICE/STUDY/WORKROOM/DEN/LIBRARY→**storage** |
| `detect_stairs()` | **新增**：踏板幾何偵測（層 4），≥4 條等距等長平行線 |
| `classify_rooms_cc` | `n["stair"]` → `score["stair"] += 0.6` |
| GT 側 `gt_label_of()` | `training/scripts/eval_rooms_cc.py`，塌陷前攔截具名 token；`Office`→`storage` |

**為什麼 `office` 撤回**：實測證明這個區分不帶資訊——DINOv2 裁切分類器在 72 房
上**從未把 office 與 storage 互相搞混**（三個相關錯誤全是跨家族的），合併前後
正確率完全相同（DINOv2 65/72、管線 57/72，逐類 recall 一分未動）。且書房沒有
專屬家具（桌椅書櫃全跟別的房型共用），證據層供不出分數，管線 office recall
恆為 0.000。`stair` 得以保留是因為踏板是樓梯獨有的圖案——**有專屬視覺特徵的
類別才立得住**。

標注資料同步：`testdata/Identify_ans/own_*` 的 9 個 `Space Office` 群組已改為
`Space Storage`（含底色 `#c9b458`→`#b8a06a` 與文字標籤），House 回讀 65/65 通過。

**驗收**（`--own-dir own_dataset --gt-seg`，24 圖／157 房，與 v2.18 基準同尺）：

| | 基準 | 本次 |
| :--- | ---: | ---: |
| 具名命中 | 114/157 = 72.6% | **117/157 = 74.5%** |
| `space` 混合桶 | n=14, recall 0.286 | **已解散**（n=0） |
| `stair` | — | n=7, recall 0.429, precision 0.75 |
| 舊八類 recall | — | **逐類完全未動**（zero regression） |

`office` 掛零已查明原因：那 7 張圖 OCR 只讀到 0~3 行雜訊（「这」「中」「区」），
圖面上沒有房名文字。不是詞彙表漏收，是證據來源在此評測集結構性缺席；
在美式文字標示線稿（floor04 那類）上才會生效。

### 11. 目錄職責界線（2026-07-29 使用者裁定）

| 目錄 | 放什麼 |
| :--- | :--- |
| `backend/floorplan/` | **辨識程式與其執行期所需的一切**（權重、模板庫、模型定義） |
| `temp/` | 辨識過程生成的檔（chk 疊圖、json 產物）——已在 `.gitignore` |
| `training/` | **只放訓練材料與研發工具**，交付給 main 的東西不得依賴此目錄 |

現況：`backend/` 對 `training/` 的功能性引用已歸零（僅剩註解說明沿革）。
例外一項，經裁定維持不動：`cubicasa/room/*_mask.npz` 雖是生成物，但它是
**預算好的交付資產**（main 的 `DEFAULT_CACHE_DIR` 寫死此路徑、進版控讓部署端
免 torch 免權重即可出結果），移入 `temp/` 會同時破壞跨分支契約與版控同步。

### 12. 模板比對閘門重構（2026-07-29）——main 無需動作，但要知道行為變了

`symbol_match` 的比對閘門由「尺寸 → Hu 粗篩(0.15) → chamfer(2.0)」改為
「文字抑制 → 尺寸 → chamfer(1.2)」。Hu 粗篩移除的理由是實測：12 張圖 2016 個
輪廓候選，過尺寸閘門 509 個，**過 Hu 者 0 個**——路線 B 一直是死碼。

| 項目 | 舊 | 新 |
| :--- | :--- | :--- |
| `HU_THR` | 0.15 | **已移除** |
| `CH_THR` | 2.0 | 1.2 |
| 啟用類別 | 全部 | `ENABLED_KINDS = ("kstove","ksink")`，可用 `SYMBOL_KINDS` 環境變數覆寫 |
| `symbol_lib.npz` | 4459 條 / 478KB | **943 條 / 143KB**（CubiCasa 向量系 3516 條 A/B 證實零貢獻，已剪除） |

**管線順序變更（若 main 自己組呼叫鏈需同步）**：`text_boxes` 必須先於
`detect_symbols` 計算，否則文字抑制拿到空清單。順序反了不報錯、只靜默失效。
`floorplan2room.process()` 已調整；`recognize_cody_rooms` 走的 `build_rooms`
不受影響（它吃已備妥的 `det`）。

效果：gt-seg 24 圖/157 房，具名 117→118，**kitchen recall 0.773→0.818**，
bath precision 0.920 不變，其餘七類逐項相同。

---

## 2026-07-30 重大變更：CubiCasa 血統整批移除

**這是本清單最大的一次變更，前面第 1/3/5/5.1 節的多數內容因此作廢。**

房型命名層由 CubiCasa 語意投票換成 DINOv2 凍結骨幹＋線性頭：
own_eval 72 房保留集 **79.2% → 90.3%**，且 DINOv2 程式碼與權重皆
**Apache 2.0 可商用**——v2.15 就記載的「CC BY-NC 禁商用」硬閘至此解除。

### main 端該做什麼

| 舊要求 | 現況 |
| :--- | :--- |
| 第 1 節 `DEFAULT_WEIGHTS` 指向 v5 | **作廢**，v5 權重已刪 |
| 第 3 節 v5 權重自動下載（Release + token） | **作廢**，整套下載鏈已刪 |
| 第 5.1 節 checkout `training/CubiCasa5k` | **作廢**，推論不再需要 |
| 第 5.1 節 跑 `apply_cubicasa_patches` | **作廢** |
| 「不變的契約」表中的語意快取 `cubicasa/room/` | **作廢**，目錄已刪 |
| 「不變的契約」表中的 `CC_WEIGHTS` 環境變數 | **作廢** |
| 第 7 節 `recognize_cody_rooms(cache_key=...)` | **作廢**（快取機制本身已不存在） |
| 第 8 節 `CODY_LIVE_SEMANTIC=1` 就地推論 | **作廢** |

### 新的部署需求

| 項目 | 說明 |
| :--- | :--- |
| `torch` | 由 semantic extra 升為**必要依賴**（CPU 版即可，只推論不訓練） |
| DINOv2 骨幹 88MB | `torch.hub` 首次下載後快取於 `~/.cache/torch/hub/`。**實測封鎖網路仍可載入**——非執行期連網需求。離線部署預先放好該快取，或設 `TORCH_HOME` |
| `backend/floorplan/room_head.npz` | 15KB 線性頭，**進版控**，clone 即得 |
| `ROOM_HEAD` 環境變數 | 可覆寫線性頭路徑（A/B 用） |

不再需要：200MB v5 權重、30MB 語意快取、`GITHUB_TOKEN`（權重下載用途）、
`training/CubiCasa5k/` checkout。

### 仍然不變的契約

| 項目 | 路徑/約定 |
| :--- | :--- |
| 前端交接座標 | cm、原點左下、y 向上（`"dxf_scale"` 鍵名保留） |
| `rooms[]` 欄位 | `label`／`label_zh`／`area_m2`／`bbox`／`cc_share`／`icons_cm2`／`adjacency` |
| `rooms[].label` 值域 | 9 類 ＋ `stair`；**無 `office`**（見第 10 節） |

`icons_cm2` 在新路徑恆為空 dict（來源是 CubiCasa 圖示通道，已移除），
契約鍵保留避免下游 KeyError。`cc_share` 仍是分數明細（鍵名沿用，
內容已是 DINOv2 機率＋證據層加分）。

### 缺件時的行為

DINOv2 不可用（缺 torch／骨幹／線性頭）→ 房型退回面積規則，品質明顯下降，
**且一定印警告**。不再有 CubiCasa 這一層中間 fallback。
