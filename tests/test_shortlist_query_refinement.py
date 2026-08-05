"""問卷自由文字 LLM 前置解析（query_refinement）與 shortlist 接線的行為鎖定。

不打網路：parser 一律注入假物件。涵蓋四條紀律：
1. 自由文字太短／未設 key／止血開關 → 不呼叫 parser、照舊降級。
2. 解析成功 → semantic_query 取代嵌入文字、逐分類硬上限正確映射。
3. 解析失敗 → 降級不中斷，且失敗不進快取（暫時性錯誤要能重試）。
4. build_needs_from_workflow 會把純自由文字放進 RoomNeed.free_text，
   且 fingerprint 不因 free_text 而改變（parser 抖動不可打壞快取沿用）。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.server.shortlist_api import build_needs_from_workflow
from backend.spatial_data.rag import query_refinement
from backend.spatial_data.rag.query_refinement import (
    MIN_FREE_TEXT_CHARS,
    RefinedQuery,
    refine_free_text,
    refine_many,
)
from backend.spatial_data.rag.settings import RagSettings
from backend.spatial_data.rag.shortlist import RoomNeed, categories_for_family


def _settings(api_key: str = "test-key") -> RagSettings:
    return RagSettings(
        enabled=True,
        parser_provider="openrouter",
        openai_api_key="",
        anthropic_api_key="",
        openrouter_api_key=api_key,
        openrouter_base_url="https://example.invalid/v1",
        openrouter_site_url="",
        openrouter_app_name="",
        parser_model="test-model",
        parser_reasoning_effort="low",
        parser_timeout_seconds=5.0,
        anthropic_max_tokens=1024,
        model_cache_dir=Path("."),
        model_device="cpu",
    )


def _plan(items=(), **overrides):
    base = {
        "styles": [],
        "moods": [],
        "color_hint": None,
        "material_hint": None,
        "items": list(items),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _item(**overrides):
    base = {
        "category_group": None,
        "semantic_query": "",
        "price_max": None,
        "max_width_cm": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _clear_cache():
    query_refinement._cache.clear()
    yield
    query_refinement._cache.clear()


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("parser should not be called")


def test_short_free_text_skips_parser_entirely():
    result = refine_free_text(
        "短",
        _settings(),
        categories_for_family=categories_for_family,
        parser=_fail_if_called,
    )
    assert result.parsed is False
    assert result.reason == "below_threshold"


def test_missing_api_key_degrades_without_calling_parser():
    text = "想要一張三人布沙發，預算三萬以內，不要皮革" * 2
    result = refine_free_text(
        text,
        _settings(api_key=""),
        categories_for_family=categories_for_family,
        parser=_fail_if_called,
    )
    assert result.parsed is False
    assert result.reason == "parser_unconfigured"


def test_kill_switch_disables_parser(monkeypatch):
    monkeypatch.setenv("ROOMPILOT_SHORTLIST_PARSER", "0")
    text = "想要一張三人布沙發，預算三萬以內，不要皮革"
    result = refine_free_text(
        text,
        _settings(),
        categories_for_family=categories_for_family,
        parser=_fail_if_called,
    )
    assert result.parsed is False
    assert result.reason == "disabled"


def test_successful_parse_extracts_semantic_text_and_caps():
    plan = _plan(
        items=[
            _item(
                category_group="sofa",
                semantic_query="奶油色布面三人沙發，圓潤靠背，溫暖木質腳",
                price_max=30000,
            ),
            _item(
                category_group="coffee_table",
                semantic_query="淺木色橢圓茶几",
                max_width_cm=120,
            ),
            # 對不上族系表的群組：不得產生硬條件（寧可漏擋，不可錯擋）。
            _item(category_group="decor", semantic_query="素色陶瓷花瓶", price_max=500),
        ],
        moods=["溫暖", "放鬆"],
        material_hint="布面",
    )

    def fake_parser(text, settings):
        return SimpleNamespace(plan=plan, usage={})

    result = refine_free_text(
        "客廳想要溫暖放鬆的布沙發配茶几，沙發預算三萬內，茶几不要超過120公分寬",
        _settings(),
        categories_for_family=categories_for_family,
        parser=fake_parser,
    )
    assert result.parsed is True
    assert "奶油色布面三人沙發" in result.semantic_text
    assert "氛圍：溫暖、放鬆" in result.semantic_text
    # decor 不在 GROUP_TO_FAMILY → 只剩 sofa 與 coffee_table 兩組上限。
    assert len(result.caps) == 2
    sofa_cap = next(cap for cap in result.caps if cap.price_max == 30000)
    assert set(sofa_cap.categories) == set(categories_for_family("sofa"))
    table_cap = next(cap for cap in result.caps if cap.max_width_cm == 120)
    assert set(table_cap.categories) == set(categories_for_family("coffee-table"))


def test_parser_failure_degrades_and_is_not_cached():
    calls = {"count": 0}

    def flaky_parser(text, settings):
        calls["count"] += 1
        raise TimeoutError("upstream timeout")

    text = "臥室要一張雙人床跟大衣櫃，衣櫃預算兩萬五以內"
    for _ in range(2):
        result = refine_free_text(
            text,
            _settings(),
            categories_for_family=categories_for_family,
            parser=flaky_parser,
        )
        assert result.parsed is False
        assert "TimeoutError" in result.reason
    # 失敗不進快取：第二次應該重試而不是回放失敗結果。
    assert calls["count"] == 2


def test_successful_parse_is_cached_by_text_and_model():
    calls = {"count": 0}

    def counting_parser(text, settings):
        calls["count"] += 1
        return SimpleNamespace(plan=_plan(), usage={})

    text = "書房需要一張大書桌，至少一百四十公分，要有抽屜收納"
    for _ in range(3):
        refine_free_text(
            text,
            _settings(),
            categories_for_family=categories_for_family,
            parser=counting_parser,
        )
    assert calls["count"] == 1


def test_refine_many_preserves_order_and_thresholds():
    def fake_parser(text, settings):
        return SimpleNamespace(
            plan=_plan(items=[_item(category_group="bed", semantic_query=text[:20])]),
            usage={},
        )

    texts = ["短", "主臥想要日式風的矮床架搭配無把手衣櫃，色調要淺木色", ""]
    results = refine_many(
        texts,
        _settings(),
        categories_for_family=categories_for_family,
        parser=fake_parser,
    )
    assert len(results) == 3
    assert results[0].parsed is False and results[0].reason == "below_threshold"
    assert results[1].parsed is True
    assert results[2].parsed is False


def _workflow_with_free_text(preference: str, special: list[str]) -> dict:
    return {
        "space_confirmation": {
            "rooms": [
                {
                    "id": "room-1",
                    "type": "bedroom",
                    "label": "主臥",
                    "polygon_cm": [
                        {"x": 0, "y": 0},
                        {"x": 400, "y": 0},
                        {"x": 400, "y": 360},
                        {"x": 0, "y": 360},
                    ],
                }
            ]
        },
        "requirements": {
            "roomRequirementModel": {
                "roomRequirements": {
                    "room-1": {
                        "roomType": "bedroom",
                        "roomLabel": "主臥",
                        "usage": ["睡眠休息"],
                        "specialRequests": special,
                        "furniture": {
                            "required": ["bed"],
                            "preferenceText": preference,
                        },
                    }
                },
                "globalProfile": {},
            }
        },
    }


def test_build_needs_populates_free_text_without_changing_fingerprint():
    preference = "想要日式矮床，木質色調，預算三萬內"
    workflow = _workflow_with_free_text(preference, ["靠窗要留走道"])
    needs = build_needs_from_workflow(workflow)
    assert len(needs) == 1
    need = needs[0]
    assert preference in need.free_text
    assert "靠窗要留走道" in need.free_text
    # free_text 是 query_text 的子集來源，指紋只看原始欄位：
    # 同輸入下 free_text 有無不得影響指紋。
    stripped = RoomNeed(
        room_id=need.room_id,
        room_type=need.room_type,
        width_cm=need.width_cm,
        depth_cm=need.depth_cm,
        query_text=need.query_text,
        required_families=need.required_families,
        style_id=need.style_id,
        price_max=need.price_max,
        free_text="",
    )
    assert stripped.fingerprint_payload() == need.fingerprint_payload()


def test_min_free_text_constant_guards_llm_cost():
    # 常數變動要有人抬頭看一眼：門檻太低會讓每次問卷送出多好幾次 LLM 呼叫。
    assert MIN_FREE_TEXT_CHARS >= 8


def test_refined_query_stats_shape():
    refined = RefinedQuery(parsed=True, semantic_text="x", caps=())
    assert refined.as_stats() == {"parsed": True, "caps": 0}
