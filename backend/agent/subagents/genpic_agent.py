"""Gen_Pic Agent：兩階段生圖與一次改圖（任務 5–6），含失敗政策執行。

失敗政策（定案，計數與切換由程式強制、不交給 LLM）：

- 單一請求對主模型（nano banana）最多嘗試 3 次；
- 達上限即記錄「提示使用者的失敗原因」，改用 fallback 模型
  （nano banana 2）再試最多 3 次；
- fallback 也失敗時丟出 ``GenPicFailure``，由 Master 暫停並把原因交給使用者；
- 失敗重試不消耗「改圖僅一次」的額度（額度由 Master 計數）。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..documents import (
    ImageLibraryDoc,
    ImageRecord,
    LayoutRoom,
    LockManifestDoc,
    RequirementDoc,
    SceneDoc,
)
from ..llm import DEFAULT_IMAGE_FALLBACK_MODEL, DEFAULT_IMAGE_MODEL, LLMError, LLMGateway
from ..skills.editpic import EditPicSkill
from ..skills.genpic import GenPicSkill
from ..tools.fetch_image import FetchImageTool


@dataclass(frozen=True)
class ImagePolicy:
    max_attempts_per_model: int = 3


class GenPicFailure(RuntimeError):
    """主模型與 fallback 模型都失敗；``notices`` 是給使用者看的原因清單。"""

    def __init__(self, notices: list[str]) -> None:
        super().__init__("；".join(notices) or "生圖失敗")
        self.notices = list(notices)


class GenPicAgent:
    name = "Gen_Pic Agent"
    skills = ("生圖", "改圖")
    tools = ("genpic_info", "fetch_image")

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        *,
        policy: ImagePolicy | None = None,
    ) -> None:
        self._gateway = gateway
        self._policy = policy or ImagePolicy()
        self._genpic = GenPicSkill(gateway)
        self._editpic = EditPicSkill(gateway)
        self._fetch = FetchImageTool()

    # -- 任務 5：生圖（palette_compare / full_render 共用） --

    def render_room(
        self,
        requirements: RequirementDoc,
        scene: SceneDoc,
        room: LayoutRoom,
        images: ImageLibraryDoc,
        *,
        stage: str,
        palette: dict | None = None,
        viewpoint: dict | None = None,
        lighting: str = "day",
    ) -> ImageRecord:
        request = self._genpic.build_render_request(
            requirements,
            scene,
            room,
            stage=stage,
            palette=palette,
            viewpoint=viewpoint,
            lighting=lighting,
        )
        record = self._generate_with_policy(
            prompt=request["prompt"],
            input_images=request["images"],
            images=images,
            room_id=room.room_id,
            stage=stage,
            palette_id=(palette or {}).get("palette_id"),
            viewpoint_id=(viewpoint or {}).get("viewpoint_id"),
        )
        return record

    def lock_manifest_for(
        self,
        requirements: RequirementDoc,
        scene: SceneDoc,
        room: LayoutRoom,
        *,
        palette: dict | None = None,
        viewpoint: dict | None = None,
    ) -> LockManifestDoc:
        request = self._genpic.build_render_request(
            requirements, scene, room, stage="full_render", palette=palette, viewpoint=viewpoint
        )
        return LockManifestDoc.from_dict(request["lock_manifest"])

    # -- 任務 6：改圖（額度由 Master 計數；這裡只執行一次編輯請求） --

    def edit_room(
        self,
        lock_manifest: LockManifestDoc,
        feedback: str,
        images: ImageLibraryDoc,
        room_id: str,
    ) -> ImageRecord:
        # 改圖鎖定日光全房圖：客廳另有夜間圖 seq 較高，不指定 stage 會誤抓夜間圖。
        old = self._fetch.run(images, room_id, "full_render")
        request = self._editpic.build_edit_request(lock_manifest, feedback, old.image_ref)
        record = self._generate_with_policy(
            prompt=request["prompt"],
            input_images=request["images"],
            images=images,
            room_id=room_id,
            stage="edit",
            palette_id=old.palette_id,
            viewpoint_id=old.viewpoint_id,
        )
        record.notices.append(f"依使用者意見修改：{request['instruction']}")
        return record

    # -- 失敗政策（程式強制） --

    def _models(self) -> list[str]:
        primary = getattr(self._gateway, "image_model", "") or DEFAULT_IMAGE_MODEL
        fallback = (
            getattr(self._gateway, "image_fallback_model", "")
            or DEFAULT_IMAGE_FALLBACK_MODEL
        )
        models = [primary]
        if fallback and fallback != primary:
            models.append(fallback)
        return models

    def _generate_with_policy(
        self,
        *,
        prompt: str,
        input_images: tuple[str, ...],
        images: ImageLibraryDoc,
        room_id: str,
        stage: str,
        palette_id: str | None,
        viewpoint_id: str | None,
    ) -> ImageRecord:
        if self._gateway is None or not getattr(self._gateway, "available", True):
            raise GenPicFailure(
                ["生圖需要 OPENROUTER_API_KEY（OpenRouter gateway 未設定），無法產生影像。"]
            )
        notices: list[str] = []
        models = self._models()
        for model_index, model in enumerate(models):
            for attempt in range(1, self._policy.max_attempts_per_model + 1):
                try:
                    result = self._gateway.generate_image(
                        prompt, images=input_images, model=model
                    )
                except LLMError as exc:
                    notices.append(f"{model} 第 {attempt} 次失敗：{exc.reason}")
                    continue
                seq = images.next_seq()
                record = ImageRecord(
                    image_id=f"img_{room_id}_{stage}_{seq}",
                    room_id=room_id,
                    stage=stage,
                    model=result.model,
                    palette_id=palette_id,
                    viewpoint_id=viewpoint_id,
                    prompt=prompt,
                    image_ref=result.image_b64,
                    notices=notices.copy(),
                    seq=seq,
                )
                images.records.append(record)
                return record
            if model_index == 0 and len(models) > 1:
                notices.append(
                    f"主模型 {model} 已達 {self._policy.max_attempts_per_model} 次失敗上限，"
                    f"改用備援模型 {models[1]} 重試。"
                )
        raise GenPicFailure(notices)
