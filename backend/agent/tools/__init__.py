"""Agent tools：帶輸入/輸出契約的 deterministic 函式。

tool 不呼叫 LLM（語意決策屬於 skills）；幾何一律轉交 backend/engine/，
檢索一律轉交家具 RAG。每個 tool 的 ``contract`` 可直接餵給 function calling。
"""
from .base import ToolContract, ToolError
from .design_knowledge import DesignKnowledgeTool, selection_digest, style_note
from .engine_validate import EngineValidateTool
from .fetch_image import FetchImageTool
from .genpic_info import GenPicInfoTool
from .pick_furniture import PickFurnitureTool
from .place_furniture import PlaceFurnitureTool
from .rag_furniture import RagFurnitureTool, SpatialRagRetriever, build_room_query
from .read_docs import ReadDocsTool
from .read_layout import ReadLayoutTool, to_engine_room
from .read_rules import DEFAULT_SOFT_RULES, ReadRulesTool
from .render_pdf import RenderPdfTool

__all__ = [
    "ToolContract",
    "ToolError",
    "ReadLayoutTool",
    "ReadRulesTool",
    "RagFurnitureTool",
    "SpatialRagRetriever",
    "PickFurnitureTool",
    "PlaceFurnitureTool",
    "DesignKnowledgeTool",
    "EngineValidateTool",
    "GenPicInfoTool",
    "selection_digest",
    "style_note",
    "FetchImageTool",
    "ReadDocsTool",
    "RenderPdfTool",
    "DEFAULT_SOFT_RULES",
    "build_room_query",
    "to_engine_room",
]
