from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from .models import DocumentManifest, ReportPayload
from .repository import EngineeringRepository


class WorkbookGenerationUnavailable(RuntimeError):
    pass


class DocumentService:
    def __init__(
        self,
        *,
        generated_dir: Path,
        repository: EngineeringRepository,
        api_prefix: str = "/api/v1",
    ) -> None:
        self.generated_dir = generated_dir.resolve()
        self.repository = repository
        self.api_prefix = api_prefix.rstrip("/")
        self.workbook_builder = Path(__file__).with_name("workbook_builder.mjs")

    def render(
        self, report: ReportPayload, requested_types: list[str]
    ) -> ReportPayload:
        supported = {
            "report_json": ("report_payload.json", "application/json"),
            "report_html": (
                "design_engineering_proposal.html",
                "text/html; charset=utf-8",
            ),
            "estimate_xlsx": (
                "estimate_and_schedule.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        }
        requested = list(dict.fromkeys(requested_types))
        if not requested or any(item not in supported for item in requested):
            raise ValueError("UNSUPPORTED_DOCUMENT_TYPE")
        package_dir = (
            self.generated_dir
            / report.project_id
            / report.revision
            / report.package_id
        )
        package_dir.mkdir(parents=True, exist_ok=True)
        manifests: list[DocumentManifest] = []
        paths: dict[str, Path] = {}
        for document_type in requested:
            file_name, content_type = supported[document_type]
            document_id = f"doc_{uuid4().hex[:12]}"
            manifests.append(
                DocumentManifest(
                    document_id=document_id,
                    document_type=document_type,
                    file_name=file_name,
                    content_type=content_type,
                    download_url=(
                        f"{self.api_prefix}/documents/{document_id}/download"
                    ),
                    byte_size=0,
                )
            )
            paths[document_type] = package_dir / file_name

        provisional = report.model_copy(update={"documents": manifests}, deep=True)
        if "estimate_xlsx" in paths:
            self._write_xlsx(provisional, paths["estimate_xlsx"])
        if "report_html" in paths:
            paths["report_html"].write_text(
                self._render_html(provisional), encoding="utf-8"
            )

        sized_manifests = [
            manifest.model_copy(
                update={
                    "byte_size": (
                        paths[manifest.document_type].stat().st_size
                        if manifest.document_type != "report_json"
                        and paths[manifest.document_type].is_file()
                        else 0
                    )
                }
            )
            for manifest in manifests
        ]
        final_report = report.model_copy(
            update={"documents": sized_manifests}, deep=True
        )
        if "report_html" in paths:
            paths["report_html"].write_text(
                self._render_html(final_report), encoding="utf-8"
            )
        if "report_json" in paths:
            paths["report_json"].write_text(
                json.dumps(
                    final_report.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        final_manifests = []
        for manifest in sized_manifests:
            path = paths[manifest.document_type]
            actual = manifest.model_copy(update={"byte_size": path.stat().st_size})
            final_manifests.append(actual)
        final_report = final_report.model_copy(
            update={"documents": final_manifests}, deep=True
        )
        if "report_json" in paths:
            # JSON's own byte size is diagnostic metadata. A final rewrite keeps
            # all other document sizes accurate without a recursive size loop.
            paths["report_json"].write_text(
                json.dumps(
                    final_report.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        self.repository.save_package(final_report)
        for manifest in final_manifests:
            self.repository.register_document(
                final_report.package_id,
                manifest,
                paths[manifest.document_type],
            )
        return final_report

    def _write_xlsx(self, report: ReportPayload, path: Path) -> None:
        node = os.getenv("ROOMPILOT_ARTIFACT_NODE", "").strip() or shutil.which(
            "node"
        )
        if not node:
            raise WorkbookGenerationUnavailable(
                "artifact-tool workbook builder requires Node.js"
            )
        input_path = path.with_suffix(".report-input.json")
        input_path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        environment = os.environ.copy()
        try:
            completed = subprocess.run(
                [str(node), str(self.workbook_builder), str(input_path), str(path)],
                cwd=str(self.workbook_builder.parent),
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=float(os.getenv("ROOMPILOT_XLSX_TIMEOUT_SECONDS", "90")),
                check=False,
            )
        finally:
            input_path.unlink(missing_ok=True)
        if completed.returncode != 0 or not path.is_file():
            reason = (completed.stderr or completed.stdout or "unknown error").strip()
            raise WorkbookGenerationUnavailable(reason[-1000:])

    @staticmethod
    def _render_html(report: ReportPayload) -> str:
        esc = lambda value: html.escape(str(value if value is not None else ""))
        quantity_by_room = {item.room_id: item for item in report.quantities.rooms}
        retrieval_by_room = {item.room_id: item for item in report.retrieval.rooms}
        risks_by_room: dict[str, list] = {}
        for risk in report.risks.results:
            risks_by_room.setdefault(risk.room_id or "project", []).append(risk)
        room_sections: list[str] = []
        for room in report.snapshot.rooms:
            quantity = quantity_by_room[room.room_id]
            retrieval = retrieval_by_room[room.room_id]
            renders = "".join(
                f'<figure><img src="{esc(item.render_url)}" alt="{esc(room.name)} {esc(item.view_name)}">'
                f"<figcaption>{esc(item.view_name)}</figcaption></figure>"
                for item in room.renders
            ) or '<p class="empty">尚無逐房生圖；需在第 8 步完成或由設計師補充。</p>'
            materials = "".join(
                f"<li><b>{esc(item.part)}</b>：{esc(item.name)}（耗損 {item.waste_rate:.0%}）</li>"
                for item in room.materials
            ) or "<li>尚未指定裝修材料</li>"
            furniture = "".join(
                f"<li>{esc(item.name)} × {item.quantity}，{item.width_cm:g} × {item.depth_cm:g} × {item.height_cm:g} cm"
                f"{'；配置待處理：' + esc(item.placement_reason) if item.placement_failed else ''}</li>"
                for item in room.furniture
            ) or "<li>此房間沒有正式配置家具</li>"
            mep = "".join(
                f"<li><b>{esc(item.system)}</b>：{esc(item.related_item_name)}—{esc(item.reason)}；"
                f"{'已有相同系統點位' if item.covered_by_existing_point else '待確認／補點'} "
                f"<small>{esc(item.source_id)} / {esc(item.confidence)}</small></li>"
                for item in retrieval.mep_suggestions
            ) or "<li>目前沒有由結構化映射觸發的水電／空調建議</li>"
            notes = "".join(
                f"<li><b>{esc(item.title)}</b>：{esc(item.content)} "
                f"<small>{esc(item.source_id)} / {esc(item.confidence)}</small></li>"
                for item in retrieval.construction_notes
            ) or "<li>目前沒有命中的工程注意事項</li>"
            risks = "".join(
                f'<li class="risk-{esc(item.severity)}"><b>{esc(item.rule)}</b>：{esc(item.message)}'
                f"{'（待專業確認）' if item.professional_confirmation_required else ''}</li>"
                for item in risks_by_room.get(room.room_id, [])
                if not item.passed
            ) or "<li>未發現未通過的規則項目</li>"
            room_sections.append(
                f"""
                <section class="room">
                  <h2>{esc(room.name)} <small>{esc(room.room_type)} / {esc(room.room_id)}</small></h2>
                  <div class="metrics">
                    <span>長 {quantity.length_cm:g} cm</span><span>寬 {quantity.width_cm:g} cm</span>
                    <span>高 {quantity.height_cm:g} cm</span><span>地坪 {quantity.floor_area_m2:g} m²</span>
                    <span>牆面毛面積 {quantity.gross_wall_area_m2:g} m²</span>
                    <span>牆面淨面積 {quantity.net_wall_area_m2:g} m²</span>
                    <span>天花 {quantity.ceiling_area_m2:g} m²</span>
                  </div>
                  <div class="renders">{renders}</div>
                  <div class="two"><div><h3>家具</h3><ul>{furniture}</ul></div><div><h3>裝修材料</h3><ul>{materials}</ul></div></div>
                  <h3>水電／空調需求建議</h3><ul>{mep}</ul>
                  <h3>工程工法與 evidence</h3><ul>{notes}</ul>
                  <h3>空間風險與待專業確認</h3><ul>{risks}</ul>
                </section>
                """
            )
        assumptions = "".join(f"<li>{esc(item)}</li>" for item in report.assumptions)
        exclusions = "".join(f"<li>{esc(item)}</li>" for item in report.exclusions)
        demo_banner = (
            f'<div class="demo">{esc(report.demo_disclaimer)}</div>'
            if report.demo_mode
            else ""
        )
        retriever = report.retrieval.semantic_retriever
        return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RoomPilot 設計工程提案</title><style>
:root{{--ink:#253127;--muted:#667067;--line:#d9dfda;--paper:#fff;--accent:#335f47;--warn:#9a561f}}
*{{box-sizing:border-box}}body{{margin:0;background:#f1f3ef;color:var(--ink);font:15px/1.65 system-ui,"Noto Sans TC",sans-serif}}
main{{max-width:1080px;margin:32px auto;background:var(--paper);padding:48px;box-shadow:0 10px 40px #20302618}}
h1,h2,h3{{line-height:1.25}}h1{{font-size:34px;margin-bottom:8px}}h2{{border-bottom:2px solid var(--accent);padding-bottom:10px}}
small,.muted{{color:var(--muted)}}.meta,.metrics{{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}}.meta span,.metrics span{{background:#eef3ef;padding:7px 12px;border-radius:999px}}
.demo{{background:#a51d1d;color:white;font-size:20px;font-weight:800;padding:16px 20px;margin:20px 0;border:5px solid #ffd66b}}
.room{{padding:28px 0;border-top:1px solid var(--line)}}.renders{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
figure{{margin:0}}img{{width:100%;max-height:430px;object-fit:cover;border-radius:12px;border:1px solid var(--line)}}figcaption{{color:var(--muted)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}li{{margin:5px 0}}.risk-high{{color:#a51d1d}}.risk-medium{{color:var(--warn)}}
.empty{{padding:16px;background:#f7f8f6;color:var(--muted)}}@media(max-width:700px){{main{{margin:0;padding:24px}}.two{{grid-template-columns:1fr}}}}
@media print{{body{{background:white}}main{{box-shadow:none;margin:0;max-width:none}}}}
</style></head><body><main>
<header><p class="muted">RoomPilot DESIGNER-LOCKED ENGINEERING MVP</p><h1>設計工程提案</h1>
<div class="meta"><span>專案：{esc(report.snapshot.project_name)}</span><span>Project ID：{esc(report.project_id)}</span>
<span>Revision：{esc(report.revision)}</span><span>鎖定者：{esc(report.snapshot.confirmed_by)}</span>
<span>產生時間：{esc(report.generated_at.isoformat())}</span></div>{demo_banner}
<p>{esc(report.narratives.design_summary)}</p></header>
<section><h2>工程摘要</h2><p>{esc(report.narratives.construction_summary)}</p><p>{esc(report.narratives.cost_summary)}</p><p>{esc(report.narratives.schedule_summary)}</p><p>{esc(report.narratives.risk_summary)}</p>
<p><b>Advanced RAG：</b>Structured Retrieval active；Semantic Adapter = {esc(retriever.adapter)}；{esc(retriever.message)}</p></section>
{''.join(room_sections)}
<section><h2>假設</h2><ul>{assumptions}</ul><h2>排除與專業責任</h2><ul>{exclusions}</ul>
<p class="muted">Snapshot SHA-256：{esc(report.snapshot_hash)}</p></section>
</main></body></html>"""
