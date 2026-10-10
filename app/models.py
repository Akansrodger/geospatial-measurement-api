"""Plain data containers passed between layers (no framework dependencies)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawFeature:
    """A feature as read from a file, before measurement."""

    index: int
    geometry: dict[str, Any] | None  # GeoJSON-style geometry in the file's own CRS
    properties: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedFile:
    crs_definition: str  # anything pyproj.CRS.from_user_input accepts (e.g. "EPSG:4326" or WKT)
    features: list[RawFeature]


@dataclass
class StoredFeature:
    index: int
    geometry_type: str
    geometry: dict[str, Any] | None
    crs: str
    properties: dict[str, Any]
    measurement: dict[str, Any]


@dataclass
class FileRecord:
    id: str
    filename: str
    status: str  # COMPLETED | FAILED
    crs: str | None
    feature_count: int
    error: str | None
    created_at: str
    geometry_type_counts: dict[str, int] = field(default_factory=dict)
