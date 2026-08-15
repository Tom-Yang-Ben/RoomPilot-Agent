"""驗證 skill：流程層。提示詞與 schema 見同資料夾 ``SKILL.md``。"""
from __future__ import annotations

import json
import math
from pathlib import Path

from ...documents import (
    LayoutDoc,
    LayoutRoom,
    RequirementDoc,
    RequirementGap,
    RepairSuggestion,
    RulesDoc,
    SceneDoc,
    SoftWarning,
    ValidationReportDoc,
)
from ...llm import LLMGateway
from ...tools.engine_validate import EngineValidateTool
from ..base import ask_llm_json, load_skill_doc

DOC = load_skill_doc(Path(__file__).parent)
SUMMARY_SPEC = DOC.spec("summary")

_FACING = {0: (0.0, 1.0), 90: (-1.0, 0.0), 180: (0.0, -1.0), 270: (1.0, 0.0)}
BED_HEAD_WALL_TOLERANCE_CM = 30.0


def _facing(rotation: float) -> tuple[float, float]:
    return _FACING.get(int(rotation) % 360, (0.0, 1.0))


class ValidationSkill:
    def __init__(
        self,
        gateway: LLMGateway | None = None,
        *,
        engine_tool: EngineValidateTool | None = None,
    ) -> None:
        self._gateway = gateway
        self._engine = engine_tool or EngineValidateTool()

    def run(
        self,
        requirements: RequirementDoc,
        layout: LayoutDoc,
        scene: SceneDoc,
        rules: RulesDoc,
        *,
        round_index: int = 1,
    ) -> ValidationReportDoc:
        report = ValidationReportDoc(variant=scene.variant, round_index=round_index)
        report.hard_violations = self._engine.run(layout, scene)
        report.requirement_gaps = self._requirement_gaps(requirements, scene)
        report.soft_warnings = self._soft_warnings(layout, scene, rules)
        report.suggestions = self._suggestions(report, scene)
        report.summary = self._summary(report)
        return report

    # -- 需求滿足度（deterministic） --

    def _requirement_gaps(
        self, requirements: RequirementDoc, scene: SceneDoc
    ) -> list[RequirementGap]:
        gaps: list[RequirementGap] = []
        failures = scene.failures()
        for req in requirements.must_have():
            rows: list[dict] = []
            for room_id in scene.rooms:
                if req.room_id in (None, room_id):
                    rows.extend(scene.placed_in(room_id))
            matched = [
                row
                for row in rows
                if req.req_id in (row.get("matched_requirements") or [])
                or row.get("type") == req.category
            ]
            if len(matched) >= req.quantity:
                continue
            reason = ""
            for failure in failures:
                if req.req_id in (failure.get("matched_requirements") or []) or (
                    failure.get("category") == req.category
                    and req.room_id in (None, failure.get("room_id"))
                ):
                    reason = f"（擺放失敗：{failure.get('reason', '')}）"
                    break
            gaps.append(
                RequirementGap(
                    req_id=req.req_id,
                    message=f"硬需求「{req.text}」未滿足，缺 "
                    f"{req.quantity - len(matched)} 件{reason}",
                )
            )
        return gaps

    # -- 語意軟潛規則（advisory；只描述 engine 結果，不判合法性） --

    def _soft_warnings(
        self, layout: LayoutDoc, scene: SceneDoc, rules: RulesDoc
    ) -> list[SoftWarning]:
        enabled = {rule.rule_id for rule in rules.soft_rules}
        warnings: list[SoftWarning] = []
        for room in layout.rooms:
            rows = scene.placed_in(room.room_id)
            by_type: dict[str, list[dict]] = {}
            for row in rows:
                by_type.setdefault(str(row.get("type", "")), []).append(row)
            if "sofa_faces_tv" in enabled:
                warnings.extend(self._check_sofa_faces_tv(room, by_type))
            if "bed_head_against_wall" in enabled:
                warnings.extend(self._check_bed_head(room, by_type))
            if "rug_anchored" in enabled:
                warnings.extend(self._check_rug(room, by_type))
        return warnings

    def _check_sofa_faces_tv(
        self, room: LayoutRoom, by_type: dict[str, list[dict]]
    ) -> list[SoftWarning]:
        sofas = by_type.get("sofa") or []
        medias = by_type.get("media") or []
        if not sofas or not medias:
            return []
        sofa, media = sofas[0], medias[0]
        fx, fy = _facing(float(sofa.get("rotation", 0)))
        dx = float(media.get("pos_x", 0)) - float(sofa.get("pos_x", 0))
        dy = float(media.get("pos_y", 0)) - float(sofa.get("pos_y", 0))
        if fx * dx + fy * dy <= 0:
            return [
                SoftWarning(
                    room_id=room.room_id,
                    rule_id="sofa_faces_tv",
                    message="沙發未朝向電視櫃，建議調整朝向形成視聽焦點。",
                )
            ]
        return []

    def _check_bed_head(
        self, room: LayoutRoom, by_type: dict[str, list[dict]]
    ) -> list[SoftWarning]:
        warnings = []
        for bed in by_type.get("bed") or []:
            fx, fy = _facing(float(bed.get("rotation", 0)))
            depth = float(bed.get("depth", 0))
            head_x = float(bed.get("pos_x", 0)) - fx * depth / 2
            head_y = float(bed.get("pos_y", 0)) - fy * depth / 2
            distance = min(
                head_x, room.width_cm - head_x, head_y, room.depth_cm - head_y
            )
            if distance > BED_HEAD_WALL_TOLERANCE_CM:
                warnings.append(
                    SoftWarning(
                        room_id=room.room_id,
                        rule_id="bed_head_against_wall",
                        message=f"床頭離牆約 {distance:.0f} 公分，建議床頭靠牆。",
                    )
                )
        return warnings

    def _check_rug(
        self, room: LayoutRoom, by_type: dict[str, list[dict]]
    ) -> list[SoftWarning]:
        rugs = by_type.get("rug") or []
        anchors = (by_type.get("bed") or []) + (by_type.get("sofa") or [])
        if not rugs or not anchors:
            return []
        warnings = []
        for rug in rugs:
            rug_x, rug_y = float(rug.get("pos_x", 0)), float(rug.get("pos_y", 0))
            anchored = False
            for anchor in anchors:
                half = (
                    max(float(anchor.get("width", 0)), float(anchor.get("depth", 0))) / 2
                    + 40.0
                )
                if math.hypot(
                    rug_x - float(anchor.get("pos_x", 0)),
                    rug_y - float(anchor.get("pos_y", 0)),
                ) <= half:
                    anchored = True
                    break
            if not anchored:
                warnings.append(
                    SoftWarning(
                        room_id=room.room_id,
                        rule_id="rug_anchored",
                        message="地毯未壓在主家具下方，建議移至沙發或床下方。",
                    )
                )
        return warnings

    # -- 修復建議與總結 --

    def _suggestions(
        self, report: ValidationReportDoc, scene: SceneDoc
    ) -> list[RepairSuggestion]:
        suggestions = [
            RepairSuggestion(
                room_id=violation.room_id,
                item_id=violation.item_id,
                action="swap_smaller",
                detail=f"違規：{violation.reason}；建議換更小同類候選或移除非必要件。",
            )
            for violation in report.hard_violations
        ]
        suggestions.extend(
            RepairSuggestion(
                room_id=row["room_id"],
                item_id=row["id"],
                action="swap_smaller",
                detail=f"放不下：{row['reason']}；建議換更小同類候選。",
            )
            for row in scene.failures()
        )
        return suggestions

    def _summary(self, report: ValidationReportDoc) -> str:
        deterministic = (
            f"硬違規 {len(report.hard_violations)} 件、"
            f"需求缺口 {len(report.requirement_gaps)} 項、"
            f"軟性提醒 {len(report.soft_warnings)} 則。"
            + ("方案通過硬性驗證。" if report.passed else "方案尚未通過，需修復後重驗。")
        )
        llm_out = ask_llm_json(
            self._gateway,
            SUMMARY_SPEC,
            json.dumps(report.to_dict(), ensure_ascii=False),
            required=("summary",),
        )
        if llm_out is not None and str(llm_out.get("summary", "")).strip():
            return str(llm_out["summary"]).strip()
        return deterministic
