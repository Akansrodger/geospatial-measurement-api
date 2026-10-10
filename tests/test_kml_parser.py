import pytest

from app.errors import InvalidFileError
from app.services.parsers.kml import parse_kml


def test_parses_sample(kml_bytes):
    parsed = parse_kml(kml_bytes)
    assert parsed.crs_definition == "EPSG:4326"
    types = [f.geometry["type"] if f.geometry else None for f in parsed.features]
    assert types == ["Polygon", "LineString", "Point", "Polygon", "GeometryCollection"]
    assert [f.index for f in parsed.features] == [0, 1, 2, 3, 4]


def test_polygon_hole_and_properties(kml_bytes):
    f = parse_kml(kml_bytes).features[0]
    assert len(f.geometry["coordinates"]) == 2  # outer + 1 hole
    assert f.properties["name"].startswith("Plot A")
    assert f.properties["owner"] == "Survey Dept"


def test_multigeometry_homogeneous_becomes_multi():
    kml = b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><MultiGeometry>
      <Point><coordinates>1,1</coordinates></Point><Point><coordinates>2,2</coordinates></Point>
    </MultiGeometry></Placemark></kml>"""
    assert parse_kml(kml).features[0].geometry["type"] == "MultiPoint"


def test_bad_coordinates_become_warning_not_crash():
    kml = b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark>
      <Point><coordinates>999,999</coordinates></Point></Placemark></kml>"""
    f = parse_kml(kml).features[0]
    assert f.geometry is None and f.warnings


def test_placemark_without_geometry():
    kml = b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>x</name></Placemark></kml>'
    f = parse_kml(kml).features[0]
    assert f.geometry is None and f.properties == {"name": "x"}


def test_not_xml():
    with pytest.raises(InvalidFileError):
        parse_kml(b"this is not xml")


def test_not_kml_root():
    with pytest.raises(InvalidFileError):
        parse_kml(b"<html></html>")


def test_xxe_entities_are_not_resolved():
    kml = b"""<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY x SYSTEM "file:///etc/passwd">]>
    <kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>&x;</name></Placemark></kml>"""
    parsed = parse_kml(kml)
    assert "root:" not in str(parsed.features[0].properties)
