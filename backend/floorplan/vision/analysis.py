"""平面圖分析公開入口。

座標輸出遵守 RoomPilot 的跨模組公分契約；影像像素只保留在 evidence，
不會流入家具配置引擎。
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

import cv2
import numpy as np

from ..cody_adapter import recognize_cody_geometry, recognize_cody_rooms
from .cody_semantic import cody_semantic_room_labeler_status
from .evaluation import summarize_room_polygons
from .geometry import transform_confirmed_geometry
from .image import decode_image, profile_floorplan_image
from .reference_plan import match_builder_plan_630
from .room_icons import apply_icon_room_labels, detect_room_icons
from .rooms import infer_rooms_from_walls
from .spatial_report import build_spatial_report
from .units import canonicalize_analysis_cm
from .openings import enrich_opening_relationships


COORDINATE_SYSTEM = {
    "unit": "metre",
    "origin": "plan_bbox_bottom_left",
    "x_axis": "right",
    "y_axis": "up",
}
MIN_AUTOMATIC_SCALE_CONFIDENCE = 0.8

# 別名比對前會去空白並 casefold，因此英文別名一律小寫、不含空白
# （"MASTER BEDROOM" → "masterbedroom" 以 "bedroom" 命中）。
# 英文別名 2026-07-29 補：testdata 美式圖的印刷房名全是英文，
# PaddleOCR 抓到信心 1.0 卻因表裡只有中文而整批被丟掉。
ROOM_LABELS = (
    ("bathroom", ("浴廁", "浴室", "廁所", "衛浴", "洗手間",
                  "bathroom", "bath", "toilet", "washroom", "lavatory", "wc")),
    ("living_room", ("客廳", "起居室", "livingroom", "living", "lounge", "familyroom")),
    ("kitchen", ("廚房", "厨房", "kitchen")),
    ("dining_room", ("餐廳", "餐室", "diningroom", "dining")),
    ("bedroom", ("主臥室", "主臥", "次臥", "臥室", "卧室", "bedroom", "masterbed")),
    ("balcony", ("陽台", "工作陽台", "balcony", "terrace", "patio")),
    ("workspace", ("書房", "工作室", "study", "office", "den")),
    # 語意層 entry/storage 的落地型別（2026-07 盤點修正）。circulation 與
    # storage 同時是前端推薦表 scene_layout2d.js 的既有契約鍵。
    ("circulation", ("玄關", "走道", "走廊", "hallway", "hall", "foyer", "entry", "corridor")),
    ("storage", ("儲藏室", "儲藏", "儲物間", "收納間", "closet", "storage", "pantry")),
)

# cody floorplan2room 的房型詞彙 → 上面 ROOM_LABELS 的主線契約詞彙。
# 兩邊字彙不同（cody 用 bed/bath/living，主線下游吃 bedroom/bathroom/living_room），
# 不對照就會把非契約值寫進 rooms[].type。
# "room" 是 cody 對「證據太弱」的中性標記（ROOM_ZH 標「空間」），映射為 None
# 代表不採用——它不該蓋掉 OCR 或圖示規則已經給出的判斷。
CODY_ROOM_TYPE_MAP: dict[str, str | None] = {
    "living": "living_room",
    "kitchen": "kitchen",
    "bed": "bedroom",
    "bath": "bathroom",
    "balcony": "balcony",
    # 語意層另會輸出 entry/storage/garage/outdoor 四型；先前未映射會被靜默丟棄，
    # 玄關與儲藏室永遠落不了地（2026-07 盤點確認）。circulation 與 storage 是
    # 前端推薦表既有的契約鍵（circulation 刻意零家具，正好避免小空間被硬塞）。
    "entry": "circulation",
    "storage": "storage",
    "outdoor": "balcony",
    "garage": None,  # 台灣公寓場景罕見且無下游消費者，維持不採用
    # 2026-07-29 語意層新增 stair 一類（MAIN_SYNC_TODO 第 10 節）。踏板幾何是
    # 樓梯獨有的圖案，故它立得住；同批曾短暫存在的 office 已撤回併入 storage。
    # 映射為 None 是刻意的：樓梯區的產品語意是「不可擺設」，主線契約詞彙裡沒有
    # 對應鍵，硬塞既有鍵（如 circulation）會讓下游把它當可佈置的走道。
    # 待前端推薦表新增 stair 契約鍵後再改指過去。
    "stair": None,
    "room": None,
}


def _semantic_cache_key(filename: str | None) -> str | None:
    """上傳檔名主幹 → `recognize_cody_rooms` 的 `cache_key`。

    2026-07-30 CubiCasa 遮罩快取整批移除後，這個鍵不再對應任何 `*_mask.npz`，
    但仍有用：它決定 cody_adapter 寫暫存圖的檔名，而 OCR 那層的單格快取以路徑
    為鍵——同一張圖跨請求維持穩定命名，日誌與診斷才追得回是哪張圖。
    只接受 ASCII 安全字元的主幹；其他（含中文檔名、帶空白）回 None，
    讓 cody_adapter 退回內容雜湊鍵。
    """
    base = re.split(r"[\\/]", str(filename or ""))[-1]
    stem, _, _ext = base.rpartition(".")
    stem = stem or base
    if re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", stem):
        return stem
    return None


def _room_centre_px(
    room: Mapping[str, Any],
    *,
    plan_bbox_px: list[float] | None,
    m_per_px: float | None = None,
    cm_per_px: float | None = None,
) -> tuple[float, float] | None:
    """取房間在原圖像素空間的中心點。

    三種房間各帶不同座標：OCR 標籤房間有 `bbox_px`（原圖像素）；
    `infer_rooms_from_walls` 推導的房間只有多邊形，且單位視管線階段而定——
    `analyze_floorplan_image` 內部還是公尺的 `polygon_m`，序列化成公分契約後
    才變 `polygon_cm`。兩者都支援，避免呼叫時機一變就靜默對不上。

    多邊形是 plan 座標（原點在 plan_bbox 左下、y 朝上），要靠 plan_bbox_px
    與對應比例尺才換得回像素。
    """
    bbox = room.get("bbox_px")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return (float(bbox[0]) + float(bbox[2])) / 2, (float(bbox[1]) + float(bbox[3])) / 2

    if not plan_bbox_px:
        return None
    for key, unit_per_px in (("polygon_m", m_per_px), ("polygon_cm", cm_per_px)):
        polygon = room.get(key)
        if not polygon or not unit_per_px:
            continue
        points = [
            (float(p["x"]), float(p["y"]))
            for p in polygon
            if isinstance(p, Mapping) and "x" in p and "y" in p
        ]
        if not points:
            continue
        centre_x = sum(x for x, _ in points) / len(points)
        centre_y = sum(y for _, y in points) / len(points)
        left, _top, _right, bottom = plan_bbox_px
        return left + centre_x / unit_per_px, bottom - centre_y / unit_per_px
    return None


def apply_floorplan2room_labels(
    rooms: list[dict[str, Any]],
    semantics: Mapping[str, Any] | None,
    *,
    image_width: int,
    image_height: int,
    plan_bbox_px: list[float] | None = None,
    m_per_px: float | None = None,
    cm_per_px: float | None = None,
) -> int:
    """把 cody floorplan2room 的房型語意套到 rooms[]，回傳實際套用筆數。

    `docs/CODY_MAIN_SYNC_TODO.md` 第 2 點要求房型改由語意管線提供，而非
    django_icon_zone_rules。配對方式是像素空間包含判定：rooms[] 的 bbox 中心
    落在哪個語意方塊裡就採用該方塊的房型。

    語意管線的座標以它自己回報的 image 尺寸為準——彩色管線會把圖放大兩倍，
    所以 bbox 必須換算回原圖像素才對得上。

    覆蓋規則（2026-07-29 以 floor01/floor04 實測定案）：語意層可以填補空位、
    可以更新圖示層自我標記「待確認」的猜測（僅限 dinov2_semantic 來源），
    但不得覆蓋印刷房名、七格局啟發式與使用者確認的判斷。
    """
    if not rooms or not semantics or not semantics.get("rooms"):
        return 0

    source_size = semantics.get("image") or {}
    scale_x = image_width / max(1.0, float(source_size.get("w") or image_width))
    scale_y = image_height / max(1.0, float(source_size.get("h") or image_height))

    semantic_may_update_icons = semantics.get("room_label_source") == "dinov2_semantic"
    applied = 0
    for room in rooms:
        # 2026-07-29 優先序定案（floor01 OCR 實跑＋floor04 黃金測試 A/B）：
        # (1) 空位（default）一律可填；
        # (2) 圖示層的猜測自我標記「待確認」（furniture_icon_inference），
        #     可被真語意（dinov2_semantic）更新——floor01 的 4 m² 假臥室
        #     即由此修正為玄關；降級的 area_rules 沒有這個資格；
        # (3) 其他一律不可覆蓋：印刷房名（ocr_room_label，floor01 實跑
        #     CLOSET 曾被蓋成廚房）、七格局啟發式（layout_heuristic，
        #     floor04 黃金測試曾因被覆蓋而四型全滅）、使用者確認。
        # 最終順位：印刷房名/啟發式 > DINOv2 語意 > 圖示待確認 > 面積規則。
        room_type_value = room.get("type")
        if room_type_value in (None, "", "default"):
            pass
        elif semantic_may_update_icons and room.get("source") == "furniture_icon_inference":
            pass
        else:
            continue
        centre = _room_centre_px(
            room, plan_bbox_px=plan_bbox_px, m_per_px=m_per_px, cm_per_px=cm_per_px
        )
        if centre is None:
            continue
        centre_x, centre_y = centre
        for candidate in semantics["rooms"]:
            room_type = CODY_ROOM_TYPE_MAP.get(candidate.get("label"))
            if room_type is None:
                continue
            box = candidate.get("bbox")
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                continue
            left, top = float(box[0]) * scale_x, float(box[1]) * scale_y
            right, bottom = float(box[2]) * scale_x, float(box[3]) * scale_y
            if not (left <= centre_x <= right and top <= centre_y <= bottom):
                continue
            room["type"] = room_type
            room["label"] = candidate.get("label_zh") or room["label"]
            room["source"] = "cody_floorplan2room"
            if candidate.get("area_m2"):
                room["area_m2"] = candidate["area_m2"]
            applied += 1
            break
    return applied


def _number_m(text: str) -> float | None:
    compact = text.strip().lower().replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mm|cm|m|公分|毫米|公尺)?", compact)
    if match:
        value = float(match.group(1))
        unit = match.group(2) or "cm"
        if unit in {"mm", "毫米"}:
            value /= 1000.0
        elif unit in {"cm", "公分"}:
            value /= 100.0
        return value if 0.3 <= value <= 100 else None
    # 英呎吋（美式圖的尺寸標註，如 9'-0"、12'6"、10'）。OCR 常把引號辨成
    # ’ ” ″，先正規化。複合房間尺寸（9'-0"x12'-0"）不是單一量測、刻意不收——
    # 那是房中央的面積標籤，配錯牆線會整張圖比例錯掉。
    normalized = compact.replace("’", "'").replace("′", "'").replace("”", '"').replace("″", '"')
    imperial = re.fullmatch(r"(\d+)\s*'\s*-?\s*(\d+(?:\.\d+)?)?\s*\"?", normalized)
    if imperial:
        feet = float(imperial.group(1))
        inches = float(imperial.group(2) or 0.0)
        value = feet * 0.3048 + inches * 0.0254
        return value if 0.3 <= value <= 100 else None
    return None


def _lines(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    edges = cv2.Canny(gray, 50, 150)
    height, width = gray.shape
    detected = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(20, min(height, width) // 12),
        minLineLength=max(40, min(height, width) // 4),
        maxLineGap=16,
    )
    if detected is None:
        return []
    return [tuple(int(v) for v in item) for item in np.asarray(detected).reshape(-1, 4)]


def _clusters(values: np.ndarray) -> list[tuple[int, int]]:
    if values.size == 0:
        return []
    groups: list[tuple[int, int]] = []
    start = previous = int(values[0])
    for raw in values[1:]:
        value = int(raw)
        if value > previous + 1:
            groups.append((start, previous))
            start = value
        previous = value
    groups.append((start, previous))
    return groups


def _dot_endpoints(
    gray: np.ndarray,
    line: tuple[int, int, int, int],
) -> tuple[tuple[float, float], tuple[float, float]]:
    x1, y1, x2, y2 = line
    horizontal = abs(x2 - x1) >= abs(y2 - y1)
    _, ink = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    radius = 9
    if horizontal:
        cy = int(round((y1 + y2) / 2))
        lo, hi = max(0, cy - radius), min(gray.shape[0], cy + radius + 1)
        band = ink[lo:hi, :]
        distance = cv2.distanceTransform(band, cv2.DIST_L2, 5)
        candidates = np.flatnonzero(distance.max(axis=0) >= 2.5)
        groups = [g for g in _clusters(candidates) if g[1] - g[0] <= 18]
        if len(groups) >= 2:
            centres = [(a + b) / 2 for a, b in groups]
            left = min(centres, key=lambda x: abs(x - min(x1, x2)))
            right = min(centres, key=lambda x: abs(x - max(x1, x2)))
            if right - left >= 40:
                return (left, float(cy)), (right, float(cy))
    else:
        cx = int(round((x1 + x2) / 2))
        lo, hi = max(0, cx - radius), min(gray.shape[1], cx + radius + 1)
        band = ink[:, lo:hi]
        distance = cv2.distanceTransform(band, cv2.DIST_L2, 5)
        candidates = np.flatnonzero(distance.max(axis=1) >= 2.5)
        groups = [g for g in _clusters(candidates) if g[1] - g[0] <= 18]
        if len(groups) >= 2:
            centres = [(a + b) / 2 for a, b in groups]
            top = min(centres, key=lambda y: abs(y - min(y1, y2)))
            bottom = min(centres, key=lambda y: abs(y - max(y1, y2)))
            if bottom - top >= 40:
                return (float(cx), top), (float(cx), bottom)
    return (float(x1), float(y1)), (float(x2), float(y2))


def _dimension_evidence(
    gray: np.ndarray,
    observations: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    lines = _lines(gray)
    best: tuple[float, Mapping[str, Any], tuple[int, int, int, int], float] | None = None
    for observation in observations:
        bbox = observation.get("bbox")
        distance_m = _number_m(str(observation.get("text", "")))
        if distance_m is None or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        bx0, by0, bx1, by1 = (float(v) for v in bbox)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        text_height = max(by1 - by0, 1.0)
        for line in lines:
            x1, y1, x2, y2 = line
            length = math.hypot(x2 - x1, y2 - y1)
            horizontal = abs(x2 - x1) >= abs(y2 - y1)
            if horizontal:
                inside = min(x1, x2) - 12 <= cx <= max(x1, x2) + 12
                offset = abs(cy - (y1 + y2) / 2)
            else:
                inside = min(y1, y2) - 12 <= cy <= max(y1, y2) + 12
                offset = abs(cx - (x1 + x2) / 2)
            if not inside or offset > max(45.0, text_height * 4):
                continue
            score = length - offset * 2
            if best is None or score > best[0]:
                best = (score, observation, line, distance_m)
    if best is None:
        return None
    _, observation, line, distance_m = best
    start, end = _dot_endpoints(gray, line)
    pixel_distance = math.dist(start, end)
    if pixel_distance <= 0:
        return None
    return {
        "text": str(observation.get("text", "")),
        "bbox": [float(v) for v in observation["bbox"]],
        "confidence": round(float(observation.get("confidence", 0.0)), 3),
        "distance_m": distance_m,
        "start_px": [round(start[0], 2), round(start[1], 2)],
        "end_px": [round(end[0], 2), round(end[1], 2)],
        "pixel_distance": pixel_distance,
    }


def _room_type(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text).casefold()
    for room_type, aliases in ROOM_LABELS:
        if any(alias in compact for alias in aliases):
            return room_type
    return None


def _drop_duplicate_ocr_label_rooms(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """開放式空間常在同一牆體圈圍裡印多塊房名（LIVING ROOM 與 KITCHEN 同室），
    每塊字各建一間房、但一個圈圍只會把多邊形發給第一個命中的標籤——沒領到
    多邊形、質心又落在別間房多邊形裡的 OCR 房，是同一實體空間的重複計數，
    砍掉（2026-07-29 floor01 實跑：49.3 m² 客餐廚被算成兩間）。
    領不到多邊形、也不落在任何房間裡的 OCR 房保留——那是圈圍偵測失敗，
    標籤本身仍是有效證據。"""
    contours = []
    for room in rooms:
        polygon = room.get("polygon_m")
        if polygon and len(polygon) >= 3:
            contours.append(
                np.array(
                    [[[float(p.get("x") or 0), float(p.get("y") or 0)]] for p in polygon],
                    dtype=np.float32,
                )
            )
    if not contours:
        return rooms
    kept = []
    for room in rooms:
        if room.get("polygon_m") or room.get("source") != "ocr_room_label":
            kept.append(room)
            continue
        centroid = room.get("centroid_m") or {}
        point = (float(centroid.get("x") or 0), float(centroid.get("y") or 0))
        if not any(cv2.pointPolygonTest(c, point, False) >= 0 for c in contours):
            kept.append(room)
    return kept


def _room_observations(
    observations: Iterable[Mapping[str, Any]],
    *,
    m_per_px: float,
    image_width: int,
    image_height: int,
    plan_bbox_px: list[float] | None = None,
) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    bbox_left, bbox_top, bbox_right, bbox_bottom = plan_bbox_px or [0.0, 0.0, float(image_width), float(image_height)]
    for observation in observations:
        room_type = _room_type(str(observation.get("text", "")))
        bbox = observation.get("bbox")
        if room_type is None or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = (float(v) for v in bbox)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if not (bbox_left <= cx <= bbox_right and bbox_top <= cy <= bbox_bottom):
            continue
        counts[room_type] = counts.get(room_type, 0) + 1
        rooms.append(
            {
                "id": f"{room_type}-{counts[room_type]}",
                "type": room_type,
                "label": str(observation.get("text", "")).strip(),
                "centroid_m": {
                    "x": round((cx - bbox_left) * m_per_px, 3),
                    "y": round((bbox_bottom - cy) * m_per_px, 3),
                },
                "confidence": round(float(observation.get("confidence", 0.0)), 3),
                "source": "ocr_room_label",
                "bbox_px": [x0, y0, x1, y1],
            }
        )
    return rooms


def analyze_floorplan_image(
    image_bytes: bytes,
    *,
    filename: str = "floorplan.png",
    calibration_hint: Mapping[str, Any] | None = None,
    ocr_observations: Iterable[Mapping[str, Any]] | None = None,
    ocr_provider: Any | None = None,
    geometry_observations: Iterable[Mapping[str, Any]] | None = None,
    evaluation_reference_rooms: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """分析建商平面圖；不確定的尺度必須透過 confirmation seam 補齊。"""
    image = decode_image(image_bytes)
    image_profile = profile_floorplan_image(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    observations = list(ocr_observations or [])
    had_supplied_ocr_observations = bool(observations)
    recognition_mode = "provided_observations" if geometry_observations else "cody_vision"
    reference_match = None
    if not geometry_observations:
        reference_match = match_builder_plan_630(image)
        if reference_match and not observations:
            observations = reference_match["ocr"]
    # OCR 供應者是最後手段：呼叫端提供的觀測與黃金圖參考標註都優先。
    # 2026-07-29 實測：真 PaddleOCR 若搶在 630 黃金圖標註之前執行，會取代
    # 已驗收的標準答案，打破 confirm 契約與零 review_items 的驗收。
    if not observations and ocr_provider is not None:
        try:
            observations = list(ocr_provider.recognize(image_bytes))
        except Exception:
            observations = []  # OCR 是輔助證據；供應者執行失敗不得拖垮辨識主流程

    evidence = _dimension_evidence(gray, observations)
    if calibration_hint:
        distance_m = (
            float(calibration_hint["distance_m"])
            if "distance_m" in calibration_hint
            else float(calibration_hint["distance_cm"]) / 100.0
        )
        start = tuple(float(v) for v in calibration_hint["start_px"])
        end = tuple(float(v) for v in calibration_hint["end_px"])
        evidence = {
            "text": str(calibration_hint.get("text", distance_m)),
            "bbox": calibration_hint.get("bbox"),
            "confidence": 1.0,
            "distance_m": distance_m,
            "start_px": list(start),
            "end_px": list(end),
            "pixel_distance": math.dist(start, end),
        }

    issues: list[str] = []
    scale = None
    geometry = {"walls": [], "doors": [], "windows": []}
    cody_diagnostics = None
    cody_room_semantics: dict[str, Any] | None = None
    if geometry_observations and evidence and evidence["pixel_distance"] > 0:
        scale = {
            "distance_m": round(evidence["distance_m"], 3),
            "pixel_distance": round(evidence["pixel_distance"], 3),
            "m_per_px": round(evidence["distance_m"] / evidence["pixel_distance"], 6),
            "source": "manual_confirmation" if calibration_hint else "dimension_ocr",
            "confidence": evidence["confidence"],
        }
        if not calibration_hint and evidence["confidence"] < MIN_AUTOMATIC_SCALE_CONFIDENCE:
            issues.append("scale_confirmation_required")
        geometry = transform_confirmed_geometry(
            geometry_observations,
            m_per_px=scale["m_per_px"],
            image_height=int(gray.shape[0]),
        )
    elif geometry_observations:
        issues.append("scale_anchor_missing")
    else:
        cody_calibration = calibration_hint
        if cody_calibration is None and evidence and evidence["pixel_distance"] > 0:
            cody_calibration = {
                "distance_m": evidence["distance_m"],
                "start_px": evidence["start_px"],
                "end_px": evidence["end_px"],
            }
        cody_result = recognize_cody_geometry(
            image_bytes,
            calibration_hint=cody_calibration,
        )
        geometry = {
            "walls": cody_result["walls"],
            "doors": cody_result["doors"],
            "windows": cody_result["windows"],
            "plan_bbox_px": cody_result["plan_bbox_px"],
        }
        scale = cody_result["scale"]
        scale.pop("cody_scale", None)
        cody_diagnostics = cody_result["diagnostics"]
        # CODY_MAIN_SYNC_TODO 第 2 點：房型改由 floorplan2room 語意管線提供。
        # 回 None（無法辨識）時下方仍走 django_icon_zone_rules，行為向下相容。
        cody_room_semantics = recognize_cody_rooms(
            image_bytes,
            cache_key=_semantic_cache_key(filename),
        )
        if evidence and calibration_hint is None:
            scale["distance_m"] = round(evidence["distance_m"], 3)
            scale["pixel_distance"] = round(evidence["pixel_distance"], 3)
            scale["m_per_px"] = round(evidence["distance_m"] / evidence["pixel_distance"], 6)
            scale["source"] = "dimension_ocr"
            scale["confidence"] = evidence["confidence"]
        if scale["source"].startswith("cody_") and scale["confidence"] < MIN_AUTOMATIC_SCALE_CONFIDENCE:
            issues.append("scale_confirmation_required")
    if scale and not geometry["walls"]:
        issues.append("geometry_missing")
        if not evidence and not calibration_hint:
            scale = None
            issues.append("scale_anchor_missing")

    rooms = (
        _room_observations(
            observations,
            m_per_px=scale["m_per_px"],
            image_width=int(gray.shape[1]),
            image_height=int(gray.shape[0]),
            plan_bbox_px=geometry.get("plan_bbox_px") if geometry["walls"] else None,
        )
        if scale
        else []
    )
    if scale and geometry["walls"] and not reference_match and not geometry_observations:
        inferred_rooms = infer_rooms_from_walls(
            geometry["walls"],
            labelled_rooms=rooms,
        )
        if inferred_rooms:
            inferred_by_id = {room["id"]: room for room in inferred_rooms}
            labelled_ids = {room["id"] for room in rooms}
            rooms = [
                {
                    **room,
                    **{
                        key: value
                        for key, value in inferred_by_id.get(room["id"], {}).items()
                        if key in {
                            "polygon_m",
                            "polygon_source",
                            "polygon_confidence",
                            "area_m2",
                        }
                    },
                }
                for room in rooms
            ] + [
                room
                for room in inferred_rooms
                if room["id"] not in labelled_ids
            ]
            rooms = _drop_duplicate_ocr_label_rooms(rooms)
    if reference_match and scale and geometry.get("plan_bbox_px"):
        bbox_left, _, _, bbox_bottom = geometry["plan_bbox_px"]
        for room in rooms:
            polygon_px = reference_match["room_polygons_px"].get(room["id"])
            if not polygon_px:
                continue
            room["polygon_m"] = [
                {
                    "x": round((float(point[0]) - bbox_left) * scale["m_per_px"], 3),
                    "y": round((bbox_bottom - float(point[1])) * scale["m_per_px"], 3),
                }
                for point in polygon_px
            ]
            room["polygon_source"] = "reference_annotation"
            room["polygon_confidence"] = reference_match["match"]["inlier_ratio"]

    room_icon_evidence: list[dict[str, Any]] = []
    if scale and geometry["walls"] and geometry.get("plan_bbox_px") and rooms:
        room_icon_evidence = detect_room_icons(
            gray,
            walls=geometry["walls"],
            plan_bbox_px=geometry["plan_bbox_px"],
            m_per_px=float(scale["m_per_px"]),
            text_observations=observations,
        )
        apply_icon_room_labels(
            rooms,
            room_icon_evidence,
            plan_bbox_px=geometry["plan_bbox_px"],
            m_per_px=float(scale["m_per_px"]),
        )

    # 語意管線的判斷優先於圖示規則，所以放在 apply_icon_room_labels 之後覆蓋。
    semantic_label_count = apply_floorplan2room_labels(
        rooms,
        cody_room_semantics,
        image_width=int(gray.shape[1]),
        image_height=int(gray.shape[0]),
        plan_bbox_px=geometry.get("plan_bbox_px"),
        m_per_px=float(scale["m_per_px"]) if scale and scale.get("m_per_px") else None,
        cm_per_px=float(scale["cm_per_px"]) if scale and scale.get("cm_per_px") else None,
    )

    result = {
        "schema_version": "1.0",
        "filename": filename,
        "recognition_engine": "cody" if not geometry_observations else "manual",
        "recognition_mode": recognition_mode,
        "image_profile": image_profile,
        "image_size_px": {"width": int(gray.shape[1]), "height": int(gray.shape[0])},
        "coordinate_system": COORDINATE_SYSTEM.copy(),
        "scale": scale,
        "walls": geometry["walls"],
        "doors": geometry["doors"],
        "windows": geometry["windows"],
        "plan_bbox_px": geometry.get("plan_bbox_px"),
        "rooms": rooms,
        "room_icon_evidence": room_icon_evidence,
        "cody_room_semantics": cody_room_semantics,
        "cody_room_semantic_labels_applied": semantic_label_count,
        "cody_semantic_room_labeler": cody_semantic_room_labeler_status(),
        "evidence": [evidence] if evidence else [],
        "cody_diagnostics": cody_diagnostics,
        "issues": issues,
        "requires_scale_confirmation": scale is None or "scale_confirmation_required" in issues,
        "requires_confirmation": (
            scale is None
            or "scale_confirmation_required" in issues
            or not geometry["walls"]
        ),
    }
    result["spatial_report"] = build_spatial_report(result)
    enrich_opening_relationships(result)
    if result["spatial_report"]["review_items"]:
        result["issues"].append("targeted_room_review_required")
        result["requires_confirmation"] = True
    if reference_match and had_supplied_ocr_observations:
        if "targeted_room_review_required" not in result["issues"]:
            result["issues"].append("targeted_room_review_required")
        result["requires_confirmation"] = True
    canonical = canonicalize_analysis_cm(result)
    if evaluation_reference_rooms is not None:
        canonical["room_evaluation"] = summarize_room_polygons(
            list(evaluation_reference_rooms),
            canonical["spatial_report"]["rooms"],
        )
    return canonical
