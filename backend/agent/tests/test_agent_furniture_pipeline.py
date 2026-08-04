"""家具管線：RAG 候選 → 白名單選件 → engine 擺放。"""
import pytest

from backend.agent.documents import LayoutDoc
from backend.agent.skills.furniture import STRATEGIES, FurnitureSkill
from backend.agent.skills.requirements import RequirementSkill
from backend.agent.tools.base import ToolError
from backend.agent.tools.pick_furniture import PickFurnitureTool
from backend.agent.tools.rag_furniture import RagFurnitureTool
from backend.agent.tools.read_layout import ReadLayoutTool

from .conftest import FakeRetriever


@pytest.fixture
def layout(layout_json) -> LayoutDoc:
    return ReadLayoutTool().run(layout_json)


@pytest.fixture
def pipeline(layout, questionnaire):
    requirements = RequirementSkill(None).run(questionnaire, layout)
    skill = FurnitureSkill(None, rag_tool=RagFurnitureTool(FakeRetriever()))
    candidates = skill.build_candidates(requirements, layout)
    return requirements, skill, candidates


def test_rag_tool_builds_candidates_per_room(pipeline):
    _, _, candidates = pipeline
    assert set(candidates.by_room) == {"living", "bedroom"}
    assert all(rows for rows in candidates.by_room.values())
    assert all(len(rows) <= 8 for rows in candidates.by_room.values())
    assert candidates.retrieval["living"]["provider"] == "FakeRetriever"


def test_rag_tool_without_retriever_raises_readable_error(pipeline, layout):
    requirements, _, _ = pipeline
    with pytest.raises(ToolError) as excinfo:
        RagFurnitureTool(None).run(requirements, layout)
    assert "檢索器未接上" in excinfo.value.reason


def test_fallback_pick_covers_musts_and_assigns_hints(pipeline):
    requirements, skill, candidates = pipeline
    doc = skill.choose(requirements, candidates, strategy=STRATEGIES["A"])

    matched = {req_id for item in doc.items for req_id in item.matched_requirements}
    must_ids = {req.req_id for req in requirements.must_have()}
    assert must_ids <= matched, "每個硬需求都要被選件覆蓋"

    rugs = [item for item in doc.items if item.category == "rug"]
    assert rugs and rugs[0].hint.method == "overlay" and rugs[0].hint.anchor_item_id

    side_tables = [item for item in doc.items if item.category == "side_table"]
    if side_tables:
        assert side_tables[0].hint.method == "adjacent"


def test_selection_whitelist_rejects_unknown_catalog_id(pipeline):
    _, _, candidates = pipeline
    outcome = PickFurnitureTool().validate_selections(
        candidates,
        [
            {"room_id": "living", "catalog_id": "sofa-l"},
            {"room_id": "living", "catalog_id": "駭入的家具"},
            {"room_id": "bedroom", "catalog_id": "sofa-l"},  # 房間不符也要拒絕
        ],
        variant="A",
        strategy="測試",
    )
    assert len(outcome.doc.items) == 1
    assert len(outcome.rejected) == 2
    assert all("白名單" in row["reason"] for row in outcome.rejected)


def test_engine_places_furniture_inside_rooms(pipeline, layout):
    requirements, skill, candidates = pipeline
    doc = skill.choose(requirements, candidates, strategy=STRATEGIES["A"])
    scene = skill.place(layout, doc)

    reasons_seen = []
    for room in layout.rooms:
        placed = scene.placed_in(room.room_id)
        assert placed, f"{room.name} 應至少擺入一件家具"
        for row in placed:
            assert row["coordinate_unit"] == "cm"
            assert {"id", "type", "name", "width", "depth", "pos_x", "pos_y"} <= set(row)
            # 選件理由與擺位意圖必須帶進場景，供設計手冊引用
            assert {"reason", "hint_note"} <= set(row)
            assert 0 <= row["pos_x"] <= room.width_cm
            assert 0 <= row["pos_y"] <= room.depth_cm
            reasons_seen.append(row["reason"])
    assert any(r.strip() for r in reasons_seen), "至少一件家具應帶非空選件理由"
    # 主臥的床是硬需求，必須成功擺入
    bedroom_types = {row["type"] for row in scene.placed_in("bedroom")}
    assert "bed" in bedroom_types
