# 風格資料狀態

最後更新：2026-07-06

## 主要資料來源

1. 家具主資料：`sf3d/metadata/ikea_furniture_style_database.json`
2. 風格展示與 `/styles` 頁面也依賴同一份資料
3. 風格主視覺圖位於 `web_fastapi/static/style_images/`

## 目前風格數量

目前網站與資料庫使用 12 種風格：

1. 北歐風
2. 現代簡約風
3. 日系簡約 / 無印風
4. 北歐現代風
5. 工業風
6. 日式侘寂風
7. 美拉德風
8. 美式風
9. 美式鄉村風
10. 輕奢風
11. 古典風
12. 混搭風

## 家具資料中的風格重點欄位

1. `primary_style`
2. `style_candidates`
3. `style_confidence`
4. `style_rule_flags`
5. `style_assignment_source`
6. `manual_style_note_zh`

## 風格資料中的空間欄位

目前風格層級已補上：

1. `wall_recommendations`
2. `floor_recommendations`
3. `recommended_wall_floor_pairs_zh`

這些欄位會同時服務：

1. `/styles` 頁面展示
2. `/scene` 的牆地預設推薦
3. 後端規則挑選時的視覺方向參考

## 近期分類規則收斂

為了避免高彩度、童趣圖案、造型感過強的家具被錯分到極簡風系，規則已加入更明確旗標：

1. `novelty_motif`
2. `high_chroma`
3. `children_series`
4. `soft_kids_accessory`

這些旗標會壓低下列風格分數：

1. `scandinavian`
2. `modern`
3. `minimalist_muji`
4. `nordic_modern`
5. `wabi_sabi`

同時提高 `eclectic` 的適配機率。

## 北歐風規則補強

本次已針對 `scandinavian` 明確補上：

1. 不要明顯跳色
2. 不要高彩度撞色

同步更新：

1. `avoid_elements_zh`
   - `明顯跳色`
   - `高彩度撞色`
2. `rule.negative`
   - `orange`
   - `turquoise`
   - `multicolour`
   - `bright yellow`
   - `hot pink`
   - `primary red`
   - `high contrast kids pattern`

## 已手動修正的代表案例

以下家具原本被歸到北歐風，但已依規則重新整理：

1. `GREJSIMOJS Children's table - wood/orange 84x42 cm`
   - `scandinavian` -> `eclectic`
2. `FÖRSIKTIG Children's stool - white/turquoise`
   - `scandinavian` -> `eclectic`
3. `SKÅLBODA Armchair - orange/Ransta beige`
   - `scandinavian` -> `eclectic`
4. `ÖRFJÄLL Children's desk chair - white/Vissle light green`
   - `scandinavian` -> `modern`
5. `BÅRSLÖV 3-seat sofa-bed with chaise longue - Tibbleby light grey-turquoise`
   - `scandinavian` -> `modern`

## 風格展示資料目前狀態

1. 12 種風格都已有主圖。
2. `/styles` 已可展示牆面推薦、地板推薦、推薦搭配組合。
3. 目前仍需持續人工修正個別風格圖的圖文對位，特別是：
   - 無印 / 日系簡約
   - 日式侘寂風
   - 美式風
   - 混搭風
4. 這些問題主要不是資料欄位缺失，而是主圖裁切、標註位置與畫面元素對應仍要微調。

## 相關輸出文件

1. `docs/furniture_style_distribution_by_type.csv`
2. `docs/furniture_style_distribution.xlsx`
3. `docs/ikea_style_moodboard.docx`
