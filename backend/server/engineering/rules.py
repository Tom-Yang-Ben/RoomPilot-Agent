from __future__ import annotations

import math
from uuid import uuid4

from shapely.affinity import rotate
from shapely.geometry import LineString, box

from backend.server.scene_service import validate_single_placement

from .models import (
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
    RiskItem,
    RiskResult,
    RiskSummary,
)


def _risk_id() -> str:
    return f"risk_{uuid4().hex[:12]}"


def _scene_object(item) -> dict:
    return {
        "furniture_id": item.furniture_id,
        "catalog_furniture_id": item.catalog_furniture_id,
        "normalized_type": item.category,
        "name_zh_raw": item.name,
        "size_cm": {
            "width": item.width_cm,
            "depth": item.depth_cm,
            "height": item.height_cm,
        },
        "position_cm": {"x": item.x_cm, "z": item.y_cm},
        "rotation_y_deg": item.rotation_deg,
        "placement_failed": item.placement_failed,
        "placement_reason": item.placement_reason,
    }


def _fallback_floorplan(room) -> dict:
    return {
        "coordinate_unit": "cm",
        "width_cm": room.geometry.length_cm,
        "depth_cm": room.geometry.width_cm,
        "room_height_cm": room.geometry.height_cm,
        "wall_segments": [],
        "door_segments": [],
        "window_segments": [],
        "room_regions": [],
    }


def _furniture_footprint(item):
    footprint = box(
        item.x_cm - item.width_cm / 2,
        item.y_cm - item.depth_cm / 2,
        item.x_cm + item.width_cm / 2,
        item.y_cm + item.depth_cm / 2,
    )
    return rotate(
        footprint,
        -item.rotation_deg,
        origin=(item.x_cm, item.y_cm),
    )


class ExistingEngineRuleService:
    """Use Ancai's engine; add only clearly-labelled MVP advisory checks.

    MVP advisories never convert an otherwise legal engine placement into a new
    geometry truth. They remain professional-confirmation risks in the report.
    """

    engine_adapter = "backend.server.scene_service.validate_single_placement"

    def validate(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult | None = None,
    ) -> RiskResult:
        del quantities
        results: list[RiskItem] = []
        for room in snapshot.rooms:
            floorplan = room.layout_json or _fallback_floorplan(room)
            scene_objects = [_scene_object(item) for item in room.furniture]
            for index, furniture in enumerate(room.furniture):
                if furniture.placement_failed:
                    results.append(
                        RiskItem(
                            id=_risk_id(),
                            room_id=room.room_id,
                            rule="existing_placement_failed",
                            rule_source="ancai_engine",
                            severity="high",
                            passed=False,
                            message=(
                                furniture.placement_reason
                                or f"{furniture.name} 尚未取得合法擺放位置"
                            ),
                            related_items=[furniture.furniture_id],
                        )
                    )
                    continue
                validation = validate_single_placement(
                    floorplan,
                    scene_objects[index],
                    scene_objects[:index] + scene_objects[index + 1 :],
                )
                passed = validation.get("ok") is True
                results.append(
                    RiskItem(
                        id=_risk_id(),
                        room_id=room.room_id,
                        rule="furniture_geometry_legality",
                        rule_source="ancai_engine",
                        severity="low" if passed else "high",
                        passed=passed,
                        message=(
                            f"{furniture.name} 通過既有邊界、重疊、淨空與窗前淨空檢查"
                            if passed
                            else str(validation.get("reason") or "家具幾何檢查未通過")
                        ),
                        related_items=[furniture.furniture_id],
                    )
                )

            results.extend(self._door_advisories(room, floorplan))
            results.append(self._walkway_advisory(room))
            if room.layout_json and room.geometry.opening_area_m2 == 0:
                results.append(
                    RiskItem(
                        id=_risk_id(),
                        room_id=room.room_id,
                        rule="opening_area_confirmation",
                        rule_source="professional_confirmation",
                        severity="medium",
                        passed=False,
                        message="門窗已存在，但開口面積尚未確認；牆面淨面積目前未扣除開口。",
                        professional_confirmation_required=True,
                    )
                )

            if retrieval is not None:
                room_retrieval = next(
                    (
                        item
                        for item in retrieval.rooms
                        if item.room_id == room.room_id
                    ),
                    None,
                )
                for suggestion in (
                    room_retrieval.mep_suggestions if room_retrieval else []
                ):
                    results.append(
                        RiskItem(
                            id=_risk_id(),
                            room_id=room.room_id,
                            rule="required_mep_point_present",
                            rule_source="professional_confirmation",
                            severity=(
                                "low"
                                if suggestion.covered_by_existing_point
                                else "medium"
                            ),
                            passed=suggestion.covered_by_existing_point,
                            message=(
                                f"{suggestion.related_item_name} 的 {suggestion.system} 已有相同系統點位。"
                                if suggestion.covered_by_existing_point
                                else f"{suggestion.related_item_name} 需要 {suggestion.system}，目前未找到相同系統點位。"
                            ),
                            related_items=[suggestion.related_item_id],
                            professional_confirmation_required=True,
                        )
                    )

        risk_count = sum(1 for item in results if not item.passed)
        pass_count = sum(1 for item in results if item.passed)
        return RiskResult(
            summary=RiskSummary(
                risk_count=risk_count,
                pass_count=pass_count,
                status="has_risk" if risk_count else "passed",
            ),
            results=results,
            engine_adapter=self.engine_adapter,
        )

    @staticmethod
    def _door_advisories(room, floorplan: dict) -> list[RiskItem]:
        results: list[RiskItem] = []
        for door_index, door in enumerate(floorplan.get("door_segments") or []):
            try:
                start = door["start"]
                end = door["end"]
                segment = LineString(
                    [
                        (float(start["x"]), float(start.get("z", start.get("y", 0)))),
                        (float(end["x"]), float(end.get("z", end.get("y", 0)))),
                    ]
                )
            except (KeyError, TypeError, ValueError):
                continue
            clearance_depth_cm = max(80.0, segment.length)
            advisory_zone = segment.buffer(clearance_depth_cm, cap_style=2)
            conflicts = [
                item
                for item in room.furniture
                if not item.placement_failed
                and _furniture_footprint(item).intersects(advisory_zone)
            ]
            results.append(
                RiskItem(
                    id=_risk_id(),
                    room_id=room.room_id,
                    rule="door_swing_clearance_advisory",
                    rule_source="mvp_advisory",
                    severity="medium" if conflicts else "low",
                    passed=not conflicts,
                    message=(
                        "MVP 門片淨空 advisory 命中家具；需依鉸鏈方向與實際門扇現場確認。"
                        if conflicts
                        else "MVP 門片淨空 advisory 未命中家具；鉸鏈與開啟方向仍需確認。"
                    ),
                    related_items=[item.furniture_id for item in conflicts],
                    measured_value=round(clearance_depth_cm, 2),
                    threshold_value=80,
                    unit="cm",
                    professional_confirmation_required=True,
                )
            )
        return results

    @staticmethod
    def _walkway_advisory(room) -> RiskItem:
        if not room.furniture:
            return RiskItem(
                id=_risk_id(),
                room_id=room.room_id,
                rule="walkway_clearance_advisory",
                rule_source="mvp_advisory",
                severity="low",
                passed=True,
                message="房間沒有家具，MVP 走道寬度 advisory 無阻擋項目。",
                measured_value=min(
                    room.geometry.length_cm, room.geometry.width_cm
                ),
                threshold_value=80,
                unit="cm",
            )
        candidate_clearances = [
            min(
                room.geometry.length_cm - item.width_cm,
                room.geometry.width_cm - item.depth_cm,
            )
            for item in room.furniture
            if not item.placement_failed
        ]
        clearance = min(candidate_clearances) if candidate_clearances else 0
        passed = clearance >= 80
        return RiskItem(
            id=_risk_id(),
            room_id=room.room_id,
            rule="walkway_clearance_advisory",
            rule_source="mvp_advisory",
            severity="low" if passed else "medium",
            passed=passed,
            message=(
                "MVP 走道寬度近似檢查達 80 cm；仍需確認連通性與實際使用動線。"
                if passed
                else "MVP 走道寬度近似值低於 80 cm；需由設計師確認連通性與實際動線。"
            ),
            measured_value=round(max(0.0, clearance), 2),
            threshold_value=80,
            unit="cm",
            professional_confirmation_required=True,
        )
