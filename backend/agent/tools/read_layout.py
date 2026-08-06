"""讀室內架構 tool：layout_json → ``LayoutDoc``，並轉換為 engine ``Room``。

平面圖辨識輸出 ``layout_json``（Cody），server 端另有
``backend.server.scene_service.room_from_payload`` 做完整轉換。本 tool 接受
「已確認格局」的簡化房間清單並做欄位容錯；正式整合時應以
``docs/contracts/LAYOUT_SCENE_BOUNDARY_CONTRACT.md`` 對齊欄位。

單位契約：一律公分。``width``/``depth`` 這類相容欄位需帶
``coordinate_unit: "cm"``；新欄位使用 ``_cm`` 結尾。
"""
from __future__ import annotations

from typing import Any

from backend.engine.models import Room, Wall

from ..documents import LayoutDoc, LayoutRoom
from .base import ToolContract, ToolError

_ID_KEYS = ("room_id", "id", "space_id")
_NAME_KEYS = ("name", "space_name", "label", "room_name")
_WIDTH_KEYS = ("width_cm", "width", "w")
_DEPTH_KEYS = ("depth_cm", "depth", "d")


def _pick(row: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return None


class ReadLayoutTool:
    contract = ToolContract(
        name="read_layout",
        description="解析室內架構（layout_json 房間清單）為 LayoutDoc；長度一律公分。",
        input_schema={
            "type": "object",
            "properties": {"layout_json": {"type": "object"}},
            "required": ["layout_json"],
        },
        output_schema={"type": "object", "description": "LayoutDoc dict"},
    )

    def run(self, layout_json: dict) -> LayoutDoc:
        rows = layout_json.get("rooms")
        if not isinstance(rows, list) or not rows:
            raise ToolError("layout_json 缺少 rooms 清單", tool=self.contract.name)
        rooms: list[LayoutRoom] = []
        problems: list[str] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                problems.append(f"rooms[{index}] 不是物件")
                continue
            width = _pick(row, _WIDTH_KEYS)
            depth = _pick(row, _DEPTH_KEYS)
            if width is None or depth is None:
                problems.append(f"rooms[{index}] 缺少寬/深（公分）")
                continue
            room_id = str(_pick(row, _ID_KEYS) or f"room_{index + 1}")
            name = str(_pick(row, _NAME_KEYS) or room_id)
            walls = [wall for wall in (row.get("walls") or []) if isinstance(wall, dict)]
            rooms.append(
                LayoutRoom(
                    room_id=room_id,
                    name=name,
                    width_cm=float(width),
                    depth_cm=float(depth),
                    walls=walls,
                )
            )
        if not rooms:
            raise ToolError(
                "layout_json 沒有可用房間：" + "；".join(problems), tool=self.contract.name
            )
        return LayoutDoc(rooms=rooms)


def to_engine_room(room: LayoutRoom) -> Room:
    """LayoutRoom → engine ``Room``。牆體欄位不足時忽略該段牆。"""
    walls: list[Wall] = []
    for row in room.walls:
        try:
            walls.append(
                Wall(
                    x1=float(row["x1"]),
                    y1=float(row["y1"]),
                    x2=float(row["x2"]),
                    y2=float(row["y2"]),
                    thickness=float(row.get("thickness", 10.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return Room(width=room.width_cm, depth=room.depth_cm, walls=walls)
