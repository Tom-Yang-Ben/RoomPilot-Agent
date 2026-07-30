# furniture_engine — 家具邏輯引擎

負責 RoomPilot F3/F6:`place_furniture`(基礎配置)、`adjust_furniture`(軟裝微調)、碰撞/淨空運算。

- Owner:蔡承安(副手:林柏彥)
- 對應 SSOT:第 4 節 F3/F6、第 8 節資料結構、第 11.2 節分工
- 狀態：v0.1 相容介面保留；v1.2／v1.3 已由正式第 6 步 adapter 套用類型預設淨空

## 模組結構

| 檔案 | 職責 |
|---|---|
| `models.py` | 資料結構:`Room` / `Wall` / `ClearanceZone` / `ClearanceSpec` / `FurnitureCatalogItem` / `PlacedFurniture` |
| `geometry.py` | 本體碰撞判斷(Shapely):出界 / 穿牆 / 家具重疊 |
| `clearance.py` | 本體＋必要開啟空間＋舒適使用空間；結構化錯誤／警告 |
| `clearance_defaults.py` | 依家具原始詳細類型提供 opt-in 預設；單品指定優先 |
| `placement.py` | `place_furniture`:自動找合法位置(單件 + 批次) |
| `adjustment.py` | `adjust_furniture`:move(軸分離)/ rotate,吃結構化指令 |
| `schema.py` | 對外介面 v0.1:JSON 序列化 + LLM function-calling tool 定義 |

## 快速開始

```bash
uv sync                                  # 安裝依賴(shapely, pytest)
uv run pytest tests/test_placement.py tests/test_clearance.py -q
uv run python demo_agent_flow.py         # 看 Agent <-> Engine 的完整互動範例
```

## 介面規則(v0.1,待與 Agent 核心對齊)

### 座標系
- 單位:公分;原點在房間左下角 (0, 0)
- `pos_x` / `pos_y` 為家具中心點;`pos_y` 對應前端 three.js 的 **z 軸**(不是高度)
- `rotation`:度(0~360)

### 家具 id 規則
`{type}_{該類型流水號}`,每個類型各自從 1 開始編號。例:`sofa_1`、`table_1`、`sofa_2`。

### v1.2／v1.3 淨空與驗證（第 6 步已套類型預設）

- `ClearanceZone(side, depth=...)` 舊寫法仍可用；舊 `depth` 會同時成為理想值與最低值。
- 新寫法使用 `kind="operation"|"access"`、`ideal_cm`、`floor_cm`、`reason`。
- `operation`（門片／抽屜）低於最低值會擋下；理想值不足但最低值足夠時回 `clearance_compressed` 警告。
- `access`（取物／入座）預設只警告。呼叫端可傳 `companion_pairs`，讓餐椅／辦公椅等配套件占用主件的舒適使用空間；此豁免絕不適用於門片／抽屜空間。
- v1.3：`ClearanceSpec(zones, mode="all"|"any", enforce_floor=...)` 支援多面。
  - 床／`bed-frame`／`mattress`：左右長側 `mode="any"` + `enforce_floor`（至少一側達 60；理想 75；床尾不算）。
  - 餐桌／`table`：宣告有椅的面才檢查；預設四面；`enforce_floor`；配套椅可佔 access。
  - `sofa-bed` 不套用床側規則。
- `validate_placement_with_clearance()` 回 `PlacementValidation(errors, warnings)`；舊 `check_placement_with_clearance()` 仍回第一條錯誤字串或 `None`。
- `place_furniture()` 失敗時保留舊 `reason`，並增加 `reason_detail`。
- `clearance_defaults.catalog_with_default_clearance()` 仍是 opt-in API；正式第 6 步 adapter 已明確呼叫。單品指定值仍優先。
- JSON 可帶多面 `clearance_zones`，並用 `clearance_mode` / `clearance_enforce_floor`。


### 檢查順序(重要)
`check_placement_with_clearance` 的判斷順序固定為:

1. 出界(物件超出空間範圍)
2. 穿牆(與牆體穿透)
3. 本體重疊(與「X」重疊)
4. 淨空撞牆(「X」的開合空間被牆體阻擋)
5. 淨空撞家具本體(「X」的開合空間與「Y」衝突)
6. 淨空互撞(「X」與「Y」的開合空間互相衝突)
7. 反向檢查:本體壓到別人的淨空(擋住了「Y」的開合空間)

同時符合多項時只回報**最先命中**的那一項。例如同時出界又穿牆,只會回報「出界」。
寫測資或 debug 時請留意這個順序,數值抓不準可能被判成前面的項目。

### 失敗訊息詞彙表(Agent 可直接轉述給使用者)
- `物件超出空間範圍`
- `與牆體穿透`
- `與「{name}」重疊`
- `找不到合法擺放位置`
- `找不到目標家具:{id}`
- `「{name}」的開合空間被牆體阻擋`
- `「{name}」的開合空間與「{name}」衝突`
- `「{name}」與「{name}」的開合空間互相衝突`
- `擋住了「{name}」的開合空間`

### adjust_furniture 行為備註
- move 採**軸分離**:X/Y 分開檢查,能走多少走多少。因此「單軸被擋」時仍回 `success: true` 但該軸座標不變;只有**雙軸都被擋**才回 `success: false`。
- 失敗時 `placed` 仍回傳目前(未變動的)狀態;僅 target id 不存在時 `placed` 為 `null`。

## 給對接組員的備註

- **Agent 核心(柏彥)**:tool schema 定義在 `schema.py`(`PLACE_FURNITURE_TOOL` / `ADJUST_FURNITURE_TOOL`),互動範例跑 `demo_agent_flow.py`。v0.2 待議:add/remove、相對方位指令(toward_window 等)、場景狀態誰持有。
- **後端/DB(立凱)**:要存的擺放結果欄位 = `pos_x` / `pos_y` / `rotation`(見 `schema.py` 的 `placed_to_dict`)；`pos_x` / `pos_y` 為既有相容欄位，單位由同一 payload 的 `coordinate_unit: "cm"` 明示。
- **家具型錄(鄭典)**:型錄需新增 `clearance` 資訊(哪一面、需要幾公分開合空間),沒有這個欄位淨空檢查無法運作。無開合需求的家具(沙發、茶几)可留空。

## 尚未實作(P1/P2)

- F6 的 add / remove(規格內,v0.2)
- 相對方位指令解析(toward_window / next_to 等)
- 擺放評分機制（目前已由 13 個固定點升級為中心／沿牆／15cm 網格搜尋，但仍是 first-fit，不是全局最佳化）
- 非矩形房間(L 型)支援
- 餐桌四面淨空、床左右至少保留一側
- 走道連通性檢查(B 選項加分)
- `Door` 資料結構與門扇開闔弧判斷
