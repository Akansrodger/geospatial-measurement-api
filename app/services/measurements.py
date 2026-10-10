"""Measurement calculation for a single geometry."""
from __future__ import annotations

import logging
import math
from typing import Any, Iterable

import shapely
from pyproj import CRS
from shapely.geometry import shape
from shapely.validation import explain_validity

from app.services.crs import project_for_measurement

logger = logging.getLogger(__name__)

AREA_TYPES = {"Polygon", "MultiPolygon"}
LENGTH_TYPES = {"LineString", "MultiLineString"}
NO_MEASUREMENT_TYPES = {"Point", "MultiPoint"}

# Measurement statuses
MEASURED = "MEASURED"
NOT_REQUIRED = "NOT_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"
EMPTY = "EMPTY"
ERROR = "ERROR"


def _blank(warnings: Iterable[str]) -> dict[str, Any]:
    return {
        "status": None,
        "area_sq_m": None,
        "area_hectares": None,
        "length_m": None,
        "measurement_crs": None,
        "message": None,
        "warnings": list(warnings),
    }


def measure_geometry(
    geometry: dict[str, Any] | None,
    src_crs: CRS,
    warnings: Iterable[str] = (),
) -> dict[str, Any]:
    """Measure a GeoJSON-style geometry. Never raises: problems become a status."""
    result = _blank(warnings)

    if geometry is None:
        result.update(status=EMPTY, message="Feature has no geometry")
        return result

    try:
        geom = shape(geometry)
    except Exception as exc:  # malformed coordinates etc.
        result.update(status=ERROR, message=f"Invalid geometry: {exc}")
        return result

    if geom.is_empty:
        result.update(status=EMPTY, message="Geometry is empty")
        return result

    gtype = geom.geom_type

    if gtype in NO_MEASUREMENT_TYPES:
        result.update(status=NOT_REQUIRED, message="No measurement is defined for points")
        return result

    if gtype not in AREA_TYPES | LENGTH_TYPES:
        result.update(status=UNSUPPORTED, message=f"Measurement is not supported for {gtype}")
        return result

    try:
        geom = shapely.force_2d(geom)  # elevation is irrelevant for planar measurement
        if gtype in AREA_TYPES and not geom.is_valid:
            result["warnings"].append(
                f"Geometry is invalid ({explain_validity(geom)}); area may be unreliable"
            )
        projected, epsg = project_for_measurement(geom, src_crs)
        if not all(math.isfinite(v) for v in projected.bounds):
            raise ValueError("Projection produced non-finite coordinates")

        if gtype in AREA_TYPES:
            area = projected.area
            result["area_sq_m"] = round(area, 3)
            result["area_hectares"] = round(area / 10_000.0, 4)
        else:
            result["length_m"] = round(projected.length, 3)
        result.update(status=MEASURED, measurement_crs=f"EPSG:{epsg}")
    except Exception as exc:
        logger.warning("Measurement failed: %s", exc)
        result.update(status=ERROR, message=f"Measurement failed: {exc}")
    return result
