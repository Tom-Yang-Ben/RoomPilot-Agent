"""WorkflowSnapshotAdapter：既有前端 workflow state → ProjectSnapshot 對照測試。"""
from datetime import date

import pytest

from backend.engineering.adapters.workflow_snapshot import snapshot_draft_from_workflow


def _sample_workflow() -> dict:
    return {
        "confirmed_floorplan": {"floorplan": {"room_height_cm": 280}},
        "space_confirmation": {
            "coordinate_unit": "cm",
            "rooms": [
                {
                    "id": "room-1",
                    "label": "客廳",
                    "type": "living_room",
                    "confirmed": True,
                    "polygon_cm": [
                        {"x": 0, "y": 0},
                        {"x": 420, "y": 0},
                        {"x": 420, "y": 360},
                        {"x": 0, "y": 360},
                    ],
                },
                {
                    "id": "room-2",
                    "label": "主臥",
                    "type": "bedroom",
                    "confirmed": True,
                    "polygon_cm": [
                        {"x": 420, "y": 0},
                        {"x": 740, "y": 0},
                        {"x": 740, "y": 360},
                        {"x": 420, "y": 360},
                    ],
                },
            ],
            "structures": {
                "walls": [],
                "doors": [
                    {
                        "id": "door-1",
                        "start": {"x": 200, "y": 0},
                        "end": {"x": 290, "y": 0},
                        "height_cm": 210,
                    }
                ],
                "windows": [
                    {
                        "id": "win-1",
                        "start": {"x": 0, "y": 100},
                        "end": {"x": 0, "y": 250},
                        "height_cm": 120,
                        "sill_height_cm": 90,
                    }
                ],
                "beams": [],
                "columns": [],
            },
        },
        "requirements": {
            "finishes": {
                "stylePackId": "japandi-a",
                "wallMaterial": "乳膠漆",
                "wallColor": "米白",
                "floorMaterial": "SPC 石塑地板",
                "floorColor": "淺橡木",
                "ceilingMaterial": "平釘天花",
                "ceilingColor": "#f4f1eb",
            }
        },
        "configuration": {
            "schema_version": 3,
            "active_scheme_id": "A",
            "locked_scheme_id": "A",
            "schemes": {
                "A": {
                    "furniture": [
                {
                    "id": "room-1-sofa-1",
                    "type": "sofa",
                    "label": "三人沙發",
                    "widthCm": 210,
                    "depthCm": 90,
                    "heightCm": 80,
                    # layout_2d 座標以整張平面圖中心 (370, 180) 為原點。
                    "xCm": -160,  # 平面 210 → room-1 內
                    "yCm": -30,   # 平面 150
                    "rotationDeg": 0,
                    "roomId": "room-1",
                    "iconPath": "/static/icons/sofa.svg",
                },
                {
                    "id": "room-1-tv-1",
                    "type": "television",
                    "label": "電視",
                    "widthCm": 125,
                    "depthCm": 10,
                    "heightCm": 75,
                    "xCm": -170,
                    "yCm": 120,
                    "rotationDeg": 0,
                    "roomId": "room-1",
                },
                {
                    "id": "room-2-bed-1",
                    "type": "bed",
                    "label": "雙人床",
                    "widthCm": 152,
                    "depthCm": 190,
                    "heightCm": 45,
                    "xCm": 210,  # 平面 580 → room-2 內
                    "yCm": 0,    # 平面 180
                    "rotationDeg": 90,
                    "roomId": "room-2",
                },
                    ]
                }
            },
        },
        "proposal_review": {
            "jobs": [
                {
                    "job_id": "job-1",
                    "mode": "room_final",
                    "room_id": "room-1",
                    "label": "客廳主視角",
                    "image_url": "/api/projects/P1/renders/r1/png",
                    "status": "completed",
                }
            ]
        },
    }


def test_workflow_maps_rooms_dimensions_and_openings() -> None:
    snapshot = snapshot_draft_from_workflow(
        "P1",
        "D1",
        _sample_workflow(),
        region="新北市",
        pricing_basis_date=date(2026, 7, 29),
    )
    assert snapshot.project_id == "P1"
    assert snapshot.revision == "D1"
    assert snapshot.approval_status == "draft"
    assert [room.room_id for room in snapshot.rooms] == ["room-1", "room-2"]

    living = snapshot.rooms[0]
    assert living.geometry.length_m == pytest.approx(4.2)
    assert living.geometry.width_m == pytest.approx(3.6)
    assert living.geometry.height_m == pytest.approx(2.8)
    # 門 90cm×210cm + 窗 150cm×120cm 都落在 room-1 邊界 → 3.69 m²
    assert living.geometry.opening_area_m2 == pytest.approx(3.69, abs=0.01)


def test_workflow_maps_materials_furniture_and_renders() -> None:
    snapshot = snapshot_draft_from_workflow(
        "P1",
        "D1",
        _sample_workflow(),
        region="新北市",
        pricing_basis_date=date(2026, 7, 29),
    )
    living = snapshot.rooms[0]

    parts = {material.part: material for material in living.materials}
    assert parts["floor"].name == "SPC 石塑地板"
    assert parts["wall"].name == "乳膠漆"
    assert parts["ceiling"].name == "平釘天花"

    sofa = next(f for f in living.furniture if f.category == "sofa")
    # 平面座標 (210,150) − room-1 bbox 原點 (0,0) = 房間座標 (210,150)。
    assert sofa.x_cm == pytest.approx(210)
    assert sofa.y_cm == pytest.approx(150)

    tv = next(f for f in living.furniture if f.category == "television")
    assert tv.needs_power is True

    bedroom = snapshot.rooms[1]
    bed = bedroom.furniture[0]
    # 平面 (580,180) − room-2 bbox 原點 (420,0) = (160,180)。
    assert bed.x_cm == pytest.approx(160)
    assert bed.y_cm == pytest.approx(180)
    assert bed.rotation_deg == pytest.approx(90)

    assert living.renders
    assert living.renders[0].render_url == "/api/projects/P1/renders/r1/png"
    assert not bedroom.renders  # job 只綁 room-1


def test_workflow_without_rooms_raises() -> None:
    with pytest.raises(ValueError, match="WORKFLOW_HAS_NO_ROOMS"):
        snapshot_draft_from_workflow(
            "P1",
            "D1",
            {"space_confirmation": {"rooms": []}},
            region="新北市",
            pricing_basis_date=date(2026, 7, 29),
        )


def test_workflow_missing_height_and_finishes_records_assumptions() -> None:
    workflow = _sample_workflow()
    workflow["confirmed_floorplan"] = {}
    workflow["requirements"] = {}
    snapshot = snapshot_draft_from_workflow(
        "P1",
        "D1",
        workflow,
        region="新北市",
        pricing_basis_date=date(2026, 7, 29),
    )
    assert snapshot.rooms[0].geometry.height_m == pytest.approx(2.7)
    assert any("樓高" in item for item in snapshot.assumptions)
    assert any("材料" in item for item in snapshot.assumptions)
