"""設計手冊組稿：九章、設計理念章引用選件理由、家具章印理由、輸出 PDF。

金額只在第九章報價單出現，其餘章節不帶價格。離線（gateway=None）走
deterministic 底稿，理由來源為 place_furniture 附進 placed row 的
reason／hint_note。"""
import re
from pathlib import Path

from backend.agent.documents import (
    DocKey,
    DocStore,
    ImageLibraryDoc,
    ImageRecord,
    LayoutDoc,
    LayoutRoom,
    RequirementDoc,
    SceneDoc,
)
from backend.agent.llm import DEFAULT_REPORT_MODEL
from backend.agent.skills.furniture import STRATEGIES, FurnitureSkill
from backend.agent.skills.report import ReportSkill, _looks_like_b64
from backend.agent.skills.requirements import RequirementSkill
from backend.agent.tools.rag_furniture import RagFurnitureTool
from backend.agent.tools.read_layout import ReadLayoutTool

from .conftest import FakeRetriever, make_png_b64


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
        "四、家具清單",
        "五、材質與色卡",
        "六、驗證與調整紀錄",
        "七、渲染成果",
        "八、工程與預算章節",
        "九、報價單",
    ]

    rationale = next(s for s in manual.sections if s.heading == "二、設計理念與亮點")
    # 至少一間房的理念段落出現，且含焦點/動線等原則措辭
    assert any(name in rationale.body for name in room_names)
    assert "焦點" in rationale.body and "動線" in rationale.body

    furniture = next(s for s in manual.sections if s.heading.startswith("四、"))
    assert "選件理由：" in furniture.body

    assert Path(manual.pdf_path).exists()
    assert Path(manual.pdf_path).read_bytes()[:4] == b"%PDF"


def test_money_only_appears_in_the_quote_chapter(tmp_path, layout_json, questionnaire):
    """金額（含屋主預算）只准出現在末章報價單，內文不被價格汙染。"""
    store, _ = _store_with_scene(layout_json, questionnaire)
    manual = ReportSkill(None).run(store, str(tmp_path / "manual.pdf"))

    amount = re.compile(r"\d[\d,]*\s*元")
    for section in manual.sections:
        if section.heading.startswith("九、"):
            continue
        assert not amount.search(section.body), f"{section.heading} 出現金額"


def test_quote_chapter_lists_units_subtotals_and_pending(
    tmp_path, layout_json, questionnaire
):
    store, _ = _store_with_scene(layout_json, questionnaire)
    manual = ReportSkill(None).run(store, str(tmp_path / "manual.pdf"))
    quote = next(s for s in manual.sections if s.heading == "九、報價單")

    assert "單價 18,900 元｜小計 18,900 元" in quote.body
    assert "已標價合計：" in quote.body
    assert f"屋主家具預算參考：{questionnaire['budget_total']:,} 元" in quote.body


def test_quote_marks_unpriced_items_as_pending_without_guessing():
    layout = LayoutDoc(
        rooms=[LayoutRoom(room_id="living", name="客廳", width_cm=420, depth_cm=360)]
    )
    scene = SceneDoc(variant="A")
    scene.rooms["living"] = {
        "placed": [
            {"id": "sofa_1", "name": "三人布沙發", "type": "sofa",
             "width": 180, "depth": 90, "price": 18900},
            {"id": "ct_1", "name": "訂製茶几", "type": "coffee_table",
             "width": 90, "depth": 50, "price": None},
        ],
        "failed": [],
    }
    section = ReportSkill(None)._quote_section(layout, scene, RequirementDoc())

    assert "訂製茶几 ×1｜90x50cm｜待報價" in section.body
    assert "已標價合計：約 18,900 元（1 件）" in section.body, "待報價品項不進合計"
    assert "待報價品項：1 件" in section.body


def test_render_section_shows_living_day_and_night_others_single():
    """客廳有夜間圖 → 日光＋夜間兩張都入手冊；其他房單圖、不加光影標籤。"""
    layout = LayoutDoc(
        rooms=[
            LayoutRoom(
                room_id="living", name="客廳", width_cm=420, depth_cm=360,
                room_type="living_room",
            ),
            LayoutRoom(room_id="bedroom", name="主臥", width_cm=360, depth_cm=300),
        ]
    )
    b64 = make_png_b64()
    images = ImageLibraryDoc(
        records=[
            ImageRecord(image_id="img_living_day", room_id="living",
                        stage="full_render", image_ref=b64, seq=1),
            ImageRecord(image_id="img_living_night", room_id="living",
                        stage="full_render_night", image_ref=b64, seq=2),
            ImageRecord(image_id="img_bedroom_day", room_id="bedroom",
                        stage="full_render", image_ref=b64, seq=3),
        ]
    )
    section, images_b64 = ReportSkill(None)._render_section(layout, images)

    # 客廳兩張圖都要引用並可進 PDF；臥室維持單圖
    assert section.image_ids == ["img_living_day", "img_living_night", "img_bedroom_day"]
    assert {"img_living_day", "img_living_night"} <= set(images_b64)
    # 有夜間圖才標日光/夜間；單圖房不加標籤
    assert "客廳（日光）：" in section.body and "客廳（夜間）：" in section.body
    assert "主臥：" in section.body and "主臥（" not in section.body


def test_report_agent_pins_gpt56_luna_model_with_reasoning():
    """結案報告的 LLM 呼叫一律用 openai/gpt-5.6-luna 並開 reasoning（不管測不測試）。"""

    class SpyGateway:
        available = True

        def __init__(self):
            self.calls = []

        def chat(self, messages, *, model=None, temperature=0.3, force_json=False, reasoning=None):
            self.calls.append({"model": model, "reasoning": reasoning})
            return '{"intro": "測試前言"}'

    spy = SpyGateway()
    layout = LayoutDoc(rooms=[LayoutRoom(room_id="living", name="客廳", width_cm=400, depth_cm=350)])
    section = ReportSkill(spy)._intro_section(RequirementDoc(styles=["日式"]), layout, SceneDoc())

    assert spy.calls, "報告前言應呼叫 LLM"
    assert spy.calls[0]["model"] == DEFAULT_REPORT_MODEL == "openai/gpt-5.6-luna"
    assert spy.calls[0]["reasoning"] == {"enabled": True}
    assert "測試前言" in section.body


def test_looks_like_b64_tolerates_slash_in_image_payload():
    """base64 字母表含「/」；PNG 內容常在開頭就出現，不可誤判成檔案路徑
    而把合法生圖漏出 PDF。路徑（含副檔名、磁碟機字母）仍須判否。"""
    assert _looks_like_b64("iVBORw0KGgo/" + "A/b+" * 100)
    assert not _looks_like_b64("C:/Users/demo/.tmp/agent_output/" + "img/" * 60 + "x.png")
    assert not _looks_like_b64(".tmp/agent_output/design_manual.pdf")
    assert not _looks_like_b64("iVBORw0KGgo=")  # 太短，不是完整影像內容
