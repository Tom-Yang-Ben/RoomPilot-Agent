"""Docs 層（blackboard）：agent 流程共享文件的資料契約與文件庫。

對應架構提案的 Docs 層。每份文件都有 ``schema_version``，並以「可直接存進
PostgreSQL project store JSONB」為原則：``DocStore`` 內一律保存 plain dict，
dataclass 只是建構與讀取時的型別化外殼（``to_dict()`` / ``from_dict()``）。

邊界提醒：

- 座標與長度一律公分；場景 placed 條目沿用 ``backend.engine.schema.placed_to_dict``
  的欄位，並由擺家具 tool 附加 ``coordinate_unit: "cm"`` 標記。
- 家電（appliances）只作為問卷與生圖 context，永遠不得混入家具清單或場景。
- 文件內不記錄任何由 LLM 發明的座標；座標只能來自 engine 的結果。
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_PREFIX = "roompilot.agent"


def _rebuild(cls, rows: list[dict] | None) -> list:
    return [cls(**row) for row in (rows or [])]


# ---------- 需求文件（需求整理 skill 產出） ----------


@dataclass
class RequirementItem:
    """單一需求條目；``category`` 對應 RAG 的 category_group（可為 None）。"""

    req_id: str
    text: str
    room_id: str | None = None
    category: str | None = None
    quantity: int = 1
    source: str = "questionnaire"


@dataclass
class PaletteOption:
    palette_id: str
    name: str
    colors: list[str] = field(default_factory=list)


@dataclass
class RequirementDoc:
    """三分流需求：硬約束 / 軟偏好 / 家電（家電只給生圖）。"""

    hard: list[RequirementItem] = field(default_factory=list)
    soft: list[RequirementItem] = field(default_factory=list)
    appliances: list[RequirementItem] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    palette_options: list[PaletteOption] = field(default_factory=list)
    budget_total: int | None = None
    materials: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    raw_answers: dict[str, Any] = field(default_factory=dict)
    schema_version: str = f"{SCHEMA_PREFIX}.requirements.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RequirementDoc":
        return cls(
            hard=_rebuild(RequirementItem, d.get("hard")),
            soft=_rebuild(RequirementItem, d.get("soft")),
            appliances=_rebuild(RequirementItem, d.get("appliances")),
            styles=list(d.get("styles") or []),
            palette_options=_rebuild(PaletteOption, d.get("palette_options")),
            budget_total=d.get("budget_total"),
            materials=dict(d.get("materials") or {}),
            notes=d.get("notes", ""),
            raw_answers=dict(d.get("raw_answers") or {}),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.requirements.v1"),
        )

    def must_have(self, room_id: str | None = None) -> list[RequirementItem]:
        """回傳需要對應到實體家具的硬需求（有 category 者）。"""
        return [
            item
            for item in self.hard
            if item.category and (room_id is None or item.room_id == room_id)
        ]


# ---------- 室內架構文件（讀室內架構 tool 產出） ----------


@dataclass
class LayoutRoom:
    room_id: str
    name: str
    width_cm: float
    depth_cm: float
    walls: list[dict] = field(default_factory=list)


@dataclass
class LayoutDoc:
    rooms: list[LayoutRoom] = field(default_factory=list)
    source: str = "layout_json"
    schema_version: str = f"{SCHEMA_PREFIX}.layout.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LayoutDoc":
        return cls(
            rooms=_rebuild(LayoutRoom, d.get("rooms")),
            source=d.get("source", "layout_json"),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.layout.v1"),
        )

    def room(self, room_id: str) -> LayoutRoom | None:
        for room in self.rooms:
            if room.room_id == room_id:
                return room
        return None


# ---------- 規則文件（硬規則歸 engine，軟潛規則供 agent 參考） ----------


@dataclass
class SoftRule:
    rule_id: str
    description: str
    applies_to: list[str] = field(default_factory=list)  # category 或 room 標籤
    severity: str = "warning"  # 軟規則違反僅警告，不阻擋


@dataclass
class RulesDoc:
    soft_rules: list[SoftRule] = field(default_factory=list)
    hard_note: str = "碰撞、淨空、超界等幾何合法性只由 backend/engine/ 判定。"
    schema_version: str = f"{SCHEMA_PREFIX}.rules.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RulesDoc":
        return cls(
            soft_rules=_rebuild(SoftRule, d.get("soft_rules")),
            hard_note=d.get("hard_note", ""),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.rules.v1"),
        )


# ---------- 候選家具清單（RAG 家具 tool 產出） ----------


@dataclass
class CandidateItem:
    catalog_id: str
    name: str
    category: str
    width_cm: float
    depth_cm: float
    height_cm: float = 80.0
    style: str | None = None
    price: float | None = None
    score: float = 0.0
    reason: str = ""
    clearance: dict | None = None  # {"side": "front", "depth_cm": 60.0}
    image_url: str | None = None
    # 型錄／RAG 的 VLM 外觀描述（顏色、材質、腿型、線條）；只餵生圖提示詞，
    # 不參與選件排序，更不參與幾何。
    description: str = ""
    material: str = ""


@dataclass
class CandidateListDoc:
    by_room: dict[str, list[CandidateItem]] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)  # room_id -> provider/query
    schema_version: str = f"{SCHEMA_PREFIX}.candidates.v1"

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "by_room": {
                room_id: [asdict(item) for item in items]
                for room_id, items in self.by_room.items()
            },
            "retrieval": self.retrieval,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateListDoc":
        return cls(
            by_room={
                room_id: _rebuild(CandidateItem, rows)
                for room_id, rows in (d.get("by_room") or {}).items()
            },
            retrieval=dict(d.get("retrieval") or {}),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.candidates.v1"),
        )


# ---------- 家具清單（挑家具產出；含語意擺位意圖，不含座標） ----------


@dataclass
class PlacementHint:
    """語意擺位意圖。座標永遠由 engine 計算，這裡只描述方法與關係。"""

    method: str = "free"  # free | adjacent | overlay
    anchor_item_id: str | None = None
    note: str = ""


@dataclass
class ChosenItem:
    item_id: str
    catalog_id: str
    room_id: str
    name: str
    category: str
    width_cm: float
    depth_cm: float
    height_cm: float = 80.0
    style: str | None = None
    price: float | None = None
    matched_requirements: list[str] = field(default_factory=list)
    hint: PlacementHint = field(default_factory=PlacementHint)
    clearance: dict | None = None
    reason: str = ""
    description: str = ""  # 型錄／RAG 外觀描述，隨場景條目帶到生圖提示詞
    material: str = ""


@dataclass
class FurnitureListDoc:
    variant: str = "A"
    strategy: str = ""
    items: list[ChosenItem] = field(default_factory=list)
    schema_version: str = f"{SCHEMA_PREFIX}.furniture_list.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FurnitureListDoc":
        items = []
        for row in d.get("items") or []:
            row = dict(row)
            hint = row.pop("hint", None) or {}
            items.append(ChosenItem(hint=PlacementHint(**hint), **row))
        return cls(
            variant=d.get("variant", "A"),
            strategy=d.get("strategy", ""),
            items=items,
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.furniture_list.v1"),
        )

    def in_room(self, room_id: str) -> list[ChosenItem]:
        return [item for item in self.items if item.room_id == room_id]


# ---------- 場景配置文件（擺家具產出；placed 條目來自 engine） ----------


@dataclass
class SceneDoc:
    variant: str = "A"
    strategy: str = ""
    rooms: dict[str, dict] = field(default_factory=dict)
    # rooms[room_id] = {"placed": [engine placed dict＋agent 附加欄位...],
    #                   "failed": [{"id","reason"}...]}；長度/座標一律公分。
    notes: str = ""
    schema_version: str = f"{SCHEMA_PREFIX}.scene.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SceneDoc":
        return cls(
            variant=d.get("variant", "A"),
            strategy=d.get("strategy", ""),
            rooms=copy.deepcopy(d.get("rooms") or {}),
            notes=d.get("notes", ""),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.scene.v1"),
        )

    def placed_in(self, room_id: str) -> list[dict]:
        return list((self.rooms.get(room_id) or {}).get("placed") or [])

    def failures(self) -> list[dict]:
        out: list[dict] = []
        for room_id, data in self.rooms.items():
            for row in data.get("failed") or []:
                out.append({"room_id": room_id, **row})
        return out


# ---------- 驗證報告（Validation Agent 產出） ----------


@dataclass
class HardViolation:
    room_id: str
    item_id: str
    reason: str
    source: str = "engine"


@dataclass
class SoftWarning:
    room_id: str
    rule_id: str
    message: str


@dataclass
class RequirementGap:
    req_id: str
    message: str


@dataclass
class RepairSuggestion:
    room_id: str
    item_id: str
    action: str  # swap_smaller | remove | reorder | move
    detail: str = ""


@dataclass
class ValidationReportDoc:
    variant: str = "A"
    round_index: int = 1
    hard_violations: list[HardViolation] = field(default_factory=list)
    soft_warnings: list[SoftWarning] = field(default_factory=list)
    requirement_gaps: list[RequirementGap] = field(default_factory=list)
    suggestions: list[RepairSuggestion] = field(default_factory=list)
    summary: str = ""
    schema_version: str = f"{SCHEMA_PREFIX}.validation.v1"

    @property
    def passed(self) -> bool:
        """軟規則警告不阻擋；硬違規與硬需求缺口才算未通過。"""
        return not self.hard_violations and not self.requirement_gaps

    def to_dict(self) -> dict:
        data = asdict(self)
        data["passed"] = self.passed
        return data

    @classmethod
    def from_dict(cls, d: dict) -> "ValidationReportDoc":
        return cls(
            variant=d.get("variant", "A"),
            round_index=int(d.get("round_index", 1)),
            hard_violations=_rebuild(HardViolation, d.get("hard_violations")),
            soft_warnings=_rebuild(SoftWarning, d.get("soft_warnings")),
            requirement_gaps=_rebuild(RequirementGap, d.get("requirement_gaps")),
            suggestions=_rebuild(RepairSuggestion, d.get("suggestions")),
            summary=d.get("summary", ""),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.validation.v1"),
        )


# ---------- 鎖定清單（改圖時明列不可變動元素） ----------


@dataclass
class LockManifestDoc:
    room_id: str = ""
    palette_id: str | None = None
    viewpoint_id: str | None = None
    locked_furniture: list[str] = field(default_factory=list)
    locked_materials: dict[str, Any] = field(default_factory=dict)
    allowed_change: str = ""
    schema_version: str = f"{SCHEMA_PREFIX}.lock_manifest.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LockManifestDoc":
        d = dict(d)
        d.setdefault("schema_version", f"{SCHEMA_PREFIX}.lock_manifest.v1")
        return cls(**d)


# ---------- 生圖片庫（生圖 / 改圖 skill 產出；拿舊圖 tool 讀取） ----------


@dataclass
class ImageRecord:
    image_id: str
    room_id: str
    stage: str  # palette_compare | full_render | edit
    model: str = ""
    palette_id: str | None = None
    viewpoint_id: str | None = None
    prompt: str = ""
    image_ref: str = ""  # base64 或檔案路徑；由呼叫端決定保存策略
    notices: list[str] = field(default_factory=list)
    seq: int = 0


@dataclass
class ImageLibraryDoc:
    records: list[ImageRecord] = field(default_factory=list)
    schema_version: str = f"{SCHEMA_PREFIX}.images.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ImageLibraryDoc":
        return cls(
            records=_rebuild(ImageRecord, d.get("records")),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.images.v1"),
        )

    def next_seq(self) -> int:
        return 1 + max((record.seq for record in self.records), default=0)

    def latest(self, room_id: str, stage: str | None = None) -> ImageRecord | None:
        rows = [
            record
            for record in self.records
            if record.room_id == room_id and (stage is None or record.stage == stage)
        ]
        return max(rows, key=lambda record: record.seq, default=None)


# ---------- 設計手冊（Report Agent 產出；PDF 交付） ----------


@dataclass
class ManualSection:
    heading: str
    body: str
    image_ids: list[str] = field(default_factory=list)


@dataclass
class DesignManualDoc:
    title: str = "RoomPilot 設計手冊"
    sections: list[ManualSection] = field(default_factory=list)
    pdf_path: str = ""
    schema_version: str = f"{SCHEMA_PREFIX}.manual.v1"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DesignManualDoc":
        return cls(
            title=d.get("title", "RoomPilot 設計手冊"),
            sections=_rebuild(ManualSection, d.get("sections")),
            pdf_path=d.get("pdf_path", ""),
            schema_version=d.get("schema_version", f"{SCHEMA_PREFIX}.manual.v1"),
        )


# ---------- DocStore：共享文件庫與 checkpoint ----------


class DocKey:
    """DocStore 的固定鍵。場景與家具清單以 ``:A`` / ``:B`` 帶變體。"""

    QUESTIONNAIRE = "questionnaire"
    REQUIREMENTS = "requirements"
    LAYOUT = "layout"
    RULES = "rules"
    CANDIDATES = "candidates"
    FURNITURE_LIST = "furniture_list"  # furniture_list:A / furniture_list:B
    SCENE = "scene"  # scene:A / scene:B / scene:chosen
    VALIDATION = "validation"  # validation:A / validation:B
    LOCK_MANIFEST = "lock_manifest"
    IMAGES = "images"
    MANUAL = "manual"
    USER_CHOICES = "user_choices"  # 方案/色卡/視角/意見等人為決策歷程

    @staticmethod
    def variant(base: str, variant: str) -> str:
        return f"{base}:{variant}"


class DocStore:
    """共享文件庫。內部一律存 plain dict，checkpoint 用 deepcopy。"""

    def __init__(self, docs: dict[str, dict] | None = None) -> None:
        self._docs: dict[str, dict] = copy.deepcopy(docs) if docs else {}
        self._checkpoints: list[tuple[str, dict[str, dict]]] = []

    def set(self, key: str, doc: Any) -> None:
        self._docs[key] = doc.to_dict() if hasattr(doc, "to_dict") else copy.deepcopy(doc)

    def get(self, key: str) -> dict | None:
        return self._docs.get(key)

    def require(self, key: str) -> dict:
        doc = self._docs.get(key)
        if doc is None:
            raise KeyError(f"DocStore 缺少必要文件：{key}")
        return doc

    def delete(self, key: str) -> None:
        self._docs.pop(key, None)

    def keys(self) -> list[str]:
        return sorted(self._docs)

    def snapshot(self) -> dict[str, dict]:
        return copy.deepcopy(self._docs)

    # -- checkpoint / 可恢復上一動 --

    def checkpoint(self, label: str) -> None:
        self._checkpoints.append((label, self.snapshot()))

    def checkpoint_labels(self) -> list[str]:
        return [label for label, _ in self._checkpoints]

    def undo(self) -> str | None:
        """回復到最近一個 checkpoint 的內容，回傳該 checkpoint 標籤。"""
        if not self._checkpoints:
            return None
        label, snap = self._checkpoints.pop()
        self._docs = snap
        return label

    # -- 序列化（給 project store 保存） --

    def to_dict(self) -> dict:
        return {
            "schema_version": f"{SCHEMA_PREFIX}.docstore.v1",
            "docs": self.snapshot(),
            "checkpoints": [
                {"label": label, "docs": copy.deepcopy(snap)}
                for label, snap in self._checkpoints
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DocStore":
        store = cls(d.get("docs") or {})
        store._checkpoints = [
            (row.get("label", ""), copy.deepcopy(row.get("docs") or {}))
            for row in d.get("checkpoints") or []
        ]
        return store
