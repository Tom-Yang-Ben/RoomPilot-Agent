"""cody floorplan2room 房型語意的記憶體橋接測試。

`docs/CODY_MAIN_SYNC_TODO.md` 第 2 點要求辨識預設走 floorplan2room，一次拿到
幾何與房型。floorplan2room 本身是腳本形狀（`process()` 吃檔案路徑、回傳 bool、
把結果寫進硬編路徑 `training/json/room/`），主線 API 手上只有 image bytes，
因此由 `recognize_cody_rooms()` 做記憶體橋接。這支測試守住橋接的三個要求：

1. 真的跑得出房型（本機無權重、無 torch 時走面積規則降級，仍須有 rooms）。
2. 絕不寫進 `training/json/room/`，也不留下暫存檔——它在 API 請求路徑上。
3. 壞輸入回 None 而非拋例外，讓上游能退回 django_icon_zone_rules。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.floorplan.cody_adapter import recognize_cody_rooms

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "testdata" / "png" / "floor01.png"


@pytest.fixture(scope="module")
def sample_bytes() -> bytes:
    return SAMPLE.read_bytes()


def test_returns_rooms_with_labels(sample_bytes: bytes) -> None:
    result = recognize_cody_rooms(sample_bytes)

    assert result is not None
    assert result["rooms"], "floorplan2room 應切出至少一個房間"
    for room in result["rooms"]:
        assert isinstance(room["id"], int)
        assert room["label"]
        assert room["label_zh"]
        assert room["area_m2"] > 0
        assert len(room["bbox"]) == 4


def test_reports_pipeline_and_scale(sample_bytes: bytes) -> None:
    result = recognize_cody_rooms(sample_bytes)

    assert result["pipeline"] in {"floorplan2dxf", "floorplan2dxf_color"}
    assert result["cm_per_px"] > 0
    assert result["image"]["w"] > 0 and result["image"]["h"] > 0
    assert isinstance(result["adjacency"], list)
    # 無語意快取時房型來源必須誠實標示，上游才知道這是降級結果。
    assert result["room_label_source"] in {"cubicasa_semantic", "area_rules"}


def test_does_not_write_pipeline_artifacts(sample_bytes: bytes, monkeypatch, tmp_path) -> None:
    """floorplan2room.process() 會寫 training/json/room/ 與預覽 PNG；橋接不得沿用。"""
    monkeypatch.chdir(tmp_path)

    result = recognize_cody_rooms(sample_bytes)

    assert result is not None
    assert not (tmp_path / "training").exists()
    assert not (tmp_path / "chk").exists()
    assert list(tmp_path.iterdir()) == []


def test_invalid_image_returns_none_instead_of_raising() -> None:
    assert recognize_cody_rooms(b"not an image at all") is None


def test_empty_payload_returns_none() -> None:
    assert recognize_cody_rooms(b"") is None


# ── floorplan2room 房型語意套進 analysis rooms[] ────────────────────────────
from backend.floorplan.vision.analysis import (  # noqa: E402
    CODY_ROOM_TYPE_MAP,
    apply_floorplan2room_labels,
)


def _semantics(rooms, *, width=100, height=100, source="cubicasa_semantic"):
    """預設用真語意來源——降級來源不得覆蓋既有房型，另有專門測試涵蓋。"""
    return {
        "image": {"w": width, "h": height},
        "rooms": rooms,
        "room_label_source": source,
    }


def test_vocabulary_map_covers_every_cody_label() -> None:
    """cody 的 ROOM_ZH 六個鍵都要有對照，漏一個就會靜默不套用。"""
    from backend.floorplan.floorplan2dxf_color import ROOM_ZH

    assert set(ROOM_ZH) == set(CODY_ROOM_TYPE_MAP)


def test_labels_override_icon_fallback_when_centroid_falls_inside() -> None:
    rooms = [
        {"id": "bedroom-1", "type": "bedroom", "label": "臥室", "source": "ocr_room_label",
         "bbox_px": [10.0, 10.0, 30.0, 30.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _semantics([{"label": "living", "label_zh": "客廳", "area_m2": 42.0,
                     "bbox": [0, 0, 50, 50]}]),
        image_width=100,
        image_height=100,
    )

    assert applied == 1
    assert rooms[0]["type"] == "living_room"
    assert rooms[0]["label"] == "客廳"
    assert rooms[0]["source"] == "cody_floorplan2room"
    assert rooms[0]["area_m2"] == 42.0


def test_neutral_label_does_not_overwrite_a_known_type() -> None:
    """cody 的 room=「空間」代表證據不足，不該蓋掉既有判斷。"""
    rooms = [
        {"id": "kitchen-1", "type": "kitchen", "label": "廚房", "source": "ocr_room_label",
         "bbox_px": [10.0, 10.0, 30.0, 30.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _semantics([{"label": "room", "label_zh": "空間", "area_m2": 9.0,
                     "bbox": [0, 0, 50, 50]}]),
        image_width=100,
        image_height=100,
    )

    assert applied == 0
    assert rooms[0]["type"] == "kitchen"
    assert rooms[0]["source"] == "ocr_room_label"


def test_rooms_outside_every_semantic_bbox_are_left_alone() -> None:
    rooms = [
        {"id": "bedroom-1", "type": "bedroom", "label": "臥室", "source": "ocr_room_label",
         "bbox_px": [80.0, 80.0, 90.0, 90.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _semantics([{"label": "living", "label_zh": "客廳", "area_m2": 42.0,
                     "bbox": [0, 0, 50, 50]}]),
        image_width=100,
        image_height=100,
    )

    assert applied == 0
    assert rooms[0]["source"] == "ocr_room_label"


def test_semantic_bbox_is_rescaled_when_pipeline_upscaled_the_image() -> None:
    """彩色管線會放大 2 倍，bbox 必須換算回原圖像素才對得上。"""
    rooms = [
        {"id": "bedroom-1", "type": "bedroom", "label": "臥室", "source": "ocr_room_label",
         "bbox_px": [10.0, 10.0, 30.0, 30.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _semantics([{"label": "bath", "label_zh": "浴廁", "area_m2": 4.0,
                     "bbox": [0, 0, 100, 100]}], width=200, height=200),
        image_width=100,
        image_height=100,
    )

    assert applied == 1
    assert rooms[0]["type"] == "bathroom"


def test_missing_semantics_is_a_no_op() -> None:
    rooms = [{"id": "bedroom-1", "type": "bedroom", "label": "臥室",
              "source": "ocr_room_label", "bbox_px": [1.0, 1.0, 2.0, 2.0]}]

    assert apply_floorplan2room_labels(rooms, None, image_width=100, image_height=100) == 0
    assert apply_floorplan2room_labels(rooms, _semantics([]), image_width=100, image_height=100) == 0
    assert rooms[0]["source"] == "ocr_room_label"


# ── 牆體推導的房間只有 polygon_cm，沒有 bbox_px ─────────────────────────────
def test_polygon_cm_rooms_are_matched_via_plan_bbox_and_scale() -> None:
    """infer_rooms_from_walls 產出的房間沒有 bbox_px，只有 plan 座標的 polygon_cm。

    plan 座標原點在 plan_bbox 左下、y 朝上，換回像素要用
    px_x = left + x_cm / cm_per_px、px_y = bottom - y_cm / cm_per_px。
    """
    rooms = [
        {"id": "room-1", "type": "default", "label": "空間 1",
         "source": "cody_wall_enclosure",
         "polygon_cm": [
             {"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 0.0},
             {"x": 100.0, "y": 100.0}, {"x": 0.0, "y": 100.0},
         ]},
    ]
    # 質心 (50,50) cm → 像素 (200 + 50, 300 - 50) = (250, 250)
    applied = apply_floorplan2room_labels(
        rooms,
        _semantics([{"label": "kitchen", "label_zh": "廚房", "area_m2": 8.0,
                     "bbox": [200, 200, 300, 300]}], width=400, height=400),
        image_width=400,
        image_height=400,
        plan_bbox_px=[200.0, 100.0, 400.0, 300.0],
        cm_per_px=1.0,
    )

    assert applied == 1
    assert rooms[0]["type"] == "kitchen"
    assert rooms[0]["label"] == "廚房"
    assert rooms[0]["source"] == "cody_floorplan2room"


def test_polygon_cm_rooms_need_both_plan_bbox_and_scale() -> None:
    """缺任一項就無法換算，必須安靜略過而不是算出錯誤位置。"""
    rooms = [
        {"id": "room-1", "type": "default", "label": "空間 1",
         "source": "cody_wall_enclosure",
         "polygon_cm": [{"x": 0.0, "y": 0.0}, {"x": 100.0, "y": 100.0}]},
    ]
    semantics = _semantics([{"label": "kitchen", "label_zh": "廚房", "area_m2": 8.0,
                             "bbox": [0, 0, 400, 400]}], width=400, height=400)

    assert apply_floorplan2room_labels(
        rooms, semantics, image_width=400, image_height=400,
        plan_bbox_px=None, cm_per_px=1.0,
    ) == 0
    assert apply_floorplan2room_labels(
        rooms, semantics, image_width=400, image_height=400,
        plan_bbox_px=[0.0, 0.0, 400.0, 400.0], cm_per_px=0,
    ) == 0
    assert rooms[0]["source"] == "cody_wall_enclosure"


# ── 端對端：CODY_MAIN_SYNC_TODO 驗收條件 ────────────────────────────────────
def test_analysis_labels_rooms_from_semantic_pipeline(sample_bytes: bytes) -> None:
    """驗收條件二：上傳平面圖後 rooms[].label 來自語意管線而非 fallback。"""
    from backend.floorplan.vision.analysis import analyze_floorplan_image

    result = analyze_floorplan_image(sample_bytes, filename="floor01.png")

    assert result["cody_room_semantics"] is not None
    assert result["cody_room_semantic_labels_applied"] > 0
    semantic_rooms = [r for r in result["rooms"] if r.get("source") == "cody_floorplan2room"]
    assert semantic_rooms, "至少要有一間房型由 floorplan2room 提供"
    for room in semantic_rooms:
        # 房型必須落在主線契約詞彙裡，不能是 cody 的 bed/bath/living 原字彙。
        assert room["type"] in {label for label, _ in __import__(
            "backend.floorplan.vision.analysis", fromlist=["ROOM_LABELS"]
        ).ROOM_LABELS}


def test_analysis_still_completes_when_semantics_unavailable(
    sample_bytes: bytes, monkeypatch
) -> None:
    """驗收條件三：語意管線不可用時仍以既有 fallback 完成分析。"""
    from backend.floorplan.vision import analysis as analysis_module

    monkeypatch.setattr(analysis_module, "recognize_cody_rooms", lambda *_a, **_k: None)
    result = analysis_module.analyze_floorplan_image(sample_bytes, filename="floor01.png")

    assert result["cody_room_semantics"] is None
    assert result["cody_room_semantic_labels_applied"] == 0
    assert result["rooms"], "沒有語意也要照常產出房間"
    assert result["walls"], "幾何路徑不受語意管線影響"


# ── 降級模式不得蓋掉主線既有判斷 ────────────────────────────────────────────
def _sem_with_source(rooms, source):
    return {"image": {"w": 100, "h": 100}, "rooms": rooms, "room_label_source": source}


def test_area_rule_fallback_must_not_overwrite_a_confident_type() -> None:
    """cody 無語意快取時走自己的面積規則，那不比主線圖示推論可靠，不得覆蓋。"""
    rooms = [
        {"id": "kitchen-1", "type": "kitchen", "label": "廚房",
         "source": "furniture_icon_inference", "bbox_px": [10.0, 10.0, 30.0, 30.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _sem_with_source([{"label": "bed", "label_zh": "臥室", "area_m2": 12.0,
                           "bbox": [0, 0, 50, 50]}], "area_rules"),
        image_width=100,
        image_height=100,
    )

    assert applied == 0
    assert rooms[0]["type"] == "kitchen"
    assert rooms[0]["source"] == "furniture_icon_inference"


def test_area_rule_fallback_still_fills_rooms_with_no_type() -> None:
    """主線沒判斷出房型的空位，降級標籤仍比什麼都沒有好。"""
    rooms = [
        {"id": "room-1", "type": "default", "label": "空間 1",
         "source": "cody_wall_enclosure", "bbox_px": [10.0, 10.0, 30.0, 30.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _sem_with_source([{"label": "bed", "label_zh": "臥室", "area_m2": 12.0,
                           "bbox": [0, 0, 50, 50]}], "area_rules"),
        image_width=100,
        image_height=100,
    )

    assert applied == 1
    assert rooms[0]["type"] == "bedroom"


def test_true_semantics_may_overwrite_a_confident_type() -> None:
    """CubiCasa 語意是 TODO 指定的房型來源，優先於圖示規則。"""
    rooms = [
        {"id": "kitchen-1", "type": "kitchen", "label": "廚房",
         "source": "furniture_icon_inference", "bbox_px": [10.0, 10.0, 30.0, 30.0]},
    ]
    applied = apply_floorplan2room_labels(
        rooms,
        _sem_with_source([{"label": "bed", "label_zh": "臥室", "area_m2": 12.0,
                           "bbox": [0, 0, 50, 50]}], "cubicasa_semantic"),
        image_width=100,
        image_height=100,
    )

    assert applied == 1
    assert rooms[0]["type"] == "bedroom"
    assert rooms[0]["source"] == "cody_floorplan2room"
