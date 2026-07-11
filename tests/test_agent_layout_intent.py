"""Agent 3(擺放語意提示)測試 —— 全離線,注入 stub complete。

驗證重點:
- hint.anchor 讓 _placement_candidates 把靠該牆的候選排到最前(只改順序)。
- hints=None 與整合前完全一致(向後相容)。
- design_layout_intent 正確解析 LLM 回應;無 LLM / 壞回應 → 回 {}(降級)。
- 被提示靠某牆的家具,經引擎擺放後真的落在該側。
"""
from roompilot.agent.layout_intent import _opening_sides, design_layout_intent
from roompilot.server.scene_service import _placement_candidates, generate_layout


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


# ---------- _placement_candidates:hint 只改順序 ----------

def test_anchor_left_prepends_left_wall_candidate():
    cands = _placement_candidates("bookcase", 80, 40, 400, 400, hint={"anchor": "left"})
    x, z, rot = cands[0]
    assert x < 0          # 靠左牆(-room_width/2 側)
    assert rot == 90      # 背牆、面向房間


def test_anchor_bottom_prepends_bottom_wall_candidate():
    cands = _placement_candidates("sofa", 200, 90, 420, 360, hint={"anchor": "bottom"})
    x, z, rot = cands[0]
    assert z > 0          # 靠下牆(+room_depth/2 側)
    assert rot == 180


def test_no_hint_matches_legacy_behavior():
    """hint=None 的候選清單必須與不傳 hint 完全相同(向後相容鐵證)。"""
    legacy = _placement_candidates("sofa", 200, 90, 420, 360)
    with_none = _placement_candidates("sofa", 200, 90, 420, 360, hint=None)
    assert legacy == with_none


# ---------- design_layout_intent:解析 / 降級 ----------

def test_design_layout_intent_parses_stub_llm():
    def stub(messages):
        return {"hints": [{"furniture_id": "f1", "anchor": "left", "priority": 0, "note": "靠窗採光"}]}

    hints = design_layout_intent(
        {"style_id": "scandinavian", "space_type": "workspace"},
        [_item("f1", "desk", 120, 60)],
        {"width_cm": 400, "depth_cm": 400},
        {},
        complete=stub,
    )
    assert hints["f1"]["anchor"] == "left"
    assert hints["f1"]["priority"] == 0


def test_design_layout_intent_drops_invalid_anchor_and_unknown_id():
    def stub(messages):
        return {"hints": [
            {"furniture_id": "f1", "anchor": "沙發牆"},   # 非法 anchor
            {"furniture_id": "ghost", "anchor": "left"},   # 不在清單內的 id
        ]}

    hints = design_layout_intent(
        {}, [_item("f1", "desk", 120, 60)], {"width_cm": 400, "depth_cm": 400}, {}, complete=stub
    )
    assert hints == {}   # 兩筆都該被丟棄


def test_design_layout_intent_no_llm_returns_empty():
    hints = design_layout_intent(
        {}, [_item("f1", "desk", 120, 60)], {"width_cm": 400, "depth_cm": 400}, {}, complete=None
    )
    assert hints == {}


def test_design_layout_intent_bad_llm_returns_empty():
    def stub(messages):
        return None  # 模擬 LLM 未設定 / 呼叫失敗

    hints = design_layout_intent(
        {}, [_item("f1", "desk", 120, 60)], {"width_cm": 400, "depth_cm": 400}, {}, complete=stub
    )
    assert hints == {}


# ---------- 端到端:提示 → 引擎擺放落在該側 ----------

def test_hint_places_item_on_requested_wall():
    items = [_item("f1", "desk", 120, 60)]
    hints = {"f1": {"anchor": "left", "priority": 0}}
    objs = generate_layout(400, 400, items, hints=hints)
    assert objs[0]["placement_failed"] is False
    assert objs[0]["position_cm"]["x"] < 0   # 落在左半邊


def test_hints_preserve_output_order():
    """priority 只改擺放順序,回傳清單順序仍照原始 items 順序。"""
    items = [_item("a", "sofa", 200, 90), _item("b", "coffee-table", 100, 50)]
    hints = {"b": {"priority": 0}, "a": {"priority": 1}}  # b 先擺,但輸出仍 a 在前
    objs = generate_layout(420, 360, items, hints=hints)
    assert [o["furniture_id"] for o in objs] == ["a", "b"]


# ---------- 門窗牆側分類 ----------

def test_opening_sides_classifies_window_on_top_wall():
    # 房 400x400 → half = 200cm = 2m;窗中點 z ≈ -2m → 上牆
    windows = [{"start": {"x": -1.0, "z": -2.0}, "end": {"x": 1.0, "z": -2.0}}]
    assert _opening_sides(windows, 200, 200) == ["top"]


def test_opening_sides_classifies_door_on_right_wall():
    doors = [{"start": {"x": 2.0, "z": -0.5}, "end": {"x": 2.0, "z": 0.5}}]
    assert _opening_sides(doors, 200, 200) == ["right"]
