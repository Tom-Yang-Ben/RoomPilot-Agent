from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


WorkflowStep = Literal[
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
    "layout_2d",
    "white_model_3d",
    "viewpoint",
    "style_render",
    "realistic_3d",
]

RoomType = Literal[
    "living_room",
    "dining_room",
    "bedroom",
    "study",
    "kitchen",
    "bathroom",
    "toilet",
    "entry",
    "corridor",
    "balcony",
    "storage",
    "laundry",
    "other",
]


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=120)
    notes: str = Field(default="", max_length=2_000)


class WorkflowUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    current_step: WorkflowStep | None = None
    workflow: dict[str, Any] = Field(default_factory=dict)


class ProjectFloorplanAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    scale_m: float | None = Field(default=None, gt=0, le=500)
    thickness: float = Field(default=0.18, gt=0, le=2)
    height: float = Field(default=2.7, gt=0, le=10)
    allow_openrouter: bool = False


class RoomLabelConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(min_length=1, max_length=64)
    room_type: RoomType


class FloorplanSegmentConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x1: float
    z1: float
    x2: float
    z2: float


class FloorplanCalibrationReferenceCm(BaseModel):
    """使用者在辨識後牆線上選取的比例參考線，業務契約一律公分。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x1_cm: float
    z1_cm: float
    x2_cm: float
    z2_cm: float


class ProjectSpaceConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    rooms: list[RoomLabelConfirmation] = Field(min_length=1, max_length=100)
    doors: list[FloorplanSegmentConfirmation] = Field(default_factory=list, max_length=200)
    windows: list[FloorplanSegmentConfirmation] = Field(default_factory=list, max_length=200)


class ProjectFloorplanCalibrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    reference_cm: FloorplanCalibrationReferenceCm
    actual_length_cm: float = Field(gt=0, le=50_000)


CustomizationMode = Literal["default", "advanced"]
ConstraintPriority = Literal["high", "medium", "low"]
ConstraintType = Literal[
    "child_safety",
    "senior_accessibility",
    "pet_friendly",
    "accessibility",
    "storage",
    "allergy",
    "moisture_resistance",
    "easy_cleaning",
    "material_preference",
    "furniture_model",
    "other",
]


class OccupantProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adults: int = Field(default=1, ge=0, le=30)
    children: int = Field(default=0, ge=0, le=30)
    elderly: int = Field(default=0, ge=0, le=30)
    pets: int = Field(default=0, ge=0, le=30)

    @model_validator(mode="after")
    def require_resident(self) -> "OccupantProfile":
        if self.adults + self.children + self.elderly < 1:
            raise ValueError("至少需要一位居住者")
        return self


class RoomRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str = Field(min_length=1, max_length=64)
    room_type: RoomType
    uses: list[str] = Field(default_factory=list, max_length=12)
    required_furniture_ids: list[str] = Field(default_factory=list, max_length=20)
    special_materials: list[str] = Field(default_factory=list, max_length=12)
    special_notes: str = Field(default="", max_length=1_000)


class SpecialConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConstraintType
    room_id: str | None = Field(default=None, max_length=64)
    description_zh: str = Field(min_length=1, max_length=500)
    priority: ConstraintPriority = "medium"
    evidence: list[str] = Field(default_factory=list, max_length=5)


class SpecialRequirementsSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["suggested"] = "suggested"
    source: Literal["local_rules", "openrouter"]
    model: str | None = Field(default=None, max_length=200)
    summary_zh: str = Field(min_length=1, max_length=1_000)
    constraints: list[SpecialConstraint] = Field(default_factory=list, max_length=50)
    openrouter: dict[str, Any] = Field(default_factory=dict)


class _ProjectRequirementsBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    occupants: OccupantProfile
    customization_mode: CustomizationMode = "default"
    room_requirements: list[RoomRequirement] = Field(min_length=1, max_length=100)
    special_notes: str = Field(default="", max_length=4_000)


class ProjectRequirementsAnalyzeRequest(_ProjectRequirementsBase):
    expected_revision: int = Field(ge=0)
    allow_openrouter: bool = False


class ProjectRequirementsConfirmationRequest(_ProjectRequirementsBase):
    expected_revision: int = Field(ge=0)
    suggestion: SpecialRequirementsSuggestion


class LayoutFurnitureSizeCm(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    width: float = Field(gt=0, le=5_000)
    depth: float = Field(gt=0, le=5_000)
    height: float = Field(gt=0, le=5_000)


class LayoutPositionCm(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(ge=-50_000, le=50_000)
    z: float = Field(ge=-50_000, le=50_000)


class ProjectLayoutObject(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    instance_id: str = Field(min_length=1, max_length=160)
    furniture_id: str = Field(min_length=1, max_length=160)
    name_zh_raw: str | None = Field(default=None, max_length=512)
    normalized_type: str | None = Field(default=None, max_length=100)
    model_url: str | None = Field(default=None, max_length=500)
    primary_style: str | None = Field(default=None, max_length=100)
    placement_room_id: str = Field(min_length=1, max_length=64)
    user_required: bool = False
    selection_source: Literal["user", "openrouter", "local_rules", "rules", "style_card"] = "local_rules"
    mobility: Literal["movable", "fixed"] = "movable"
    size_cm: LayoutFurnitureSizeCm
    footprint_cm: dict[str, float] | None = None
    position_cm: LayoutPositionCm
    rotation_y_deg: float = Field(ge=-3_600, le=3_600)
    position_locked: bool = False
    placement_failed: bool = False
    placement_reason: str | None = Field(default=None, max_length=500)


class ProjectLayoutAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    allow_openrouter: bool = False


class ProjectLayoutValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    item: ProjectLayoutObject
    others: list[ProjectLayoutObject] = Field(default_factory=list, max_length=100)


class ProjectLayoutConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    user_reviewed: Literal[True]
    proposal_source: Literal["local_rules", "openrouter"]
    openrouter: dict[str, Any] = Field(default_factory=dict)
    scene_objects: list[ProjectLayoutObject] = Field(max_length=100)


class ProjectWhiteModelConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    user_reviewed: Literal[True]
    renderer: Literal["neutral_geometry"]
    visible_instance_ids: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def require_unique_visible_instances(self) -> "ProjectWhiteModelConfirmationRequest":
        if len(set(self.visible_instance_ids)) != len(self.visible_instance_ids):
            raise ValueError("可見家具 ID 不可重複")
        return self


class CameraPointCm(BaseModel):
    """相機座標使用公分；Three.js 公尺換算只留在前端場景邊界。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(ge=-50_000, le=50_000)
    y: float = Field(ge=-50_000, le=50_000)
    z: float = Field(ge=-50_000, le=50_000)


class ProjectViewpointConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    user_reviewed: Literal[True]
    projection: Literal["perspective"] = "perspective"
    position_cm: CameraPointCm
    target_cm: CameraPointCm
    fov_deg: float = Field(gt=10, lt=120)


class ProjectStyleCardApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    card_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")


class ProjectRenderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    provider: Literal["browser_capture"] = "browser_capture"


class ProjectRecord(BaseModel):
    project_id: str
    name: str
    notes: str
    current_step: WorkflowStep
    workflow: dict[str, Any]
    revision: int
    created_at: str
    updated_at: str


class ProjectResponse(BaseModel):
    project: ProjectRecord


class ProjectUploadRecord(BaseModel):
    filename: str
    extension: str
    mime_type: str
    source_url: str


class ProjectUploadResponse(BaseModel):
    project: ProjectRecord
    upload: ProjectUploadRecord


class ProjectFloorplanAnalyzeResponse(BaseModel):
    project: ProjectRecord
    analysis: dict[str, Any]


class ProjectSpaceConfirmationResponse(BaseModel):
    project: ProjectRecord
    confirmation: dict[str, Any]


class ProjectFloorplanCalibrationResponse(BaseModel):
    project: ProjectRecord
    analysis: dict[str, Any]
    calibration: dict[str, Any]


class ProjectRequirementsAnalyzeResponse(BaseModel):
    suggestion: SpecialRequirementsSuggestion


class ProjectRequirementsConfirmationResponse(BaseModel):
    project: ProjectRecord
    requirements: dict[str, Any]


class ProjectLayoutAnalyzeResponse(BaseModel):
    proposal: dict[str, Any]


class ProjectLayoutValidateResponse(BaseModel):
    ok: bool
    reason: str | None = None


class ProjectLayoutConfirmationResponse(BaseModel):
    project: ProjectRecord
    layout: dict[str, Any]


class ProjectWhiteModelConfirmationResponse(BaseModel):
    project: ProjectRecord
    white_model: dict[str, Any]


class ProjectViewpointConfirmationResponse(BaseModel):
    project: ProjectRecord
    viewpoint: dict[str, Any]


class ProjectStyleCardApplyResponse(BaseModel):
    project: ProjectRecord
    style_render: dict[str, Any]


class ProjectRenderResponse(BaseModel):
    project: ProjectRecord
    render: dict[str, Any]


class ProjectRenderListResponse(BaseModel):
    renders: list[dict[str, Any]]
