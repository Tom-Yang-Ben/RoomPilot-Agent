# 空間資料邊界

Owner：Django。開始前閱讀 `docs/owners/DJANGO.md` 與
`docs/contracts/LIGHTING_CEILING_CATALOG_CONTRACT.md`。

此目錄是可重用空間關係與格局評估 schema 的唯一位置。目前尚未有完整 runtime；新增程式前必須先定義 producer／consumer 契約。

- 輸入是已確認或帶信心度的格局幾何。
- 輸出可包含尺寸、面積、相鄰關係、門窗 host wall、窗門淨空、樑柱與可用天花區域。
- 家具 ID、GLB、圖片、授權與正式尺寸屬於 Kai catalog，不在此目錄維護。
- Graph RAG 只能檢索空間關係，不能決定幾何合法性。
- 長度單位為公分，面積單位為平方公尺。

變更需同時有 Cody producer 測試與 Bella／Ancai consumer 測試。
