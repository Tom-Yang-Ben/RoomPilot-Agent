from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


def test_initial_interview_replaces_the_visible_legacy_questionnaire() -> None:
    html = (STATIC_DIR / "scene.html").read_text(encoding="utf-8")

    assert 'id="first-meeting-questionnaire"' in html
    assert 'id="first-meeting-progress"' in html
    assert 'id="first-meeting-panel"' in html
    assert 'id="first-meeting-back"' in html
    assert 'id="first-meeting-next"' in html
    assert 'class="rp-questionnaire-workspace rp-legacy-questionnaire" hidden' in html
    assert "約 8–10 分鐘完成" in html


def test_first_meeting_requires_three_goals_two_likes_and_one_dislike() -> None:
    module_uri = (STATIC_DIR / "scene_first_meeting.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ firstMeetingReady, normalizeFirstMeeting }} from {json.dumps(module_uri)};

        const rooms = [
          {{ id: "living", label: "客廳" }},
          {{ id: "bedroom", label: "主臥" }},
        ];
        const meeting = normalizeFirstMeeting({{
          started: true,
          residents: {{ adults: 2 }},
          goalIds: ["circulation", "storage", "daylight"],
          priorityRoomIds: ["living"],
          budgetRange: "100–200 萬",
          targetTimeline: "3–6 個月",
          likedStylePackIds: ["pack-a", "pack-b"],
          dislikedStylePackId: "pack-c",
        }}, rooms);
        const ready = firstMeetingReady(meeting, rooms);
        const incomplete = firstMeetingReady({{
          ...meeting,
          likedStylePackIds: ["pack-a"],
          dislikedStylePackId: "",
        }}, rooms);
        console.log(JSON.stringify({{ meeting, ready, incomplete }}));
        """,
    )

    assert result["ready"]["ready"] is True
    assert result["incomplete"]["ready"] is False
    assert result["meeting"]["goalIds"] == ["circulation", "storage", "daylight"]
    assert result["meeting"]["priorityRoomIds"] == ["living"]


def test_first_meeting_discards_removed_rooms_and_limits_priorities() -> None:
    module_uri = (STATIC_DIR / "scene_first_meeting.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ normalizeFirstMeeting }} from {json.dumps(module_uri)};

        const meeting = normalizeFirstMeeting({{
          priorityRoomIds: ["a", "b", "missing", "c", "d"],
          roomNotes: {{ a: "A", b: "B", missing: "old", c: "C" }},
        }}, [{{ id: "a" }}, {{ id: "b" }}, {{ id: "c" }}, {{ id: "d" }}]);
        console.log(JSON.stringify(meeting));
        """,
    )

    assert result["priorityRoomIds"] == ["a", "b", "c"]
    assert result["roomNotes"] == {"a": "A", "b": "B", "c": "C"}


def test_first_meeting_is_saved_and_translated_only_on_confirmation() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    # 佇列 7 第六批：applyFirstMeetingToRequirements 純搬家到
    # scene_questionnaire_flow.js 工廠，確認時翻譯的本體改掃新檔；
    # 保存欄位與完成旗標的呼叫點仍在 scene_v2.js。
    flow = (STATIC_DIR / "scene_questionnaire_flow.js").read_text(encoding="utf-8")

    assert "firstMeetingStep: state.firstMeetingStep" in source
    assert "firstMeeting: state.firstMeeting" in source
    assert "function applyFirstMeetingToRequirements()" in flow
    assert "legacyBasicAnswersFromFirstMeeting(state.firstMeeting, STYLE_PACKS)" in flow
    assert 'state.visualCatalogVersion = "first-meeting-1.0"' in flow
    assert 'airConditioning: "designer-review"' in flow
    assert "firstMeetingConfirmed: true" in source
