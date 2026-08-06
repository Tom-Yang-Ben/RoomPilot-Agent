"""知識型 skill（interior_designer / interior_design_principles）與 design_knowledge tool。"""
from pathlib import Path

import backend.agent.skills as skills_pkg
from backend.agent.documents import CandidateListDoc, LayoutRoom, RequirementDoc, SceneDoc
from backend.agent.skills.furniture import STRATEGIES, FurnitureSkill
from backend.agent.tools.design_knowledge import (
    DesignKnowledgeTool,
    selection_digest,
    style_note,
)
from backend.agent.tools.genpic_info import GenPicInfoTool
from backend.agent.tools.rag_furniture import RagFurnitureTool


def test_knowledge_skill_folders_installed():
    base = Path(skills_pkg.__file__).parent
    for name in ("interior_design_principles", "interior_designer"):
        text = (base / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---"), f"{name}/SKILL.md 缺 frontmatter"
        assert f"name: {name.replace('_', '-')}" in text


def test_selection_digest_extracts_layout_principles():
    digest = selection_digest()
    assert "FOCAL POINT" in digest
    assert "TRAFFIC FLOW" in digest
    assert "SCALE AND PROPORTION" in digest


def test_style_note_maps_questionnaire_styles():
    note = style_note(["日式無印"])
    assert "MINIMALIST" in note
    assert "Materials:" in note and "Colors:" in note
    assert "SCANDINAVIAN" in style_note(["北歐風"])
    assert style_note(["火星未來風"]) == ""
    assert style_note([]) == ""


def test_tool_contract_run():
    out = DesignKnowledgeTool().run(styles=["工業風 loft"])
    assert "INDUSTRIAL" in out["style_note"]
    assert out["selection_digest"] == selection_digest()


def test_furniture_select_prompt_carries_design_digest():
    skill = FurnitureSkill(None, rag_tool=RagFurnitureTool(retriever=None))
    prompt = skill._select_prompt(RequirementDoc(), CandidateListDoc(), STRATEGIES["A"])
    assert "設計知識參考" in prompt
    assert "FOCAL POINT" in prompt
    assert "不得輸出座標" in prompt


def test_genpic_prompt_carries_style_note():
    requirements = RequirementDoc(styles=["日式無印"])
    room = LayoutRoom(room_id="living", name="客廳", width_cm=420, depth_cm=360)
    out = GenPicInfoTool().run(
        requirements, SceneDoc(), room, stage="palette_compare"
    )
    assert "整體風格：日式無印" in out["prompt"]
    assert "風格參考（MINIMALIST）" in out["prompt"]
    assert "。、，" not in out["prompt"]
    assert "不得增減或移動固定家具、牆、門、窗、樑或柱" in out["prompt"]
    # 對不上矩陣時不加行，不得出現空殼字樣
    plain = GenPicInfoTool().run(
        RequirementDoc(styles=["火星未來風"]), SceneDoc(), room, stage="palette_compare"
    )
    assert "風格參考" not in plain["prompt"]
