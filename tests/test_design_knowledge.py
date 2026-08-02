"""設計語彙知識庫的契約：鍵值對齊、來源完整、可信度不得灌水。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.server.engineering.design_knowledge import (
    JsonDesignKnowledgeRepository,
    validate_design_knowledge,
)
from backend.server.engineering.design_narrative import (
    DesignNarrativeService,
    StyleCardPaletteRepository,
    _relative_luminance,
)
from backend.server.engineering.models import ProjectSnapshot
from backend.server.scene_service import SPACE_DEFAULTS


PROJECT_DIR = Path(__file__).resolve().parents[1]
DESIGN_DIR = PROJECT_DIR / "backend" / "catalog" / "data" / "design"
STYLE_CARDS = PROJECT_DIR / "backend" / "catalog" / "data" / "taiwan_style_cards.json"


@pytest.fixture(scope="module")
def knowledge() -> JsonDesignKnowledgeRepository:
    return JsonDesignKnowledgeRepository(DESIGN_DIR)


def test_design_knowledge_passes_its_own_contract(knowledge) -> None:
    counts = validate_design_knowledge(knowledge)

    assert counts["styles"] > 0
    assert counts["room_principles"] > 0


def test_style_ids_match_the_shipped_style_cards(knowledge) -> None:
    cards = json.loads(STYLE_CARDS.read_text(encoding="utf-8"))
    card_style_ids = {style["style_id"] for style in cards["styles"]}
    vocabulary_ids = {item["style_id"] for item in knowledge.style_vocabulary()}

    # 語彙缺哪個風格，報告的設計章節就會在那個風格下開天窗。
    assert vocabulary_ids == card_style_ids


def test_room_types_match_the_canonical_space_defaults(knowledge) -> None:
    principle_types = {
        item["room_type"] for item in knowledge.room_design_principles()
    }

    assert principle_types == set(SPACE_DEFAULTS)


def test_internal_editorial_sources_cannot_claim_high_confidence(knowledge) -> None:
    sources = {item["source_id"]: item for item in knowledge.source_registry()}

    for record in knowledge.style_vocabulary():
        source = sources[record["source_id"]]
        if source.get("external_reference") is not True:
            assert record["confidence"] != "high", (
                f"{record['style_id']} 用內部編纂來源卻標成 high，"
                "報告會看起來有外部背書"
            )


def test_editorial_sources_declare_their_caveat(knowledge) -> None:
    for source in knowledge.source_registry():
        if source.get("source_type") == "internal_design_editorial":
            assert source.get("caveat_zh"), "內部編纂來源必須寫清楚適用界線"
            assert source.get("external_reference") is False


def test_validation_rejects_confidence_inflation(tmp_path: Path) -> None:
    for name in (
        "design_source_registry.json",
        "style_vocabulary.json",
        "color_strategy.json",
        "material_vocabulary.json",
        "room_design_principles.json",
    ):
        (tmp_path / name).write_text(
            (DESIGN_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    inflated = json.loads(
        (tmp_path / "style_vocabulary.json").read_text(encoding="utf-8")
    )
    inflated[0]["confidence"] = "high"
    (tmp_path / "style_vocabulary.json").write_text(
        json.dumps(inflated, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="high"):
        validate_design_knowledge(JsonDesignKnowledgeRepository(tmp_path))


def test_relative_luminance_orders_light_to_dark() -> None:
    assert _relative_luminance("#FFFFFF") == 1.0
    assert _relative_luminance("#000000") == 0.0
    assert _relative_luminance("#F3EBDD") > _relative_luminance("#8B684B")
    # 格式壞掉時回中間值，不能讓整份報告失敗。
    assert _relative_luminance("not-a-color") == 0.5


def _snapshot(**room_overrides) -> ProjectSnapshot:
    room = {
        "room_id": "r1",
        "name": "客廳",
        "room_type": "living_room",
        "style": "scandinavian",
        "geometry": {"length_cm": 500, "width_cm": 400, "height_cm": 280},
        "materials": [
            {"material_id": "m1", "part": "floor", "name": "超耐磨木地板"}
        ],
        "furniture": [
            {
                "furniture_id": "f1",
                "name": "三人沙發",
                "category": "sofa",
                "width_cm": 210,
                "depth_cm": 90,
                "height_cm": 80,
                "quantity": 2,
            }
        ],
    }
    room.update(room_overrides)
    return ProjectSnapshot(
        project_id="p1",
        project_name="測試案",
        revision="R1",
        source_project_revision=1,
        approval_status="designer_confirmed",
        confirmed_by="tester",
        pricing_basis_date="2026-08-02",
        rooms=[room],
    )


@pytest.fixture(scope="module")
def service(knowledge) -> DesignNarrativeService:
    return DesignNarrativeService(knowledge, StyleCardPaletteRepository(STYLE_CARDS))


def test_narrative_uses_the_selected_style_card_palette(service) -> None:
    narrative = service.generate(_snapshot(style_card_id="scandinavian_2"))

    assert narrative.style_id == "scandinavian"
    assert narrative.color.palette_source == "style_card"
    assert "scandinavian_2" in narrative.color.palette_source_detail
    roles = [role.role for role in narrative.color.roles]
    assert roles == ["dominant", "secondary", "accent"]
    # 主色必須是最淺的那個，這是知識庫的色卡判讀規則。
    luminance = [role.relative_luminance for role in narrative.color.roles]
    assert luminance == sorted(luminance, reverse=True)


def test_narrative_falls_back_to_style_default_palette_and_says_so(service) -> None:
    narrative = service.generate(_snapshot())

    assert narrative.color.palette_source == "style_default"
    assert "未記錄選定色卡" in narrative.color.palette_source_detail


def test_furniture_summary_is_snapshot_fact_not_invention(service) -> None:
    narrative = service.generate(_snapshot())

    summary = narrative.rooms[0].furniture_summary_zh
    assert "2 件" in summary, "數量必須反映快照的 quantity"
    assert "sofa 2 件" in summary


def test_unknown_style_degrades_without_inventing_vocabulary(service) -> None:
    narrative = service.generate(_snapshot(style="not-a-real-style"))

    assert narrative.style_id == "not-a-real-style"
    assert narrative.positioning_zh is None
    assert narrative.design_language_zh is None
    assert narrative.signature_elements_zh == []
    # 房型語彙仍在，因為那是依 room_type 而不是 style。
    assert narrative.rooms[0].knowledge_available is True


def test_unknown_room_type_is_flagged_rather_than_filled_in(service) -> None:
    narrative = service.generate(_snapshot(room_type="wine_cellar"))

    room = narrative.rooms[0]
    assert room.knowledge_available is False
    assert room.design_focus_zh is None
    assert room.furniture_summary_zh, "快照事實仍必須列出"


def test_evidence_declares_editorial_confidence(service) -> None:
    narrative = service.generate(_snapshot(style_card_id="scandinavian_1"))

    scopes = {item.scope: item for item in narrative.evidence}
    assert scopes["style"].confidence == "medium"
    assert scopes["snapshot"].confidence == "contractor_confirmed"
    # 色票數值來自專案色卡，可信度高於語彙本身。
    assert scopes["color"].confidence in {"high", "medium"}
    assert "medium confidence" in narrative.disclaimer_zh
