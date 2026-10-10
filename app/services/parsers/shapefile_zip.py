"""Shapefile (zipped) parser using pyshp - pure Python, no GDAL required."""
from __future__ import annotations

import datetime
import decimal
import io
import logging
import posixpath
import zipfile
from collections import defaultdict
from typing import Any

import shapefile  # pyshp

from app.errors import InvalidFileError
from app.models import ParsedFile, RawFeature

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _group_members(zf: zipfile.ZipFile, max_uncompressed: int) -> dict[str, dict[str, zipfile.ZipInfo]]:
    infos = [
        i for i in zf.infolist()
        if not i.is_dir()
        and not i.filename.startswith("__MACOSX/")
        and not posixpath.basename(i.filename).startswith("._")
    ]
    if sum(i.file_size for i in infos) > max_uncompressed:
        raise InvalidFileError("Zip archive is too large when uncompressed")
    groups: dict[str, dict[str, zipfile.ZipInfo]] = defaultdict(dict)
    for info in infos:
        stem, ext = posixpath.splitext(info.filename.lower())
        groups[stem][ext] = info
    return groups


def parse_shapefile_zip(
    content: bytes, max_uncompressed: int, crs_override: str | None = None
) -> ParsedFile:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise InvalidFileError("File is not a valid zip archive") from exc

    with zf:
        groups = _group_members(zf, max_uncompressed)
        stems = [s for s, exts in groups.items() if ".shp" in exts]
        if not stems:
            raise InvalidFileError("Zip archive does not contain a .shp file")
        if len(stems) > 1:
            raise InvalidFileError(
                f"Zip contains {len(stems)} shapefiles; upload one shapefile per zip"
            )
        members = groups[stems[0]]
        missing = [e for e in (".shx", ".dbf") if e not in members]
        if missing:
            raise InvalidFileError(f"Shapefile is missing required component(s): {', '.join(missing)}")

        crs_definition = crs_override
        if crs_definition is None:
            if ".prj" not in members:
                raise InvalidFileError(
                    "Shapefile has no .prj file, so its CRS is unknown. Include the .prj "
                    "or pass the 'crs' form field (e.g. EPSG:4326)."
                )
            crs_definition = zf.read(members[".prj"]).decode("utf-8", errors="replace").strip()

        encoding = "utf-8"
        if ".cpg" in members:
            encoding = zf.read(members[".cpg"]).decode("ascii", errors="ignore").strip() or "utf-8"

        shp = io.BytesIO(zf.read(members[".shp"]))
        shx = io.BytesIO(zf.read(members[".shx"]))
        dbf = io.BytesIO(zf.read(members[".dbf"]))

    features: list[RawFeature] = []
    try:
        reader = shapefile.Reader(shp=shp, shx=shx, dbf=dbf, encoding=encoding, encodingErrors="replace")
        for index, sr in enumerate(reader.iterShapeRecords()):
            warnings: list[str] = []
            geometry = None
            if sr.shape.shapeType == shapefile.NULL:
                warnings.append("Null shape (no geometry)")
            else:
                try:
                    geometry = dict(sr.shape.__geo_interface__)
                except Exception as exc:
                    warnings.append(f"Could not read geometry: {exc}")
            properties = {k: _json_safe(v) for k, v in sr.record.as_dict().items()}
            features.append(RawFeature(index, geometry, properties, warnings))
    except InvalidFileError:
        raise
    except Exception as exc:
        logger.exception("Failed reading shapefile")
        raise InvalidFileError(f"Could not read shapefile: {exc}") from exc

    return ParsedFile(crs_definition=crs_definition, features=features)
