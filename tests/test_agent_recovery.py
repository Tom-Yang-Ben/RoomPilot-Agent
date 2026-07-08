"""Agent 4(擺放失敗修復)測試 —— 全離線,注入 place_fn 與(可選)stub complete。

驗證重點:
- pick_smaller_model 確定性挑最小同型可用款。
- 放不下 → 有更小款則換款(replace)、無更小款則移除(remove,附繁中訊息)。
- 卡住偵測 / max_iter:即使全放不下也在上限內收斂,不無限迴圈。
- complete=None(降級)仍能修復;stub LLM 指令會被採用。
"""
from roompilot.agent.recovery import pick_smaller_model, run_recovery
from roompilot.server.scene_service import generate_layout


def _item(fid, ftype, w, d, h=80):
    return {
        "furniture_id": fid,
        "normalized_type": ftype,
        "name_zh_raw": fid,
        "size_cm": {"width": w, "depth": d, "height": h},
        "has_model": True,
        "model_url": None,
        "primary_style": None,
    }


def _place(width_cm, depth_cm):
    def place(items):
        return generate_layout(width_cm, depth_cm, items)

    return place


# ---------- pick_smaller_model ----------

def test_pick_smaller_returns_smallest_under_cap():
    pool = [_item("big", "sofa", 300, 120), _item("mid", "sofa", 200, 90), _item("small", "sofa", 140, 80)]
    picked = pick_smaller_model(pool, "sofa", footprint_cap=300 * 120, exclude_ids={"big"})
    assert picked["furniture_id"] == "small"   # 最小的一款


def test_pick_smaller_returns_none_when_nothing_smaller():
    pool = [_item("big", "sofa", 300, 120)]
    assert pick_smaller_model(pool, "sofa", footprint_cap=300 * 120, exclude_ids={"big"}) is None


def test_pick_smaller_ignores_other_types_and_no_model():
    pool = [
        _item("chair", "armchair", 60, 60),          # 別的類型
        {**_item("nomodel", "sofa", 100, 60), "has_model": False},  # 無 3D 模型
        _item("ok", "sofa", 120, 70),
    ]
    picked = pick_smaller_model(pool, "sofa", footprint_cap=200 * 90, exclude_ids=set())
    assert picked["furniture_id"] == "ok"


# ---------- run_recovery ----------

def test_recovery_replaces_oversized_with_smaller():
    big = _item("big", "sofa", 500, 200)
    small = _item("small", "sofa", 120, 70)
    objs = generate_layout(300, 300, [big])
    assert objs[0]["placement_failed"] is True

    objs2, final, report = run_recovery(
        objs, [big], {"space_type": "living_room"}, [big, small], place_fn=_place(300, 300), complete=None
    )
    assert any(r["action"] == "replace" for r in report)
    assert all(not o["placement_failed"] for o in objs2)
    assert final[0]["furniture_id"] == "small"


def test_recovery_removes_when_no_smaller():
    big = _item("big", "sofa", 500, 200)
    objs = generate_layout(300, 300, [big])
    assert objs[0]["placement_failed"] is True

    objs2, final, report = run_recovery(
        objs, [big], {"space_type": "living_room"}, [big], place_fn=_place(300, 300), complete=None
    )
    assert any(r["action"] == "remove" for r in report)
    assert final == []
    assert report[-1]["message_zh"]   # 有繁中訊息給使用者


def test_recovery_converges_within_max_iter():
    items = [_item(f"big{i}", "sofa", 500, 200) for i in range(3)]
    objs = generate_layout(300, 300, items)
    objs2, final, report = run_recovery(
        objs, items, {"space_type": "living_room"}, list(items), place_fn=_place(300, 300), complete=None, max_iter=3
    )
    # 全放不下、無更小款 → 應全部移除且不殘留失敗(收斂,不無限迴圈)
    assert all(not o["placement_failed"] for o in objs2)
    assert final == []


def test_recovery_no_failures_is_noop():
    small = _item("small", "sofa", 120, 70)
    objs = generate_layout(420, 360, [small])
    assert objs[0]["placement_failed"] is False

    objs2, final, report = run_recovery(
        objs, [small], {"space_type": "living_room"}, [small], place_fn=_place(420, 360), complete=None
    )
    assert report == []
    assert [f["furniture_id"] for f in final] == ["small"]


def test_recovery_uses_llm_instruction():
    """有 LLM 時採用其指令:這裡 stub 叫 remove,即使池中有更小款也照 remove。"""
    big = _item("big", "sofa", 500, 200)
    small = _item("small", "sofa", 120, 70)

    def stub(messages):
        return {"instructions": [{"furniture_id": "big", "action": "remove", "reason_zh": "客廳偏小,先不放沙發。"}]}

    objs = generate_layout(300, 300, [big])
    objs2, final, report = run_recovery(
        objs, [big], {"space_type": "living_room"}, [big, small], place_fn=_place(300, 300), complete=stub
    )
    assert report[0]["action"] == "remove"
    assert report[0]["message_zh"] == "客廳偏小,先不放沙發。"
    assert final == []
