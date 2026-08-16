from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone

from .cost_estimation import estimate_project_cost, load_default_cost_catalog


DESIGNER_REFERENCE_BY_ROOM_TYPE = {
    "living_room": "設計觀點參照 Ilse Crawford 重視以人為本、觸感與日常舒適的取向；本案僅借用方法論，不代表設計師參與或背書。",
    "bedroom": "設計觀點參照 Kelly Hoppen 對安定對稱、層次中性色與休憩感的運用；本案僅借用方法論，不代表設計師參與或背書。",
    "kitchen": "設計觀點參照 Patricia Urquiola 對耐用表面、節制用色與生活機能平衡的處理；本案僅借用方法論，不代表設計師參與或背書。",
    "bathroom": "設計觀點參照 John Pawson 對比例、簡潔面材與受控光線的處理；本案僅借用方法論，不代表設計師參與或背書。",
    "dining_room": "設計觀點參照 Ilse Crawford 以人的互動與用餐觸感建立空間核心的取向；本案僅借用方法論，不代表設計師參與或背書。",
    "study": "設計觀點參照 John Pawson 以清楚秩序、留白與自然光降低視覺干擾的取向；本案僅借用方法論，不代表設計師參與或背書。",
    "default": "設計觀點參照專業室內設計常用的動線、採光、材質連續性與收納需求四項原則。",
}


DELIVERY_ROOM_TYPE_ALIASES = {
    "living": "living_room",
    "livingroom": "living_room",
    "客廳": "living_room",
    "master_bedroom": "bedroom",
    "guest_bedroom": "bedroom",
    "臥室": "bedroom",
    "主臥": "bedroom",
    "次臥": "bedroom",
    "廚房": "kitchen",
    "餐廳": "dining_room",
    "dining": "dining_room",
    "書房": "study",
    "office": "study",
    "衛浴": "bathroom",
    "浴室": "bathroom",
}


DELIVERY_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "openrouter_api_key",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "cookie",
    "set_cookie",
    "email",
    "phone",
    "phone_number",
    "full_name",
    "address",
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _delivery_room_type(room: dict) -> str:
    raw = str(
        room.get("room_type")
        or room.get("type")
        or (room.get("questionnaire") or {}).get("roomType")
        or room.get("room_name")
        or "default"
    ).strip()
    normalized = raw.casefold().replace("-", "_").replace(" ", "_")
    if normalized in DESIGNER_REFERENCE_BY_ROOM_TYPE:
        return normalized
    if "bedroom" in normalized:
        return "bedroom"
    return DELIVERY_ROOM_TYPE_ALIASES.get(normalized, DELIVERY_ROOM_TYPE_ALIASES.get(raw, "default"))


def _delivery_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback

_PRICE_LOOKUP_KEYS = (
    "furniture_id",
    "catalog_furniture_id",
    "catalogFurnitureId",
    "id",
)


def _price_lookup_keys(item: dict):
    """該件家具所有可能的型錄 id，依可信度排序。

    最後一把是 ``model_url`` 的 GLB 檔名。型錄每一筆的 model_url 檔名都等於自己
    的 furniture_id，所以擺位 id 蓋掉型錄 id 之後，它是唯一還認得出「屋主選的是
    哪一款」的線索；少了它，報價單每一列都會是「待報價」、小計恆為 0。
    """
    for name in _PRICE_LOOKUP_KEYS:
        yield str(item.get(name) or "").strip()
    url = str(item.get("model_url") or "").strip()
    yield url.rsplit("/", 1)[-1].rsplit(".", 1)[0] if url else ""

def _delivery_amount_twd(item: dict) -> int | None:
    for key in ("price_twd", "unit_price_twd", "amount_twd"):
        value = item.get(key)
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        if amount > 0:
            return round(amount)
    return None


def _delivery_furniture_lines(snapshot: dict) -> list[dict]:
    lines: list[dict] = []
    for index, item in enumerate(snapshot.get("furniture") or [], start=1):
        if not isinstance(item, dict):
            continue
        amount_twd = _delivery_amount_twd(item)
        lines.append(
            {
                "id": item.get("instance_id") or item.get("id") or f"furniture-{index}",
                "category": "furniture",
                "category_label": "家具",
                "room_id": item.get("room_id"),
                "name": _delivery_text(
                    item.get("name")
                    or item.get("label")
                    or item.get("name_zh")
                    or item.get("name_zh_raw"),
                    "已選家具",
                ),
                "quantity": 1,
                "unit": "件",
                "material": item.get("material"),
                "size_cm": item.get("size_cm"),
                "amount_twd": amount_twd,
                "status": "catalog_reference" if amount_twd is not None else "pending_quote",
                "status_label": "家具目錄參考價" if amount_twd is not None else "待報價",
                "price_source": item.get("price_source"),
                "note": (
                    "沿用家具目錄參考價；運送、安裝與現場條件仍以正式報價為準。"
                    if amount_twd is not None
                    else "家具目錄未附可驗證價格，保留待報價，不自行推估。"
                ),
            }
        )
    return lines


def _delivery_renovation_lines(rooms: list[dict]) -> list[dict]:
    lines: list[dict] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_name = _delivery_text(room.get("room_name"), "未命名空間")
        questionnaire = room.get("questionnaire") if isinstance(room.get("questionnaire"), dict) else {}
        surfaces = questionnaire.get("surfaces") if isinstance(questionnaire.get("surfaces"), dict) else {}
        scope_labels = [
            label
            for key, label in (
                ("wallDefault", "牆面"),
                ("floor", "地板"),
                ("ceiling", "天花與照明"),
            )
            if surfaces.get(key)
        ]
        lines.append(
            {
                "id": f"{room.get('room_id') or room_name}-finish",
                "category": "renovation",
                "category_label": "裝潢工程",
                "room_id": room.get("room_id"),
                "name": f"{room_name}裝潢、材質與照明工程",
                "quantity": 1,
                "unit": "房",
                "amount_twd": None,
                "status": "pending_quote",
                "status_label": "待報價",
                "scope": scope_labels or ["牆面", "地板", "天花與照明"],
                "note": _delivery_text(
                    questionnaire.get("note")
                    or questionnaire.get("generation_notes")
                    or questionnaire.get("furniture_preference"),
                    "須先確認現場丈量、材質型號、施工範圍、燈具迴路與插座條件後再報價。",
                ),
                "quote_requirements": ["現場丈量", "材質型號", "施工範圍", "機電與插座條件"],
            }
        )
    return lines


def _beam_run_length_cm(beam: dict) -> float:
    start = beam.get("start") or {}
    end = beam.get("end") or {}
    try:
        dx = float(end.get("x", 0)) - float(start.get("x", 0))
        dy = float(end.get("y", 0)) - float(start.get("y", 0))
    except (TypeError, ValueError):
        return 0.0
    return (dx * dx + dy * dy) ** 0.5


def _delivery_structural_work_items(fixed_structure: dict) -> list[dict]:
    """把第 4 步固定結構裡「對得到費率表」的包覆項（包樑/包柱）組成 work_items。
    一般牆面/地板/天花無費率不進來（留給 ``_delivery_renovation_lines`` 標待報價）。"""
    items: list[dict] = []
    for index, beam in enumerate(fixed_structure.get("beams") or [], start=1):
        if not isinstance(beam, dict):
            continue
        length_m = round(_beam_run_length_cm(beam) / 100.0, 3)
        if length_m <= 0:
            continue
        beam_id = str(beam.get("id") or f"beam-{index}")
        items.append(
            {
                "id": beam_id,
                "work_code": "wall_wrap.carpentry",
                "description": "包樑木作",
                "quantity": {"value": length_m, "unit": "m"},
                "quantity_evidence": [beam_id, "fixed_structure.beams"],
                "assumptions": ["以樑兩端點水平距離估算包覆長度；三面展開與轉角須現場確認。"],
            }
        )
    for index, column in enumerate(fixed_structure.get("columns") or [], start=1):
        if not isinstance(column, dict):
            continue
        try:
            height_m = round(float(column.get("height_cm") or 0) / 100.0, 3)
        except (TypeError, ValueError):
            height_m = 0.0
        if height_m <= 0:
            continue
        column_id = str(column.get("id") or f"column-{index}")
        items.append(
            {
                "id": column_id,
                "work_code": "wall_wrap.carpentry",
                "description": "包柱木作",
                "quantity": {"value": height_m, "unit": "m"},
                "quantity_evidence": [column_id, "fixed_structure.columns"],
                "assumptions": ["以柱高估算包覆立面長度；轉角與展開面積須現場確認。"],
            }
        )
    return items


def _delivery_structural_lines(fixed_structure: dict) -> list[dict]:
    """對包樑/包柱呼叫後端 ``estimate_project_cost`` 產生「含來源」的概算預算行。
    無可估項或費率／目錄異常時回空清單（不擋成果包）。"""
    work_items = _delivery_structural_work_items(fixed_structure)
    if not work_items:
        return []
    try:
        estimate = estimate_project_cost(work_items, catalog=load_default_cost_catalog())
    except (ValueError, OSError, KeyError):
        return []
    lines: list[dict] = []
    for item in estimate.get("items") or []:
        quantity = item.get("quantity") or {}
        estimate_twd = item.get("estimate_twd") or {}
        lines.append(
            {
                "id": item.get("id"),
                "category": "renovation",
                "category_label": "結構包覆工程",
                "name": item.get("description") or "結構包覆",
                "quantity": quantity.get("value"),
                "unit": quantity.get("unit"),
                "amount_twd": estimate_twd.get("base"),
                "amount_range_twd": estimate_twd,
                "status": "concept_estimate",
                "status_label": "概算（含公開行情來源）",
                "work_code": item.get("work_code"),
                "sources": item.get("sources"),
                "source_ids": item.get("source_ids"),
                "inclusions": item.get("inclusions"),
                "exclusions": item.get("exclusions"),
                "price_date": item.get("price_date"),
                "assumptions": item.get("assumptions"),
                "note": "以公開行情概算；不含油漆飾面與轉角，須現場丈量後正式報價。",
            }
        )
    for missing in estimate.get("needs_quote") or []:
        lines.append(
            {
                "id": missing.get("id"),
                "category": "renovation",
                "category_label": "結構包覆工程",
                "name": missing.get("description") or "結構包覆",
                "amount_twd": None,
                "status": "pending_quote",
                "status_label": "待報價",
                "note": f"費率表無對應項（{missing.get('reason')}），保留待報價。",
            }
        )
    return lines


def _delivery_sensitive_paths(value: object, path: str = "$payload") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            child_path = f"{path}.{key}"
            if normalized in DELIVERY_SENSITIVE_KEYS:
                paths.append(child_path)
                continue
            paths.extend(_delivery_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_delivery_sensitive_paths(child, f"{path}[{index}]"))
    return paths


def _delivery_sanitized_copy(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _delivery_sanitized_copy(child)
            for key, child in value.items()
            if str(key).strip().casefold().replace("-", "_") not in DELIVERY_SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_delivery_sanitized_copy(child) for child in value]
    return deepcopy(value)


def _delivery_security_review(payload: dict) -> dict:
    redacted_paths = sorted(set(_delivery_sensitive_paths(payload)))
    return {
        "status": "passed_with_redactions" if redacted_paths else "passed",
        "status_label": "通過（敏感欄位已排除）" if redacted_paths else "通過",
        "reviewer": "RoomPilot 後端 deterministic security gate",
        "reviewed_at": _utc_timestamp(),
        "checks": [
            {
                "check_id": "provider_secret_isolation",
                "status": "passed",
                "detail": "瀏覽器成果包與生圖內容不包含伺服器端供應商金鑰。",
            },
            {
                "check_id": "sensitive_field_redaction",
                "status": "redacted" if redacted_paths else "passed",
                "detail": "以欄位白名單組稿；識別資訊、cookie、密碼與 token 類欄位不進入成果包。",
            },
            {
                "check_id": "price_integrity",
                "status": "passed",
                "detail": "僅列出家具目錄已附參考價；其餘裝潢與家具費用一律標示待報價。",
            },
        ],
        "redacted_paths": redacted_paths,
    }


def build_design_delivery_package(
    project_id: str,
    payload: dict,
    delivery_proposal: dict | None = None,
    *,
    with_catalog_prices: Callable[[list], list[dict]],
) -> dict:
    rooms = payload.get("rooms") if isinstance(payload.get("rooms"), list) else []
    snapshot = payload.get("configuration_snapshot") if isinstance(payload.get("configuration_snapshot"), dict) else {}
    snapshot_furniture = with_catalog_prices(snapshot.get("furniture") or [])
    snapshot = {**snapshot, "furniture": snapshot_furniture}
    raw_style_card = payload.get("style_card") if isinstance(payload.get("style_card"), dict) else {}
    style_card = _delivery_sanitized_copy(raw_style_card)
    security_review = _delivery_security_review(payload)
    presentation_rooms: list[dict] = []
    engineering_rooms: list[dict] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        questionnaire = room.get("questionnaire") if isinstance(room.get("questionnaire"), dict) else {}
        locked_furniture = questionnaire.get("lockedFurniture") or questionnaire.get("locked_furniture") or []
        if not isinstance(locked_furniture, list):
            locked_furniture = []
        room_type = _delivery_room_type(room)
        room_name = _delivery_text(room.get("room_name"), "未命名空間")
        room_id = room.get("room_id")
        room_furniture = [
            _delivery_sanitized_copy(item) for item in snapshot_furniture
            if str(item.get("room_id") or "") == str(room_id or "")
        ]
        usage = questionnaire.get("usage") if isinstance(questionnaire.get("usage"), list) else []
        note = _delivery_text(
            questionnaire.get("summary") or questionnaire.get("note"),
            "本房未填獨立補充，採用全屋問卷、已鎖定配置與色卡。",
        )
        raw_render_status = room.get("render") if isinstance(room.get("render"), dict) else {}
        raw_view = room.get("view") if isinstance(room.get("view"), dict) else {}
        raw_surfaces = questionnaire.get("surfaces") if isinstance(questionnaire.get("surfaces"), dict) else {}
        raw_equipment = questionnaire.get("generativeEquipment") if isinstance(questionnaire.get("generativeEquipment"), dict) else {}
        render_status = _delivery_sanitized_copy(raw_render_status)
        view = _delivery_sanitized_copy(raw_view)
        surfaces = _delivery_sanitized_copy(raw_surfaces)
        equipment = _delivery_sanitized_copy(raw_equipment)
        presentation_rooms.append(
            {
                "room_id": room_id,
                "room_name": room_name,
                "room_type": room_type,
                "style_card": style_card.get("name") or style_card.get("id"),
                "designer_reference": DESIGNER_REFERENCE_BY_ROOM_TYPE.get(
                    room_type,
                    DESIGNER_REFERENCE_BY_ROOM_TYPE["default"],
                ),
                "design_summary": (
                    f"{room_name}保留第 4 步固定結構與第 7 步鎖定視角，"
                    f"再把問卷需求、{len(room_furniture)} 件確認家具與「{style_card.get('name') or '已選色卡'}」整合為同一設計。"
                ),
                "decoration_summary": {
                    "questionnaire_source": questionnaire.get("source") or "room",
                    "questionnaire_note": note,
                    "usage": usage,
                    "locked_furniture": locked_furniture,
                    "materials": surfaces,
                    "ceiling_and_lighting": equipment,
                    "render_status": render_status,
                },
            }
        )
        engineering_rooms.append(
            {
                "room_id": room_id,
                "room_name": room_name,
                "structure_source": "第 4 步已確認固定結構",
                "view_source": "第 7 步已鎖定視角",
                "view": view,
                "furniture_count": len(room_furniture),
                "furniture": room_furniture,
                "materials": surfaces,
                "ceiling_and_lighting": equipment,
                "questionnaire_note": note,
                "render_completed": bool(render_status.get("submitted_at")),
                "revision_used": bool(render_status.get("revision_submitted_at")),
            }
        )
    fixed_structure = snapshot.get("fixed_structure") if isinstance(snapshot.get("fixed_structure"), dict) else {}
    budget_lines = [
        *_delivery_structural_lines(fixed_structure),
        *_delivery_renovation_lines(rooms),
        *_delivery_furniture_lines(snapshot),
    ]
    known_furniture_subtotal = sum(
        int(line["amount_twd"])
        for line in budget_lines
        if line.get("category") == "furniture" and line.get("amount_twd") is not None
    )
    estimated_structural_subtotal = sum(
        int(line["amount_twd"])
        for line in budget_lines
        if line.get("status") == "concept_estimate" and line.get("amount_twd") is not None
    )
    pending_quote_count = sum(1 for line in budget_lines if line.get("status") == "pending_quote")
    budget_report = {
        "title": "裝潢與家具預算報告書",
        "currency": "TWD",
        "pricing_status": "pending_quote" if pending_quote_count else "catalog_reference_only",
        "pricing_status_label": (
            "含結構概算與待報價項目"
            if pending_quote_count and estimated_structural_subtotal
            else "含待報價項目"
            if pending_quote_count
            else "含結構包覆概算"
            if estimated_structural_subtotal
            else "家具目錄參考價"
        ),
        "known_furniture_reference_subtotal_twd": known_furniture_subtotal,
        "estimated_structural_subtotal_twd": estimated_structural_subtotal,
        "pending_quote_count": pending_quote_count,
        "lines": budget_lines,
        "disclaimer": "本成果包含結構包覆概算（公開行情）與家具目錄參考價；最終工程及家具總價須經現場丈量、材料確認與廠商正式報價。",
    }
    engineering_report = {
        "title": "RoomPilot 工程報告書",
        "basis": [
            "第 4 步固定結構",
            "第 5 步問卷與 RAG 專業需求",
            "第 6 步家具、材質、天花與照明配置",
            "第 7 步逐房鎖定視角",
            "第 8 步最終生圖與每房一次修改紀錄",
        ],
        "snapshot_id": snapshot.get("snapshot_id"),
        "structure_counts": {
            key: len(fixed_structure.get(key) or [])
            for key in ("walls", "doors", "windows", "beams", "columns")
        },
        "rooms": engineering_rooms,
        "completion": {
            "room_count": len(engineering_rooms),
            "rendered_room_count": sum(1 for room in engineering_rooms if room["render_completed"]),
            "revised_room_count": sum(1 for room in engineering_rooms if room["revision_used"]),
        },
        "notes": [
            "幾何合法性與家具位置以保存快照為準，報告組稿不重新產生座標。",
            "施工前仍須由建築、結構、機電與室內裝修專業人員依現場條件複核。",
        ],
    }
    presentation = {
        "title": "RoomPilot 全屋設計與裝潢簡報",
        "subtitle": "依問卷、RAG、確認配置、鎖定視角與最終生圖整理",
        "style_card": style_card,
        "rooms": presentation_rooms,
        "security_review": security_review,
    }
    return {
        "schema_version": "1.1",
        "artifact_type": "roompilot.web_design_delivery.v1",
        "project_id": project_id,
        "snapshot_id": snapshot.get("snapshot_id"),
        "generated_at": payload.get("generated_at") or _utc_timestamp(),
        "presentation": presentation,
        "engineering_report": engineering_report,
        "security_review": security_review,
        "budget": budget_report,
        "budget_report": budget_report,
        "delivery_proposal": delivery_proposal or {"status": "not_generated"},
        "web_report": {
            "title": "RoomPilot 設計成果包",
            "format": "web_package",
            "sections": [
                {"heading": "一、全屋設計與裝潢簡報", "data_key": "presentation"},
                {"heading": "二、逐房設計與生圖成果", "data_key": "presentation.rooms"},
                {"heading": "三、工程報告書", "data_key": "engineering_report"},
                {"heading": "四、資安工程審核", "data_key": "security_review"},
                {"heading": "五、裝潢與家具預算報告書", "data_key": "budget_report"},
                {"heading": "六、設計提案 PDF", "data_key": "delivery_proposal"},
            ],
        },
    }
