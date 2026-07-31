# ben 分支配合修改清單（cody-dev 合併對接）

> 2026-07-30 由 `cody-dev` 分支發起，取代同名舊檔（468 行、12 節）。
> **舊清單已結案**——`ben` 該做的六項都做完了，其餘因 CubiCasa 血統移除而作廢，
> 逐項結案狀態見第 6 節。本檔只寫**還沒做的事**與**判斷所需的證據**。

## 這份文件怎麼用

`cody-dev` 是以 `ben` 為基底、疊上 cody 辨識管線最新進度的分支。它**不是**單純
「cody 覆蓋 ben」——ben 的產品側改良全數保留，衝突逐處以「保留 ben 的產品能力、
採用 cody 的管線進展」為準則裁定，四處實際衝突見第 3 節。

審查順序建議：

1. 第 1 節看辨識率證據（可自行重跑，指令都列了）
2. 第 2 節看 cody-dev 帶來什麼
3. 第 3 節看四處衝突怎麼裁的——**這裡最需要 ben 端覆核**
4. 第 4 節是還要動手的事：4.1 ben 必做、4.2 三項建議、4.3 圖檔集收斂的知悉事項
5. 第 5 節是已知風險

**本檔的敘述時態**：所有「已完成／已改／已刪除」都是 `cody-dev` 當前提交的實際
狀態，可用 `git diff ben cody-dev` 逐項核對。尚未執行的事只出現在第 4.1／4.2 節，
且都明寫是留給 ben 的。

---

## 1. 辨識率證據（在 cody-dev 上實測，2026-07-30）

### 1.1 房型辨識：own_eval 72 房保留集

```bash
python training/scripts/eval_rooms_cc.py --own-eval --gt-seg
# 報表 → training/json/eval_rooms/report_own_gtseg.json（已隨分支提交）
```

實測輸出：

| 指標 | 數值 |
| :--- | ---: |
| 樣本 | 12 張／72 房，分割失敗 0 |
| 房間配對 | 72/72（過切率 1.00，平均 IoU **1.000**） |
| **房型命名正確** | **65/72 = 90.3%** |

逐類 P/R：kitchen 1.0/0.8、living 1.0/0.833、bed 0.909/1.0、bath 0.933/1.0、
entry 1.0/0.857、storage 0.667/0.5、outdoor 1.0/1.0、**stair 1.0/1.0**、
space 混合桶已解散（GT 0）。

**與什麼比？** cody 端記載的 CubiCasa 語意投票基準是同一批 GT 上的 **79.2%**，
即 +11.1pp。但要誠實說明一件事：

> ⚠ **這個 79.2% 無法在 ben 上重新量測**。`ben` 沒有任何評測工具
> （`training/` 整個被 `.gitignore` 排除，見第 2.3 節），且 CubiCasa 路徑要的
> 200MB v5 權重從未進版控、已於 7/30 刪除。所以 90.3% 是本次實測值，
> 79.2% 是引用 cody 的歷史記載，兩者不是同一次執行產生的對照。
> 若 ben 端要求可自證的 A/B，唯一可行做法是在 cody-dev 上以 `ROOM_HEAD`
> 覆寫成別的線性頭做同尺對照，CubiCasa 側已不具備可重跑條件。

### 1.2 幾何無倒退（驗證第 3 節的手工三方合併）

```bash
python backend/floorplan/eval_doors.py                    # 門過濾
python backend/floorplan/floorplan2dxf.py                 # 產 temp/chk/gray/
python backend/floorplan/eval_windows.py                  # 窗戶評分
```

| 項目 | cody 基準 | cody-dev 實測 | 判定 |
| :--- | :--- | :--- | :--- |
| 門過濾率 | 84/86 = 98% | **84/86 = 98%** | 一致 |
| 窗戶 P/R | 99%/94~95% | **98%/95%**（TP 127／FP 3／FN 6） | 一致範圍內 |
| 批次成功率 | — | **37/37 成功、0 失敗** | — |

> 批次數字是第 4.3 節圖檔收斂**之後**的 37 張圖檔集。門過濾與窗戶分數在刪除前後
> 逐項相同（刪除前批次為 44/44），因為被刪的圖本來就沒有人工答案、不參與計分。

### 1.3 裁定 1 的產品契約仍然成立

舊清單「裁定 1」記載 main 實測直接換入口會讓幾何倒退
（`builder_plan_630` 牆 28→0），故幾何保留主線、房型語意由記憶體橋接疊加。
本次在 cody-dev 上實跑該案例：

```
recognize_cody_geometry(builder_plan_630.png) → 牆 28  窗 2
recognize_cody_rooms(...)                     → room_label_source = "dinov2_semantic"
```

**牆 28 未變**，橋接契約完好。

附帶查證一件容易誤判的事：standalone `floorplan2dxf.py` 腳本對這張圖回報
「實心牆塊 0 個」——這在 **ben 原生分支上也是 0**（已用 worktree 實測），
是既有行為而非本次合併造成。28 面牆來自 `cody_adapter.recognize_cody_geometry()`
的 `paired_centerlines`／`hatch_normalized` 模式，那條路徑本次未改動。

### 1.4 測試

| 測試集 | 結果 |
| :--- | :--- |
| `pytest training/tests/`（cody 管線 107 支） | **107 passed** |
| `pytest tests/` 辨識相關 10 檔 | **79 passed / 2 skipped** |
| `pytest tests/` 全部 | 485 passed / 7 skipped / **92 failed** |

那 92 個失敗**全部**在 `test_scene_*.py`／`test_questionnaire_visual_catalog.py`／
`test_surface_material_processing.py`，失敗原因是 `FileNotFoundError` — 這些測試
`subprocess` 啟動 `node` 跑三維／前端邏輯，而本次執行環境沒有安裝 node。
已用 worktree 在**原始 ben** 上重跑 `test_scene_workflow.py`：同樣 15 failed / 2 passed，
數字與 cody-dev 完全相同 → 與本次合併無關。

> ⚠ **未驗證項**：ben 端請在有 node 的環境重跑這 92 支。理論上本次改動不觸及
> 任何 JS，但「理論上」不等於量過。

---

## 2. cody-dev 帶來什麼

700 檔變更（+394001／−8255）：新增 444、修改 45、刪除 210。絕大多數是評測測資，
程式碼實際只動 19 檔。

### 2.1 管線層（`backend/floorplan/`）

| 檔案 | 動作 |
| :--- | :--- |
| `floorplan2room.py` | 取 cody 版（+597/−232）。CubiCasa 語意投票 → DINOv2 裁切分類；新增 `stair` 類與 `detect_stairs()`；OCR 證據層；`_merge_nondoor_bridges`／`_bridge_has_door_ink` |
| `symbol_match.py` | 取 cody 版（+108/−39）。`HU_THR` 移除、`CH_THR` 2.0→1.2、新增 `ENABLED_KINDS = ("kstove","ksink")` |
| `floorplan2dxf.py` | **手工三方合併**，見第 3 節 |
| `floorplan2dxf_color.py`／`config*.ini`／`eval_*.py` | 取 cody 版（多為 `training/` → `temp/` 路徑改名） |
| `room_classifier.py` | **新增**。DINOv2 ViT-S/14 ＋ 線性頭推論；另加 `available()` 供產品端判斷來源 |
| `room_head.npz` | **新增**，15KB 線性頭，進版控 |
| `symbol_lib.npz` | **新增**，943 條模板庫。**舊清單第 9 點的欠項，本次補上**——ben 先前整個 repo 沒有這個檔，`load_lib()` 回 None、模板比對靜默停用 |
| `infer_cubicasa.py`／`apply_cubicasa_patches.py` | **刪除** |

### 2.2 產品層（ben 的地盤，已改到可運行）

| 檔案 | 改了什麼與為什麼 |
| :--- | :--- |
| `cody_adapter.py` | ①`_cc_path`／`_cc_ok` 已隨 CubiCasa 移除，原呼叫會 **AttributeError**，已改掉；②**補上 OCR 必須先於 `detect_symbols`**——ben 的呼叫鏈少了 `text_boxes`／`texts`，文字抑制與 OCR 證據層會靜默失效（不報錯）；③`label_source` → `dinov2_semantic` |
| `vision/cody_semantic.py` | **由 368 行重寫為 ~100 行**。整份是 CubiCasa 權重下載／遮罩快取／推論腳本管理，主體已不存在。保留唯一對外函式 `cody_semantic_room_labeler_status()`（`analysis.py:641` 消費），改回報 DINOv2 就緒狀態並宣告 `license: Apache-2.0` |
| `vision/analysis.py` | ①`room_label_source` 判斷字串三處改 `dinov2_semantic`；②**`CODY_ROOM_TYPE_MAP` 新增 `stair`**（舊清單第 10 點的產品側欠項），刻意映射為 `None`，理由見該處註解 |
| `requirements.txt`／`pyproject.toml` | 增補 `opencv-python-headless`（鎖 <5）、`svgpathtools`、`rapidocr-onnxruntime`；`semantic` extra 的說明改指 DINOv2。**ben 的全隊 baseline 完整保留**，見第 3 節 |
| `tests/` 5 支 | 見第 2.4 節 |

### 2.3 `.gitignore`：`training/` 加負向規則

ben 原本 `training/` 整個忽略，但 cody 的評測工具與 107 支測試都在
`training/scripts`／`training/tests`。少了它們，**第 1 節的 90.3% 在別台機器上
無法重跑**——證據不可重現等於沒有證據。故改為 cody 的寫法：

```
training/*
!training/scripts/    !training/tests/    !training/json/    !training/*.npz
```

同時移除三條指向已刪目錄的死規則（`cubicasa/room/*_cc.png`、`cubicasa/room_ft/`、
`/cubicasa5k.zip`）與「語意快取 `cubicasa/` npz 進版控供雙機同步」這句已作廢的說明。

### 2.4 測試改動（5 支，逐項有理由）

| 測試 | 改動 |
| :--- | :--- |
| `test_cody_semantic_status.py` | **重寫**。原 15 支測權重下載／SHA-256 校驗／token 換簽名／遮罩欄位驗證／subprocess 推論，機制全部不存在。新版 7 支專測狀態回報誠實性（含 `ROOM_HEAD` 覆寫、覆寫指向空檔、授權欄位） |
| `test_floorplan2room_paths.py` | **重寫但保留意圖**。原測 `CC_WEIGHTS`／`CC_CACHE_DIR` 不得依賴 cwd；那兩個常數沒了，**但失效模式沒消失只是換主角**——改測 `room_classifier.HEAD_PATH` 與 `symbol_match.LIB_PATH`，並加「檔案真的在」的斷言（兩者缺檔都是靜默停用） |
| `test_semantic_cache_alignment.py` | 移除 3 支 `_cc_ok` 測試（遮罩快取機制已不存在，DINOv2 無快取層故不需替代）；其餘 6 支保留，新增 `stair` 映射斷言 |
| `test_cody_pipeline_modules.py` | 模組清單 `apply_cubicasa_patches` → `room_classifier`；進入點斷言改鎖 `detect_room_text`／`detect_text_boxes`（釘住第 2.2 節的順序陷阱） |
| `test_cody_room_recognition.py` | `cubicasa_semantic` → `dinov2_semantic`（3 處） |

---

## 3. 四處衝突的裁定——**請 ben 端覆核**

裁定準則：**保留 ben 的產品能力，採用 cody 的管線進展**。

### 3.1 `floorplan2dxf.py`：取 cody 版後回植 ben 三處

直接拿 cody 版覆蓋會刪掉 ben 獨有的產品側改良。已逐處回植：

| ben 獨有 | 為什麼必須留 | 處理 |
| :--- | :--- | :--- |
| `detect_door_swing_arcs()` 104 行 | 單葉門＋四分之一迴轉弧偵測，builder plan 專用。舊清單自己提過要對齊它的元組序 | **逐行還原**（已比對與 ben 版 104 行完全相同） |
| `load_gray` 用 `np.fromfile`＋`imdecode` | cody 是 `cv2.imread`，走 C 層 fopen，**Windows 上中文路徑直接回 None**。產品端上傳檔名不可控 | 還原並補註解說明原因 |
| `detect_doors` 的 OpenCV 5 reshape | cody 是 `segs[:, 0]`，OpenCV 5 回 shape 改變會掛。鎖 `<5` 是防線，這是安全網 | 還原 |

cody 側保留的：`derive_wall_T()`（磨牆害徵防護，floor13 實案 T=30 撐爆使下半牆全滅）
與 `training/` → `temp/` 路徑改名。

三者皆為行為中性或純新增，理論上不改變幾何輸出；第 1.2／1.3 節的實測數字證實了這點。

### 3.2 `requirements.txt`：增補而非取代

ben 的是**全隊 baseline**（shapely／fastapi／uvicorn／selenium／SQLAlchemy／
psycopg2…），cody 的只有管線那幾個。**若直接取 cody 版會刪掉整個產品與型錄的依賴**。
已改為在 ben 的檔案上增補辨識端所需，原有 pin 一律不動。

### 3.3 `cubicasa/` 209 檔快取：刪除

含 173 個 `.npz` ＋ 36 個 `.png`，分 `color/`／`gray/`／`room/`。消費者
（`_cc_ok`／`ensure_cc_masks`／`infer_cubicasa.py`）全數移除，且 CC BY-NC 禁商用。
連同 `.gitignore` 的相關規則一併清除。

### 3.4 cody 的 `Readme.md` 未帶入

cody 的 `Readme.md`（85KB，全是 cody 的 changelog）與 ben 的 `README.md`（9.6KB）
**在 Windows 上大小寫衝突**（同一個檔名），無法共存。cody 的變更史未併入本分支，
需要時請從 `cody` 分支查閱。

---

## 4. ben 端還要做的事

### 4.1 必做

- [ ] **重新產生 `uv.lock`**。`pyproject.toml` 的 `vision` extra 已增補
      `svgpathtools`／`rapidocr-onnxruntime`，lock 檔未同步（本機無法可靠執行
      `uv lock`，留給 ben）。
- [ ] **在有 node 的環境重跑 `pytest tests/`**，確認第 1.4 節那 92 支恢復原狀。
- [ ] **部署端備妥 DINOv2 骨幹快取**。88MB，`torch.hub` 首次下載後存於
      `~/.cache/torch/hub/`。實測封鎖網路仍可載入，**非執行期連網需求**；
      離線部署預先放好該快取或設 `TORCH_HOME`。

### 4.2 三項建議（附理由與建議做法，最終由 ben 拍板）

#### 建議 1：torch 列為**辨識服務端的必要依賴**——它在產品執行路徑上

先釐清一件常被誤會的事：**torch 不是只有驗證才需要**。呼叫鏈全在 HTTP 請求裡：

```
vision/analysis.py:530   recognize_cody_rooms(image_bytes, cache_key=...)
  → cody_adapter.py       build_rooms(detection)
  → floorplan2room.py:852 room_classifier.classify(det["bgr"], labels, rooms)
  → room_classifier.py    import torch
```

缺 torch 不會崩（`classify()` 回 `None`、退回面積規則），但**房型品質從 90.3%
掉回純幾何猜測的水準，且一定印警告**。既然 cody 分支執行辨識就必須有它，
合併後同樣必須有。

**建議做法**（兼顧只做前端／catalog 的隊員不必背 2GB）：

- `pyproject.toml` 的 `semantic` extra **維持獨立**，不強迫全隊安裝
- 但**任何要提供房型辨識的部署環境視為必裝**，寫進 README 部署章節
- `requirements.txt` 目前以註解記錄此點、未加 pin。若 ben 認同「凡執行辨識即必要」，
  就把 `torch==2.13.0` 移進 baseline；反之維持現狀即可，程式行為不變

#### 建議 2：兩個 OCR 引擎——短期保留、中期收斂到 `rapidocr`

兩者服務不同層，目前可共存：

| 引擎 | 位置 | 用途 |
| :--- | :--- | :--- |
| `rapidocr-onnxruntime` | `floorplan2room` 層 5 | 房型文字證據（圖面印的 KITCHEN/DORMITORY…） |
| `paddleocr` | `vision/ocr.py` | 產品側印刷房名 `ocr_room_label`（覆蓋優先序最高） |

**建議中期收斂到 `rapidocr`**：純 pip／CPU、免系統套件（cody 當初捨 tesseract 正是
因為它需要 apt），而 paddle 體積大且平台相依。短期不動——paddle 本來就在獨立的
`requirements-ocr.txt`、不進預設環境，沒有立即成本。

#### 建議 3：前端新增 `stair` 契約鍵，比照 `circulation` 零家具處理

`rooms[].label` 新增 `"stair"`（own_eval **P=1.0／R=1.0**，是本次表現最好的類別
之一）。產品語意是**不可擺設**（v2.14 使用者裁決的硬需求）。

目前 `CODY_ROOM_TYPE_MAP["stair"] = None`：主線契約詞彙沒有對應鍵，硬塞
`circulation` 會被下游當成可佈置走道。**建議**在前端推薦表（`scene_layout2d.js`）
新增 `stair` 鍵並設為零家具——`circulation` 已經是這樣處理的，模式現成。
改完把映射由 `None` 改指 `"stair"` 即可，一行。

### 4.3 floor 圖檔集已收斂到 `Identify_ans/`——ben 端請知悉刪除範圍

**規則（使用者裁定）**：`floor*.png` 一律以 `testdata/Identify_ans/` 的人工答案集
為準，沒有對應答案的圖一律刪除。理由是答案集才是「這張圖算不算分」的唯一依據，
留著無答案的圖只會讓後續有人以為它在評測範圍內。

**已刪除 58 檔**：

| 目錄 | 已刪除 | 為什麼沒有答案 |
| :--- | :--- | :--- |
| `testdata/png/` | floor10、11、14、16、17、18、21（7 張） | 見下表逐張理由 |
| `testdata/color_png/` | color_floor_11（1 張） | 彩色答案集 28 張中無它 |
| `testdata/dxf/` | 上述 8 張的 `.dxf` 輸出 | 來源圖已刪，輸出成孤兒 |
| `testdata/pngans/` | ben 的舊答案目錄（21 檔） | 已被 `Identify_ans/pngans/gray/`（37 張）取代；`eval_windows.py` 預設早已指向新路徑 |
| `testdata/chk/` | ben 提交的疊圖（21 檔） | cody 起疊圖寫入 `temp/`（已 gitignore），版控裡的是過時產物 |

刪除前已驗證無程式碼引用那兩個目錄：`pngans` 的消費者（`eval_windows.py`、
`eval_color_walls.py`、`score_compare.py`）全指向 `Identify_ans/`，`chk` 全指向 `temp/`。

**刪除後重跑，分數零變動**（證實被刪的圖本來就不參與計分）：

| 項目 | 刪除前 | 刪除後 |
| :--- | :--- | :--- |
| 門過濾率 | 84/86 = 98% | **84/86 = 98%**（相同） |
| 窗戶 P/R | 98%/95%（TP 127／FP 3／FN 6） | **98%/95%（TP 127／FP 3／FN 6，逐項相同）** |
| 灰階批次 | 44/44 成功 | **37/37 成功、0 失敗** |

逐張理由（依據 `docs/CODY_PIPELINE_README.md:378` 與 `:99`）：

| 圖 | 原屬 | 理由 |
| :--- | :--- | :--- |
| floor10 | 兩邊都有 | 與 floor38 像素級相同；**答案與重複對矛盾，確認標錯後已刪除**（2026/7/13），以 floor38 計分 |
| floor14 | ben 獨有 | 與 floor61 像素級相同，同上，以 floor61 計分 |
| floor16 | ben 獨有 | 與 floor46 像素級相同，而 floor46 屬 own_wip 淘汰 5 題 |
| floor17 | ben 獨有 | **own_wip 定案淘汰 5 題之一**（floor17/24/30/34/46） |
| floor18 | ben 獨有 | 與 floor54 像素級相同，以 floor54 計分 |
| floor11、floor21 | ben 獨有 | cody 答案集無此二題，亦無重複對應記載 |

**明確保留**（使用者確認）`testdata/png/builder_plan_630.png` 與其
`_annotations.json`：它不是 `floor*.png`，是 ben 裁定 1 的產品測試案例
（第 1.3 節用它驗證牆 28 未變）。

> ⚠ **一項先前判斷的更正**：本檔早先的草稿曾說 floor11/14/18/21「無人工答案」，
> 那是只查了 `Identify_ans/` 的結論。實際上 **ben 的 `testdata/pngans/` 裡有
> 這些圖的答案**——只是那是被 `Identify_ans/` 取代的舊答案集，且 cody 已判定
> 其中 floor10／floor14 兩張標錯並刪除對應答案。刪除整個舊答案目錄正是為了
> 消除兩套答案集並存的歧義。

**cody 端待清理（不在本分支處理，屬 cody 自己的既有狀態）**：
`testdata/dxf/` 仍有 floor24／30／34／46／49 五個 `.dxf`，其來源 png 在 cody 上
本來就不存在（24/30/34/46 是 own_wip 淘汰題；floor49 是 floor12 的重複對，
答案存在其名下但無獨立圖檔）。另有 ben 獨有的 `floor01_center.dxf`／
`floor01_outline.dxf` 兩個衍生輸出，floor01 本身有答案故保留，但用途需 ben 確認。

---

## 5. 已知風險

| 風險 | 說明 |
| :--- | :--- |
| `storage` 類偏弱 | own_eval P=0.667／R=0.5（GT 僅 4 間，樣本太少）。曾短暫存在的 `office` 已於 7/29 撤回併入 `storage`——實測 DINOv2 從未把兩者互相搞混，且書房無專屬家具、證據層供不出分數 |
| `kitchen` recall 0.8 | 10 間中 2 間被判為 `space`。cody 端記載命名層後處理曾誤傷真廚房，已於 `c7d44c28` 修正 |
| 缺件時明顯降級 | 缺 torch／骨幹／線性頭 → 房型退回面積規則，**一定印警告**。不再有 CubiCasa 這層中間 fallback |
| `room_classifier.available()` 是 cody-dev 新增 | 為讓產品端能誠實標示 `room_label_source` 而加在 cody 的檔案上。cody 分支尚無此函式，回併 cody 時需帶回，否則兩邊 `room_classifier.py` 分岔 |

---

## 6. 舊清單結案狀態

| 節 | 項目 | 結案 |
| :-- | :--- | :--- |
| §1 | `DEFAULT_WEIGHTS` 指向 v5 | ben 已完成 → 因 v5 刪除而**作廢** |
| §2 | 預設入口改 `floorplan2room` | ben 已完成（裁定 1 的橋接介面），**契約延續**，見第 1.3 節 |
| §3 | 權重自動下載鏈 | ben 已完成 → **作廢**，整套下載鏈與 `GITHUB_TOKEN` 需求消失 |
| §4 | 更新 `test_cody_semantic_status.py` | ben 已完成 → 本次**重寫**，見第 2.4 節 |
| §5 | 環境與依賴（torch／opencv 鎖 <5） | ben 已完成，`opencv-python-headless<5` 的鎖仍然必要 |
| §5.1 | `ccmodel/` 與 `training/` 脫鉤 | ben 未做 → **作廢**，CubiCasa 模型定義已不需要 |
| §6 | door 評測集改 `testdata/Asset/door` | ben 已完成 |
| §7 | `analysis.py` 傳 `cache_key` | ben 已完成（`_semantic_cache_key`）。快取機制已作廢，但**該參數仍有用**——它決定暫存圖與 OCR 單格快取的命名，故保留 |
| §8 | `CODY_LIVE_SEMANTIC=1` 就地推論 | ben 未做 → **作廢**，DINOv2 本來就是現推，無快取概念 |
| §9 | `symbol_lib.npz` 移入 `backend/floorplan/` | ben 未做 → **本次由 cody-dev 補上**（含檔案本身） |
| §10 | 房型新增 `stair`（`office` 已撤回） | ben 未做 → **本次補上產品側映射**，前端契約鍵見第 4.2 節決定 3 |
| §11 | 目錄職責界線 | 延續。`temp/` 收辨識過程產物（已在 `.gitignore`）；`training/` 只放研發工具，但**負向規則已放行 scripts／tests／json**，見第 2.3 節 |
| §12 | `symbol_match` 閘門重構 | ben 未做 → **本次隨檔案取用完成**（`HU_THR` 移除、`CH_THR` 1.2、`ENABLED_KINDS`） |

## 7. 不變的契約

| 項目 | 路徑/約定 |
| :--- | :--- |
| 前端交接座標 | cm、原點左下、y 向上（`"dxf_scale"` 鍵名保留） |
| `rooms[]` 欄位 | `label`／`label_zh`／`area_m2`／`bbox`／`cc_share`／`icons_cm2`／`adjacency` |
| `rooms[].label` 值域 | 9 類 ＋ `stair`；**無 `office`** |
| 幾何主線 | `recognize_cody_geometry()`，房型語意只疊加不取代（裁定 1） |
| 房型只填空不覆蓋 | 不分來源一律只填 `type` 為空/default 的房間（裁定 3） |
| 權重覆蓋 | `ROOM_HEAD` 環境變數（取代已作廢的 `CC_WEIGHTS`／`CC_CACHE_DIR`） |
| 授權 | DINOv2 程式碼與權重皆 **Apache 2.0 可商用**。CC BY-NC 禁商用的硬閘至此解除 |

`icons_cm2` 在新路徑恆為空 dict（來源是 CubiCasa 圖示通道，已移除），契約鍵保留
避免下游 KeyError。`cc_share` 仍是分數明細（鍵名沿用，內容已是 DINOv2 機率＋
證據層加分）。
