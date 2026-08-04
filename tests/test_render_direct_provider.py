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


def _camera(room_id: str = "living-1") -> dict:
    if room_id == "bedroom-1":
        return {"position_cm": [300, 165, 100], "target_cm": [200, 120, 0], "fov_deg": 52}
    return {"position_cm": [-80, 165, 100], "target_cm": [-180, 120, 0], "fov_deg": 52}


def _room_regions() -> list[dict]:
    return [
        {
            "room_id": "living-1",
            "label": "客廳",
            "room_type": "living_room",
            "exterior": [[-350, -150], [50, -150], [50, 150], [-350, 150]],
        },
        {
            "room_id": "bedroom-1",
            "label": "主臥",
            "room_type": "bedroom",
            "exterior": [[50, -150], [350, -150], [350, 150], [50, 150]],
        },
    ]


def _scene_objects() -> list[dict]:
    """模擬第 8 步定案後的 scene_objects（欄位名對齊 scene_service）。"""
    return [
        {
            "furniture_id": "f-1",
            "catalog_furniture_id": "IKEA-SOFA-001",
            "name_zh_raw": "三人座布沙發",
            "normalized_type": "sofa",
            "material": "亞麻布",
            "primary_style": "nordic",
            "price_twd": 28900,
            "size_cm": {"width": 210, "depth": 90, "height": 75},
            "position_cm": {"x": -150, "z": -130},
            "rotation_y_deg": 0,
            "placement_room_id": "living-1",
        },
        {
            "furniture_id": "f-2",
            "catalog_furniture_id": "IKEA-TV-014",
            "name_zh_raw": "低檯面電視櫃",
            "normalized_type": "tv-stand",
            "size_cm": {"width": 180, "depth": 40, "height": 45},
            "position_cm": {"x": -150, "z": 130},
            "rotation_y_deg": 180,
            "placement_room_id": "living-1",
        },
        {
            "furniture_id": "f-3",
            "catalog_furniture_id": "ABO-BED-777",
            "name_zh_raw": "雙人加大床架",
            "normalized_type": "bed",
            "size_cm": {"width": 180, "depth": 210, "height": 40},
            "position_cm": {"x": 200, "z": 0},
            "rotation_y_deg": 90,
            "placement_room_id": "bedroom-1",
        },
        {
            # 引擎放不下的品項不在截圖裡，列進 prompt 等於要模型畫出不存在的東西。
            "furniture_id": "f-4",
            "catalog_furniture_id": "IKEA-SHELF-909",
            "name_zh_raw": "頂天書櫃",
            "normalized_type": "bookcase",
            "size_cm": {"width": 80, "depth": 30, "height": 220},
            "position_cm": {"x": 0, "z": 0},
            "rotation_y_deg": 0,
            "placement_room_id": "living-1",
            "placement_failed": True,
            "placement_reason": "no_valid_position",
        },
    ]


def _requirements_digest() -> dict:
    """前端 renderRequirementsDigest() 的輸出形狀（標籤已解析成中文）。"""
    return {
        "schema_version": "1.0",
        "whole_house": {
            "household": "兩大一小",
            "members_and_pets": "有幼兒",
            "lifestyle": "常在家工作",
            "immutable_needs": "廚衛主排水不動",
            "wall": "暖白礦物漆 #F7F3EA",
            "floor": "淺橡木地板 #D9B985",
            "ceiling": "間接燈槽 #f4f1eb",
            "lighting": "崁燈",
            "render_details": [
                "間接光：以間接光為主要氛圍",
                "吊扇：不要吊扇",
                "廚房家電：嵌入櫃體隱藏",
            ],
        },
        "rooms": [
            {
                "room_id": "living-1",
                "room_label": "客廳",
                "wall": "柔霧石灰洗 #EDE5D8",
                "floor": "淺橡木地板 #D9B985",
                "ceiling": "線性燈天花",
                "lighting": "軌道燈",
                "air_conditioning": "壁掛式",
            },
            {
                "room_id": "bedroom-1",
                "room_label": "主臥",
                "wall": "暖白礦物漆 #F7F3EA",
                "floor": "深胡桃木地板",
                "ceiling": "平釘天花",
                "lighting": "吊燈",
                "air_conditioning": "隱藏式",
            },
        ],
    }


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
        "scene": {
            "scene_id": "scene-1",
            "floorplan": {"room_regions": _room_regions()},
            "scene_objects": _scene_objects(),
        },
        "locks": {"furniture": True, "structure": True, "surfaces": True, "style_card_id": "card-1"},
        "requirements": {
            "basic": {"household": "兩大一小", "name": "Ada", "phone": "0900"},
            "digest": _requirements_digest(),
        },
        "master_view": {"camera": _camera()},
        "room_views": [],
        "reference_png_data_url": _png_data_url(),
    }
    if mode == "room_final":
        payload["style_card_ids"] = ["card-1"]
        payload["room_views"] = [
            {"room_id": "living-1", "room_label": "客廳", "camera": _camera("living-1"),
             "reference_png_data_url": _png_data_url()},
            {"room_id": "bedroom-1", "room_label": "主臥", "camera": _camera("bedroom-1")},  # 缺參考圖→退用主圖
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


def test_prompt_enumerates_furniture_identity_so_model_cannot_hallucinate(
    direct_provider,
) -> None:
    project_id = _create_project()
    client.post(f"/api/projects/{project_id}/render-jobs", json=_payload(project_id))

    prompt = direct_provider[0]["body"]["messages"][0]["content"][0]["text"]
    # 身分：型號與名稱都要明文，模型才不會自行換一張沙發。
    assert "IKEA-SOFA-001" in prompt
    assert "三人座布沙發" in prompt
    assert "ABO-BED-777" in prompt
    # 位置：精確座標與角度必須附上。
    assert '"position_cm":{"x":-150,"z":-130}' in prompt
    assert '"rotation_deg":0' in prompt
    # 數量：明講件數，避免模型補一張椅子。
    assert "共 3 件" in prompt
    # 引擎放不下的品項不得出現在畫面描述裡。
    assert "頂天書櫃" not in prompt
    assert "IKEA-SHELF-909" not in prompt
    # 價格是報價資料，不是視覺條件。
    assert "28900" not in prompt


def test_room_final_prompt_carries_only_that_rooms_furniture(direct_provider) -> None:
    project_id = _create_project()
    client.post(
        f"/api/projects/{project_id}/render-jobs",
        json=_payload(project_id, mode="room_final"),
    )

    living, bedroom = (
        call["body"]["messages"][0]["content"][0]["text"] for call in direct_provider
    )
    assert "三人座布沙發" in living
    assert "雙人加大床架" not in living, "客廳那張不該帶主臥家具，逐房出圖才鎖得準"
    assert "雙人加大床架" in bedroom
    assert "三人座布沙發" not in bedroom


def test_locked_furniture_reports_wall_adjacency_from_engine_coordinates() -> None:
    prepared = render_providers.prepare_render_payload(_payload("p-1", mode="room_final"))

    items, truncated = render_providers.locked_furniture(
        prepared, {"room_id": "living-1"}
    )

    assert truncated == 0
    hints = {item["name"]: item["wall_hint"] for item in items}
    assert hints["三人座布沙發"] == "貼北側牆"  # z=-130，距 z 最小邊 20cm
    assert hints["低檯面電視櫃"] == "貼南側牆"  # z=130，距 z 最大邊 20cm
    bedroom_items, _ = render_providers.locked_furniture(
        prepared, {"room_id": "bedroom-1"}
    )
    assert bedroom_items[0]["wall_hint"] == "位於房間中央區域"


def test_furniture_lock_truncation_is_declared_not_silent(monkeypatch) -> None:
    monkeypatch.setattr(render_providers, "MAX_LOCKED_FURNITURE", 2)
    prepared = render_providers.prepare_render_payload(_payload("p-1"))

    items, truncated = render_providers.locked_furniture(prepared)
    prompt = render_providers.build_render_prompt(prepared, {"card_id": "card-1"})

    assert len(items) == 2
    assert truncated == 1
    assert "另有 1 件未列出" in prompt, "截斷必須寫進 prompt，不能無聲砍掉"


def test_prompt_survives_scene_without_furniture(direct_provider) -> None:
    project_id = _create_project()
    payload = _payload(project_id)
    payload["scene"] = {"scene_id": "scene-1", "scene_objects": []}

    response = client.post(f"/api/projects/{project_id}/render-jobs", json=payload)

    assert response.status_code == 202
    prompt = direct_provider[0]["body"]["messages"][0]["content"][0]["text"]
    assert "共 0 件" not in prompt
    assert "不得新增、刪除或移動" in prompt


def test_prompt_carries_questionnaire_visual_requirements(direct_provider) -> None:
    project_id = _create_project()
    client.post(f"/api/projects/{project_id}/render-jobs", json=_payload(project_id))

    prompt = direct_provider[0]["body"]["messages"][0]["content"][0]["text"]
    assert "需求問卷重點" in prompt
    # 材質、天花、燈具是 3D 場景表現不出來的軸，必須靠 prompt 表達。
    assert "暖白礦物漆" in prompt
    assert "間接燈槽" in prompt
    assert "崁燈" in prompt
    assert "有幼兒" in prompt
    assert "常在家工作" in prompt
    assert "廚衛主排水不動" in prompt
    # 全景模式帶所有房間。
    assert "客廳——" in prompt
    assert "主臥——" in prompt
    assert "壁掛式" in prompt


def test_prompt_carries_render_only_detail_choices(direct_provider) -> None:
    """天花分區、送風、吊扇這類軸 3D 場景畫不出來，只能靠 prompt 表達。"""
    project_id = _create_project()
    client.post(f"/api/projects/{project_id}/render-jobs", json=_payload(project_id))

    prompt = direct_provider[0]["body"]["messages"][0]["content"][0]["text"]
    assert "間接光：以間接光為主要氛圍" in prompt
    assert "吊扇：不要吊扇" in prompt
    assert "廚房家電：嵌入櫃體隱藏" in prompt
    # 使用者留白的軸前端不會送，prompt 也就不該憑空出現。
    assert "維修口" not in prompt
    assert "送風方式" not in prompt


def test_room_final_prompt_carries_only_that_rooms_requirements(direct_provider) -> None:
    project_id = _create_project()
    client.post(
        f"/api/projects/{project_id}/render-jobs",
        json=_payload(project_id, mode="room_final"),
    )

    living, bedroom = (
        call["body"]["messages"][0]["content"][0]["text"] for call in direct_provider
    )
    assert "線性燈天花" in living and "軌道燈" in living
    assert "平釘天花" not in living, "客廳那張不該帶主臥的天花方案"
    assert "平釘天花" in bedroom and "隱藏式" in bedroom
    assert "線性燈天花" not in bedroom
    # 全屋層級的需求兩張都要有。
    assert "廚衛主排水不動" in living and "廚衛主排水不動" in bedroom


def test_requirement_notes_never_carry_furniture_identity() -> None:
    """問卷說「想要什麼」，scene 說「實際擺了什麼」；後者才是畫面依據。"""
    prepared = render_providers.prepare_render_payload(_payload("p-1"))

    notes = "".join(render_providers.requirement_notes(prepared))

    assert "沙發" not in notes
    assert "IKEA-SOFA-001" not in notes


def test_prompt_survives_missing_or_malformed_digest(direct_provider) -> None:
    project_id = _create_project()
    payload = _payload(project_id)
    payload["requirements"]["digest"] = "not-a-dict"

    response = client.post(f"/api/projects/{project_id}/render-jobs", json=payload)

    assert response.status_code == 202
    prompt = direct_provider[0]["body"]["messages"][0]["content"][0]["text"]
    assert "需求問卷重點" not in prompt
    assert "不得新增、刪除或移動" in prompt


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


def test_one_failed_room_does_not_take_down_the_whole_batch(monkeypatch) -> None:
    """QA 2026-08-01 #7：逐房批次遇首個 502 即整批中止，成功的房間也一起消失。"""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ROOMPILOT_RENDER_PROVIDER_URL", raising=False)
    monkeypatch.delenv("ROOMPILOT_RENDER_IMAGE_DISABLED", raising=False)

    calls = {"count": 0}

    async def flaky_post(body: dict, headers: dict) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            return {"choices": [{"message": {"content": "抱歉，我無法生成圖片"}}]}
        image_url = "data:image/png;base64," + base64.b64encode(_png_bytes()).decode()
        return {"choices": [{"message": {"images": [{"image_url": {"url": image_url}}]}}]}

    monkeypatch.setattr(render_providers, "_post_openrouter", flaky_post)
    project_id = _create_project()

    response = client.post(
        f"/api/projects/{project_id}/render-jobs",
        json=_payload(project_id, mode="room_final"),
    )

    assert response.status_code == 202, response.text
    body = response.json()
    by_room = {job["room_id"]: job for job in body["jobs"]}
    assert by_room["living-1"]["status"] == "failed"
    assert by_room["living-1"]["message_zh"]
    assert by_room["bedroom-1"]["status"] == "completed"
    assert body["failed_count"] == 1
    # 成功的那張必須真的入庫，不能跟著失敗一起消失。
    assert len(client.get(f"/api/projects/{project_id}/renders").json()["renders"]) == 1
