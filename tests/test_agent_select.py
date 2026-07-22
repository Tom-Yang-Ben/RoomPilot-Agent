"""LLM 選件 agent 測試 —— 全離線,注入 stub complete(自 room_pilot2 測試移植)。

驗證重點(系統邊界永不信任 LLM):
- build_select_messages:潛規則 + 空間摘要 + 候選白名單都進 prompt。
- parse_selections:未知 room/furniture 丟棄、count 夾 1..6、同族系一款
  (先到先贏,使用者精選先入座)、每房上限、潛規則過濾(房型適配 →
  成組依賴;精選豁免)、全空 raise。
- request_selections:無候選不打 LLM;complete 缺/失敗 → Unavailable。
"""
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


def _cand(fid, ftype, w=100, d=50, name=None, color="白色"):
    return {
        "furniture_id": fid,
        "normalized_type": ftype,
        "name_zh_raw": name or fid,
        "color": color,
        "size_cm": {"width": w, "depth": d, "height": 80},
        "has_model": True,
        "model_url": f"/dataset/{fid}.glb",
    }


def _rooms():
    return [
        {"room_id": "r-bed", "room_type": "bedroom", "width_cm": 360, "depth_cm": 300,
         "required_furniture_ids": []},
        {"room_id": "r-liv", "room_type": "living_room", "width_cm": 480, "depth_cm": 400,
         "required_furniture_ids": []},
    ]


def _offers():
    return {
        "r-bed": [
            _cand("bed-1", "bed-frame", 160, 200),
            _cand("ns-1", "bedside-table", 40, 40),
            _cand("ward-1", "pax-wardrobe", 150, 60),
        ],
        "r-liv": [
            _cand("sofa-1", "fabric-sofa", 220, 90),
            _cand("sofa-2", "leather-sofa", 180, 85),
            _cand("ct-1", "coffee-table", 110, 60),
            _cand("tv-1", "tv-bench", 160, 40),
            _cand("book-1", "bookcase", 80, 30),
        ],
    }


def _sel(room_id, *entries):
    return {"room_id": room_id, "items": [
        e if isinstance(e, dict) else {"furniture_id": e} for e in entries
    ]}


# ---------- build_select_messages ----------

def test_messages_include_rules_rooms_and_candidates():
    messages = build_select_messages(_rooms(), _offers(), "scandinavian")
    system = messages[0]["content"]
    assert "擺放潛規則" in system          # knowledge.prompt_rules 注入
    assert "床頭櫃" in system and "沙發" in system
    payload = json.loads(messages[1]["content"])
    assert payload["style_id"] == "scandinavian"
    room_ids = {room["room_id"] for room in payload["rooms"]}
    assert room_ids == {"r-bed", "r-liv"}
    liv = next(room for room in payload["rooms"] if room["room_id"] == "r-liv")
    assert {c["furniture_id"] for c in liv["candidates"]} >= {"sofa-1", "ct-1"}
    assert liv["room_type_zh"] == "客廳"
    assert "output_shape" in payload


def test_messages_carry_caller_context():
    messages = build_select_messages(
        _rooms(), _offers(), "japandi",
        context={"occupants": 2, "constraints": [{"type": "avoid", "value": "深色"}], "empty": []},
    )
    payload = json.loads(messages[1]["content"])
    assert payload["occupants"] == 2
    assert payload["constraints"][0]["value"] == "深色"
    assert "empty" not in payload          # 空值不佔 prompt


# ---------- parse_selections:白名單與夾限 ----------

def test_parse_drops_unknown_room_and_unknown_furniture():
    raw = {"selections": [
        _sel("ghost-room", "sofa-1"),
        _sel("r-liv", "sofa-1", "invented-id"),
        {"room_id": ["not", "hashable"], "items": []},
    ]}
    result = parse_selections(raw, _rooms(), _offers())
    assert set(result) == {"r-liv"}
    assert [s.item["furniture_id"] for s in result["r-liv"]] == ["sofa-1"]


def test_parse_clamps_count_to_1_6():
    raw = {"selections": [_sel(
        "r-liv",
        {"furniture_id": "sofa-1", "count": 0},
        {"furniture_id": "book-1", "count": 99},
        {"furniture_id": "ct-1", "count": "四"},
    )]}
    result = parse_selections(raw, _rooms(), _offers())
    by_id = {s.item["furniture_id"]: s.count for s in result["r-liv"]}
    assert by_id == {"sofa-1": 1, "book-1": 6, "ct-1": 1}


def test_parse_one_model_per_family_first_wins():
    raw = {"selections": [_sel("r-liv", "sofa-1", "sofa-2", "book-1")]}
    result = parse_selections(raw, _rooms(), _offers())
    ids = [s.item["furniture_id"] for s in result["r-liv"]]
    assert "sofa-1" in ids and "sofa-2" not in ids   # fabric/leather 同 sofa 族系


def test_parse_caps_items_per_room():
    offers = {"r-liv": [_cand(f"g-{i}", f"generic-type-{i}") for i in range(12)]}
    raw = {"selections": [_sel("r-liv", *[f"g-{i}" for i in range(12)])]}
    result = parse_selections(raw, _rooms(), offers)
    assert len(result["r-liv"]) == MAX_ITEMS_PER_ROOM


# ---------- parse_selections:潛規則 ----------

def test_parse_drops_bed_in_living_room():
    offers = {"r-liv": [*_offers()["r-liv"], _cand("bed-x", "bed-frame", 160, 200)]}
    raw = {"selections": [_sel("r-liv", "sofa-1", "bed-x")]}
    result = parse_selections(raw, _rooms(), offers)
    ids = [s.item["furniture_id"] for s in result["r-liv"]]
    assert "bed-x" not in ids and "sofa-1" in ids


def test_parse_drops_companion_without_anchor():
    raw = {"selections": [_sel("r-liv", "ct-1", "tv-1", "book-1")]}   # 沒選沙發
    result = parse_selections(raw, _rooms(), _offers())
    ids = [s.item["furniture_id"] for s in result["r-liv"]]
    assert ids == ["book-1"]               # 茶几/電視櫃缺主件 → 潛規則丟棄


def test_parse_keeps_companion_with_anchor():
    raw = {"selections": [_sel("r-liv", "sofa-1", "ct-1", "tv-1")]}
    result = parse_selections(raw, _rooms(), _offers())
    ids = {s.item["furniture_id"] for s in result["r-liv"]}
    assert ids == {"sofa-1", "ct-1", "tv-1"}


def test_parse_preselected_seed_family_and_bypass_conventions():
    """使用者精選:先佔族系名額(LLM 同族讓位),且不受潛規則否決。"""
    offers = _offers()
    user_sofa = _cand("user-sofa", "sofa-bed", 190, 88)
    offers["r-bed"] = [*offers["r-bed"], user_sofa]
    raw = {"selections": [_sel("r-bed", "bed-1", "ns-1")]}
    result = parse_selections(
        raw, _rooms(), offers, preselected={"r-bed": [user_sofa]}
    )
    ids = [s.item["furniture_id"] for s in result["r-bed"]]
    # 沙發不適合臥室(房型適配),但使用者精選是產品承諾 → 保留
    assert ids[0] == "user-sofa"
    assert "bed-1" in ids and "ns-1" in ids


def test_parse_all_invalid_raises():
    raw = {"selections": [_sel("r-liv", "invented-1", "invented-2")]}
    with pytest.raises(SelectionParseError):
        parse_selections(raw, _rooms(), _offers())
    with pytest.raises(SelectionParseError):
        parse_selections({"no_selections": True}, _rooms(), _offers())


# ---------- request_selections ----------

def test_request_without_candidates_skips_llm():
    calls = []

    def complete(messages):
        calls.append(messages)
        return ("model", {"selections": []})

    result, model = request_selections(_rooms(), {}, "japandi", complete=complete)
    assert result == {} and model is None
    assert calls == []                     # 沒候選不打 LLM


def test_request_without_complete_raises_unavailable():
    with pytest.raises(SelectionUnavailableError):
        request_selections(_rooms(), _offers(), "japandi", complete=None)


def test_request_complete_failure_raises_unavailable():
    with pytest.raises(SelectionUnavailableError):
        request_selections(_rooms(), _offers(), "japandi", complete=lambda m: None)


def test_request_happy_path_returns_validated_selections_and_model():
    def complete(messages):
        return ("mock/select", {"selections": [
            _sel("r-bed", {"furniture_id": "bed-1"}, {"furniture_id": "ns-1", "count": 2}),
            _sel("r-liv", "sofa-1", "ct-1", "invented-id"),
        ]})

    result, model = request_selections(_rooms(), _offers(), "japandi", complete=complete)
    assert model == "mock/select"
    assert [s.count for s in result["r-bed"] if s.item["furniture_id"] == "ns-1"] == [2]
    assert {s.item["furniture_id"] for s in result["r-liv"]} == {"sofa-1", "ct-1"}
