# IKEA GLB 下載器

這個專案使用 `ikea_category_glb_downloader.py` 從 IKEA 商品分類頁尋找可用的 3D 模型，並下載 `.glb` 檔案，同時產生 CSV / JSON metadata。

目前支援的 IKEA 站點：

| 代碼 | 站點 | Base URL |
| --- | --- | --- |
| `fi` | Finland | `https://www.ikea.com/fi/en` |
| `jp` | Japan | `https://www.ikea.com/jp/en` |

## 安裝

```bash
pip install -r requirements.txt
```

## 互動式下載

```bash
python ikea_category_glb_downloader.py
```

互動模式會依序詢問：

1. IKEA 站點，例如 `fi` 或 `jp`
2. 家具分類或細分類代碼，例如 `office-chairs`、`desks`、`rugs`
3. 要下載的 GLB 數量

輸出會放在：

```text
downloaded-files/<site>-<category>/
```

例如：

```text
downloaded-files/fi-office-chairs/
downloaded-files/jp-bookcases/
```

## 批次下載

腳本也包含幾個批次模式，會依分類逐一搜尋，並用 registry 避免重複下載。

```bash
python ikea_category_glb_downloader.py --table-batch
python ikea_category_glb_downloader.py --bed-batch
python ikea_category_glb_downloader.py --wardrobe-batch
python ikea_category_glb_downloader.py --rug-batch
```

地毯也支援單一分類補跑：

```bash
python ikea_category_glb_downloader.py --rug-category=sheepskins-cowhides
```

## 輸出檔案

| 檔案 | 說明 |
| --- | --- |
| `.glb` | IKEA 商品 3D 模型 |
| `*_glb_metadata.csv` | 下載商品 metadata CSV |
| `*_glb_metadata.json` | 下載商品 metadata JSON |
| `_registry.json` | 批次模式用的去重紀錄 |

## 家具與細分類清單

以下分類可作為互動式下載的輸入代碼。下載器會用「細分類代碼」對應 IKEA Finland 的 `/cat/.../` 分類頁。

## Bookcases and shelving / 書櫃與層架

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `bookcases` | Bookcases | 書櫃 | `bookcases-10382` |
| `shelving-units` | Shelving units | 層架組 | `shelving-units-10397` |
| `wall-shelves` | Wall shelves | 壁架 | `wall-shelves-10398` |

## Sofas and armchairs / 沙發與扶手椅

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `sofas` | All sofas | 所有沙發 | `sofas-fu003` |
| `fabric-sofas` | Fabric sofas | 布沙發 | `fabric-sofas-10661` |
| `leather-sofas` | Leather and coated fabric sofas | 皮革與塗層布沙發 | `leather-coated-fabric-sofas-10662` |
| `sofa-beds` | Sofa beds | 沙發床 | `sofa-beds-10663` |
| `modular-sofas` | Modular sofas | 模組沙發 | `modular-sofas-31786` |
| `armchairs` | Armchairs | 扶手椅 | `armchairs-16239` |

## Chairs, stools and benches / 椅子、凳子與長凳

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `chairs` | All chairs | 所有椅子 | `tables-chairs-fu002` |
| `dining-chairs` | Dining chairs | 餐椅 | `dining-chairs-25219` |
| `office-chairs` | Office and desk chairs | 辦公椅與書桌椅 | `desk-chairs-20652` |
| `armchairs` | Armchairs | 扶手椅 | `armchairs-16239` |
| `stools-benches` | Stools and benches | 凳子與長凳 | `stools-benches-16244` |
| `gaming-chairs` | Gaming chairs | 電競椅 | `gaming-chairs-47067` |

## Tables and desks / 桌子與書桌

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `tables` | All tables and desks | 所有桌子與書桌 | `tables-desks-fu004` |
| `dining-tables` | Dining tables | 餐桌 | `dining-tables-21825` |
| `desks` | Desks and computer desks | 書桌與電腦桌 | `desks-computer-desks-20649` |
| `coffee-tables` | Coffee tables | 咖啡桌 / 茶几 | `coffee-tables-10705` |
| `bedside-tables` | Bedside tables | 床邊桌 | `bedside-tables-20656` |
| `bar-tables` | Bar tables | 吧台桌 | `bar-tables-20862` |

## Beds and mattresses / 床與床墊

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `beds` | All beds | 所有床 | `beds-bm003` |
| `bed-frames` | Bed frames | 床架 | `beds-16284` |
| `sofa-beds` | Sofa beds | 沙發床 | `sofa-beds-10663` |
| `mattresses` | Mattresses | 床墊 | `mattresses-bm002` |
| `bedside-tables` | Bedside tables | 床邊桌 | `bedside-tables-20656` |

## Wardrobes and clothes storage / 衣櫃與衣物收納

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `wardrobes` | All wardrobes | 所有衣櫃 | `wardrobes-19053` |
| `pax-wardrobes` | PAX wardrobes | PAX 衣櫃 | `pax-wardrobes-19086` |
| `open-wardrobes` | Open wardrobes | 開放式衣櫃 | `open-wardrobes-11480` |
| `clothes-racks` | Clothes racks and shoe racks | 衣架與鞋架 | `clothes-stands-shoe-racks-10456` |
| `shoe-cabinets` | Shoe cabinets | 鞋櫃 | `shoe-cabinets-10456` |

## Storage furniture / 收納家具

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `storage-furniture` | All storage furniture | 所有收納家具 | `storage-furniture-st001` |
| `storage-solution-systems` | Storage solution systems | 收納系統 | `storage-solution-systems-46052` |
| `cabinets-cupboards` | Cabinets and cupboards | 櫃子與櫥櫃 | `cabinets-cupboards-st003` |
| `display-cabinets` | Display cabinets | 展示櫃 | `display-cabinets-10410` |
| `chests-of-drawers` | Chests of drawers and drawer units | 抽屜櫃與抽屜組 | `chest-of-drawers-drawer-units-st004` |
| `sideboards` | Sideboards, buffets and console tables | 邊櫃、餐邊櫃與玄關桌 | `sideboards-buffets-console-tables-30454` |
| `trolleys` | Trolleys | 推車 | `trolleys-fu005` |
| `room-dividers` | Room dividers | 屏風 / 空間隔間 | `room-dividers-46080` |

## TV and media furniture / 電視與影音家具

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `tv-media-furniture` | All TV and media furniture | 所有電視與影音家具 | `tv-media-furniture-10475` |
| `tv-benches` | TV benches | 電視櫃 | `tv-benches-10810` |

## Outdoor furniture / 戶外家具

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `outdoor-furniture` | All outdoor furniture | 所有戶外家具 | `garden-furniture-od003` |
| `outdoor-seating` | Outdoor seating | 戶外座椅 | `outdoor-seating-700350` |
| `outdoor-dining` | Outdoor dining | 戶外餐桌椅 | `outdoor-dining-700351` |
| `sun-loungers-hammocks` | Sun loungers and hammocks | 躺椅與吊床 | `sun-loungers-hammocks-21963` |
| `outdoor-coffee-side-tables` | Outdoor coffee and side tables | 戶外咖啡桌與邊桌 | `garden-coffee-side-tables-700192` |

## Children's furniture / 兒童家具

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `childrens-furniture` | Children's small furniture | 兒童小型家具 | `childrens-small-furniture-18767` |
| `kids-chairs-stools` | Kids chairs and stools | 兒童椅與凳子 | `kids-chairs-stools-18769` |
| `childrens-tables` | Children's tables | 兒童桌 | `childrens-tables-18768` |
| `childrens-stools-benches` | Children's stools and benches | 兒童凳與長凳 | `childrens-stools-benches-45816` |
| `kids-armchairs` | Kids armchairs | 兒童扶手椅 | `kids-armchairs-20483` |

## Mirrors / 鏡子

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `mirrors` | All mirrors | 所有鏡子 | `mirrors-20489` |
| `wall-mirrors` | Wall mirrors | 壁鏡 | `wall-mirrors-20490` |
| `large-mirrors` | Large mirrors | 大型鏡子 | `large-mirrors-24858` |
| `standing-mirrors` | Standing mirrors | 立鏡 | `standing-mirrors-20491` |
| `mirror-cabinets` | Mirror cabinets | 鏡櫃 | `mirror-cabinets-20820` |

## Rugs and mats / 地毯與踏墊

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `rugs` | All rugs | 所有地毯 | `rugs-10653` |
| `large-medium-rugs` | Large and medium rugs | 大型與中型地毯 | `large-medium-rugs-10692` |
| `runner-small-rugs` | Runners and small rugs | 走道毯與小地毯 | `runner-small-rugs-10689` |
| `round-rugs` | Round rugs | 圓形地毯 | `round-rugs-20543` |
| `outdoor-rugs` | Outdoor rugs | 戶外地毯 | `outdoor-rugs-34204` |
| `door-mats` | Door mats | 門墊 | `door-mats-10698` |
| `handmade-rugs` | Handmade rugs | 手工地毯 | `handmade-rugs-39267` |
| `anti-slip-rug-underlays` | Anti-slip and rug underlays | 止滑墊與地毯底墊 | `anti-slip-rug-underlays-10699` |
| `sheepskins-cowhides` | Cowhides, sheepskins and faux fur rugs | 牛皮、羊皮與仿毛地毯 | `sheepskins-cowhides-20544` |
| `childrens-rugs-curtains` | Children's rugs and curtains | 兒童地毯與窗簾 | `childrens-rugs-curtains-18774` |
| `nursery-rugs-and-curtains` | Nursery rugs and curtains | 嬰幼兒房地毯與窗簾 | `nursery-rugs-and-curtains-18699` |

## Lighting / 燈具

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `lamps` | All lamps | 所有燈具 | `lamps-li002` |
| `table-lamps` | Table lamps | 桌燈 | `table-lamps-10732` |
| `floor-lamps` | Floor lamps | 立燈 | `floor-lamps-10731` |
| `work-lamps` | Work lamps | 工作燈 | `work-lamps-20502` |
| `lamp-shades-bases` | Lamp shades, bases and cords | 燈罩、燈座與電線 | `lamp-shades-bases-cords-10728` |

## Decor and small storage / 裝飾與小型收納

| 細分類代碼 | 英文名稱 | 中文名稱 | IKEA category path |
| --- | --- | --- | --- |
| `storage-boxes-baskets` | Storage boxes and baskets | 收納盒與籃子 | `storage-boxes-baskets-10550` |
| `flower-pots-planters` | Flower pots and planters | 花盆與植栽盆 | `flower-pots-planters-pp004` |

## 注意事項

不是每個 IKEA 商品頁都有 GLB。腳本會跳過沒有 3D 模型的商品，並繼續搜尋下一個商品。

批次模式會用 `_registry.json` 依照 product id、product URL、GLB URL 和檔案 hash 去重，避免重複下載。

## License

本專案參考 `apinanaivot/IKEA-3d-model-batch-downloader`，並沿用 GPL-3.0 授權。詳見 [LICENSE](LICENSE)。
