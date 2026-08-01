"""`/api/agent/furniture/select` 的兩端契約：需求進得來，選件 agent 叫得動。

QA 2026-08-01 的兩個斷點：前端送的 ``context`` 在本地規則分支被整包丟掉，
而 LLM 分支只有 payload 自帶 ``llm_selection`` 時才會走，等於從未觸發。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.server import main
from backend.server import scene_service
from backend.server.main import app


client = TestClient(app)


def _candidate(fid: str, kind: str) -> dict:
    return {
        "furniture_id": fid,
        "normalized_type": kind,
        "variant_id": "standard",
        "name_zh_raw": fid,
        "size_cm": {"width": 120, "depth": 60, "height": 80},
    }


def _bedroom_payload(context: dict | None = None) -> dict:
    payload: dict = {
        "rooms": [{"room_id": "bedroom-1", "room_type": "bedroom"}],
        "offers": {
            "bedroom-1": [
                _candidate("bed-1", "bed-frame"),
                _candidate("nightstand-1", "bedside-table"),
                _candidate("wardrobe-1", "pax-wardrobe"),
            ]
        },
        "style_id": "japandi",
    }
    if context is not None:
        payload["context"] = context
    return payload


def _room_requirements(**furniture: object) -> dict:
    return {
        "room_requirements": {
            "bedroom-1": {
                "roomId": "bedroom-1",
                "roomLabel": "主臥",
                "usage": ["睡眠"],
                "furniture": {"required": [], "optional": [], "selected": [], "deferred": [], **furniture},
                "specialRequests": [],
                "confirmed": True,
            }
        }
    }


def _selected_ids(payload: dict) -> list[str]:
    return [item["furniture_id"] for item in payload["rooms"][0]["items"]]


def test_local_rules_follow_questionnaire_selection_order_and_count() -> None:
    response = client.post(
        "/api/agent/furniture/select",
        json=_bedroom_payload(_room_requirements(selected=[
            {"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe", "count": 2},
        ])),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    # 問卷勾選的衣櫃排第一並保住數量；QA 實測的「全案 0 衣櫃」不再發生。
    assert _selected_ids(payload)[0] == "wardrobe-1"
    assert payload["rooms"][0]["items"][0]["count"] == 2


def test_local_rules_drop_furniture_the_user_deferred() -> None:
    response = client.post(
        "/api/agent/furniture/select",
        json=_bedroom_payload(_room_requirements(deferred=[
            {"furniture_id": "wardrobe-1", "normalized_type": "pax-wardrobe"},
        ])),
    )

    assert response.status_code == 200
    ids = _selected_ids(response.json())
    assert "wardrobe-1" not in ids
    assert "bed-1" in ids


def test_selection_without_context_keeps_previous_local_behaviour() -> None:
    response = client.post("/api/agent/furniture/select", json=_bedroom_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    assert payload["warnings"] == []
    assert "bed-1" in _selected_ids(payload)


def test_server_calls_the_selection_agent_without_client_supplied_llm_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """伺服器自己注入 LLM 呼叫器；前端不需要、也不該持有 API 金鑰。"""
    seen: list[list[dict[str, str]]] = []

    def fake_complete_fn():
        def complete(messages: list[dict[str, str]]) -> tuple[str, dict]:
            seen.append(messages)
            return "mock/select", {
                "selections": [{
                    "room_id": "bedroom-1",
                    "items": [{"furniture_id": "bed-1"}, {"furniture_id": "wardrobe-1"}],
                }]
            }

        return complete

    monkeypatch.setattr(main, "selection_complete_fn", fake_complete_fn)

    response = client.post(
        "/api/agent/furniture/select",
        json=_bedroom_payload(_room_requirements(required=["pax-wardrobe"])),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "openrouter"
    assert payload["model"] == "mock/select"
    assert set(_selected_ids(payload)) == {"bed-1", "wardrobe-1"}
    # 問卷需求確實被帶進提示，而不是只留在前端。
    assert seen and "must_include_types" in seen[0][1]["content"]


def test_llm_output_missing_questionnaire_furniture_falls_back_to_local_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_complete_fn():
        return lambda _messages: ("mock/select", {
            "selections": [{"room_id": "bedroom-1", "items": [{"furniture_id": "bed-1"}]}]
        })

    monkeypatch.setattr(main, "selection_complete_fn", fake_complete_fn)

    response = client.post(
        "/api/agent/furniture/select",
        json=_bedroom_payload(_room_requirements(required=["pax-wardrobe"])),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "local_rules"
    assert any("衣櫃" in warning for warning in payload["warnings"])
    assert "wardrobe-1" in _selected_ids(payload)


def test_selection_stays_offline_when_the_flag_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_SELECTION_ENABLED", "0")
    assert scene_service.selection_enabled() is False
    assert scene_service.selection_complete_fn() is None


def test_selection_is_enabled_by_default_once_an_api_key_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.delenv("OPENROUTER_SELECTION_ENABLED", raising=False)
    assert scene_service.selection_enabled() is True
    assert scene_service.get_openrouter_status()["selection_enabled"] is True
