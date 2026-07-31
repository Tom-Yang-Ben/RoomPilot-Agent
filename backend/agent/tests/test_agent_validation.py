"""驗證 skill：engine 硬規則、需求缺口、語意軟規則（advisory）。"""
from backend.agent.documents import (
    LayoutDoc,
    LayoutRoom,
    RequirementDoc,
    RequirementItem,
    SceneDoc,
)
from backend.agent.skills.validation import ValidationSkill
from backend.agent.tools.read_rules import ReadRulesTool


def _layout() -> LayoutDoc:
    return LayoutDoc(rooms=[LayoutRoom(room_id="living", name="客廳", width_cm=400, depth_cm=300)])


def _placed(item_id, type_, width, depth, pos_x, pos_y, rotation=0.0, **extra) -> dict:
    return {
        "schema_version": "2.0",
        "coordinate_unit": "cm",
        "id": item_id,
        "type": type_,
        "name": item_id,
        "width": width,
        "depth": depth,
        "height": 80,
        "pos_x": pos_x,
        "pos_y": pos_y,
        "rotation": rotation,
        **extra,
    }


def test_engine_hard_track_catches_overlap():
    scene = SceneDoc(
        rooms={
            "living": {
                "placed": [
                    _placed("sofa_1", "sofa", 180, 90, 200, 150),
                    _placed("sofa_2", "sofa", 180, 90, 200, 150),  # 完全重疊
                ],
                "failed": [],
            }
        }
    )
    report = ValidationSkill(None).run(
        RequirementDoc(), _layout(), scene, ReadRulesTool().run(None)
    )
    assert report.hard_violations, "重疊家具必須被 engine 攔下"
    assert not report.passed
    assert all(v.source == "engine" for v in report.hard_violations)


def test_requirement_gap_detected_when_must_missing():
    requirements = RequirementDoc(
        hard=[RequirementItem(req_id="H1", text="雙人床", room_id="living", category="bed")]
    )
    scene = SceneDoc(
        rooms={
            "living": {
                "placed": [_placed("sofa_1", "sofa", 180, 90, 200, 150)],
                "failed": [
                    {
                        "id": "bed_1",
                        "category": "bed",
                        "room_id": "living",
                        "matched_requirements": ["H1"],
                        "reason": "找不到合法擺放位置",
                    }
                ],
            }
        }
    )
    report = ValidationSkill(None).run(
        requirements, _layout(), scene, ReadRulesTool().run(None)
    )
    assert len(report.requirement_gaps) == 1
    gap = report.requirement_gaps[0]
    assert gap.req_id == "H1" and "擺放失敗" in gap.message
    assert report.suggestions, "放不下應產生修復建議"


def test_soft_rules_warn_but_do_not_block():
    # 沙發（rot=180 面向下緣）背對電視櫃（在上緣）；地毯遠離主家具。
    scene = SceneDoc(
        rooms={
            "living": {
                "placed": [
                    _placed("sofa_1", "sofa", 180, 90, 200, 100, rotation=180),
                    _placed("media_1", "media", 160, 40, 200, 270),
                    _placed("rug_1", "rug", 100, 60, 60, 260),
                ],
                "failed": [],
            }
        }
    )
    report = ValidationSkill(None).run(
        RequirementDoc(), _layout(), scene, ReadRulesTool().run(None)
    )
    rule_ids = {warning.rule_id for warning in report.soft_warnings}
    assert "sofa_faces_tv" in rule_ids
    assert "rug_anchored" in rule_ids
    # 軟規則不影響 passed（此場景無硬違規、無需求缺口時）
    if not report.hard_violations:
        assert report.passed
