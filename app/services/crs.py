"""CRS parsing, labelling and projection to a metric measurement CRS."""
from __future__ import annotations

from functools import lru_cache

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from app.errors import InvalidFileError
from app.services.utm import select_utm_epsg


def parse_crs(definition: str) -> CRS:
    try:
        return CRS.from_user_input(definition)
    except (CRSError, ValueError, TypeError) as exc:
        raise InvalidFileError(f"Could not interpret the coordinate reference system: {exc}") from exc


def crs_label(crs: CRS) -> str:
    """Short human label, e.g. 'EPSG:4326'; falls back to the CRS name."""
    epsg = crs.to_epsg(min_confidence=70)
    if epsg:
        return f"EPSG:{epsg}"
    authority = crs.to_authority(min_confidence=70)
    if authority:
        return f"{authority[0]}:{authority[1]}"
    return crs.name or "UNKNOWN"


@lru_cache(maxsize=256)
def _to_wgs84(src: CRS) -> Transformer:
    return Transformer.from_crs(src, CRS.from_epsg(4326), always_xy=True)


@lru_cache(maxsize=256)
def _to_measurement_crs(src: CRS, dst_epsg: int) -> Transformer:
    return Transformer.from_crs(src, CRS.from_epsg(dst_epsg), always_xy=True)


def _center_lonlat(geom: BaseGeometry, src: CRS) -> tuple[float, float]:
    minx, miny, maxx, maxy = geom.bounds
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    if src.is_geographic:
        return cx, cy
    lon, lat = _to_wgs84(src).transform(cx, cy)
    return lon, lat


def project_for_measurement(geom: BaseGeometry, src: CRS) -> tuple[BaseGeometry, int]:
    """Reproject ``geom`` (in ``src``) to a metric CRS chosen from its location.

    Always reprojects, even if the source is already projected, because many
    projected CRSs (e.g. Web Mercator, EPSG:3857) badly distort area/length.
    Returns the projected geometry and the EPSG code used.
    """
    if not (src.is_geographic or src.is_projected):
        raise ValueError(f"CRS '{src.name}' is neither geographic nor projected; cannot measure")
    lon, lat = _center_lonlat(geom, src)
    epsg = select_utm_epsg(lon, lat)
    projected = shapely_transform(_to_measurement_crs(src, epsg).transform, geom)
    return projected, epsg
