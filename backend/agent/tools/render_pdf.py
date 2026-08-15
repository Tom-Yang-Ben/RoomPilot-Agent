"""組版輸出 tool：把設計手冊內容與生圖渲染成多頁 PDF。

實作策略：用 Pillow 逐頁排版（A4 @150dpi）後以 ``save_all`` 輸出多頁 PDF，
零新增依賴（repo baseline 已含 Pillow）。代價是文字為點陣、不可選取；
若日後需要向量文字排版，於此替換為專門排版工具即可（介面不變）。

中文字型尋找順序：``ROOMPILOT_PDF_FONT`` 環境變數 → Windows 常見中文字型
→ Noto 系列；都找不到時退回 Pillow 內建字型（中文會缺字，僅保底不失敗）。
"""
from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..documents import DesignManualDoc
from .base import ToolContract, ToolError

PAGE_W, PAGE_H = 1240, 1754  # A4 @ 150dpi
MARGIN = 100
CONTENT_W = PAGE_W - 2 * MARGIN
INK = (31, 36, 48)
MUTED = (92, 100, 112)
LINE = (210, 214, 222)

_FONT_CANDIDATES = [
    ("C:/Windows/Fonts/msjh.ttc", 0),
    ("C:/Windows/Fonts/msyh.ttc", 0),
    ("C:/Windows/Fonts/mingliu.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
]


def _font_path() -> tuple[str, int] | None:
    explicit = os.getenv("ROOMPILOT_PDF_FONT", "").strip()
    if explicit and Path(explicit).exists():
        return explicit, 0
    for path, index in _FONT_CANDIDATES:
        if Path(path).exists():
            return path, index
    return None


def _load_font(size: int):
    found = _font_path()
    if found:
        try:
            return ImageFont.truetype(found[0], size, index=found[1])
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # 舊版 Pillow 無 size 參數
        return ImageFont.load_default()


class _PageWriter:
    """逐頁往下寫的簡單排版器；空間不足自動換頁。"""

    def __init__(self) -> None:
        self.pages: list[Image.Image] = []
        self.draw: ImageDraw.ImageDraw | None = None
        self.y = MARGIN
        self.new_page()

    def new_page(self) -> None:
        page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        self.pages.append(page)
        self.draw = ImageDraw.Draw(page)
        self.y = MARGIN

    def ensure(self, height: int) -> None:
        if self.y + height > PAGE_H - MARGIN:
            self.new_page()

    def text_block(self, text: str, font, *, color=INK, line_gap: int = 10) -> None:
        for paragraph in text.split("\n"):
            lines = self._wrap(paragraph, font) or [""]
            for line in lines:
                height = self._line_height(font)
                self.ensure(height + line_gap)
                self.draw.text((MARGIN, self.y), line, font=font, fill=color)
                self.y += height + line_gap

    def divider(self) -> None:
        self.ensure(24)
        self.draw.line([(MARGIN, self.y), (PAGE_W - MARGIN, self.y)], fill=LINE, width=2)
        self.y += 24

    def spacer(self, height: int) -> None:
        self.ensure(height)
        self.y += height

    def image(self, image: Image.Image, caption: str, caption_font) -> None:
        image = image.convert("RGB")
        scale = min(CONTENT_W / image.width, 900 / image.height, 1.0)
        resized = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        )
        block = resized.height + 46
        self.ensure(block)
        offset_x = MARGIN + (CONTENT_W - resized.width) // 2
        self.pages[-1].paste(resized, (offset_x, self.y))
        self.y += resized.height + 8
        if caption:
            self.draw.text((MARGIN, self.y), caption, font=caption_font, fill=MUTED)
            self.y += self._line_height(caption_font) + 12

    def _line_height(self, font) -> int:
        bbox = self.draw.textbbox((0, 0), "永Ag", font=font)
        return bbox[3] - bbox[1] + 6

    def _wrap(self, text: str, font) -> list[str]:
        lines: list[str] = []
        current = ""
        for char in text:
            trial = current + char
            if self.draw.textlength(trial, font=font) > CONTENT_W and current:
                lines.append(current)
                current = char
            else:
                current = trial
        if current:
            lines.append(current)
        return lines


class RenderPdfTool:
    contract = ToolContract(
        name="render_pdf",
        description="把設計手冊（章節＋引用生圖）排版輸出為多頁 PDF 檔。",
        input_schema={
            "type": "object",
            "properties": {
                "manual": {"type": "object"},
                "images_b64": {"type": "object", "description": "image_id -> base64"},
                "out_path": {"type": "string"},
            },
            "required": ["manual", "out_path"],
        },
        output_schema={
            "type": "object",
            "properties": {"pdf_path": {"type": "string"}, "pages": {"type": "integer"}},
        },
    )

    def run(
        self,
        manual: DesignManualDoc,
        out_path: str,
        images_b64: dict[str, str] | None = None,
    ) -> dict:
        images_b64 = images_b64 or {}
        title_font = _load_font(46)
        heading_font = _load_font(33)
        body_font = _load_font(24)
        caption_font = _load_font(19)

        writer = _PageWriter()
        writer.spacer(360)
        writer.text_block(manual.title, title_font)
        writer.spacer(18)
        writer.text_block("RoomPilot 設計成果統整", body_font, color=MUTED)

        for section in manual.sections:
            writer.new_page()
            writer.text_block(section.heading, heading_font)
            writer.divider()
            if section.body:
                writer.text_block(section.body, body_font)
            for image_id in section.image_ids:
                encoded = images_b64.get(image_id)
                if not encoded:
                    continue
                try:
                    image = Image.open(io.BytesIO(base64.b64decode(encoded)))
                except Exception:
                    writer.text_block(f"（影像 {image_id} 無法解碼）", caption_font, color=MUTED)
                    continue
                writer.spacer(10)
                writer.image(image, f"圖：{image_id}", caption_font)

        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            writer.pages[0].save(
                path,
                "PDF",
                save_all=True,
                append_images=writer.pages[1:],
                resolution=150.0,
            )
        except Exception as exc:
            raise ToolError(f"PDF 輸出失敗：{exc}", tool=self.contract.name) from exc
        return {"pdf_path": str(path), "pages": len(writer.pages)}
