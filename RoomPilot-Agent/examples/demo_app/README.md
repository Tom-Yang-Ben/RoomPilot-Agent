# RoomPilot · 走通骨架 Demo(demo_app)

給老師看的「端到端最小可跑版」。目的:展示**架構 + 真進度 + 清楚的待補點**,不是完成品。

## 這條線在做什麼

```
使用者一句話
  → Agent 解析意圖        （stub · 柏彥待接真 LLM）      agent_stub.py
  → furniture_engine 配置 （✅ 真的,ancai 已完成、25 測試過） 上一層 furniture_engine/
  → render_style 風格化    （stub · 舒媁待接 ControlNet）   render_style_stub.py
```

- **綠色(真)**:`furniture_engine` —— 輸入家具清單,真的算出每件的座標 `pos_x/pos_y/rotation`,會避開牆、避免重疊。
- **黃色(stub)**:Agent 用規則式關鍵字解析頂著;render_style 用 PIL 畫俯視示意圖頂著。**兩者介面固定,之後換內部實作即可,前後端不用改。**

## 怎麼跑(3 步)

```bash
cd demo_app
pip install fastapi uvicorn shapely pillow      # 第一次才要
uvicorn main:app --reload --port 8000
```
瀏覽器開 **http://127.0.0.1:8000**,在輸入框打例如:

> 放三人沙發、茶几、電視櫃,想要北歐風

會看到:① Agent 回話 → ② 家具引擎把 3 件家具擺進房間(俯視圖)→ ③ 風格化示意圖。

## 待接的兩個 stub(舒媁 / 柏彥直接換裡面就好)

| 檔案 | 現在(stub) | 之後(真的) | **不變的介面** |
|---|---|---|---|
| `agent_stub.py` `parse_command(text)` | 關鍵字規則解析 | LLM function-calling(用 `furniture_engine/schema.py` 的 tool schema) | 回傳 `{intent, items, style, reply}` |
| `render_style_stub.py` `render_style(room, placed, style)` | PIL 俯視上色 | ControlNet/depth 依風格生成 | 回傳 `{image_base64, style, note}` |

> 只要**函式的輸入/輸出格式不變**,把裡面換成真的實作,整個 app 照樣跑。這就是「先接線、再補內容」的意義。

## 正式版接點(給整合看)

- `main.py` 的 `demo_room()` 現在寫死 5×4 房間 → **正式版改成呼叫 `upgrade_to_3d` / cody 的 `floorplan2dxf`**,把上傳平面圖解析成 `Room`。
- 家具型錄/尺寸之後接 kai 的 `scripts/`(型錄→PostgreSQL)。
