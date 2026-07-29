"""語意快取鍵對齊與尺寸驗證（2026-07 盤點「房型語意斷鏈」的修復測試）。

守住四件事：

1. `analyze_floorplan_image` 必須把上傳檔名主幹傳給 `recognize_cody_rooms`——
   `cubicasa/room/<stem>_mask.npz` 語意快取全以檔名為鍵，斷鍵即 100% 降級到
   面積規則。
2. 檔名鍵快取與影像尺寸錯配（floor10 案例：896×1200 對 419×687）必須被
   `_cc_ok` 擋下，不得無檢查最近鄰縮放硬套。
3. 語意層的 entry/storage/outdoor 房型不得再被 `CODY_ROOM_TYPE_MAP` 靜默丟棄。
4. floor01 帶檔名鍵可端到端命中語意快取（`room_label_source ==
   "cubicasa_semantic"`），且廚房／玄關能落到主線 rooms[].type。

外部資產（testdata 圖與語意快取）不存在時安全跳過，符合 tests/AGENTS.md。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.floorplan import floorplan2room
from backend.floorplan.cody_adapter import recognize_cody_rooms
from backend.floorplan.vision import analysis

REPO_ROOT = Path(__file__).resolve().parents[1]
FLOOR01 = REPO_ROOT / "testdata" / "png" / "floor01.png"
FLOOR01_CACHE = REPO_ROOT / "cubicasa" / "room" / "floor01_mask.npz"

needs_floor01 = pytest.mark.skipif(
    not FLOOR01.exists(), reason="需要 testdata/png/floor01.png"
)
needs_floor01_cache = pytest.mark.skipif(
    not (FLOOR01.exists() and FLOOR01_CACHE.exists()),
    reason="需要 floor01 測資與 cubicasa/room/floor01_mask.npz 語意快取",
)


# ── 1. 檔名 → 快取鍵 ──────────────────────────────────────────────


def test_semantic_cache_key_uses_ascii_filename_stem() -> None:
    assert analysis._semantic_cache_key("floor01.png") == "floor01"
    assert analysis._semantic_cache_key("1041.PNG") == "1041"
    assert analysis._semantic_cache_key("my-plan_2.jpg") == "my-plan_2"
    assert analysis._semantic_cache_key("noext") == "noext"


def test_semantic_cache_key_falls_back_for_unsafe_names() -> None:
    assert analysis._semantic_cache_key("我家平面圖.png") is None
    assert analysis._semantic_cache_key("floor plan (1).png") is None
    assert analysis._semantic_cache_key("") is None
    assert analysis._semantic_cache_key(None) is None
    # 路徑成分一律剝除，不可能組出跳脫路徑的鍵。
    assert analysis._semantic_cache_key("../../etc/passwd.png") == "passwd"


@needs_floor01
def test_analyze_passes_filename_stem_to_semantic_layer(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_rooms(image_bytes: bytes, *, cache_key: str | None = None):
        captured["cache_key"] = cache_key
        return None  # 上游應照常退回圖示規則，不得炸掉

    monkeypatch.setattr(analysis, "recognize_cody_rooms", fake_rooms)

    result = analysis.analyze_floorplan_image(
        FLOOR01.read_bytes(), filename="floor01.png"
    )

    assert captured["cache_key"] == "floor01"
    assert result["rooms"], "語意層回 None 時仍須產出房間"


# ── 2. 快取尺寸驗證 ──────────────────────────────────────────────


def _write_mask_npz(path: Path, shape: tuple[int, int]) -> None:
    np.savez(
        path,
        room=np.zeros(shape, dtype=np.uint8),
        icon=np.zeros(shape, dtype=np.uint8),
    )


def test_cc_ok_accepts_matching_and_proportional_masks(tmp_path: Path) -> None:
    cache = tmp_path / "x_mask.npz"
    _write_mask_npz(cache, (100, 150))

    assert floorplan2room._cc_ok(str(cache)) is True  # 建快取路徑：只問可用性
    assert floorplan2room._cc_ok(str(cache), (100, 150)) is True
    assert floorplan2room._cc_ok(str(cache), (200, 300)) is True  # 彩圖管線 2 倍


def test_cc_ok_rejects_aspect_mismatched_mask(tmp_path: Path) -> None:
    cache = tmp_path / "floor10_mask.npz"
    _write_mask_npz(cache, (1200, 896))  # 已知錯配案例的快取尺寸

    assert floorplan2room._cc_ok(str(cache), (687, 419)) is False


def test_cc_ok_rejects_legacy_cache_without_room_channel(tmp_path: Path) -> None:
    cache = tmp_path / "old_mask.npz"
    np.savez(cache, wall=np.zeros((10, 10), dtype=np.uint8))

    assert floorplan2room._cc_ok(str(cache), (10, 10)) is False


# ── 3. 房型對照表 ────────────────────────────────────────────────


def test_room_type_map_lands_entry_storage_outdoor() -> None:
    # circulation 與 storage 是前端推薦表（scene_layout2d.js）的既有契約鍵。
    assert analysis.CODY_ROOM_TYPE_MAP["entry"] == "circulation"
    assert analysis.CODY_ROOM_TYPE_MAP["storage"] == "storage"
    assert analysis.CODY_ROOM_TYPE_MAP["outdoor"] == "balcony"
    assert analysis.CODY_ROOM_TYPE_MAP["garage"] is None
    assert analysis.CODY_ROOM_TYPE_MAP["room"] is None


# ── 4. floor01 端到端：補鍵即命中語意快取 ───────────────────────


@needs_floor01_cache
def test_floor01_cache_key_restores_semantic_rooms() -> None:
    result = recognize_cody_rooms(FLOOR01.read_bytes(), cache_key="floor01")

    assert result is not None
    assert result["room_label_source"] == "cubicasa_semantic"
    labels = {room["label"] for room in result["rooms"]}
    assert "kitchen" in labels, "floor01 語意快取應認出廚房"
    assert "entry" in labels, "floor01 語意快取應認出玄關"


@needs_floor01_cache
def test_analyze_floor01_lands_kitchen_and_entry_types() -> None:
    result = analysis.analyze_floorplan_image(
        FLOOR01.read_bytes(), filename="floor01.png"
    )

    types = {room.get("type") for room in result["rooms"]}
    assert "kitchen" in types, "廚房應由語意層落到主線 rooms[].type"
    assert "circulation" in types, "玄關不得再被對照表靜默丟棄"
