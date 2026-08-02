"""scene_json 必須帶門洞（QA 2026-08-01 #9）。

scene_viewer.js 的走動碰撞會豁免 floorplan.door_openings，但後端從來沒有輸出
這個鍵 → 門洞豁免永不生效，每一扇門在第 7 步都是實牆，人走到門口就被擋住。
"""

from __future__ import annotations

from backend.paths import STATIC_DIR
from backend.server.scene_service import door_openings_from_segments


def _door(start: dict, end: dict, **extra) -> dict:
    return {"start": start, "end": end, **extra}


def test_plain_door_becomes_an_opening_with_measured_width() -> None:
    openings = door_openings_from_segments({
        "door_segments": [_door({"x": 0, "z": 0}, {"x": 90, "z": 0})]
    })

    assert openings == [{
        "start": {"x": 0.0, "z": 0.0},
        "end": {"x": 90.0, "z": 0.0},
        "width_cm": 90.0,
        "kind": "door",
    }]


def test_swing_door_uses_the_closed_leaf_not_the_opened_one() -> None:
    """start → end 是打開後的門片；牆洞是 hinge → swing_end。"""
    openings = door_openings_from_segments({
        "door_segments": [
            _door(
                {"x": 0, "z": 0},
                {"x": 0, "z": 80},
                closed_segment={
                    "start": {"x": 0, "z": 0},
                    "end": {"x": 80, "z": 0},
                    "source": "swing_arc",
                },
            )
        ]
    })

    assert openings[0]["end"] == {"x": 80.0, "z": 0.0}
    assert openings[0]["width_cm"] == 80.0


def test_declared_width_wins_over_the_measured_one() -> None:
    openings = door_openings_from_segments({
        "door_segments": [_door({"x": 0, "z": 0}, {"x": 90, "z": 0}, width_cm=75)]
    })

    assert openings[0]["width_cm"] == 75.0


def test_malformed_doors_are_skipped_without_raising() -> None:
    openings = door_openings_from_segments({
        "door_segments": [
            "not-a-dict",
            {"start": {"x": 0, "z": 0}},
            _door({"x": "abc", "z": 0}, {"x": 90, "z": 0}),
            _door({"x": 0, "z": 0}, {"x": 90, "z": 0}),
        ]
    })

    assert len(openings) == 1


def test_missing_floorplan_returns_no_openings() -> None:
    assert door_openings_from_segments(None) == []
    assert door_openings_from_segments({}) == []


def test_scene_payload_exposes_door_openings_to_the_viewer() -> None:
    from backend.server import scene_service

    source = (scene_service.__file__ and open(scene_service.__file__, encoding="utf-8").read())
    assert '"door_openings": door_openings_from_segments(parsed_floorplan)' in source

    viewer = (
        STATIC_DIR / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    # 消費端的鍵名不能和生產端漂開。
    assert "floorplan?.door_openings" in viewer
