# json/ 目錄說明

所有管線的 JSON 產出統一收在此目錄，依「管線 × 用途」分子目錄。座標系約定全 repo 一致：

- **px**：影像座標，原點左上、y 向下（方便疊回原圖）
- **cm**：實體座標，原點左下、y 向上（與 `dxf_scale/` 的 DXF 完全一致）

```
json/
├─ gray/        黑白管線前端交接（floorplan2dxf.py）
├─ room/        房型辨識結果（floorplan2room.py）
├─ arch/        3D 白模交接（floorplan2dxf.py）
├─ eval_rooms/  房型評分報告（eval_rooms_cc.py）
├─ color/       彩色管線前端交接（floorplan2dxf_color.py，暫停輸出）
└─ color_arch/  彩色管線白模交接（同上，暫停輸出）
```

---

## gray/ — 前端交接（黑白管線）

`scripts/floorplan2dxf.py` 每張圖一份 `<名>.json`，原則是「**偵測到什麼就完整交出什麼**」，過濾交給前端：

- `image`：檔名與像素尺寸
- `scale`：比例尺推算全紀錄（cm_per_px、方法、信心度、用了幾扇門、外牆厚等）
- `walls` / `windows`：bbox 形式，**px 與 cm 兩套座標並列**
- `doors`：**保留全部候選並附 score**（含低信心的），由前端自行過濾
- `dxf_scale`：對應 DXF 檔路徑

## arch/ — 白模交接（黑白管線）

同一次執行的另一種下游格式：`architecture.json` schema，給 3D 白模端**直接蓋模型**，因此只收高信心資料：

- 只有 cm 座標；每個物件是「中心點 + rotation + 尺寸」參數化描述，帶 `id`（wall_1 / win_1 / door_1）
- 補 2D 圖沒有的立面資訊：牆高、窗高、窗台高（取 `config.ini` [arch] 預設值）
- 窗/門帶 `host_wall`；門另有 `hinge`（鉸鏈左右）、`swing_in`（內外開）、rotation=門面法線
- **門只收 score ≥ 0.85 且換算門寬 50~250cm** 者（低信心與離譜尺寸不進白模）
- `room_polygon`：房間外圍多邊形

## room/ — 房型辨識（floorplan2room.py）

每張圖一份 `<名>_room.json`，房間層的完整結果與可追溯證據：

- `pipeline` / `is_color` / `color_ratio`：走了黑白還是彩色偵測
- `cm_per_px` / `scale_info`：門寬鐵律校正後的比例尺（單門 85cm / 雙門 175cm / 牆厚 17.5cm）
- `rooms[]`：每間房的 `label`（房型）、`label_zh`、`area_m2`、`bbox`、`has_door`、`reach`（能否從客廳走到），以及**辨識證據**——`cc_share`（CubiCasa 語意票）、`icons_cm2`（圖示面積）、`symbols`（古典符號命中）
- `doors[]` / `door_ranges_cm`：門位與判定門寬區間（80~95 單門 / 160~190 雙開門）
- `adjacency`：房間相鄰圖（經真門連通）

對應的目視檢查圖在 `chk/room/`。

## eval_rooms/ — 房型評分報告（eval_rooms_cc.py，路線圖 A）

以 CubiCasa5k val/test 樣本的 Space 多邊形當 ground truth 的量測報告，是房型權重調整的驗收依據：

- `report.json`：完整管線評分（分割＋房型），`summary` 含 hit_rate / mean_iou / 房型混淆矩陣，`images[]` 逐樣本狀態
- `report_gtseg.json`：`--gt-seg` 解耦模式——GT 多邊形當房間，只評房型辨識層
- `report_gtseg_ft_v1.json`：v2.11 首輪微調的驗收快照（未達標，預設權重維持基線，留檔對照）

評分疊圖在 `eval_rooms/chk/`（gitignore，執行時重建）。

## color/、color_arch/ — 彩色管線（暫停輸出）

`scripts/floorplan2dxf_color.py` 的前端交接與白模交接，格式同 gray/ 與 arch/。彩色管線現階段只輸出牆體 DXF（門/窗/房間標籤停用中），這兩個目錄待功能接回後恢復產出。

---

## 對應關係速查

| 產生程式 | JSON | 檢查圖 | DXF |
| :--- | :--- | :--- | :--- |
| floorplan2dxf.py | `gray/`＋`arch/` | `chk/gray/` | `dxf_scale/gray/` |
| floorplan2dxf_color.py | `color/`＋`color_arch/`（暫停） | `chk/color/` | `dxf_scale/color/` |
| floorplan2room.py | `room/` | `chk/room/` | 不出 DXF |
| eval_rooms_cc.py | `eval_rooms/` | `eval_rooms/chk/` | — |
