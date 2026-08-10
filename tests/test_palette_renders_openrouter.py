"""第 7 步代表房「三色卡比較」生圖 adapter 與 FastAPI 端到端測試。

不碰網路：以假 gateway 替換 OpenRouter。驗證：
- 同一代表房 × N 張色卡各送一次(各卡自己的 60/30/10 用色);
- 一次併發送出(barrier 證明三請求同時在途);
- 用 Nano Banana Pro 模型;
- 每個專案只能成功生成一次(201 → 409),全部失敗則不鎖定可重試;
- 未設定金鑰明確 503,缺欄位 422。
"""
from __future__ import annotations

import base64
import io
import threading

from fastapi.testclient import TestClient
from PIL import Image

from backend.server import ai_render_service, main
from backend.server.ai_render_service import (
    DEFAULT_PALETTE_IMAGE_MODEL,
    _palette_gateway,
    generate_palette_images,
)
from backend.server.project_store import ProjectStore
from backend.server.style_cards import load_taiwan_style_cards
from backend.agent.llm import ImageResult, LLMError


def _png_b64(color=(200, 180, 150)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


REFERENCE_PNG = f"data:image/png;base64,{_png_b64((10, 20, 30))}"


class CapturingGateway:
    available = True
    image_model = DEFAULT_PALETTE_IMAGE_MODEL
    image_fallback_model = "google/gemini-2.5-flash-image"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.models: list[str] = []
        self._lock = threading.Lock()

    def chat(self, messages, **kwargs) -> str:
        raise LLMError("測試環境不提供文字模型")

    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        with self._lock:
            self.prompts.append(prompt)
            self.models.append(model or self.image_model)
        return ImageResult(image_b64=_png_b64(), model=model or self.image_model)


class FailingGateway(CapturingGateway):
    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        raise LLMError("模型連線失敗")


def _scene() -> dict:
    return {
        "scene_id": "scene-x",
        "requirement": {"style": "scandinavian", "constraints": {"notes": []}},
        "style_card": {"card_id": "scandinavian_1", "name_zh": "自然木質"},
        "design_choices": {},
        "surface_catalog": {"surfaces": []},
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
            }
        ],
    }


def _room() -> dict:
    return {
        "room_id": "living-1",
        "room_label": "客廳",
        "reference_png_data_url": REFERENCE_PNG,
    }


def _three_distinct_cards() -> list[dict]:
    """從官方色卡取三張 palette_hex 各不相同的卡,供「各卡各自用色」斷言。"""
    seen: dict[str, list[str]] = {}
    for group in load_taiwan_style_cards():
        for card in group.get("cards") or []:
            colors = [str(c) for c in (card.get("palette_hex") or [])]
            key = "|".join(colors)
            if colors and key not in {"|".join(v) for v in seen.values()}:
                seen[str(card.get("card_id"))] = colors
            if len(seen) == 3:
                return [{"card_id": cid, "colors": cols} for cid, cols in seen.items()]
    raise AssertionError("需要至少三張 palette 不同的官方色卡")


# ------------------------------------------------------------ adapter 單元測試


def test_one_request_per_card_with_that_cards_palette() -> None:
    cards = _three_distinct_cards()
    gateway = CapturingGateway()
    outcome = generate_palette_images(
        _scene(), _room(), [c["card_id"] for c in cards], gateway=gateway
    )

    assert [r["status"] for r in outcome["results"]] == ["completed"] * 3
    assert [r["style_card_id"] for r in outcome["results"]] == [c["card_id"] for c in cards]
    assert all(r["image_data_url"].startswith("data:image/png;base64,") for r in outcome["results"])
    # 三張色卡 → 三次生圖請求。
    assert len(gateway.prompts) == 3
    # 每張卡自己的用色都要有進到某一張提示詞(併發故不保證順序)。
    for card in cards:
        assert any(card["colors"][0] in prompt for prompt in gateway.prompts), (
            f"{card['card_id']} 的色卡用色沒進提示詞"
        )
    # 三張提示詞互不相同(各卡用色不同)。
    assert len(set(gateway.prompts)) == 3


def test_palette_render_uses_nano_banana_pro_model() -> None:
    cards = _three_distinct_cards()
    gateway = CapturingGateway()
    generate_palette_images(_scene(), _room(), [c["card_id"] for c in cards], gateway=gateway)
    assert set(gateway.models) == {DEFAULT_PALETTE_IMAGE_MODEL}
    # 預設就是 nano banana pro,可用 env 覆蓋。
    assert _palette_gateway().image_model == DEFAULT_PALETTE_IMAGE_MODEL
    assert DEFAULT_PALETTE_IMAGE_MODEL == "google/gemini-3-pro-image-preview"


def test_palette_env_override_changes_model(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_GENPIC_PALETTE_MODEL", "google/custom-pro")
    assert _palette_gateway().image_model == "google/custom-pro"


def test_three_requests_are_in_flight_at_once() -> None:
    """barrier(3):三個請求必須同時在途才會通過;若是逐一序列送出,barrier 會 timeout。"""
    cards = _three_distinct_cards()
    barrier = threading.Barrier(3, timeout=8)

    class BarrierGateway(CapturingGateway):
        def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
            barrier.wait()  # 逐一序列會卡在這裡等不到另外兩個 → BrokenBarrier/timeout
            return super().generate_image(prompt, images=images, model=model)

    outcome = generate_palette_images(
        _scene(), _room(), [c["card_id"] for c in cards], gateway=BarrierGateway()
    )
    assert [r["status"] for r in outcome["results"]] == ["completed"] * 3


# ------------------------------------------------------------ FastAPI 端到端


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "palette"}).json()["project"]
    return client, project["project_id"]


def _post(client, project_id, **overrides):
    body = {
        "project_id": project_id,
        "scene": _scene(),
        "room": _room(),
        "style_card_ids": [c["card_id"] for c in _three_distinct_cards()],
    }
    body.update(overrides)
    return client.post(f"/api/projects/{project_id}/palette-renders", json=body)


def test_palette_render_can_only_be_generated_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_render_service, "OpenRouterGateway", lambda *a, **k: CapturingGateway())
    client, project_id = _client(tmp_path, monkeypatch)

    first = _post(client, project_id)
    assert first.status_code == 201
    assert first.json()["already_generated"] is False
    assert len(first.json()["results"]) == 3

    second = _post(client, project_id)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "palette_already_generated"


def test_total_failure_does_not_lock_and_allows_retry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_render_service, "OpenRouterGateway", lambda *a, **k: FailingGateway())
    client, project_id = _client(tmp_path, monkeypatch)

    failed = _post(client, project_id)
    assert failed.status_code == 201
    assert all(r["status"] == "failed" for r in failed.json()["results"])

    # 全部失敗未鎖定:再次請求不會 409(仍走生成路徑)。
    retry = _post(client, project_id)
    assert retry.status_code == 201


def test_unconfigured_openrouter_reports_503(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ROOMPILOT_GENPIC_PALETTE_MODEL", raising=False)
    client, project_id = _client(tmp_path, monkeypatch)
    resp = _post(client, project_id)
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "openrouter_api_key_not_configured"


def test_missing_reference_png_is_422(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_render_service, "OpenRouterGateway", lambda *a, **k: CapturingGateway())
    client, project_id = _client(tmp_path, monkeypatch)
    resp = _post(client, project_id, room={"room_id": "living-1", "room_label": "客廳"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "reference_png_required"
