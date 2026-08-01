"""印刷房名／尺寸標註 OCR 的接線測試（2026-07 盤點第 3 項「OCR 死碼」修復）。

paddle 刻意不進團隊基線（requirements.txt 注記：體積大且平台特定），因此
這裡全部用假供應者驗「接線」與「降級」，不需要安裝 paddleocr——符合
tests/AGENTS.md「外部資產與權重必須 opt-in 或安全跳過」的原則。

守住四件事：
1. `default_ocr_provider` 是單例（lru_cache），且 paddle 未安裝／引擎初始化
   失敗都安靜回 None，不炸請求路徑。
2. 產品主路徑 `/api/projects/{id}/floorplan/analyze` 真的會呼叫 OCR 供應者
   ——這正是先前的死碼點（provider 從未被建構）。
3. `ROOMPILOT_OCR_DISABLED=1` 能現場停用。
4. 供應者執行中拋例外時，辨識主流程照常完成（OCR 只是輔助證據）。
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.floorplan.vision import analysis, ocr
from backend.server import main as server_main

client = TestClient(server_main.app)

REPO_ROOT = Path(__file__).resolve().parents[1]
FLOOR01 = REPO_ROOT / "testdata" / "png" / "floor01.png"

needs_floor01 = pytest.mark.skipif(
    not FLOOR01.exists(), reason="需要 testdata/png/floor01.png"
)


class _RecordingProvider:
    def __init__(self, observations: list | None = None, error: Exception | None = None):
        self.calls = 0
        self._observations = observations or []
        self._error = error

    def recognize(self, image_bytes: bytes) -> list:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return list(self._observations)


# ── 1. 單例與安靜降級 ───────────────────────────────────────────


def test_default_provider_is_cached_and_none_without_paddle(monkeypatch) -> None:
    ocr.default_ocr_provider.cache_clear()
    constructed: list[int] = []

    class MissingPaddle:
        def __init__(self) -> None:
            constructed.append(1)
            raise ModuleNotFoundError("paddleocr")

    monkeypatch.setattr(ocr, "PaddleOCRProvider", MissingPaddle)
    try:
        assert ocr.default_ocr_provider() is None
        assert ocr.default_ocr_provider() is None
        # lru_cache 單例：不會每個請求都重試建構引擎。
        assert len(constructed) == 1
    finally:
        ocr.default_ocr_provider.cache_clear()


def test_default_provider_survives_engine_init_failure(monkeypatch) -> None:
    ocr.default_ocr_provider.cache_clear()

    class BrokenEngine:
        def __init__(self) -> None:
            raise RuntimeError("模型下載失敗")

    monkeypatch.setattr(ocr, "PaddleOCRProvider", BrokenEngine)
    try:
        assert ocr.default_ocr_provider() is None
    finally:
        ocr.default_ocr_provider.cache_clear()


# ── 2. 產品主路徑真的會呼叫供應者（先前的死碼點）─────────────────


def _project_with_floor01() -> str:
    project = client.post(
        "/api/projects", json={"name": f"ocr接線-{uuid4().hex[:8]}"}
    ).json()["project"]
    project_id = project["project_id"]
    uploaded = client.post(
        f"/api/projects/{project_id}/floorplan",
        files={"file": ("floor01.png", FLOOR01.read_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    saved = client.put(
        f"/api/projects/{project_id}/workflow",
        json={
            "current_step": "upload",
            "workflow": {"floorplan_confirmation": {"confirmed": True}},
        },
    )
    assert saved.status_code == 200
    return project_id


@needs_floor01
def test_product_analyze_path_invokes_ocr_provider(monkeypatch) -> None:
    provider = _RecordingProvider()
    monkeypatch.setattr(server_main, "_floorplan_ocr_provider", lambda: provider)
    project_id = _project_with_floor01()

    analyzed = client.post(f"/api/projects/{project_id}/floorplan/analyze")

    assert analyzed.status_code == 200
    assert provider.calls == 1, "產品主路徑必須把 OCR 供應者接進 analyze"


# ── 3. 現場停用旗標 ─────────────────────────────────────────────


def test_ocr_disabled_env_skips_provider_construction(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_OCR_DISABLED", "1")
    monkeypatch.setattr(
        server_main,
        "default_ocr_provider",
        lambda: pytest.fail("停用旗標下不得建構 OCR 供應者"),
    )

    assert server_main._floorplan_ocr_provider() is None


# ── 4. 供應者執行失敗不得拖垮辨識 ───────────────────────────────


@needs_floor01
def test_provider_crash_does_not_break_analysis() -> None:
    result = analysis.analyze_floorplan_image(
        FLOOR01.read_bytes(),
        filename="floor01.png",
        ocr_provider=_RecordingProvider(error=RuntimeError("paddle 執行中炸掉")),
    )

    assert result["rooms"], "OCR 失敗時主流程仍須產出完整辨識結果"


# ── 4a. 黃金圖參考標註優先於即時 OCR ────────────────────────────────


BUILDER_630 = REPO_ROOT / "testdata" / "png" / "builder_plan_630.png"


@pytest.mark.skipif(not BUILDER_630.exists(), reason="需要 builder_plan_630 測資")
def test_reference_annotations_outrank_live_ocr_provider() -> None:
    """630 黃金圖有已驗收的參考標註；真 OCR 不得搶走標準答案
    （2026-07-29 mac 實跑：paddle 先執行導致 confirm 422 與 review_items 非空）。"""
    provider = _RecordingProvider(
        observations=[{"text": "999", "bbox": [0.0, 0.0, 10.0, 10.0], "confidence": 0.9}]
    )

    result = analysis.analyze_floorplan_image(
        BUILDER_630.read_bytes(),
        filename="builder_plan_630.png",
        ocr_provider=provider,
    )

    assert provider.calls == 0, "參考標註存在時不得呼叫 OCR 供應者"
    assert result["scale"]["distance_cm"] == 630.0


# ── 4b. 同圈圍多房名去重與印刷房名優先權（floor01 實跑病灶）────────────


def _polygon(points: list[tuple[float, float]]) -> list[dict[str, float]]:
    return [{"x": x, "y": y} for x, y in points]


def test_duplicate_ocr_label_in_same_enclosure_is_dropped() -> None:
    rooms = [
        {  # 領到多邊形的客廳（圈圍發給第一個命中的標籤）
            "id": "living_room-1", "type": "living_room", "label": "LIVING ROOM",
            "source": "ocr_room_label", "centroid_m": {"x": 2.0, "y": 2.0},
            "polygon_m": _polygon([(0, 0), (7, 0), (7, 7), (0, 7)]),
        },
        {  # 同一圈圍裡的第二塊房名：沒多邊形、質心落在客廳裡 → 重複計數
            "id": "kitchen-1", "type": "kitchen", "label": "KITCHEN",
            "source": "ocr_room_label", "centroid_m": {"x": 5.0, "y": 5.0},
        },
        {  # 圈圍偵測失敗但位置獨立的 OCR 房 → 保留
            "id": "bathroom-1", "type": "bathroom", "label": "BATH",
            "source": "ocr_room_label", "centroid_m": {"x": 20.0, "y": 20.0},
        },
        {  # 非 OCR 來源、沒多邊形 → 不在去重範圍
            "id": "room-2", "type": "default", "label": "空間 2",
            "source": "cody_wall_enclosure", "centroid_m": {"x": 6.0, "y": 6.0},
        },
    ]

    kept = analysis._drop_duplicate_ocr_label_rooms(rooms)

    kept_ids = [room["id"] for room in kept]
    assert "kitchen-1" not in kept_ids, "同圈圍第二塊房名是重複房，必須砍掉"
    assert kept_ids == ["living_room-1", "bathroom-1", "room-2"]


def test_semantic_layer_must_not_overwrite_printed_room_labels() -> None:
    rooms = [
        {
            "id": "storage-1", "type": "storage", "label": "WALK-IN CLOSET",
            "source": "ocr_room_label", "bbox_px": [10.0, 10.0, 30.0, 30.0],
        }
    ]
    semantics = {
        "room_label_source": "cubicasa_semantic",  # 具覆蓋權的語意來源
        "image": {"w": 100, "h": 100},
        "rooms": [{
            "label": "kitchen", "label_zh": "廚房", "area_m2": 49.3,
            "bbox": [0, 0, 50, 50],
        }],
    }

    applied = analysis.apply_floorplan2room_labels(
        rooms, semantics, image_width=100, image_height=100
    )

    assert applied == 0
    assert rooms[0]["type"] == "storage", "印刷房名不得被模型語意覆蓋"
    assert rooms[0]["label"] == "WALK-IN CLOSET"


# ── 5. 美式圖調校：英文房名與英呎吋（floor01 實跑 OCR 輸出的實例）──────


def test_room_type_matches_english_printed_labels() -> None:
    # 以下皆為 floor01 於 mac 實跑 PaddleOCR 的真實輸出（信心 0.98-1.0）。
    assert analysis._room_type("MASTER BEDROOM") == "bedroom"
    assert analysis._room_type("BEDROOM #2") == "bedroom"
    assert analysis._room_type("BEDROOM #3") == "bedroom"
    assert analysis._room_type("BATH") == "bathroom"
    assert analysis._room_type("KITCHEN") == "kitchen"
    assert analysis._room_type("LIVING ROOM") == "living_room"
    assert analysis._room_type("WALK-IN CLOSET") == "storage"
    assert analysis._room_type("HALL") == "hallway"
    assert analysis._room_type("STAIR") == "stair"
    # 中文別名不受 casefold 影響。
    assert analysis._room_type("主臥室") == "bedroom"
    assert analysis._room_type("儲藏室") == "storage"
    # 純尺寸標籤不是房名。
    assert analysis._room_type("9'-0\"x 12'-0\"") is None


def test_number_m_parses_imperial_dimension_annotations() -> None:
    assert analysis._number_m("9'-0\"") == pytest.approx(2.7432)
    assert analysis._number_m("12'6\"") == pytest.approx(3.81)
    assert analysis._number_m("10'") == pytest.approx(3.048)
    # OCR 常見的彎引號變體。
    assert analysis._number_m("9’-0”") == pytest.approx(2.7432)
    # 複合房間尺寸標籤刻意不收（配錯牆線會毀掉整張比例尺）。
    assert analysis._number_m("9'-0\"x 12'-0\"") is None
    # 公制行為不變。
    assert analysis._number_m("300 cm") == pytest.approx(3.0)
    assert analysis._number_m("3200mm") == pytest.approx(3.2)


@needs_floor01
def test_product_analyze_survives_provider_crash(monkeypatch) -> None:
    provider = _RecordingProvider(error=RuntimeError("paddle 執行中炸掉"))
    monkeypatch.setattr(server_main, "_floorplan_ocr_provider", lambda: provider)
    project_id = _project_with_floor01()

    analyzed = client.post(f"/api/projects/{project_id}/floorplan/analyze")

    assert analyzed.status_code == 200
    assert provider.calls == 1
