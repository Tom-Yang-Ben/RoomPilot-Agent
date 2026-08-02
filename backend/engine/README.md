# furniture_engine — 家具邏輯引擎

負責 RoomPilot F3/F6:`place_furniture`(基礎配置)、`adjust_furniture`(軟裝微調)、碰撞/淨空運算。

- Owner:蔡承安(副手:林柏彥)
- 對應 SSOT:第 4 節 F3/F6、第 8 節資料結構、第 11.2 節分工
- 狀態:P0 完成(v0.1),等待 Agent 核心/後端對接後迭代

## 模組結構

| 檔案 | 職責 |
|---|---|
| `models.py` | 資料結構:`Room` / `Wall` / `ClearanceZone` / `FurnitureCatalogItem` / `PlacedFurniture` |
| `geometry.py` | 本體碰撞判斷(Shapely):出界 / 穿牆 / 家具重疊 |
| `clearance.py` | 淨空運算:開合空間(衣櫃門、抽屜等)的衝突檢查 |
| `placement.py` | `place_furniture`:自動找合法位置(單件 + 批次) |
| `adjustment.py` | `adjust_furniture`:move(軸分離)/ rotate,吃結構化指令 |
| `schema.py` | 對外介面 v0.1:JSON 序列化 + LLM function-calling tool 定義 |

## 快速開始

```bash
uv sync                                  # 安裝依賴(shapely, pytest)
uv run pytest tests/ -v                  # 跑測試(25 cases)
uv run python demo_agent_flow.py         # 看 Agent <-> Engine 的完整互動範例
```

## 介面規則(v0.1,待與 Agent 核心對齊)

### 座標系與單位(對齊全隊契約,2026-07-08 公分化)
- 單位:**一律公分(cm)**。上游 dxf_parser 輸出公尺,在 `dxf_room.py` 進門時 ×100——那是引擎唯一的 m→cm 邊界。
- 平面座標:X 向右、Y 向上(數學慣例),原點在平面圖左下角 (0, 0)。
- `pos_x` / `pos_y` 為家具**中心點**;`pos_y` 是平面第二軸(**不是高度**)。
- `rotation`:逆時針角度(度,0~360),0 度時家具正面朝 +Y(即 `ClearanceZone` 的 front 方向)。
- 尺寸:`width` 沿物件本地 X、`depth` 沿本地 Y、`height` 沿 Z。

### 家具 id 規則
`{type}_{該類型流水號}`,每個類型各自從 1 開始編號。例:`sofa_1`、`table_1`、`sofa_2`。

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
- **後端/DB(立凱)**:要存的擺放結果欄位 = `pos_x` / `pos_y` / `rotation`(見 `schema.py` 的 `placed_to_dict`)。**2026-07-08 起數值為公分**,既有以公尺存的紀錄需遷移;`pos_x` / `pos_y` 為既有相容欄位,單位由同一 payload 的 `coordinate_unit: "cm"` 明示。
- **家具型錄(鄭典)**:型錄需新增 `clearance` 資訊(哪一面、需要幾**公分**開合空間),沒有這個欄位淨空檢查無法運作。無開合需求的家具(沙發、茶几)可留空。

## 尚未實作(P1/P2)

- F6 的 add / remove(規格內,v0.2)
- 相對方位指令解析(toward_window / next_to 等)
- 擺放評分機制(目前 first-fit,擺得合法但不見得好看)
- 非矩形房間(L 型)支援
- 走道連通性檢查(B 選項加分)
- `Door` 資料結構與門扇開闔弧判斷
