"""PDF 組版輸出：多頁、含圖、無中文字型時也不失敗。"""
from pathlib import Path

from backend.agent.documents import DesignManualDoc, ManualSection
from backend.agent.tools.render_pdf import RenderPdfTool

from .conftest import make_png_b64


def test_render_pdf_multipage_with_image(tmp_path):
    manual = DesignManualDoc(
        title="RoomPilot 測試設計手冊",
        sections=[
            ManualSection(
                heading="一、專案與需求摘要",
                body="這是一段測試內文。\n" + "很長的中文段落內容，" * 40,
            ),
            ManualSection(heading="二、渲染成果", body="客廳渲染圖如下。", image_ids=["img1"]),
        ],
    )
    result = RenderPdfTool().run(
        manual, str(tmp_path / "manual.pdf"), {"img1": make_png_b64(size=(320, 200))}
    )
    pdf_path = Path(result["pdf_path"])
    assert pdf_path.exists()
    assert pdf_path.read_bytes()[:4] == b"%PDF"
    assert result["pages"] >= 3  # 封面＋兩個章節
