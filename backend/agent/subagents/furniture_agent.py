"""Furniture Agent：需求整理＋RAG 候選＋挑擺（任務 1–3）。

Skills：需求整理、家具。Tools：RAG 家具、挑家具、擺家具、讀室內架構、
讀規則/需求（共用）。座標與合法性一律由 engine 決定。
"""
from __future__ import annotations

from ..documents import (
    CandidateListDoc,
    FurnitureListDoc,
    LayoutDoc,
    RequirementDoc,
    SceneDoc,
    ValidationReportDoc,
)
from ..llm import LLMGateway
from ..skills.furniture import STRATEGIES, FurnitureSkill
from ..skills.requirements import RequirementSkill
from ..tools.rag_furniture import FurnitureRetriever, RagFurnitureTool


class FurnitureAgent:
    name = "Furniture Agent"
    skills = ("需求整理", "家具")
    tools = ("rag_furniture", "pick_furniture", "place_furniture", "read_layout", "read_rules")

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        *,
        retriever: FurnitureRetriever | None = None,
        rag_tool: RagFurnitureTool | None = None,
    ) -> None:
        self._requirements = RequirementSkill(gateway)
        self._furniture = FurnitureSkill(
            gateway, rag_tool=rag_tool or RagFurnitureTool(retriever)
        )

    def organize_requirements(
        self, questionnaire: dict, layout: LayoutDoc
    ) -> RequirementDoc:
        """任務 1：問卷 → 需求文件（硬/軟/家電三分流）。"""
        return self._requirements.run(questionnaire, layout)

    def retrieve_candidates(
        self, requirements: RequirementDoc, layout: LayoutDoc
    ) -> CandidateListDoc:
        """任務 2：RAG 檢索排序 → 候選家具清單。"""
        return self._furniture.build_candidates(requirements, layout)

    def propose(
        self,
        requirements: RequirementDoc,
        candidates: CandidateListDoc,
        layout: LayoutDoc,
        variant: str,
    ) -> tuple[FurnitureListDoc, SceneDoc]:
        """任務 3：依策略（A 動線優先／B 收納優先）選件並由 engine 擺放。"""
        strategy = STRATEGIES[variant]
        furniture_list = self._furniture.choose(requirements, candidates, strategy=strategy)
        scene = self._furniture.place(layout, furniture_list)
        return furniture_list, scene

    def repair(
        self,
        furniture_list: FurnitureListDoc,
        report: ValidationReportDoc,
        scene: SceneDoc,
        candidates: CandidateListDoc,
        layout: LayoutDoc,
    ) -> tuple[FurnitureListDoc, SceneDoc]:
        """驗證失敗的修復：換小/移除由 skill 決定，重擺仍由 engine 計算。"""
        repaired = self._furniture.repair(furniture_list, report, scene, candidates)
        return repaired, self._furniture.place(layout, repaired)
