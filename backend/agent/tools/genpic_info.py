"""生圖資訊整理 tool：組出生圖提示詞包與鎖定清單（deterministic）。

依定案：視角畫面（Three.js 截圖）作構圖參考、提示詞素材來自需求文件
（含材質與家電 context）、色卡與場景配置。改圖時額外產出「鎖定清單」，
明確告訴模型只能改使用者指定的內容、其餘元素保持不變。

家電只在這裡進入畫面描述（渲染 context），不影響任何配置決策。
位置措辭是把 engine 算好的座標翻成文字，不是幾何決策。
"""
from __future__ import annotations

from ..documents import (
    LayoutRoom,
    LockManifestDoc,
    RequirementDoc,
    SceneDoc,
)
from .base import ToolContract
from .design_knowledge import style_note

_ROTATION_FACING = {0: "面向上緣", 90: "面向左緣", 180: "面向下緣", 270: "面向右緣"}


def position_phrase(pos_x: float, pos_y: float, width_cm: float, depth_cm: float) -> str:
    """把公分座標翻成構圖用的相對位置措辭（左/中/右 × 前/中/後）。"""
    third_x = "左側" if pos_x < width_cm / 3 else ("右側" if pos_x > width_cm * 2 / 3 else "中間")
    third_y = "前段" if pos_y < depth_cm / 3 else ("後段" if pos_y > depth_cm * 2 / 3 else "中段")
    if third_x == "中間" and third_y == "中段":
        return "房間中央"
    return f"房間{third_y}{third_x}"


def facing_phrase(rotation: float) -> str:
    return _ROTATION_FACING.get(int(rotation) % 360, f"旋轉 {rotation:.0f} 度")


def furniture_lines(scene: SceneDoc, room: LayoutRoom) -> list[str]:
    lines = []
    for row in scene.placed_in(room.room_id):
        lines.append(
            "{name}（{type}，{w:.0f}x{d:.0f}cm，{pos}，{facing}）".format(
                name=row.get("name", row.get("id", "家具")),
                type=row.get("type", ""),
                w=float(row.get("width", 0)),
                d=float(row.get("depth", 0)),
                pos=position_phrase(
                    float(row.get("pos_x", 0)),
                    float(row.get("pos_y", 0)),
                    room.width_cm,
                    room.depth_cm,
                ),
                facing=facing_phrase(float(row.get("rotation", 0))),
            )
        )
    return lines


class GenPicInfoTool:
    contract = ToolContract(
        name="genpic_info",
        description="整理生圖提示詞包（需求＋材質＋色卡＋場景＋家電 context）與鎖定清單。",
        input_schema={
            "type": "object",
            "properties": {
                "requirements": {"type": "object"},
                "scene": {"type": "object"},
                "room": {"type": "object"},
                "palette": {"type": ["object", "null"]},
                "viewpoint": {"type": ["object", "null"]},
                "stage": {"type": "string"},
            },
            "required": ["requirements", "scene", "room", "stage"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "lock_manifest": {"type": "object"},
            },
        },
    )

    def run(
        self,
        requirements: RequirementDoc,
        scene: SceneDoc,
        room: LayoutRoom,
        *,
        stage: str,
        palette: dict | None = None,
        viewpoint: dict | None = None,
    ) -> dict:
        lines = [
            "高品質室內設計實景渲染（photorealistic）。",
            f"房間：{room.name}（{room.width_cm:.0f}x{room.depth_cm:.0f} 公分）。",
        ]
        if requirements.styles:
            lines.append(f"整體風格：{'、'.join(requirements.styles[:2])}。")
            note = style_note(requirements.styles)
            if note:
                lines.append(f"{note}。")
        if palette:
            colors = "、".join(str(c) for c in (palette.get("colors") or [])[:5])
            lines.append(f"色卡「{palette.get('name', palette.get('palette_id', ''))}」主色：{colors}。")
        materials = requirements.materials or {}
        if materials:
            material_text = "；".join(f"{key}：{value}" for key, value in materials.items())
            lines.append(f"表面材質：{material_text}。")
        furniture = furniture_lines(scene, room)
        if furniture:
            lines.append("家具配置（位置與數量必須與下列完全一致，不可增減或移動）：")
            lines.extend(f"- {line}" for line in furniture)
        appliances = [
            item.text for item in requirements.appliances if item.room_id in (None, room.room_id)
        ]
        if appliances:
            lines.append(
                "情境家電（只作為畫面元素呈現，不改變家具配置）："
                + "、".join(appliances)
                + "。"
            )
        if viewpoint and viewpoint.get("note"):
            lines.append(f"視角：{viewpoint['note']}。")
        lines.append(
            "構圖：嚴格依照附上的視角截圖之相機角度與家具位置生成；"
            "比例正確、光線自然、材質真實。"
        )
        prompt = "\n".join(lines)
        manifest = LockManifestDoc(
            room_id=room.room_id,
            palette_id=(palette or {}).get("palette_id"),
            viewpoint_id=(viewpoint or {}).get("viewpoint_id"),
            locked_furniture=furniture,
            locked_materials={**materials, "palette": (palette or {}).get("name", "")},
            allowed_change="",
        )
        return {"prompt": prompt, "lock_manifest": manifest.to_dict(), "stage": stage}

    @staticmethod
    def edit_instruction(lock_manifest: LockManifestDoc, feedback: str) -> str:
        """把使用者意見與鎖定清單組成「只改這些、其餘不動」的編輯指令。"""
        lines = [
            f"請只修改以下內容：{feedback.strip()}。",
            "除上述修改外，畫面其他一切必須與附圖完全一致，特別是：",
        ]
        for row in lock_manifest.locked_furniture:
            lines.append(f"- {row}（位置、樣式、數量不可變）")
        if lock_manifest.locked_materials:
            material_text = "；".join(
                f"{key}：{value}" for key, value in lock_manifest.locked_materials.items() if value
            )
            if material_text:
                lines.append(f"- 材質與色調維持：{material_text}")
        lines.append("- 相機視角、房間結構、門窗位置完全不變。")
        return "\n".join(lines)
