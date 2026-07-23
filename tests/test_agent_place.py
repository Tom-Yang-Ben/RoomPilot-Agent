"""Agent 擺位策略測試：座標永遠由 backend.engine 計算。"""

from backend.agent.place import pick_smaller_model, placement_hints, resolve_placements
from backend.engine.models import FurnitureCatalogItem, Room
from backend.engine.placement import place_furniture_batch


def _item(fid: str, kind: str, width_cm: float, depth_cm: float, **extra) -> dict:
    return {
        "furniture_id": fid,
        "normalized_type": kind,
        "name_zh_raw": fid,
        "size_cm": {"width": width_cm, "depth": depth_cm, "height": 80},
        "has_model": True,
        **extra,
    }


def _failed_object(item: dict) -> dict:
    return {
        "instance_id": item.get("instance_id"),
        "furniture_id": item["furniture_id"],
        "normalized_type": item["normalized_type"],
        "placement_failed": True,
    }


def _threshold_engine(max_width_cm: float):
    """測試替身只模擬 engine 回報；它不是 Agent 內部協作者。"""
    def place(items: list[dict]) -> list[dict]:
        return [
            {
                "instance_id": item.get("instance_id"),
                "furniture_id": item["furniture_id"],
                "normalized_type": item["normalized_type"],
                "placement_failed": item["size_cm"]["width"] > max_width_cm,
            }
            for item in items
        ]

    return place


def test_hints_order_anchor_generic_companion_without_coordinates() -> None:
    bed = _item("bed", "bed-frame", 160, 200)
    wardrobe = _item("wardrobe", "pax-wardrobe", 150, 60)
    nightstand = _item("nightstand", "bedside-table", 40, 40)
    hints = placement_hints([nightstand, wardrobe, bed])
    assert hints["bed"]["priority"] < hints["wardrobe"]["priority"] < hints["nightstand"]["priority"]
    assert hints["bed"]["group"] == hints["nightstand"]["group"] == "sleeping"
    forbidden = {"x", "y", "z", "position", "position_cm", "rotation"}
    assert all(not forbidden.intersection(hint) for hint in hints.values())


def test_hints_prefer_instance_id_and_are_deterministic() -> None:
    items = [
        _item("sofa", "fabric-sofa", 200, 90, instance_id="living-sofa-1"),
        _item("coffee", "coffee-table", 100, 50, instance_id="living-coffee-1"),
    ]
    assert "living-sofa-1" in placement_hints(items)
    assert placement_hints(items) == placement_hints(list(reversed(items)))


def test_pick_smaller_prefers_smallest_same_type_then_family() -> None:
    pool = [
        _item("large", "fabric-sofa", 300, 120),
        _item("medium", "fabric-sofa", 200, 90),
        _item("small", "fabric-sofa", 140, 80),
        _item("leather", "leather-sofa", 120, 70),
    ]
    picked = pick_smaller_model(pool, "fabric-sofa", 300 * 120, {"large"})
    assert picked and picked["furniture_id"] == "small"
    family_only = pick_smaller_model([pool[-1]], "fabric-sofa", 300 * 120, set())
    assert family_only and family_only["furniture_id"] == "leather"


def test_resolve_replaces_oversized_anchor_with_smaller_model() -> None:
    large = _item("large", "fabric-sofa", 500, 200, instance_id="sofa-1", color="舊色")
    small = _item("small", "fabric-sofa", 120, 70, color="新色")
    objects, final, report = resolve_placements(
        [_failed_object(large)],
        [large],
        [large, small],
        engine_place_fn=_threshold_engine(300),
    )
    assert all(not obj["placement_failed"] for obj in objects)
    assert [item["furniture_id"] for item in final] == ["small"]
    assert final[0]["instance_id"] == "sofa-1"
    assert final[0]["color"] == "新色"
    assert report[0]["action"] == "replace"
    assert report[0]["message_zh"]


def test_resolve_removes_item_when_no_smaller_model_exists() -> None:
    large = _item("large", "fabric-sofa", 500, 200)
    objects, final, report = resolve_placements(
        [_failed_object(large)], [large], [large], engine_place_fn=_threshold_engine(300)
    )
    assert objects == [] and final == []
    assert report[0]["action"] == "remove"


def test_resolve_never_replaces_failed_companion_without_its_anchor() -> None:
    sofa = _item("sofa", "fabric-sofa", 200, 90)
    large_table = _item("large-table", "coffee-table", 600, 300)
    small_table = _item("small-table", "coffee-table", 90, 50)
    objects, final, report = resolve_placements(
        [
            {**_failed_object(sofa), "placement_failed": False},
            _failed_object(large_table),
        ],
        [sofa, large_table],
        [sofa, large_table, small_table],
        engine_place_fn=_threshold_engine(300),
    )
    assert [item["furniture_id"] for item in final] == ["sofa"]
    assert next(row["action"] for row in report if row["furniture_id"] == "large-table") == "remove"


def test_resolve_removes_agent_companion_when_anchor_is_absent() -> None:
    nightstand = _item(
        "nightstand", "bedside-table", 40, 40, selection_source="local_rules"
    )
    objects, final, report = resolve_placements(
        [{**_failed_object(nightstand), "placement_failed": False}],
        [nightstand],
        [nightstand],
        engine_place_fn=_threshold_engine(300),
    )
    assert objects == [] and final == []
    assert report[0]["action"] == "remove"
    assert "床" in report[0]["message_zh"]


def test_resolve_preserves_user_or_legacy_companion_without_anchor() -> None:
    nightstand = _item("nightstand", "bedside-table", 40, 40)
    objects, final, report = resolve_placements(
        [{**_failed_object(nightstand), "placement_failed": False}],
        [nightstand],
        [nightstand],
        engine_place_fn=_threshold_engine(300),
    )
    assert objects and final == [nightstand] and report == []


def test_protected_furniture_is_reported_but_never_replaced_or_removed() -> None:
    large = _item("large", "fabric-sofa", 500, 200)
    small = _item("small", "fabric-sofa", 120, 70)
    _objects, final, report = resolve_placements(
        [_failed_object(large)],
        [large],
        [large, small],
        engine_place_fn=_threshold_engine(300),
        protected_ids={"large"},
    )
    assert [item["furniture_id"] for item in final] == ["large"]
    assert [row["action"] for row in report] == ["escalate"]
    assert "使用者指定" in report[0]["message_zh"]


def test_actual_roompilot_engine_receives_centimeters_and_owns_coordinates() -> None:
    """整合回歸：Agent 與引擎都使用公分，且 Agent 未計算任何座標。"""
    room = Room(width=400, depth=400)
    item = _item("bed", "bed-frame", 160, 200)
    size = item["size_cm"]
    catalog = FurnitureCatalogItem(
        type="bed",
        name="床",
        width=size["width"],
        depth=size["depth"],
        height=size["height"],
    )
    result = place_furniture_batch(room, [(catalog, "bed-1")])
    assert result["failed"] == []
    placed = result["placed"][0]
    assert 0 <= placed.pos_x <= room.width
    assert 0 <= placed.pos_y <= room.depth


def test_resolve_reflows_through_actual_centimeter_engine_adapter() -> None:
    room = Room(width=400, depth=400)
    large = _item("large", "fabric-sofa", 500, 200, instance_id="sofa-1")
    small = _item("small", "fabric-sofa", 120, 70)

    def engine_adapter(items: list[dict]) -> list[dict]:
        batches = []
        for item in items:
            size = item["size_cm"]
            batches.append((FurnitureCatalogItem(
                type=item["normalized_type"],
                name=item["name_zh_raw"],
                width=size["width"],
                depth=size["depth"],
                height=size["height"],
            ), item["instance_id"]))
        result = place_furniture_batch(room, batches)
        failed_ids = {failure["id"] for failure in result["failed"]}
        placed_by_id = {placed.id: placed for placed in result["placed"]}
        return [
            {
                "instance_id": item["instance_id"],
                "furniture_id": item["furniture_id"],
                "normalized_type": item["normalized_type"],
                "placement_failed": item["instance_id"] in failed_ids,
                "position_cm": (
                    {
                        "x": placed_by_id[item["instance_id"]].pos_x,
                        "y": placed_by_id[item["instance_id"]].pos_y,
                    }
                    if item["instance_id"] in placed_by_id
                    else None
                ),
            }
            for item in items
        ]

    objects, final, report = resolve_placements(
        [_failed_object(large)],
        [large],
        [large, small],
        engine_place_fn=engine_adapter,
    )
    assert final[0]["furniture_id"] == "small"
    assert report[0]["action"] == "replace"
    assert objects[0]["placement_failed"] is False
    assert objects[0]["position_cm"] is not None
