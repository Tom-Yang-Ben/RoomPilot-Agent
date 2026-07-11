# Furniture Missing Color / Material / Role Audit 2026-07-08

資料來源：目前本機服務 `http://127.0.0.1:8002/api/site-data` 回傳的合併後家具資料。

## 結論

- 合併後家具總數：6978 筆。
- `color` 缺漏或仍為 `尚未整理`：2686 筆。
- `material` 缺漏或仍為 `尚未整理`：5456 筆。
- `role` 缺漏或仍為 `尚未整理`：3952 筆。
- 三者同時缺漏：1326 筆。

## 缺漏重疊

| 缺漏組合 | 筆數 | 說明 |
|---|---:|---|
| color + material | 2128 | 名稱裡常可推顏色與材質，適合先做文字抽取。 |
| color + role | 1680 | 同時缺色彩與家具用途，會影響篩選與配置說明。 |
| material + role | 3138 | 最常見的規則層缺口，會影響風格判斷與配置理由。 |
| color + material + role | 1326 | 高優先整理批次。 |

## Color 缺漏最多的類型

| 類型 | 缺漏筆數 |
|---|---:|
| desk | 258 |
| stool-bench | 246 |
| fabric-sofa | 224 |
| decoration | 209 |
| sofa | 158 |
| bed-frame | 129 |
| armchair | 108 |
| lamp | 98 |
| cabinet-cupboard | 73 |
| bookcase | 66 |
| dining-chair | 64 |
| leather-sofa | 63 |
| large-medium-rug | 52 |
| small-kitchen-appliance | 48 |
| pillow-cushion | 45 |
| air-conditioner | 43 |
| table-lamp | 41 |
| coffee-table | 40 |
| planter | 38 |
| toaster | 38 |

## Material 缺漏最多的類型

| 類型 | 缺漏筆數 |
|---|---:|
| stool-bench | 412 |
| desk | 395 |
| decoration | 317 |
| fabric-sofa | 317 |
| sofa | 310 |
| large-medium-rug | 268 |
| armchair | 213 |
| bed-frame | 197 |
| bookcase | 161 |
| dining-chair | 157 |
| lamp | 135 |
| runner-small-rug | 124 |
| table-lamp | 101 |
| wall-art | 99 |
| office-chair | 98 |
| coffee-table | 95 |
| rug | 93 |
| planter | 83 |
| pillow-cushion | 76 |
| cabinet-cupboard | 70 |

## Role 缺漏最多的類型

| 類型 | 缺漏筆數 |
|---|---:|
| stool-bench | 570 |
| fabric-sofa | 489 |
| decoration | 363 |
| table-lamp | 171 |
| lamp | 170 |
| leather-sofa | 148 |
| cabinet-cupboard | 121 |
| wall-art | 119 |
| planter | 116 |
| rug | 101 |
| pillow-cushion | 88 |
| trolley | 74 |
| outdoor-furniture | 71 |
| small-kitchen-appliance | 66 |
| chests-of-drawer | 64 |
| floor-lamp | 64 |
| wall-mirror | 63 |
| door-mat | 50 |
| fridge-freezer | 50 |
| wardrobe | 46 |

## 代表缺漏資料

### Color 缺漏代表

| furniture_id | 類型 | 名稱 | 已有 material | 已有 role |
|---|---|---|---|---|
| `fi-childrens-tables-03-grejsimojs-children-s-table-woodorange-84x42-cm` | childrens-table | GREJSIMOJS 兒童桌，木/橘色，84x42 公分 | 空 | 空 |
| `fi-kids-armchairs-02-po-ng-children-s-armchair-cushion-skogbo-animal-pattern` | armchair | POÄNG 兒童扶手椅椅墊，Skogbo 動物圖案 | 空 | 輔助座位 |
| `fi-kids-chairs-stools-05-grejsimojs-cover-for-children-s-chair-faux-furpink` | kids-chairs-stool | GREJSIMOJS 兒童椅布套，人造毛皮/粉紅色 | 空 | 空 |
| `fi-large-medium-rugs-04-rende-rug-high-pile-yellow-120x180-cm` | large-medium-rug | ÄRENDE 長毛地毯，黃色，120x180 公分 | 空 | 區域界定軟裝 |
| `fi-outdoor-dining-05-soluppg-ng-folding-table-eucalyptus-82-cm` | outdoor-dining | SOLUPPGÅNG 折疊桌，尤加利木，82 公分 | 空 | 空 |

### Material 缺漏代表

| furniture_id | 類型 | 名稱 | 已有 color | 已有 role |
|---|---|---|---|---|
| `fi-childrens-furniture-01-agam-junior-chair-black` | childrens-furniture | AGAM 少年椅，黑色 | black | 空 |
| `fi-childrens-furniture-02-agam-junior-chair-white` | childrens-furniture | AGAM 少年椅，白色 | white | 空 |
| `fi-childrens-stools-benches-04-b-nkkamrat-bench-pad-dot-pattern-90x50x3-cm` | childrens-stools-benche | BÄNKKAMRAT 長凳墊，圓點圖案，90x50x3 公分 | grey | 空 |
| `fi-childrens-tables-01-l-tt-children-s-table-with-2-chairs-whitepine` | childrens-table | LÄTT 兒童桌附2椅，白色/松木 | beige, white | 空 |
| `fi-childrens-tables-05-mammut-children-s-table-inoutdoorlight-blue-85-cm` | childrens-table | MAMMUT 兒童桌，室內外/淺藍色，85 公分 | blue | 空 |

### Role 缺漏代表

| furniture_id | 類型 | 名稱 | 已有 color | 已有 material |
|---|---|---|---|---|
| `fi-childrens-furniture-01-agam-junior-chair-black` | childrens-furniture | AGAM 少年椅，黑色 | black | 空 |
| `fi-childrens-stools-benches-02-sm-stad-bench-with-toy-storage-whitelight-green-90x52x48-cm` | childrens-stools-benche | SMÅSTAD 附玩具收納長凳，白色/淺綠色，90x52x48 公分 | green, white | 空 |
| `fi-childrens-tables-01-l-tt-children-s-table-with-2-chairs-whitepine` | childrens-table | LÄTT 兒童桌附2椅，白色/松木 | beige, white | 空 |
| `fi-childrens-tables-07-kritter-children-s-table-white-59x50-cm` | childrens-table | KRITTER 兒童桌，白色，59x50 公分 | white | 空 |
| `fi-childrens-tables-08-sundvik-children-s-table-white-76x50-cm` | childrens-table | SUNDVIK 兒童桌，白色，76x50 公分 | white | 空 |

## 補資料建議順序

1. 先補 `color`：直接影響前端色彩篩選、淺色家具黑底判斷與風格搭配。
2. 再補 `material`：可從名稱抽 `木/松木/橡木/金屬/布/皮革/藤/玻璃/塑膠/陶瓷/石材` 等，影響風格與材質推薦。
3. 再補 `role`：應以 `normalized_type` 對應用途規則，例如主座位、輔助座位、桌面、收納、照明、軟裝、裝飾、家電、動線輔助。
4. 三者都缺的 1326 筆應列為第一批資料清洗候選。

## 建議未來輸出

- `color_fix_candidates.json`：由名稱/材質抽色，標記 confidence。
- `material_fix_candidates.json`：由名稱/材質關鍵字抽材質，標記 confidence。
- `role_fix_candidates.json`：由 `normalized_type` 映射 role，適合作為規則表而不是逐筆人工填。
