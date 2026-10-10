"""Pydantic response models (these also drive the OpenAPI docs)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: str | None = Field(None, description="CRS of the uploaded file, e.g. EPSG:4326")
    status: Literal["COMPLETED", "FAILED"]
    error: str | None = None
    created_at: str
    geometry_type_counts: dict[str, int] = {}


class Measurement(BaseModel):
    status: Literal["MEASURED", "NOT_REQUIRED", "UNSUPPORTED", "EMPTY", "ERROR"]
    area_sq_m: float | None = None
    area_hectares: float | None = None
    length_m: float | None = None
    measurement_crs: str | None = Field(None, description="Projected CRS used for the calculation")
    message: str | None = None
    warnings: list[str] = []


class Feature(BaseModel):
    index: int
    geometry_type: str
    geometry: dict[str, Any] | None
    crs: str
    properties: dict[str, Any]
    measurement: Measurement


class MeasurementItem(BaseModel):
    index: int
    geometry_type: str
    crs: str
    properties: dict[str, Any]
    measurement: Measurement


class MeasurementSummary(BaseModel):
    total_area_sq_m: float
    total_area_hectares: float
    total_length_m: float
    status_counts: dict[str, int]


class MeasurementsResponse(BaseModel):
    file_id: str
    crs: str | None
    total_features: int
    limit: int
    offset: int
    summary: MeasurementSummary
    features: list[MeasurementItem]


class FeaturesResponse(BaseModel):
    file_id: str
    crs: str | None
    total_features: int
    limit: int
    offset: int
    features: list[Feature]
