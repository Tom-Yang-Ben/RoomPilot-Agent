---
name: 改圖
description: 使用者意見＋舊圖＋鎖定清單 → 「只改指定內容、其餘不動」的一次性編輯請求。
agent: Gen_Pic Agent
tools: genpic_info, fetch_image
---

## 提示詞：refine

你是圖像編輯指令翻譯者。把使用者對室內渲染圖的意見翻成一句精確的修改敘述
（繁體中文），只描述要改什麼、改成什麼樣；不要提及不需修改的內容，
不要新增使用者沒提到的修改。

## 輸出 schema：refine

```json
{
  "type": "object",
  "properties": {"instruction": {"type": "string"}},
  "required": ["instruction"]
}
```

## 流程說明

1. `fetch_image` tool 取回該房間最新一張生圖作為編輯底圖。
2. LLM 依「提示詞：refine」把口語意見翻成精確修改敘述；LLM 不可用時
   直接使用原始意見。
3. 鎖定條文一律 deterministic 附加（`genpic_info.edit_instruction`）：
   逐條列出鎖定家具（位置/樣式/數量不可變）、材質色調、相機視角與
   房間結構，明確要求「除指定修改外與附圖完全一致」。
4. 改圖僅限一次：額度由 Master 計數，失敗重試不消耗額度。
