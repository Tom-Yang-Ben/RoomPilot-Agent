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
        _selection("living-1", "sofa-1", "tv-1", "invented"),
        _selection(["not", "hashable"]),
    ]}
    result = parse_selections(raw, _living_only(), _offers())
    assert [entry.item["furniture_id"] for entry in result["living-1"]] == ["sofa-1", "tv-1"]


def test_parse_clamps_count_and_allows_only_one_model_per_family() -> None:
    raw = {"selections": [_selection(
        "living-1",
        {"furniture_id": "sofa-1", "count": 0},
        {"furniture_id": "sofa-2", "count": 2},
        {"furniture_id": "tv-1", "count": 1},
        {"furniture_id": "bookcase-1", "count": 99},
    )]}
    result = parse_selections(raw, _living_only(), _offers())
    by_id = {entry.item["furniture_id"]: entry.count for entry in result["living-1"]}
    assert by_id == {"sofa-1": 1, "tv-1": 1, "bookcase-1": 6}


def test_parse_caps_items_per_room() -> None:
    offers = {"living-1": [
        _candidate("sofa", "fabric-sofa"),
        _candidate("tv", "tv-bench"),
        *[_candidate(f"g-{i}", f"generic-{i}") for i in range(12)],
    ]}
    raw = {"selections": [_selection("living-1", "sofa", "tv", *[f"g-{i}" for i in range(12)])]}
    assert len(parse_selections(raw, _living_only(), offers)["living-1"]) == MAX_ITEMS_PER_ROOM


def test_parse_applies_room_affinity_and_companion_dependency() -> None:
    offers = _offers()
    offers["living-1"].append(_candidate("wrong-bed", "bed-frame", 160, 200))
    raw = {"selections": [_selection(
        "living-1", "sofa-1", "tv-1", "wrong-bed", "bookcase-1"
    )]}
    result = parse_selections(raw, _living_only(), offers)
    assert [entry.item["furniture_id"] for entry in result["living-1"]] == ["sofa-1", "tv-1", "bookcase-1"]


def test_parse_drops_companion_without_anchor_in_non_required_room() -> None:
    # 多功能室無硬性最少清單，用來測「有副件無主件 → 丟棄副件」。
    rooms = [{"room_id": "flex-1", "room_type": "multifunction"}]
    offers = {"flex-1": [
        _candidate("chair", "office-chair"),
        _candidate("bookcase", "bookcase"),
    ]}
    raw = {"selections": [_selection("flex-1", "chair", "bookcase")]}
    result = parse_selections(raw, rooms, offers)
    assert [entry.item["furniture_id"] for entry in result["flex-1"]] == ["bookcase"]


def test_workspace_requires_desk_and_office_chair() -> None:
    rooms = [{"room_id": "study-1", "room_type": "study"}]
    offers = {"study-1": [
        _candidate("desk-1", "desk"),
        _candidate("chair", "office-chair"),
        _candidate("bookcase", "bookcase"),
    ]}
    result = parse_selections(
        {"selections": [_selection("study-1", "desk-1", "chair", "bookcase")]},
        rooms,
        offers,
    )
    assert {entry.item["furniture_id"] for entry in result["study-1"]} == {
        "desk-1", "chair", "bookcase"
    }
    with pytest.raises(SelectionParseError, match="desk"):
        parse_selections(
            {"selections": [_selection("study-1", "chair", "bookcase")]},
            rooms,
            offers,
        )


def test_parse_keeps_companions_when_anchor_exists() -> None:
    raw = {"selections": [_selection("living-1", "sofa-1", "coffee-1", "tv-1")]}
    ids = {entry.item["furniture_id"] for entry in parse_selections(raw, _living_only(), _offers())["living-1"]}
    assert ids == {"sofa-1", "coffee-1", "tv-1"}


def test_parse_rejects_answered_room_without_required_anchor() -> None:
    raw = {"selections": [_selection("bedroom-1", "wardrobe-1")]}
    with pytest.raises(SelectionParseError, match="bed"):
        parse_selections(raw, _bedroom_only(), _offers())


def test_parse_rejects_bedroom_without_wardrobe() -> None:
    raw = {"selections": [_selection("bedroom-1", "bed-1", "nightstand-1")]}
    with pytest.raises(SelectionParseError, match="wardrobe"):
        parse_selections(raw, _bedroom_only(), _offers())


def test_parse_rejects_living_room_without_tv_bench() -> None:
    raw = {"selections": [_selection("living-1", "sofa-1", "coffee-1")]}
    with pytest.raises(SelectionParseError, match="tv-bench"):
        parse_selections(raw, _living_only(), _offers())


def test_parse_rejects_when_llm_omits_a_required_room() -> None:
    raw = {"selections": [_selection("living-1", "sofa-1", "tv-1")]}
    with pytest.raises(SelectionParseError, match="bedroom-1"):
        parse_selections(raw, _rooms(), _offers())


def test_parse_never_silently_drops_preselected_item_when_anchor_is_missing() -> None:
    user_wardrobe = _candidate("user-wardrobe", "pax-wardrobe", 120, 55)
    offers = _offers()
    offers["bedroom-1"].append(user_wardrobe)
    raw = {"selections": [_selection("living-1", "sofa-1", "tv-1")]}
    with pytest.raises(SelectionParseError, match="bedroom-1"):
        parse_selections(
            raw,
            _rooms(),
            offers,
            preselected={"bedroom-1": [user_wardrobe]},
        )


def test_dining_room_requires_both_table_and_chair() -> None:
    rooms = [{"room_id": "dining-1", "room_type": "dining_room"}]
    offers = {"dining-1": [
        _candidate("table", "dining-table"),
        _candidate("chair", "dining-chair"),
    ]}
    with pytest.raises(SelectionParseError, match="dining-chair"):
        parse_selections(
            {"selections": [_selection("dining-1", "table")]},
            rooms,
            offers,
        )


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
    assert {"bed-1", "wardrobe-1", "nightstand-1"}.issubset(ids)


def test_preselected_and_required_items_survive_when_llm_omits_room() -> None:
    rooms = _rooms()
    rooms[0]["required_furniture_ids"] = ["bed-1", "nightstand-1"]
    user_wardrobe = _candidate("user-wardrobe", "pax-wardrobe", 120, 55)
    offers = _offers()
    offers["bedroom-1"].append(user_wardrobe)
    raw = {"selections": [_selection("living-1", "sofa-1", "tv-1")]}
    result = parse_selections(
        raw,
        rooms,
        offers,
        preselected={"bedroom-1": [user_wardrobe]},
    )
    assert [entry.item["furniture_id"] for entry in result["bedroom-1"]] == [
        "user-wardrobe",
        "bed-1",
        "nightstand-1",
    ]


def test_all_invalid_selection_raises() -> None:
    with pytest.raises(SelectionParseError):
        parse_selections({"selections": [_selection("living-1", "invented")]}, _living_only(), _offers())
    with pytest.raises(SelectionParseError):
        parse_selections({"wrong": []}, _living_only(), _offers())


def test_entry_requires_shoe_cabinet() -> None:
    rooms = [{"room_id": "entry-1", "room_type": "entryway"}]
    offers = {"entry-1": [
        _candidate("shoe-1", "shoe-cabinet"),
        _candidate("rack-1", "clothes-rack"),
    ]}
    result = parse_selections(
        {"selections": [_selection("entry-1", "shoe-1", "rack-1")]},
        rooms,
        offers,
    )
    assert [entry.item["furniture_id"] for entry in result["entry-1"]] == ["shoe-1", "rack-1"]
    with pytest.raises(SelectionParseError, match="shoe-cabinet"):
        parse_selections(
            {"selections": [_selection("entry-1", "rack-1")]},
            rooms,
            offers,
        )


def test_kitchen_allows_empty_automatic_selection() -> None:
    rooms = [{"room_id": "kitchen-1", "room_type": "kitchen"}]
    offers = {"kitchen-1": [_candidate("cabinet-1", "cabinet-cupboard")]}
    # 廚房無最少必備族系：本地／LLM 可不選，但若選了仍須通過房型規則。
    result = parse_selections({"selections": []}, rooms, offers)
    assert result == {}


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
            _selection(
                "bedroom-1",
                "bed-1",
                "wardrobe-1",
                {"furniture_id": "nightstand-1", "count": 2},
            ),
            _selection("living-1", "sofa-1", "tv-1", "coffee-1", "invented"),
        ]}

    result, model = request_selections(_rooms(), _offers(), "japandi", complete=complete)
    assert model == "mock/select"
    assert next(entry.count for entry in result["bedroom-1"] if entry.item["furniture_id"] == "nightstand-1") == 2
    assert {entry.item["furniture_id"] for entry in result["living-1"]} == {"sofa-1", "tv-1", "coffee-1"}


def test_prompt_rules_match_room_strategy_minimums() -> None:
    from backend.agent.knowledge import prompt_rules

    text = prompt_rules()
    assert "床、衣櫃、床頭櫃" in text
    assert "沙發、電視櫃" in text
    assert "count=2" not in text
