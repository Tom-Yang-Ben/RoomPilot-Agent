from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.paths import STATIC_DIR
from backend.server.main import app
from test_scene_workflow import ROOT, run_workflow_script


client = TestClient(app)


def test_questionnaire_matching_catalog_glb_wins_over_size_only_candidate() -> None:
    module_uri = (STATIC_DIR / "scene_furniture_retrieval.js").as_uri()
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


def test_room_role_and_rag_text_influence_questionnaire_catalog_ranking() -> None:
    module_uri = (STATIC_DIR / "scene_furniture_retrieval.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankCatalogFurniture }} from {json.dumps(module_uri)};

        const request = {{
          type: "storage-cabinet",
          roomType: "bedroom",
          roomLabel: "主臥",
          queryText: "主臥 木質 儲物 溫馨",
          preferAnchor: true,
          widthCm: 120,
          depthCm: 50,
        }};
        const ranked = rankCatalogFurniture([
          {{
            furniture_id: "generic-same-size",
            normalized_type: "cabinet-cupboard",
            primary_style: "industrial",
            size_cm: {{ width: 120, depth: 50 }},
            model_url: "/models/generic.glb",
            room_types: ["storage"],
            catalog_role: "decor",
            rag_text: ["metal office cabinet"],
          }},
          {{
            furniture_id: "kai-rag-match",
            normalized_type: "cabinet-cupboard",
            primary_style: "rustic",
            size_cm: {{ width: 121, depth: 51 }},
            model_url: "/models/match.glb",
            room_types: ["bedroom", "living_room"],
            catalog_role: "anchor",
            rag_text: ["主臥 木質 儲物 溫馨 櫃體"],
            description: "適合臥室使用的木質儲物櫃",
          }},
        ], request);

        console.log(JSON.stringify(ranked.map((item) => item.furniture_id)));
        """
    )

    assert result == ["kai-rag-match", "generic-same-size"]


def test_step_six_contract_requires_catalog_models_instead_of_white_fallbacks() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    assert "catalogOffersForRoomPlans" in source
    assert "missingCatalogModels" in source
    assert "自由旋轉" in html
    assert "全屋家具配置" not in html
    assert "白色替代物" not in source


def test_appliance_catalog_is_retired_from_step_six() -> None:
    response = client.get(
        "/api/appliances",
        params={"type": "fridge-freezer", "detail": "scene", "page_size": 4},
    )

    assert response.status_code == 404


def test_frontend_no_longer_maps_questionnaire_appliances_to_an_api() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

    assert 'endpoint: "/api/appliances"' not in source
    assert '"/api/appliances"' not in source
    assert "catalogCandidatesForType(current.type" in source
    assert "rankCatalogFurniture(catalogCandidates, request)" in source


def test_semantic_product_name_rejects_wrongly_classified_catalog_rows() -> None:
    module_uri = (STATIC_DIR / "scene_furniture_retrieval.js").as_uri()
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


def test_shortlist_degradation_is_visible_not_console_only() -> None:
    """候選集失效或某族系退回全型錄時，使用者必須看得到（QA 2026-08-03）。

    退化只留 console.warn 的後果：使用者以為在用候選集，實際整輪全型錄，
    載入慢還不知道原因。這裡釘住三個誠實回報點。
    """
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    assert 'id="furniture-source-notice"' in html, "第 6 步必須有家具來源通知元素"

    ensure_block = source.split("async function ensureFurnitureShortlist(", 1)[1].split(
        "async function catalogOffersForSpec(", 1
    )[0]
    assert ensure_block.count("renderFurnitureSourceNotice()") >= 2, (
        "候選集建立成功與失敗兩條路徑都要更新來源通知"
    )
    assert "shortlistState.notice" in ensure_block

    offers_block = source.split("async function catalogOffersForSpec(", 1)[1].split(
        "async function catalogFallbackOffersForSpec(", 1
    )[0]
    assert "noteShortlistFallback(spec[0])" in offers_block, (
        "候選集查無該族系而退回全型錄時必須記錄"
    )

    fallback_block = source.split("async function catalogFallbackOffersForSpec(", 1)[1].split(
        "async function catalogOffersForRoomPlans(", 1
    )[0]
    assert "noteShortlistFallback(spec[0])" in fallback_block, (
        "「找相似」全型錄補搜也必須記錄"
    )
