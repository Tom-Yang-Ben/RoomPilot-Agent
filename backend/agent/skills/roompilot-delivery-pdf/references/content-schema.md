# content.json 欄位說明

`build_pdf.py` 只讀這一個檔。所有區塊都是選填——沒寫的區塊會整段跳過，不會產生空白頁。所以要少寫一個章節，就把那個 key 刪掉，不要留空字串。

文字欄位裡的換行 `\n` 會被轉成段落。不要寫 HTML 標籤，會被跳脫成純文字。

## 完整範例

```json
{
  "meta": {
    "kicker": "室內設計提案 · Interior Design Proposal",
    "project_name": "文山 · 林宅",
    "subtitle": "三房兩廳 28.6 坪｜日式現代 Japandi",
    "cover_image": "rooms/客廳/最終渲染.png",
    "version": "scene v12 · render v3",
    "cover_meta": [
      {"label": "屋主", "value": "林先生 · 林太太"},
      {"label": "日期", "value": "2026 年 8 月 3 日"},
      {"label": "版本", "value": "v1 初版提案"}
    ]
  },

  "whats_new": {
    "title": "這一版改了什麼",
    "title_en": "What's Changed",
    "hook": "一到兩句。第二版以後才寫，會排在封面之後的第一頁。",
    "body": "選填，補充說明。",
    "items": [
      {"feedback": "屋主提出的原話或摘要", "response": "這一版怎麼處理；資料回答不了就說明缺什麼、何時能給"}
    ]
  },

  "statement": {
    "title": "設計總論",
    "title_en": "Design Statement",
    "hook": "兩到三句。從屋主的生活場景切入，不要從風格名詞切入，也不要寫這份文件怎麼做出來的。",
    "pillars": [
      {"title": "全案速覽", "body": "後面每一章各一條摘要，約 50 字。title 就是章名。"},
      {"title": "客廳", "body": "這一章會看到什麼：尺寸、主要配置、材質方向。"},
      {"title": "色彩與材質", "body": "..."},
      {"title": "接下來", "body": "..."}
    ]
  },

  "overview": {
    "title": "全案速覽",
    "title_en": "At a Glance",
    "intro": "一段。把規模、風格、共用材質與屋主需求講成可讀的話，別讓這頁只剩幾格數字。",
    "facts": [
      {"label": "總坪數", "value": "28.6 坪 (94.5 m²)"},
      {"label": "格局", "value": "三房兩廳兩衛"},
      {"label": "風格", "value": "日式現代 Japandi"},
      {"label": "主色卡", "value": "米白 × 淺橡木 × 炭灰"}
    ],
    "table": {
      "columns": ["空間", "尺寸（約）", "主要配置"],
      "rows": [["客廳", "4.2 × 3.6 米", "沙發、茶几、電視櫃"]]
    },
    "plan_image": "configuration/平面配置.png",
    "plan_caption": "第 6 步確認的最終配置。"
  },

  "rooms": [
    {
      "name": "客廳",
      "name_en": "Living Room",
      "hero_image": "rooms/客廳/最終渲染.png",
      "hero_caption": "自玄關方向望向南面採光。",
      "scene_line": "一句。屋主在這個空間最日常的一個畫面。",
      "look": "兩到四句。走進來會看到什麼、材質手感、光的方向，以及待在裡面是什麼心情。不寫家具型號。",
      "rationale": [
        {"title": "選件依據", "body": "什麼樣的設計判斷 → 所以選了什麼家具與材質 → 搭起來是什麼空間感。"},
        {"title": "把電視牆讓給光", "body": "選填第二條。接回屋主的需求或空間條件。"}
      ],
      "specs": [
        {"label": "主沙發", "value": "三人布沙發 2100 × 900 mm，離牆 150 mm"},
        {"label": "地板", "value": "橡木海島型 (oak engineered)"}
      ],
      "extra_images": [
        {"src": "rooms/客廳/鎖定視角.png", "caption": "第 7 步鎖定視角。"}
      ]
    }
  ],

  "palette": {
    "title": "色彩與材質",
    "title_en": "Palette & Materials",
    "intro": "選填。",
    "swatches": [
      {"hex": "#F2EDE6", "name": "米白 Off-white", "usage": "全室牆面主色"},
      {"hex": "#C8A87C", "name": "淺橡木 Light Oak", "usage": "地板與木作"}
    ]
  },

  "materials": [
    {"area": "地板", "spec": "橡木海島型 (oak engineered)", "why": "耐潮，赤腳踩起來不冰。"}
  ],

  "lighting": {
    "title": "燈光與氛圍",
    "title_en": "Lighting",
    "intro": "選填。",
    "items": [
      {"label": "客廳主照明", "value": "嵌燈 3000K × 6，沿沙發軸線配置"}
    ]
  },

  "quote": {
    "title": "報價單",
    "title_en": "Quotation",
    "intro": "一到兩句。這一頁在講什麼、跟前面的規格表怎麼對應。",
    "table": {
      "columns": ["空間", "品項", "規格", "數量", "單價", "小計"],
      "rows": [["客廳", "三人布沙發", "210x90cm", "1", "18,800 元", "18,800 元"]]
    },
    "summary": [
      {"label": "已標價合計", "value": "約 45,990 元（6 件）"},
      {"label": "待報價品項", "value": "2 件"}
    ],
    "notes": ["本表是型錄參考價，不含工程、運送與安裝費用。"]
  },

  "next_steps": {
    "title": "接下來",
    "title_en": "Next Steps",
    "body": "一到兩段：這份文件之後會發生什麼。",
    "notes": ["需要你確認的事項一", "事項二"]
  },

  "appendix": {
    "files": [
      {"name": "rooms/客廳/最終渲染.png", "desc": "客廳最終渲染圖"}
    ],
    "limits": ["次臥渲染任務失敗，圖面待補。"],
    "version_line": "configuration_snapshot v12 · render_brief v3 · 產出於 2026-08-03"
  }
}
```

## 篇幅上限

一個空間一頁是這份文件的節奏。超過就會出現「整頁只有一張落單表格」的殘頁，而那看起來像排版壞掉。抓這個量：

`look` 約 100–140 字。`rationale` 一到兩條，每條 `body` 60–90 字。`specs` 三到六列。`extra_images` 只給客廳、主臥這種重點空間，它會讓該空間多佔半頁。

`build_pdf.py` 跑完會告訴你哪一頁太空。照它的建議精簡，不要靠加字填滿——加出來的字一定是廢話。

## 欄位注意事項

`whats_new` 只有第二版以後才寫。`items` 要逐條對上屋主的回饋，包括資料回答不了的那些：說明缺什麼、什麼時候能給。跳過某一條屋主一定會發現。

`meta.cover_meta` 最多放三到四項，超過封面會擠。日期與版本一定要有——屋主過兩週回來看，需要知道這是哪一版。

`statement.pillars` 是**後續每一章的摘要**，不是三個抽象主張。章名當 `title`，`body` 約 50 字講那一章會看到什麼。屋主翻開第一頁要知道這份文件裡有什麼，而不是讀三段換哪個案子都成立的宣言。

`overview` 只放四五格 `facts` 會整頁發空。補 `intro` 一段與 `table`（空間／尺寸／主要配置）——屋主翻開最想先確認的就是「哪幾間、多大、放了什麼」。

`rooms[].rationale` 每個空間一到兩條。第一條固定是「選件依據」。**不要寫擺位、淨空、走道寬度、碰撞或幾何驗證**——那是我們的工作紀錄，不是屋主要讀的設計理由。

`rooms[].specs` 是給屋主核對用的表格，不是完整家具清單。挑三到六項屋主真的會在意的（主要家具、尺寸、材質），**同款同尺寸的合併成一列加數量**（四張一樣的餐椅寫一列「共 4 件」，不要抄四遍）。其他留在成果包的 JSON 裡。

`palette` 不要只有色塊。`intro` 要講清楚這組色卡的調子、三個顏色各自落在哪些部位、地板牆面怎麼跟它搭；`swatches[].name` 給中文色名＋色碼（只印 `#F7F5ED` 屋主看到的是亂碼），`materials[].why` 每列都要有理由。一排四個色票，五到八個剛好，`hex` 要用真實色碼，不要憑印象填。

**浴室與陽台不做。** 這兩種空間不在軟裝提案範圍，`rooms` 不要放它們的篇章；在 `overview.intro` 一句話交代不列的原因就好。

**`quote` 固定排在最後一頁**（在「接下來／附錄」之後），不管它寫在 content.json 的哪個位置。**金額只能寫在 `quote`。** `rooms[].specs`、`look`、`rationale`、`overview` 一律不帶價格——屋主一看到數字就會停下來算錢，設計還沒讀完。價格集中在報價單這一頁，他可以讀完設計再翻過去。缺價的品項照樣列一行、單價寫「待報價」，`summary` 的合計只加已標價的；用同類中位數或預算回推補一個數字，屋主會當成報價記住。

`rooms[].extra_images` 會把該空間推到第二頁。只有真的值得多看一張圖的重點空間（通常是客廳、主臥）才放，其他空間留空，維持一個空間一頁的節奏。

`rooms[].hero_image` 生圖失敗時留空字串，會自動變成佔位框。但**一定要同時在 `appendix.limits` 提到那個房間的名字**，否則屋主會以為你漏做了——`preflight_check.py` 會檢查這件事。

`appendix.limits` 寧可多寫。所有失敗的房間、沒確認的材質、跟現場可能有落差的地方都寫進去。
