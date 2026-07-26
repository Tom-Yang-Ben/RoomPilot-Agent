from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.server.main import app
from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"
client = TestClient(app)


def test_questionnaire_matching_catalog_glb_wins_over_size_only_candidate() -> None:
    module_uri = (STATIC / "scene_furniture_retrieval.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankCatalogFurniture }} from {json.dumps(module_uri)};

        const request = {{
          styleId: "japanese",
          palette: ["#d8c6a9", "#92785b"],
          materials: ["wood", "fabric"],
          widthCm: 180,
          depthCm: 85,
        }};
        const ranked = rankCatalogFurniture([
          {{
            furniture_id: "wrong-style-near-size",
            primary_style: "industrial",
            material: "metal",
            color: "#222222",
            size_cm: {{ width: 180, depth: 85 }},
            model_url: "/models/wrong.glb",
          }},
          {{
            furniture_id: "questionnaire-match",
            primary_style: "japanese",
            material: "wood",
            color: "#92785b",
            size_cm: {{ width: 188, depth: 88 }},
            model_url: "/models/match.glb",
          }},
          {{
            furniture_id: "missing-model",
            primary_style: "japanese",
            material: "wood",
            color: "#92785b",
            size_cm: {{ width: 180, depth: 85 }},
            model_url: null,
          }},
        ], request);

        console.log(JSON.stringify(ranked.map((item) => item.furniture_id)));
        """
    )

    assert result == ["questionnaire-match", "wrong-style-near-size"]


def test_step_six_contract_requires_catalog_models_instead_of_white_fallbacks() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    assert "catalogOffersForRoomPlans" in source
    assert "missingCatalogModels" in source
    assert "全屋家具配置" in html
    assert "白色替代物" not in source


def test_appliance_catalog_exposes_verified_fridge_and_washer_glbs() -> None:
    fridge = client.get(
        "/api/appliances",
        params={"type": "fridge-freezer", "detail": "scene", "page_size": 4},
    )
    washer = client.get(
        "/api/appliances",
        params={"type": "washing-machine", "detail": "scene", "page_size": 4},
    )

    assert fridge.status_code == 200
    assert washer.status_code == 200
    assert fridge.json()["total"] == 25
    assert washer.json()["total"] == 8
    assert all(item["model_url"].endswith(".glb") for item in fridge.json()["items"])
    assert all(item["model_url"].endswith(".glb") for item in washer.json()["items"])


def test_frontend_maps_questionnaire_appliances_to_the_appliance_catalog() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert '"refrigerator": { endpoint: "/api/appliances", type: "fridge-freezer" }' in source
    assert '"washer": { endpoint: "/api/appliances", type: "washing-machine" }' in source
    assert "catalogCandidatesForType(current.type" in source
    assert "rankCatalogFurniture(catalogCandidates, request)" in source


def test_semantic_product_name_rejects_wrongly_classified_catalog_rows() -> None:
    module_uri = (STATIC / "scene_furniture_retrieval.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankCatalogFurniture }} from {json.dumps(module_uri)};

        const sofa = rankCatalogFurniture([
          {{
            furniture_id: "chair",
            name_en: "Industrial Dining Chair",
            primary_style: "industrial",
            size_cm: {{ width: 210, depth: 90 }},
            model_url: "/models/chair.glb",
          }},
          {{
            furniture_id: "couch",
            name_en: "Industrial Three Seat Sofa Couch",
            primary_style: "industrial",
            size_cm: {{ width: 220, depth: 92 }},
            model_url: "/models/couch.glb",
          }},
        ], {{ type: "sofa", styleId: "industrial", widthCm: 210, depthCm: 90 }});
        const washer = rankCatalogFurniture([
          {{
            furniture_id: "pedestal",
            name_en: "Pedestal for washer dryer",
            size_cm: {{ width: 60, depth: 62 }},
            model_url: "/models/pedestal.glb",
          }},
          {{
            furniture_id: "machine",
            name_en: "UDDARP Washing Machine",
            size_cm: {{ width: 60, depth: 60 }},
            model_url: "/models/machine.glb",
          }},
        ], {{ type: "washer", widthCm: 60, depthCm: 65 }});

        console.log(JSON.stringify({{
          sofa: sofa.map((item) => item.furniture_id),
          washer: washer.map((item) => item.furniture_id),
        }}));
        """
    )

    assert result == {
        "sofa": ["couch", "chair"],
        "washer": ["machine", "pedestal"],
    }
