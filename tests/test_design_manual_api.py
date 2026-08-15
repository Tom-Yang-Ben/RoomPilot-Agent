"""第 8 步收尾設計手冊（Report Agent）adapter 與 FastAPI 端到端測試。

不碰網路：離線（無 OPENROUTER_API_KEY）必須照樣輸出九章 PDF（deterministic
底稿）；LLM 可用時只潤飾前言。驗證 scene_json＋生圖成果 → agent 文件的組裝、
workflow 保存與 PDF 下載。
"""
from __future__ import annotations

import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from backend.server import design_manual_service, main
from backend.server.design_manual_service import create_design_manual
from backend.server.project_store import ProjectStore
from backend.agent.llm import LLMError

EXPECTED_HEADINGS = [
    "一、專案與需求摘要",
    "二、設計理念與亮點",
    "三、空間與平面配置",
    "四、家具清單",
    "五、材質與色卡",
    "六、驗證與調整紀錄",
    "七、渲染成果",
    "八、工程與預算章節",
    "九、報價單",
]


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
        "render_context": {
            "appliance_requirements": [
                {
                    "appliance_id": "fridge-1",
                    "normalized_type": "refrigerator",
                    "name_zh_raw": "雙門冰箱",
                    "quantity": 1,
                }
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
                "position_cm": {"x": -80, "z": 100},
                "size_cm": {"width": 210, "depth": 90, "height": 85},
                "placement_room_id": "living-1",
            },
            {
                "id": "bad-1",
                "furniture_id": "bad-1",
                "normalized_type": "cabinet",
                "name_zh_raw": "無法擺放的櫃",
                "placement_failed": True,
                "size_cm": {"width": 10, "depth": 10},
            },
        ],
    }


def _rooms(with_image: bool = True, with_night: bool = False) -> list[dict]:
    room = {
        "room_id": "living-1",
        "room_label": "客廳",
        "width_cm": 400,
        "depth_cm": 360,
        "image_data_url": (
            f"data:image/png;base64,{_png_b64()}" if with_image else None
        ),
        "model": "google/gemini-3.1-flash-image",
    }
    if with_night:
        # 客廳才有的夜間燈光圖（stage=full_render_night），由第 8 步一併回傳。
        room["night_image_data_url"] = f"data:image/png;base64,{_png_b64((20, 24, 40))}"
        room["night_model"] = "google/gemini-3.1-flash-image"
    return [room]


# ------------------------------------------------------------ adapter 單元測試


def test_offline_manual_has_nine_sections_and_scene_facts(tmp_path) -> None:
    manual, record = create_design_manual(
        "proj12345678", _scene(), _rooms(), tmp_path, gateway=object()
    )

    assert [section.heading for section in manual.sections] == EXPECTED_HEADINGS
    assert record["sections"] == EXPECTED_HEADINGS
    assert record["rendered_rooms"] == ["living-1"]
    assert record["filename"].startswith("roompilot-manual-proj1234-")

    furniture = next(s for s in manual.sections if s.heading.startswith("四、"))
    assert "北歐布沙發" in furniture.body
    assert "18,800" not in furniture.body  # 金額只在第九章報價單
    assert "無法擺放的櫃" not in furniture.body  # placement_failed 不進手冊

    quote = next(s for s in manual.sections if s.heading.startswith("九、"))
    assert "北歐布沙發 ×1" in quote.body and "18,800 元" in quote.body

    render = next(s for s in manual.sections if s.heading.startswith("七、"))
    assert "客廳" in render.body
    assert render.image_ids == ["img_living-1_final"]

    materials = next(s for s in manual.sections if s.heading.startswith("五、"))
    assert "自然木質" in materials.body and "（選定）" in materials.body

    validation = next(s for s in manual.sections if s.heading.startswith("六、"))
    assert "backend/engine" in validation.body

    pdf = (tmp_path / record["filename"]).read_bytes()
    assert pdf[:4] == b"%PDF"


def test_living_room_night_image_reaches_the_render_chapter(tmp_path) -> None:
    """客廳夜間圖要在「七、渲染成果」與日光並列。

    先前 `_image_library()` 只讀 `image_data_url`，圖庫裡永遠沒有
    `full_render_night`，report skill 那段日光／夜間並列因此是死碼——夜間圖
    生出來了卻不會出現在任何一份報告裡。
    """
    manual, record = create_design_manual(
        "proj12345678", _scene(), _rooms(with_night=True), tmp_path, gateway=object()
    )

    render = next(s for s in manual.sections if s.heading.startswith("七、"))
    assert "客廳（日光）" in render.body
    assert "客廳（夜間）" in render.body
    assert render.image_ids == ["img_living-1_final", "img_living-1_night"]
    assert record["rendered_rooms"] == ["living-1", "living-1"]


def test_manual_render_chapter_stays_single_image_without_night(tmp_path) -> None:
    """沒有夜間圖的房間維持單圖原樣，不會多出空的「（日光）」標記。"""
    manual, _ = create_design_manual(
        "proj12345678", _scene(), _rooms(), tmp_path, gateway=object()
    )
    render = next(s for s in manual.sections if s.heading.startswith("七、"))
    assert "客廳（日光）" not in render.body and "（夜間）" not in render.body
    assert "客廳：" in render.body


def test_manual_without_images_marks_render_section_pending(tmp_path) -> None:
    manual, record = create_design_manual(
        "proj12345678", _scene(), _rooms(with_image=False), tmp_path, gateway=object()
    )
    render = next(s for s in manual.sections if s.heading.startswith("七、"))
    assert "（尚無渲染成果）" in render.body
    assert record["rendered_rooms"] == []


def test_llm_available_polishes_intro(tmp_path) -> None:
    class IntroGateway:
        available = True

        def chat(self, messages, *, model=None, temperature=0.3, force_json=False, reasoning=None):
            if "前言" in messages[0]["content"]:
                return '{"intro": "為兩位屋主打造的北歐提案前言。"}'
            raise LLMError("其他提示詞不在本測試範圍")

    manual, _ = create_design_manual(
        "proj12345678", _scene(), _rooms(), tmp_path, gateway=IntroGateway()
    )
    intro = next(s for s in manual.sections if s.heading.startswith("一、"))
    assert "為兩位屋主打造的北歐提案前言。" in intro.body


# ------------------------------------------------------------ FastAPI 端到端


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "設計手冊"}).json()["project"]
    return client, project["project_id"]


def test_generate_then_download_manual(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    created = client.post(
        f"/api/projects/{project_id}/design-manual",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms()},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["manual"]["sections"] == EXPECTED_HEADINGS
    assert body["manual"]["download_url"] == (
        f"/api/projects/{project_id}/design-manual/pdf"
    )
    assert "filename" not in body["manual"]  # 檔名只留在 workflow，不進公開回應

    downloaded = client.get(f"/api/projects/{project_id}/design-manual/pdf")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content[:4] == b"%PDF"

    project = client.get(f"/api/projects/{project_id}").json()["project"]
    record = project["workflow"]["design_manual"]
    assert record["sections"] == EXPECTED_HEADINGS
    assert record["filename"].endswith(".pdf")
    assert project["revision"] == body["revision"]

    # 重新產出：取代 workflow 紀錄並提高 revision，下載仍可用。
    regenerated = client.post(
        f"/api/projects/{project_id}/design-manual",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms()},
    )
    assert regenerated.status_code == 201
    assert regenerated.json()["revision"] > body["revision"]
    assert (
        client.get(f"/api/projects/{project_id}/design-manual/pdf").status_code == 200
    )


def test_download_before_generation_is_404(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    response = client.get(f"/api/projects/{project_id}/design-manual/pdf")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "design_manual_not_found"


def test_generate_requires_scene_and_rooms(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    missing_scene = client.post(
        f"/api/projects/{project_id}/design-manual",
        json={"project_id": project_id, "rooms": _rooms()},
    )
    assert missing_scene.status_code == 422
    assert missing_scene.json()["detail"]["code"] == "scene_required"

    missing_rooms = client.post(
        f"/api/projects/{project_id}/design-manual",
        json={"project_id": project_id, "scene": _scene(), "rooms": []},
    )
    assert missing_rooms.status_code == 422
    assert missing_rooms.json()["detail"]["code"] == "rooms_required"


def test_manual_project_mismatch_is_422(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    mismatched = client.post(
        f"/api/projects/{project_id}/design-manual",
        json={"project_id": "other", "scene": _scene(), "rooms": _rooms()},
    )
    assert mismatched.status_code == 422
    assert mismatched.json()["detail"]["code"] == "manual_project_mismatch"
