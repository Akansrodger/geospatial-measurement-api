import pytest

from tests.conftest import make_shapefile_zip


def upload(client, name, data, **form):
    return client.post("/api/files/", files={"file": (name, data)}, data=form)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_kml_end_to_end(client, kml_bytes):
    r = upload(client, "survey.kml", kml_bytes)
    assert r.status_code == 201
    info = r.json()
    assert info["status"] == "COMPLETED"
    assert info["feature_count"] == 5
    assert info["crs"] == "EPSG:4326"
    assert info["filename"] == "survey.kml"

    got = client.get(f"/api/files/{info['id']}/").json()
    assert got["id"] == info["id"]
    assert got["geometry_type_counts"]["Polygon"] == 2

    m = client.get(f"/api/files/{info['id']}/measurements/").json()
    assert m["total_features"] == 5
    by_index = {f["index"]: f for f in m["features"]}
    assert by_index[0]["measurement"]["status"] == "MEASURED"
    assert by_index[0]["measurement"]["area_sq_m"] > 0
    assert by_index[1]["measurement"]["length_m"] == pytest.approx(111_319, rel=0.005)
    assert by_index[2]["measurement"]["status"] == "NOT_REQUIRED"
    assert by_index[4]["measurement"]["status"] == "UNSUPPORTED"
    assert m["summary"]["total_area_sq_m"] > 0
    assert m["summary"]["status_counts"]["MEASURED"] == 3


def test_features_endpoint_returns_geometry_and_crs(client, kml_bytes):
    fid = upload(client, "s.kml", kml_bytes).json()["id"]
    body = client.get(f"/api/files/{fid}/features/").json()
    first = body["features"][0]
    assert first["geometry"]["type"] == "Polygon"
    assert first["crs"] == "EPSG:4326"
    assert "name" in first["properties"]


def test_pagination(client, kml_bytes):
    fid = upload(client, "s.kml", kml_bytes).json()["id"]
    m = client.get(f"/api/files/{fid}/measurements/?limit=2&offset=1").json()
    assert [f["index"] for f in m["features"]] == [1, 2]
    assert m["total_features"] == 5


def test_upload_shapefile_zip(client):
    r = upload(client, "parcels.zip", make_shapefile_zip())
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert r.json()["crs"] == "EPSG:4326"
    feats = client.get(f"/api/files/{fid}/measurements/").json()["features"]
    assert len(feats) == 2
    assert feats[0]["properties"]["NAME"] == "Parcel 1"
    assert 1.22e6 < feats[0]["measurement"]["area_sq_m"] < 1.24e6


def test_shapefile_without_prj_fails_then_succeeds_with_crs_override(client):
    data = make_shapefile_zip(with_prj=False)
    r = upload(client, "parcels.zip", data)
    assert r.status_code == 422
    failed_id = r.json()["file_id"]
    info = client.get(f"/api/files/{failed_id}/").json()
    assert info["status"] == "FAILED" and ".prj" in info["error"]
    assert client.get(f"/api/files/{failed_id}/measurements/").status_code == 409

    ok = upload(client, "parcels.zip", data, crs="EPSG:4326")
    assert ok.status_code == 201


def test_unsupported_extension(client):
    assert upload(client, "notes.txt", b"hello").status_code == 415


def test_corrupt_zip_is_422_and_recorded(client):
    r = upload(client, "bad.zip", b"not a zip")
    assert r.status_code == 422 and "file_id" in r.json()


def test_corrupt_kml_is_422(client):
    assert upload(client, "bad.kml", b"<kml><broken").status_code == 422


def test_unknown_id_is_404(client):
    assert client.get("/api/files/nope/").status_code == 404
    assert client.get("/api/files/nope/measurements/").status_code == 404


def test_upload_too_large(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    s = Settings(db_path=str(tmp_path / "t.db"), max_upload_bytes=10)
    with TestClient(create_app(s)) as c:
        assert upload(c, "a.kml", b"x" * 100).status_code == 413
