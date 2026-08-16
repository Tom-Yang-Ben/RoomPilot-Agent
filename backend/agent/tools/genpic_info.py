"""生圖資訊整理 tool：組出生圖提示詞包與鎖定清單（deterministic）。

依定案：視角畫面（Three.js 截圖）作構圖參考、提示詞素材來自需求文件
（含材質與家電 context）、色卡與場景配置。家具逐件附型錄／RAG 的 VLM
外觀描述（顏色、材質、腿型、線條），讓模型畫對每件家具而不是照名稱猜。
改圖時額外產出「鎖定清單」，明確告訴模型只能改使用者指定的內容、
其餘元素保持不變。

家電只在這裡進入畫面描述（渲染 context），不影響任何配置決策。
"""
from __future__ import annotations

import re

from ..documents import (
    LayoutRoom,
    LockManifestDoc,
    RequirementDoc,
    SceneDoc,
)
from .base import ToolContract
from .design_knowledge import style_note

# 型錄 primary_material 有近三成是這個佔位字串（Kai 的 VLM 未標示材質時的
# 預設值）。放進提示詞只會讓模型去猜「GLB」是什麼材質，逐筆濾掉。
MATERIAL_PLACEHOLDERS = {"glb材質（未標示）", "未標示", "unknown", "none"}

# RAG／型錄的 VLM 描述（``roompilot.furniture_catalog_current.description``，
# 平均約 120 字）是家具外觀的唯一文字證據：顏色、布料或皮革、腿型、線條。
# 只有生圖提示詞吃它；報告與鎖定清單仍用短標籤。
DESCRIPTION_MAX_CHARS = 90
# 描述結尾常是「適合現代客廳…」這類用途建議，對畫面沒有貢獻，整句丟棄。
USAGE_SENTENCE_PREFIXES = ("適合", "無論", "可搭配")

# 生圖光影提示（結尾補述）：預設白天日光；客廳另出一張夜間光影供設計手冊並列。
# "day" 維持既有字串不變，避免動到現有全房生圖的輸出。
_LIGHTING_HINTS = {
    "day": "光影以窗戶陽光及室內燈光為主",
    "night": "光影以夜晚室內燈光為主，窗外為入夜暗景，呈現溫暖靜謐的夜間氛圍",
}

# 房型專屬補述（2026-08-14 使用者定案）：固定設備不在白模也不在家具清單裡，
# 模型照著截圖畫就會生出沒有馬桶的浴室、沒有廚具的廚房；陽台的白色地面則常
# 被當成室內地板。這三類空間必須用文字把它補回來。
_ROOM_TYPE_HINTS = {
    "bathroom": "必須包含衛浴設備（馬桶、洗手台、淋浴設備）",
    "kitchen": "必須包含系統廚具（整排廚櫃、檯面、水槽與爐具）以及冰箱",
    "balcony": "白色部分為「室外」空間，室外空間風景以高樓眺望出去的風景為主",
}
# room_type 是權威訊號，中文房名為容錯後援（對齊 master._is_living_room 的判法）。
_ROOM_TYPE_ALIASES = {"bath": "bathroom"}
_ROOM_NAME_TOKENS = (
    ("bathroom", ("衛浴", "浴室", "廁所")),
    ("kitchen", ("廚房",)),
    ("balcony", ("陽台", "露台")),
)

# 尺寸不進生圖提示詞（定案；2026-08-14 起浴室／廚房／陽台例外，見 room_size_note）：
# 畫面比例由 img2img 視角截圖鎖定，文字給了數字
# 只會讓模型照數字重新推比例。部分型錄名稱會帶規格，例如
# 「206x46x54 公分」「88"W」「5' 3"」），描述偶爾也帶（201 件）。
# 鎖定清單與設計手冊要保留規格，所以只在提示詞這條路上清掉。
_UNIT = (
    r"公分|公尺|公厘|毫米|釐米|厘米|英呎|英尺|英吋|英寸|吋|米"
    # 英文單位：ft 可省略句點，in 一律要求句點，否則會誤吃「Set of 3 in Black」
    r"|cm|mm|inches|inch|feet|foot|ft\.?|in\."
    r"|[\"'‘’“”′″]"
)
_NUM = r"[0-9０-９]+(?:[.,][0-9０-９]+)?"
# 88"W、35cm L 這種軸向後綴（W 寬 / D 深 / H 高 / L 長）
_AXIS = r"(?:\s*[WDHLwdhl]\b)?"
_SEGMENT = rf"{_NUM}\s*(?:{_UNIT})?{_AXIS}"
# 順序即優先序：整條尺寸串要一次吃完，否則只清掉頭一段、留下孤立乘號
# （`6'×9'` → `×`）。一次吃完就不需要事後補救孤立符號，也就不會誤傷
# 「X型交叉支撐」「X大碼」這類真的有意義的 X。
_MEASUREMENT_PATTERNS = (
    # 逐段帶單位的串：6'×9'、1.72 cm x 20.32 cm、35cm L x 77cm W x 185cm H
    re.compile(
        rf"{_NUM}\s*(?:{_UNIT}){_AXIS}(?:\s*[xX×*]\s*{_SEGMENT})+",
        re.IGNORECASE,
    ),
    # 數字串後接單位：206x46x54 公分、148公分、88"W
    re.compile(
        rf"{_NUM}(?:\s*[xX×*]\s*{_NUM})*\s*(?:{_UNIT}){_AXIS}",
        re.IGNORECASE,
    ),
    # 無單位的尺寸串（型錄常把單位截掉）：200x41x95
    re.compile(rf"{_NUM}\s*[xX×*]\s*{_NUM}(?:\s*[xX×*]\s*{_NUM})*"),
)
# 規格被清掉後留下的空括號：「（約 22.9 釐米）高」→「（約 ）高」
_EMPTY_BRACKETS = re.compile(r"[（(]\s*(?:約|approx\.?|about)?\s*[)）]", re.IGNORECASE)
# 清規格後留下的孤立分隔符與空白（「地毯,8 x 10 英尺,藍色」→「地毯,,藍色」）
_DANGLING_SEPARATORS = re.compile(r"\s*([,，、;；/])\s*(?=[,，、;；/])")
_EDGE_SEPARATORS = re.compile(r"^[\s,，、;；/：:\-–—]+|[\s,，、;；/：:\-–—]+$")


def strip_measurements(text: object) -> str:
    """清掉尺寸規格；名稱本體、型號與顏色留著。

    只針對「數字＋長度單位」與「數字x數字」的尺寸串，不動 `2L`、`A8910`、
    `2 SEATER` 這類型號與件數——那些對畫面有意義。
    """
    out = str(text or "")
    for pattern in _MEASUREMENT_PATTERNS:
        out = pattern.sub("", out)
    out = _EMPTY_BRACKETS.sub("", out)
    out = re.sub(r"[ \t　]{2,}", " ", out)
    out = re.sub(r"[ \t　]+(?=[,，、;；。)）])", "", out)  # 「Bookcase , Gray」
    out = _DANGLING_SEPARATORS.sub("", out)
    return _EDGE_SEPARATORS.sub("", out)


def _material(row: dict) -> str:
    material = str(row.get("material") or "").strip()
    return "" if material.casefold() in MATERIAL_PLACEHOLDERS else material


def _label(row: dict, *, keep_measurements: bool = True) -> str:
    # 定案：數值與相對位置措辭都不進提示詞——畫面位置由 img2img 視角
    # 截圖鎖定，文字只補名稱、類型與材質描述。
    name = str(row.get("name") or row.get("id") or "家具")
    if not keep_measurements:
        name = strip_measurements(name) or str(row.get("type") or "家具")
    details = "，".join(
        value
        for value in (str(row.get("type") or "").strip(), _material(row))
        if value
    )
    return f"{name}（{details}）" if details else name


def visual_description(text: object) -> str:
    """把型錄描述裁成純外觀敘述：丟用途句，其餘整句取到字數上限為止。

    只在句號邊界切，不從句中截斷——半句話進提示詞比沒有描述更糟。
    """
    sentences = [s.strip() for s in re.split(r"[。\n]+", str(text or "")) if s.strip()]
    kept: list[str] = []
    used = 0
    for sentence in sentences:
        if sentence.startswith(USAGE_SENTENCE_PREFIXES):
            continue
        if kept and used + len(sentence) > DESCRIPTION_MAX_CHARS:
            break
        kept.append(sentence)
        used += len(sentence)
    return "。".join(kept) + "。" if kept else ""


def room_kind(room: LayoutRoom) -> str:
    """有專屬提示的房型鍵（bathroom / kitchen / balcony）；其餘回空字串。"""
    room_type = str(getattr(room, "room_type", "") or "")
    room_type = _ROOM_TYPE_ALIASES.get(room_type, room_type)
    if room_type in _ROOM_TYPE_HINTS:
        return room_type
    if room_type:
        # 房型已明確標成別的空間，就不再用房名猜（「主臥（含衛浴）」不是浴室）。
        return ""
    name = str(room.name or "")
    for kind, tokens in _ROOM_NAME_TOKENS:
        if any(token in name for token in tokens):
            return kind
    return ""


def room_size_note(room: LayoutRoom) -> str:
    """浴室／廚房／陽台才給的尺寸敘述（2026-08-14 使用者定案）：其他房型仍不給數值。

    這三類空間的畫面由固定設備決定，模型要靠尺寸才知道擺不擺得下一字型廚具、
    淋浴間或洗衣機。面積取長寬外接矩形，L 型或狹長空間會略為高估；要精確得改
    帶多邊形進來。
    """
    width = float(room.width_cm or 0)
    depth = float(room.depth_cm or 0)
    if width <= 0 or depth <= 0:
        return ""
    return (
        f"空間尺寸：約 {width:.0f} 公分 × {depth:.0f} 公分，"
        f"面積約 {width * depth / 10000:.1f} 平方公尺"
    )


def furniture_lines(scene: SceneDoc, room: LayoutRoom) -> list[str]:
    """短標籤：名稱（類型，材質）。給鎖定清單與設計手冊用，規格原樣保留。"""
    return [_label(row) for row in scene.placed_in(room.room_id)]


def furniture_prompt_lines(scene: SceneDoc, room: LayoutRoom) -> list[str]:
    """生圖用：短標籤再接型錄／RAG 的外觀描述，名稱與描述都先清掉尺寸規格。"""
    lines = []
    for row in scene.placed_in(room.room_id):
        label = _label(row, keep_measurements=False)
        # 先清規格再裁字數，字數上限才是花在外觀敘述上
        description = visual_description(strip_measurements(row.get("description")))
        lines.append(f"{label}：{description}" if description else label)
    return lines


class GenPicInfoTool:
    contract = ToolContract(
        name="genpic_info",
        description=(
            "整理生圖提示詞包（需求＋材質＋色卡＋場景＋家具外觀描述＋家電 context）"
            "與鎖定清單。"
        ),
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
        lighting: str = "day",
    ) -> dict:
        # 提示詞模板（2026-08-04 使用者定案）：
        # 「渲染成寫實風格，房間：{}、整體風格：{}、風格參考：{}、
        #   色調採(60%, 30%, 10%)：{}、地板材質：{}、牆壁材質：{}、
        #   家具配置(位置與數量必須與下列完全一致，不可增減或移動)：{}、
        #   家電：{}、{額外補充需求}」
        # 有數值資訊（尺寸/公分）不提供；沒有資料的段落整段省略。
        # 開場白自帶句號，不參與 "、" 串接：一起串會產生「。、，將此草圖…」的贅字。
        header = "你是室內軟裝設計師，風格要「極致寫實」。"
        segments: list[str] = []
        if requirements.styles:
            segments.append(f"將此草圖渲染成{'、'.join(requirements.styles[:2])}風的配色")
            note = style_note(requirements.styles)
            '''
            if note:
                segments.append(note)   # 已含「風格參考（…）：」前綴
            '''

        segments.append(f'房間：{room.name}')
        kind = room_kind(room)
        if kind:  # 有專屬提示的三類（bathroom/kitchen/balcony）才報尺寸
            size_note = room_size_note(room)
            if size_note:
                segments.append(size_note)

        if palette:
            colors = "、".join(str(c) for c in (palette.get("colors") or [])[:3])
            # colors = "、".join(str(c) for c in (palette.get("colors") or [])[:5])
            segments.append(f"整體色調比例採(60%, 30%, 10%)：{colors}")

        materials = requirements.materials or {}
        for key, label in (("地板", "地板材質"), ("牆面", "牆壁材質")):
            if materials.get(key):
                segments.append(f"{label}：{materials[key]}")
        furniture = furniture_lines(scene, room)
        # 提示詞用帶外觀描述的版本；鎖定清單仍存短標籤（改圖指令要精簡）。
        described = furniture_prompt_lines(scene, room)
        '''
        if furniture:
            segments.append(
                "家具配置(位置與數量必須與下列完全一致，不可增減或移動)："
                + "、".join(furniture)
            )
        '''
        if described:
            segments.append(
                "家具配置：\n"
                + "、\n\t".join(described)
            )

        appliances = [
            item.text for item in requirements.appliances if item.room_id in (None, room.room_id)
        ]
        if appliances:
            segments.append("家電：" + "、".join(appliances))
        if viewpoint and viewpoint.get("note"):
            segments.append(str(viewpoint["note"]))
        prompt = header + "、".join(segments)
        manifest = LockManifestDoc(
            room_id=room.room_id,
            palette_id=(palette or {}).get("palette_id"),
            viewpoint_id=(viewpoint or {}).get("viewpoint_id"),
            locked_furniture=furniture,
            locked_materials={**materials, "palette": (palette or {}).get("name", "")},
            allowed_change="",
        )
        if lighting == "night":
            # 夜景是日光成圖的「重打光」，附圖就是那張日光圖（GenPicAgent.render_room
            # 會換圖）：整套家具／材質／色卡敘述再送一次只會讓模型重畫一個房間。
            # 只留夜間光影一句（2026-08-14 使用者定案）。
            prompt = _LIGHTING_HINTS["night"]
        else:
            tail = ["可以加上任何需要元素"]
            if _ROOM_TYPE_HINTS.get(kind):
                tail.append(_ROOM_TYPE_HINTS[kind])
            tail.append("草圖中的格局位置不可變動、視角位置不可變動、牆壁地板材質家具位置門窗皆不可變動")
            tail.append(_LIGHTING_HINTS.get(lighting, _LIGHTING_HINTS["day"]))
            prompt += "\n" + "\n".join(tail)
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
