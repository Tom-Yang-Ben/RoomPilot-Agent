"""Tool 基礎契約。

依架構提案：tool＝「帶輸入/輸出契約的函式」。每個 tool 都掛一份
``ToolContract``（名稱、描述、輸入/輸出 JSON schema），未來要接
function calling 或其他框架時直接取用；tool 本身保持 deterministic，
不呼叫 LLM——語意決策屬於 skills。
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ToolError(RuntimeError):
    """Tool 執行失敗；``reason`` 需可讀，供 sub-agent 回報與報告引用。"""

    def __init__(self, reason: str, *, tool: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.tool = tool


@dataclass(frozen=True)
class ToolContract:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
