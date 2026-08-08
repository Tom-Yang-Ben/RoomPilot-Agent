"""逐房問卷需求進入選件層的契約（2026-08 需求鏈斷裂修復）。

QA 2026-08-01 實測：前端送出的 ``context`` 只有 LLM 分支會讀，而該分支
從未被觸發，導致問卷勾選的衣櫃在全案 0 件。這裡鎖住三件事：需求能被
正規化、本地規則會照著選、LLM 漏掉必要家具時會被擋下。
"""

import json

import pytest

from backend.agent.select import (
    SelectionParseError,
    build_select_messages,
    local_selection_raw,
    parse_selections,
    preselected_from_requirements,
    requirements_from_context,
)


def _candidate(fid: str, kind: str, width_cm: float = 100, depth_cm: float = 50) -> dict:
    return {
        "furniture_id": fid,
        "normalized_type": kind,
        "name_zh_raw": fid,
        "size_cm": {"width": width_cm, "depth": depth_cm, "height": 80},
        "has_model": True,
    }


def _bedroom() -> list[dict]:
    return [{"room_id": "bedroom-1", "room_type": "bedroom", "width_cm": 360, "depth_cm": 300}]


def _offers() -> dict[str, list[dict]]:
    return {
        "bedroom-1": [
            _candidate("bed-1", "bed-frame", 160, 200),
            _candidate("nightstand-1", "bedside-table", 40, 40),
            _candidate("wardrobe-1", "pax-wardrobe", 150, 60),
        ]
    }


def _selection(room_id: str, *ids: object) -> dict:
    return {
        "room_id": room_id,
        "items": [value if isinstance(value, dict) else {"furniture_id": value} for value in ids],
    }


def _room_requirement(
    room_id: str = "bedroom-1",
    *,
    selected: list[dict] | None = None,
    required: list[str] | None = None,
    deferred: list[dict] | None = None,
    usage: list[str] | None = None,
    special_requests: object = None,
) -> dict:
    """模擬 scene_room_requirements.js 寫出的單房需求物件。"""
    return {
        "roomId": room_id,
        "roomLabel": "主臥",
        "usage": usage or [],
        "furniture": {
            "required": required or [],
            "optional": [],
            "selected": selected or [],
            "deferred": deferred or [],
        },
        "specialRequests": special_requests if special_requests is not None else [],
        "confirmed": True,
    }


def _context(entry: dict) -> dict:
    return {"room_requirements": {entry["roomId"]: entry}}


def test_requirements_read_both_dict_and_list_shapes() -> None:
    entry = _room_requirement(
        selected=[{"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe", "count": 2}],
        usage=["睡眠", "更衣"],
    )

    by_dict = requirements_from_context(_context(entry))
    by_list = requirements_from_context({"questionnaire": {"roomRequirements": [entry]}})

    for requirements in (by_dict, by_list):
        requirement = requirements["bedroom-1"]
        assert requirement.selected_furniture_ids == ("wardrobe-1",)
        assert requirement.counts == {"wardrobe-1": 2}
        assert requirement.required_families == ("wardrobe",)
        assert requirement.usage == ("睡眠", "更衣")


def test_requirements_tolerate_free_text_and_missing_furniture_block() -> None:
    # 隨機填答路徑會把自由文字寫進 furniture.required，不得讓選件整批失敗。
    requirements = requirements_from_context({
        "room_requirements": {
            "bedroom-1": {"roomId": "bedroom-1", "furniture": {"required": ["想要很多收納"]}},
            "living-1": {"roomId": "living-1"},
            "ghost": {"furniture": {"selected": []}},
        }
    })

    assert requirements["bedroom-1"].required_families == ("想要很多收納",)
    assert requirements["living-1"].required_families == ()
    assert "ghost" not in requirements
    assert requirements_from_context(None) == {}


def test_requirements_collect_special_requests_from_string_or_objects() -> None:
    as_text = requirements_from_context(
        _context(_room_requirement(special_requests="要放得下鋼琴"))
    )
    as_objects = requirements_from_context(
        _context(_room_requirement(
            special_requests=[{"optionId": "bathtub", "custom": "想保留浴缸"}],
        ))
    )

    assert as_text["bedroom-1"].notes == ("要放得下鋼琴",)
    assert as_objects["bedroom-1"].notes == ("想保留浴缸",)


def test_local_rules_keep_questionnaire_selection_and_count() -> None:
    requirements = requirements_from_context(_context(_room_requirement(
        selected=[
            {"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe", "count": 1},
            {"furniture_id": "nightstand-1", "normalized_type": "bedside-table", "count": 2},
        ],
    )))

    items = local_selection_raw(_bedroom(), _offers(), requirements)["selections"][0]["items"]

    # 問卷勾選排在最前面，數量沿用問卷填的值。
    assert [item["furniture_id"] for item in items[:2]] == ["wardrobe-1", "nightstand-1"]
    assert items[1]["count"] == 2
    # 床沒被勾選，仍由既有的一族一件補齊。
    assert "bed-1" in [item["furniture_id"] for item in items]


def test_local_rules_never_select_deferred_furniture() -> None:
    requirements = requirements_from_context(_context(_room_requirement(
        deferred=[{"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe"}],
    )))

    items = local_selection_raw(_bedroom(), _offers(), requirements)["selections"][0]["items"]
    ids = [item["furniture_id"] for item in items]

    assert "wardrobe-1" not in ids
    assert "bed-1" in ids


def test_local_rules_without_requirements_keep_one_item_per_family() -> None:
    items = local_selection_raw(_bedroom(), _offers())["selections"][0]["items"]

    assert [item["furniture_id"] for item in items] == ["bed-1", "nightstand-1", "wardrobe-1"]


def test_questionnaire_required_family_is_enforced_against_llm_output() -> None:
    # QA 2026-08-01 實測「全案 0 衣櫃」：使用者要了衣櫃，LLM 漏掉時必須擋下。
    requirements = requirements_from_context(
        _context(_room_requirement(required=["pax-wardrobe"]))
    )

    with pytest.raises(SelectionParseError, match="衣櫃"):
        parse_selections(
            {"selections": [_selection("bedroom-1", "bed-1")]},
            _bedroom(),
            _offers(),
            requirements=requirements,
        )

    result = parse_selections(
        {"selections": [_selection("bedroom-1", "bed-1", "wardrobe-1")]},
        _bedroom(),
        _offers(),
        requirements=requirements,
    )
    assert "wardrobe-1" in [entry.item["furniture_id"] for entry in result["bedroom-1"]]


def test_questionnaire_required_family_is_skipped_when_catalog_has_none() -> None:
    # 型錄缺貨不該讓整間房失敗，否則使用者連床都拿不到。
    # 衣櫃列入選件是因為它現在是臥室基礎必備（REQUIRED_FAMILIES_BY_ROOM）。
    requirements = requirements_from_context(
        _context(_room_requirement(required=["piano"]))
    )

    result = parse_selections(
        {"selections": [_selection("bedroom-1", "bed-1", "wardrobe-1")]},
        _bedroom(),
        _offers(),
        requirements=requirements,
    )

    assert [entry.item["furniture_id"] for entry in result["bedroom-1"]] == [
        "bed-1",
        "wardrobe-1",
    ]


def test_parse_drops_deferred_furniture_chosen_by_llm() -> None:
    requirements = requirements_from_context(_context(_room_requirement(
        deferred=[{"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe"}],
    )))

    result = parse_selections(
        {"selections": [_selection("bedroom-1", "bed-1", "wardrobe-1")]},
        _bedroom(),
        _offers(),
        requirements=requirements,
    )

    assert [entry.item["furniture_id"] for entry in result["bedroom-1"]] == ["bed-1"]


def test_preselected_from_requirements_ignores_ids_missing_from_catalog() -> None:
    requirements = requirements_from_context(_context(_room_requirement(
        selected=[
            {"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe"},
            {"furniture_id": "retired-sku", "normalized_type": "pax-wardrobe"},
        ],
    )))

    protected = preselected_from_requirements(_bedroom(), _offers(), requirements)

    assert [item["furniture_id"] for item in protected["bedroom-1"]] == ["wardrobe-1"]


def test_prompt_carries_questionnaire_requirements_to_the_llm() -> None:
    requirements = requirements_from_context(_context(_room_requirement(
        selected=[{"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe"}],
        deferred=[{"furniture_id": "nightstand-1", "normalized_type": "bedside-table"}],
        usage=["睡眠"],
        special_requests="要放得下鋼琴",
    )))

    messages = build_select_messages(
        _bedroom(), _offers(), "japandi", requirements=requirements
    )
    room = json.loads(messages[1]["content"])["rooms"][0]

    assert room["must_include_types"] == ["wardrobe"]
    assert room["user_selected_furniture_ids"] == ["wardrobe-1"]
    assert room["deferred_furniture_ids"] == ["nightstand-1"]
    assert room["special_requests"] == ["要放得下鋼琴"]
    assert room["uses"] == ["睡眠"]
    assert "must_include_types" in messages[0]["content"]
