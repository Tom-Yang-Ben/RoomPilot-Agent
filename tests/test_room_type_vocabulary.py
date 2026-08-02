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

from backend.floorplan.vision.analysis import CODY_ROOM_TYPE_MAP, ROOM_LABELS
from backend.paths import STATIC_DIR
from backend.server.scene_service import SPACE_DEFAULTS


CANONICAL = {room_type for room_type, _aliases in ROOM_LABELS}


def _scene_v2_dropdown_types() -> set[str]:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
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
    source = (STATIC_DIR / "scene_layout2d.js").read_text(encoding="utf-8")
    block = source.split("const recommendations = {", 1)[1].split("};", 1)[0]
    known = set(re.findall(r"^\s*([a-z_]+):", block, re.MULTILINE))
    missing = CANONICAL - known
    assert not missing, f"前端推薦表缺型別：{sorted(missing)}"


def test_room_type_select_is_wired_in_the_review_card() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-type"' in html
    assert 'roomType: $("#room-type")' in source
    assert "applyRoomTypeSelection" in source
    assert "export function roomTypeFromName" in (
        STATIC_DIR / "scene_layout2d.js"
    ).read_text(encoding="utf-8")
    # 改名時若尚未指定型別，必須嘗試由名稱回寫 room.type。
    # 舊版傳的 `name` 是未宣告變數，回寫等於永遠拿不到型別。
    assert "roomTypeFromName({ label: option.label })" in source
    assert "roomTypeFromName({ label: name })" not in source


def test_room_name_select_is_generated_from_the_single_option_table() -> None:
    """房名下拉不得寫死在 HTML（QA 2026-08-01 迴歸）。

    7242f0b 把房名收斂到辨識層的 10 類，但 scene.html 仍留著舊 12 類硬編碼
    <option>：臥室選不到、主臥／次臥等 6 個舊值按「套用名稱」會被判成
    「請選擇空間名稱」——錯誤訊息還把資料脫鉤說成使用者沒選。
    """
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-name"' in html
    assert "function renderRoomNameSelect" in source
    assert "renderRoomNameSelect(selectedRoom)" in source
    # 選項只能由 ROOM_NAME_OPTIONS 生成，HTML 不得自己列。
    for legacy in ("primary_bedroom", "secondary_bedroom", "dining_room", "multi_purpose"):
        assert f'<option value="{legacy}"' not in html
    assert 'ROOM_NAME_OPTIONS.map' in source


def test_room_name_options_only_emit_canonical_room_types() -> None:
    """「空間名稱」寫進 room.type 的值，每一個都必須在正典裡。

    這條邊原本沒鎖：7242f0b 給玄關／樓梯／車庫配了 entry／stair／garage 三個
    正典外的 type，第 4 步「空間用途」因此顯示「其他／未指定」，而
    normalize_required_furniture 對表外型別會退成 SPACE_DEFAULTS["living_room"]
    ——玄關被塞沙發、茶几與電視櫃。dropdown 那條契約是綠的，因為它只檢查
    ROOM_TYPE_OPTIONS，不檢查 ROOM_NAME_OPTIONS 產出的值。
    """
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    block = source.split("const ROOM_NAME_OPTIONS = Object.freeze([", 1)[1].split("]);", 1)[0]
    emitted = set(re.findall(r'type:\s*"([a-z_]+)"', block))

    assert emitted, "ROOM_NAME_OPTIONS 解析失敗"
    outside = emitted - CANONICAL
    assert not outside, f"空間名稱寫出正典外的用途：{sorted(outside)}"
    # 每一個都必須有家具預設，否則會靜默退成客廳家具。
    assert not emitted - set(SPACE_DEFAULTS), sorted(emitted - set(SPACE_DEFAULTS))


def test_legacy_room_types_migrate_into_canonical_vocabulary() -> None:
    """舊專案存下來的 entry／stair／garage 必須遷移，不能落到 default。"""
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    block = source.split("const LEGACY_ROOM_TYPES = Object.freeze({", 1)[1].split("});", 1)[0]
    migration = dict(re.findall(r'(\w+):\s*"([a-z_]+)"', block))

    assert set(migration) == {"entry", "stair", "garage"}
    assert set(migration.values()) <= CANONICAL
    assert "LEGACY_ROOM_TYPES[raw] || raw" in source


def test_questionnaire_routes_by_room_name_not_room_type() -> None:
    """問卷分派看空間名稱，不看空間用途。

    玄關與樓梯的 type 都併成 circulation 之後，若還從 type 反推，玄關會拿到
    走道的 2 題而不是自己的 4 題。
    """
    source = (STATIC_DIR / "scene_questionnaire_test2.js").read_text(encoding="utf-8")
    block = source.split("const VISUAL_SPACES_BY_ROOM_NAME = Object.freeze({", 1)[1].split("});", 1)[0]

    assert re.search(r'entryway:\s*\["entryway"\]', block)
    assert re.search(r'hallway:\s*\["circulation"\]', block)
    assert re.search(r'stair:\s*\[\]', block)
    assert re.search(r'garage:\s*\[\]', block)
    assert "function visualSpacesFor" in source
    assert "ROOM_TO_VISUAL_SPACES[room.type] || []" in source, "名稱缺漏時仍要能退回用途"


def test_scene_html_has_no_duplicate_element_ids() -> None:
    """重複 id 讓 querySelector 只拿得到第一個，另一半 UI 變成死的。"""
    import collections

    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")
    counts = collections.Counter(re.findall(r'\sid="([^"]+)"', html))
    duplicates = {name: count for name, count in counts.items() if count > 1}

    assert duplicates == {}
