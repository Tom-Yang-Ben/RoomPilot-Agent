"""辨識複核（review_items）必須有前端消費端與伺服器閘門。

背景：`spatial_report.py` 逐房產出「需人工複核」訊號，曾經整條沒有消費端。
這裡釘三件事：

1. 後端每個 `reason` 值都有對應的前端標籤——新增 reason 而未補標籤時要紅。
2. 第 4 步 UI 真的消費 review_items：模組被 import、容器存在、一鍵確認
   會跳過被標記的房間。
3. 伺服器閘門：workflow 宣告 space_confirmation 完成、卻仍有被標記房間
   未確認時，PUT /workflow 回 422 `recognition_review_unresolved`。
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.server.main import STATIC_DIR, app
from scripts.static_source_graph import scene_controller_source

client = TestClient(app)

SPATIAL_REPORT = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "floorplan"
    / "vision"
    / "spatial_report.py"
)


def _backend_reasons() -> set[str]:
    reasons: set[str] = set()
    for line in SPATIAL_REPORT.read_text(encoding="utf-8").splitlines():
        if '"reason"' not in line:
            continue
        for value in re.findall(r'"([a-z0-9_]+)"', line):
            if value != "reason":
                reasons.add(value)
    return reasons


def _frontend_labels() -> set[str]:
    source = (STATIC_DIR / "scene_recognition_review.js").read_text(encoding="utf-8")
    block = re.search(
        r"REVIEW_REASON_LABELS = Object\.freeze\(\{(.*?)\}\)", source, re.DOTALL
    )
    assert block, "scene_recognition_review.js 缺少 REVIEW_REASON_LABELS"
    return set(re.findall(r"^\s*([a-z0-9_]+):", block.group(1), re.MULTILINE))


def test_every_backend_review_reason_has_a_frontend_label() -> None:
    backend = _backend_reasons()
    assert backend, "解析不到後端 reason 值，代表這支測試的解析壞了"
    missing = backend - _frontend_labels()
    assert not missing, (
        f"後端新增了 review reason {sorted(missing)}，"
        "請在 backend/server/static/scene_recognition_review.js 補上對應標籤"
    )


def test_step_four_surfaces_review_items_in_the_recognition_summary() -> None:
    """目前第 4 步沒有複核清單區塊與逐間引導卡。

    仍必須保留的最小消費端：第 3 步辨識摘要要把「幾間房需人工複核」講出來，
    否則 spatial_report 的訊號整條沒有出口。

    已知缺口：一鍵確認**不再**跳過被標記的房間（confirmAllRooms 一律
    全確認）。伺服器閘門（下面四支測試）因此不會被觸發——它只在有房間未確認
    時才擋，而目前流程走到宣告完成時所有房間都已是 confirmed。
    """
    scene_v2 = scene_controller_source(STATIC_DIR)

    assert "./scene_recognition_review.js?v=sha256-" in scene_v2
    assert "unresolvedReviewRooms" in scene_v2
    assert "function recognitionReviewSuffix()" in scene_v2
    assert "系統標記 ${flagged} 間房需人工複核" in scene_v2
    assert "recognitionReviewSuffix()" in scene_v2

    confirm_all = re.search(
        r"function confirmAllRooms\(\) \{.*?\n\}", scene_v2, re.DOTALL
    )
    assert confirm_all, "confirmAllRooms 不存在"
    assert "unresolvedRecognitionReviewRooms" not in confirm_all.group(0), (
        "目前一鍵確認不做旗標房排除；若要改回排除，請一併恢復複核清單 UI"
    )


def _create_project() -> str:
    response = client.post("/api/projects", json={"name": "辨識複核閘門測試"})
    assert response.status_code == 201
    return response.json()["project"]["project_id"]


def _workflow(*, completed: bool, rooms: list[dict]) -> dict:
    steps = ["project", "upload", "recognition", "calibration"]
    if completed:
        steps.append("space_confirmation")
    return {
        "_flow": {"completed": steps},
        "recognition": {
            "spatial_report": {
                "review_items": [
                    {
                        "id": "room:room-1:label",
                        "category": "room_label",
                        "room_id": "room-1",
                        "reason": "room_label_icon_evidence_conflict",
                        "status": "needs_targeted_review",
                    }
                ]
            }
        },
        "space_confirmation": {
            "coordinate_unit": "cm",
            "schema_version": "2.0",
            "rooms": rooms,
            "structures": {
                "walls": [],
                "doors": [],
                "windows": [],
                "beams": [],
                "columns": [],
            },
        },
    }


def _put_workflow(project_id: str, workflow: dict):
    return client.put(
        f"/api/projects/{project_id}/workflow",
        json={"current_step": "space_confirmation", "workflow": workflow},
    )


def test_workflow_completion_claim_with_unreviewed_room_is_rejected() -> None:
    project_id = _create_project()
    response = _put_workflow(
        project_id,
        _workflow(
            completed=True,
            rooms=[{"id": "room-1", "label": "廚房", "confirmed": False}],
        ),
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "recognition_review_unresolved"
    assert detail["rooms"][0]["room_id"] == "room-1"
    assert detail["rooms"][0]["reason"] == "room_label_icon_evidence_conflict"


def test_workflow_completion_claim_passes_once_flagged_room_confirmed() -> None:
    project_id = _create_project()
    response = _put_workflow(
        project_id,
        _workflow(
            completed=True,
            rooms=[{"id": "room-1", "label": "廚房", "confirmed": True}],
        ),
    )
    assert response.status_code == 200


def test_deleted_flagged_room_counts_as_human_intervention() -> None:
    project_id = _create_project()
    response = _put_workflow(
        project_id,
        _workflow(
            completed=True,
            rooms=[{"id": "room-2", "label": "客廳", "confirmed": True}],
        ),
    )
    assert response.status_code == 200


def test_gate_only_applies_when_completion_is_claimed() -> None:
    project_id = _create_project()
    response = _put_workflow(
        project_id,
        _workflow(
            completed=False,
            rooms=[{"id": "room-1", "label": "廚房", "confirmed": False}],
        ),
    )
    assert response.status_code == 200
