"""固定資料契約（與 contracts/project_snapshot.schema.json、report_payload.schema.json 對齊）。

UI 欄位改名時只改 Adapter，不改這裡；這裡是工程模組的 SSOT。
"""
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


class RoomGeometry(StrictModel):
    length_m: float = Field(gt=0)
    width_m: float = Field(gt=0)
    height_m: float = Field(gt=0)
    opening_area_m2: float = Field(default=0, ge=0)


class MaterialSelection(StrictModel):
    material_id: str
    part: Literal["floor", "wall", "ceiling", "other"]
    name: str
    description: str | None = None
    waste_rate: float = Field(default=0.05, ge=0, le=1)


class FurniturePlacement(StrictModel):
    furniture_id: str
    name: str
    category: str
    width_cm: float = Field(gt=0)
    depth_cm: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    # x_cm / y_cm 為家具「中心點」在房間座標系（房間外接框左下角為原點）的位置，
    # 與 backend.engine 的 PlacedFurniture 座標約定一致。
    x_cm: float = 0
    y_cm: float = 0
    rotation_deg: float = 0
    needs_power: bool = False
    needs_water: bool = False
    needs_drain: bool = False
    unit_price: float | None = Field(default=None, ge=0)
    asset_url: str | None = None


class MEPPoint(StrictModel):
    point_id: str
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
    render_url: str
    view_name: str
    prompt_hash: str | None = None


class RoomSnapshot(StrictModel):
    room_id: str
    name: str
    room_type: str
    style: str | None = None
    geometry: RoomGeometry
    # 保存既有前端的多邊形／牆門窗資料，供 Rule Adapter 使用；此契約不自行解讀。
    layout_json: dict[str, Any] | None = None
    materials: list[MaterialSelection] = Field(default_factory=list)
    furniture: list[FurniturePlacement] = Field(default_factory=list)
    mep_points: list[MEPPoint] = Field(default_factory=list)
    renders: list[RenderReference] = Field(default_factory=list)


class ProjectSnapshot(StrictModel):
    project_id: str
    revision: str
    approval_status: ApprovalStatus = "draft"
    region: str
    pricing_basis_date: date
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    rooms: list[RoomSnapshot] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "ProjectSnapshot":
        if self.approval_status == "designer_confirmed" and not self.confirmed_by:
            raise ValueError("designer_confirmed 狀態必須有 confirmed_by")
        return self


class LockRevisionRequest(StrictModel):
    confirmed_by: str = Field(min_length=1)


class EngineeringPackageRequest(StrictModel):
    revision: str
    documents: list[
        Literal["report_json", "report_html", "estimate_xlsx"]
    ] = Field(default_factory=lambda: ["report_json", "report_html", "estimate_xlsx"])


class RoomQuantity(StrictModel):
    room_id: str
    floor_area_m2: float
    ceiling_area_m2: float
    perimeter_m: float
    gross_wall_area_m2: float
    opening_area_m2: float
    net_wall_area_m2: float


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
    related_furniture_id: str
    related_furniture_name: str
    system: str
    reason: str
    covered_by_existing_point: bool
    source_id: str
    confidence: Confidence


class RoomRetrieval(StrictModel):
    room_id: str
    semantic_query: str
    work_items: list[RetrievedWorkItem]
    mep_suggestions: list[MEPSuggestion]


class RetrievalResult(StrictModel):
    rooms: list[RoomRetrieval]
    retrieval_version: str = "advanced-rag-v1"


class RiskItem(StrictModel):
    id: str
    room_id: str | None = None
    rule: str
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
    currency: str = "TWD"
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
    document_type: str
    file_name: str
    content_type: str
    download_url: str


class ReportPayload(StrictModel):
    package_id: str
    project_id: str
    revision: str
    generated_at: datetime
    status: Literal["completed", "completed_with_warnings"]
    snapshot_hash: str
    snapshot: ProjectSnapshot
    quantities: QuantityResult
    retrieval: RetrievalResult
    risks: RiskResult
    estimate: EstimateResult
    schedule: ScheduleResult
    narratives: NarrativeResult
    assumptions: list[str]
    documents: list[DocumentManifest] = Field(default_factory=list)


class JobStatus(StrictModel):
    job_id: str
    status: JobState
    progress: int = Field(ge=0, le=100)
    package_id: str | None = None
    error: str | None = None
    documents: list[DocumentManifest] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(StrictModel):
    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
