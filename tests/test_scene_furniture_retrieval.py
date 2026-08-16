from __future__ import annotations

from scripts.static_source_graph import scene_controller_source

import json
import re

from fastapi.testclient import TestClient

from backend.server.main import app, _filter_furniture_payload
from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"
client = TestClient(app)

# 伺服器 /api/furniture 一頁上限(main.py page_size le=80);無 query 不排序,
# 只回自然序前 N —— fallback query 必須在這一頁內就撈得到目標家具。
_FURNITURE_PAGE_SIZE = 80


def _fallback_query_for(furniture_type: str) -> str:
    """讀問卷型錄設定的 fallback rule query（單一事實源）。"""
    source = (STATIC / "scene_questionnaire_catalog.js").read_text(encoding="utf-8")
    rules = source.split("QUESTIONNAIRE_FALLBACK_CATALOG_RULES = Object.freeze({", 1)[1].split("});", 1)[0]
    block = rules.split(f'"{furniture_type}":', 1)[1].split("},", 1)[0]
    return re.search(r'query:\s*"([^"]+)"', block).group(1)


def test_tv_bench_fallback_query_retrieves_a_tv_bench_in_first_page() -> None:
    """回歸(feedback floor04:電視櫃完全不在清單):電視櫃 fallback rule.query 必須是
    「會逐字命中型錄名稱的詞」。伺服器 _furniture_matches_query 是整串連續子字串比對,
    原本 query='tv stand console cabinet'(關鍵字清單、非任何名稱的連續子字串)→ 撈 0 筆;
    無 query 的 tier-2 又不排序、只回前 80(電視櫃在型錄第 331 筆起)→ 也 0 → 選不到。
    此測直接打真實過濾器,確保該 query 在第一頁(page_size 上限)就撈得到電視櫃族。"""
    query = _fallback_query_for("tv-bench")
    page = _filter_furniture_payload(q=query, has_model=True)[:_FURNITURE_PAGE_SIZE]
    families = {"tv-bench", "tv-media-furniture"}
    hits = [it for it in page if str(it.get("normalized_type")) in families]
    assert hits, f"query={query!r} 在前 {_FURNITURE_PAGE_SIZE} 筆撈不到電視櫃(共 {len(page)} 筆)"


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


def test_room_role_and_rag_text_influence_questionnaire_catalog_ranking() -> None:
    module_uri = (STATIC / "scene_furniture_retrieval.js").as_uri()
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
    source = scene_controller_source(STATIC)
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

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
    source = scene_controller_source(STATIC)

    assert 'endpoint: "/api/appliances"' not in source
    assert '"/api/appliances"' not in source
    assert "catalogCandidatesForType(current.type" in source
    assert "rankCatalogFurniture(catalogCandidates, rankingRequest)" in source


def test_outdoor_named_rows_rank_below_indoor_for_indoor_rooms() -> None:
    module_uri = (STATIC / "scene_furniture_retrieval.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ rankCatalogFurniture }} from {json.dumps(module_uri)};

        const candidates = [
          {{
            furniture_id: "outdoor-chaise",
            name_en: "All-weather adjustable outdoor patio chaise lounge",
            name_zh: "全天候戶外露臺躺椅",
            normalized_type: "armchair",
            primary_style: "scandinavian",
            size_cm: {{ width: 90, depth: 80 }},
            model_url: "/models/outdoor.glb",
          }},
          {{
            furniture_id: "indoor-armchair",
            name_en: "EKENÄSET armchair",
            normalized_type: "armchair",
            size_cm: {{ width: 80, depth: 75 }},
            model_url: "/models/indoor.glb",
          }},
        ];
        const living = rankCatalogFurniture(candidates, {{
          type: "armchair", roomType: "living_room", styleId: "scandinavian",
          widthCm: 90, depthCm: 80,
        }});
        const balcony = rankCatalogFurniture(candidates, {{
          type: "armchair", roomType: "balcony", styleId: "scandinavian",
          widthCm: 90, depthCm: 80,
        }});

        console.log(JSON.stringify({{
          living: living.map((item) => item.furniture_id),
          balcony: balcony.map((item) => item.furniture_id),
        }}));
        """
    )

    assert result == {
        "living": ["indoor-armchair", "outdoor-chaise"],
        "balcony": ["outdoor-chaise", "indoor-armchair"],
    }


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
