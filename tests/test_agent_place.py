"""擺位紀律測試 —— 全離線,引擎即 place_fn(自 room_pilot2 測試移植)。

驗證重點:
- placement_hints:主件先、泛用次、副件最後的確定性優先序;成組標籤。
- pick_smaller_model:確定性挑最小同型(同型缺貨放寬到同族系)。
- resolve_placements:換小 / 移除 / 寧缺勿亂(副件不獨活)/ 使用者指定只
  升級回報 / 收斂不空轉;座標一律由 place_fn(引擎)算。
- 引擎成組回歸:床頭櫃經提示順序後真的貼在床兩側;hints 只改試放順序。
"""
from backend.agent.place import (
    pick_smaller_model,
    placement_hints,
    resolve_placements,
)
from backend.server.scene_service import _placement_candidates, generate_layout


def _item(fid, ftype, w, d, h=80, **extra):
    return {
        "furniture_id": fid,
        "normalized_type": ftype,
        "name_zh_raw": fid,
        "size_cm": {"width": w, "depth": d, "height": h},
        "has_model": True,
        "model_url": None,
        "primary_style": None,
        **extra,
    }


def _place(width_cm, depth_cm):
    def place(items):
        return generate_layout(width_cm, depth_cm, items, hints=placement_hints(items))

    return place


# ---------- placement_hints ----------

def test_hints_order_anchor_generic_companion():
    bed = _item("bed", "bed-frame", 160, 200)
    wardrobe = _item("ward", "pax-wardrobe", 150, 60)
    nightstand = _item("ns", "bedside-table", 40, 40)
    hints = placement_hints([nightstand, wardrobe, bed])
    assert hints["bed"]["priority"] < hints["ward"]["priority"] < hints["ns"]["priority"]


def test_hints_prefer_instance_id_and_carry_group():
    sofa = _item("sofa", "fabric-sofa", 200, 90, instance_id="liv-1-sofa")
    book = _item("book", "bookcase", 80, 30)
    hints = placement_hints([sofa, book])
    assert "liv-1-sofa" in hints and hints["liv-1-sofa"]["group"] == "seating"
    assert "group" not in hints["book"]    # 泛用件無成組標籤


def test_hints_place_essentials_before_generic_items():
    """基礎家具(含衣櫃)先卡位,其他物件依它們的位置再配置:
    衣櫃雖非成組主件,量體大、靠牆需求強,必須排在泛用件(書櫃)之前。"""
    wardrobe = _item("ward", "pax-wardrobe", 150, 60)
    bookcase = _item("book", "bookcase", 200, 45)     # 面積更大的泛用件
    hints = placement_hints([bookcase, wardrobe])
    assert hints["ward"]["priority"] < hints["book"]["priority"]


def test_hints_are_deterministic():
    items = [_item("a", "fabric-sofa", 200, 90), _item("b", "coffee-table", 100, 50)]
    assert placement_hints(items) == placement_hints(list(reversed(items)))


def test_hints_place_free_seating_after_companions():
    """自由座椅(躺椅/單人椅)最後擺:先擺會以房間中央泛用候選搶走
    沙發正前方,茶几/電視櫃的成組位就沒了(feedback.png 躺椅擋沙發前)。"""
    sofa = _item("sofa", "fabric-sofa", 200, 90)
    lounge = _item("lounge", "lounge-chair", 90, 80)
    coffee = _item("ct", "coffee-table", 100, 50)
    tv = _item("tv", "tv-bench", 120, 40)
    hints = placement_hints([lounge, tv, coffee, sofa])
    assert hints["sofa"]["priority"] < hints["ct"]["priority"]
    assert hints["ct"]["priority"] < hints["lounge"]["priority"]
    assert hints["tv"]["priority"] < hints["lounge"]["priority"]


# ---------- pick_smaller_model ----------

def test_pick_smaller_returns_smallest_under_cap():
    pool = [_item("big", "sofa", 300, 120), _item("mid", "sofa", 200, 90), _item("small", "sofa", 140, 80)]
    picked = pick_smaller_model(pool, "sofa", footprint_cap=300 * 120, exclude_ids={"big"})
    assert picked["furniture_id"] == "small"


def test_pick_smaller_returns_none_when_nothing_smaller():
    pool = [_item("big", "sofa", 300, 120)]
    assert pick_smaller_model(pool, "sofa", footprint_cap=300 * 120, exclude_ids={"big"}) is None


def test_pick_smaller_ignores_other_types_and_no_model():
    pool = [
        _item("chair", "armchair", 60, 60),
        {**_item("nomodel", "sofa", 100, 60), "has_model": False},
        _item("ok", "sofa", 120, 70),
    ]
    picked = pick_smaller_model(pool, "sofa", footprint_cap=200 * 90, exclude_ids=set())
    assert picked["furniture_id"] == "ok"


def test_pick_smaller_falls_back_to_same_family():
    """同 normalized_type 缺貨時放寬到同族系(fabric-sofa ↔ leather-sofa)。"""
    pool = [_item("leather", "leather-sofa", 150, 80)]
    picked = pick_smaller_model(pool, "fabric-sofa", footprint_cap=220 * 90, exclude_ids=set())
    assert picked["furniture_id"] == "leather"


# ---------- resolve_placements:換小 / 移除 / 收斂 ----------

def test_resolve_replaces_oversized_with_smaller():
    big = _item("big", "sofa", 500, 200)
    small = _item("small", "sofa", 120, 70)
    objs = generate_layout(300, 300, [big])
    assert objs[0]["placement_failed"] is True

    objs2, final, report = resolve_placements(
        objs, [big], [big, small], place_fn=_place(300, 300)
    )
    assert any(r["action"] == "replace" for r in report)
    assert all(not o["placement_failed"] for o in objs2)
    assert final[0]["furniture_id"] == "small"


def test_resolve_removes_when_no_smaller():
    # 泛用件(書櫃)才可移除;基礎家具(床/沙發/餐桌)只升級,另有測試
    big = _item("big", "bookcase", 500, 200)
    objs = generate_layout(300, 300, [big])
    objs2, final, report = resolve_placements(objs, [big], [big], place_fn=_place(300, 300))
    assert any(r["action"] == "remove" for r in report)
    assert final == []
    assert report[-1]["message_zh"]        # 有繁中訊息給使用者


def test_resolve_converges_within_max_rounds():
    items = [_item(f"big{i}", "bookcase", 500, 200) for i in range(3)]
    objs = generate_layout(300, 300, items)
    objs2, final, report = resolve_placements(
        objs, items, list(items), place_fn=_place(300, 300), max_rounds=3
    )
    assert all(not o["placement_failed"] for o in objs2)
    assert final == []


def test_resolve_no_failures_is_noop():
    small = _item("small", "sofa", 120, 70)
    objs = generate_layout(420, 360, [small])
    assert objs[0]["placement_failed"] is False
    objs2, final, report = resolve_placements(objs, [small], [small], place_fn=_place(420, 360))
    assert report == []
    assert [f["furniture_id"] for f in final] == ["small"]


def test_resolve_escalates_protected_user_furniture():
    big = _item("big", "sofa", 500, 200)
    small = _item("small", "sofa", 120, 70)
    objs = generate_layout(300, 300, [big])
    objs2, final, report = resolve_placements(
        objs, [big], [big, small], place_fn=_place(300, 300), protected_ids={"big"}
    )
    assert [r["action"] for r in report] == ["escalate"]   # 只回報一次,不換不移
    assert [f["furniture_id"] for f in final] == ["big"]
    assert "使用者指定" in report[0]["message_zh"]


# ---------- resolve_placements:寧缺勿亂(副件紀律) ----------

def test_resolve_removes_failed_companion_instead_of_replacing():
    sofa = _item("sofa", "fabric-sofa", 200, 90)
    huge_ct = _item("huge-ct", "coffee-table", 600, 300)
    small_ct = _item("small-ct", "coffee-table", 90, 50)
    objs = generate_layout(420, 360, [sofa, huge_ct], hints=placement_hints([sofa, huge_ct]))
    assert any(o["placement_failed"] for o in objs if o["furniture_id"] == "huge-ct")

    objs2, final, report = resolve_placements(
        objs, [sofa, huge_ct], [sofa, huge_ct, small_ct], place_fn=_place(420, 360)
    )
    ct_actions = [r["action"] for r in report if r["furniture_id"] == "huge-ct"]
    assert ct_actions == ["remove"]        # 副件放不下:直接退場,不換小獨活
    assert [f["furniture_id"] for f in final] == ["sofa"]


def test_resolve_removes_agent_selected_companion_without_anchor():
    ns = _item("ns", "bedside-table", 40, 40, selection_source="local_rules")
    objs = generate_layout(400, 400, [ns])
    assert objs[0]["placement_failed"] is False   # 引擎本身放得下
    objs2, final, report = resolve_placements(objs, [ns], [ns], place_fn=_place(400, 400))
    assert final == []                     # 主件(床)不在 → 寧缺勿亂
    assert report[0]["action"] == "remove"
    assert "床" in report[0]["message_zh"]


def test_resolve_keeps_unlabeled_companion_without_anchor():
    """未標記選件來源(legacy 場景頁)不套用主件清掃,避免動使用者的東西。"""
    ns = _item("ns", "bedside-table", 40, 40)
    objs = generate_layout(400, 400, [ns])
    objs2, final, report = resolve_placements(objs, [ns], [ns], place_fn=_place(400, 400))
    assert [f["furniture_id"] for f in final] == ["ns"]
    assert report == []


# ---------- resolve_placements:預設無上限,修到收斂 ----------

def test_resolve_default_unbounded_resolves_cascading_failures():
    """連鎖位移:每輪修完一件又擠出下一件。舊預設 max_rounds=3 會提前退出,
    留下 placement_failed 件;預設無上限必須修到全數收斂(或無可動)。"""
    items = [_item(f"i{n}", "bookcase", 200, 90) for n in range(6)]

    def cascading_place(working):
        # 模擬引擎:多於一件時,第一件永遠被其他件擠到放不下
        return [
            {
                "furniture_id": candidate["furniture_id"],
                "normalized_type": "bookcase",
                "placement_failed": index == 0 and len(working) > 1,
            }
            for index, candidate in enumerate(working)
        ]

    objs = cascading_place(items)
    objs2, final, report = resolve_placements(objs, items, [], place_fn=cascading_place)
    assert [f["furniture_id"] for f in final] == ["i5"]
    assert all(not o["placement_failed"] for o in objs2)
    assert [r["action"] for r in report] == ["remove"] * 5


def test_resolve_replacement_carries_catalog_traceability():
    """換小後 catalog_furniture_id 必須跟著換:前端 2D 對帳與 GLB 追溯都認它,
    掛舊型錄 id 會讓新件對不回資料庫。"""
    big = _item("big", "sofa", 500, 200)
    small = _item("small", "sofa", 120, 70)
    objs = generate_layout(300, 300, [big])
    _, final, _ = resolve_placements(objs, [big], [big, small], place_fn=_place(300, 300))
    assert final[0]["furniture_id"] == "small"
    assert final[0]["catalog_furniture_id"] == "small"


def test_pick_smaller_skips_outdoor_models():
    """換小替補不得引入戶外家具(型錄把庭院躺椅歸在室內類型)。"""
    outdoor = {
        **_item("patio", "sofa", 120, 70),
        "name_zh_raw": "全天候戶外露臺沙發",
        "name_en": "All-weather outdoor patio sofa",
    }
    indoor = _item("indoor", "sofa", 150, 80)
    picked = pick_smaller_model([outdoor, indoor], "sofa", footprint_cap=200 * 90, exclude_ids=set())
    assert picked["furniture_id"] == "indoor"
    assert pick_smaller_model([outdoor], "sofa", footprint_cap=200 * 90, exclude_ids=set()) is None


# ---------- 引擎成組回歸:提示順序 → 床頭櫃貼床 ----------

def test_nightstand_pair_lands_beside_bed():
    bed = _item("bed", "bed-frame", 160, 200, instance_id="bed-1")
    ns1 = _item("ns", "bedside-table", 40, 40, instance_id="ns-1")
    ns2 = _item("ns", "bedside-table", 40, 40, instance_id="ns-2")
    items = [bed, ns1, ns2]
    objs = generate_layout(400, 400, items, hints=placement_hints(items))
    by_id = {o["instance_id"]: o for o in objs}
    assert all(not o["placement_failed"] for o in objs)
    bed_x = by_id["bed-1"]["position_cm"]["x"]
    xs = [by_id["ns-1"]["position_cm"]["x"], by_id["ns-2"]["position_cm"]["x"]]
    # 兩個床頭櫃分居床兩側,且緊貼床緣(距床中心 ≤ 床寬/2 + 櫃寬 + 餘裕)
    assert (xs[0] - bed_x) * (xs[1] - bed_x) < 0
    assert all(abs(x - bed_x) <= 160 / 2 + 40 + 15 for x in xs)


# ---------- 引擎嚴格成組:副件不再退到泛用候選亂放 ----------

def test_engine_marks_companion_failed_without_anchor_under_hints():
    """hints 啟用時副件只准貼主件:主件不在 → 引擎層直接標失敗(交修復移除),
    不再退到泛用候選「成功」落在遠牆(床頭櫃流落遠牆的根因)。"""
    ns = _item("ns", "bedside-table", 40, 40)
    objs = generate_layout(400, 400, [ns], hints=placement_hints([ns]))
    assert objs[0]["placement_failed"] is True
    assert "床" in objs[0]["placement_reason"]


def test_dining_chairs_pair_around_dining_table():
    table = _item("table", "dining-table", 160, 90, instance_id="t-1")
    chairs = [
        _item("chair", "dining-chair", 45, 50, instance_id=f"c-{i}") for i in range(4)
    ]
    items = [table, *chairs]
    objs = generate_layout(400, 360, items, hints=placement_hints(items))
    by_id = {o["instance_id"]: o for o in objs}
    assert all(not o["placement_failed"] for o in objs)
    tx = by_id["t-1"]["position_cm"]["x"]
    tz = by_id["t-1"]["position_cm"]["z"]
    sides = set()
    for i in range(4):
        chair = by_id[f"c-{i}"]
        dx = chair["position_cm"]["x"] - tx
        dz = chair["position_cm"]["z"] - tz
        assert abs(dx) <= 160 / 2 and abs(dz) <= 90 / 2 + 50 + 10, f"c-{i} 未貼桌"
        sides.add(dz > 0)
    assert sides == {True, False}          # 兩長邊都有椅子


def test_corridor_keeps_free_seating_out_of_sofa_tv_axis():
    """沙發→電視櫃的視聽走廊只留給茶几/地毯;躺椅/泛用件不得卡在中間,
    但側邊有位就要放得下(不是整件消失)。"""
    sofa = _item("sofa", "sofa", 200, 90)
    tv = _item("tv", "tv-bench", 120, 40)
    lounge = _item("lounge", "lounge-chair", 90, 80)
    items = [sofa, tv, lounge]
    objs = generate_layout(450, 380, items, hints=placement_hints(items))
    by_id = {o["furniture_id"]: o for o in objs}
    assert all(not o["placement_failed"] for o in objs)
    sofa_x = by_id["sofa"]["position_cm"]["x"]
    band_left, band_right = sofa_x - 100, sofa_x + 100   # 走廊寬 = 沙發寬
    lx = by_id["lounge"]["position_cm"]["x"]
    lw = by_id["lounge"]["footprint_cm"]["width"]
    assert lx + lw / 2 <= band_left + 3 or lx - lw / 2 >= band_right - 3, (
        f"躺椅 x={lx} 侵入沙發-電視軸線 [{band_left}, {band_right}]"
    )


def test_free_seating_pairs_beside_sofa_front():
    """客廳休閒椅只准沙發左前/右前(對談 L 型):貼著沙發側緣、位於
    沙發前緣一帶、面向座位區中線;不再散落牆邊或卡進視聽走廊。"""
    sofa = _item("sofa", "sofa", 200, 90)
    tv = _item("tv", "tv-bench", 120, 40)
    ct = _item("ct", "coffee-table", 100, 50)
    arm = _item("arm", "armchair", 80, 75)
    items = [sofa, tv, ct, arm]
    objs = generate_layout(450, 380, items, hints=placement_hints(items))
    by_id = {o["furniture_id"]: o for o in objs}
    assert all(not o["placement_failed"] for o in objs)
    sofa_obj, arm_obj = by_id["sofa"], by_id["arm"]
    dx = arm_obj["position_cm"]["x"] - sofa_obj["position_cm"]["x"]
    dz = arm_obj["position_cm"]["z"] - sofa_obj["position_cm"]["z"]
    # 側向:貼著沙發左或右緣(沙發半寬 100 + 椅半徑 + 12 間距,±5 容差)
    assert 130 <= abs(dx) <= 165, f"椅不在沙發側前,dx={dx}"
    # 縱向(沙發面向 -z):位於沙發中心之前、不超過前緣 + 40 滑位
    assert -90 <= dz <= -30, f"椅不在沙發前緣帶,dz={dz}"
    # 面向座位區中線(左側面向 +x = 90,右側面向 -x = 270)
    expected_rot = 90.0 if dx < 0 else 270.0
    assert arm_obj["rotation_y_deg"] == expected_rot


def test_bed_is_escalated_not_removed_when_nothing_fits():
    """臥室一定要有床:床連最小款都放不下時只升級回報,絕不靜默移除。"""
    bigbed = _item("bigbed", "bed-frame", 500, 300)
    objs = generate_layout(300, 300, [bigbed])
    assert objs[0]["placement_failed"] is True
    objs2, final, report = resolve_placements(
        objs, [bigbed], [bigbed], place_fn=_place(300, 300)
    )
    assert [f["furniture_id"] for f in final] == ["bigbed"]   # 保留待處理
    assert [r["action"] for r in report] == ["escalate"]
    assert "臥室必須有床" in report[0]["message_zh"]


def test_all_room_essentials_are_escalated_not_removed():
    """房型基礎家具(床/沙發/餐桌)一體適用「只升級不移除」護欄。"""
    for ftype, keyword in (("fabric-sofa", "沙發"), ("dining-table", "餐桌")):
        big = _item("big", ftype, 500, 300)
        objs = generate_layout(300, 300, [big])
        objs2, final, report = resolve_placements(
            objs, [big], [big], place_fn=_place(300, 300)
        )
        assert [f["furniture_id"] for f in final] == ["big"], ftype
        assert [r["action"] for r in report] == ["escalate"], ftype
        assert keyword in report[0]["message_zh"]


# ---------- 引擎 hints 回歸(能力保留:anchor 只改試放順序) ----------

def test_engine_anchor_hint_prepends_left_wall_candidate():
    cands = _placement_candidates("bookcase", 80, 40, 400, 400, hint={"anchor": "left"})
    x, z, rot = cands[0]
    assert x < 0 and rot == 90


def test_engine_no_hint_matches_legacy_behavior():
    legacy = _placement_candidates("sofa", 200, 90, 420, 360)
    with_none = _placement_candidates("sofa", 200, 90, 420, 360, hint=None)
    assert legacy == with_none


def test_hints_preserve_output_order():
    """priority 只改擺放順序,回傳清單順序仍照原始 items 順序。"""
    items = [_item("a", "fabric-sofa", 200, 90), _item("b", "coffee-table", 100, 50)]
    objs = generate_layout(420, 360, items, hints=placement_hints(items))
    assert [o["furniture_id"] for o in objs] == ["a", "b"]
