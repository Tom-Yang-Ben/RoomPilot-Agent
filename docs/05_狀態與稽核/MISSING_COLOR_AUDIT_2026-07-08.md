# Missing Color Audit 2026-07-08

資料來源：目前本機服務 `http://127.0.0.1:8002/api/site-data` 回傳的合併後家具資料。

## 結論

- 合併後家具總數：6978 筆。
- `color` 缺漏或仍為 `尚未整理`：2686 筆。
- 可先由名稱或材質字串推測顏色：970 筆。
- 仍無法可靠推測顏色：1716 筆。
- 這不是單一冰箱問題，而是資料清洗層尚未完整抽取家具名稱中的色彩資訊。

## 可先回填的顏色群

同一家具可能同時命中多個顏色，例如 `白色/木`、`灰綠色/淺棕色`，因此以下數量可重疊。

| 推測顏色 | 命中數 | 依據關鍵字範例 |
|---|---:|---|
| 白色 | 264 | 白色、米白色、white、off-white、cream |
| 淺木色 | 200 | 淺木、橡木、oak、birch、ash、beech、pine、bamboo、rattan |
| 米色 | 134 | 米色、米白、beige、sand、khaki |
| 黑色 | 122 | 黑色、black |
| 灰色 | 116 | 灰色、灰、grey、gray、charcoal |
| 銀色 | 100 | 銀色、silver、stainless、steel、chrome、aluminium |
| 棕色 | 64 | 棕色、咖啡、brown、walnut、wood effect |
| 藍色 | 52 | 藍色、blue、navy |
| 紅色 | 32 | 紅色、red、pink、rose |
| 黃色 | 30 | 黃色、yellow、gold、brass |
| 綠色 | 22 | 綠色、green、sage |

## 缺漏最多的家具類型

| 類型 | 缺 color 筆數 |
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
| bed | 37 |
| electric-fan | 37 |
| wall-art | 37 |
| fridge-freezer | 34 |
| vacuum-cleaner | 33 |
| office-chair | 32 |
| washing-machine | 32 |
| rug | 28 |
| wardrobe | 27 |
| hair-dryer | 27 |
| runner-small-rug | 22 |
| outdoor-furniture | 22 |
| cabinets-cupboard | 20 |
| door-mat | 19 |
| trolley | 19 |
| wall-mirror | 18 |
| extractor-hood | 18 |
| robot-vacuum | 16 |
| chests-of-drawer | 15 |
| dining-table | 14 |
| floor-lamp | 12 |
| air-purifier | 12 |
| bedside-table | 9 |
| tv-bench | 8 |
| dishwasher | 8 |
| mirror | 7 |
| standing-mirror | 7 |
| lamp-shades-base | 6 |
| shelving-unit | 5 |
| sofa-bed | 5 |

## 代表例

### 白色

- `fi-cabinets-cupboards-09-skruvby-cabinet-with-doors-white-70x90-cm`：SKRUVBY 附門收納櫃，白色，70x90 公分。
- `fi-cabinets-cupboards-24-eket-cabinet-combination-with-legs-whitewood-70x35x80-cm`：EKET 附腳收納櫃組合，白色/木，70x35x80 公分。
- `fi-chests-of-drawers-09-lastare-chest-of-4-drawers-white-40x42x100-cm`：LASTARE 四斗抽屜櫃，白色，40x42x100 公分。
- `ext_5454ddb1beb4c6`：HAUGA - 雙門櫃，白色，70x116 公分。

### 淺木色

- `fi-kids-chairs-stools-18-po-ng-children-s-armchair-birch-veneerskogbo-animal-pattern`：POÄNG 兒童扶手椅，樺木實木貼皮/Skogbo 動物圖案。
- `fi-cabinets-cupboards-29-tonstad-storage-comb-w-sliding-glass-doors-oak-veneerclear-glass-82x47x201-cm`：TONSTAD 附滑動玻璃門收納組合，橡木實木貼皮/透明玻璃。
- `fi-cabinets-cupboards-34-billy-oxberg-bookcase-with-glass-doors-oak-effect-80x30x202-cm`：BILLY / OXBERG 附玻璃門書櫃，橡木紋。
- `ext_b6e4b8007b10c8`：VOXLÖV Chair - light bamboo。

### 米色

- `fi-cabinets-cupboards-16-f-rjkarl-cabinet-off-white-77x45x116-cm`：FÄRJKARL 收納櫃，米白色。
- `fi-armchairs-04-dyvlinge-swivel-easy-chair-kelinge-beige`：DYVLINGE 旋轉休閒椅，Kelinge 米色。
- `fi-large-medium-rugs-09-j-rnv-g-rug-low-pile-ornament-pattern-pinkbeige-200x300-cm`：JÄRNVÄG 短毛地毯，粉紅色/米色。
- `ext_16c3e4996bc552`：BESTÅ - 上牆式收納櫃組合，白色/Krukmakare 米色。

### 銀色 / 金屬色

- `ext_9c2077d9c35b7f`：AmazonBasics 4 Step Aluminium Lightweight Folding Step Ladder Silver。
- `ext_cf24b79b605f34`：AmazonBasics 1500W Oscillating Ceramic Heater, Silver。
- `ext_50aa649f87a41c`：Ravenna Home Traditional Table Lamp, Brushed Nickel。
- `ext_78449234d80dd5`：Stone & Beam Culver Reclaimed Industrial Wood Coffee Table, Natural and Steel。

### 灰色

- `fi-cabinets-cupboards-15-s-gm-stare-cabinet-light-grey-blue-83x36x128-cm`：SÅGMÄSTARE 收納櫃，淺灰藍色。
- `fi-cabinets-cupboards-20-ledamot-cabinet-light-grey-beige-150x42x75-cm`：LEDAMOT 收納櫃，淺灰米色。
- `fi-cabinets-cupboards-25-eket-cabinet-combination-with-legs-dark-greywood-70x35x80-cm`：EKET 附腳收納櫃組合，深灰色/木。
- `fi-outdoor-seating-06-vittsk-r-2-seat-modular-sofa-outdoorplastic-rattan-dark-grey`：VITTSKÄR 雙人座模組沙發，塑膠藤深灰色。

## 建議清洗規則

1. 先建立 `infer_color_from_name()`，從 `name_zh_raw`、`name_en`、`material` 抽取顏色。
2. 支援多色家具，`color` 可顯示為 `白色 / 淺木色`，資料層可另保留 `color_tags`。
3. 抽色優先順序：中文明確顏色 > 英文明確顏色 > 材質推測色 > 不回填。
4. 材質推測要保守，例如 `oak` 可回填 `淺木色`，但 `wood` 單獨出現不一定要回填，避免深木/淺木誤判。
5. 家電類缺色若沒有 `white/silver/black` 等字樣，不建議硬猜，應改由模型預覽或圖片分析補。
6. 前端黑底判斷可以繼續保留作為保護，但資料根治應回填 catalog。

## 下一步可落地

- 新增資料清洗腳本，對 2686 筆缺漏家具產生 `color_fix_candidates.json`。
- 先自動回填高信心 970 筆，低信心 1716 筆保留待人工或圖片分析。
- 回填後重新檢查 `/library`、`/styles`、`/scene` 的顏色篩選與淺色模型黑底顯示。
