"""拿舊圖 tool：從生圖片庫取回指定房間的最新一張圖（改圖與報告用）。"""
from __future__ import annotations

from ..documents import ImageLibraryDoc, ImageRecord
from .base import ToolContract, ToolError


class FetchImageTool:
    contract = ToolContract(
        name="fetch_image",
        description="取回指定房間（可指定階段）最新一張生圖，供改圖或報告引用。",
        input_schema={
            "type": "object",
            "properties": {
                "images": {"type": "object"},
                "room_id": {"type": "string"},
                "stage": {"type": ["string", "null"]},
            },
            "required": ["images", "room_id"],
        },
        output_schema={"type": "object", "description": "ImageRecord dict"},
    )

    def run(
        self, images: ImageLibraryDoc, room_id: str, stage: str | None = None
    ) -> ImageRecord:
        record = images.latest(room_id, stage)
        if record is None:
            label = f"{room_id}/{stage}" if stage else room_id
            raise ToolError(f"生圖片庫沒有 {label} 的影像", tool=self.contract.name)
        return record
