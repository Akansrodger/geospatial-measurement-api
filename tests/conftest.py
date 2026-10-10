import io
import os
import tempfile
import zipfile

import pytest

SAMPLE_KML = os.path.join(os.path.dirname(__file__), "..", "samples", "sample.kml")

WGS84_ESRI_WKT = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


@pytest.fixture
def kml_bytes() -> bytes:
    with open(SAMPLE_KML, "rb") as f:
        return f.read()


def make_shapefile_zip(with_prj: bool = True) -> bytes:
    import shapefile

    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "parcels")
        with shapefile.Writer(base) as w:
            w.field("NAME", "C", 40)
            w.poly([[[3.000, 0.000], [3.000, 0.010], [3.010, 0.010], [3.010, 0.000], [3.000, 0.000]]])
            w.record("Parcel 1")
            w.poly([[[10, 60], [10, 61], [11, 61], [11, 60], [10, 60]]])
            w.record("Parcel 2")
        exts = [".shp", ".shx", ".dbf"]
        if with_prj:
            with open(base + ".prj", "w") as f:
                f.write(WGS84_ESRI_WKT)
            exts.append(".prj")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for ext in exts:
                z.write(base + ext, "parcels" + ext)
        return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    settings = Settings(db_path=str(tmp_path / "test.db"))
    with TestClient(create_app(settings)) as c:
        yield c
