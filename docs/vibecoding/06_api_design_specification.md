# API 設計規範 - RoomPilot-Agent（CLI 與資料契約規範）

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿 | **OpenAPI 定義:** N/A（無 HTTP API，見下方轉寫說明）

---

## 轉寫說明（為何本文件不是 REST API 規範）

RoomPilot-Agent 是**純 Python CLI 專案**：無 Web 後端、無資料庫、無 REST API。模組之間與上下游系統之間的「介面」由三種契約構成：

1. **CLI 契約** — 各入口腳本的參數、預設值與輸出位置（對應模板的「API 端點定義」）
2. **設定檔與環境變數契約** — `config.ini`、`config_color.ini`、`CC_WEIGHTS`/`CC_CACHE_DIR`/`GITHUB_TOKEN`（對應「認證與通用行為」）
3. **輸出格式契約** — DXF 圖層、`json/` 各子目錄 JSON schema、`cubicasa/room/*.npz` 語意快取（對應「資料模型」）

因此本文件依模板精神轉寫為「CLI 與資料契約規範」，**保留模板章節架構**，各節標明原模板概念在本專案的對應物。模板中確實無對應物的項目標 N/A 並附理由。

系統整體架構見 [./05_architecture_and_design_document.md](./05_architecture_and_design_document.md)；模組內部規格見 [./07_module_specification_and_tests.md](./07_module_specification_and_tests.md)。

---

## 1. 設計約定

| 項目 | 規範 |
| :--- | :--- |
| **風格** | CLI（argparse / `sys.argv`），一腳本一職責；REST 資源路徑 → N/A，對應物是「一支腳本＝一個入口」 |
| **Base URL** | N/A（無 HTTP 服務）。對應物：**工作目錄一律為專案根** `~/RoomPilot-Agent/`，所有預設路徑（`png/`、`dxf_scale/`、`json/`…）皆相對於專案根 |
| **呼叫格式** | `python3 scripts/<腳本>.py [位置參數] [--選項]`；根目錄入口為 `python3 floorplan2room.py`、`python3 cabinet_designer.py` |
| **輸入格式** | 影像：PNG / JPG / JPEG / BMP（`IMG_EXTS`，alpha 圖層自動合成白底） |
| **輸出格式** | DXF（ezdxf，公分單位 `insunits=5`）、JSON（UTF-8、`ensure_ascii=False`、`indent=2`）、PNG 檢核圖、`.npz`（`np.savez_compressed`） |
| **欄位命名** | JSON 欄位一律 `snake_case`（`cm_per_px`、`score_fused`、`has_door`…） |
| **座標系（全 repo 鐵律）** | **px**：影像座標，原點左上、y 向下（疊回原圖用）；**cm**：實體座標，原點左下、y 向上（與 `dxf_scale/` DXF 完全一致）。定義見 `json/README.md` |
| **日期格式** | N/A（輸出無時間戳欄位）。對應物：版本追溯靠 git commit 與 `json/eval_rooms/report_*_ft_v{N}.json` 檔名快照 |
| **認證** | N/A（無使用者認證）。對應物：私有 GitHub Release 權重下載需 `GITHUB_TOKEN`（見 §4、§6.2） |
| **版本控制** | 權重：GitHub Release tag `weights-v5`＋SHA-256 校驗；程式：分支即機器（main/cody/bella/ben/ancai/django/kai-dev），經 main PR 匯流；依賴：`requirements.txt` 鎖 `opencv-python>=4.10,<5` |

---

## 2. 通用行為

### 2.1 批次 / 單張雙模式（對應模板「分頁」）

游標分頁 N/A（無列表 API）。對應物：主管線與評測腳本都支援「不帶參數＝全量批次、帶名稱＝限定子集」：

- `floorplan2dxf.py`：不帶參數批次 `png/*.png`；給檔名跑單張（只寫檔名會自動去 `png/` 找）；給目錄批次該目錄
- `floorplan2dxf_color.py`：同上，預設目錄 `color_png/`
- `floorplan2room.py`：`python floorplan2room.py [輸入圖檔或目錄] [輸出目錄]`，預設 `png/` → `training/chk/room/`
- 評測腳本（`eval_color_walls.py`、`eval_cc_masks.py`、`door_match.py`、`door_propose.py`）：位置參數 `names`（`nargs="*"`，如 `color_floor_01`）限定圖名，不給就全部

### 2.2 排序 / 過濾

N/A（無查詢 API）。對應物：§2.1 的 `names` 位置參數，以及 `eval_rooms_cc.py` 的樣本抽樣參數 `--n-test`（預設 40）、`--n-val`（預設 30）、`--smoke N`（冒煙小樣本）。

### 2.3 參數自動推導（換圖免改的契約）

兩條向量化管線的像素類參數**留空即依自動牆厚 T 推導**（`T = 2 × distanceTransform 最大值`）：

| 參數 | 留空時的預設 |
| :--- | :--- |
| `solid`（去細線核） | ≈ 0.35×T |
| `h_len` / `v_len`（牆最短長度） | ≈ 1.5×T（一定 > 牆厚） |
| `snap` | ≈ 0.6×T |
| `gap` | ≈ 0.4×T |
| `min_len` | ≈ 1.0×T |

這是設定檔契約的一部分：**換任何解析度的圖都不需改 config**；要鎖死行為才填數字。

### 2.4 冪等性

`Idempotency-Key` N/A。對應物（皆可重複執行、結果一致）：

- **語意快取**：`floorplan2room.py` 逐圖查 `cubicasa/room/<名>_mask.npz`，快取命中即跳過 CNN 推論（CPU 約 1 分/張，快取讓重跑成本趨近零）。換權重後須全量重算快取（v5 已重算）
- **權重下載**：`_ensure_cc_weights()` 先寫 `<檔名>.part`、SHA-256 校驗通過才 `os.replace` 原子改名——中斷重跑不留半成品
- **補丁腳本**：`apply_cubicasa_patches.py` 已補丁自動跳過，可重複執行
- **標注修復**：`fix_annotation_paths.py --check`、`sync_room_labels.py --dry-run`、`rebuild_room_gt.py --check`、`fix_own_floor.py --dry-run` 皆提供「只掃描不寫檔」模式

### 2.5 評測守門（本專案特有的「變更前契約」）

改動 `chk/`、`dxf/` 邏輯前**必先跑 `scripts/eval_windows.py` 對 `Identify_ans/pngans/` 評分**，不得退化後覆蓋。彩色管線對應 `eval_color_walls.py`，房型對應 `eval_rooms_cc.py`。此鐵律見 [./01_workflow_manual.md](./01_workflow_manual.md) 與專案記憶。

---

## 3. 錯誤處理

HTTP 錯誤碼 N/A。對應物：CLI 以**非零 exit code＋繁中錯誤訊息**（`sys.exit("訊息")`）終止，訊息直接告知修復動作；可降級的錯誤**明確警告後降級**，絕不靜默吞噬。

| 情境 | 行為 | 對應 REST 概念 |
| :--- | :--- | :--- |
| 讀不到輸入圖 | `sys.exit("讀不到圖: <path>")` | 404 resource_not_found |
| 批次目錄不存在 / 目錄內無圖檔 | `sys.exit("找不到目錄 png/ …")` / `sys.exit("png/ 裡找不到圖檔 …")` | 404 |
| 未知設定值（如 `thresh` 非 otsu/fixed/adaptive） | `sys.exit("未知 thresh: …")` | 400 parameter_invalid |
| 缺輸入且 config 未鎖單張 | `sys.exit("缺輸入：用 floorplan2dxf.py 圖.png，…")` | 400 parameter_missing |
| 權重下載無憑證（私有 repo） | 印出「⚠ 權重下載無可用管道：私有 repo 需 GITHUB_TOKEN / GH_TOKEN 或 git 憑證」 | 401 authentication_failed |
| 權重 SHA-256 校驗失敗 | 刪除 `.part`、報錯不落地 | 409/422（完整性失敗） |
| 使用者以 `CC_WEIGHTS` 指定的權重缺檔 | **直接報錯，不代抓**（缺了就該報錯而非默默換檔） | 400 |
| 權重完全取不到 | 印出「⚠ 找不到 <權重>，跳過語意辨識（房型退回面積規則）」——降級而非中斷 | 503 降級 |
| `training/symbol_lib.npz` / `door_lib.npz` 缺失 | 回空清單，管線行為不變（符號證據不啟用） | 優雅降級 |
| Inkscape 手修標注含曲線指令 | `fix_annotation_paths.py` 報錯**不動檔案**（無損轉換保證） | 422 |

---

## 4. 安全性

- **TLS**：N/A（無自架 HTTP 服務）。唯一網路行為是權重下載，走 GitHub HTTPS（`github.com` Release 直鏈與 `api.github.com` asset API）
- **秘密管理**：`GITHUB_TOKEN` / `GH_TOKEN` 為 PAT（密碼等級秘密），**只經環境變數傳入、絕不進版控**；無 token 時退回 git 憑證（`GIT_TERMINAL_PROMPT=0` 非互動，取不到即失敗不掛住）。規範見 `.claude/rules/security.md`
- **下載完整性**：權重 SHA-256 `b7a280d2d7cf2dde580a947e1ebc7b4d12e53135c05581babb3b5797a166f4cf` 寫死於 `floorplan2room.py`（`CC_WEIGHTS_SHA256`），校驗不過即刪除暫存檔；`tests/test_cc_weights_download.py` 覆蓋此流程
- **反序列化安全**：`scripts/infer_cubicasa.py` 以 `torch.load(..., weights_only=True)` 載入 checkpoint，僅放行張量與 numpy 標量（`add_safe_globals`），杜絕 pickle 任意程式碼執行
- **速率限制**：N/A（本機 CLI）。對應物：GitHub API 的限流由呼叫端承受，下載僅首次執行發生（約 200MB）
- **供應鏈**：`requirements.txt` 鎖 `opencv-python>=4.10,<5`（5.0 的 HoughLinesP 回傳 shape 破壞性變更會弄壞門偵測；`opencv-python-headless<5` 同鎖，防 torch 生態後裝覆蓋）
- **授權風險（部署前必讀）**：CubiCasa5k repo CC BY-NC 4.0、資料集 CC BY-NC-SA 4.0——官方權重與微調 v1~v5 **全繼承禁商用**；商用部署前必須替換（DINOv2 去 CubiCasa 路線的動機）。詳見 [./13_security_and_readiness_checklists.md](./13_security_and_readiness_checklists.md)

---

## 5. CLI 入口定義（對應模板「API 端點定義」）

以下每支腳本相當於一個「端點」。授權 scope N/A（本機執行）；「回應」為輸出檔案位置。

### 5.1 主管線

#### `python3 scripts/floorplan2dxf.py [input] [output] [--config config.ini] [--preview 路徑]` — 灰階向量化（**已凍結，不再修改**）

- **輸入**：不帶參數＝批次 `png/`；給檔名＝單張（自動去 `png/` 找）；給目錄＝批次該目錄
- **輸出**：`dxf_scale/gray/<名>.dxf`（公分）＋ `training/chk/gray/<名>_chk.png`（紅牆綠窗疊圖）＋ `json/gray/<名>.json`（前端交接）＋ `json/arch/<名>.json`（白模交接）
- **設定**：`config.ini`（§6.1）

#### `python3 scripts/floorplan2dxf_color.py [input] [output] [--config config_color.ini] [--preview 路徑]` — 彩色向量化（現行開發重點）

- **輸入**：預設批次 `color_png/`，其餘同上
- **輸出**：`dxf_scale/color/`＋`training/chk/color/`；`json/color/`、`json/color_arch/` **暫停輸出**（門/窗/房間標籤接回後恢復）——與灰階管線目錄完全隔離、不互相覆蓋
- **設定**：`config_color.ini`（§6.1，含彩色專屬 `[binarize]` 鍵）

#### `python3 floorplan2room.py [input] [output] [--config config.ini] [--config-color config_color.ini]` — 房型辨識（專案根，663 行）

- **輸入**：預設批次 `png/`；單張或目錄皆可；自動判斷黑白/彩色（HSV 飽和度>60 且亮度>60 像素 ≥ 8%＝彩色；檔名含 `color` 強制彩色）
- **輸出**：`training/chk/room/<名>_room.png`（房間疊圖）＋ `training/chk/room/<名>_door.png`（門位檢查圖）＋ `json/room/<名>_room.json`（§6.4）；**不出 DXF**
- **副作用**：權重缺檔自動下載（§6.2）；語意快取缺檔自動呼叫 `infer_cubicasa.py` 補算（§6.5）

#### `python3 cabinet_designer.py [--port 8765] [--no-browser]` — 櫃體設計（早期入口）

- 啟動本機 HTTP 伺服器（`ThreadingHTTPServer`）＋自動開瀏覽器的拖曳式設計工具；產出施工圖 DXF、報價 CSV、存檔 JSON。此為專案內**唯一**的 HTTP 介面，僅供本機互動，非對外 API

### 5.2 深度學習推論

#### `python infer_cubicasa.py <weights.pkl> <out_dir> <img1> [img2 ...]`

- **輸出**：`<out_dir>/<名>_mask.npz`（§6.5）＋ `<名>_cc.png` 疊圖（紅牆/綠窗/橘門）
- 44 類（21 junction＋12 room＋11 icon）hourglass CNN、4 方向旋轉平均、CPU 限邊長 1100px 後放回原尺寸

#### `python apply_cubicasa_patches.py [--dir training/CubiCasa5k]`

- CubiCasa5k 程式庫 numpy 2.x 相容補丁；clone 後跑一次，可重複執行

### 5.3 評測守門（eval 系列）

| 指令 | Ground truth | 評什麼 | 輸出 |
| :--- | :--- | :--- | :--- |
| `python3 eval_windows.py [答案目錄] [chk目錄]`（預設 `Identify_ans/pngans/gray` vs `training/chk/gray`） | 人工綠框 | 窗偵測 TP/FP/FN（交集/較小框 ≥ 0.3 或中心落框） | 終端摘要 |
| `python3 eval_doors.py [door目錄]`（預設 `Asset/door`） | 門樣式圖 | 門不被誤判成窗（過濾率目標 ≥ 95%，現況 100%） | 終端摘要 |
| `python3 eval_color_walls.py [名 ...] [--config config_color.ini] [--vis]` | `Identify_ans/pngans/color/` RGB(136,0,21) 標註 | 彩牆像素級 P/R/IoU | 終端摘要；`--vis` 差異圖 → `training/chk/color/` |
| `python3 eval_cc_masks.py [名 ...] [--dir cubicasa/color] [--vis]` | 同上 | DL 原始 wall mask（不經矩形化） | 終端摘要 |
| `python eval_rooms_cc.py [--n-test 40] [--n-val 30] [--smoke N] [--thr 0.5] [--gt-seg] [--own-eval]` | CubiCasa model.svg Space 多邊形 / own_eval | 房間分割 IoU＋房型混淆矩陣 | `json/eval_rooms/report[_own][_gtseg].json`（§6.6）＋疊圖 `training/eval_rooms/chk/` |
| `python scripts/eval_door_match.py [--thr 0.85] [--tol 12]` | `Identify_ans/own_dataset` 26 題 Door quad | `score` vs `score_fused` 門檻策略 P/R | 終端摘要 |
| `python score_compare.py <repo_dir> <cc_out_dir>` | `Identify_ans/pngans/` 21 張 | 古典 CV 管線 vs CubiCasa 正面對決（牆±3px、窗綠框） | 終端摘要 |

### 5.4 標注工具鏈

| 指令 | 職責 |
| :--- | :--- |
| `python make_annotation_drafts.py [--png-dir png] [--out Identify_ans/own_dataset]` | 管線輸出組成 CubiCasa model.svg 標注初稿，供 Inkscape 人工修正；產出後逐張 `House()` 回讀驗證 |
| `python scripts/fix_annotation_paths.py [--check] [--dir Identify_ans/own_dataset]` | Inkscape 把 polygon 存成 path 的無損修復（解析器只認 polygon） |
| `python scripts/sync_room_labels.py [--dataset Identify_ans/own_dataset] [--dry-run] [--no-validate]` | 人工文字標籤同步回 `class` 屬性（解析器只讀 class），詞彙正規化進 CubiCasa 詞彙 |
| `python scripts/fix_own_floor.py <floor_dir> [--backup-dir D] [--render-dir D] [--dry-run]` | 逐層標注修復（own 統一色表，見專案記憶 annotation color convention） |
| `python scripts/rebuild_room_gt.py [--dir Identify_ans/own_eval] [--check]` | 重建房型 GT |

> Inkscape 手修後**必跑工序**：`fix_annotation_paths.py` → `sync_room_labels.py`。

### 5.5 門偵測增強（只讀寫 `json/gray`，凍結主管線零接觸；**先 door_match 再 door_propose**）

| 指令 | 職責 |
| :--- | :--- |
| `python scripts/extract_door_lib.py [--src Asset/door] [--out training/door_lib.npz]` | 門樣式模板庫（48×48、8 向展開去重） |
| `python scripts/door_match.py [名 ...] [--lib training/door_lib.npz] [--png-dir png] [--json-dir json/gray]` | 弧候選 × 模板 chamfer 重評分，命中把 `score_fused` 保底 0.90，原 `score` 不動 |
| `python scripts/door_propose.py [名 ...] [--png-dir png] [--json-dir json/gray]` | 門位 zone 提名（`score_fused=0.88`、`src="zone"`），對已入選候選去重 |

### 5.6 符號庫、分類探針與訓練資料

| 指令 | 職責 |
| :--- | :--- |
| `python extract_symbol_lib.py [--out training/symbol_lib.npz]` | 六類 FixedFurniture 48×48 模板庫（只用 train.txt，評分集衛生） |
| `python scripts/extract_room_crops.py [--margin 0.15] [--out training/room_crops]` | 房間裁切樣本萃取（DINOv2 探針用） |
| `python scripts/probe_room_classifier.py [--crops training/room_crops] [--backbone dinov2_vits14] [--report 路徑]` | DINOv2 凍結骨幹＋線性頭分類探針（具名正確率 0.730） |
| `python pack_finetune_data.py [--n-hq 300] [--oversample 3]` | 打包 `training/finetune_data.zip`（own ×3 過採樣＋hq_arch 300 張防遺忘）；本機（Cody）無 GPU，zip 帶去 GPU 機訓練 |

---

## 6. 資料契約（對應模板「資料模型」）

### 6.1 設定檔契約：`config.ini` / `config_color.ini`

兩檔**完全分離**——灰階管線只讀 `config.ini`、彩色管線只讀 `config_color.ini`。INI 格式，值留空＝取程式內建預設或自動推導（§2.3）。共同章節：

| 章節 | 鍵（預設值） | 說明 |
| :--- | :--- | :--- |
| `[io]` | `input` / `output` / `preview`（皆留空） | 留空＝批次＋慣例路徑；填檔名鎖單張 |
| `[binarize]` | `thresh=otsu`、`thresh_value=110`、`adaptive_block=31`、`adaptive_c=5`、`invert=false`、`blur=0`、`deskew=false` | 二值化策略 |
| `[walls]` | `style=solid`、`wall_min_pct=3`、`windows=true`、`win_cover_pct=70`、`win_min_pct=20`、`door_arc_pct=55`、`solid`/`h_len`/`v_len`（留空自動） | 牆/窗/門偵測門檻 |
| `[postprocess]` | `snap`/`gap`/`min_len`（留空自動） | 線段吸附/併合 |
| `[scale]` | `mm_per_px=8.8`、`dpi`（空）、`door_width_cm=90` | 門寬中位數反推每圖比例 |
| `[arch]` | `wall_height_cm=280`、`window_height_cm=120`、`sill_height_cm=90` | 白模立面預設（平面圖量不到） |
| `[hough]` | `hough_thresh=50`、`hough_min_len=25`、`hough_max_gap=5`、`angle_tol=8` | Hough 線偵測 |
| `[output]` | `layer=WALL`（程式另有 `win_layer` 鍵，預設 `WINDOW`） | DXF 圖層名 |

`config_color.ini` 的 `[binarize]` **額外**鍵（彩色專屬）：

| 鍵（預設值） | 說明 |
| :--- | :--- |
| `fade_levels=5` / `fade_keep=2` | 色調分離層次數／保留最深幾層當實心牆（留 1 層會丟中灰外牆） |
| `chroma_max=40` | 絕對色度上限，低於才算牆 |
| `gray_delta=25` | 自適應假牆過濾（0=停用） |
| `cc_mask_dir=`（空） | 語意牆遮罩快取目錄；有檔＝啟用語意融合，空＝純古典管線 |
| `cc_veto_cov=0.3` | 否決票覆蓋率門檻（高精準遮罩 0.3、CubiCasa 改 0.15） |
| `cc_rescue=true` | 漏牆救回；CubiCasa 遮罩純度僅 37%，用它時**必須 false** |

### 6.2 環境變數契約

| 變數 | 預設 | 讀取端 | 契約 |
| :--- | :--- | :--- | :--- |
| `CC_WEIGHTS` | `model_finetuned_v5.pkl`（專案根） | `floorplan2room.py` | 指定房型 CNN 權重路徑，A/B 驗收換權重用。**使用者明示指定的權重缺檔即報錯，不自動下載**；未設且預設檔缺，才走自動下載（Release tag `weights-v5`，約 200MB，SHA-256 校驗） |
| `CC_CACHE_DIR` | `cubicasa/room` | `floorplan2room.py` | 語意快取目錄（`<名>_mask.npz`）；換權重驗收時可指到獨立目錄避免污染正式快取 |
| `GITHUB_TOKEN` / `GH_TOKEN` | 無 | `_ensure_cc_weights()`（`floorplan2room.py`）、`tests/test_cc_weights_download.py` | 私有 repo Release 資產下載憑證（PAT，勿進版控）。順位：`GITHUB_TOKEN` → `GH_TOKEN` → git 憑證（`GIT_TERMINAL_PROMPT=0`）。repo 轉 public 後直鏈自動生效、零設定 |

### 6.3 DXF 輸出契約

- **單位**：公分（`insunits=5`）；原點左下、y 向上；比例由門寬鐵律反推（單門 85 / 雙門 175 / 牆厚 17.5 cm；外牆厚下限 15cm 把關）
- **圖層**：

| 圖層 | 顏色 | 內容 | 管線 |
| :--- | :--- | :--- | :--- |
| `WALL`（`[output] layer` 可改） | 7 | 牆：`LWPOLYLINE`（閉合）＋ `HATCH` 實心填充；center/outline 模式為線段 | 灰階＋彩色 |
| `WINDOW`（`win_layer` 可改） | 5 | 窗符號線段（門洞留開） | 灰階＋彩色 |
| `DOORZONE` | 2 | 門位區帶 | 僅彩色管線 |

- **輸出位置**：`dxf_scale/gray/<名>.dxf`、`dxf_scale/color/<名>.dxf`

### 6.4 JSON 輸出契約（`json/` 目錄，權威說明見 `json/README.md`）

#### `json/gray/<名>.json` — 前端交接（原則：偵測到什麼就完整交出什麼，過濾交給前端）

```json
{
  "image":  { "file": "...", "width_px": 0, "height_px": 0 },
  "scale":  { "cm_per_px": 0.0, "mm_per_px": 0.0, "method": "...", "confidence": 0.0,
              "doors_used": 0, "wall_min_cm": 15.0, "outer_wall_cm": 0.0,
              "median_door_cm": 0.0, "outer_wall_px": 0 },
  "units":  { "cm": "同 dxf_scale：原點左下、y 向上", "px": "原點左上、y 向下" },
  "walls":   [ { "px": [...], "cm": [...] } ],
  "windows": [ { "orient": "h|v", "px": [...], "cm": [...] } ],
  "doors":   [ { "px": [...], "cm": [...], "score": 0.0,
                 "tpl_chamfer": 0.0, "tpl_kind": "...", "score_fused": 0.0 } ],
  "dxf_scale": "dxf_scale/gray/<名>.dxf"
}
```

門保留**全部候選含低信心**，附 `score`／`score_fused`（door_match/door_propose 追加欄位 `src="zone"`）。

#### `json/arch/<名>.json` — 白模交接（只收高信心；門過濾：score ≥ 0.85 且門寬 50~250cm）

```json
{
  "units": "cm",
  "room_polygon": [ [x, y], ... ],
  "walls":   [ { "id": "wall_1", "position": [...], "rotation": 0.0,
                 "width": 0.0, "thickness": 0.0, "height": 280.0 } ],
  "windows": [ { "id": "win_1", "position": [...], "rotation": 0.0, "width": 0.0,
                 "height": 120.0, "sill_height": 90.0, "host_wall": "wall_1" } ],
  "doors":   [ { "id": "door_1", "position": [...], "rotation": 0.0, "width": 0.0,
                 "hinge": "left|right", "host_wall": "wall_1", "swing_in": true } ],
  "meta": { "image": "...", "cm_per_px": 0.0, "scale_method": "...", "scale_confidence": 0.0 }
}
```

立面高度取 `config.ini [arch]` 預設。`json/color/`、`json/color_arch/` 格式同上，**暫停輸出**。

#### `json/room/<名>_room.json` — 房型辨識結果（floorplan2room.py）

```json
{
  "image": { "w": 0, "h": 0 },
  "is_color": false, "color_ratio": 0.0, "pipeline": "floorplan2dxf|floorplan2dxf_color",
  "cm_per_px": 0.0,
  "scale_info": { "method": "...", "gaps_used": 0, "cm_per_px_initial": 0.0,
                  "outer_wall_cm": 0.0, "door_anchor_cm": null },
  "walls": 0, "windows": 0,
  "door_ranges_cm": [ [80, 95], [160, 190] ],
  "doors": [ { "length_cm": 0.0, "type": "single|double", "bbox": [...] } ],
  "rooms": [ { "id": 0, "label": "kitchen", "label_zh": "廚房", "area_m2": 0.0,
               "bbox": [...], "center": [...], "aspect": 0.0,
               "has_door": true, "reach": true,
               "cc_share": { "<CubiCasa 語意類>": 0.0 },
               "icons_cm2": { "<圖示類>": 0.0 },
               "symbols":  { "<古典符號>": 0 } } ],
  "adjacency": [ [id, id], ... ]
}
```

`label` 詞彙（現行評分 9 類）：`kitchen / living / bed / bath / entry / storage / garage / outdoor / space`（office/stair 未進評分與訓練，10 類對齊列入待辦）。注意：JSON 檔內弱證據房間的 `label` 欄位值為 `room`（中文「空間」，`floorplan2room.py` classify_rooms_cc 寫入）；`space` 是 `eval_rooms_cc.py` norm_label 正規化後的**評分類別**，不會出現在 JSON 檔內。`cc_share` / `icons_cm2` / `symbols` 是可追溯的辨識證據。

#### `json/eval_rooms/report[_own][_gtseg].json` — 評測報表（eval_rooms_cc.py）

```json
{
  "summary": {
    "n_images": 0, "n_ok": 0, "n_seg_fail": 0, "n_skip": 0,
    "gt_rooms": 0, "pred_rooms": 0, "matched": 0,
    "hit_rate": 0.0, "overseg": 0.0, "mean_iou": 0.0,
    "confusion": { "<gt類>": { "<pred類>": 0 } },
    "iou_thr": 0.5, "gt_seg_mode": false, "own_eval_mode": false,
    "per_class": { "<類>": { "gt": 0, "precision": 0.0, "recall": 0.0 } }
  },
  "images": [ { "id": "...", "status": "ok|seg_fail|skip", "n_gt": 0, "split": "val|test", "...": "逐樣本細節" } ]
}
```

檔名規則：`report.json`（完整管線）／`report_gtseg.json`（`--gt-seg`：GT 多邊形當房間，只評房型層）／`report_own*.json`（`--own-eval`：own 保留評分集）；`report_gtseg_ft_v1..v5.json` 為各輪微調驗收快照（留檔對照，不覆蓋）。

### 6.5 語意快取契約：`cubicasa/room/<名>_mask.npz`

`np.savez_compressed` 產生，`infer_cubicasa.py` 寫入、`floorplan2room.py` 讀取；現有 137 檔（2026-07-25 實測，v5 權重全量重算）。欄位：

| 鍵 | dtype/shape | 語意 |
| :--- | :--- | :--- |
| `wall` / `window` / `door` | bool，原圖尺寸 | 二值遮罩（既有欄位，讀取端向下相容） |
| `room` | uint8，原圖尺寸 | 房間語意 argmax：0背景 1戶外 2牆 3廚房 4客廳 5臥室 6浴室 7玄關 8欄杆 9儲藏 10車庫 11未定義 |
| `icon` | uint8，原圖尺寸 | 圖示 argmax：0無 1窗 2門 3衣櫃 4電器 5馬桶 6水槽 7桑拿椅 8壁爐 9浴缸 10煙囪 |

快取檔名即契約：`floorplan2room.py` 以 `<CC_CACHE_DIR>/<圖檔基底名>_mask.npz` 查找，缺檔自動補算（CPU 約 1 分/張）。**換權重必須重算全部快取**，否則語意票來自舊模型（v5 已重算完成）。

### 6.6 其他二進位資產契約

| 檔案 | 格式 | 生產者 → 消費者 |
| :--- | :--- | :--- |
| `model_finetuned_v5.pkl`（200MB，不進版控） | torch checkpoint（`model_state` 鍵；`weights_only=True` 可載） | GPU 機訓練 → `infer_cubicasa.py`；散布走 GitHub Release `weights-v5` |
| `training/symbol_lib.npz` | 48×48 模板陣列 | `extract_symbol_lib.py` → `symbol_match.py`（缺檔＝證據源不啟用） |
| `training/door_lib.npz` | 48×48、8 向展開 | `extract_door_lib.py` → `door_match.py` |
| `training/finetune_data.zip` | own_dataset＋hq_arch 打包 | `pack_finetune_data.py` → GPU 機（RTX 3060 / GTX 1650）訓練 |

---

## 附錄：契約變更守則

1. JSON 欄位**只增不改不刪**（`npz` 的 wall/window/door 即為向下相容先例）；破壞性變更須同步改所有讀取端並在 commit body 的 IMPACT 區塊標記（見 `.claude/rules/git-workflow.md`）
2. 改輸出格式前先跑對應 eval 腳本留基準分，改後比對（§2.5 守門鐵律）
3. 預設值變更（config 鍵、CLI 預設路徑）視同介面變更，需在 `Readme.md` 版本紀錄留痕
