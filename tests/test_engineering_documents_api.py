from __future__ import annotations

import json
import os
import re
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.server.main import app


client = TestClient(app)


def _project() -> dict:
    response = client.post("/api/projects", json={"name": "工程文件 E2E"})
    assert response.status_code == 201
    return response.json()["project"]


def _snapshot(project: dict) -> dict:
    return {
        "project_id": project["project_id"],
        "project_name": project["name"],
        "revision": f"D{project['revision']}",
        "source_project_revision": project["revision"],
        "pricing_basis_date": date.today().isoformat(),
        "rooms": [
            {
                "room_id": "living-1",
                "name": "客廳",
                "room_type": "living_room",
                "style": "scandinavian",
                "geometry": {
                    "length_cm": 420,
                    "width_cm": 360,
                    "height_cm": 270,
                    "opening_area_m2": 2.1,
                    "polygon_cm": [
                        {"x_cm": 0, "y_cm": 0},
                        {"x_cm": 420, "y_cm": 0},
                        {"x_cm": 420, "y_cm": 360},
                        {"x_cm": 0, "y_cm": 360},
                    ],
                },
                "materials": [
                    {
                        "material_id": "spc-oak",
                        "part": "floor",
                        "name": "SPC 木紋地板",
                        "waste_rate": 0.08,
                    },
                    {
                        "material_id": "latex-wall",
                        "part": "wall",
                        "name": "乳膠漆",
                        "waste_rate": 0.05,
                    },
                ],
                "furniture": [
                    {
                        "furniture_id": "tv-1",
                        "name": "電視",
                        "category": "television",
                        "width_cm": 120,
                        "depth_cm": 10,
                        "height_cm": 80,
                        "x_cm": 0,
                        "y_cm": 0,
                    }
                ],
                "equipment_requirements": [
                    {
                        "equipment_id": "air-conditioner",
                        "name": "分離式冷氣",
                        "category": "air_conditioner",
                        "quantity": 1,
                        "source": "questionnaire",
                    }
                ],
                "mep_points": [],
                "renders": [
                    {
                        "render_url": "/api/projects/demo/renders/demo/png",
                        "view_name": "客廳設計意向圖",
                    }
                ],
            }
        ],
        "assumptions": ["現場為空屋且可於日間施工。"],
    }


def _save_and_lock(project: dict) -> dict:
    snapshot = _snapshot(project)
    revision = snapshot["revision"]
    saved = client.put(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/snapshot",
        json=snapshot,
    )
    assert saved.status_code == 200
    locked = client.post(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/lock",
        json={"confirmed_by": "王設計師"},
    )
    assert locked.status_code == 200
    return locked.json()["snapshot"]


def test_unlocked_revision_returns_required_409() -> None:
    project = _project()
    snapshot = _snapshot(project)
    revision = snapshot["revision"]
    assert client.put(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/snapshot",
        json=snapshot,
    ).status_code == 200
    response = client.post(
        f"/api/v1/projects/{project['project_id']}/engineering-packages",
        json={"revision": revision, "documents": ["report_json"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "REVISION_NOT_LOCKED"


def test_demo_e2e_generates_html_json_and_four_sheet_artifact_xlsx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not os.getenv("ROOMPILOT_ARTIFACT_TOOL_MODULES"):
        pytest.skip("artifact-tool module path is not configured")
    monkeypatch.setenv("ROOMPILOT_DEMO_MODE", "true")
    project = _project()
    snapshot = _save_and_lock(project)
    response = client.post(
        f"/api/v1/projects/{project['project_id']}/engineering-packages",
        json={
            "revision": snapshot["revision"],
            "documents": ["report_json", "report_html", "estimate_xlsx"],
        },
    )
    assert response.status_code == 202
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}")
    assert job.status_code == 200
    assert job.json()["status"] in {"completed", "completed_with_warnings"}
    assert job.json()["progress"] == 100
    assert job.json()["stage"] == "completed"

    package = client.get(f"/api/v1/packages/{job.json()['package_id']}")
    assert package.status_code == 200
    report = package.json()
    assert report["demo_mode"] is True
    assert "示範資料，非正式報價" in report["demo_disclaimer"]
    assert report["snapshot"]["revision"] == snapshot["revision"]
    assert report["snapshot"]["approval_status"] == "designer_confirmed"
    assert report["estimate"]["estimated_total"] > 0
    assert report["schedule"]["estimated_total_days"] > 0
    assert report["retrieval"]["semantic_retriever"]["is_real_vector_retrieval"] is False

    downloaded = {}
    for document in report["documents"]:
        result = client.get(document["download_url"])
        assert result.status_code == 200
        assert result.content
        downloaded[document["document_type"]] = result.content

    html_document = next(
        document
        for document in report["documents"]
        if document["document_type"] == "report_html"
    )
    inline_preview = client.get(f'{html_document["download_url"]}?preview=1')
    assert inline_preview.status_code == 200
    assert inline_preview.headers["content-disposition"].startswith("inline;")
    assert inline_preview.headers["content-type"].startswith("text/html")

    html_text = downloaded["report_html"].decode("utf-8")
    assert "設計工程提案" in html_text
    assert "客廳" in html_text
    assert "水電／空調需求建議" in html_text
    assert "示範資料，非正式報價" in html_text
    assert snapshot["revision"] in html_text

    debug_report = json.loads(downloaded["report_json"].decode("utf-8"))
    assert debug_report["snapshot_hash"] == report["snapshot_hash"]
    assert debug_report["package_id"] == report["package_id"]

    with zipfile.ZipFile(BytesIO(downloaded["estimate_xlsx"])) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
        # 2026-08-03 起 builder 產四張表（58e11c55 加入家具採購與設計語彙）。
        # sheet 與 f 標籤不綁 XML 命名空間前綴：不同 xlsx writer（@oai/artifact-tool
        # 與本機相容層）序列化前綴不同，內容契約不該綁 writer 實作。
        assert len(re.findall(r"<(?:\w+:)?sheet ", workbook_xml)) == 4
        assert "工程估價" in workbook_xml
        assert "初步排程" in workbook_xml
        assert "家具採購" in workbook_xml
        assert "設計語彙" in workbook_xml
        worksheet_xml = "".join(
            workbook.read(name).decode("utf-8")
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        assert re.search(r"<(?:\w+:)?f>", worksheet_xml)


_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x87\xa1N\xd4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_report_carries_per_render_rationale_and_embeds_png(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """簡報鏈驗收：第 8 步落地的 prompt 素材要變成逐圖理念，圖要內嵌可離線看。"""
    from backend.server import main as server_main

    monkeypatch.setenv("ROOMPILOT_DEMO_MODE", "false")
    project = _project()
    render, project = server_main.PROJECT_STORE.save_render(
        project["project_id"],
        expected_revision=project["revision"],
        content=_TINY_PNG,
        white_model_version=0,
        viewpoint_version=0,
        style_version=0,
        style_card_id="card-nordic",
        provider="openrouter_image",
        room_id="living-1",
        prompt_text="你是室內設計渲染引擎。硬性限制：不得新增、刪除或移動任何家具。",
        design_context={
            "style_card_id": "card-nordic",
            "style_name": "北歐奶油風",
            "palette_hex": ["#F5EFE6", "#D8C3A5"],
            "surfaces": {"wall": "暖白乳膠漆", "floor": "淺橡木超耐磨木地板"},
            "room_id": "living-1",
            "room_label": "客廳",
            "requirement_notes": ["客廳——天花：線性燈天花、燈具：軌道燈"],
        },
    )
    snapshot = _snapshot(project)
    snapshot["rooms"][0]["renders"] = [
        {
            "render_url": (
                f"/api/projects/{project['project_id']}/renders/"
                f"{render['render_id']}/png"
            ),
            "view_name": "客廳渲染",
            "render_id": render["render_id"],
            "prompt_hash": render["prompt_hash"],
        },
        {
            # 瀏覽器截圖（無落地 prompt）：不得被編造理念。
            "render_url": "/api/projects/demo/renders/manual/png",
            "view_name": "設計師補充視角",
        },
    ]
    revision = snapshot["revision"]
    assert client.put(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/snapshot",
        json=snapshot,
    ).status_code == 200
    assert client.post(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/lock",
        json={"confirmed_by": "王設計師"},
    ).status_code == 200
    response = client.post(
        f"/api/v1/projects/{project['project_id']}/engineering-packages",
        json={"revision": revision, "documents": ["report_json", "report_html"]},
    )
    assert response.status_code == 202
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] in {"completed", "completed_with_warnings"}

    report = client.get(f"/api/v1/packages/{job['package_id']}").json()
    rationales = report["render_rationales"]
    assert len(rationales) == 1, "只有生圖有落地素材；截圖不得被編造理念"
    rationale = rationales[0]
    assert rationale["render_id"] == render["render_id"]
    assert rationale["room_label"] == "客廳"
    assert rationale["style_name_zh"] == "北歐奶油風"
    assert rationale["palette_hex"] == ["#F5EFE6", "#D8C3A5"]
    assert rationale["prompt_hash"] == render["prompt_hash"]
    assert "北歐奶油風" in rationale["rationale_zh"]
    assert "淺橡木超耐磨木地板" in rationale["rationale_zh"]
    assert "線性燈天花" in rationale["rationale_zh"]

    html_document = next(
        item for item in report["documents"] if item["document_type"] == "report_html"
    )
    html_text = client.get(html_document["download_url"]).content.decode("utf-8")
    # 報告是離線交付文件：圖片必須內嵌，不能指向需要 token 的下載端點。
    assert "data:image/png;base64," in html_text
    assert "整體以「北歐奶油風」為風格基調" in html_text
    assert "此圖無對應的生圖理念紀錄" in html_text

    # 舊 package 沒有 render_rationales 欄位也要能讀回（加法契約）。
    from backend.server.engineering.models import ReportPayload

    legacy = {
        key: value for key, value in report.items() if key != "render_rationales"
    }
    assert ReportPayload.model_validate(legacy).render_rationales == []


def test_production_report_has_pending_quotes_and_no_fake_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROOMPILOT_DEMO_MODE", "false")
    project = _project()
    snapshot = _save_and_lock(project)
    response = client.post(
        f"/api/v1/projects/{project['project_id']}/engineering-packages",
        json={"revision": snapshot["revision"], "documents": ["report_json"]},
    )
    assert response.status_code == 202
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed_with_warnings"
    report = client.get(f"/api/v1/packages/{job['package_id']}").json()
    assert report["demo_mode"] is False
    assert report["estimate"]["estimated_total"] is None
    assert report["estimate"]["pending_quote_count"] == len(
        report["estimate"]["lines"]
    )
    assert all(item["subtotal"] is None for item in report["estimate"]["lines"])
    assert report["schedule"]["estimated_total_days"] is None
