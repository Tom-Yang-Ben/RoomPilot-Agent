"""依空間用途產生初步水電瓦斯需求，不取代技師設計與法規簽證。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def _item(
    utility: str,
    code: str,
    description: str,
    *,
    status: str = "required",
    confirmation: bool = False,
) -> dict[str, Any]:
    return {
        "utility": utility,
        "code": code,
        "description_zh": description,
        "status": status,
        "source": "room_type_rule",
        "confidence": 0.85 if status == "required" else 0.65,
        "requires_confirmation": confirmation,
    }


ROOM_REQUIREMENTS = {
    "living_room": [
        _item("electricity", "general_power", "一般插座與照明迴路"),
        _item("electricity", "media_data", "電視、網路與弱電位置", status="conditional", confirmation=True),
        _item("electricity", "air_conditioning", "空調專用電源與排水位置", status="conditional", confirmation=True),
    ],
    "kitchen": [
        _item("electricity", "appliance_power", "冰箱、排油煙機與烹調設備用電"),
        _item("electricity", "countertop_power", "檯面小家電插座"),
        _item("water", "hot_cold_water", "水槽冷熱給水"),
        _item("drainage", "sink_drainage", "水槽排水與存水彎位置"),
        _item("gas", "cooking_gas", "瓦斯烹調設備與安全通風", status="conditional", confirmation=True),
        _item("ventilation", "range_hood_exhaust", "排油煙機排氣路徑"),
    ],
    "bathroom": [
        _item("water", "hot_cold_water", "面盆與淋浴冷熱給水"),
        _item("drainage", "soil_waste_drainage", "馬桶、面盆、淋浴與地排"),
        _item("electricity", "leakage_protected_power", "潮濕區漏電保護用電與插座"),
        _item("ventilation", "bathroom_exhaust", "浴廁排風路徑"),
    ],
    "bedroom": [
        _item("electricity", "general_power", "床頭、一般插座與照明迴路"),
        _item("electricity", "air_conditioning", "空調專用電源與排水位置", status="conditional", confirmation=True),
    ],
    "storage": [
        _item("electricity", "workstation_power", "工作桌插座、網路與照明"),
    ],
    "balcony": [
        _item("water", "balcony_water", "清潔或洗衣給水", status="conditional", confirmation=True),
        _item("drainage", "balcony_drainage", "陽台地排或洗衣排水", status="conditional", confirmation=True),
        _item("electricity", "weather_protected_power", "戶外或洗衣設備用電", status="conditional", confirmation=True),
    ],
}


def infer_room_requirements(
    analysis: Mapping[str, Any],
    brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """由已辨識房間產生設計提問與初步設備需求。"""
    brief = dict(brief or {})
    observed_by_room: dict[str, list[dict[str, Any]]] = {}
    for observation in analysis.get("observed_utilities", []):
        observed_by_room.setdefault(str(observation.get("room_id", "")), []).append(dict(observation))
    confirmed_by_room: dict[str, list[dict[str, Any]]] = {}
    for confirmation in brief.get("utilities", []):
        confirmed_by_room.setdefault(str(confirmation.get("room_id", "")), []).append(dict(confirmation))

    rooms = []
    for room in analysis.get("rooms", []):
        room_type = str(room.get("type", "unknown"))
        room_id = str(room.get("id", ""))
        requirements = deepcopy(ROOM_REQUIREMENTS.get(room_type, []))
        for observation in observed_by_room.get(room_id, []):
            requirements.append(
                {
                    "utility": str(observation.get("utility", "unknown")),
                    "code": str(observation.get("code", "observed_utility")),
                    "description_zh": str(observation.get("description_zh", "圖面設備觀察")),
                    "status": "observed",
                    "source": "floorplan_observation",
                    "confidence": round(float(observation.get("confidence", 0.0)), 3),
                    "requires_confirmation": True,
                }
            )
        for confirmation in confirmed_by_room.get(room_id, []):
            code = str(confirmation.get("code", "confirmed_utility"))
            replacement = {
                "utility": str(confirmation.get("utility", "unknown")),
                "code": code,
                "description_zh": str(confirmation.get("description_zh", "使用者已確認設備需求")),
                "status": "confirmed" if confirmation.get("confirmed") else "rejected",
                "source": "user_confirmation",
                "confidence": 1.0,
                "requires_confirmation": False,
            }
            match = next((index for index, item in enumerate(requirements) if item["code"] == code), None)
            if match is None:
                requirements.append(replacement)
            else:
                requirements[match] = {**requirements[match], **replacement}
        rooms.append(
            {
                "room_id": room.get("id"),
                "room_type": room_type,
                "label": room.get("label"),
                "requirements": requirements,
            }
        )
    return {
        "schema_version": "1.0",
        "rooms": rooms,
        "brief_evidence": brief,
        "requires_professional_review": True,
        "disclaimer_zh": "本結果為提案階段需求盤點，施工前須由合格建築、機電與瓦斯專業人員確認。",
    }
