"""layout_rules 邊界契約：LLM 回傳的規則項目一律正規化為含 message 的 dict。

背景：build_scene_payload 組 render_context.constraints.must_keep 時直接呼叫
rule.get("message")（scene_service.py 內 must_keep 推導式）。LLM 若回字串陣列，
該處會 AttributeError 噴 500。驗證責任放在資料進入系統的邊界
（_normalize_openrouter_plan），下游沿用 dict 假設即可。
"""
from backend.server.scene_service import _normalize_openrouter_plan

STYLES = [{"style_id": "scandinavian", "style_name_zh": "北歐"}]
QUESTIONNAIRE = {"space_type": "living_room", "style_preference": "scandinavian"}


def _normalize(layout_rules):
    plan = _normalize_openrouter_plan(
        {"required_furniture": ["sofa"], "layout_rules": layout_rules},
        QUESTIONNAIRE,
        STYLES,
    )
    assert plan is not None
    return plan["layout_rules"]


def _must_keep(rules):
    """複製 build_scene_payload 取用 must_keep 的表達式，作為真正的迴歸點。"""
    return [rule.get("message") for rule in rules if rule.get("message")]


def test_string_rules_are_wrapped_into_message_dict():
    rules = _normalize(["家具避免遮擋主要採光面。", "床不要對到門。"])

    assert all(isinstance(rule, dict) for rule in rules)
    assert _must_keep(rules) == ["家具避免遮擋主要採光面。", "床不要對到門。"]


def test_dict_rules_pass_through_unchanged():
    original = {"rule": "keep_door_clear", "message": "入口前方保持淨空。"}
    rules = _normalize([original])

    assert rules == [original]


def test_mixed_and_unusable_items_do_not_break_must_keep():
    rules = _normalize(
        [
            "字串規則。",
            {"rule": "need_storage", "message": "優先收納家具。"},
            {"rule": "no_message_field"},
            123,
            None,
            "   ",
        ]
    )

    assert all(isinstance(rule, dict) for rule in rules)
    assert _must_keep(rules) == ["字串規則。", "優先收納家具。"]


def test_non_list_layout_rules_becomes_empty():
    assert _normalize("家具避免遮擋採光") == []
    assert _normalize(None) == []
