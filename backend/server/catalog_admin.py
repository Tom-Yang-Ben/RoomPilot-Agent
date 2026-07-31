"""Protected FastAPI adapter for Phase 2 PostgreSQL furniture writes."""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..catalog.postgres_admin_repository import (
    CatalogAdminActivationError,
    CatalogAdminConflict,
    CatalogAdminError,
    CatalogAdminNotFound,
    CatalogAdminReferenceError,
    catalog_admin_token,
    catalog_admin_writes_enabled,
    create_furniture,
    get_admin_furniture,
    patch_furniture,
    soft_delete_furniture,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
router = APIRouter(prefix="/api/admin/furniture", tags=["catalog-admin"])

PositiveDimension = Annotated[float, Field(gt=0)]
NonNegativePrice = Annotated[int, Field(ge=0)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StyleAssignmentInput(_StrictModel):
    style_code: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    confidence: float | None = Field(default=None, ge=0, le=1)


class AnnotationInput(_StrictModel):
    model_name: str | None = Field(default=None, max_length=100)
    model_version: str | None = Field(default=None, max_length=100)
    prompt_version: str | None = Field(default=None, max_length=100)
    object_type_zh: str | None = None
    description: str | None = None
    role: str | None = Field(default=None, max_length=30)
    visual_weight: str | None = Field(default=None, max_length=30)
    height_zone: str | None = Field(default=None, max_length=30)
    size_class: str | None = Field(default=None, max_length=10)
    pattern: str | None = None
    mood_tags: list[str] = Field(default_factory=list)
    shape_tags: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    rag_text: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    description_source: str | None = Field(default=None, max_length=100)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class FurnitureCreateInput(_StrictModel):
    item_id: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    category_code: str = Field(min_length=1, max_length=100)
    source_group: str | None = Field(default=None, max_length=50)
    catalog: str | None = Field(default=None, max_length=100)
    source_type: str | None = Field(default=None, max_length=100)
    name_en: str = Field(min_length=1)
    name_zh: str | None = None
    primary_color: str | None = None
    colors: list[str] = Field(default_factory=list)
    primary_material: str | None = None
    materials: list[str] = Field(default_factory=list)
    width_cm: PositiveDimension | None = None
    depth_cm: PositiveDimension | None = None
    height_cm: PositiveDimension | None = None
    price_twd: NonNegativePrice | None = None
    price_is_estimated: bool = False
    product_url: str | None = None
    styles: list[StyleAssignmentInput] = Field(default_factory=list, max_length=2)
    room_codes: list[str] = Field(default_factory=list)
    annotation: AnnotationInput | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("colors", "materials", "room_codes")
    @classmethod
    def unique_text_values(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("duplicate_values_not_allowed")
        return cleaned

    @model_validator(mode="after")
    def unique_styles(self) -> "FurnitureCreateInput":
        style_codes = [assignment.style_code for assignment in self.styles]
        if len(style_codes) != len(set(style_codes)):
            raise ValueError("duplicate_style_codes_not_allowed")
        return self


class FurniturePatchInput(_StrictModel):
    expected_updated_at: datetime | None = None
    category_code: str | None = Field(default=None, min_length=1, max_length=100)
    source_group: str | None = Field(default=None, max_length=50)
    catalog: str | None = Field(default=None, max_length=100)
    source_type: str | None = Field(default=None, max_length=100)
    name_en: str | None = Field(default=None, min_length=1)
    name_zh: str | None = None
    primary_color: str | None = None
    colors: list[str] | None = None
    primary_material: str | None = None
    materials: list[str] | None = None
    width_cm: PositiveDimension | None = None
    depth_cm: PositiveDimension | None = None
    height_cm: PositiveDimension | None = None
    price_twd: NonNegativePrice | None = None
    price_is_estimated: bool | None = None
    product_url: str | None = None
    styles: list[StyleAssignmentInput] | None = Field(default=None, max_length=2)
    room_codes: list[str] | None = None
    annotation: AnnotationInput | None = None
    raw_data: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("colors", "materials", "room_codes")
    @classmethod
    def unique_optional_text_values(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("duplicate_values_not_allowed")
        return cleaned

    @model_validator(mode="after")
    def validate_patch(self) -> "FurniturePatchInput":
        mutation_fields = self.__pydantic_fields_set__ - {"expected_updated_at"}
        if not mutation_fields:
            raise ValueError("catalog_patch_empty")
        non_nullable_fields = {"name_en", "colors", "materials", "price_is_estimated", "is_active"}
        invalid_nulls = sorted(
            field_name
            for field_name in mutation_fields & non_nullable_fields
            if getattr(self, field_name) is None
        )
        if invalid_nulls:
            raise ValueError(
                "null_not_allowed_for:" + ",".join(invalid_nulls)
            )
        if "styles" in mutation_fields and self.styles is not None:
            style_codes = [assignment.style_code for assignment in self.styles]
            if len(style_codes) != len(set(style_codes)):
                raise ValueError("duplicate_style_codes_not_allowed")
        if self.expected_updated_at is not None and self.expected_updated_at.tzinfo is None:
            raise ValueError("expected_updated_at_timezone_required")
        return self


def _admin_principal(
    authorization: str | None = Header(default=None),
    actor_header: str | None = Header(default=None, alias="X-RoomPilot-Admin-Actor"),
) -> str:
    if not catalog_admin_writes_enabled(PROJECT_DIR):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "catalog_admin_requires_strict_postgres"},
        )
    configured_token = catalog_admin_token(PROJECT_DIR)
    if not configured_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "catalog_admin_not_configured"},
        )

    scheme, separator, candidate = (authorization or "").partition(" ")
    authenticated = (
        bool(separator)
        and scheme.casefold() == "bearer"
        and bool(candidate)
        and secrets.compare_digest(
            candidate.strip().encode("utf-8"), configured_token.encode("utf-8")
        )
    )
    if not authenticated:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "catalog_admin_unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    actor = (actor_header or "catalog-admin").strip()
    if not actor or len(actor) > 100 or any(ord(character) < 32 for character in actor):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "catalog_admin_actor_invalid"},
        )
    return actor


def _raise_admin_error(exc: Exception) -> None:
    if isinstance(exc, CatalogAdminNotFound):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, CatalogAdminConflict):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(exc, (CatalogAdminReferenceError, CatalogAdminActivationError)):
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, CatalogAdminError):
        http_status = status.HTTP_400_BAD_REQUEST
    else:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "postgres_catalog_write_unavailable",
                "reason": type(exc).__name__,
            },
        ) from exc
    raise HTTPException(
        http_status,
        detail={"code": exc.code, **exc.context},
    ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_catalog_furniture(
    payload: FurnitureCreateInput,
    include_raw_data: bool = Query(default=False),
    actor: str = Depends(_admin_principal),
) -> dict[str, Any]:
    try:
        item = create_furniture(
            PROJECT_DIR,
            payload.model_dump(mode="json"),
            actor=actor,
            include_raw_data=include_raw_data,
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return {"action": "created", "item": item}


@router.get("/{item_id}")
def read_catalog_furniture(
    item_id: str,
    include_raw_data: bool = Query(default=False),
    _actor: str = Depends(_admin_principal),
) -> dict[str, Any]:
    try:
        item = get_admin_furniture(
            PROJECT_DIR,
            item_id,
            include_raw_data=include_raw_data,
        )
    except Exception as exc:
        _raise_admin_error(exc)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "catalog_item_not_found"},
        )
    return {"item": item}


@router.patch("/{item_id}")
def update_catalog_furniture(
    item_id: str,
    payload: FurniturePatchInput,
    include_raw_data: bool = Query(default=False),
    actor: str = Depends(_admin_principal),
) -> dict[str, Any]:
    try:
        item = patch_furniture(
            PROJECT_DIR,
            item_id,
            payload.model_dump(mode="json", exclude_unset=True),
            actor=actor,
            include_raw_data=include_raw_data,
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return {"action": "updated", "item": item}


@router.delete("/{item_id}")
def delete_catalog_furniture(
    item_id: str,
    expected_updated_at: datetime | None = Query(default=None),
    include_raw_data: bool = Query(default=False),
    actor: str = Depends(_admin_principal),
) -> dict[str, Any]:
    if expected_updated_at is not None and expected_updated_at.tzinfo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "expected_updated_at_timezone_required"},
        )
    try:
        item = soft_delete_furniture(
            PROJECT_DIR,
            item_id,
            actor=actor,
            expected_updated_at=expected_updated_at,
            include_raw_data=include_raw_data,
        )
    except Exception as exc:
        _raise_admin_error(exc)
    return {"action": "soft_deleted", "item": item}
