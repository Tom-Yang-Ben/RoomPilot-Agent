# 問卷、風格材質與生圖空間契約

狀態：待實作契約。本文描述 RoomPilot 問卷、RAG、家具引擎與外部生圖服務必須共同遵守的資料與流程；不得將本文誤稱為既有功能。

## 1. 核心原則

1. 第 4 步確認的牆、門、窗、樑、柱與房間邊界為固定結構。後續單一家具配置只能調整家具，不得改結構。
2. 一般房間以資料庫家具和 GLB 為主；廚房、浴室、陽台以設備需求和生圖描述為主。第 6 步不可用白模或假設備冒充真實資料庫家具。
3. 家具缺 GLB 或放不下時，問卷不可卡住。第 6 步必須顯示原因、可行替代與使用者可採取的動作。
4. 問卷可逐房確認並提早送出 RAG 工作，但 RAG 與生圖永遠不得延伸房間、移牆、改門窗或忽略尺寸限制。

## 2. 標準房型

| room_type | 顯示名稱 |
| --- | --- |
| entry | 玄關 |
| living_room | 客廳 |
| dining_room | 餐廳 |
| kitchen | 廚房 |
| primary_bedroom | 主臥 |
| secondary_bedroom | 次臥 |
| bathroom | 浴室 |
| study | 書房／工作區 |
| balcony | 陽台 |
| storage | 儲藏室 |
| circulation | 走道／動線 |
| multipurpose_room | 多功能室 |

前端名稱下拉選單、後端 payload、RAG metadata 與家具引擎都必須使用這組 `room_type`；不得再以自由輸入名稱作為邏輯判斷。

## 3. 問卷流程

### 3.1 一般房間

逐房只問必要資訊：用途（可複選）、家具類別與尺寸族群、想要的家具形容詞／材質、選填補充。不得再用「生活情境二選一」強迫使用者選擇。

例：臥室選睡眠休息後，UI 必須提供使用者可理解的床型族群，例如單人床、小雙人床、標準雙人床；選閱讀／工作後才展示書桌與工作椅。資料庫品名是次要資訊，不得取代使用者可理解的家具類別與尺寸。

每個選項顯示快速可行性：`feasible`、`tradeoff_required`、`infeasible`、`size_recommended`。這是提示而不是問卷攔截；不合法或缺 GLB 的品項要原樣帶到第 6 步處理。

### 3.2 廚房、浴室、陽台

這三類空間沒有足夠可展示的真實設備／家具時，不能顯示空白家具清單後直接通過。必填：`primary_use` 與 `equipment_direction`（可選「依尺寸推薦」）；選填：`must_not_have`。系統要說明：這些答案會限制最終生圖中的設備、收納、乾濕區與動線，且不能超出已辨識房間尺寸。

若設備互斥，保留所有選擇並標記「待取捨」。使用者必須移除其中一項、改選較小方案或選「依尺寸推薦」後才能確認該房；這是唯一可阻擋的問卷情境。

第 6 步顯示這類房間的結構、材質與可用家具，不放大型白模設備；最終生圖才依 `generative_equipment` 生成設備與裝修。

### 3.3 補充給設計與生圖

提供符合已選風格色卡的可點標籤，以及可自由輸入的文字欄。偵測到「擴建、移牆、加房間、隔間、拆牆、改門窗」等結構語意時，跳出確認：

- 返回第 4 步調整結構。
- 保留需求，依現有空間生成。

選第二項時，payload 必須寫入 `structure_locked: true` 與 `structural_intent_acknowledged: true`，後續畫面顯示「結構限制已套用」。

## 4. 風格與材質

1. 先選全屋風格，再展開該風格的色卡與材質推薦；不可一開始塞滿所有圖片。
2. 一般室內空間預設繼承全屋設定；廚房、浴室、陽台可有功能性覆寫。走道預設跟客廳一致，使用者解除同步前先警告。
3. 每張材質卡只能使用一筆 `material_id`：名稱、縮圖、色票、說明、PBR 欄位與第 6 步 3D 套用都必須對應同一筆資料。
4. 初始只推薦 3 至 4 張，推薦依風格、色卡、房型與用途變化。縮圖完整鋪滿卡片主視覺，文字置於下方，不重複附假色票。
5. 使用者鎖定的逐房材質不可被全屋風格更新覆寫。

## 5. RAG 與生圖邊界

房間確認後可送出 RAG，前端顯示「此房已送出建議準備」。RAG 可推薦家具、材質與設備取捨，但不可修改下列固定資料：`polygon_cm`、`walls`、`doors`、`windows`、`beams`、`columns`。

生圖提示必須附帶：

> 僅能在提供的房間邊界與固定結構內生成。不得新增房間、延伸面積、移動牆、門、窗、樑或柱；無法容納時，優先保留使用者標記的 priority，並以較小或替代方案取捨。

## 6. 家具引擎 payload

```json
{
  "schema_version": "2.0",
  "room": {
    "room_id": "room-bathroom-1",
    "room_type": "bathroom",
    "label": "主浴室",
    "polygon_cm": [[0, 0], [302, 0], [302, 158], [0, 158]],
    "usable_area_m2": 4.78,
    "fixed_structure": {
      "walls": ["wall-12"], "doors": ["door-5"], "windows": [], "beams": [], "columns": []
    }
  },
  "style": {
    "global_style_pack_id": "japanese-natural-01",
    "inherits_global_style": false,
    "wall_material_id": "wall-mineral-warm-001",
    "floor_material_id": "floor-stone-slip-resistant-002",
    "manual_locks": ["floor_material_id"]
  },
  "usage": ["shower", "storage"],
  "catalog_furniture_slots": [],
  "generative_equipment": {
    "required": true,
    "primary_use": "shower",
    "equipment_direction": ["walk_in_shower", "single_vanity"],
    "must_not_have": ["bathtub"],
    "priority": "walk_in_shower",
    "fit_status": "feasible",
    "generation_notes": "明亮、好清潔、保留 75 公分動線"
  },
  "constraints": {
    "structure_locked": true,
    "do_not_expand_room": true,
    "do_not_modify_walls_or_openings": true,
    "minimum_walkway_cm": 75,
    "structural_intent_acknowledged": false
  },
  "ui_status": {
    "questionnaire_confirmed": true,
    "rag_status": "queued",
    "generation_status": "awaiting_final_render"
  }
}
```

## 7. 第 6 步責任

第 6 步必須將問卷選定品項、RAG 推薦與實體 GLB 放置結果並列。對每個問題品項提供：衝突原因（門片、窗前淨空、走道、尺寸、朝向、缺 GLB）、定位、換家具、刪除與詳細資料。視角保持不跳動，定位只以藍色外框高亮該物件。
