"""
agent_stub.py — 「Agent 核心」的假實作佔位(柏彥之後把這裡換成真 LLM function-calling)

現在(P0 保底):規則式關鍵字解析,把一句話 → 決定要呼叫哪個工具 + 參數。
之後(柏彥):換成 LLM,用 furniture_engine/schema.py 裡的
             PLACE_FURNITURE_TOOL / ADJUST_FURNITURE_TOOL(+ 之後的 render_style tool)當 tools。
             **只要輸出格式(intent / items / style)不變,前端與後端都不用改。**
"""

# 關鍵字 → 家具:(type, 顯示名稱, 寬 m, 深 m)
FURNITURE = {
    "三人沙發": ("sofa", "三人沙發", 2.1, 0.9),
    "沙發": ("sofa", "沙發", 2.0, 0.9),
    "茶几": ("coffee", "茶几", 1.0, 0.55),
    "電視櫃": ("tv", "電視櫃", 1.6, 0.4),
    "餐桌": ("table", "餐桌", 1.4, 0.8),
    "書桌": ("desk", "書桌", 1.2, 0.6),
    "書櫃": ("bookcase", "書櫃", 0.8, 0.3),
    "雙人床": ("bed", "雙人床", 1.6, 2.0),
    "床": ("bed", "雙人床", 1.6, 2.0),
    "單椅": ("chair", "單椅", 0.5, 0.55),
}
STYLES = ["北歐", "日式", "無印", "工業", "現代"]


def parse_command(text: str) -> dict:
    """
    一句自然語言 → 結構化意圖(這就是 Agent 目前『假裝理解』的部分)

    回傳:
      { intent: "place_furniture" | "render_style" | "unknown",
        items:  [ {type,name,width,depth}, ... ],   # place 用
        style:  "北歐" | None,
        reply:  給使用者看的回話 }
    """
    text = text or ""

    # 1) 抓風格
    style = next((s for s in STYLES if s in text), None)

    # 2) 抓家具(長關鍵字先抓,避免「三人沙發」被「沙發」吃掉)
    remaining = text
    items = []
    for kw in sorted(FURNITURE, key=len, reverse=True):
        if kw in remaining:
            t, n, w, d = FURNITURE[kw]
            items.append({"type": t, "name": n, "width": w, "depth": d})
            remaining = remaining.replace(kw, "")

    # 3) 決定意圖
    if items:
        names = "、".join(i["name"] for i in items)
        reply = f"好的,幫你擺:{names}" + (f"(之後套用「{style}」風格)" if style else "")
        return {"intent": "place_furniture", "items": items, "style": style, "reply": reply}

    if style:
        return {"intent": "render_style", "items": [], "style": style,
                "reply": f"套用「{style}」風格(示意圖)。"}

    return {"intent": "unknown", "items": [], "style": None,
            "reply": "我還聽不懂 😅 試試:『放三人沙發、茶几、電視櫃,想要北歐風』"}
