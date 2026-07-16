# 風格生成交接摘要

更新日期：2026-07-03

## 1. 我目前負責什麼

我現在主要負責的是「風格生成 / 風格系統整理」，不是直接做 3D 幾何生成。

目前這塊工作的目標是：

1. 把抽象風格詞整理成 LLM 可以理解的規格。
2. 建立可重複使用的風格資料，不要每次都靠臨場亂下 prompt。
3. 讓風格資料之後能接到家具推薦、Prompt 組裝、前端篩選或場景配置。

## 2. 我已經整理好的東西

### 已完成的風格數量

已整理 8 種風格：

1. 北歐風 `Scandinavian`
2. 現代風 `Modern`
3. 簡約風 / 無印風 `Minimalist / MUJI`
4. 工業風 `Industrial`
5. 侘寂風 `Wabi-Sabi`
6. 日系禪風 `Japanese`
7. 美式風 `American`
8. 輕奢風 `Light Luxury`

### 每種風格目前已整理的欄位

每種風格都已整理以下內容：

1. `style_id`
2. `style_name_zh`
3. `style_name_en`
4. `keywords_zh`
5. `main_colors_zh`
6. `materials_zh`
7. `shape_features_zh`
8. `avoid_elements_zh`
9. `scene_background`
10. `furniture_mapping_zh`

### `furniture_mapping_zh` 的用途

這個欄位是目前最重要的橋樑。

它不是只寫「北歐風很溫暖」這種抽象描述，而是把風格拆到家具部位，例如：

- 沙發要長什麼樣
- 扶手椅要長什麼樣
- 茶几要長什麼樣

這樣 LLM 比較容易把「字」對到「實體家具外觀」。

## 3. 已經產出的正式檔案

### Word 文件

[style_moodboard_catalog.docx](D:\產業新兵計畫\期末專題\test_furniture\docs\style_moodboard_catalog.docx)

用途：

1. 給人閱讀
2. 給老師或組員看現在的風格整理進度
3. 當作風格總表與 JSON 欄位說明文件

### JSON 檔案

[style_moodboard.json](D:\產業新兵計畫\期末專題\test_furniture\sf3d\metadata\style_moodboard.json)

用途：

1. 給 LLM / Prompt 流程使用
2. 給前端或後端讀取
3. 當未來風格推薦與家具分類的資料來源

### 產生器腳本

[generate_style_catalog.py](D:\產業新兵計畫\期末專題\test_furniture\scripts\generate_style_catalog.py)

用途：

1. 用同一份資料同時生成 Word 與 JSON
2. 避免 Word 跟 JSON 內容不同步

## 4. 目前對 LLM 的理解方式

目前的結論是：

不要只跟 LLM 說「我要北歐風」。

要改成：

`任務 + 風格規格 + 家具類型 + 不要的元素 + 輸出格式`

### 正確方向

例如要這樣講：

1. 我要北歐風
2. 主色是米白、淺灰、淺木色
3. 材質是棉麻布、淺木、霧面金屬
4. 套用在三人沙發
5. 不要亮面皮革、不要豪華雕花、不要厚重金屬感

### 錯誤方向

不要只丟一句：

`幫我做北歐風沙發`

因為這樣 LLM 容易自由發揮，結果會飄。

## 5. 目前對資料結構的決策

### 已決定

1. 風格資料先獨立成 `style_moodboard.json`
2. 不直接混進主場景 JSON
3. JSON key 用英文
4. JSON value 以中文為主

### 為什麼先獨立

因為風格資料是「共用規格層」，不是某一個單一房間專案才有的內容。

如果直接塞進每個 scene JSON，之後會很亂。

比較合理的做法是：

1. 先有一份共用的 `style_moodboard.json`
2. 之後某個場景或某件家具再引用它

## 6. 我現在還沒做的事

以下是目前還沒接上的部分：

1. 還沒把 `style_moodboard.json` 接進前端
2. 還沒把 `style_moodboard.json` 接進家具推薦流程
3. 還沒做「讓 LLM 自動判斷某件家具屬於哪種風格，並回寫 metadata」
4. 還沒把每一件家具都標上正式 style metadata

## 7. 我現在最適合的下一步

如果下一個接手的人要延續這塊，最合理的順序是：

1. 先讀 `style_moodboard.json`
2. 確認 8 種風格欄位是否還要補更多資訊
3. 決定這份資料要先接哪一段流程

建議優先順序：

1. 接到 Prompt 組裝
2. 接到家具推薦
3. 接到前端篩選
4. 最後再做逐件家具的 style 標記

## 8. 如果要跟下一個 LLM 說什麼

可以直接貼這段：

```text
我目前負責的是風格生成 / 風格系統整理，不是 3D 幾何生成。
請先讀：
1. docs/style_progress_handoff_2026-07-03.md
2. sf3d/metadata/style_moodboard.json
3. PROJECT_CONTEXT.md

目前已整理 8 種風格，並產出一份 Word 與一份 JSON。
請延續這套風格資料，協助我把它接到 LLM 溝通、Prompt 組裝、家具推薦或前端篩選流程。
不要把工作重做成單純文字介紹。
```

## 9. 重要提醒

1. 目前風格資料已經獨立成正式 JSON，不要回頭只用散亂文字描述。
2. 目前這塊的重點是「讓 LLM 理解字與家具外觀的關係」。
3. `furniture_mapping_zh` 是這份資料最重要的欄位，不要刪掉。
4. 如果後續還會繼續擴充風格資料，建議把更多風格或實驗記錄拆到 `docs/`，不要一直把內容塞回 `PROJECT_CONTEXT.md`。
