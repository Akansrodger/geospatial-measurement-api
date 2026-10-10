"""HTTP routes for /api/files."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import FileTooLargeError
from app.models import FileRecord
from app.repository import FileRepository
from app.schemas import (
    FeaturesResponse,
    FileInfo,
    MeasurementItem,
    MeasurementsResponse,
    MeasurementSummary,
)
from app.services.processor import process_upload

router = APIRouter(prefix="/files", tags=["files"])


def get_repo(request: Request) -> FileRepository:
    return request.app.state.repo


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _info(record: FileRecord) -> FileInfo:
    return FileInfo(**record.__dict__)


def _completed_record(file_id: str, repo: FileRepository) -> FileRecord:
    record = repo.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if record.status != "COMPLETED":
        raise HTTPException(
            status_code=409, detail=f"File processing failed: {record.error}"
        )
    return record


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/", response_model=FileInfo, status_code=201, summary="Upload and process a file")
async def upload_file(
    file: UploadFile = File(..., description="A .zip containing a Shapefile, or a .kml file"),
    crs: str | None = Form(
        None,
        description="Optional CRS override (e.g. EPSG:32643). Only needed for shapefiles without a .prj.",
    ),
    repo: FileRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
) -> FileInfo:
    content = await _read_limited(file, settings.max_upload_bytes)
    record = await run_in_threadpool(
        process_upload, file.filename or "upload", content, repo, settings, crs or None
    )
    return _info(record)


@router.get("/{file_id}/", response_model=FileInfo, summary="Get file information")
def get_file(file_id: str, repo: FileRepository = Depends(get_repo)) -> FileInfo:
    record = repo.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    return _info(record)


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get measurements for every feature",
)
def get_measurements(
    file_id: str,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    repo: FileRepository = Depends(get_repo),
) -> MeasurementsResponse:
    record = _completed_record(file_id, repo)
    rows = repo.list_features(file_id, limit, offset)
    items = [
        MeasurementItem(
            index=r["index"], geometry_type=r["geometry_type"], crs=r["crs"],
            properties=r["properties"], measurement=r["measurement"],
        )
        for r in rows
    ]
    return MeasurementsResponse(
        file_id=file_id, crs=record.crs, total_features=record.feature_count,
        limit=limit, offset=offset,
        summary=MeasurementSummary(**repo.summary(file_id)), features=items,
    )


@router.get(
    "/{file_id}/features/",
    response_model=FeaturesResponse,
    summary="Get full features (geometry, CRS, properties, measurement)",
)
def get_features(
    file_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: FileRepository = Depends(get_repo),
) -> FeaturesResponse:
    record = _completed_record(file_id, repo)
    return FeaturesResponse(
        file_id=file_id, crs=record.crs, total_features=record.feature_count,
        limit=limit, offset=offset, features=repo.list_features(file_id, limit, offset),
    )
