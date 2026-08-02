# StylePack 渲染契約

本文件定義 RoomPilot 色卡與 3D 場景之間的穩定契約。具體色碼、
材質參數與選項以程式資料為準，避免文件和執行結果分歧。

## 適用範圍

RoomPilot 提供六種室內風格，每種風格包含三張色卡，共 18 張：

| 風格 ID | 顯示名稱 | 色卡 ID |
|---|---|---|
| `scandinavian` | 北歐風 | `scandinavian_1` 至 `scandinavian_3` |
| `japanese` | 日式 | `japanese_1` 至 `japanese_3` |
| `modern_minimal` | 現代簡約 | `modern_minimal_1` 至 `modern_minimal_3` |
| `cream` | 奶油風 | `cream_1` 至 `cream_3` |
| `industrial` | 工業風 | `industrial_1` 至 `industrial_3` |
| `american` | 美式 | `american_1` 至 `american_3` |

色卡不得改變平面圖、房間幾何、牆體開口或家具合法座標。

## 執行來源

下列檔案是可執行資料的正式來源：

| 路徑 | 責任 |
|---|---|
| `backend/catalog/data/taiwan_style_cards.json` | 後端色卡 ID、名稱、圖片與基礎色票 |
| `backend/server/style_cards.py` | 驗證與提供後端色卡資料 |
| `frontend/scene_style_packs.js` | 3D StylePack、材質、燈光及套用規則 |
| `frontend/scene_v2.js` | 使用者操作、狀態保存與 3D 場景更新 |

調整色碼、PBR 數值、圖片路徑或燈光參數時，應直接修改上述資料並
更新測試，不在本文件複製一份數值。

## 色票語意

`scene_style_packs.js` 的每張色卡使用四個固定位置：

1. `palette[0]`：牆面主色。
2. `palette[1]`：家具與軟裝主色。
3. `palette[2]`：地板或主要木質色。
4. `palette[3]`：家具、金屬或裝飾強調色。

後端基礎色卡可以只提供展示所需色票；3D 使用的完整四色色票由
`scene_style_packs.js` 定義。兩邊必須使用相同的風格與色卡 ID。

## StylePack 欄位

每個 StylePack 至少提供：

| 欄位 | 用途 |
|---|---|
| `id`、`styleId`、`name` | 跨 API、專案保存與前端選取的穩定識別 |
| `sourceImage`、`palette` | 色卡預覽及四個固定色彩角色 |
| `wall`、`floor` | 表面選項、顏色與 PBR 設定 |
| `furniture` | 家具主色、強調色、材質語言與替換政策 |
| `furnitureRules`、`decorRules` | 同風格家具與裝飾候選規則 |
| `placementRules` | 提供 Agent 或後續流程使用的風格擺放偏好 |
| `lighting`、`rendering` | 環境光、色溫、陰影、GTAO 與色調映射 |

`furnitureRules`、`decorRules` 與 `placementRules` 是規則資料。前端把
它們送入正式流程，不得因欄位存在就假設家具引擎已執行每一條偏好。
家具座標、碰撞及淨空仍由 `backend/engine/` 決定。

## 套用行為

切換色卡時，系統應：

- 更新全屋牆面與地板的顏色、表面選項及 PBR 設定。
- 更新未鎖定家具的材質主色、強調色與 PBR 設定。
- 套用該色卡的燈光及渲染設定。
- 保存 `activeStylePackId`，重新載入專案後恢復同一張色卡。
- 保留房間、門窗、牆樑柱、家具座標及使用者已確認的需求。

家具模型替換只能在相同房間角色有合法候選時進行。替換後仍須通過
家具引擎的碰撞與淨空驗證，不能為了符合風格而硬塞家具。

## 使用者鎖定

使用者指定的選擇優先於 StylePack：

- `model_locked: true`：切換風格時不得替換家具模型。
- `material_locked: true`：保留使用者指定的顏色與材質。
- `styleLocked: true`：`applyStylePack()` 不覆寫該家具的材質狀態。
- `user_specified: true`：自動替換流程不得移除或改換該家具。

衛浴設備、廚房固定設備、牆、門、窗、樑與柱不屬於家具風格替換
範圍。

## 燈光設定

正式燈光 profile 為：

- `soft_daylight`
- `warm_evening`
- `gallery_neutral`
- `industrial_contrast`

profile 的 HDR、色溫、強度、接觸陰影與 GTAO 數值以
`scene_style_packs.js` 為準。新增或改名時必須同步場景載入程式與
測試。

## 驗收

StylePack 變更至少要通過下列驗證：

1. 18 張色卡都有唯一且可保存的 ID。
2. 色卡圖片可載入，風格與色卡 ID 在前後端一致。
3. 切換色卡會改變牆面、地板、未鎖定家具、燈光及渲染狀態。
4. 鎖定模型或材質不會被 StylePack 覆寫。
5. 重新整理或重新開啟專案後能恢復選定色卡。
6. 切換色卡不改變平面圖與合法家具座標。
7. 北歐、工業與美式等不同風格在相同格局中可清楚辨識。

相關自動化測試集中於：

- `tests/test_taiwan_style_cards.py`
- `tests/test_scene_v2_contract.py`
- `tests/test_project_workflow_api.py`
