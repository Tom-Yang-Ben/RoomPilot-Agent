# 第 6 步 3D 的牆不成面，門片嵌不進去

## 狀態

**2026-08-06 更新：顯示路線改回逐段牆（bella-test1 同款），本文的 wall_polys
連續牆體僅剩無 wall_segments 來源的後路。** 原因：ExtrudeGeometry 的 UV 是
平面公分座標，型錄貼圖糊成雜色；逐三角形材質採樣在轉角出現拼布。Ben 實測
牆與地板材質「一直修不好」，而 bella-test1 的逐段 BoxGeometry 畫面正確。
本輪已移植：接縫補牆（buildConfirmedWallJunctionFills，護開口）、外牆繼承
相鄰房間材質（fd75fda3）、全屋同色 tintOnly、混搭界線每側真實地材、門片嵌
洞尺寸；並移除牆段延長（wallSegmentsExtendedForOpenings）與端點內縮。後端
`wall_polys` 產出與開槽契約不動（`refreshRestoredFloorplanStructure` 仍消
費 `wall_polys_openings_cut`）。契約測試已同步（`test_confirmed_wall_
segments_walk_segment_walls_not_wall_mass` 等）。以下 8/3 記錄保留為歷史。

**主體已修（2026-08-03），待瀏覽器目視驗收。** 修法照本文「修的方向」：

- `floorplan_from_editor_payload()` 依各牆 `thickness_cm` 把中線 buffer 成
  實心牆團（方形端帽＋斜接，同 `dxf_parser.py`），門洞用 `closed_segment`
  （鉸鏈→swing_end）、窗洞用線段本身，以平端帽**全高開槽**後輸出
  `wall_polys` 與 `wall_polys_openings_cut` 旗標；`build_scene_payload()`
  透傳旗標。實資料驗證：本案 19 面牆 → 7 塊牆團，5 門 5 窗全部開槽成功。
- `scene_viewer.js` 閘門改為「開槽過的 wall_polys 可帶著門窗走連續牆體」
  （DXF 的 wall_polys 沒開槽，維持無開口才走 mass）；開口上下的牆由既有的
  door-wall-header／window-wall-sill 補回。另修 `flipSegmentZ` 漏翻
  `closed_segment` 的 z 鏡像——漏翻的話門片會嵌不進牆上的槽。
- 測試：`tests/test_wall_polys_from_editor.py` 新增 5 條；閘門契約測試改為
  `test_accurate_floorplan_walks_wall_mass_when_backend_cut_the_openings`。

**目視驗收（2026-08-03）**：以本案復原路徑實開瀏覽器確認——俯視圖牆體為
連續帶、轉角乾淨、開口都在牆上；旋轉視角門片嵌在牆面開口內、上方有補牆、
窗玻璃帶在牆身上；門診斷 expected/resolved/rendered 5/5/5。尚未以
`floor01.png` 從頭重跑八步（流程級驗證，非幾何驗證）。

**與遠端 `bella-test1` 的關係**：該分支 8/1–8/2 已用另一條路修同一症狀
（逐段牆路線：第 4 步 `confirmed_wall_opening` 快照、door-header-wall 門楣、
接縫補齊），但基底較舊、前端仍在 `backend/server/static/`。本輪的
`closed_segment` 對齊＋`door-wall-header`＋wall_polys 連續牆體已涵蓋其
門/牆修正，不需移植；其逐房材質統一系列是另一件事，未搬。

下方「純 2D 子畫面要移除」仍是待辦。以下保留當時的完整交接脈絡。

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
