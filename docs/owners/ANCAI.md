# Ancai：家具幾何與擺位決策

更新：2026-08-04

## 角色與範圍

Ancai 負責 RoomPilot 的確定性家具幾何：擺放、移動、碰撞、淨空、牆關係與合法性。正式程式位置為 `backend/engine/`。引擎自 2026-08-01 起不只是驗證器，也是決策層：`layout_strategy.py` 決定家具貼哪面牆、朝哪個方向、跟誰成組；但「這個位置合不合法」的判定仍然只有一份，所有擺法原語都回頭呼叫同一支 `validate_placement_with_clearance()`。

| 檔案 | 行數 | 職責 |
|---|---:|---|
| `layout_strategy.py` | 1037 | 五種擺法原語＋`ROOM_RULES`＋整房編排 `place_room()` |
| `clearance.py` / `clearance_defaults.py` | 558 / 116 | 淨空驗證（operation／access、all／any、companion、反向）／類型預設淨空（opt-in，單品指定優先） |
| `geometry.py` / `placement.py` | 76 / 241 | Shapely 本體碰撞（出界／穿牆／重疊）／ first-fit 自動找位（中心→四牆→15cm 網格） |
| `models.py` / `schema.py` | 262 / 158 | 資料結構與單位／座標契約 ／ JSON 序列化與 LLM tool schema |
| `layout_room.py` / `dxf_room.py` | 189 / 127 | `layout_json` → `Room`（未接正式線）／ DXF → `Room`（公尺→公分唯一邊界） |
| `adjustment.py` | 91 | move（軸分離）／rotate |

`backend/engine/README.md` 是正式介面文件，`room_strategy/README.md` 是房型策略的人讀 SSOT，`notes/` 底下兩本工作筆記**不是 SSOT**。不可改我的什麼：Yen 解釋失敗但不能改變合法性；Bella 呈現與保存結果但不得把演算法複製進 `main.py` 或 JS；Django 的 Graph RAG 只透過 evaluation report 提供 reason code；前端與 LLM 永遠不自行推算合法位置。反過來，引擎也不擁有型錄真相（Kai）、問卷 UI（Bella）、RAG 檢索（Django／Yen）與「每間房要放什麼」（`room_strategy` 拍板 ＋ `backend/agent/knowledge.py`），且不在引擎內抓型錄、呼叫外部 API 或保存專案。

## 資料流

```text
房間 polygon + 牆 + 開口（門扇 swing／窗型／窗台高）+ 型錄尺寸 + 需求家具清單
  ->【策略層 layout_strategy】選牆、選朝向、選貼附對象
      rank_wall_candidates：無門優先 → 無窗優先 → 區段長者優先
      ROOM_RULES：房型 × 擺位族系 → PlacementRule（anchor／attach／order／avoid_windows）
  ->【驗證層 geometry + clearance】同一份合法性判定，七步固定順序
      出界 → 穿牆 → 本體重疊 → 淨空撞牆 → 淨空撞家具 → 淨空互撞 → 反向壓別人淨空
  -> 合法擺放（PlacedFurniture + warnings）或結構化失敗
     （code / message_zh / item_id / rule / required_cm / available_cm / shortfall_cm）
```

分工的界線很硬：**策略層只提候選位置，不放行任何一件家具**；每個候選一律經 `_is_legal()`（門扇矩形 → 呼叫端 `extra_check` → `validate_placement_with_clearance`）。策略層有 bug 的後果是「擺得醜」，驗證層有 bug 的後果才是「擺得不合法」。單位與座標契約（`models.py:1-8`）：長度一律公分；X 向右、Y 向上，原點在平面圖左下角；position 是物件中心；rotation 是逆時針角度，0 度時家具正面朝 +Y。

## 擺位決策層（layout_strategy）

| 擺法原語 | 語意 | 關鍵預設 | 失敗 code |
|---|---|---|---|
| `place_against_wall` | 背貼牆、正面朝內 | `margin_cm=0`（只在房間兩端生效）、`treat_windows_as_blocking=False` | `no_legal_wall_position` |
| `place_in_front_of` | 主家具正前方＋中線對齊（茶几對沙發、椅對桌） | `gap=45`，退讓序列 gap→×0.75→×0.5，下限 2.0cm | `no_legal_front_position` |
| `place_at_center` | 房間中央刻意不貼牆（餐桌專用） | rotation ∈ (0, 90) × 9 個偏移 | `no_legal_center_position` |
| `place_around` | 環繞主家具，正面一律朝桌心 | `gap=6`；長邊夠長排 2 張，否則置中 1 張 | `no_legal_seat_position` |
| `place_beside` | 貼側邊並對齊指定端（床頭櫃貼床頭） | `end="head"｜"foot"`（其他值 raise）、`gap=5` | `no_legal_adjacent_position` |

三支帶 `target` 的原語（`place_in_front_of`／`place_around`／`place_beside`）成功時會自動把 `(target.id, item_id)` 加進 `companion_pairs` 並回傳 `companion_pair`——否則後面的家具驗證會把已經合法的床頭櫃重新判成侵入床側淨空。

`ROOM_RULES` 是六房型 / 26 條規則的擺位規則表。鍵一律是 `backend.agent.knowledge.family_of()` 摺疊後的**擺位族系**，不是型錄原始 `normalized_type`；引擎自己不做這層摺疊（不讓幾何模組反向相依 Agent 模組），由整合端換算，查不到的家具 fallback 成「背貼牆」。`order` 對齊 `knowledge.py`：**錨點 0–9 → 泛用件 10–19 → companion 副件 20+**。

| 房型 | 錨點 | 貼附關係 | 其餘（`order`） |
|---|---|---|---|
| `bedroom` | `bed`（`avoid_windows`, 0）、`wardrobe`(5) | `bedside-table` beside `bed` head gap 5 (20)；`office-chair` front `desk` gap 8 face=target (25) | `chests-of-drawer`(10)、`desk`(12)、`bookcase`(15) |
| `living_room` | `tv-bench`（`avoid_windows`, 0） | `sofa` **opposite** `tv-bench`(5)；`coffee-table` front `sofa` gap 45 (25)；`office-chair` front `desk`(30) | `bookcase`(10)、`armchair`(15)、`desk`(18) |
| `dining_room` | `dining-table`（`attach="center"`, 0） | `dining-chair` around `dining-table` gap 6 (20) | `sideboard`(10)、`display-cabinet`(12) |
| `workspace` | `desk`(0) | `office-chair` front `desk` gap 8 face=target (20) | `bookcase`(10)、`shelving-unit`(12) |
| `storage` | `shelving-unit`(0) | — | `cabinet-cupboard`(10) |
| `entry` | `shoe-cabinet`(0) | — | `clothes-rack`(10) |

`rank_wall_candidates()` 的排序鍵是 `(int(has_door), int(has_window), -length)`，即「無門優先 → 無窗優先 → 區段長者優先」，同分時保留 `WALL_SIDES` 的 south→north→west→east 順序。`free_spans()` 扣掉門窗，**門扇 swing 端點也投影到牆軸一併扣除**；`_blocks_height()` 在家具高度為 `None` 時保守地一律視為會擋，落地窗 `sill_cm=0` 因此擋下任何家具。沿牆的候選座標順序是 `[置中, 貼左端, 貼右端]` 再往外每 15cm 對稱擴散——早期把兩端排最後，小房間會出現「床離牆 10 公分」的死縫。

`place_room()` 依 `(rule.order, 輸入順序)` 排序，故確定性。失敗**不做換小或砍件**，那是 Agent 的職責。

## 淨空體系（clearance v1.2／v1.3）

雙層門檻：`ideal_cm`（理想）與 `floor_cm`（底線）。`ClearanceZone.__post_init__` 會做規範化——缺一補一、`≤0` 或 `ideal < floor` 直接 raise，最後把 `depth` 固定成 `floor`，讓 v0.1 呼叫端繼續正常運作。

| 維度 | 規則 |
|---|---|
| `operation`（開合空間）vs `access`（舒適使用空間） | operation 低於 `floor` → **error 擋下**；access 預設只警告（`rule="access_clearance"`，只比 `ideal_cm`），只有 `enforce_floor=True` 時 floor 才是硬門檻。硬門檻的面過 floor 但不足 ideal → 降級成 `clearance_compressed` 警告 |
| `mode="all"` vs `mode="any"` | all＝每一面都要過，hard 面不足即 error 並立即 return；any＝只有**每一面 floor 都失敗**才報 `access_any_side_unmet`（取 available 最小者當代表），有一面過 floor 但無一面達 ideal 則降級成 warning |
| companion 豁免與淨空互撞 | companion 豁免**只對 access 生效**，operation 區永遠擋得下來（配套可佔舒適區，不可佔門／抽屜區）；**只有兩個 operation 區互撞才硬擋**，舒適區可以彼此共用 |
| 反向檢查 | 新家具本體壓到別人的淨空：hard 出 `blocks_clearance`（error），非 hard 出 `blocks_access`（warning） |

失敗訊息一律帶 `required_cm / available_cm / shortfall_cm`（`_available_depth_cm()` 用固定 24 次二分搜尋求可用深度），使用者看得到「差幾公分」。errors 一命中即 return，所以**同時多項只回報最先命中者**。

類型預設淨空（`clearance_defaults.py`，opt-in，**單品自帶 clearance 永遠優先**，鍵使用原始 `normalized_type` 不經 `family_of()` 合併）：`DEFAULT_CLEARANCE_BY_TYPE` 17 個單面鍵（`wardrobe` 90/50「門扇開啟」、`chests-of-drawer` 90/60「抽屜拉出」、`tv-bench` 60/45、`shoe-cabinet` 75/50；access 類 `desk` 105/75、`bookcase` 75/40）；`DEFAULT_CLEARANCE_SPEC_BY_TYPE` 6 個多面鍵（`bed`／`bed-frame`／`mattress` → any + `enforce_floor`，左右各 75/60「上下床」，**床尾不算側**；`dining-table`／`table` → all 四面 75/60「拉椅入座」；`bar-table` → 只前後）。`sofa-bed` 刻意不套床側規則；覆蓋率未到 100% 是 2026-07-31 拍板的刻意設計，不是缺口。

## 已定案規格

不可再議的拍板。房型與選件的人讀 SSOT 一律是 `backend/engine/room_strategy/README.md`，機器 SSOT 是 `backend/agent/knowledge.py`。

| 規格 | 拍板日 |
|---|---|
| 12 個房型即全集寫死不再新增；廚房／浴室／陽台／走道「最少自動配置＝空白」；房間標籤只當排序加分絕不當硬過濾 | 2026-07-31 |
| 通用砍件律 G1–G5：先換小再砍可選、由清單尾端往前砍、必備仍失敗就誠實失敗、軟裝不進自動配置、家電永不進 2D/3D；改策略的順序固定：先改 `room_strategy/README.md` → 再改 `knowledge.py` → 補測試 | 2026-07-31 |
| 淨空雙層（ideal／floor）＋ operation 擋下／access 只警告 ＋ companion 只豁免 access；檢查順序固定七步，同時多項只回報最先命中者 | 2026-07-29 v1.2 |
| 床至少一側 75/60（床尾不算側）、餐桌有椅才留面、`ClearanceSpec` 多面 all／any | 2026-07-29 v1.3 |
| 五種擺法原語定案（`center`／`around`／`face` 於 08-02 補齊） | 2026-07-29 起 |
| 客廳 TV-first：`tv-bench` 是錨點先定電視牆，`sofa` 貼**對面牆**（背有靠、面向電視），`coffee-table` 居中其間；`opposite` 的「退任意牆」fallback 死刑——對面牆放不下＝誠實失敗，換牆交給上游 | 2026-08-02 |
| 電視不進窗下（逆光）、床頭不靠窗共用同一個 `avoid_windows` 機制；餐桌是全系統唯一「刻意置中」的錨點；擺放邏輯一律用比例、零絕對公分（未重定標的「巨人屋」平面下語意不失真） | 2026-08-02 |
| 模型視覺朝向走 `modelOrientationDeg` 渲染層欄位，**絕不動擺位 rotation**；標注屬單顆 GLB 事實，換款必重驗 | 2026-08-02／08-03 |
| RAG／LLM／瀏覽器永不決定幾何；換小款歸 Agent，引擎只回「放不下＋原因」 | — |

客廳定版樣本 `room_strategy/samples/living_room_floor04_v1.md`（2026-08-03，專案 `b2b2c83f` rev 474，四件已 locked）可當人工覆核基準：沙發前緣→電視櫃前緣 228.5cm、沙發前緣→茶几近緣 46cm、三件共線容差 y ±15cm、門窗前零家具。

## 修改前的作業手冊

1. **確認要改的是哪一層。** 「擺得醜」改策略層（`layout_strategy.py`），「擺得不合法」改驗證層（`geometry.py`／`clearance.py`）。兩者的測試檔與回歸風險完全不同。
2. **先讀四份。** `backend/engine/README.md`（介面與檢查順序）→ `backend/engine/AGENTS.md`（守則）→ 目標模組的檔頭 docstring 與行內註解（多數設計決策的根因記在那裡）→ 若碰房型清單，加讀 `room_strategy/README.md`。
3. **跑一次基準線再動手。** 下方「引擎回歸六支」記下現況數字（2026-08-04 為 143 passed）。改房型清單另跑 `.venv/bin/python scripts/audit_room_programs.py`，改前改後各一次。
4. **先寫紅燈測試。** 新擺法原語要有「成功案例 + 每一種失敗模式」；新失敗模式必須驗 `reason_detail` 的 `code` 與 `rule`，不是只驗 `success is False`；新淨空規則要同時驗 error 與 warning 兩條路徑。
5. **實作時守四條硬規矩。** 演算法必須確定性（絕不從 LLM 文字生成座標）；公分制與 rotation 單位不可改；`clearance` 的七步順序不可重排（順序決定使用者看到哪一條失敗訊息）；策略層的候選一律回頭走 `_is_legal()`，不在原語裡另寫一份「這樣應該可以」的判斷——那正是「改了引擎卻沒效果」的成因。
6. **用真實平面覆核。** `.venv/bin/python scripts/floor04_layout_preview.py` 走真實辨識端點 → `place_room()`，逐房印座標、朝向、貼哪面牆與浮空偵測；刻意不做快照，Cody 改進辨識即刻反映（冷啟約 48 秒、熱跑約 25 秒）。
7. **收尾跑全庫閘門並更新正式文件。** `.venv/bin/python -m pytest -q tests/`，確認 `git diff --check`、`git status --short` 乾淨（不覆蓋他人未提交變更）；進度以 `backend/engine/README.md` 為準而非 `notes/`——不得把「規格寫了」說成「引擎做完」，也不得把「引擎測過」說成「第 6 步已啟用」。

## 跨資料夾改動規則

跨界時必須用 `AGENTS.md:16-30` 的六欄位格式記錄（主要 owner／協作 owner／修改檔案／改變的契約／為何不能只在單一目錄完成／兩端驗證測試），且共享契約要同時驗證生產端與消費端。

| 對象 | 我對他的義務 | 他對我的義務 |
|---|---|---|
| Yen（`backend/agent/`） | 產出結構化失敗原因供其呈現；房型最少清單須與 `knowledge.py` 對齊，動它之前先知會；每次換件重呼叫都要重算，不沿用舊座標 | 回傳結構化意圖、絕不發明座標；Graph RAG 證據可支持選件但不能推翻幾何 |
| Bella（`backend/server/`、`static/`） | 引擎須可被 server adapter 直接呼叫；配置合法性交付 review；`SPACE_DEFAULTS`／問卷模板接線前不得宣稱策略表已上線 | 不得複製引擎演算法進 `main.py` 或 JS；新增任何「不准擺／可以重疊／要留幾公分」的規則前先問我；`placement_failed` 不得在前端改成成功 |
| Kai（catalog／PostgreSQL） | 擺放器只使用 `verification_status=verified`；只擺真實 GLB，不產生白模替代品；需要單品淨空時走 catalog 欄位，無欄位才用型別預設 | 長期在 catalog 寫入單品 `clearance` 欄位；隔離區資料不得進 API 或場景 |
| Django（`backend/spatial_data/`） | 門窗 host wall／窗戶淨空／房間 polygon 改動時，我出 consumer 測試；與其共同定義「家具可放置」的 reason code | Graph RAG 不取代碰撞檢查，不決定門洞／牆／家具實際座標，不自行改寫第 6 步擺放器 |
| Cody（`backend/floorplan/`、`backend/upgrade3d/`） | 只消費已確認幾何；不確定的偵測不算牆；不從畫面文字或模型名稱猜測需求 | 家具擺放屬 Ancai，不推論設計選擇；`upgrade3d/` 座標改動需引擎與場景回歸測試 |

`backend/server/AGENTS.md:13-32` 是我於 2026-08-01 立下的邊界條文。服務層目前仍持有四條引擎看不到的規則：`window_clearance_zones`（窗前禁放帶，現已分級為落地窗 60cm／一般窗 70cm＋窗台高度豁免）、`_OVERLAY_TYPES`（地毯可壓）、`_IGNORE_COLLISION_TYPES`（壁架跳過碰撞）、`_shrunk_boundary`（全房內縮 8cm）。**現行立場是「不主動收回，但各有觸發條件」**：第 4 條屬設計如此（引擎以 `margin_cm` 參數接收，數字由服務層決定）；前三條要等引擎的落地窗留距與堆疊層落地後才有收回的意義。在那之前，新規則一律進引擎。一鍵退回開關（改壞了先用它止血）：`ROOMPILOT_LAYOUT_STRATEGY=0` 整個關掉策略層、`ROOMPILOT_WINDOW_BAND_FLAT=1` 退回舊的 70cm 平頭窗帶。

## 待拍板與已知缺口

| 項目 | 卡在哪 |
|---|---|
| 沙發背窗：牆不夠才背窗，還是看到落地窗就主動背窗 | 待拍板，擋住落地窗禁放帶與客廳擺法收斂 |
| 窗要分兩類還是三類（缺「可通行落地窗門」，底線 30 vs 60 差一倍） | 待拍板，前端目前只有 `standard`／`floor_to_ceiling` |
| 門開向未確認時要不要做「預設門前通行帶」fallback | 待拍板，目前門前淨空實際零生效 |
| 堆疊層（地面層 vs 家具層）、電視上櫃；清死鍵 `bed-frame`／`cabinets-cupboard` | 未動工；只改引擎沒有用，必須連 `scene_service` 的 `_OVERLAY_TYPES`／`_IGNORE_COLLISION_TYPES`／`FURNITURE_ALIASES` 一起改 |
| 美學／擺放評分排序 | 未做；策略層已能產生「有設計」的候選，但選位仍是 first-fit |
| 走道連通、門前動線帶、高家具擋窗（高矮分層）、`bedside-table` 淨空規則 | 未做，`README.md` 已列為下一輪 |
| `place_room()`／`layout_room.py` 尚未被 `backend/server/` 呼叫 | 第 6 步走 scene_service 自己的逐件流程；`place_at_center`／`place_around`／`rank_wall_candidates`／`layout_room` 目前僅供 `place_room()` 內部、測試與 `floor04_layout_preview.py` 使用 |
| 五表對帳殘餘缺口：玄關 `entry`；`backend/engine/README.md` 模組表尚未列入 `layout_strategy.py`／`layout_room.py` | 前者因後端問卷詞彙未開放 `entry`（屬 Bella）；後者是文件落後於程式，下次動引擎時一併補 |

## 驗證

以 `/home/ancai/RoomPilot-Agent` 為工作目錄。WSL 下一律用 `.venv/bin/python`（本 venv 無 pip，裝套件走 `uv pip install --python .venv/bin/python <pkg>` 或 `uv sync`）。測試不需 PostgreSQL——`tests/conftest.py` 會強制切成 sqlite／json provider。

```bash
# 引擎核心四支（最快的紅綠迴圈）：2026-08-04 實測 106 passed
.venv/bin/python -m pytest -q tests/test_layout_strategy.py tests/test_layout_tv_first.py \
  tests/test_clearance.py tests/test_placement.py

# 引擎回歸六支（動擺放邏輯的基準線）：2026-08-04 實測 143 passed
.venv/bin/python -m pytest -q tests/test_layout_strategy.py tests/test_clearance.py \
  tests/test_placement.py tests/test_agent_place.py tests/test_agent_select.py \
  tests/test_scene_layout_regions.py

# 跨界接線（動到 scene_service 或前端後必跑）：2026-08-04 實測 189 passed
.venv/bin/python -m pytest -q tests/test_scene_visual_regressions.py \
  tests/test_scene_v2_contract.py tests/test_project_workflow_api.py

# 全庫閘門：2026-08-04 實測 784 passed / 12 skipped
.venv/bin/python -m pytest -q tests/
```

**務必帶 `tests/`**。裸跑 `pytest -q` 會多收 `training/tests/`，多出 7 個與引擎無關的失敗（缺 `svgpathtools`／`floortrans` 兩個選用依賴），基準數字會對不上。以下三支稽核與預覽腳本 `scripts/README.md` 尚未收錄：

```bash
.venv/bin/python scripts/audit_room_programs.py      # 五表對帳量尺，改任一張清單前後各跑一次（約 0.5 秒，不需 DB）
.venv/bin/python scripts/audit_furniture_vanish.py   # 家具無聲消失五道關卡全量掃描（需 PostgreSQL）
.venv/bin/python scripts/floor04_layout_preview.py   # 真實辨識 → place_room 的逐房覆核；--image / --no-draw / --retype
```

2026-08-04 現況基準：`audit_room_programs.py` 為「11 房型中 1 個偏離」（玄關 `entry`，屬 Bella 未結項）；`floor04_layout_preview.py` 在 floor04.png 上是「擺放成功 10 件、失敗 0 件、浮空 0 件」，加 `--retype room-2=dining_room` 後為 15 件全成功。
