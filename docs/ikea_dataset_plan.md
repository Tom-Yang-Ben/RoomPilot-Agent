# IKEA-Dataset 家具主線規劃

最後更新：2026-06-28

這份文件是 `PROJECT_CONTEXT.md` 的補充文件，專門整理：

1. 資料夾架構
2. 命名規則
3. 第一批樣本怎麼挑
4. 後續 3D 生成與前端擺放流程

## 1. 目標

我們要從 [IKEA-Dataset](https://github.com/valexande/IKEA-Dataset) 的客廳資料中，先做 10 種最常出現在客廳的家具，之後把它們放進 Three.js 的 1m 網格地板裡，做成可拖曳、可旋轉、可磁吸擺放的家具系統。

第一批主線家具：

1. 沙發
2. 扶手椅
3. 單人椅
4. 茶几
5. 邊几
6. 電視櫃
7. 書櫃
8. 收納櫃
9. 腳凳
10. 層架 / 展示櫃

## 2. 建議資料夾架構

以下是建議的工作資料夾，不是強制，但之後都照這個走最省事：

```text
test_furniture/
  docs/
    ikea_dataset_plan.md
  dataset/
    ikea/
      raw/
        living_room_1/
        living_room_2/
      selected/
        sofa/
        armchair/
        chair/
        coffee_table/
        side_table/
        tv_stand/
        bookshelf/
        storage_cabinet/
        ottoman/
        shelf_display/
  sf3d/
    inputs/
    outputs_raw/
    outputs_normalized/
    metadata/
    scripts/
  web_fastapi/
    static/
      models/
      previews/
```

## 3. 命名規則

命名要固定，後面才好寫腳本、好找檔案、好對照網頁。

建議格式：

```text
{category}_{source}_{item_id}_{variant}
```

例子：

```text
sofa_ikea_0001_source.jpg
sofa_ikea_0001_raw.glb
sofa_ikea_0001_normalized.glb
sofa_ikea_0001.json
```

分類英文對應：

- `sofa`
- `armchair`
- `chair`
- `coffee_table`
- `side_table`
- `tv_stand`
- `bookshelf`
- `storage_cabinet`
- `ottoman`
- `shelf_display`

如果同一個家具有多張圖，可以再加 view：

```text
sofa_ikea_0001_front.jpg
sofa_ikea_0001_angle.jpg
sofa_ikea_0001_side.jpg
```

## 4. 第一批樣本怎麼挑

第一批不要貪多。每一類先挑 1 到 3 張最乾淨、最能代表家具外型的圖。

共同標準：

- 家具主體清楚
- 背景不要太亂
- 遮擋不要太重
- 輪廓要容易看懂
- 優先有尺寸資訊
- 優先能看出底部和接地

各類重點：

- 沙發：先選 2 到 3 人座，扶手與靠背完整。
- 扶手椅：選輪廓明顯、扶手清楚、背靠高度分明。
- 單人椅：選結構簡單、椅腳清楚、適合校正接地。
- 茶几：選桌面乾淨、桌腳簡單、長寬比例清楚。
- 邊几：選尺寸較小、方形或圓形輪廓明確。
- 電視櫃：選長條型、水平感強、底部接地清楚。
- 書櫃：選直立層板結構清楚的樣本。
- 收納櫃：選盒型清楚、正面平整的樣本。
- 腳凳：選低矮、單體簡單、底部好辨識。
- 層架 / 展示櫃：選架構直線感強、層板明確的樣本。

## 5. 每一類先怎麼收

建議流程：

1. 先在 `Living Room 1.zip` 和 `Living Room2.zip` 內找圖。
2. 每類挑 1 到 3 張備選。
3. 先以「輪廓最清楚」為優先，不要先追求量。
4. 把尺寸資訊一起整理到 JSON。
5. 再進入 3D 生成。

如果同一類有很多張圖，優先順序如下：

1. 外型最清楚
2. 遮擋最少
3. 尺寸最完整
4. 最接近客廳常見款式

## 6. 3D 生成流程

每個家具的標準流程：

1. 先做 raw GLB。
2. 檢查姿態與幾何是否合理。
3. 做 normalize。
4. 設定 bottom-center pivot。
5. 把底部放到 `Y = 0`。
6. 套真實尺寸。
7. 輸出到 `web_fastapi/static/models/`。

## 7. 網格與擺放規格

- 地板用 `GridHelper`。
- 主要單位是 `1 m x 1 m`。
- 家具進場後必須對應真實尺寸。
- 家具放上地板時要看得出 footprint。
- 後續要能拖曳、旋轉、吸附網格。

## 8. 之後的判斷原則

如果一張圖不夠清楚、遮擋太多、底部看不懂，就不要勉強拿去做主樣本。  
專題先追求「穩定可展示」，再追求「每張都能跑」。

