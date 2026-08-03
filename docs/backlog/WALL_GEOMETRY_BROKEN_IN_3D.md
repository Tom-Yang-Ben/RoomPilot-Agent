# 第 6 步 3D 的牆不成面，門片嵌不進去

## 狀態

**待修，最高優先。** 2026-08-03 Ben 實走 QA 發現，當天未修。
這份文件是給下一輪的完整交接，不必重新摸索。

## 症狀（實機截圖確認，不是推測）

第 6 步 3D 主畫面：

- 牆變成**一根根不相連的細長板片**站在地上，另有白色細條**橫躺在地板上**。
  19 面牆沒有形成連續的牆面。
- 門片（深棕色板）站在**沒有牆的空地上**——因為周圍沒有連續牆體可嵌入。
- 使用者的原話：「不是牆的地方，你就不用幫我把它升起來變成牆」「走道與廚房
  之間哪來的門」。

## 關鍵線索：`wall_polys` 是 0

```
場景 floorplan：wall_segments 19（＝第 4 步標的 19 面牆，數量正確）
                wall_polys     0   ← 連續牆體多邊形，空的
                room_regions   7
```

`frontend/scene_viewer.js` 的 `buildWallMass()`（約 2741 行）與
`buildWallMassTopCaps()`（約 2766 行）都是：

```js
const wallMassRegions = (floorplan?.wall_polys || []).filter(...);
if (!wallMassRegions.length) return false;   // ← 直接放棄
```

拿不到 `wall_polys` 就回傳 false，於是退回逐段畫板子的路徑——這就是「一根根
細長板片」的來源。

`wall_polys` 由 `backend/upgrade3d/dxf_parser.py` 用 shapely 把牆中線 buffer
成實心牆團時產生（該檔 200-206 行附近），但**第 4 步確認後走的是
`backend/server/scene_service.py` 的 `floorplan_from_editor_payload()`**，
那個函式只把 structures 逐段轉座標，**完全沒有產生 `wall_polys`**。

→ **修的方向**：`floorplan_from_editor_payload()` 要把 wall_segments 依各自
`thickness_cm` buffer 成多邊形並聯集，補出 `wall_polys`（可直接參考
`dxf_parser.py` 既有作法，shapely 已是既有依賴）。門洞要從牆體挖掉——
`door_openings` 已經產生（見下），挖洞邏輯要一起確認。

## 當天已完成、不必重做的部分

| 項目 | 狀態 | 位置 |
|---|---|---|
| `/api/scene/layout` 回傳補 `door_openings` | 已修 | `scene_api.py` `_floorplan_with_openings()` |
| 門對齊到牆的**延伸線**（用關閉門洞，非打開門片） | 已修 | `scene_service.py` `_align_doors_to_wall_lines()` |
| 窗貼回宿主牆 | 已修 | `scene_service.py` `_snap_openings_to_walls()` |

門的座標語意（**下一輪必須知道，否則會再踩一次**）：

```
door.start → door.end        ＝ 門「打開後」的門片（使用者在第 4 步看到的粗線）
door.start → door.swing_end  ＝ 門「關起來」佔的那段牆洞 ★牆洞要用這個
door.host_wall_id            ＝ 用「打開的門片」算出來的，★不可信★
```

拿 `start→end` 去找最近的牆會把門貼到隔壁那面牆上（當天犯過這個錯，憑空生出
一扇走道↔廚房的門）。門坐落在**兩段牆之間的缺口**裡，所以量距離要量到牆的
**延伸線**，量到線段端點會得到 50~70cm 的假距離。

實測資料（Ben 的專案 `529f26895d524cebbd638ab46556b484`，floor01 平面圖）：

```
door-1 鉸鏈(484,606) 開片→(369,606) 關閉→(484,491)
       wall-15(垂直) x=494 y657→608 ┐ 同一條線，缺口 y495~608（113cm）
       wall-17(垂直) x=494 y495→281 ┘ 門洞長 115cm，正好吻合
對齊後：五扇門離牆線 0.0cm，各移動 10~15cm（約半個牆厚）
連通關係：走道↔儲藏室、臥室↔廚房、陽台↔客廳、室外↔廚房、走道↔浴室
```

## 另一件事：純 2D 子畫面要移除

Ben 明確要求刪掉第 6 步的純 2D 子畫面（`#layout-2d-step`）——3D 主畫面右側
已經有平面座標細調。當天只做到「導覽不再進入它」（`scene_v2.js` 導覽處理把
`layout_2d` 轉向 `white_model_3d`）。

正式移除的範圍：`layout_2d` 是工作流狀態機的正式步驟，問卷送出的自動流程會
經過 `confirmLayout2d()` 才轉 3D；約十支測試釘著 `#layout-plan-stage`、
`#confirm-layout-2d` 等節點。要做成不可見的過場並同步更新那批測試。

## 驗收

- 3D 牆體是連續的面，門洞在牆上，門片嵌在洞裡。
- 以 `testdata/png/floor01.png` 重跑一次八步，第 6 步目視確認。
- `pytest -q tests` 維持綠（當天基準 929 passed / 9 skipped）。
