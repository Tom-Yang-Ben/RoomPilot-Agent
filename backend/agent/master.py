"""Master Agent：程式固定流程的 state machine（非 LLM）。

依架構提案定案，Master 的職責是流程控制而非智慧：

- 主流程：問卷 → S1 需求整理 → S2 RAG 過濾 → S3 挑擺（A/B 兩套）→ S4 驗證
  →（修復迴圈 ≤3）→ 方案擇一＋視角 → S5a 單房色卡生圖 → 色卡擇一
  → S5b 全房生圖 → 意見 → S6 改圖（≤1 次）→ S7 設計手冊（PDF）。
- 人為決策點（HITL）由 ``submit()`` 接收輸入後推進；每次 submit 前自動
  checkpoint，``undo()`` 恢復上一動。
- 計數器全在這裡：修復迴圈上限、改圖一次額度、生圖失敗重試與
  fallback 模型切換（執行在 Gen_Pic Agent，政策數字由本層設定）。
- LLM 只在各 sub-agent 內做語意決策；Master 不呼叫 LLM。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .documents import (
    DocKey,
    DocStore,
    ImageLibraryDoc,
    LayoutDoc,
    LockManifestDoc,
    RequirementDoc,
    RulesDoc,
    SceneDoc,
    ValidationReportDoc,
)
from .subagents import (
    FurnitureAgent,
    GenPicAgent,
    GenPicFailure,
    ReportAgent,
    ValidationAgent,
)
from .tools.base import ToolError
from .tools.read_layout import ReadLayoutTool
from .tools.read_rules import ReadRulesTool


def _is_living_room(room) -> bool:
    """客廳判定：room_type 是權威訊號，中文房名「客廳」為容錯後援。"""
    return room.room_type == "living_room" or "客廳" in (room.name or "")


class MasterState:
    AWAIT_QUESTIONNAIRE = "await_questionnaire"
    AWAIT_PLAN_CHOICE = "await_plan_choice"
    AWAIT_PALETTE_CHOICE = "await_palette_choice"
    AWAIT_FEEDBACK = "await_feedback"
    AWAIT_RENDER_RETRY = "await_render_retry"
    DONE = "done"


@dataclass
class MasterConfig:
    repair_max_rounds: int = 3
    edit_max: int = 1
    output_dir: str = ".tmp/agent_output"
    manual_filename: str = "design_manual.pdf"
    palette_limit: int = 3


@dataclass
class PauseInfo:
    state: str
    message: str
    expects: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class MasterAgent:
    def __init__(
        self,
        furniture: FurnitureAgent,
        validation: ValidationAgent,
        genpic: GenPicAgent,
        report: ReportAgent,
        *,
        store: DocStore | None = None,
        config: MasterConfig | None = None,
    ) -> None:
        self.furniture = furniture
        self.validation = validation
        self.genpic = genpic
        self.report = report
        self.store = store or DocStore()
        self.config = config or MasterConfig()
        self.state = MasterState.AWAIT_QUESTIONNAIRE
        self.edit_used = 0
        self.repair_rounds_used: dict[str, int] = {}
        self._pending_render: dict | None = None
        self._pause = PauseInfo(
            state=self.state, message="請先呼叫 start() 載入室內架構。"
        )
        self._checkpoints: list[dict] = []
        self._read_layout = ReadLayoutTool()
        self._read_rules = ReadRulesTool()

    # ------------------------------------------------------------------ 入口

    @property
    def pause(self) -> PauseInfo:
        return self._pause

    def start(self, layout_json: dict, rules_json: dict | None = None) -> PauseInfo:
        """載入室內架構與規則文件，進入等待問卷狀態。"""
        layout = self._read_layout.run(layout_json)
        self.store.set(DocKey.LAYOUT, layout)
        self.store.set(DocKey.RULES, self._read_rules.run(rules_json))
        self.store.set(DocKey.USER_CHOICES, {"feedback": [], "edit_used": 0})
        self.state = MasterState.AWAIT_QUESTIONNAIRE
        return self._set_pause(
            "室內架構已載入，請提供問卷答案。",
            expects={"questionnaire": "問卷答案物件"},
            payload={"rooms": [asdict(room) for room in layout.rooms]},
        )

    def submit(self, payload: dict) -> PauseInfo:
        """在目前的人為決策點提交輸入並推進流程；每次提交前自動 checkpoint。"""
        payload = payload or {}
        self._push_checkpoint(f"before:{self.state}")
        handlers = {
            MasterState.AWAIT_QUESTIONNAIRE: self._on_questionnaire,
            MasterState.AWAIT_PLAN_CHOICE: self._on_plan_choice,
            MasterState.AWAIT_PALETTE_CHOICE: self._on_palette_choice,
            MasterState.AWAIT_FEEDBACK: self._on_feedback,
            MasterState.AWAIT_RENDER_RETRY: self._on_render_retry,
        }
        handler = handlers.get(self.state)
        if handler is None:
            self._pop_checkpoint_noop()
            return self._set_pause("流程已完成，無可提交的步驟。", expects={})
        try:
            return handler(payload)
        except ValueError as exc:
            # 輸入不合法不算一動：回復 checkpoint，讓使用者重新提交。
            self.undo()
            return self._set_pause(str(exc), expects=self._pause.expects)

    def undo(self) -> PauseInfo | None:
        """可恢復上一動：回復到上一次 submit 之前的完整狀態。"""
        if not self._checkpoints:
            return None
        record = self._checkpoints.pop()
        self.store.undo()
        self.state = record["state"]
        self.edit_used = record["edit_used"]
        self.repair_rounds_used = dict(record["repair_rounds_used"])
        self._pending_render = record["pending_render"]
        self._pause = PauseInfo(**record["pause"])
        return self._pause

    # ------------------------------------------------------------ HITL 處理

    def _on_questionnaire(self, payload: dict) -> PauseInfo:
        questionnaire = payload.get("questionnaire")
        if payload.get("retry") and not questionnaire:
            questionnaire = self.store.get(DocKey.QUESTIONNAIRE)
        if not isinstance(questionnaire, dict):
            raise ValueError("請提供 questionnaire 物件。")
        self.store.set(DocKey.QUESTIONNAIRE, questionnaire)
        layout = self._layout()
        # S1 需求整理
        requirements = self.furniture.organize_requirements(questionnaire, layout)
        self.store.set(DocKey.REQUIREMENTS, requirements)
        # S2 RAG 過濾
        try:
            candidates = self.furniture.retrieve_candidates(requirements, layout)
        except ToolError as exc:
            self.state = MasterState.AWAIT_QUESTIONNAIRE
            return self._set_pause(
                f"候選家具檢索失敗：{exc.reason}。修復後以 retry 重新執行。",
                expects={"retry": "true 以重試", "questionnaire": "（可選）更新問卷"},
            )
        self.store.set(DocKey.CANDIDATES, candidates)
        # S3+S4：A/B 兩套方案，各自帶修復迴圈（上限由 config 控制）
        rules = self._rules()
        summaries = {}
        for variant in ("A", "B"):
            summaries[variant] = self._build_variant(
                variant, requirements, candidates, layout, rules
            )
        self.state = MasterState.AWAIT_PLAN_CHOICE
        return self._set_pause(
            "A/B 兩套擺放方案已完成驗證，請擇一並提供各房視角（可先在 2D/3D 微調）。",
            expects={
                "variant": "A 或 B",
                "viewpoints": "room_id -> {viewpoint_id, note, image_b64}",
                "palette_room_id": "（可選）色卡比對用房間",
                "scene_override": "（可選）使用者微調後的場景",
            },
            payload={"variants": summaries},
        )

    def _on_plan_choice(self, payload: dict) -> PauseInfo:
        variant = str(payload.get("variant", "")).upper()
        if variant not in ("A", "B"):
            raise ValueError("variant 必須是 A 或 B。")
        chosen_key = DocKey.variant(DocKey.SCENE, variant)
        scene_dict = payload.get("scene_override") or self.store.require(chosen_key)
        scene = SceneDoc.from_dict(scene_dict)
        scene.notes = f"採用方案 {variant}" + ("（含使用者微調）" if payload.get("scene_override") else "")
        self.store.set(DocKey.variant(DocKey.SCENE, "chosen"), scene)
        choices = self._choices()
        choices.update(
            {
                "plan_variant": variant,
                "viewpoints": payload.get("viewpoints") or {},
                "palette_room_id": payload.get("palette_room_id")
                or self._default_palette_room(scene),
                "unresolved_validation": any(
                    (self.store.get(DocKey.variant(DocKey.VALIDATION, v)) or {}).get("passed")
                    is False
                    for v in (variant,)
                ),
            }
        )
        self.store.set(DocKey.USER_CHOICES, choices)
        return self._stage_palette()

    def _on_palette_choice(self, payload: dict) -> PauseInfo:
        palette_id = payload.get("palette_id")
        options = {p.palette_id for p in self._requirements().palette_options}
        if options and palette_id not in options:
            raise ValueError(f"palette_id 必須是其中之一：{sorted(options)}")
        choices = self._choices()
        choices["palette_id"] = palette_id
        self.store.set(DocKey.USER_CHOICES, choices)
        return self._stage_full()

    def _on_feedback(self, payload: dict) -> PauseInfo:
        feedback = str(payload.get("feedback") or "").strip()
        if payload.get("skip") or not feedback:
            return self._finalize()
        if self.edit_used >= self.config.edit_max:
            return self._set_pause(
                f"改圖額度已用完（僅限 {self.config.edit_max} 次），"
                "請以 skip 完成流程並輸出設計手冊。",
                expects={"skip": "true 以完成流程"},
            )
        room_id = payload.get("room_id") or self._choices().get("palette_room_id")
        return self._stage_edit(feedback, room_id)

    def _on_render_retry(self, payload: dict) -> PauseInfo:
        pending = self._pending_render or {}
        stage = pending.get("stage")
        if payload.get("retry"):
            self._pending_render = None
            if stage == "palette":
                return self._stage_palette()
            if stage == "full":
                return self._stage_full()
            if stage == "edit":
                return self._stage_edit(pending.get("feedback", ""), pending.get("room_id"))
            raise ValueError("沒有待重試的生圖階段。")
        if payload.get("skip"):
            self._pending_render = None
            return self._skip_stage(stage)
        raise ValueError("請提供 retry 或 skip。")

    # ------------------------------------------------------------ 流程階段

    def _build_variant(
        self,
        variant: str,
        requirements: RequirementDoc,
        candidates,
        layout: LayoutDoc,
        rules: RulesDoc,
    ) -> dict:
        furniture_list, scene = self.furniture.propose(
            requirements, candidates, layout, variant
        )
        report = self.validation.validate(
            requirements, layout, scene, rules, round_index=1
        )
        rounds = 0
        while not report.passed and rounds < self.config.repair_max_rounds:
            rounds += 1
            furniture_list, scene = self.furniture.repair(
                furniture_list, report, scene, candidates, layout
            )
            report = self.validation.validate(
                requirements, layout, scene, rules, round_index=rounds + 1
            )
        self.repair_rounds_used[variant] = rounds
        self.store.set(DocKey.variant(DocKey.FURNITURE_LIST, variant), furniture_list)
        self.store.set(DocKey.variant(DocKey.SCENE, variant), scene)
        self.store.set(DocKey.variant(DocKey.VALIDATION, variant), report)
        placed_total = sum(len(scene.placed_in(r.room_id)) for r in layout.rooms)
        return {
            "strategy": furniture_list.strategy,
            "placed_total": placed_total,
            "failed_total": len(scene.failures()),
            "repair_rounds": rounds,
            "passed": report.passed,
            "summary": report.summary,
            "unresolved": not report.passed,
        }

    def _stage_palette(self) -> PauseInfo:
        requirements = self._requirements()
        palettes = requirements.palette_options[: self.config.palette_limit]
        choices = self._choices()
        if not palettes:
            choices["palette_id"] = None
            self.store.set(DocKey.USER_CHOICES, choices)
            return self._stage_full()
        scene = self._chosen_scene()
        layout = self._layout()
        room = layout.room(choices.get("palette_room_id", "")) or layout.rooms[0]
        viewpoint = (choices.get("viewpoints") or {}).get(room.room_id)
        images = self._images()
        generated = []
        try:
            for palette in palettes:
                record = self.genpic.render_room(
                    requirements,
                    scene,
                    room,
                    images,
                    stage="palette_compare",
                    palette=asdict(palette),
                    viewpoint=viewpoint,
                )
                generated.append(
                    {"image_id": record.image_id, "palette_id": palette.palette_id}
                )
        except GenPicFailure as exc:
            self.store.set(DocKey.IMAGES, images)
            return self._render_failure("palette", exc)
        finally:
            self.store.set(DocKey.IMAGES, images)
        self.state = MasterState.AWAIT_PALETTE_CHOICE
        return self._set_pause(
            f"已完成「{room.name}」×{len(generated)} 組色卡比對圖，請擇一色卡。",
            expects={"palette_id": [p.palette_id for p in palettes]},
            payload={"room_id": room.room_id, "images": generated},
        )

    def _stage_full(self) -> PauseInfo:
        requirements = self._requirements()
        scene = self._chosen_scene()
        layout = self._layout()
        choices = self._choices()
        palette = self._chosen_palette(requirements, choices.get("palette_id"))
        viewpoints = choices.get("viewpoints") or {}
        images = self._images()
        manifests = (self.store.get(DocKey.LOCK_MANIFEST) or {}).get("rooms", {})
        generated = []
        try:
            for room in layout.rooms:
                if not scene.placed_in(room.room_id):
                    continue
                viewpoint = viewpoints.get(room.room_id)
                record = self.genpic.render_room(
                    requirements,
                    scene,
                    room,
                    images,
                    stage="full_render",
                    palette=palette,
                    viewpoint=viewpoint,
                )
                manifest = self.genpic.lock_manifest_for(
                    requirements, scene, room, palette=palette, viewpoint=viewpoint
                )
                manifests[room.room_id] = manifest.to_dict()
                generated.append({"room_id": room.room_id, "image_id": record.image_id})
                # 客廳額外產一張夜間光影圖；設計手冊渲染成果章日光＋夜間並列。
                # 改圖仍鎖日光圖（見 GenPicAgent.edit_room），夜間圖不另出鎖定清單。
                if _is_living_room(room):
                    night = self.genpic.render_room(
                        requirements,
                        scene,
                        room,
                        images,
                        stage="full_render_night",
                        palette=palette,
                        viewpoint=viewpoint,
                        lighting="night",
                    )
                    generated.append(
                        {"room_id": room.room_id, "image_id": night.image_id}
                    )
        except GenPicFailure as exc:
            self.store.set(DocKey.IMAGES, images)
            self.store.set(DocKey.LOCK_MANIFEST, {"rooms": manifests})
            return self._render_failure("full", exc)
        finally:
            self.store.set(DocKey.IMAGES, images)
            self.store.set(DocKey.LOCK_MANIFEST, {"rooms": manifests})
        self.state = MasterState.AWAIT_FEEDBACK
        return self._set_pause(
            "全房生圖完成。可提出一次修改意見（改圖僅限一次），或 skip 直接輸出設計手冊。",
            expects={"feedback": "修改意見（可選）", "room_id": "要修改的房間", "skip": "true 直接完成"},
            payload={"images": generated, "edit_remaining": self.config.edit_max - self.edit_used},
        )

    def _stage_edit(self, feedback: str, room_id: str | None) -> PauseInfo:
        if not room_id:
            raise ValueError("請指定要修改的 room_id。")
        manifests = (self.store.get(DocKey.LOCK_MANIFEST) or {}).get("rooms", {})
        manifest_dict = manifests.get(room_id)
        if not manifest_dict:
            raise ValueError(f"房間 {room_id} 沒有鎖定清單（尚未完成全房生圖）。")
        images = self._images()
        try:
            record = self.genpic.edit_room(
                LockManifestDoc.from_dict(manifest_dict), feedback, images, room_id
            )
        except GenPicFailure as exc:
            self.store.set(DocKey.IMAGES, images)
            return self._render_failure("edit", exc, feedback=feedback, room_id=room_id)
        except ToolError as exc:
            raise ValueError(exc.reason) from exc
        self.store.set(DocKey.IMAGES, images)
        self.edit_used += 1  # 只有成功才消耗額度；失敗重試不扣。
        choices = self._choices()
        choices["edit_used"] = self.edit_used
        choices.setdefault("feedback", []).append(f"{room_id}：{feedback}")
        self.store.set(DocKey.USER_CHOICES, choices)
        self.state = MasterState.AWAIT_FEEDBACK
        return self._set_pause(
            "改圖完成（額度已用完）。請確認後以 skip 完成流程並輸出設計手冊。",
            expects={"skip": "true 以完成流程"},
            payload={
                "images": [{"room_id": room_id, "image_id": record.image_id}],
                "edit_remaining": self.config.edit_max - self.edit_used,
            },
        )

    def _finalize(self) -> PauseInfo:
        out_path = str(Path(self.config.output_dir) / self.config.manual_filename)
        manual = self.report.build_manual(self.store, out_path)
        self.store.set(DocKey.MANUAL, manual)
        self.state = MasterState.DONE
        return self._set_pause(
            "流程完成：設計手冊已輸出。",
            expects={},
            payload={"pdf_path": manual.pdf_path, "sections": [s.heading for s in manual.sections]},
        )

    # ---------------------------------------------------------- 失敗與略過

    def _render_failure(
        self, stage: str, failure: GenPicFailure, **context
    ) -> PauseInfo:
        self._pending_render = {"stage": stage, **context}
        self.state = MasterState.AWAIT_RENDER_RETRY
        stage_names = {"palette": "色卡比對生圖", "full": "全房生圖", "edit": "改圖"}
        return self._set_pause(
            f"{stage_names.get(stage, stage)}失敗（主模型與備援模型皆已重試）。"
            "失敗原因如下，請選擇 retry 重試或 skip 略過。",
            expects={"retry": "true 重試", "skip": "true 略過此階段"},
            payload={"failure_notices": failure.notices, "stage": stage},
        )

    def _skip_stage(self, stage: str | None) -> PauseInfo:
        choices = self._choices()
        if stage == "palette":
            palettes = self._requirements().palette_options
            choices["palette_id"] = palettes[0].palette_id if palettes else None
            choices.setdefault("feedback", []).append(
                "（色卡比對生圖略過，沿用第一組色卡）"
            )
            self.store.set(DocKey.USER_CHOICES, choices)
            return self._stage_full()
        if stage == "full":
            choices.setdefault("feedback", []).append("（全房生圖略過）")
            self.store.set(DocKey.USER_CHOICES, choices)
            self.state = MasterState.AWAIT_FEEDBACK
            return self._set_pause(
                "已略過全房生圖。可 skip 直接輸出設計手冊。",
                expects={"skip": "true 以完成流程"},
                payload={"images": []},
            )
        if stage == "edit":
            self.state = MasterState.AWAIT_FEEDBACK
            return self._set_pause(
                "已略過本次改圖（額度未消耗）。可再次提出意見或 skip 完成流程。",
                expects={"feedback": "修改意見（可選）", "skip": "true 直接完成"},
                payload={"edit_remaining": self.config.edit_max - self.edit_used},
            )
        raise ValueError("沒有可略過的生圖階段。")

    # ------------------------------------------------------------ 內部工具

    def _layout(self) -> LayoutDoc:
        return LayoutDoc.from_dict(self.store.require(DocKey.LAYOUT))

    def _rules(self) -> RulesDoc:
        return RulesDoc.from_dict(self.store.require(DocKey.RULES))

    def _requirements(self) -> RequirementDoc:
        return RequirementDoc.from_dict(self.store.require(DocKey.REQUIREMENTS))

    def _chosen_scene(self) -> SceneDoc:
        return SceneDoc.from_dict(self.store.require(DocKey.variant(DocKey.SCENE, "chosen")))

    def _images(self) -> ImageLibraryDoc:
        return ImageLibraryDoc.from_dict(self.store.get(DocKey.IMAGES) or {})

    def _choices(self) -> dict:
        return dict(self.store.get(DocKey.USER_CHOICES) or {})

    def _default_palette_room(self, scene: SceneDoc) -> str:
        layout = self._layout()
        for room in layout.rooms:
            if scene.placed_in(room.room_id):
                return room.room_id
        return layout.rooms[0].room_id if layout.rooms else ""

    def _chosen_palette(self, requirements: RequirementDoc, palette_id) -> dict | None:
        for palette in requirements.palette_options:
            if palette.palette_id == palette_id:
                return asdict(palette)
        return None

    def _set_pause(self, message: str, *, expects: dict, payload: dict | None = None) -> PauseInfo:
        self._pause = PauseInfo(
            state=self.state, message=message, expects=expects, payload=payload or {}
        )
        return self._pause

    # -- checkpoint（可恢復上一動） --

    def _push_checkpoint(self, label: str) -> None:
        self.store.checkpoint(label)
        self._checkpoints.append(
            {
                "label": label,
                "state": self.state,
                "edit_used": self.edit_used,
                "repair_rounds_used": dict(self.repair_rounds_used),
                "pending_render": (
                    dict(self._pending_render) if self._pending_render else None
                ),
                "pause": self._pause.to_dict(),
            }
        )

    def _pop_checkpoint_noop(self) -> None:
        if self._checkpoints:
            self._checkpoints.pop()
            self.store.undo()

    # -- 序列化（存 project store 用） --

    def to_dict(self) -> dict:
        return {
            "schema_version": "roompilot.agent.master.v1",
            "state": self.state,
            "edit_used": self.edit_used,
            "repair_rounds_used": dict(self.repair_rounds_used),
            "pending_render": dict(self._pending_render) if self._pending_render else None,
            "pause": self._pause.to_dict(),
            "checkpoints": list(self._checkpoints),
            "store": self.store.to_dict(),
        }

    def restore(self, data: dict) -> None:
        self.store = DocStore.from_dict(data.get("store") or {})
        self.state = data.get("state", MasterState.AWAIT_QUESTIONNAIRE)
        self.edit_used = int(data.get("edit_used", 0))
        self.repair_rounds_used = dict(data.get("repair_rounds_used") or {})
        self._pending_render = data.get("pending_render")
        pause = data.get("pause") or {}
        self._pause = PauseInfo(
            state=pause.get("state", self.state),
            message=pause.get("message", ""),
            expects=pause.get("expects") or {},
            payload=pause.get("payload") or {},
        )
        self._checkpoints = list(data.get("checkpoints") or [])
