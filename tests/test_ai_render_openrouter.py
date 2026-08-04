"""第 8 步 AI 生圖（OpenRouter nano banana）adapter 與 FastAPI 端到端測試。

不碰網路：以假 gateway 替換 OpenRouter；驗證 scene_json → 生圖提示詞的資訊補充
（家具鎖定、家電 context、色卡、逐房與整體補充需求、視角截圖 img2img）、整批
一次改圖額度，以及未設定金鑰時明確 503。
"""
from __future__ import annotations

import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from backend.server import ai_render_service, main
from backend.server.ai_render_service import generate_room_images
from backend.server.project_store import ProjectStore
from backend.agent.llm import ImageResult, LLMError


def _png_b64(color=(200, 180, 150)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


REFERENCE_PNG = f"data:image/png;base64,{_png_b64((10, 20, 30))}"


class CapturingGateway:
    """記錄每次生圖/改圖的提示詞與輸入圖；chat 一律失敗以走改圖 fallback。"""

    available = True
    image_model = "google/gemini-2.5-flash-image"
    image_fallback_model = "google/gemini-3-pro-image-preview"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.image_inputs: list[tuple] = []

    def chat(self, messages, *, model=None, temperature=0.3, force_json=False) -> str:
        raise LLMError("測試環境不提供文字模型")

    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        self.prompts.append(prompt)
        self.image_inputs.append(tuple(images))
        return ImageResult(image_b64=_png_b64(), model=model or self.image_model)


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
                "normalized_type": "sofa",
                "name_zh_raw": "北歐布沙發",
                "position_cm": {"x": -80, "z": 100},
                "rotation_y_deg": 180,
                "size_cm": {"width": 210, "depth": 90, "height": 85},
                "placement_room_id": "living-1",
            },
            {
                "id": "bad-1",
                "furniture_id": "bad-1",
                "normalized_type": "cabinet",
                "name_zh_raw": "無法擺放的櫃",
                "placement_failed": True,
                "position_cm": {"x": 0, "z": 0},
                "size_cm": {"width": 10, "depth": 10},
            },
        ],
    }


def _rooms() -> list[dict]:
    return [
        {
            "room_id": "living-1",
            "room_label": "客廳",
            "reference_png_data_url": REFERENCE_PNG,
            "note": "沙發旁要立燈",
        }
    ]


# ------------------------------------------------------------ adapter 單元測試


def test_prompt_supplements_all_collected_info() -> None:
    gateway = CapturingGateway()
    outcome = generate_room_images(_scene(), _rooms(), gateway=gateway)

    assert [row["status"] for row in outcome["results"]] == ["completed"]
    prompt = gateway.prompts[0]
    # 模板定案：「渲染成寫實風格，房間：{}、…」；數值資訊（尺寸）不提供。
    assert prompt.startswith("渲染成寫實風格，房間：客廳")
    # 家具鎖定（不含尺寸數值），且 placement_failed 家具不進畫面。
    assert "北歐布沙發" in prompt
    assert "210x90cm" not in prompt
    assert "無法擺放的櫃" not in prompt
    assert "不可增減或移動" in prompt
    # 家電只作為畫面 context。
    assert "家電：" in prompt and "雙門冰箱" in prompt
    # 地板材質、60-30-10 色調。
    assert "地板材質：" in prompt and "橡木地板" in prompt
    assert "色調採(60%, 30%, 10%)：" in prompt and "#F3EBDD" in prompt
    # 逐房與整體補充需求（額外需求）都補進視角備註。
    assert "使用者補充：沙發旁要立燈" in prompt
    assert "整體補充需求：保留閱讀角落" in prompt
    # 3D 視角截圖當 img2img 參考（不移動擺設的關鍵）。
    assert _png_b64((10, 20, 30)) in gateway.image_inputs[0][0]


def test_failed_furniture_room_still_returns_other_rooms() -> None:
    scene = _scene()
    rooms = [
        {"room_id": "living-1", "room_label": "客廳", "reference_png_data_url": REFERENCE_PNG},
        {"room_id": "study-1", "room_label": "書房", "reference_png_data_url": REFERENCE_PNG},
    ]
    outcome = generate_room_images(scene, rooms, gateway=CapturingGateway())
    assert {row["room_id"] for row in outcome["results"]} == {"living-1", "study-1"}
    assert all(row["status"] == "completed" for row in outcome["results"])


# ------------------------------------------------------------ FastAPI 端到端


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "AI render"}).json()["project"]
    return client, project["project_id"]


def test_generate_then_single_batch_edit_budget(tmp_path, monkeypatch) -> None:
    gateway = CapturingGateway()
    monkeypatch.setattr(ai_render_service, "OpenRouterGateway", lambda: gateway)
    client, project_id = _client(tmp_path, monkeypatch)

    generated = client.post(
        f"/api/projects/{project_id}/ai-renders",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms()},
    )
    assert generated.status_code == 201
    body = generated.json()
    assert body["edit_remaining"] == 1
    image_data_url = body["results"][0]["image_data_url"]
    assert image_data_url.startswith("data:image/png;base64,")

    edited = client.post(
        f"/api/projects/{project_id}/ai-renders/living-1/edit",
        json={"feedback": "把牆面改成淺灰", "image_data_url": image_data_url},
    )
    assert edited.status_code == 201
    assert edited.json()["edit_remaining"] == 0
    # 改圖鎖定清單約束既有家具不動，且帶入使用者意見。
    edit_prompt = gateway.prompts[-1]
    assert "把牆面改成淺灰" in edit_prompt
    assert "北歐布沙發" in edit_prompt

    exhausted = client.post(
        f"/api/projects/{project_id}/ai-renders/living-1/edit",
        json={"feedback": "再改一次", "image_data_url": image_data_url},
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["detail"]["code"] == "ai_edit_budget_exhausted"


def test_unconfigured_openrouter_reports_explicit_503(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client, project_id = _client(tmp_path, monkeypatch)

    status = client.get("/api/ai-render/status")
    assert status.status_code == 200
    assert status.json()["configured"] is False

    generated = client.post(
        f"/api/projects/{project_id}/ai-renders",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms()},
    )
    assert generated.status_code == 503
    assert generated.json()["detail"]["code"] == "openrouter_api_key_not_configured"


def test_generate_requires_room_views(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_render_service, "OpenRouterGateway", lambda: CapturingGateway())
    client, project_id = _client(tmp_path, monkeypatch)

    missing_rooms = client.post(
        f"/api/projects/{project_id}/ai-renders",
        json={"project_id": project_id, "scene": _scene(), "rooms": []},
    )
    assert missing_rooms.status_code == 422
    assert missing_rooms.json()["detail"]["code"] == "room_views_required"

    missing_png = client.post(
        f"/api/projects/{project_id}/ai-renders",
        json={
            "project_id": project_id,
            "scene": _scene(),
            "rooms": [{"room_id": "living-1", "room_label": "客廳"}],
        },
    )
    assert missing_png.status_code == 422
    assert missing_png.json()["detail"]["code"] == "reference_png_required"
