"""RoomPilot guided intake with OpenRouter-first extraction and safe fallback."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

INTAKE_STEPS = (
    ("space_type", "你想規劃哪一個空間？可以直接用一段話描述整體需求。"),
    ("occupants", "為了確認尺度，這個空間會由幾位成人、小孩、長輩或寵物使用？"),
    ("needs", "這個空間最重要的生活需求是什麼？例如收納、休息、工作、閱讀或接待。"),
    ("style", "你希望空間呈現什麼風格、明暗、冷暖或色彩？"),
    ("materials", "你偏好哪些材質？例如木頭、石材、布料、金屬或玻璃。"),
    ("constraints", "有哪些一定要保留或不能被遮擋的條件？例如門、窗、走道或既有設備。"),
)
DEFAULT_MODELS = ["qwen/qwen3-32b:free"]
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ENV_PATHS = (os.path.join(PROJECT_DIR, ".env"), os.path.join(PROJECT_DIR, "roompilot", "server", ".env"))

def _load_local_env() -> None:
    for path in ENV_PATHS:
        if not os.path.exists(path):
            continue
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

def _models() -> list[str]:
    _load_local_env()
    raw = os.getenv("OPENROUTER_MODELS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    single = os.getenv("OPENROUTER_MODEL", "").strip()
    return [single] if single else DEFAULT_MODELS.copy()

def _api_key() -> str:
    _load_local_env()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return "" if not key or key in {"你的金鑰", "your-key", "YOUR_KEY"} else key

def new_client_brief() -> dict[str, Any]:
    return {"schema_version": "1.1", "created_at": datetime.now(timezone.utc).isoformat(), "space": {"type": None, "width_cm": 420, "depth_cm": 360, "floorplan_filename": None}, "occupants": {"adults": 0, "children": 0, "elderly": 0, "pets": 0}, "needs": [], "style": {"preferred": [], "colors": [], "materials": [], "selected_card_id": None}, "constraints": [], "notes": "", "confirmation": {"status": "draft", "confirmed_at": None}, "evidence": []}

def _brief_copy(value: Any) -> dict[str, Any]:
    brief = new_client_brief()
    if isinstance(value, dict):
        for key in brief:
            if key in value and isinstance(value[key], type(brief[key])):
                brief[key] = value[key]
    return brief

_CN_NUMBERS = {"零": 0, "一": 1, "二": 2, "兩": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

def _number(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else _CN_NUMBERS.get(raw)

def _count(text: str, labels: tuple[str, ...]) -> int | None:
    for label in labels:
        for pattern in (rf"{label}\s*[:：]?\s*(\d+|[零一二兩两三四五六七八九十]+)", rf"(\d+|[零一二兩两三四五六七八九十]+)\s*(?:位|名|個|人)?\s*{label}"):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return _number(match.group(1))
    return None

def _tokens(text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
    lowered = text.lower()
    return [key for key, aliases in mapping.items() if any(alias.lower() in lowered for alias in aliases)]

def _fallback_extract(text: str) -> dict[str, Any]:
    lower = text.lower()
    extracted: dict[str, Any] = {"space": {}, "occupants": {}, "style": {}, "needs": [], "constraints": []}
    space = _tokens(lower, {"living_room": ("客廳", "living room"), "bedroom": ("臥室", "bedroom"), "workspace": ("書房", "工作區", "office"), "dining_room": ("餐廳", "dining"), "studio": ("套房", "studio")})
    if space:
        extracted["space"]["type"] = space[0]
    extracted["occupants"] = {key: value for key, value in {"adults": _count(text, ("成人", "大人")), "children": _count(text, ("小孩", "兒童", "孩子")), "elderly": _count(text, ("長輩", "老人")), "pets": _count(text, ("寵物", "狗", "貓"))}.items() if value is not None}
    extracted["needs"] = _tokens(lower, {"storage": ("收納", "櫃子", "置物"), "work": ("工作", "辦公", "書桌"), "reading": ("閱讀", "看書"), "display": ("展示", "收藏"), "entertaining": ("接待", "聚會", "朋友", "客人"), "rest": ("休息", "放鬆", "睡覺")})
    extracted["style"]["preferred"] = _tokens(lower, {"japanese": ("日式", "日系", "無印", "侘寂", "japandi"), "scandinavian": ("北歐", "scandinavian"), "modern": ("現代", "現代簡約", "modern"), "industrial": ("工業", "industrial"), "american": ("美式", "american"), "warm_neutral": ("溫暖", "暖色", "奶油", "奶茶", "米色")})
    extracted["style"]["colors"] = _tokens(lower, {"warm_neutral": ("暖", "米", "奶茶", "奶油", "棕"), "light": ("明亮", "淺色", "白"), "dark": ("深色", "沉穩", "黑"), "low_saturation": ("低彩度", "淡色")})
    extracted["style"]["materials"] = _tokens(lower, {"wood": ("木", "原木", "橡木", "胡桃"), "stone": ("石材", "大理石", "石紋"), "fabric": ("布", "布料", "棉麻"), "metal": ("金屬", "鐵", "黃銅"), "glass": ("玻璃", "透明")})
    extracted["constraints"] = _tokens(lower, {"keep_window_clear": ("不要擋窗", "保留窗", "窗戶不能", "採光"), "keep_door_clear": ("不要擋門", "保留門", "出入口", "動線"), "keep_wide_walkway": ("寬走道", "寬動線", "無障礙"), "keep_existing": ("既有家具", "不能更動", "保留設備")})
    return extracted

def _merge_extracted(brief: dict[str, Any], extracted: Any, raw_text: str) -> dict[str, Any]:
    extracted = extracted if isinstance(extracted, dict) else {}
    if isinstance(extracted.get("space"), dict) and extracted["space"].get("type"):
        brief["space"]["type"] = str(extracted["space"]["type"])
    occupants = extracted.get("occupants") or {}
    if isinstance(occupants, dict):
        for key in ("adults", "children", "elderly", "pets"):
            value = occupants.get(key)
            if isinstance(value, int) and value >= 0:
                brief["occupants"][key] = value
    style = extracted.get("style") or {}
    if isinstance(style, dict):
        for key in ("preferred", "colors", "materials"):
            values = style.get(key)
            if isinstance(values, list) and values:
                brief["style"][key] = list(dict.fromkeys(str(item) for item in values if item))
    for key in ("needs", "constraints"):
        values = extracted.get(key)
        if isinstance(values, list) and values:
            brief[key] = list(dict.fromkeys(str(item) for item in values if item))
    if raw_text:
        brief["notes"] = (brief.get("notes", "") + "\n" + raw_text).strip()
        brief["evidence"] = (brief.get("evidence") or []) + [raw_text]
    return brief

def _missing_step(brief: dict[str, Any]) -> tuple[str | None, str | None]:
    if not brief["space"].get("type"): return INTAKE_STEPS[0]
    if not any(isinstance(value, int) and value > 0 for value in brief.get("occupants", {}).values()): return INTAKE_STEPS[1]
    if not brief.get("needs"): return INTAKE_STEPS[2]
    if not brief["style"].get("preferred"): return INTAKE_STEPS[3]
    if not brief["style"].get("materials"): return INTAKE_STEPS[4]
    if not brief.get("constraints"): return INTAKE_STEPS[5]
    return None, None

def _llm_messages(brief: dict[str, Any], answer: str) -> list[dict[str, str]]:
    schema = {"extracted": {"space": {"type": None}, "occupants": {"adults": None, "children": None, "elderly": None, "pets": None}, "needs": [], "style": {"preferred": [], "colors": [], "materials": []}, "constraints": []}, "reply": "繁體中文簡短回覆"}
    system = "你是 RoomPilot 的室內設計需求解析器。只輸出 JSON，不要 markdown。把使用者一段話中所有已知資訊一次抽取，不要只解析目前問題。人數支援『2位大人』『兩位大人』『成人2』；不確定填 null，不要猜。輸出格式：" + json.dumps(schema, ensure_ascii=False)
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"current_brief": brief, "new_answer": answer}, ensure_ascii=False)}]

def _call_openrouter(brief: dict[str, Any], answer: str) -> dict[str, Any] | None:
    key = _api_key()
    if not key or os.getenv("OPENROUTER_INTAKE_ENABLED") != "1": return None
    for model in _models():
        payload = {"model": model, "messages": _llm_messages(brief, answer), "temperature": 0.1, "max_tokens": 900}
        request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "HTTP-Referer": "http://127.0.0.1:8002", "X-Title": "RoomPilot"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(content).strip(), flags=re.IGNORECASE)
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                parsed["model"] = model
                return parsed
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError):
            continue
    return None

def start_intake(session_id: str) -> dict[str, Any]:
    key, question = INTAKE_STEPS[0]
    llm_enabled = bool(_api_key() and os.getenv("OPENROUTER_INTAKE_ENABLED") == "1")
    return {"session_id": session_id, "mode": "guided_llm" if llm_enabled else "guided_fallback", "step": key, "question": question, "client_brief": new_client_brief(), "ready_for_confirmation": False}

def advance_intake(session_id: str, step: str, answer: str, brief: Any) -> dict[str, Any]:
    current = _brief_copy(brief)
    llm_result = _call_openrouter(current, answer)
    updated = _merge_extracted(current, llm_result.get("extracted") if llm_result else _fallback_extract(answer), answer)
    mode = "guided_llm" if llm_result else "guided_fallback"
    reply = str((llm_result or {}).get("reply") or "我已整理這段需求。")
    upcoming, question = _missing_step(updated)
    ready = upcoming is None
    if ready:
        updated["confirmation"] = {"status": "draft", "confirmed_at": None}
        reply += "需求已整理完成，請確認摘要。"
    return {"session_id": session_id, "mode": mode, "step": upcoming, "question": question, "reply": reply, "client_brief": updated, "ready_for_confirmation": ready, "llm_model": (llm_result or {}).get("model")}
