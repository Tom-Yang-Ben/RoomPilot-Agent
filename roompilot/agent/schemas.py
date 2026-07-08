"""roompilot.agent 的輸出契約(貼進 prompt 當格式約束、也用於解析驗證)。

定位:Agent 3 / Agent 4 是「鐵律版」角色 —— 都【不輸出座標】。
- Agent 3 只輸出擺放語意提示(靠牆側/朝向/成組/優先序)。
- Agent 4 只輸出修復指令(換更小 / 移除 / 升級)。

欄位設計沿用 for_agent/SCHEMA_審查_V1.md §3.1 的原則:
用陣列不用逗號字串、鍵名單複數一致、不把「機器真值」與「LLM 敘事」混在同一鍵。
"""
from __future__ import annotations

# 允許的靠牆側(引擎唯一會消費的擺放提示)
ANCHORS = ("top", "bottom", "left", "right", "center")
# 允許的朝向(選填,目前引擎以 anchor 推導旋轉,face 供未來/前端說明)
FACES = ("up", "down", "left", "right", "center")
# Agent 4 允許的修復動作
ACTIONS = ("replace", "remove", "escalate")

# Agent 3 輸出範例(丟給 LLM 當 output_shape,ensure_ascii=False 序列化)
AGENT3_OUTPUT_SHAPE = {
    "hints": [
        {
            "furniture_id": "對應輸入家具的 id",
            "anchor": "top|bottom|left|right|center|null(偏好靠牆側)",
            "face": "up|down|left|right|center|null(朝向,選填)",
            "group": "字串|null(成組標籤,如 seating / dining / sleeping)",
            "priority": "整數,越小越先擺(大件、靠牆件優先)",
            "note": "一句繁體中文擺放理由",
        }
    ]
}

# Agent 4 輸出範例
AGENT4_OUTPUT_SHAPE = {
    "instructions": [
        {
            "furniture_id": "對應放不下的家具 id",
            "action": "replace|remove|escalate",
            "reason_zh": "一句繁體中文說明(給使用者看)",
        }
    ]
}
