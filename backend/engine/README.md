
# furniture_engine — 家具邏輯引擎

負責 RoomPilot 第 6 步几何合法性：`place_furniture`、`adjust_furniture`、碰撞／淨空。

- Owner：蔡承安（Ancai）；Agent 對接：Yen
- 狀態：v0.1 介面相容；v1.2／v1.3 淨空已由正式第 6 步 adapter 套用類型預設
- **本模組不算「放哪些家具」**；房型清單見下方策略表，選件規則見 Agent `knowledge.py`

## 文件地圖（先讀這裡）

| 文件                                                  | 回答什麼問題                               | 是否正式                            |
| ----------------------------------------------------- | ------------------------------------------ | ----------------------------------- |
| **本檔**                                        | 引擎怎麼用、座標、淨空、檢查順序、驗證指令 | 是                                  |
| [`room_strategy/README.md`](room_strategy/README.md) | 每間房最少放什麼、砍件順序、為何這樣定     | 是（策略規格；server 清單尚未全接） |
| [`../../agent/knowledge.py`](../agent/knowledge.py)  | Agent 執行用的房型／成組／最少族系         | 是（程式 SSOT）                     |
| [`notes/README.md`](notes/README.md)                 | 討論筆記索引                               | 否（工作筆記）                      |
| [`AGENTS.md`](AGENTS.md)                             | 改此目錄前的 AI 守則摘要                   | 是                                  |

衝突時：**几何以本檔＋程式為準；房型清單以 `room_strategy` 拍板為準，並同步 `agent/knowledge.py`。**

## 模組結構

| 檔案                      | 職責                                                                      |
| ------------------------- | ------------------------------------------------------------------------- |
| `models.py`             | `Room`／`Wall`／`ClearanceZone`／`ClearanceSpec`／catalog／placed |
| `geometry.py`           | 本體碰撞（出界／穿牆／重疊）                                              |
| `clearance.py`          | 必要開啟＋舒適使用；結構化錯誤／警告                                      |
| `clearance_defaults.py` | 類型預設淨空（opt-in；單品指定優先）                                      |
| `placement.py`          | 自動找合法位置                                                            |
| `adjustment.py`         | move（軸分離）／rotate                                                    |
| `schema.py`             | JSON 序列化＋ tool schema                                                 |
| `room_strategy/`        | 房型策略人讀規格                                                          |
| `notes/`                | 非正式討論筆記                                                            |

## 快速開始

```bash
uv sync
uv run pytest tests/test_placement.py tests/test_clearance.py -q
uv run pytest tests/test_agent_select.py tests/test_agent_place.py -q
```

## 介面規則（v0.1）

### 座標系

- 單位：公分；引擎房間座標以左下為原點時，`pos_x`／`pos_y` 為家具中心
- 前端 three.js：`pos_y` 對應 **z**（不是高度）
- `rotation`：度（0～360）

### 家具 id

`{type}_{流水號}`，每類型各自從 1 起。例：`sofa_1`、`table_1`。

### v1.2／v1.3 淨空（第 6 步已套類型預設）

- 舊 `ClearanceZone(side, depth=...)` 仍可用（depth＝理想＝最低）
- 新欄位：`kind="operation"|"access"`、`ideal_cm`、`floor_cm`、`reason`
- `operation` 低於最低值 → 擋下；僅理想不足 → `clearance_compressed` 警告
- `access` 預設只警告；`companion_pairs` 可讓配套佔用舒適區（**不可**佔門／抽屜區）
- v1.3 `ClearanceSpec`：床至少一側；餐桌有椅才留面；`sofa-bed` 不套床側
- `catalog_with_default_clearance()` 為 opt-in；第 6 步 adapter 已呼叫

### 檢查順序（重要）

`check_placement_with_clearance` 固定順序：

1. 出界
2. 穿牆
3. 本體重疊
4. 淨空撞牆
5. 淨空撞家具本體
6. 淨空互撞
7. 反向：本體壓到別人的淨空

同時多項時只回報**最先命中**者。

### 失敗訊息（可給使用者）

- `物件超出空間範圍`
- `與牆體穿透`
- `與「{name}」重疊`
- `找不到合法擺放位置`
- `找不到目標家具:{id}`
- `「{name}」的開合空間被牆體阻擋`
- `「{name}」的開合空間與「{name}」衝突`
- `「{name}」與「{name}」的開合空間互相衝突`
- `擋住了「{name}」的開合空間`

### adjust_furniture

- move 軸分離：單軸被擋仍可 `success: true`（該軸不變）；雙軸都擋才 `false`
- 失敗時 `placed` 仍為目前狀態；僅 id 不存在時 `placed` 為 `null`

## 與 Agent／RAG 的分工

```text
房型策略（放什麼） → RAG／白名單候選 → Agent 選定／排序／換小
                                 ↓
                         Engine（能不能放、座標）
                                 ↓
                              2D／3D 呈現
```

- RAG／LLM **不**決定坐标與合法性
- Agent **不**改碰撞規則
- Engine **不**決定房型最少清單

## 給對接組員

- **Yen／Agent**：成組與最少族系在 `backend/agent/knowledge.py`；须与 `room_strategy` 同步
- **Kai**：長期應在 catalog 寫入單品 `clearance`；無欄位時用類型預設
- **Bella**：`SPACE_DEFAULTS`／問卷模板接線前，勿宣稱策略表已上線

## 尚未實作／下一輪

- Agent hints 排序與 `companion_pairs` 完整灌入第 6 步（進行中規劃）
- 高家具擋窗（高矮分層）、門前動線帶
- 走道連通、美學評分（非 first-fit）
- F6 add／remove、相對方位（toward_window）
- `Door` 開闔弧
- 非矩形房間完整支援（DXF 邊界已有部分補強）

（床至少一側、餐桌有椅才留面：**已完成**於 v1.3。）
