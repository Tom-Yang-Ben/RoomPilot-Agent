"""改圖 skill：流程層。提示詞與 schema 見同資料夾 ``SKILL.md``。"""
from __future__ import annotations

from pathlib import Path

from ...documents import LockManifestDoc
from ...llm import LLMGateway
from ...tools.genpic_info import GenPicInfoTool
from ..base import ask_llm_json, load_skill_doc

DOC = load_skill_doc(Path(__file__).parent)
REFINE_SPEC = DOC.spec("refine")

STAGE_EDIT = "edit"


class EditPicSkill:
    def __init__(self, gateway: LLMGateway | None = None) -> None:
        self._gateway = gateway

    def build_edit_request(
        self,
        lock_manifest: LockManifestDoc,
        feedback: str,
        old_image_b64: str,
    ) -> dict:
        """回傳 {"prompt", "images", "stage"}；images 只含要被編輯的舊圖。"""
        instruction = feedback.strip()
        llm_out = ask_llm_json(
            self._gateway,
            REFINE_SPEC,
            f"使用者意見：{feedback}",
            required=("instruction",),
        )
        if llm_out is not None and str(llm_out.get("instruction", "")).strip():
            instruction = str(llm_out["instruction"]).strip()
        manifest = LockManifestDoc.from_dict(lock_manifest.to_dict())
        manifest.allowed_change = instruction
        prompt = GenPicInfoTool.edit_instruction(manifest, instruction)
        return {
            "prompt": prompt,
            "images": (old_image_b64,),
            "stage": STAGE_EDIT,
            "instruction": instruction,
        }
