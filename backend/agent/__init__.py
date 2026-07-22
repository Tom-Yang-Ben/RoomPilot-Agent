"""backend.agent —— 選件 + 擺位紀律 agent(room_pilot2 移植版,2026-07-21)。

取代原 layout_intent / recovery 提示鏈。哲學與鐵律不變且更徹底:LLM 只決定
「選哪些件」(select),座標一律由 backend.engine 計算;擺放潛規則
(knowledge)是單一事實源,同時餵給選件 prompt、系統邊界驗證與擺位紀律
(place:主件先行、副件成組、寧缺勿亂 + 確定性換小)。

LLM 呼叫器(complete)與擺放函式(place_fn)由呼叫端注入 —— 本套件不
import backend.server、不碰網路;無 key 時 select 由呼叫端降級本機規則,
place 全程確定性,離線測試可行。
"""
from .knowledge import COMPANION_OF, ROOM_AFFINITY, family_of, prompt_rules
from .place import pick_smaller_model, placement_hints, resolve_placements
from .select import (
    SelectedItem,
    SelectionParseError,
    SelectionUnavailableError,
    build_select_messages,
    parse_selections,
    request_selections,
)

__all__ = [
    "COMPANION_OF",
    "ROOM_AFFINITY",
    "family_of",
    "prompt_rules",
    "pick_smaller_model",
    "placement_hints",
    "resolve_placements",
    "SelectedItem",
    "SelectionParseError",
    "SelectionUnavailableError",
    "build_select_messages",
    "parse_selections",
    "request_selections",
]
