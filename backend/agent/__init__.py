"""RoomPilot Agent：Master state machine ＋ 四個 sub-agent（skills / tools 分層）。

新架構（2026-07 提案定案版）：

- ``master``：程式固定流程 state machine——HITL 暫停點、修復迴圈 ≤3、
  改圖 ≤1、生圖失敗 3 次 fallback、checkpoint 可恢復上一動。
- ``subagents``：Furniture／Validation／Gen_Pic／Report。
- ``skills``：系統提示詞＋流程模板＋輸出 schema（LLM 語意決策、離線 fallback）。
- ``tools``：帶輸入/輸出契約的 deterministic 函式（engine 與 RAG 邊界）。
- ``documents``：Docs 層 blackboard 與 ``DocStore``。
- ``llm``：OpenRouter gateway（文字＋nano banana 生圖、fallback nano banana 2）。

邊界不變：座標與合法性只來自 :mod:`backend.engine`；RAG 只檢索排序；
家電只進生圖 context。

（歷史模組 ``knowledge`` / ``select`` / ``place`` 仍由 backend/server 現行
流程 import，維持原樣不動；新功能一律使用上述新架構。）
"""
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
