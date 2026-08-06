"""Report Agent：統整全部文件輸出設計手冊 PDF（任務 7）。"""
from __future__ import annotations

from ..documents import DesignManualDoc, DocStore
from ..llm import LLMGateway
from ..skills.report import ReportSkill


class ReportAgent:
    name = "Report Agent"
    skills = ("報告整理輸出",)
    tools = ("read_docs", "render_pdf")

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._skill = ReportSkill(gateway)

    def build_manual(self, store: DocStore, out_path: str) -> DesignManualDoc:
        return self._skill.run(store, out_path)
