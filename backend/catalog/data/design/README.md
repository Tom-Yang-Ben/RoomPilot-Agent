# 設計語彙知識庫

成果報告第 3 章「設計風格與語彙」的唯一資料來源。與 `../engineering/`
的工程知識庫平行：那邊回答「要做哪些工項、多少錢、多久」，這邊回答
「這是什麼風格、為什麼這樣配色、每個空間的設計邏輯是什麼」。

## 檔案

| 檔案 | 內容 | 對應鍵 |
|---|---|---|
| `design_source_registry.json` | 來源登錄，所有知識必須引用其中的 `source_id` | — |
| `style_vocabulary.json` | 造型語言、代表元素、照明手法、應避免做法 | `style_id` |
| `color_strategy.json` | 主／次／點綴色比例、色溫、明度對比、色卡判讀規則 | `style_id` |
| `material_vocabulary.json` | 主副材質、表面處理、對比邏輯、地牆關係 | `style_id` |
| `room_design_principles.json` | 逐房設計重點、動線、照明、收納與常見問題 | `room_type` |

`style_id` 與 `backend/catalog/data/taiwan_style_cards.json`、
`furniture_catalog_6styles_zh.json` 同一組六個值。`room_type` 與
`backend/server/scene_service.py` 的 `SPACE_DEFAULTS` 同一組十個值。
新增風格或房型時兩邊必須同時補齊，`tests/test_design_knowledge.py` 會擋。

## 可信度契約

`SRC-DESIGN-EDITORIAL-V1` 是**團隊內部編纂**，不是外部權威引用，因此所有
語彙知識的 `confidence` 一律是 `medium`，報告會如實標示。

這樣分級是刻意的：

- 設計語彙是專業判斷與慣例，本來就沒有單一權威標準可引用。標成
  `high` 會讓報告看起來有外部背書，實際上沒有。
- 報告中的**數字**（面積、數量、金額、工期）一律來自鎖定版快照與
  工程知識庫，不由這裡產生。這裡只提供論述語言。

因此本目錄刻意**不寫具體尺寸數值**（例如走道淨寬幾公分、吊燈離桌面幾
公分）。那類數字需要可查證的法規或標準出處；在補上真實來源之前寫進來，
等於用 medium confidence 的文件冒充規範依據。需要這類數值時，補進
`../engineering/construction_knowledge.jsonl` 並附上真實出處。

## 升級為外部引用

若要把某條知識升級成 `high`：

1. 在 `design_source_registry.json` 新增一筆真實來源，`source_type` 改為
   出版品或標準的實際類型，`external_reference` 設為 `true`，填上可查證的
   `url` 與 `retrieved_date`。
2. 把對應知識的 `source_id` 指到該筆，`confidence` 改為 `high`。
3. 跑 `pytest -q tests/test_design_knowledge.py` 確認來源引用完整。
