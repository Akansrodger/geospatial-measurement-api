"""KML parser. Produces GeoJSON-style geometries in EPSG:4326 (the KML standard CRS)."""
from __future__ import annotations

from typing import Any

from lxml import etree

from app.errors import InvalidFileError
from app.models import ParsedFile, RawFeature

KML_CRS = "EPSG:4326"
_SIMPLE = ("Point", "LineString", "LinearRing", "Polygon")


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname


def _text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    value = el.text.strip()
    return value or None


def _parse_coordinates(el: etree._Element | None) -> list[list[float]]:
    text = _text(el.find("{*}coordinates")) if el is not None else None
    if not text:
        raise ValueError("missing <coordinates>")
    coords: list[list[float]] = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            raise ValueError(f"bad coordinate tuple '{token}'")
        values = [float(p) for p in parts[:3] if p != ""]
        if len(values) < 2:
            raise ValueError(f"bad coordinate tuple '{token}'")
        lon, lat = values[0], values[1]
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise ValueError(f"coordinate out of WGS84 range: {lon},{lat}")
        coords.append(values)
    return coords


def _simple_geometry(el: etree._Element) -> dict[str, Any]:
    kind = _local(el)
    if kind == "Point":
        return {"type": "Point", "coordinates": _parse_coordinates(el)[0]}
    if kind in ("LineString", "LinearRing"):
        # A LinearRing is a closed line; measure it as a line (its length is the perimeter).
        return {"type": "LineString", "coordinates": _parse_coordinates(el)}
    if kind == "Polygon":
        outer = el.find("{*}outerBoundaryIs/{*}LinearRing")
        if outer is None:
            raise ValueError("Polygon without outerBoundaryIs")
        rings = [_parse_coordinates(outer)]
        for inner in el.findall("{*}innerBoundaryIs/{*}LinearRing"):
            rings.append(_parse_coordinates(inner))
        return {"type": "Polygon", "coordinates": rings}
    raise ValueError(f"unsupported KML geometry '{kind}'")


def _collect(el: etree._Element) -> list[dict[str, Any]]:
    """Flatten a geometry element (recursing into MultiGeometry) into simple geometries."""
    kind = _local(el)
    if kind == "MultiGeometry":
        out: list[dict[str, Any]] = []
        for child in el:
            if isinstance(child.tag, str) and _local(child) in _SIMPLE + ("MultiGeometry",):
                out.extend(_collect(child))
        return out
    return [_simple_geometry(el)]


def _assemble(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    types = {p["type"] for p in parts}
    if len(types) == 1:
        kind = types.pop()
        return {"type": f"Multi{kind}", "coordinates": [p["coordinates"] for p in parts]}
    return {"type": "GeometryCollection", "geometries": parts}


def _properties(placemark: etree._Element) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for tag in ("name", "description"):
        value = _text(placemark.find(f"{{*}}{tag}"))
        if value is not None:
            props[tag] = value
    for data in placemark.findall("{*}ExtendedData/{*}Data"):
        key = data.get("name")
        if key:
            props[key] = _text(data.find("{*}value"))
    for data in placemark.findall("{*}ExtendedData//{*}SimpleData"):
        key = data.get("name")
        if key:
            props[key] = _text(data)
    return props


def parse_kml(content: bytes) -> ParsedFile:
    # Hardened parser: no entity expansion, no network, no external DTDs.
    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
    )
    try:
        root = etree.fromstring(content, parser)
    except etree.XMLSyntaxError as exc:
        raise InvalidFileError(f"File is not well-formed XML: {exc}") from exc
    if root is None or _local(root) != "kml":
        raise InvalidFileError("File is not a KML document (root element must be <kml>)")

    features: list[RawFeature] = []
    for placemark in root.iter("{*}Placemark"):
        warnings: list[str] = []
        geometry: dict[str, Any] | None = None
        geom_el = next(
            (c for c in placemark if isinstance(c.tag, str)
             and _local(c) in _SIMPLE + ("MultiGeometry",)),
            None,
        )
        if geom_el is None:
            warnings.append("Placemark has no supported geometry")
        else:
            try:
                geometry = _assemble(_collect(geom_el))
            except ValueError as exc:
                warnings.append(f"Could not read geometry: {exc}")
        features.append(
            RawFeature(
                index=len(features),
                geometry=geometry,
                properties=_properties(placemark),
                warnings=warnings,
            )
        )
    return ParsedFile(crs_definition=KML_CRS, features=features)
