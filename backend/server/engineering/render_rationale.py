"""逐圖設計理念：把第 8 步隨圖落地的 prompt 素材整理進 ReportPayload。

資料來源是 render_outputs 的 ``design_context``／``prompt_text``（見
``render_providers.build_design_context``），生圖當下就固定了；這裡只做
決定性重排版，不呼叫 LLM、不生成新語意，也不改動鎖定快照——因此
snapshot_hash 完全不受影響。瀏覽器截圖（browser_capture）沒有 prompt，
不會被編造理念，如實缺席。
"""
from __future__ import annotations

from typing import Any, Callable

from .models import ProjectSnapshot, RenderRationale

_SURFACE_LABELS = (
    ("wall", "牆面"),
    ("floor", "地板"),
    ("lighting", "燈光"),
    ("rendering", "渲染語言"),
)


def _format_rationale(context: dict[str, Any]) -> str:
    segments: list[str] = []
    style_name = str(context.get("style_name") or "").strip()
    if style_name:
        segments.append(f"整體以「{style_name}」為風格基調。")
    surfaces = context.get("surfaces") or {}
    surface_parts = [
        f"{label}：{surfaces[key]}"
        for key, label in _SURFACE_LABELS
        if surfaces.get(key)
    ]
    if surface_parts:
        segments.append("；".join(surface_parts) + "。")
    notes = [str(note).strip() for note in context.get("requirement_notes") or []]
    notes = [note for note in notes if note]
    if notes:
        segments.append("本張回應的需求問卷重點：" + "；".join(notes) + "。")
    if not segments:
        # prompt 有落地但素材為空（極舊紀錄）：只陳述鎖定事實，不補猜。
        segments.append("本張生圖沿用專案已鎖定的場景、家具與視角，僅補完材質與光線。")
    return " ".join(segments)


class RenderRationaleService:
    def __init__(self, project_store_getter: Callable[[], Any]) -> None:
        self._project_store_getter = project_store_getter

    def collect(self, snapshot: ProjectSnapshot) -> list[RenderRationale]:
        try:
            store = self._project_store_getter()
        except Exception:
            # 理念是報告的加值內容；store 暫時不可用時報告照樣產出，
            # 缺席會在 HTML 逐圖區如實顯示為「無對應理念紀錄」。
            return []
        rationales: list[RenderRationale] = []
        seen: set[str] = set()
        for room in snapshot.rooms:
            for reference in room.renders:
                render_id = reference.render_id
                if not render_id or render_id in seen:
                    continue
                seen.add(render_id)
                try:
                    record = store.get_render(snapshot.project_id, render_id)
                except (FileNotFoundError, KeyError):
                    continue
                context = record.get("design_context") or {}
                if not context and not record.get("prompt_text"):
                    continue
                room_label = str(
                    context.get("room_label") or room.name or room.room_id
                )
                rationales.append(
                    RenderRationale(
                        render_id=render_id,
                        room_id=str(context.get("room_id") or room.room_id),
                        room_label=room_label,
                        style_card_id=record.get("style_card_id"),
                        style_name_zh=(
                            str(context["style_name"])
                            if context.get("style_name")
                            else None
                        ),
                        palette_hex=[
                            str(color) for color in context.get("palette_hex") or []
                        ],
                        surfaces_zh={
                            str(key): str(value)
                            for key, value in (context.get("surfaces") or {}).items()
                        },
                        requirement_notes_zh=[
                            str(note)
                            for note in context.get("requirement_notes") or []
                        ],
                        rationale_zh=_format_rationale(context),
                        prompt_hash=record.get("prompt_hash"),
                    )
                )
        return rationales
