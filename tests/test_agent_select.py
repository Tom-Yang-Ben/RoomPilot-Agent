"""LLM 選件邊界測試：不信任模型輸出。"""

import json

import pytest

from backend.agent.select import (
    MAX_ITEMS_PER_ROOM,
    SelectionParseError,
    SelectionUnavailableError,
    build_select_messages,
    parse_selections,
    request_selections,
)


def _candidate(fid: str, kind: str, width_cm: float = 100, depth_cm: float = 50) -> dict:
    return {
        "furniture_id": fid,
        "normalized_type": kind,
        "name_zh_raw": fid,
        "color": "白色",
        "size_cm": {"width": width_cm, "depth": depth_cm, "height": 80},
        "has_model": True,
        "model_url": f"/dataset/{fid}.glb",
    }


def _rooms() -> list[dict]:
    return [
        {"room_id": "bedroom-1", "room_type": "bedroom", "width_cm": 360, "depth_cm": 300},
        {"room_id": "living-1", "room_type": "living_room", "width_cm": 480, "depth_cm": 400},
    ]


def _offers() -> dict[str, list[dict]]:
    return {
        "bedroom-1": [
            _candidate("bed-1", "bed-frame", 160, 200),
            _candidate("nightstand-1", "bedside-table", 40, 40),
            _candidate("wardrobe-1", "pax-wardrobe", 150, 60),
        ],
        "living-1": [
            _candidate("sofa-1", "fabric-sofa", 220, 90),
            _candidate("sofa-2", "leather-sofa", 180, 85),
            _candidate("coffee-1", "coffee-table", 110, 60),
            _candidate("tv-1", "tv-bench", 160, 40),
            _candidate("bookcase-1", "bookcase", 80, 30),
        ],
    }


def _bedroom_only() -> list[dict]:
    return [_rooms()[0]]


def _living_only() -> list[dict]:
    return [_rooms()[1]]


def _selection(room_id: object, *ids: object) -> dict:
    return {
        "room_id": room_id,
        "items": [value if isinstance(value, dict) else {"furniture_id": value} for value in ids],
    }


def test_messages_include_rules_rooms_candidates_and_context() -> None:
    messages = build_select_messages(
        _rooms(),
        _offers(),
        "japandi",
        context={"occupants": 2, "constraints": [{"value": "不要深色"}], "empty": []},
    )
    assert "擺放潛規則" in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert payload["occupants"] == 2
    assert "empty" not in payload
    assert {room["room_id"] for room in payload["rooms"]} == {"bedroom-1", "living-1"}
    assert next(room for room in payload["rooms"] if room["room_id"] == "living-1")["room_type_zh"] == "客廳"


def test_parse_drops_unknown_room_furniture_and_unhashable_room_id() -> None:
    raw = {"selections": [
        _selection("ghost", "sofa-1"),
        _selection("living-1", "sofa-1", "invented"),
        _selection(["not", "hashable"]),
    ]}
    result = parse_selections(raw, _living_only(), _offers())
    assert [entry.item["furniture_id"] for entry in result["living-1"]] == ["sofa-1"]


def test_parse_clamps_count_and_allows_only_one_model_per_family() -> None:
    raw = {"selections": [_selection(
        "living-1",
        {"furniture_id": "sofa-1", "count": 0},
        {"furniture_id": "sofa-2", "count": 2},
        {"furniture_id": "bookcase-1", "count": 99},
    )]}
    result = parse_selections(raw, _living_only(), _offers())
    by_id = {entry.item["furniture_id"]: entry.count for entry in result["living-1"]}
    assert by_id == {"sofa-1": 1, "bookcase-1": 6}


def test_parse_caps_items_per_room() -> None:
    offers = {"living-1": [
        _candidate("sofa", "fabric-sofa"),
        *[_candidate(f"g-{i}", f"generic-{i}") for i in range(12)],
    ]}
    raw = {"selections": [_selection("living-1", "sofa", *[f"g-{i}" for i in range(12)])]}
    assert len(parse_selections(raw, _living_only(), offers)["living-1"]) == MAX_ITEMS_PER_ROOM


def test_parse_applies_room_affinity_and_companion_dependency() -> None:
    offers = _offers()
    offers["living-1"].append(_candidate("wrong-bed", "bed-frame", 160, 200))
    raw = {"selections": [_selection(
        "living-1", "sofa-1", "wrong-bed", "bookcase-1"
    )]}
    result = parse_selections(raw, _living_only(), offers)
    assert [entry.item["furniture_id"] for entry in result["living-1"]] == ["sofa-1", "bookcase-1"]


def test_parse_drops_companion_without_anchor_in_non_required_room() -> None:
    rooms = [{"room_id": "study-1", "room_type": "study"}]
    offers = {"study-1": [
        _candidate("chair", "office-chair"),
        _candidate("bookcase", "bookcase"),
    ]}
    raw = {"selections": [_selection("study-1", "chair", "bookcase")]}
    result = parse_selections(raw, rooms, offers)
    assert [entry.item["furniture_id"] for entry in result["study-1"]] == ["bookcase"]


def test_parse_keeps_companions_when_anchor_exists() -> None:
    raw = {"selections": [_selection("living-1", "sofa-1", "coffee-1", "tv-1")]}
    ids = {entry.item["furniture_id"] for entry in parse_selections(raw, _living_only(), _offers())["living-1"]}
    assert ids == {"sofa-1", "coffee-1", "tv-1"}


def test_parse_rejects_answered_room_without_required_anchor() -> None:
    raw = {"selections": [_selection("bedroom-1", "wardrobe-1")]}
    with pytest.raises(SelectionParseError):
        parse_selections(raw, _bedroom_only(), _offers())


def test_parse_rejects_when_llm_omits_a_required_room() -> None:
    raw = {"selections": [_selection("living-1", "sofa-1")]}
    with pytest.raises(SelectionParseError, match="bedroom-1"):
        parse_selections(raw, _rooms(), _offers())


def test_parse_never_silently_drops_preselected_item_when_anchor_is_missing() -> None:
    user_wardrobe = _candidate("user-wardrobe", "pax-wardrobe", 120, 55)
    offers = _offers()
    offers["bedroom-1"].append(user_wardrobe)
    raw = {"selections": [_selection("living-1", "sofa-1")]}
    with pytest.raises(SelectionParseError, match="bedroom-1"):
        parse_selections(
            raw,
            _rooms(),
            offers,
            preselected={"bedroom-1": [user_wardrobe]},
        )


def test_dining_furniture_belongs_to_the_living_room_and_is_not_forced() -> None:
    # 第 4 步房名收斂到辨識層的類別集後不再有獨立餐廳，餐桌餐椅改掛客廳（餐客合一）。
    # 刻意不列為必備：否則每間客廳都會被硬塞一組餐桌。
    offers = _offers()
    offers["living-1"].append(_candidate("table-1", "dining-table", 130, 90))
    offers["living-1"].append(_candidate("chair-1", "dining-chair", 45, 50))

    result = parse_selections(
        {"selections": [_selection("living-1", "sofa-1", "table-1")]},
        _living_only(),
        offers,
    )

    ids = [entry.item["furniture_id"] for entry in result["living-1"]]
    assert "table-1" in ids


def test_dining_furniture_is_kept_in_a_recognized_dining_room() -> None:
    rooms = [{"room_id": "dining-1", "room_type": "dining_room"}]
    offers = {"dining-1": [
        _candidate("table-1", "dining-table", 130, 90),
        _candidate("chair-1", "dining-chair", 45, 50),
    ]}

    result = parse_selections(
        {"selections": [_selection("dining-1", "table-1", "chair-1")]},
        rooms,
        offers,
    )

    assert [entry.item["furniture_id"] for entry in result["dining-1"]] == [
        "table-1",
        "chair-1",
    ]


def test_dining_furniture_is_dropped_outside_the_living_room() -> None:
    # 房型不合的選件是丟棄並記錄，不是拋錯——LLM 選錯房間不該中止整份配置。
    # 衣櫃一併選入：它現在是臥室基礎必備（REQUIRED_FAMILIES_BY_ROOM）。
    offers = _offers()
    offers["bedroom-1"].append(_candidate("table-1", "dining-table", 130, 90))

    result = parse_selections(
        {"selections": [_selection("bedroom-1", "bed-1", "wardrobe-1", "table-1")]},
        _bedroom_only(),
        offers,
    )

    ids = [entry.item["furniture_id"] for entry in result["bedroom-1"]]
    assert "bed-1" in ids
    assert "table-1" not in ids


def test_preselected_item_is_protected_and_takes_family_slot() -> None:
    offers = _offers()
    user_sofa = _candidate("user-sofa", "sofa-bed", 190, 88)
    offers["bedroom-1"].append(user_sofa)
    raw = {"selections": [_selection("bedroom-1", "bed-1", "wardrobe-1", "nightstand-1")]}
    result = parse_selections(
        raw, _bedroom_only(), offers, preselected={"bedroom-1": [user_sofa]}
    )
    ids = [entry.item["furniture_id"] for entry in result["bedroom-1"]]
    assert ids[0] == "user-sofa"
    assert {"bed-1", "nightstand-1"}.issubset(ids)


def test_preselected_and_required_items_survive_when_llm_omits_room() -> None:
    rooms = _rooms()
    rooms[0]["required_furniture_ids"] = ["bed-1"]
    user_wardrobe = _candidate("user-wardrobe", "pax-wardrobe", 120, 55)
    offers = _offers()
    offers["bedroom-1"].append(user_wardrobe)
    raw = {"selections": [_selection("living-1", "sofa-1")]}
    result = parse_selections(
        raw,
        rooms,
        offers,
        preselected={"bedroom-1": [user_wardrobe]},
    )
    assert [entry.item["furniture_id"] for entry in result["bedroom-1"]] == [
        "user-wardrobe",
        "bed-1",
    ]


def test_all_invalid_selection_raises() -> None:
    with pytest.raises(SelectionParseError):
        parse_selections({"selections": [_selection("living-1", "invented")]}, _living_only(), _offers())
    with pytest.raises(SelectionParseError):
        parse_selections({"wrong": []}, _living_only(), _offers())


def test_request_skips_llm_without_candidates() -> None:
    calls: list = []
    result, model = request_selections(
        _rooms(), {}, "japandi", complete=lambda messages: calls.append(messages)
    )
    assert result == {} and model is None and calls == []


def test_request_reports_unavailable_llm() -> None:
    with pytest.raises(SelectionUnavailableError):
        request_selections(_rooms(), _offers(), "japandi", complete=None)
    with pytest.raises(SelectionUnavailableError):
        request_selections(_rooms(), _offers(), "japandi", complete=lambda _messages: None)


def test_request_returns_validated_result_and_model() -> None:
    def complete(_messages: list[dict[str, str]]) -> tuple[str, dict]:
        return "mock/select", {"selections": [
            _selection("bedroom-1", "bed-1", "wardrobe-1",
                       {"furniture_id": "nightstand-1", "count": 2}),
            _selection("living-1", "sofa-1", "coffee-1", "invented"),
        ]}

    result, model = request_selections(_rooms(), _offers(), "japandi", complete=complete)
    assert model == "mock/select"
    assert next(entry.count for entry in result["bedroom-1"] if entry.item["furniture_id"] == "nightstand-1") == 2
    assert {entry.item["furniture_id"] for entry in result["living-1"]} == {"sofa-1", "coffee-1"}
