# 辨識複核項目（`review_items`）沒有消費端

## 狀態

**2026-08-03 已接線**（Ben 指示動工）。實作與本文「最小可用範圍」對齊：

- 前端消費端：`frontend/scene_recognition_review.js`（理由標籤表以後端
  `reason` 值為準，正是下方「接線時的注意事項」要求的重寫版）＋
  `scene_v2.js` 第 4 步房間面板的「系統標記需人工複核」清單，點擊即跳到
  該房間改名／調整；第 3 步辨識摘要附註標記房數。
- resolved 語意：被標記房間經使用者逐一確認（含改名後確認）即視為已複核；
  房間被刪除／合併／切割（id 消失）視為人工介入。「一鍵確認全部房間」會
  跳過被標記的房間，訊號不能被整批略過。
- 伺服器閘門（延伸原範圍）：`main.py` 的 `_unresolved_recognition_review`
  在 workflow 宣告 `space_confirmation` 完成時做 `confirmation.py` 的等值
  檢查，未複核回 422 `recognition_review_unresolved`——正式前端不走
  `/api/floorplan/confirm` 的缺口由此補上。
- 契約測試：`tests/test_recognition_review_wiring.py`（後端每個 reason 值
  必須有前端標籤，新增未補即紅；一鍵確認必須跳過被標記房間；閘門三案例）。

以下原始分析留作背景。

## 問題

`backend/floorplan/vision/spatial_report.py` 會針對每個房間產出 `review_items`
——系統自己標記「這幾間的辨識需要人工複核」，並在 `analysis.py:661` 把
`targeted_room_review_required` 加進 `issues`、把 `requires_confirmation` 設為
`True`。

前端一個都不讀：

```
grep "review_items"          frontend/ → 0
grep "\.issues"              frontend/scene_v2.js → 0
grep "requires_confirmation" frontend/scene_v2.js → 0
```

唯一的消費端是 `scene_guidance.js` 的 `buildRecognitionPresentation`，它只被
`7a799770` 刪掉的 `scene.js`（3,128 行死碼）import 過。那次刪除搶救了風格卡交接，
但沒有注意到這條鏈也一起斷了。`scene_guidance.js` 本身已於 `8cc54e95` 刪除——
還原檔案不會讓任何提示出現，因為沒有頁面 import 它。

`scene_v2.js` 有一句 `targeted_room_review_required: "尺寸已確認；請在下一步逐一
檢查房間範圍與名稱。"`，但它掛在錯誤訊息對照表上（`detail?.message`），要 API
**失敗**並回傳該字串才會出現。活路徑 `/api/floorplan/analyze` 不 raise，只把它塞進
`issues`，所以這句永遠不顯示。

會 raise 的是 `confirmation.py:137`（`/api/floorplan/confirm`），但前端只呼叫
`/api/floorplan/analyze`，那個端點現在只有測試在用。**因此使用者不會被卡住，
只是完全收不到訊號。**

## 實測（2026-08-02，`testdata/png/floor01–08.png`）

八張圖全部產生 `review_items`，不是邊角案例：

| 圖 | 房間數 | review_items | 理由分佈 |
|---|---:|---:|---|
| floor01 | 10 | 11 | 房名衝突 6、信心不足 4、不規則 1 |
| floor02 | 6 | 1 | 不規則 1 |
| floor03 | 6 | 4 | 房名衝突 2、信心不足 2 |
| floor04 | 7 | 7 | 信心不足 7 |
| floor05 | 5 | 3 | 房名衝突 1、信心不足 1、不規則 1 |
| floor06 | 4 | 3 | 房名衝突 1、不規則 2 |
| floor07 | 9 | 5 | 房名衝突 2、信心不足 1、不規則 2 |
| floor08 | 5 | 2 | 房名衝突 1、不規則 1 |

`unresolved` 房間 0 個、`polygon_cm` 為 `None` 的房間 0 個——曾經懷疑「未解析房間
帶著空多邊形走到第 7 步」的路徑，這批測資沒有觸發，不列為本項目的理由。

### 代價的具體樣貌

floor01 十房中六房被標記，其中：

```
room-7   kitchen   confidence high 0.82   net_area 56.83 m²
         標記：房名與圖示證據衝突、不規則需逐牆確認
```

同圖臥室是 11–16 m²。56.83 m² 的「廚房」幾乎確定是客餐廳被併入後貼錯標籤，而
系統已經標出衝突。使用者看不到，於是第 5 步逐房問卷會拿「廚房」問他需求，
第 6 步會往這個房間配廚房家具。房型錯誤一路帶到底，攔截訊號在 API 邊界掉了。

## 接線時的注意事項

**不要直接還原 `scene_guidance.js`。** 它的 `REVIEW_REASON_LABELS` 在被孤立前就已
與後端脫節：

| 後端實際產出 | 舊標籤表 |
|---|---|
| `room_label_icon_evidence_conflict`（八張圖共 13 次，最常見） | **缺** |
| `room_geometry_low_confidence`（15 次） | 有 |
| `irregular_room_detailed_geometry_required`（9 次） | 有 |
| — | `room_boundary_unresolved`（八張圖 0 次） |

還原舊檔的話，最常見的那一類每次都會落到 fallback「此項辨識需要局部修正」，
等於還是沒說出「這間房的名字可能是錯的」。理由標籤表要重寫，並以後端的
`reason` 值為準。

舊檔可用 `git show 8cc54e95^:frontend/scene_guidance.js` 取回參考。

## 最小可用範圍

1. 第 3 步格局確認畫面消費 `spatial_report.review_items`，依 `room_id` 分組列出。
2. `room_label_icon_evidence_conflict` 提供改名入口（後端已有 `room_type` 詞彙表）。
3. `room_geometry_low_confidence` 與 `irregular_room_detailed_geometry_required`
   至少要指出是哪一間、為什麼，讓使用者知道該檢查什麼。
4. 已處理的項目要能標成 `resolved`，否則 `review_items` 永遠非空。

## 驗收

- 以 `testdata/png/floor01.png` 為例，第 3 步應點名六間房與各自理由，而非只顯示
  `辨識結果：牆 N、門 N、窗 N`。
- 契約測試：前端有 `review_items` 的消費端，且每個後端 `reason` 值都有對應標籤
  （新增 reason 而未補標籤時測試要紅）。
- 依 `AGENTS.md` 驗證矩陣，靜態前端變更需要實際瀏覽器 QA。
