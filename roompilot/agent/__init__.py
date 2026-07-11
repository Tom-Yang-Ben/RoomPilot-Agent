"""roompilot.agent —— F3 LLM Agent 鏈的「鐵律版」封裝。

只採用 for_agent 的 Agent 提示,丟棄與引擎重工的部分(見 docs 整合方案):
- Agent 3(design_layout_intent):輸出擺放語意提示,不出座標。
- Agent 4(run_recovery):把引擎的 placement_failed 轉成換小 / 移除 / 升級,重擺至收斂。

家具座標一律由 roompilot.engine 決定;本套件透過依賴注入拿到 LLM 呼叫器(complete)與
擺放函式(place_fn),不 import roompilot.server,避免耦合、也方便離線測試。
"""
from .layout_intent import design_layout_intent
from .recovery import pick_smaller_model, run_recovery

__all__ = ["design_layout_intent", "run_recovery", "pick_smaller_model"]
