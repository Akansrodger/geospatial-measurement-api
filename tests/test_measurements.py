import pytest
from pyproj import CRS

from app.services.measurements import measure_geometry

WGS84 = CRS.from_epsg(4326)


def square(lon, lat, size):
    return {"type": "Polygon", "coordinates": [[
        [lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]]}


def test_area_near_equator():
    m = measure_geometry(square(3.0, 0.0, 0.01), WGS84)
    assert m["status"] == "MEASURED"
    assert m["measurement_crs"] == "EPSG:32631"
    assert 1.22e6 < m["area_sq_m"] < 1.24e6      # ~1113 m x ~1106 m
    assert m["area_hectares"] == pytest.approx(m["area_sq_m"] / 1e4, rel=1e-3)


def test_area_at_60_north_not_naive_degrees():
    m = measure_geometry(square(10.0, 60.0, 1.0), WGS84)
    assert m["area_sq_m"] == pytest.approx(6.12e9, rel=0.01)  # true ellipsoidal area; shrinks with cos(lat)


def test_line_length_one_degree_at_equator():
    line = {"type": "LineString", "coordinates": [[0, 0], [1, 0]]}
    m = measure_geometry(line, WGS84)
    assert m["status"] == "MEASURED"
    assert m["length_m"] == pytest.approx(111_319, rel=0.005)


def test_polygon_hole_reduces_area():
    outer = square(3.0, 0.0, 0.01)["coordinates"][0]
    hole = square(3.004, 0.004, 0.002)["coordinates"][0]
    full = measure_geometry({"type": "Polygon", "coordinates": [outer]}, WGS84)["area_sq_m"]
    holed = measure_geometry({"type": "Polygon", "coordinates": [outer, hole]}, WGS84)["area_sq_m"]
    assert holed < full


def test_multipolygon_sums():
    one = square(3.0, 0.0, 0.01)["coordinates"]
    multi = {"type": "MultiPolygon", "coordinates": [one, one]}
    single = measure_geometry({"type": "Polygon", "coordinates": one}, WGS84)["area_sq_m"]
    assert measure_geometry(multi, WGS84)["area_sq_m"] == pytest.approx(2 * single, rel=1e-6)


def test_point_needs_no_measurement():
    m = measure_geometry({"type": "Point", "coordinates": [1, 1]}, WGS84)
    assert m["status"] == "NOT_REQUIRED" and m["area_sq_m"] is None


def test_geometry_collection_is_unsupported_not_crash():
    gc = {"type": "GeometryCollection", "geometries": [{"type": "Point", "coordinates": [1, 1]}]}
    assert measure_geometry(gc, WGS84)["status"] == "UNSUPPORTED"


def test_missing_geometry_is_empty():
    assert measure_geometry(None, WGS84)["status"] == "EMPTY"


def test_malformed_geometry_is_error_not_crash():
    bad = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1]]]}
    assert measure_geometry(bad, WGS84)["status"] == "ERROR"


def test_projected_source_crs_is_handled():
    # Same 0.01 deg square expressed in Web Mercator must give ~same (true) area,
    # NOT the hugely distorted Mercator area.
    from pyproj import Transformer

    t = Transformer.from_crs(4326, 3857, always_xy=True)
    ring = [list(t.transform(x, y)) for x, y in square(10.0, 60.0, 0.1)["coordinates"][0]]
    m_merc = measure_geometry({"type": "Polygon", "coordinates": [ring]}, CRS.from_epsg(3857))
    m_geo = measure_geometry(square(10.0, 60.0, 0.1), WGS84)
    assert m_merc["area_sq_m"] == pytest.approx(m_geo["area_sq_m"], rel=0.001)
