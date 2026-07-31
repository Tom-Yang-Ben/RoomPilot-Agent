from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ApprovalStatus = Literal["draft", "designer_confirmed"]
Confidence = Literal["low", "medium", "high", "contractor_confirmed"]
JobState = Literal[
    "queued",
    "processing",
    "completed",
    "completed_with_warnings",
    "failed",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PointCm(StrictModel):
    x_cm: float
    y_cm: float


class RoomGeometry(StrictModel):
    length_cm: float = Field(gt=0)
    width_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    opening_area_m2: float = Field(default=0, ge=0)
    polygon_cm: list[PointCm] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_polygon(self) -> "RoomGeometry":
        if self.polygon_cm and len(self.polygon_cm) < 3:
            raise ValueError("polygon_cm 至少需要三個點")
        return self


class MaterialSelection(StrictModel):
    material_id: str = Field(min_length=1)
    part: Literal["floor", "wall", "ceiling", "other"]
    name: str = Field(min_length=1)
    description: str | None = None
    waste_rate: float = Field(default=0.05, ge=0, le=1)


class FurniturePlacement(StrictModel):
    furniture_id: str = Field(min_length=1)
    catalog_furniture_id: str | None = None
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    width_cm: float = Field(gt=0)
    depth_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    x_cm: float = 0
    y_cm: float = 0
    rotation_deg: float = 0
    position_reference: Literal["center"] = "center"
    placement_failed: bool = False
    placement_reason: str | None = None
    needs_power: bool = False
    needs_water: bool = False
    needs_drain: bool = False
    asset_url: str | None = None


class EquipmentRequirement(StrictModel):
    equipment_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    source: Literal["questionnaire", "scene_context", "designer"]


class MEPPoint(StrictModel):
    point_id: str = Field(min_length=1)
    system: Literal[
        "power",
        "lighting",
        "data",
        "cold_water",
        "hot_water",
        "drain",
        "hvac",
        "other",
    ]
    purpose: str
    x_cm: float = 0
    y_cm: float = 0
    z_cm: float = 0
    quantity: int = Field(default=1, ge=1)
    professional_status: Literal["pending", "confirmed", "not_applicable"] = "pending"


class RenderReference(StrictModel):
    render_url: str = Field(min_length=1)
    view_name: str = Field(min_length=1)
    render_id: str | None = None
    prompt_hash: str | None = None


class RoomSnapshot(StrictModel):
    room_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    room_type: str = Field(min_length=1)
    style: str | None = None
    geometry: RoomGeometry
    layout_json: dict[str, Any] | None = None
    materials: list[MaterialSelection] = Field(default_factory=list)
    furniture: list[FurniturePlacement] = Field(default_factory=list)
    equipment_requirements: list[EquipmentRequirement] = Field(default_factory=list)
    mep_points: list[MEPPoint] = Field(default_factory=list)
    renders: list[RenderReference] = Field(default_factory=list)


class ProjectSnapshot(StrictModel):
    schema_version: Literal["roompilot.project-snapshot.v1"] = (
        "roompilot.project-snapshot.v1"
    )
    coordinate_unit: Literal["cm"] = "cm"
    project_id: str = Field(min_length=1)
    project_name: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[A-Za-z0-9._-]{1,80}$")
    source_project_revision: int = Field(ge=0)
    approval_status: ApprovalStatus = "draft"
    region: str = Field(default="Taiwan", min_length=1)
    pricing_basis_date: date
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    rooms: list[RoomSnapshot] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "ProjectSnapshot":
        if self.approval_status == "designer_confirmed" and not self.confirmed_by:
            raise ValueError("designer_confirmed 狀態必須有 confirmed_by")
        if self.approval_status == "draft" and (self.confirmed_by or self.confirmed_at):
            raise ValueError("draft 不可帶 confirmed_by 或 confirmed_at")
        room_ids = [room.room_id for room in self.rooms]
        if len(room_ids) != len(set(room_ids)):
            raise ValueError("room_id 不可重複")
        return self


class SnapshotCompleteness(StrictModel):
    score: int = Field(ge=0, le=100)
    complete: bool
    missing: list[str]
    warnings: list[str]


class SnapshotEnvelope(StrictModel):
    snapshot: ProjectSnapshot
    completeness: SnapshotCompleteness


class LockRevisionRequest(StrictModel):
    confirmed_by: str = Field(min_length=1, max_length=200)


class EngineeringPackageRequest(StrictModel):
    revision: str = Field(pattern=r"^[A-Za-z0-9._-]{1,80}$")
    documents: list[Literal["report_json", "report_html", "estimate_xlsx"]] = Field(
        default_factory=lambda: ["report_json", "report_html", "estimate_xlsx"]
    )


class RoomQuantity(StrictModel):
    room_id: str
    length_cm: float
    width_cm: float
    height_cm: float
    floor_area_m2: float
    ceiling_area_m2: float
    perimeter_m: float
    gross_wall_area_m2: float
    opening_area_m2: float
    net_wall_area_m2: float
    geometry_source: Literal["polygon_cm", "rectangle_cm"]


class QuantityResult(StrictModel):
    rooms: list[RoomQuantity]
    total_floor_area_m2: float
    total_ceiling_area_m2: float
    total_net_wall_area_m2: float


class RetrievalEvidence(StrictModel):
    source_id: str
    source_type: str
    score: float = Field(ge=0, le=1)
    confidence: Confidence
    reason: str
    retrieval_modes: list[Literal["structured", "vector"]]


class RetrievedWorkItem(StrictModel):
    room_id: str
    work_item_code: str
    trade: str
    name: str
    unit: str
    quantity_key: str
    quantity: float
    waste_rate: float = Field(default=0, ge=0, le=1)
    description: str
    professional_confirmation_required: bool = False
    evidence: list[RetrievalEvidence] = Field(default_factory=list)


class MEPSuggestion(StrictModel):
    room_id: str
    related_item_id: str
    related_item_name: str
    system: str
    reason: str
    covered_by_existing_point: bool
    source_id: str
    confidence: Confidence


class ConstructionNote(StrictModel):
    room_id: str
    title: str
    content: str
    source_id: str
    confidence: Confidence
    professional_confirmation_required: bool = False


class RoomRetrieval(StrictModel):
    room_id: str
    semantic_query: str
    work_items: list[RetrievedWorkItem]
    mep_suggestions: list[MEPSuggestion]
    construction_notes: list[ConstructionNote]


class RetrieverStatus(StrictModel):
    adapter: str
    mode: Literal["noop", "vector"]
    is_real_vector_retrieval: bool
    message: str


class RetrievalResult(StrictModel):
    rooms: list[RoomRetrieval]
    retrieval_version: str = "advanced-rag-v1"
    structured_retrieval: Literal["active"] = "active"
    semantic_retriever: RetrieverStatus


class RiskItem(StrictModel):
    id: str
    room_id: str | None = None
    rule: str
    rule_source: Literal["ancai_engine", "mvp_advisory", "professional_confirmation"]
    severity: Literal["low", "medium", "high"]
    passed: bool
    message: str
    related_items: list[str] = Field(default_factory=list)
    measured_value: float | None = None
    threshold_value: float | None = None
    unit: str | None = None
    professional_confirmation_required: bool = False


class RiskSummary(StrictModel):
    risk_count: int
    pass_count: int
    status: Literal["passed", "has_risk"]


class RiskResult(StrictModel):
    summary: RiskSummary
    results: list[RiskItem]
    engine_adapter: str


class EstimateLine(StrictModel):
    room_id: str
    work_item_code: str
    trade: str
    name: str
    unit: str
    raw_quantity: float
    waste_rate: float
    pricing_quantity: float
    material_unit_price: float | None
    labor_unit_price: float | None
    other_unit_price: float | None
    subtotal: float | None
    price_record_id: str | None
    price_source: str | None
    price_effective_date: date | None
    price_region: str | None
    status: Literal["priced", "pending_quote"]
    confidence: Confidence


class EstimateResult(StrictModel):
    lines: list[EstimateLine]
    known_subtotal: float
    estimated_total: float | None
    pending_quote_count: int
    currency: Literal["TWD"] = "TWD"
    disclaimer: str


class ScheduleTask(StrictModel):
    task_id: str
    room_id: str
    work_item_code: str
    name: str
    quantity: float
    unit: str
    daily_productivity: float | None
    crew_count: int | None
    preparation_days: float
    construction_days: float | None
    waiting_days: float
    total_days: float | None
    predecessor_task_ids: list[str] = Field(default_factory=list)
    start_day: float | None
    finish_day: float | None
    source: str | None
    confidence: Confidence
    status: Literal["estimated", "productivity_data_missing"]


class ScheduleResult(StrictModel):
    tasks: list[ScheduleTask]
    estimated_total_days: float | None
    unknown_duration_count: int
    disclaimer: str


class NarrativeResult(StrictModel):
    design_summary: str
    construction_summary: str
    cost_summary: str
    schedule_summary: str
    risk_summary: str


class DocumentManifest(StrictModel):
    document_id: str
    document_type: Literal["report_json", "report_html", "estimate_xlsx"]
    file_name: str
    content_type: str
    download_url: str
    byte_size: int = Field(ge=0)


class ReportPayload(StrictModel):
    schema_version: Literal["roompilot.report-payload.v1"] = "roompilot.report-payload.v1"
    package_id: str
    project_id: str
    revision: str
    generated_at: datetime
    status: Literal["completed", "completed_with_warnings"]
    snapshot_hash: str
    demo_mode: bool
    demo_disclaimer: str | None
    snapshot: ProjectSnapshot
    quantities: QuantityResult
    retrieval: RetrievalResult
    risks: RiskResult
    estimate: EstimateResult
    schedule: ScheduleResult
    narratives: NarrativeResult
    assumptions: list[str]
    exclusions: list[str]
    documents: list[DocumentManifest] = Field(default_factory=list)


class JobStatus(StrictModel):
    job_id: str
    project_id: str
    revision: str
    status: JobState
    progress: int = Field(ge=0, le=100)
    stage: str
    package_id: str | None = None
    error_code: str | None = None
    error: str | None = None
    documents: list[DocumentManifest] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def snapshot_completeness(snapshot: ProjectSnapshot) -> SnapshotCompleteness:
    missing: list[str] = []
    warnings: list[str] = []
    if not snapshot.rooms:
        missing.append("rooms")
    for room in snapshot.rooms:
        prefix = f"rooms.{room.room_id}"
        if not room.geometry.polygon_cm:
            warnings.append(f"{prefix}.polygon_cm_missing_using_rectangle")
        if not room.materials:
            missing.append(f"{prefix}.materials")
        if not room.renders:
            warnings.append(f"{prefix}.renders")
        if room.geometry.opening_area_m2 == 0 and room.layout_json:
            warnings.append(f"{prefix}.opening_area_m2_requires_confirmation")
    weighted_total = max(1, len(snapshot.rooms) * 2)
    score = max(0, round(100 * (weighted_total - len(missing)) / weighted_total))
    return SnapshotCompleteness(
        score=score,
        complete=not missing,
        missing=missing,
        warnings=warnings,
    )

