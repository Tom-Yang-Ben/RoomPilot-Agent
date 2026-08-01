"""語意層鍵傳遞與房型對照（2026-07 盤點「房型語意斷鏈」的修復測試）。

守住三件事：

1. `analyze_floorplan_image` 必須把上傳檔名主幹傳給 `recognize_cody_rooms`。
   原因已隨 2026-07-30 的 CubiCasa 移除改變——當時是為了命中
   `cubicasa/room/<stem>_mask.npz` 快取，現在是為了讓暫存圖與 OCR 單格快取
   有穩定命名，日誌與診斷追得回是哪張圖。
2. 語意層的 entry/storage/outdoor 房型不得再被 `CODY_ROOM_TYPE_MAP` 靜默丟棄，
   且新增的 stair 必須有明確映射（刻意為 None，見該處註解）。
3. floor01 可端到端由 DINOv2 判出房型（`room_label_source == "dinov2_semantic"`），
   且廚房／玄關能落到主線 rooms[].type。

外部資產（testdata 圖）不存在時安全跳過，符合 tests/AGENTS.md。
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


# 2026-07-30：原本這一節有三支 `_cc_ok` 測試（尺寸相符/成比例接受、floor10 長寬比
# 錯配拒絕、舊快取缺 room 通道拒絕）。CubiCasa 語意遮罩快取隨血統移除一併消失，
# `_cc_ok` 與 `cubicasa/room/*_mask.npz` 都不存在了，這三支測的機制沒有了主體。
# DINOv2 路徑無快取層——每次裁切現推，故不存在對應的錯配風險，不需要替代測試。


# ── 3. 房型對照表 ────────────────────────────────────────────────


def test_room_type_map_lands_entry_storage_outdoor_stair_and_garage() -> None:
    assert analysis.CODY_ROOM_TYPE_MAP["entry"] == "entryway"
    assert analysis.CODY_ROOM_TYPE_MAP["storage"] == "storage"
    assert analysis.CODY_ROOM_TYPE_MAP["outdoor"] == "balcony"
    assert analysis.CODY_ROOM_TYPE_MAP["garage"] == "garage"
    assert analysis.CODY_ROOM_TYPE_MAP["room"] is None
    # stair 是 2026-07-29 語意層新增的類（MAIN_SYNC_TODO 第 10 節）。刻意映射為
    # None：樓梯區的產品語意是「不可擺設」，硬塞 circulation 會被當可佈置走道。
    assert analysis.CODY_ROOM_TYPE_MAP["stair"] == "stair"


# ── 4. floor01 端到端：補鍵即命中語意快取 ───────────────────────


@needs_floor01_cache
def test_floor01_cache_key_restores_semantic_rooms() -> None:
    result = recognize_cody_rooms(FLOOR01.read_bytes(), cache_key="floor01")

    assert result is not None
    assert result["room_label_source"] == "dinov2_semantic"
    labels = {room["label"] for room in result["rooms"]}
    assert "kitchen" in labels, "floor01 應認出廚房"
    assert "entry" in labels, "floor01 應認出玄關"


@needs_floor01_cache
def test_analyze_floor01_lands_kitchen_and_entry_types() -> None:
    result = analysis.analyze_floorplan_image(
        FLOOR01.read_bytes(), filename="floor01.png"
    )

    types = {room.get("type") for room in result["rooms"]}
    assert "kitchen" in types, "廚房應由語意層落到主線 rooms[].type"
    assert "circulation" in types, "玄關不得再被對照表靜默丟棄"
