"""第 8 步內建生圖供應者的轉接層測試（2026-07 盤點第 10 項修復）。

不打真實 OpenRouter——網路縫（render_providers._post_openrouter）以假回應
取代，驗證整條轉接鏈：payload 驗證與去識別化（沿用 render_service）→
prompt 組裝 → 參考圖驗證 → 回圖解析 → 入庫 PROJECT_STORE → 回傳
completed＋preview_url（前端首回即顯示）。

金鑰紀律：測試自行設定假的 OPENROUTER_API_KEY，結束即還原；
不讀、不印任何真實金鑰。
"""
from __future__ import annotations

import base64
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.server import main as server_main
from backend.server import render_providers

client = TestClient(server_main.app)


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 12), "beige").save(buffer, format="PNG")
    return buffer.getvalue()


def _png_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(_png_bytes()).decode()


def _camera() -> dict:
    return {"position_cm": [420, 165, 380], "target_cm": [210, 120, 190], "fov_deg": 52}


def _payload(project_id: str, mode: str = "palette_comparison") -> dict:
    payload = {
        "schema_version": "1.0",
        "mode": mode,
        "project_id": project_id,
        "scene_version": "scene-1:revision-3:card-1",
        "style_card_ids": ["card-1", "card-2"],
        "style_packs": [
            {"card_id": "card-1", "name": "北歐奶油風", "palette_hex": ["#F5EFE6", "#D8C3A5"],
             "wall": "暖白乳膠漆", "floor": "淺橡木超耐磨木地板", "lighting": "3000K 間接光"},
            {"card_id": "card-2", "name": "現代深色風", "palette_hex": ["#2E2E2E"]},
        ],
        "scene": {"scene_id": "scene-1", "scene_objects": []},
        "locks": {"furniture": True, "structure": True, "surfaces": True, "style_card_id": "card-1"},
        "requirements": {"basic": {"household": "兩大一小", "name": "Ada", "phone": "0900"}},
        "master_view": {"camera": _camera()},
        "room_views": [],
        "reference_png_data_url": _png_data_url(),
    }
    if mode == "room_final":
        payload["style_card_ids"] = ["card-1"]
        payload["room_views"] = [
            {"room_id": "living-1", "room_label": "客廳", "camera": _camera(),
             "reference_png_data_url": _png_data_url()},
            {"room_id": "bedroom-1", "room_label": "主臥", "camera": _camera()},  # 缺參考圖→退用主圖
        ]
    return payload


def _create_project() -> str:
    response = client.post("/api/projects", json={"name": f"生圖驗收-{uuid4().hex[:8]}"})
    assert response.status_code == 201
    return response.json()["project"]["project_id"]


@pytest.fixture()
def direct_provider(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    monkeypatch.delenv("ROOMPILOT_RENDER_IMAGE_DISABLED", raising=False)

    calls: list[dict] = []

    async def fake_post(body: dict, headers: dict) -> dict:
        calls.append({"body": body, "headers": headers})
        image_url = "data:image/png;base64," + base64.b64encode(_png_bytes()).decode()
        return {"choices": [{"message": {"images": [{"image_url": {"url": image_url}}]}}]}

    monkeypatch.setattr(render_providers, "_post_openrouter", fake_post)
    return calls


def test_palette_jobs_complete_synchronously_and_land_in_project_renders(direct_provider) -> None:
    project_id = _create_project()

    response = client.post(
        f"/api/projects/{project_id}/render-jobs", json=_payload(project_id)
    )

    assert response.status_code == 202
    jobs = response.json()["jobs"]
    assert len(jobs) == 2
    assert all(job["status"] == "completed" for job in jobs)
    assert {job["style_card_id"] for job in jobs} == {"card-1", "card-2"}

    # preview_url 必須真的可下載（回圖已入庫，與截圖成果同一清單）。
    preview = client.get(jobs[0]["preview_url"])
    assert preview.status_code == 200
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")

    listed = client.get(f"/api/projects/{project_id}/renders").json()["renders"]
    assert {record["provider"] for record in listed} == {"openrouter_image"}


def test_room_final_uses_per_room_reference_and_falls_back_to_master(direct_provider) -> None:
    project_id = _create_project()

    response = client.post(
        f"/api/projects/{project_id}/render-jobs",
        json=_payload(project_id, mode="room_final"),
    )

    assert response.status_code == 202
    jobs = response.json()["jobs"]
    assert [job["room_id"] for job in jobs] == ["living-1", "bedroom-1"]
    assert len(direct_provider) == 2, "每個房間各叫一次生圖"


def test_prompt_locks_structure_and_carries_style_language(direct_provider) -> None:
    project_id = _create_project()
    client.post(f"/api/projects/{project_id}/render-jobs", json=_payload(project_id))

    prompt = direct_provider[0]["body"]["messages"][0]["content"][0]["text"]
    assert "不得新增、刪除或移動" in prompt, "結構與家具鎖定必須進 prompt"
    assert "北歐奶油風" in prompt
    assert "淺橡木超耐磨木地板" in prompt
    # 去識別化沿用 render_service：姓名電話不得進 prompt 材料。
    assert "Ada" not in prompt
    assert "0900" not in prompt
    assert "兩大一小" in prompt, "家庭組成是設計脈絡，應保留"


def test_disabled_flag_restores_503_behavior(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    monkeypatch.setenv("ROOMPILOT_RENDER_IMAGE_DISABLED", "1")
    project_id = _create_project()

    response = client.post(
        f"/api/projects/{project_id}/render-jobs", json=_payload(project_id)
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "render_provider_not_configured"


def test_legacy_remote_url_still_takes_priority(monkeypatch, direct_provider) -> None:
    # 設了舊遠端 URL → 走原轉送契約（此處 URL 不可達 → 503 unreachable），
    # 內建生圖不得被呼叫。
    monkeypatch.setenv("ROOMPILOT_RENDER_PROVIDER_URL", "http://127.0.0.1:9")
    project_id = _create_project()

    response = client.post(
        f"/api/projects/{project_id}/render-jobs", json=_payload(project_id)
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "render_provider_unreachable"
    assert direct_provider == [], "舊契約優先時不得動用內建生圖"


def test_provider_status_reports_builtin_image_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    monkeypatch.delenv("ROOMPILOT_RENDER_IMAGE_DISABLED", raising=False)

    status = client.get("/api/render-provider/status").json()

    assert status["configured"] is True
    assert status["provider"].startswith("openrouter:")


def test_garbage_provider_response_is_rejected_not_stored(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    monkeypatch.delenv("ROOMPILOT_RENDER_IMAGE_DISABLED", raising=False)

    async def fake_post(body: dict, headers: dict) -> dict:
        return {"choices": [{"message": {"content": "抱歉，我無法生成圖片"}}]}

    monkeypatch.setattr(render_providers, "_post_openrouter", fake_post)
    project_id = _create_project()

    response = client.post(
        f"/api/projects/{project_id}/render-jobs", json=_payload(project_id)
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "image_provider_no_image_returned"
    assert client.get(f"/api/projects/{project_id}/renders").json()["renders"] == []
