"""Application settings, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/geo.db"
    max_upload_bytes: int = 50 * 1024 * 1024  # compressed upload size cap
    max_uncompressed_bytes: int = 200 * 1024 * 1024  # zip-bomb guard

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=os.getenv("GEO_DB_PATH", "data/geo.db"),
            max_upload_bytes=int(os.getenv("GEO_MAX_UPLOAD_MB", "50")) * 1024 * 1024,
            max_uncompressed_bytes=int(os.getenv("GEO_MAX_UNCOMPRESSED_MB", "200")) * 1024 * 1024,
        )
