"""Pydantic contracts for LLM parsing and the public RAG search API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RoomType = Literal[
    "living_room",
    "bedroom",
    "entryway",
    "bathroom",
    "kitchen",
    "storage",
    "balcony",
    "hallway",
    "stair",
    "garage",
]
StyleId = Literal[
    "scandinavian", "japanese", "modern_minimal", "cream", "industrial", "american"
]
MoodId = Literal[
    "溫馨", "放鬆", "明亮", "寧靜", "俐落", "率性", "沉穩", "大器",
    "優雅", "浪漫", "質樸", "自然", "精緻", "高級", "復古", "懷舊",
    "活潑", "繽紛", "純粹", "靜謐", "粗獷", "溫潤", "療癒", "都會",
]
CategoryGroup = Literal[
    "sofa", "armchair", "dining_chair", "office_chair", "stool_bench",
    "coffee_table", "side_table", "dining_table", "desk", "bed", "storage",
    "wardrobe", "rug", "lighting", "mirror", "decor", "kids", "media", "partition",
]


class RagQueryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    label_zh: str = Field(min_length=1, max_length=80)
    category_group: CategoryGroup | None
    quantity: int = Field(ge=1, le=8)
    priority: Literal["must_have", "nice_to_have"]
    is_inferred: bool
    semantic_query: str = Field(min_length=1, max_length=500)
    styles: list[StyleId] = Field(max_length=2)
    price_max: int | None = Field(default=None, gt=0)
    max_width_cm: float | None = Field(default=None, gt=0)
    max_height_cm: float | None = Field(default=None, gt=0)
    role: Literal["anchor", "accent"] | None
    size_hint: Literal["S", "M", "L"] | None


class RagQueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_type: RoomType | None
    styles: list[StyleId] = Field(max_length=2)
    moods: list[MoodId] = Field(max_length=3)
    pattern: Literal["素色", "木紋", "幾何", "花紋"] | None
    color_hint: str | None = Field(default=None, max_length=80)
    material_hint: str | None = Field(default=None, max_length=80)
    price_level: Literal["budget", "mid", "premium"] | None
    budget_total: int | None = Field(default=None, gt=0)
    is_set: bool
    items: list[RagQueryItem] = Field(min_length=1, max_length=6)
    confidence: float = Field(ge=0, le=1)
    needs_clarification: bool
    clarify_question: str | None = Field(default=None, max_length=300)
    clarify_options: list[str] = Field(max_length=4)
    reasoning: str = Field(max_length=800)

    @model_validator(mode="after")
    def validate_clarification(self) -> "RagQueryPlan":
        if self.needs_clarification and not self.clarify_question:
            raise ValueError("clarify_question is required when clarification is needed")
        return self


class RagSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=8, ge=1, le=8)
    # Step 5 must not wait for a free external LLM queue. It still uses the
    # same pgvector and reranker pipeline after local intent normalization.
    fast: bool = False
