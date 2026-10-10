"""SQLite persistence (stdlib only). Swap for PostgreSQL/PostGIS without touching callers."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.models import FileRecord, StoredFeature

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id            TEXT PRIMARY KEY,
    filename      TEXT NOT NULL,
    status        TEXT NOT NULL,
    crs           TEXT,
    feature_count INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS features (
    file_id            TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    idx                INTEGER NOT NULL,
    geometry_type      TEXT NOT NULL,
    geometry           TEXT,
    crs                TEXT NOT NULL,
    properties         TEXT NOT NULL,
    measurement        TEXT NOT NULL,
    measurement_status TEXT NOT NULL,
    area_sq_m          REAL,
    length_m           REAL,
    PRIMARY KEY (file_id, idx)
);
"""


class FileRepository:
    def __init__(self, db_path: str):
        directory = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(directory, exist_ok=True)
        self._db_path = db_path
        with self._tx() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:  # commit on success, rollback on error
                yield conn
        finally:
            conn.close()

    # ---- writes -----------------------------------------------------------
    def create_failed(self, filename: str, error: str) -> FileRecord:
        record_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO files (id, filename, status, crs, feature_count, error, created_at) "
                "VALUES (?, ?, 'FAILED', NULL, 0, ?, ?)",
                (record_id, filename, error, created),
            )
        return FileRecord(record_id, filename, "FAILED", None, 0, error, created)

    def create_completed(
        self, filename: str, crs: str, features: list[StoredFeature]
    ) -> FileRecord:
        record_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                record_id,
                f.index,
                f.geometry_type,
                json.dumps(f.geometry) if f.geometry is not None else None,
                f.crs,
                json.dumps(f.properties),
                json.dumps(f.measurement),
                f.measurement["status"],
                f.measurement.get("area_sq_m"),
                f.measurement.get("length_m"),
            )
            for f in features
        ]
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO files (id, filename, status, crs, feature_count, error, created_at) "
                "VALUES (?, ?, 'COMPLETED', ?, ?, NULL, ?)",
                (record_id, filename, crs, len(features), created),
            )
            conn.executemany(
                "INSERT INTO features (file_id, idx, geometry_type, geometry, crs, properties, "
                "measurement, measurement_status, area_sq_m, length_m) VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        counts: dict[str, int] = {}
        for f in features:
            counts[f.geometry_type] = counts.get(f.geometry_type, 0) + 1
        return FileRecord(record_id, filename, "COMPLETED", crs, len(features), None, created, counts)

    # ---- reads ------------------------------------------------------------
    def get(self, file_id: str) -> FileRecord | None:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            if row is None:
                return None
            counts = {
                r["geometry_type"]: r["n"]
                for r in conn.execute(
                    "SELECT geometry_type, COUNT(*) AS n FROM features WHERE file_id = ? "
                    "GROUP BY geometry_type",
                    (file_id,),
                )
            }
        return FileRecord(
            id=row["id"], filename=row["filename"], status=row["status"], crs=row["crs"],
            feature_count=row["feature_count"], error=row["error"], created_at=row["created_at"],
            geometry_type_counts=counts,
        )

    def list_features(self, file_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM features WHERE file_id = ? ORDER BY idx LIMIT ? OFFSET ?",
                (file_id, limit, offset),
            ).fetchall()
        return [
            {
                "index": r["idx"],
                "geometry_type": r["geometry_type"],
                "geometry": json.loads(r["geometry"]) if r["geometry"] else None,
                "crs": r["crs"],
                "properties": json.loads(r["properties"]),
                "measurement": json.loads(r["measurement"]),
            }
            for r in rows
        ]

    def summary(self, file_id: str) -> dict[str, Any]:
        with self._tx() as conn:
            totals = conn.execute(
                "SELECT COALESCE(SUM(area_sq_m), 0) AS area, COALESCE(SUM(length_m), 0) AS length "
                "FROM features WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            statuses = {
                r["measurement_status"]: r["n"]
                for r in conn.execute(
                    "SELECT measurement_status, COUNT(*) AS n FROM features WHERE file_id = ? "
                    "GROUP BY measurement_status",
                    (file_id,),
                )
            }
        area = round(totals["area"], 3)
        return {
            "total_area_sq_m": area,
            "total_area_hectares": round(area / 10_000.0, 4),
            "total_length_m": round(totals["length"], 3),
            "status_counts": statuses,
        }
