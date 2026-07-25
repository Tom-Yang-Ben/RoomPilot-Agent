# 專案結構指南 - RoomPilot-Agent

> **版本:** v1.0 | **更新:** 2026-07-25 | **狀態:** 草稿

本文件以**專案根目錄實際盤點**（2026-07-25、cody 分支、v2.16）為準，描述 RoomPilot-Agent 的目錄結構、命名慣例、資料與程式的分界，以及結構演進原則。專案總覽見 [./02_project_brief_and_prd.md](./02_project_brief_and_prd.md)。

---

## 設計原則

RoomPilot-Agent 是純 Python CLI 的平面圖向量化與房型辨識管線（無 Web 後端、無資料庫、無 REST API），結構原則與典型 Web 專案不同：

- **管線腳本集中於 `scripts/`，管線入口留在專案根**：`floorplan2dxf*.py` 等處理腳本放 `scripts/`；`floorplan2room.py`、`cabinet_designer.py` 兩個使用者入口留在根目錄，方便直接 `python3 floorplan2room.py` 執行。
- **資料即一級公民**：考卷（`png/`、`color_png/`）、人工答案（`Identify_ans/`）、語意快取（`cubicasa/`）、評測報表（`json/`）都是有明確目錄的資料資產，且**答案與快取進版控**（雙機同步的依據）。
- **輸出隔離**：灰階與彩色管線的所有輸出走各自的 `gray/`、`color/` 子目錄（`dxf_scale/gray|color/`、`training/chk/gray|color/`、`json/arch` vs `json/color_arch`），互不覆蓋。
- **配置外部化＋雙檔制**：參數全在 `config.ini`（灰階、凍結）與 `config_color.ini`（彩色、開發中），程式碼不硬編參數。
- **大檔不進 Git**：GitHub 100MB 硬限 → 權重（`model_finetuned_v5.pkl`，200MB）走 GitHub Release（tag `weights-v5`）；訓練環境整包 `training.zip`（約 8.2GB）用實體媒介換機。
- **凍結區明確標示**：`scripts/floorplan2dxf.py` 已凍結不再修改；改動集中在彩色管線與房型辨識。

---

## 頂層結構（實際盤點）

```plaintext
RoomPilot-Agent/
├── .claude/                  # Claude Code 規則/context（每機自管，不進版控）
├── .mcp.json                 # MCP 設定（含 API key，不進版控）
├── Asset/                    # 符號素材庫：bathroom/ door/ kitchen/ pieces/
├── Identify_ans/             # 人工答案總目錄（進版控，詳見下方資料層）
├── VibeCoding_Workflow_Templates/  # 文件模板（本文件的來源模板）
├── cabinet_designer.py       # 櫃體設計入口（早期入口，約 70KB）
├── color_png/                # 彩色考卷 29 題
├── config.ini                # 灰階管線參數（凍結）
├── config_color.ini          # 彩色管線參數（開發中）
├── cubicasa/                 # CNN 語意快取（npz 進版控；_cc.png 預覽視目錄而定）
│   ├── color/  gray/        # 彩/灰考卷的 mask.npz＋_cc.png
│   └── room/                 # 房型辨識用快取（*_mask.npz 共 137 檔，v5 權重全量重算）
├── docs/                     # 專案文件（HANDOVER_finetune_v5.md、vibecoding/）
├── dxf_scale/                # DXF 輸出（gray/ color/ 隔離）
├── floorplan2room.py         # 房型辨識管線入口（663 行）
├── json/                     # 結構化輸出與評測報表
│   ├── arch/  gray/  room/  # 灰階管線建築件/線段/房間 JSON
│   └── eval_rooms/           # 房型評測報表（report.json、report_own*.json…）
├── model_finetuned_v5.pkl    # 現行預設權重（200MB，不進版控，Release 自動下載）
├── png/                      # 灰階考卷 38 題
├── recognition_report.html   # HTML 辨識報表（產出物）
├── requirements.txt          # 依賴鎖版（opencv <5 等，含理由註解）
├── scripts/                  # 管線/評測/標注/訓練腳本共 25 個 .py（附 README.md）
├── tests/                    # pytest 測試 6 檔
├── training/                 # 訓練環境總目錄（不進版控，training.zip 換機）
├── training.zip              # 訓練環境打包件（約 8.2GB，不進版控）
├── .gitignore
└── Readme.md                 # 主文件（含版本沿革至 v2.16）
```

> 註：`scripts/README.md` 開頭寫「本目錄共 20 個 Python 腳本」，實際盤點為 25 個（README 落後於現狀，待更新）。彩色管線輸出目錄 `json/color/`、`json/color_arch/` 於執行時建立，本次盤點根目錄 `json/` 下尚未出現。

### scripts/ 六大功能組（25 個 .py）

| 功能組 | 腳本 |
| :--- | :--- |
| 核心轉換管線 | `floorplan2dxf.py`（約 1400 行，**凍結**）、`floorplan2dxf_color.py`（約 1900 行，開發主力） |
| 深度學習推論 | `infer_cubicasa.py`、`apply_cubicasa_patches.py` |
| 評分守門（eval 系列） | `eval_windows.py`、`eval_doors.py`、`eval_door_match.py`、`eval_rooms_cc.py`、`eval_color_walls.py`、`eval_cc_masks.py`、`score_compare.py` |
| 標注工具鏈 | `fix_own_floor.py`、`fix_annotation_paths.py`、`rebuild_room_gt.py`、`make_annotation_drafts.py`、`sync_room_labels.py` |
| 符號/門庫 | `extract_symbol_lib.py`、`extract_door_lib.py`、`symbol_match.py`、`door_match.py`、`door_propose.py` |
| 訓練/資料打包與探針 | `pack_finetune_data.py`、`extract_room_crops.py`、`probe_room_classifier.py`、`dxf2png_pieces.py` |

---

## 原始碼結構 (Clean Architecture)

**N/A（未採 `src/` 分層佈局）— 理由與本專案對應物：**

本專案是單機批次管線，不是多層服務：沒有 Web/persistence 邊界，也沒有跨團隊共用的 domain model，導入 `src/[app]/domains|application|infrastructure` 分層會製造空殼目錄。實際的「分層」對應如下：

| Clean Architecture 概念 | 本專案對應物 |
| :--- | :--- |
| 入口點（main.py） | 專案根的 `floorplan2room.py`、`cabinet_designer.py`；`scripts/floorplan2dxf_color.py` 直接以腳本執行 |
| Domain / 業務邏輯 | 各管線腳本內部的偵測/重建演算法（正交線重建、flood fill 切割、語意投票融合） |
| Application / 用例 | `scripts/` 內每支腳本＝一個用例（一支腳本做一件事，CLI 即用例邊界） |
| Infrastructure / 外部整合 | `ezdxf`（DXF 輸出）、PyTorch＋`training/CubiCasa5k/floortrans/`（模型定義）、`_ensure_cc_weights`（GitHub Release 權重下載＋SHA-256 校驗，位於 `floorplan2room.py`） |
| 配置（core/config） | `config.ini`／`config_color.ini` 雙檔制＋`GITHUB_TOKEN` 環境變數 |

長期若管線模組化需求出現（例如彩色管線拆分超過 800 行上限的檔案），再依 `.claude/rules/coding-style.md`（200-400 行典型、800 行上限）演進為套件結構，屆時以 ADR 記錄（見 [./04_architecture_decision_record_template.md](./04_architecture_decision_record_template.md)）。

---

## 資料目錄與程式目錄的分界

這是本專案結構的核心約定，分成三圈：

### 1. 進版控的程式碼

`scripts/*.py`、根目錄 `floorplan2room.py`／`cabinet_designer.py`、`tests/`、`config.ini`／`config_color.ini`、`requirements.txt`、`docs/`。

### 2. 進版控的資料（雙機同步依據）

| 目錄 | 內容 | 實際數量 |
| :--- | :--- | :--- |
| `png/`、`color_png/` | 灰階/彩色考卷原圖 | 38 題／29 題 |
| `Identify_ans/pngans/` | 牆窗像素 GT（`*_ans.png`） | gray 38 檔／color 29 檔（專案簡報記 28，與實際盤點差 1，待確認） |
| `Identify_ans/own_dataset/` | 微調訓練集（每題一個 `floorNN/` 目錄＋`own_train.txt`/`own_val.txt` 切分檔） | 25 題 |
| `Identify_ans/own_eval/` | 房型保留評分集（**永不進訓練**，`eval_list.txt` 定義） | 12 題 |
| `Identify_ans/own_dataset_color/` | 彩色標注草稿訓練集 | 20 題 |
| `Identify_ans/own_eval_color/` | 彩色保留評分集 | 9 題（記憶/簡報記 10，實際目錄 9 個，待確認） |
| `cubicasa/room/*_mask.npz` | CNN 語意快取（v5 權重全量重算） | 137 檔 |
| `json/` | 線段/建築件/房間 JSON＋`eval_rooms/` 評測報表 | — |
| `Asset/` | 門/衛浴/廚房符號素材 | — |

每題標注目錄的內容物固定為 `F1_original.png`（原圖）、`F1_scaled.png`（縮放圖）、`model.svg`（CubiCasa House 格式標注）。

### 3. 不進版控的本機資產（.gitignore 明列）

- `training/`＋`training.zip`：CubiCasa5k 程式庫與資料集、微調權重 v1~v3、官方權重、`finetune_data/`、管線預覽輸出 `training/chk/{gray,color,room}/`、房型評分工作區——**換機＝整包 training.zip 搬運解壓**
- `/model_finetuned_*.pkl`：微調權重（200MB 超 GitHub 100MB 限制；v5 走 Release tag `weights-v5` 自動下載，SHA-256 校驗）
- `cubicasa/room/*_cc.png`：語意快取預覽圖（分鐘級可重生，只提交 npz 與 report）
- `.claude/`、`.mcp.json`：每台機器自行維護的 agent 設定（`.mcp.json` 含 API key）
- `.venv/`、`__pycache__/`、`temp/`（除錯暫存）

**鐵律**：覆蓋 `chk/`、`dxf_scale/` 輸出前，必先跑 `scripts/eval_windows.py` 對 `Identify_ans/pngans/` 評分，不得退化後覆蓋（詳見 [./03_behavior_driven_development_guide.md](./03_behavior_driven_development_guide.md) 與 `.claude/rules/`）。

---

## 測試結構

```plaintext
tests/
├── conftest.py                    # 全局 fixtures
├── test_annotation_drafts.py      # 標注草稿工具測試
├── test_cc_weights_download.py    # 權重自動下載＋SHA-256 校驗測試
├── test_eval_rooms_cc.py          # CubiCasa 尺房型評測測試
├── test_eval_rooms_own.py         # own 尺房型評測測試
└── test_symbol_match.py           # 符號比對測試
```

- 未細分 `unit/`／`integration/`／`features/` 子目錄——目前 6 檔規模扁平放置即可，超過約 15 檔再分層。
- 命名一律 `test_<被測對象>.py`，與被測腳本同名對應（如 `test_symbol_match.py` ↔ `scripts/symbol_match.py`）。
- 另一層「測試」是**評測守門 harness**（`scripts/eval_*.py`）：pytest 保證程式正確性，eval 系列保證**辨識品質不退化**，兩者互補、缺一不可。
- 覆蓋率目標 80%（`.claude/rules/testing.md`）；管線腳本的實際覆蓋率現況待確認。

---

## 文檔結構

```plaintext
docs/
├── HANDOVER_finetune_v5.md   # v5 微調交接文件（GPU 機執行步驟＋人工審批 SOP）
├── superpowers/               # （既有工作流輔助目錄）
└── vibecoding/                # 本系列實例化文件（01~17，依模板編號）
```

另有三處在地文件：
- `Readme.md`（專案根，約 60KB）：主文件，含完整版本沿革（至 v2.16）、House 解析陷阱記錄——**新結論先進 Readme，再回流各專門文件**
- `scripts/README.md`：scripts/ 六大功能組逐腳本說明
- `Identify_ans/README.md`、`json/README.md`：資料目錄自帶說明

ADR 目前以 Readme 版本沿革＋commit message（WHY/WHAT/IMPACT）承載；獨立 `docs/adrs/` 目錄尚未建立，重大結構變更時依演進原則補建。

---

## 命名慣例

### 檔案與目錄

| 對象 | 慣例 | 實例 |
| :--- | :--- | :--- |
| Python 腳本 | `snake_case.py`，動詞或「來源2目標」式 | `floorplan2dxf_color.py`、`extract_room_crops.py` |
| 評測腳本 | `eval_` 前綴 | `eval_windows.py`、`eval_color_walls.py` |
| 測試 | `test_` 前綴 | `test_cc_weights_download.py` |
| 灰階考卷/題目 | `floorNN` | `png/floor01.png`、`Identify_ans/own_dataset/floor01/` |
| 彩色考卷/題目 | `color_floor_NN` | `color_png/color_floor_01.png` |
| 像素 GT | `<題名>_ans.png` | `Identify_ans/pngans/gray/floor01_ans.png` |
| 語意快取 | `<題名>_mask.npz`＋預覽 `<題名>_cc.png` | `cubicasa/room/1041_mask.npz` |
| 檢核圖 | `<題名>_chk.png`（輸出於 `training/chk/{gray,color}/`） | — |
| 權重 | `model_finetuned_v<N>.pkl` | `model_finetuned_v5.pkl` |
| 評測報表 | `report*.json` | `json/eval_rooms/report_gtseg_ft_v5.json` |
| 資料切分 | 純文字清單檔 | `own_train.txt`、`own_val.txt`、`eval_list.txt` |

### 配置雙檔制

- `config.ini` ↔ `scripts/floorplan2dxf.py`（灰階，**兩者一起凍結**）
- `config_color.ini` ↔ `scripts/floorplan2dxf_color.py`（彩色，現行開發重點）
- 新管線參數一律進 `config_color.ini`，禁止回頭改 `config.ini`（記憶規則：只改 color 管線，gray 凍結不動）

### 中文 Commit 慣例

Subject 採 **英文 type(scope)＋中文描述**，body 依 `.claude/rules/git-workflow.md` 的 WHY/WHAT/IMPACT 三段（實例取自近期歷史）：

```
feat(data): color_png 30 題標注草稿——own_dataset_color 20＋own_eval_color 10
fix(data): own_dataset 25＋own_eval 12 全題標注修復——逐張人工驗收
chore(data): 移除重複考卷 png/floor49.png
```

- type 用標準英文（feat/fix/refactor/docs/test/chore/perf/ci），scope 用目錄或模組名（data、tools）
- 中文描述直接寫清楚做了什麼＋關鍵數字；破折號「——」帶補充說明
- 分支命名維持英文 `<type>/<short-description>`；另有**分支即機器**慣例：`cody`/`bella`/`ben`/`ancai`/`django`/`kai-dev` 各對應一台開發機，經 PR 匯流回 `main`

---

## 演進原則

1. **凍結區不動**：`scripts/floorplan2dxf.py`＋`config.ini` 已凍結；灰階指標（牆 F1 0.99、窗 96%/96%）是回歸基準，不是改進對象。
2. **改動前後必評分**：任何影響 `chk/`/`dxf`/房型輸出的結構或程式調整，前後都跑對應 `eval_*.py`（窗：`eval_windows.py`；房型：`eval_rooms_cc.py`），退化即回退。
3. **gray/color 隔離不可破**：新增輸出類型時必須同時開 `gray/`、`color/` 子目錄，禁止共用單一輸出目錄。
4. **資料集只增不改語意**：`own_eval*/` 保留集永不進訓練；擴充 `own_dataset` 走「VLM 盲標＋人工把關」流程（`scripts/make_annotation_drafts.py` → review.html → `scripts/fix_own_floor.py`）。
5. **大檔走既定通道**：>100MB 一律 Release（權重）或 training.zip（訓練環境），禁止嘗試進 Git；新增權重版本沿用 `weights-v<N>` tag＋SHA-256 記錄。
6. **頂層結構重大變更需留痕**：目前以 Readme 版本沿革＋WHY/WHAT/IMPACT commit 承載；若建立 `docs/adrs/` 則改用 ADR（[./04_architecture_decision_record_template.md](./04_architecture_decision_record_template.md)）。
7. **一致性優先於教條**：不為了符合 `src/` 佈局而搬目錄；現有「腳本＋資料目錄」結構在單機批次管線場景是合理解，等出現真實痛點（檔案超過 800 行、多入口共用邏輯重複）再演進。
