from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import box

from roompilot.floorplan.room_analysis import derive_room_regions
from roompilot.upgrade3d.dxf_parser import parse_dxf_file


def _record(polygon) -> dict:
    return {
        "exterior": [[x, z] for x, z in polygon.exterior.coords],
        "holes": [],
    }


def _two_room_floorplan() -> dict:
    walls = [
        box(0, 0, 10, 0.2),
        box(0, 7.8, 10, 8),
        box(0, 0, 0.2, 8),
        box(9.8, 0, 10, 8),
        box(4.9, 0.2, 5.1, 3.6),
        box(4.9, 4.4, 5.1, 7.8),
    ]
    return {
        "bbox": {"minx": 0, "minz": 0, "maxx": 10, "maxz": 8},
        "wall_thickness": 0.18,
        "wall_polys": [_record(wall) for wall in walls],
        "texts": [],
        "rooms": [],
    }


def test_offline_geometry_closes_door_gap_and_produces_stable_rooms() -> None:
    floorplan = _two_room_floorplan()

    first = derive_room_regions(floorplan)
    second = derive_room_regions(floorplan)

    assert len(first) == 2
    assert [room["room_id"] for room in first] == [room["room_id"] for room in second]
    assert all(room["confirmed"] is False for room in first)
    assert all(room["room_type"] == "other" for room in first)
    assert sum(room["area_m2"] for room in first) > 65


def test_dxf_text_wins_over_openrouter_suggestion_and_ai_fills_other_room() -> None:
    floorplan = _two_room_floorplan()
    floorplan["texts"] = [{"text": "BEDROOM", "x": 2.5, "z": 4.0}]
    floorplan["rooms"] = [
        {
            "label": "KITCHEN",
            "label_zh": "廚房",
            "kind": "fixed_utility",
            "evidence": "fixtures",
            "bbox": [5.2, 0.5, 9.5, 7.5],
        },
        {
            "label": "LIVING",
            "label_zh": "客廳",
            "kind": "living",
            "evidence": "text",
            "bbox": [0.5, 0.5, 4.8, 7.5],
        },
    ]

    regions = derive_room_regions(floorplan)
    sources = {room["label_source"]: room for room in regions}

    assert sources["dxf_text"]["room_type"] == "bedroom"
    assert sources["dxf_text"]["confidence"] == 0.95
    assert sources["ai_suggestion"]["room_type"] == "kitchen"
    assert sources["ai_suggestion"]["confidence"] < 1


def test_dxf_parser_exposes_text_with_the_same_centered_metre_coordinates(
    tmp_path: Path,
) -> None:
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for start, end in (
        ((0, 0), (6, 0)),
        ((6, 0), (6, 4)),
        ((6, 4), (0, 4)),
        ((0, 4), (0, 0)),
    ):
        msp.add_line(start, end, dxfattribs={"layer": "WALL"})
    msp.add_text("KITCHEN", dxfattribs={"insert": (3, 2), "layer": "ROOM_NAME"})
    path = tmp_path / "labels.dxf"
    doc.saveas(path)

    parsed = parse_dxf_file(path)
    regions = derive_room_regions(parsed)

    assert parsed["texts"] == [{"text": "KITCHEN", "x": 0.0, "z": 0.0}]
    assert parsed["stats"]["texts"] == 1
    assert len(regions) == 1
    assert regions[0]["room_type"] == "kitchen"
    assert regions[0]["label_source"] == "dxf_text"


def test_png_is_sent_to_openrouter_only_with_explicit_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from roompilot.server import main as server_main

    source = Path(__file__).resolve().parents[1] / "testdata" / "png" / "floor21.png"
    calls = []

    def fake_annotation(raw: bytes, mime: str):
        calls.append((len(raw), mime))
        return {
            "model": "test/vision-model",
            "rooms": [{
                "label": "LIVING ROOM",
                "label_zh": "客廳",
                "kind": "living",
                "evidence": "fixtures",
                "bbox_norm": [0, 0, 1000, 1000],
            }],
            "door_count": 1,
            "window_count": 2,
            "printed_dimensions": [],
        }

    monkeypatch.setattr(server_main, "vlm_enabled", lambda: True)
    monkeypatch.setattr(server_main, "annotate_floorplan", fake_annotation)
    analysis = server_main._recognize_floorplan_bytes(
        source.read_bytes(),
        source.name,
        allow_openrouter=True,
    )

    assert calls == [(source.stat().st_size, "image/png")]
    assert analysis["openrouter"] == {
        "provider": "openrouter",
        "requested": True,
        "sent": True,
        "status": "suggested",
        "model": "test/vision-model",
    }
    assert analysis["floorplan"]["room_regions"][0]["room_type"] == "living_room"
    assert analysis["floorplan"]["room_regions"][0]["label_source"] == "ai_suggestion"

    calls.clear()
    offline = server_main._recognize_floorplan_bytes(
        source.read_bytes(),
        source.name,
        allow_openrouter=False,
    )
    assert calls == []
    assert offline["openrouter"]["status"] == "not_requested"
