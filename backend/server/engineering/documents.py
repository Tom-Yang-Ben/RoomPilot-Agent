from __future__ import annotations

import base64
import html
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable
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
        render_asset_loader: Callable[[str, str], bytes | None] | None = None,
    ) -> None:
        self.generated_dir = generated_dir.resolve()
        self.repository = repository
        self.api_prefix = api_prefix.rstrip("/")
        self.workbook_builder = Path(__file__).with_name("workbook_builder.mjs")
        # (project_id, render_id) -> PNG bytes。報告 HTML 是要離線交付的文件，
        # 而 renders 下載端點需要 bearer token——<img src> 不帶身分一律 401，
        # 所以生成時直接內嵌 base64；loader 缺席或單張失敗時退回原網址。
        self.render_asset_loader = render_asset_loader

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
    def _render_design_section(report: ReportPayload, esc) -> str:
        """設計風格與語彙章節。所有內容都來自知識庫或快照，不在此處生成文字。"""
        design = report.design_narrative
        if design.style_id is None and not design.rooms:
            return ""
        bullets = lambda items: "".join(f"<li>{esc(item)}</li>" for item in items)

        color = ""
        if design.color is not None:
            swatches = "".join(
                f'<div class="swatch"><span style="background:{esc(role.hex)}"></span>'
                f"<b>{esc(role.hex)}</b><small>{esc(role.usage_zh)}</small></div>"
                for role in design.color.roles
            ) or '<p class="empty">查無可用色票。</p>'
            ratios = ""
            if design.color.dominant_ratio is not None:
                ratios = (
                    f"<p>建議面積比例：主色 {design.color.dominant_ratio:.0%}／"
                    f"次色 {design.color.secondary_ratio:.0%}／"
                    f"點綴 {design.color.accent_ratio:.0%}</p>"
                )
            color = f"""
            <h3>色彩策略</h3>
            <p class="muted">色票來源：{esc(design.color.palette_source_detail)}</p>
            <div class="swatches">{swatches}</div>
            {ratios}
            <ul>
              <li><b>色溫</b>：{esc(design.color.temperature_zh)}</li>
              <li><b>明度對比</b>：{esc(design.color.value_contrast_zh)}</li>
              <li><b>彩度上限</b>：{esc(design.color.saturation_ceiling_zh)}</li>
              <li><b>判讀規則</b>：{esc(design.color.reading_rule_zh)}</li>
            </ul>"""

        material = ""
        if design.material is not None:
            selected = bullets(design.material.selected_materials_zh) or (
                "<li>快照尚未指定裝修材料</li>"
            )
            material = f"""
            <h3>材質語彙</h3>
            <div class="two">
              <div><h4>本案實際選用（來自快照）</h4><ul>{selected}</ul></div>
              <div><h4>風格建議主材</h4><ul>
                {bullets(design.material.primary_materials_zh) or '<li>—</li>'}
              </ul></div>
            </div>
            <ul>
              <li><b>表面處理</b>：{esc(design.material.finish_rule_zh)}</li>
              <li><b>對比邏輯</b>：{esc(design.material.contrast_logic_zh)}</li>
              <li><b>地牆關係</b>：{esc(design.material.floor_wall_relationship_zh)}</li>
            </ul>
            <h4>應避免的組合</h4>
            <ul>{bullets(design.material.avoid_combinations_zh) or '<li>—</li>'}</ul>"""

        rooms = "".join(
            f"""
            <div class="design-room">
              <h4>{esc(room.room_name)} <small>{esc(room.room_name_zh or room.room_type)}</small></h4>
              <p>{esc(room.furniture_summary_zh)}</p>
              {'<p><b>設計重點</b>：' + esc(room.design_focus_zh) + '</p>' if room.design_focus_zh else ''}
              {'<p><b>動線</b>：' + esc(room.circulation_zh) + '</p>' if room.circulation_zh else ''}
              {'<p><b>照明</b>：' + esc(room.lighting_zh) + '</p>' if room.lighting_zh else ''}
              {'<p><b>收納</b>：' + esc(room.storage_zh) + '</p>' if room.storage_zh else ''}
              {'<p class="muted">此房型未收錄設計語彙，僅列快照事實。</p>' if not room.knowledge_available else ''}
            </div>"""
            for room in design.rooms
        )

        evidence = "".join(
            f"<li>{esc(item.source_id)}（{esc(item.scope)}／{esc(item.confidence)}）"
            f"{'：' + esc(item.caveat_zh) if item.caveat_zh else ''}</li>"
            for item in design.evidence
        )
        form = "".join(
            f"<li><b>{esc(key)}</b>：{esc(value)}</li>"
            for key, value in design.form_vocabulary_zh.items()
        )
        return f"""
        <section><h2>設計風格與語彙</h2>
        <div class="meta"><span>風格：{esc(design.style_name_zh or '未設定')}</span>
        <span>{esc(design.style_id or '—')}</span></div>
        <p class="muted">{esc(design.style_resolution_zh)}</p>
        {'<p>' + esc(design.positioning_zh) + '</p>' if design.positioning_zh else ''}
        {'<h3>造型語言</h3><p>' + esc(design.design_language_zh) + '</p>' if design.design_language_zh else ''}
        {'<ul>' + form + '</ul>' if form else ''}
        {'<h4>代表元素</h4><ul>' + bullets(design.signature_elements_zh) + '</ul>' if design.signature_elements_zh else ''}
        {'<h4>照明手法</h4><p>' + esc(design.lighting_approach_zh) + '</p>' if design.lighting_approach_zh else ''}
        {'<h4>應避免</h4><ul>' + bullets(design.avoid_zh) + '</ul>' if design.avoid_zh else ''}
        {color}
        {material}
        <h3>逐房設計說明</h3>{rooms}
        <h4>資料來源與可信度</h4><ul>{evidence}</ul>
        <p class="muted">{esc(design.disclaimer_zh)}</p>
        </section>"""

    @staticmethod
    def _render_furniture_section(report: ReportPayload, esc) -> str:
        """家具採購明細。與工程施工費分開列示，兩者不合計。"""
        estimate = report.furniture_estimate
        if not estimate.lines:
            return ""
        rows = "".join(
            f"""<tr class="{'unpriced' if line.status != 'priced' else ''}">
              <td>{esc(line.room_name)}</td>
              <td>{esc(line.name)}<br><small>{esc(line.category)}</small></td>
              <td>{line.width_cm:g}×{line.depth_cm:g}×{line.height_cm:g}</td>
              <td class="num">{line.quantity}</td>
              <td class="num">{f'{line.unit_price_twd:,}' if line.unit_price_twd is not None else '待詢價'}
                {'<br><small>推估價</small>' if line.price_is_estimated else ''}</td>
              <td class="num">{f'{line.subtotal_twd:,}' if line.subtotal_twd is not None else '—'}</td>
            </tr>"""
            for line in estimate.lines
        )
        total = (
            f"NT$ {estimate.estimated_total_twd:,}"
            if estimate.estimated_total_twd is not None
            else f"NT$ {estimate.known_subtotal_twd:,}（不完整）"
        )
        return f"""
        <section><h2>家具採購明細</h2>
        <div class="meta"><span>已知小計：NT$ {estimate.known_subtotal_twd:,}</span>
        <span>採購總價：{total}</span><span>已報價 {estimate.priced_count} 項</span>
        <span>待詢價 {estimate.unpriced_count} 項</span>
        <span>型錄來源：{esc(estimate.catalog_provider)}</span></div>
        <table><thead><tr><th>空間</th><th>品項</th><th>尺寸 (cm)</th>
        <th>數量</th><th>單價 (TWD)</th><th>小計 (TWD)</th></tr></thead>
        <tbody>{rows}</tbody></table>
        <p class="muted">{esc(estimate.disclaimer)}</p>
        </section>"""

    def _embedded_render_src(self, project_id: str, reference) -> str:
        if self.render_asset_loader is not None and reference.render_id:
            try:
                raw = self.render_asset_loader(project_id, reference.render_id)
            except Exception:
                raw = None
            if raw:
                return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        return reference.render_url

    def _render_html(self, report: ReportPayload) -> str:
        esc = lambda value: html.escape(str(value if value is not None else ""))
        quantity_by_room = {item.room_id: item for item in report.quantities.rooms}
        retrieval_by_room = {item.room_id: item for item in report.retrieval.rooms}
        rationale_by_render = {
            item.render_id: item for item in report.render_rationales
        }
        risks_by_room: dict[str, list] = {}
        for risk in report.risks.results:
            risks_by_room.setdefault(risk.room_id or "project", []).append(risk)
        room_sections: list[str] = []
        for room in report.snapshot.rooms:
            quantity = quantity_by_room[room.room_id]
            retrieval = retrieval_by_room[room.room_id]
            figures: list[str] = []
            for item in room.renders:
                rationale = rationale_by_render.get(item.render_id or "")
                rationale_html = (
                    f'<p class="render-rationale">{esc(rationale.rationale_zh)}</p>'
                    if rationale is not None
                    else '<p class="render-rationale muted">此圖無對應的生圖理念紀錄'
                    "（例如瀏覽器截圖）。</p>"
                )
                figures.append(
                    f'<figure><img src="{esc(self._embedded_render_src(report.project_id, item))}"'
                    f' alt="{esc(room.name)} {esc(item.view_name)}">'
                    f"<figcaption>{esc(item.view_name)}</figcaption>"
                    f"{rationale_html}</figure>"
                )
            renders = "".join(figures) or (
                '<p class="empty">尚無逐房生圖；需在第 8 步完成或由設計師補充。</p>'
            )
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
        design_section = DocumentService._render_design_section(report, esc)
        furniture_section = DocumentService._render_furniture_section(report, esc)
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
.render-rationale{{margin:6px 0 0;font-size:13px;line-height:1.6}}.render-rationale.muted{{color:var(--muted)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}li{{margin:5px 0}}.risk-high{{color:#a51d1d}}.risk-medium{{color:var(--warn)}}
.empty{{padding:16px;background:#f7f8f6;color:var(--muted)}}
.swatches{{display:flex;flex-wrap:wrap;gap:14px;margin:14px 0}}
.swatch{{display:flex;flex-direction:column;gap:4px;min-width:150px}}
.swatch span{{height:52px;border-radius:8px;border:1px solid var(--line)}}
.design-room{{padding:14px 0;border-top:1px dashed var(--line)}}
.design-room h4{{margin:0 0 6px}}.design-room p{{margin:4px 0}}
table{{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{background:#eef3ef}}td.num{{text-align:right;white-space:nowrap}}
tr.unpriced td{{color:var(--warn)}}
@media(max-width:700px){{main{{margin:0;padding:24px}}.two{{grid-template-columns:1fr}}
table{{display:block;overflow-x:auto}}}}
@media print{{body{{background:white}}main{{box-shadow:none;margin:0;max-width:none}}}}
</style></head><body><main>
<header><p class="muted">RoomPilot DESIGNER-LOCKED ENGINEERING MVP</p><h1>設計工程提案</h1>
<div class="meta"><span>專案：{esc(report.snapshot.project_name)}</span><span>Project ID：{esc(report.project_id)}</span>
<span>Revision：{esc(report.revision)}</span><span>鎖定者：{esc(report.snapshot.confirmed_by)}</span>
<span>產生時間：{esc(report.generated_at.isoformat())}</span></div>{demo_banner}
<p>{esc(report.narratives.design_summary)}</p></header>
{design_section}
{furniture_section}
<section><h2>工程摘要</h2><p>{esc(report.narratives.construction_summary)}</p><p>{esc(report.narratives.cost_summary)}</p><p>{esc(report.narratives.schedule_summary)}</p><p>{esc(report.narratives.risk_summary)}</p>
<p><b>Advanced RAG：</b>Structured Retrieval active；Semantic Adapter = {esc(retriever.adapter)}；{esc(retriever.message)}</p></section>
{''.join(room_sections)}
<section><h2>假設</h2><ul>{assumptions}</ul><h2>排除與專業責任</h2><ul>{exclusions}</ul>
<p class="muted">Snapshot SHA-256：{esc(report.snapshot_hash)}</p></section>
</main></body></html>"""
