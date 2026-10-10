"""Create samples/sample_shapefile.zip (a WGS84 polygon layer with two parcels).

Usage:  python scripts/make_sample_shapefile.py
"""
import os
import tempfile
import zipfile

import shapefile  # pyshp

WGS84_ESRI_WKT = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def build(out_zip: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "parcels")
        with shapefile.Writer(base) as w:
            w.field("NAME", "C", 40)
            w.field("LANDUSE", "C", 20)
            w.poly([[[3.000, 0.000], [3.000, 0.010], [3.010, 0.010], [3.010, 0.000], [3.000, 0.000]]])
            w.record("Parcel 1", "residential")
            w.poly([[[10, 60], [10, 61], [11, 61], [11, 60], [10, 60]]])
            w.record("Parcel 2", "forest")
        with open(base + ".prj", "w") as f:
            f.write(WGS84_ESRI_WKT)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for ext in (".shp", ".shx", ".dbf", ".prj"):
                z.write(base + ext, "parcels" + ext)


if __name__ == "__main__":
    target = os.path.join(os.path.dirname(__file__), "..", "samples", "sample_shapefile.zip")
    build(os.path.abspath(target))
    print("wrote", os.path.abspath(target))
