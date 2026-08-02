# 客廳定版樣本 v1（floor04・使用者定版）

> 2026-08-03 Ancai 拍板「寫定樣本」：專案 `b2b2c83f` rev 474 的客廳四件組
> （側欄 #4/#5/#6/#16），使用者親手微調後的終版。四件已在專案內 `locked`，
> generate 重排與拖曳誤觸都不會動它們。此文件是位置／物件／擺設的規格快照，
> 供之後 generate 驗收、其他專案套樣、以及引擎客廳規則的對照基準。

## 房間

- 客廳 `room-split-1785592992188-1`，bbox x[666,1270] × y[33,562]（絕對 cm，未重定標巨人屋座標）
- 北緣：陽台門（668-833）＋落地窗（880-1063）——**全段淨空**
- 西緣上段：通陽台開口（y33-214）——留動線
- 東牆：整面實牆（本房唯一無窗無門牆）＝ TV 牆
- 南緣：浴室門（x856-946）

## 物件（型錄真身）

| # | 型別 | 型號 | 尺寸（寬×深×高 cm） | catalog id |
|---|---|---|---|---|
| 4 | tv-bench | Movian TV Unit with Storage（Oak/White） | 155×40×44 | `abo-tables-130-amazon-brand-movian-tv-unit-with-stor…` |
| 5 | fabric-sofa | Stone & Beam Bartow（灰石色） | 229×103.1×103.4 | `abo-fabric-sofas-345-amazon-brand-stone-beam-bartow-…` |
| 6 | coffee-table | Movian Adour 橢圓茶几 | 108.3×54.2×39 | `abo-coffee-tables-14-amazon-brand-movian-adour-oval-…` |
| 16 | flower-pots-planter | Rivet Surrey 陶瓷花盆（白，Small） | 22.4×22.4×35.8 | `abo-flower-pots-planters-38-amazon-brand-rivet-surre…` |

## 位置與擺設（絕對 cm・rotation 為 2D 場景角）

| # | 中心位置 | rot | 擺設語意 |
|---|---|---|---|
| 4 電視櫃 | (1210.4, 401.1) | 90 | 貼 **東牆**（TV 牆），面西朝沙發 |
| 5 沙發 | (910.4, 386.1) | 270 | 房中偏西，**面東正對電視**；背後留通往陽台開口的動線 |
| 6 茶几 | (1035.4, 386.1) | 90 | 沙發與電視**同軸居中**（y≈386–401 觀影軸） |
| 16 植栽 | (1210.4, 531.1) | 0 | 東南角點景，緊鄰 TV 牆南端 |

## 關鍵間距（驗收基準）

- 沙發前緣 → 電視櫃前緣：**228.5cm**（觀影淨距；巨人屋座標，重定標後 ≈91cm 視覺同比例）
- 沙發前緣 → 茶几近緣：**46cm**（人體工學取物距）
- 三件套共線容差：y 軸 ±15cm 內
- 北緣門窗、西緣陽台開口、南緣浴室門前:零家具

## 模型朝向標注

沙發（abo 系）`modelOrientationDeg=180`；電視櫃／茶几／植栽無需標注。

## 套樣方式

新專案／重 generate 後比照本表逐件校位（validate 全過再寫入三處：
`layout_2d.furniture`＋`schemes[A/B]`），或直接以 locked 快照複製。
