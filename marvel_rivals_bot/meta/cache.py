"""Disk cache primitives for the global Marvel Rivals Meta data."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .errors import MetaCacheError


logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_SEASON_SAFE_CHARS = re.compile(r"[^\w.-]+", re.UNICODE)


@dataclass(slots=True)
class CacheRecord:
    """A validated cached season payload and its freshness state."""

    payload: dict[str, Any]
    source: str
    season: str
    source_timestamp: int | float | str | None
    fetched_at: datetime
    stale: bool = False


def _normalize_season(season: str) -> str:
    """Return a filename-safe, stable cache key for a season."""

    if not isinstance(season, str):
        raise TypeError("season must be a string")
    normalized = unicodedata.normalize("NFKC", season).strip()
    normalized = _SEASON_SAFE_CHARS.sub("_", normalized)
    normalized = normalized.strip("._")
    if not normalized:
        raise ValueError("season must contain at least one safe character")
    return normalized


def _serialize_datetime(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("fetched_at must be a datetime")
    return value.isoformat()


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("fetched_at is not an ISO datetime")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("fetched_at is not an ISO datetime") from exc


def _age_seconds(now: datetime, fetched_at: datetime) -> float:
    """Calculate age while supporting both naive and timezone-aware clocks."""

    if now.tzinfo is None and fetched_at.tzinfo is not None:
        fetched_at = fetched_at.replace(tzinfo=None)
    elif now.tzinfo is not None and fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=now.tzinfo)
    return (now - fetched_at).total_seconds()


class MetaDiskCache:
    """Persist one season-wide Meta response per JSON file.

    ``stale_seconds`` is the maximum total age accepted by :meth:`load`, not
    an additional grace period after ``fresh_seconds``.
    """

    def __init__(
        self,
        root: Path,
        fresh_seconds: float = 600,
        stale_seconds: float = 86400,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if fresh_seconds < 0 or stale_seconds < 0:
            raise ValueError("cache durations must be non-negative")
        if stale_seconds < fresh_seconds:
            raise ValueError("stale_seconds must be at least fresh_seconds")
        self.root = Path(root)
        self.fresh_seconds = fresh_seconds
        self.stale_seconds = stale_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def cache_dir(self) -> Path:
        return self.root / "meta" / "cache" / "hero_stats"

    def _path_for(self, season: str) -> Path:
        return self.cache_dir / f"season_{_normalize_season(season)}.json"

    def load(self, season: str, now: datetime | None = None) -> CacheRecord | None:
        """Load a fresh or usable stale record, or return ``None``."""

        normalized_season = _normalize_season(season)
        path = self._path_for(normalized_season)
        if not path.is_file():
            logger.info("Meta source=unknown season=%s cache=miss", normalized_season)
            return None

        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            logger.warning("Discarding damaged Meta cache %s: %s", path, exc)
            return None

        try:
            if not isinstance(envelope, dict):
                raise ValueError("envelope is not an object")
            if envelope.get("schema_version") != SCHEMA_VERSION:
                logger.warning(
                    "Discarding Meta cache with schema version %r at %s",
                    envelope.get("schema_version"),
                    path,
                )
                return None
            if envelope.get("season") != normalized_season:
                raise ValueError("season does not match cache key")
            payload = envelope["payload"]
            source = envelope["source"]
            source_timestamp = envelope.get("source_timestamp")
            fetched_at = _parse_datetime(envelope["fetched_at"])
            if not isinstance(payload, dict):
                raise ValueError("payload is not an object")
            if not isinstance(source, str):
                raise ValueError("source is not a string")
            if source_timestamp is not None and not isinstance(
                source_timestamp, (int, float, str)
            ):
                raise ValueError("source_timestamp has an unsupported type")
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Discarding damaged Meta cache %s: %s", path, exc)
            return None

        current_time = now if now is not None else self.clock()
        age = _age_seconds(current_time, fetched_at)
        if age > self.stale_seconds:
            logger.info("Meta source=%s season=%s cache=expired", source, normalized_season)
            return None
        state = "stale" if age > self.fresh_seconds else "fresh"
        logger.info("Meta source=%s season=%s cache=%s", source, normalized_season, state)
        return CacheRecord(
            payload=payload,
            source=source,
            season=normalized_season,
            source_timestamp=source_timestamp,
            fetched_at=fetched_at,
            stale=age > self.fresh_seconds,
        )

    def save(
        self,
        season: str,
        payload: dict[str, Any],
        source: str,
        source_timestamp: int | float | str | None = None,
        fetched_at: datetime | None = None,
    ) -> None:
        """Atomically save a season payload below the configured root."""

        normalized_season = _normalize_season(season)
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        if not isinstance(source, str):
            raise TypeError("source must be a string")
        if source_timestamp is not None and not isinstance(
            source_timestamp, (int, float, str)
        ):
            raise TypeError("source_timestamp has an unsupported type")

        timestamp = fetched_at if fetched_at is not None else self.clock()
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "season": normalized_season,
            "source_timestamp": source_timestamp,
            "fetched_at": _serialize_datetime(timestamp),
            "payload": payload,
        }
        cache_dir = self.cache_dir
        path = self._path_for(normalized_season)
        temporary_path: str | None = None
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=cache_dir,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                json.dump(envelope, temporary, ensure_ascii=False, separators=(",", ":"))
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(
                "Meta source=%s season=%s cache=write_failure error=%s",
                source,
                normalized_season,
                type(exc).__name__,
            )
            raise MetaCacheError("无法写入 Meta 磁盘缓存") from exc
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
