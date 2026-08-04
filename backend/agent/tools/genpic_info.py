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
    # 尺寸等數值不進提示詞（定案）：位置與朝向用相對措辭，數值只留在座標翻譯的輸入端。
    lines = []
    for row in scene.placed_in(room.room_id):
        lines.append(
            "{name}（{type}，{pos}，{facing}）".format(
                name=row.get("name", row.get("id", "家具")),
                type=row.get("type", ""),
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
        # 提示詞模板（2026-08-04 使用者定案）：
        # 「渲染成寫實風格，房間：{}、整體風格：{}、風格參考：{}、
        #   色調採(60%, 30%, 10%)：{}、地板材質：{}、牆壁材質：{}、
        #   家具配置(位置與數量必須與下列完全一致，不可增減或移動)：{}、
        #   家電：{}、{額外補充需求}」
        # 有數值資訊（尺寸/公分）不提供；沒有資料的段落整段省略。
        segments = [f"渲染成寫實風格，房間：{room.name}"]
        if requirements.styles:
            segments.append(f"整體風格：{'、'.join(requirements.styles[:2])}")
            note = style_note(requirements.styles)
            if note:
                segments.append(note)   # 已含「風格參考（…）：」前綴
        if palette:
            colors = "、".join(str(c) for c in (palette.get("colors") or [])[:5])
            segments.append(f"色調採(60%, 30%, 10%)：{colors}")
        materials = requirements.materials or {}
        for key, label in (("地板", "地板材質"), ("牆面", "牆壁材質")):
            if materials.get(key):
                segments.append(f"{label}：{materials[key]}")
        furniture = furniture_lines(scene, room)
        if furniture:
            segments.append(
                "家具配置(位置與數量必須與下列完全一致，不可增減或移動)："
                + "、".join(furniture)
            )
        appliances = [
            item.text for item in requirements.appliances if item.room_id in (None, room.room_id)
        ]
        if appliances:
            segments.append("家電：" + "、".join(appliances))
        if viewpoint and viewpoint.get("note"):
            segments.append(str(viewpoint["note"]))
        prompt = "、".join(segments)
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
