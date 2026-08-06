"""設計手冊組稿：八章、設計理念章引用選件理由、家具章印理由、輸出 PDF。

離線（gateway=None）走 deterministic 底稿，理由來源為 place_furniture 附進
placed row 的 reason／hint_note。"""
from pathlib import Path

from backend.agent.documents import DocKey, DocStore
from backend.agent.skills.furniture import STRATEGIES, FurnitureSkill
from backend.agent.skills.report import ReportSkill, _looks_like_b64
from backend.agent.skills.requirements import RequirementSkill
from backend.agent.tools.rag_furniture import RagFurnitureTool
from backend.agent.tools.read_layout import ReadLayoutTool

from .conftest import FakeRetriever


def _store_with_scene(layout_json, questionnaire) -> tuple[DocStore, list[str]]:
    layout = ReadLayoutTool().run(layout_json)
    requirements = RequirementSkill(None).run(questionnaire, layout)
    skill = FurnitureSkill(None, rag_tool=RagFurnitureTool(FakeRetriever()))
    candidates = skill.build_candidates(requirements, layout)
    doc = skill.choose(requirements, candidates, strategy=STRATEGIES["A"])
    scene = skill.place(layout, doc)

    store = DocStore()
    store.set(DocKey.REQUIREMENTS, requirements)
    store.set(DocKey.LAYOUT, layout)
    store.set(DocKey.variant(DocKey.SCENE, "A"), scene)
    room_names = [room.name for room in layout.rooms]
    return store, room_names


def test_manual_has_rationale_chapter_and_furniture_reasons(
    tmp_path, layout_json, questionnaire
):
    store, room_names = _store_with_scene(layout_json, questionnaire)
    manual = ReportSkill(None).run(store, str(tmp_path / "manual.pdf"))

    headings = [s.heading for s in manual.sections]
    assert headings == [
        "一、專案與需求摘要",
        "二、設計理念與亮點",
        "三、空間與平面配置",
        "四、家具清單與預算參考",
        "五、材質與色卡",
        "六、驗證與調整紀錄",
        "七、渲染成果",
        "八、工程與預算章節",
    ]

    rationale = next(s for s in manual.sections if s.heading == "二、設計理念與亮點")
    # 至少一間房的理念段落出現，且含焦點/動線等原則措辭
    assert any(name in rationale.body for name in room_names)
    assert "焦點" in rationale.body and "動線" in rationale.body

    furniture = next(s for s in manual.sections if s.heading.startswith("四、"))
    assert "選件理由：" in furniture.body

    assert Path(manual.pdf_path).exists()
    assert Path(manual.pdf_path).read_bytes()[:4] == b"%PDF"


def test_looks_like_b64_tolerates_slash_in_image_payload():
    """base64 字母表含「/」；PNG 內容常在開頭就出現，不可誤判成檔案路徑
    而把合法生圖漏出 PDF。路徑（含副檔名、磁碟機字母）仍須判否。"""
    assert _looks_like_b64("iVBORw0KGgo/" + "A/b+" * 100)
    assert not _looks_like_b64("C:/Users/demo/.tmp/agent_output/" + "img/" * 60 + "x.png")
    assert not _looks_like_b64(".tmp/agent_output/design_manual.pdf")
    assert not _looks_like_b64("iVBORw0KGgo=")  # 太短，不是完整影像內容
