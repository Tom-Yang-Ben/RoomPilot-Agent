"""Report Agent：統整全部文件輸出設計手冊 PDF（任務 7），
另可輸出品牌版交付提案 PDF（roompilot-delivery-pdf 打包 skill 排版）供比較。"""
from __future__ import annotations

from ..documents import DesignManualDoc, DocStore
from ..llm import LLMGateway
from ..skills.delivery import DeliverySkill
from ..skills.report import ReportSkill


class ReportAgent:
    name = "Report Agent"
    skills = ("報告整理輸出", "交付提案輸出")
    tools = ("read_docs", "render_pdf", "build_delivery_pdf")

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._skill = ReportSkill(gateway)
        self._delivery = DeliverySkill(gateway)

    def build_manual(self, store: DocStore, out_path: str) -> DesignManualDoc:
        return self._skill.run(store, out_path)

    def build_delivery(
        self,
        store: DocStore,
        out_path: str,
        *,
        project_name: str = "RoomPilot 專案",
        design_revision=None,
    ) -> dict:
        """輸出交付提案 PDF；排版引擎未安裝時丟 ToolError（可讀原因）。"""
        return self._delivery.run(
            store, out_path, project_name=project_name, design_revision=design_revision
        )
