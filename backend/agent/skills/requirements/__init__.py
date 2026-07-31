"""需求整理 skill：流程層。提示詞與 schema 見同資料夾 ``SKILL.md``。"""
from __future__ import annotations

import json
from pathlib import Path

from ...documents import LayoutDoc, PaletteOption, RequirementDoc, RequirementItem
from ...llm import LLMGateway
from ..base import ask_llm_json, load_skill_doc

DOC = load_skill_doc(Path(__file__).parent)
SPEC = DOC.spec("main")

APPLIANCE_KEYWORDS = (
    "冰箱",
    "洗衣機",
    "烘衣機",
    "乾衣機",
    "冷氣",
    "空調",
    "電視",
    "熱水器",
    "除濕機",
    "加濕器",
    "微波爐",
    "烤箱",
    "電鍋",
    "洗碗機",
    "電風扇",
    "冷凍櫃",
    "掃地機",
)

# 對齊 backend/spatial_data/rag 的 category_group 詞彙表。
KNOWN_CATEGORIES = {
    "sofa",
    "armchair",
    "dining_chair",
    "office_chair",
    "stool_bench",
    "coffee_table",
    "side_table",
    "dining_table",
    "desk",
    "bed",
    "storage",
    "wardrobe",
    "rug",
    "lighting",
    "mirror",
    "decor",
    "kids",
    "media",
    "partition",
}

# 中文需求描述 → category_group 的 deterministic 對照（fallback 與防線共用）。
CATEGORY_HINTS: list[tuple[str, str]] = [
    ("床頭櫃", "side_table"),
    ("邊几", "side_table"),
    ("茶几", "coffee_table"),
    ("餐桌", "dining_table"),
    ("餐椅", "dining_chair"),
    ("書桌", "desk"),
    ("辦公椅", "office_chair"),
    ("電腦椅", "office_chair"),
    ("衣櫃", "wardrobe"),
    ("衣櫥", "wardrobe"),
    ("電視櫃", "media"),
    ("視聽櫃", "media"),
    ("收納", "storage"),
    ("櫃", "storage"),
    ("沙發", "sofa"),
    ("單椅", "armchair"),
    ("扶手椅", "armchair"),
    ("床", "bed"),
    ("地毯", "rug"),
    ("燈", "lighting"),
    ("鏡", "mirror"),
    ("屏風", "partition"),
    ("凳", "stool_bench"),
]


def guess_category(text: str) -> str | None:
    for keyword, category in CATEGORY_HINTS:
        if keyword in text:
            return category
    return None


def is_appliance(text: str) -> bool:
    return any(keyword in text for keyword in APPLIANCE_KEYWORDS)


class RequirementSkill:
    spec = SPEC

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway

    def run(self, questionnaire: dict, layout: LayoutDoc) -> RequirementDoc:
        doc = self._base_doc(questionnaire)
        room_ids = {room.room_id for room in layout.rooms}
        llm_out = ask_llm_json(
            self._gateway,
            self.spec,
            self._user_prompt(questionnaire, layout),
            required=("hard", "soft", "appliances"),
        )
        if llm_out is not None:
            self._fill_from_llm(doc, llm_out, room_ids)
            doc.notes = str(llm_out.get("notes", ""))
            if llm_out.get("styles"):
                doc.styles = [str(s) for s in llm_out["styles"]][:3] or doc.styles
        else:
            self._fill_fallback(doc, questionnaire, room_ids)
        self._enforce_contracts(doc)
        return doc

    # -- 建構 --

    def _base_doc(self, questionnaire: dict) -> RequirementDoc:
        styles = questionnaire.get("styles") or []
        if not styles and questionnaire.get("style"):
            styles = [questionnaire["style"]]
        palettes = [
            PaletteOption(
                palette_id=str(row.get("palette_id", f"palette_{index + 1}")),
                name=str(row.get("name", f"色卡 {index + 1}")),
                colors=[str(c) for c in row.get("colors") or []],
            )
            for index, row in enumerate(questionnaire.get("palette_options") or [])
            if isinstance(row, dict)
        ]
        budget = questionnaire.get("budget_total")
        return RequirementDoc(
            styles=[str(s) for s in styles][:3],
            palette_options=palettes,
            budget_total=int(budget) if budget else None,
            materials=dict(questionnaire.get("materials") or {}),
            raw_answers=dict(questionnaire),
        )

    def _user_prompt(self, questionnaire: dict, layout: LayoutDoc) -> str:
        rooms = [{"room_id": room.room_id, "name": room.name} for room in layout.rooms]
        return (
            "房間清單：" + json.dumps(rooms, ensure_ascii=False) + "\n"
            "問卷答案：" + json.dumps(questionnaire, ensure_ascii=False)
        )

    def _fill_from_llm(self, doc: RequirementDoc, data: dict, room_ids: set[str]) -> None:
        for bucket, target in (("hard", doc.hard), ("soft", doc.soft), ("appliances", doc.appliances)):
            for row in data.get(bucket) or []:
                if not isinstance(row, dict) or not str(row.get("text", "")).strip():
                    continue
                room_id = row.get("room_id")
                target.append(
                    RequirementItem(
                        req_id="",
                        text=str(row["text"]).strip(),
                        room_id=room_id if room_id in room_ids else None,
                        category=row.get("category"),
                        quantity=max(1, int(row.get("quantity", 1) or 1)),
                        source="llm",
                    )
                )

    def _fill_fallback(
        self, doc: RequirementDoc, questionnaire: dict, room_ids: set[str]
    ) -> None:
        for row in questionnaire.get("rooms") or []:
            if not isinstance(row, dict):
                continue
            room_id = row.get("room_id")
            room_id = room_id if room_id in room_ids else None
            for text in row.get("furniture_needs") or []:
                text = str(text).strip()
                if not text:
                    continue
                bucket = doc.appliances if is_appliance(text) else doc.hard
                bucket.append(
                    RequirementItem(
                        req_id="",
                        text=text,
                        room_id=room_id,
                        category=guess_category(text),
                        source="questionnaire",
                    )
                )
            for text in row.get("appliances") or []:
                doc.appliances.append(
                    RequirementItem(
                        req_id="", text=str(text), room_id=room_id, source="questionnaire"
                    )
                )
            if row.get("notes"):
                doc.soft.append(
                    RequirementItem(
                        req_id="",
                        text=str(row["notes"]),
                        room_id=room_id,
                        source="questionnaire",
                    )
                )
        if questionnaire.get("extra_notes"):
            doc.soft.append(
                RequirementItem(
                    req_id="", text=str(questionnaire["extra_notes"]), source="questionnaire"
                )
            )
        for style in doc.styles:
            doc.soft.append(
                RequirementItem(req_id="", text=f"整體風格：{style}", source="questionnaire")
            )

    # -- 契約防線與收尾 --

    def _enforce_contracts(self, doc: RequirementDoc) -> None:
        kept_hard: list[RequirementItem] = []
        for item in doc.hard:
            if is_appliance(item.text):
                item.category = None
                doc.appliances.append(item)
                continue
            if item.category not in KNOWN_CATEGORIES:
                item.category = guess_category(item.text)
            kept_hard.append(item)
        doc.hard = kept_hard
        kept_soft: list[RequirementItem] = []
        for item in doc.soft:
            if is_appliance(item.text):
                doc.appliances.append(item)
            else:
                kept_soft.append(item)
        doc.soft = kept_soft
        for prefix, bucket in (("H", doc.hard), ("S", doc.soft), ("A", doc.appliances)):
            for index, item in enumerate(bucket, start=1):
                item.req_id = f"{prefix}{index}"
