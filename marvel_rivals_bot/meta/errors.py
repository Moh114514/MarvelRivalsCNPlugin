from __future__ import annotations


class MetaDataSourceError(RuntimeError):
    """Base error for failures while loading a Meta data source."""


class MetaSchemaError(MetaDataSourceError):
    """Raised when an upstream Meta payload does not match the contract."""


class MetaHTTPError(MetaDataSourceError):
    """Raised for non-successful responses from a Meta provider."""

    def __init__(self, status_code: int, message: str | None = None) -> None:
        self.status_code = status_code
        super().__init__(message or f"Meta source returned HTTP {status_code}")


class MetaCacheError(RuntimeError):
    """Raised when a Meta cache cannot be read or written safely."""


class MetaQueryError(ValueError):
    """Raised when a user's Meta query cannot be normalized or fulfilled."""
