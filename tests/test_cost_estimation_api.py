from fastapi.testclient import TestClient

from roompilot.server.main import app


client = TestClient(app)


def test_cost_api_uses_versioned_online_sources_without_live_network() -> None:
    response = client.post(
        "/api/cost/estimate",
        json={
            "items": [
                {
                    "id": "wall-boxing-bedroom-1",
                    "work_code": "wall_wrap.carpentry",
                    "description": "主臥樑柱包覆",
                    "quantity": {"value": 3.6, "unit": "m"},
                    "quantity_evidence": ["wall-boxing-bedroom-1", "bedroom-1"],
                }
            ]
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["totals_twd"] == {"low": 4752, "base": 8910, "high": 13068}
    assert report["items"][0]["sources"][0]["publisher"] == "UpToGo"
    assert report["items"][0]["sources"][0]["retrieved_on"] == "2026-07-12"
    assert "機電移位" in report["items"][0]["exclusions"]
    assert report["status"] == "concept_estimate"
