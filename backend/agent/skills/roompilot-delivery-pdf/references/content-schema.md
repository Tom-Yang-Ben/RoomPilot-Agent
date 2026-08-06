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
    "hook": "兩到三句。從屋主的生活場景切入，不要從風格名詞切入。",
    "pillars": [
      {"title": "動線先於家具", "body": "一到兩段。這個主張怎麼貫穿全案。"},
      {"title": "收納藏起來", "body": "..."},
      {"title": "留一面完整的光", "body": "..."}
    ]
  },

  "overview": {
    "title": "全案速覽",
    "title_en": "At a Glance",
    "intro": "選填，一段。",
    "facts": [
      {"label": "總坪數", "value": "28.6 坪 (94.5 m²)"},
      {"label": "格局", "value": "三房兩廳兩衛"},
      {"label": "風格", "value": "日式現代 Japandi"},
      {"label": "主色卡", "value": "米白 × 淺橡木 × 炭灰"}
    ],
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
      "look": "兩到四句。從一個人實際走進來的視角描述：先看到什麼、材質手感、光的方向。",
      "rationale": [
        {"title": "把電視牆讓給光", "body": "為什麼這樣做，接回屋主的需求或空間條件。"},
        {"title": "走道留 90 公分", "body": "..."}
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

`look` 約 100–140 字。`rationale` 兩條，每條 `body` 60–90 字（第三條通常是硬湊的）。`specs` 三到五列。`extra_images` 只給客廳、主臥這種重點空間，它會讓該空間多佔半頁。

`build_pdf.py` 跑完會告訴你哪一頁太空。照它的建議精簡，不要靠加字填滿——加出來的字一定是廢話。

## 欄位注意事項

`whats_new` 只有第二版以後才寫。`items` 要逐條對上屋主的回饋，包括資料回答不了的那些：說明缺什麼、什麼時候能給。跳過某一條屋主一定會發現。

`meta.cover_meta` 最多放三到四項，超過封面會擠。日期與版本一定要有——屋主過兩週回來看，需要知道這是哪一版。

`rooms[].rationale` 每個空間寫兩到三條就夠。四條以上會排到第二頁，而且第四條通常是硬湊的。

`rooms[].specs` 是給屋主核對用的表格，不是完整家具清單。挑三到六項屋主真的會在意的（主要家具、尺寸、地材、關鍵淨空），其他留在成果包的 JSON 裡。

`palette.swatches` 一排四個。給五到八個色票剛好，`hex` 要用真實色碼，不要憑印象填。

`rooms[].extra_images` 會把該空間推到第二頁。只有真的值得多看一張圖的重點空間（通常是客廳、主臥）才放，其他空間留空，維持一個空間一頁的節奏。

`rooms[].hero_image` 生圖失敗時留空字串，會自動變成佔位框。但**一定要同時在 `appendix.limits` 提到那個房間的名字**，否則屋主會以為你漏做了——`preflight_check.py` 會檢查這件事。

`appendix.limits` 寧可多寫。所有失敗的房間、沒確認的材質、跟現場可能有落差的地方都寫進去。
