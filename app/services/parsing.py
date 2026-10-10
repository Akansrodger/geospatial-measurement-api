"""Dispatch an upload to the right parser based on file extension."""
from __future__ import annotations

from app.errors import UnsupportedFileTypeError
from app.models import ParsedFile
from app.services.parsers.kml import parse_kml
from app.services.parsers.shapefile_zip import parse_shapefile_zip

SUPPORTED_EXTENSIONS = (".zip", ".kml")


def parse_file(
    extension: str, content: bytes, max_uncompressed: int, crs_override: str | None = None
) -> ParsedFile:
    if extension == ".kml":
        return parse_kml(content)
    if extension == ".zip":
        return parse_shapefile_zip(content, max_uncompressed, crs_override)
    raise UnsupportedFileTypeError(
        f"Unsupported file type '{extension}'. Upload a .zip (Shapefile) or a .kml file."
    )
