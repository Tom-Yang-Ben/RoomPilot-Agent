"""交付提案 PDF（roompilot-delivery-pdf 打包 skill）adapter 與 FastAPI 測試。

content.json 底稿與 LLM 合稿不需排版引擎，離線可測；實際 Chromium 排版與
端到端下載在 playwright 可用時執行（未安裝則 skip，API 必須明確 503）。
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.agent.skills.delivery import DeliverySkill, build_content
from backend.server import design_manual_service, main
from backend.server.design_manual_service import (
    _assemble_store,
    create_delivery_proposal,
)
from backend.server.project_store import ProjectStore

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None


def _png_b64(color=(200, 180, 150)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _scene() -> dict:
    return {
        "scene_id": "scene-x",
        "requirement": {
            "style": "scandinavian",
            "constraints": {"notes": ["保留閱讀角落"]},
        },
        "style_card": {
            "card_id": "scandinavian_1",
            "name_zh": "自然木質",
            "palette_hex": ["#F3EBDD", "#D3B48A"],
        },
        "design_choices": {"floor_option": "wood_oak", "wall_option": "auto"},
        "surface_catalog": {
            "surfaces": [
                {"surface_id": "wood_oak", "name_zh": "橡木地板", "color_zh": "暖木色"}
            ]
        },
        "floorplan": {"width_cm": 400, "depth_cm": 360},
        "scene_objects": [
            {
                "id": "sofa-1",
                "furniture_id": "sofa-1",
                "instance_id": "sofa-1#1",
                "normalized_type": "sofa",
                "name_zh_raw": "北歐布沙發",
                "material": "亞麻布",
                "primary_style": "scandinavian",
                "price_twd": 18800,
                "size_cm": {"width": 210, "depth": 90, "height": 85},
                "placement_room_id": "living-1",
            }
        ],
    }


def _rooms(with_image: bool = True) -> list[dict]:
    return [
        {
            "room_id": "living-1",
            "room_label": "客廳",
            "width_cm": 400,
            "depth_cm": 360,
            "image_data_url": (
                f"data:image/png;base64,{_png_b64()}" if with_image else None
            ),
        },
        {"room_id": "study-1", "room_label": "書房", "width_cm": 300, "depth_cm": 280},
        # 浴室與陽台不在軟裝提案範圍，不該排出篇章。
        {"room_id": "bath-1", "room_label": "浴室", "width_cm": 200, "depth_cm": 180},
        {"room_id": "balcony-1", "room_label": "陽台", "width_cm": 300, "depth_cm": 120},
    ]


def _docs():
    """經 server 組裝取得 agent 文件（與正式路徑同一條組裝）。"""
    store, _ = _assemble_store(_scene(), _rooms(), design_revision=3)
    from backend.agent.documents import DocKey, LayoutDoc, RequirementDoc, SceneDoc

    snapshot = store.snapshot()
    return (
        RequirementDoc.from_dict(snapshot[DocKey.REQUIREMENTS]),
        LayoutDoc.from_dict(snapshot[DocKey.LAYOUT]),
        SceneDoc.from_dict(snapshot[DocKey.variant(DocKey.SCENE, "chosen")]),
    )


# ------------------------------------------------------------ content 底稿


def test_offline_content_is_factual_and_clean() -> None:
    requirements, layout, scene = _docs()
    content = build_content(
        "林宅", requirements, layout, scene,
        {"living-1": "rooms/living-1.png"}, design_revision=3,
    )

    assert content["meta"]["project_name"] == "林宅"
    assert content["meta"]["cover_image"] == "rooms/living-1.png"
    assert "revision 3" in content["meta"]["version"]

    rooms = {room["name"]: room for room in content["rooms"]}
    # 浴室與陽台不排篇章，範圍在速覽開場交代。
    assert set(rooms) == {"客廳", "書房"}
    assert "浴室" in content["overview"]["intro"] and "陽台" in content["overview"]["intro"]
    living = rooms["客廳"]
    assert len(living["look"]) >= 40
    # 選件依據一條就夠；擺位與淨空是工作紀錄，不是屋主要讀的設計理由。
    assert living["rationale"][0]["title"] == "選件依據"
    assert not any(
        word in json.dumps(living["rationale"], ensure_ascii=False)
        for word in ("擺位", "淨空", "幾何引擎", "不重疊")
    )
    spec_text = json.dumps(living["specs"], ensure_ascii=False)
    assert "北歐布沙發" in spec_text and "210×90 cm" in spec_text
    assert "18,800" in spec_text
    # 型號留在規格表，敘述只用通用中文名。
    assert "北歐布沙發" in living["look"] and "sofa" not in living["look"]

    # 設計總論＝後續每一章的摘要（章名當標題）。
    titles = [pillar["title"] for pillar in content["statement"]["pillars"]]
    assert titles[0] == "全案速覽" and titles[-1] == "接下來"
    assert "客廳" in titles and "書房" in titles and "色彩與材質" in titles

    # 全案速覽不能只有幾格數字：要有開場與空間一覽表。
    assert content["overview"]["intro"]
    assert len(content["overview"]["table"]["rows"]) == 2

    # 無圖房間必須寫進 appendix.limits（不能讓屋主以為漏做）。
    assert any("書房" in limit for limit in content["appendix"]["limits"])
    # 未標價原則保留。
    assert any("正式報價" in limit for limit in content["appendix"]["limits"])
    # 60/30/10 色卡 swatches：色名要看得懂，不是把色碼印兩次。
    swatch = content["palette"]["swatches"][0]
    assert swatch["usage"].startswith("主色")
    assert swatch["name"].startswith("米白") and swatch["hex"] in swatch["name"]
    assert content["palette"]["intro"].count("\n") >= 2
    assert all(material["why"] for material in content["materials"])

    # deterministic 底稿不得出現廣告腔／AI 高頻詞（writing-rules 禁詞抽查）。
    serialized = json.dumps(content, ensure_ascii=False)
    for banned in ("打造", "極致", "匠心", "營造出", "坐落於", "此外", "藉由", "不只是"):
        assert banned not in serialized, banned


def test_identical_furniture_collapses_into_one_spec_row() -> None:
    """四張一樣的餐椅抄四遍，屋主第一反應是「這表格是不是壞了」。"""
    scene = _scene()
    chair = {
        "id": "chair",
        "normalized_type": "dining-chair",
        "name_zh_raw": "鉚釘現代餐椅，34 英寸（約 86.4 釐米）高, 粉筆色",
        "material": "brass",
        "size_cm": {"width": 51, "depth": 52, "height": 86},
        "placement_room_id": "living-1",
    }
    scene["scene_objects"] += [
        {**chair, "instance_id": f"chair#{index}"} for index in range(1, 4)
    ]
    store, _ = _assemble_store(scene, _rooms(), design_revision=1)
    from backend.agent.documents import DocKey, LayoutDoc, RequirementDoc, SceneDoc

    snapshot = store.snapshot()
    content = build_content(
        "林宅",
        RequirementDoc.from_dict(snapshot[DocKey.REQUIREMENTS]),
        LayoutDoc.from_dict(snapshot[DocKey.LAYOUT]),
        SceneDoc.from_dict(snapshot[DocKey.variant(DocKey.SCENE, "chosen")]),
        {},
    )
    living = next(room for room in content["rooms"] if room["name"] == "客廳")
    chairs = [row for row in living["specs"] if "餐椅" in row["label"]]
    assert len(chairs) == 1
    assert "共 3 件" in chairs[0]["value"]
    # 類型欄出中文，不是 dining-chair。
    assert "餐椅，51×52 cm" in chairs[0]["value"] and "brass" not in chairs[0]["value"]
    # 敘述用通用名，不重複列三次。
    assert living["look"].count("餐椅") == 1


def test_llm_copy_merges_into_content() -> None:
    requirements, layout, scene = _docs()
    content = build_content("林宅", requirements, layout, scene, {}, design_revision=1)

    class CopyGateway:
        available = True

        def chat(self, messages, *, model=None, temperature=0.3, force_json=False):
            return json.dumps(
                {
                    "statement": {
                        "hook": "從玄關進門會先看到整面南向的光。",
                        "pillars": [
                            {"title": "把光留下來", "body": "南向開窗前不放高櫃。"},
                            {"title": "收納藏起來", "body": "櫃體全部靠牆做滿。"},
                        ],
                    },
                    "rooms": [
                        {
                            "room_id": "living-1",
                            "scene_line": "週五晚上四個人擠在沙發上看片。",
                            "look": "沙發背對走道，回家坐下時不會有人從背後經過；"
                                    "布面是亞麻的，夏天不黏腿。",
                            "rationale": [
                                {"title": "沙發背對走道", "body": "你說常有朋友來，動線留在沙發後面。"},
                                {"title": "留白不塞櫃", "body": "多一個櫃走道會縮，兩人錯身會卡。"},
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            )

    merged = DeliverySkill(CopyGateway())._merge_llm_copy(
        content, requirements, layout, scene
    )

    assert merged is True
    living = next(room for room in content["rooms"] if room["room_id"] == "living-1")
    assert living["scene_line"] == "週五晚上四個人擠在沙發上看片。"
    assert "亞麻" in living["look"]
    assert living["rationale"][0]["title"] == "沙發背對走道"
    assert content["statement"]["hook"] == "從玄關進門會先看到整面南向的光。"
    # 書房未回傳 → 保留 deterministic 底稿。
    study = next(room for room in content["rooms"] if room["room_id"] == "study-1")
    assert "書房" in study["look"]


def test_llm_placement_rationale_is_dropped() -> None:
    """LLM 若又寫回「擺位與淨空」，合稿時擋掉——那是工作紀錄不是設計理由。"""
    requirements, layout, scene = _docs()
    content = build_content("林宅", requirements, layout, scene, {}, design_revision=1)

    class NoisyGateway:
        available = True

        def chat(self, messages, *, model=None, temperature=0.3, force_json=False):
            return json.dumps(
                {
                    "overview_intro": "28.6 坪、兩個空間，材質與配色同一套。",
                    "palette_intro": "米白鋪底，木色收邊，點綴只出現在小物件上。",
                    "rooms": [
                        {
                            "room_id": "living-1",
                            "look": "從玄關轉進來，第一眼是整面南向的窗。",
                            "rationale": [
                                {"title": "擺位與淨空", "body": "位置由幾何引擎驗證，不重疊。"},
                                {"title": "選件依據", "body": "你說很少看電視，電視收在側牆淺櫃。"},
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            )

    DeliverySkill(NoisyGateway())._merge_llm_copy(content, requirements, layout, scene)

    living = next(room for room in content["rooms"] if room["room_id"] == "living-1")
    assert [row["title"] for row in living["rationale"]] == ["選件依據"]
    assert content["overview"]["intro"].startswith("28.6 坪")
    assert content["palette"]["intro"].startswith("米白鋪底")


def test_offline_copy_is_reported_not_silently_downgraded() -> None:
    """沒有 LLM 照樣出檔，但不能假裝文案是寫過的。"""
    requirements, layout, scene = _docs()
    content = build_content("林宅", requirements, layout, scene, {}, design_revision=1)
    assert DeliverySkill(None)._merge_llm_copy(content, requirements, layout, scene) is False


# ------------------------------------------------------------ PDF 端到端


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright 未安裝")
def test_delivery_pdf_end_to_end(tmp_path) -> None:
    result, record = create_delivery_proposal(
        "proj12345678", "林宅", _scene(), _rooms(), tmp_path,
        design_revision=3, gateway=object(),
    )
    pdf = (tmp_path / record["filename"]).read_bytes()
    assert pdf[:4] == b"%PDF"
    assert record["filename"].startswith("roompilot-proposal-proj1234-")
    assert record["rendered_rooms"] == ["living-1"]
    # content.json 留存於 PDF 旁供數字溯源。
    content = json.loads(
        (tmp_path / record["filename"]).with_suffix(".content.json").read_text("utf-8")
    )
    assert content["meta"]["project_name"] == "林宅"

    import pikepdf

    with pikepdf.open(tmp_path / record["filename"]) as doc:
        # 封面＋總論＋速覽＋兩房＋色彩材質＋接下來 ≈ 7 頁，至少要有 5 頁。
        assert len(doc.pages) >= 5


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "交付提案"}).json()["project"]
    return client, project["project_id"]


@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="playwright 未安裝")
def test_generate_then_download_proposal(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    created = client.post(
        f"/api/projects/{project_id}/delivery-proposal",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms()},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["proposal"]["download_url"] == (
        f"/api/projects/{project_id}/delivery-proposal/pdf"
    )
    assert "filename" not in body["proposal"]

    downloaded = client.get(f"/api/projects/{project_id}/delivery-proposal/pdf")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content[:4] == b"%PDF"

    project = client.get(f"/api/projects/{project_id}").json()["project"]
    assert project["workflow"]["delivery_proposal"]["filename"].endswith(".pdf")


def test_engine_missing_reports_503(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        design_manual_service,
        "delivery_engine_status",
        lambda: (False, "尚未安裝交付提案排版引擎（測試）。"),
    )
    status = client.get("/api/delivery-proposal/status")
    assert status.json() == {
        "available": False,
        "reason": "尚未安裝交付提案排版引擎（測試）。",
    }
    created = client.post(
        f"/api/projects/{project_id}/delivery-proposal",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms()},
    )
    assert created.status_code == 503
    assert created.json()["detail"]["code"] == "delivery_engine_not_configured"


def test_download_before_generation_is_404(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    response = client.get(f"/api/projects/{project_id}/delivery-proposal/pdf")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "delivery_proposal_not_found"
