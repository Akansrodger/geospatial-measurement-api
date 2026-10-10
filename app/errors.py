"""Domain errors. Each carries the HTTP status it should be reported with."""
from __future__ import annotations


class GeoFileError(Exception):
    status_code = 400

    def __init__(self, message: str, file_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.file_id = file_id


class UnsupportedFileTypeError(GeoFileError):
    status_code = 415


class FileTooLargeError(GeoFileError):
    status_code = 413


class InvalidFileError(GeoFileError):
    """The upload is the right type but its content cannot be used."""

    status_code = 422
