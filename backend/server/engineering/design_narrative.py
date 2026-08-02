"""從鎖定版快照與設計語彙知識庫組出設計論述。

沿用 :class:`TemplateNarrativeService` 的原則：不讓語言模型發明事實。風格語彙
來自版本化知識庫，數字與品項來自快照，兩者交會處只做決定性的檢索與組裝。
知識庫查不到就如實標記 ``knowledge_available=false``，不憑空補寫。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .design_knowledge import JsonDesignKnowledgeRepository
from .models import (
    ColorNarrative,
    DesignEvidence,
    DesignNarrative,
    MaterialNarrative,
    PaletteRole,
    ProjectSnapshot,
    RoomDesignNarrative,
    RoomSnapshot,
)


DISCLAIMER_ZH = (
    "設計論述為風格說明與溝通用途，屬團隊編纂的設計語彙（medium confidence），"
    "非法規、標準或第三方權威依據。文中面積、數量與品項均取自鎖定版快照。"
)

# 相對亮度係數（ITU-R BT.709 luma），用來把色票由淺到深排序。
_LUMA_COEFFICIENTS = (0.2126, 0.7152, 0.0722)

_ROLE_USAGE_ZH = {
    "dominant": "主色：牆面與天花等最大面積",
    "secondary": "次色：地坪、主要櫃體與家具量體",
    "accent": "點綴色：軟裝織品與單一重點元素",
}


def _relative_luminance(hex_color: str) -> float:
    """回傳 0（最深）到 1（最淺）的相對亮度；格式不合法時回 0.5。"""
    value = (hex_color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) != 6:
        return 0.5
    try:
        channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    except ValueError:
        return 0.5
    return round(
        sum(
            coefficient * channel
            for coefficient, channel in zip(_LUMA_COEFFICIENTS, channels)
        ),
        4,
    )


class StyleCardPaletteRepository:
    """從既有色卡資料取得 palette_hex；這是色票數值的唯一來源。"""

    def __init__(self, style_cards_path: Path) -> None:
        self.style_cards_path = style_cards_path
        self._by_card: dict[str, list[str]] | None = None
        self._by_style: dict[str, tuple[str, list[str]]] | None = None

    def _load(self) -> None:
        if self._by_card is not None:
            return
        by_card: dict[str, list[str]] = {}
        by_style: dict[str, tuple[str, list[str]]] = {}
        try:
            payload = json.loads(self.style_cards_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # 色卡讀不到不能讓整份報告失敗；色彩章節會標成 unavailable。
            self._by_card, self._by_style = {}, {}
            return
        for style in payload.get("styles") or []:
            style_id = style.get("style_id")
            for index, card in enumerate(style.get("cards") or []):
                palette = [str(value) for value in card.get("palette_hex") or []]
                card_id = str(card.get("card_id") or "")
                if card_id:
                    by_card[card_id] = palette
                if style_id and index == 0:
                    by_style[style_id] = (card_id, palette)
        self._by_card, self._by_style = by_card, by_style

    def palette_for_card(self, card_id: str | None) -> list[str] | None:
        self._load()
        if not card_id:
            return None
        return (self._by_card or {}).get(card_id)

    def default_palette_for_style(
        self, style_id: str | None
    ) -> tuple[str, list[str]] | None:
        self._load()
        if not style_id:
            return None
        return (self._by_style or {}).get(style_id)


class DesignNarrativeService:
    def __init__(
        self,
        knowledge: JsonDesignKnowledgeRepository,
        palettes: StyleCardPaletteRepository,
    ) -> None:
        self.knowledge = knowledge
        self.palettes = palettes

    def generate(self, snapshot: ProjectSnapshot) -> DesignNarrative:
        style_id, resolution = self._resolve_style(snapshot)
        style = self.knowledge.style_entry(style_id)
        evidence: list[DesignEvidence] = [
            DesignEvidence(
                source_id="SRC-DESIGN-SNAPSHOT-GEOMETRY",
                scope="snapshot",
                confidence="contractor_confirmed",
                caveat_zh="面積、數量與品項取自鎖定版快照。",
            )
        ]
        if style is not None:
            evidence.append(
                DesignEvidence(
                    source_id=style["source_id"],
                    scope="style",
                    confidence=style.get("confidence", "medium"),
                    caveat_zh="風格語彙為團隊編纂，非外部權威引用。",
                )
            )

        color = self._build_color(snapshot, style_id, evidence)
        material = self._build_material(snapshot, style_id, evidence)
        rooms = [self._build_room(room, evidence) for room in snapshot.rooms]

        return DesignNarrative(
            style_id=style_id,
            style_name_zh=(style or {}).get("style_name_zh"),
            style_resolution_zh=resolution,
            positioning_zh=(style or {}).get("positioning_zh"),
            design_language_zh=(style or {}).get("design_language_zh"),
            signature_elements_zh=list((style or {}).get("signature_elements_zh") or []),
            form_vocabulary_zh=dict((style or {}).get("form_vocabulary_zh") or {}),
            lighting_approach_zh=(style or {}).get("lighting_approach_zh"),
            avoid_zh=list((style or {}).get("avoid_zh") or []),
            color=color,
            material=material,
            rooms=rooms,
            evidence=self._dedupe_evidence(evidence),
            disclaimer_zh=DISCLAIMER_ZH,
        )

    def _resolve_style(self, snapshot: ProjectSnapshot) -> tuple[str | None, str]:
        """全屋風格取各房眾數；平手時取第一個出現的，並如實說明判定方式。"""
        styles = [room.style for room in snapshot.rooms if room.style]
        if not styles:
            return None, "快照未帶風格設定，設計論述只能提供逐房事實摘要。"
        counts = Counter(styles)
        top_count = max(counts.values())
        winners = [style for style in styles if counts[style] == top_count]
        style_id = winners[0]
        if len(set(styles)) == 1:
            return style_id, f"全屋 {len(snapshot.rooms)} 個空間皆採同一風格設定。"
        return (
            style_id,
            f"{len(snapshot.rooms)} 個空間中有 {top_count} 個採用此風格，"
            f"以多數決作為全屋定位；其餘空間的個別風格仍列於逐房說明。",
        )

    def _build_color(
        self,
        snapshot: ProjectSnapshot,
        style_id: str | None,
        evidence: list[DesignEvidence],
    ) -> ColorNarrative | None:
        strategy = self.knowledge.color_entry(style_id)
        card_id = next(
            (room.style_card_id for room in snapshot.rooms if room.style_card_id),
            None,
        )
        palette = self.palettes.palette_for_card(card_id)
        if palette:
            source, detail = "style_card", f"第 5 步選定色卡 {card_id}"
        else:
            fallback = self.palettes.default_palette_for_style(style_id)
            if fallback and fallback[1]:
                palette = fallback[1]
                source = "style_default"
                detail = (
                    f"快照未記錄選定色卡，採 {style_id} 的預設色卡 {fallback[0]}"
                )
            else:
                palette, source, detail = [], "unavailable", "查無可用色票"
        if palette:
            evidence.append(
                DesignEvidence(
                    source_id="SRC-DESIGN-CATALOG-STYLE-CARDS",
                    scope="color",
                    confidence="high",
                    caveat_zh="色票數值取自專案色卡資料，未另行發明顏色。",
                )
            )
        if strategy is not None:
            evidence.append(
                DesignEvidence(
                    source_id=strategy["source_id"],
                    scope="color",
                    confidence=strategy.get("confidence", "medium"),
                )
            )
        if not palette and strategy is None:
            return None

        distribution = (strategy or {}).get("distribution_zh") or {}
        return ColorNarrative(
            palette_hex=palette,
            palette_source=source,
            palette_source_detail=detail,
            roles=self._assign_roles(palette),
            dominant_ratio=distribution.get("dominant_ratio"),
            secondary_ratio=distribution.get("secondary_ratio"),
            accent_ratio=distribution.get("accent_ratio"),
            temperature_zh=(strategy or {}).get("temperature_zh"),
            value_contrast_zh=(strategy or {}).get("value_contrast_zh"),
            saturation_ceiling_zh=(strategy or {}).get("saturation_ceiling_zh"),
            reading_rule_zh=(strategy or {}).get("reading_rule_zh"),
        )

    @staticmethod
    def _assign_roles(palette: list[str]) -> list[PaletteRole]:
        """由淺到深指派主／次／點綴，對應知識庫的色卡判讀規則。"""
        if not palette:
            return []
        ordered = sorted(
            palette, key=_relative_luminance, reverse=True
        )
        roles: list[PaletteRole] = []
        for index, hex_color in enumerate(ordered):
            if index == 0:
                role = "dominant"
            elif index == len(ordered) - 1 and len(ordered) > 2:
                role = "accent"
            else:
                role = "secondary"
            roles.append(
                PaletteRole(
                    hex=hex_color,
                    role=role,
                    relative_luminance=_relative_luminance(hex_color),
                    usage_zh=_ROLE_USAGE_ZH[role],
                )
            )
        return roles

    def _build_material(
        self,
        snapshot: ProjectSnapshot,
        style_id: str | None,
        evidence: list[DesignEvidence],
    ) -> MaterialNarrative | None:
        vocabulary = self.knowledge.material_entry(style_id)
        selected = sorted(
            {
                selection.name
                for room in snapshot.rooms
                for selection in room.materials
                if selection.name
            }
        )
        if vocabulary is None and not selected:
            return None
        if vocabulary is not None:
            evidence.append(
                DesignEvidence(
                    source_id=vocabulary["source_id"],
                    scope="material",
                    confidence=vocabulary.get("confidence", "medium"),
                )
            )
        return MaterialNarrative(
            primary_materials_zh=list((vocabulary or {}).get("primary_materials_zh") or []),
            secondary_materials_zh=list(
                (vocabulary or {}).get("secondary_materials_zh") or []
            ),
            finish_rule_zh=(vocabulary or {}).get("finish_rule_zh"),
            contrast_logic_zh=(vocabulary or {}).get("contrast_logic_zh"),
            floor_wall_relationship_zh=(vocabulary or {}).get(
                "floor_wall_relationship_zh"
            ),
            avoid_combinations_zh=list(
                (vocabulary or {}).get("avoid_combinations_zh") or []
            ),
            selected_materials_zh=selected,
        )

    def _build_room(
        self, room: RoomSnapshot, evidence: list[DesignEvidence]
    ) -> RoomDesignNarrative:
        principles = self.knowledge.room_entry(room.room_type)
        if principles is not None:
            evidence.append(
                DesignEvidence(
                    source_id=principles["source_id"],
                    scope="room",
                    confidence=principles.get("confidence", "medium"),
                )
            )
        return RoomDesignNarrative(
            room_id=room.room_id,
            room_name=room.name,
            room_type=room.room_type,
            room_name_zh=(principles or {}).get("room_name_zh"),
            design_focus_zh=(principles or {}).get("design_focus_zh"),
            circulation_zh=(principles or {}).get("circulation_zh"),
            lighting_zh=(principles or {}).get("lighting_zh"),
            storage_zh=(principles or {}).get("storage_zh"),
            common_pitfalls_zh=list((principles or {}).get("common_pitfalls_zh") or []),
            furniture_summary_zh=self._furniture_summary(room),
            applied_materials_zh=[
                f"{_PART_LABELS.get(selection.part, selection.part)}：{selection.name}"
                for selection in room.materials
            ],
            knowledge_available=principles is not None,
        )

    @staticmethod
    def _furniture_summary(room: RoomSnapshot) -> str:
        """逐房家具摘要，全部是快照事實，不含建議語言。"""
        if not room.furniture:
            return "此空間未配置家具。"
        total = sum(item.quantity for item in room.furniture)
        by_category: Counter[str] = Counter()
        for item in room.furniture:
            by_category[item.category] += item.quantity
        breakdown = "、".join(
            f"{category} {count} 件" for category, count in by_category.most_common()
        )
        failed = [item for item in room.furniture if item.placement_failed]
        summary = f"共配置 {total} 件家具（{breakdown}）。"
        if failed:
            summary += f" 其中 {len(failed)} 項未能完成擺放，已列入風險章節。"
        return summary

    @staticmethod
    def _dedupe_evidence(evidence: list[DesignEvidence]) -> list[DesignEvidence]:
        seen: set[tuple[str, str]] = set()
        unique: list[DesignEvidence] = []
        for item in evidence:
            key = (item.source_id, item.scope)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique


_PART_LABELS = {
    "floor": "地坪",
    "wall": "牆面",
    "ceiling": "天花",
    "other": "其他",
}
