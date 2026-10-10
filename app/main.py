"""FastAPI application factory.

Run with:  uvicorn app.main:create_app --factory --reload
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import files
from app.config import Settings
from app.errors import GeoFileError
from app.repository import FileRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or Settings.from_env()

    app = FastAPI(
        title="Geospatial File Measurement API",
        version="1.0.0",
        description="Upload a zipped Shapefile or KML and get per-feature area/length measurements.",
    )
    app.state.settings = settings
    app.state.repo = FileRepository(settings.db_path)

    @app.exception_handler(GeoFileError)
    async def geo_error_handler(_: Request, exc: GeoFileError) -> JSONResponse:
        body: dict[str, str] = {"detail": exc.message}
        if exc.file_id:
            body["file_id"] = exc.file_id
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(files.router, prefix="/api")
    return app
