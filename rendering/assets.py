"""Runtime asset cache for remote Marvel Rivals images.

The cache is deliberately independent from the HTML renderer.  Callers may
ask for a cached hero path, provide a newly observed image URL for lazy
loading, or warm a batch of ``(hero_id, image_url)`` pairs in the background.
Network and cache failures return ``None``/partial results so CSS-only pages
remain usable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from base64 import b64encode
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


MANIFEST_VERSION = 1
DEFAULT_REFRESH_DAYS = 30.0
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_IMAGE_BYTES = 8 * 1024 * 1024
HERO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_IMAGE_SIGNATURES = (
    ("image/png", ".png", lambda payload: payload.startswith(b"\x89PNG\r\n\x1a\n")),
    ("image/jpeg", ".jpg", lambda payload: payload.startswith(b"\xff\xd8\xff")),
    ("image/gif", ".gif", lambda payload: payload.startswith((b"GIF87a", b"GIF89a"))),
    (
        "image/webp",
        ".webp",
        lambda payload: payload[:4] == b"RIFF" and payload[8:12] == b"WEBP",
    ),
    (
        "image/avif",
        ".avif",
        lambda payload: len(payload) >= 12 and payload[4:8] == b"ftyp" and b"avif" in payload[8:32],
    ),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _image_signature(payload: bytes) -> tuple[str, str] | None:
    for content_type, extension, matches in _IMAGE_SIGNATURES:
        if matches(payload):
            return content_type, extension
    return None


def _valid_image_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@dataclass(frozen=True, slots=True)
class AssetRecord:
    """The stable metadata stored for one cached hero image."""

    hero_id: str
    file: str
    source_url: str
    content_type: str
    fetched_at: str
    etag: str | None = None
    last_modified: str | None = None
    sha256: str | None = None

    @classmethod
    def from_mapping(cls, hero_id: str, value: Mapping[str, Any]) -> AssetRecord | None:
        file = value.get("file")
        source_url = value.get("source_url")
        content_type = value.get("content_type")
        fetched_at = value.get("fetched_at")
        if not all(isinstance(item, str) and item for item in (file, source_url, content_type, fetched_at)):
            return None
        return cls(
            hero_id=hero_id,
            file=file,
            source_url=source_url,
            content_type=content_type,
            fetched_at=fetched_at,
            etag=value.get("etag") if isinstance(value.get("etag"), str) else None,
            last_modified=(
                value.get("last_modified")
                if isinstance(value.get("last_modified"), str)
                else None
            ),
            sha256=value.get("sha256") if isinstance(value.get("sha256"), str) else None,
        )

    def as_dict(self) -> dict[str, str]:
        value = {
            "hero_id": self.hero_id,
            "file": self.file,
            "source_url": self.source_url,
            "content_type": self.content_type,
            "fetched_at": self.fetched_at,
        }
        if self.etag:
            value["etag"] = self.etag
        if self.last_modified:
            value["last_modified"] = self.last_modified
        if self.sha256:
            value["sha256"] = self.sha256
        return value


class AssetManager:
    """Manage a non-shipped, cache-aside image store.

    ``root`` should point to AstrBot's plugin data directory, not the source
    tree.  ``get_hero_image`` can be used without a URL to read an existing
    cache entry.  When a URL is available, it performs lazy loading and uses a
    30-day revalidation window by default.  A stale image remains usable if a
    refresh fails.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        refresh_days: float = DEFAULT_REFRESH_DAYS,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        verify_ssl: bool | str = True,
        proxy: str | None = None,
        trust_env: bool = False,
    ):
        self.root = Path(root)
        self.heroes_root = self.root / "heroes"
        self.manifest_path = self.root / "manifest.json"
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.refresh_after = timedelta(days=max(0.0, float(refresh_days)))
        self.max_concurrency = max(1, int(max_concurrency))
        self._client = client
        self._client_options = {
            "timeout": self.timeout_seconds,
            "follow_redirects": True,
            "verify": verify_ssl,
            "proxy": proxy,
            "trust_env": trust_env,
        }
        self._hero_locks: dict[str, asyncio.Lock] = {}
        self._manifest_lock: asyncio.Lock | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self.available = True
        self._records: dict[str, AssetRecord] = {}
        try:
            self.heroes_root.mkdir(parents=True, exist_ok=True)
            self._records = self._load_manifest()
            if not self.manifest_path.exists():
                self.manifest_path.write_text(
                    json.dumps({"version": MANIFEST_VERSION, "heroes": {}}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        except OSError:
            # The cache is an optimization.  A read-only or unavailable data
            # directory must not prevent the plugin from loading.
            self.available = False

    def _load_manifest(self) -> dict[str, AssetRecord]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if not isinstance(value, dict) or value.get("version") != MANIFEST_VERSION:
            return {}
        heroes = value.get("heroes")
        if not isinstance(heroes, Mapping):
            return {}
        records = {}
        for hero_id, record in heroes.items():
            normalized = self._normalize_hero_id(hero_id)
            if normalized and isinstance(record, Mapping):
                parsed = AssetRecord.from_mapping(normalized, record)
                if parsed:
                    records[normalized] = parsed
        return records

    @staticmethod
    def _normalize_hero_id(hero_id: Any) -> str | None:
        value = str(hero_id).strip()
        return value if HERO_ID_RE.fullmatch(value) else None

    def _hero_lock(self, hero_id: str) -> asyncio.Lock:
        lock = self._hero_locks.get(hero_id)
        if lock is None:
            lock = asyncio.Lock()
            self._hero_locks[hero_id] = lock
        return lock

    def _get_manifest_lock(self) -> asyncio.Lock:
        if self._manifest_lock is None:
            self._manifest_lock = asyncio.Lock()
        return self._manifest_lock

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    def _record_path(self, record: AssetRecord | None) -> Path | None:
        if record is None:
            return None
        try:
            root = self.root.resolve()
            candidate = (self.root / record.file).resolve()
        except OSError:
            return None
        if candidate != root and root not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None

    def _is_fresh(self, record: AssetRecord) -> bool:
        fetched_at = _timestamp(record.fetched_at)
        return fetched_at is not None and _now() - fetched_at < self.refresh_after

    async def _persist_record(self, record: AssetRecord) -> None:
        async with self._get_manifest_lock():
            self._records[record.hero_id] = record
            payload = {
                "version": MANIFEST_VERSION,
                "heroes": {
                    hero_id: item.as_dict()
                    for hero_id, item in sorted(self._records.items())
                },
            }
            temporary = self.manifest_path.with_name(f".{self.manifest_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, self.manifest_path)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

    async def get_hero_image(self, hero_id: str, image_url: str | None = None) -> str | None:
        """Return a local image path, lazily fetching it when ``image_url`` is known."""

        normalized = self._normalize_hero_id(hero_id)
        if not normalized or not self.available:
            return None
        if image_url is not None:
            image_url = str(image_url).strip()
            if not _valid_image_url(image_url):
                image_url = None
        async with self._hero_lock(normalized):
            record = self._records.get(normalized)
            cached_path = self._record_path(record)
            if cached_path and (image_url is None or (record and record.source_url == image_url and self._is_fresh(record))):
                return str(cached_path)
            if image_url is None:
                # A stale cached file is still safer than making the renderer
                # depend on a URL that was not present in the current response.
                return str(cached_path) if cached_path else None
            refreshed = await self._refresh_locked(normalized, image_url, record, cached_path)
            return str(refreshed) if refreshed else None

    async def refresh_hero(self, hero_id: str, image_url: str) -> str | None:
        """Force one hero URL through the cache; failures keep an old file usable."""

        normalized = self._normalize_hero_id(hero_id)
        image_url = str(image_url).strip()
        if not normalized or not self.available or not _valid_image_url(image_url):
            return None
        async with self._hero_lock(normalized):
            record = self._records.get(normalized)
            cached_path = self._record_path(record)
            refreshed = await self._refresh_locked(normalized, image_url, record, cached_path)
            return str(refreshed) if refreshed else None

    async def _refresh_locked(
        self,
        hero_id: str,
        image_url: str,
        record: AssetRecord | None,
        cached_path: Path | None,
    ) -> Path | None:
        try:
            async with self._get_semaphore():
                response = await self._fetch(image_url, record if record and record.source_url == image_url else None)
            if response[3]:
                if not cached_path or not record:
                    return None
                refreshed_record = replace(
                    record,
                    fetched_at=_now().isoformat(),
                    etag=response[2].get("etag") or record.etag,
                    last_modified=response[2].get("last-modified") or record.last_modified,
                )
                await self._persist_record(refreshed_record)
                return cached_path
            payload, content_type, headers, _ = response
            if payload is None or content_type is None or len(payload) > MAX_IMAGE_BYTES:
                return None
            signature = _image_signature(payload)
            if signature is None:
                return None
            detected_type, extension = signature
            target = self.heroes_root / f"{hero_id}{extension}"
            temporary = self.heroes_root / f".{target.name}.{uuid.uuid4().hex}.tmp"
            try:
                temporary.write_bytes(payload)
                os.replace(temporary, target)
                new_record = AssetRecord(
                    hero_id=hero_id,
                    file=target.relative_to(self.root).as_posix(),
                    source_url=image_url,
                    content_type=detected_type,
                    fetched_at=_now().isoformat(),
                    etag=headers.get("etag"),
                    last_modified=headers.get("last-modified"),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
                await self._persist_record(new_record)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
            old_path = self._record_path(record)
            if old_path and old_path != target:
                try:
                    old_path.unlink()
                except OSError:
                    pass
            return target
        except Exception:
            return cached_path

    async def _fetch(
        self,
        image_url: str,
        record: AssetRecord | None,
    ) -> tuple[bytes | None, str | None, httpx.Headers, bool]:
        headers: dict[str, str] = {}
        if record:
            if record.etag:
                headers["If-None-Match"] = record.etag
            if record.last_modified:
                headers["If-Modified-Since"] = record.last_modified
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(**self._client_options)
        try:
            response = await client.get(image_url, headers=headers)
            if response.status_code == 304:
                return None, None, response.headers, True
            response.raise_for_status()
            payload = response.content
            if not payload:
                return None, None, response.headers, False
            signature = _image_signature(payload)
            content_type = signature[0] if signature else None
            header_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type is None and header_type.startswith("image/"):
                # Do not trust a MIME header without a recognizable image
                # signature; this prevents caching an HTML error page.
                return None, None, response.headers, False
            return payload, content_type, response.headers, False
        finally:
            if own_client:
                await client.aclose()

    async def warmup(
        self,
        heroes: Mapping[str, str] | Iterable[tuple[str, str]] | Iterable[Mapping[str, str]],
    ) -> dict[str, str | None]:
        """Best-effort prefetch for known ``hero_id -> image_url`` pairs."""

        items: list[tuple[str, str]] = []
        source = heroes.items() if isinstance(heroes, Mapping) else heroes
        for item in source:
            if isinstance(item, Mapping):
                hero_id = item.get("hero_id", item.get("id"))
                image_url = item.get("image_url", item.get("url"))
            else:
                try:
                    hero_id, image_url = item
                except (TypeError, ValueError):
                    continue
            if hero_id is not None and image_url is not None:
                items.append((str(hero_id), str(image_url)))

        async def load(hero_id: str, image_url: str) -> tuple[str, str | None]:
            try:
                return hero_id, await self.get_hero_image(hero_id, image_url)
            except Exception:
                return hero_id, None

        results = await asyncio.gather(*(load(hero_id, url) for hero_id, url in items))
        return dict(results)

    async def refresh_all(
        self,
        heroes: Mapping[str, str] | Iterable[tuple[str, str]] | Iterable[Mapping[str, str]],
    ) -> dict[str, str | None]:
        """Administrative alias for an explicit best-effort full refresh."""

        return await self.warmup(heroes)

    def to_data_uri(self, image_path: str | Path) -> str | None:
        """Read a cached file as a browser-safe Data URI for the renderer."""

        if not self.available:
            return None
        path = Path(image_path)
        if not path.is_absolute():
            path = self.root / path
        try:
            root = self.root.resolve()
            path = path.resolve()
            if path != root and root not in path.parents:
                return None
            payload = path.read_bytes()
        except OSError:
            return None
        signature = _image_signature(payload)
        if signature is None:
            return None
        content_type = signature[0]
        return f"data:{content_type};base64," + b64encode(payload).decode("ascii")

    async def get_hero_data_uri(self, hero_id: str, image_url: str | None = None) -> str | None:
        path = await self.get_hero_image(hero_id, image_url)
        return self.to_data_uri(path) if path else None

    def status(self) -> dict[str, Any]:
        """Return a safe, non-secret cache summary for diagnostics."""

        total_bytes = 0
        cached = 0
        missing = 0
        stale = 0
        for record in self._records.values():
            path = self._record_path(record)
            if not path:
                missing += 1
                continue
            cached += 1
            try:
                total_bytes += path.stat().st_size
            except OSError:
                missing += 1
            if not self._is_fresh(record):
                stale += 1
        return {
            "available": self.available,
            "root": str(self.root),
            "manifest": str(self.manifest_path),
            "records": len(self._records),
            "cached": cached,
            "missing": missing,
            "stale": stale,
            "bytes": total_bytes,
        }

    def clear_cache(self, hero_id: str | None = None) -> None:
        """Clear one hero or all runtime hero files; intended for administration."""

        if not self.available:
            return
        normalized = self._normalize_hero_id(hero_id) if hero_id is not None else None
        if hero_id is not None and not normalized:
            return
        records = (
            {normalized: self._records.get(normalized)}
            if normalized
            else dict(self._records)
        )
        for record in records.values():
            path = self._record_path(record)
            if path:
                try:
                    path.unlink()
                except OSError:
                    pass
        if normalized:
            self._records.pop(normalized, None)
        else:
            for path in self.heroes_root.iterdir():
                if path.is_file():
                    try:
                        path.unlink()
                    except OSError:
                        pass
            self._records.clear()
        payload = {"version": MANIFEST_VERSION, "heroes": {hero: item.as_dict() for hero, item in self._records.items()}}
        temporary = self.manifest_path.with_name(f".{self.manifest_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.manifest_path)
        except OSError:
            pass
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


__all__ = ["AssetManager", "AssetRecord", "MANIFEST_VERSION"]
