"""RoomPilot Agent：Master state machine ＋ 四個 sub-agent（skills / tools 分層）。

新架構（2026-07 提案定案版）：

- ``master``：程式固定流程 state machine——HITL 暫停點、修復迴圈 ≤3、
  改圖 ≤1、生圖失敗 3 次 fallback、checkpoint 可恢復上一動。
- ``subagents``：Furniture／Validation／Gen_Pic／Report。
- ``skills``：每個 skill 一資料夾＋``SKILL.md``（提示詞與 schema 唯一來源）。
- ``tools``：帶輸入/輸出契約的 deterministic 函式（engine 與 RAG 邊界）。
- ``documents``：Docs 層 blackboard 與 ``DocStore``。
- ``llm``：OpenRouter gateway（stdlib urllib；文字＋nano banana 生圖、
  fallback nano banana 2）。業務碼不 import httpx（CLAUDE.md）。

邊界不變：座標與合法性只來自 :mod:`backend.engine`；RAG 只檢索排序；
家電只進生圖 context。

room_pilot2 移植版三模組（``knowledge`` / ``select`` / ``place``）仍是
``backend.server.services`` 現行選件/擺位流程的依賴，其 re-export 必須保留；
新功能一律使用上述新架構。
"""
# -- room_pilot2 移植版（server services 依賴，不可移除） --
from .knowledge import (
    COMPANION_OF,
    ROOM_AFFINITY,
    family_of,
    item_allowed_in_room,
    prompt_rules,
)
from .place import pick_smaller_model, placement_hints, resolve_placements
from .select import (
    SelectedItem,
    SelectionParseError,
    SelectionUnavailableError,
    build_select_messages,
    parse_selections,
    request_selections,
)

# -- Master ＋ sub-agent 新架構 --
from .documents import DocKey, DocStore
from .llm import LLMError, OpenRouterGateway
from .master import MasterAgent, MasterConfig, MasterState, PauseInfo
from .runtime import build_gateway, build_master
from .subagents import (
    FurnitureAgent,
    GenPicAgent,
    GenPicFailure,
    ImagePolicy,
    ReportAgent,
    ValidationAgent,
)

__all__ = [
    # room_pilot2 移植版
    "COMPANION_OF",
    "ROOM_AFFINITY",
    "family_of",
    "item_allowed_in_room",
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
    # 新架構
    "DocKey",
    "DocStore",
    "LLMError",
    "OpenRouterGateway",
    "MasterAgent",
    "MasterConfig",
    "MasterState",
    "PauseInfo",
    "build_gateway",
    "build_master",
    "FurnitureAgent",
    "ValidationAgent",
    "GenPicAgent",
    "GenPicFailure",
    "ImagePolicy",
    "ReportAgent",
]
