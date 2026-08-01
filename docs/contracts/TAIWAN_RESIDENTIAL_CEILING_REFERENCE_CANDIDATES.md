# 台灣住宅天花參考案例候選清單

本清單是依 `MATERIAL_CEILING_REFERENCE_EXPERIENCE_CONTRACT.md` 蒐集的第一批候選來源。它只記錄外部案例頁、可觀察到的設計語言與 Agent 關鍵詞；未下載、內嵌或上傳任何來源圖片。

使用前需逐張確認畫面確實符合卡片描述，並取得可在產品中顯示的授權，或改以來源連結開啟外部案例頁。

## 優先候選

| ID | 形式 | 台灣住宅案例 | 可用的視覺與工法語言 | 不可推論的內容 |
| --- | --- | --- | --- | --- |
| `tw_wood_slat_01` | 單向木格柵天花 | [高雄 35 坪人文和風日系宅，DECOmyplace](https://decomyplace.com/n.php?id=11571) | 玄關格柵、木皮層次、軌道燈、溫暖木質與日式住宅語言。 | 不能推論固定格柵間距、特定木皮品牌、所有房間都適用。 |
| `tw_wood_slat_02` | 線性木格柵天花 | [65 坪現代東方人文住宅，Searchome](https://www.searchome.net/article.aspx?id=50053) | 線性木格柵延伸、景深、公共區域分界、石材與木質的沉穩對比。 | 不能推論豪宅尺度、同款石材或原始樓高。 |
| `tw_linear_light_01` | 平釘天花與線型燈 | [高雄輕鋼架、線條燈與間接照明工程案例](https://www.gfdesign.com.tw/work123.htm) | 平整天花、鋁條線型燈、間接照明、台灣住宅施工情境。 | 不能把工程頁當成單一商品型錄或固定 15 cm 吊頂標準。 |
| `tw_lighting_01` | 嵌燈與線性照明 | [台北私宅照明案例，久耀照明](https://www.jiouyao.com.tw/album_d.php?id=59&lang=tw&tb=2) | 台灣私宅、嵌燈、線型照明與木地板的整體光感。 | 頁面可能調整或重新導向，使用前需確認原始案例頁與圖片授權。 |

## Agent 語言對照

### `tw_wood_slat_01`

```json
{
  "reference_kind": "real_case",
  "visual_language": [
    "single-direction wood slats",
    "warm wood veneer",
    "soft entry lighting",
    "Japanese-inspired residential calm"
  ],
  "construction_language": [
    "wood slat ceiling",
    "track lighting integrated below slats"
  ],
  "suitable_spaces": ["entryway", "hallway", "living_room"],
  "constraints": [
    "confirm ceiling height before adding a dropped slat ceiling",
    "coordinate lighting, HVAC and maintenance access"
  ]
}
```

### `tw_wood_slat_02`

```json
{
  "reference_kind": "real_case",
  "visual_language": [
    "linear wood slats extending the view",
    "warm dark wood with stone contrast",
    "depth and rhythm across open public spaces"
  ],
  "construction_language": [
    "linear wood slat ceiling",
    "partial ceiling zone to define living and dining areas"
  ],
  "suitable_spaces": ["living_room", "kitchen", "hallway"],
  "constraints": [
    "do not force the treatment over every room",
    "preserve daylight and avoid visual compression in low ceilings"
  ]
}
```

### `tw_linear_light_01`

```json
{
  "reference_kind": "real_case",
  "visual_language": [
    "clean flat ceiling",
    "recessed linear illumination",
    "soft indirect perimeter glow"
  ],
  "construction_language": [
    "flat suspended ceiling",
    "recessed aluminum linear light channel",
    "indirect lighting recess"
  ],
  "suitable_spaces": ["living_room", "bedroom", "hallway", "kitchen"],
  "constraints": [
    "drop depth depends on fixture, HVAC, fire systems and existing ceiling height",
    "confirm glare control and maintenance access"
  ]
}
```

## 尚未完成

- 將確認後的外部案例轉成可顯示的產品參考卡。
- 取得或確認圖片使用權；未完成前只能外連，不可下載到專案或嵌入介面。
- 為每個天花形式補至少三個真實住宅案例，避免單一案例代表所有風格。
- 建立 `reference_cases` 結構化資料來源，與 KAI PostgreSQL 商品資料和本機表面材質資料分開。
