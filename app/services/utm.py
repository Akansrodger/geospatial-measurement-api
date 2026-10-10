"""Pure helper: choose a projected CRS suited to a lon/lat location."""
from __future__ import annotations


def select_utm_epsg(lon: float, lat: float) -> int:
    """Return the EPSG code of the WGS84 projected CRS best suited to (lon, lat).

    * -80 <= lat <= 84  -> UTM zone (EPSG:326xx north / 327xx south)
    * lat > 84          -> UPS North (EPSG:32661)
    * lat < -80         -> UPS South (EPSG:32761)

    Raises ValueError for coordinates outside valid lon/lat ranges.
    """
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise ValueError(f"Coordinates out of lon/lat range: lon={lon}, lat={lat}")
    if lat > 84.0:
        return 32661
    if lat < -80.0:
        return 32761
    zone = min(int((lon + 180.0) // 6) + 1, 60)
    return (32600 if lat >= 0 else 32700) + zone
