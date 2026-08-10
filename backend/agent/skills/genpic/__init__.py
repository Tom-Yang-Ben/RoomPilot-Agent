"""生圖 skill：流程層。兩階段流程說明見同資料夾 ``SKILL.md``（無文字 LLM）。"""
from __future__ import annotations

from pathlib import Path

from ...documents import LayoutRoom, RequirementDoc, SceneDoc
from ...llm import LLMGateway
from ...tools.genpic_info import GenPicInfoTool
from ..base import load_skill_doc

DOC = load_skill_doc(Path(__file__).parent)

STAGE_PALETTE = "palette_compare"
STAGE_FULL = "full_render"


class GenPicSkill:
    def __init__(
        self, gateway: LLMGateway | None = None, *, info_tool: GenPicInfoTool | None = None
    ) -> None:
        self._gateway = gateway
        self._info = info_tool or GenPicInfoTool()

    def build_render_request(
        self,
        requirements: RequirementDoc,
        scene: SceneDoc,
        room: LayoutRoom,
        *,
        stage: str,
        palette: dict | None = None,
        viewpoint: dict | None = None,
        lighting: str = "day",
    ) -> dict:
        """回傳 {"prompt", "lock_manifest", "images", "stage"}。"""
        info = self._info.run(
            requirements,
            scene,
            room,
            stage=stage,
            palette=palette,
            viewpoint=viewpoint,
            lighting=lighting,
        )
        images: tuple[str, ...] = ()
        if viewpoint and viewpoint.get("image_b64"):
            images = (str(viewpoint["image_b64"]),)
        return {
            "prompt": info["prompt"],
            "lock_manifest": info["lock_manifest"],
            "images": images,
            "stage": stage,
        }
