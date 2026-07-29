"""房型詞彙的跨層一致性契約（2026-07 盤點第 5 項「指定用途」修復）。

盤點確認全系統曾有六套以上互不一致的房型詞彙表，是快取鍵、entry/storage
被丟等多個洞的共同病根。本檔以 `backend.floorplan.vision.analysis.ROOM_LABELS`
為唯一正典，鎖住四個消費層：

1. 前端「空間用途」下拉（scene_v2.js ROOM_TYPE_OPTIONS）＝正典 ∪ {default}
2. 後端問卷預設家具表（scene_service.SPACE_DEFAULTS）⊇ 正典
3. 語意層對照表（CODY_ROOM_TYPE_MAP）的值 ⊆ 正典 ∪ {None}
4. 前端推薦表（scene_layout2d.js）認得正典的每一型

任何一層加新房型而其他層沒跟上，這裡會先紅。
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.floorplan.vision.analysis import CODY_ROOM_TYPE_MAP, ROOM_LABELS
from backend.server.scene_service import SPACE_DEFAULTS

STATIC = Path(__file__).resolve().parents[1] / "backend" / "server" / "static"

CANONICAL = {room_type for room_type, _aliases in ROOM_LABELS}


def _scene_v2_dropdown_types() -> set[str]:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    block = source.split("const ROOM_TYPE_OPTIONS = [", 1)[1].split("];", 1)[0]
    return set(re.findall(r'\[\s*"([a-z_]+)"\s*,', block))


def test_canonical_room_types_are_the_expected_nine() -> None:
    assert CANONICAL == {
        "living_room", "bedroom", "kitchen", "dining_room", "bathroom",
        "balcony", "workspace", "storage", "circulation",
    }


def test_room_type_dropdown_matches_canonical_vocabulary() -> None:
    assert _scene_v2_dropdown_types() == CANONICAL | {"default"}


def test_space_defaults_cover_every_canonical_type() -> None:
    """下拉開放後使用者選得到的每一型，後端問卷預設表都必須認得——
    表外型別會靜默退成客廳家具（盤點實測：浴室被塞沙發）。"""
    missing = CANONICAL - set(SPACE_DEFAULTS)
    assert not missing, f"SPACE_DEFAULTS 缺型別：{sorted(missing)}"
    # circulation 是刻意零家具，但鍵必須存在（顯式空清單≠表外退化）。
    assert SPACE_DEFAULTS["circulation"] == []


def test_semantic_map_values_stay_inside_canonical_vocabulary() -> None:
    values = {value for value in CODY_ROOM_TYPE_MAP.values() if value is not None}
    assert values <= CANONICAL


def test_frontend_recommendation_table_knows_every_canonical_type() -> None:
    source = (STATIC / "scene_layout2d.js").read_text(encoding="utf-8")
    block = source.split("const recommendations = {", 1)[1].split("};", 1)[0]
    known = set(re.findall(r"^\s*([a-z_]+):", block, re.MULTILINE))
    missing = CANONICAL - known
    assert not missing, f"前端推薦表缺型別：{sorted(missing)}"


def test_room_type_select_is_wired_in_the_review_card() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-type"' in html
    assert 'roomType: $("#room-type")' in source
    assert "applyRoomTypeSelection" in source
    assert "export function roomTypeFromName" in (
        STATIC / "scene_layout2d.js"
    ).read_text(encoding="utf-8")
    # 改名時若尚未指定型別，必須嘗試由名稱回寫 room.type。
    assert "roomTypeFromName({ label: name })" in source
