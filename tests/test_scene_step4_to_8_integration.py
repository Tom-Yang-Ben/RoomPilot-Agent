"""第 4→8 步跨步整合測試（指南 YEN_BELLA_INTEGRATION_GUIDE §6）。

以「至少三個 room id 不連續的房間」建構第 4-7 步完成後的 scene_json 與逐房 payload，
驗證第 8 步兩條生圖／成果線都嚴格以 room_id 分房：

- ``_placed_objects`` 逐房隔離：房間沒有自己的家具時回空，不得挪用他房家具
  （指南 §5／§3E；此函式同時餵給 ai-renders 生圖與 design-manual 成果 PDF）。
- ``/api/projects/{id}/ai-renders`` 逐房生圖：每房只用自己的家具與鎖定視角截圖，
  家具不跨房出現在同一張提示詞。
- 逐房各自一次改圖額度（指南 §3E：每房可在初圖後提出一次修改）。
- ``/api/projects/{id}/design-delivery`` 成果包：presentation／engineering 逐房只帶
  該 room_id 的家具與視角。
- 前端一鍵生圖對「所有」第 7 步鎖定視角逐房送圖，不截斷成第一房（指南 §3E）。

room id 刻意用 room-2 / room-7 / room-13（不連續），確保對應不是靠陣列位置或順序。
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.agent.llm import ImageResult, LLMError
from backend.server import ai_render_service, main
from backend.server.ai_render_service import _placed_objects, generate_room_images
from backend.server.project_store import ProjectStore

ROOT = Path(__file__).resolve().parents[1]

LIVING, BEDROOM, STUDY = "room-2", "room-7", "room-13"


def _png(color) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class _Gateway:
    """假 OpenRouter gateway：逐次記錄生圖提示詞，回傳固定 PNG。"""

    available = True
    image_model = "google/gemini-2.5-flash-image"
    image_fallback_model = "google/gemini-3-pro-image-preview"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def chat(self, messages, *, model=None, temperature=0.3, force_json=False) -> str:
        raise LLMError("測試環境不提供文字模型")

    def generate_image(self, prompt, *, images=(), model=None) -> ImageResult:
        self.prompts.append(prompt)
        buffer = io.BytesIO()
        Image.new("RGB", (24, 24), (210, 200, 180)).save(buffer, format="PNG")
        return ImageResult(
            image_b64=base64.b64encode(buffer.getvalue()).decode("ascii"),
            model=model or self.image_model,
        )


def _scene() -> dict:
    """三房 scene_json：LIVING 有沙發、BEDROOM 有床、STUDY 刻意沒有家具。"""
    return {
        "scene_id": "scene-step4-8",
        "requirement": {"style": "scandinavian"},
        "style_card": {
            "card_id": "scandinavian_1",
            "name_zh": "自然木質",
            "palette_hex": ["#F3EBDD", "#D3B48A"],
        },
        "design_choices": {"floor_option": "wood_oak"},
        "surface_catalog": {"surfaces": [{"surface_id": "wood_oak", "name_zh": "橡木地板"}]},
        "floorplan": {"width_cm": 420, "depth_cm": 380},
        # 逐房材質 override，key 為 room_id（非名稱／index）。
        "surface_overrides": [
            {"room_id": LIVING, "floor_option": "wood_oak", "wall_option": "warm_white"},
            {"room_id": BEDROOM, "floor_option": "carpet_grey", "wall_option": "sage"},
            {"room_id": STUDY, "floor_option": "tile_slate", "wall_option": "warm_white"},
        ],
        "scene_objects": [
            {
                "id": "sofa-1",
                "furniture_id": "sofa-1",
                "normalized_type": "sofa",
                "name_zh_raw": "北歐布沙發",
                "material": "亞麻布",
                "position_cm": {"x": -80, "z": 100},
                "size_cm": {"width": 210, "depth": 90, "height": 85},
                "placement_room_id": LIVING,
            },
            {
                "id": "bed-1",
                "furniture_id": "bed-1",
                "normalized_type": "bed",
                "name_zh_raw": "雙人床架",
                "material": "梣木",
                "position_cm": {"x": 120, "z": -60},
                "size_cm": {"width": 200, "depth": 210, "height": 45},
                "placement_room_id": BEDROOM,
            },
            {
                # 擺放失敗的物件不進任何房間畫面。
                "id": "bad-1",
                "furniture_id": "bad-1",
                "normalized_type": "cabinet",
                "name_zh_raw": "無法擺放的櫃",
                "placement_failed": True,
                "position_cm": {"x": 0, "z": 0},
                "size_cm": {"width": 10, "depth": 10},
                "placement_room_id": STUDY,
            },
        ],
    }


def _rooms_render() -> list[dict]:
    """逐房各自的第 7 步鎖定視角截圖（每房獨立 img2img 參考）。"""
    return [
        {
            "room_id": LIVING,
            "room_label": "客廳",
            "camera": {"preset": "full-room-v2-locked", "room_id": LIVING},
            "reference_png_data_url": _png((200, 180, 150)),
        },
        {
            "room_id": BEDROOM,
            "room_label": "主臥",
            "camera": {"preset": "full-room-v2-locked", "room_id": BEDROOM},
            "reference_png_data_url": _png((150, 160, 200)),
        },
        {
            "room_id": STUDY,
            "room_label": "書房",
            "camera": {"preset": "full-room-v2-locked", "room_id": STUDY},
            "reference_png_data_url": _png((160, 200, 160)),
        },
    ]


def _client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "step4-8"}).json()["project"]
    return client, project["project_id"]


def test_placed_objects_never_borrow_another_rooms_furniture() -> None:
    """核心迴歸：家具已分房時，視角房間沒有自己的家具就回空，不得挪用他房家具。

    舊 ``len(room_ids) <= 1`` 守衛在「只有一房有家具」時，會把那房的家具廣播給任何
    視角房間（指南 §5／§3E 禁止）。此函式同時餵給 ai-renders 與 design-manual。
    """
    single_tag = {
        "scene_objects": [
            {"id": "sofa-1", "name_zh_raw": "北歐布沙發", "placement_room_id": LIVING},
            {"id": "bad-1", "placement_failed": True, "placement_room_id": STUDY},
        ]
    }
    assert [obj["id"] for obj in _placed_objects(single_tag, LIVING)] == ["sofa-1"]
    # STUDY 沒有自己的家具 → 必須回空，不可拿 LIVING 的沙發。
    assert _placed_objects(single_tag, STUDY) == []

    # 完全未標記 placement_room_id（單房或未分房）才回全部家具。
    untagged = {"scene_objects": [{"id": "sofa-1", "name_zh_raw": "沙發"}]}
    assert [obj["id"] for obj in _placed_objects(untagged, STUDY)] == ["sofa-1"]


def test_ai_renders_keep_each_room_furniture_isolated() -> None:
    gateway = _Gateway()
    outcome = generate_room_images(_scene(), _rooms_render(), gateway=gateway)

    # 三個不連續 room id 都有逐房生圖結果。
    assert {row["room_id"] for row in outcome["results"]} == {LIVING, BEDROOM, STUDY}

    prompts = gateway.prompts
    # 每件家具只出現在自己房間的那一張提示詞，不跨房洩漏。
    assert sum("北歐布沙發" in prompt for prompt in prompts) == 1
    assert sum("雙人床架" in prompt for prompt in prompts) == 1
    # 沒有任何一張提示詞同時混入兩房的家具。
    assert all(
        not ("北歐布沙發" in prompt and "雙人床架" in prompt) for prompt in prompts
    )
    # 擺放失敗的家具不進任何畫面。
    assert all("無法擺放的櫃" not in prompt for prompt in prompts)


def test_each_locked_room_gets_its_own_single_revision(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ai_render_service, "OpenRouterGateway", lambda: _Gateway())
    client, project_id = _client(tmp_path, monkeypatch)

    generated = client.post(
        f"/api/projects/{project_id}/ai-renders",
        json={"project_id": project_id, "scene": _scene(), "rooms": _rooms_render()},
    )
    assert generated.status_code == 201, generated.text
    results = {row["room_id"]: row for row in generated.json()["results"]}
    assert set(results) == {LIVING, BEDROOM, STUDY}
    image = results[LIVING]["image_data_url"]

    # 每一房都能各自改一次圖（指南 §3E）。
    for room_id in (LIVING, BEDROOM, STUDY):
        edited = client.post(
            f"/api/projects/{project_id}/ai-renders/{room_id}/edit",
            json={"feedback": "微調燈光層次", "image_data_url": image},
        )
        assert edited.status_code == 201, (room_id, edited.text)

    # 同一房第二次改圖才被擋，且不影響其他房間的額度。
    again = client.post(
        f"/api/projects/{project_id}/ai-renders/{BEDROOM}/edit",
        json={"feedback": "再改一次", "image_data_url": image},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "ai_edit_budget_exhausted"


def test_design_delivery_packages_each_room_by_room_id(tmp_path, monkeypatch) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    snapshot = {
        "snapshot_id": "snap-1",
        "furniture": [
            {"furniture_id": "sofa-1", "name_zh": "北歐布沙發", "room_id": LIVING},
            {"furniture_id": "bed-1", "name_zh": "雙人床架", "room_id": BEDROOM},
        ],
    }
    rooms = [
        {
            "room_id": room_id,
            "room_name": name,
            "room_type": room_type,
            "view": {"camera": {"preset": "full-room-v2-locked", "room_id": room_id}},
        }
        for room_id, name, room_type in (
            (LIVING, "客廳", "living_room"),
            (BEDROOM, "主臥", "bedroom"),
            (STUDY, "書房", "study"),
        )
    ]
    resp = client.post(
        f"/api/projects/{project_id}/design-delivery",
        json={
            "project_id": project_id,
            "style_card": {"id": "scandinavian_1", "name": "自然木質"},
            "configuration_snapshot": snapshot,
            "rooms": rooms,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    presentation = {room["room_id"]: room for room in body["presentation"]["rooms"]}
    engineering = {room["room_id"]: room for room in body["engineering_report"]["rooms"]}

    # 三房 room_id 都在（不連續、順序無關）。
    assert set(presentation) == {LIVING, BEDROOM, STUDY}
    assert set(engineering) == {LIVING, BEDROOM, STUDY}

    # 逐房家具數只反映自己 room_id 的家具；STUDY 沒有家具。
    assert "1 件確認家具" in presentation[LIVING]["design_summary"]
    assert "1 件確認家具" in presentation[BEDROOM]["design_summary"]
    assert "0 件確認家具" in presentation[STUDY]["design_summary"]

    # 每房工程視角來自自己的 room_id。
    assert engineering[LIVING]["view"]["camera"]["room_id"] == LIVING
    assert engineering[BEDROOM]["view"]["camera"]["room_id"] == BEDROOM


def test_one_click_render_submits_every_locked_room() -> None:
    source = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")
    render_fn = source.split("async function runAiOpenrouterRender()", 1)[1].split(
        "\nasync function ", 1
    )[0]

    # 逐房生圖必須送出所有第 7 步鎖定視角，不得截斷成第一房（指南 §3E）。
    assert "lockedRoomViews()" in render_fn
    assert "const views = allViews;" in render_fn
    assert "allViews.slice(0, 1)" not in render_fn
