"""交付提案輸出 skill：流程層。提示詞與文案規範見同資料夾 ``SKILL.md``。

文案（content.json）在這裡產生：deterministic 底稿只寫資料裡有的事實，
LLM 可用時依 SKILL.md 規範改寫敘事；版面與品牌樣式屬打包 skill
``../roompilot-delivery-pdf/``（Playwright Chromium 排版），以 subprocess
呼叫其 ``scripts/build_pdf.py``，本層不重寫 HTML/CSS。
"""
from __future__ import annotations

import base64
import colorsys
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ...documents import (
    DocKey,
    DocStore,
    ImageLibraryDoc,
    ImageRecord,
    LayoutDoc,
    RequirementDoc,
    SceneDoc,
)
from ...knowledge import FAMILY_ZH
from ...llm import LLMGateway, report_model
from ...quote import PENDING_TEXT, build_quote, merge_rows
from ...tools.base import ToolError
from ...tools.read_docs import ReadDocsTool
from ..base import ask_llm_json, load_skill_doc
from ..report import _looks_like_b64

DOC = load_skill_doc(Path(__file__).parent)
CONTENT_SPEC = DOC.spec("content")

PACKAGED_SKILL_DIR = Path(__file__).resolve().parent.parent / "roompilot-delivery-pdf"
BUILD_PDF_SCRIPT = PACKAGED_SKILL_DIR / "scripts" / "build_pdf.py"

_INSTALL_HINT = (
    "尚未安裝交付提案排版引擎：請執行 "
    "`uv pip install --python .venv\\Scripts\\python.exe -r requirements-delivery.txt` "
    "與 `.venv\\Scripts\\playwright.exe install chromium`。"
)


def delivery_engine_status() -> tuple[bool, str]:
    """排版引擎是否可用；不可用時回報可讀原因（不得假成功）。"""
    if not BUILD_PDF_SCRIPT.exists():
        return False, "找不到 roompilot-delivery-pdf 打包 skill（scripts/build_pdf.py）。"
    if importlib.util.find_spec("playwright") is None:
        return False, _INSTALL_HINT
    return True, ""


class DeliverySkill:
    def __init__(
        self,
        gateway: LLMGateway | None = None,
        *,
        read_docs_tool: ReadDocsTool | None = None,
    ) -> None:
        self._gateway = gateway
        self._read_docs = read_docs_tool or ReadDocsTool()

    def run(
        self,
        store: DocStore,
        out_path: str,
        *,
        project_name: str = "RoomPilot 專案",
        design_revision=None,
    ) -> dict:
        available, reason = delivery_engine_status()
        if not available:
            raise ToolError(reason, tool="build_delivery_pdf")

        snapshot = self._read_docs.run(store)
        requirements = RequirementDoc.from_dict(snapshot.get(DocKey.REQUIREMENTS) or {})
        layout = LayoutDoc.from_dict(snapshot.get(DocKey.LAYOUT) or {})
        scene = self._chosen_scene(snapshot)
        images = ImageLibraryDoc.from_dict(snapshot.get(DocKey.IMAGES) or {})

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="rp-delivery-") as tmp:
            workdir = Path(tmp)
            image_files, night_image_files = self._write_room_images(
                images, layout, workdir
            )
            content = build_content(
                project_name,
                requirements,
                layout,
                scene,
                image_files,
                night_image_files=night_image_files,
                design_revision=design_revision,
            )
            merged = self._merge_llm_copy(content, requirements, layout, scene)
            content_path = workdir / "content.json"
            serialized = json.dumps(content, ensure_ascii=False, indent=2)
            content_path.write_text(serialized, encoding="utf-8")
            warnings = self._run_build_pdf(content_path, out, workdir)
            if not merged:
                # 底稿只寫得出資料裡有的事實，寫不出氛圍與感受。輸出仍然成立，
                # 但使用者要知道這一份是離線文案，不是沒設定就悄悄降級。
                warnings.insert(
                    0,
                    "文案走離線底稿（LLM 未套用）：敘述僅含資料事實，"
                    "空間氛圍與感受需設定 OPENROUTER_API_KEY 後重跑。",
                )
            # content.json 留在 PDF 旁：文案的每個數字都要可追溯（來源＝場景資料）。
            out.with_suffix(".content.json").write_text(serialized, encoding="utf-8")
        return {
            "pdf_path": str(out),
            "content_path": str(out.with_suffix(".content.json")),
            "warnings": warnings,
            "rendered_rooms": sorted(image_files),
        }

    # -- 資料讀取 --

    def _chosen_scene(self, snapshot: dict) -> SceneDoc:
        for key in (DocKey.variant(DocKey.SCENE, "chosen"), DocKey.variant(DocKey.SCENE, "A")):
            if snapshot.get(key):
                return SceneDoc.from_dict(snapshot[key])
        return SceneDoc()

    def _write_room_images(
        self, images: ImageLibraryDoc, layout: LayoutDoc, workdir: Path
    ) -> tuple[dict[str, str], dict[str, str]]:
        """把逐房最新生圖（base64）落成檔案。

        回傳 ``(主視覺, 夜間)`` 兩份 room_id -> 相對路徑。夜間燈光圖只有客廳
        會有，走該章的 ``extra_images``：排版會把它與主視覺並列（左日光、右
        夜間），封面與主視覺仍是日光那張。
        """
        rooms_dir = workdir / "rooms"
        files: dict[str, str] = {}
        night_files: dict[str, str] = {}
        for room in layout.rooms:
            hero = self._write_image(
                images.latest(room.room_id, "edit")
                or images.latest(room.room_id, "full_render"),
                rooms_dir,
                f"{room.room_id}.png",
            )
            if hero:
                files[room.room_id] = hero
            night = self._write_image(
                images.latest(room.room_id, "full_render_night"),
                rooms_dir,
                f"{room.room_id}_night.png",
            )
            if night:
                night_files[room.room_id] = night
        return files, night_files

    @staticmethod
    def _write_image(
        record: ImageRecord | None, rooms_dir: Path, filename: str
    ) -> str:
        """單筆生圖落檔；無圖或 base64 壞掉回空字串（該章由排版改用佔位框）。"""
        if record is None or not _looks_like_b64(record.image_ref):
            return ""
        try:
            payload = base64.b64decode(record.image_ref)
        except ValueError:  # 含 binascii.Error（其子類）
            return ""
        rooms_dir.mkdir(parents=True, exist_ok=True)
        (rooms_dir / filename).write_bytes(payload)
        return f"rooms/{filename}"

    # -- LLM 改寫（離線沿用 deterministic 底稿） --

    def _merge_llm_copy(
        self,
        content: dict,
        requirements: RequirementDoc,
        layout: LayoutDoc,
        scene: SceneDoc,
    ) -> bool:
        """以 SKILL.md 規範改寫敘事欄位；回傳是否真的套用（否＝沿用底稿）。

        餵給 LLM 的家具只給**通用中文名與類型**，不給型號字串——敘述裡出現
        「Amazon Brand – Rivet New Luna…」屋主根本讀不下去，型號留在規格表。
        """
        chapters = [str(room.get("name") or "") for room in content.get("rooms") or []]
        facts = {
            "style": "、".join(requirements.styles),
            "palette": (
                {
                    "name": requirements.palette_options[0].name,
                    "colors": [
                        {"hex": color, "zh": _color_name_zh(color), "role": role}
                        for color, role in zip(
                            requirements.palette_options[0].colors, _PALETTE_ROLES
                        )
                    ],
                }
                if requirements.palette_options
                else None
            ),
            "materials": {
                area: _material_zh(spec)
                for area, spec in (requirements.materials or {}).items()
            },
            "owner_notes": requirements.notes,
            "appliances": [item.text for item in requirements.appliances[:8]],
            "chapters_after_statement": ["全案速覽", *chapters, "色彩與材質", "接下來"],
            "rooms": [
                {
                    "room_id": room["room_id"],
                    "name": room["name"],
                    "width_cm": room.get("width_cm"),
                    "depth_cm": room.get("depth_cm"),
                    "furniture": [
                        {
                            "name": _short_name(row),
                            "type": _type_zh(row),
                            "count": count,
                            "width_cm": row.get("width"),
                            "depth_cm": row.get("depth"),
                            "material": _material_zh(row.get("material")),
                        }
                        for row, count in _dedupe_rows(
                            scene.placed_in(room["room_id"])
                        )[:8]
                    ],
                }
                for room in content.get("rooms") or []
                if room.get("room_id")
            ],
        }
        llm_out = ask_llm_json(
            self._gateway,
            CONTENT_SPEC,
            json.dumps(facts, ensure_ascii=False),
            required=("rooms",),
            model=report_model(),
            reasoning={"enabled": True},
        )
        if llm_out is None:
            return False

        statement = llm_out.get("statement")
        if isinstance(statement, dict) and str(statement.get("hook", "")).strip():
            # pillars 是「後續每一章的摘要」，章數多少就給多少，不砍到三條。
            pillars = [
                {"title": str(p.get("title", "")).strip(), "body": str(p.get("body", "")).strip()}
                for p in statement.get("pillars") or []
                if isinstance(p, dict) and str(p.get("title", "")).strip()
            ]
            if pillars:
                content["statement"] = {
                    "title": "設計總論",
                    "title_en": "Design Statement",
                    "hook": str(statement["hook"]).strip(),
                    "pillars": pillars[:12],
                }

        overview_intro = str(llm_out.get("overview_intro") or "").strip()
        if overview_intro and content.get("overview"):
            content["overview"]["intro"] = overview_intro
        palette_intro = str(llm_out.get("palette_intro") or "").strip()
        if palette_intro and content.get("palette"):
            content["palette"]["intro"] = palette_intro

        by_id = {room["room_id"]: room for room in content.get("rooms", []) if room.get("room_id")}
        for entry in llm_out.get("rooms") or []:
            if not isinstance(entry, dict):
                continue
            room = by_id.get(str(entry.get("room_id", "")).strip())
            if room is None:
                continue
            for key in ("scene_line", "look"):
                value = str(entry.get(key, "")).strip()
                if value:
                    room[key] = value
            rationale = [
                {"title": str(r.get("title", "")).strip(), "body": str(r.get("body", "")).strip()}
                for r in entry.get("rationale") or []
                if isinstance(r, dict)
                and str(r.get("title", "")).strip()
                and str(r.get("body", "")).strip()
                # 擺位與淨空是引擎的工作紀錄，不是屋主要讀的設計理由。
                and not _PLACEMENT_TITLE.search(str(r.get("title", "")))
            ]
            if rationale:
                room["rationale"] = rationale[:2]
        return True

    # -- 排版（打包 skill 的 build_pdf.py 擁有版面） --

    def _run_build_pdf(self, content_path: Path, out: Path, workdir: Path) -> list[str]:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_PDF_SCRIPT),
                    str(content_path),
                    "-o",
                    str(out),
                    "--base-dir",
                    str(workdir),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ToolError("交付提案 PDF 排版逾時（180 秒）。", tool="build_delivery_pdf") from exc
        if proc.returncode != 0 or not out.is_file():
            blob = f"{proc.stderr}\n{proc.stdout}"
            if "playwright" in blob.lower():
                raise ToolError(_INSTALL_HINT, tool="build_delivery_pdf")
            tail = " / ".join(line.strip() for line in blob.strip().splitlines()[-5:])
            raise ToolError(f"交付提案 PDF 排版失敗：{tail}", tool="build_delivery_pdf")
        return [
            line.strip().lstrip("⚠️").strip()
            for line in proc.stdout.splitlines()
            if "⚠️" in line
        ]


# ---------------------------------------------------------------- 文字素材

# 敘述裡只出現通用中文名。knowledge.FAMILY_ZH 未涵蓋的類型補在這裡。
_TYPE_ZH_EXTRA = {
    "storage-cabinet": "收納櫃",
    "cabinet-cupboard": "收納櫃",
    "chest-of-drawers": "抽屜櫃",
    "shoe-cabinet": "鞋櫃",
    "mirror-cabinet": "鏡櫃",
    "mirror": "鏡子",
    "console-table": "玄關桌",
    "side-table": "邊几",
    "lounge-chair": "休閒椅",
    "stool": "凳子",
    "bench": "長凳",
    "rug": "地毯",
    "curtain": "窗簾",
    "floor-lamp": "立燈",
    "table-lamp": "桌燈",
    "pendant-lamp": "吊燈",
    "flower-pots-planter": "植栽盆器",
    "tv": "電視",
    "fridge-freezer": "冰箱",
    "washing-machine": "洗衣機",
}

# 材質欄位混雜中英（catalog 原始值），對屋主一律出中文。
_MATERIAL_ZH = {
    "fabric": "布面",
    "textile": "織品",
    "linen": "亞麻布",
    "cotton": "棉布",
    "leather": "皮革",
    "wood": "木材",
    "oak": "橡木",
    "walnut": "胡桃木",
    "pine": "松木",
    "birch": "樺木",
    "bamboo": "竹",
    "rattan": "藤編",
    "metal": "金屬",
    "steel": "鋼",
    "brass": "黃銅",
    "iron": "鐵件",
    "glass": "玻璃",
    "marble": "大理石",
    "stone": "石材",
    "ceramic": "陶瓷",
    "plastic": "塑料",
    "veneer": "貼皮",
    "mdf": "密迪板",
    "particleboard": "塑合板",
}

_PALETTE_ROLES = ("主色", "輔色", "點綴色")
_PALETTE_USAGE = (
    "牆面、天花與大面櫃體",
    "窗簾、床品與布件",
    "抱枕、掛畫與小物件",
)

# 選件依據的收尾句。八個空間用同一句收，讀者翻到第三頁就開始跳著看。
_SPATIAL_FEEL = (
    "件數壓下來，站在門口一眼看得完，房間會比實際看起來深。",
    "顏色收在同一組裡，視線在房裡不會一直被打斷。",
    "少放一件，走動的地方就多一塊，兩個人錯身不用互相讓。",
    "每一件都有它要做的事，沒有一件是為了把空位填起來。",
    "質感集中在少數幾種材質上，房間看起來才不會雜。",
)

_LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
_NAME_HEAD = re.compile(r"\s+[-–—]\s+|[，,、(（]")
# 只擋「家具放得下」這種工作紀錄式的理由；具體到尺寸的動線判斷（「走道留 90
# 公分」）是合法的設計理由，只要數字來自輸入資料。
_PLACEMENT_TITLE = re.compile(r"擺位|淨空|碰撞|不重疊|幾何引擎")
# 色相分界（度）→ 中文色名；暖色另有木質語彙，見 _color_name_zh。
_HUE_ZH = (
    (16, "紅"), (50, "橘"), (66, "黃"), (95, "黃綠"), (155, "綠"),
    (185, "青綠"), (205, "青"), (245, "藍"), (275, "藍紫"),
    (310, "紫"), (340, "紫紅"), (361, "紅"),
)


def _type_zh(row: dict) -> str:
    key = str(row.get("type") or "").strip()
    return _TYPE_ZH_EXTRA.get(key) or FAMILY_ZH.get(key) or (key or "家具")


def _short_name(row: dict) -> str:
    """取得可以寫進敘述的家具名：型號、品牌、英文一律換成通用中文名。"""
    head = _NAME_HEAD.split(str(row.get("name") or "").strip())[0].strip()
    if not head or len(head) > 10 or _LATIN.search(head):
        return _type_zh(row)
    return head


_REDUNDANT_PAREN = re.compile(r"^(.*?)[（(]([^（）()]{1,8})[）)]\s*$")


def _material_zh(text) -> str:
    """把 catalog 的材質字串正規化成中文；認不出的保留原字。

    順手拆掉重複的括號色名：``_surface_text`` 產出的是「暖木色木地板（暖木色）」，
    名稱裡已經有顏色了，再括號一次只是佔位子。
    """
    raw = str(text or "").strip()
    match = _REDUNDANT_PAREN.match(raw)
    if match and match.group(2) in match.group(1):
        raw = match.group(1).strip()
    parts = [part.strip() for part in re.split(r"[,，/、]", raw) if part.strip()]
    out: list[str] = []
    for part in parts:
        zh = _MATERIAL_ZH.get(part.casefold(), part)
        if zh not in out:
            out.append(zh)
    return "、".join(out)


def _dedupe_rows(rows: list[dict]) -> list[tuple[dict, int]]:
    """同款同尺寸的家具（例如四張一樣的餐椅）合併成一列＋數量。

    與報價單共用同一套併列規則（``backend/agent/quote``），否則規格表寫「共 4
    件」而報價單算 3 件，屋主一對就發現對不起來。
    """
    return merge_rows(rows)


def _hex_to_hls(code: str) -> tuple[float, float, float] | None:
    text = str(code or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        return None
    try:
        red, green, blue = (int(text[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    hue, light, sat = colorsys.rgb_to_hls(red, green, blue)
    return hue * 360, light, sat


def _color_name_zh(code: str) -> str:
    """由色碼本身推出中文色名。

    色卡 JSON 只有 palette_hex，沒有色名；直接把 #F7F5ED 印在色票下面，屋主
    看到的是一串亂碼。這裡描述的是這個色碼真正的樣子，不是編一個名字。
    """
    hls = _hex_to_hls(code)
    if hls is None:
        return "色塊"
    hue, light, sat = hls
    if sat < 0.12:
        for bound, name in ((0.93, "白"), (0.78, "淺灰"), (0.50, "中灰"), (0.25, "深灰")):
            if light >= bound:
                return name
        return "近黑"
    base = next(name for bound, name in _HUE_ZH if hue < bound)
    if base in ("紅", "橘", "黃"):  # 暖色系用木質與米色語彙，比「橘」貼近實物
        for bound, name in ((0.88, "米白"), (0.75, "米色"), (0.55, "淺木"), (0.35, "棕")):
            if light >= bound:
                return name
        return "深棕"
    for bound, prefix in ((0.75, "淺"), (0.55, "霧"), (0.35, "")):
        if light >= bound:
            return prefix + base
    return "深" + base


def _size_text(width_cm, depth_cm) -> str:
    try:
        width, depth = float(width_cm or 0), float(depth_cm or 0)
    except (TypeError, ValueError):
        return ""
    if width <= 0 or depth <= 0:
        return ""
    return f"{width / 100:.1f} × {depth / 100:.1f} 米"


def _furniture_phrase(pairs: list[tuple[dict, int]], limit: int = 4) -> str:
    """敘述用的家具列舉：通用名、去重、標數量。"""
    parts = []
    for row, count in pairs[:limit]:
        name = _short_name(row)
        parts.append(f"{name}（{count} 件）" if count > 1 else name)
    if len(pairs) > limit:
        parts.append(f"另有 {len(pairs) - limit} 件")
    return "、".join(parts)


# ---------------------------------------------------------------- 底稿組稿


def build_content(
    project_name: str,
    requirements: RequirementDoc,
    layout: LayoutDoc,
    scene: SceneDoc,
    image_files: dict[str, str],
    *,
    night_image_files: dict[str, str] | None = None,
    design_revision=None,
    today: datetime | None = None,
) -> dict:
    """deterministic content.json 底稿：只寫資料裡有的事實，禁詞不入稿。

    寫作邊界（2026-08-06 依屋主回饋定案）：

    - 敘述不出現家具型號與品牌，只出現通用中文名；型號留在規格表。
    - 不寫「位置經過幾何引擎驗證」這類製作過程——那是我們的工作紀錄，
      屋主要讀的是空間本身。同理，`rationale` 不寫擺位與淨空。
    - 設計總論的 `pillars` 是**後續每一章的摘要**（每條約 50 字），不是
      三個抽象主張。
    - 全部房型都排篇章（含浴室、陽台等）；沒有配置家具的空間也出一章，
      據實寫「這一版沒有放家具」。

    底稿寫得出「有什麼、多大、什麼材質」，寫不出「走進來的感覺」；氛圍與
    感受由 LLM 依 SKILL.md 改寫（statement／overview_intro／palette_intro／
    scene_line／look／rationale）。meta、specs、色卡、materials、appendix
    一律由此處取自場景資料。
    """
    style = "、".join(requirements.styles) or "依問卷偏好"
    palette = requirements.palette_options[0] if requirements.palette_options else None
    colors = list(palette.colors)[:8] if palette else []
    color_names = [_color_name_zh(color) for color in colors]
    floor = _material_zh(requirements.materials.get("地板")) if requirements.materials else ""
    wall = _material_zh(requirements.materials.get("牆面")) if requirements.materials else ""
    now = today or datetime.now(timezone.utc)
    date_text = f"{now.year} 年 {now.month} 月 {now.day} 日"
    version_text = "v1" + (f" · revision {design_revision}" if design_revision is not None else "")

    in_scope = list(layout.rooms)  # 全部房型都排篇章（含浴室/陽台等），不做範圍過濾

    # 各房開頭句型輪替：八個空間都用同一句起手，讀者翻到第三個就開始跳著看。
    openers = (
        "推開{name}的門，",
        "從走道轉進{name}，",
        "站在{name}門口往裡看，",
        "{name}進門的第一眼，",
        "走進{name}，",
    )
    rooms: list[dict] = []
    overview_rows: list[list[str]] = []
    chapter_facts: list[dict] = []
    no_image: list[str] = []
    files: list[dict] = []
    materials_seen: list[str] = []
    furniture_total = 0
    cover_image = ""
    for index, room in enumerate(in_scope):
        pairs = _dedupe_rows(scene.placed_in(room.room_id))
        furniture_total += sum(count for _, count in pairs)
        size = _size_text(room.width_cm, room.depth_cm)
        image = image_files.get(room.room_id, "")
        if image and not cover_image:
            cover_image = image
        if image:
            files.append({"name": image, "desc": f"{room.name}最終渲染圖"})
        else:
            no_image.append(room.name)
        # 夜間燈光圖只有客廳會有；封面仍用日光那張。
        night_image = (night_image_files or {}).get(room.room_id, "")
        if night_image:
            files.append({"name": night_image, "desc": f"{room.name}夜間燈光渲染圖"})
        room_materials: list[str] = []
        for row, _count in pairs:
            for material in _material_zh(row.get("material")).split("、"):
                if not material:
                    continue
                if material not in room_materials:
                    room_materials.append(material)
                if material not in materials_seen:
                    materials_seen.append(material)

        # 每房只寫這個房間才有的事。配色與地牆材質全案共用，寫在總論、速覽與
        # 色彩章各一次就夠——八個空間各抄一次，屋主翻到第三頁就開始跳著看。
        listed = _furniture_phrase(pairs)
        opener = openers[index % len(openers)].format(name=room.name)
        if pairs:
            look = f"{opener}最先看到的是{listed}。"
        else:
            look = f"{opener}這一版沒有放家具，地面是空的。"
        if size:
            look += f"{room.name}約 {size}"
            widest = max(pairs, key=lambda pair: float(pair[0].get("width") or 0))[0] if pairs else None
            if widest and float(widest.get("width") or 0) > 0:
                look += (
                    f"，最大的一件是{_short_name(widest)}，"
                    f"寬 {float(widest['width']):.0f} 公分"
                )
            look += "。"
        if room_materials:
            look += f"摸得到的材質以{'、'.join(room_materials[:2])}為主。"

        # 選件依據＝什麼樣的設計判斷 → 選了什麼 → 搭起來是什麼空間感。
        # 家具清單與材質已經在 look 與規格表出現過，這裡不再抄一次。
        if pairs:
            body = (
                f"{room.name}的件數是照用途決定的，只留"
                f" {sum(count for _, count in pairs)} 件，不把空間填滿。"
            )
            if palette:
                body += f"款式與顏色都往「{palette.name}」這個方向收，"
            body += _SPATIAL_FEEL[index % len(_SPATIAL_FEEL)]
        else:
            body = (
                f"{room.name}這一版不放家具。它的作用是把其他空間接起來，"
                "空著的時候最好用——擺一件矮櫃就會變成每天要側身經過的地方。"
            )
        rationale = [{"title": "選件依據", "body": body}]

        specs = []
        for row, count in pairs[:6]:
            value = "{type}，{w:.0f}×{d:.0f} cm".format(
                type=_type_zh(row),
                w=float(row.get("width") or 0),
                d=float(row.get("depth") or 0),
            )
            material = _material_zh(row.get("material"))
            if material:
                value += f"，{material}"
            if count > 1:
                value += f"，共 {count} 件"
            # 規格表不帶價格：金額集中在報價單章節（quote），避免屋主邊看設計
            # 邊算錢，也避免價格混進 LLM 潤稿的敘述。
            specs.append(
                {"label": str(row.get("name") or _type_zh(row)), "value": value}
            )
        overview_rows.append(
            [room.name, size or "—", listed or "本次未配置家具"]
        )
        chapter_facts.append(
            {
                "name": room.name,
                "size": size,
                "listed": listed,
                "materials": room_materials[:2],
            }
        )
        rooms.append(
            {
                "room_id": room.room_id,
                "name": room.name,
                "width_cm": room.width_cm,
                "depth_cm": room.depth_cm,
                "hero_image": image,
                # 有夜間圖時兩張並列，標題就要講光線（左日光、右夜間），
                # 只寫「最終渲染」屋主分不出左邊那張是什麼。
                "hero_caption": (
                    (f"{room.name}日光。" if night_image else f"{room.name}最終渲染。")
                    if image
                    else ""
                ),
                "look": look,
                "rationale": rationale,
                "specs": specs,
                **(
                    {
                        "extra_images": [
                            {
                                "src": night_image,
                                "caption": f"{room.name}夜間燈光。同一視角、同一色卡，只換光影。",
                            }
                        ]
                    }
                    if night_image
                    else {}
                ),
            }
        )

    swatches = [
        {
            "hex": color,
            "name": f"{color_names[index]} {color}",
            "usage": (
                f"{_PALETTE_ROLES[index]}｜{_PALETTE_USAGE[index]}"
                if index < len(_PALETTE_ROLES)
                else ""
            ),
        }
        for index, color in enumerate(colors)
    ]

    # 範圍說明放在速覽的開場（屋主一翻就看到），限制欄只留真正的缺口，
    # 同一件事不在兩個地方各講一次。
    limits: list[str] = []
    if no_image:
        limits.append(f"{'、'.join(no_image)}尚無渲染圖，圖面待補。")
    limits.append("報價單標「待報價」的品項型錄尚未給價，依正式報價為準。")

    facts = [
        {"label": "空間數", "value": f"{len(rooms)} 間"},
        {"label": "家具總件數", "value": f"{furniture_total} 件"},
        {"label": "風格", "value": style},
    ]
    if palette:
        facts.append({"label": "主色卡", "value": palette.name})
    if floor:
        facts.append({"label": "地板", "value": floor})
    if wall:
        facts.append({"label": "牆面", "value": wall})

    overview_intro = (
        f"全案 {len(rooms)} 個空間、共 {furniture_total} 件家具，"
        f"配色與材質同一套：{floor or '風格預設地板'}、{wall or '風格預設牆面'}"
        + (f"，色卡是「{palette.name}」。" if palette else "。")
    )
    if requirements.notes:
        overview_intro += f"\n你在問卷裡提到：{requirements.notes}。"

    content: dict = {
        "meta": {
            "project_name": project_name,
            "subtitle": f"{len(rooms)} 個空間｜{style}",
            "cover_image": cover_image,
            "version": version_text,
            "cover_meta": [
                {"label": "日期", "value": date_text},
                {"label": "版本", "value": version_text},
                {"label": "風格", "value": style},
            ],
        },
        "statement": {
            "title": "設計總論",
            "title_en": "Design Statement",
            "hook": _statement_hook(project_name, rooms, style, palette, floor, wall),
            "pillars": _chapter_summaries(
                chapter_facts, style, palette, color_names, floor, wall, furniture_total
            ),
        },
        "overview": {
            "title": "全案速覽",
            "title_en": "At a Glance",
            "intro": overview_intro,
            "facts": facts,
            "table": {
                "columns": ["空間", "尺寸（約）", "主要配置"],
                "rows": overview_rows,
            },
        },
        "rooms": rooms,
        "next_steps": {
            "title": "接下來",
            "title_en": "Next Steps",
            "body": (
                "確認這份提案的方向後，下一步是建材選樣與正式報價；"
                "想調整的部分可以先列出來，下次修訂一併處理。"
            ),
            "notes": ["確認各空間的家具與材質方向", "未標價品項的正式報價"],
        },
        "appendix": {
            "files": files,
            "limits": limits,
            "version_line": f"design {version_text} · 產出於 {now.date().isoformat()}",
        },
    }
    quote_block = _quote_block(in_scope, scene, requirements)
    if quote_block:
        content["quote"] = quote_block
    if swatches:
        content["palette"] = {
            "title": "色彩與材質",
            "title_en": "Palette & Materials",
            "intro": _palette_intro(palette, color_names, floor, wall),
            "swatches": swatches,
        }
    materials = [
        {
            "area": str(area),
            "spec": _material_zh(spec),
            "why": "全室同一款，房間之間沒有段差。"
            if str(area) == "地板"
            else "全室同一款，各空間的色底一致。",
        }
        for area, spec in (requirements.materials or {}).items()
    ]
    if materials_seen:
        materials.append(
            {
                "area": "家具材質",
                "spec": "、".join(materials_seen[:6]),
                "why": "跟著家具一起定下來；實際布種與木皮色號依選樣確認。",
            }
        )
    if materials:
        content["materials"] = materials
    return content


def _quote_block(rooms, scene: SceneDoc, requirements: RequirementDoc) -> dict | None:
    """報價單章節：整份提案唯一出現金額的地方（彙整規則見 ``backend/agent/quote``）。"""
    quote = build_quote(
        [(room.name, scene.placed_in(room.room_id)) for room in rooms],
        budget_total=requirements.budget_total,
    )
    if quote.is_empty:
        return None
    table_rows = [
        [
            room.room_name,
            line.name,
            line.spec,
            f"{line.count}",
            f"{line.unit_price:,.0f} 元" if line.unit_price is not None else PENDING_TEXT,
            f"{line.subtotal:,.0f} 元" if line.subtotal is not None else "—",
        ]
        for room in quote.rooms
        for line in room.lines
    ]
    summary = []
    if quote.priced_count:
        summary.append(
            {
                "label": "已標價合計",
                "value": f"約 {quote.total:,.0f} 元（{quote.priced_count} 件）",
            }
        )
    if quote.pending_count:
        summary.append(
            {"label": "待報價品項", "value": f"{quote.pending_count} 件"}
        )
    if quote.budget_total:
        summary.append(
            {"label": "你的預算", "value": f"{quote.budget_total:,} 元"}
        )
    notes = ["本表是型錄參考價，不含工程、運送與安裝費用。"]
    if quote.pending_count:
        notes.append(
            "標「待報價」的品項型錄尚未給價，等正式報價出來才算得出來，"
            "這裡不先估一個數字給你。"
        )
    return {
        "title": "報價單",
        "title_en": "Quotation",
        "intro": (
            "前面談的是設計，這一頁談錢。同款同尺寸的併成一列，"
            "數量與規格跟各空間的規格表對得起來。"
        ),
        "table": {
            "columns": ["空間", "品項", "規格", "數量", "單價", "小計"],
            "rows": table_rows,
        },
        "summary": summary,
        "notes": notes,
    }


def _statement_hook(
    project_name: str, rooms: list[dict], style: str, palette, floor: str, wall: str
) -> str:
    """總論開場：講這個案子在做什麼，不講這份文件怎麼做出來的。"""
    named = "、".join(room["name"] for room in rooms[:4])
    if len(rooms) > 4:
        named += f"等 {len(rooms)} 個空間"
    text = f"{project_name}這一版做{named}，全案走「{style}」。"
    if floor or wall:
        text += f"地板{floor or '依風格預設'}、牆面{wall or '依風格預設'}，"
    if palette:
        text += f"配色收在「{palette.name}」一張色卡裡，"
    text += "房間之間不各走各的，走過去是同一個家。"
    return text


def _chapter_summaries(
    chapter_facts: list[dict],
    style: str,
    palette,
    color_names: list[str],
    floor: str,
    wall: str,
    furniture_total: int,
) -> list[dict]:
    """後續每一章的摘要，每條約 50 字——總論要讓屋主知道後面有什麼。

    刻意不寫「本章包含樣貌、選件依據與規格表」這種每章都成立的句子：講完
    第一次就沒有資訊量了，八個空間各寫一次只是把版面填滿。
    """
    pillars = [
        {
            "title": "全案速覽",
            "body": (
                f"{len(chapter_facts)} 個空間的尺寸與主要配置一次列出，"
                f"共 {furniture_total} 件家具；地板{floor or '依風格預設'}、"
                f"牆面{wall or '依風格預設'}，風格{style}。"
            ),
        }
    ]
    for fact in chapter_facts:
        body = f"約 {fact['size']}，" if fact["size"] else ""
        body += f"放{fact['listed']}。" if fact["listed"] else "這一版不配置家具，留給動線。"
        if fact["materials"]:
            body += f"材質以{'、'.join(fact['materials'])}為主。"
        pillars.append({"title": fact["name"], "body": body})
    if palette:
        pillars.append(
            {
                "title": "色彩與材質",
                "body": (
                    f"「{palette.name}」色卡的三個顏色怎麼分配："
                    + "、".join(
                        f"{name}{role}"
                        for name, role in zip(color_names, _PALETTE_ROLES)
                    )
                    + f"；地板{floor or '依風格預設'}、牆面{wall or '依風格預設'}全室同一款。"
                ),
            }
        )
    pillars.append(
        {
            "title": "接下來",
            "body": "方向確認後要做的事：建材選樣、未標價品項的正式報價，以及這一版需要你回覆的項目。",
        }
    )
    return pillars


def _palette_intro(palette, color_names: list[str], floor: str, wall: str) -> str:
    """色彩與材質的開場：三段——分配原則、三個顏色各自的位置、地牆怎麼搭。"""
    if not palette:
        return ""
    tone = color_names[0] if color_names else ""
    paragraphs = [
        f"配色收在「{palette.name}」這一張色卡裡，三個顏色照 60／30／10 分配。"
        f"面積最大的{tone}決定整個家的底，另外兩個只在小範圍出現——"
        "比例固定下來，房間之間才不會各走各的。",
        "".join(
            f"{name}是{role}，落在{usage}。"
            for name, role, usage in zip(color_names, _PALETTE_ROLES, _PALETTE_USAGE)
        ),
        f"地板{floor or '依風格預設'}與牆面{wall or '依風格預設'}全室同一款，"
        "從走道走進房間不會換材質，視覺上是連著的。",
    ]
    return "\n".join(paragraph for paragraph in paragraphs if paragraph)
