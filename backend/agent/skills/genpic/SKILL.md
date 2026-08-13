---
name: 生圖
description: 組出送往 nano banana 的渲染請求；兩階段：單房×色卡比對 → 全房逐房生圖。
agent: Gen_Pic Agent
tools: genpic_info, design_knowledge
---

## 流程說明

本 skill 不使用文字 LLM：提示詞包與鎖定清單由 `genpic_info` tool
deterministic 產生（素材＝需求文件的材質/風格/家電 context＋色卡＋
engine 場景座標翻成的位置措辭＋視角備註；問卷風格可對應到
`design_knowledge` tool 的風格矩陣時，再附一行材質/色彩/氛圍描述）。

1. 階段一 `palette_compare`：單一房間 × 各色卡方案（上限 3 組），供使用者
   比對擇一——先小成本試色，選定後才全房生圖（成本漏斗）。
2. 階段二 `full_render`：全房逐房生成；同時產出每房的鎖定清單
   （家具位置/材質/視角），供改圖 skill 使用。
3. 視角畫面（Three.js 截圖，base64）作為構圖參考隨請求附上；提示詞明確
   要求「依附圖視角與家具位置生成、不得增減家具」。
4. 家電只作為畫面元素進入提示詞，不影響任何配置決策。浴室／廚房／陽台另補
   固定設備與室內外提示（白模沒有這些東西，模型照著截圖畫就會漏掉）；
   尺寸只有廚房會報（長寬與面積），其餘房型維持不給數值。
5. `lighting="night"`（客廳夜間圖，`stage=full_render_night`）是日光成圖的
   重打光：img2img 附該房 `full_render` 成品而非視角截圖，提示詞也只留夜間
   光影一句——整套家具/材質敘述再送一次會讓模型重畫，兩張就對不起來。
5. 實際 API 呼叫與失敗政策（主模型 3 次 → 提示原因 → fallback
   nano banana 2）在 `subagents/genpic_agent.py`；額度與次數由 Master 控制。
