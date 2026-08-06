"""交付提案輸出 skill：流程層。提示詞與文案規範見同資料夾 ``SKILL.md``。

文案（content.json）在這裡產生：deterministic 底稿只寫資料裡有的事實，
LLM 可用時依 SKILL.md 規範改寫敘事；版面與品牌樣式屬打包 skill
``../roompilot-delivery-pdf/``（Playwright Chromium 排版），以 subprocess
呼叫其 ``scripts/build_pdf.py``，本層不重寫 HTML/CSS。
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ...documents import (
    DocKey,
    DocStore,
    ImageLibraryDoc,
    LayoutDoc,
    RequirementDoc,
    SceneDoc,
)
from ...llm import LLMGateway
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
            image_files = self._write_room_images(images, layout, workdir)
            content = build_content(
                project_name,
                requirements,
                layout,
                scene,
                image_files,
                design_revision=design_revision,
            )
            self._merge_llm_copy(content, requirements, layout, scene)
            content_path = workdir / "content.json"
            serialized = json.dumps(content, ensure_ascii=False, indent=2)
            content_path.write_text(serialized, encoding="utf-8")
            warnings = self._run_build_pdf(content_path, out, workdir)
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
    ) -> dict[str, str]:
        """把逐房最新生圖（base64）落成檔案，回傳 room_id -> 相對路徑。"""
        rooms_dir = workdir / "rooms"
        files: dict[str, str] = {}
        for room in layout.rooms:
            record = images.latest(room.room_id, "edit") or images.latest(
                room.room_id, "full_render"
            )
            if record is None or not _looks_like_b64(record.image_ref):
                continue
            try:
                payload = base64.b64decode(record.image_ref)
            except ValueError:  # 含 binascii.Error（其子類）
                continue
            rooms_dir.mkdir(parents=True, exist_ok=True)
            target = rooms_dir / f"{room.room_id}.png"
            target.write_bytes(payload)
            files[room.room_id] = f"rooms/{room.room_id}.png"
        return files

    # -- LLM 改寫（離線沿用 deterministic 底稿） --

    def _merge_llm_copy(
        self,
        content: dict,
        requirements: RequirementDoc,
        layout: LayoutDoc,
        scene: SceneDoc,
    ) -> None:
        facts = {
            "style": "、".join(requirements.styles),
            "palette": (
                {
                    "name": requirements.palette_options[0].name,
                    "colors": list(requirements.palette_options[0].colors),
                }
                if requirements.palette_options
                else None
            ),
            "materials": dict(requirements.materials or {}),
            "owner_notes": requirements.notes,
            "appliances": [item.text for item in requirements.appliances[:8]],
            "rooms": [
                {
                    "room_id": room.room_id,
                    "name": room.name,
                    "width_cm": room.width_cm,
                    "depth_cm": room.depth_cm,
                    "furniture": [
                        {
                            "name": row.get("name"),
                            "type": row.get("type"),
                            "width_cm": row.get("width"),
                            "depth_cm": row.get("depth"),
                            "material": row.get("material"),
                            "reason": row.get("reason"),
                        }
                        for row in scene.placed_in(room.room_id)[:10]
                    ],
                }
                for room in layout.rooms
            ],
        }
        llm_out = ask_llm_json(
            self._gateway,
            CONTENT_SPEC,
            json.dumps(facts, ensure_ascii=False),
            required=("rooms",),
        )
        if llm_out is None:
            return

        statement = llm_out.get("statement")
        if isinstance(statement, dict) and str(statement.get("hook", "")).strip():
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
                    "pillars": pillars[:4],
                }

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
            ]
            if len(rationale) >= 2:
                room["rationale"] = rationale[:3]

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


# ---------------------------------------------------------------- 底稿組稿


def build_content(
    project_name: str,
    requirements: RequirementDoc,
    layout: LayoutDoc,
    scene: SceneDoc,
    image_files: dict[str, str],
    *,
    design_revision=None,
    today: datetime | None = None,
) -> dict:
    """deterministic content.json 底稿：只寫資料裡有的事實，禁詞不入稿。

    LLM 之後只改寫敘事欄位（statement／scene_line／look／rationale）；
    meta、specs、色卡、materials、appendix 一律由此處取自場景資料。
    """
    style = "、".join(requirements.styles) or "依問卷偏好"
    palette = requirements.palette_options[0] if requirements.palette_options else None
    now = today or datetime.now(timezone.utc)
    date_text = f"{now.year} 年 {now.month} 月 {now.day} 日"
    version_text = "v1" + (f" · revision {design_revision}" if design_revision is not None else "")

    rooms: list[dict] = []
    limits: list[str] = []
    files: list[dict] = []
    cover_image = ""
    for room in layout.rooms:
        rows = scene.placed_in(room.room_id)
        image = image_files.get(room.room_id, "")
        if image and not cover_image:
            cover_image = image
        if image:
            files.append({"name": image, "desc": f"{room.name}最終渲染圖"})
        else:
            limits.append(f"「{room.name}」尚無渲染圖，圖面待補。")
        names = [str(row.get("name") or "").strip() for row in rows]
        names = [name for name in names if name]
        look = (
            f"走進{room.name}會看到{('、'.join(names[:3]) or '尚未配置的空間')}。"
            f"全案沿用{style}的配色與材質方向，家具位置與走道淨空都經幾何引擎驗證，"
            "實際尺寸見下方規格表。"
        )
        rationale = [
            {
                "title": "選件依據",
                "body": (
                    f"家具依第 5 步問卷的需求與風格（{style}）自正式家具庫挑選，"
                    "尺寸與材質列在規格表，可逐項核對。"
                ),
            },
            {
                "title": "擺位與淨空",
                "body": (
                    "位置由幾何引擎計算與驗證：不重疊、留走道、不擋門窗。"
                    "此配置即第 7 步鎖定的方案，圖面與清單一致。"
                ),
            },
        ]
        for row in rows:
            reason = str(row.get("reason") or "").strip()
            name = str(row.get("name") or "").strip()
            if reason and name and len(rationale) < 3:
                rationale.insert(0, {"title": name, "body": reason})
        specs = []
        for row in rows[:5]:
            value = "{type}，{w:.0f}×{d:.0f} cm".format(
                type=row.get("type") or "家具",
                w=float(row.get("width") or 0),
                d=float(row.get("depth") or 0),
            )
            material = str(row.get("material") or "").strip()
            if material:
                value += f"，{material}"
            price = row.get("price")
            if price:
                value += f"，參考價 {float(price):,.0f} 元"
            specs.append({"label": str(row.get("name") or row.get("type") or "家具"), "value": value})
        rooms.append(
            {
                "room_id": room.room_id,
                "name": room.name,
                "hero_image": image,
                "hero_caption": f"{room.name}最終渲染。" if image else "",
                "look": look,
                "rationale": rationale[:3],
                "specs": specs,
            }
        )

    swatches = []
    usage_labels = ["主色（60%）", "輔色（30%）", "點綴（10%）"]
    for index, color in enumerate((palette.colors if palette else [])[:8]):
        swatches.append(
            {
                "hex": color,
                "name": color,
                "usage": usage_labels[index] if index < len(usage_labels) else "",
            }
        )

    limits.append("未標價品項不列參考價，依正式報價為準。")

    content: dict = {
        "meta": {
            "project_name": project_name,
            "subtitle": f"{len(layout.rooms)} 個空間｜{style}",
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
            "hook": (
                f"這份提案整理 {len(layout.rooms)} 個空間的配置結果："
                "家具怎麼選、為什麼放在那裡、以及每個空間完成後的樣子。"
            ),
            "pillars": [
                {
                    "title": "風格一致",
                    "body": (
                        f"全案以{style}貫穿"
                        + (f"，配色採用「{palette.name}」色卡的 60/30/10 三色" if palette else "")
                        + "；各空間的家具與材質沿同一方向挑選，不會這房一個樣、那房一個樣。"
                    ),
                },
                {
                    "title": "位置經過驗證",
                    "body": (
                        "每件家具的位置都由幾何引擎計算與驗證：不重疊、留走道、"
                        "不擋門窗。圖面上看到的就是可以放得下的方案。"
                    ),
                },
            ],
        },
        "overview": {
            "title": "全案速覽",
            "title_en": "At a Glance",
            "facts": [
                {"label": "空間數", "value": f"{len(layout.rooms)} 間"},
                {"label": "風格", "value": style},
            ]
            + ([{"label": "主色卡", "value": palette.name}] if palette else []),
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
    if swatches:
        content["palette"] = {
            "title": "色彩與材質",
            "title_en": "Palette & Materials",
            "swatches": swatches,
        }
    if requirements.materials:
        content["materials"] = [
            {"area": str(area), "spec": str(spec)}
            for area, spec in requirements.materials.items()
        ]
    return content
