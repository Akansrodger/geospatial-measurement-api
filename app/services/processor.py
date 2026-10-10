"""Orchestrates: validate -> parse -> resolve CRS -> measure -> persist."""
from __future__ import annotations

import posixpath

from app.config import Settings
from app.errors import GeoFileError, UnsupportedFileTypeError
from app.models import FileRecord, RawFeature, StoredFeature
from app.repository import FileRepository
from app.services.crs import crs_label, parse_crs
from app.services.measurements import measure_geometry
from app.services.parsing import SUPPORTED_EXTENSIONS, parse_file


def _to_stored(feature: RawFeature, crs, crs_name: str) -> StoredFeature:
    geometry_type = feature.geometry["type"] if feature.geometry else "None"
    measurement = measure_geometry(feature.geometry, crs, feature.warnings)
    return StoredFeature(
        index=feature.index,
        geometry_type=geometry_type,
        geometry=feature.geometry,
        crs=crs_name,
        properties=feature.properties,
        measurement=measurement,
    )


def process_upload(
    filename: str,
    content: bytes,
    repo: FileRepository,
    settings: Settings,
    crs_override: str | None = None,
) -> FileRecord:
    """Process an uploaded file and persist the outcome.

    * Unsupported extensions are rejected up front (nothing is stored).
    * Content errors are stored as a FAILED record and re-raised with its id,
      so the client can later GET the record and see why it failed.
    """
    safe_name = posixpath.basename(filename.replace("\\", "/"))[:255] or "upload"
    extension = posixpath.splitext(safe_name)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension or safe_name}'. Upload a .zip (Shapefile) or a .kml file."
        )

    try:
        parsed = parse_file(extension, content, settings.max_uncompressed_bytes, crs_override)
        crs = parse_crs(parsed.crs_definition)
        name = crs_label(crs)
        stored = [_to_stored(f, crs, name) for f in parsed.features]
    except GeoFileError as exc:
        exc.file_id = repo.create_failed(safe_name, exc.message).id
        raise

    return repo.create_completed(safe_name, name, stored)
