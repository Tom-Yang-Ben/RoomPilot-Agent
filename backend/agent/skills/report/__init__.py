"""報告整理輸出 skill：流程層。提示詞與章節規格見同資料夾 ``SKILL.md``。"""
from __future__ import annotations

import json
from pathlib import Path

from ...documents import (
    DesignManualDoc,
    DocKey,
    DocStore,
    ImageLibraryDoc,
    LayoutDoc,
    ManualSection,
    RequirementDoc,
    SceneDoc,
    ValidationReportDoc,
)
from ...llm import LLMGateway
from ...tools.design_knowledge import selection_digest
from ...tools.genpic_info import furniture_lines
from ...tools.read_docs import ReadDocsTool
from ...tools.render_pdf import RenderPdfTool
from ..base import ask_llm_json, load_skill_doc

DOC = load_skill_doc(Path(__file__).parent)
INTRO_SPEC = DOC.spec("intro")
RATIONALE_SPEC = DOC.spec("rationale")


def _looks_like_b64(value: str) -> bool:
    return bool(value) and len(value) > 200 and "/" not in value[:80] and "\\" not in value[:80]


class ReportSkill:
    def __init__(
        self,
        gateway: LLMGateway | None = None,
        *,
        read_docs_tool: ReadDocsTool | None = None,
        pdf_tool: RenderPdfTool | None = None,
    ) -> None:
        self._gateway = gateway
        self._read_docs = read_docs_tool or ReadDocsTool()
        self._pdf = pdf_tool or RenderPdfTool()

    def run(self, store: DocStore, out_path: str) -> DesignManualDoc:
        snapshot = self._read_docs.run(store)
        requirements = RequirementDoc.from_dict(snapshot.get(DocKey.REQUIREMENTS) or {})
        layout = LayoutDoc.from_dict(snapshot.get(DocKey.LAYOUT) or {})
        scene = self._chosen_scene(snapshot)
        images = ImageLibraryDoc.from_dict(snapshot.get(DocKey.IMAGES) or {})
        choices = snapshot.get(DocKey.USER_CHOICES) or {}
        validation = self._chosen_validation(snapshot, scene.variant)

        manual = DesignManualDoc(title="RoomPilot 設計手冊")
        manual.sections.append(self._intro_section(requirements, layout, scene))
        manual.sections.append(self._rationale_section(requirements, layout, scene))
        manual.sections.append(self._layout_section(layout, scene))
        manual.sections.append(self._furniture_section(layout, scene))
        manual.sections.append(self._material_section(requirements, choices))
        manual.sections.append(self._validation_section(validation, choices))
        render_section, images_b64 = self._render_section(layout, images)
        manual.sections.append(render_section)
        manual.sections.append(self._engineering_section(choices))

        result = self._pdf.run(manual, out_path, images_b64)
        manual.pdf_path = result["pdf_path"]
        return manual

    # -- 資料讀取 --

    def _chosen_scene(self, snapshot: dict) -> SceneDoc:
        for key in (DocKey.variant(DocKey.SCENE, "chosen"), DocKey.variant(DocKey.SCENE, "A")):
            if snapshot.get(key):
                return SceneDoc.from_dict(snapshot[key])
        return SceneDoc()

    def _chosen_validation(self, snapshot: dict, variant: str) -> ValidationReportDoc:
        key = DocKey.variant(DocKey.VALIDATION, variant or "A")
        if snapshot.get(key):
            return ValidationReportDoc.from_dict(snapshot[key])
        return ValidationReportDoc(variant=variant or "A")

    # -- 各章節（deterministic 組稿） --

    def _intro_section(
        self, requirements: RequirementDoc, layout: LayoutDoc, scene: SceneDoc
    ) -> ManualSection:
        styles = "、".join(requirements.styles) or "依問卷偏好"
        placed_total = sum(len(scene.placed_in(room.room_id)) for room in layout.rooms)
        intro = (
            f"本手冊統整 {len(layout.rooms)} 個空間的設計成果：風格以{styles}為主軸，"
            f"共配置 {placed_total} 件家具。以下章節依序整理需求、平面配置、"
            "家具清單、材質色卡、驗證紀錄與渲染成果。"
        )
        llm_out = ask_llm_json(
            self._gateway,
            INTRO_SPEC,
            json.dumps(
                {
                    "styles": requirements.styles,
                    "rooms": [room.name for room in layout.rooms],
                    "budget_total": requirements.budget_total,
                    "placed_total": placed_total,
                },
                ensure_ascii=False,
            ),
            required=("intro",),
        )
        if llm_out is not None and str(llm_out.get("intro", "")).strip():
            intro = str(llm_out["intro"]).strip()
        body_lines = [intro, ""]
        if requirements.hard:
            body_lines.append("硬性需求：" + "；".join(i.text for i in requirements.hard[:12]))
        if requirements.soft:
            body_lines.append("風格偏好：" + "；".join(i.text for i in requirements.soft[:8]))
        if requirements.appliances:
            body_lines.append(
                "家電情境（僅入渲染畫面，不列入家具配置）："
                + "、".join(i.text for i in requirements.appliances[:10])
            )
        if requirements.budget_total:
            body_lines.append(f"家具總預算參考：{requirements.budget_total:,} 元")
        return ManualSection(heading="一、專案與需求摘要", body="\n".join(body_lines))

    def _rationale_section(
        self, requirements: RequirementDoc, layout: LayoutDoc, scene: SceneDoc
    ) -> ManualSection:
        # 每房收集選件理由（reason／hint.note，由 place_furniture 附進 placed row）。
        rooms_payload: list[dict] = []
        reasons_by_room: dict[str, list[str]] = {}
        for room in layout.rooms:
            reasons = []
            for row in scene.placed_in(room.room_id):
                label = str(row.get("name") or row.get("id") or "家具")
                detail = (
                    str(row.get("reason") or "").strip()
                    or str(row.get("hint_note") or "").strip()
                )
                if detail:
                    reasons.append(f"{label}：{detail}")
            if reasons:
                reasons_by_room[room.name] = reasons
                rooms_payload.append({"name": room.name, "reasons": reasons})

        # deterministic 底稿：每房把選件理由組成一段（LLM 不可用時直接用）。
        texts = {
            name: "本空間依焦點、動線、尺度與視覺平衡原則配置——" + "；".join(reasons) + "。"
            for name, reasons in reasons_by_room.items()
        }
        if rooms_payload:
            llm_out = ask_llm_json(
                self._gateway,
                RATIONALE_SPEC,
                json.dumps(
                    {
                        "styles": requirements.styles,
                        "principles": selection_digest(),
                        "rooms": rooms_payload,
                    },
                    ensure_ascii=False,
                ),
                required=("rooms",),
            )
            for entry in (llm_out or {}).get("rooms", []):
                name = str(entry.get("name", "")).strip()
                text = str(entry.get("text", "")).strip()
                if name in texts and text:
                    texts[name] = text

        if not texts:
            return ManualSection(
                heading="二、設計理念與亮點",
                body="本方案家具由 deterministic 規則配置，各空間依焦點、動線、尺度與"
                "視覺平衡原則擺放。",
            )
        lines: list[str] = []
        for room in layout.rooms:
            if room.name in texts:
                lines.extend((room.name, texts[room.name], ""))
        return ManualSection(heading="二、設計理念與亮點", body="\n".join(lines).rstrip())

    def _layout_section(self, layout: LayoutDoc, scene: SceneDoc) -> ManualSection:
        lines: list[str] = []
        for room in layout.rooms:
            lines.append(
                f"{room.name}（{room.width_cm:.0f}x{room.depth_cm:.0f} 公分）"
            )
            for line in furniture_lines(scene, room):
                lines.append(f"  - {line}")
            if not scene.placed_in(room.room_id):
                lines.append("  -（本空間無自動配置家具）")
            lines.append("")
        lines.append("＊座標與合法性由幾何引擎（backend/engine）計算與驗證，單位公分。")
        return ManualSection(heading="三、空間與平面配置", body="\n".join(lines))

    def _furniture_section(self, layout: LayoutDoc, scene: SceneDoc) -> ManualSection:
        lines: list[str] = []
        total_price = 0.0
        priced_items = 0
        for room in layout.rooms:
            rows = scene.placed_in(room.room_id)
            if not rows:
                continue
            lines.append(f"{room.name}：")
            for row in rows:
                price = row.get("price")
                price_text = f"，參考價 {price:,.0f} 元" if price else ""
                if price:
                    total_price += float(price)
                    priced_items += 1
                lines.append(
                    "  - {name}（{type}，{w:.0f}x{d:.0f}cm{style}{price}）".format(
                        name=row.get("name", row.get("id")),
                        type=row.get("type", ""),
                        w=float(row.get("width", 0)),
                        d=float(row.get("depth", 0)),
                        style=f"，{row['style']}" if row.get("style") else "",
                        price=price_text,
                    )
                )
                reason = str(row.get("reason") or "").strip()
                if reason:
                    lines.append(f"    選件理由：{reason}")
            lines.append("")
        if priced_items:
            lines.append(f"已標價家具合計：約 {total_price:,.0f} 元（{priced_items} 件）")
        lines.append("未標價品項依正式報價為準，不予估算。")
        return ManualSection(heading="四、家具清單與預算參考", body="\n".join(lines))

    def _material_section(self, requirements: RequirementDoc, choices: dict) -> ManualSection:
        lines = []
        for key, value in (requirements.materials or {}).items():
            lines.append(f"{key}：{value}")
        chosen_palette_id = choices.get("palette_id")
        for palette in requirements.palette_options:
            marker = "（選定）" if palette.palette_id == chosen_palette_id else ""
            lines.append(
                f"色卡 {palette.name}{marker}：{'、'.join(palette.colors[:6])}"
            )
        if not lines:
            lines.append("（問卷未提供材質與色卡資料）")
        return ManualSection(heading="五、材質與色卡", body="\n".join(lines))

    def _validation_section(
        self, validation: ValidationReportDoc, choices: dict
    ) -> ManualSection:
        lines = [
            f"採用方案：{choices.get('plan_variant', validation.variant)}",
            f"驗證輪次：{validation.round_index}",
            validation.summary or "（無驗證摘要）",
        ]
        if validation.soft_warnings:
            lines.append("軟性提醒（不阻擋方案）：")
            lines.extend(f"  - {w.message}" for w in validation.soft_warnings[:8])
        if choices.get("unresolved_validation"):
            lines.append("＊部分驗證問題於修復上限後由使用者裁決保留。")
        feedback_rows = choices.get("feedback") or []
        if feedback_rows:
            lines.append("生圖調整紀錄（改圖僅一次）：")
            lines.extend(f"  - {row}" for row in feedback_rows[:5])
        return ManualSection(heading="六、驗證與調整紀錄", body="\n".join(lines))

    def _render_section(
        self, layout: LayoutDoc, images: ImageLibraryDoc
    ) -> tuple[ManualSection, dict[str, str]]:
        image_ids: list[str] = []
        images_b64: dict[str, str] = {}
        lines: list[str] = []
        for room in layout.rooms:
            record = images.latest(room.room_id, "edit") or images.latest(
                room.room_id, "full_render"
            )
            if record is None:
                continue
            lines.append(f"{room.name}：{record.image_id}（模型 {record.model or '未記錄'}）")
            if record.notices:
                lines.extend(f"  - 備註：{notice}" for notice in record.notices[:3])
            image_ids.append(record.image_id)
            if _looks_like_b64(record.image_ref):
                images_b64[record.image_id] = record.image_ref
        if not lines:
            lines.append("（尚無渲染成果）")
        section = ManualSection(
            heading="七、渲染成果", body="\n".join(lines), image_ids=image_ids
        )
        return section, images_b64

    def _engineering_section(self, choices: dict) -> ManualSection:
        body = (
            "工程數量、費率與工序排程沿用工程文件 MVP（設計師鎖定 D-revision 後之 "
            "ReportPayload）產出，於本手冊以附錄章節併入。\n"
            "正式模式缺單價或工率時保留 pending_quote／待確認，本手冊不自行補猜總價。\n"
            f"對應設計 revision：{choices.get('design_revision', '（保存時寫入）')}"
        )
        return ManualSection(heading="八、工程與預算章節", body=body)
