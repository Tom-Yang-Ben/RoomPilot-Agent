"""Validation Agent：雙軌驗證（任務 4）。

硬規則呼叫 engine（違反即擋）；軟潛規則與需求滿足度為 advisory。
修復「迴圈次數」不在這裡——那是 Master 的職責。
"""
from __future__ import annotations

from ..documents import (
    LayoutDoc,
    RequirementDoc,
    RulesDoc,
    SceneDoc,
    ValidationReportDoc,
)
from ..llm import LLMGateway
from ..skills.validation import ValidationSkill


class ValidationAgent:
    name = "Validation Agent"
    skills = ("驗證規則/需求",)
    tools = ("engine_validate", "read_rules", "read_layout")

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._skill = ValidationSkill(gateway)

    def validate(
        self,
        requirements: RequirementDoc,
        layout: LayoutDoc,
        scene: SceneDoc,
        rules: RulesDoc,
        *,
        round_index: int = 1,
    ) -> ValidationReportDoc:
        return self._skill.run(
            requirements, layout, scene, rules, round_index=round_index
        )
