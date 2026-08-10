"""選件規則:客廳三件組、臥室不重複床、廚房餐椅依入住人數。"""
from __future__ import annotations

from backend.server.scene_service import (
    _expand_dining_seats,
    _merge_exact_and_chosen,
    _occupant_headcount,
    normalize_required_furniture,
    selected_furniture_items_from_questionnaire,
)


def _item(fid, ntype, **extra):
    return {"furniture_id": fid, "normalized_type": ntype, **extra}


# ── Fix 2:客廳至少沙發 + 茶几 + 電視櫃 ──────────────────────────
def test_living_room_required_includes_sofa_coffee_table_tv_bench():
    req = normalize_required_furniture(["armchair"], "living_room")
    assert "sofa" in req
    assert "coffee-table" in req
    assert "tv-bench" in req
    assert "armchair" in req            # 原有的保留


def test_living_room_no_duplicate_when_already_present():
    req = normalize_required_furniture(["sofa", "coffee-table", "tv-bench"], "living_room")
    assert req.count("sofa") == 1 and req.count("coffee-table") == 1 and req.count("tv-bench") == 1


# ── Fix 1:同族去重,臥室不出現兩張床 ──────────────────────────
def test_merge_dedups_bed_across_type_aliases():
    exact = [_item("u-bed", "bed-frame")]                 # 使用者精選床(bed-frame)
    chosen = [_item("auto-bed", "bed"), _item("auto-wd", "wardrobe")]
    merged = _merge_exact_and_chosen(exact, chosen)
    beds = [it for it in merged if it["normalized_type"] in ("bed", "bed-frame")]
    assert len(beds) == 1 and beds[0]["furniture_id"] == "u-bed"
    assert any(it["furniture_id"] == "auto-wd" for it in merged)   # 別族保留


# ── Fix 1b:exact 選件路徑(selected_furniture_exact)也只留一張床 ─────
# 迴歸來源:floor04 臥室出現兩張床相貼、無走道。逐房 A/B 送 exact 選件繞過
# _merge_exact_and_chosen,原本只比 furniture_id,兩件床族商品都會留。
def _picked(fid, ntype):
    # has_model=False + user_specified=True 通過「無模型但使用者確認」的驗證分支
    return {"furniture_id": fid, "normalized_type": ntype,
            "has_model": False, "user_specified": True}


def test_exact_selection_keeps_only_one_bed():
    q = {"selected_furniture": [
        _picked("bed-a", "bed"),
        _picked("bed-b", "bed-frame"),   # 同族(family_of→bed),應被折掉
        _picked("wd", "wardrobe"),
    ]}
    out = selected_furniture_items_from_questionnaire(q, [])
    beds = [it for it in out if it["normalized_type"] in ("bed", "bed-frame")]
    assert len(beds) == 1 and beds[0]["furniture_id"] == "bed-a"   # 保留先選的
    assert any(it["furniture_id"] == "wd" for it in out)           # 別族保留


def test_exact_selection_keeps_plural_non_bed_families():
    # 範圍守衛:只折 bed 家族;床頭櫃/餐椅等成對成組,不得被去重
    q = {"selected_furniture": [
        _picked("ns1", "bedside-table"),
        _picked("ns2", "bedside-table"),
        _picked("ch1", "dining-chair"),
        _picked("ch2", "dining-chair"),
    ]}
    out = selected_furniture_items_from_questionnaire(q, [])
    assert len([it for it in out if it["normalized_type"] == "bedside-table"]) == 2
    assert len([it for it in out if it["normalized_type"] == "dining-chair"]) == 2


# ── Fix 4:廚房餐椅 = max(2, 入住人數),不超過桌子可坐數 ─────────
def test_occupant_headcount_sums_people_not_pets():
    assert _occupant_headcount({"occupants": {"adults": 2, "children": 1, "elderly": 1, "pets": 3}}) == 4
    assert _occupant_headcount({}) == 0


def test_dining_chairs_expand_to_occupants():
    items = [
        _item("t", "dining-table", size_cm={"width": 150, "depth": 90}),
        _item("c", "dining-chair", size_cm={"width": 45, "depth": 45}),
    ]
    out = _expand_dining_seats(items, {"occupants": {"adults": 3}})
    chairs = [it for it in out if it["normalized_type"] == "dining-chair"]
    assert len(chairs) == 3                                   # max(2,3)=3,寬桌 cap 4
    assert len({it["instance_id"] for it in chairs}) == 3     # 各有獨立 instance_id


def test_dining_chairs_min_two_when_few_occupants():
    items = [
        _item("t", "dining-table", size_cm={"width": 120, "depth": 80}),
        _item("c", "dining-chair", size_cm={"width": 45, "depth": 45}),
    ]
    out = _expand_dining_seats(items, {"occupants": {"adults": 1}})
    chairs = [it for it in out if it["normalized_type"] == "dining-chair"]
    assert len(chairs) == 2                                   # 至少 2


def test_dining_chairs_capped_by_small_table():
    items = [
        _item("t", "dining-table", size_cm={"width": 120, "depth": 80}),
        _item("c", "dining-chair", size_cm={"width": 45, "depth": 45}),
    ]
    out = _expand_dining_seats(items, {"occupants": {"adults": 5}})
    chairs = [it for it in out if it["normalized_type"] == "dining-chair"]
    assert len(chairs) == 2                                   # min(max(2,5), 2 席) = 2


def test_no_dining_table_no_expansion():
    items = [_item("c", "dining-chair", size_cm={"width": 45, "depth": 45})]
    assert _expand_dining_seats(items, {"occupants": {"adults": 4}}) == items
